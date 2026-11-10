"""One timed run of the website's script writing, in-process (no database, no worker), on a copy of a home.

  .venv/bin/python web/bench/run_one.py <out-dir> <minutes> [--engine <root>] [--home <me>] [--set NAME=VALUE]...
      [--provider google|openrouter] [--model <id>] [--line <request, with {minutes}>]

The agent gets the page's starter sentence for a strength workout at home with two one-sided limits, answers its
questions with "Go with your pick", and stops at the price: nothing is recorded or logged. The home is copied into
<out-dir>/home without its key file; the Gemini key is read from the real home through the engine's own loader and
never printed. --engine runs another checkout (a git worktree of an earlier release, to compare); --set changes a
writer's setting for the run (LEVEL.trainer=LOW, STORY_WORDS=100). Run it through batch.sh, which also prepares
the copied home. --provider and --model write with another provider's model (OpenRouter's "anthropic/claude-opus-5.5",
say) without changing the site's own choice; --line is the request sentence, for a home whose files another one
doesn't fit (an invented demo listener's). The Gemini key still prices the coach.

Every model request is recorded (requests.jsonl: who asked, the agent's phase, the messages' size, the provider's
usage as it came back), every engine command (commands.jsonl), and the draft as each lint read it (drafts/), so a
run shows where its tokens went and what each round changed.
"""
import argparse
import contextvars
import dataclasses
import datetime
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINE = ("Hey, coach Freya, I'd like a {minutes}-minute strength workout at home, right now. Go easy on my "
        "left knee, and keep off my right shoulder today.")
ANSWER = "Go with your pick."
WHO = contextvars.ContextVar("who", default=None)   # the writer whose call is running; None for the agent itself


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
    p.add_argument("--provider", default="google", choices=("google", "openrouter"))
    p.add_argument("--model", help="the provider's model id, in place of the site's (providers.PROVIDERS)")
    p.add_argument("--line", default=LINE, help="the request sentence, with {minutes}")
    a = p.parse_args()
    engine, real_home = os.path.abspath(a.engine), os.path.abspath(a.home)
    keys, providers, agent, tools, writers = setup(engine, real_home)
    apply(writers, a.set)

    os.makedirs(a.out, exist_ok=True)
    home = os.path.join(a.out, "home")
    shutil.rmtree(home, ignore_errors=True)
    shutil.copytree(a.base or real_home, home, symlinks=True, ignore=shutil.ignore_patterns(".env", ".audio-cache"))
    key = keys.get("gemini")
    env_keys = {"GEMINI_API_KEY": key}   # the coach's price: Gemini voices
    if a.provider == "openrouter":
        env_keys["OPENROUTER_API_KEY"] = keys.get("openrouter")
    if a.model:
        spec = providers.PROVIDERS[a.provider]
        providers.PROVIDERS[a.provider] = dataclasses.replace(spec, model=a.model)
    model = providers.model_for(a.provider, env_keys["GEMINI_API_KEY" if a.provider == "google" else "OPENROUTER_API_KEY"])
    t0 = time.monotonic()
    events, room, captured, requests, commands = [], [], [], [], []
    os.makedirs(os.path.join(a.out, "drafts"), exist_ok=True)

    def stamp() -> float:
        return round(time.monotonic() - t0, 2)

    def say(text, tool, code, step=None, think=False):
        events.append({"t": stamp(), "text": text, "tool": tool, "code": code, "step": step, "think": think})

    def log(text):
        room.append({"t": stamp(), "line": text})

    orig = writers._ask

    async def ask(deps, who, ag, mdl, prompt, usage, level, capabilities=(), history=None):
        token = WHO.set(who)
        began = stamp()
        try:
            r = await orig(deps, who, ag, mdl, prompt, usage, level, capabilities, history)
        finally:
            WHO.reset(token)
        captured.append({"t": stamp(), "began": began, "who": who, "level": level, "prompt": prompt,
                         "output": r.output.model_dump()})
        return r
    writers._ask = ask

    # every model request, at the model's own class: a wrapper would hide the class the harness checks to set
    # Gemini's thinking level, and so change what's measured
    from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest  # noqa: PLC0415
    cls = type(model)
    base = next(k for k in cls.__mro__ if "request" in k.__dict__)
    orig_request = base.__dict__["request"]
    deps_box = {}

    async def request(self, messages, model_settings, model_request_parameters):
        began = stamp()
        last = next((m for m in reversed(messages) if isinstance(m, ModelRequest)), None)
        instructions = len(last.instructions or "") if last is not None else 0
        sent = len(ModelMessagesTypeAdapter.dump_json(messages))
        tools_n = len(model_request_parameters.function_tools or []) if model_request_parameters else 0
        row = {"n": len(requests) + 1, "t": began, "who": WHO.get() or "agent",
               "phase": getattr(deps_box.get("deps"), "phase", None), "turn": deps_box.get("turn"),
               "messages": len(messages), "chars_sent": sent, "instructions_chars": instructions,
               "function_tools": tools_n, "settings": {k: v for k, v in (model_settings or {}).items()
                                                        if "thinking" in k or "reasoning" in k}}
        try:
            resp = await orig_request(self, messages, model_settings, model_request_parameters)
        except Exception as e:
            row.update(seconds=round(stamp() - began, 2), error=f"{type(e).__name__}: {e}"[:300])
            requests.append(row)
            raise
        u = dataclasses.asdict(resp.usage)
        kinds = {}
        for part in resp.parts:
            kinds[type(part).__name__] = kinds.get(type(part).__name__, 0) + 1
        row.update(seconds=round(stamp() - began, 2), usage=u, model=resp.model_name,
                   finish=getattr(resp, "finish_reason", None), parts=kinds,
                   provider_details=getattr(resp, "provider_details", None))
        requests.append(row)
        return resp
    setattr(base, "request", request)

    # every engine command, and the draft as each build or lint read it: the interim versions
    from webapp import engine as engine_mod  # noqa: PLC0415
    orig_run = engine_mod.run

    def run_cmd(engine_root, home_dir, argv, *args, **kwargs):
        began = stamp()
        snap = None
        if argv and argv[0] == "build" and len(argv) > 1:
            src = os.path.join(home_dir, argv[1][3:] if argv[1].startswith("me/") else argv[1])
            try:
                with open(src, encoding="utf-8") as f:
                    text = f.read()
                snap = f"drafts/{len(commands) + 1:03d}-{'lint' if '--lint-only' in argv else 'build'}.draft.txt"
                with open(os.path.join(a.out, snap), "w", encoding="utf-8") as f:
                    f.write(text)
            except OSError:
                pass
        r = orig_run(engine_root, home_dir, argv, *args, **kwargs)
        commands.append({"n": len(commands) + 1, "t": began, "seconds": round(stamp() - began, 2),
                         "who": WHO.get() or "agent", "argv": argv, "code": r.code, "draft": snap,
                         "output": engine_mod.scrub(r.stdout, env_keys.values())[-6000:],
                         "error": engine_mod.scrub(r.stderr, env_keys.values())[-3000:]})
        return r
    engine_mod.run = run_cmd

    now = datetime.datetime.now()
    deps = agent.Deps(engine_root=engine, home=home, keys=env_keys, today=now.strftime("%Y-%m-%d"),
                      now=now.strftime("%Y-%m-%d %A %H:%M"), say=say, log=log,
                      writers=os.environ["HARMONICFITNESS_WRITERS"]   # as the worker sets it (settings.writers)
                      if os.environ["HARMONICFITNESS_WRITERS"] in agent.WRITERS else "three")
    deps_box["deps"] = deps
    turns, history, line = [], None, a.line.format(minutes=a.minutes)
    for turn in range(3):
        deps_box["turn"] = turn
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
    lint = lint_code = None
    deps_box["turn"] = "final check"
    if draft_path and deps.offer:
        r = tools.run(deps, ["build", draft_path, deps.offer.get("name") or tools.build_name(draft_path),
                             "--coach", deps.offer.get("coach") or deps.brief_coach or "Coach Freya", "--lint-only"])
        lint, lint_code = r.output + "\n" + r.error, r.code
    result = {"minutes": a.minutes, "provider": a.provider, "model": providers.PROVIDERS[a.provider].model,
              "line": line if not turns else a.line.format(minutes=a.minutes), "set": a.set, "turns": turns, "events": events, "room": room,
              "offer": deps.offer, "draft_path": draft_path, "draft": draft, "final_lint": lint,
              "final_lint_code": lint_code, "writers": captured, "history": history,
              "requests_counted": sum((t["usage"] or {}).get("requests", 0) for t in turns),
              "requests_recorded": len(requests)}
    for name, rows in (("requests.jsonl", requests), ("commands.jsonl", commands)):
        with open(os.path.join(a.out, name), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, default=str) + "\n" for r in rows)
    with open(os.path.join(a.out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=str)
    brief_t = next((e["t"] for e in events if (e["tool"] or "").startswith("run brief") and e["code"] is None), None)
    end = turns[-1]["start"] + turns[-1]["seconds"]
    print(json.dumps({"out": a.out, "priced": deps.offer is not None, "lint": lint_code,
                      "requests": [result["requests_counted"], len(requests)], "turns": len(turns), "total": round(end, 1),
                      "from_brief": round(end - brief_t, 1) if brief_t is not None else None,
                      "error": turns[-1]["error"]}))


if __name__ == "__main__":
    main()
