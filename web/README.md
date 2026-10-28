# web/

The web client for HarmonicFitness, called "HarmonicFitness" in the app itself: a FastAPI server (`webapp/`) that runs the engine for a listener from a browser. It is an optional extra; a command-line install doesn't grow.

Install its dependencies:

    uv sync --extra web

On a computer that also has local voices, keep the voice engine's extra too (a sync without it uninstalls PyTorch):

    uv sync --extra cpu --extra web

Run its tests (`./harmonicfitness test` runs them after the engine's, or prints a skip line when the extra isn't installed):

    .venv/bin/python -m unittest discover -s web/webtests -t web -v

Set `HARMONICFITNESS_TEST_DATABASE_URL` (for example `postgresql://postgres@localhost:5432/postgres`) to a Postgres database to enable the database tests; without it they are skipped.

## Admin

People make their own accounts (username and password) while registration is open. Set `HARMONICFITNESS_REGISTRATION=closed` on the web service to stop new accounts; sign-in keeps working.

For someone who forgot their password, run from `web/` (or with `web/` on `PYTHONPATH`), with `DATABASE_URL`, `HARMONICFITNESS_BASE_URL` and `HARMONICFITNESS_MASTER_KEY` set:

    python -m webapp.admin reset-password <username>

It clears their password, signs out their devices and prints a one-time sign-in link (24 hours) and nothing else; send it to them yourself. Opening it signs them in, and the app asks for a new password. It never migrates: against a database still missing a migration (one the web service hasn't applied yet) it refuses, exits 1, and says to deploy first.

## Keys

Each listener's voice service keys (one per web voice service in the engine's `knowledge/services.toml`) are entered in the app's Keys box and stored in the `user_keys` table (migration 005), one row per user and service, sealed with that user's data key; only the service name and a timestamp are plain. A key is trimmed, must be printable ASCII with no spaces (the engine's `keys.clean_value`) and 16 to 1024 characters.

The web process seals a key on entry and never opens one: `GET /api/keys` says only which services have a key, `PUT /api/keys/<service>` sets or replaces one and `DELETE` removes it. Only the worker opens a listener's keys, for a job, and passes them to the engine under the variable names in `services.toml` (such as `FISH_AUDIO_API_KEY`); the engine's output is scrubbed of them.

Every job runs the engine with `HARMONICFITNESS_WEB=1`: no local voices, "add a key" messages point at the app, a stock web coach by default, and the finished MP3 is kept for the app to upload.

## Agent

The app is a chat and a Keys drawer. The coach works as Claude Code does on a listener's computer: one agent (Pydantic AI) follows the workout skill itself (`.claude/skills/workout/SKILL.md` and `research.md`, read from the engine at run time) under a short preamble (`webapp/agent/instructions.md`) that says what the web client offers in place of each Claude Code tool, as `AGENTS.md` does for Codex. Questions are asked in the chat, research is done in turn, and the build runs with `--lint-only` only: the audio comes in a later version.

Its four tools (`webapp/agent/tools.py`):
- `run`: one `./harmonicfitness` command in the listener's folder. Allowed: brief, build (`--lint-only`), check, content, coaches (list), coverage, feeds, get, help, keys, log-session, movements, youtube. `me/...` paths in arguments become the folder's own; any other path is refused.
- `read_file`: `me/...` (never `me/.env`) and the engine's `knowledge/`, `.claude/skills/` and `coaches/`.
- `write_file`: `me/...` only; never `me/.env`, `me/health.md` (read-only here for now) or the kinds of file the store doesn't keep.
- `list_files`: under `me/`.

To save round trips, the worker does two things itself. On a conversation's first turn it runs step 1 of the skill before the first model request, all at once (`check`, `content plan --minutes 25`, `get coach`, the coach's `get route`, `coaches list`, and reads of `profile.md`, `training.md`, `health.md` and `log.md`), and hands the results to the model with the listener's first message. On each later turn it starts `feeds` in the background as the turn begins, unless today's sheet is already there; the model's `run feeds` waits for that run instead of starting another, and the turn ends only once it has finished.

Safety is the engine's: the brief's safe menu and the build's menu gate (movements off the menu, one side only, names the catalog doesn't hold) refuse what the writer gets wrong.

A conversation is a series of short `turn` jobs. Each runs one turn in the listener's temporary folder with their own language-model key, then saves the conversation (its history and chat lines) sealed with their data key, and writes back the files its folder changed, never `health.md`. A turn stops at 60 model requests, 120 tool calls, 3,000,000 tokens or ten minutes; nothing is retried (`max_retries=0`, 180 seconds per request).

The providers are Claude (`claude-sonnet-5-5`), ChatGPT (`gpt-6.1-sol`) and Gemini (`gemini-3.8-flash`); `HARMONICFITNESS_PROVIDERS` names the ones offered, on both services (default `anthropic`). A model key is stored like a voice key, and only that job's model client holds it: the engine's environment never gets it.

The model provider sees the files the agent reads (the profile, health and log among them), the engine's output, the skill, the chat, and the local date and time.

"New chat" clears the page; the next message starts a new conversation, as does a message after a conversation from an earlier day.

Routes: `POST /api/conversations`, `GET /api/conversations/latest`, `GET /api/conversations/{id}` and `POST /api/conversations/{id}/messages`.

## Serve

Run from `web/`, with `DATABASE_URL`, `HARMONICFITNESS_BASE_URL` and `HARMONICFITNESS_MASTER_KEY` set (the same as the admin commands). It applies any database migrations once at startup, then serves the API and, when `web/client/dist` has been built, the client:

    uvicorn webapp.api:create_app_from_env --factory --no-access-log --host 0.0.0.0 --port 8000

`--no-access-log` matters: a one-time sign-in link's page is `GET /link/<token>`, so an access log would write those tokens to the logs. The server itself logs no token, job argument, event or result.

The session cookie is `Secure` unless `HARMONICFITNESS_BASE_URL` starts with `http://localhost` or `http://127.0.0.1`, so local development works over plain http. Every POST must carry an `Origin` (or `Referer`) of `HARMONICFITNESS_BASE_URL`'s origin, so set it to the address the browser uses.

## Client

The browser client is in `client/` (Vite, React and TypeScript; Node 20 or later). From `web/client`:

    npm ci
    npm test          # the client's own tests
    npm run build     # writes dist/, which the server above serves
    npm run dev       # a dev server on :5173 that sends /api and /link to the server on :8000

## Deploy

The root `Dockerfile` builds one image (the client built in a Node stage, then the engine and `web/` on `python:3.11-slim` with ffmpeg and the `web` extra only: no local voices), and `railway.json` points Railway's builder at it. Railway runs it as two services from the same repo, told apart by `HARMONICFITNESS_ROLE`; `web/entrypoint.sh` starts the right one:

| Service | `HARMONICFITNESS_ROLE` | Runs |
|---|---|---|
| web | `web` | uvicorn on `$PORT` (default 8000): applies the migrations, then serves the API and client. Set its health check to `/healthz` in Railway (not in `railway.json`, which both services share). |
| worker | `worker` | `python -m webapp.worker`: waits until the migrations are applied (up to two minutes, then exits 3), then runs jobs. |

Variables on both services: `HARMONICFITNESS_ROLE`, `DATABASE_URL` (`${{Postgres.DATABASE_URL}}`), `HARMONICFITNESS_BASE_URL` (the web service's public address, `https://...`) and `HARMONICFITNESS_MASTER_KEY` (32 random bytes, base64; the same on both, and keep a copy: files stored under another key can't be read). Railway supplies `PORT`. On the web service only, optionally `HARMONICFITNESS_REGISTRATION` (`open`, the default, or `closed`).

**Deploy from the GitHub repo (`RNCDev/harmonicfitness`, branch `main`), never with `railway up`**: only committed files reach the server, and `me/` is never one of them (`.dockerignore` leaves it out too).

The repo is `/app` and its environment `/app/.venv`, which `./harmonicfitness` finds on its own; `HARMONICFITNESS_PYTHON` names it, so a job never runs uv or reaches the network. The container runs as a non-root user.

**Admin on Railway:** open a shell in the running web service with `railway ssh --service web`, then

    cd /app/web && python -m webapp.admin reset-password <username>

(`python` is the image's environment, and the service's variables are in the shell's environment. If your shell lacks them, `railway run --service web` runs the command on your computer against the same variables, with `DATABASE_URL` needing Railway's public database address instead of the private one.)
