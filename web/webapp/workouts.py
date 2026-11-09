"""The Logs page: the listener's logged workouts, each one's script, feedback, a rating, and delete.

Every call writes the listener's files to a temporary folder and runs the engine's `workouts` command there in
its own process (as `start.gather` does), so HARMONICFITNESS_HOME is never set in this one. A change (feedback,
a rating, a delete) comes back as the files it changed, for the caller to write back against the versions it
read. Nothing here opens a key.
"""
import json
import os
import re
import tempfile

from . import engine, folder

TIMEOUT = 60   # seconds per engine command
RATINGS = ("positive", "neutral", "negative", "none")
REF = re.compile(r"[A-Za-z0-9]{1,40}")   # a workout's build id, or its number in the list
FEEDBACK_MAX = 1000


class Refused(Exception):
    """The engine refused the request (an unknown workout, a script not kept); its message says why, and `kind`
    what the route answers: "not_found" (404) for a workout or script that isn't there, else "invalid" (400)."""

    def __init__(self, message: str, kind: str = "invalid"):
        super().__init__(message)
        self.kind = kind


NOT_FOUND = ("no logged workout", "no script")   # the engine's words for a workout or script that isn't there
SAID = (1, 64)   # the engine's exits whose last line is its reason for a person; any other is a fault of its own
DIDNT_WORK = "That didn't work. Try again in a minute."


def _run(engine_root: str, files: dict[str, bytes], argv: list[str]):
    """(the engine's result, the files it changed: path -> bytes, or None for deleted)."""
    with tempfile.TemporaryDirectory(prefix="wt-workouts-") as tmp:
        home = os.path.join(tmp, "me")
        os.mkdir(home)
        written = folder.materialize({**folder.seed(engine_root), **files}, home)
        result = engine.run(engine_root, home, argv, timeout=TIMEOUT)
        changed = folder.harvest(home, written)
    # the starter files the listener never had stay unwritten unless the command changed them
    changed = {p: b for p, b in changed.items() if not (b is None and p not in files)}
    return result, changed


def _ok(result) -> str:
    """The engine's output, or Refused: with its reason when it refused the request (exit 1 or 64), else (a crash,
    a timeout) a plain sentence, never the engine's own last line, which may be a traceback's."""
    if result.code != 0:
        if result.code not in SAID:
            raise Refused(DIDNT_WORK, "failed")
        lines = [x for x in (result.stderr or result.stdout or "").strip().splitlines() if x.strip()]
        reason = lines[-1] if lines else DIDNT_WORK
        raise Refused(reason, "not_found" if any(w in reason for w in NOT_FOUND) else "invalid")
    return result.stdout


def check_ref(ref: str) -> str:
    """One workout's build id or number. Never "all", which the engine reads as every workout."""
    if not REF.fullmatch(ref or "") or ref.lower() == "all":
        raise Refused("That isn't a workout.")
    return ref


def listing(engine_root: str, files: dict[str, bytes]) -> list[dict]:
    result, _ = _run(engine_root, files, ["workouts", "--json"])
    try:
        data = json.loads(_ok(result))
    except ValueError:
        raise Refused("The workout list couldn't be read.") from None
    rows = data.get("workouts") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def script(engine_root: str, files: dict[str, bytes], ref: str) -> str:
    result, _ = _run(engine_root, files, ["workouts", "show", check_ref(ref)])
    return _ok(result)


def add_feedback(engine_root: str, files: dict[str, bytes], ref: str, text: str) -> dict[str, bytes | None]:
    text = " ".join((text or "").split())
    if not text:
        raise Refused("Say what the feedback is.")
    if len(text) > FEEDBACK_MAX:
        raise Refused(f"Keep feedback under {FEEDBACK_MAX} characters.")
    result, changed = _run(engine_root, files, ["workouts", "feedback", check_ref(ref), "--", text])
    _ok(result)
    return changed


def rate(engine_root: str, files: dict[str, bytes], ref: str, rating: str) -> dict[str, bytes | None]:
    if rating not in RATINGS:
        raise Refused(f"A rating is one of {', '.join(RATINGS)}.")
    result, changed = _run(engine_root, files, ["workouts", "rate", check_ref(ref), rating])
    _ok(result)
    return changed


def delete(engine_root: str, files: dict[str, bytes], ref: str) -> dict[str, bytes | None]:
    """Take the workout back, files and all (its folder: draft, brief, menu, script, build record)."""
    result, changed = _run(engine_root, files, ["workouts", "delete", check_ref(ref), "--files"])
    _ok(result)
    return changed
