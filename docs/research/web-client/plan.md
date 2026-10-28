# Web client: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the web client in `docs/research/web-client/design.md` as a series of milestones, starting with Slice 1: an invited user signs in, sets one sentence ("a 20-minute strength workout with bodyweight"), presses one button, and watches a background job run the engine's `brief` on their own stored context and show the result.

**Architecture:** FastAPI (`web`) and a Python worker (`worker`) share Postgres. Each user's context files live in Postgres, one encrypted row per file. A job writes them to a fresh temporary folder, runs `./sweatcast` in a subprocess with `SWEATCAST_HOME` pointed there, writes back only what changed (with a version check), and deletes the folder. Progress goes worker → Postgres `NOTIFY` → server-sent events → the React app.

**Tech stack:** Python 3.11 (the engine's pin), FastAPI, uvicorn, psycopg 3 (plain SQL, no ORM), `cryptography` (AES-GCM), Pydantic AI from Milestone 3, boto3 from Milestone 4; React + TypeScript on Vite, vitest; Postgres and a bucket on Railway.

**Spec:** `docs/research/web-client/design.md`. UI reference: `docs/research/web-client/ui-6-zones.html` (layout and interaction, not copy).

## Global constraints

- The engine (`tools/`, `knowledge/`, `coaches/`) is used as is. Any change it needs goes into the engine as a general feature, with engine tests, and doesn't change CLI behaviour.
- The web layer never writes context files in a format of its own; every write to a context file is the engine's (run as `./sweatcast …`) or a byte-for-byte store of a file the engine wrote.
- Web dependencies are the optional extra `web` in `pyproject.toml`, never core dependencies. A CLI install doesn't grow.
- Python `>=3.11,<3.12`. The Docker image installs with `uv sync --locked --extra web`, never the `cpu` or `cuda` extras.
- The user-facing name is **"Working Title"** in the app's title, wordmark and copy only (`APP_NAME` in one place on each side). Code, folders, packages, the engine and Railway stay `sweatcast` / `sweatcast-web`.
- No personal details in `web/`'s code, tests or fixtures. `tools/hooks/private-paths` matches by file name anywhere (`profile.md`, `health.md`, `training.md`, `content.md`, `log.md`, `settings.toml`, `movements.toml`, `.env`): web tests build their context from `me.example/` at run time and never ship files with those names.
- Keys, health details, context files, chat, transcripts, job arguments, results and events are stored encrypted with the user's data key. Plain columns hold only ids, states, timestamps, versions, service names and the email address.
- Nothing is ever retried automatically after it may have reached a paid service. A job that dies is marked failed, not requeued.
- The engine subprocess gets an allowlisted environment: never `DATABASE_URL`, `WT_MASTER_KEY`, `SESSION_SECRET` or bucket credentials.
- Railway services deploy from the GitHub repo (`RNCDev/sweatcast`, branch `main`), never `railway up` from a working tree, so only committed files (never `me/`) reach a server. `.dockerignore` also leaves out `me/`, `me.*/` (sparing `me.example/`), `models`, `.venv`, `.cache`, `.codegraph`, `docs/eval/out*`.
- Build on `main`. The release level is the maintainer's call (expected: minor, 0.20.0).

## Decisions this plan makes (builder's calls in the spec)

- **Sign-in:** invite links. The maintainer runs `python -m webapp.admin invite <email>` (locally against staging through `railway run`, or in the service's shell), which prints a one-time link valid for 7 days. Opening it shows a small page whose button signs in (a POST): email and chat apps open links to preview them, so a GET never uses the invite up. Signing in sets a session cookie (HttpOnly, Secure, SameSite=Lax) for 90 days, renewed to 90 days whenever it's used (at most once a day, to spare writes). **Add a device:** a signed-in person can open "Sign in another device", which shows a one-time link and its QR code, valid for 10 minutes; opening it on the other device goes through the same sign-in page. Only someone who has lost every device needs a new link from `admin login-link <email>`. No email service, no passwords (the maintainer's decision, 2026-10-27: links plus add a device). Passkeys can come later without changing this.
- **Queue:** a `jobs` table claimed with `FOR UPDATE SKIP LOCKED`. "One job per user at a time" is a partial unique index on `jobs(user_id) WHERE state = 'running'`, so the database enforces it.
- **A dead job:** the worker updates `heartbeat_at` every 15 s. A running job whose heartbeat is older than 120 s is marked `failed` ("interrupted") by the next worker poll, never requeued.
- **Store:** one row per context file (`context_files`), body encrypted, with an integer `version`. Clip cache and voice pace are not stored in Slice 1; whether to keep them between jobs is decided in Milestone 4.
- **Agent framework (Milestone 3):** Pydantic AI, for its one tool-calling interface over Anthropic, OpenAI and Gemini and its built-in web search for all three.
- **MP3 expiry (Milestone 4):** Railway's bucket CLI offers no lifecycle rule, so every upload is recorded with `expires_at` and the worker deletes expired objects every 10 minutes. A bucket lifecycle rule, if Railway adds one, is a backup only.
- **Fonts:** Zilla Slab and Figtree self-hosted through `@fontsource`, so no page load reaches Google.

## Railway (created 2026-10-27)

Project `sweatcast-web` (workspace "rncdev's Projects"), **one environment** (the maintainer's decision, 2026-10-27: no separate staging and production; the spec's two environments are dropped). It holds `Postgres`, the bucket `media` (region iad), and the `web` and `worker` services deployed from `main` (Task 10), at https://web-staging-1b5a.up.railway.app. The environment is still named `staging` until it's renamed in the dashboard; the old `production` environment held only a stray service and is to be deleted.

## Milestones

| | Milestone | What it proves | Spec sections |
|---|---|---|---|
| **1** | **Slice 1** (detailed below) | sign-in, the store, a job running the engine on a user's folder, write-back, live progress, deployed to staging | Stack, Railway layout, Per-user isolation, Jobs (no agent) |
| 2 | Engine web mode and keys | `SWEATCAST_WEB=1` as an engine feature; encrypted per-service keys, entered once, never shown | Engine changes, Keys |
| 3 | The agent, through the plan | a provider-agnostic loop with the engine's commands as typed tools, ask and show tools, the check-in and the plan shown | The agent, Jobs and conversations |
| 4 | Build, render, deliver | the long job: write, lint, build, upload, signed link, 24 h expiry, log; spend guard | Delivery and storage, anti-goal on billing |
| 5 | Instructions from the skills | a generator beside `harness sync` writes the web agent's instructions; a test fails when stale; the eval gate per provider | The agent |
| 6 | The doors | setup's quick start, edit my stuff, something hurts, coaches and audition, feedback on older workouts, analytics, tour | Goals 1, Workflows |
| 7 | Leaving and arriving | import from the CLI, export, delete account, privacy page | Workflows, Data and privacy |

The ui-6 polish (copy, motion, more separation between the working panel and the context column) runs as its own pass alongside Milestones 3 to 6, against the components Task 9 lays down. Each milestone after 1 gets its own detailed plan when it starts, written against what Slice 1 actually built.

### Milestone 2 in outline

- Engine: `paths.WEB = os.environ.get("SWEATCAST_WEB") == "1"`. `doctor.sh --facts` reports `local=no` with the reason "the web client speaks with web coaches only"; `routes.missing_key` says to add the key in the app's settings; `coachpick.default` never falls back to a local stand-in; `coaches download` exits 64; `build` with no delivery folder records `kept_local` with the reason "the web client uploads the MP3". Engine tests for each, and the CHANGELOG.
- Web: `user_keys(user_id, service, secret, updated_at)`; a settings view listing which services have a key, replace and delete; keys decrypted only in the worker, passed only into a job's environment under the names in `knowledge/services.toml`.

### Carried into Milestone 4 (from Slice 1's final review)

Required before renders, which are long and billed:
- **A deploy mid-job:** today SIGTERM waits between jobs, so a running job is reaped after 120 s as "interrupted". Choose: drain (Railway's draining time) or, on SIGTERM, kill the engine's process group and fail the job at once.
- **Heartbeat:** one failed heartbeat fails the whole job. Reconnect and retry instead, let `jobs.complete` (row lock, `state='running'`) decide, and kill the engine when the job turns out to be reaped, so a reaped job stops billing.
- **Event streams:** each holds a Postgres connection and a thread token. Cap them per user and overall, or move to one shared async LISTEN.
- **Sizes:** a per-file cap in `folder.harvest`, and a cap on the engine's buffered output.
- **Coming back to a job:** a "latest job" route so a reload finds a running job, the client re-following a stream that dropped while the job runs, and a `useJob` test.
- **Per-job write rules:** `NEVER_WRITE_BACK` (`health.md`) applies to every job today; the check-in job must be able to write `health.md`.
- **Key rotation:** a new `key_version` must re-seal and re-hash every stored path (the path hash is keyed by the data key).

## Review focus

1. **The engine subprocess sees server secrets.** A job's environment holds `WT_MASTER_KEY` or `DATABASE_URL` because the runner copied `os.environ`. Expected: only the allowlist reaches it. Pinned by `test_engine_env_is_allowlisted` (Task 5).
2. **One user reaches another's job or files by id.** `GET /api/jobs/{id}/events` for another user's job. Expected: 404, the same as a job that doesn't exist. Pinned by `test_other_users_job_is_404` (Task 8).
3. **A worker dies mid-job.** The job stays `running` and blocks that user forever, or is retried and bills again. Expected: marked failed after 120 s without a heartbeat, the user's next job runs, nothing is retried. Pinned by `test_stale_running_job_fails_and_frees_user` (Task 6).
4. **The user edits a file while a job runs.** Expected: the user's edit wins, the job's write of that file is dropped and noted. Pinned by `test_write_back_conflict_keeps_users_edit` (Task 3).
5. **The engine leaves files the store must not take.** A `.env`, lock files, the clip cache, MP3s, or a symlink pointing outside the folder. Expected: none stored. Pinned by `test_harvest_skips_unsafe_and_bulky` (Task 4).

---

## Slice 1

File map (all new unless marked):

```
pyproject.toml, uv.lock              modify: the `web` extra
sweatcast                            modify: `test` also discovers web/webtests when the extra is installed
.github/workflows/test.yml           modify: a Postgres service, `uv sync --locked --extra web`
.dockerignore, Dockerfile            the image (Task 10)
web/README.md                        how to run it locally, the env variables, the admin commands
web/entrypoint.sh                    WT_ROLE=web → migrate, then uvicorn; WT_ROLE=worker → the worker
web/webapp/__init__.py
web/webapp/config.py                 Settings from the environment
web/webapp/crypto.py                 envelope encryption
web/webapp/db.py                     connection pool, migration runner
web/webapp/migrations/001_init.sql   the schema
web/webapp/store.py                  context files: read, versioned write-back
web/webapp/folder.py                 materialize a folder, harvest what changed, seed a new user
web/webapp/engine.py                 run ./sweatcast in a subprocess
web/webapp/jobs.py                   enqueue, claim, heartbeat, finish, events
web/webapp/worker.py                 the loop and the handlers (Slice 1: `brief`)
web/webapp/auth.py                   invites and sessions
web/webapp/admin.py                  `python -m webapp.admin invite|login-link`
web/webapp/api.py                    FastAPI app: API, SSE, the built client
web/webtests/                           unittest; DB tests skip without WT_TEST_DATABASE_URL
web/client/                          Vite + React + TypeScript
```

Tests use `unittest` (as the engine does). Tests that need Postgres read `WT_TEST_DATABASE_URL` and skip when it's unset; each test class creates a fresh schema (`CREATE SCHEMA t_<random>`, `SET search_path`) and drops it after. The folder is `web/webtests/` (not `tests/`, which would clash with the engine's `tests` package); each test file inserts `web/` on `sys.path`, as engine tests insert `tools/`. Run them all with `./sweatcast test` once Task 1 lands; one file with `.venv/bin/python -m unittest discover -s web/webtests -t web -p test_crypto.py -v` from the repo root.

### Task 1: The `web` extra and test wiring

**Files:**
- Modify: `pyproject.toml` (`[project.optional-dependencies] web = [...]`), `uv.lock`, `sweatcast` (the `test` branch near line 88), `.github/workflows/test.yml`
- Create: `web/webapp/__init__.py`, `web/webtests/__init__.py`, `web/webtests/test_wiring.py`, `web/README.md`

**Interfaces:**
- Produces: `import webapp` works with `web/` on `sys.path` (each web test file inserts it, as engine tests insert `tools/`); `webapp.APP_NAME = "Working Title"`.

- [ ] **Step 1:** Add the `web` extra: `fastapi`, `uvicorn[standard]`, `psycopg[binary,pool]`, `cryptography`, `httpx` (for FastAPI's TestClient), each pinned `==` to the newest release at least two weeks old. Run `uv lock` and `uv sync --extra web`.
- [ ] **Step 2: Write the failing test** `test_wiring.py::test_app_name`: `assert webapp.APP_NAME == "Working Title"`.
- [ ] **Step 3:** Run `./sweatcast test`. Expected: the web test isn't discovered yet (count unchanged).
- [ ] **Step 4:** In `sweatcast`'s `test` branch, after the engine's discover, run `python -m unittest discover -s web/webtests -t web` when `importlib.util.find_spec("fastapi")` is found, else print `web tests skipped: install with uv sync --extra web` and don't fail. Create `webapp/__init__.py` with `APP_NAME`.
- [ ] **Step 5:** Run `./sweatcast test`. Expected: all engine tests and `test_app_name` pass.
- [ ] **Step 6:** CI: add `services: postgres: image: postgres:16` with a health check, `env: WT_TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/postgres`, and change `uv sync --locked` to `uv sync --locked --extra web`.
- [ ] **Step 7: Commit** `web: the web extra and its tests in ./sweatcast test`.

### Task 2: Settings and envelope encryption

**Files:** Create `web/webapp/config.py`, `web/webapp/crypto.py`, `web/webtests/test_crypto.py`

**Interfaces:**
- Produces: `config.Settings` (frozen dataclass): `database_url: str`, `master_key: bytes` (32 bytes, from base64 `WT_MASTER_KEY`), `engine_root: str` (default: the repo root, two levels up from `webapp/`), `session_days: int = 90`, `invite_days: int = 7`, `base_url: str` (`WT_BASE_URL`), `role: str` (`WT_ROLE`, `web` or `worker`). `config.load(env: Mapping[str, str]) -> Settings` raises `config.ConfigError` naming the missing or malformed variable (never its value).
- Produces: `crypto.new_data_key(master: bytes) -> tuple[bytes, bytes]` (plain data key, wrapped data key); `crypto.unwrap(master: bytes, wrapped: bytes) -> bytes`; `crypto.seal(key: bytes, plaintext: bytes, aad: bytes) -> bytes`; `crypto.open_(key: bytes, sealed: bytes, aad: bytes) -> bytes`, raising `crypto.Tampered`. AES-256-GCM, 12-byte random nonce prefixed to the ciphertext. The AAD binds a value to its place: `f"{user_id}:{table}:{key}".encode()`.

- [ ] **Step 1: Write the failing tests:**
  - `test_round_trip`: `open_(k, seal(k, b"x", b"a"), b"a") == b"x"`.
  - `test_wrong_aad_fails`: a value sealed for `u1:context_files:health.md` raises `Tampered` when opened with `u2:context_files:health.md`.
  - `test_unwrap_needs_the_master`: a data key wrapped under one master raises `Tampered` under another.
  - `test_config_refuses_short_master_key`: `load({"WT_MASTER_KEY": base64(16 bytes), ...})` raises `ConfigError` whose message contains `WT_MASTER_KEY` and not the value.
- [ ] **Step 2:** Run `.venv/bin/python -m unittest discover -s web/webtests -t web -p test_crypto.py -v`. Expected: FAIL, no module `webapp.crypto`.
- [ ] **Step 3:** Implement both modules.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `web: settings and envelope encryption`.

### Task 3: The schema and the context store

**Files:** Create `web/webapp/db.py`, `web/webapp/migrations/001_init.sql`, `web/webapp/store.py`, `web/webtests/dbcase.py` (the fresh-schema base class), `web/webtests/test_store.py`

**Interfaces:**
- Produces, `001_init.sql`:
  - `users(id uuid primary key default gen_random_uuid(), email text unique not null, wrapped_key bytea not null, created_at timestamptz not null default now())`
  - `invites(token_hash bytea primary key, user_id uuid not null references users on delete cascade, expires_at timestamptz not null, used_at timestamptz)`
  - `sessions(token_hash bytea primary key, user_id uuid not null references users on delete cascade, expires_at timestamptz not null)`
  - `context_files(user_id uuid references users on delete cascade, path text, version int not null, body bytea not null, updated_at timestamptz not null default now(), primary key (user_id, path))`
  - `jobs(id bigserial primary key, user_id uuid not null references users on delete cascade, kind text not null, args bytea not null, state text not null check (state in ('queued','running','done','failed')), result bytea, error text, created_at, started_at, heartbeat_at, finished_at timestamptz)` and `create unique index one_running_job_per_user on jobs(user_id) where state = 'running'`
  - `job_events(id bigserial primary key, job_id bigint not null references jobs on delete cascade, at timestamptz not null default now(), body bytea not null)`
  - `schema_migrations(name text primary key, applied_at timestamptz not null default now())`
- Produces: `db.connect(url: str) -> psycopg.Connection`; `db.migrate(conn) -> list[str]` (applies `migrations/*.sql` not yet in `schema_migrations`, in name order, each in its own transaction; returns the names applied).
- Produces: `store.UserKey` (user id plus the plain data key, built by `store.user_key(conn, settings, user_id)`); `store.read_all(conn, uk) -> dict[str, tuple[int, bytes]]` (path → version, plain body); `store.write_back(conn, uk, changes: dict[str, bytes | None], base: dict[str, int]) -> list[str]` (`None` deletes; returns the paths that conflicted). A changed file updates only `where version = base[path]` and sets `version = version + 1`; a new file inserts with `version = 1` and conflicts if the row exists; a delete deletes only at `base[path]`. `store.put(conn, uk, path, body) -> int` (a direct edit from the panel: always wins, bumps the version, returns it).

- [ ] **Step 1: Write the failing tests** (in a `dbcase.DBCase`):
  - `test_migrate_is_idempotent`: first `migrate` returns `["001_init.sql"]`, the second `[]`.
  - `test_bodies_are_encrypted_at_rest`: after `write_back` of `{"health.md": b"left ankle"}`, `select body from context_files` doesn't contain `b"left ankle"`.
  - `test_write_back_conflict_keeps_users_edit`: read (version 1), `put` the same path (version 2), `write_back` with base 1 → returns `["health.md"]`, and `read_all` gives the `put` body.
  - `test_users_are_isolated`: user B's `read_all` never includes user A's paths, and opening A's row with B's key raises `Tampered`.
- [ ] **Step 2:** Run them against Postgres. Expected: FAIL, no module `webapp.db`.
- [ ] **Step 3:** Implement `db.py`, the SQL and `store.py`. The AAD for a file is `f"{user_id}:context_files:{path}"`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5: Commit** `web: the schema and the versioned context store`.

### Task 4: Materialize, harvest, seed

**Files:** Create `web/webapp/folder.py`, `web/webtests/test_folder.py`

**Interfaces:**
- Consumes: `store.read_all`, `store.write_back` (Task 3).
- Produces: `folder.materialize(files: dict[str, bytes], root: str) -> dict[str, str]` (writes each file under `root`, refusing any path that is absolute or contains `..`; returns path → sha256 of what was written). `folder.harvest(root: str, written: dict[str, str], never: frozenset[str] = frozenset()) -> dict[str, bytes | None]` (files new or changed since `written`, and `None` for files deleted; skipping symlinks, anything under `SKIP`, and any path in `never`). `folder.SKIP`: `.env`, `*.lock`, `workouts/.audio-cache/`, `coaches/.auditions/`, `*.mp3`, `*.wav`, `*.log`, `*.log.1`, `.gitignore`, `.DS_Store`. `folder.seed(engine_root: str) -> dict[str, bytes]` (every file in `me.example/` as path → bytes, skipping `SKIP`).

- [ ] **Step 1: Write the failing tests:**
  - `test_round_trip_finds_only_changes`: materialize `seed(...)`, change one file and add `workouts/x/x.brief.md` → harvest returns exactly those two.
  - `test_harvest_skips_unsafe_and_bulky`: create `.env`, `workouts/.audio-cache/a.wav`, `x.lock`, `a.mp3` and a symlink `evil → /etc/hosts` → none in the result.
  - `test_never_set_is_respected`: change `health.md`, harvest with `never={"health.md"}` → not in the result.
  - `test_materialize_refuses_escape`: `{"../x": b""}` raises `ValueError`.
  - `test_seed_is_the_template`: `seed()` holds `profile.md` and `health.md`, and every key exists under `me.example/`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: write a user's folder out and take back what changed`.

### Task 5: The engine runner

**Files:** Create `web/webapp/engine.py`, `web/webtests/test_engine.py`

**Interfaces:**
- Produces: `engine.Result` (NamedTuple: `code: int`, `stdout: str`, `stderr: str`). `engine.run(engine_root: str, home: str, argv: list[str], extra_env: Mapping[str, str] = {}, timeout: float = 120) -> Result`. Runs `[engine_root + "/sweatcast", *argv]` with `cwd=engine_root` and an environment built only from `engine.ALLOWED = ("PATH", "LANG", "LC_ALL", "TZ", "UV_CACHE_DIR", "SWEATCAST_PYTHON")` taken from `os.environ`, plus `HOME=home`, `SWEATCAST_HOME=home` and `extra_env`. On timeout it kills the process group and returns code 124 with `stderr` saying so. Output passes through the engine's own `redact.scrub` (imported from `tools/redact.py`, a leaf module) with every value in `extra_env` added as a secret to scrub.

- [ ] **Step 1: Write the failing tests:**
  - `test_engine_env_is_allowlisted`: with `os.environ` patched to hold `WT_MASTER_KEY=secret-master` and `DATABASE_URL=postgres://x`, run `["get", "wpm"]` through a stub `sweatcast` script in a temp engine root that prints `env` → stdout contains neither value, and contains `SWEATCAST_HOME=<home>`.
  - `test_brief_runs_on_a_seeded_folder`: materialize `folder.seed(ROOT)` into a temp dir and run the real engine: `["brief", "--goal", "strength", "--minutes", "20", "--preset", "bodyweight", "--today", "2026-10-27", "--save", f"{home}/workouts/2026-10-27-strength-20/2026-10-27-strength-20.draft.txt"]` → code 0, stdout starts with `# Today's brief: strength, 20 minutes`, and the `.menu.json` exists.
  - `test_extra_env_values_are_scrubbed`: a stub that echoes `$FISH_AUDIO_API_KEY` with `extra_env={"FISH_AUDIO_API_KEY": "sk-abcdefghijklmnop"}` → stdout doesn't contain the key.
  - `test_timeout_kills`: a stub that sleeps 10 s with `timeout=0.5` → code 124.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement (`subprocess.Popen(..., start_new_session=True)`, `os.killpg` on timeout). Check `redact.scrub`'s signature with `codegraph_explore` before calling it.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: run the engine in a subprocess with an allowlisted environment`.

### Task 6: Jobs, the worker and the `brief` job

**Files:** Create `web/webapp/jobs.py`, `web/webapp/worker.py`, `web/webtests/test_jobs.py`

**Interfaces:**
- Consumes: Tasks 3 to 5.
- Produces: `jobs.enqueue(conn, uk, kind: str, args: dict) -> int`; `jobs.claim(conn) -> Job | None` (`Job`: `id`, `user_id`, `kind`; claims the oldest queued job whose user has none running: `select … for update skip locked limit 1`, then `update … set state='running', started_at=now(), heartbeat_at=now()`, catching the unique violation from `one_running_job_per_user` as "nothing to claim"); `jobs.heartbeat(conn, job_id)`; `jobs.finish(conn, uk, job_id, result: dict)`; `jobs.fail(conn, uk, job_id, error: str)`; `jobs.reap(conn, stale_after: int = 120) -> list[int]` (running jobs with an old heartbeat → failed, `error = 'interrupted'`); `jobs.event(conn, uk, job_id, body: dict)` (inserts, then `select pg_notify('job_events', job_id::text)`); `jobs.events(conn, uk, job_id, after: int = 0) -> list[tuple[int, dict]]`; `jobs.args(conn, uk, job_id) -> dict`.
- Produces: `worker.HANDLERS: dict[str, Callable[[Ctx], dict]]`; `worker.run_one(conn, settings) -> bool` (reap, claim, run the handler with heartbeats from a timer thread on its own connection (a psycopg connection is never shared between threads), finish or fail; returns whether a job ran); `worker.main()` (loop `run_one`, sleeping 1 s when idle, `LISTEN jobs_queued` to wake early). `Ctx` holds `conn`, `uk`, `job_id`, `args`, `settings`, `home` (the temp folder) and `say(stage: str, **fields)` (a job event).
- Like the server, the worker sets `SWEATCAST_HOME` to a path that doesn't exist before importing any engine module (`tools/sessions.py`, `tools/catalog.py`), and touches a user's files only through `engine.run` in their own folder: no process ever switches between users' folders.
- The `brief` handler: validate `args` (`goal` in the session goals from `tools/sessions.py`, `minutes` in 10..60, `preset` in the catalog's presets; anything else fails the job with a message, never runs the engine), `say("folder")`, materialize, `say("brief")`, run `brief` with `--today <args.today>` and `--save` into `workouts/<date>-<goal>-<minutes>/`, harvest with `never={"health.md"}`, write back, `say("saved", conflicts=[...])`, return `{"brief_md": stdout, "stem": stem}`. The folder is removed in a `finally`.

- [ ] **Step 1: Write the failing tests:**
  - `test_brief_job_end_to_end`: seed a user, enqueue `brief` (strength, 20, bodyweight), `run_one` → job `done`, result `brief_md` starts with `# Today's brief`, the store holds `workouts/<stem>/<stem>.menu.json`, events are `folder`, `brief`, `saved` in order.
  - `test_one_job_per_user`: two queued jobs for one user and one claimed → the second `claim` returns `None`; a queued job for another user is claimed.
  - `test_stale_running_job_fails_and_frees_user`: a running job with `heartbeat_at = now() - 5 min` → `reap` returns it, its state is `failed`, its error `interrupted`, and the user's next queued job is claimable. It is never set back to `queued`.
  - `test_bad_args_never_run_the_engine`: `minutes = 999` → `failed`, with `engine.run` patched to raise if called.
  - `test_folder_is_removed`: after success and after a handler exception, the temp folder no longer exists.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. `enqueue` also runs `pg_notify('jobs_queued', '')`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: the job queue, the worker and the brief job`.

### Task 7: Invites and sessions

**Files:** Create `web/webapp/auth.py`, `web/webapp/admin.py`, `web/webtests/test_auth.py`

**Interfaces:**
- Consumes: `crypto.new_data_key`, `folder.seed`, `store.write_back` (a new user's context is the template).
- Produces: `auth.invite(conn, settings, email: str) -> str` (creates the user if new, with a wrapped data key and the seeded context; returns `f"{base_url}/invite/{token}"`; the token is 32 random bytes, URL-safe base64, stored only as its sha256); `auth.device_link(conn, settings, user_id) -> str` (a new invite row for an existing user, expiring in 10 minutes; same link shape as `invite`); `auth.redeem(conn, settings, token: str) -> str` (called only from the POST; returns a session token; raises `auth.Refused` for an unknown, used or expired invite); `auth.user_for(conn, session_token: str) -> UUID | None` (None when unknown or expired; pushes `expires_at` to now + `session_days` when it was last set more than a day ago); `auth.sign_out(conn, session_token)`. `admin.py`: `invite <email>` and `login-link <email>` (the same link for an existing user), printing the link and nothing else.

- [ ] **Step 1: Write the failing tests:**
  - `test_invite_creates_seeded_user`: after `invite`, the user's `read_all` holds `profile.md`.
  - `test_invite_is_single_use`: the second `redeem` of a token raises `Refused`.
  - `test_expired_invite_refused`: an invite with `expires_at` in the past raises `Refused`.
  - `test_tokens_stored_hashed`: no row in `invites` or `sessions` contains the raw token bytes.
  - `test_device_link_signs_in_same_user`: `redeem(device_link(user))` gives a session whose `user_for` is that user; after 11 minutes (an `expires_at` set in the past) it raises `Refused`.
  - `test_session_renews_on_use`: a session with `expires_at` 10 days away → after `user_for`, it is about 90 days away; an expired one → `None`.
  - `test_reinvite_keeps_context`: `invite` twice for one email → one user, context unchanged.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: invite links and sessions`.

### Task 8: The API

**Files:** Create `web/webapp/api.py`, `web/webtests/test_api.py`

**Interfaces:**
- Consumes: Tasks 2 to 7.
- Produces, all JSON under `/api`, every route but the two invite routes needing the session cookie `wt_session` (else 401):
  - `GET /invite/{token}` → a plain page with one button, "Sign in to Working Title", that POSTs the token; it doesn't redeem.
  - `POST /api/invite/redeem` body `{"token"}` → redeems, sets the cookie, 303 to `/`. A refused invite → 410.
  - `GET /api/me` → `{"app_name": "Working Title", "email": ...}`.
  - `GET /api/options` → `{"minutes": [10, 15, 20, 25, 30, 45], "goals": [...], "presets": [...]}`, goals and presets read from `tools/sessions.py` and `tools/catalog.py` (shared knowledge only: the server process sets `SWEATCAST_HOME` to a path that doesn't exist before importing any engine module).
  - `GET /api/context` → `[{"path", "version", "updated_at"}]` (names only; bodies in Milestone 6).
  - `POST /api/jobs` body `{"kind": "brief", "goal", "minutes", "preset", "today"}` → `{"id"}` (202). `today` is the browser's local date (`YYYY-MM-DD`, within a day of the server's): the menu gate refuses a menu from another day, so the worker's UTC date must never stand in for the user's.
  - `GET /api/jobs/{id}` → `{"id", "state", "error", "result"}`.
  - `GET /api/jobs/{id}/events` → `text/event-stream`: each event as `id: <event id>\ndata: <json>\n\n`, resuming after `Last-Event-ID`; a `state` event when the job ends, then the stream closes. Woken by `LISTEN job_events`, with a 15 s keep-alive comment.
  - `POST /api/device-link` → `{"url", "expires_at"}` for the signed-in user.
  - `POST /api/sign-out`.
  - Everything else: the built client from `web/client/dist` (`index.html` for unknown paths).
- A job, event or file of another user is 404, the same as one that doesn't exist.

- [ ] **Step 1: Write the failing tests** (FastAPI `TestClient`):
  - `test_requires_session`: `GET /api/me` without a cookie → 401.
  - `test_invite_get_does_not_redeem`: `GET /invite/<token>` twice → 200 both times, and the invite's `used_at` is still null.
  - `test_invite_sets_cookie`: `POST /api/invite/redeem` → 303 to `/`, cookie `wt_session` HttpOnly; a second POST → 410.
  - `test_other_users_job_is_404`: user A's job id requested by user B → 404 on `/api/jobs/{id}` and `/events`.
  - `test_events_stream_until_done`: enqueue a brief job, run `worker.run_one` in a thread, read the stream → events `folder`, `brief`, `saved`, then `state` with `done`.
  - `test_device_link_needs_session`: `POST /api/device-link` without a cookie → 401; with one → a URL whose redeem signs in the same user.
  - `test_options_lists_goals`: `"strength"` in `goals`, `"bodyweight"` in `presets`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5: Commit** `web: the API and the job event stream`.

### Task 9: The client shell

**Files:** Create `web/client/` (Vite React TypeScript): `src/main.tsx`, `src/App.tsx`, `src/theme.css` (the Trail tokens from `ui-6-zones.html`'s `:root` and its dark block, guarded for a `data-theme` override), `src/sentence/model.ts`, `src/sentence/Sentence.tsx`, `src/sentence/TokenPopover.tsx`, `src/zones/Band.tsx`, `src/zones/Chat.tsx`, `src/zones/Panel.tsx`, `src/zones/ContextColumn.tsx`, `src/api.ts`, `src/sentence/model.test.ts`, `src/zones/Panel.test.tsx`

**Interfaces:**
- Consumes: the API (Task 8).
- Produces: `model.ts`: `type Token = {key: string; value: string | number; options: {value: string | number; label: string}[]; why: string}`; `type SentenceModel = {parts: (string | Token)[]}`; `buildWorkoutSentence(opts: Options, chosen: Chosen): SentenceModel`; `setToken(m: SentenceModel, key: string, value): SentenceModel` (pure); `toJobArgs(m: SentenceModel, today: string): {kind: "brief"; goal: string; minutes: number; preset: string; today: string}`.
- Layout as ui-6: the sticky band (wordmark "Working Title" on the left, the sentence, the button at its right end), then chat, the working panel, and the context column at 1700 px and wider (a drawer below). The context column gets a stronger edge than the mockup: its own surface colour (`--sheet` on `--base`) and a 1 px rule plus 24 px gap from the panel. Chat in Slice 1 holds one line: the agent arrives in Milestone 3. The panel shows the job's stages as they stream (Queued, Writing your folder, Reading your limits, Saved) and then the brief, rendered with `react-markdown` (raw HTML off). The context column lists the user's files by name, and under them a "Sign in another device" button that shows the link from `POST /api/device-link` as text and as a QR code (the `qrcode` npm package, drawn on a canvas), with its 10-minute expiry.
- Motion in Slice 1 only where ui-6 has it: a changed token rolls in (`roll` and `flash` keyframes), with `prefers-reduced-motion` turning it off. The copy pass comes later.

- [ ] **Step 1: Write the failing tests:**
  - `model.test.ts › setToken replaces only that token and is pure`.
  - `model.test.ts › toJobArgs reads minutes, goal and preset`: the default sentence gives `{kind: "brief", goal: "strength", minutes: 20, preset: "bodyweight", today: <the local date>}`.
  - `Panel.test.tsx › renders stages, then the brief`: given events `folder`, `brief`, `saved`, `state: done` and a result, the panel shows the brief's first heading; given `state: failed` it shows the error and no brief.
- [ ] **Step 2:** Run `npm test` in `web/client`. Expected: FAIL.
- [ ] **Step 3:** Implement. Fonts through `@fontsource/zilla-slab` and `@fontsource/figtree`. In dev, Vite proxies `/api` and `/invite` to `localhost:8000`.
- [ ] **Step 4:** Run `npm test` and `npm run build`. Expected: PASS, and `dist/index.html` exists.
- [ ] **Step 5:** Run the server and worker locally against a local Postgres (`web/README.md` says how), sign in with an invite link, press the button, and check the brief appears. Check at 390 px wide (no horizontal scroll) and at 1800 px (the context column shows), in light and dark.
- [ ] **Step 6: Commit** `web: the client shell, the sentence band and the brief panel`.

### Task 10: Deploy to staging

**Files:** Create `Dockerfile`, `.dockerignore`, `web/entrypoint.sh`; modify `web/README.md`

- [ ] **Step 1:** `Dockerfile`, two stages: `node:20-slim` runs `npm ci && npm run build` in `web/client`; `python:3.11-slim` installs `ffmpeg` and uv (the version CI pins), copies the repo, runs `uv sync --locked --extra web`, copies `web/client/dist`, and runs `web/entrypoint.sh`. `.dockerignore` as in Global constraints, plus `web/client/node_modules`.
- [ ] **Step 2:** Build locally: `docker build -t sweatcast-web .`, then `docker run --rm sweatcast-web sh -c 'ls me 2>&1; .venv/bin/python -c "import importlib.util as u; assert u.find_spec(\"pocket_tts\") is None"'`. Expected: no `me`, and the assert passes (the local voice isn't installed; `doctor` still reports the hardware as able until Milestone 2's web mode).
- [ ] **Step 3:** Check in Railway's dashboard that its GitHub app can read `RNCDev/sweatcast` (the CLI can't). Push `main`, then add the services from the repo: `railway add --repo RNCDev/sweatcast --branch main --service web` and the same for `worker`, in `staging`. Variables on both: `WT_ROLE` (`web` / `worker`), `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `WT_BASE_URL` (the web service's Railway domain, from `railway domain`), and `WT_MASTER_KEY`, generated and set in one pipe so it's never printed: `python3 -c 'import os,base64;print(base64.b64encode(os.urandom(32)).decode())' | railway variable set WT_MASTER_KEY --stdin` (check the flag in `railway variable set --help` first; if there's no stdin form, set it from the dashboard).
- [ ] **Step 4:** Check that `production` didn't also pick up the new services (`railway environment production` then `railway status`); remove them there if it did. Deploy staging and check: `railway logs --service web` shows the migration applied and uvicorn listening; `railway run --service web python -m webapp.admin invite <the maintainer's email>` prints a link; opening it and pressing the button shows the brief.
- [ ] **Step 5: Commit** `web: the image and the staging deploy`. Note the staging URL in `web/README.md`.

## Done for Slice 1

`./sweatcast test` passes with and without the `web` extra, CI passes with Postgres, and on staging an invited user gets from the invite link to a brief on their own stored context, with the job's stages streaming in. No language model, voice service, key or bucket is used yet.
