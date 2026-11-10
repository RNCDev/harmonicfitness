"""The bench's read of its runs: time by step, how long each writer took, and the quality checks.

  .venv/bin/python web/bench/summarize.py <label>...      (each a folder under .bench/out/)

Per run: seconds from the brief to the price, to the writers' room, in it and after it; the fixes the agent made
after the room; each writer's seconds; what the opening leaves out (the made-by-AI line, the stop rule); names in a told story that none
of the researcher's notes hold (fabrication candidates); greetings or goodbyes mid-session; weekday, month, season or weather words the listener never wants (`never_said`). Per label: the medians,
and the host's words against what it was asked, by kind of segment.
"""
import json
import os
import re
import statistics
import sys
import unicodedata

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.join(REPO, "web")]
from webapp.agent import writers  # noqa: E402

OUT = os.path.join(REPO, ".bench", "out")
STORY = re.compile(r"\[story\](.*?)\[/story\]", re.DOTALL | re.IGNORECASE)
COMMON = set("""I I'm I've I'll I'd You You're We We're It It's That That's This The A An And But So Now Then Here There
What When Where Why How If Or Not No Yes Okay Ok Alright All Right Left Good Great Nice Next One Two Three Four Five Six
Seven Eight Nine Ten Eleven Twelve Twenty Thirty Forty Fifty Hold Keep Let Let's Rest Breathe Back Down Up Go Start Stop
Today Tonight Tomorrow Yesterday Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May
June July August September October November December Coach Your My Our Their His Her They He She Just Last First
Still Even Also Well Oh Think Picture Imagine Remember Speaking Meanwhile Anyway Plus Some Most Every Each Any More Less
Very Really Quick Easy Light Big Small New Old Those These""".split())


def opening(draft):
    """What the opening (the first segment, stories aside) leaves out of what the build can't check alone: the
    made-by-AI line and the stop rule. The sides are the menu gate's; read the scripts for the rest."""
    _, segs = writers.split(draft)
    if not segs:
        return []
    body = STORY.sub(" ", "\n".join(segs[0][3]))
    out = []
    if not re.search(r"\b(?:AI|A\.I\.|artificial intelligence)\b", body):
        out.append("no made-by-AI line")
    if not re.search(r"\bstop\b", body, re.IGNORECASE):
        out.append("no stop rule")
    return out


def names(text):
    found = set()
    for sent in re.split(r"(?<=[.!?])\s+", text):
        for w in re.findall(r"[A-Za-z][\w'’-]*", sent)[1:]:
            if w[0].isupper() and w.strip("'’") not in COMMON:
                found.add(w.strip("'’").removesuffix("'s").removesuffix("’s"))
    return found


NUMBER_WORDS = set("""zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen
sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand first second
third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth
seventeenth eighteenth nineteenth twentieth thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth
hundredth thousandth""".split())


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c))


def number_name(name):
    """A name made only of number words or ordinals ("Thirtieth", "X-One": hyphen parts a letter or a number word)."""
    parts = name.lower().split("-")
    return all(len(p) == 1 or p in NUMBER_WORDS for p in parts)


def fidelity(r):
    known = fold(" ".join(json.dumps(w["output"], ensure_ascii=False) + " " + w["prompt"] for w in r["writers"]
                          if w["who"] in ("research", "top-up")))
    draft = r["draft"] or ""
    unknown = sorted({n for s in STORY.findall(draft) for n in names(s)
                      if fold(n) not in known and not number_name(n)})
    odd = []
    segs = re.split(r"^@@.*$", draft, flags=re.MULTILINE)[1:]
    for i, body in enumerate(segs[1:-1], 2):
        plain = STORY.sub("", body).lower()
        if re.search(r"\b(welcome|good morning|good evening|hey there|hi there)\b", plain):
            odd.append(f"#{i} greeting")
        if re.search(r"\b(that's a wrap|see you next time|great work today|that's the session|until next time)\b", plain):
            odd.append(f"#{i} wrap-up")
    return unknown, odd


WEEKDAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()
MONTHS = "January February March April June July August September October November December".split()  # not May: a verb
SEASONS = "spring summer autumn winter".split()
WEATHER = "rain rainy raining sunny snow snowy snowing cloudy windy humid forecast".split()


def never_said(draft, content_md):
    """The weekday, month, season and weather words a script says when the listener's `## Never bring up` section
    names the day, the date, the season or the weather. Only the spoken lines are read, `@@` lines aside."""
    m = re.search(r"^## Never bring up\s*\n(.*?)(?=^## |\Z)", content_md, re.MULTILINE | re.DOTALL)
    rule = m.group(1).lower() if m else ""
    words = []
    if re.search(r"day of the week|weekday", rule):
        words += WEEKDAYS
    if re.search(r"\bdate\b", rule):
        words += MONTHS
    if "season" in rule:
        words += SEASONS
    if "weather" in rule:
        words += WEATHER
    if not words:
        return []
    spoken = STORY.sub(" ", draft or "")   # the rule is about the present; a story carries historical dates
    spoken = re.sub(r"^@@.*$", " ", spoken, flags=re.MULTILINE)
    spoken = re.sub(r"\[[^\]]*\]", " ", spoken)
    found = []
    for w in re.findall(r"[A-Za-z]+", spoken):
        if w.lower() in {x.lower() for x in words} and w not in found:
            found.append(w)
    return found


def words_by_kind(r):
    """(kind, host words / asked, story words / its share, coaching words / its share) for each segment."""
    hosts = [w for w in r["writers"] if w["who"] == "host"]
    if not hosts:
        return []
    h, out = hosts[-1], []
    meta = {}
    for b in re.split(r"\n(?=## #\d+ )", h["prompt"]):
        m = re.match(r"## #(\d+) at [\d:]+, (\d+) s, (.*?)\nWrite about (\d+) words\.(?: About (\d+) of them are the story)?", b)
        if m:
            meta[int(m.group(1))] = (m.group(3), int(m.group(4)), int(m.group(5) or 0), "Tell this story" in b)
    last = max(meta) if meta else 0
    for s in h["output"]["segments"]:
        n = s["number"]
        if n not in meta or not meta[n][1]:
            continue
        label, asked, story_ask, has = meta[n]
        words = len(re.sub(r"\[[^\]]*\]", " ", s["text"]).split())
        st = STORY.search(s["text"])
        sw = len(re.sub(r"\[[^\]]*\]", " ", st.group(1)).split()) if st else 0
        low = label.lower()
        rest = re.search(r"\b(rest|transition)\b", low)
        kind = ("welcome" if n == 1 else "close" if n == last else "rest+story" if has and rest else
                "set+story" if has else "rest" if rest else "later set" if re.search(r"set [2-9]", low) else "first set")
        out.append((kind, words / asked, sw / story_ask if story_ask else None,
                    (words - sw) / max(1, asked - story_ask) if story_ask else None))
    return out


def host_against_budget(r, commands):
    """The last host's words (outside markers) over the skeleton's word budgets, from the lint report of the last
    skeleton the room was given; None without a host or that report."""
    hosts = [w for w in r["writers"] if w["who"] == "host"]
    skeleton = [c for c in commands if c["argv"][:1] == ["build"] and "--lint-only" in c["argv"]
                and "no words yet" in (c["error"] or "")]
    if not hosts or not skeleton:
        return None
    budget = sum(writers.budgets(skeleton[-1]["output"]).values())
    words = sum(len(re.sub(r"\[[^\]]*\]", " ", seg["text"]).split()) for seg in hosts[-1]["output"]["segments"])
    return words / budget if budget else None


def facts(path):
    with open(path, encoding="utf-8") as f:
        r = json.load(f)
    ev = r["events"]
    brief = next((e["t"] for e in ev if (e["tool"] or "").startswith("run brief") and e["code"] is None), None)
    last = r["turns"][-1]
    end = last["start"] + last["seconds"]
    room_start = next((ln["t"] for ln in r["room"] if "straight to the writers" in ln["line"]), None) or next(
        (e["t"] for e in ev if e["tool"] == "write_script" and e["code"] is None), None)
    room_end = next((ln["t"] for ln in r["room"] if ln["line"].startswith("room wrote the script")), None) or next(
        (w["t"] for w in reversed(r["writers"])), None)
    after = [e for e in ev if e["code"] is not None and room_end is not None and e["t"] > room_end]
    writers_s = {}
    for ln in r["room"]:
        m = re.match(r"room (research|trainer|host|review|top-up) (\w+) ([\d.]+)s", ln["line"])
        if m:
            writers_s.setdefault(m.group(1), []).append(float(m.group(3)))
        m = re.match(r"room research waited for ([\d.]+)s", ln["line"])
        if m:
            writers_s["research wait"] = [float(m.group(1))]
        if "research was ready" in ln["line"]:
            writers_s["research wait"] = [0.0]
    unknown, odd = fidelity(r)
    try:
        with open(os.path.join(os.path.dirname(path), "commands.jsonl"), encoding="utf-8") as f:
            commands = [json.loads(ln) for ln in f if ln.strip()]
    except OSError:
        commands = []
    against = host_against_budget(r, commands)
    try:
        with open(os.path.join(os.path.dirname(path), "home", "content.md"), encoding="utf-8") as f:
            content = f.read()
    except OSError:
        content = ""   # a run kept without its home (the committed examples) has no rule to read
    return {"run": os.path.basename(os.path.dirname(path)), "priced": bool(r["offer"]), "total": round(end, 1),
            "from_brief": round(end - brief, 1) if brief is not None else None,
            "to_room": round(room_start - brief, 1) if room_start and brief is not None else None,
            "room": round(room_end - room_start, 1) if room_start and room_end else None,
            "after_room": round(end - room_end, 1) if room_end else None,
            "fixes_after": sum(1 for e in after if e["tool"] == "edit_segments"),
            "reviews": len(writers_s.get("review", [])),
            "host_vs_budget": round(against, 2) if against is not None else None,
            "writers": {k: round(sum(v), 1) for k, v in writers_s.items()},
            "opening": opening(r["draft"]) if r["draft"] else ["no draft"],
            "not_in_notes": unknown, "one_voice": odd,
            "never_said": never_said(r["draft"], content), "lint_clean": bool(r["final_lint"]) and "Fix and rerun" not in r["final_lint"],
            "error": last["error"]}, words_by_kind(r)


def main(labels):
    for label in labels:
        d = os.path.join(OUT, label)
        rows, kinds = [], {}
        for n in sorted(os.listdir(d), key=lambda x: int(x) if x.isdigit() else 0):
            p = os.path.join(d, n, "result.json")
            if os.path.exists(p):
                f, k = facts(p)
                rows.append(f)
                for kind, *ratios in k:
                    kinds.setdefault(kind, []).append(ratios)
        print(f"## {label}")
        for f in rows:
            print(json.dumps(f))
        ok = [f for f in rows if f["priced"]]
        for k in ("from_brief", "to_room", "room", "after_room", "fixes_after", "reviews"):
            vals = [f[k] for f in ok if f[k] is not None]
            if vals:
                print(f"  median {k}: {statistics.median(vals):.1f}  ({', '.join(f'{v:.0f}' for v in vals)})")
        vals = [f["host_vs_budget"] for f in ok if f["host_vs_budget"] is not None]
        if vals:
            print(f"  host words against the budget, median: {statistics.median(vals):.2f}  ({', '.join(f'{v:.2f}' for v in vals)})")
        for w in ("research", "research wait", "top-up", "trainer", "host", "review"):
            vals = [f["writers"][w] for f in ok if w in f["writers"]]
            if vals:
                print(f"  median {w}: {statistics.median(vals):.1f}  ({', '.join(f'{v:.0f}' for v in vals)})")
        print("  host words against asked, median by kind (story and coaching against their shares):")
        for kind, v in sorted(kinds.items()):
            st = [s for _, s, _ in v if s]
            co = [c for _, _, c in v if c]
            print(f"    {kind:10} n={len(v):3} {statistics.median([t for t, _, _ in v]):.2f}"
                  + (f"  story {statistics.median(st):.2f}  coaching {statistics.median(co):.2f}" if st else ""))
        print(f"  priced {len(ok)}/{len(rows)}")


if __name__ == "__main__":
    main(sys.argv[1:])
