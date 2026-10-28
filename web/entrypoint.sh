#!/bin/sh
# The container's start: HARMONICFITNESS_ROLE=web serves the API and client, HARMONICFITNESS_ROLE=worker runs jobs.
set -eu
APP="${HARMONICFITNESS_APP_DIR:-/app}"
case "${HARMONICFITNESS_ROLE:-}" in
  web)
    cd "$APP/web"
    exec uvicorn webapp.api:create_app_from_env --factory --no-access-log \
      --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  worker)
    cd "$APP/web"
    # the worker itself waits until the web service has applied the migrations (db.wait_for_migrations)
    exec python -m webapp.worker
    ;;
  *)
    echo "entrypoint: HARMONICFITNESS_ROLE must be 'web' or 'worker' (got '${HARMONICFITNESS_ROLE:-}')" >&2
    exit 64
    ;;
esac
