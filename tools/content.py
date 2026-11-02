#!/usr/bin/env python3
"""What fills the rests besides the coaching: the topics due, the ways to tell them, what's been told, the stock.

The listener owns the topics (lines under `## Topics` in me/content.md: what they like to stay current
on and learn about); the engine owns the formats (knowledge/content.toml: a quick hit, the big story, an
explainer, a serial, a quiz, this or that...), each open to any topic. The model does the rest: how big
a story is, which format suits it, how it's woven into the workout.

- The plan (`./harmonicfitness content plan --minutes N`): the topics due today, never told first, then
  the one told longest ago (how many by the session's length), the formats (less the profile's
  `skip_formats`), what's been told lately, the stock and what to restock.
- The record of what's been told (me/workouts/research/told.jsonl, one item a line), so nothing repeats
  and the topics rotate. `./harmonicfitness content log` adds a session's items after it's built. A line
  from before 0.35.0 (slot and category) still reads, its category as the topic.
- The stock (me/workouts/research/reserve/<slug>.md): pieces researched ahead of time, while a build
  renders, a sheet each with its topic, format and the date it stops being current. A piece is used once
  the record names its slug.
- Trending (`./harmonicfitness content trending`): what's popular today (Reddit's front page, safe for
  work only, else Wikipedia's most read), for suggesting new topics.

    ./harmonicfitness content plan --minutes 25
    ./harmonicfitness content log --date 2026-10-23 --item "Seattle Kraken | quick_hit | Kraken beat the Canucks 4-2" \\
        --item "Cities | explainer | Why old cities have crooked streets | https://... | crooked-streets"
    ./harmonicfitness content thread --date 2026-10-23 --open "Space | quiz | Which planet has the longest day? (Venus)"
    ./harmonicfitness content thread --date 2026-10-25 --close t1
    ./harmonicfitness content reserve
    ./harmonicfitness content trending

- Threads (me/workouts/research/threads.jsonl): what a session left open for a later one (a serial to carry on,
  a quiz answered next time, a story to follow up, the coach's take on a this-or-that, a promise), listed in
  the plan until `content thread --close` closes it.
"""
import datetime
import json
import os
import re
import sys
import tomllib
from typing import Dict, List, NamedTuple, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import errors  # noqa: E402
import context  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402

RECIPE = paths.CONTENT   # the engine's formats; the listener's told.jsonl and stock are read at call time
RECENT_DAYS = 30    # how far back the plan lists what's been told
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NO_TOPIC = "-"      # a told item tied to no topic (a puzzle, a callback from the log)
RESEARCH = ("news", "evergreen", "either", "none")
FITS = ("steady", "rest", "close")   # where a format lands: during steady work, in a rest, at the close
# A stock sheet from before 0.35.0 names a slot; the format it was written for.
LEGACY_SLOT_FORMAT = {"quiz": "quiz", "delight": "recommendation", "learn": "explainer", "today": "quick_hit",
                      "science": "explainer", "deep_dive": "serial"}


class Format(NamedTuple):
    id: str
    name: str
    group: str
    what: str
    words: int
    research: str
    across: bool
    fits: Tuple[str, ...] = ()   # FITS
    tell: str = ""               # its shape in beats
    ends: str = ""               # what it lands on
    avoid: str = ""              # how it goes flat


class Band(NamedTuple):
    up_to: int
    topics: int
    spares: int
    serial: bool
    in_work: int = 0   # pieces told during steady timed work, after the setup and the first cue


class Recipe(NamedTuple):
    formats: Dict[str, Format]
    bands: List[Band]
    per_topic: int
    per_run: int
    mix: Tuple[str, ...] = ()   # how the pieces sit together across a session


class Piece(NamedTuple):
    slug: str
    title: str
    topic: str
    format: str
    source: str
    good_until: Optional[str]   # YYYY-MM-DD, or None for evergreen
    path: str
    bad_until: str = ""         # a Good until line that's neither a date nor evergreen, as written


EVERGREEN = ("", "evergreen", "none", "never")


def recipe(path=RECIPE) -> Recipe:
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:   # the file's fault (exit 1), never the command's
            raise errors.ContextError(f"{paths.show(path)} isn't valid TOML: {e}") from e
    try:
        formats = {f["id"]: Format(f["id"], f["name"], f["group"], f["what"], int(f["words"]), f["research"],
                                   bool(f.get("across")), tuple(f.get("fits", ())), str(f.get("tell", "")),
                                   str(f.get("ends", "")), str(f.get("avoid", ""))) for f in data["format"]}
        bands = sorted((Band(int(b["up_to"]), int(b["topics"]), int(b.get("spares", 0)), bool(b.get("serial")),
                             int(b.get("in_work", 0)))
                        for b in data["band"]), key=lambda b: b.up_to)
        stock = data.get("stock", {})
        per_topic, per_run = int(stock.get("per_topic", 2)), int(stock.get("per_run", 6))
        mix = tuple(str(x) for x in data.get("mix", {}).get("rules", ()))
    except (KeyError, TypeError, ValueError) as e:
        raise errors.ContextError(f"{paths.show(path)}: a format or band is missing a field or has the wrong type "
                                  f"({e})") from e
    bad = [f.id for f in formats.values() if f.research not in RESEARCH]
    if bad:
        raise errors.ContextError(f"{paths.show(path)}: research must be one of {', '.join(RESEARCH)} "
                                  f"(not for {', '.join(bad)})")
    bad = [f.id for f in formats.values() if not f.fits or set(f.fits) - set(FITS)]
    if bad:
        raise errors.ContextError(f"{paths.show(path)}: fits must name one or more of {', '.join(FITS)} "
                                  f"(not for {', '.join(bad)})")
    if not bands:
        raise errors.ContextError(f"{paths.show(path)}: no [[band]]")
    return Recipe(formats, bands, per_topic, per_run, mix)


def band(r: Recipe, minutes: int) -> Band:
    return next((b for b in r.bands if minutes <= b.up_to), r.bands[-1])


def format_id(r: Recipe, text: str) -> Optional[str]:
    """A format's id from its id or name as written ("quick hit", "Quick-hit", "The big story"), else None."""
    key = re.sub(r"[\s-]+", "_", text.strip().casefold())
    if key in r.formats:
        return key
    for f in r.formats.values():
        if re.sub(r"[\s-]+", "_", f.name.casefold()) in (key, "the_" + key):
            return f.id
    return None


def skipped(r: Recipe, profile=None) -> List[str]:
    """The format ids the profile's skip_formats leaves out (unknown names ignored here; check reports them)."""
    if profile is None:
        return []
    return [i for i in (format_id(r, x) for x in context.str_list(profile.settings.get("skip_formats"))) if i]


def told(path=None) -> List[dict]:
    """Every item told, oldest first. A damaged line is skipped, not fatal."""
    path = path or paths.TOLD
    return [item for item in fileio.read_jsonl(path) if item.get("date") and item.get("title")]


def item_topic(item: dict) -> str:
    """A told item's topic: `topic`, or a line from before 0.35.0's `category`."""
    return str(item.get("topic") or item.get("category") or "")


def item_format(item: dict) -> str:
    return str(item.get("format") or LEGACY_SLOT_FORMAT.get(str(item.get("slot")), item.get("slot") or ""))


def last_told(items: List[dict]) -> Dict[str, str]:
    """{topic, casefolded: the last date told}."""
    out = {}
    for item in items:
        t = item_topic(item).casefold()
        if t and t != NO_TOPIC and item["date"] > out.get(t, ""):
            out[t] = item["date"]
    return out


def due(topics: List[context.Topic], items: List[dict], n: int, strength: Optional[Dict[str, float]] = None,
        today: Optional[datetime.date] = None) -> List[tuple]:
    """The n topics to tell next, as (Topic, last date or None): never told first (the strongest first, then in
    the listener's order), then by strength times the days since each was told, so a strong interest comes round
    sooner and a faint one later. With no strengths (or all equal) that's the one told longest ago. Fewer topics
    than n are all of them."""
    last = last_told(items)
    strength = strength or {}
    today = today or datetime.date.today()

    def key(t):
        name = t.name.casefold()
        s = strength.get(name, 1.0)
        if name not in last:
            return (0, -s, topics.index(t))
        days = max((today - datetime.date.fromisoformat(last[name])).days, 0) + 1
        return (1, -s * days, last[name], topics.index(t))
    ranked = sorted(topics, key=key)
    return [(t, last.get(t.name.casefold())) for t in ranked[:n]]


def all_topics(profile, today: Optional[datetime.date] = None, lr=None) -> List[context.Topic]:
    """The listener's own topics, then the learned ones (interests.py) strong enough to tell, strongest first."""
    import interests
    own = context.topics(profile) if profile is not None else []
    if profile is None:
        return own
    lr = lr or interests.learned(profile, today)
    return own + [context.Topic(x.name, "learned" + (f", part of {x.parent}" if x.parent else "")
                                + (f": {x.note}" if x.note else "")) for x in lr.topics]


def sheets(folder=None) -> List[str]:
    """Every sheet in the stock (`folder`, default research/reserve/), oldest first."""
    folder = folder or paths.RESERVE
    if not os.path.isdir(folder):
        return []
    return sorted((os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".md")), key=os.path.getmtime)


def current(piece: Piece, today: Optional[datetime.date]) -> bool:
    """True while a piece is still worth telling: evergreen, or its Good until date not passed. A Good until
    that can't be read ("Nov 15") is never current: a dated piece must never pass for evergreen."""
    if piece.bad_until:
        return today is None
    return today is None or not piece.good_until or piece.good_until >= today.isoformat()


def unreadable(folder=None, items=None) -> List[Piece]:
    """The stock's unused pieces whose Good until is neither a date (YYYY-MM-DD) nor evergreen: left out of the
    plan's stock until the line is fixed."""
    return [p for p in reserve(folder, items) if p.bad_until]


def reserve(folder=None, items=None, today=None) -> List[Piece]:
    """The stock's unused pieces, oldest first, from `folder` (default research/reserve/); with `today`,
    only those still current."""
    used = {i.get("reserve") for i in (told() if items is None else items)} - {None}
    out = []
    for path in sheets(folder):
        if os.path.splitext(os.path.basename(path))[0] in used:
            continue
        p = read_piece(path)
        if p and current(p, today):
            out.append(p)
    return out


GOOD_UNTIL_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def read_piece(path) -> Optional[Piece]:
    """A stock sheet's header: `# <title>`, then `- Topic:`, `- Format:`, `- Source:` and `- Good until:`
    lines (a sheet from before 0.35.0 has `- Slot:` and `- Category:` instead: the category is its topic)."""
    title, fields = None, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("# ") and title is None:
                title = line[2:].strip()
            m = re.match(r"- (Topic|Format|Slot|Category|Source|Good until):\s*(.*)", line, re.I)
            if m:
                fields.setdefault(m.group(1).lower(), m.group(2).strip())
    topic = fields.get("topic") or fields.get("category") or ""
    fmt = fields.get("format") or LEGACY_SLOT_FORMAT.get(fields.get("slot", "").lower(), fields.get("slot", ""))
    if not title or not (topic or fmt):
        return None
    written = fields.get("good until", "").strip()
    until = GOOD_UNTIL_RE.fullmatch(written.split()[0].rstrip(".,;")) if written else None
    if until:
        try:
            datetime.date.fromisoformat(until.group(0))
        except ValueError:
            until = None
    bad = "" if until or written.casefold().rstrip(".") in EVERGREEN else written
    slug = os.path.splitext(os.path.basename(path))[0]
    return Piece(slug, title, topic, fmt, fields.get("source", ""), until.group(0) if until else None, path, bad)


def restock(r: Recipe, topics: List[context.Topic], items, pieces) -> List[tuple]:
    """[(Topic, more)]: the topics holding fewer unused pieces than the stock keeps, the emptiest first (then
    the one due soonest), at most per_run pieces in all."""
    have = {}
    for p in pieces:
        have[p.topic.casefold()] = have.get(p.topic.casefold(), 0) + 1
    order = [t for t, _ in due(topics, items, len(topics))]
    short = sorted((t for t in order if have.get(t.name.casefold(), 0) < r.per_topic),
                   key=lambda t: (have.get(t.name.casefold(), 0), order.index(t)))
    out, left = [], r.per_run
    for t in short:
        if left <= 0:
            break
        more = min(r.per_topic - have.get(t.name.casefold(), 0), left)
        out.append((t, more))
        left -= more
    return out


def plan_facts(minutes: int, today: datetime.date, r: Recipe = None, profile=None, items=None,
               pieces=None) -> dict:
    """The plan as data (content plan --json): minutes; topics (how many the rests touch), spares, serial
    (whether the session carries one thread), in_work (pieces told during steady timed work), mix [rules]; venues [{name, note}] (whose
    upcoming shows they want to hear about); due [{topic, note, last_told (a date or null), spare}]; formats
    [{id, name, group, what, words, research, across, fits, tell, ends, avoid}] and skipped [ids]; recent_days and told_recent
    [{date, topic, format, title}]; reserve [{slug, title, topic, format, source, good_until, path}]; restock
    [{topic, note, more}]; threads [{id, date, topic, kind, what}] (left open by earlier sessions); unreadable
    [{slug, good_until, path}] (stock left out until its Good until line is a date or evergreen)."""
    r = r or recipe()
    items = told() if items is None else items
    pieces = reserve(items=items, today=today) if pieces is None else [p for p in pieces if current(p, today)]
    import interests
    lr = interests.learned(profile, today) if profile is not None else interests.Learned()
    tops = all_topics(profile, today, lr)
    b = band(r, minutes)
    skip = skipped(r, profile)
    since = (today - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    picked = due(tops, items, b.topics + b.spares, lr.strength, today)
    return {
        "minutes": minutes, "topics": b.topics, "spares": b.spares, "serial": b.serial, "in_work": b.in_work,
        "mix": list(r.mix),
        "venues": [{"name": v.name, "note": v.note or None, "learned": False}
                   for v in (context.venues(profile) if profile is not None else [])]
        + [{"name": x.name, "note": x.note or None, "learned": True} for x in lr.venues],
        "taste": [{"name": x.name, "note": x.note or None, "parent": x.parent} for x in lr.taste],
        "due": [{"topic": t.name, "note": t.note or None, "last_told": d, "spare": i >= b.topics}
                for i, (t, d) in enumerate(picked)],
        "formats": [dict(f._asdict(), fits=list(f.fits)) for f in r.formats.values() if f.id not in skip],
        "skipped": skip,
        "recent_days": RECENT_DAYS,
        "told_recent": [{"date": i["date"], "topic": item_topic(i) or None, "format": item_format(i) or None,
                         "title": i["title"]} for i in items if i["date"] >= since],
        "reserve": [{"slug": p.slug, "title": p.title, "topic": p.topic, "format": p.format, "source": p.source,
                     "good_until": p.good_until, "path": paths.show(p.path)} for p in pieces],
        "restock": [{"topic": t.name, "note": t.note or None, "more": k} for t, k in restock(r, tops, items, pieces)],
        "threads": threads(),
        "unreadable": [{"slug": p.slug, "good_until": p.bad_until, "path": paths.show(p.path)}
                       for p in unreadable(items=items)],
    }


FITS_SAYS = {"steady": "in steady work", "rest": "in a rest", "close": "at the close"}
RESEARCH_SAYS = {"news": "found on the day", "evergreen": "from the stock", "either": "the day or the stock",
                 "none": "no research: from the brief, the log or the session"}


def plan(minutes: int, today: datetime.date, r: Recipe = None, profile=None, items=None,
         pieces=None) -> List[str]:
    """The plan's lines (plan_facts, as text)."""
    f = plan_facts(minutes, today, r, profile, items, pieces)
    out = [f"# Content plan, {minutes} minutes", "",
           f"The session touches about {f['topics']} of the listener's topics"
           + (f", plus {f['spares']} spare in case there's room" if f["spares"] else "")
           + (", and carries one serial thread told across it" if f["serial"] else "")
           + ". Pick each item's format by what there is to tell and where it lands, not by habit; the brief's "
             "Talk to time line says how much each part holds.", ""]
    if f["in_work"]:
        out += [f"In the work: about {f['in_work']} pieces. Steady timed work is set up before the go (the movement, "
                "its one or two form points, the target), gets a cue in its first seconds, then carries a piece while "
                "they move, in [story] ... [/story], broken by the time checks (halfway, the last ten seconds) and a "
                "form reminder where tiredness bites. Never in a hard effort, a counted set or the named peak, never "
                "in place of a safety line, a limit cue or a count. Each is logged like any item told.", ""]
    if f["mix"]:
        out += ["## How they sit together"] + [f"- {x}" for x in f["mix"]] + [""]
    out += ["## Topics due (never told first, then the one told longest ago)"]
    out += [f"- {d['topic']}{' (spare)' if d['spare'] else ''}"
            f"{': ' + d['note'] if d['note'] else ''} ({'last told ' + d['last_told'] if d['last_told'] else 'never told'})"
            for d in f["due"]] or ["- No topics yet (## Topics in me/content.md is empty): pick broadly from today's "
                                   "news, science and history, and suggest they add topics (\"update my interests\")."]
    out += ["", "## What's on (upcoming shows near them, told as whats_on)"]
    if f["venues"]:
        out += ["Look up what's on in the next two weeks at their venues (and, for a kind of show their topics name, "
                "at the major venues near their neighborhood); tell one or two that fit, with the night:"]
        out += [f"- {v['name']}{': ' + v['note'] if v['note'] else ''}{' (learned)' if v['learned'] else ''}"
                for v in f["venues"]]
    else:
        out.append("- No venues yet (## Venues in me/content.md): when a topic names a kind of show (music, comedy, "
                   "talks, the arts), what's on at the major venues near their neighborhood still counts.")
    if f["taste"]:
        out += ["", "## Taste they've shown lately (learned; for recommendations, alongside ## Taste)"]
        out += [f"- {x['name']}{' (' + x['parent'] + ')' if x['parent'] else ''}{': ' + x['note'] if x['note'] else ''}"
                for x in f["taste"]]
    out += ["", "## Formats (pick to suit the item and where it lands; ids for content log)"]
    groups = {}
    for x in f["formats"]:
        groups.setdefault(x["group"], []).append(x)
    for group, xs in groups.items():
        out.append(f"- {group}:")
        out += [f"  - {x['id']} ({x['name']}, about {x['words']} words"
                f"{', told across the session' if x['across'] else ''}; {RESEARCH_SAYS[x['research']]}; "
                f"{', '.join(FITS_SAYS[w] for w in x['fits'])}): {x['what']}."
                + (f" Tell it: {x['tell']}." if x["tell"] else "") + (f" End on {x['ends']}." if x["ends"] else "")
                + (f" Not {x['avoid']}." if x["avoid"] else "")
                for x in xs]
    if f["skipped"]:
        out.append(f"- left out by the listener: {', '.join(f['skipped'])}")
    today_told = [i for i in f["told_recent"] if i["date"] == today.isoformat()]
    if today_told:
        out += ["", "## Already told today, in an earlier session (never again today, not even reworded)"]
        out += [f"- {i['topic'] or '?'} / {i['format'] or '?'}: {i['title']}" for i in today_told]
    out += ["", f"## Told in the last {RECENT_DAYS} days (don't tell again; a follow-up needs something new)"]
    out += [f"- {i['date']} {i['topic'] or '?'} / {i['format'] or '?'}: {i['title']}" for i in f["told_recent"]] \
        or ["- nothing yet"]
    out += ["", "## Stock (unused pieces, still current, ready to tell)"]
    out += [f"- {p['topic']} / {p['format']}: {p['title']} ({p['path']}, slug {p['slug']}"
            f"{', good until ' + p['good_until'] if p['good_until'] else ''})" for p in f["reserve"]] or ["- empty"]
    if f["unreadable"]:
        out += ["", "## Stock to fix (left out: its Good until is neither a date, YYYY-MM-DD, nor evergreen)"]
        out += [f"- {p['path']}: \"{p['good_until']}\"" for p in f["unreadable"]]
    out += ["", "## Open threads (left open by earlier sessions: bring one back when it fits, and close it once "
                "told: content thread --close <id>)"]
    out += [f"- {t['id']} ({t['date']}, {t['kind']}, {t['topic'] or '-'}): {t['what']}" for t in f["threads"]] \
        or ["- none"]
    if f["restock"]:
        out += ["", "## Restock (while the audio renders)", "Stock these topics, the emptiest first:"]
        out += [f"- {x['topic']}{': ' + x['note'] if x['note'] else ''}: {x['more']} more" for x in f["restock"]]
    return out


def parse_item(text: str, date: str, r: Recipe, profile=None) -> dict:
    """"topic | format | title [| source [| stock slug]]" as a record item; ValueError says what's wrong.
    The topic must be one of the listener's (any case), or - for an item tied to none, or the rotation would
    never see it told; the format, one of knowledge/content.toml's (its id or name)."""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 3 or not all(parts[:3]):
        raise ValueError(f"'{text}': expected 'topic | format | title [| source [| stock slug]]'")
    if len(parts) > 5:
        raise ValueError(f"'{text}': too many fields (a title can't hold a |)")
    topic, fmt, title = parts[:3]
    fid = format_id(r, fmt)
    if not fid:
        raise ValueError(f"'{text}': unknown format '{fmt}' (one of {', '.join(r.formats)})")
    if topic != NO_TOPIC:
        known = {t.name.casefold(): t.name for t in all_topics(profile)}
        if known and topic.casefold() not in known:
            raise ValueError(f"'{text}': '{topic}' isn't one of the listener's topics (one of "
                             f"{', '.join(known.values())}, or {NO_TOPIC} for none)")
        topic = known.get(topic.casefold(), topic)
    item = {"date": date, "topic": topic, "format": fid, "title": title}
    if len(parts) > 3 and parts[3]:
        item["source"] = parts[3]
    if len(parts) > 4 and parts[4]:
        if not SLUG_RE.match(parts[4]):
            raise ValueError(f"'{text}': stock slug '{parts[4]}' should be lowercase words and dashes")
        item["reserve"] = parts[4]
    return item


def log(date: str, texts: List[str], path=None, r: Recipe = None, profile=None, build: str = None) -> List[dict]:
    """Record the items a session told; `build` (the session's build id) ties them to it, so deleting the
    workout (`./harmonicfitness workouts delete`) takes them back."""
    r = r or recipe()
    datetime.date.fromisoformat(date)
    path = path or paths.TOLD
    new = [parse_item(t, date, r, profile) for t in texts]   # all checked before any is written
    for item in new:
        if build:
            item["build"] = build
    with locks.file_lock(path):   # read, check and append as one step, so a piece is told once
        return _log_new(new, path)


def _log_new(new: List[dict], path) -> List[dict]:
    used = {i.get("reserve") for i in told(path)} - {None}
    for item in new:
        slug = item.get("reserve")
        if slug and not os.path.exists(os.path.join(paths.RESERVE, slug + ".md")):
            raise ValueError(f"no stock piece '{slug}' in {paths.show(paths.RESERVE)} (a typo here would leave the real "
                             "piece unused, to be told again)")
        if slug in used:
            raise ValueError(f"stock piece '{slug}' is already told (in {paths.show(path)} or earlier in this "
                             "command); a piece is told once")
        if slug:
            used.add(slug)
    if new:
        fileio.append_jsonl(path, new)
    return new


# ---- threads: what a session left open for a later one ----------------------------------------

THREAD_KINDS = ("serial", "quiz", "follow-up", "take", "promise")
THREAD_RE = re.compile(r"^t\d+$")


def threads(path=None) -> List[dict]:
    """The open threads, oldest first: [{id, date, topic, kind, what}]. Each `content thread --open` adds an
    "open" line to threads.jsonl and each `--close` a "close" line naming its id; a thread is open until closed."""
    rows = fileio.read_jsonl(path or paths.THREADS) if os.path.exists(path or paths.THREADS) else []
    opened, closed = {}, set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            continue
        if row.get("event") == "close":
            closed.add(row["id"])
        elif row.get("event") == "open" and all(isinstance(row.get(k), str) for k in ("date", "kind", "what")):
            opened[row["id"]] = {k: row.get(k) for k in ("id", "date", "topic", "kind", "what")}
    return [t for i, t in opened.items() if i not in closed]


def parse_thread(text: str, profile=None) -> tuple:
    """(topic, kind, what) from "topic | kind | what"; ValueError says what's wrong. The kind is one of
    THREAD_KINDS: a serial to carry on, a quiz to answer, a story to follow up, the coach's take (so it stays
    the same next time), or a promise ("next week we add weight")."""
    parts = [p.strip() for p in text.split("|")]
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"'{text}': expected 'topic | kind | what' (topic - for none)")
    topic, kind, what = parts
    if kind.casefold() not in THREAD_KINDS:
        raise ValueError(f"'{text}': unknown kind '{kind}' (one of {', '.join(THREAD_KINDS)})")
    if topic != NO_TOPIC:
        known = {t.name.casefold(): t.name for t in all_topics(profile)}
        if known and topic.casefold() not in known:
            raise ValueError(f"'{text}': '{topic}' isn't one of the listener's topics (one of "
                             f"{', '.join(known.values())}, or {NO_TOPIC} for none)")
        topic = known.get(topic.casefold(), topic)
    return topic, kind.casefold(), what


def open_threads(date: str, texts: List[str], path=None, profile=None, build: str = None) -> List[dict]:
    """Record each "topic | kind | what" as an open thread (all checked before any is written); `build` ties it
    to the session that opened it."""
    datetime.date.fromisoformat(date)
    parsed = [parse_thread(t, profile) for t in texts]
    path = path or paths.THREADS
    with locks.file_lock(path):
        rows = fileio.read_jsonl(path) if os.path.exists(path) else []
        n = max([int(r["id"][1:]) for r in rows if isinstance(r, dict) and THREAD_RE.match(str(r.get("id")))]
                or [0])
        new = [dict({"event": "open", "id": f"t{n + k}", "date": date, "topic": topic, "kind": kind, "what": what},
                    **({"build": build} if build else {}))
               for k, (topic, kind, what) in enumerate(parsed, 1)]
        fileio.append_jsonl(path, new)
    return new


def close_thread(date: str, tid: str, path=None, build: str = None) -> dict:
    """Mark an open thread closed (told, answered, or no longer worth it); ValueError when it isn't open."""
    datetime.date.fromisoformat(date)
    path = path or paths.THREADS
    with locks.file_lock(path):
        if tid not in {t["id"] for t in threads(path)}:
            raise ValueError(f"no open thread '{tid}' (content plan lists the open ones)")
        row = dict({"event": "close", "id": tid, "date": date}, **({"build": build} if build else {}))
        fileio.append_jsonl(path, [row])
    return row


# ---- trending: ideas for new topics ----------------------------------------------------------

REDDIT = "https://www.reddit.com/r/popular/top.json?t=day&limit=100"


def parse_reddit(d, limit=40) -> List[tuple]:
    """[(subreddit, title)] from Reddit's listing JSON: safe for work only (the post and its community), one
    post per community, most upvoted first."""
    out, seen = [], set()
    for child in ((d or {}).get("data") or {}).get("children") or []:
        post = child.get("data") or {}
        sub = str(post.get("subreddit") or "")
        if (post.get("over_18") or post.get("subreddit_type") not in (None, "public")
                or str(post.get("whitelist_status") or "").startswith("promo_adult")
                or not sub or sub.casefold() in seen or not post.get("title")):
            continue
        seen.add(sub.casefold())
        out.append((sub, " ".join(str(post["title"]).split())[:200]))
        if len(out) >= limit:
            break
    return out


def trending(today: datetime.date, fetch=None) -> tuple:
    """(source, [line]): today's popular posts on Reddit, safe for work only; when Reddit refuses (it often
    does a client without an account), Wikipedia's most read articles of the last two days."""
    import feeds
    fetch = fetch or feeds.fetch
    try:
        posts = parse_reddit(json.loads(fetch(REDDIT)))
        if posts:
            return "Reddit's front page today (safe for work only)", [f"- r/{s}: {t}" for s, t in posts]
    except Exception:   # noqa: BLE001 - any failure falls back to Wikipedia
        pass
    lines, seen = [], set()
    for day in (today, today - datetime.timedelta(days=1)):
        try:
            parts = feeds.parse_featured(json.loads(fetch(feeds.featured_url(day))), mostread=25)
        except Exception:   # noqa: BLE001 - a day Wikipedia can't give is skipped
            continue
        for title, about, _ in parts["mostread"]:
            if title.casefold() not in seen:
                seen.add(title.casefold())
                lines.append(f"- {title}" + (f": {about}" if about else ""))
    if not lines:
        raise errors.HarmonicFitnessError("couldn't reach Reddit or Wikipedia for what's trending; try again later, "
                                          "or search the web for it")
    return "Wikipedia's most read articles (Reddit refused)", lines


def draft_build(draft_path: str) -> str:
    """The build id of the newest MP3 made from the draft as it stands (content log/thread --draft); ValueError when
    there is none."""
    import records
    try:
        rec = records.latest_build(records.draft_hash(draft_path))
    except OSError as e:
        raise ValueError(f"can't read the draft {draft_path} ({e})")
    if rec is None or not rec.get("build_id"):
        raise ValueError(f"no build of {draft_path} as it stands; build it first (or leave out --draft)")
    return rec["build_id"]


def main(argv=None):
    ap = cli.ArgumentParser(prog="harmonicfitness content", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="the topics due, the formats, what's been told, the stock")
    p.add_argument("--minutes", type=cli.positive_int, default=25, help="the session's length (default 25)")
    cli.today_arg(p)
    p.add_argument("--json", action="store_true",
                   help="the same plan as one JSON object: minutes, topics, spares, serial, in_work, mix, venues (name, note, learned), taste (name, note, parent), due (topic, note, "
                        "last_told, spare), formats (id, name, group, what, words, research, across, fits, tell, ends, avoid), skipped, "
                        "recent_days, told_recent, reserve, restock, threads (id, date, topic, kind, what), "
                        "unreadable (slug, good_until, path)")
    lg = sub.add_parser("log", help="record the items a session told")
    lg.add_argument("--date", required=True, help="the session's date, YYYY-MM-DD")
    lg.add_argument("--item", action="append", required=True,
                    help='"topic | format | title [| source [| stock slug]]", once per item; topic - for none')
    lg.add_argument("--draft", help="the session's draft: ties the items to its build, so deleting the workout "
                                    "takes them back")
    th = sub.add_parser("thread", help="open or close a thread a later session picks up")
    th.add_argument("--date", required=True, help="the session's date, YYYY-MM-DD")
    act = th.add_mutually_exclusive_group(required=True)
    act.add_argument("--open", action="append", metavar="ITEM",
                     help='"topic | kind | what", once per thread; kind one of ' + ", ".join(THREAD_KINDS)
                          + "; topic - for none")
    act.add_argument("--close", action="append", metavar="ID", help="an open thread's id (t3), once per thread")
    th.add_argument("--draft", help="the session's draft: ties the thread to its build")
    sub.add_parser("reserve", help="list the stock's unused pieces, still current")
    tr = sub.add_parser("trending", help="what's popular today, for suggesting new topics")
    cli.today_arg(tr)
    args = ap.parse_args(argv)
    # --minutes is checked by argparse; a damaged knowledge or context file is the file's problem (exit 1, through
    # cli.run), never "the command was wrong"
    if args.cmd == "plan":
        today = args.today or datetime.date.today()
        if args.json:
            print(json.dumps(plan_facts(args.minutes, today, profile=context.profile()), indent=1,
                             ensure_ascii=False))
        else:
            print("\n".join(plan(args.minutes, today, profile=context.profile())))
    elif args.cmd == "log":
        # the topics come from the profile; with no profile, any topic is taken
        prof = context.profile() if os.path.exists(paths.PROFILE) else None
        try:
            build = draft_build(args.draft) if args.draft else None
            new = log(args.date, args.item, profile=prof, build=build)   # a ValueError: an --item, --date or --draft it can't take
        except ValueError as e:
            print(f"harmonicfitness content: {e}", file=sys.stderr)
            return cli.USAGE
        print(f"Recorded {len(new)} item(s) in {paths.show(paths.TOLD)}.")
    elif args.cmd == "thread":
        prof = context.profile() if os.path.exists(paths.PROFILE) else None
        try:
            build = draft_build(args.draft) if args.draft else None
            if args.open:
                done = open_threads(args.date, args.open, profile=prof, build=build)
                print("\n".join(f"Opened {t['id']}: {t['what']}" for t in done))
            else:
                done = [close_thread(args.date, t, build=build) for t in args.close]
                print("\n".join(f"Closed {t['id']}." for t in done))
        except ValueError as e:
            print(f"harmonicfitness content: {e}", file=sys.stderr)
            return cli.USAGE
    elif args.cmd == "trending":
        source, lines = trending(args.today or datetime.date.today())
        print("\n".join([f"# Trending: {source}", ""] + lines))
    else:
        pieces = reserve(today=datetime.date.today())
        print("\n".join(f"{p.topic} / {p.format}: {p.title} ({p.slug}"
                        f"{', good until ' + p.good_until if p.good_until else ''})" for p in pieces)
              or "The stock is empty.")
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
