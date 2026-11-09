"""The worker's log lines about what went wrong: where, never what was in hand.

An exception's message may carry a listener's words, a path inside their folder or a provider's answer, so it is
never logged; its type is, and since 0.76.0 the frames it passed through (file, line and function, the code's own
names, nothing a listener wrote), so a failure in production can be found without reproducing it.
"""
import os
import sys
import traceback

FRAMES = 8   # the innermost frames kept: enough to place a failure, short enough for one line
_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _where(filename: str) -> str:
    """A frame's file as the repo names it (web/webapp/worker.py); a library's by its last two parts."""
    full = os.path.abspath(filename)
    if full.startswith(_ROOT + os.sep):
        return os.path.relpath(full, _ROOT).replace(os.sep, "/")
    return "/".join(full.replace(os.sep, "/").split("/")[-2:])


def frames(e: BaseException, limit: int = FRAMES) -> str:
    """" [file:line function > ...]", outermost first, for the innermost `limit` frames; "" with no traceback."""
    tb = traceback.extract_tb(e.__traceback__)[-limit:]
    if not tb:
        return ""
    return " [" + " > ".join(f"{_where(f.filename)}:{f.lineno} {f.name}" for f in tb) + "]"


def failure(what: str, e: BaseException) -> None:
    """`worker: <what>: <ExceptionType> [frames]` on stderr: never the exception's message."""
    print(f"worker: {what}: {type(e).__name__}{frames(e)}", file=sys.stderr, flush=True)
