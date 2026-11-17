"""Where a workout's files live in the context folder: one folder per workout.

    me/workouts/
      2026-10-25-strength-25/      one workout: <stem>.draft.txt, .brief.md, .menu.json, then the build's
                                   <name>.txt and <name>.build.json (and <name>.mp3 until it's delivered)
      checks/                      smoke tests and any build whose draft isn't in a workout folder
      research/                    told.jsonl, reserve/, videos/, puzzles/, and daily/ (each day's sheet and feeds)
      .audio-cache/, .logs/        rendered clips and build logs
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import paths  # noqa: E402

NOT_WORKOUTS = ("checks", "research", "drafts")


def session_dir(stem, workouts=None):
    """The folder for the workout whose draft has this stem (a path or a bare stem)."""
    return os.path.join(workouts or paths.WORKOUTS, os.path.basename(stem))


def out_dir(draft, workouts=None):
    """Where a build of `draft` writes: the draft's own workout folder, else checks/."""
    workouts = os.path.abspath(workouts or paths.WORKOUTS)
    parent = os.path.dirname(os.path.abspath(draft))
    name = os.path.basename(parent)
    if os.path.dirname(parent) == workouts and name not in NOT_WORKOUTS and not name.startswith("."):
        return parent
    return os.path.join(workouts, "checks")


# What a file name may not hold on Windows (and so nowhere: drafts and folders move between a Mac and a PC). A
# colon there writes the text into a hidden side stream ("Workout 1: Strength") or leaves the folder ("D:foo").
UNSAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{n}" for n in range(1, 10)), *(f"lpt{n}" for n in range(1, 10))}


def safe_name(name):
    """`name` when it can be a file name on every computer, else errors.UsageError (exit 64) saying why: no
    < > : " / \\ | ? * or control character, no trailing dot or space, not "." or "..", and not a name Windows
    keeps for a device (con, prn, aux, nul, com1-9, lpt1-9, with any extension)."""
    bad = sorted(set(UNSAFE_NAME_RE.findall(name)))
    if bad:
        shown = " ".join(repr(c) if ord(c) < 32 else c for c in bad)
        raise errors.UsageError(f"The name can't contain {shown}: {name!r}. Use a dash instead, such as "
                                "\"Workout 2026-10-25 Strength 25 min\".")
    if not name.strip() or name in (".", ".."):
        raise errors.UsageError(f"{name!r} isn't a name for a file.")
    if name.endswith((".", " ")):
        raise errors.UsageError(f"The name can't end with a dot or a space: {name!r}.")
    if name.split(".")[0].strip().casefold() in RESERVED_NAMES:
        raise errors.UsageError(f"{name!r} is a name Windows keeps for a device; choose another.")
    return name


def record_path(mp3):
    """The build record beside an MP3 (or .m4a, .wav): <name>.build.json."""
    return os.path.splitext(mp3)[0] + ".build.json"
