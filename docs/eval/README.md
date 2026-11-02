# The script-writing loop

How a change to the web app's three writers is tried (maintainer only). Content first: safety, clarity, and
personal content woven into the workout; speed only once those score well.

The three writers (`web/webapp/agent/writers.py`), each a short task beside it followed by its part of
`knowledge/script.md` and `knowledge/tts-rules.md`:
- **Coach Writer** (`coach`, `coach-writer.md`): the coaching.
- **Personal Content Writer** (`content`, `personal-content-writer.md`): the stories in the rests, with its searches.
- **Final Script Writer** (`final`, `final-script-writer.md`): joins the two into one coach and fixes the build's issues.

Everything runs on this computer, on Gemini, with the key in `me/.env` (never printed), and lands in `me/.eval/`:
the listener's, never the engine's.

## 1. Freeze, once

```sh
.venv/bin/python docs/eval/loop.py freeze
```

Copies `me/`, fetches the feeds sheet once, then runs one whole web-app workout turn for each of eight 30-minute
requests (`loop.REQUESTS`: home, gym with a knee, dumbbell conditioning, a beginner with bands, kettlebells with a low
back, rower sprints, hotel dumbbells, barbell with a shoulder), side by side. Each workout keeps its skeleton, brief,
menu, stories, coaching and what the content writer's searches found. It also records each writer's prompt size:
the cap no challenger may pass. `--only 3,5` re-freezes those workouts alone. Last it writes the research notes
(`loop.py research`, also run alone): Gemini's search hands the code only its suggestion chips, never the pages, so
one searching call writes about twenty items as plain notes with sources, `me/.eval/frozen/research.md`. They are a
content round's material and what the judges check story facts against. Research happens here and never again.

## 2. A round tries one writer, in two stages

The eight workouts have roles (`loop.SCREEN`, `CONFIRM`, `HOLDOUT`): three screen, three confirm, two are held out
until the end, so the writers can't get good at only these.

```sh
.venv/bin/python docs/eval/loop.py prompts coach      # me/.eval/prompts/coach/champion.md
# copy it to B.md ... F.md beside it, one change each: a small one from the judges' notes, a bold rewrite, a wild card
.venv/bin/python docs/eval/loop.py round coach        # the screen: A and every challenger on the screen's three
.venv/bin/python docs/eval/loop.py judge <round>; ...; loop.py tally <round>
.venv/bin/python docs/eval/loop.py confirm <round>    # A and the screen's best two on the confirm's three
.venv/bin/python docs/eval/loop.py judge <round>; ...; loop.py tally <round>   # merged with the screen's verdicts
```

The champion (A, the prompt as the source files make it) runs against the challengers (`--versions A,B` to choose,
`--workouts` to pick others). Only that writer runs again: the others' saved output stands, on the freeze's date. In
a content round the writer searches nothing and gets the research notes instead, so research stays the same. With no
challengers it's a noise round (A, A, A): the same prompt three times, to see how much verdicts move by chance. A
coach challenger can't change the safety rules, and none may pass its cap. A script that isn't lint clean counts as
a failure. Two winners on different criteria can be combined (crossover) as the next round's challenger.

## 3. Judge, with three Claude personas

`loop.py judge <round>` writes one prompt per persona and group of workouts (`judge.md`, filled), the scripts
lettered in a shuffled order of each job's own. Give every job to a fresh Claude subagent with no other context; it
writes `verdict.json` beside its prompt.
- **The trainer:** a strength coach and physio who has coached through earbuds: right, enough, not too much.
- **The listener:** reads as the listener, from their profile, topics and log feedback: is this my world?
- **The producer:** a podcast producer: pace, a story's shape, one voice, the seams.

Each marks safety pass or fail (the line quoted), ranks clarity, content and flow, scores them 1 to 5, and gives
each writer at most one note.

## 4. Tally, then change

```sh
.venv/bin/python docs/eval/loop.py tally <round>      # me/.eval/rounds/<n>/tally.md
```

A challenger wins a workout when at least two of the three judges rank it above the champion there (and more prefer
it than not). Round 0, three copies of one prompt, showed how much is chance: copies won 5 of 6 workouts against
an identical champion, while averages moved only 0.3. So a challenger is kept only when its average on its
writer's own criterion beats the champion's by at least 0.5 (`loop.MARGIN`, `tally --margin`) and it wins at least
two more workouts than it loses (`NET_WINS`). The screen's best two by their writer's own criterion (coach: clarity; content: content; final: flow)
go on to the confirm; a confirmed challenger is kept when, over all six workouts, it clears that bar, fails no
safety or lint check, and loses no ground elsewhere. A safety fail is the judge's claim: read the quoted line
before acting on it. A kept change goes into the source file (the task
`.md`, or `script.md` when it's shared guidance, then `./harmonicfitness test`) and is the next champion. A writer
scoring 4+ on its criterion, winning or tying its round, is locked and the loop moves to the next. Before the speed
phase each locked writer gets one more round against the others' final versions, and `loop.py holdout` writes the
held-out workouts with every champion against the app's script as frozen (O).

`loop.py status` lists the freeze and the rounds.
