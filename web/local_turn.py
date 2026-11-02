"""Run one web-app workout turn on this computer, as the worker does, on a fresh copy of a context folder: the eval
loops' way to try a change to the web coach without a deploy (maintainer only).

    .venv/bin/python web/local_turn.py <a context folder, such as a pull's me/> <out dir> "<request line>"

The same agent, instructions, tools and step 1 as the worker, on Gemini (with HARMONICFITNESS_WRITERS=two, the
two writers' version, whose calls go to <out>/writers.json). The key comes from the repo root's .env
(as web/qat_key.py reads it) and is never printed; it writes the script and prices a Gemini coach. Saves
<out>/me/ (the turn's files) and <out>/history.json (as `pull` saves one), and prints the time, the requests and
tokens, the offer and the reply. Nothing is sent to the live site, and the context folder itself isn't changed.
"""
import datetime
import json
import os
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "web"))
from qat_key import read_key  # noqa: E402
from webapp import agent, providers, worker  # noqa: E402

snapshot, out, line = sys.argv[1], sys.argv[2], sys.argv[3]
home = os.path.join(out, "me")
if os.path.exists(out):
    shutil.rmtree(out)
shutil.copytree(snapshot, home, ignore=shutil.ignore_patterns("web", ".git", ".audio-cache", "*.mp3"))
key = read_key(os.path.join(ROOT, ".env"))
if not key:
    sys.exit("no GEMINI_API_KEY in the repo's .env")

now_dt = datetime.datetime.now()
today, now = now_dt.date().isoformat(), now_dt.strftime("%Y-%m-%d %A %H:%M")
zone = worker.listener_zone(now)
deps = agent.Deps(engine_root=ROOT, home=home, keys={"GEMINI_API_KEY": key, **({"TZ": zone} if zone else {})},
                  today=today, now=now, cancel=threading.Event())
deps.setup = agent.needs_setup(home)
deps.coach = agent.audition_open(home)
deps.chars_left = 10 ** 9
model = providers.model_for("google", key)
del key

pool = ThreadPoolExecutor(max_workers=1)
sheet = os.path.join(home, "workouts", "research", "daily", f"{today}-feeds.md")
if agent.intent(line) == "workout" and not os.path.exists(sheet):
    deps.feeds = agent.start_feeds(deps, pool)
start = time.monotonic()
context = agent.prefetch(deps, line)
pre = time.monotonic() - start
outcome = agent.run_turn(model, deps, None, line, None, context=context)
total = time.monotonic() - start
pool.shutdown(wait=True)
u = outcome.usage
with open(os.path.join(out, "history.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps({"id": 0, "history": json.loads(outcome.history_json)}))
if deps.tracks:   # HARMONICFITNESS_WRITERS=two: each writer's call, for docs/eval/timing.py
    with open(os.path.join(out, "writers.json"), "w", encoding="utf-8") as f:
        json.dump(deps.tracks, f, indent=1)
print(f"[{total:.0f}s] (step 1 {pre:.1f}s) {u.get('requests')} requests, {u.get('input_tokens')} in, "
      f"{u.get('output_tokens')} out, {u.get('searches', 0)} searches; offer={json.dumps(deps.offer)}")
print(outcome.reply or "")
