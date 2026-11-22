#!/usr/bin/env bash
# Bring the repo's .env up to date with the live site's secrets on Fly, for developing on another computer
# (maintainer only). Needs the Fly CLI, signed in (fly auth login). Windows: run it from Git Bash, or use
# web/env-sync.ps1 in PowerShell.
#
#   web/env-sync.sh            the keys the local site needs (web/dev.sh): OpenRouter and Clerk
#   web/env-sync.sh --bucket   and the media bucket's, for the maintainer's uploads (tools/bucket.py)
#
# Each name is read from a running machine's environment and written to .env in place of its old line; every
# other line is kept. No value is ever printed. Live Stripe keys, the database and the master key are never
# copied: local development makes its own. Keys that live only on your computers (GEMINI_API_KEY,
# OPENROUTER_MANAGEMENT_KEY) are named at the end when they're missing: add those by hand.
set -euo pipefail

APP="${HARMONICFITNESS_FLY_APP:-harmonicfitness}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
NAMES="OPENROUTER_API_KEY CLERK_PUBLISHABLE_KEY CLERK_SECRET_KEY"
BUCKET="AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_ENDPOINT_URL_S3 BUCKET_NAME"
LOCAL_ONLY="GEMINI_API_KEY OPENROUTER_MANAGEMENT_KEY"

die() { printf 'env-sync: %s\n' "$*" >&2; exit 1; }

case "${1:-}" in
  "") ;;
  --bucket) NAMES="$NAMES $BUCKET" ;;
  *) die "usage: web/env-sync.sh [--bucket]" ;;
esac
command -v fly >/dev/null 2>&1 || die "the Fly CLI isn't installed: https://fly.io/docs/flyctl/install/"
fly auth whoami >/dev/null 2>&1 || die "not signed in to Fly: run fly auth login"
git -C "$ROOT" check-ignore -q .env || die ".env isn't git-ignored here: refusing to write keys into it"

# the machine's whole environment, read into memory only and filtered here, so one connection serves every name
remote="$(fly ssh console -a "$APP" -C env 2>/dev/null)" || die "couldn't reach a running machine of $APP"
remote="${remote//$'\r'/}"

tmp="$(mktemp "$ROOT/.env.sync.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
chmod 600 "$tmp"
[ -f "$ENV_FILE" ] && cat "$ENV_FILE" > "$tmp"

updated=() missing=()
for name in $NAMES; do
  line="$(printf '%s\n' "$remote" | grep -m1 "^$name=" || true)"
  if [ -z "$line" ] || [ "$line" = "$name=" ]; then missing+=("$name"); continue; fi
  grep -v "^[[:space:]]*$name[[:space:]]*=" "$tmp" > "$tmp.next" || true
  printf '%s\n' "$line" >> "$tmp.next"
  mv "$tmp.next" "$tmp"
  updated+=("$name")
done
unset remote line
chmod 600 "$tmp"   # yours alone, as the engine keeps me/.env
mv "$tmp" "$ENV_FILE"
trap - EXIT

printf 'env-sync: %s updated from %s: %s\n' "$(basename "$ENV_FILE")" "$APP" "${updated[*]:-nothing}"
[ ${#missing[@]} -eq 0 ] || printf 'env-sync: not set on %s, so left as they were: %s\n' "$APP" "${missing[*]}"
absent=()
for name in $LOCAL_ONLY; do grep -q "^[[:space:]]*$name[[:space:]]*=" "$ENV_FILE" || absent+=("$name"); done
[ ${#absent[@]} -eq 0 ] || printf 'env-sync: only on your other computers, add by hand if you need them: %s\n' "${absent[*]}"
