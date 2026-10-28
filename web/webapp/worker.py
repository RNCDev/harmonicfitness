"""The worker: claims a job, runs its handler in a temporary folder, finishes or fails it.

    python -m webapp.worker        (with DATABASE_URL, WT_MASTER_KEY, WT_BASE_URL in the environment)

A user's files are touched only through `engine.run` in that user's own temporary folder, which is
removed whatever happens; this process never reads or writes anyone's context as the engine would.
Before importing any engine module (for the session goals and kit presets) the worker points
SWEATCAST_HOME at a folder that doesn't exist, so the engine's libraries never find a real `me/`.
"""
import datetime
import os
import shutil
import signal
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import psycopg

from . import config, db, engine, folder, jobs, store

HEARTBEAT_EVERY = 15      # seconds; jobs.reap fails a job silent for 120
IDLE_WAIT = 5             # seconds to wait for NOTIFY jobs_queued before polling again
BRIEF_TIMEOUT = 300       # seconds; the engine's cold start can be slow
NEVER_WRITE_BACK = frozenset({"health.md"})


class JobFailed(Exception):
    """A job that failed in a way the worker expected. `error` is plain, non-personal wording; `detail`
    (what the engine said, say) is stored sealed in the job's result."""

    def __init__(self, error: str, detail: dict | None = None):
        super().__init__(error)
        self.error = error
        self.detail = detail


@dataclass
class Ctx:
    conn: Any
    uk: store.UserKey
    job_id: int
    args: dict
    settings: config.Settings
    home: str

    def say(self, stage: str, **fields) -> None:
        """A job event, committed now so a stream sees it live."""
        jobs.event(self.conn, self.uk, self.job_id, {"stage": stage, **fields})


# ---- the engine's own lists -------------------------------------------------------------------

_lists: dict[str, tuple[frozenset, frozenset]] = {}


def _no_home() -> str:
    while True:
        path = os.path.join(tempfile.gettempdir(), f"wt-no-context-{uuid.uuid4().hex}")
        if not os.path.exists(path):
            return path


def engine_lists(engine_root: str) -> tuple[frozenset, frozenset]:
    """(session goals, kit presets) from the engine's tools/sessions.py and tools/catalog.py."""
    if engine_root not in _lists:
        home = os.environ.get("SWEATCAST_HOME", "")
        if not home or os.path.exists(home):
            os.environ["SWEATCAST_HOME"] = _no_home()
        tools = os.path.join(engine_root, "tools")
        if tools not in sys.path:
            sys.path.append(tools)   # after everything else, so no engine module shadows another
        import catalog
        import sessions
        for mod in (catalog, sessions):
            if os.path.dirname(os.path.abspath(mod.__file__)) != os.path.abspath(tools):
                raise RuntimeError(f"{mod.__name__} was imported from outside the engine")
        _lists[engine_root] = (frozenset(sessions.load().goals),
                               frozenset(catalog.load(extra=[]).presets))
    return _lists[engine_root]


def _uv_cache() -> None:
    """uv's cache outside every user's folder (the engine runs with HOME set to one)."""
    os.environ.setdefault("UV_CACHE_DIR", os.path.join(tempfile.gettempdir(), "wt-uv-cache"))


# ---- handlers ---------------------------------------------------------------------------------

BRIEF_ARGS = {"goal", "minutes", "preset", "today"}


def _brief_request(args: dict, settings: config.Settings) -> tuple[str, int, str, str]:
    if not isinstance(args, dict) or set(args) != BRIEF_ARGS:
        raise JobFailed("invalid request: needs goal, minutes, preset and today")
    goals, presets = engine_lists(settings.engine_root)
    goal, minutes, preset, today = args["goal"], args["minutes"], args["preset"], args["today"]
    if not isinstance(goal, str) or goal not in goals:
        raise JobFailed("invalid request: unknown goal")
    if type(minutes) is not int or not 10 <= minutes <= 60:
        raise JobFailed("invalid request: minutes must be 10..60")
    if not isinstance(preset, str) or preset not in presets:
        raise JobFailed("invalid request: unknown preset")
    try:
        day = datetime.date.fromisoformat(today) if isinstance(today, str) and len(today) == 10 else None
    except ValueError:
        day = None
    now = datetime.datetime.now(datetime.timezone.utc).date()
    if day is None or abs((day - now).days) > 1:
        raise JobFailed("invalid request: today must be a date within a day of today")
    return goal, minutes, preset, day.isoformat()


def brief(ctx: Ctx) -> dict:
    """Run `./sweatcast brief` on the user's files and save its brief and menu back."""
    goal, minutes, preset, today = _brief_request(ctx.args, ctx.settings)
    stem = f"{today}-{goal}-{minutes}"
    ctx.say("folder")
    files = store.read_all(ctx.conn, ctx.uk)
    ctx.conn.commit()
    base = {path: version for path, (version, _) in files.items()}
    written = folder.materialize({path: body for path, (_, body) in files.items()}, ctx.home)
    ctx.say("brief")
    draft = os.path.join(ctx.home, "workouts", stem, f"{stem}.draft.txt")
    r = engine.run(ctx.settings.engine_root, ctx.home,
                   ["brief", "--goal", goal, "--minutes", str(minutes), "--preset", preset,
                    "--today", today, "--save", draft], timeout=BRIEF_TIMEOUT)
    if r.code != 0:
        raise JobFailed(f"the engine stopped (exit {r.code})", {"stderr": r.stderr})
    changes = folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK)
    try:
        conflicts = store.write_back(ctx.conn, ctx.uk, changes, base)
        ctx.conn.commit()
    except Exception:
        ctx.conn.rollback()
        raise
    ctx.say("saved", conflicts=conflicts)
    return {"brief_md": r.stdout, "stem": stem}


HANDLERS: dict[str, Callable[[Ctx], dict]] = {"brief": brief}


# ---- the loop ---------------------------------------------------------------------------------

class _Heartbeat(threading.Thread):
    """Marks one job alive every HEARTBEAT_EVERY seconds, on a connection of its own."""

    def __init__(self, connect: Callable[[], Any], job_id: int):
        super().__init__(daemon=True, name=f"heartbeat-{job_id}")
        self.connect, self.job_id, self.halt = connect, job_id, threading.Event()

    def run(self) -> None:
        conn = None
        try:
            conn = self.connect()
            while not self.halt.wait(HEARTBEAT_EVERY):
                jobs.heartbeat(conn, self.job_id)
        except Exception as e:  # noqa: BLE001 - the job carries on; reap fails it if it goes silent
            print(f"worker: heartbeat for job {self.job_id} stopped: {type(e).__name__}", file=sys.stderr)
        finally:
            if conn is not None:
                conn.close()

    def stop(self) -> None:
        self.halt.set()
        self.join()


def run_one(conn, settings: config.Settings, connect: Callable[[], Any] | None = None) -> bool:
    """Reap stale jobs, claim one and run it; whether a job ran. `connect` opens the heartbeat's
    own connection (default: settings.database_url)."""
    _uv_cache()
    connect = connect or (lambda: db.connect(settings.database_url))
    jobs.reap(conn)
    job = jobs.claim(conn)
    if job is None:
        return False
    beat = _Heartbeat(connect, job.id)
    beat.start()
    home = None
    uk = None
    outcome: tuple = ("failed", "the job stopped unexpectedly", None)
    try:
        uk = store.user_key(conn, settings, job.user_id)
        args = jobs.args(conn, uk, job.id)
        conn.commit()
        home = tempfile.mkdtemp(prefix="wt-job-")
        handler = HANDLERS.get(job.kind)
        if handler is None:
            raise JobFailed("unknown job kind")
        outcome = ("done", handler(Ctx(conn=conn, uk=uk, job_id=job.id, args=args,
                                       settings=settings, home=home)))
    except JobFailed as e:
        conn.rollback()
        outcome = ("failed", e.error, e.detail)
    except Exception as e:  # noqa: BLE001 - only the type is logged: the message may be personal
        conn.rollback()
        print(f"worker: job {job.id} stopped: {type(e).__name__}", file=sys.stderr)
    finally:
        beat.stop()
        if home is not None:
            shutil.rmtree(home, ignore_errors=True)
    if outcome[0] == "done":
        jobs.finish(conn, uk, job.id, outcome[1])
    else:
        jobs.fail(conn, uk, job.id, outcome[1], outcome[2] if uk is not None else None)
    return True


def main() -> int:
    try:
        settings = config.load(os.environ)
    except config.ConfigError as e:
        print(f"worker: {e}", file=sys.stderr)
        return 2
    _uv_cache()
    engine_lists(settings.engine_root)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    conn = db.connect(settings.database_url)
    listen = psycopg.connect(settings.database_url, autocommit=True)
    listen.execute("listen jobs_queued")
    try:
        while not stopping.is_set():
            if run_one(conn, settings):
                continue
            for _ in listen.notifies(timeout=IDLE_WAIT, stop_after=1):
                pass
    finally:
        listen.close()
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
