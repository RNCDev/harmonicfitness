"""One timed run of the website's script writing, in-process (no database, no worker), on a copy of a home.

  .venv/bin/python web/bench/run_one.py <out-dir> <minutes> [--engine <root>] [--home <me>] [--set NAME=VALUE]...

The agent gets the page's starter sentence for a strength workout at home with two one-sided limits, answers its
questions with "Go with your pick", and stops at the price: nothing is recorded or logged. The home is copied into
<out-dir>/home without its key file; the Gemini key is read from the real home through the engine's own loader and
never printed. --engine runs another checkout (a git worktree of an earlier release, to compare); --set changes a
writer's setting for the run (LEVEL.trainer=LOW, STORY_WORDS=100). Run it through batch.sh, which also prepares
the copied home.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINE = ("Hey, coach Freya, I'd like a {minutes}-minute strength workout at home. Go easy on my left knee, "
        "and keep off my right shoulder today.")
ANSWER = "Go with your pick."


def setup(engine: str, home: str):
    os.environ["HARMONICFITNESS_HOME"] = home   # the key loader reads the real home's key file
    os.environ.setdefault("HARMONICFITNESS_WRITERS", "three")
    os.environ.setdefault("HARMONICFITNESS_PYTHON", os.path.join(REPO, ".venv", "bin", "python"))
    sys.path[:0] = [os.path.join(engine, "web"), os.path.join(engine, "tools")]
    import keys  # noqa: PLC0415
    from webapp import agent, providers  # noqa: PLC0415
    from webapp.agent import tools, writers  # noqa: PLC0415
    return keys, providers, agent, tools, writers


def apply(writers, settings: list[str]) -> None:
    for item in settings:
        name, _, value = item.partition("=")
        value = int(value) if value.isdigit() else value
        if name.startswith("LEVEL."):
            writers.LEVEL[name.split(".", 1)[1]] = value
        else:
            setattr(writers, name, value)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("minutes", type=int)
    p.add_argument("--engine", default=REPO)
    p.add_argument("--home", default=os.environ.get("HARMONICFITNESS_HOME") or os.path.join(REPO, "me"))
    p.add_argument("--base", help="the prepared copy of the home to start from (batch.sh makes it)")
    p.add_argument("--set", action="append", default=[])
    a = p.parse_args()
    engine, real_home = os.path.abspath(a.engine), os.path.abspath(a.home)
    keys, providers, agent, tools, writers = setup(engine, real_home)
    apply(writers, a.set)

    os.makedirs(a.out, exist_ok=True)
    home = os.path.join(a.out, "home")
    shutil.rmtree(home, ignore_errors=True)
    shutil.copytree(a.base or real_home, home, symlinks=True, ignore=shutil.ignore_patterns(".env", ".audio-cache"))
    key = keys.get("gemini")
    model = providers.model_for("google", key)
    t0 = time.monotonic()
    events, room, captured = [], [], []

    def stamp() -> float:
        return round(time.monotonic() - t0, 2)

    def say(text, tool, code, step=None, think=False):
        events.append({"t": stamp(), "text": text, "tool": tool, "code": code, "step": step, "think": think})

    def log(text):
        room.append({"t": stamp(), "line": text})

    orig = writers._ask

    async def ask(deps, who, ag, mdl, prompt, usage, level, capabilities=(), history=None):
        r = await orig(deps, who, ag, mdl, prompt, usage, level, capabilities, history)
        captured.append({"t": stamp(), "who": who, "level": level, "prompt": prompt, "output": r.output.model_dump()})
        return r
    writers._ask = ask

    now = datetime.datetime.now()
    deps = agent.Deps(engine_root=engine, home=home, keys={"GEMINI_API_KEY": key}, today=now.strftime("%Y-%m-%d"),
                      now=now.strftime("%Y-%m-%d %A %H:%M"), say=say, log=log)
    turns, history, line = [], None, LINE.format(minutes=a.minutes)
    for turn in range(3):
        began = time.monotonic()
        context = agent.prefetch(deps, line) if turn == 0 else None
        err = None
        try:
            outcome = agent.run_turn(model, deps, history, line, context=context)
            history, reply, usage = outcome.history_json, outcome.reply, outcome.usage
        except Exception as e:  # noqa: BLE001 - recorded as the run's failure
            err, reply, usage = f"{type(e).__name__}: {e}"[:500], None, {}
        turns.append({"turn": turn, "start": round(began - t0, 2), "seconds": round(time.monotonic() - began, 2),
                      "reply": reply, "usage": usage, "error": err, "priced": deps.offer is not None})
        if err or deps.offer is not None:
            break
        line = ANSWER
        deps.steps = 0   # a new turn: what the worker starts fresh
    draft_path = (deps.offer or {}).get("draft") or next(iter(deps.reports), None)
    draft = ""
    if draft_path:
        full, _ = tools._mine(deps, draft_path)
        try:
            with open(full, encoding="utf-8") as f:
                draft = f.read()
        except (OSError, TypeError):
            pass
    lint = None
    if draft_path and deps.offer:
        r = tools.run(deps, ["build", draft_path, deps.offer.get("name") or tools.build_name(draft_path),
                             "--coach", deps.offer.get("coach") or deps.brief_coach or "Coach Freya", "--lint-only"])
        lint = r.output + "\n" + r.error
    result = {"minutes": a.minutes, "engine": engine, "set": a.set, "turns": turns, "events": events, "room": room,
              "offer": deps.offer, "draft_path": draft_path, "draft": draft, "final_lint": lint,
              "writers": captured, "history": history}
    with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=str)
    brief_t = next((e["t"] for e in events if (e["tool"] or "").startswith("run brief") and e["code"] is None), None)
    end = turns[-1]["start"] + turns[-1]["seconds"]
    print(json.dumps({"out": a.out, "priced": deps.offer is not None, "turns": len(turns), "total": round(end, 1),
                      "from_brief": round(end - brief_t, 1) if brief_t is not None else None,
                      "error": turns[-1]["error"]}))


if __name__ == "__main__":
    main()
