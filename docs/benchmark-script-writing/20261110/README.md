# Script-writing token bench, 2026-11-10

Four 15-minute workouts written by the website's harness as it stands at 0.78.1: two on Gemini 3.8 Flash (Google,
direct) and two on Claude Opus 5.5 (through OpenRouter). Each run went from the request to the price. Every model
request was recorded, so the tables show where the tokens went. Nothing was rendered.

## Setup

- **Listener:** Jo, the invented demo listener from `docs/demos/listeners/jo/` (nobody real). Jo trains in a hotel
  room with a chair and a towel and has a delicate left knee. A copy of Jo's folder was used, so the demo itself is
  unchanged.
- **Request:** "Hey, coach Freya, I'd like a 15-minute strength workout in a hotel room, right now. Go easy on my
  left knee today." Any question the agent asked was answered "Go with your pick." In all four runs the agent asked
  nothing and priced in the first turn.
- **Harness:** the three-writer room (`HARMONICFITNESS_WRITERS=three`), as on the site.
  - **Gemini:** the site's own thinking levels: LOW to MEDIUM for the agent, LOW for the researcher and the review,
    MEDIUM for the trainer and the host.
  - **Opus:** the harness sets no thinking level for any model other than Gemini, so Opus ran at OpenRouter's
    default reasoning. It also has no retry at a lower level when a call runs long.
  - **Both:** the researcher's web search was on.
- **Coach:** Coach Freya, a Gemini voice, in all four runs. The voice price is the same whichever model writes.
- **Runner:** `web/bench/run_one.py`, with `--provider openrouter --model anthropic/claude-opus-5.5` for Opus. The
  tables come from `web/bench/tokens.py` (`tokens.txt` here).

## Compliance: all four pass

| Run | Priced | Final lint | Opening (made-by-AI line, stop rule, "left knee") | Story names outside the notes | Script length |
|---|---|---|---|---|---|
| gemini-1 | yes | exit 0 | all present | none* | 8,881 characters |
| gemini-2 | yes | exit 0 | all present | none* | 9,822 characters |
| opus-1 | yes | exit 0 | all present | none ("Thirtieth" is "30th Street" in words) | 8,968 characters |
| opus-2 | yes | exit 0 | all present | none* | 10,557 characters |

\* `summarize.py` flagged names in three runs. It reads only the researcher's first notes, not the top-up's. Every
flagged name is in one or the other.

- **Final lint:** this check covers the read-aloud rules, the menu gate and the total within five percent.
- **No greetings or goodbyes** mid-session in any run.
- **One slip that still passed:** opus-2's opening names the day ("Tuesday"), although Jo's `content.md` lists the day
  of the week under "Never bring up". No check catches it; only reading the script did.

## Where the money went

Costs are at list prices checked today:
- **Gemini 3.8 Flash**, from Google's price list: $0.75 per million input tokens, $0.075 per million cached, $3.75 per
  million output (thinking included), and $14 per 1,000 searches. The first 5,000 searches a month are free. These
  are introductory prices: input and output double on 1 January 2027.
- **Opus 5.5**, from OpenRouter's list: $4 per million input tokens, $0.20 per million cached, $20 per million output,
  and $0.01 per search. The estimate matches OpenRouter's own reported charge within 2¢ per run.

| Run | Requests | Input tokens | Cached | Output | Of it thinking | Searches | Seconds | Writing cost | Voice cost (Gemini TTS) |
|---|---|---|---|---|---|---|---|---|---|
| gemini-1 | 12 | 209,817 | 87,697 (42%) | 15,142 | 4,010 | 1 | 122 | **$0.17** | $0.12 |
| gemini-2 | 12 | 208,636 | 65,791 (32%) | 18,886 | 7,589 | 2 | 146 | **$0.21** | $0.13 |
| opus-1 | 10 | 334,634 | 0 | 36,502 | 19,579 | 5 | 373 | **$2.12** | $0.12 |
| opus-2 | 9 | 282,919 | 8,748 (3%) | 44,031 | 25,172 | 10 | 426 | **$2.09** | $0.14 |

This corrects an estimate given earlier the same day: about 45¢ for 15 minutes of writing on Gemini, taken from the
bench README's 0.69 runs. Measured here it is 17¢ to 21¢. A 15-minute Gemini workout costs about 30¢ to 35¢ in all.
On Opus the same workout costs about $2.25, which a price of $1 to $1.50 a workout can't carry.

### By step

The agent sends each request; the writers are the room's four roles.

| Step | gemini-1 | gemini-2 | opus-1 | opus-2 |
|---|---|---|---|---|
| Agent: check-in and brief (its first 2 to 3 requests) | $0.036 | $0.051 | $0.320 | $0.316 |
| Agent: skeleton handed to the room ("rests") | $0.006 | $0.005 | (in brief) | (in brief) |
| Room: researcher, with top-up | $0.029 | $0.041 | $0.497 | $0.736 |
| Room: trainer | $0.021 | $0.033 | $0.171 | $0.138 |
| Room: host | $0.028 | $0.028 | $0.292 | $0.446 |
| Room: review (its rounds) | $0.021 (2) | $0.024 (2) | $0.391 (3) | $0.284 (2) |
| Agent: fix after the room | none | none | $0.244 | none |
| Agent: price and reply | $0.028 | $0.028 | $0.204 | $0.184 |
| **Agent's share** | **41%** | **40%** | **36%** | **24%** |

## What the logs show

1. **The agent re-sends its whole conversation on every request.**
   - Every agent request carries the same 43,831 characters of instructions (about 11,000 to 16,000 tokens): the
     preamble, the workout skill and the first part of `script.md`, plus `tts-rules.md`.
   - On top of that comes the conversation so far. Its size per request on Gemini was 59, 134, 184, 235, 294 and 341
     thousand characters, so the agent's six requests sent about 155,000 input tokens.
   - That is three quarters of Gemini's input; the room's twelve calls sent 54,000.
2. **Caching works on Gemini by accident and not at all on Opus.**
   - Gemini read 32% to 42% of input from its cache with nothing in the harness asking for it. That is Gemini's
     implicit caching, which isn't guaranteed.
   - Opus read almost nothing from cache, since nothing marks the prefix for caching.
   - On opus-1 about 60% of the agent's input was a repeat of the request before it. Caching it would save about
     $0.35 a run (about 17%), at the price of writing the cache once.
3. **On Opus, the researcher's web search is the largest line.**
   - Its 4 to 10 searches come back as page text: 83,000 to 90,000 input tokens and $0.46 to $0.50 a run, plus the top-up's
     own searches on opus-2.
   - Gemini's researcher sent only 4,400 input tokens a run with its search on, so the pages it found weren't counted
     as input. Google states this for Search grounding on its Cloud (Vertex) price list; that the same holds for a
     Gemini API key is my reading, not checked.
   - A shared research pass, made once a day for a topic and read by every listener who follows it, would remove most
     of this line.
4. **Thinking is over half of Opus's output.**
   - Of 37,000 to 44,000 output tokens, 20,000 to 25,000 were thinking, and output was a third or more of the bill.
   - The host alone thought for 7,000 to 14,000 tokens and took 140 to 230 seconds.
   - The harness never sets an effort for Opus, so this is the provider's default. Setting one is a direct lever.
5. **Review rounds are paid for in full.**
   - Every review round after the first re-sends the round before it.
   - opus-1's review used all three rounds and still left the total too long. The agent then fixed it itself:
     $0.63, 30% of that run.
   - On Gemini both runs took two rounds. The first round's check failed on length every time, and the second passed.
6. **The Gemini host writes long, so the review has to cut.**

   Words the host wrote against words asked, median by kind of segment:

   | Kind of segment | Gemini | Opus |
   |---|---|---|
   | First set | 1.50 | 1.24 |
   | Later set | 1.23 | 0.92 |
   | Rest with a story | 1.53 | 1.14 |

   Each of Gemini's runs failed its first full lint as "total too long" and needed a second review round to reach five
   percent. A host held to its length would save that round and its re-sent history.
7. **The skeleton costs the agent a second request on Gemini.** Its first skeleton lint failed in both runs, once
   with "off the menu", and the agent re-sent everything to fix it.

## What this suggests, from two runs each

Two runs per model show the spread, not a reliable average.

- **On Gemini, the agent loop is the target.** If code ran the steps after the check-in (brief, skeleton lint, room,
  price) and the agent's history stopped carrying the full draft, roughly 100,000 of the 155,000 agent input tokens
  would go: about two thirds of the agent's 7¢ to 8¢. That would bring writing to about 12¢ to 16¢ for 15 minutes.
- **On Opus**, in order of size:
  - prompt caching for the agent's prefix and the review's rounds;
  - a lower reasoning effort for the review and the researcher;
  - shared research instead of per-listener search.

  Even with all three, Opus would stay near $1 for 15 minutes. It suits a premium tier, or the host's step alone,
  rather than every step.
- **Both:** hold the host to its length, so the review passes in one round.

## Files

One folder per run:

| File | What it holds |
|---|---|
| `requests.jsonl` | One line per model request: who asked (the agent and its phase, or the writer), the messages' size, the instructions' size, the thinking setting, and the provider's usage as it came back (input, cached, output, thinking, searches, OpenRouter's charge) |
| `commands.jsonl` | Every engine command the run ran, with its exit code and output |
| `drafts/` | The draft as each lint read it, numbered by command: the skeleton's lints first, then each round of the room's review, then the agent's own fixes. These are the interim versions |
| `room.jsonl` | Each writer's prompt and what it returned: the researcher's and top-up's notes, the trainer's notes, the host's script, each review's edits |
| `brief.md`, `menu.json` | The brief and safe menu the run wrote |
| `final.draft.txt`, `final-lint.txt` | The final script and its clean lint |
| `result.json` | The whole run: turns, steps, the offer, the agent's message history |
| `summary.json` | The run's one-line result |

Paths on the bench computer appear as `<repo>` and `<bench>`.
