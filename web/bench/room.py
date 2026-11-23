"""The writers' room alone, on a recorded run's brief and skeleton, written by Claude through the CLI (claude_cli.py).

  .venv/bin/python web/bench/room.py <out-dir> <fixture-run-dir> [--model <id>] [--salt <text>] [--set NAME=VALUE]...
      [--skeleton <file>] [--cache <dir>]

To try a branch, run its worktree's copy of this file (git worktree add .bench/wt/<branch> <branch>) with
HARMONICFITNESS_PYTHON and HARMONICFITNESS_BENCH_CACHE pointing at the main checkout's, and an <out-dir> under the
main checkout's .bench/out, so the arms share kept answers and the judge reads them side by side.

A fixture is a run_one.py run of the real agent (.bench/out/<label>/<n>): its home holds the brief and the menu, and
its first clean skeleton is what the room fills here. So every arm of a comparison starts from the same plan, and
the CLI model's kept answers (.bench/claude-cache) make two arms differ only from the step under test onward. The
fixture must be today's (a menu is dated); nothing is recorded, logged or billed to a provider.

Writes result.json in run_one.py's shape as far as the room goes (draft, final_lint, writers, room), requests.jsonl
(one row a CLI call), drafts/ (the draft as each lint read it) and checks.json (what code can tell of the script).
"""
import argparse
import asyncio
import contextvars
import datetime
import glob
import json
import os
import re
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WHO = contextvars.ContextVar("who", default=None)
EFFORT = {"LOW": "low", "MEDIUM": "medium", "HIGH": "high"}


def skeleton_of(fixture: str, tools) -> str:
    """The fixture's last draft with no words: the skeleton its room was given."""
    found = None
    for path in sorted(glob.glob(os.path.join(fixture, "drafts", "*.draft.txt"))):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if tools.is_skeleton(text):
            found = text
    if found is None:
        raise SystemExit(f"no skeleton among {fixture}/drafts")
    return found


def checks(draft: str, result: dict, content_md: str, limit: str = "left knee") -> dict:
    """What code can tell of a script: the opening's lines, story names outside the notes, never-bring-up words, a
    greeting or goodbye mid-session, and how often the limit is named after the opening (its one reminder)."""
    sys.path[:0] = [os.path.dirname(os.path.abspath(__file__))]
    import summarize  # noqa: PLC0415
    unknown, odd = summarize.fidelity(result)
    bodies = re.split(r"^@@.*$", draft, flags=re.MULTILINE)[1:]
    later = [len(re.findall(re.escape(limit), summarize.STORY.sub(" ", b), re.IGNORECASE)) for b in bodies[1:]]
    return {"opening": summarize.opening(draft), "not_in_notes": unknown, "one_voice": odd,
            "never_said": summarize.never_said(draft, content_md),
            "limit_named_after_opening": sum(later), "segments_naming_limit": sum(1 for n in later if n)}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("fixture")
    p.add_argument("--model", default="claude-sonnet-5-5")
    p.add_argument("--salt", default="")
    p.add_argument("--set", action="append", default=[])
    p.add_argument("--skeleton", help="a skeleton to fill in place of the fixture's own")
    p.add_argument("--aim", type=float, default=0.77, help="the share of a segment's words the host is asked for")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--cache", default=os.environ.get("HARMONICFITNESS_BENCH_CACHE") or os.path.join(REPO, ".bench", "claude-cache"),
                   help="where the CLI model's answers are kept (shared by the arms of a comparison, so by its worktrees)")
    a = p.parse_args()
    out, fixture = os.path.abspath(a.out), os.path.abspath(a.fixture)
    os.environ["HARMONICFITNESS_HOME"] = os.path.join(out, "home")
    os.environ.setdefault("HARMONICFITNESS_WRITERS", "three")
    os.environ.setdefault("HARMONICFITNESS_PYTHON", os.path.join(REPO, ".venv", "bin", "python"))
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    sys.path[:0] = [os.path.join(REPO, "web"), os.path.join(REPO, "tools"), os.path.dirname(os.path.abspath(__file__))]
    from pydantic_ai.capabilities import NativeTool  # noqa: PLC0415
    from pydantic_ai.usage import RunUsage  # noqa: PLC0415
    from webapp import agent, engine as engine_mod  # noqa: PLC0415
    from webapp.agent import tools, writers  # noqa: PLC0415

    import claude_cli  # noqa: PLC0415
    import run_one  # noqa: PLC0415
    # Sonnet writes about a tenth over the words it's asked for at the site's 0.85 for a model that isn't Gemini,
    # and the review can't cut that much: the rig asks it for less, so its scripts reach the check near their length
    writers.AIMS["other"] = a.aim
    run_one.apply(writers, a.set)

    with open(os.path.join(fixture, "result.json"), encoding="utf-8") as f:
        fx = json.load(f)
    home = os.path.join(out, "home")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(out, "drafts"))
    shutil.copytree(os.path.join(fixture, "home"), home, symlinks=True)
    real = fx["draft_path"]
    rel = real[3:] if real.startswith("me/") else os.path.relpath(real, os.path.join(fixture, "home"))
    path = "me/" + rel
    if a.skeleton:
        with open(a.skeleton, encoding="utf-8") as f:
            skeleton = f.read()
    else:
        skeleton = skeleton_of(fixture, tools)
    with open(os.path.join(home, rel), "w", encoding="utf-8") as f:
        f.write(skeleton)

    t0 = time.monotonic()
    room, captured, requests, commands = [], [], [], []

    def stamp() -> float:
        return round(time.monotonic() - t0, 2)

    def record(row: dict) -> None:
        requests.append({"n": len(requests) + 1, "t": stamp(), "who": WHO.get() or "agent", **row})

    model = claude_cli.ClaudeCLI(a.model, cache=None if a.no_cache else a.cache,
                                 salt=a.salt, record=record,
                                 # each writer thinks as hard as the site has it think (writers.LEVEL)
                                 effort=lambda: EFFORT.get(writers.LEVEL.get(
                                     "research" if WHO.get() == "top-up" else WHO.get() or "", ""), "low"))
    orig = writers._ask

    async def ask(deps, who, ag, mdl, prompt, usage, level, capabilities=(), history=None, **more):
        token = WHO.set(who)
        began = stamp()
        try:
            r = await orig(deps, who, ag, mdl, prompt, usage, level, capabilities, history, **more)
        finally:
            WHO.reset(token)
        captured.append({"t": stamp(), "began": began, "who": who, "level": level, "prompt": prompt,
                         "output": r.output.model_dump()})
        return r
    writers._ask = ask

    orig_run = engine_mod.run

    def run_cmd(engine_root, home_dir, argv, *args, **kwargs):
        began, snap = stamp(), None
        if argv and argv[0] == "build" and len(argv) > 1:
            src = os.path.join(home_dir, argv[1][3:] if argv[1].startswith("me/") else argv[1])
            try:
                with open(src, encoding="utf-8") as f:
                    text = f.read()
                snap = f"drafts/{len(commands) + 1:03d}-lint.draft.txt"
                with open(os.path.join(out, snap), "w", encoding="utf-8") as f:
                    f.write(text)
            except OSError:
                pass
        r = orig_run(engine_root, home_dir, argv, *args, **kwargs)
        commands.append({"n": len(commands) + 1, "t": began, "seconds": round(stamp() - began, 2),
                         "who": WHO.get() or "room", "argv": argv, "code": r.code, "draft": snap,
                         "output": r.stdout[-6000:], "error": r.stderr[-3000:]})
        return r
    engine_mod.run = run_cmd

    today = datetime.date.today().strftime("%Y-%m-%d")
    coach = (fx.get("offer") or {}).get("coach") or "Coach Freya"
    name = (fx.get("offer") or {}).get("name") or tools.build_name(path)
    deps = agent.Deps(engine_root=REPO, home=home, keys={}, today=today,
                      now=datetime.date.today().strftime("%Y-%m-%d %A") + " 12:00",   # the same in every arm
                      log=lambda text: room.append({"t": stamp(), "line": text}), writers="three")
    deps.brief_coach = coach
    err = None
    try:
        draft, note = asyncio.run(writers.write(deps, model, RunUsage(), path, [NativeTool(agent.SEARCH)], name, coach))
        tools.write_file(deps, path, draft)
    except Exception as e:  # noqa: BLE001 - recorded as the run's failure
        import traceback  # noqa: PLC0415
        traceback.print_exc()
        draft, note, err = "", "", f"{type(e).__name__}: {e}"[:500]
    lint = lint_code = None
    if draft:
        r = tools.run(deps, ["build", path, name, "--coach", coach, "--lint-only"])
        lint, lint_code = r.output + "\n" + r.error, r.code
    result = {"minutes": fx.get("minutes"), "provider": "claude-cli", "model": a.model, "line": fx.get("line"),
              "set": a.set, "fixture": fixture, "turns": [], "events": [], "room": room, "offer": None,
              "draft_path": path, "draft": draft, "final_lint": lint, "final_lint_code": lint_code,
              "writers": captured, "note": note, "error": err, "seconds": stamp()}
    for fname, rows in (("requests.jsonl", requests), ("commands.jsonl", commands)):
        with open(os.path.join(out, fname), "w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, default=str) + "\n" for r in rows)
    with open(os.path.join(out, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, default=str)
    try:
        with open(os.path.join(home, "content.md"), encoding="utf-8") as f:
            content = f.read()
    except OSError:
        content = ""
    found = checks(draft, result, content) if draft else {}
    lints = [c["code"] for c in commands if c["argv"][0] == "build"]
    asked = {}
    for row in requests:
        asked[row["who"]] = asked.get(row["who"], 0) + 1
    found.update(lint=lint_code, lints=lints, calls=asked, searches=sum(r["searches"] for r in requests),
                 fresh_calls=sum(not r["cached"] for r in requests), seconds=stamp(), error=err)
    with open(os.path.join(out, "checks.json"), "w", encoding="utf-8") as f:
        json.dump(found, f, indent=1)
    print(json.dumps({"out": os.path.relpath(out, REPO), **found}))


if __name__ == "__main__":
    main()
