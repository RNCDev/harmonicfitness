# The script-writing bench

Times the website's script writing from the brief to the price, step by step, and reads the scripts for what matters
to the listener. It's for the maintainer, and it isn't a test: each run calls Gemini on the maintainer's own key
(about 45 cents for a 15-minute workout, about a dollar for a 30-minute one) and nothing checks it in CI.

## What a run is

`run_one.py` runs the website's agent in this process, as the worker would but with no database: the page's starter
sentence ("Hey, coach Ana, I'd like a 15-minute strength workout at home, right now. Go easy on my left knee, and
keep off my right shoulder today."), "Go with your pick" to any question, and a stop at the price. Nothing is recorded
or logged. Two one-sided limits on opposite sides make it a hard request: the menu, the opening and every set's side
wording are all in play.

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
- `--provider openrouter --model anthropic/claude-opus-5.5` writes with another provider's model (the OpenRouter
  key from the key file; the Gemini key still prices the coach), and `--line` gives another request sentence, for
  a home the default sentence doesn't fit. To bench an invented listener rather than `me/`, run with
  `HARMONICFITNESS_HOME=docs/demos/listeners/<slug>` and `HARMONICFITNESS_KEYS=me/.env`: only then may a run's
  files leave `.bench/`.

Every run also writes `requests.jsonl` (each model request: who asked, the agent's phase, the size sent, the
provider's usage as it came back), `commands.jsonl` (each engine command) and `drafts/` (the draft as each lint
read it). `.venv/bin/python web/bench/tokens.py <run-dir>...` prints a run's tokens and estimated cost by step.

`summarize.py` prints, for each run:
- seconds from the brief to the price, to the writers' room, in it and after it;
- the agent's fixes after the room, and the review's passes;
- each writer's seconds;
- what the opening leaves out of the made-by-AI line and the stop rule;
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

### The gate

`.venv/bin/python web/bench/compare.py <baseline-label> <candidate-label>` prints, per label, the medians of writing
cost, requests, input tokens and seconds from the brief to the price, and how many runs fail a quality check, then
`GATE: pass` or `GATE: fail (<reasons>)`. It passes only when every candidate run is compliant (priced, final lint
clean, and nothing from `summarize.py`'s opening, story-names, one-voice and `never_said` checks: the weekday,
month, season or weather words a listener's `## Never bring up` rules out) and the median writing cost is no higher
than the baseline's. Bench Jo, whose rules the clips need, with `HARMONICFITNESS_HOME=docs/demos/listeners/jo`:
`batch.sh` keeps one prepared copy per home, so Jo's and `me/`'s never share a folder.

## The room alone, written by Claude

A change to what the writers do can be tried many times before a paid run, with no provider bill:
- `room.py <out> <fixture>` runs the writers' room alone (`writers.write`) on a recorded run's brief and first clean
  skeleton (a `run_one.py` run, its home included), written by Claude Sonnet 5.5 through the Claude Code CLI
  (`claude_cli.py`, `claude -p`). Every arm of a comparison starts from the same plan, and the CLI's answers are kept
  in `.bench/claude-cache` by what was asked, so two arms differ only from the step under test; `--salt` asks
  afresh. Each writer thinks at the effort the site gives it, and `--aim` (0.77) asks Sonnet for fewer words, since
  it writes about a tenth long. Writes `result.json` in `run_one.py`'s shape and `checks.json`.
- `host.py <out> <run>` asks the host again, alone and paid, on a recorded OpenRouter run's own prompt
  (`--level LOW`), and lints the old answer and the new one on the same skeleton.
- `judge.py <baseline> <candidate> --prepare` writes each pair as a blind folder (`.bench/judge/<hash>/<run>-a|b/`,
  both orders), for a judge the CLI can't reach: a Claude Code subagent on Opus, told to read `task.md` there and
  write `verdict.json`; `--tally` reads them. It scores each script 1 to 5 on safety, coaching, voice, stories and
  personal, and lists defects with the words quoted.

The judge is noisy: a baseline against its own rerun went 1 to 5 over three pairs. Count by pair (both orders
agreeing), at fifteen pairs or more, and read every safety defect in the script.

## Results

### 0.92.0 (2026-11-22): a fifth off the hosted script

Paid 20-minute runs for Jo through OpenRouter on Gemini 3.8 Flash, five fixed requests, and Sonnet rooms judged
blind by Opus. The baseline wrote a script for $0.21 to $0.32 (mean about $0.27), research and its top-up about
45 percent of it, nearly all web searches at about 1.4 cents each.

| Change | What it did | Kept? |
|---|---|---|
| One research pass on a four-search budget | searches 4 or 5 against 6 to 8; about 18 percent less; judged level | Yes |
| The planning agent skips `movements --about` | its planning 3.0 to 3.5 cents against 3.9 to 6.3 | Yes |
| A clean script goes without a review | one false stop removed ("an A I"); a request saved where it applies | Yes |
| The researcher asked for 1.15 pieces a minute | a top-up (2 to 6 cents) in 1 of 5 Sonnet rooms, against 7 of 14 paid runs | Yes |
| The trainer's notes put together by code | baseline better in 9 pairs of 15, code in 1; coaching -0.6, voice -0.8 | No |
| No trainer; length fitted by segment | 9 percent less at MEDIUM, quality level over 15 pairs; the host's thinking ran away once | No |
| The same, the host at LOW | 24 percent less, but it offered kneeling and sitting back on the heels under a delicate knee | No |
| The host at LOW alone | no thinking, judged level at five pairs, but 9 percent off plan against 6 | No |

All kept: $0.17 to $0.22 a script on three requests, against $0.21 to $0.27 for the same three before.

Found along the way:
- OpenRouter doesn't hold `max_uses` on Gemini's search (three searches with a cap of one), nor the host's
  4,000-token thinking budget (18,500 and 27,000 in 2 of 15 runs, 9 and 12.5 cents for the host).
- Fixed: the trainer lost the menu's entries when the `movements:` line named movements by name; the host named
  the weekday against a never-bring-up list it was never shown; a check-in limit the same as a health.md row was
  listed twice; the bench's model client failed on a second turn ("Event loop is closed"); the bench asked for
  Coach Freya, who isn't on the site.


### 0.78.1 (2026-11-10): where the tokens go, Gemini and Opus

Two 15-minute runs on Gemini 3.8 Flash and two on Opus 5.5 through OpenRouter, for the invented listener Jo, every
request recorded (the run files were removed in 0.92.0; the figures are kept here).
All four priced and linted clean. Writing cost $0.17 and $0.21 on Gemini, $2.12 and $2.09 on Opus. On Gemini the
agent's own requests sent three quarters of the input tokens.

### 0.70.1 (2026-11-08): a set's go before its reps, the reminder once

Three runs of the 10-minute workout, priced 3/3. Every skeleton was clean at once and every set read
`[count 3 go] [reps N]`; the lint found no set out of shape in the final scripts. The right arm or shoulder came up
three or four times after the opening (setting up a one-arm press, rolling over, the close), where 0.70.0's runs
named it eight to ten. Median time to the price 187 s (120, 270, 187): one host call took its full 150 s and was
asked again at LOW, the slow tail 0.58.0 found, not the change.

### 0.70.0 (2026-11-08): safety said once, in the coach's words

The same 10-minute request against 0.69.1's baseline (the table below), three runs, from the brief to the price.
The trainer's `SAY EXACTLY:` lines and the review's word-for-word checklist went, the safety guide shrank from
thirteen rules to eight, and the build's wording checks stop only what would send the listener somewhere unsafe.

| | 0.69.1 | 0.70.0 |
|---|---|---|
| Median s (runs) | 218 (293, 218, 158) | 129 (129, 134, 108) |
| Review passes, median | 3 | 1 (1, 2, 1) |
| Fixes after the room, median | 1 | 0 (0, 0, 0) |
| Rooms whose first check failed "off the menu" | 3 of 3 | 1 of 3 (a knee hug off the menu: caught) |
| Final scripts within 4 percent of plan | 3 of 3 | 3 of 3 |

Two batches on the way there found the rest of the false stops, each now a warning or read past: the resting
side's care in other words ("down to the floor without loading that right arm", "notice how that right shoulder
feels", "the other arm rests limp"), "pin both shoulder blades", and "right there". A shortened name that is
another movement ("floor presses" for the single-arm floor press, which loads both shoulders) still stops the
build; the host is told to say the label's full name the first time in a segment.

### 0.69.1 (2026-11-08): the host and trainer at LOW

The 10-minute request, three runs a configuration, from the brief to the price, about $3.60 in all. The rule, set
before the runs: kept only if the median drops at least 25 percent and every run holds quality. None did, so
`LEVEL` stays as it was.

| Configuration | Median s (runs) | Runs clean | Kept? |
|---|---|---|---|
| As it is (trainer and host at MEDIUM) | 218 (293, 218, 158) | | |
| The host at LOW | 91 (91, 82, 98) | 1 of 3 | No |
| The trainer at LOW | 86 (86, 237, 67) | 1 of 3 | No |
| Both at LOW | 67 (64, 67, 91) | 1 of 3 | No |

Every run was priced, every final script within 4 percent of plan, and no setting took more review passes than the
baseline's three. What failed, read in the scripts:
- **The host at LOW:** story details stretched past the notes (a weekday the notes don't give, a number pinned to
  one thing the notes spread over several); in another run every rep set's cues sat in paragraphs after `[reps]`, so the lint
  never timed them, and the coach talked through about 7 s of a 27-second set.
- **The trainer at LOW:** a warm-up knee hug, screened off today's menu and pulling with the off-limits arm, which the
  menu gate missed ("hug your knees"); the per-movement knee stop sign dropped; story claims widened (a record
  "in American history" where the notes said within one team). In one run it put labels before its `SAY EXACTLY:`
  marks, so `writers.SAY` caught two of nine and the review's checklist missed the rest; the host said them anyway.
  It kept the self-check a limit adds every time, but dropped the off-limits pain split in all three both-LOW runs.
- **Both at LOW:** a set cued "fingertips behind ears" under an off-limits shoulder, time calls that missed their
  marks ("halfway" at 13 s of 60), small claims past the notes.
- **The baseline isn't clean either:** one run in three left out seven must-say lines. Every room's first lint, in
  every configuration, failed on "off the menu" as well as the total.

Found along the way, not yet fixed:
- The lint times a set's cues only in the `[reps]` marker's own paragraph; cues in the next paragraphs go untimed.
- `summarize.py`'s story check reads only the researcher's notes, not the top-up's, so a top-up story's names show
  as not in the notes.

### 0.59.0 (2026-11-03): the host's length, stories from nowhere, the knowledge files

0.58.0 itself (a worktree of the tag) against this release's code, three runs each, from the brief to the price.

| | 0.58.0 | 0.59.0 |
|---|---|---|
| 15 minutes, median s (runs) | 149 (146, 149, 185) | 130 (123, 130, 248) |
| Fixes after the room, median | 2 | 0 (0, 0, 0) |
| Must-say lines kept | 51 of 54 | 41 of 41 |
| Host's script at the review, against plan | 17 to 24 percent long | 0.5 percent short to 11 percent long |
| A story rest, host's words against asked | 1.23 (its coaching 1.65) | 1.06 (its coaching 1.00) |
| 30 minutes, median s (before the stop-sign, label, host-wording and short-rest fixes) | 252 (250, 252, 278) | 172 (142, 172, 222) |

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
