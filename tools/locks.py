"""An exclusive lock on an open file, on macOS and Windows alike.

macOS (and Linux) use flock; Windows locks one byte far past the end of the file with
msvcrt, so the file's own contents (render.py writes the holder's pid there) stay
readable and writable by everyone. Either way the lock goes when the file is closed or
the process ends.
"""
import os
import time

if os.name == "nt":
    import msvcrt
else:
    import fcntl

_FAR = 1 << 30   # Windows: the locked byte, well past anything written to the file


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
            except OSError:
                if not block:
                    return False
                time.sleep(0.5)
    finally:
        f.seek(pos)


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
