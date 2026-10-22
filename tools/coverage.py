#!/usr/bin/env python3
"""Which muscle groups recent sessions covered, read from me/log.md.

The workout skill plans whole-body sessions: anything the last session left out
comes first next time, and the last session's main movements are avoided. This
reads the Sessions list in log.md, maps each movement to the groups it trains, and
prints what to prioritize and what to avoid. It also prints the last session's
format (today's should differ) and each movement's last logged load and tempo, so
the plan can progress from it.

Sessions are read through tools/context.py, which owns the log's line format (and
writes it: `./sweatcast log-session ...`).

    ./sweatcast coverage            # the last session, plus a look further back
    ./sweatcast coverage --last 3   # groups across the last three sessions

Each movement is looked up in the movement catalog (knowledge/movements.toml) first,
and its groups come from there. A name the catalog doesn't know falls back to the
keywords below. A name that matches no group is listed as unmapped, so the planner
can judge it; add the movement, or an alias for it, to the catalog when it becomes a
regular. The last seven days are counted too, so a group the week has neglected is
prioritized even when the last session touched it.
"""
import datetime
import os
import re
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
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


_catalog = None


def _shared_catalog():
    global _catalog
    if _catalog is None:
        _catalog = catalog.load()
    return _catalog


def groups_of(movement: str, cat: Optional[catalog.Catalog] = None) -> List[str]:
    """The checklist groups a movement trains: the catalog's word if it knows the
    movement, else the keywords above."""
    found = catalog.resolve(cat or _shared_catalog(), movement)
    if found:
        return list(found.groups)
    m = movement.lower()
    return [name for name, pattern in GROUPS if re.search(pattern, m)]


def coverage(movements, cat: Optional[catalog.Catalog] = None):
    """({group: [movements]}, [unmapped movements])."""
    cat = cat or _shared_catalog()
    hit, unmapped = {name: [] for name, _ in GROUPS}, []
    for mv in movements:
        gs = groups_of(mv, cat)
        for g in gs:
            hit[g].append(mv)
        if gs or catalog.resolve(cat, mv) or re.search(NOT_STRENGTH, mv.lower()):
            continue
        unmapped.append(mv)
    return hit, unmapped


def week(sessions, today: datetime.date, days: int = 7, cat: Optional[catalog.Catalog] = None) -> Dict[str, int]:
    """{group: sessions in the last `days` days that trained it}, every group present."""
    cat = cat or _shared_catalog()
    counts = {name: 0 for name, _ in GROUPS}
    first = today - datetime.timedelta(days=days)
    for e in sessions:
        if not first < datetime.date.fromisoformat(e.date) <= today:
            continue
        trained = {g for mv in e.movements for g in groups_of(mv, cat)}
        for g in trained:
            counts[g] += 1
    return counts


def main():
    ap = cli.ArgumentParser()
    ap.add_argument("--last", type=int, default=1, help="how many recent sessions to pool (default 1)")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    cat = catalog.load()
    full = context.sessions(args.log)
    if not full:
        print("No sessions in log.md yet: every group is open, nothing to avoid.")
        return 0
    log = [(e.date, e.movements) for e in full]
    recent = log[-args.last:]
    movements = [mv for _, mvs in recent for mv in mvs]
    hit, unmapped = coverage(movements, cat)
    span = recent[0][0] if len(recent) == 1 else f"{recent[0][0]} to {recent[-1][0]}"
    print(f"Coverage, {len(recent)} session(s), {span}:")
    for name, _ in GROUPS:
        print(f"  {'yes' if hit[name] else ' no'}  {name}" + (f": {', '.join(hit[name])}" if hit[name] else ""))
    missed = [name for name, _ in GROUPS if not hit[name]]
    counts = week(full, datetime.date.today(), cat=cat)
    thin = [name for name, _ in GROUPS if counts[name] < 2 and name not in missed]
    print("\nPrioritize: " + (", ".join(missed + thin) if missed + thin else "nothing, all groups covered"))
    print("Last 7 days, sessions per group:")
    for name, _ in GROUPS:
        print(f"  {counts[name]}  {name}")
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
