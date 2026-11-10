# Leaner Script Writing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write each workout with fewer tokens, fewer requests and fewer failed turns, with the listener hearing the same
script or a better one.

**Architecture:**
- Most of the saving is in the agent loop. Code, not a model request, does what is fixed: it logs the session from
  fields given with the skeleton, closes the turn once the price is in, and adds a go the skeleton left out.
- The writers' room gets narrower fixes: the host is asked for words in proportion to how long it writes, Gemini
  through OpenRouter thinks at levels measured to match Gemini direct, and a failed research call no longer fails the
  turn.
- Prompt caching goes on for the Claude providers.
- Every change is kept only if a bench gate shows the output held.

**Tech Stack:** Python 3.11, pydantic-ai (`Agent.iter`, `FunctionModel` in tests), the web bench (`web/bench/`).

**Spec:** [20261110/README.md](20261110/README.md) and the findings in [README.md](README.md). Read both before Task 1.
The cut numbers below (#1 and so on) are the ranked cuts in that README.

## Global Constraints

- **Same or better output only.** Each task's gate must pass in every run before the task is kept:
  - priced, with the final lint at exit 0;
  - `summarize.py`'s opening, story-notes and one-voice checks empty;
  - the new never-bring-up check empty;
  - review rounds no more than the baseline's median.

  A change that makes cost or time worse while holding quality is reverted.
- **Bench rules,** from `web/bench/README.md`, "Deciding what to keep":
  - three runs a configuration;
  - a time difference under about 25% is noise;
  - a change that removes fixed work is kept on reasoning when every run is clean and the step log shows the step
    gone.
- **Who the bench runs for:** Jo, the invented listener (`docs/demos/listeners/jo`), with
  `HARMONICFITNESS_KEYS=$PWD/me/.env`. Nothing from `me/` goes into `docs/`. Copied runs have this computer's paths
  scrubbed.
- **The request sentence** for every gate run: `Hey, coach Freya, I'd like a {minutes}-minute strength workout in a
  hotel room, right now. Go easy on my left knee today.`
- **The safety gate stays as it is:** the screen, the menu gate and the build's lint keep their checks. Nothing here
  loosens a lint rule.
- **Three-writer mode only.** Changes apply where `deps.writers == "three"`. One-writer turns behave exactly as now.
- **Tests run on every task:** `./harmonicfitness test web` and `./harmonicfitness test changed` pass after each one.
- **Commits:** one per task, a descriptive sentence in the repo's style, ending
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Release (version, changelog, tag) only when the
  maintainer says.

## Review Focus

1. **Record without asking is on.** A clean price records in the same turn (`agent.run`, the `auto_record` branch).
   Closing the turn at the price must never skip that recording. Test in Task 3.
2. **A scheduled turn priced over its ceiling.** The offer stays and the turn closes with the longer-than-planned line,
   not the ready line. Test in Task 3.
3. **The next turn after a turn closed by code** ("make it shorter", or the Record button's turn). The saved history
   must load, and the model must see the price and the closing line. Test in Task 3.
4. **A skeleton set that already has its go, a `[count 5 go]`, or `[reps N]` in a segment that isn't a set.** The
   normalizer must change none of them. Test in Task 4.
5. **The researcher fails, twice.** The room goes on with coaching in every place, the script still lints clean, and
   the turn doesn't fail. Test in Task 7.

---

## Phase 0: the gate

### Task 1: The bench can judge "same or better"

**Files:**
- Modify: `web/bench/batch.sh` (BASE per home, so Jo's copy and `me/`'s copy never share a folder)
- Modify: `web/bench/summarize.py` (`fidelity` reads the top-up's notes too, so `not_in_notes` stops flagging its names; new `never_said` check)
- Create: `web/bench/compare.py`
- Modify: `web/bench/README.md` (the gate, in "Deciding what to keep")
- Test: `web/webtests/test_bench.py` (new)

**Interfaces:**
- Produces: `summarize.never_said(draft: str, content_md: str) -> list[str]`. It returns the weekday, month, season
  and weather words the script says when the listener's `## Never bring up` section names the day, the date, the
  season or the weather.
- Produces: `compare.py <baseline-label> <candidate-label>`, which prints a table per label:
  - medians of writing cost (`tokens.cost`), requests, input tokens and seconds from brief to price;
  - the count of runs failing any quality check;
  - a last line, `GATE: pass` or `GATE: fail (<reasons>)`.

- [ ] **Step 1: Write the failing tests**

```python
class NeverSaid(unittest.TestCase):
    def test_a_weekday_is_flagged_when_the_day_is_never_brought_up(self):
        content = "## Never bring up\n- News, politics, today's date, the day of the week, the season or the weather\n"
        self.assertEqual(summarize.never_said("@@ 50 | Welcome\nTuesday, fifteen minutes.\n", content), ["Tuesday"])
    def test_nothing_is_flagged_when_the_listener_allows_it(self):
        self.assertEqual(summarize.never_said("@@ 50 | Welcome\nTuesday, fifteen minutes.\n", "## Never bring up\n- Politics\n"), [])

class NotInNotes(unittest.TestCase):
    def test_a_top_up_storys_names_count_as_noted(self):
        writers = [{"who": "research", "prompt": "", "output": {"stories": [{"text": "Miles Davis at Thirtieth Street"}]}},
                   {"who": "top-up", "prompt": "", "output": {"stories": [{"text": "Margaret Hamilton wrote the code"}]}}]
        draft = "@@ 60 | Welcome\n@@ 60 | Rest\n[story] Margaret Hamilton led the software team. [/story]\n@@ 60 | Close\n"
        unknown, _ = summarize.fidelity({"draft": draft, "writers": writers})
        self.assertEqual(unknown, [])

class Gate(unittest.TestCase):
    def test_gate_fails_when_any_candidate_run_is_not_compliant(self):
        self.assertIn("GATE: fail", compare.gate(baseline_rows, [ok_row, {**ok_row, "lint_clean": False}]))
```

- [ ] **Step 2: Run the tests to make sure they fail**

Run: `.venv/bin/python -m unittest web.webtests.test_bench -v`
Expected: FAIL (`never_said` and `compare` aren't defined)

- [ ] **Step 3: Implement**
  - In `batch.sh`, set `BASE="$REPO/.bench/base-$(basename "$HOME_DIR")"` and keep the per-day `.prepared-$today`
    marker. Exclude `coaches/` from the rsync as well.
  - `never_said` reads the `## Never bring up` section of `content.md` and the script's words outside `@@` lines.
  - `compare.gate` returns `"GATE: pass"` only when every candidate run is compliant and its median writing cost is
    no higher than the baseline's.

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `.venv/bin/python -m unittest web.webtests.test_bench -v` then `./harmonicfitness test web`
Expected: PASS

- [ ] **Step 5: Record the baseline**

Run:

```sh
HARMONICFITNESS_HOME=docs/demos/listeners/jo HARMONICFITNESS_KEYS=$PWD/me/.env web/bench/batch.sh base 15 3 --line "$LINE"
```

Expected: three priced runs in `.bench/out/base/`. This is the label every later gate compares against. It costs
about 60¢.

- [ ] **Step 6: Commit**

---

## Phase 1: the agent loop (Gemini's largest line)

### Task 2: The skeleton carries what the session log needs

Gemini never sent `log-session` in the same reply as the skeleton, as the instructions ask. It spent a request on it
after the room every time (`gemini-*/result.json`, history message 9). With the log's fields carried on the skeleton's
write, code can log the session and Task 3 can close the turn.

**Files:**
- Modify: `web/webapp/agent/tools.py` (a `LogFields` model and `log_argv`)
- Modify: `web/webapp/agent/__init__.py` (`write_file` and `edit_segments` take `log`)
- Modify: `web/webapp/agent/instructions.md` (the three-writer block: pass `log` with the skeleton, in place of the
  separate `log-session`)
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Produces:
  ```python
  class LogFields(BaseModel):
      format: str   # the session method, as log-session's --format takes it
      topics: str   # the content plan's topics
      loads: str    # '<movement> = <load and tempo>; ...'
  ```
- Produces: `tools.log_argv(path: str, coach: str, fields: LogFields) -> list[str]`, which returns
  `["log-session", "--draft", path, "--coach", coach, "--format", ..., "--topics", ..., "--loads", ...]`.
- Produces: `write_file(..., log: tools.LogFields | None = None)` and the same argument on `edit_segments`. A
  skeleton written with `log` in three-writer mode sets `deps.pending_log = tools.log_argv(...)`.

- [ ] **Step 1: Write the failing tests**
  - `test_a_skeleton_written_with_log_fields_keeps_the_log`: after `write_file` of a skeleton with
    `log=LogFields(format="circuit", topics="Jazz", loads="push-up = bodyweight")`, `deps.pending_log` equals
    `log_argv(path, "Coach Freya", fields)`, and the offer the price makes carries `"log"`.
  - `test_without_log_fields_nothing_changes`: `deps.pending_log` stays None.

- [ ] **Step 2: Run them to make sure they fail.** `./harmonicfitness test web`. Expected: FAIL (an unexpected
  keyword `log`).
- [ ] **Step 3: Implement.** `log_argv` quotes nothing, since the engine takes the values as given. The write's result
  line says "The session's log is kept: the site logs it once the recording is made", so the agent sends no
  `log-session`.
- [ ] **Step 4: Run the tests to make sure they pass.** `./harmonicfitness test web`. Expected: PASS.
- [ ] **Step 5: Commit**

### Task 3: The turn closes at the price, without a model request

The two requests after the price cost 2.8¢ on Gemini (`priced`, 31,000 input tokens each) and $0.18 to $0.20 on Opus,
only to say the script is ready. The page already shows the plan and the price on the Record card. Cut #1.

**Files:**
- Modify: `web/webapp/agent/__init__.py` (`run_turn` runs with `AGENT.iter` and stops on `closed(deps)`; new
  `closing_reply`)
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Consumes: `deps.offer` and `deps.pending_log` (Task 2), `deps.ceiling`, `deps.recorded`.
- Produces: `closed(deps: Deps) -> bool`. It is true when all of these hold:
  - `deps.phase == "priced"`;
  - `deps.offer` is set and `deps.recorded` isn't, so no recording ran this turn;
  - `deps.offer` has `"log"` or `deps.logged == deps.offer["draft"]`.
- Produces: `closing_reply(deps: Deps) -> str`, exact copy:
  - `"Your script is written and checked. Press Record when you're ready."`
  - when `deps.ceiling` is set and `deps.offer["chars"] > deps.ceiling`: `"Your script is written and checked, but it came out longer than planned, so it waits for your Record."`
- Produces: the saved history ends with `ModelResponse(parts=[TextPart(closing_reply(deps))])`, so the next turn reads
  it as the coach's own line.

- [ ] **Step 1: Write the failing tests**, each with a `FunctionModel` whose next request after the price fails the
  test if it's made:
  - `test_a_clean_price_closes_the_turn_without_another_request`: the script writes the skeleton with `log`, then the
    priced build. The reply is `closing_reply(deps)`, and `usage["requests"]` equals the requests made up to and
    including the one that called the build.
  - `test_record_without_asking_records_before_the_turn_closes` (Review Focus 1): with `auto_record` on, the build
    records, `closed()` is false, and the model writes the reply as now.
  - `test_a_scheduled_price_over_the_ceiling_says_it_waits` (Review Focus 2).
  - `test_the_next_turn_reads_a_closed_turns_history` (Review Focus 3): a second `run_turn` on the saved
    `history_json` runs, and its first request's messages hold the price result and the closing line.
  - `test_without_a_kept_log_the_model_closes_as_now`: no `"log"` on the offer, so `closed()` is false.
- [ ] **Step 2: Run them to make sure they fail.** `./harmonicfitness test web`. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - `run_turn` keeps its cancellation and clock, and swaps `AGENT.run_sync` for an `AGENT.iter` run under
    `asyncio.run`.
  - Before each `ModelRequestNode`, it checks `closed(deps)`; when that holds, it stops iterating and builds the
    `TurnOutcome` from the run's messages plus the closing `ModelResponse`.
  - Usage comes from the run's usage, as now.
- [ ] **Step 4: Run the tests to make sure they pass.** `./harmonicfitness test web`. Expected: PASS.
- [ ] **Step 5: Gate (Tasks 2 and 3 together).** Run `batch.sh close 15 3 --line "$LINE"`, then
  `compare.py base close`. Expected:
  - `GATE: pass`;
  - median requests down by 2 on Gemini;
  - every run's `offer` carries `"log"`.
- [ ] **Step 6: Commit**

### Task 4: Code adds the go a skeleton set left out

Both Gemini runs' first skeleton lint failed only for `[reps N]` with no go before it, eight to eleven times. The
agent re-sent the whole conversation to fix it. The lint names the fix: `[count 3 go] [reps 10]`.

**Files:**
- Modify: `web/webapp/agent/tools.py` (new `add_missing_go`, called by `write_file` and `edit_segments` for a
  skeleton in three-writer mode)
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Produces: `tools.add_missing_go(skeleton: str) -> tuple[str, int]`: the skeleton with `[count 3 go] ` put before
  each `[reps N]` whose segment has no `go` marker before it, and how many were added. The write's result says
  "Added the go before N sets' reps".

- [ ] **Step 1: Write the failing tests**
  - `test_a_bare_reps_gets_its_go`: `"@@ 45 | Push-up set 1, 10 reps\n[reps 10]\n"` comes back as
    `("@@ 45 | Push-up set 1, 10 reps\n[count 3 go] [reps 10]\n", 1)`.
  - `test_a_set_with_its_go_is_left_alone` (Review Focus 4): `[count 3 go] [reps 10]` and `[count 5 go] [reps 8]`
    come back unchanged, with 0 added.
  - `test_a_full_draft_is_never_touched`: a draft with words isn't normalized, so the lint still reports it.
- [ ] **Step 2: Run them to make sure they fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** Use `writers.split` for the segments and `tools.MARK` to read the markers in order. Only
  `is_skeleton(content)` drafts are changed.
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Gate.** `batch.sh go 15 3`, then `compare.py close go`. Expected: `GATE: pass`, and no run's first
  skeleton lint failing on "has no go before it".
- [ ] **Step 6: Commit**

### Task 5: The agent reads only the guides it writes with

In three-writer mode the agent writes only the skeleton, but every request carries all of `tts-rules.md`: Characters,
Numbers and abbreviations, Local and web voices, Words that trip a voice. Cut #7.

**Files:**
- Modify: `web/webapp/agent/__init__.py` (`skill_text`: with `writers == "three"`, `knowledge/tts-rules.md` keeps only
  its `## The draft` and `## Markers` sections)
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Consumes: `writers.sections(text) -> dict[str, str]`.

- [ ] **Step 1: Write the failing test.** `test_three_writer_turns_carry_only_the_drafts_guides`: `skill_text(root,
  writers="three")` holds `"## The draft"` and `"## Markers"`, and doesn't hold `"## Words that trip a voice"` or
  `"## Characters"`. `skill_text(root, writers="one")` still holds all of them.
- [ ] **Step 2: Run it to make sure it fails.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Gate.** `batch.sh guides 15 3`, then `compare.py go guides`. Expected:
  - `GATE: pass`;
  - the agent's `instructions_chars` (in `requests.jsonl`) down by the trimmed sections' length;
  - no skeleton round more than in `go`.
- [ ] **Step 6: Commit**

---

## Phase 2: the room

### Task 6: The host is asked for words in proportion to how long it writes

Words written against words asked, median by kind of segment:

| | Gemini | Opus |
|---|---|---|
| First set | 1.50 | 1.24 |
| Rest with a story | 1.53 | 1.14 |

Each Gemini review's first round only cuts length, and opus-1 needed three rounds and an agent fix ($0.63).

**Files:**
- Modify: `web/webapp/agent/writers.py` (`COACH_AIM` becomes `AIMS`, by model family; `asked()` takes the model)
- Test: `web/webtests/test_writers.py` (or the existing writers tests in `test_agent.py`)

**Interfaces:**
- Produces: `AIMS: dict[str, float] = {"gemini": <from the bench>, "other": 0.85}`.
- Produces: `aim(model) -> float`: `AIMS["gemini"]` when `is_gemini(model)`, else `AIMS["other"]`.
- Produces: `asked(n, body, budget, model) -> int`. Every caller passes the turn's model.

- [ ] **Step 1: Write the failing test.** `test_the_host_is_asked_less_on_gemini`: with `AIMS["gemini"] = 0.6`,
  `asked(3, ["text"], {3: 100}, gemini_model) == 60`; a `[hold]` segment still asks the full 100.
- [ ] **Step 2: Run it to make sure it fails.** Expected: FAIL.
- [ ] **Step 3: Implement.** Set `AIMS["gemini"] = 0.6` as the starting value, which is 0.85 divided by Gemini's
  pooled ratio of about 1.4.
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Gate.** `batch.sh aim 15 3`, then `compare.py guides aim`. Expected:
  - `GATE: pass`;
  - review rounds median 1;
  - the host's words against the budget between 0.95 and 1.10 (`summarize.py`'s table, against the budget, not the
    ask);
  - no silence warnings in the final lint.

  If the host's ratio is outside that band, set `AIMS["gemini"]` from the measured ratio and run the gate again,
  once.
- [ ] **Step 6: Commit**

### Task 7: A failed research call never fails the turn

The first OpenRouter run failed: both of the researcher's calls came back 504 after Google rate-limited OpenRouter's
upstream (`or-gemini-1`). With no stories, every place still gets coaching, as a failed top-up already does.

**Files:**
- Modify: `web/webapp/agent/writers.py` (`write`'s `the_stories`: a second failure returns `[]` with a log line)
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Consumes: `writers.stories(...)`.
- Produces: no new names. Log line, exact copy: `"research failed twice: every place gets coaching only"`.

- [ ] **Step 1: Write the failing test** (Review Focus 5).
  `test_the_room_writes_coaching_only_when_research_fails_twice`: a model that raises `ModelHTTPError(504)` for the
  researcher's agent and answers for the others. `write()` returns a draft, `placed` is empty, and the host's prompt
  says "No story here" for each place.
- [ ] **Step 2: Run it to make sure it fails.** Expected: FAIL (the error propagates).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Kept on reasoning: it changes only a turn that fails today.

### Task 8: Gemini through OpenRouter thinks as Gemini direct does

At "medium", OpenRouter's Gemini thought for 4,800 to 9,500 tokens on agent requests, where Gemini direct at MEDIUM
reported almost none. Its trainer ran past its 110-second patience (`or-gemini-2`). At "low" it matched Gemini
direct's LOW.

**Files:**
- Modify: `web/webapp/agent/writers.py` (`thinking_settings` maps through `OPENROUTER_EFFORT`)
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Produces: `OPENROUTER_EFFORT: dict[str, str] = {"HIGH": <bench>, "MEDIUM": <bench>, "LOW": "low"}`.
  `thinking_settings` returns `{"openrouter_reasoning": {"effort": OPENROUTER_EFFORT[level]}}`.

- [ ] **Step 1: Calibrate.** One run per mapping, `--provider openrouter`: MEDIUM→`low` and MEDIUM→`medium`, about 20¢
  each. For each step, read `usage.details.reasoning_tokens` and `seconds` in `requests.jsonl` against the Gemini
  direct baseline. Pick the mapping whose trainer and host thinking falls within the direct runs' range (trainer
  2,200 to 5,700, host 1,800 to 1,900), with no call past its patience.
- [ ] **Step 2: Write the failing test.** `test_openrouter_gemini_effort_follows_the_table`: `thinking_settings(gemini,
  "MEDIUM") == {"openrouter_reasoning": {"effort": OPENROUTER_EFFORT["MEDIUM"]}}` for the value Step 1 chose.
- [ ] **Step 3: Implement, then run the tests to make sure they pass.** Expected: PASS.
- [ ] **Step 4: Gate.** `batch.sh or 15 3 --provider openrouter`, then `compare.py base or`. Expected: `GATE: pass`,
  and no "gave up" lines in any run's room log.
- [ ] **Step 5: Commit**

### Task 9: Prompt caching on the Claude providers

Opus read nothing from cache. About 60% of the agent's input repeated the request before it, and each review round
re-sent the last. Cut #4. This applies to the Claude provider and to any Claude model through OpenRouter. Gemini's
implicit caching is left as it is.

**Files:**
- Modify: `web/webapp/providers.py` (new `cache_settings`)
- Modify: `web/webapp/agent/__init__.py` (`Narrated.request` merges it in)
- Modify: `web/webapp/agent/writers.py` (`_ask` merges it in)
- Test: `web/webtests/test_providers.py`

**Interfaces:**
- Produces: `providers.cache_settings(model) -> dict`:
  - `AnthropicModel`: `{"anthropic_cache_instructions": True, "anthropic_cache_messages": True}`;
  - `OpenRouterModel` with a name starting `anthropic/`: `{"openrouter_cache_instructions": True, "openrouter_cache_messages": True}`;
  - anything else: `{}`.

- [ ] **Step 1: Write the failing tests.** One per model class above, asserting the dict exactly.
- [ ] **Step 2: Run them to make sure they fail, implement, then run them to make sure they pass.**
- [ ] **Step 3: Gate.** Two runs with `--provider openrouter --model anthropic/claude-opus-5.5` (about $4). Expected:
  - every run compliant;
  - `cache_read_tokens` above 40% of the agent's input;
  - OpenRouter's own charge down by at least $0.25 a run against opus-1 and opus-2.
- [ ] **Step 4: Commit**

---

## Phase 3: shared research (its own design first)

The largest saving left on Opus is the researcher's pages ($0.46 to $0.74 a run), and on Gemini it is 3¢ to 4¢ a
workout. The proposal: research a topic once a day and read it from a shared store for every listener who follows
that topic. That needs a design before a plan, because it moves listener-derived topics into a store shared across
accounts.

The design has to settle:
- the store and its key (a normalized topic, never a listener's own wording);
- how picking and framing stay per listener (`told.jsonl`, repeats, taste);
- time-proofing;
- what happens when a topic is followed by one listener only.

This is not started here.

## Expected result

| 15 minutes, Gemini | Writing cost | Requests |
|---|---|---|
| 20261110 | 17¢ to 21¢ | 12 |
| After Phase 1 (Tasks 2 to 5) | about 13¢ to 16¢ | 9 to 10 |
| After Phase 2 (Tasks 6 to 8) | about 12¢ to 15¢, one review round | 8 to 9 |

With Task 9, Opus through OpenRouter would cost about $1.40 to $1.60 by the same arithmetic.
