#!/usr/bin/env python3
"""Which muscle groups recent sessions covered, read from me/log.md.

The workout skill plans whole-body sessions: anything the last session left out
comes first next time, and the last session's main movements are avoided. This
reads the Sessions list in log.md, maps each movement to the groups it trains, and
prints what to prioritize and what to avoid. It also prints the last session's
format (today's should differ) and each movement's last logged load and tempo, so
the plan can progress from it.

Sessions are read through tools/context.py, which owns the log's line format (and
writes it: `python3 tools/context.py log-session ...`).

    python3 tools/coverage.py            # the last session, plus a look further back
    python3 tools/coverage.py --last 3   # groups across the last three sessions

A movement that matches no group is listed as unmapped, so the planner can judge
it; add a keyword below when a new movement becomes a regular.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import context  # noqa: E402

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


def last_loads(log, look_back=6):
    """{movement: (date, load)}: the newest logged load per movement in recent sessions."""
    out = {}
    for e in log[-look_back:]:
        for mv, load in e.loads.items():
            out[mv] = (e.date, load)
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
    ap = cli.ArgumentParser()
    ap.add_argument("--last", type=int, default=1, help="how many recent sessions to pool (default 1)")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    full = context.sessions(args.log)
    if not full:
        print("No sessions in log.md yet: every group is open, nothing to avoid.")
        return 0
    log = [(e.date, e.movements) for e in full]
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
    fmt = full[-1].format
    print("Last format: " + (f"{fmt} (use a different one today)" if fmt else "not logged"))
    loads = last_loads(full)
    if loads:
        print("Last loads (progress from these):")
        for mv, (date, load) in sorted(loads.items(), key=lambda kv: kv[1][0], reverse=True):
            print(f"  {mv}: {load} ({date})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
