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

Each listener's voice service keys (one per web voice service in the engine's `knowledge/services.toml`) are entered in the app's Settings panel (the gear, top right) and stored in the `user_keys` table (migration 005), one row per user and service, sealed with that user's data key; only the service name and a timestamp are plain. A key is trimmed, must be printable ASCII with no spaces (the engine's `keys.clean_value`) and 16 to 1024 characters.

The web process seals a key on entry and never opens one: `GET /api/keys` says only which services have a key, `PUT /api/keys/<service>` sets or replaces one and `DELETE` removes it. Only the worker opens a listener's keys, for a job, and passes them to the engine under the variable names in `services.toml` (such as `FISH_AUDIO_API_KEY`); the engine's output is scrubbed of them.

Every job runs the engine with `HARMONICFITNESS_WEB=1`: no local voices, "add a key" messages point at the app, a stock web coach by default, and the finished MP3 is kept for the app to upload.

## Agent

The app is a chat and a Settings drawer (the listener's coaches, their keys and their account). The coach works as Claude Code does on a listener's computer: one agent (Pydantic AI) follows the workout skill itself (`.claude/skills/workout/SKILL.md` and `research.md`, read from the engine at run time) under a short preamble (`webapp/agent/instructions.md`) that says what the web client offers in place of each Claude Code tool, as `AGENTS.md` does for Codex. Questions are asked in the chat and research is done in turn. A new listener (no experience level in their profile yet), or one who asks to be set up, also gets the setup skill: its quick start in the chat, keys added in Settings, the stock web coach for a keyed service made with `coaches make` (its sample plays in the chat), then a ten-minute first workout. The check-in may change `health.md`, with the listener's permission, as the skill says.

**Recording costs money, so it waits for the listener.** A full build is first only priced: the `run` tool lints the draft, counts its characters and prices them (`get cost`), and keeps the offer in the conversation; the chat shows a Record button with the price. `POST /api/conversations/{id}/record` reserves those characters from today's allowance (`spend`, `HARMONICFITNESS_DAILY_CHARS`, default 60,000 a day) and queues a turn in which the same build runs, with `--max-chars` set to the approved count. That turn loads the listener's kept clips (`clip_cache`, sealed, a week), so a re-record sends only lines that changed, and keeps the new ones. The worker keeps each MP3 the turn made for 24 hours (`media`, sealed with the user's data key) and adds it to the chat as a player with a download. `GET /api/media/{id}` serves it to its owner only (byte ranges for Safari; `?download=1` for a download; `Cache-Control: private` until it expires), and the worker deletes expired MP3s and week-old clips. MP3s never go into the store.

**Stop.** `POST /api/conversations/{id}/stop` flags the running job; the heartbeat looks every two seconds and sets the job's cancel event, which cancels the model run and kills the engine's process group (`engine.run(cancel=)`), so nothing keeps billing. The conversation says "Stopped."

**Logs.** The Logs button beside the gear opens a page of the listener's logged workouts (the chat stays as it was, behind it): each one's date, length, format, kit, coach, movements, topics and feedback, its script on request, a rating (positive, neutral or negative; pressing it again clears it), a line of feedback, and delete (after a confirm), with search, filters (rating, format, kit) and sorting in the page. `webapp/workouts.py` runs the engine's `workouts` command on the listener's files in a temporary folder, as `/api/start` does: `GET /api/workouts`, `GET /api/workouts/{ref}/script`, `POST /api/workouts/{ref}/feedback`, `PUT /api/workouts/{ref}/rating` and `DELETE /api/workouts/{ref}` (its folder and files too), where `ref` is the build id, or the workout's number when it has none. A change is written back against the versions read; a turn saving at the same moment makes it a 409, to try again.

**Leaving.** `GET /api/export` is every file as a ZIP laid out as `me/` (keys are never files here). `POST /api/account/delete`, with the password, deletes the user row and everything that hangs from it.

Its four tools (`webapp/agent/tools.py`):
- `run`: one `./harmonicfitness` command in the listener's folder (a full build gets 10 minutes, a turn 15). Allowed: brief, build (not `--follow` or `--clips-only`), check, content, coaches (list, last, measured, make, audition (not `--play`; one a turn), keep, forget-audition, archive), coverage, feeds, get, help, keys, log-session, movements, youtube. A voice design or save (`make`, `audition`, `keep`) gets 10 minutes. `me/...` paths in arguments become the folder's own; any other path is refused.
- `read_file`: `me/...` (never `me/.env`) and the engine's `knowledge/`, `.claude/skills/` and `coaches/`.
- `write_file`: `me/...` only; never `me/.env`, the kinds of file the store doesn't keep, or an audition's own files (only its narrative, `me/coaches/.auditions/<slug>.md`).
- `list_files`: under `me/`.

To save round trips, the worker does two things itself. On a conversation's first turn it runs step 1 of the skill before the first model request, all at once (`check`, `content plan --minutes 25`, `get coach`, the coach's `get route`, `coaches list`, and reads of `profile.md`, `training.md`, `health.md` and `log.md`), and hands the results to the model with the listener's first message. On each later turn it starts `feeds` in the background as the turn begins, unless today's sheet is already there; the model's `run feeds` waits for that run instead of starting another, and the turn ends only once it has finished.

**A coach of their own.** The coach skill comes with the workout skill when the listener asks for a new coach or a different voice, and while an audition waits for their pick. It runs as on a computer, in the chat: the narrative from their answers, `coaches audition` on every keyed service (about a cent a service where the cost is published), each candidate in the chat as a player labeled by letter and cost a workout (never the service), then next turn `coaches keep` for the ones they name and `coaches forget-audition`, which deletes Gemini's unkept voices. The audition's files (its narrative, candidates list and each candidate's WAV and MP3) are kept with the listener's files until it's closed, since `keep` sends the chosen WAV to its service a turn later; MP3s and WAVs elsewhere are still never stored.

Safety is the engine's: the brief's safe menu and the build's menu gate (movements off the menu, one side only, names the catalog doesn't hold) refuse what the writer gets wrong.

A conversation is a series of short `turn` jobs. Each runs one turn in the listener's temporary folder with their own language-model key, then saves the conversation (its history and chat lines) sealed with their data key, and writes back the files its folder changed, never `health.md`. A turn stops at 60 model requests, 120 tool calls, 3,000,000 tokens or fifteen minutes; nothing is retried (`max_retries=0`, 180 seconds per request).

The providers are Claude (`claude-sonnet-5-5`), ChatGPT (`gpt-6.1-sol`) and Gemini (`gemini-3.8-flash`); `HARMONICFITNESS_PROVIDERS` names the ones offered, on both services (default `anthropic`). A model key is stored like a voice key, and only that job's model client holds it: the engine's environment never gets it.

While a turn runs, the chat shows each step in plain words ("Checking today's safety limits", "Recording your workout"), never a command or a file's name, and, while the model itself works between steps, a live line saying what it's thinking about ("Reading your message", "Writing your script"), which goes once it's done. A step running longer than eight seconds shows its own clock, and past 25 seconds a line says why it's a long one. A listener not set up yet who asks for a new coach gets the coach first; setup waits until it's made.

The model provider sees the files the agent reads (the profile, health and log among them), the engine's output, the skill, the chat, and the local date and time.

The page opens fresh: a finished conversation isn't shown again. It opens on one that isn't done: one still working, which it follows (a reload in the middle of a turn keeps its steps and Stop), or one from today waiting on the listener (the coach spoke last, or a Record offer is open), as long as it hasn't failed or recorded a workout yet. "New workout" clears the page; the next message starts a new conversation, as does a message after a conversation from an earlier day.

**The first screen.** `GET /api/start` gives what the page's opening sentence is filled in with ("Hey, coach Reed, I'd like a 25-minute strength workout at home. Go easy on my left knee today."; each blank opens its choices, and the second line opens a body chart: areas head to feet, each side a three-way toggle tapped from OK to "go easy" to "keep off"): the web coaches, stock and the listener's own, each with whether its service has a key here, the one used last (else the first with a key) first and marked current; the profile's kits, then the engine's presets, each with words for "at ..." ("a hotel room"); the usual length from the profile's Default session (10 to 60, else 25); `health.md`'s limits; a suggestion from `coverage` (a body part not trained this week, or the days since the last session; null with nothing to say); and whether setup is still quick. It writes the listener's files to a temporary folder and runs `coaches list --json` and `coverage --json` there; it changes nothing. The sentence goes as the first message, and the agent takes its answers as the check-in's (`agent/instructions.md`); a limit from `health.md` can be tightened there for the day, never loosened. Below it, "Or ask for something else" lists the other common asks, each with a line saying what it does (an injury, equipment, what fills the rests, a coach, feedback).

**The look.** Moonrise, after Ansel Adams' "Moonrise, Hernandez": dark only, with a faint moving pattern behind every page (`client/src/Sky.tsx`), the listener's choice in Settings: Flow (fine lines drifting sideways, an SVG translated in a loop) or Field (a grid of dots on a canvas, crossed by a ripple from the top right every seven seconds). Both hold still under the system's reduced-motion setting and brighten a little while the coach works. The choice is saved per account (`users.sky`, migration 011, null meaning Flow): `GET /api/me` returns it as `sky`, and `PUT /api/sky` with `{"sky": "flow" | "field"}` sets it (anything else is 422). Big Shoulders Display for headings, the request and buttons; IBM Plex Sans Condensed for the rest; the logo's coral for the request's fixed words, cream for everything you act on.

Routes: `GET /api/me`, `PUT /api/sky`, `PUT /api/coach` (`{"slug", "day"}`: the coach chosen in Settings or the sentence, kept in `users.coach` and `coach_day`, migration 012, as the first screen's coach and the chat's until a workout logged on a later day used another), `GET /api/start`, `POST /api/conversations`, `GET /api/conversations/latest`, `GET /api/conversations/{id}`, `POST /api/conversations/{id}/messages`, `.../record` and `.../stop`; `GET /api/media/{id}`; `POST /api/import`, `GET /api/export`, `POST /api/account/delete`.

## Run it locally

With Postgres running and the web extra installed (`uv sync --extra web`), one command runs the server and the worker together in one terminal, each line labeled `[web]` or `[worker]`; Ctrl-C stops both:

    web/dev.sh          # builds the client, then serves it at http://localhost:8000
    web/dev.sh hot      # adds Vite at http://localhost:5173, which reloads as you edit the client
    web/dev.sh reset    # deletes the local database and key, for a fresh start

It makes the database `harmonicfitness_dev` (`HARMONICFITNESS_DEV_DB` changes it) and a master key in `.cache/webdev/` (git-ignored) the first time, and keeps both between runs. `HARMONICFITNESS_PROVIDERS`, if set in your shell, passes through.

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

The root `Dockerfile` builds one image (the client built in a Node stage, then the engine and `web/` on `python:3.11-slim` with ffmpeg and the `web` extra only: no local voices), and `.railway/railway.ts` (Railway's infrastructure as code, which replaced `railway.json` in 0.25.0) points both services' builder at it. Railway runs it as two services from the same repo, told apart by `HARMONICFITNESS_ROLE`; `web/entrypoint.sh` starts the right one:

| Service | `HARMONICFITNESS_ROLE` | Runs |
|---|---|---|
| web | `web` | uvicorn on `$PORT` (default 8000): applies the migrations, then serves the API and client. Its health check is `/healthz`. |
| worker | `worker` | `python -m webapp.worker`: waits until the migrations are applied (up to two minutes, then exits 3), then runs jobs. |

Variables on both services: `HARMONICFITNESS_ROLE`, `DATABASE_URL` (`${{Postgres.DATABASE_URL}}`), `HARMONICFITNESS_BASE_URL` (the web service's public address, `https://...`) and `HARMONICFITNESS_MASTER_KEY` (32 random bytes, base64; the same on both, and keep a copy: files stored under another key can't be read). Railway supplies `PORT`. On the web service only, optionally `HARMONICFITNESS_REGISTRATION` (`open`, the default, or `closed`).

**The project's settings live in `.railway/railway.ts`:** the services, Postgres and its volume, the `media` bucket, each service's build (the Dockerfile), restart policy and the web's health check, and the names of the variables. Every variable is `preserve()`, so its value stays as set in Railway and never appears in the file; keep it that way (never `railway config pull --include-variables`), since the repo is public. To change a setting, edit the file, then from the repo root:

    (cd .railway && npm ci)   # once: Railway's SDK (railway, pinned), which the file imports
    railway config plan       # what would change; changes nothing
    railway config apply      # asks before applying

**Deploy from the GitHub repo (`RNCDev/harmonicfitness`, branch `main`), never with `railway up`**: only committed files reach the server, and `me/` is never one of them (`.dockerignore` leaves it out too).

The repo is `/app` and its environment `/app/.venv`, which `./harmonicfitness` finds on its own; `HARMONICFITNESS_PYTHON` names it, so a job never runs uv or reaches the network. The container runs as a non-root user.

**Admin on Railway:** open a shell in the running web service with `railway ssh --service web`, then

    cd /app/web && python -m webapp.admin reset-password <username>

(`python` is the image's environment, and the service's variables are in the shell's environment. If your shell lacks them, `railway run --service web` runs the command on your computer against the same variables, with `DATABASE_URL` needing Railway's public database address instead of the private one.)
