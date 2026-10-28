#!/usr/bin/env python3
"""Which movement patterns recent sessions covered, read from me/log.md.

The workout skill plans whole-body sessions: anything the last session left out
comes first next time, and the last session's main movements are avoided. This
reads the Sessions list in log.md, maps each movement to the patterns it trains, and
prints what to prioritize and what to avoid. It also prints the last session's
format (today's should differ) and each movement's last logged load and tempo, so
the plan can progress from it.

Sessions are read through tools/context.py, which owns the log's line format (and
writes it: `./harmonicfitness log-session ...`).

    ./harmonicfitness coverage            # the last session, plus a look further back
    ./harmonicfitness coverage --last 3   # patterns across the last three sessions

Each movement is looked up in the movement catalog (knowledge/movements.toml) first,
and its patterns come from there. A name the catalog doesn't know falls back to the
keywords below. A name that matches no pattern is listed as unmapped, so the planner
can judge it; add the movement, or an alias for it, to the catalog when it becomes a
regular. The last seven days are counted too, so a pattern the week has neglected is
prioritized even when the last session touched it.
"""
import argparse
import datetime
import json
import os
import re
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402
import context  # noqa: E402
import sessionlog  # noqa: E402

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
            out[catalog.key(cat, mv)] = (found.name if found else mv.strip(), e.date, load)
    return {name: (date, load) for name, date, load in out.values()}


def _shared_catalog():
    return catalog.default()


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


def days_ago(date: str, today: datetime.date) -> Optional[int]:
    try:
        return (today - datetime.date.fromisoformat(date)).days
    except ValueError:
        return None


def facts(log_path=None, last=1, today: Optional[datetime.date] = None) -> dict:
    """What the report says, as data (the --json output; its keys are kept stable):
    sessions (how many logged), pooled (how many recent sessions the coverage pools), span (their dates),
    covered {pattern: [movements]} for every pattern, prioritize [patterns] (left out by the pooled
    sessions, then those trained fewer than twice in the last 7 days), week {pattern: sessions in the last 7
    days}, avoid [the last session's movements], unmapped [movements], last_format, last_kit, days_since,
    sessions_7d, feedback (the latest, or null) and last_loads {movement: {date, load}}, newest first. With no
    session logged, sessions is 0 and the rest are empty or null."""
    today = today or datetime.date.today()
    cat = catalog.load()
    full = sessionlog.sessions(log_path)
    out = {"sessions": len(full), "pooled": 0, "span": None, "covered": {name: [] for name in cat.patterns},
           "prioritize": [], "week": {name: 0 for name in cat.patterns}, "avoid": [], "unmapped": [],
           "last_format": None, "last_kit": None, "days_since": None, "sessions_7d": 0, "feedback": None,
           "last_loads": {}}
    if not full:
        return out
    log = [(e.date, e.movements) for e in full]
    recent = log[-last:]
    hit, unmapped = coverage([mv for _, mvs in recent for mv in mvs], cat)
    missed = [name for name in cat.patterns if not hit[name]]
    counts = week(full, today, cat=cat)
    thin = [name for name in cat.patterns if counts[name] < 2 and name not in missed]
    notes = context.feedback(log_path)
    loads = sorted(last_loads(full, cat=cat).items(), key=lambda kv: kv[1][0], reverse=True)
    out.update({
        "pooled": len(recent),
        "span": recent[0][0] if len(recent) == 1 else f"{recent[0][0]} to {recent[-1][0]}",
        "covered": {name: list(hit[name]) for name in cat.patterns},
        "prioritize": missed + thin,
        "week": counts,
        "avoid": list(log[-1][1]),
        "unmapped": unmapped,
        "last_format": full[-1].format or None,
        "last_kit": full[-1].kit,
        "days_since": days_ago(full[-1].date, today),
        "sessions_7d": sum(1 for e in full if days_ago(e.date, today) is not None
                           and 0 <= days_ago(e.date, today) < 7),
        "feedback": notes[-1] if notes else None,
        "last_loads": {mv: {"date": date, "load": load} for mv, (date, load) in loads},
    })
    return out


def text(f: dict) -> List[str]:
    """The report's lines, from facts()."""
    if not f["sessions"]:
        return ["No sessions in log.md yet: every pattern is open, nothing to avoid."]
    lines = [f"Coverage, {f['pooled']} session(s), {f['span']}:"]
    for name, mvs in f["covered"].items():
        lines.append(f"  {'yes' if mvs else ' no'}  {name}" + (f": {', '.join(mvs)}" if mvs else ""))
    lines.append("\nPrioritize: " + (", ".join(f["prioritize"]) if f["prioritize"] else "nothing, all patterns covered"))
    lines.append("Last 7 days, sessions per pattern:")
    lines += [f"  {n}  {name}" for name, n in f["week"].items()]
    lines.append("Avoid (last session's main movements): " + ", ".join(f["avoid"]))
    if f["unmapped"]:
        lines.append("Unmapped (judge these by hand): " + ", ".join(f["unmapped"]))
    fmt, since = f["last_format"], f["days_since"]
    lines.append("Last format: " + (f"{fmt} (use a different one today)" if fmt else "not logged")
                 + f"; last kit: {f['last_kit']}")
    lines.append("Since the last session: " + (f"{since} day{'s' if since != 1 else ''}" if since is not None
                                               else "unknown")
                 + f"; sessions in the last 7 days: {f['sessions_7d']} (mention it if it's worth saying)")
    if f["feedback"]:
        lines.append("Latest feedback (honour it, and say so in the audio): " + f["feedback"])
    if f["last_loads"]:
        lines.append("Last loads (progress from these):")
        lines += [f"  {mv}: {v['load']} ({v['date']})" for mv, v in f["last_loads"].items()]
    return lines


def main(argv=None):
    ap = cli.ArgumentParser(prog="harmonicfitness coverage", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--last", type=cli.positive_int, default=1, help="how many recent sessions to pool (default 1)")
    ap.add_argument("--log", default=None)
    ap.add_argument("--json", action="store_true",
                    help="the same facts as one JSON object: sessions, pooled, span, covered, prioritize, week, "
                         "avoid, unmapped, last_format, last_kit, days_since, sessions_7d, feedback, last_loads")
    args = ap.parse_args(argv)
    f = facts(args.log, args.last)
    if args.json:
        print(json.dumps(f, indent=1, ensure_ascii=False))
    else:
        print("\n".join(text(f)))
    return 0


if __name__ == "__main__":
    sys.exit(cli.run(main))
