# sweatcast 10.0.0: web coaches — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. On approval, the first commit copies this file to `docs/superpowers/plans/2026-10-25-web-coaches.md`.

**Goal:** A web coach is an original voice designed at a service from the listener's description, auditioned across every keyed service, approved, named and kept; a session renders on that coach's own service. Local coaches keep working as today.

**Architecture:** Persona files gain `kind` (web | local) and a schema bump (4 → 5, migrated by `./sweatcast migrate`). Each service module in `tools/services/` exposes `design`, `save`, `delete` and `speaker`; `tools/coaches.py` gains `audition`, web `keep`, `forget-audition`, `archive`, `make`. Routing for a web coach is its service (key or stop, exit 64); a local coach renders only locally. Clip copying on the web (Fish inline clip, ElevenLabs clone, `services.json`) and Cartesia/Deepgram are removed.

**Tech Stack:** Python 3.11 stdlib (urllib via `cloud.request`), `unittest`, local fake HTTP servers (`tests/fakes.py`), ffmpeg via `tools/ffmpeg.py`.

**Spec:** `docs/superpowers/specs/2026-10-25-web-coaches-design.md` (commit db2572c), including "Decisions after the builder check". It is the source of truth; this plan only adds the builder's choices below.

## Decisions this plan adds (beyond the spec)

- **Coach Demo stays in `me.example/personas/coach-demo/`** as the local stand-in (`kind = "local"`, `placeholder = true`), beside the four web defaults (listener's answer, 2026-10-25). Only the listener's own copy is archived, in their session.
- **Four default web coaches** (all `placeholder = true`, `pending = "design"`, no `voice_id`, identical `[voice]` and `[character]`): Coach Reed (fish), Coach Ellis (elevenlabs), Coach Nolan (gemini), Coach Owen (inworld). Shared `[voice]`: who "A man in his forties, a seasoned personal trainer talking to one client"; sound "Low, warm baritone, American accent, clear diction"; energy "Steady and grounded, calm authority"; pace "Natural; brisk during work"; avoid "Hype, shouting, announcer voice, sleepy delivery". `[character]` from Coach Demo's two "How this coach talks" lines.
- **Design description sent to a service** = `personas.voice_description(voice_table)`: `"{who}. {sound}. {energy}. Pace: {pace}. Avoid: {avoid}."` (empty parts skipped).
- **Candidates per audition:** fish 2, elevenlabs 3 (all previews), gemini 1, inworld 2. Lettered A, B, C… in service order fish, elevenlabs, gemini, inworld.
- **Names at the service:** "sweatcast <coach name>" where a save step names it (Fish title, ElevenLabs voice_name, Inworld displayName). Gemini names at design time, before a name exists: `display_name = "sweatcast audition <audition id> <letter>"`; no rename.
- **Gemini cost** uses an effective rate per million characters: 13.5 for `gemini-3.8-flash-tts` (from the spec's $0.27 / 20,000 chars; comment: doubles to 27 from 2027-01-01), 9 for the Lite model. Inworld 25 (`inworld-tts-2`) and 15 (`inworld-tts-2-flash`). ElevenLabs 80 (`eleven_v4`, default) and 40 (`eleven_v4_turbo`). Fish 15 per million bytes (`s2.1-pro`).
- **Pace estimate from the sample** is in `voices.weight` units (char_weight), not raw characters: `weight(line) / trimmed_seconds`, stored as `{"name","weight","seconds","estimate": true}` under the coach's rate key. `voices.pace()` returns an estimate record's rate (with `measured=False`) instead of the seed; the first real `record_rate` replaces an estimate rather than adding to it.
- **Web identity key** = `sha256(f"{service}|{voice_id}|{model}|{style}|{json.dumps(settings, sort_keys=True)}")[:12]`, `settings` = the persona's optional `[settings]` table (default `{}`). It is `voice["key"]` for cache and pace.
- **Exit codes:** web coach whose service has no key here → 64 from `get route` and `build`; `--engine` naming another service for a web coach → 64. A local coach on a cloud route → not usable ("a local coach renders only locally").
- **Default coach** (`personas.default()`): last coach in the log if active; if that name is archived, stop ("Coach Julius is archived; name a coach: …"); else the first non-placeholder; else the first placeholder usable here (web defaults whose key is set, then Coach Demo when local works); else the first.
- **Archive lookup:** `personas.lookup(name, archived=False)`; code that reads names from the log (log-session validation, coverage, `default()`) passes `archived=True`; `all()` skips every dot folder.
- **Backup:** `me/.gitignore` gains `!personas/*/sample.mp3` and `personas/.auditions/`; migrate appends them to an existing one.
- **v8 clips:** `tools/migrate-assets/` is removed; `migrate._v8_voice` reads `me/voices/` then `git show v8.0.1:` (existing `_from_git`). Tests read the tag and skip without it (CI has `fetch-depth: 0`).

## Global Constraints

- Never read, print or copy `me/.env`. Live calls get keys only through `keys.get()` / `cloud.key_or_stop()`. No tool prints a key; the existing "key never reaches records, logs or cache keys" test extends to the new services.
- Service facts (verbatim from the live probes):
  - Fish design `POST /v1/voice-design`, header `model: voice-design-1`, JSON `{"instruction", "reference_text", "language": "en", "n"}`; candidates have `audio_base64`, `text`, `signature`. Save `POST /model` multipart: `visibility=private`, `type=tts`, `title`, `train_mode=fast`, `texts=<candidate text>`, `voice_design_signatures=<signature>`, file `voices=<candidate WAV>`; 201 with `_id`, `state: trained`. Speech `POST /v1/tts`, header `model: s2.1-pro`, JSON `{"text", "reference_id", "format": "wav", "sample_rate": 24000}`.
  - ElevenLabs design `POST /v1/text-to-voice/design` (three previews, `generated_voice_id`); save `POST /v1/text-to-voice` with `voice_name`, `voice_description`, `generated_voice_id`; speech by voice ID with seed and `previous_text`/`next_text`; models `eleven_v4`, `eleven_v4_turbo`. Labeled "not yet tried on a Free account" with Free's 3-voice limit and monthly allowance.
  - Gemini design `POST /v1beta/voices` `{"voice": {"type": "prompted", "display_name", "prompted": {"input": <description>}}, "store": true}` — no other fields inside `prompted`; response `id`, `sample_audio {mime_type, data}`, `expire_time`. Speech `POST /v1beta/interactions` `{"model": "gemini-3.8-flash-tts", "input": [{"type": "text", "text"}], "response_modalities": ["audio"], "generation_config": {"speech_config": [{"voice": id}]}}`; find the base64 audio by searching the response for a `data` string. Header `x-goog-api-key`. Never put style in the text. `style` is sent only when non-empty, in the shape the Task 0 probe confirms.
  - Inworld design `POST /voices/v1/voices:design` `{"designPrompt", "previewText", "languageCode": "EN_US", "numberOfSamples"}` → `previewVoices[].voiceId` + base64 audio; publish `POST /voices/v1/voices/{voiceId}:publish` `{"displayName", "description", "tags": ["sweatcast"]}`; speech `POST /tts/v1/voice` `{"text", "voiceId", "modelId", "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 24000}}` → `audioContent`. Header `Authorization: Basic <key as given>`. 2,000 characters a request; design 2 a minute.
- Keys: `FISH_AUDIO_API_KEY`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `INWORLD_API_KEY`. Hosts: `api.fish.audio`, `api.elevenlabs.io`, `generativelanguage.googleapis.com`, `api.inworld.ai`.
- `knowledge/services.toml`: `rates_checked = "2026-10-25"`; `tried_live = true` for all four; concurrency fish 5, elevenlabs 2, gemini 2, inworld 5; `max_chars` inworld 2000, elevenlabs 10000, others 0.
- Coaching line: `voices.DESIGN_LINE` ("Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. Breathe out as you drive. That's the pace we want.").
- Words: "local coach" and "web coach", never "Mac coach". Every `./sweatcast <cmd>` named in skills, README, CLAUDE.md, `knowledge/voices.md` must exist in `sweatcast.COMMANDS` (`tests/test_setup.py` `test_skills_name_only_current_commands`).
- Work on main, commit per task, `./sweatcast test` green before each commit. Ask before pushing.

## Review Focus

1. **An existing coach at persona schema 4** (the listener's Julius/Solo, a fork's coaches) must still be readable after `./sweatcast migrate`, and before it the error names `./sweatcast migrate` (Task 1 `test_schema_4_persona_says_migrate`, `test_migrate_adds_kind_to_every_persona_including_archive`).
2. **The log's last coach is archived** (the listener's state right after release): a build with no coach named stops with a list of the stable, never silently picks another (Task 1 `test_default_stops_when_last_coach_is_archived`).
3. **One service fails during an audition** (no credit, 429 past retries, a 500): the others' candidates still land and the failure is one plain line (Task 5 `test_audition_survives_one_service_failing`).
4. **A web coach on a computer without its key, or with `--engine` naming another service**: exit 64 with a reason, nothing sent (Task 4 `test_web_coach_without_key_exits_64`, `test_engine_override_on_web_coach_exits_64`).
5. **First build with a pending default coach**: designs once, says so first, and a second build doesn't design again; an interrupted design leaves the coach pending, not half-written (Task 6 `test_pending_default_is_made_once`, `test_failed_make_leaves_coach_pending`).

---

### Task 0: Live probe of the unverified shapes, and plan copy

**Files:**
- Create: `docs/superpowers/plans/2026-10-25-web-coaches.md` (this plan)
- Scratch only: a probe script in the session scratchpad (never in the repo), using `sys.path.insert(0, "tools"); import keys` and `keys.get(service)`.

- [ ] **Step 1:** Copy this plan to `docs/superpowers/plans/2026-10-25-web-coaches.md`; commit "Plan: web coaches for 10.0.0".
- [ ] **Step 2:** Probe, one call each, printing only status and field names (never keys, never full bodies): Inworld design's audio field name (`previewAudio` or `audioContent`); Inworld `synthesisContext.previousRequests` accepted on speech (and its shape); delete endpoints — Fish `DELETE /model/{id}`, ElevenLabs `DELETE /v1/voices/{id}`, Gemini `DELETE /v1beta/voices/{id}`, Inworld `DELETE /voices/v1/voices/{id}`; Gemini `style` placement (try `speech_metadata: {"style": ...}` as the spec names it; record where it's accepted, or that it isn't); ElevenLabs design → save on Starter, and that a `generated_voice_id` still saves after 10 minutes. Delete every voice the probe made. Cost: a few cents.
- [ ] **Step 3:** Write the results into the Task 3 notes below (edit this plan file in the repo copy) and commit. Anything refused is left out of the code (e.g. no `previousRequests`, no `style` field) and noted in `knowledge/voices.md` in Task 8.

### Task 1: Persona model, schema 5, archive, migration

**Files:**
- Modify: `tools/context.py` (`PERSONA_SCHEMA = 5`, `persona()` message, `PERSONA_COMMENTS`, `check_coaches` web branch), `tools/personas.py`, `tools/migrate.py`, `me.example/.gitignore`, all persona fixtures (`tests/fixtures/personas/coach-test`, `tests/fixtures/listener/personas/*`, `me.example/personas/coach-demo`) to `schema = 5`, `kind = "local"`.
- Test: `tests/test_personas.py`, `tests/test_migrate5.py`

**Interfaces:**
- Produces: `Persona.kind -> str` ("web" | "local", default "local"), `.service`, `.voice_id`, `.model` (str | None), `.style` (str, ""), `.pending` (str | None), `.voice` (dict, `[voice]`), `.character` (dict), `.sample` (path to `sample.mp3`), `.is_web -> bool`; `personas.voice_description(voice: dict) -> str`; `personas.web_key(p, model: str) -> str`; `personas.lookup(name, folder=None, archived=False)`; `personas.archive(p) -> str` (new folder); `personas.ARCHIVE = <PERSONAS>/.archive`, `personas.AUDITIONS = <PERSONAS>/.auditions`; `context.persona_text` writes `[voice]`/`[character]` tables with list values.

- [ ] **Step 1: Failing tests** in `tests/test_personas.py`:
  - `test_web_persona_fields`: a schema-5 web persona.md (the spec's Coach Maya example) loads with `kind == "web"`, `service == "inworld"`, `character["signature"] == ["Stay with it.", "That's the pace we want."]`; `persona_text` round-trips it (tomllib-equal).
  - `test_voice_description_joins_the_voice_table`: Maya's `[voice]` → `"A woman in her thirties, a strength coach. Warm, mid-low, American accent, crisp diction. Steady, calm authority. Pace: Natural; brisk during work. Avoid: Hype, shouting, announcer voice, sleepy delivery."`
  - `test_web_key_changes_with_voice_id_model_and_style`, and is 12 hex chars.
  - `test_all_skips_dot_folders`: `.archive/x/persona.md` and `.auditions/y/persona.md` are not listed.
  - `test_archived_coach_found_only_when_asked`: `lookup("Coach Julius")` raises SystemExit after `archive`; `lookup(..., archived=True)` finds it.
  - `test_default_stops_when_last_coach_is_archived`: log's last session names an archived coach → SystemExit whose message lists the active coaches.
  - `test_default_prefers_a_usable_web_default`: only placeholders, `GEMINI_API_KEY` set, local not usable → Coach Nolan; non-placeholder present → it wins (update `test_default_prefers_non_placeholder`).
  - `test_schema_4_persona_says_migrate`: a schema-4 persona.md → SystemExit containing `./sweatcast migrate`.
  - `test_check_web_coach`: a web coach with no `voice_id` and no `pending` is an issue; `pending = "design"` is a note; no clip issue for web.
  - In `tests/test_brief.py`, `test_brief_quotes_the_character_table`: for a web coach the brief's coach lines include each `[character]` entry (`- Calls you: Ritujoy`, lists joined with "; ") followed by the prose's `- Key: value` lines, as `brief._coach_lines` does today (modify `tools/brief.py`).
- [ ] **Step 2:** In `tests/test_migrate5.py`: `test_migrate_adds_kind_to_every_persona_including_archive` (schema-4 personas in `personas/` and `personas/.archive/` become `schema = 5` + `kind = "local"` by a text edit that keeps comments and prose byte for byte otherwise; context files already at 5 still trigger it; a second run says nothing to do) and `test_migrate_adds_the_sample_and_audition_ignore_rules`.
- [ ] **Step 3: Run** `./sweatcast test` → new tests fail.
- [ ] **Step 4: Implement.** Migration is a text step: insert `kind = "local"` after the `schema = 4` line and change it to `schema = 5`; `plan()` lists persona files below the context files; backup as today. Bump every fixture.
- [ ] **Step 5: Run** `./sweatcast test` → all pass. **Commit** "Coach files at schema 5: kind, web fields, archive".

### Task 2: Routes, keys, services.toml, doctor

**Files:**
- Modify: `tools/routes.py`, `tools/keys.py`, `tools/context.py` (`ROUTE_NAMES`, `get route` exit 64 for web), `tools/doctor.py` (`web_lines`), `knowledge/services.toml`, `tools/sweatcast.py` if `keys open` needs listing.
- Test: `tests/test_routes.py`, `tests/test_keys.py`, `tests/test_setup.py` (CloudSession doctor lines)

**Interfaces:**
- Produces: `routes.ROUTES == ("local", "fish", "elevenlabs", "gemini", "inworld")`; `routes.pick(preferences, persona=None, override=None, facts=None) -> str` — for `persona.is_web` returns `persona.service` when keyed, else `SystemExit` (`routes.WebCoachUnavailable(SystemExit)` so `get route` can map it to 64); `keys.SERVICE_VARS` with gemini → `GEMINI_API_KEY`, inworld → `INWORLD_API_KEY`; `keys.open_env(path=None, run=subprocess.Popen) -> list[str]` (argv used); services.toml fields `name, url, key_var, default_model, models, unit, usd_per_million, concurrency, max_chars, tried_live, design_usd` (float or absent = unpublished), `note` (optional), with `copies_clip`, `designs`, `stock_voices` gone.

- [ ] **Step 1: Failing tests:**
  - `test_routes.py`: `test_web_coach_routes_to_its_service_whatever_the_render_list`; `test_web_coach_without_key_says_which_key` (message names `INWORLD_API_KEY` and `keys init inworld`); `test_engine_override_naming_another_service_is_refused`; `test_local_coach_renders_only_locally` (render `["fish"]`, local coach → not usable, message says "local coach"); `test_hosts` gains gemini → `generativelanguage.googleapis.com`, inworld → `api.inworld.ai`; delete `test_deepgram_needs_a_stock_voice`.
  - `test_keys.py`: `test_keys_lists_four_services`; `test_keys_open_uses_the_system_editor` (darwin → `["open", "-e", path]`, win32 → `["notepad", path]`, linux → `["xdg-open", path]`; creates the file via `init`'s header if missing; never opens it for reading — patch `keys._read` to raise); `test_keys_open_on_the_web_points_to_settings`; replace the deepgram case in `test_init_keeps_what_is_there`.
  - `test_cloud.py` `test_services_settings`: set == {fish, elevenlabs, gemini, inworld}, `rates_checked == "2026-10-25"`, all `tried_live`, elevenlabs has a `note` containing "Free".
  - Doctor: web key line names the four vars; network line lists the four hosts.
- [ ] **Step 2: Run** → fail. **Step 3: Implement** (services.toml values per Global Constraints). `context.py get route` returns 64 on `WebCoachUnavailable`.
- [ ] **Step 4: Run** `./sweatcast test` → pass (cloud service tests for removed services are deleted in Task 3; skip-mark them here if they break, removed next task). **Commit** "Routes and keys: Gemini and Inworld in, Cartesia and Deepgram out".

### Task 3: Service modules: design, save, delete, speech by saved voice

**Files:**
- Modify: `tools/services/fish.py`, `tools/services/elevenlabs.py`, `tools/cloud.py` (`voice_for` web-only; remove `cloned_voice`), `tools/personas.py` (remove `services_*`, `clip_hash` if unused, `stock_only`)
- Create: `tools/services/gemini.py`, `tools/services/inworld.py`
- Delete: `tools/services/cartesia.py`, `tools/services/deepgram.py`
- Test: `tests/test_cloud.py` (classes `Fish`, `ElevenLabs`, `Gemini`, `Inworld`; delete `Cartesia`, `Deepgram`)

**Interfaces:**
- Consumes: `cloud.request`, `cloud.audio_pcm`, `cloud.multipart`, `cloud.key_or_stop`, `cloud.base_url`; `personas.web_key`.
- Produces, in every `tools/services/<svc>.py`:
  - `design(description: str, line: str, n: int, label: str) -> list[dict]`, each `{"pcm": bytes (16-bit mono 24 kHz), "wav": bytes, "text": str, "draft_id": str | None, "signature": str | None}` (`label` is Gemini's display name; others ignore it).
  - `save(candidate: dict, name: str, description: str, wav: bytes) -> str` (voice ID; Gemini returns `candidate["draft_id"]`).
  - `delete(voice_id: str) -> bool` (False where the API has none, per Task 0).
  - `speaker(voice) -> say(text, seed, previous_text=None, next_text=None) -> bytes`.
- `cloud.voice_for(p, route)` for a web coach: `{"name", "persona", "persona_dir", "engine": service, "backend": "cloud", "route": service, "service", "model", "voice_id", "style", "revision": None, "generate": {}, "pace_file", "concurrency", "max_chars", "key": web_key}`; no `ref_audio`.
- Task 0 results: _(filled in at Task 0 step 3)_

- [ ] **Step 1: Failing tests** (FakeService per service, URL via `SWEATCAST_<SVC>_URL`, key via env):
  - Fish: `test_fish_speaks_by_reference_id` (JSON body with `reference_id`, header `model: s2.1-pro`, no `references`); `test_fish_design_keeps_signature_and_wav`; `test_fish_save_posts_multipart_private_model` (fields as in Global Constraints; returns `_id`); `test_fish_402_is_billing` kept.
  - ElevenLabs: `test_elevenlabs_design_returns_three_with_generated_ids`; `test_elevenlabs_save_posts_generated_voice_id`; `test_elevenlabs_sends_neighbors_and_seed` kept against a saved voice ID; no clone request ever (`/v1/voices/add` never hit).
  - Gemini: `test_gemini_design_body_has_only_input_in_prompted`; `test_gemini_speech_finds_audio_anywhere_in_the_answer` (audio nested two levels deep); `test_gemini_text_is_sent_verbatim` (no style words added to `text`); `test_gemini_delete`.
  - Inworld: `test_inworld_basic_auth_as_given`; `test_inworld_design_then_publish`; `test_inworld_linear16_24k`; `test_inworld_refuses_a_paragraph_over_2000_characters`.
  - `test_key_never_reaches_records_logs_or_cache_keys` extended to gemini and inworld.
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** Reuse `cloud.request` retries; Inworld design waits through 429 via `Retry-After`.
- [ ] **Step 4: Run** `./sweatcast test` → pass. `grep -rn "cartesia\|deepgram\|cloned_voice\|services_get" tools tests` → nothing. **Commit** "Web services design, save and speak by saved voice; Cartesia and Deepgram removed".

### Task 4: Render and build for web coaches

**Files:**
- Modify: `tools/build.py` (no exit 3 for web; 64 from `get route`), `tools/voices.py` (estimate records), `tools/coaches.py` (`measured` OK for a web coach), `tools/tts_build.py`/`tools/brief.py` only if they assume `ref_audio`.
- Test: `tests/test_cloud.py` (`CloudRender`), `tests/test_personas.py`, `tests/test_tools.py`

**Interfaces:**
- Produces: `voices.record_estimate(v, weight: float, seconds: float) -> None`; `voices.pace(v)` returns an estimate's rate with `measured=False`; `record_rate` replaces an `estimate` record.

- [ ] **Step 1: Failing tests:** `test_estimate_is_used_until_the_first_render` (pace from the estimate, not the seed; after `record_rate` with 40 s the estimate flag is gone and only measured data remains); `test_web_coach_builds_without_smoke_test` (build of a draft with a web coach that has only an estimate goes past the measured check: no exit 3); `test_web_coach_without_key_exits_64`; `test_engine_override_on_web_coach_exits_64`; `test_web_render_sends_voice_id_and_caches_by_web_key` (render a two-paragraph draft on the fake Fish; second run sends nothing); `test_cost_print_for_gemini` (uses the effective rate).
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass. **Commit** "Builds render a web coach on its own service".

### Task 5: Coaches CLI: audition, keep, forget-audition, archive, list

**Files:**
- Modify: `tools/coaches.py` (`DESIGNERS = ("local",)`; remove `samples`; add subcommands), `tools/sweatcast.py` (help text)
- Test: `tests/test_personas.py` (class `Auditions`)

**Interfaces:**
- Consumes: Task 3's `design/save/delete`, `personas.voice_description`, `voices.record_estimate`, `tools/ffmpeg.py`.
- Produces:
  - `coaches.audition(narrative: str, services: list[str] | None = None, coach: str | None = None) -> str` (audition folder). Folder `me/personas/.auditions/<YYYY-MM-DD>-<n>/` with `narrative.md` (copy), `<service>-<k>.wav`, `<service>-<k>.mp3` (mono 48 kbps), `candidates.json` = list of `{"letter", "service", "k", "draft_id", "signature", "text", "wav", "mp3", "usd_per_workout", "design_usd", "note"}`. Services in parallel (thread pool); prints one line per candidate: `B  ElevenLabs  about $1.60 a workout  <path>.mp3  (not yet tried on a Free account; Free keeps 3 voices)`. Gemini speaks `DESIGN_LINE` once after design so every candidate says the same line. With `coach`, only that coach's service and its own persona.md as the narrative.
  - `coaches.keep_web(ref: str, name: str | None, replace_old: bool = False) -> str` (persona folder). `ref` is `<audition>/<letter>` or `<audition>/<service>-<k>`. Saves at the service as "sweatcast <name>", writes `persona.md` (narrative's `[voice]`, `[character]`, prose + `kind`, `service`, `voice_id`, `made`), `sample.mp3`, and the pace estimate. With an existing coach of that name (re-voice): replaces `voice_id` and `sample.mp3`, drops pace records under the old key, and with `replace_old` deletes the old voice at the service.
  - `coaches.forget_audition(audition: str) -> list[str]` (lines said): deletes Gemini candidates not kept, removes the folder, says plainly that unsaved Fish/ElevenLabs/Inworld drafts need nothing.
  - `coaches.archive(name: str) -> str`.
  - CLI: `coaches audition <narrative> [--services fish,gemini] [--coach <name>] [--play]`, `coaches keep <audition>/<letter> --name "<name>" [--replace-old]` (a path to a take/clip still goes to today's local `keep`), `coaches forget-audition <audition>`, `coaches archive <name>`, list shows `web · Inworld` or `local · chatterbox`.
- [ ] **Step 1: Failing tests:** `test_audition_makes_lettered_candidates_from_every_keyed_service` (fakes for all four; 8 candidates A–H; no save request sent; Gemini sent one design and one speech); `test_audition_survives_one_service_failing`; `test_audition_only_named_services`; `test_keep_saves_and_writes_the_coach` (persona.md fields, sample.mp3 exists, pace estimate present, service got one save with title "sweatcast Coach Maya"); `test_keep_two_from_one_audition`; `test_revoice_replaces_voice_and_clears_old_pace`; `test_forget_audition_deletes_unkept_gemini_only`; `test_archive_moves_and_lists_without_it`; `test_list_shows_service`; `test_keep_refuses_an_existing_name_without_coach_revoice`.
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass. **Commit** "Coaches: audition, keep, forget-audition, archive".

### Task 6: Default web coaches, made on first use

**Files:**
- Create: `me.example/personas/coach-reed/persona.md`, `coach-ellis/`, `coach-nolan/`, `coach-owen/` (values in "Decisions")
- Modify: `tools/coaches.py` (`make`), `tools/build.py` (calls `coaches.py make` before the lint when the coach is pending), `me.example/profile.md` (render comment: local engines only; drop cartesia/deepgram), `tests/fixtures/listener/profile.md`, `docs/eval/listeners/*/profile.md` (comment only)
- Test: `tests/test_personas.py`, `tests/test_tools.py` (`FreshFork`), `tests/test_setup.py`

**Interfaces:**
- Produces: `coaches.make(name: str) -> str` (voice ID): prints first "Coach Reed is made the first time it's used: designing a voice at Fish Audio from its description (about $0.01)."; designs with n=1, saves the first candidate, writes `voice_id`, `made`, `sample.mp3`, pace estimate, removes `pending` — persona.md written last, atomically. CLI `coaches make "<name>"`.

- [ ] **Step 1: Failing tests:** `test_four_defaults_share_one_description` (same `[voice]` and `[character]`, one per service, all placeholder + pending); `test_pending_default_is_made_once` (build twice against fakes: one design and one save in total); `test_failed_make_leaves_coach_pending` (save returns 500 → persona.md unchanged); `FreshFork.test_example_context_works` expects `[".gitkeep", "coach-demo", "coach-ellis", "coach-nolan", "coach-owen", "coach-reed"]`; Coach Demo tests updated to `kind == "local"`.
- [ ] **Step 2: Run** → fail. **Step 3: Implement.** **Step 4: Run** → pass. **Commit** "Four default web coaches, designed on first use".

### Task 7: Remove the v8 migration assets

**Files:**
- Delete: `tools/migrate-assets/`
- Modify: `tools/paths.py` (drop `V8_VOICES`), `tools/migrate.py` (`_v8_voice` reads `me/voices/` then `_from_git`), `tests/test_migrate4.py`, `tests/test_personas.py` (`test_local_model_pins_match_the_shipped_voices`)
- Test: same

- [ ] **Step 1:** Add a test helper `v8_file(stem, ext) -> bytes` (`git show v8.0.1:voices/<stem><ext>`); the three `test_migrate4.py` uses and the personas pin test read through it, with `skipUnless(tag v8.0.1 exists)`.
- [ ] **Step 2:** Delete the folder and `V8_VOICES`. **Run** `./sweatcast test` → pass (and the migrate4 tests ran, not skipped, here). **Commit** "Remove tools/migrate-assets (v8 clips come from the v8.0.1 tag)".

### Task 8: Skills, docs, release notes

**Files:** `.claude/skills/coach/SKILL.md`, `.claude/skills/setup/SKILL.md`, `.claude/skills/workout/SKILL.md`, `knowledge/voices.md`, `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`, `tools/migrate-assets`-free mentions.

- [ ] **Step 1: Coach skill** rewritten around keys → describe → audition → approve and name → stable (web coaches), with the quick coach as: one sketch question → narrative file in `me/personas/.auditions/` → `coaches audition` → send candidates by letter and per-workout cost (SendUserFile, else `--play`, else paths) → `keep` each approved one → `forget-audition`. Re-voicing: `audition --coach`, ask before `--replace-old`. Tweaking how they talk: edit `[character]`, no cost. The local path's text kept under "Local coaches (unchanged until the local redesign)", minus Fish/ElevenLabs design and Deepgram.
- [ ] **Step 2: Setup skill:** keys step (`./sweatcast keys`; with none, the four services with a line each on cost and what's needed; `keys init <service>` then `keys open` on a computer; environment settings on the web); privacy line gains Gemini's free-tier training and that every service receives the script, which can mention injuries; quick start uses the default web coach of the keyed service (first build makes it, said first), or Coach Demo on local; audition offered after, never required.
- [ ] **Step 3: Workout skill:** pick a coach from `./sweatcast coaches` by name; exit 64 for a web coach without its key → offer the coaches whose service works here; archived last coach → offer the stable; exit 3 only for local coaches; pending default → say "made the first time, about $0.01" before the build.
- [ ] **Step 4: `knowledge/voices.md`** web half rewritten from the spec's services table (plus Task 0 findings); clip-copying, Cartesia, Deepgram text removed; Coach Demo described as the local stand-in. **README, CLAUDE.md:** coaches, routes, files and Audio paragraphs; Cartesia, Deepgram, OpenAI, `migrate-assets` removed; new commands named.
- [ ] **Step 5: CHANGELOG** `## [10.0.0] - 2026-10-25` with summary, `### For forks` (run `./sweatcast migrate`: coach files go to schema 5 with `kind = "local"` and two ignore rules; Cartesia and Deepgram coaches render locally, or make a web coach with an audition; a clip-based coach now renders locally only; four default web coaches arrive only with a new `me/` — copy `me.example/personas/coach-{reed,ellis,nolan,owen}/` to have them; a v8 folder migrates only from a git clone with the v8.0.1 tag; `render` lists order local engines only; a customized coach/setup/workout skill needs merging), `### Added`, `### Changed`, `### Removed`. `VERSION` and `pyproject.toml` → 10.0.0.
- [ ] **Step 6: Run** `./sweatcast test` and `./sweatcast check` on `me.example` (fresh copy) → pass. **Commit** "Skills and docs for web coaches; 10.0.0".

### Task 9: Live rehearsal, then release

- [ ] **Step 1:** Migrate the listener's real `me/` (`./sweatcast migrate`, backup made); `./sweatcast check` clean except expected notes; `./sweatcast keys` shows the four set.
- [ ] **Step 2:** Live audition with a throwaway narrative across all four (cost printed first, a few cents); keep one Fish candidate as "Coach Rehearsal"; build `knowledge/smoke-test.draft.txt` with it (no exit 3; MP3 made); `forget-audition`; delete Coach Rehearsal's voice at Fish and its folder. List anything that couldn't be deleted.
- [ ] **Step 3:** Request a whole-branch code review (superpowers:requesting-code-review) and fix what holds up.
- [ ] **Step 4:** Commit, tag `git tag -a v10.0.0 -m "sweatcast 10.0.0: web coaches"`. **Ask the listener before pushing.** On yes: `git push --follow-tags`, `gh release create v10.0.0 --notes-file <the 10.0.0 section>`.
- [ ] **Step 5 (listener's session):** `./sweatcast coaches archive "Coach Julius"`, `"Coach Solo"`, `"Coach Demo"`; offer an audition for the first web coach; ask before deleting the probe leftovers: Gemini `voice_j84pg40buem8`; Fish private model `fc2a4741ef7740e59e2cfcfd34f6c34e`; Inworld "sweatcast probe coach" and drafts in workspace `funky-finch-6967`; ElevenLabs clone "sweatcast Coach Julius". Update the memory notes (cloud-voice-plans).

## Verification

- `./sweatcast test` after each task (CI runs the same on push with Python 3.11).
- Fake-server tests cover every request shape; Task 0 and Task 9 confirm them live with the listener's keys through the engine's own key loader.
- End to end: Task 9 step 2 (audition → keep → build smoke test → cleanup) on the real `me/`, then a fresh copy of `me.example` with only a Fish key: `./sweatcast build` of a ten-minute draft with no coach named picks Coach Reed, makes it once, renders.
