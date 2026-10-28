# Web client, Milestone 3: the agent, through the plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in user with a language-model key types or taps "a 25-minute strength workout", answers the check-in in the panel, and sees the plan table for today's session. An agent loop does the work over the user's own key, calling the engine's commands as typed tools.

**Architecture:** Each user message, or each answer to a question, is a short `turn` job. The worker writes out the user's folder and opens their keys. It builds a Pydantic AI model with the user's own key and no retries, then runs one agent with typed tools: engine commands run through `engine.run` in that folder, plus `ask_user` and `show_plan`. The run stops when the agent asks the user something (a deferred tool call) or finishes. The conversation's history, its chat lines and its open question are stored sealed in Postgres. The next turn resumes from them. The browser shows chat lines in the chat zone and the open question, or the plan, in the panel.

**Tech stack:** as before, plus `pydantic-ai-slim[anthropic,openai,google]==2.56.0` and `anthropic>=1.12,<2` in the `web` extra, used only by the worker. Research behind every API shape here: `docs/research/web-client/m3-pydantic-ai.md` (checked 2026-10-28).

**Spec:** `docs/research/web-client/design.md` ("The agent"; "Jobs and conversations"; "Workflows: Build a workout"; Anti-goals). Built on Milestone 2 (`plan-m2.md`, through `2155fb6`).

## Global constraints

Everything in `plan.md`'s and `plan-m2.md`'s Global constraints holds. In particular:
- The safety guarantees are the engine's and are never weakened: the brief's safe menu, the screen and the red-flag stop. The agent has no shell and no general file access, only the tools named here.
- Keys are opened only in the worker, for a job. A language-model key goes only into that job's model client, never into an environment, a log, a stored history or an event.
- Nothing is retried automatically after it may have reached a paid service. Every SDK client is built with `max_retries=0` (Google: `HttpRetryOptions(attempts=1)`). A turn that fails is marked failed, never requeued.
- **One agent loop serves every provider.** Provider differences live only in `webapp/providers.py`, which builds the model.
- **A provider is offered only after its model passes the eval grid (Milestone 5).** Until then the variable `HARMONICFITNESS_PROVIDERS` (on both services, default `anthropic`) lists the offered ones. The others are built and tested with `FunctionModel`, but hidden.
- Conversations, their history, chat lines, questions, answers and plans are personal: stored sealed with the user's data key, as `jobs.args` are. Plain columns hold only ids, states and timestamps.

## Decisions this plan makes

- **Providers and models** (`webapp/providers.py`; ids from each provider's docs, 2026-10-28): `anthropic`, "Claude", model `claude-sonnet-5-5`; `openai`, "ChatGPT", model `gpt-6.1-sol` (to re-check before Milestone 5); `google`, "Gemini", model `gemini-3.8-flash`. A model key is a `user_keys` row whose `service` is one of these ids. The voice service `gemini` and the model provider `google` stay separate rows, even though Google issues one key for both.
- **Which model a turn uses:** the first offered provider, in the order above, for which the user has a key. A user with no offered key can't start a conversation (409 "Add a key for Claude in Keys first.").
- **A turn is a job** of kind `turn`. The plan's "one job per user at a time" makes a user's turns run in order. Limits per turn: `UsageLimits(request_limit=25, tool_calls_limit=40, total_tokens_limit=400_000)`. Hitting one fails the turn with "this turn ran too long; try again with less to do".
- **Instructions are hand-ported for now.** `webapp/agent/instructions.md` covers steps 1 to 4 of `.claude/skills/workout/SKILL.md`: read enough to ask, check in, brief, design and post the plan. Each skill rule maps to a tool here. Milestone 5 replaces the file with the generator.
- **Scope ends at the plan.** Research, writing, the build, the log and the privacy line are Milestone 4. The agent finishes with the plan shown and one line saying the script and audio come in a later version.
- **Health stays read-only in Milestone 3.** A change for today becomes the brief's `--limit`. A lasting change is noted in chat ("I'll use that for today; saving it to your health notes comes in a later version"), and `health.md` is never written back (`NEVER_WRITE_BACK` already holds).
- **`show_plan` checks every movement against the brief's menu** (`<stem>.menu.json`, through the engine's `catalog.resolve` and `menu.py`). A movement the menu doesn't hold is a tool error the model must fix, so an off-menu plan is never shown.
- **Questions:** `ask_user` takes one to four questions, as the skill's check-in does. Each has `id`, `prompt`, two to six `options` (`label`, optional `description`, one marked `recommended`), `multi: bool`, and `other: bool` (a free-text "Other"). The answer comes back as `{question id: [chosen labels] or "other: <text>"}`. Answering an old or already-answered question is a 409.
- **Dates:** each turn's arguments carry the browser's `today` (YYYY-MM-DD, within a day of the server's date, as the brief job checks) and `now` (a local "YYYY-MM-DD Weekday HH:MM"), which take the place of the skill's `date` command.

## Review focus

1. **The agent plans a movement the menu doesn't hold.** Expected: `show_plan` refuses it with the movement's name, nothing is shown, and the model gets the error to fix. Pinned by `test_show_plan_refuses_off_menu` (Task 5).
2. **A refused, expired or out-of-credit model key.** Expected: the turn fails with "Claude refused the key" (401/403) or "Claude says the account is out of credit or over its limit" (429, or a 400 about billing). The call is made once and never retried, and no message holds the key. Pinned by `test_refused_key_fails_once` (Task 1) and `test_turn_maps_provider_errors` (Task 6).
3. **A runaway loop.** Expected: the turn stops at the usage limit and fails with its message. Nothing is retried and the history isn't saved half-done. Pinned by `test_turn_stops_at_usage_limit` (Task 6).
4. **The answer races the conversation.** The answer is sent twice, or a stale question is answered after a new message. Expected: the second is 409, no job is queued, and the conversation is unchanged. Pinned by `test_answer_twice_is_409` (Task 7).
5. **One user reaches another's conversation by id.** Expected: 404 for read, message and answer alike. Pinned by `test_other_users_conversation_is_404` (Task 7).

---

## File map

```
pyproject.toml, uv.lock                 modify: pydantic-ai-slim, anthropic<2 in `web`
web/webapp/providers.py                 new: the providers, the model factory, error mapping
web/webapp/api.py                       modify: model keys in /api/keys; conversation routes
web/webapp/worker.py                    modify: the `turn` handler (model keys read separately from the engine's voice keys)
web/webapp/migrations/006_conversations.sql
web/webapp/conversations.py             new: sealed conversations: create, load, save turn, answerable
web/webapp/agent/__init__.py            new: the Agent, its tools, run_turn
web/webapp/agent/tools.py               new: the engine tools
web/webapp/agent/instructions.md        new: ported from the workout skill, steps 1–4
web/webtests/test_providers.py, test_conversations.py, test_agent.py, test_agent_tools.py (new); test_api.py, test_jobs.py
web/client/src/api.ts, App.tsx, zones/Chat.tsx, zones/Panel.tsx, zones/Question.tsx (new), zones/PlanTable.tsx (new), zones/KeysBox.tsx, tests
web/README.md, CHANGELOG.md
```

---

### Task 1: Providers and the model factory

**Files:**
- Modify: `pyproject.toml` (`web` extra: `"pydantic-ai-slim[anthropic,openai,google]==2.56.0"`, `"anthropic>=1.12,<2"`), `uv.lock` (`uv lock`, then `uv sync --extra web`, plus `--extra cpu` on a Mac with local voices)
- Create: `web/webapp/providers.py`
- Test: `web/webtests/test_providers.py`

**Interfaces:**
- Produces:
  - `PROVIDERS: dict[str, Provider]`, in order, with `Provider(id: str, name: str, model: str, key_page: str)` frozen. Key pages: `https://console.anthropic.com/settings/keys`, `https://platform.openai.com/api-keys`, `https://aistudio.google.com/apikey`.
  - `offered(env: Mapping[str, str]) -> list[str]`: `HARMONICFITNESS_PROVIDERS` split on commas, stripped, kept in `PROVIDERS` order. Default `["anthropic"]`. An unknown id raises `config.ConfigError` naming it.
  - `model_for(provider: str, key: str) -> pydantic_ai.models.Model`, built as in the research note §2: Anthropic `AsyncAnthropic(api_key=key, max_retries=0, timeout=600)`, OpenAI `OpenAIResponsesModel` with `AsyncOpenAI(api_key=key, max_retries=0, timeout=600)`, Google `GoogleProvider(api_key=key, retry_options=HttpRetryOptions(attempts=1))`. Never a string model id.
  - `class ProviderFailed(Exception)` with `.message` (plain, names the provider, never the key) and `.kind` (`"auth" | "quota" | "unavailable" | "other"`).
  - `explain(provider: str, exc: Exception) -> ProviderFailed`: `ModelHTTPError` 401/403 → auth "{name} refused the key. Replace it in Keys."; 429, or a 400 whose body mentions credit, billing or quota → quota "{name} says the account is out of credit or over its limit."; 5xx, a timeout or a connection error → unavailable "{name} didn't answer. Try again in a minute."; anything else → other "{name} stopped with an error." `UsageLimitExceeded` is not handled here (Task 6 does that).

- [ ] **Step 1: Write the failing tests**
  - `test_offered`: unset → `["anthropic"]`; `" google, anthropic "` → `["anthropic", "google"]`; `"nope"` → `ConfigError`.
  - `test_model_for_builds_each_with_the_key`: for each provider, `model_for(p, "k" * 20)` is the right model class with model name `PROVIDERS[p].model`; Anthropic's and OpenAI's client has `max_retries == 0`.
  - `test_refused_key_fails_once`: an Anthropic model whose client goes through an httpx2 `MockTransport` (per the research note §8) that counts requests and returns 401. One `Agent(...).run_sync("hi", model=m)` raises; `explain` gives kind `auth`, the message contains "Claude" and not the key; the transport saw exactly 1 request. Do the same with 500: still 1 request, kind `unavailable`.
  - `test_explain_quota`: 429 → `quota`; 400 with body `{"error":{"message":"Your credit balance is too low"}}` → `quota`.
- [ ] **Step 2: Run them; they fail** — `.venv/bin/python -m unittest discover -s web/webtests -t web -p test_providers.py -v`.
- [ ] **Step 3: Implement.** Also confirm `./harmonicfitness test` still passes with the new lock, and `docker build` isn't needed until Task 9.
- [ ] **Step 4: Run them; all pass.**
- [ ] **Step 5: Commit** — `git commit -m "web: providers: Claude, ChatGPT and Gemini over the user's own key, never retried"`

### Task 2: Model keys in Keys

**Files:**
- Modify: `web/webapp/api.py` (`/api/keys`), `web/webapp/config.py` (`Settings.providers: tuple[str, ...]` from `providers.offered`), `web/client/src/api.ts`, `web/client/src/zones/KeysBox.tsx`
- Test: `web/webtests/test_api.py`, `web/client/src/zones/KeysBox.test.tsx`

**Interfaces:**
- Consumes: `providers.PROVIDERS`, `providers.offered` (Task 1); the existing key routes (Milestone 2).
- Produces: `GET /api/keys` entries gain `"kind": "voice" | "model"`. Model entries come first, offered providers only, with `name` the provider's name and `key_page` its page. `PUT` and `DELETE /api/keys/{id}` accept an offered provider id with the same rules (16 to 1024 characters, the engine's `clean_value` rule, the same 400 wording with the provider's name). A provider that isn't offered is 404. `KeyState` in the client gains `kind`. KeysBox is headed "Keys" with two groups, "Language model" and "Voice", and keeps its footer line, which now reads "Stored encrypted, never shown again. Each key goes only to its own service, when you use it."

- [ ] **Step 1: Write the failing tests** — API: `test_model_keys_listed_first_and_only_offered` (default settings: one model entry `anthropic`, `kind: "model"`, then the voice entries), `test_put_model_key` (204, then `set: true`), `test_unoffered_provider_is_404` (`PUT /api/keys/openai` → 404 with default settings). Client: `groups keys by kind` (both headings present, model rows under "Language model").
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass** — web tests with the DB URL; `npm test`.
- [ ] **Step 5: Commit** — `git commit -m "web: a language-model key in Keys, beside the voice keys"`

### Task 3: Conversations

**Files:**
- Create: `web/webapp/migrations/006_conversations.sql`, `web/webapp/conversations.py`
- Test: `web/webtests/test_conversations.py`

**Interfaces:**
- Consumes: `store.UserKey`, `crypto.seal`/`open_`.
- Produces:
  - Table `conversations(id bigserial primary key, user_id uuid not null references users on delete cascade, state text not null check (state in ('working','waiting','idle','failed')), body bytea not null, version int not null default 1, created_at timestamptz not null default now(), updated_at timestamptz not null default now())`, plus index `(user_id, updated_at desc)`. `body` is sealed with AAD `f"{user_id}:conversations:{id}"`.
  - `body` holds JSON `{"history": <pydantic-ai messages JSON string or null>, "lines": [{"role": "user"|"agent", "text": str}], "question": <ask_user args plus "tool_call_id"> | null, "plan": <show_plan args> | null, "stem": str | null}`.
  - `conversations.create(conn, uk, first_line: str) -> int` (state `working`, lines `[{"role":"user","text":first_line}]`); `load(conn, uk, cid) -> Conversation` (dataclass: `id, state, version, history, lines, question, plan, stem`; `LookupError` when it's missing or another user's); `latest(conn, uk) -> Conversation | None`; `save(conn, uk, conv: Conversation, expect_version: int) -> bool` (version check, bumps it, sets `updated_at`; `False` when the version moved); `begin_turn(conn, uk, cid, line: str | None, answer: dict | None) -> bool` (only from `waiting`, `idle` or `failed` to `working`; appends the user's line, or an answer line made by `answer_line(question, answer)`, and clears `question`; `False` otherwise); `answer_line(question: dict, answer: dict) -> str` (for example "Limits: Nothing new · Length: 25 min"). None of them commits.

- [ ] **Step 1: Write the failing tests:** `test_create_load_roundtrip`; `test_body_is_sealed` (the raw `body` holds no line text); `test_other_user_is_lookup_error`; `test_save_version_check` (an old version → `False`, nothing changed); `test_begin_turn_states` (`waiting`, `idle` and `failed` → `working` ok; `working`→ refused; an answer clears `question` and adds the answer line); `test_answer_line`.
- [ ] **Step 2: Run them; they fail.** — `... -p test_conversations.py -v` with the DB URL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass.**
- [ ] **Step 5: Commit** — `git commit -m "web: conversations, sealed, with their history, lines and open question"`

### Task 4: The engine tools

**Files:**
- Create: `web/webapp/agent/__init__.py` (empty for now), `web/webapp/agent/tools.py`
- Test: `web/webtests/test_agent_tools.py`

**Interfaces:**
- Consumes: `engine.run`, `worker.engine_lists` (goals, presets).
- Produces: `Deps` (dataclass): `engine_root: str, home: str, keys: dict[str, str]` (`repr=False`), `today: str`, `now: str`, `stem: str | None = None`. `ToolResult` (pydantic model): `code: int, output: str, error: str`, with output and error cut to 20,000 characters each and a "[cut]" mark. These functions each take `deps: Deps` first and return a `ToolResult`, running `./harmonicfitness …` through `engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=120)`:
  - `read_file(deps, name: Literal["profile.md","training.md","health.md","log.md"])`: reads `<home>/<name>` (code 0; a missing file gives code 1 and "no such file yet"). Not through the engine: it's a read of the user's own file.
  - `check(deps)`: `check`.
  - `get_coach(deps)`: `get coach`. `get_route(deps, coach: str)`: `get route --coach <coach>`.
  - `coaches(deps)`: `coaches list --json`. `content_plan(deps, minutes: int)`: `content plan --minutes N --json`. `coverage(deps)`: `coverage --json`.
  - `brief(deps, goal: str, minutes: int, kit: str | None, preset: str | None, equipment: list[str] | None, coach: str, limits: list[str] = [], avoid: list[str] = [], target: list[str] = [], add: list[str] = [])`: exactly one of kit, preset or equipment. The stem is `f"{today}-{goal}-{minutes}"`, with `-2`, `-3`… added while `<home>/workouts/<stem>/` already holds a menu. Runs `brief … --today <today> --save workouts/<stem>/<stem>.draft.txt` and sets `deps.stem`. Each `limits` item is passed as `--limit item`, `avoid`/`target` as single comma-joined flags, and `add` as `--add item` (check the engine's `brief --help` for each flag's exact form). Arguments are checked before the engine runs: goal in the engine's goals, preset in its presets, minutes 10 to 60. A bad argument returns code 64 and a plain error, without running anything.
  - Every argv is a list, never a shell string. No tool takes a path.

- [ ] **Step 1: Write the failing tests** (a user's folder seeded from `me.example/` with `folder.seed` + `folder.materialize`, as `test_jobs.py`'s brief test does; the real engine): `test_read_file_and_missing`; `test_brief_saves_menu_and_sets_stem` (code 0; `workouts/<stem>/<stem>.menu.json` exists; `deps.stem` set); `test_brief_second_today_gets_suffix` (running twice → `…-2`); `test_brief_refuses_bad_args_without_running` (`engine.run` patched to fail if called; unknown goal → 64); `test_get_coach_and_check_run` (code 0, non-empty output); `test_output_is_cut`.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass.**
- [ ] **Step 5: Commit** — `git commit -m "web: the agent's engine tools: typed, in the user's folder, nothing else"`

### Task 5: The agent

**Files:**
- Modify: `web/webapp/agent/__init__.py`
- Create: `web/webapp/agent/instructions.md`
- Test: `web/webtests/test_agent.py`

**Interfaces:**
- Consumes: the Task 4 tools and `Deps`; the research note §3–§7.
- Produces:
  - `Question`, `Option`, `Plan`, `PlanRow` pydantic models: Question as in Decisions; `Plan(format: str, equipment: str, rows: list[PlanRow], left_out: str, total_seconds: int)`; `PlanRow(block: str, movements: list[str], dose: str, seconds: int)`.
  - `AGENT`: `Agent(deps_type=Deps, output_type=[str, DeferredToolRequests], instructions=<instructions.md>, retries=1)`, with every Task 4 tool registered through `@AGENT.tool` wrappers that call the tools.py functions with `ctx.deps`, plus:
    - `ask_user(questions: list[Question])` (one to four): raises `CallDeferred(metadata={"kind": "questions"})`.
    - `show_plan(plan: Plan)`: needs `deps.stem` (else `ModelRetry("run brief first")`). Every movement in every row must resolve to a menu movement in `<home>/workouts/<stem>/<stem>.menu.json` (through the engine's own `catalog.resolve` and `menu` reader, imported under `worker._engine_modules`). Rows' seconds must add up to `total_seconds`, and that must equal the brief's minutes × 60. On failure it raises `ModelRetry` naming each problem. On success it stores the plan on `deps.plan` and returns "shown".
  - `TurnOutcome` (dataclass): `history_json: str, reply: str | None, question: dict | None, plan: dict | None, stem: str | None, usage: dict`.
  - `run_turn(model, deps: Deps, history_json: str | None, prompt: str | None, answer: tuple[str, dict] | None) -> TurnOutcome`: one `AGENT.run_sync`. `prompt` is the user's line. `answer` is `(tool_call_id, answer dict)` for the open question, passed as `DeferredToolResults(calls={id: answer})`. Limits are the Decisions' `UsageLimits`, and `UsageLimitExceeded` propagates. `question` is the deferred call's args plus its `tool_call_id`. `reply` is the final text, if any.
  - `instructions.md`: steps 1 to 4 of the workout skill, ported. Tool names replace commands (`./harmonicfitness check` → `check`, `get coach` → `get_coach`, AskUserQuestion → `ask_user`, the posted plan → `show_plan`). Kept: the check-in table (Limits, Readiness, Goal, Length, Kit, Coach) and its "just go" rule, the readiness and limit rules, the red-flag stop, the brief's flags and its "would open up" question, and the design rules. Left out, each with one line: research, writing, the build, the log, `health.md` edits ("say a lasting change is used for today only"), backup and delivery. End: after `show_plan`, a two-line reply saying the plan is ready and the script and audio come in a later version. Today is `deps.now`. No other file is read.
- [ ] **Step 1: Write the failing tests** (FunctionModel scripts, research note §7; a seeded folder as in Task 4):
  - `test_turn_asks_then_resumes`: script turn 1 calls `get_coach`, then `ask_user` with one question. The outcome has a `question` with a `tool_call_id` and no reply. Turn 2, with `answer=(id, {"q1": ["Nothing new"]})` and the saved history, sees the answer as the tool's return, then replies text. The outcome's `reply` is set and `question` is None.
  - `test_show_plan_refuses_off_menu`: after `brief`, `show_plan` with a movement not in the menu → the model receives a retry naming it; with menu movements and seconds adding up, `plan` is set.
  - `test_show_plan_needs_brief`: `show_plan` before `brief` → a retry saying so.
  - `test_history_roundtrip`: the outcome's `history_json` reloads through `ModelMessagesTypeAdapter` and holds the tool calls.
  - `test_instructions_cover_the_check_in`: `instructions.md` names each tool and the six check-in slots, and says the red flag stops.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass.**
- [ ] **Step 5: Commit** — `git commit -m "web: the agent: the check-in, the brief and the plan, over typed tools"`

### Task 6: The turn job

**Files:**
- Modify: `web/webapp/worker.py`
- Test: `web/webtests/test_jobs.py`

**Interfaces:**
- Consumes: `conversations` (Task 3), `agent.run_turn` and `Deps` (Task 5), `providers` (Task 1), `Ctx.keys` (Milestone 2).
- Produces: handler `turn` in `HANDLERS`. Args are `{"conversation_id": int, "line": str | None, "answer": {"tool_call_id": str, "values": dict} | None, "today": str, "now": str}`, with exactly one of line or answer. The handler:
  1. Validates the args: `today` as the brief job checks it; `now` matching `^\d{4}-\d{2}-\d{2} \w+ \d{2}:\d{2}$`.
  2. Loads the conversation. It must be `working`; else `JobFailed("the conversation moved on")`.
  3. Picks the provider: the first of `settings.providers` with a key in `ctx.keys`' source, `keystore.open_all` (model keys are not in the engine environment: `key_env` passes only voice keys, by the engine services' names). With none, `JobFailed("add a language-model key in Keys")`.
  4. Writes out the folder (`store.read_all` + `folder.materialize`).
  5. Says `ctx.say("thinking")`.
  6. Runs `run_turn`.
  7. Saves the new history, the lines (adds the agent's reply line), the question, the plan and the stem through `conversations.save`, with state `waiting` if a question is open, else `idle`.
  8. Writes back the files the brief made (`ctx.save(folder.harvest(...), base)`).

  Failure paths:
  - A provider error goes through `providers.explain`.
  - `UsageLimitExceeded` fails with "this turn ran too long; try again with less to do".
  - Any failure sets the conversation to `failed` with an agent line "That didn't work: <message>", saved in its own transaction. The previous history is kept, so the user can send another message (`begin_turn` accepts `failed`).

  The result is `{"conversation_id": id, "state": <state>}`. The worker logs nothing from the conversation.
- [ ] **Step 1: Write the failing tests** (FunctionModel through a patched `providers.model_for`):
  - `test_turn_job_saves_question`: conversation `waiting`, question stored, lines hold the user's line.
  - `test_turn_job_with_answer_finishes_with_plan`: brief and show_plan scripted; state `idle`, plan set, the menu stored in the user's files.
  - `test_turn_needs_a_model_key`: no key → job failed, conversation `failed`, the line says to add a key.
  - `test_turn_maps_provider_errors`: `model_for` returning a model that raises `ModelHTTPError(401)` → the line holds "Claude refused the key".
  - `test_turn_stops_at_usage_limit`: a FunctionModel that calls `get_coach` forever → job failed with the limit message; the stored history is the one from before the turn.
  - `test_model_key_never_in_engine_env`: `engine.run` records `extra_env` → it never holds the model key.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass** — all web tests and `./harmonicfitness test`.
- [ ] **Step 5: Commit** — `git commit -m "web: the turn job: one agent turn on the user's folder and key"`

### Task 7: The conversation API

**Files:**
- Modify: `web/webapp/api.py`
- Test: `web/webtests/test_api.py`

**Interfaces:**
- Consumes: `conversations`, `jobs.enqueue`, `settings.providers`, `keystore.listing`.
- Produces (all need a session; POSTs need same-origin; another user's conversation is 404):
  - `POST /api/conversations` `{"line": str (1..2000), "today", "now"}` → 202 `{"id", "job_id"}`. 409 "Add a key for {first offered provider's name} in Keys first." when the user has no offered model key.
  - `GET /api/conversations/latest` → the latest conversation or 204.
  - `GET /api/conversations/{id}` → `{"id", "state", "lines", "question", "plan"}` (never `history`).
  - `POST /api/conversations/{id}/messages` `{"line", "today", "now"}` → 202 `{"job_id"}`; 409 "Still working on the last message." unless `begin_turn` accepts it.
  - `POST /api/conversations/{id}/answer` `{"tool_call_id", "values": {question id: list[str] | str}, "today", "now"}` → 202 `{"job_id"}`. 409 when the open question's `tool_call_id` differs, or none is open. 422 when a value names no option of its question (an `other:` text needs `other: true`; a list needs `multi`).
  - Each POST creates or begins the turn and enqueues the `turn` job in one transaction (the per-user queued cap of 3 still applies, 429).
- [ ] **Step 1: Write the failing tests:** `test_start_needs_model_key` (409); `test_start_queues_turn` (202, a `turn` job whose sealed args hold the line); `test_get_never_returns_history`; `test_answer_twice_is_409` (a question stored, the first answer 202, the second 409, one job only); `test_answer_validates_options` (422); `test_message_while_working_is_409`; `test_other_users_conversation_is_404` (get, messages, answer).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass.**
- [ ] **Step 5: Commit** — `git commit -m "web: the conversation API: start, message, answer, read"`

### Task 8: Chat and panel in the browser

**Files:**
- Modify: `web/client/src/api.ts`, `App.tsx`, `zones/Chat.tsx`, `zones/Panel.tsx`, `theme.css`
- Create: `web/client/src/zones/Question.tsx`, `zones/PlanTable.tsx`, tests beside them and `zones/Chat.test.tsx`

**Interfaces:**
- Consumes: the Task 7 routes, the existing `useJob` stream (for the turn's job: when it ends, reload the conversation).
- Produces:
  - **The sentence band's button** starts a conversation with the sentence as its first line, for example "A 20-minute strength workout with bodyweight". It replaces the Slice 1 brief job in the UI; the `brief` job kind stays in the worker.
  - **Chat** shows the lines, a "Thinking…" line while a turn's job runs, and a text box with Send (Enter sends, Shift+Enter makes a new line; disabled while working). The page loads the latest conversation on sign-in.
  - **Panel** shows the open question as a form (Question: radio or checkbox options, the recommended one preselected and marked "Recommended", an "Other" text field when allowed, one Send button for all questions). It shows the plan as a table when there is one (PlanTable: block, movements, dose, time as m:ss; then the format, equipment, total and the left-out line). Otherwise it shows the existing empty state.
  - With no model key, the 409 message shows in the chat with a button that opens Keys.
- [ ] **Step 1: Write the failing tests:** Question: `preselects the recommended option`, `sends every question's answer once` (calls `api.answer` with the values, and the button is disabled after). PlanTable: `shows rows and total`. Chat: `sends a line and shows Thinking while working`, `shows the no-key message with a Keys button`.
- [ ] **Step 2: Run them; they fail** — `npm test`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass** — `npm test`, `npm run build`, no warnings.
- [ ] **Step 5: Commit** — `git commit -m "web: chat, the check-in in the panel, and the plan table"`

### Task 9: Deploy and check it live

- [ ] **Step 1:** `web/README.md`: an "Agent" section covering the providers, `HARMONICFITNESS_PROVIDERS`, the limits per turn, no retries, where history is kept, and what the model sees (the profile, training, health and log files, and the brief). `CHANGELOG.md` `[Unreleased]`: the agent through the plan, Claude only until the eval. Run `./harmonicfitness test` and `npm test`. Commit.
- [ ] **Step 2:** `docker build -t harmonicfitness-web .` succeeds and `docker run --rm harmonicfitness-web .venv/bin/python -c "import pydantic_ai, anthropic; print(anthropic.__version__)"` prints a 1.x version.
- [ ] **Step 3:** Push `main`. Both services report `SUCCESS`, and the worker is running (it waits for migration 006).
- [ ] **Step 4:** The maintainer adds a Claude key in Keys and taps the sentence's button. Expected: the check-in appears in the panel; after answering, the plan table appears, and every movement in it is one the brief listed. The worker's log holds job ids only.
- [ ] **Step 5:** Mark Milestone 3 built in `plan.md`'s table; commit.
