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
