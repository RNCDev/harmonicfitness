# Browser QAT profile: the HarmonicFitness web client

How a browser walk (the `browser-qat` skill) runs this repo's web client. The facts are in `web/README.md`
(Serve, Keys, Agent) and CLAUDE.md; this says only how a walk uses them.

## Serve

Locally, against a local Postgres only, never Fly's. Build the client, then start the web service and the
worker from `web/`, each in the background, with these variables set for the walk's processes only:

    cd web/client && npm run build
    export DATABASE_URL=postgresql://$USER@localhost:5432/hf_qat
    export HARMONICFITNESS_BASE_URL=http://localhost:8000
    export HARMONICFITNESS_MASTER_KEY=$(cat "$SCRATCH/hf_qat.key")   # 32 random bytes, base64, made once:
    #   head -c 32 /dev/urandom | base64 > "$SCRATCH/hf_qat.key"   (a throwaway: the database is too)
    export HARMONICFITNESS_PROVIDERS=google    # as on Fly: Gemini writes the workouts
    cd web
    HARMONICFITNESS_ROLE=web ../.venv/bin/uvicorn webapp.api:create_app_from_env --factory --no-access-log --port 8000
    HARMONICFITNESS_ROLE=worker ../.venv/bin/python -m webapp.worker

Make the database once: `createdb hf_qat` (Homebrew's `postgresql@16`, `/opt/homebrew/opt/postgresql@16/bin`).
The web service applies the migrations at startup. URL: http://localhost:8000. Ready when `GET /api/auth`
answers 200. No auto-reload: after a code change, rebuild the client and restart both processes.

## Sign in

A throwaway account made through the app's own sign-up: username `qat-<yyyymmdd>-<n>`, a password of
16 random characters. Write the username in the report before the first click.

A walk past the welcome card needs a real language-model key (Gemini, from Google AI Studio). The
maintainer keeps one as `GEMINI_API_KEY=` in the repo's root `.env` (git-ignored; never `me/.env`), and
the walk stores it in its own account, after signing up in the browser, with:

    .venv/bin/python web/qat_key.py --username <the walk's username> --password <its password>

(`--register` makes the account instead, for a walk that starts already signed up.) It reads only that
line, never prints the key, and refuses any server but localhost. The walker never opens `.env` itself.
Without the file, the owner adds the key in the walk's account in their own browser, or the walk stops at
the welcome card. A recording costs a few cents on that key.

## Writes

`persist: yes`, to `hf_qat` only. Never `DATABASE_URL` from Fly or anywhere else; refuse to walk if
`DATABASE_URL` isn't a `localhost` URL. Cleanup: delete the walk's account in the app (Settings > Account >
Delete my account), which removes its files, keys, chats and audio. Dry run: `psql hf_qat -c "select
username from users"` lists what's there; only the walk's own accounts may go. The whole `hf_qat`
database is a throwaway and can be dropped (`dropdb hf_qat`).

A walk on https://harmonicfitness.fly.dev/ (after a release) is read-only except for its own throwaway
account, deleted in the app at the end.

## Out of reach

- The agent's turns without a real model key (the walk stops at the welcome card).
- Timers in a headless browser run slow: the Working clock can look stalled; check it in a real browser
  before calling it a bug.
- Known noise: none yet.

## Allowed hosts

`localhost:8000` only. The model and voice services are reached by the worker, never the browser.

## Standing criteria

- **S1** the sign-in page says what the app is, and sign-up lands in the app with no error.
- **S2** no 401 on a page load before the page knows who is signed in.
- **S3** buttons look like buttons (filled or outlined), in light and dark.
- **S4** with no language-model key, a welcome card says what's needed and its button opens that key's row;
  the message box waits.
- **S5** the Settings drawer (the gear) shows the coaches, then one row per key (Gemini once), Required apart from Optional, and the account
  settings under their own heading.
- **S6** nothing shows a key, a file path or `me/.env`.

## Checks

    cd web/client && npm test && npm run build
    HARMONICFITNESS_TEST_DATABASE_URL=postgresql://$USER@localhost:5432/hf_webtest ./harmonicfitness test

## Evidence

`.playwright-mcp/` (git-ignored): `.playwright-mcp/YYYY-MM-DD-qat-<name>/`, with `report.md`.

## Commits

On `main` (this repo releases from main; see the maintainer's notes), one commit per fix, in the history's
style: `Web: <what changed, in plain words>`, a short body, and the co-author line.
