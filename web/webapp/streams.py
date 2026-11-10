"""The one listener every progress stream shares (0.77.0): a thread holding one connection that LISTENs on
job_events and wakes the streams following the job each NOTIFY names. A stream holds no connection or thread of its
own: it waits on its Sub and reads the job through the pool in short calls.

The thread starts with the first stream and stops, closing its connection, when the last one leaves. A connection
the database drops is opened again; every stream is woken meanwhile, and each stream's own status read every few
seconds covers a NOTIFY sent while none was listening.
"""
import asyncio
import sys
import threading
from typing import Any, Callable

PER_USER = 3          # streams a listener may have open; a fourth closes their oldest (the browser reconnects it)
SLICE = 0.5           # seconds the thread waits for a NOTIFY before checking it should still run
READY_WAIT = 5        # seconds subscribe waits for LISTEN to run; the stream's own status read covers a slower one
RECONNECT_WAIT = 2    # seconds between tries at a connection the database dropped


class Sub:
    """One stream's place in the hub: woken (`wait`) by a NOTIFY for its job, or when the hub lost its connection;
    `closed` once the listener opened one stream too many."""

    def __init__(self, user_id, job_id: int, loop: asyncio.AbstractEventLoop):
        self.user_id, self.job_id, self.loop = user_id, job_id, loop
        self.closed = False
        self._woken = asyncio.Event()

    def wake(self) -> None:
        """From any thread."""
        try:
            self.loop.call_soon_threadsafe(self._woken.set)
        except RuntimeError:   # its loop has closed: the stream is gone
            pass

    async def wait(self, timeout: float) -> bool:
        """Whether it was woken within `timeout` seconds."""
        try:
            await asyncio.wait_for(self._woken.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            self._woken.clear()


class Hub:
    def __init__(self, open_conn: Callable[[], Any], per_user: int = PER_USER):
        self._open = open_conn
        self._per_user = per_user
        self._lock = threading.Lock()
        self._jobs: dict[int, set[Sub]] = {}
        self._users: dict[Any, list[Sub]] = {}
        self._gen = 0                       # the running thread's; a thread whose number is past stops
        self._thread: threading.Thread | None = None
        self.listening = threading.Event()  # the current thread's LISTEN has run on a live connection
        self._closed = False                # the app has shut down: no thread starts again

    def subscribe(self, user_id, job_id: int, loop: asyncio.AbstractEventLoop) -> Sub:
        """A stream's Sub, once the hub is listening (or READY_WAIT has passed). Blocks: call it off the loop."""
        sub = Sub(user_id, job_id, loop)
        with self._lock:
            if self._closed:
                sub.closed = True
                return sub
            mine = self._users.setdefault(user_id, [])
            mine.append(sub)
            self._jobs.setdefault(job_id, set()).add(sub)
            while len(mine) > self._per_user:
                oldest = mine[0]
                self._drop(oldest)
                oldest.closed = True
                oldest.wake()
            if self._thread is None:
                self._gen += 1
                self.listening = threading.Event()
                self._thread = threading.Thread(target=self._run, args=(self._gen, self.listening), daemon=True,
                                                name="job-events")
                self._thread.start()
            ready = self.listening
        ready.wait(READY_WAIT)
        return sub

    def unsubscribe(self, sub: Sub) -> None:
        with self._lock:
            self._drop(sub)
            if not self._jobs and self._thread is not None:
                self._gen += 1   # the thread stops and closes its connection
                self._thread = None

    def close(self) -> None:
        """Stop the thread (the app's shutdown)."""
        with self._lock:
            self._closed = True
            thread, self._thread = self._thread, None
            self._gen += 1
            self._jobs.clear()
            self._users.clear()
        if thread is not None:
            thread.join(SLICE * 4)

    def _drop(self, sub: Sub) -> None:
        """Under the lock."""
        subs = self._jobs.get(sub.job_id)
        if subs is not None:
            subs.discard(sub)
            if not subs:
                del self._jobs[sub.job_id]
        mine = self._users.get(sub.user_id)
        if mine is not None and sub in mine:
            mine.remove(sub)
            if not mine:
                del self._users[sub.user_id]

    def _live(self, gen: int) -> bool:
        with self._lock:
            return gen == self._gen

    def _wake(self, job_id: int | None) -> None:
        """Wake the streams following `job_id`, or every stream (None)."""
        with self._lock:
            subs = [s for s in self._jobs.get(job_id, ())] if job_id is not None else \
                [s for group in self._jobs.values() for s in group]
        for s in subs:
            s.wake()

    def _run(self, gen: int, listening: threading.Event) -> None:
        stop = threading.Event()   # only ever waited on, for the back-off
        while self._live(gen):
            conn = None
            try:
                conn = self._open()
                conn.autocommit = True
                conn.execute("listen job_events")
                listening.set()
                while self._live(gen):
                    for n in conn.notifies(timeout=SLICE, stop_after=1):
                        try:
                            self._wake(int(n.payload))
                        except ValueError:
                            pass
            except Exception as e:  # noqa: BLE001 - only the type: the message may name the database
                listening.clear()
                if self._live(gen):
                    print(f"web: the job events listener lost the database ({type(e).__name__}); listening again",
                          file=sys.stderr, flush=True)
                    self._wake(None)   # each stream reads its job's status meanwhile
                    stop.wait(RECONNECT_WAIT)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001 - a dead connection may not close cleanly
                        pass
