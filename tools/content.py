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
from typing import Dict, List, NamedTuple, Optional

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


class Band(NamedTuple):
    up_to: int
    topics: int
    spares: int
    serial: bool


class Recipe(NamedTuple):
    formats: Dict[str, Format]
    bands: List[Band]
    per_topic: int
    per_run: int


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
                                   bool(f.get("across"))) for f in data["format"]}
        bands = sorted((Band(int(b["up_to"]), int(b["topics"]), int(b.get("spares", 0)), bool(b.get("serial")))
                        for b in data["band"]), key=lambda b: b.up_to)
        stock = data.get("stock", {})
        per_topic, per_run = int(stock.get("per_topic", 2)), int(stock.get("per_run", 6))
    except (KeyError, TypeError, ValueError) as e:
        raise errors.ContextError(f"{paths.show(path)}: a format or band is missing a field or has the wrong type "
                                  f"({e})") from e
    bad = [f.id for f in formats.values() if f.research not in RESEARCH]
    if bad:
        raise errors.ContextError(f"{paths.show(path)}: research must be one of {', '.join(RESEARCH)} "
                                  f"(not for {', '.join(bad)})")
    if not bands:
        raise errors.ContextError(f"{paths.show(path)}: no [[band]]")
    return Recipe(formats, bands, per_topic, per_run)


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


def due(topics: List[context.Topic], items: List[dict], n: int) -> List[tuple]:
    """The n topics to tell next, as (Topic, last date or None): never told first, in the listener's order,
    then the one told longest ago. Fewer topics than n are all of them."""
    last = last_told(items)
    ranked = sorted(topics, key=lambda t: (t.name.casefold() in last, last.get(t.name.casefold(), ""),
                                           topics.index(t)))
    return [(t, last.get(t.name.casefold())) for t in ranked[:n]]


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
    (whether the session carries one thread); due [{topic, note, last_told (a date or null), spare}]; formats
    [{id, name, group, what, words, research, across}] and skipped [ids]; recent_days and told_recent
    [{date, topic, format, title}]; reserve [{slug, title, topic, format, source, good_until, path}]; restock
    [{topic, note, more}]; threads [{id, date, topic, kind, what}] (left open by earlier sessions); unreadable
    [{slug, good_until, path}] (stock left out until its Good until line is a date or evergreen)."""
    r = r or recipe()
    items = told() if items is None else items
    pieces = reserve(items=items, today=today) if pieces is None else [p for p in pieces if current(p, today)]
    tops = context.topics(profile) if profile is not None else []
    b = band(r, minutes)
    skip = skipped(r, profile)
    since = (today - datetime.timedelta(days=RECENT_DAYS)).isoformat()
    picked = due(tops, items, b.topics + b.spares)
    return {
        "minutes": minutes, "topics": b.topics, "spares": b.spares, "serial": b.serial,
        "due": [{"topic": t.name, "note": t.note or None, "last_told": d, "spare": i >= b.topics}
                for i, (t, d) in enumerate(picked)],
        "formats": [f._asdict() for f in r.formats.values() if f.id not in skip],
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


RESEARCH_SAYS = {"news": "found on the day", "evergreen": "from the stock", "either": "the day or the stock",
                 "none": "no research: from the brief, the log or the session"}


def plan(minutes: int, today: datetime.date, r: Recipe = None, profile=None, items=None,
         pieces=None) -> List[str]:
    """The plan's lines (plan_facts, as text)."""
    f = plan_facts(minutes, today, r, profile, items, pieces)
    out = [f"# Rests plan, {minutes} minutes", "",
           f"The rests touch about {f['topics']} of the listener's topics"
           + (f", plus {f['spares']} spare in case there's room" if f["spares"] else "")
           + (", and carry one serial thread told across the session" if f["serial"] else "")
           + ". Judge each find by how big it is: a routine result is a quick hit; a big move, a breakthrough or "
             "a great long read earns the big story, an explainer or the serial. Mix the formats; the brief's "
             "Talk to time line says how much the rests hold.", "",
           "## Topics due (never told first, then the one told longest ago)"]
    out += [f"- {d['topic']}{' (spare)' if d['spare'] else ''}"
            f"{': ' + d['note'] if d['note'] else ''} ({'last told ' + d['last_told'] if d['last_told'] else 'never told'})"
            for d in f["due"]] or ["- No topics yet (## Topics in me/content.md is empty): pick broadly from today's "
                                   "news, science and history, and suggest they add topics (\"update my interests\")."]
    out += ["", "## Formats (pick to suit the item; ids for content log)"]
    groups = {}
    for x in f["formats"]:
        groups.setdefault(x["group"], []).append(x)
    for group, xs in groups.items():
        out.append(f"- {group}:")
        out += [f"  - {x['id']} ({x['name']}, about {x['words']} words"
                f"{', told across rests' if x['across'] else ''}; {RESEARCH_SAYS[x['research']]}): {x['what']}"
                for x in xs]
    if f["skipped"]:
        out.append(f"- left out by the listener: {', '.join(f['skipped'])}")
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
        known = {t.name.casefold(): t.name for t in (context.topics(profile) if profile is not None else [])}
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
        known = {t.name.casefold(): t.name for t in (context.topics(profile) if profile is not None else [])}
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
                   help="the same plan as one JSON object: minutes, topics, spares, serial, due (topic, note, "
                        "last_told, spare), formats (id, name, group, what, words, research, across), skipped, "
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
