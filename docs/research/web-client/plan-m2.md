# Web client, Milestone 2: engine web mode and voice keys

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The engine gains a web-client mode (`HARMONICFITNESS_WEB=1`), and a signed-in user can store a key for each web voice service in the app (encrypted, never shown again), which the worker passes only into a job's engine environment.

**Architecture:** Engine: a new flag `paths.WEB`, separate from Claude Code on the web's `paths.REMOTE`, that turns local voices off, points every "add a key" message at the app's settings, never falls back to a local stand-in coach, and records a finished MP3 as kept for the web client to upload. Web: a `user_keys` table (one sealed row per user and service), `GET/PUT/DELETE /api/keys` routes that seal and never open, a worker that opens a user's keys for a job and passes them as the engine's own key variables, and a Keys box in the context column.

**Tech stack:** as Slice 1 (`plan.md`): Python 3.11, FastAPI, psycopg 3, `cryptography` AES-GCM; React + TypeScript, vitest. No new dependencies.

**Spec:** `docs/research/web-client/design.md` (Keys; Engine changes this needs; Per-user isolation). Outline: `plan.md`, "Milestone 2 in outline". Built on what Slice 1 shipped (through `3dcdc94`).

## Global constraints

Everything in `plan.md`'s Global constraints holds. In particular:
- The engine change is a general feature with engine tests, and changes no CLI behaviour when `HARMONICFITNESS_WEB` is unset.
- Keys are stored sealed with the user's data key; plain columns hold only ids, the service name and timestamps.
- Keys are decrypted only inside the worker, only for a job, and passed only into the engine's environment. The web process seals a key on entry and never opens one.
- Nothing is retried automatically after it may have reached a paid service. Milestone 2 never calls a voice service: no live key check.
- The services and their variable names come from the engine's `knowledge/services.toml` (`tools/services/__init__.py`'s `settings()`: `name`, `key_var`, `key_page`), never a list in `web/`.
- No release level is set here: the maintainer decides (0.20.0 is tagged; changes go under a new `## [Unreleased]` section of `CHANGELOG.md`).

## Decisions this plan makes

- **`paths.WEB` beside `paths.REMOTE`, not instead.** Each `paths.REMOTE` site is decided below; where both apply, the web client's wording wins only in WEB mode. `find_home`'s REMOTE branch is untouched: the worker always sets `HARMONICFITNESS_HOME`.
- **Default coach in WEB mode** with no key at all: the first stock web coach in `services.toml` order (Coach Reed today), never a local stand-in. Its brief then quotes its `[character]`, and `brief.talk_rate` falls back to that coach's estimated pace on its own service (today it tries `local`, which fails for a web coach, and prints no rate).
- **Delivery in WEB mode:** no web copy unless `--web` is given; no delivery folders read; the record says `kept_local: true`, reason `"the web client uploads the MP3"`. Milestone 4 does the upload.
- **Every job gets the user's keys,** brief included: the brief names the default coach, which depends on which services have a key (`coachpick._usable_here` calls `keys.is_set`).
- **A key is checked at entry by the engine's own rule** (`keys.clean_value`, public from Task 1): stripped; refused if it holds whitespace or anything outside printable ASCII; at most 1024 characters.
- **`HARMONICFITNESS_WEB=1` is set by `engine._env` for every job**, not passed through `extra_env` (the secrets channel, whose values are scrubbed from output).
- **A key replaced while a job runs:** that job keeps the key it started with; the next job gets the new one. Not a bug.
- **Language-model keys** (Claude, OpenAI, Gemini) wait for Milestone 3; the table takes them then as more `service` values.

## Review focus

1. **A new web user with no keys asks for a brief.** Expected: the brief runs, names a stock web coach (not Coach Andy) and its estimated pace. Pinned by `test_web_default_is_a_web_stand_in` (Task 2) and `test_talk_rate_web_coach_without_key` (Task 2).
2. **A key pasted with a trailing newline, or a space inside.** Expected: the newline is stripped and the key saved; one with a space inside is refused with 400 naming the service, never echoing the value. Pinned by `test_put_key_strips_and_refuses` (Task 4).
3. **A key reaching stored job output.** The engine prints a key to stderr and fails. Expected: the job's sealed detail holds `<key>`, never the value. Pinned by `test_key_in_engine_output_is_scrubbed` (Task 5).
4. **One user's request touching another's key.** Expected: user B's `GET /api/keys` shows nothing user A set, and B's `DELETE` leaves A's row. Pinned by `test_keys_are_per_user` (Task 4).
5. **The web process opening a key.** Expected: `webapp/api.py` never calls `keystore.open_all`, and `GET /api/keys` returns no value field. Pinned by `test_api_never_opens_keys` (Task 4).

---

## File map

```
tools/paths.py              modify: WEB
tools/doctor.sh             modify: read HARMONICFITNESS_WEB; local off; a web= fact
tools/keys.py               modify: clean_value public; init/open in WEB mode
tools/routes.py             modify: missing_key, way_out wording in WEB mode
tools/coaches.py            modify: download refused in WEB mode
tools/coachpick.py          modify: default's last fallback in WEB mode
tools/brief.py              modify: talk_rate fallback for a web coach
tools/build.py              modify: no web copy, no folders, delivery_plan(client=)
tests/test_setup.py, test_keys.py, test_routes.py, test_stock.py, test_brief.py, test_integrity.py
CLAUDE.md, CHANGELOG.md     modify
web/webapp/migrations/005_user_keys.sql
web/webapp/keystore.py      new: put, delete, listing, open_all
web/webapp/worker.py        modify: engine_services; keys into each job's env
web/webapp/engine.py        modify: HARMONICFITNESS_WEB=1 in every run
web/webapp/api.py           modify: /api/keys routes
web/webtests/test_keystore.py (new), test_api.py, test_jobs.py, test_engine.py
web/client/src/api.ts, zones/ContextColumn.tsx, zones/KeysBox.tsx (new), zones/KeysBox.test.tsx (new), theme.css
web/README.md
```

---

### Task 1: Engine web mode: the computer and the keys

**Files:**
- Modify: `tools/paths.py:16`, `tools/doctor.sh:81-129`, `tools/keys.py:64-70,145-175`, `tools/routes.py:36-46,104-117`, `tools/coaches.py:218-223`
- Test: `tests/test_setup.py`, `tests/test_keys.py`, `tests/test_routes.py`

**Interfaces:**
- Produces: `paths.WEB: bool` (`os.environ.get("HARMONICFITNESS_WEB") == "1"`); fact `web=yes|no` from `doctor.sh --facts`; `keys.clean_value(var: str, value: str | None) -> str` (today's `_clean`, renamed; raises `keys.BadKey`); `keys.APP_SETTINGS = "HarmonicFitness's settings, under Keys"` (the place named in every WEB message).

- [ ] **Step 1: Write the failing tests**
  - `test_setup.py`: `test_web_client_facts_no_local`: with `HARMONICFITNESS_WEB="1"` on a faked Apple Silicon Mac and a faked Linux with an NVIDIA card, `local`, `local_hw` and `local_engine` are `no`, `no`, `""`; `web` is `yes`; `remote` is `no`; `local_reason` contains `"web client"`. Without it, `web` is `no`.
  - `test_keys.py`: `test_init_in_the_web_client_points_to_the_app` and `test_open_in_the_web_client_points_to_the_app`: as the existing `OnTheWeb` tests, with `HARMONICFITNESS_WEB="1"` (no `CLAUDE_CODE_REMOTE`): exit 0, stdout contains `"HarmonicFitness's settings"`, no `.env` is made. `test_clean_value`: `clean_value("X", " ab12cd34\n") == "ab12cd34"`; `"ab 12"` and `"abé"` raise `BadKey` whose message holds `"X"` and not the value.
  - `test_routes.py`: `test_missing_key_in_the_web_client`: with `paths.WEB` patched true, `missing_key(<stock Fish coach>)` contains `"HarmonicFitness's settings"` and not `"keys init"`; `way_out()` the same. `test_download_refused_in_the_web_client`: `coaches.main(["download"])` with `paths.WEB` true returns 64 and never calls `voices.download`.
- [ ] **Step 2: Run them; they fail** — `./harmonicfitness test` (or `.venv/bin/python -m unittest tests.test_setup tests.test_keys tests.test_routes -v`): the new tests fail, every other test passes.
- [ ] **Step 3: Implement.**
  - `paths.py`: `WEB` beside `REMOTE`, with a comment ("the HarmonicFitness web client's worker").
  - `doctor.sh`: `WEB=no; [ "${HARMONICFITNESS_WEB:-}" = 1 ] && WEB=yes`; after the REMOTE block, when `WEB=yes`: `LOCAL=no`, `LOCAL_ENGINE=""`, `LOCAL_REASON="This is the HarmonicFitness web client, which speaks with web coaches only."`, and `LOCAL_HW=no`, `LOCAL_ENGINE_HW=""` (set after the existing `LOCAL_HW="$LOCAL"` line, so nothing local is ever offered). Print `web=$WEB` after `remote=`. The report's header line for WEB: `This is the HarmonicFitness web client: it speaks with web coaches, through your own keys.`
  - `keys.py`: rename `_clean` to `clean_value` (update its callers); in `main`, `init` and `open` in WEB mode print `f"Add your {name} key in {APP_SETTINGS}. Never paste it into the chat."` (for `open`, without a service name: `f"Add your keys in {APP_SETTINGS}."`) and return 0, touching no file. `open_env` returns `[]` in WEB mode.
  - `routes.py`: in `missing_key` and `way_out`, a WEB branch before the REMOTE one: fix `f"add your {name} key in {keys.APP_SETTINGS}"`.
  - `coaches.py`: `download` in WEB mode prints `"The web client speaks with web coaches only, so there's no local model to fetch."` to stderr, returns `cli.USAGE`.
- [ ] **Step 4: Run them; all pass** — the same command: 0 failures.
- [ ] **Step 5: Commit** — `git commit -m "engine: HARMONICFITNESS_WEB, the web client's mode: no local voice, keys added in the app"`

### Task 2: Engine web mode: the coach and the delivery

**Files:**
- Modify: `tools/coachpick.py:29-56`, `tools/brief.py:314-334`, `tools/build.py:149-166,513-528`, `CLAUDE.md`, `CHANGELOG.md`
- Test: `tests/test_stock.py`, `tests/test_brief.py`, `tests/test_integrity.py:660-675`

**Interfaces:**
- Consumes: `paths.WEB` (Task 1).
- Produces: `build.delivery_plan(remote: bool, web: bool, deliver_to: list, client: bool = False) -> dict` (same keys as today). With `client`: `{"copy_to": [], "remove_local": False, "note": None, "record": {"delivered_to": [], "kept_local": True, "reason": "the web client uploads the MP3"}}`, whatever the other arguments.

- [ ] **Step 1: Write the failing tests**
  - `test_stock.py`: `test_web_default_is_a_web_stand_in`: with the stock fixture, no log, no key set and `paths.WEB` patched true, `coachpick.default()` is the first stock web coach by `cloud.SERVICES` order (`is_web`, `shipped`); with `paths.WEB` false the result is unchanged from today (assert it equals what `default()` returned before the patch).
  - `test_brief.py`: `test_talk_rate_web_coach_without_key`: for a stock web coach with no key, `brief.talk_rate(<its name>)` is not `None` and its `measured` flag is `False`.
  - `test_integrity.py` (beside the existing `delivery_plan` checks): `delivery_plan(False, False, ["/x"], client=True)` and `delivery_plan(True, True, [], client=True)` both equal the `client` dict above; the four existing calls are unchanged.
  - `test_integrity.py` or `test_tools.py`, beside the in-process build tests: `test_build_in_the_web_client_keeps_the_mp3`: an in-process build with `paths.WEB` true and no `deliver_to` in the profile exits 0, makes no `.web-1.mp3`, keeps the MP3 in the workout folder, and the record's `reason` is `"the web client uploads the MP3"` (no "no delivery folder" problem raised).
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
  - `coachpick.default`: the last line becomes, in WEB mode, the first of `sorted(found, key=order)` that `is_web` (else `found[0]`); local stand-ins are never chosen in WEB mode, even if `_usable_here`.
  - `brief.talk_rate`: the fallback tries `personas.voice_for(coach, coach.service, pending=True)` for a web coach (keeping `"local"` for a local one).
  - `build.py`: `web = (opts.web or paths.REMOTE) and not opts.no_web` stays (WEB mode adds no default web copy); folders are read only when neither `paths.REMOTE` nor `paths.WEB`; `delivery_plan(paths.REMOTE, web, folders, client=paths.WEB)`.
  - `CLAUDE.md`: name `HARMONICFITNESS_WEB` beside each `CLAUDE_CODE_REMOTE` mention (Tools › Setup, doctor; Building, `--web`/delivery; Audio, the last bullet), one clause each: "the web client's worker sets `HARMONICFITNESS_WEB=1`: no local voice, keys added in the app, the MP3 kept for the app to upload".
  - `CHANGELOG.md`: a new `## [Unreleased]` section above 0.20.0, `### Added`: the web client's mode, and (from Tasks 3 to 6) voice keys in the web app.
- [ ] **Step 4: Run them; all pass** — `./harmonicfitness test`: 0 failures.
- [ ] **Step 5: Commit** — `git commit -m "engine: in the web client, a web stand-in by default and the MP3 kept for upload"`

### Task 3: The key store

**Files:**
- Create: `web/webapp/migrations/005_user_keys.sql`, `web/webapp/keystore.py`
- Test: `web/webtests/test_keystore.py`

**Interfaces:**
- Consumes: `store.UserKey`, `crypto.seal`, `crypto.open_`.
- Produces:
  - Table `user_keys(user_id uuid references users on delete cascade, service text, secret bytea not null, updated_at timestamptz not null default now(), primary key (user_id, service))`.
  - `keystore.put(conn, uk: UserKey, service: str, value: str) -> None` (upsert, sealed, AAD `f"{uk.user_id}:user_keys:{service}"`); `keystore.delete(conn, uk, service) -> bool` (whether a row went); `keystore.listing(conn, uk) -> dict[str, datetime]` (service → updated_at; never opens); `keystore.open_all(conn, uk) -> dict[str, str]` (service → value; the worker only). None of them commits: the caller does.

- [ ] **Step 1: Write the failing tests** (a `DBCase`, as `test_store.py`)
  - `test_put_seals_and_open_all_returns`: after `put(..., "fish", "k-123456789")`, the row's `secret` doesn't contain `b"k-123456789"`; `open_all` returns `{"fish": "k-123456789"}`; a second `put` replaces it and moves `updated_at`.
  - `test_listing_never_opens`: with `crypto.open_` patched to raise, `listing` still returns `{"fish": <datetime>}`.
  - `test_secret_bound_to_user_and_service`: copying user A's `secret` into user B's row, or into A's `elevenlabs` row, makes `open_all` raise `crypto.Tampered`.
  - `test_delete`: `delete` returns `True` then `False`; `open_all` is `{}`.
  - `test_cascade`: deleting the user deletes its keys.
- [ ] **Step 2: Run them; they fail** — `.venv/bin/python -m unittest discover -s web/webtests -t web -p test_keystore.py -v` with `HARMONICFITNESS_TEST_DATABASE_URL` set (local: `.superpowers/pg` on port 54329).
- [ ] **Step 3: Implement the migration and `keystore.py`.**
- [ ] **Step 4: Run them; all pass.**
- [ ] **Step 5: Commit** — `git commit -m "web: user_keys, each voice key sealed with the user's data key"`

### Task 4: The keys API

**Files:**
- Modify: `web/webapp/api.py`, `web/webapp/worker.py` (`engine_services`)
- Test: `web/webtests/test_api.py`

**Interfaces:**
- Consumes: `keystore.put`, `delete`, `listing` (Task 3); `keys.clean_value` (Task 1).
- Produces:
  - `worker.engine_services(engine_root) -> dict[str, dict]`: `{service: {"name", "key_var", "key_page"}}` from `services.settings()`, in `services.toml` order, imported under `engine_lists`'s guard (HARMONICFITNESS_HOME pointed nowhere, `tools/` appended last, the module's origin checked), cached per root. Also `worker.clean_key(engine_root, var, value) -> str`, which calls the engine's `keys.clean_value`.
  - `GET /api/keys` → `[{"service", "name", "key_page", "set": bool, "updated_at": iso | null}]`, one per service, in order.
  - `PUT /api/keys/{service}` (POST rules: same-origin; body `{"key": str, max_length 1024}`, `extra="forbid"`) → 204. Unknown service → 404. Empty after stripping, or refused by `clean_value` → 400 `f"That doesn't look like a {name} key: it has a space, a line break or a symbol in it. Paste it again."`
  - `DELETE /api/keys/{service}` (same-origin) → 204 whether or not one was set; unknown service → 404.

- [ ] **Step 1: Write the failing tests**
  - `test_keys_need_session`: all three routes without a cookie → 401; `PUT`/`DELETE` without Origin → 403.
  - `test_list_shows_every_service_unset`: a new user gets one entry per `engine_services` service, each `set: false`, `updated_at: null`.
  - `test_put_then_list`: `PUT /api/keys/fish {"key": "abc123def456"}` → 204; the list shows fish `set: true`; no response body anywhere contains `abc123def456`.
  - `test_put_key_strips_and_refuses`: `"abc123def456\n"` → 204 and the stored value (via `keystore.open_all`) is `"abc123def456"`; `"abc 123"` → 400 whose detail names Fish Audio and doesn't contain `abc 123`; `""` → 400; 1025 characters → 422; `PUT /api/keys/nope` → 404.
  - `test_keys_are_per_user`: user A sets fish; user B's list shows fish unset; B's `DELETE /api/keys/fish` → 204 and A's key is still in `open_all(A)`.
  - `test_delete_key`: set, delete → 204, the list shows unset.
  - `test_api_never_opens_keys`: the source of `webapp/api.py` doesn't contain `open_all`.
- [ ] **Step 2: Run them; they fail** — `... -p test_api.py -v`.
- [ ] **Step 3: Implement** the routes in `create_app`, beside `/api/context`, each in its own `connection()`, committing a write, rolling back a read. `engine_services` and `clean_key` load once at app creation (as `options` does).
- [ ] **Step 4: Run them; all pass** — every web test file: 0 failures.
- [ ] **Step 5: Commit** — `git commit -m "web: /api/keys: set, replace and remove a voice key; never shown again"`

### Task 5: Keys and web mode into each job

**Files:**
- Modify: `web/webapp/engine.py:13-60`, `web/webapp/worker.py` (`Ctx`, `brief`)
- Test: `web/webtests/test_engine.py`, `web/webtests/test_jobs.py`

**Interfaces:**
- Consumes: `keystore.open_all` (Task 3), `worker.engine_services` (Task 4).
- Produces: `engine._env` sets `HARMONICFITNESS_WEB="1"` and `RESERVED` includes it. `Ctx.key_env() -> dict[str, str]`: `{key_var: value}` for each of the user's keys whose service `engine_services` knows (others skipped), read through `open_all` and committed; `brief` passes it as `extra_env`.

- [ ] **Step 1: Write the failing tests**
  - `test_engine.py`: `test_web_mode_always_on`: a fake engine root whose `harmonicfitness` script prints `$HARMONICFITNESS_WEB` → stdout `"1\n"`; `extra_env={"HARMONICFITNESS_WEB": "0"}` raises `ValueError`.
  - `test_jobs.py`: `test_brief_gets_the_users_keys`: with a fish key stored and `engine.run` patched to record its `extra_env`, a brief job's call has `extra_env == {"FISH_AUDIO_API_KEY": <value>}`; another user's job has `{}`.
  - `test_jobs.py`: `test_key_in_engine_output_is_scrubbed`: a fake engine root whose script writes `$FISH_AUDIO_API_KEY` to stderr and exits 1 (settings' `engine_root` pointed at it); the job fails and its sealed detail (`jobs.result`/the stored `detail`) contains `<key>` and not the value.
- [ ] **Step 2: Run them; they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass** — every web test file and `./harmonicfitness test`: 0 failures.
- [ ] **Step 5: Commit** — `git commit -m "web: every job runs in the engine's web mode with the user's keys"`

### Task 6: The Keys box

**Files:**
- Create: `web/client/src/zones/KeysBox.tsx`, `web/client/src/zones/KeysBox.test.tsx`
- Modify: `web/client/src/api.ts`, `web/client/src/zones/ContextColumn.tsx`, `web/client/src/theme.css`

**Interfaces:**
- Consumes: the routes of Task 4.
- Produces: `api.keys(): Promise<KeyState[]>`, `api.setKey(service: string, key: string): Promise<void>`, `api.deleteKey(service: string): Promise<void>`; `type KeyState = { service: string; name: string; key_page: string; set: boolean; updated_at: string | null }`. `<KeysBox onSignedOut={() => void} />`, placed in the context column above the device link.

Behaviour: heading "Voice keys"; a row per service: its name, "Set {date}" or "Not set", and "Add" / "Replace"; "Remove" only when set, asking once ("Remove your {name} key?"). Add/Replace opens an `<input type="password" autoComplete="off" spellCheck={false}>`, never pre-filled, with "Save" and "Cancel", and a "Get a key" link to `key_page` (`target="_blank" rel="noopener noreferrer"`). After Save the field is cleared and closed, and the row shows "Set". A 400 shows the server's message under the field. Below the rows: "Stored encrypted, never shown again. Your key goes only to its own service, when a workout is spoken." A `NotSignedIn` calls `onSignedOut`. Uses the existing `cx-box` / `cx-s` / `quiet` styles.

- [ ] **Step 1: Write the failing tests** (vitest + Testing Library, mocking `api` as `Panel.test.tsx` does)
  - `shows every service, set or not`: two services, one set → "Not set" and "Set" each appear once.
  - `saves a key and never shows it`: typing `secret-value-1` and Save calls `api.setKey("fish", "secret-value-1")`; afterwards no element's text or input value contains `secret-value-1`.
  - `shows the server's refusal`: `setKey` rejecting with an `ApiError(400, "That doesn't look like…")` shows that message; the field stays open.
  - `removes after asking`: Remove, confirm → `api.deleteKey("fish")`; cancel → not called.
- [ ] **Step 2: Run them; they fail** — from `web/client`: `npm test`.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them; all pass** — `npm test` and `npm run build`: 0 failures, the build writes `dist/`.
- [ ] **Step 5: Commit** — `git commit -m "web: the Keys box: add, replace and remove a voice key"`

### Task 7: Deploy and check it live

**Files:**
- Modify: `web/README.md` (a short "Keys" section: where keys live, that the web process never opens one, `HARMONICFITNESS_WEB` set on every job)

- [ ] **Step 1:** `./harmonicfitness test` and, from `web/client`, `npm test`: 0 failures. Commit the README.
- [ ] **Step 2:** Push `main`; Railway deploys `web` and `worker` from GitHub. `railway deployment list --service web` and `--service worker`: the newest is `SUCCESS`. The web log shows migration `005_user_keys` applied once.
- [ ] **Step 3:** The maintainer signs in at https://harmonicfitness.up.railway.app, adds a key in Voice keys, and runs a brief. Expected: the brief's coach is the stock web coach for that service; `railway logs --service web --http` shows `PUT /api/keys/<service>` 204; `railway logs --service worker` shows the job's lines and no `_API_KEY` or key text (the worker logs only job ids and error types).
- [ ] **Step 4:** Mark Milestone 2 done in `plan.md`'s table; commit.
