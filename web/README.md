# web/

The web client for sweatcast, called "Working Title" in the app itself: a FastAPI server (`webapp/`) that runs the engine for a listener from a browser. It is an optional extra; a command-line install doesn't grow.

Install its dependencies:

    uv sync --extra web

On a computer that also has local voices, keep the voice engine's extra too (a sync without it uninstalls PyTorch):

    uv sync --extra cpu --extra web

Run its tests (`./sweatcast test` runs them after the engine's, or prints a skip line when the extra isn't installed):

    .venv/bin/python -m unittest discover -s web/webtests -t web -v

Set `WT_TEST_DATABASE_URL` (for example `postgresql://postgres@localhost:5432/postgres`) to a Postgres database to enable the database tests; without it they are skipped.

## Admin

Run from `web/` (or with `web/` on `PYTHONPATH`), with `DATABASE_URL`, `WT_BASE_URL` and `WT_MASTER_KEY` set. Each prints the sign-in link and nothing else:

    python -m webapp.admin invite <email>
    python -m webapp.admin login-link <email>    # an existing user only

## Serve

Run from `web/`, with `DATABASE_URL`, `WT_BASE_URL` and `WT_MASTER_KEY` set (the same as the admin commands). It applies any database migrations once at startup, then serves the API and, when `web/client/dist` has been built, the client:

    uvicorn webapp.api:create_app_from_env --factory --no-access-log --host 0.0.0.0 --port 8000

`--no-access-log` matters: an invite's sign-in page is `GET /invite/<token>`, so an access log would write every sign-in token to the logs. The server itself logs no token, job argument, event or result.

The session cookie is `Secure` unless `WT_BASE_URL` starts with `http://localhost` or `http://127.0.0.1`, so local development works over plain http. Every POST must carry an `Origin` (or `Referer`) of `WT_BASE_URL`'s origin, so set it to the address the browser uses.

## Client

The browser client is in `client/` (Vite, React and TypeScript; Node 20 or later). From `web/client`:

    npm ci
    npm test          # the client's own tests
    npm run build     # writes dist/, which the server above serves
    npm run dev       # a dev server on :5173 that sends /api and /invite to the server on :8000

## Deploy

The root `Dockerfile` builds one image (the client built in a Node stage, then the engine and `web/` on `python:3.11-slim` with ffmpeg and the `web` extra only: no local voices), and `railway.json` points Railway's builder at it. Railway runs it as two services from the same repo, told apart by `WT_ROLE`; `web/entrypoint.sh` starts the right one:

| Service | `WT_ROLE` | Runs |
|---|---|---|
| web | `web` | uvicorn on `$PORT` (default 8000): applies the migrations, then serves the API and client. Set its health check to `/healthz` in Railway (not in `railway.json`, which both services share). |
| worker | `worker` | `python -m webapp.worker`: waits until the migrations are applied (up to two minutes, then exits 3), then runs jobs. |

Variables on both services: `WT_ROLE`, `DATABASE_URL` (`${{Postgres.DATABASE_URL}}`), `WT_BASE_URL` (the web service's public address, `https://...`) and `WT_MASTER_KEY` (32 random bytes, base64; the same on both, and keep a copy: files stored under another key can't be read). Railway supplies `PORT`.

**Deploy from the GitHub repo (`RNCDev/sweatcast`, branch `main`), never with `railway up`**: only committed files reach the server, and `me/` is never one of them (`.dockerignore` leaves it out too).

The repo is `/app` and its environment `/app/.venv`, which `./sweatcast` finds on its own; `SWEATCAST_PYTHON` names it, so a job never runs uv or reaches the network. The container runs as a non-root user.

**Admin in production:** open a shell in the running web service with `railway ssh --service web`, then

    cd /app/web && python -m webapp.admin invite <email>

(`python` is the image's environment, and the service's variables are in the shell's environment. If your shell lacks them, `railway run --service web` runs the command on your computer against the same variables, with `DATABASE_URL` needing Railway's public database address instead of the private one.)
