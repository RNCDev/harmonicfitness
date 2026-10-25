"""Where a workout's files live in the context folder: one folder per workout.

    me/workouts/
      2026-10-25-strength-25/      one workout: <stem>.draft.txt, .brief.md, .menu.json, then the build's
                                   <name>.txt and <name>.build.json (and <name>.mp3 until it's delivered)
      checks/                      smoke tests and any build whose draft isn't in a workout folder
      research/                    told.jsonl, reserve/, videos/, puzzles/, and daily/ (each day's sheet and feeds)
      .audio-cache/, .logs/        rendered clips and build logs

reorganize() moves a folder from the old layout (drafts/ beside every build's output, and the day's
research loose in research/) into this one; ./sweatcast migrate runs it once, at schema 4 to 5.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

DRAFT_SUFFIXES = (".draft.txt", ".brief.md", ".menu.json")
OUTPUT_SUFFIXES = (".build.json", ".txt", ".mp3", ".m4a")
NOT_WORKOUTS = ("checks", "research", "drafts")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


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


def record_path(mp3):
    """The build record beside an MP3 (or .m4a, .wav): <name>.build.json."""
    return os.path.splitext(mp3)[0] + ".build.json"


def _strip(name, suffixes):
    for s in suffixes:
        if name.endswith(s):
            return name[:-len(s)]
    return None


def _free(dst):
    """`dst`, or `dst` with " (2)", " (3)" ... before its extension when something is already there."""
    if not os.path.exists(dst):
        return dst
    folder, base = os.path.split(dst)
    ext = next((s for s in (*DRAFT_SUFFIXES, ".build.json") if base.endswith(s)), os.path.splitext(base)[1])
    stem = base[:-len(ext)] if ext else base
    n = 2
    while os.path.exists(os.path.join(folder, f"{stem} ({n}){ext}")):
        n += 1
    return os.path.join(folder, f"{stem} ({n}){ext}")


def _record_stem(record_path):
    """(the draft's stem, whether it's the smoke test) from a build record, or (None, False)."""
    try:
        with open(record_path, encoding="utf-8") as f:
            draft = json.load(f).get("draft") or ""
    except (OSError, ValueError):
        return None, False
    base = os.path.basename(draft)
    if base == "smoke-test.draft.txt":
        return None, True
    return _strip(base, (".draft.txt",)) or os.path.splitext(base)[0] or None, False


def plan(home):
    """[(src, dst)] that would bring `home`'s workouts into the folder-per-workout layout."""
    w = os.path.join(home, "workouts")
    if not os.path.isdir(w):
        return []
    moves = []
    drafts = os.path.join(w, "drafts")
    stems = set()
    if os.path.isdir(drafts):
        for name in sorted(os.listdir(drafts)):
            src = os.path.join(drafts, name)
            if not os.path.isfile(src) or name.startswith("."):
                continue
            stem = _strip(name, DRAFT_SUFFIXES) or os.path.splitext(name)[0]
            stems.add(stem)
            moves.append((src, os.path.join(session_dir(stem, w), name)))
    stems |= {d for d in os.listdir(w) if os.path.isdir(os.path.join(w, d))
              and d not in NOT_WORKOUTS and not d.startswith(".")}

    groups = {}
    for name in sorted(os.listdir(w)):
        src = os.path.join(w, name)
        if os.path.isfile(src) and not name.startswith("."):
            groups.setdefault(_strip(name, OUTPUT_SUFFIXES) or os.path.splitext(name)[0], []).append(name)
    for base, names in groups.items():
        stem, smoke = _record_stem(os.path.join(w, base + ".build.json"))
        if smoke or (stem and stem not in stems):
            stem = None
        if stem is None and not smoke:
            m = DATE_RE.search(base)
            same_day = sorted(s for s in stems if m and s.startswith(m.group(1)))
            stem = same_day[0] if len(same_day) == 1 else None
        folder = session_dir(stem, w) if stem else os.path.join(w, "checks")
        moves += [(os.path.join(w, n), os.path.join(folder, n)) for n in names]

    research = os.path.join(w, "research")
    if os.path.isdir(research):
        for name in sorted(os.listdir(research)):
            src = os.path.join(research, name)
            if os.path.isfile(src) and re.match(r"\d{4}-\d{2}-\d{2}.*\.md$", name):
                moves.append((src, os.path.join(research, "daily", name)))
    return moves


def reorganize(home, dry_run=False):
    """Move `home`'s workouts into the folder-per-workout layout; never overwrites. Returns [(src, dst)]."""
    done = []
    for src, dst in plan(home):
        if dry_run:
            done.append((src, dst))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        dst = _free(dst)
        shutil.move(src, dst)
        done.append((src, dst))
    drafts = os.path.join(home, "workouts", "drafts")
    if not dry_run and os.path.isdir(drafts) and not [n for n in os.listdir(drafts) if not n.startswith(".")]:
        shutil.rmtree(drafts)
    return done
