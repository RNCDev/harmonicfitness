#!/bin/sh
# One step from draft to deliverables: lint + export the .txt, then render the .mp3.
#
#   tools/build.sh <draft> "<name>" [--voice <name>] [render options...]
#   tools/build.sh workouts/drafts/x.draft.txt "Workout 2026-10-19 Bench 25 min" --voice Coach
#
# Writes workouts/<name>.txt and workouts/<name>.mp3. Stops after the lint if it
# finds issues (fix and rerun). Set LINT_ONLY=1 to skip rendering. Without
# --voice, uses the first voice listed under Voices in knowledge/profile.md.
set -e
[ $# -ge 2 ] || { echo "usage: tools/build.sh <draft> \"<name>\" [--voice <name>] [render options]"; exit 64; }
DRAFT="$1"; NAME="$2"; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PROFILE="$ROOT/knowledge/profile.md"
VS_PY="$HOME/Library/Application Support/VoiceStudio/runtime/project/.venv/bin/python"

# The drafting guide (words per minute) and the default voice live in the profile.
WPM="$(sed -n 's/^- Measured words per minute[^:]*: \([0-9][0-9]*\).*/\1/p' "$PROFILE" | head -1)"
DEFAULT_VOICE="$(awk '/^- Voices/ {v=1; next} v && /^  - / {sub(/^  - /, ""); sub(/:.*/, ""); print; exit} v && !/^  / {exit}' "$PROFILE")"

# The lint predicts spoken length, so it needs the same voice and speed as the render.
VOICE=""; SPEED=""; PREV=""
for ARG in "$@"; do
  case "$PREV" in --voice) VOICE="$ARG" ;; --speed) SPEED="$ARG" ;; esac
  PREV="$ARG"
done
if [ -z "$VOICE" ]; then VOICE="${DEFAULT_VOICE:-demo0001}"; set -- "$@" --voice "$VOICE"; fi

python3 "$HERE/tts_build.py" "$DRAFT" --voice "$VOICE" ${SPEED:+--speed "$SPEED"} \
  --wpm "${WPM:-170}" --out "$ROOT/workouts/$NAME.txt"
[ -n "$LINT_ONLY" ] && exit 0

[ -x "$VS_PY" ] || { echo "VoiceStudio runtime not found at $VS_PY (open the VoiceStudio app once to install it)"; exit 1; }
LOG="${TMPDIR:-/tmp}/workout-render.log"
set +e
"$VS_PY" "$HERE/render.py" "$DRAFT" --out "$ROOT/workouts/$NAME.mp3" "$@" 2>"$LOG"
STATUS=$?
# Model loading is chatty on stderr; only surface it when something went wrong.
[ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 2 ] && tail -20 "$LOG"
exit "$STATUS"
