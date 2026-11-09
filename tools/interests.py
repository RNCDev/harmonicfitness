#!/usr/bin/env python3
"""What the listener has shown they like, as evidence that builds and fades (./harmonicfitness interests).

Every signal is one line in me/workouts/research/interests.jsonl: a topic they mentioned enjoying, a venue, a
place or show for their taste, a movement they liked or didn't, or that a session felt too easy or too hard,
each with a weight (+1 a plain mention or "loved it", -1 "not for me", up to +-2 for strong words), where it came
from (a mention, a feedback line, a rating) and the day. An interest's strength is the sum of its signals, each
halving every `half_life_days` (knowledge/content.toml, [interests]), plus a share of its children's (a comedian's
signals count toward "stand-up comedy"). So a one-off fades by itself and what keeps coming back rises.

The listener's own lines (## Topics and ## Venues in content.md, likes and dislikes in training.md) are pinned:
they never fade or drop. What's learned joins them where it's strong enough: the content plan rotates learned
topics by strength, the brief's screen adds learned likes and dislikes, and an effort lean says whether
sessions have felt too easy or too hard. A learned name under ## Never bring up is never used. `apply` writes
what's learned, strongest first, as a section of its own in content.md and training.md ("## Learned from you"),
regenerated each time; the listener's own lines are never moved or rewritten.

    ./harmonicfitness interests                          # what's learned, strongest first
    ./harmonicfitness interests --json
    ./harmonicfitness interests add --source mention \\
        --signal "topic | Atsuko Okatsuka | 1 | stand-up comedy | saw her at the Bell House" \\
        --signal "venue | The Bell House | 1"
    ./harmonicfitness interests forget "Atsuko Okatsuka"
    ./harmonicfitness interests apply                    # rewrite the Learned sections
"""
import argparse
import datetime
import json
import os
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context  # noqa: E402
import errors  # noqa: E402
import fileio  # noqa: E402
import frontmatter  # noqa: E402
import locks  # noqa: E402
import store  # noqa: E402
import paths  # noqa: E402

KINDS = ("topic", "venue", "taste", "movement", "effort")
SOURCES = ("mention", "feedback", "rating")
MAX_WEIGHT = 2.0
SECTION = "Learned from you"
EFFORT = "effort"   # the one name an effort signal takes: + harder wanted, - easier


@dataclass(frozen=True)
class Tuning:
    half_life_days: float = 90.0   # a signal's weight halves this often
    keep: float = 0.3              # a learned topic, venue or taste counts from this strength
    like: float = 0.5              # a learned movement like from this strength
    dislike: float = 0.75          # a learned dislike (it takes a movement off the menu) from minus this
    lean: float = 0.75             # an effort lean from this strength either way
    parent_share: float = 0.5      # the share of a child's strength its parent gets
    learned_max: int = 10          # learned topics in the plan's pool, strongest first
    per_event_max: int = 12        # signals one `add` may write
    rating_weight: float = 0.5     # a rating's signal on each topic its workout told


def tuning(path=None) -> Tuning:
    """knowledge/content.toml's [interests], each value falling back to Tuning's default."""
    try:
        with open(path or paths.CONTENT, "rb") as f:
            raw = tomllib.load(f).get("interests", {})
    except (OSError, tomllib.TOMLDecodeError):
        raw = {}
    base = Tuning()
    values = {}
    for name in Tuning.__dataclass_fields__:
        v = raw.get(name, getattr(base, name))
        values[name] = type(getattr(base, name))(v) if isinstance(v, (int, float)) and not isinstance(v, bool) \
            else getattr(base, name)
    return Tuning(**values)


@dataclass
class Interest:
    kind: str
    name: str                  # as most recently written
    strength: float = 0.0
    signals: int = 0
    last: str = ""             # the latest signal's date
    parent: Optional[str] = None
    note: str = ""             # the latest note


def _record(r: dict) -> Optional[dict]:
    """A readable evidence line, or None: a known kind, a name, a numeric weight, an ISO date."""
    try:
        if r.get("kind") not in KINDS or not str(r.get("name") or "").strip():
            return None
        float(r["weight"])
        datetime.date.fromisoformat(str(r["date"]))
        return r
    except (KeyError, TypeError, ValueError):
        return None


def evidence(path=None) -> List[dict]:
    """Every readable signal, oldest first; a damaged line is skipped."""
    return list(fileio.read_jsonl(path or paths.INTERESTS, _record))


def _age(date: str, today: datetime.date) -> float:
    return max((today - datetime.date.fromisoformat(date)).days, 0)


def strengths(records: List[dict], today: datetime.date, t: Tuning = None) -> Dict[tuple, Interest]:
    """{(kind, casefolded name): Interest}: each signal's weight halved every half_life_days, summed, then each
    parent (a topic) given parent_share of its children's own strength."""
    t = t or tuning()
    out: Dict[tuple, Interest] = {}
    for r in records:
        name = str(r["name"]).strip()
        key = (r["kind"], name.casefold())
        x = out.setdefault(key, Interest(r["kind"], name))
        x.name, x.signals = name, x.signals + 1
        x.strength += float(r["weight"]) * 0.5 ** (_age(str(r["date"]), today) / t.half_life_days)
        if str(r["date"]) >= x.last:
            x.last = str(r["date"])
            x.parent = (str(r.get("parent") or "").strip() or None) if r.get("parent") is not None else x.parent
            x.note = str(r.get("note") or "") or x.note
    own = {k: x.strength for k, x in out.items()}
    for k, x in list(out.items()):
        if x.parent and own[k] > 0:
            p = out.setdefault(("topic", x.parent.casefold()), Interest("topic", x.parent))
            p.strength += t.parent_share * own[k]
    return out


def never(p) -> List[str]:
    """The listener's Never bring up lines, casefolded (template hints left out)."""
    out = []
    for _, line in frontmatter.section(p.body, "Never bring up"):
        text = line.strip().lstrip("-* ").strip()
        if text and not text.startswith("[") and text.casefold() not in ("nothing", "none"):
            out.append(text.casefold())
    return out


def _blocked(name: str, blocks: List[str]) -> bool:
    n = name.casefold()
    return any(b and (b in n or n in b) for b in blocks)


@dataclass
class Learned:
    """What the evidence adds to the listener's own lines, today."""
    topics: List[Interest] = field(default_factory=list)      # learned, not pinned, strongest first (capped)
    venues: List[Interest] = field(default_factory=list)
    taste: List[Interest] = field(default_factory=list)
    likes: List[str] = field(default_factory=list)            # movement names
    dislikes: List[str] = field(default_factory=list)
    effort: float = 0.0                                       # + harder wanted, - easier
    strength: Dict[str, float] = field(default_factory=dict)  # every topic's (pinned too), casefolded: for rotation


def learned(p, today: Optional[datetime.date] = None, records: Optional[List[dict]] = None,
            t: Optional[Tuning] = None) -> Learned:
    """What's learned for profile `p` on `today`: pinned topics keep a strength of at least a quarter (one with
    no evidence is 1); learned ones count from `keep`, never one under Never bring up or already pinned."""
    today = today or datetime.date.today()
    t = t or tuning()
    found = strengths(evidence() if records is None else records, today, t)
    blocks = never(p)
    pinned = {x.name.casefold() for x in context.topics(p)}
    pinned_venues = {x.name.casefold() for x in context.venues(p)}
    out = Learned()

    def ranked(kind):
        return sorted((x for (k, _), x in found.items() if k == kind), key=lambda x: -x.strength)
    for x in ranked("topic"):
        if x.name.casefold() in pinned:
            continue
        if x.strength >= t.keep and not _blocked(x.name, blocks) and len(out.topics) < t.learned_max:
            out.topics.append(x)
    out.venues = [x for x in ranked("venue") if x.strength >= t.keep and x.name.casefold() not in pinned_venues
                  and not _blocked(x.name, blocks)]
    out.taste = [x for x in ranked("taste") if x.strength >= t.keep and not _blocked(x.name, blocks)]
    out.likes = [x.name for x in ranked("movement") if x.strength >= t.like]
    out.dislikes = [x.name for x in ranked("movement") if x.strength <= -t.dislike]
    effort = found.get(("effort", EFFORT))
    out.effort = round(effort.strength, 2) if effort else 0.0
    for name in pinned:
        x = found.get(("topic", name))
        out.strength[name] = max(0.25, 1.0 + (x.strength if x else 0.0))
    for x in out.topics:
        out.strength[x.name.casefold()] = x.strength
    return out


def lean(lr: Learned, t: Optional[Tuning] = None) -> Optional[str]:
    """"harder" or "easier" when recent feedback leans that way, else None."""
    t = t or tuning()
    return "harder" if lr.effort >= t.lean else "easier" if lr.effort <= -t.lean else None


# ---- writing ------------------------------------------------------------------------------------------

def parse_signal(text: str) -> dict:
    """"kind | name | weight [| parent [| note]]" as a signal; ValueError says what's wrong."""
    parts = [x.strip() for x in str(text).split("|")]
    if len(parts) < 3:
        raise ValueError(f"\"{text}\": a signal is \"kind | name | weight [| parent [| note]]\"")
    kind, name, weight = parts[0].casefold(), parts[1], parts[2]
    if kind not in KINDS:
        raise ValueError(f"\"{text}\": the kind is one of {', '.join(KINDS)}")
    if not name or any(c in name for c in "\n\r"):
        raise ValueError(f"\"{text}\": give a name")
    if kind == "effort":
        name = EFFORT
    try:
        w = float(weight)
    except ValueError:
        raise ValueError(f"\"{text}\": the weight is a number from -{MAX_WEIGHT:g} to {MAX_WEIGHT:g}") from None
    if not -MAX_WEIGHT <= w <= MAX_WEIGHT or w == 0:
        raise ValueError(f"\"{text}\": the weight is a number from -{MAX_WEIGHT:g} to {MAX_WEIGHT:g}, not zero")
    out = {"kind": kind, "name": name, "weight": w}
    if len(parts) > 3 and parts[3]:
        out["parent"] = parts[3]
    if len(parts) > 4 and parts[4]:
        out["note"] = " ".join(parts[4:]).strip()[:200]
    return out


def add(signals: List[dict], source: str, date: Optional[str] = None, build: Optional[str] = None,
        key: Optional[str] = None, path=None, t: Optional[Tuning] = None) -> int:
    """Record `signals` (from parse_signal) from `source`; with `key`, every earlier line with that key goes first
    (a rating replaced). At most per_event_max at once. Returns how many were written."""
    t = t or tuning()
    path = path or paths.INTERESTS
    if source not in SOURCES:
        raise ValueError(f"the source is one of {', '.join(SOURCES)}")
    if len(signals) > t.per_event_max:
        raise ValueError(f"at most {t.per_event_max} signals at once (the strongest: the graph grows over time)")
    date = date or datetime.date.today().isoformat()
    datetime.date.fromisoformat(date)
    rows = [dict(s, date=date, source=source, **({"build": build} if build else {}), **({"key": key} if key else {}))
            for s in signals]
    if key:
        _rewrite(path, lambda r: r.get("key") != key)
    if rows:
        fileio.append_jsonl(path, rows)
    return len(rows)


def _rewrite(path, keep) -> int:
    """Keep the evidence lines `keep` accepts, under the file's lock; how many went."""
    if not os.path.exists(path):
        return 0
    with locks.file_lock(path):
        rows = list(fileio.read_jsonl(path))
        kept = [r for r in rows if keep(r)]
        if len(kept) != len(rows):
            fileio.atomic_write(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
        return len(rows) - len(kept)


def forget(name: str, path=None) -> int:
    """Every signal for `name` (any kind) removed; how many went."""
    n = name.strip().casefold()
    return _rewrite(path or paths.INTERESTS, lambda r: str(r.get("name") or "").strip().casefold() != n)


def forget_builds(build_ids, path=None) -> int:
    """The signals a deleted workout's ratings and feedback left (by build id) removed; how many went."""
    ids = set(b for b in build_ids if b)
    return _rewrite(path or paths.INTERESTS, lambda r: r.get("build") not in ids) if ids else 0


def rating(build: str, value: str, topics: List[str], date: Optional[str] = None, path=None,
           t: Optional[Tuning] = None) -> int:
    """A workout's rating as a small signal on each topic it told: positive +rating_weight, negative minus it,
    neutral or none nothing. Replaces this workout's rating signals before (key rating:<build>)."""
    t = t or tuning()
    w = {"positive": t.rating_weight, "negative": -t.rating_weight}.get(value)
    names = list(dict.fromkeys(x for x in topics if x and x != "-"))
    signals = [{"kind": "topic", "name": x, "weight": w} for x in names][:t.per_event_max] if w else []
    return add(signals, "rating", date=date, build=build, key=f"rating:{build}", path=path, t=t)


def _replace_section(text: str, lines: List[str]) -> str:
    """`text` with its `## Learned from you` section replaced by `lines` (added at the end when missing; removed
    when `lines` is empty)."""
    rows = text.split("\n")
    start = frontmatter.heading_index(rows, SECTION)
    if start is None:
        if not lines:
            return text
        return text.rstrip("\n") + "\n\n" + "\n".join([f"## {SECTION}"] + lines) + "\n"
    end = next((i for i in range(start + 1, len(rows)) if frontmatter.heading(rows[i]) is not None), len(rows))
    block = ([f"## {SECTION}"] + lines + [""]) if lines else []
    out = rows[:start] + block + rows[end:]
    while len(out) > 1 and out[-1] == "" and out[-2] == "":
        out.pop()
    return "\n".join(out)


def _when(x: Interest) -> str:
    if not x.signals:   # a broader topic known only through what's under it
        return "from what's under it"
    return f"{x.signals} signal{'s' if x.signals != 1 else ''}, last {x.last}"


def content_lines(lr: Learned) -> List[str]:
    if not (lr.topics or lr.venues or lr.taste):
        return []
    out = ["The coach keeps this list from your feedback and what you've told it you enjoyed, strongest first, and "
           "rewrites it each time: to drop one, tell the coach, or put it under Never bring up. Your own lines "
           "above always stay."]
    for title, xs in (("Topics", lr.topics), ("Venues", lr.venues), ("Taste", lr.taste)):
        if xs:
            out.append(f"{title}:")
            out += [f"- {x.name}{' (part of ' + x.parent + ')' if x.parent else ''}: strength {x.strength:.1f}, "
                    f"{_when(x)}{'; ' + x.note if x.note else ''}" for x in xs]
    return out


def training_lines(lr: Learned, t: Optional[Tuning] = None) -> List[str]:
    way = lean(lr, t)
    if not (lr.likes or lr.dislikes or way):
        return []
    out = ["The coach keeps this list from your feedback and rewrites it each time; your own likes and dislikes "
           "above always stay."]
    if lr.likes:
        out.append(f"- Liked lately: {', '.join(lr.likes)}")
    if lr.dislikes:
        out.append(f"- Not for you lately (left off the menu): {', '.join(lr.dislikes)}")
    if way:
        out.append(f"- Recent sessions felt too {'easy' if way == 'harder' else 'hard'}: aiming a little {way}")
    return out


def apply(p=None, today: Optional[datetime.date] = None) -> List[str]:
    """Rewrite the Learned sections of content.md and training.md from the evidence; the files written."""
    p = p or context.profile()
    lr = learned(p, today)
    written = []
    for path, lines in ((paths.CONTENT_MD, content_lines(lr)), (paths.TRAINING, training_lines(lr))):
        if not os.path.exists(path):
            continue
        with locks.file_lock(path):   # as every writer of these files takes it
            text = store.read_raw(path)
            new = _replace_section(text, lines)
            if new != text:
                fileio.atomic_write(path, new)
                written.append(path)
    return written


# ---- reading out ----------------------------------------------------------------------------------------

def facts(p, today: Optional[datetime.date] = None) -> dict:
    """What's learned, as data (--json): topics, venues, taste [{name, strength, signals, last, parent, note}];
    likes, dislikes [movement names]; effort (the lean's strength) and lean ("harder", "easier" or null)."""
    lr = learned(p, today)

    def row(x):
        return {"name": x.name, "strength": round(x.strength, 2), "signals": x.signals, "last": x.last,
                "parent": x.parent, "note": x.note or None}
    return {"topics": [row(x) for x in lr.topics], "venues": [row(x) for x in lr.venues],
            "taste": [row(x) for x in lr.taste], "likes": lr.likes, "dislikes": lr.dislikes,
            "effort": lr.effort, "lean": lean(lr)}


def text(f: dict) -> List[str]:
    out = []
    for title, key in (("Topics", "topics"), ("Venues", "venues"), ("Taste", "taste")):
        xs = f[key]
        out.append(f"{title} learned: " + ("none yet" if not xs else ""))
        out += [f"  {x['name']}{' (part of ' + x['parent'] + ')' if x['parent'] else ''}: {x['strength']:.2f}, "
                + (f"{x['signals']} signal(s), last {x['last']}" if x["signals"] else "from what's under it")
                for x in xs]
    out.append("Movements liked lately: " + (", ".join(f["likes"]) or "none"))
    out.append("Movements not for them lately: " + (", ".join(f["dislikes"]) or "none"))
    out.append(f"Effort: {f['effort']:+.2f}" + (f" (lean {f['lean']})" if f["lean"] else " (no lean)"))
    return out


def main(argv=None):
    import cli
    ap = cli.ArgumentParser(prog="harmonicfitness interests", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true",
                    help="what's learned as one JSON object: topics, venues, taste (name, strength, signals, last, "
                         "parent, note), likes, dislikes, effort, lean")
    sub = ap.add_subparsers(dest="cmd")
    ad = sub.add_parser("add", help="record signals, then rewrite the Learned sections")
    ad.add_argument("--signal", action="append", default=[], metavar="\"kind | name | weight [| parent [| note]]\"",
                    help=f"kind one of {', '.join(KINDS)}; weight -2 to 2 (1 a plain mention or liked it, 2 loved it, "
                         "-1 not for them, -2 never again); parent: the broader topic it belongs to (a comedian's: "
                         "stand-up comedy, a chef's: their cuisine); `effort | effort | 1` for too easy, -1 too hard. "
                         "A movement by its name in the workout. At most twelve at once; pain or soreness is never a "
                         "signal (the next check-in asks)")
    ad.add_argument("--source", required=True, choices=SOURCES)
    ad.add_argument("--build", help="the workout's build id, for feedback on one (deleting it takes these back)")
    ad.add_argument("--date", help="the day on record, YYYY-MM-DD (default today)")
    fo = sub.add_parser("forget", help="remove every signal for a name, then rewrite the Learned sections")
    fo.add_argument("name")
    sub.add_parser("apply", help="rewrite the Learned sections of content.md and training.md")
    args = ap.parse_args(argv)
    p = context.profile()
    if args.cmd == "add":
        try:
            signals = [parse_signal(s) for s in args.signal]
            n = add(signals, args.source, date=args.date, build=args.build)
        except ValueError as e:
            raise cli.Usage(str(e)) from None
        apply()
        print(f"Recorded {n} signal(s).")
        return errors.OK
    if args.cmd == "forget":
        n = forget(args.name)
        apply()
        print(f"Forgot {n} signal(s) for {args.name}." if n else f"Nothing was recorded for {args.name}.")
        return errors.OK
    if args.cmd == "apply":
        done = apply()
        print("Rewrote " + (", ".join(paths.show(x) for x in done) if done else "nothing (already current)"))
        return errors.OK
    f = facts(p)
    print(json.dumps(f, indent=1, ensure_ascii=False) if args.json else "\n".join(text(f)))
    return errors.OK


if __name__ == "__main__":
    import cli
    sys.exit(cli.run(main))
