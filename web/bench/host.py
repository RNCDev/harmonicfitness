"""The host alone, asked again on a recorded run's own prompt: one paid request, to try a change to the host's
call (its thinking level) on what the room really gave it.

  HARMONICFITNESS_KEYS=me/.env .venv/bin/python web/bench/host.py <out-dir> <run-dir> [--level LOW] [--set NAME=VALUE]

<run-dir> is a run_one.py run on OpenRouter (.bench/out/<label>/<n>): its result.json holds the host's prompt and
answer, and its home the brief and skeleton. The new answer goes in the same room steps the site takes after the
host (unasked stories out, edits on the skeleton with its long holds opened), and so does the recorded one, so
<out-dir>/recorded.draft.txt and <out-dir>/asked.draft.txt differ only in the host's call. Each is linted
(lints.json), and the request's tokens and cost are written to requests.jsonl in run_one.py's shape, so tokens.py
reads it. Nothing is recorded, logged or delivered.
"""
import argparse
import asyncio
import dataclasses
import datetime
import glob
import json
import os
import shutil
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("run")
    p.add_argument("--level", default="LOW", help="the host's thinking level (HIGH, MEDIUM or LOW)")
    p.add_argument("--set", action="append", default=[])
    a = p.parse_args()
    out, run = os.path.abspath(a.out), os.path.abspath(a.run)
    os.environ.setdefault("HARMONICFITNESS_WRITERS", "three")
    os.environ.setdefault("HARMONICFITNESS_PYTHON", os.path.join(REPO, ".venv", "bin", "python"))
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    home = os.path.join(out, "home")
    shutil.copytree(os.path.join(run, "home"), home, symlinks=True)
    os.environ["HARMONICFITNESS_HOME"] = home
    sys.path[:0] = [os.path.join(REPO, "web"), os.path.join(REPO, "tools"), os.path.dirname(os.path.abspath(__file__))]
    import keys  # noqa: PLC0415
    from pydantic_ai.usage import RunUsage  # noqa: PLC0415
    from webapp import agent, providers  # noqa: PLC0415
    from webapp.agent import tools, writers  # noqa: PLC0415
    import room  # noqa: PLC0415
    import run_one  # noqa: PLC0415
    run_one.apply(writers, a.set)

    with open(os.path.join(run, "result.json"), encoding="utf-8") as f:
        fx = json.load(f)
    hosted = [w for w in fx["writers"] if w["who"] == "host"]
    if not hosted:
        raise SystemExit(f"no host request in {run}")
    prompt, recorded = hosted[-1]["prompt"], hosted[-1]["output"]
    skeleton = room.skeleton_of(run, tools)
    opened, _ = writers.open_holds(skeleton)

    requests = []
    model = providers.model_for("openrouter", keys.get("openrouter"))
    base = next(k for k in type(model).__mro__ if "request" in k.__dict__)
    orig_request = base.__dict__["request"]
    t0 = time.monotonic()

    async def request(self, messages, model_settings, model_request_parameters):
        began = time.monotonic()
        resp = await orig_request(self, messages, model_settings, model_request_parameters)
        requests.append({"n": len(requests) + 1, "t": round(began - t0, 2), "who": "host",
                         "seconds": round(time.monotonic() - began, 2), "usage": dataclasses.asdict(resp.usage),
                         "model": resp.model_name, "settings": {k: v for k, v in (model_settings or {}).items()
                                                               if "reasoning" in k or "thinking" in k},
                         "provider_details": getattr(resp, "provider_details", None)})
        return resp
    setattr(base, "request", request)

    deps = agent.Deps(engine_root=REPO, home=home, keys={}, today=datetime.date.today().strftime("%Y-%m-%d"),
                      now="", log=lambda text: None, writers="three")
    got = asyncio.run(writers._ask(deps, "host", writers.HOST, model, prompt, RunUsage(), a.level))
    asked = got.output.model_dump()

    real = fx["draft_path"]
    rel = real[3:] if real.startswith("me/") else os.path.relpath(real, os.path.join(run, "home"))
    path = "me/" + rel
    coach = (fx.get("offer") or {}).get("coach") or "Coach Ana"
    name = (fx.get("offer") or {}).get("name") or tools.build_name(path)
    lints = {}
    for label, answer in (("recorded", recorded), ("asked", asked)):
        edits = writers.Edits.model_validate(answer).segments
        kept, unasked = writers.without_unasked(edits, {n: None for n in range(1, 999)})
        draft = writers.apply_edits(opened, kept)
        with open(os.path.join(out, f"{label}.draft.txt"), "w", encoding="utf-8") as f:
            f.write(draft)
        tools.write_file(deps, path, draft)
        r = tools.run(deps, ["build", path, name, "--coach", coach, "--lint-only"])
        lints[label] = {"code": r.code, "report": (r.output + "\n" + r.error)[-2500:]}
    with open(os.path.join(out, "requests.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(r, default=str) + "\n" for r in requests)
    with open(os.path.join(out, "lints.json"), "w", encoding="utf-8") as f:
        json.dump(lints, f, indent=1)
    u = requests[-1]["usage"] if requests else {}
    print(json.dumps({"out": os.path.relpath(out, REPO), "level": a.level, "requests": len(requests),
                      "out_tokens": u.get("output_tokens"), "thinking": (u.get("details") or {}).get("reasoning_tokens"),
                      "cost": sum(float((r.get("provider_details") or {}).get("cost") or 0) for r in requests),
                      "lint": {k: v["code"] for k, v in lints.items()}}))


if __name__ == "__main__":
    main()
