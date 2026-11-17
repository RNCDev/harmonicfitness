#!/bin/sh
# The fresh-clone smoke test (2026-11-17): a new listener's first minutes on this computer, the commands the setup
# skill runs, each expected to succeed. CI runs it on Linux; run it by hand (on any system) as
#
#   sh tools/smoke.sh
#
# It sets up in a context folder of its own (a new temporary one, unless HARMONICFITNESS_HOME names one), so a
# listener's me/ is never touched, then checks it, writes a brief and lints the smoke-test draft with a web coach.
# No voice is sent anything and no MP3 is made: a lint needs no key, so the key file holds a stand-in. About half a
# minute once uv's cache is warm.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [ -z "${HARMONICFITNESS_HOME:-}" ]; then
  HARMONICFITNESS_HOME="$(mktemp -d)/me"
  export HARMONICFITNESS_HOME
fi
KEYS="$(mktemp)"
trap 'rm -f "$KEYS"' EXIT
# a well-formed Gemini key that opens nothing: the lint reads the coach's pace, never the key
printf 'GEMINI_API_KEY=AIzaSmokeTestSmokeTestSmokeTestSmoke00\n' > "$KEYS"

step() {
  echo "== ./harmonicfitness $*"
  ./harmonicfitness "$@"
}

step setup --no-models
step doctor --short
step check
step brief --minutes 15 --goal strength --preset bodyweight > /dev/null
HARMONICFITNESS_KEYS="$KEYS" step get route --coach "Coach Wade"
HARMONICFITNESS_KEYS="$KEYS" step build knowledge/smoke-test.draft.txt smoke --coach "Coach Wade" --lint-only > /dev/null
echo "smoke: a fresh clone sets up, checks, briefs and lints"
