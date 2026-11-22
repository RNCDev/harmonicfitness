"""A blind read of two arms' scripts, pair by pair, by Claude Opus through the CLI: for the maintainer's bench only.

  .venv/bin/python web/bench/judge.py <baseline-label> <candidate-label> [--runs 1,2,3] [--model <id>] [--salt <text>]
  .venv/bin/python web/bench/judge.py <baseline-label> <candidate-label> --prepare     (then, once judged: --tally)

--prepare writes each judgment's reading as a folder (.bench/judge/<a hash>/<run>-<a or b>/: task.md,
listener.md, request.txt, first.txt, second.txt) for a judge the CLI can't reach (a Claude Code subagent on Opus,
say: "read task.md there and do what it says"), which writes verdict.json beside them; --tally reads those. The
folder names tell the judge nothing of the arms (<run>-a has the baseline first).

Each pair is run <n> of both labels (.bench/out/<label>/<n>), the same request and listener. The judge reads the
listener's files and both scripts, named only "first" and "second", and each pair is judged twice, once in each
order, so a lean toward a position cancels. It scores each script from 1 to 5 on what the listener hears (safe,
coached, one human voice, stories, theirs), names an overall preference, and lists each script's defects by segment
number with the words quoted, so every one can be checked in the text. Prints each judgment, then the candidate's
wins, ties and losses and its mean score less the baseline's by criterion. Judgments are kept in
.bench/claude-cache by what was read; --salt asks again.

It measures a preference, with noise: judge a baseline against its own rerun first, and read a difference only
against that.
"""
import argparse
import asyncio
import hashlib
import json
import os
import statistics
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [os.path.dirname(os.path.abspath(__file__))]
import claude_cli  # noqa: E402

OUT = os.path.join(REPO, ".bench", "out")
CRITERIA = ("safety", "coaching", "voice", "stories", "personal")
SYSTEM = """You judge scripts for an audio workout: a narrated MP3 for earbuds, with no screen and no timer. The audio is the workout. It tells one listener what to do, keeps them company, and moves them along on time. The coach sets each movement up before the go, then keeps them company: steady timed work and the rests carry stories from the listener's own interests (inside [story] ... [/story]), while hard efforts and counted sets keep to short cues. The priorities, in order: safe for the listener's body today, clean to the ear, worth listening to.

A script is a list of segments. Each starts with a line `@@ <seconds> | <label>`, which is never spoken. Markers in square brackets are not spoken either: [count 3 go] is a recorded count-in and go, [reps 12] is the quiet while the listener does the reps, [hold], [pause] and [chime] are timing, [cue rest] a recorded cue. A separate build already holds each script to its clock and to what a voice can read, so don't judge length, timing or formatting. Judge what the listener would hear.

You are given the listener's own files, their request, and two scripts written for it, called first and second. Read both whole, as the listener, then score each from 1 (poor) to 5 (excellent) on:
- safety: the opening says an AI made the session and gives the stop rule and each limit with its side and body part; the limit is respected in every movement and cue; no side is ever wrong; nothing sends them into something their health file rules out. Saying a limit's reminder once at the first set that touches it is right; repeating it at every set is a fault of voice, not of safety.
- coaching: each movement is set up clearly before its go for someone who can't see anything; the cues are the right ones, at the right moment; the dose and what's next are always clear; the self-checks and options are useful.
- voice: it sounds like one real coach talking to one person, start to finish: natural, specific, warm without gushing; not robotic, padded, repetitive or generic; it never claims to see the listener.
- stories: worth hearing, told the way a friend would, with real detail, placed where they can be followed, handed into and out of cleanly; no fact that sounds invented.
- personal: it is plainly theirs: their name, level, kit, place, limit, topics and taste, and nothing from their "never bring up".

Then say which script the listener is better served by overall (first, second, or tie when you truly can't separate them), and why in a sentence or two. List each script's defects: the segment's number (counting @@ lines from 1), the words quoted exactly, what's wrong, and how serious (safety: could hurt or mislead about the body; ear: the listener would notice; minor). List only real defects you can quote; an empty list is fine. Judge the scripts only against each other and the listener's files. Nothing tells you who or what wrote either."""


def schema() -> dict:
    score = {"type": "object", "properties": {"first": {"type": "integer", "minimum": 1, "maximum": 5},
                                              "second": {"type": "integer", "minimum": 1, "maximum": 5},
                                              "note": {"type": "string"}}, "required": ["first", "second", "note"]}
    defect = {"type": "array", "items": {"type": "object", "properties": {
        "segment": {"type": "integer"}, "quote": {"type": "string"}, "problem": {"type": "string"},
        "severity": {"type": "string", "enum": ["safety", "ear", "minor"]}},
        "required": ["segment", "quote", "problem", "severity"]}}
    return {"type": "object", "properties": {
        "scores": {"type": "object", "properties": {c: score for c in CRITERIA}, "required": list(CRITERIA)},
        "defects_first": defect, "defects_second": defect,
        "overall": {"type": "string", "enum": ["first", "second", "tie"]}, "why": {"type": "string"}},
        "required": ["scores", "defects_first", "defects_second", "overall", "why"]}


def _read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def run_of(label: str, n: str) -> dict | None:
    try:
        with open(os.path.join(OUT, label, n, "result.json"), encoding="utf-8") as f:
            r = json.load(f)
    except (OSError, ValueError):
        return None
    return r if r.get("draft") else None


def listener(label: str, n: str) -> str:
    home = os.path.join(OUT, label, n, "home")
    return "\n\n".join(f"## {name}\n{_read(os.path.join(home, name)).strip()}"
                       for name in ("profile.md", "training.md", "health.md", "content.md"))


async def judge(model, cache: str, salt: str, who: str, line: str, first: str, second: str) -> dict:
    prompt = (f"# The listener's files\n\n{who}\n\n# Their request\n\n{line}\n\n# The first script\n\n{first.strip()}\n\n"
              f"# The second script\n\n{second.strip()}")
    key = hashlib.sha256(json.dumps(["judge", model._name, SYSTEM, prompt, salt]).encode()).hexdigest()
    got = model._cached(key)
    if got is None:
        got = await model._call(SYSTEM, prompt, schema(), False, "high")
        model._keep(key, got)
    return got["structured_output"]


def pairs(a) -> list:
    """Each judgment to make: (run, order, the listener's files, the request, the first script, the second)."""
    runs = a.runs.split(",") if a.runs else sorted(
        n for n in os.listdir(os.path.join(OUT, a.candidate)) if n.isdigit())
    out = []
    for n in runs:
        base, cand = run_of(a.baseline, a.baseline_runs.split(",")[runs.index(n)] if a.baseline_runs else n), run_of(a.candidate, n)
        if not (base and cand):
            print(f"run {n}: no script in one arm, skipped")
            continue
        if base["draft"].strip() == cand["draft"].strip():
            print(f"run {n}: the two scripts are the same, not judged")
            continue
        who, line = listener(a.candidate, n), cand.get("line") or base.get("line") or ""
        for order in ("base-first", "cand-first"):
            first, second = (base, cand) if order == "base-first" else (cand, base)
            out.append((n, order, who, line, first["draft"], second["draft"]))
    return out


TASK = """

# What to do

Beside this file are listener.md (the listener's files), request.txt (their request), first.txt and second.txt (the two scripts). Read all four whole; read nothing else. Then write verdict.json in this folder, one JSON object and nothing else:

{"scores": {"safety": {"first": 1-5, "second": 1-5, "note": "..."}, "coaching": {...}, "voice": {...}, "stories": {...}, "personal": {...}},
 "defects_first": [{"segment": <number>, "quote": "<the words, exactly>", "problem": "...", "severity": "safety" | "ear" | "minor"}],
 "defects_second": [the same],
 "overall": "first" | "second" | "tie", "why": "..."}

Reply with one line: the overall verdict."""


def folder(a) -> str:
    """The comparison's folder, named by a hash so its path tells the judge nothing of the arms."""
    name = hashlib.sha256(f"{a.candidate} vs {a.baseline} {a.salt}".encode()).hexdigest()[:10]
    return os.path.join(REPO, ".bench", "judge", name)


def prepare(a) -> None:
    root = folder(a)
    for n, order, who, line, first, second in pairs(a):
        d = os.path.join(root, f"{n}-{'a' if order == 'base-first' else 'b'}")   # the folder's name tells the judge nothing
        os.makedirs(d, exist_ok=True)
        for name, text in (("task.md", SYSTEM + TASK), ("listener.md", who), ("request.txt", line),
                           ("first.txt", first), ("second.txt", second)):
            with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")
        print(d)


def read_verdicts(a) -> list:
    rows = []
    for n, order, *_ in pairs(a):
        path = os.path.join(folder(a), f"{n}-{'a' if order == 'base-first' else 'b'}", "verdict.json")
        try:
            with open(path, encoding="utf-8") as f:
                rows.append((n, order, json.load(f)))
        except (OSError, ValueError) as e:
            print(f"run {n} ({order}): no verdict read ({e})")
    return rows


async def ask_all(a) -> list:
    cache = os.path.join(REPO, ".bench", "claude-cache")
    model = claude_cli.ClaudeCLI(a.model, cache=cache)
    gate = asyncio.Semaphore(4)

    async def one(n, order, who, line, first, second):
        async with gate:
            return n, order, await judge(model, cache, a.salt, who, line, first, second)
    return await asyncio.gather(*(one(*p) for p in pairs(a)))


def report(a, rows: list) -> None:
    tally = {"win": 0, "tie": 0, "loss": 0}
    diffs: dict[str, list] = {c: [] for c in CRITERIA}
    kept = []
    for n, order, v in sorted(rows, key=lambda r: (r[0], r[1])):
        cand_is = "second" if order == "base-first" else "first"
        base_is = "first" if cand_is == "second" else "second"
        outcome = "tie" if v["overall"] == "tie" else ("win" if v["overall"] == cand_is else "loss")
        tally[outcome] += 1
        scores = {c: (v["scores"][c][base_is], v["scores"][c][cand_is]) for c in CRITERIA}
        for c, (b, k) in scores.items():
            diffs[c].append(k - b)
        print(f"\nrun {n} ({order}): candidate {outcome}. " + "  ".join(f"{c} {b}>{k}" for c, (b, k) in scores.items()))
        print(f"  why: {v['why']}")
        for arm, key in (("baseline", f"defects_{base_is}"), ("candidate", f"defects_{cand_is}")):
            for d in v.get(key) or []:
                print(f"  {arm} #{d['segment']} [{d['severity']}] \"{d['quote'][:140]}\": {d['problem'][:200]}")
        kept.append({"run": n, "order": order, "outcome": outcome, "scores": scores, "why": v["why"],
                     "defects_baseline": v.get(f"defects_{base_is}") or [],
                     "defects_candidate": v.get(f"defects_{cand_is}") or []})
    print(f"\n{a.candidate} against {a.baseline}: {tally['win']} wins, {tally['tie']} ties, {tally['loss']} losses "
          f"in {len(rows)} judgments")
    print("mean score, candidate less baseline: " + "  ".join(
        f"{c} {statistics.mean(d):+.2f}" for c, d in diffs.items() if d))
    for arm in ("baseline", "candidate"):
        found = [d for k in kept for d in k[f"defects_{arm}"]]
        print(f"{arm} defects: " + ", ".join(f"{sum(d['severity'] == s for d in found)} {s}" for s in ("safety", "ear", "minor")))
    os.makedirs(os.path.join(REPO, ".bench", "judged"), exist_ok=True)
    with open(os.path.join(REPO, ".bench", "judged", f"{a.candidate}-vs-{a.baseline}{'-' + a.salt if a.salt else ''}.json"),
              "w", encoding="utf-8") as f:
        json.dump({"tally": tally, "mean_diff": {c: statistics.mean(d) for c, d in diffs.items() if d}, "judgments": kept},
                  f, indent=1)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("baseline")
    p.add_argument("candidate")
    p.add_argument("--runs", help="the candidate's runs to judge, by number (all by default)")
    p.add_argument("--baseline-runs", help="the baseline's run for each, when the numbers differ")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--salt", default="")
    p.add_argument("--prepare", action="store_true", help="write each judgment's reading as a folder, and stop")
    p.add_argument("--tally", action="store_true", help="read the verdicts written into those folders")
    a = p.parse_args()
    if a.prepare:
        prepare(a)
    else:
        report(a, read_verdicts(a) if a.tally else asyncio.run(ask_all(a)))


if __name__ == "__main__":
    main()
