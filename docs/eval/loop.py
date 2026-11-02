"""The script-writing loop (maintainer only; docs/eval/README.md): freeze a set of workouts once, then run rounds
that try one writer's champion prompt against challengers on those same workouts, for Claude judges to rank.

    .venv/bin/python docs/eval/loop.py freeze [--only 1,2]
    .venv/bin/python docs/eval/loop.py prompts <writer>          # write the champion's prompt, to copy for a challenger
    .venv/bin/python docs/eval/loop.py round <writer> [--versions A,B,C] [--scripts N]
    .venv/bin/python docs/eval/loop.py judge <round> [--per-job 2]
    .venv/bin/python docs/eval/loop.py tally <round>
    .venv/bin/python docs/eval/loop.py status

Writers: coach (the Coach Writer), content (the Personal Content Writer), final (the Final Script Writer).

Everything lives in me/.eval/ (the listener's own: never in the engine). `freeze` runs one whole web-app workout
turn per request, on Gemini with the key in me/.env (never printed), on a copy of me/: the planning agent writes
the skeleton, the writers write, the content writer searches. It keeps each workout's skeleton, brief, menu, the
feeds sheet, the content plan, the stories, the coaching, and what the searches found. A round re-runs only the
writer under test: the others' saved output stands, the date is the freeze's (`--today`), and the content writer
searches nothing, given the saved results instead (production searches; the loop doesn't, so research is once).
"""
import argparse
import asyncio
import concurrent.futures
import datetime
import json
import os
import random
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "web"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import keys  # noqa: E402
import paths  # noqa: E402
from webapp import agent, providers, worker  # noqa: E402
from webapp.agent import tools, writers  # noqa: E402

EVAL = os.path.join(paths.HOME, ".eval")
FROZEN = os.path.join(EVAL, "frozen")
ROUNDS = os.path.join(EVAL, "rounds")
PROMPTS = os.path.join(EVAL, "prompts")
JUDGE = os.path.join(ROOT, "docs", "eval", "judge.md")
WRITERS = ("coach", "content", "final")
NAMES = {"coach": "Coach Writer", "content": "Personal Content Writer", "final": "Final Script Writer"}
# what each writer is judged on first: the criterion a challenger must win
OWNS = {"coach": "clarity", "content": "content", "final": "flow"}
CRITERIA = ("clarity", "content", "flow")
REQUESTS = [
    "I'd like a 30-minute full-body workout at home, bodyweight only. Nothing's bothering me today.",
    "I'd like a 30-minute strength workout at the gym. Go easy on my left knee today.",
    "I'd like a 30-minute conditioning workout with dumbbells. Nothing's bothering me today.",
    "I'd like a 30-minute full-body workout with resistance bands. Treat me as a beginner today. Nothing's bothering me.",
    "I'd like a 30-minute strength workout with kettlebells. My low back is a bit delicate today.",
    "I'd like a 30-minute conditioning workout on a rowing machine, with sprint intervals. Nothing's bothering me today.",
    "I'd like a 30-minute full-body hotel-room workout with a pair of light dumbbells. Nothing's bothering me today.",
    "I'd like a 30-minute strength workout at home with a barbell. My right shoulder is delicate today.",
]
SKIP = shutil.ignore_patterns(".eval", "web", ".git", ".audio-cache", "*.mp3", ".logs", ".auditions", ".backup-*",
                              "*.bundle", "*.lock")
CONCURRENCY = 8
# a challenger is kept only when its average on its writer's own criterion beats the champion's by this much (round
# 0, three copies of one prompt, moved 0.3 by chance) and it wins at least NET_WINS more workouts than it loses
MARGIN = 0.5
NET_WINS = 2
# the frozen workouts, by role: a round screens on three and confirms on three others; two are held out until the end
SCREEN = ["b2", "b3", "b4"]     # gym with a knee, dumbbell conditioning, a beginner with bands
CONFIRM = ["b1", "b5", "b6"]    # home bodyweight, kettlebells with a low back, rower sprints
HOLDOUT = ["b7", "b8"]          # hotel dumbbells, barbell with a shoulder


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _json(path: str):
    return json.loads(_read(path))


def _key() -> str:
    key = keys.get("gemini")
    if not key:
        sys.exit("no GEMINI_API_KEY in me/.env: ./harmonicfitness keys init gemini, then keys open")
    return key


def words(text: str) -> int:
    return len(text.split())


# --- what every run in the loop shares: the freeze's date, its feeds sheet, the saved output of the writers not
# under test. tools.run and writers._ask are wrapped once; each run's own state is found by its home folder.

STATE: dict[str, dict] = {}     # by deps.home: {"today", "feeds", "found", "coaching"}
_run, _ask = tools.run, writers._ask


def _state(deps) -> dict | None:
    return STATE.get(os.path.realpath(deps.home))


def run_pinned(deps, args):
    """tools.run, on the freeze's day: its feeds sheet as saved, and the build and the content plan at its date."""
    st = _state(deps)
    if st:
        command = args[1] if args and args[0] == "./harmonicfitness" else (args[0] if args else "")
        if command == "feeds" and st.get("feeds") is not None:
            return tools.ToolResult(code=0, output=st["feeds"])
        if (command == "build" or command == "content" and "plan" in args) and "--today" not in args:
            args = list(args) + ["--today", st["today"]]
    return _run(deps, args)


class Saved:
    """A writer's saved output, standing in for its call."""
    def __init__(self, output):
        self.output = output

    def all_messages(self):
        return []

    def new_messages(self):
        return []


async def ask_frozen(deps, who, agent_, model, prompt, usage, level, capabilities=(), history=None):
    st = _state(deps)
    if st and who == "coach" and st.get("coaching") is not None:
        deps.tracks.append({"writer": who, "saved": True})
        return Saved(writers.Coaching(**st["coaching"]))
    if st and who == "content" and st.get("research") is not None:
        capabilities = ()
        if history is None:
            prompt += ("\n\n# What the searches found\n\nSearching is off for this run: these are the research "
                       "notes from the searches already made for this session. Use them as you would your own.\n\n"
                       + st["research"])
    return await _ask(deps, who, agent_, model, prompt, usage, level, capabilities, history)


tools.run = run_pinned
writers._ask = ask_frozen


def make_deps(home: str, today: str, now: str, key: str):
    zone = worker.listener_zone(now)
    deps = agent.Deps(engine_root=ROOT, home=home, keys={"GEMINI_API_KEY": key, **({"TZ": zone} if zone else {})},
                      today=today, now=now, cancel=threading.Event())
    deps.setup = agent.needs_setup(home)
    deps.coach = agent.audition_open(home)
    deps.chars_left = 10 ** 9
    return deps


# --- freeze

def cmd_freeze(a) -> None:
    only = [int(x) for x in a.only.split(",")] if a.only else list(range(1, len(REQUESTS) + 1))
    key = _key()
    now_dt = datetime.datetime.now()
    meta_path = os.path.join(FROZEN, "freeze.json")
    if a.only and os.path.exists(meta_path):
        meta = _json(meta_path)
    else:
        if os.path.exists(FROZEN) and not a.only:
            shutil.rmtree(FROZEN)
        meta = {"today": now_dt.date().isoformat(), "now": now_dt.strftime("%Y-%m-%d %A %H:%M"),
                "frozen_at": now_dt.isoformat(timespec="seconds"),
                "words": {w: words(t) for w, t in writers.guides(ROOT).items()}}
    os.makedirs(FROZEN, exist_ok=True)
    _write(meta_path, json.dumps(meta, indent=1))
    base = os.path.join(FROZEN, "base")
    if not os.path.exists(base):
        shutil.copytree(paths.HOME, base, ignore=SKIP)
        feeds = _run(make_deps(base, meta["today"], meta["now"], key), ["feeds"])
        _write(os.path.join(FROZEN, "feeds.txt"), feeds.output if feeds.code == 0 else "")
    feeds_text = _read(os.path.join(FROZEN, "feeds.txt"))
    del key

    caught: dict[str, dict] = {}
    original_write = writers.write

    async def capture_write(deps, model_, usage, path, search=()):
        full, _ = tools._mine(deps, path)
        caught[os.path.realpath(deps.home)] = {"path": path, "skeleton": _read(full), "name": tools.build_name(path) or
                                               "Workout " + os.path.basename(path).removesuffix(".draft.txt"),
                                               "coach": deps.brief_coach}
        return await original_write(deps, model_, usage, path, search)
    writers.write = capture_write

    def one(i: int) -> str:
        folder = os.path.join(FROZEN, f"b{i}")
        if os.path.exists(folder):
            shutil.rmtree(folder)
        home = os.path.join(folder, "me")
        shutil.copytree(base, home)
        deps = make_deps(home, meta["today"], meta["now"], _key())
        STATE[os.path.realpath(home)] = {"today": meta["today"], "feeds": feeds_text}
        start = time.monotonic()
        line = REQUESTS[i - 1]
        model = providers.model_for("google", _key())   # its own client: each turn runs on its own event loop
        try:
            context = agent.prefetch(deps, line)
            outcome = agent.run_turn(model, deps, None, line, None, context=context)
        except Exception as e:  # noqa: BLE001 - one workout's failure is its own: --only re-freezes it
            _write(os.path.join(folder, "error.txt"), f"{type(e).__name__}: {e}")
            return f"b{i}: failed ({type(e).__name__}: {str(e)[:200]}): loop.py freeze --only {i}"
        got = caught.get(os.path.realpath(home))
        _write(os.path.join(folder, "turn.json"), json.dumps({
            "request": line, "seconds": round(time.monotonic() - start), "reply": outcome.reply,
            "usage": outcome.usage, "tracks": deps.tracks}, indent=1, default=str))
        if not got:
            return f"b{i}: no script written (the agent never called write_script): see {folder}/turn.json"
        stories: dict[int, dict] = {}
        found = []
        coaching = None
        for t in deps.tracks:
            if t.get("writer") == "content" and "output" in t:
                stories.update({s["number"]: s for s in t["output"]["stories"]})
                found += t.get("found", [])
            elif t.get("writer") == "coach" and "output" in t:
                coaching = t["output"]
        _write(os.path.join(folder, "skeleton.txt"), got["skeleton"])
        _write(os.path.join(folder, "found.txt"), "\n\n---\n\n".join(found) or "(no searches)")
        _write(os.path.join(folder, "stories.json"), json.dumps([stories[n] for n in sorted(stories)], indent=1))
        _write(os.path.join(folder, "coaching.json"), json.dumps(coaching, indent=1))
        _write(os.path.join(folder, "workout.json"), json.dumps(
            {"request": line, "path": got["path"], "name": got["name"], "coach": got["coach"]}, indent=1))
        return f"b{i}: frozen ({round(time.monotonic() - start)} s, {len(stories)} stories, {len(found)} search results)"

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        for line in pool.map(one, only):
            print(line, flush=True)
    writers.write = original_write
    _write(meta_path, json.dumps(meta, indent=1))
    if not a.only or research_notes() is None:
        cmd_research(a)
    print(f"frozen on {meta['today']}; prompt sizes (words, the caps): {meta['words']}")


def frozen_workouts() -> list[str]:
    return sorted((d for d in os.listdir(FROZEN) if re.fullmatch(r"b\d+", d)
                   and os.path.exists(os.path.join(FROZEN, d, "workout.json"))), key=lambda d: int(d[1:]))


# --- research, once: Gemini's search hands back only its suggestion chips (the pages it read never reach the code),
# so the stories' facts can't be saved from the writers' own searches. One searching call writes them as notes
# instead, for every workout: the content writer's material in its rounds, and the judges' to check facts against.

RESEARCH_ASK = """You are researching the stories for this listener's audio workouts today. Below are their profile, \
what they like, the content plan (the topics due, what's been told, the formats) and today's feeds sheet. Run about \
eight web searches for what the sheets don't cover: the plan's topics due, their teams' latest results and next \
games, upcoming shows at their venues or near them, a few quick hits in their topics. Then write research notes, \
not stories: about twenty items, each a heading (its topic as the plan names it), the facts exactly as the pages \
state them (names, numbers, dates), when it happened, and its source link. Only what a page or a sheet says; mark \
anything unconfirmed. No item the plan lists as told."""


def cmd_research(a) -> None:
    from pydantic_ai import Agent
    from pydantic_ai.capabilities import NativeTool
    meta = _json(os.path.join(FROZEN, "freeze.json"))
    base = os.path.join(FROZEN, "base")
    deps = make_deps(base, meta["today"], meta["now"], _key())
    STATE[os.path.realpath(base)] = {"today": meta["today"], "feeds": _read(os.path.join(FROZEN, "feeds.txt"))}
    plan = tools.run(deps, ["content", "plan", "--minutes", "30"]).output
    prompt = (f"Now: {meta['now']}.\n\n{RESEARCH_ASK}\n\n# Their profile\n\n{writers._home_text(deps, 'profile.md')}"
              f"\n\n# What they like\n\n{writers._home_text(deps, 'content.md')}\n\n# The content plan\n\n{plan}"
              f"\n\n# Today's feeds sheet\n\n{_read(os.path.join(FROZEN, 'feeds.txt'))}")
    model = providers.model_for("google", _key())
    search = [NativeTool(t) for t in agent.native_tools(model)]
    start = time.monotonic()
    result = asyncio.run(Agent(output_type=str).run(prompt, model=model, capabilities=search))
    _write(os.path.join(FROZEN, "research.md"), result.output.strip() + "\n")
    print(f"research notes: {os.path.join(FROZEN, 'research.md')} ({words(result.output)} words, "
          f"{round(time.monotonic() - start)} s)")


def research_notes() -> str | None:
    path = os.path.join(FROZEN, "research.md")
    return _read(path) if os.path.exists(path) else None


# --- prompts: a challenger is the writer's whole prompt, edited

def cmd_prompts(a) -> None:
    path = os.path.join(PROMPTS, a.writer, "champion.md")
    _write(path, writers.guides(ROOT)[a.writer])
    print(f"{path}: the champion's {NAMES[a.writer]} prompt ({words(_read(path))} words). Copy it to B.md or C.md "
          "beside it and make one change.")


def version_guides(writer: str, version: str, cap: int) -> dict:
    champion = dict(writers.guides(ROOT))
    if version == "A":
        return champion
    text = _read(os.path.join(PROMPTS, writer, f"{version}.md")).strip()
    if words(text) > cap:
        sys.exit(f"{writer} {version}.md runs {words(text)} words, over its cap of {cap}: cut before adding")
    if writer == "coach":   # the safety rules are pinned: a challenger can't touch them
        whole = champion["coach"]
        safety = whole[whole.index("## Safety: the rules"):whole.index("## Getting the workout done")].strip()
        if safety not in text:
            sys.exit(f"coach {version}.md changes the safety rules, which stay as knowledge/script.md has them")
    champion[writer] = text
    return champion


# --- a round: one writer's champion (A) and challengers on the round's workouts; the screen tries many on a few,
# the confirm takes the screen's best two on the rest. `all` writes everything fresh with the champions, against the
# app's own script as frozen (O): the check at the end, on the held-out workouts.

def next_round() -> int:
    os.makedirs(ROUNDS, exist_ok=True)
    done = [int(d) for d in os.listdir(ROUNDS) if d.isdigit()]
    return max(done, default=-1) + 1


def draft_path(b: str) -> str:
    w = _json(os.path.join(FROZEN, b, "workout.json"))
    return os.path.join(FROZEN, b, "me", w["path"].removeprefix("me/"))


async def write_one(sem, model, meta, writer, version, guides, folder, b) -> dict:
    src = os.path.join(FROZEN, b)
    w = _json(os.path.join(src, "workout.json"))
    out = os.path.join(folder, version, b)
    if version == "O":   # the app's own script, as the freeze wrote it
        _write(os.path.join(out, "script.txt"), _read(draft_path(b)))
        return {"version": version, "workout": b, "ok": True, "seconds": 0}
    home = os.path.join(out, "me")
    shutil.copytree(os.path.join(src, "me"), home)
    deps = make_deps(home, meta["today"], meta["now"], _key())
    full, _ = tools._mine(deps, w["path"])
    _write(full, _read(os.path.join(src, "skeleton.txt")))
    deps.writers, deps.brief_coach, deps.guides = "three", w["coach"], guides
    st = {"today": meta["today"], "feeds": _read(os.path.join(FROZEN, "feeds.txt")), "research": research_notes()}
    if writer in ("content", "all") and st["research"] is None:
        raise SystemExit("no research notes yet: loop.py research")
    if writer not in ("coach", "all"):
        st["coaching"] = _json(os.path.join(src, "coaching.json"))
    if writer not in ("content", "all"):
        job = concurrent.futures.Future()
        job.set_result([writers.Told(**x) for x in _json(os.path.join(src, "stories.json"))])
        deps.content_job, deps.content_for = job, w["path"]
    STATE[os.path.realpath(home)] = st
    async with sem:
        start = time.monotonic()
        try:
            draft, _ = await writers.write(deps, model, None, w["path"])
        except Exception as e:  # noqa: BLE001 - one workout's failure is that script's, not the round's
            _write(os.path.join(out, "error.txt"), f"{type(e).__name__}: {e}")
            return {"version": version, "workout": b, "ok": False, "error": f"{type(e).__name__}: {e}"}
        seconds = round(time.monotonic() - start)
        check = await writers._lint(deps, replace(deps, say=None), w["path"], full, w["name"], w["coach"], draft)
    _write(os.path.join(out, "script.txt"), draft)
    _write(os.path.join(out, "lint.txt"), check)
    _write(os.path.join(out, "tracks.json"), json.dumps(deps.tracks, indent=1, default=str))
    return {"version": version, "workout": b, "ok": check.startswith("clean"), "seconds": seconds}


def run_round(writer: str, versions: list[str], workouts: list[str], stage: str, parent: int | None = None) -> int:
    meta = _json(os.path.join(FROZEN, "freeze.json"))
    labels = [v if versions.count(v) == 1 else f"{v}{i}" for i, v in enumerate(versions, 1)]
    guides = {lab: (dict(writers.guides(ROOT)) if writer == "all" or v == "O"
                    else version_guides(writer, v, meta["words"][writer])) for lab, v in zip(labels, versions)}
    n = next_round()
    folder = os.path.join(ROUNDS, str(n))
    os.makedirs(folder)
    if writer != "all":
        for lab in labels:
            _write(os.path.join(folder, "prompts", f"{lab}.md"), guides[lab][writer])
    print(f"round {n} ({stage}): {NAMES.get(writer, 'all three writers')}, versions {', '.join(labels)}, "
          f"on {', '.join(workouts)} ({len(labels) * len(workouts)} scripts)", flush=True)
    model = providers.model_for("google", _key())
    start = time.monotonic()

    async def go():
        sem = asyncio.Semaphore(CONCURRENCY)
        return await asyncio.gather(*(write_one(sem, model, meta, writer, lab, guides[lab], folder, b)
                                      for lab in labels for b in workouts))
    results = asyncio.run(go())
    _write(os.path.join(folder, "round.json"), json.dumps({
        "round": n, "writer": writer, "stage": stage, "parent": parent, "versions": dict(zip(labels, versions)),
        "workouts": workouts, "seconds": round(time.monotonic() - start), "scripts": results,
        "prompt_words": {lab: words(guides[lab][writer]) for lab in labels if writer != "all"}}, indent=1))
    bad = [r for r in results if not r["ok"]]
    print(f"done in {round(time.monotonic() - start)} s; {len(results) - len(bad)} of {len(results)} lint clean"
          + "".join(f"\n  {r['version']} {r['workout']}: {r.get('error') or 'not lint clean (lint.txt)'}"
                    for r in bad))
    print(f"next: loop.py judge {n}")
    return n


def cmd_round(a) -> None:
    pdir = os.path.join(PROMPTS, a.writer)
    challengers = sorted(os.path.splitext(f)[0] for f in os.listdir(pdir) if re.fullmatch(r"[B-Z]\.md", f)) \
        if os.path.isdir(pdir) else []
    versions = a.versions.split(",") if a.versions else (["A"] + challengers if challengers else ["A"])
    if len(versions) == 1:
        versions = versions * 3   # a noise round: the same prompt three times
    workouts = a.workouts.split(",") if a.workouts else SCREEN
    run_round(a.writer, versions, workouts, "screen" if not a.workouts else "custom")


def cmd_confirm(a) -> None:
    info = _json(os.path.join(ROUNDS, str(a.round), "round.json"))
    t = tally(a.round)
    own = OWNS[info["writer"]]
    # a challenger goes on only if the screen put it ahead on its criterion
    challengers = [lab for lab in info["versions"] if lab != "A" and not t["unsafe"].get(lab)]
    best = sorted(challengers, key=lambda lab: (-(t["h2h"][lab][own][0] - t["h2h"][lab][own][2]),
                                                 -t["mean"].get((lab, own), 0)))[:a.top]
    if not best:
        sys.exit("no challenger survived the screen safely: nothing to confirm")
    versions = ["A"] + [info["versions"][lab] for lab in best]
    run_round(info["writer"], versions, CONFIRM, "confirm", parent=a.round)


def cmd_holdout(a) -> None:
    run_round("all", ["A", "O"], HOLDOUT, "holdout")


def replace(deps, **kw):
    from dataclasses import replace as _r
    return _r(deps, **kw)


# --- judging: three Claude personas, each given a workout's scripts as letters in its own order

PERSONAS = {
    "trainer": "You are a certified strength coach and physiotherapist who has coached hundreds of people through "
               "earbuds, with no eyes on them. You judge as a professional: is every instruction right, enough to do "
               "the movement well and safely, and no more than that? You notice a cue that's missing for the joint at "
               "risk, a dose that doesn't fit, and coaching that buries the instruction in talk.",
    "listener": "You are the listener: the person in the profile, training and content files below. Read them, and "
                "the Feedback at the end of {HOME}log.md, until you know what you like and what you've complained "
                "about. You judge as yourself, earbuds in, mid-workout: is this my world, is it fun, does it get me "
                "through, would I want tomorrow's?",
    "producer": "You are the producer of a top-rated podcast, with an ear for how words land when heard once: pace, "
                "rhythm, a story's shape, a voice that stays one person, the seams where one thing hands to the "
                "next. You judge it as audio, not text.",
}
LETTERS = "UVWXYZ"


def cmd_judge(a) -> None:
    folder = os.path.join(ROUNDS, str(a.round))
    info = _json(os.path.join(folder, "round.json"))
    labels, workouts = list(info["versions"]), info["workouts"]
    if len(labels) > len(LETTERS):
        sys.exit(f"at most {len(LETTERS)} versions a round")
    per_job = a.per_job or (1 if len(labels) > 3 else 2)
    template = _read(JUDGE)
    jobs_dir = os.path.join(folder, "judge")
    if os.path.exists(jobs_dir):
        shutil.rmtree(jobs_dir)
    rng = random.Random(a.round)
    mapping, jobs = {}, []
    groups = [workouts[i:i + per_job] for i in range(0, len(workouts), per_job)]
    letters = LETTERS[-len(labels):] if len(labels) <= 3 else LETTERS[:len(labels)]
    # a script that isn't lint clean is ranked last for whoever wrote it, champion or challenger
    failed = {(x["version"], x["workout"]) for x in info["scripts"] if not x["ok"]}
    home = os.path.join(FROZEN, "base") + "/"
    notes = os.path.join(FROZEN, "research.md") if research_notes() else "(none: don't fail a story on a fact you can't check)"
    for persona, who in PERSONAS.items():
        for g, group in enumerate(groups, 1):
            job = f"{persona}-{g}"
            jd = _mk(os.path.join(jobs_dir, job))
            listing = []
            for b in group:
                order = labels[:]
                rng.shuffle(order)
                mapping.setdefault(job, {})[b] = dict(zip(letters, order))
                w = _json(os.path.join(FROZEN, b, "workout.json"))
                brief = draft_path(b).replace(".draft.txt", ".brief.md")
                files = []
                for letter, lab in zip(letters, order):
                    src = os.path.join(folder, lab, b, "script.txt")
                    dst = os.path.join(jd, f"{b}-{letter}.txt")
                    if os.path.exists(src) and (lab, b) not in failed:
                        shutil.copy(src, dst)
                        files.append(f"  - {letter}: {dst}")
                    else:
                        files.append(f"  - {letter}: (no script: it failed the build's check; rank it last, safe)")
                listing.append(f"### Workout {b}\n- Request: \"{w['request']}\"\n- Brief (limits, menu, the "
                               f"listener): {brief}\n- The research notes the stories' facts come from: {notes}\n"
                               "- Scripts:\n" + "\n".join(files))
            prompt = (template.replace("{PERSONA}", who).replace("{HOME}", home)
                      .replace("{LETTERS}", ", ".join(letters)).replace("{WORKOUTS}", "\n\n".join(listing))
                      .replace("{OUT}", os.path.join(jd, "verdict.json")))
            _write(os.path.join(jd, "prompt.md"), prompt)
            jobs.append(os.path.join(jd, "prompt.md"))
    _write(os.path.join(jobs_dir, "mapping.json"), json.dumps(mapping, indent=1))
    print(f"{len(jobs)} judge jobs (each to a fresh Claude judge with no other context):")
    print("\n".join(jobs))
    print(f"then: loop.py tally {a.round}")


def _mk(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def verdicts(n: int) -> tuple[dict, list, dict, list]:
    """A round's verdicts: ranks[(workout, label, criterion)] = {persona: rank}; safety failures; scores[(label,
    criterion)] = [1-5]; notes."""
    folder = os.path.join(ROUNDS, str(n))
    mapping = _json(os.path.join(folder, "judge", "mapping.json"))
    ranks, scores, fails, notes, missing = {}, {}, [], [], []
    for job, by_workout in mapping.items():
        persona = job.rsplit("-", 1)[0]
        path = os.path.join(folder, "judge", job, "verdict.json")
        if not os.path.exists(path):
            missing.append(job)
            continue
        verdict = _json(path)
        for b, letters in by_workout.items():
            v = verdict.get(b) or {}
            for letter, lab in letters.items():
                s = (v.get("scripts") or {}).get(letter) or {}
                if s.get("safe") is False:
                    fails.append((lab, b, persona, s.get("line", ""), s.get("why", "")))
                for c in CRITERIA:
                    r = (v.get("rank") or {}).get(c, {}).get(letter)
                    if r is not None:
                        ranks.setdefault((b, lab, c), {})[persona] = r
                    if isinstance(s.get(c), (int, float)):
                        scores.setdefault((lab, c), []).append(s[c])
            for w in WRITERS:
                if (v.get("notes") or {}).get(w):
                    notes.append((w, b, persona, v["notes"][w]))
    return ranks, fails, scores, notes + [("missing", m, "", "") for m in missing]


def tally(n: int) -> dict:
    """A round's results, merged with its screen's for a confirm: head to head against A (a workout is won when at
    least two judges rank the challenger higher and more judges prefer it than not), mean scores, safety."""
    info = _json(os.path.join(ROUNDS, str(n), "round.json"))
    ranks, fails, scores, notes = verdicts(n)
    workouts = list(info["workouts"])
    scripts = [x for x in info["scripts"] if x["workout"] in workouts]
    if info.get("parent") is not None:
        pinfo = _json(os.path.join(ROUNDS, str(info["parent"]), "round.json"))
        back = {v: lab for lab, v in pinfo["versions"].items()}   # the screen's labels by prompt file
        here = {lab: back.get(v, lab) for lab, v in info["versions"].items()}
        r2, f2, s2, n2 = verdicts(info["parent"])
        keep = set(here.values())
        relabel = {lab: [k for k, v in here.items() if v == lab][0] for lab in keep}
        ranks.update({(b, relabel[lab], c): v for (b, lab, c), v in r2.items() if lab in keep})
        fails += [(relabel[f[0]],) + f[1:] for f in f2 if f[0] in keep]
        for (lab, c), v in s2.items():
            if lab in keep:
                scores.setdefault((relabel[lab], c), []).extend(v)
        notes += n2
        workouts = pinfo["workouts"] + workouts
        scripts += [dict(x, version=relabel[x["version"]]) for x in pinfo["scripts"] if x["version"] in keep]
    labels = list(info["versions"])
    h2h = {}
    for lab in labels[1:]:
        h2h[lab] = {}
        for c in CRITERIA:
            w = t = l = 0
            for b in workouts:
                mine, theirs = ranks.get((b, lab, c), {}), ranks.get((b, labels[0], c), {})
                both = [p for p in mine if p in theirs]
                better = sum(mine[p] < theirs[p] for p in both)
                worse = sum(mine[p] > theirs[p] for p in both)
                if better >= 2 and better > worse:
                    w += 1
                elif worse >= 2 and worse > better:
                    l += 1
                else:
                    t += 1
            h2h[lab][c] = (w, t, l)
    # in a coach or final round every version tells the freeze's stories, so a judge's fail the champion shares on
    # that workout is the stories', not the writer's: it doesn't count against a challenger (a content round's do)
    champ = {(f[1], f[2]) for f in fails if f[0] == labels[0]}
    shared = [f for f in fails if info["writer"] in ("coach", "final") and f[0] != labels[0] and (f[1], f[2]) in champ]
    unsafe = {}
    for f in fails:
        if f not in shared:
            unsafe.setdefault(f[0], []).append(f)
    for x in scripts:
        if not x["ok"]:
            unsafe.setdefault(x["version"], []).append((x["version"], x["workout"], "lint", x.get("error", ""), ""))
    mean = {k: sum(v) / len(v) for k, v in scores.items()}
    return {"info": info, "labels": labels, "workouts": workouts, "h2h": h2h, "unsafe": unsafe, "mean": mean,
            "fails": fails, "shared": shared, "notes": notes}


def cmd_tally(a) -> None:
    t = tally(a.round)
    info, labels = t["info"], t["labels"]
    writer = info["writer"]
    lines = [f"# Round {a.round} ({info.get('stage', 'screen')}): {NAMES.get(writer, 'all three writers')}", "",
             f"Versions: {', '.join(f'{k} = {v}' for k, v in info['versions'].items())}; workouts "
             f"{', '.join(t['workouts'])}; written in {info['seconds']} s"
             + (f"; prompt words {info['prompt_words']}" if info.get("prompt_words") else ""), ""]
    missing = [m[1] for m in t["notes"] if m[0] == "missing"]
    if missing:
        lines += [f"**Verdicts missing:** {', '.join(missing)}", ""]
    lines += ["## Safety", ""] + ([f"- FAIL {lab} {b} ({p}): \"{line}\": {why}" if p != "lint" else
                                   f"- {lab} {b}: not lint clean {line}" for lab, b, p, line, why in
                                   (f for fs in t["unsafe"].values() for f in fs)] or ["- every script passed"])
    if t["shared"]:
        lines += ["", "Shared with the champion on the same workout and judge (the freeze's stories), so not counted: "
                  + ", ".join(f"{lab} {b} ({p})" for lab, b, p, _, _ in t["shared"])]
    lines += ["", "## Average scores (1-5, every judge)", "", "| version | " + " | ".join(CRITERIA) + " |",
              "|---|" + "---|" * len(CRITERIA)]
    for lab in labels:
        lines.append(f"| {lab} | " + " | ".join(
            f"{t['mean'][(lab, c)]:.2f}" if (lab, c) in t["mean"] else "-" for c in CRITERIA) + " |")
    lines += ["", f"## Head to head against {labels[0]} (won: two or more of the three judges prefer it)", "",
              "| version | " + " | ".join(f"{c} W-T-L" for c in CRITERIA) + " |", "|---|" + "---|" * len(CRITERIA)]
    for lab in labels[1:]:
        lines.append(f"| {lab} | " + " | ".join("-".join(map(str, t["h2h"][lab][c])) for c in CRITERIA) + " |")
    lines += ["", "## Verdict", ""]
    if writer in OWNS:
        own = OWNS[writer]
        for lab in labels[1:]:
            w, _, l = t["h2h"][lab][own]
            lost = [c for c in CRITERIA if c != own and t["h2h"][lab][c][2] > t["h2h"][lab][c][0]]
            gain = t["mean"].get((lab, own), 0) - t["mean"].get((labels[0], own), 0)
            ok = gain >= a.margin and w - l >= NET_WINS and not t["unsafe"].get(lab) and not lost
            stage = info.get("stage")
            word = ("KEEP" if stage == "confirm" else "to confirm") if ok else "no"
            lines.append(f"- {lab}: {word} ({own} {gain:+.2f} on average, {w} won, {l} lost" + ("; a safety or lint failure" if
                         t["unsafe"].get(lab) else "") + (f"; lost on {', '.join(lost)}" if lost else "") + ")")
        if len(set(info["versions"].values())) == 1:
            lines.append("- a noise round (every version the same prompt): any win above is chance")
    lines += ["", "## The judges' notes, by writer", ""]
    for w in WRITERS:
        mine = [x for x in t["notes"] if x[0] == w]
        if mine:
            lines += [f"### {NAMES[w]}", ""] + [f"- ({b}, {p}) {text}" for _, b, p, text in mine] + [""]
    _write(os.path.join(ROUNDS, str(a.round), "tally.md"), "\n".join(lines) + "\n")
    print("\n".join(lines))


def cmd_status(a) -> None:
    if not os.path.exists(os.path.join(FROZEN, "freeze.json")):
        print("not frozen yet: loop.py freeze")
        return
    meta = _json(os.path.join(FROZEN, "freeze.json"))
    print(f"frozen {meta['frozen_at']} for {meta['today']}: {len(frozen_workouts())} workouts (screen "
          f"{','.join(SCREEN)}, confirm {','.join(CONFIRM)}, held out {','.join(HOLDOUT)}); caps {meta['words']}")
    for d in sorted((d for d in os.listdir(ROUNDS) if d.isdigit()), key=int) if os.path.isdir(ROUNDS) else []:
        p = os.path.join(ROUNDS, d, "round.json")
        info = _json(p) if os.path.exists(p) else {}
        state = "tallied" if os.path.exists(os.path.join(ROUNDS, d, "tally.md")) else \
            "judged?" if os.path.exists(os.path.join(ROUNDS, d, "judge")) else "written" if info else "running"
        print(f"round {d} ({info.get('stage', '?')}): {NAMES.get(info.get('writer'), info.get('writer'))} "
              f"{info.get('versions')}: {state}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--only", help="re-freeze these workouts (1-based, comma-separated), keeping the rest")
    p = sub.add_parser("prompts")
    p.add_argument("writer", choices=WRITERS)
    r = sub.add_parser("round", help="the screen: the champion and every challenger on the screen's workouts")
    r.add_argument("writer", choices=WRITERS)
    r.add_argument("--versions", help="A (the champion) and challengers in me/.eval/prompts/<writer>/, such as A,B,C; "
                                      "default A and every challenger there, or A,A,A (a noise round) when none")
    r.add_argument("--workouts", help=f"the workouts, comma-separated (default the screen's: {','.join(SCREEN)})")
    c = sub.add_parser("confirm", help="the screen's best challengers against the champion on the confirm workouts")
    c.add_argument("round", type=int, help="the screen round, judged")
    c.add_argument("--top", type=int, default=2, help="how many challengers go on (default 2)")
    sub.add_parser("holdout", help="the champions, all three writing fresh, against the app's own script (O), "
                                   "on the held-out workouts")
    j = sub.add_parser("judge")
    j.add_argument("round", type=int)
    j.add_argument("--per-job", type=int, help="workouts per judge job (default 2, or 1 with more than 3 versions)")
    t = sub.add_parser("tally")
    t.add_argument("round", type=int)
    t.add_argument("--margin", type=float, default=MARGIN, help=f"the average gain a challenger needs (default {MARGIN})")
    sub.add_parser("research", help="the research notes, once (freeze runs it): every content round's material")
    sub.add_parser("status")
    a = ap.parse_args()
    {"freeze": cmd_freeze, "research": cmd_research, "prompts": cmd_prompts, "round": cmd_round, "confirm": cmd_confirm,
     "holdout": cmd_holdout, "judge": cmd_judge, "tally": cmd_tally, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    main()
