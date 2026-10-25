#!/usr/bin/env python3
"""Which movement patterns recent sessions covered, read from me/log.md.

The workout skill plans whole-body sessions: anything the last session left out
comes first next time, and the last session's main movements are avoided. This
reads the Sessions list in log.md, maps each movement to the patterns it trains, and
prints what to prioritize and what to avoid. It also prints the last session's
format (today's should differ) and each movement's last logged load and tempo, so
the plan can progress from it.

Sessions are read through tools/context.py, which owns the log's line format (and
writes it: `./sweatcast log-session ...`).

    ./sweatcast coverage            # the last session, plus a look further back
    ./sweatcast coverage --last 3   # patterns across the last three sessions

Each movement is looked up in the movement catalog (knowledge/movements.toml) first,
and its patterns come from there. A name the catalog doesn't know falls back to the
keywords below. A name that matches no pattern is listed as unmapped, so the planner
can judge it; add the movement, or an alias for it, to the catalog when it becomes a
regular. The last seven days are counted too, so a pattern the week has neglected is
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

# Fallback for names the catalog doesn't know: keywords per pattern (a movement can match several).
KEYWORDS = [
    ("horizontal-push", r"push-?up|(?<!overhead )(?<!leg )press"),
    ("horizontal-pull", r"\brow(?:s|ing)?\b|face pull|band pull-apart"),
    ("hinge", r"bridge|hip thrust|deadlift|\brdl\b|hip extension|good morning|kettlebell swing|hinge"),
    ("squat", r"squat|lunge|step-?up|wall sit"),
    ("anti-extension", r"dead ?bug|(?<!side )plank|rollout|hollow|bird ?dog"),
    ("anti-rotation", r"side plank|pallof|suitcase|anti-rotation"),
    ("arms", r"(?<!leg )(?<!hamstring )curl|kickback|triceps|biceps"),
    ("locomotion", r"\bbike\b|row erg|\brun(?:ning)?\b|jog"),
    ("mobility", r"stretch|mobility"),
    ("breathing", r"breathing"),
]

# Movements that train no pattern on purpose (finishers, skills).
NOT_STRENGTH = r"finisher|stickhandling|punch|breathing|stretch|mobility|bike|march"


def last_loads(log, look_back=6, cat: Optional[catalog.Catalog] = None):
    """{movement: (date, load)}: the newest logged load per movement in recent sessions. Names are matched
    through the catalog ("Goblet squats" and "goblet squat" are one movement, shown by its catalog name);
    a name it doesn't know stands as written."""
    cat = cat or _shared_catalog()
    out = {}
    for e in log[-look_back:]:
        for mv, load in e.loads.items():
            found = catalog.resolve(cat, mv)
            key = found.id if found else mv.strip().lower()
            out[key] = (found.name if found else mv.strip(), e.date, load)
    return {name: (date, load) for name, date, load in out.values()}


_catalog = None


def _shared_catalog():
    global _catalog
    if _catalog is None:
        _catalog = catalog.load()
    return _catalog


def patterns_of(movement: str, cat: Optional[catalog.Catalog] = None) -> List[str]:
    """The movement patterns a movement trains: the catalog's word if it knows the
    movement, else the keywords above."""
    found = catalog.resolve(cat or _shared_catalog(), movement)
    if found:
        return list(found.patterns)
    m = movement.lower()
    return [name for name, pattern in KEYWORDS if re.search(pattern, m)]


def coverage(movements, cat: Optional[catalog.Catalog] = None):
    """({pattern: [movements]}, [unmapped movements])."""
    cat = cat or _shared_catalog()
    hit, unmapped = {name: [] for name in cat.patterns}, []
    for mv in movements:
        ps = patterns_of(mv, cat)
        for p in ps:
            hit.setdefault(p, []).append(mv)
        if ps or catalog.resolve(cat, mv) or re.search(NOT_STRENGTH, mv.lower()):
            continue
        unmapped.append(mv)
    return hit, unmapped


def week(sessions, today: datetime.date, days: int = 7, cat: Optional[catalog.Catalog] = None) -> Dict[str, int]:
    """{pattern: sessions in the last `days` days that trained it}, every pattern present."""
    cat = cat or _shared_catalog()
    counts = {name: 0 for name in cat.patterns}
    first = today - datetime.timedelta(days=days)
    for e in sessions:
        if not first < datetime.date.fromisoformat(e.date) <= today:
            continue
        trained = {p for mv in e.movements for p in patterns_of(mv, cat)}
        for p in trained:
            counts[p] = counts.get(p, 0) + 1
    return counts


def _days_ago(date: str, today: datetime.date) -> Optional[int]:
    try:
        return (today - datetime.date.fromisoformat(date)).days
    except ValueError:
        return None


def main():
    ap = cli.ArgumentParser()
    ap.add_argument("--last", type=int, default=1, help="how many recent sessions to pool (default 1)")
    ap.add_argument("--log", default=None)
    args = ap.parse_args()

    cat = catalog.load()
    full = context.sessions(args.log)
    if not full:
        print("No sessions in log.md yet: every pattern is open, nothing to avoid.")
        return 0
    log = [(e.date, e.movements) for e in full]
    recent = log[-args.last:]
    movements = [mv for _, mvs in recent for mv in mvs]
    hit, unmapped = coverage(movements, cat)
    span = recent[0][0] if len(recent) == 1 else f"{recent[0][0]} to {recent[-1][0]}"
    print(f"Coverage, {len(recent)} session(s), {span}:")
    for name in cat.patterns:
        print(f"  {'yes' if hit[name] else ' no'}  {name}" + (f": {', '.join(hit[name])}" if hit[name] else ""))
    missed = [name for name in cat.patterns if not hit[name]]
    counts = week(full, datetime.date.today(), cat=cat)
    thin = [name for name in cat.patterns if counts[name] < 2 and name not in missed]
    print("\nPrioritize: " + (", ".join(missed + thin) if missed + thin else "nothing, all patterns covered"))
    print("Last 7 days, sessions per pattern:")
    for name in cat.patterns:
        print(f"  {counts[name]}  {name}")
    print("Avoid (last session's main movements): " + ", ".join(log[-1][1]))
    if unmapped:
        print("Unmapped (judge these by hand): " + ", ".join(unmapped))
    fmt = full[-1].format
    print("Last format: " + (f"{fmt} (use a different one today)" if fmt else "not logged")
          + f"; last kit: {full[-1].kit}")
    today = datetime.date.today()
    try:
        since = (today - datetime.date.fromisoformat(full[-1].date)).days
    except ValueError:
        since = None
    seven = sum(1 for e in full if _days_ago(e.date, today) is not None and 0 <= _days_ago(e.date, today) < 7)
    print("Since the last session: " + (f"{since} day{'s' if since != 1 else ''}" if since is not None else "unknown")
          + f"; sessions in the last 7 days: {seven} (mention it if it's worth saying)")
    notes = context.feedback(args.log)
    if notes:
        print("Latest feedback (honour it, and say so in the audio): " + notes[-1])
    loads = last_loads(full, cat=cat)
    if loads:
        print("Last loads (progress from these):")
        for mv, (date, load) in sorted(loads.items(), key=lambda kv: kv[1][0], reverse=True):
            print(f"  {mv}: {load} ({date})")
    return 0


if __name__ == "__main__":
    sys.exit(cli.run(main))
