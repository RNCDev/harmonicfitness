# The script-writing loop

How a change to script writing is tried before a release (maintainer only): write real sessions with the web
coach, time them, and have independent judges score them. Each loop is a change, a run, the scores, and the next
change. It replaced the forty-case grid of invented listeners (until 0.49.6), which judged against a six-part
rubric that marked scripts down a point or two for faults a listener wouldn't notice.

## 1. Run

`web/local_turn.py` runs one web-app workout turn on this computer, with the worker's own agent, instructions,
tools and step 1, on Gemini, against a copy of a context folder: no deploy, and nothing sent to the live site. The
key comes from the repo root's `.env` (`GEMINI_API_KEY`), never printed.

```sh
.venv/bin/python web/local_turn.py <context folder> <out dir> "<request>"
```

- **The context folder** is a snapshot, the same for every loop of a set so runs compare: a `pull`'s `me/` (from
  `./harmonicfitness pull`) is the listener as the site has them. Copy it aside once and point every run at the copy.
- **The requests:** the page's sentence, the same each loop, such as "Hey, coach Freya, I'd like a 30-minute
  full-body workout at home. Nothing's bothering me today." and "Hey, coach Freya, I'd like a 30-minute strength
  workout at the gym. Go easy on my left knee today." (a limit keeps safety in the test). Two runs can go side by
  side; each has its own copy.
- **Out:** `<out>/me/` holds the turn's files (the draft, brief and menu in `me/workouts/<stem>/`),
  `<out>/history.json` every request of the agent, and `<out>/writers.json` each of the three writers' calls (the
  story writer, the coach writer, the editor: its level, seconds, tokens, output and what its searches found, for the
  judges). The printed line gives the turn's seconds, requests and tokens. `HARMONICFITNESS_WRITERS=one` runs the
  agent writing the script itself, in passes, as before 0.51.0.
- **One writer at a time:** each writer's task is a paragraph beside `web/webapp/agent/writers.py`
  (`story-writer.md`, `coach-writer.md`, `editor.md`), followed by its part of `knowledge/script.md` and
  `knowledge/tts-rules.md`; a loop can change one writer and judge the coaching and the stories apart.

A live run, once a release is deployed, is the same request sent to the site and the conversation pulled with
`./harmonicfitness pull --conversation <id>`; its folder holds the same `history.json`.

## 2. Time

```sh
.venv/bin/python docs/eval/timing.py <out dir>
```

Each model request's seconds, output and input tokens and tool calls; what each draft write added up to; and each
build's spread of segment fills and its distance from plan. The usual costs: thinking (a write's output tokens far
above the script's own), round trips before the first word, and passes that lengthen or trim a draft a little at a
time.

## 3. Judge

`judge.md` is the judge's prompt: safety, efficacy and engagement, 1 to 5, each against written anchors, judged as
the listener would hear it, with at most three improvements. Fill `{REQUEST}`, `{SCRIPT}` (the draft's path),
`{HOME}` (the turn's `me/`, with its trailing slash) and the feeds sheet's date, and give it to **two independent
judges a script**; average their scores. When comparing with an earlier run, judge that run again with the same
prompt rather than trusting old scores.

## 4. Change

Prefer a check in code to a sentence of guidance, and fewer rules to more: each rule the writer weighs costs
attention, and rules collide (a story that keeps its source's numbers became a list of figures). Make a fix for
safety or fact when both judges name it. The changelog records what each loop found and changed.
