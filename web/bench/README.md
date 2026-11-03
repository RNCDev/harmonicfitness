# The script-writing bench

Times the website's script writing from the brief to the price, step by step, and reads the scripts for what matters
to the listener. It's for the maintainer, and it isn't a test: each run calls Gemini on the maintainer's own key
(about 45 cents for a 15-minute workout, about a dollar for a 30-minute one) and nothing checks it in CI.

## What a run is

`run_one.py` runs the website's agent in this process, as the worker would but with no database: the page's starter
sentence ("Hey, coach Freya, I'd like a 15-minute strength workout at home. Go easy on my left knee, and keep off my
right shoulder today."), "Go with your pick" to any question, and a stop at the price. Nothing is recorded or logged.
Two one-sided limits on opposite sides make it a hard request: the menu, the opening and every set's side wording
are all in play.

Each run works on its own copy of the listener's folder, made from `.bench/base`. The first batch of the day makes
that from `me/`, without the key file or the clip cache, and fetches the day's feeds once so every run reads the
same sheet. The Gemini key is read from the real `me/.env` by the engine's own loader and never printed.

Everything a run writes goes to `.bench/` at the root: git-ignored, left out of the Fly image, and refused by the
privacy hook, since each run holds a copy of the listener's files. Nothing personal belongs in this folder.

## Running it

```sh
web/bench/batch.sh <label> <minutes> <runs> [--engine <checkout>] [--set NAME=VALUE]...
.venv/bin/python web/bench/summarize.py <label>...
```

- `batch.sh` starts one run every 20 s: Gemini's paid tier 2 caps input at 3,000,000 tokens a minute, and fifteen
  runs starting together passed it.
- `--engine` runs another checkout, so a change can be measured against the last release:
  `git worktree add .bench/engine-0.58.0 v0.58.0`, then `--engine .bench/engine-0.58.0`.
- `--set` changes one of the writers' settings for the run: `LEVEL.trainer=LOW`, `STORY_WORDS=100`.
- Don't start a batch near midnight: a run's menu is dated by the day it began, so a run that crosses midnight
  fails its build.

`summarize.py` prints, for each run:
- seconds from the brief to the price, to the writers' room, in it and after it;
- the agent's fixes after the room, and the review's passes;
- each writer's seconds;
- the must-say lines the final script leaves out;
- names in a told story that none of the researcher's notes hold (a name the host may have made up; read the
  story to judge);
- a greeting or goodbye mid-session.

For each label it prints the medians, and the host's words against what it was asked, by kind of segment.

## Deciding what to keep

Set the rule before the runs:
- Three runs a configuration, and Gemini's thinking time swings widely, so a median difference under about 25
  percent is noise.
- A change that removes fixed work (a round trip, a lint, a second call) is kept on reasoning when every run is
  clean and the step log shows the step gone.
- A change to what a writer does is kept only if the median holds or drops and quality holds in every run: priced,
  every must-say line in, the sides right, no story fact outside its notes, one voice start to finish.

## Results

### 0.59.0 (2026-11-03): the host's length, stories from nowhere, the knowledge files

0.58.0 itself (a worktree of the tag) against this release's code, three runs each, from the brief to the price.

| | 0.58.0 | 0.59.0 |
|---|---|---|
| 15 minutes, median s (runs) | 149 (146, 149, 185) | 130 (123, 130, 248) |
| Fixes after the room, median | 2 | 0 (0, 0, 0) |
| Must-say lines kept | 51 of 54 | 41 of 41 |
| Host's script at the review, against plan | 17 to 24 percent long | 0.5 percent short to 11 percent long |
| A story rest, host's words against asked | 1.23 (its coaching 1.65) | 1.06 (its coaching 1.00) |
| 30 minutes, median s (before the last three fixes) | 252 (250, 252, 278) | 172 (142, 172, 222) |

On the way there:
- **Rests labelled with the next movement** ("Rest before single-arm floor press") made the rest that movement's
  segment, so the reason the other side rests couldn't be said there: five and six fixes after the room, and the
  host thinking up to 150 s. Back to plain `Rest`.
- **The coaching floor in full** left a session of thirty-second rests no story at all (three runs in twelve). A
  short rest now keeps a 40-word story.
- **The limit's stop signs** at the healthy side's set were cut by the review to pass the build; the build now lets
  them through, in the brief's forms.
- **Still open:** the host thinks 130 to 150 s in about one run in three (usually 30 to 60), and the trainer swings
  from 28 to 86 s.

### 0.58.0 (2026-11-02 and 11-03): the five experiments

The 15-minute request, three runs a configuration, from the brief to the price.

| Configuration | Median s | Kept? |
|---|---|---|
| 0.57.0 as it was (two sets of three) | 234 and 239 | |
| A: a clean skeleton goes straight to the writers | room reached in 13 s rather than 17 | Yes |
| B: code checks the must-say lines, so the review can be skipped | 223; the review was never skipped | No |
| C: the build reuses the room's clean lint | under a second here, about 5 s on Fly | Yes |
| D: a story told before gives way to a spare | never needed in the timed runs | Yes, on reasoning |
| E: the host writes in two halves at once | 236; the slower half sets the pace | No |
| The researcher at LOW | 185; research 17 to 27 s rather than 78 to 160 | Yes |
| The host at LOW | 203; scripts 12 percent long, with silences | No |
| All kept (A, C, D, research at LOW) | 184 | |

Found along the way, and fixed in 0.58.0:
- Two limits on opposite sides could never pass the build: the opening check read one limit's line as the other's
  care on the wrong side.
- The opening check refused the brief's own opening line beside the healthy-side movement.
- A skeleton's empty welcome failed the opening check, so a skeleton under a one-sided limit never linted clean.

Found and left for 0.59.0 (above):
- The host wrote long: first sets and the coaching around a rest's story ran 30 to 70 percent over what it was asked
  for, so scripts reached the review 6 to 14 percent long.
- A rest the agent labelled with a topic got a story made up from the label when the researcher brought none.
- The trainer became the slowest writer, at 60 to 104 s.
- The skeleton's seconds took the agent up to four tries to add up.
