#!/usr/bin/env python3
"""The filler between the exercises: what a session should carry, what's been told, and the reserve.

Three things, so the stories rotate instead of repeating and the slow research happens ahead of time:
- The plan (`./sweatcast content plan --minutes N`): how many items of each slot (today, science,
  deep dive, quiz, delight, learn; knowledge/content.toml) the session carries, and for each the
  categories due, the one told longest ago (or never) first. Categories come from the profile's
  [[interests]] (name, slot, detail), or content.toml's defaults.
- The record of what's been told (me/workouts/research/told.jsonl, one item a line): the plan lists
  the last few weeks of it, so research doesn't tell a story twice. `./sweatcast content log` adds a
  session's items after it's built.
- The reserve (me/workouts/research/reserve/<slug>.md): evergreen pieces (quiz, delight, learn)
  researched ahead of time, a sheet each. A piece is used once the record names its slug. The plan
  lists the unused ones and says which slots run low. (Before 0.10.2 it was research/pantry/;
  ./sweatcast migrate renames it.)

    ./sweatcast content plan --minutes 25
    ./sweatcast content log --date 2026-10-23 --item "today | sports | The home team wins in overtime" \\
        --item "learn | history | Why old cities have crooked streets | https://... | crooked-streets"
    ./sweatcast content reserve
"""
import datetime
import json
import os
import re
import sys
import tomllib
from typing import Dict, List, NamedTuple, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import errors  # noqa: E402
import context  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402

RECIPE = paths.CONTENT   # the engine's filler plan; the listener's told.jsonl and reserve are read at call time
RECENT_DAYS = 30    # how far back the plan lists what's been told
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class Slot(NamedTuple):
    id: str
    what: str
    words: int
    fresh: bool
    reserve: int


class Recipe(NamedTuple):
    slots: Dict[str, Slot]
    bands: List[dict]
    defaults: Dict[str, List[str]]


class Piece(NamedTuple):
    slug: str
    title: str
    slot: str
    category: str
    source: str
    path: str


def recipe(path=RECIPE) -> Recipe:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    slots = {s["id"]: Slot(s["id"], s["what"], int(s["words"]), bool(s.get("fresh")), int(s.get("reserve", 0)))
             for s in data["slot"]}
    bands = sorted(data["band"], key=lambda b: b["up_to"])
    for b in bands:
        unknown = set(b) - set(slots) - {"up_to"}
        if unknown:
            raise errors.SweatcastError(f"{paths.show(path)}: a band names unknown slots: {', '.join(sorted(unknown))}")
    return Recipe(slots, bands, {k: list(v) for k, v in data.get("defaults", {}).items()})


def counts(r: Recipe, minutes: int) -> Dict[str, int]:
    band = next((b for b in r.bands if minutes <= b["up_to"]), r.bands[-1])
    return {s: int(band.get(s, 0)) for s in r.slots}


def categories(r: Recipe, profile=None) -> Dict[str, List[str]]:
    """{slot: categories in the listener's order}: the profile's [[interests]] where it lists any for
    a slot, the defaults otherwise."""
    mine: Dict[str, List[str]] = {}
    for name, slot, _ in context.interests(profile) if profile is not None else []:
        if slot in r.slots:
            mine.setdefault(slot, []).append(name)
    return {s: mine.get(s) or r.defaults.get(s, []) for s in r.slots}


def told(path=None) -> List[dict]:
    """Every item told, oldest first. A damaged line is skipped, not fatal."""
    path = path or paths.TOLD
    return [item for item in fileio.read_jsonl(path) if item.get("date") and item.get("title")]


def due(cats: List[str], items: List[dict], slot: str, n: int) -> List[tuple]:
    """The n categories to tell next in a slot, as (category, last date or None): never told first, in
    the listener's order, then the one told longest ago. Fewer categories than n repeat the first."""
    last = {}
    for item in items:
        if item.get("slot") == slot:
            last[str(item.get("category", "")).lower()] = item["date"]
    ranked = sorted(cats, key=lambda c: (last.get(c.lower()) is not None, last.get(c.lower()) or "",
                                         cats.index(c)))
    out = [(c, last.get(c.lower())) for c in ranked[:n]]
    while ranked and len(out) < n:
        out.append(out[len(out) % len(ranked)])
    return out


def sheets(folder=None) -> List[str]:
    """Every sheet in the reserve (`folder`, default research/reserve/), oldest first."""
    folder = folder or paths.RESERVE
    if not os.path.isdir(folder):
        return []
    return sorted((os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".md")), key=os.path.getmtime)


def reserve(folder=None, items=None) -> List[Piece]:
    """The reserve's unused pieces, oldest first: from `folder` (default research/reserve/)."""
    used = {i.get("reserve") for i in (told() if items is None else items)} - {None}
    out = []
    for path in sheets(folder):
        if os.path.splitext(os.path.basename(path))[0] in used:
            continue
        p = read_piece(path)
        if p:
            out.append(p)
    return out


def read_piece(path) -> Optional[Piece]:
    """A reserve sheet's header: `# <title>`, then `- Slot:`, `- Category:`, `- Source:` lines."""
    title, fields = None, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# ") and title is None:
                title = line[2:].strip()
            m = re.match(r"- (Slot|Category|Source):\s*(.*)", line)
            if m:
                fields[m.group(1).lower()] = m.group(2).strip()
    if not title or not fields.get("slot"):
        return None
    slug = os.path.splitext(os.path.basename(path))[0]
    return Piece(slug, title, fields["slot"], fields.get("category", ""), fields.get("source", ""), path)


def plan_facts(minutes: int, today: datetime.date, r: Recipe = None, profile=None, items=None,
               pieces=None) -> dict:
    """The filler plan as data (content plan --json; its keys are kept stable): minutes; slots, one per slot
    the session carries, in the recipe's order: {slot, count, words, what, fresh, due: [{category, last_told
    (a date or null), detail (the listener's, or null)}]}; recent_days and told_recent [{date, slot, category,
    title}]; reserve [{slug, title, slot, category, source, path}]; restock [{slot, more, categories}]."""
    r = r or recipe()
    items = told() if items is None else items
    pieces = reserve(items=items) if pieces is None else pieces
    cats = categories(r, profile)
    n = counts(r, minutes)
    details = {name.lower(): detail for name, _, detail in context.interests(profile)} if profile else {}
    since = (today - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    return {
        "minutes": minutes,
        "slots": [{"slot": sid, "count": n[sid], "words": slot.words, "what": slot.what, "fresh": slot.fresh,
                   "due": [{"category": c, "last_told": d, "detail": details.get(c.lower()) or None}
                           for c, d in due(cats[sid], items, sid, n[sid])]}
                  for sid, slot in r.slots.items() if n[sid]],
        "recent_days": RECENT_DAYS,
        "told_recent": [{"date": i["date"], "slot": i.get("slot"), "category": i.get("category"),
                         "title": i["title"]} for i in items if i["date"] >= since],
        "reserve": [{"slug": p.slug, "title": p.title, "slot": p.slot, "category": p.category,
                     "source": p.source, "path": paths.show(p.path)} for p in pieces],
        "restock": [{"slot": sid, "more": k, "categories": [c for c, _ in due(cats[sid], items, sid, k)]}
                    for sid, k in restock(r, cats, items, pieces).items()],
    }


def plan(minutes: int, today: datetime.date, r: Recipe = None, profile=None, items=None,
         pieces=None) -> List[str]:
    """The filler plan's lines (plan_facts, as text)."""
    f = plan_facts(minutes, today, r, profile, items, pieces)
    out = [f"# Filler plan, {minutes} minutes", "",
           "The items the session's rests carry, by slot, each with its category, when that category was "
           "last told, and what the listener likes in it. The deep dive is told in beats across several rests.", ""]
    for slot in f["slots"]:
        source = "research it today" if slot["fresh"] else "from the reserve, or research it if none fits"
        out.append(f"- {slot['slot']} x{slot['count']}, about {slot['words']} words each ({slot['what']}; {source}):")
        for d in slot["due"]:
            out.append(f"  - {d['category']}, {'last told ' + d['last_told'] if d['last_told'] else 'never told'}"
                       f"{': ' + d['detail'] if d['detail'] else ''}")
    out += ["", f"## Told in the last {RECENT_DAYS} days (don't tell again; a follow-up needs something new)"]
    out += [f"- {i['date']} {i['slot'] or '?'} / {i['category'] or '?'}: {i['title']}" for i in f["told_recent"]] \
        or ["- nothing yet"]
    out += ["", "## Reserve (unused pieces, ready to tell)"]
    out += [f"- {p['slot']} / {p['category']}: {p['title']} ({p['path']}, slug {p['slug']})" for p in f["reserve"]] \
        or ["- empty"]
    if f["restock"]:
        out += ["", "## Restock", "The reserve is low; stock these (the categories told longest ago first):"]
        out += [f"- {x['slot']}: {x['more']} more, in {', '.join(x['categories'])}" for x in f["restock"]]
    return out


def restock(r: Recipe, cats, items, pieces) -> Dict[str, int]:
    """{slot: pieces short} for the slots the reserve keeps, where it holds fewer unused than its target."""
    have = {}
    for p in pieces:
        have[p.slot] = have.get(p.slot, 0) + 1
    return {sid: s.reserve - have.get(sid, 0) for sid, s in r.slots.items()
            if s.reserve and have.get(sid, 0) < s.reserve and cats.get(sid)}


def parse_item(text: str, date: str, r: Recipe, profile=None) -> dict:
    """"slot | category | title [| source [| reserve slug]]" as a record item; ValueError says what's wrong.
    The category must be one the plan rotates for that slot (the profile's [[interests]], else the
    defaults), or the rotation would never see it told."""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3 or not all(parts[:3]):
        raise ValueError(f"'{text}': expected 'slot | category | title [| source [| reserve slug]]'")
    if len(parts) > 5:
        raise ValueError(f"'{text}': too many fields (a title can't hold a |)")
    slot, category, title = parts[:3]
    slot = re.sub(r"[\s-]+", "_", slot.strip().lower())   # "deep dive" and "deep-dive" are deep_dive
    if slot not in r.slots:
        raise ValueError(f"'{text}': unknown slot '{slot}' (one of {', '.join(r.slots)})")
    known = categories(r, profile)[slot]
    if known and category.lower() not in {c.lower() for c in known}:
        raise ValueError(f"'{text}': category '{category}' isn't one the plan rotates for {slot} "
                         f"(one of {', '.join(known)})")
    item = {"date": date, "slot": slot, "category": category.lower(), "title": title}
    if len(parts) > 3 and parts[3]:
        item["source"] = parts[3]
    if len(parts) > 4 and parts[4]:
        if not SLUG_RE.match(parts[4]):
            raise ValueError(f"'{text}': reserve slug '{parts[4]}' should be lowercase words and dashes")
        item["reserve"] = parts[4]
    return item


def log(date: str, texts: List[str], path=None, r: Recipe = None, profile=None) -> List[dict]:
    r = r or recipe()
    datetime.date.fromisoformat(date)
    path = path or paths.TOLD
    new = [parse_item(t, date, r, profile) for t in texts]   # all checked before any is written
    with locks.file_lock(path):   # read, check and append as one step, so a piece is told once
        return _log_new(new, path)


def _log_new(new: List[dict], path) -> List[dict]:
    used = {i.get("reserve") for i in told(path)} - {None}
    for item in new:
        slug = item.get("reserve")
        if slug and not os.path.exists(os.path.join(paths.RESERVE, slug + ".md")):
            raise ValueError(f"no reserve piece '{slug}' in {paths.show(paths.RESERVE)} (a typo here would leave the real "
                             "piece unused, to be told again)")
        if slug in used:
            raise ValueError(f"reserve piece '{slug}' is already told (in {paths.show(path)} or earlier in this "
                             "command); a piece is told once")
        if slug:
            used.add(slug)
    if new:
        fileio.append_jsonl(path, new)
    return new


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast content", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="the filler plan for a session, what's been told, the reserve")
    p.add_argument("--minutes", type=int, default=25, help="the session's length (default 25)")
    cli.today_arg(p)
    p.add_argument("--json", action="store_true",
                   help="the same plan as one JSON object: minutes, slots (slot, count, words, what, fresh, due: "
                        "category, last_told, detail), recent_days, told_recent, reserve, restock")
    lg = sub.add_parser("log", help="record the items a session told")
    lg.add_argument("--date", required=True, help="the session's date, YYYY-MM-DD")
    lg.add_argument("--item", action="append", required=True,
                    help='"slot | category | title [| source [| reserve slug]]", once per item')
    sub.add_parser("reserve", help="list the reserve's unused pieces")
    args = ap.parse_args(argv)
    try:
        if args.cmd == "plan":
            today = args.today or datetime.date.today()
            if args.minutes <= 0:
                raise ValueError("--minutes must be above zero")
            if args.json:
                print(json.dumps(plan_facts(args.minutes, today, profile=context.profile()), indent=1,
                                 ensure_ascii=False))
            else:
                print("\n".join(plan(args.minutes, today, profile=context.profile())))
        elif args.cmd == "log":
            # the profile's [[interests]] name the categories; with no profile, the defaults
            new = log(args.date, args.item, profile=context.profile() if os.path.exists(paths.PROFILE) else None)
            print(f"Recorded {len(new)} item(s) in {paths.show(paths.TOLD)}.")
        else:
            pieces = reserve()
            print("\n".join(f"{p.slot} / {p.category}: {p.title} ({p.slug})" for p in pieces) or "The reserve is empty.")
    except ValueError as e:
        print(f"sweatcast content: {e}", file=sys.stderr)
        return cli.USAGE
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
