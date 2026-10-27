"""An exclusive lock on an open file, on macOS and Windows alike, and the render lock built on it.

macOS (and Linux) use flock; Windows locks one byte far past the end of the file with
msvcrt, so the file's own contents (the render lock writes the holder's pid there) stay
readable and writable by everyone. Either way the lock goes when the file is closed or
the process ends.

render_lock(folder) is the one render at a time (two voice models don't fit in 16 GB):
a render, a render-ahead (--follow) and a cache prune all take it, so none deletes or
writes a clip another is reading. The maintainer's coachmaker tools don't: run them with
no build going.

file_lock(path) guards one file's read, check and write (the pace file, the session log,
told.jsonl, builds.jsonl).
"""
import contextlib
import errno
import os
import time

FOLLOWING = "following"   # the lock holder's tag while it renders ahead (--follow)

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_FAR = 1 << 30   # Windows: the locked byte, well past anything written to the file
BUSY = (errno.EACCES, errno.EDEADLK)   # Windows: what msvcrt.locking raises while another holds the byte


def acquire(f, block=True):
    """Lock `f` exclusively. With block=False, return False at once if someone else holds it."""
    if os.name != "nt":
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | (0 if block else fcntl.LOCK_NB))
            return True
        except BlockingIOError:
            return False
    pos = f.tell()
    try:
        while True:
            f.seek(_FAR)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError as e:
                if e.errno not in BUSY:   # held by another is EACCES (or EDEADLK); anything else is a real fault
                    raise
                if not block:
                    return False
                time.sleep(0.5)
    finally:
        f.seek(pos)


_held = {}   # (lock path, thread id) -> depth, so a thread holding a file's lock can take it again


def lock_key(path):
    """One name per file, however it's spelt: links resolved and, on Windows, case and slashes folded."""
    return os.path.normcase(os.path.realpath(path))


@contextlib.contextmanager
def file_lock(path):
    """An exclusive lock beside `path` (`<path>.lock`), held while its contents are read, checked and written:
    the pace file, the session log, told.jsonl, builds.jsonl. Re-entrant within one thread (a second flock on
    a new open of the same file would wait on itself)."""
    import threading
    key = (lock_key(path), threading.get_ident())
    if _held.get(key):
        _held[key] += 1
        try:
            yield
        finally:
            _held[key] -= 1
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path + ".lock", "a") as lock:
        acquire(lock)
        _held[key] = 1
        try:
            yield
        finally:
            _held.pop(key, None)
            release(lock)


def release(f):
    if os.name != "nt":
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return
    pos = f.tell()
    try:
        f.seek(_FAR)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        f.seek(pos)


def stop_file(folder):
    """Where a build asks a render-ahead in `folder` to stop after its current clip."""
    return os.path.join(folder, ".follow.stop")


@contextlib.contextmanager
def render_lock(folder, wait_message=True, follow=False):
    """One render at a time: two voice models don't fit in 16 GB. A second render
    waits here for the first to finish, then reuses the clips it cached. A render
    running ahead (--follow) is asked to stop instead, after its current clip."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, ".render.lock")
    with open(path, "a+") as f:
        if not acquire(f, block=False):
            f.seek(0)
            holder = f.read().strip() or "unknown"
            if holder.endswith(FOLLOWING):
                open(stop_file(folder), "w").close()
                if wait_message:
                    print("Stopping the render running ahead after its current clip.", flush=True)
            elif wait_message:
                print(f"Another render is running (pid {holder}); waiting for it to finish.", flush=True)
            acquire(f)
        f.seek(0)
        f.truncate()
        f.write(f"{os.getpid()} {FOLLOWING}" if follow else str(os.getpid()))
        f.flush()
        try:
            yield
        finally:
            release(f)
