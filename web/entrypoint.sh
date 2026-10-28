#!/bin/sh
# The container's start: WT_ROLE=web serves the API and client, WT_ROLE=worker runs jobs.
set -eu
APP="${WT_APP_DIR:-/app}"
case "${WT_ROLE:-}" in
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
    echo "entrypoint: WT_ROLE must be 'web' or 'worker' (got '${WT_ROLE:-}')" >&2
    exit 64
    ;;
esac
