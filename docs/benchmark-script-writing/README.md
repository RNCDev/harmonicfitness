# Script-writing benchmarks: findings

**The question:** what does the website's harness spend to write one workout, where does that spend go, and what
can be cut without the listener hearing a worse workout?

**The data:** [20261110/](20261110/README.md), four 15-minute runs on engine 0.78.1, each recorded request by request:
- two on Gemini 3.8 Flash, the site's default;
- two on Claude Opus 5.5, through OpenRouter.

All four were for Jo, an invented listener (`docs/demos/listeners/jo/`), and all four were compliant. Each figure
below cites the run files it comes from. With two runs per model, read the ranges as the spread seen, not as
averages.

## In short

- **Gemini writes a 15-minute workout for 17¢ to 21¢; Opus costs $2.09 to $2.12.**
  - The voice adds 12¢ to 14¢ either way. Coach Freya is a Gemini voice.
  - Gemini also took a third of the time: 2 to 2.5 minutes from request to price, against 6 to 7 for Opus.
- **On Gemini, the agent loop costs as much as the four writers together.**
  - The agent sends the request that opens the turn, runs the brief, lays out the skeleton, and replies once the
    price is in.
  - Its six requests sent three quarters of all input tokens. Most of that was the same text sent again: its
    instructions and the conversation so far, every time.
- **On Opus, the spend is spread across the steps.** In order of size:
  - the researcher's web pages: 83,000 to 90,000 tokens of input a run;
  - thinking: 54% to 57% of output tokens;
  - the agent's re-sent prefix, with no caching.
- **Quality held in all four.** One slip that no check catches: Opus run 2 named the weekday in its opening, against
  the listener's "never bring up".
- **Pricing:** the per-minute spend is about half what was assumed when the credit price was sketched, so 6¢ a minute
  leaves a wide margin. Google's rates double on 1 January 2027, and the cuts below matter most from then on.

## What one workout costs

Costs are list prices checked on 2026-11-10:
- **Gemini 3.8 Flash**, on Google's price list: $0.75 per million input tokens, $0.075 per million cached, $3.75 per
  million output (thinking included), and $14 per 1,000 searches. The first 5,000 searches a month are free. Input
  and output double on 2027-01-01.
- **Opus 5.5**, on OpenRouter's list: $4 per million input tokens, $0.20 per million cached, $20 per million output,
  and $0.01 per search.

| Per 15-minute workout | Gemini | Opus |
|---|---|---|
| Writing | 17¢ to 21¢ (1.1¢ to 1.4¢ a minute) | $2.09 to $2.12 (14¢ a minute) |
| Voice (Gemini TTS, 8,900 to 10,600 characters) | 12¢ to 13¢ | 12¢ to 14¢ |
| **Spend** | **29¢ to 34¢ (about 2¢ to 2.3¢ a minute)** | **about $2.25** |
| Writing at 2027 rates | about 34¢ to 42¢ | unchanged |
| Requests / input tokens / output tokens | 12 / 209,000 / 15,000 to 19,000 | 9 to 10 / 283,000 to 335,000 / 37,000 to 44,000 |

Not included in these figures:
- hosting, a fixed monthly cost not in the repo;
- check-in questions (the agent asked none in these runs);
- re-records and failed runs;
- longer sessions;
- any change to the voice price. Only the writing rates are known to double.

## Findings

### 1. The agent re-sends everything, every request (Gemini: the largest line)

Each agent request carries:
- the same 43,831 characters of instructions: the preamble, the workout skill, `script.md` up to its craft section,
  and `tts-rules.md`;
- the whole conversation so far.

On Gemini the size sent per request grew 59k, 134k, 184k, 235k, then 294k and 341k characters, about 155,000 input
tokens across six requests (`gemini-*/requests.jsonl`, rows marked `agent`). The four writers' six calls sent 54,000.

Two of those six requests do almost nothing:
- Request 2 sends 24,400 tokens and gets back a single tool call, 47 to 50 output tokens. It costs 1.8¢.
- The two requests after the price (`priced`) send 31,000 tokens each to write the closing reply: 2.8¢. The page
  already shows the plan and the price on its own card (`web/README.md`, "Recording costs money"), so the model is
  re-reading the whole session to say a line or two.

On Opus the same pattern costs more:
- The opening request is $0.10.
- The closing reply after the price is $0.18 to $0.20 (45,000 to 50,000 tokens in, 124 to 140 out).
- The agent's fix after the room, in opus-1, was $0.24.

### 2. Caching happens on Gemini by itself, and never on Opus

Nothing in the harness asks for caching.
- **Gemini** read 32% to 42% of input from cache on its own. The hits land only on a request sent seconds after a
  near-identical one, such as requests 4, 10 and 12. Request 11, the first after the room's minute and a half, missed
  every time. So the reply after the room paid full price for its 31,000 tokens.
- **Opus** read 0% (opus-1) and 3% (opus-2).
  - In opus-1 about 60% of the agent's input repeated the request before it, and each review round after the first
    re-sent the round before.
  - Marking the instructions and the history for caching would save about $0.30 to $0.40 a run, net of writing the
    cache once.

### 3. On Opus, the researcher's pages are the largest single cost

The researcher's 4 to 10 searches come back as page text: 83,000 to 90,000 input tokens and $0.46 to $0.50 a run.
On opus-2 the top-up searched six more times, for another $0.28. The search fees themselves are small ($0.05 to
$0.10); the cost is the pages.

Gemini's researcher sent 4,400 input tokens a run with its search on. The pages weren't counted as input, which is
Google's stated rule for grounding on its Cloud price list. That the same holds for an API key is a reading, not
checked.

Gemini's research and top-up came to 2.9¢ to 4.1¢ a workout.

### 4. Thinking is a fifth to a quarter of Opus's bill

Thinking was 19,600 to 25,200 tokens a run: $0.39 to $0.50, or 19% to 24% of the cost.
- The host alone thought for 7,300 to 14,100 tokens and took 140 to 230 seconds.
- The harness sets thinking levels only for Gemini (`writers._thinking`, `agent.thinking_level`), so Opus runs at
  OpenRouter's default for every step, the review included.
- On Gemini, thinking was 1.5¢ to 2.8¢ a run, nearly all of it in the trainer and the host.

### 5. Review rounds: cheap on Gemini, costly on Opus

- **Gemini:** both runs failed the first full lint as "total too long" (see finding 6), and both passed on the second
  round. The second round was cheap: 0.4¢ to 0.5¢, mostly from cache.
- **Opus:**
  - Each review round cost $0.09 to $0.19.
  - opus-1 used all three rounds and still left the total too long. The agent then fixed it itself for $0.24.
  - Review and fix together came to $0.63, 30% of that run.

Each round's draft is kept in `drafts/`, numbered by engine command, beside its lint in `commands.jsonl`.

### 6. Gemini's host writes long

The host's words against the words it was asked for, median by kind of segment:

| Kind of segment | Gemini | Opus |
|---|---|---|
| First set | 1.50 | 1.24 |
| Later set | 1.23 | 0.92 |
| Rest with a story | 1.53 | 1.14 |

This is why every Gemini review starts by cutting. On Gemini it costs time (about 20 seconds a round) more than
money. On Opus a round costs as much as a writer.

### 7. Opus counts the same text as half as many tokens again

The same opening request, 59,000 characters, is 15,884 tokens to Gemini and 24,117 to Opus. Every per-token price
comparison between the two understates Opus's cost by that factor before its higher rates apply.

### 8. Opus runs slowly enough to matter

From request to price took 373 and 426 seconds, with the host up to 230 seconds on a single call.
- The harness retries at a lower thinking level only on Gemini, so an Opus call that runs long has no fallback.
- A turn's cap is 900 seconds (`TURN_SECONDS`), so a 30-minute session on Opus would come close to it. This
  bench didn't measure that.

### 9. Quality

All four were compliant:
- priced, with a clean final lint (the read-aloud rules, the menu gate, the total within five percent);
- the made-by-AI line, the stop rule and "left knee" in every opening;
- no greeting or goodbye mid-session;
- no story fact outside the researcher's notes. `summarize.py` flags names from top-up stories, since it reads only
  the first notes; every flagged name is in the notes.

The one slip, opus-2's "Tuesday", is a gap in the checks: nothing reads a listener's "Never bring up" against the
script.

## Where to cut, ranked

Savings are per 15-minute workout, estimated from the runs above. Each should be measured on the bench before it's
kept, by the rules in `web/bench/README.md`.

| # | Change | Gemini saves | Opus saves | Risk to what the listener hears |
|---|---|---|---|---|
| 1 | **End the turn without a model request once the price is in.** The page already shows the plan and price; any line the coach adds can be a template. | 2.8¢ (about 15%) | $0.18 to $0.20 | None: no words of the workout change |
| 2 | **Code runs the fixed steps after the check-in.** Brief, skeleton lint, room, price. The model writes only the skeleton, from a lean prompt (the brief and the draft format, not the whole skill), and the full draft never enters its history. Includes #1. | 4¢ to 6¢ | $0.35 to $0.60 | Low: the same writers write the same words; the skeleton's design is the step to watch |
| 3 | **Research once a day per topic, shared by every listener who follows it.** A per-listener pass then only picks and frames. | 3¢ to 4¢ | $0.50 to $0.75 | Medium: keep the pick personal; time-proofing and repeats (`told.jsonl`) stay per listener |
| 4 | **Explicit prompt caching** on the agent's instructions and history and on the review's rounds. | 2¢ to 3¢ (the misses after the room) | $0.30 to $0.40 | None |
| 5 | **Set Opus's reasoning effort per step**, as Gemini's levels are set: low for the review, the researcher and the agent's glue; the host kept higher. | none | $0.20 to $0.25 if thinking halves | Medium: the host's stories and the trainer's self-check are where Gemini's lower levels failed before (`web/bench/README.md`, 0.69.1) |
| 6 | **Hold the host to its word budget** (asked-for words, a firmer instruction, or a trim in code before the review), so the review passes in one round. | under 1¢, about 20 s | $0.10 to $0.40 | Low, if the trim keeps the cues and sides |
| 7 | **Trim the agent's prompt in three-writer mode**: the voice rules and craft it never writes with. Smaller once #2 is in. | about 1.5¢ | about $0.09 | Low |
| 8 | **Mix models: Opus only for the host**, Gemini for the rest. | n/a | brings Opus's writing to about 45¢ to 65¢ | The premium tier's recipe: the host is where a stronger model is heard |

With #1, #2 and #4, Gemini's writing would be about 12¢ to 16¢ for 15 minutes; with #3 as well, about 9¢ to 12¢.
With #1, #2 and #4 at 2027 rates it would be 24¢ to 32¢, not far above today's 17¢ to 21¢ without them.

## What it means for the credit price

These figures assume six cents a minute, sold in $10 packs. A card payment costs 2.9% plus 30¢, so a $10 pack
keeps about 94% of its price. Hosting is left out, so treat the margins as before hosting.

| 15-minute workout | Spend | Sold at 90¢ (85¢ after card fees) |
|---|---|---|
| Gemini today | 29¢ to 34¢ | 2.5 to 2.9 times spend |
| Gemini at 2027 rates | 46¢ to 56¢ | 52% to 85% over spend |
| Gemini at 2027 rates, with cuts #1 to #4 | 36¢ to 46¢ | 85% to 136% over spend |
| Opus, as it is | about $2.25 | a loss |
| Opus on the host only (#8) | about 55¢ to 77¢ | 10% to 55% over spend: a premium rate is needed |

A 20% margin after the 2027 increase is reached at about 4¢ to 4.8¢ a minute without the cuts, or about 3¢ to 4¢
with them. That margin is still before hosting and failed runs. Measure both before setting a price.

## Not yet measured

- **Longer sessions:** 30 minutes, where the agent's history and the host's call are both longer.
- **A check-in with questions:** each answer is another turn, and another full re-send.
- **Re-records and failed runs,** which the site already counts in its records.
- **Hosting per workout,** from the Fly bill and the number of workouts a month.
- **Gemini's explicit cache,** which has storage charges and minimum sizes, against the implicit hits it already
  gets.
- **More than two runs a model:** Gemini's thinking time is known to swing widely (`web/bench/README.md`).

## Running another

The bench and its options are in `web/bench/README.md`. A run for an invented listener, with every request
recorded:

```sh
HARMONICFITNESS_HOME=docs/demos/listeners/jo HARMONICFITNESS_KEYS=me/.env \
  .venv/bin/python web/bench/run_one.py .bench/out/<label>/<n> 15 --base <a copy of that folder> \
  --line "Hey, coach Freya, I'd like a {minutes}-minute strength workout in a hotel room, right now. Go easy on my left knee today." \
  [--provider openrouter --model anthropic/claude-opus-5.5]
.venv/bin/python web/bench/tokens.py .bench/out/<label>/*
```

Put each new set in a dated folder beside `20261110/`, with this computer's paths scrubbed and nothing from `me/`.
