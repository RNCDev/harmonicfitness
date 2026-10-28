# Web client, Milestone 4: build, render, deliver

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After the plan is shown, the user presses one button that names what the voice service may charge. They can leave. A background job writes the script, lints it, renders it with their web coach, and uploads the MP3. It also logs the session. When they come back, the panel plays the workout and offers a download for 24 hours.

**Architecture:** The turn that shows the plan also stores an **offer** on the conversation: the coach, the voice service, the most characters the build may send (the allowance) and what that costs at most. Pressing **Make the audio** reserves the allowance against the user's daily cap and queues one long `workout` job, in one transaction. The job writes out the folder and fetches the feeds. Then a second agent, the **writer**, runs over its own typed tools: it reads the brief by section, writes the draft, lints it, builds it and logs it. Every build carries `--max-chars <what's left of the allowance>`, so the engine itself refuses to send more than the user agreed to. As soon as a build delivers, the worker uploads the MP3 to the bucket and records it with `expires_at`. It also writes the workout's files back, so nothing paid for is lost if a later step fails. The browser follows the job's stages, then plays the MP3 through a short-lived signed link. The worker deletes expired objects every 10 minutes.

**Tech stack:** as Milestone 3, plus `boto3` in the `web` extra (pinned `==`, the newest release at least two weeks old), used by both services for the bucket.

**Spec:** `docs/research/web-client/design.md` ("Delivery and storage"; "Jobs and conversations"; "The agent"; "Keys"; "Per-user isolation"; Anti-goals, billing). Built on Milestone 3 (`plan-m3.md`, through `8af95d3`). Workflow ported: `.claude/skills/workout/SKILL.md` steps 5 to 7, for web coaches only (`HARMONICFITNESS_WEB=1`; `delivery_plan(..., client=True)` keeps the MP3; the `--web` copy doesn't apply).

## Global constraints

Everything in `plan.md`'s, `plan-m2.md`'s and `plan-m3.md`'s Global constraints holds. In particular:
- **Nothing reaches a paid voice service without the user's press of Make the audio**, and never more characters than that offer named. The engine enforces the bound (`--max-chars`), not the agent's instructions. Nothing billed is retried automatically. A job that dies is failed, never requeued.
- **Audio the user paid for is never lost to a later failure.** The upload and the write-back of the workout's files happen as soon as a build delivers, before logging.
- The engine subprocess never sees bucket credentials, the database URL or the master key. They stay out of `engine.ALLOWED`, and the test proves it.
- The writer has no shell and no general file access. It writes one file, the current workout's draft, and nothing else.
- Every engine change is a general feature, with engine tests (`./harmonicfitness test`), a CHANGELOG `[Unreleased]` line, and CLAUDE.md updated where it describes the changed behaviour. If a skill is edited, run `./harmonicfitness harness sync`.
- Tests make no real network call and no paid call. They use the fake voice servers in `tests/fakes.py`, `FunctionModel` for both agents, a memory bucket, Postgres through `HARMONICFITNESS_TEST_DATABASE_URL`, and vitest with Testing Library (`fireEvent`) for the client. A test that encodes skips without ffmpeg (`helpers.HAS_FFMPEG`).

## Decisions

- **Ruling: the consent is a button on the shown plan, before the long job, never a question inside it.** Why: the spec's in-job questions time out to their default, and for a billed render neither default is acceptable. "No" means no workout. "Yes" breaks the anti-goal. The button also keeps the spec's promise that the user can leave once it's pressed. Cost if wrong: one extra tap per workout. A standing "auto-approve up to $X" setting could replace it later.
- **Ruling: the long job is its own kind, `workout`, with its own agent run (the writer). It is not a continuation of the turn's history.** Why: the spec puts write, lint, build, upload and log in one unattended job, so the clip cache in the job's folder is reused across rebuilds (exit 2, adjust, rebuild sends only changed paragraphs). A fresh run starts from the stored plan and the brief file. It doesn't replay the turn's history, which holds the whole 87,000-character brief. Brief and design stay in the turn (Milestone 3), so this job runs research, write, lint, build, upload, log. Cost if wrong: the writer misses something said in the check-in. To guard against that, it gets the conversation's last 20 chat lines.
- **Ruling: the allowance is `min(the profile's cloud_max_chars, what's left of today's cap)`, shown as "up to N characters, at most $X".** It comes from the engine's new `get cost`, which reads the rates in `knowledge/services.toml`, so the web never copies a rate. If the coach is still `pending`, the offer adds the design ("your coach's voice is designed first and saved in your <service> account, about $0.01"). Why: the allowance is the one number the engine can enforce. An estimate can't be made before the script exists. Cost if wrong: the offer shows a ceiling rather than a typical cost.
- **Ruling: a daily cap of `HARMONICFITNESS_DAILY_CHARS` (default 60,000) per user per local day**, kept in a `spend` table. Each row is one job's reservation, then what it actually sent. A job that dies keeps its full reservation as spent. This amends the global constraint: `spend` holds plain character counts, which are not personal, so the cap can be checked under a row lock without opening anything. Cost if wrong: a user who rebuilds a lot is stopped for the day. The maintainer raises the variable.
- **Ruling: the build's budget lives in the engine.** `build --max-chars N` lowers that build's ceiling below `cloud_max_chars`. The lint then refuses a script whose spoken characters exceed N, and the render stops before sending (exit 1) when the clips it would send exceed N. The writer passes what's left of the allowance on every lint and build. That figure is the allowance minus `chars_sent` from each `builds.jsonl` line this job added, `mp3` and `failed` lines alike, read through the engine's `records.parse`. Cost if wrong: none to the user; at worst a rebuild is refused early.
- **Ruling: at most 3 full builds and 10 lints per job, and the writer's limits are `UsageLimits(request_limit=40, tool_calls_limit=80, total_tokens_limit=1_500_000)` with a wall clock of `WORKOUT_SECONDS = 1200`.** A build's engine call may run up to 900 s. Cost if wrong: a long workout that needs more drift passes fails and has to be pressed again (its clips are lost, see the clip-cache ruling).
- **Ruling: research is the smallest version that still gives a good workout.** The job runs the engine's `feeds` once (60 s, best effort). The writer reads `content plan`, the feeds sheet and the existing reserve sheets, and records what it told with `content log`. M4 has no web search, no page fetch, no YouTube and no reserve restocking. When the plan's deep dive is a video, the writer tells a news or featured-article deep dive from the feeds instead. Why: the spec's search runs through each provider's native tool, which isn't verified per provider until Milestone 5's eval. YouTube's transcript endpoint often refuses datacenter addresses. Cost if wrong: thinner filler until the next milestone.
- **Ruling: MP3s go to the existing Railway bucket `media` under `u/<user_id>/<32 random hex>.mp3`. A `media` row (sealed name and length; plain size, `expires_at = now() + 24 h`) records each upload.** `GET /api/media/{id}` answers with a 302 to a presigned GET valid for 300 s. With `?download=1`, the presigned URL carries `ResponseContentDisposition=attachment; filename="<name>.mp3"`, because browsers ignore `download` on a cross-origin link. The worker's loop sweeps expired objects every 10 minutes (`plan.md`'s decision). The audio itself isn't app-encrypted: a signed link must play it. A private bucket, an unguessable key and 24 hours are the safeguards. Cost if wrong: proxy the audio through `web` with decryption instead.
- **Ruling: deploys drain the worker.** On SIGTERM the worker already stops claiming. M4 lets the running job finish, and sets the worker's Railway draining time above `WORKOUT_SECONDS` (`RAILWAY_DEPLOYMENT_DRAINING_SECONDS=1500`; Task 14 verifies the name and limit in Railway's docs, and if Railway caps it lower, `WORKOUT_SECONDS` drops to fit). Why: killing a render loses clips already billed, which is the anti-goal. Cost if wrong: during a long job, a deploy keeps the old worker up to 25 minutes.
- **Ruling: a heartbeat that fails reconnects and retries (every 5 s) until 100 s have passed since the last good beat.** At that point, or when the row is no longer running (reaped), the job's `cancel` event is set. That kills the engine's process group and cancels the agent run, so a reaped job stops billing. `jobs.complete` still decides at the end.
- **Ruling: write-back is an allowlist per job kind, not one global `NEVER_WRITE_BACK`.** `brief` and `turn` may write `workouts/`. `workout` may write `log.md`, `workouts/` and `coaches/` (a stock coach made on first use). `health.md` is in no list in M4. The check-in's permission to write it arrives with the edit tool in Milestone 6, which adds it to `turn`'s list.
- **Ruling: the clip cache and the voice-pace file don't persist between jobs.** A web coach's measured pace does persist: it lives in `coaches/<slug>/pace.json`, which is harvested. Cost if wrong: a workout pressed again after a failure re-bills its clips. The allowance and the daily cap bound that.
- **Ruling: prompt caching.** Anthropic gets `anthropic_cache_instructions`, `anthropic_cache_tool_definitions` and `anthropic_cache_messages`, verified present in the installed pydantic-ai 2.56. OpenAI and Gemini cache long prefixes on their own. The writer reads the brief by section (`read_brief`, `movement_notes`), never whole. The turn agent keeps the whole brief, since it designs from all of it. Cost if wrong: higher model bills on Claude only.
- **Ruling: generic names.** The catalog gains an `[unlisted]` table of real movements it doesn't hold ("pistol squat(s)", "forward lunge(s)", "walking lunge(s)", "lunges"). The menu scan treats them as movements that are never on a menu. A bare "lunges" is still excused as a short form of a declared lunge (`part_of`). Why: an alias would point at a different movement, which weakens the screen. A real catalog entry needs sourced research. Cost if wrong: a writer has to name the exact lunge.
- **Ruling: the side rule lives in the engine.** `menu.side_problems` is shared by the build's `menu.check` (spoken text) and the web's `show_plan`, so the CLI and the web refuse the same thing.
- **Ruling: a plan is for its day.** Make the audio needs the browser's `today` to equal the stem's date. Otherwise it returns 409 "This plan was for an earlier day; start a new one." A health change after the plan stops the build at the menu gate. The writer then ends with "your health notes changed since the plan; make a new plan".
- **Ruling: no per-clip progress in M4.** The panel shows stages (Writing, Checking, Recording, Saving, Ready). It doesn't show clip counts, because the engine's render chatter goes to its log, not to stdout.

## Review focus

1. **A billed render the user didn't agree to, or bigger than the offer.** Expected: no `workout` job without the button's POST carrying the current offer's id, and the fake service sees zero requests when the script exceeds `--max-chars`. Pinned by `test_build_route_needs_the_current_offer` (Task 10) and `test_max_chars_stops_before_sending` (Task 3).
2. **Paid audio lost to a later failure.** Expected: a job whose `log_session` fails or hits its limit still has its `media` row, its object, and its draft, text and build record in the store. Pinned by `test_audio_kept_when_a_later_step_fails` (Task 12).
3. **A reaped job keeps billing.** Expected: the engine is killed within 2 s of the heartbeat finding the job reaped, and nothing is written back. Pinned by `test_reaped_job_kills_the_engine` (Task 5).
4. **Two presses race the daily cap.** Expected: one 202, one 409, one `spend` row, one job. Pinned by `test_daily_cap_holds_under_two_posts` (Task 10).
5. **Another user's audio, or audio past 24 hours.** Expected: 404 for another user's media; 410 for one's own expired media, and the sweep removes the object. Pinned by `test_other_users_media_is_404` and `test_expired_media_is_410_and_swept` (Task 9).
6. **A one-sided movement spoken on both sides.** Expected: the build refuses "each side" next to a movement the menu allows on the right only. Pinned by `test_build_refuses_both_sides_for_a_one_sided_movement` (Task 2).

---

## File map

```
tools/routes.py, cloud.py, render.py, audition.py, keys.py   modify: web-mode wording (Task 1)
tools/menu.py, catalog.py, knowledge/movements.toml          modify: side_problems, part_of, [unlisted] (Task 2)
tools/build.py, tts_build.py, render.py, context.py          modify: --max-chars, get cost (Task 3)
tests/test_tools.py, test_safety.py, test_cloud.py, test_routes.py, test_keys.py   engine tests
CLAUDE.md, CHANGELOG.md
pyproject.toml, uv.lock                                      modify: boto3 in `web`
web/webapp/engine.py, folder.py, worker.py                   modify: cancel, caps, write rules, heartbeat, drain, workout job
web/webapp/keystore.py, api.py, config.py, conversations.py  modify
web/webapp/media.py, spend.py                                new
web/webapp/migrations/007_damaged_keys.sql, 008_media.sql, 009_spend.sql   new
web/webapp/agent/__init__.py, tools.py, instructions.md      modify (Task 8)
web/webapp/agent/writer.py, writer.md                        new (Task 11)
web/webtests/test_media.py, test_spend.py, test_writer.py, test_workout_job.py (new); test_engine.py, test_folder.py, test_jobs.py, test_api.py, test_agent.py, test_keystore.py
web/client/src/api.ts, conversation.ts, App.tsx, zones/Panel.tsx, zones/Offer.tsx (new), zones/Player.tsx (new), zones/Stages.tsx (new), zones/KeysBox.tsx, zones/Chat.tsx, tests
web/README.md, docs/research/web-client/plan.md
```

---

### Task 1: Engine: web-mode wording and docs

**Files:** Modify `tools/routes.py` (`usable`, `missing_key`), `tools/cloud.py` (the two key messages at :269 and :533), `tools/render.py` (:339), `tools/audition.py` (:187), `tools/keys.py` (`clean_value`'s `BadKey`), `CLAUDE.md` (`--coach` and `delivery_plan` in Building a workout), `CHANGELOG.md`. Test: `tests/test_routes.py`, `test_cloud.py`, `test_keys.py`, `test_tools.py`.

**Interfaces:**
- Produces: under `paths.WEB` (true when `HARMONICFITNESS_WEB=1`), each message names "Keys, in the app" and never says `keys init`, `keys open` or `me/.env`. The CLI's wording is unchanged.

- [ ] **Step 1: Write the failing tests:**
  - `test_web_mode_messages_never_say_env`: under `HARMONICFITNESS_WEB=1`, check each of the six messages: `routes.usable("fish")` with no key, the local route's reason, `cloud`'s no-key `ServiceError` and stray-character error, the render's refused-key line (through the fake server returning 401), `audition`'s no-service line and `keys.clean_value("FISH_AUDIO_API_KEY", "a b…")`. Each says "Keys" and contains none of `keys init`, `keys open`, `me/.env`.
  - `test_cli_messages_unchanged`: the same calls without the variable still say `keys init`.
  - `test_web_build_takes_the_default_web_coach`: a full build in web mode with no `--coach`, a Fish key in the environment, and a made Fish coach. It runs against the fake server (`HARMONICFITNESS_FISH_URL`). The record names that coach and `kept_local: true`. It closes the "the build test names its coach" item.
- [ ] **Step 2:** Run `./harmonicfitness test`. Expected: the three fail.
- [ ] **Step 3:** Implement a `paths.WEB` branch at each site. In CLAUDE.md, say `--coach`'s default in web mode never falls back to a local stand-in, and `delivery_plan(..., client=True)` keeps the MP3 for the web client. CHANGELOG: "web mode's key messages point at the app's Keys".
- [ ] **Step 4:** Run `./harmonicfitness test`. Expected: PASS.
- [ ] **Step 5: Commit** `engine: web mode says Keys, never me/.env`.

### Task 2: Engine: one side only, in the build's check; names the catalog doesn't hold

**Files:** Modify `tools/menu.py`, `tools/catalog.py` (load `[unlisted]`), `knowledge/movements.toml`, `CLAUDE.md` (the menu scan paragraph), `CHANGELOG.md`. Test: `tests/test_safety.py`, `tests/test_catalog.py`.

**Interfaces:**
- Produces: `menu.part_of(cat, words, names, declared) -> bool`, the old `_part_of` made public (`_part_of` kept as an alias for this release). `menu.SIDES`, `menu.BOTH_SIDES` and `menu.side_problems(cat, on_menu: dict, text: str) -> list[str]`, moved from `web/webapp/agent/__init__.py`'s `_side_problem`, `_one_side_problem`, `_both_sides` and `BOTH_SIDES`, with the same wording. The rule: a clause that names a movement the menu allows on one side only may not hold a both-sides phrase or another side's word. A segment naming one may not hold a switch phrase anywhere (`switch`, `other side`, `other leg`, `swap sides`, `repeat on the other`). `menu.check` adds `side_problems` as issues, per segment's spoken text.
- Produces: `catalog.Catalog.unlisted: tuple[str, ...]`, from `[unlisted] names = [...]`. `menu.mentions` yields each one as `("unlisted", said, before)`, and `check` reports it: '"pistol squats" isn't in the catalog, so it can't be on today's menu; use a movement the brief lists'. A short form of a declared movement is still excused (`part_of`).

- [ ] **Step 1: Write the failing tests:**
  - `test_build_refuses_both_sides_for_a_one_sided_movement`: a menu with the single-leg glute bridge on `right`. The draft line "Right single-leg glute bridge, ten each side." gives an issue naming "each side". "Right single-leg glute bridge, ten." gives none.
  - `test_switch_in_the_segment_is_refused`: the same movement, and "Now switch to the other leg." later in its segment, is an issue.
  - `test_unlisted_names_are_refused`: "Ten pistol squats." gives an issue. "Reverse lunges, then more lunges." with reverse lunge declared gives none.
  - `test_catalog_unlisted_loads`: `catalog.load().unlisted` holds "pistol squat". A name there that is also a catalog name or alias is a load error.
- [ ] **Step 2:** Run `./harmonicfitness test`. Expected: FAIL.
- [ ] **Step 3:** Implement. CLAUDE.md: the scan's one-side rule and `[unlisted]`. CHANGELOG lines for both.
- [ ] **Step 4:** Run `./harmonicfitness test`. Expected: PASS.
- [ ] **Step 5: Commit** `engine: the build keeps one-sided movements on their side; names the catalog doesn't hold are refused`.

### Task 3: Engine: a build's allowance and its cost

**Files:** Modify `tools/build.py` (`--max-chars`, `BuildOptions.max_chars`), `tools/tts_build.py` (the lint's character check), `tools/render.py` (`render_cloud`'s ceiling), `tools/context.py` (`get cost`), `CLAUDE.md`, `CHANGELOG.md`. Test: `tests/test_tools.py`, `tests/test_cloud.py`.

**Interfaces:**
- Produces: `build --max-chars N` (`cli.positive_int`; `BuildOptions.max_chars: Optional[int] = None`). With a web voice, the lint adds the issue "the script speaks N characters; this build may send at most M (--max-chars)" when over. `render_cloud`'s ceiling is `min(cloud_max_chars, max_chars)`; over it, the stop names `--max-chars` when that was the lower bound. A local voice ignores the flag.
- Produces (in `tools/context.py`'s `get`; check `tests/test_imports.py`'s cycle allowlist before importing `coachpick` and `services` there, and put the work in a module of its own if it objects): `get cost --coach <coach> [--chars N] [--json]` gives `{"coach", "service", "model", "chars", "usd", "ceiling", "pending_design": bool, "design_usd": float | null}`. With no `--chars`, `chars` is the ceiling. Exit 64 if the coach is a local coach or can't speak here, with `routes`' web-mode wording.

- [ ] **Step 1: Write the failing tests:**
  - `test_max_chars_stops_before_sending`: a made Fish coach and `--max-chars 50` on a draft longer than that. The full build exits 1 naming `--max-chars`, and the fake server saw 0 requests. The `stopped` outcome line has stage `lint`.
  - `test_max_chars_render_ceiling`: a draft under the lint's count, with clips that exceed `--max-chars` once retakes are added. The render stops before the first request. Set this up by making the lint's count pass and the render's `todo` exceed it, for example with the clip cache pre-filled for some clips and not others. Check the arithmetic in `render_cloud` first.
  - `test_max_chars_ignored_for_local`: `--lint-only --max-chars 1` with a local coach passes.
  - `test_get_cost_json`: for a made Fish coach, `chars == ceiling == 30000` and `usd` equals `services.estimate`'s value. For a pending stock coach, `pending_design` is true. A local coach gives 64.
- [ ] **Step 2:** Run `./harmonicfitness test`. Expected: FAIL.
- [ ] **Step 3:** Implement. Add `--max-chars` to `test_contract`'s numeric option walk. CLAUDE.md: the build's options and `get`'s values. CHANGELOG.
- [ ] **Step 4:** Run `./harmonicfitness test`. Expected: PASS.
- [ ] **Step 5: Commit** `engine: build --max-chars and get cost, so a caller can bound and price a web build`.

### Task 4: The runner can be stopped, and takes back only what it may

**Files:** Modify `web/webapp/engine.py`, `web/webapp/folder.py`, `web/webapp/worker.py` (`Handler`, `HANDLERS`), `web/webapp/agent/__init__.py` (`run_turn`'s timer), `web/webapp/agent/tools.py` (`Deps.cancel`, `_run`). Test: `test_engine.py`, `test_folder.py`, `test_jobs.py`, `test_agent.py`.

**Interfaces:**
- Produces: `engine.run(engine_root, home, argv, extra_env={}, timeout=120, cancel: threading.Event | None = None, max_output: int = MAX_OUTPUT) -> Result`. It polls `cancel` every 0.2 s while the process runs. When it's set, it kills the process group (SIGTERM, then SIGKILL after 5 s) and returns `CANCELLED = 125` with "stopped: the job was cancelled". It reads stdout and stderr in two threads into bounded buffers (`MAX_OUTPUT = 1_000_000` characters each). Over that, it keeps the first and last halves with "[cut]" between.
- Produces: `folder.harvest(root, written, never=frozenset(), only: tuple[str, ...] | None = None, max_file: int = MAX_FILE, left_out: list[str] | None = None)`. `only` lists allowed exact paths or folder prefixes ending in `/`; deletions outside `only` are ignored too. `MAX_FILE = 2_000_000` bytes. A bigger file is left out, with its path appended to `left_out`.
- Produces: `worker.Handler(fn: Callable[[Ctx], dict], writes: tuple[str, ...])` (frozen dataclass). `HANDLERS = {"brief": Handler(brief, ("workouts/",)), "turn": Handler(turn, ("workouts/",))}`. `Ctx.cancel: threading.Event` and `Ctx.writes`. Ctx owns the folder's state: `Ctx.materialize()` reads the store, writes the folder and keeps `ctx.base` (path → version) and `ctx.written` (path → sha256). `Ctx.harvest() -> dict` is the one harvest call handlers make, with `only=ctx.writes`, and `ctx.save(ctx.harvest())` takes `ctx.base`. It says `left_out` in the `saved` event. `brief` and `turn` move to these. `NEVER_WRITE_BACK` goes away.
- Produces: `Deps.cancel: threading.Event | None = None` (`repr=False`), which every tool's `engine.run` gets. `run_turn` takes `cancel`. When the `TURN_SECONDS` timer fires it sets `cancel` and cancels the token, and a watcher thread cancels the token when anything else sets `cancel`.

- [ ] **Step 1: Write the failing tests:**
  - `test_cancel_kills_the_group`: a stub engine that starts a child process and sleeps. Setting `cancel` after 0.3 s returns code 125 within 1.5 s, and the child's pid is gone.
  - `test_output_is_capped`: a stub printing 3 MB gives stdout of at most `MAX_OUTPUT + 20` characters, holding "[cut]", starting with its first line and ending with its last.
  - `test_harvest_only_and_max_file`: `only=("workouts/",)` leaves out a changed `health.md` and `log.md`. A 3 MB `workouts/x.md` is left out and listed.
  - `test_turn_never_writes_health`: a scripted turn whose tool writes `health.md`, which a patched `read_file` does for the test, stores no `health.md` change.
  - `test_turn_cap_kills_the_engine_call`: `TURN_SECONDS` patched to 1, and a tool whose stub engine sleeps 30 s. The turn fails with `TOO_LONG` within 8 s, which closes the "2 minutes past the cap" item.
- [ ] **Step 2:** Run the web tests. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run all web tests and `./harmonicfitness test`. Expected: PASS.
- [ ] **Step 5: Commit** `web: an engine call can be cancelled; output and harvested files are capped; write-back per job kind`.

### Task 5: The worker keeps its jobs through a flaky database and a deploy

**Files:** Modify `web/webapp/worker.py` (`_Heartbeat`, `run_one`, `main`). Test: `test_jobs.py`.

**Interfaces:**
- Consumes: `Ctx.cancel` (Task 4).
- Produces: `_Heartbeat(connect, job_id, cancel)`. When a beat raises, it closes the connection and reconnects every `RETRY_EVERY = 5` s. It sets `lost` and `cancel` when `heartbeat()` returns False (the row isn't running) or when `GIVE_UP = 100` s have passed since the last good beat. `run_one` passes `ctx.cancel`. `main`'s SIGTERM handler only sets `stopping`, so a running job finishes. `main` logs "worker: draining job <id>" once. A job kind's wall clock (`WORKOUT_SECONDS`, Task 12) must be below `DRAIN_SECONDS = 1500`, which a test pins.

- [ ] **Step 1: Write the failing tests:**
  - `test_heartbeat_reconnects_after_a_failure`: `connect` returns a connection whose first `heartbeat` raises `OperationalError`, then a good one. With `HEARTBEAT_EVERY` patched to 0.1, after 1 s `lost` is clear and the row's `heartbeat_at` moved.
  - `test_reaped_job_kills_the_engine`: a `brief` job on a stub engine root (`Settings.engine_root` pointing at a temp folder whose `harmonicfitness` sleeps 30 s; `engine_lists` patched). The test reaps it mid-run (sets it failed directly). Within 2 s the engine returns 125, the job stays `failed` "interrupted", and the store is unchanged.
  - `test_heartbeat_gives_up_and_cancels`: `connect` always raises, with `GIVE_UP` patched to 0.5. `cancel` is set within 1 s.
  - `test_sigterm_lets_the_running_job_finish`: `main`'s loop with `stopping` set while a job runs. The job ends `done`, no second job is claimed, and the loop returns 0.
  - `test_wall_clocks_fit_the_drain`: every `*_SECONDS` cap in `worker` and `agent` is below `DRAIN_SECONDS`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: the heartbeat retries, a reaped job's engine is killed, and a deploy drains`.

### Task 6: Keys: one damaged key, and wording

**Files:** Modify `web/webapp/keystore.py`, `web/webapp/worker.py` (`Ctx.key_env`, `_turn`), `web/webapp/api.py` (`/api/keys`, the too-short 400), `web/webapp/migrations/007_damaged_keys.sql` (new: `user_keys.damaged_at`), `web/client/src/zones/KeysBox.tsx`. Test: `test_keystore.py`, `test_api.py`, `KeysBox.test.tsx`.

**Interfaces:**
- Produces: `keystore.open_all(conn, uk) -> tuple[dict[str, str], list[str]]`, the keys that opened and the services whose rows didn't (`crypto.Tampered`). Each damaged row gets `damaged_at = now()`, set by the worker. `put` clears it. Every caller (`key_env`, `_turn`) takes the pair. A damaged row emits `{"stage": "key_unreadable", "services": [...]}` and the job carries on with the rest. `GET /api/keys` entries gain `"damaged": bool`. A key under `KEY_MIN` is 400 "That's too short to be a key: paste the whole key." KeysBox shows "Can't be read; paste it again" on a damaged row.
- Key rotation is out of scope (see Not in this milestone). `test_key_version_is_only_set_at_creation` pins that nothing else writes `key_version`.

- [ ] **Step 1: Write the failing tests:** `test_one_damaged_key_is_skipped_and_reported` (two keys, one row's `secret` overwritten with junk: the job runs with the other key, the event names the damaged service, `damaged_at` is set). `test_put_clears_damaged`. `test_short_key_wording` (400 text). `test_key_version_is_only_set_at_creation` (reads `webapp/*.py` and asserts no `update` statement names `key_version`). Client: `marks a damaged key`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the web tests and `npm test`. Expected: PASS.
- [ ] **Step 5: Commit** `web: one unreadable key no longer fails every job; the Keys box says which to replace`.

### Task 7: Coming back to a job

**Files:** Modify `web/webapp/api.py` (stream caps, `GET /api/jobs/latest`), `web/client/src/api.ts` (`useJob`), `web/client/src/App.tsx`. Test: `test_api.py`, `web/client/src/useJob.test.tsx` (new).

**Interfaces:**
- Produces: `STREAMS_PER_USER = 3` and `STREAMS_ALL = 40`, counted in the web process under a lock and released in the stream's `finally`. Past either, the response is 429 "Too many open pages; close one." `GET /api/jobs/latest` gives `{"id", "kind", "state"}` for the user's newest queued or running job, else 204. `useJob`: when a stream closes while the job reads `queued` or `running`, it follows again after 2 s, then 5 s, then every 10 s, and stops once the job ends or the user signs out. On load, `App` follows `/api/jobs/latest` when no conversation is working.

- [ ] **Step 1: Write the failing tests:** `test_stream_caps` (a fourth stream for one user is 429, and closing one frees a slot). `test_latest_job` (204, then a queued job's id). `test_latest_job_is_per_user`. Client (`useJob.test.tsx`, a fake `EventSource` class on `globalThis`): `follows again after a dropped stream while running`, `stops after the state event`, `stops on sign-out`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: event streams are capped; a reload finds a running job and a dropped stream is followed again`.

### Task 8: The planner hands over

**Files:** Modify `web/webapp/agent/__init__.py`, `web/webapp/agent/tools.py`, `web/webapp/agent/instructions.md`, `web/webapp/providers.py`. Test: `test_agent.py`, `test_agent_tools.py`, `test_providers.py`.

**Interfaces:**
- Consumes: `menu.side_problems`, `menu.part_of`, `menu.mentions` yielding `"unlisted"` (Task 2).
- Produces: `plan_problems` uses `menu.side_problems` and `menu.part_of`. The local `_side_problem`, `_one_side_problem`, `_both_sides`, `BOTH_SIDES` and the use of `menu._part_of` are removed. The plan's `equipment` field is scanned with the catalog's equipment names (`cat.equipment`) excused, so "jump rope" passes there. An `"unlisted"` mention is refused like an off-menu one.
- Produces: `Deps.coach: str | None`, set by `tools.brief` with `stem`. `Deps.shown_this_run: bool = False`, set only by a successful `show_plan`. Every turn starts it False, even when `deps.plan` comes from an earlier turn. If `brief` runs while it is True, it returns 64 "the plan is already shown; send a new message to plan again", so a response holding [show_plan, brief] never clears a shown plan. `TurnOutcome.coach`.
- Produces: `providers.settings_for(provider) -> ModelSettings`: for `anthropic`, `{"anthropic_cache_instructions": True, "anthropic_cache_tool_definitions": True, "anthropic_cache_messages": True}`; `{}` for the others. `run_turn` passes `model_settings=`.
- `instructions.md`: the end becomes "After `show_plan` returns "shown", reply in two lines: the plan is ready, and pressing Make the audio writes and records it." "Not in this version" drops the build and the privacy line, which the panel now shows, and keeps research beyond the feeds, health edits and a new coach.

- [ ] **Step 1: Write the failing tests:** `test_show_plan_uses_the_engines_side_rule` (the Milestone 3 side cases, unchanged, pass through `menu.side_problems`, checked by patching it to count calls). `test_equipment_line_may_name_jump_rope`. `test_show_plan_refuses_unlisted` ("pistol squats" in a dose). `test_brief_after_show_plan_in_one_response_is_refused` (a FunctionModel response holding both calls: `plan` stays set). `test_replanning_in_a_later_turn_runs_brief` (a conversation with a stored plan: the next turn's `brief` runs and clears it). `test_outcome_carries_coach`. `test_anthropic_settings_cache` (the three keys are set, and pydantic-ai accepts them: a FunctionModel run with them doesn't raise). `test_instructions_hand_over` (instructions.md names Make the audio and no longer says "a later version" about the audio).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: show_plan uses the engine's side rule; the plan carries its coach; Claude's prompts are cached`.

### Task 9: Audio storage

**Files:** Modify `pyproject.toml`, `uv.lock` (boto3), `web/webapp/config.py`, `web/webapp/api.py` (`GET /api/media/{id}`), `web/webapp/worker.py` (`main`'s sweep). Create `web/webapp/migrations/008_media.sql`. Create `web/webapp/media.py`. Test: `web/webtests/test_media.py`, `test_engine.py`.

**Interfaces:**
- Produces, in SQL: `media(id bigserial primary key, user_id uuid not null references users on delete cascade, job_id bigint references jobs on delete set null, conversation_id bigint references conversations on delete set null, object_key text unique not null, bytes bigint not null, meta bytea not null, created_at timestamptz not null default now(), expires_at timestamptz not null, deleted_at timestamptz)`, plus the index `(user_id, conversation_id)`. `meta` is sealed with AAD `f"{user_id}:media:{id}"` and holds `{"name", "seconds"}`.
- Produces: `config.Settings.bucket: media.BucketSettings | None` (`repr=False`; from `HARMONICFITNESS_BUCKET_ENDPOINT`, `_NAME`, `_REGION`, `_ACCESS_KEY_ID`, `_SECRET_ACCESS_KEY`; all or none, else `ConfigError` naming the missing one). `Settings.media_hours = 24` (`HARMONICFITNESS_MEDIA_HOURS`, 1..72).
- Produces: `media.Bucket` (Protocol: `put(key, path, content_type)`, `delete(key)`, `url(key, seconds, filename: str | None) -> str`). `media.S3Bucket(settings)` uses boto3 with path-style addressing. `media.MemoryBucket` is for tests. `media.bucket_for(settings) -> Bucket | None`. `media.upload(conn, uk, bucket, job_id, conversation_id, path, name, seconds, hours) -> Audio`: puts, inserts and commits, then deletes the object if the insert fails. `Audio(id, name, seconds, bytes, expires_at, expired)`. `media.for_conversation(conn, uk, cid) -> list[Audio]` (newest first; no commit). `media.signed(conn, uk, bucket, media_id, download: bool) -> str`: raises `LookupError` for missing or another user's media, and `media.Expired` past `expires_at`. `media.sweep(conn, bucket) -> int`: deletes objects past `expires_at`, sets `deleted_at`, and leaves a failed delete for next time. The worker's `main` calls `sweep` every `SWEEP_EVERY = 600` s between jobs, and only when a bucket is configured.
- Produces: `GET /api/media/{id}[?download=1]` returns 302 to `media.signed(..., seconds=300)` with `Cache-Control: no-store`, 404 for missing or another user's, 410 "This audio has expired.", and 503 when no bucket is configured.

- [ ] **Step 1: Write the failing tests:** `test_upload_records_and_seals` (the raw `meta` holds no name, and the object is in the memory bucket under `u/<user_id>/`). `test_other_users_media_is_404`. `test_expired_media_is_410_and_swept` (`expires_at` in the past gives 410, then `sweep` returns 1, the object is gone and `deleted_at` is set). `test_sweep_keeps_a_failed_delete` (a bucket whose `delete` raises leaves `deleted_at` null). `test_s3_presign_is_offline_and_short` (`S3Bucket.url` with fake credentials and a local endpoint gives `X-Amz-Expires=300`, and with a filename `response-content-disposition=attachment`, without any network). `test_bucket_settings_all_or_none`. `test_engine_env_is_allowlisted` gains the bucket variables in `os.environ`: none reach the engine.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Pin boto3, `uv lock`, `uv sync --extra web`.
- [ ] **Step 4:** Run the web tests and `./harmonicfitness test`. Expected: PASS.
- [ ] **Step 5: Commit** `web: MP3s in the bucket for 24 hours, behind signed links`.

### Task 10: The offer and the daily cap

**Files:** Modify `web/webapp/conversations.py` (`offer`, `coach` in the sealed body), `web/webapp/worker.py` (`_turn` makes the offer), `web/webapp/api.py` (`POST /api/conversations/{cid}/build`; `GET` shows `offer` and `audio`; the wording of a 409 while building), `web/webapp/config.py` (`daily_chars`). Create `web/webapp/migrations/009_spend.sql`. Create `web/webapp/spend.py`. Test: `web/webtests/test_spend.py`, `test_jobs.py`, `test_api.py`.

**Interfaces:**
- Consumes: `get cost` (Task 3), `get web-builds --json`, `TurnOutcome.coach` (Task 8), `media.for_conversation` (Task 9).
- Produces, in SQL: `spend(job_id bigint primary key references jobs on delete cascade, user_id uuid not null references users on delete cascade, day date not null, reserved int not null, sent int, created_at timestamptz not null default now())`, plus the index `(user_id, day)`.
- Produces: `spend.left_today(conn, user_id, day, cap) -> int` (cap minus the sum of `coalesce(sent, reserved)`). `spend.reserve(conn, uk, job_id, day, chars)` (no commit). `spend.settle(conn, job_id, sent: int)` (commits; never sets `sent` above `reserved`). `Settings.daily_chars = 60_000` (`HARMONICFITNESS_DAILY_CHARS`, 1,000..1,000,000).
- Produces: when a turn ends with a newly shown plan, `_turn` runs `get cost --coach <coach> --chars <min(ceiling, left_today)> --json` (after a first `get cost --coach <coach> --json` for the ceiling) and `get web-builds --json`, and stores `conv.offer = {"id": <16 random hex>, "coach", "service", "chars": min(ceiling, left_today), "usd", "pending_design", "design_usd", "first_web_build": bool, "day": <stem date>}`. A `get cost` failure (64, the coach can't speak here) stores no offer and adds an agent line with the engine's first line. Any later turn clears the offer.
- Produces: `POST /api/conversations/{cid}/build` with `{"offer_id", "today", "now"}` returns 202 `{"job_id"}`. In one transaction it locks the user row, checks the conversation is `idle` with that offer (else 409 "That offer has changed; look at the plan again."), checks `today` equals `offer.day` (else 409, Decisions), and recomputes `left_today` (when it's under `offer.chars`, 409 "Today's voice allowance is used up; it resets tomorrow."). It then queues `workout` with args `{"conversation_id", "stem", "coach", "allowance": offer.chars, "today", "now"}`, reserves the allowance, sets the conversation `working` with `job_id`, and clears `offer`. A message posted while a `workout` job runs is 409 "Still making your workout; it'll be ready in a few minutes." `GET /api/conversations/{id}` adds `offer` and `audio` (`media.for_conversation`, as `{"id", "name", "seconds", "expires_at", "expired"}`).

- [ ] **Step 1: Write the failing tests:** `test_turn_with_plan_stores_offer` (scripted brief and show_plan, with `get cost` from the real engine on a made Fish coach: the offer's chars are 30000 and `first_web_build` is true). `test_offer_capped_by_today` (a `spend` row of 50,000 today makes the offer 10,000). `test_build_route_needs_the_current_offer` (a wrong id, or a later turn, gives 409 and no job). `test_daily_cap_holds_under_two_posts` (two threads POST at once: one 202, one 409, one spend row, one job). `test_build_route_refuses_another_day`. `test_message_while_building_is_409_with_wording`. `test_settle_never_raises_above_reserved`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: the plan carries an offer; Make the audio reserves it against a daily cap`.

### Task 11: The writer

**Files:** Create `web/webapp/agent/writer.py`, `web/webapp/agent/writer.md`. Modify `web/webapp/agent/tools.py`. Test: `web/webtests/test_writer.py`.

**Interfaces:**
- Consumes: `Deps` and its tools (Milestone 3, Task 4), `providers.settings_for` (Task 8), `build --max-chars` (Task 3), `engine.run(cancel=)` (Task 4).
- Produces: `WriterDeps(Deps)` with `stem: str`, `coach: str`, `name: str` (`"Workout <date> <Goal> <N> min"`, from the menu's request), `allowance: int`, `sent: int = 0`, `builds: int = 0`, `lints: int = 0`, `logged: bool = False`, `sent_unknown: bool = False`, `delivered: Callable[[str], None]` (the handler's upload, Task 12) and `say: Callable[[str], None]` (a job stage).
- Produces: `WRITER = Agent(deps_type=WriterDeps, output_type=str, instructions=<writer.md>, retries=1)` with these tools, each a `tools.py` function taking the deps first. `write_draft`, `edit_draft`, `lint`, `build`, `log_session` and `content_log` are registered `sequential=True`: they use the handler's one connection (through `say` and `delivered`) and the one draft file.
  - `read_brief(section: str = "")`: `workouts/<stem>/<stem>.brief.md`'s `## ` headings when empty, else that section, cut to 20,000.
  - `movement_notes(ids: list[str])`: `movements --about <ids>` (check its exact flag form in `--help`). The ids must be on the menu.
  - `read_file` (profile, training, log), `content_plan(minutes)`, and `read_research(name: str)`: `"feeds"` reads `workouts/research/daily/<today>-feeds.md`, and a slug matching `^[a-z0-9-]{1,80}$` reads `workouts/research/reserve/<slug>.md`.
  - `write_draft(text: str)` (at most 60,000 characters, written to `<stem>.draft.txt` only) and `edit_draft(old: str, new: str)` (`old` must occur exactly once).
  - `lint()`: says `checking`, then runs `build <draft> <name> --lint-only --coach <coach> --max-chars <allowance - sent>`. Past 10 it returns 64 and does nothing.
  - `build()`: says `recording`, runs the full build with `--max-chars <allowance - sent>`, `timeout=900` and `cancel`, then adds this build's `chars_sent` to `sent` (the new `builds.jsonl` lines, through the engine's `records.parse`). A build that was cancelled or timed out (125 or 124) wrote no line, so what it sent is unknown: it sets `sent = allowance` and `sent_unknown = True`, and no further build runs in the job. On exit 0 it calls `delivered(<mp3 path>)` before returning. Past 3 builds, or with nothing left of the allowance, it returns 64 and does nothing.
  - `log_session(format: str, topics: str, loads: str)`: `log-session --draft <draft> --coach <coach> --format … --topics … --loads …`. Only once, and only after a delivered build.
  - `content_log(items: list[str])`: `content log --date <today> --item …`, each item checked by `_text`, at most 12.
- Produces: `run_writer(model, deps: WriterDeps, plan: dict, lines: list[dict], cancel) -> WriterOutcome(reply: str, usage: dict)`. The prompt is the plan as JSON, the last 20 chat lines and the allowance. It uses `WRITER_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=80, total_tokens_limit=1_500_000)` and `WORKOUT_SECONDS = 1200`, with the same cancel-token wiring as `run_turn`.
- `writer.md` ports steps 5 to 7 of the workout skill, with tool names in place of commands, and points at `knowledge/script.md` and `knowledge/tts-rules.md`. Those two are pasted in at import time, read from the engine root, so the writer never needs file access. It keeps: every movement from the menu, with its side; the opening and its safety rules; coaching from the notes; filler from the plan's slots, from the feeds sheet and the reserve only (a video deep dive becomes news or the featured article); lint until clean; then one build; the meaning of exits 1, 2, 4 and 64 for a web coach; staying within the allowance; logging with the format, topics and loads rules; recording every filler item; and a final reply naming the workout, the coach and the length, and saying the audio is kept 24 hours. It leaves out: render-ahead, local coaches, delivery folders, SendUserFile, backup and the web copy.

- [ ] **Step 1: Write the failing tests** (a FunctionModel writer on a seeded folder whose brief ran, through the real engine):
  - `test_write_lint_build_log`: the script writes a 10-minute draft of held segments (the shape of `tests/helpers.draft_with_menu`'s fixture, over the brief's menu), lints and builds against the fake Fish server with a made coach, then logs. `delivered` is called once with an existing MP3, `log.md` holds the session line, and `sent > 0`.
  - `test_write_draft_writes_only_the_draft`: no tool argument can name another path, and `edit_draft` refuses an `old` that occurs twice.
  - `test_build_cap_and_allowance`: a fourth `build` returns 64 without running the engine, and with `sent == allowance`, `build` returns 64.
  - `test_drift_rebuild_sends_only_changes`: a first build exits 2 and the writer edits one segment. The second build's `chars_sent` is below the first's (the fake server's request count rises only by the changed paragraphs).
  - `test_log_needs_a_delivered_build`: `log_session` before any build returns 64.
  - `test_writer_instructions_cover_steps_5_to_7`: `writer.md` names every tool, "allowance", and the build's exits 1, 2, 4 and 64.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: the writer: draft, lint, build within the allowance, log`.

### Task 12: The workout job

**Files:** Modify `web/webapp/worker.py` (the `workout` handler, `Ctx.checkpoint`), `web/webapp/jobs.py` (`while_running`), `web/webapp/store.py` (`versions`). Test: `web/webtests/test_workout_job.py`.

**Interfaces:**
- Consumes: Tasks 4, 5, 9, 10 and 11.
- Produces: `jobs.while_running(conn, job_id, apply: Callable[[], None]) -> bool`: `complete`'s row lock without finishing the job. It commits when the job is still running, else rolls back and returns False. `store.versions(conn, uk, paths) -> dict[str, int]`. `Ctx.checkpoint() -> bool`: `ctx.harvest()`, written back under `while_running`, then `ctx.base` moves to the new versions (`store.versions`) and `ctx.written` to the new hashes, so the final write-back sees only later changes. False when the job is no longer running (nothing written).
- Produces: `HANDLERS["workout"] = Handler(workout, ("log.md", "workouts/", "coaches/"))`. The handler:
  1. Validates the args (the same `today`/`now` rules, `stem` matching `^\d{4}-\d{2}-\d{2}-[a-z]+-\d{2}(-\d+)?$` on `today`, `allowance` 1..1,000,000), loads the conversation (`working`, its `job_id` this job), and picks the provider as `_turn` does.
  2. Says `folder` and materializes. Says `research` and runs `feeds` (`timeout=60`, `cancel`; a failure says `no_feeds` and carries on).
  3. Says `writing` and runs `run_writer`, with `delivered` doing the following: say `saving`, `media.upload` (`hours=settings.media_hours`), `ctx.checkpoint()`, then say `ready` with `media_id`.
  4. On success, saves the conversation `idle` with the reply line. On any failure, `_fail_conversation`'s pattern applies, with the line "That didn't work: <message>", plus "The audio is ready above." once a build delivered.
  5. In `finally`, runs `spend.settle(conn, job_id, deps.sent)`, unless `ctx.cancel` is set or `deps.sent_unknown`: then `sent` stays null and the whole reservation counts (as it does when the worker dies).
  6. Passes `ctx.keys` as `extra_env` to every engine call.
- Writer failures map as the turn's do. `UsageLimitExceeded` and the wall clock give "this workout ran too long; press Make the audio again to retry". `providers.explain` handles the rest. Exit 4 from a build gives the engine's first line, scrubbed ("Fish Audio refused the key…").

- [ ] **Step 1: Write the failing tests** (scripted writer, memory bucket, fake Fish server):
  - `test_workout_job_end_to_end`: the job is `done`. Events, in order: `folder`, `research`, `writing`, `checking`, `recording`, `saving`, `ready`, `saved`. One `media` row and its object. The store holds `workouts/<stem>/<name>.txt`, `<name>.build.json` and `workouts/.logs/builds.jsonl`, with `log.md` changed and no MP3. The conversation is `idle` with the reply. `spend.sent` equals the build record's `chars_sent`.
  - `test_audio_kept_when_a_later_step_fails`: the writer builds, then its next request raises `UsageLimitExceeded`. The job fails, the `media` row and the object remain, the store holds the build record (written at the checkpoint), and the conversation's line says the audio is ready.
  - `test_workout_never_writes_health_or_profile`: changes to `health.md` and `profile.md` in the folder aren't stored.
  - `test_feeds_failure_carries_on`: `feeds` patched to exit 1 still ends `done`, with a `no_feeds` event.
  - `test_reaped_mid_build_keeps_reservation`: the job is reaped during the build. The engine is killed, and `spend.sent` is null, so `coalesce` counts the reservation.
  - `test_every_engine_call_gets_the_keys`: `engine.run` is wrapped to record calls. Across a `brief`, a `turn` and a `workout` job, every call's `extra_env` holds the user's voice key variable and no model key.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run all web tests and `./harmonicfitness test`. Expected: PASS.
- [ ] **Step 5: Commit** `web: the workout job: research, write, build, upload, log, unattended`.

### Task 13: Make the audio, follow it, play it

**Files:** Modify `web/client/src/api.ts` (`Offer`, `Audio`, `api.build`), `conversation.ts` (`build`), `App.tsx`, `zones/Panel.tsx`, `zones/Chat.tsx` (a building line in place of "Thinking…"). Create `zones/Offer.tsx`, `zones/Stages.tsx`, `zones/Player.tsx` and tests beside them.

**Interfaces:**
- Consumes: the Task 10 conversation fields and route, the Task 9 media route, and `useJob`'s stages (Task 7).
- Produces:
  - **Offer** (under the plan table): "<Coach> will record it on <service>: up to N characters, at most $X." If `pending_design`: "First, <Coach>'s voice is designed and saved in your <service> account (about $D)." If `first_web_build`, the privacy line: "Your script goes to <service> to be spoken. Your language model (<provider>) has already seen your profile, health notes and log to plan it. Both keys are yours." Then "The audio is kept for 24 hours." and the **Make the audio** button, disabled while posting and gone once it's pressed. A 409's message shows in place.
  - **Stages**: the job's stages as words (Writing the script, Checking it, Recording the audio, Saving, Ready), the current one marked, and "You can close this page; it carries on." A `key_unreadable` stage shows "One of your keys can't be read; replace it in Keys."
  - **Player**: `<audio controls preload="none" src="/api/media/{id}">`, a Download link to `/api/media/{id}?download=1`, and "Available until <local time>". When expired: "This audio has expired." and no player.
  - The Offer hides with the plan when the conversation is from an earlier day (`isHistory`).
  - **Panel** order: the open question, else the plan with the Offer, Stages while a `workout` job runs, then the Player (newest audio), else the empty state.

- [ ] **Step 1: Write the failing tests:** Offer: `shows the bound and the privacy line on a first build`, `presses once` (`api.build` is called with the offer id, and the button is disabled after), `shows the design line for a pending coach`. Stages: `marks the current stage`. Player: `plays and downloads from the media route`, `says when it expired`. Panel: `shows the player after a finished workout`.
- [ ] **Step 2:** Run `npm test`. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `npm test` and `npm run build` (no warnings). Expected: PASS. Then run it locally against a local Postgres and a local S3 stand-in (MinIO in Docker, its address and keys in the `HARMONICFITNESS_BUCKET_*` variables; `web/README.md` says how), with a voice key for one service, and check the panel at 390 px and 1800 px, in light and dark.
- [ ] **Step 5: Commit** `web: Make the audio, its stages, and the player`.

### Task 14: Deploy and check it live

- [ ] **Step 1:** `web/README.md`: a "Build and delivery" section covering the offer and its allowance, `HARMONICFITNESS_DAILY_CHARS`, the bucket variables, the 24-hour expiry and sweep, the drain, and what the voice service sees (the script). `CHANGELOG.md` `[Unreleased]`: the web client builds, records and delivers. Mark Milestone 4 built in `plan.md`'s table and add "Carried into Milestone 5" from this milestone's reviews. Run `./harmonicfitness test` and `npm test`. Commit.
- [ ] **Step 2:** `docker build -t harmonicfitness-web .` succeeds. `docker run --rm harmonicfitness-web .venv/bin/python -c "import boto3"` exits 0.
- [ ] **Step 3: Railway variables** (CLI, in project `harmonicfitness-web`). No new paid service is needed: the bucket `media` exists. List its variable names without values: `railway variables --service media --kv | cut -d= -f1`. Set them on both `web` and `worker` as references: `railway variables --service web --set 'HARMONICFITNESS_BUCKET_ENDPOINT=${{media.<ENDPOINT name>}}'`, and the same for `_NAME`, `_REGION`, `_ACCESS_KEY_ID` and `_SECRET_ACCESS_KEY`, then repeat for `worker`. Check the `--set` form in `railway variables --help`. On `worker` only, set `RAILWAY_DEPLOYMENT_DRAINING_SECONDS=1500`, after checking its name and maximum in Railway's docs on deployment draining (if it's capped lower, lower `WORKOUT_SECONDS` and `DRAIN_SECONDS` to fit and commit that first). `HARMONICFITNESS_DAILY_CHARS` is left at its default.
- [ ] **Step 4:** Push `main`. Both services report `SUCCESS`, `web`'s log shows migrations 007 to 009 applied, and `/healthz` shows the new commit.
- [ ] **Step 5: The maintainer's live check (by hand, not automation):** with a Gemini model key and one voice key in Keys, plan a 10-minute bodyweight workout, read the offer (allowance, cost and privacy line), and press Make the audio. Close the tab and reopen it after a minute: the stages are still following. When it's Ready, play it on a phone and download it. Expected: every movement spoken is on the plan, the build record's `chars_sent` is at most the offer, the session is in the log (Analytics later; check with `GET /api/context` that `log.md`'s version moved), and the worker's log holds job ids only. The next day, the link says "This audio has expired." and the object is gone from the bucket (check in Railway's dashboard).

## Not in this milestone

- **Key rotation** (carried): nothing writes `key_version` after a user is created (pinned by `test_key_version_is_only_set_at_creation`, Task 6), so there's nothing to re-seal yet. It arrives with whatever first rotates a key: Milestone 7's account work, or a master-key change.
- **The check-in writing `health.md`** (carried): Task 4 lands the per-kind write rule. The write itself needs an edit tool through the engine's formats, which is Milestone 6's "Something hurts".
- **One shared async LISTEN** (carried, the alternative): Task 7 caps streams instead, which is enough for tens of users.
- **Web search, page fetches, YouTube and reserve restocking:** need each provider's native search verified in Milestone 5's eval, and outbound access to YouTube from Railway.
- **Keeping the clip cache between jobs**, a made coach's `sample.mp3` (left out by `folder.SKIP`; the coaches door in Milestone 6 decides), per-clip render progress, feedback on older workouts and the analytics views (Milestone 6), and generated instructions (Milestone 5).

## Done for Milestone 4

`./harmonicfitness test` passes, with and without the `web` extra; `npm test` and CI pass. On Railway, a signed-in user with a model key and a voice key goes from the plan to an MP3 on their phone. They press one button that named the most it could cost, and nothing they agreed to was exceeded. They can leave while it runs. The audio plays and downloads for 24 hours, then is gone. The session is in their log.

---

## Pre-flight scan

| Pair or task | Shared file or interface | Produces / consumes | Finding and ruling |
|---|---|---|---|
| 2 → 8 | `menu.side_problems`, `menu.part_of`, `"unlisted"` from `menu.mentions` | Task 2 makes them public; Task 8 imports them through `worker._engine_modules` | Task 8 relies on Task 2's wording, unchanged from Milestone 3's local copy, so Milestone 3's `test_show_plan_*` side tests carry over as they are. `_part_of` stays as an alias, so the order between the two tasks can't break the web. |
| 3 → 10, 11 | `get cost` JSON keys; `build --max-chars` | 3 makes them; 10 reads `chars/usd/ceiling/pending_design/design_usd`; 11 passes the flag | The key names match in all three tasks. Task 10's offer uses `min(ceiling, left_today)`, and Task 11 passes `allowance - sent`. They agree. |
| 1 → 10, 12 | the web-mode wording of `routes`/`cloud` errors | 1 makes it; 10 shows `get cost`'s 64 line; 12 shows exit 4's line | Both show the engine's first line, so Task 1 must land first. The order holds. |
| 4 → 5 | `Ctx.cancel`, `engine.run(cancel=)` | 4 adds them; 5's heartbeat sets `cancel` | Task 5 consumes only what 4 makes. Found: 5's test needs a handler that runs the engine, so it uses the `brief` handler with a stub engine root (`HARMONICFITNESS_ENGINE_ROOT` in `Settings.engine_root`). Noted in Task 5's test. |
| 4 → 11, 12 | `Deps.cancel`, `Handler.writes`, `Ctx.materialize/harvest`, `ctx.base/written` | 4 makes them; 11's tools pass `deps.cancel`; 12's `checkpoint` moves `ctx.base`/`ctx.written` | Found: the first draft had `checkpoint` move a `base` and `written` that the handlers held locally. Ruling: Ctx owns both (Task 4), and `checkpoint` (Task 12) updates them in place. `WriterDeps` inherits `cancel` from `Deps`. |
| 4, 5 → 12 | `WORKOUT_SECONDS` < `DRAIN_SECONDS` | 5's test walks every `*_SECONDS` cap; 11 defines `WORKOUT_SECONDS` | Found: 5's test runs before 11 exists. Ruling: the test walks the caps that exist when it runs, and when 11 adds `WORKOUT_SECONDS` to `agent.writer`, the same test covers it, since it discovers names by pattern. |
| 6, 9, 10 | migrations | 6 adds `007_damaged_keys.sql`, 9 `008_media.sql`, 10 `009_spend.sql` | Found: one file edited by three tasks would never re-apply on a developer's database that already ran it. Ruling: one migration per task, in task order. |
| 6 → 12 | `keystore.open_all` now returns a pair | 6 changes every caller; 12's handler calls `key_env` | They agree. Task 12 calls only `Ctx.key_env`, never `open_all` directly. |
| 7 → 13 | `useJob` refollowing; `GET /api/jobs/latest` | 7 makes them; 13's Stages reads `job.stages` | They agree. Found: 13 labels "Checking it", which no event carried. Ruling: the lint tool says `checking` (fixed in Task 11). Stage names in 11's and 12's events and 13's labels are `folder, research, no_feeds, writing, checking, recording, saving, ready, saved, key_unreadable`, the same list in all three. |
| 8 → 10 | `TurnOutcome.coach` | 8 adds it; 10's `_turn` reads it for `get cost` | They agree. |
| 9 → 10, 12, 13 | `media.upload`, `for_conversation`, `/api/media/{id}` | 9 makes them; 10 lists them in GET; 12 uploads; 13 plays | `Audio`'s fields (`id, name, seconds, expires_at, expired`) are the same in 9, 10 and 13. `bytes` stays server-side, not in the API. |
| 10 → 12 | `workout` args; `spend.settle` | 10 queues `{conversation_id, stem, coach, allowance, today, now}`; 12 validates those six | They agree. |
| 11 → 12 | `WriterDeps.sent`, `sent_unknown`; `spend.settle` | 11 counts sent from `builds.jsonl`; 12 settles | Found: a killed render writes no `failed` line, so settling `sent` would release billed characters. Ruling: 11 marks `sent_unknown`, and 12 skips the settle on cancel or unknown, so `coalesce` keeps the reservation. Matches `test_reaped_mid_build_keeps_reservation`. |
| 8 → 10 | `Deps.shown_this_run` vs `conv.plan` | 8 refuses `brief` after this run's `show_plan`; 10's `_turn` seeds `deps.plan` from the conversation | Found: refusing on `deps.plan` alone would block re-planning in a later turn. Ruling: the this-run flag (Task 8), pinned by `test_replanning_in_a_later_turn_runs_brief`. |
| 11 → 12 | `WriterDeps.delivered`, `say`, `sent` | 11 calls them; 12 supplies them and settles `sent` | They agree. `delivered` takes the MP3 path only. The name and length come from `<name>.build.json` (its duration field: check the mp3 shape in `tools/records.py` before naming it), which 12 reads before uploading. |
| Task 1 | | | It agrees with itself. The six message sites are listed in Files and in the test. |
| Task 2 | | | The switch phrases' scope is per segment, and the per-clause rule is stated once. They agree. |
| Task 3 | | | Found: the second test needs a set-up where the clips to send exceed the lint's count. The step says to check `render_cloud`'s arithmetic first. Kept, as a test to design, not assume. |
| Tasks 4 and 5 | | | Both agree with themselves. In 5, `GIVE_UP` (100 s) is below `jobs.reap`'s 120 s, so a job cancels before it can be reaped twice. |
| Tasks 6 and 7 | | | Both agree with themselves. |
| Task 8 | | | It agrees with itself. The instructions test checks the new ending. |
| Task 9 | | | It agrees with itself. Expired own media gives 410, another user's 404, as in Review focus. |
| Task 10 | | | Found: "any later turn clears the offer" and the 409 for a stale offer id. The two are consistent, since both make the button's offer the current one only. |
| Task 11 | | | The caps (3 builds, 10 lints, 40 requests) match the Decisions. |
| Task 12 | | | Its event order matches Task 13's labels. `settle` in `finally` matches the reservation ruling. |
| Task 13 | | | It agrees with itself. |
| Task 14 | | | It names the bucket variables only by reference, never by value, as the Global constraints require. |
