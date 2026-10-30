#!/usr/bin/env bash
# Run the web app on this computer, in one terminal: the server and the worker (and with `hot`, Vite's dev
# server too), their output side by side, all stopped by one Ctrl-C. Needs Postgres running locally.
#
#   web/dev.sh          build the client, then serve it at http://localhost:8000
#   web/dev.sh hot      the same, plus Vite at http://localhost:5173, which reloads as you edit the client
#   web/dev.sh reset    delete the local database and key: the next run starts with no accounts
#
# The database is harmonicfitness_dev (HARMONICFITNESS_DEV_DB changes it); the master key is made once and kept
# in .cache/webdev/ (git-ignored). Your shell's HARMONICFITNESS_PROVIDERS, if set, passes through.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/web"
STATE="$ROOT/.cache/webdev"
DB="${HARMONICFITNESS_DEV_DB:-harmonicfitness_dev}"
PORT=8000
PY="$ROOT/.venv/bin/python"

say() { printf 'dev: %s\n' "$*"; }
die() { printf 'dev: %s\n' "$*" >&2; exit 1; }

# Postgres's tools: on the PATH, else Homebrew's keg (postgresql@NN isn't linked by default)
pg() {
  local tool="$1"; shift
  if command -v "$tool" >/dev/null 2>&1; then "$tool" "$@"; return; fi
  local keg
  for keg in /opt/homebrew/opt/postgresql@* /usr/local/opt/postgresql@*; do
    if [ -x "$keg/bin/$tool" ]; then "$keg/bin/$tool" "$@"; return; fi
  done
  die "can't find Postgres's $tool. Install Postgres (brew install postgresql@16) and start it."
}

reset() {
  pg dropdb --if-exists --force "$DB"   # --force: even while web/dev.sh still has it open
  rm -rf "$STATE"
  say "deleted the database $DB and the local key. The next run starts fresh."
}

up() {
  local hot="$1"
  pg pg_isready -q || die "Postgres isn't running. Start it (brew services start postgresql@16), then run this again."
  [ -x "$PY" ] || die "no Python environment yet: run ./harmonicfitness setup first."
  "$PY" -c "import fastapi, psycopg" 2>/dev/null \
    || die "the web extra isn't installed: run uv sync --extra web (add --extra cpu to keep local voices)."

  if ! pg psql -lqt | cut -d'|' -f1 | grep -qw "$DB"; then
    pg createdb "$DB"
    say "made the database $DB"
  fi
  mkdir -p "$STATE"
  if [ ! -s "$STATE/master_key" ]; then
    (umask 077; "$PY" -c 'import base64, os; print(base64.b64encode(os.urandom(32)).decode())' > "$STATE/master_key")
  fi

  export DATABASE_URL="postgresql://localhost/$DB"
  export HARMONICFITNESS_BASE_URL="http://localhost:$PORT"
  export HARMONICFITNESS_MASTER_KEY="$(cat "$STATE/master_key")"

  [ -d "$WEB/client/node_modules" ] || (cd "$WEB/client" && npm ci)
  if [ "$hot" = no ]; then
    say "building the client"
    (cd "$WEB/client" && npm run build --silent) >/dev/null
  fi

  # one Ctrl-C (or any of them stopping) stops them all, and waits for the worker to finish what it's doing
  # only what this script started: never the shell or script that ran it
  killtree() { local p; for p in $(pgrep -P "$1"); do killtree "$p"; done; kill -TERM "$1" 2>/dev/null || true; }
  cleanup() {
    trap - INT TERM EXIT
    say "stopping"
    local c
    for c in $(pgrep -P $$); do killtree "$c"; done
    wait 2>/dev/null || true
    say "stopped. Your accounts and keys are kept; web/dev.sh reset deletes them."
    exit 0
  }
  trap cleanup INT TERM EXIT
  run() {   # run <label> <dir> <command...>: its output with the label in front of each line
    local label="$1" dir="$2"; shift 2
    (cd "$dir" && "$@" 2>&1 | sed -u "s/^/[$label] /") &
  }
  run web "$WEB" "$ROOT/.venv/bin/uvicorn" webapp.api:create_app_from_env --factory --no-access-log \
    --host 127.0.0.1 --port "$PORT"
  run worker "$WEB" "$PY" -m webapp.worker
  if [ "$hot" = yes ]; then
    run vite "$WEB/client" npx vite --port 5173 --strictPort
    say "open http://localhost:5173 (it reloads as you edit; the API is on :$PORT). Ctrl-C stops everything."
  else
    say "open http://localhost:$PORT. Ctrl-C stops everything."
  fi
  # bash 3.2 (the Mac's) has no `wait -n`: watch until any one of them stops
  while [ "$(jobs -rp | wc -l)" -eq "$(jobs -p | wc -l)" ]; do sleep 1; done
  say "one of them stopped; stopping the rest"
}

case "${1:-up}" in
  up) up no ;;
  hot) up yes ;;
  reset) reset ;;
  -h|--help|help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//' ;;
  *) die "unknown command: $1 (up, hot or reset)" ;;
esac
