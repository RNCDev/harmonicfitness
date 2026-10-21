#!/usr/bin/env python3
"""Which muscle groups recent sessions covered, read from log.md.

The workout skill plans whole-body sessions: anything the last session left out
comes first next time, and the last session's main movements are avoided. This
reads the Sessions list in log.md, maps each movement to the groups it trains, and
prints what to prioritize and what to avoid.

    python3 tools/coverage.py            # the last session, plus a look further back
    python3 tools/coverage.py --last 3   # groups across the last three sessions

A movement that matches no group is listed as unmapped, so the planner can judge
it; add a keyword below when a new movement becomes a regular.
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "log.md")

# The skill's whole-body checklist, in its order. A movement can train several groups.
GROUPS = [
    ("horizontal push", r"push-?up|(?<!overhead )(?<!leg )press"),
    ("horizontal pull", r"\brow(?:s|ing)?\b|face pull|band pull-apart"),
    ("hip hinge or glutes", r"bridge|hip thrust|deadlift|\brdl\b|hip extension|good morning|kettlebell swing"),
    ("hamstrings", r"bridge|deadlift|\brdl\b|hamstring|leg curl|good morning|nordic"),
    ("quads", r"squat|lunge|step-?up|straight-leg raise|leg extension|wall sit|quad set"),
    ("hip abductors and adductors", r"clamshell|abduct|adduct|side-lying leg|fire hydrant|copenhagen|squeeze"),
    ("anti-extension core", r"dead ?bug|(?<!side )plank|rollout|hollow|bird ?dog|reverse crunch"),
    ("lateral or anti-rotation core", r"side plank|pallof|suitcase|woodchop|anti-rotation|side bend"),
    ("arms", r"(?<!leg )(?<!hamstring )curl|kickback|triceps|biceps"),
]

# Movements that train no checklist group on purpose (finishers, skills).
NOT_STRENGTH = r"finisher|stickhandling|punch|breathing|stretch|mobility|bike|march"


def sessions(path=LOG):
    """Each logged session as (date, [movements]), oldest first."""
    out, in_sessions = [], False
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                in_sessions = line.strip().lower() == "## sessions"
                continue
            if in_sessions and line.startswith("- "):
                fields = [x.strip() for x in line[2:].split("|")]
                if len(fields) >= 5:
                    out.append((fields[0], [m.strip() for m in fields[4].split(",") if m.strip()]))
    return out


def groups_of(movement):
    m = movement.lower()
    return [name for name, pattern in GROUPS if re.search(pattern, m)]


def coverage(movements):
    """({group: [movements]}, [unmapped movements])."""
    hit, unmapped = {name: [] for name, _ in GROUPS}, []
    for mv in movements:
        gs = groups_of(mv)
        for g in gs:
            hit[g].append(mv)
        if not gs and not re.search(NOT_STRENGTH, mv.lower()):
            unmapped.append(mv)
    return hit, unmapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last", type=int, default=1, help="how many recent sessions to pool (default 1)")
    ap.add_argument("--log", default=LOG)
    args = ap.parse_args()

    log = sessions(args.log)
    if not log:
        print("No sessions in log.md yet: every group is open, nothing to avoid.")
        return 0
    recent = log[-args.last:]
    movements = [mv for _, mvs in recent for mv in mvs]
    hit, unmapped = coverage(movements)
    span = recent[0][0] if len(recent) == 1 else f"{recent[0][0]} to {recent[-1][0]}"
    print(f"Coverage, {len(recent)} session(s), {span}:")
    for name, _ in GROUPS:
        print(f"  {'yes' if hit[name] else ' no'}  {name}" + (f": {', '.join(hit[name])}" if hit[name] else ""))
    missed = [name for name, _ in GROUPS if not hit[name]]
    print("\nPrioritize (left out): " + (", ".join(missed) if missed else "nothing, all groups covered"))
    print("Avoid (last session's main movements): " + ", ".join(log[-1][1]))
    if unmapped:
        print("Unmapped (judge these by hand): " + ", ".join(unmapped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
