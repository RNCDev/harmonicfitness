#!/bin/sh
# One step from draft to deliverables: lint + export the .txt, then render the .mp3.
#
#   tools/build.sh <draft> "<name>" [render options...]
#   tools/build.sh workouts/drafts/x.draft.txt "Workout 2026-10-19 Ankle-Safe 25 min" --quality balanced
#
# Writes workouts/<name>.txt and workouts/<name>.mp3. Stops after the lint if it
# finds issues (fix and rerun). Set LINT_ONLY=1 to skip rendering.
set -e
DRAFT="$1"; NAME="$2"; shift 2 || { echo "usage: tools/build.sh <draft> \"<name>\" [render options]"; exit 64; }
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
VS_PY="$HOME/Library/Application Support/VoiceStudio/runtime/project/.venv/bin/python"

# Words per minute and voice come from the profile so there's one place to change them.
WPM="$(sed -n 's/^- Measured words per minute[^:]*: \([0-9][0-9]*\).*/\1/p' "$ROOT/knowledge/profile.md" | head -1)"
VOICE="$(sed -n 's/^- VoiceStudio voice: profile id \([A-Za-z0-9_-]*\).*/\1/p' "$ROOT/knowledge/profile.md" | head -1)"

python3 "$HERE/tts_build.py" "$DRAFT" --wpm "${WPM:-140}" --out "$ROOT/workouts/$NAME.txt"
[ -n "$LINT_ONLY" ] && exit 0

[ -x "$VS_PY" ] || { echo "VoiceStudio runtime not found at $VS_PY (open the VoiceStudio app once to install it)"; exit 1; }
LOG="${TMPDIR:-/tmp}/workout-render.log"
set +e
"$VS_PY" "$HERE/render.py" "$DRAFT" --out "$ROOT/workouts/$NAME.mp3" --voice "${VOICE:-demo0001}" "$@" 2>"$LOG"
STATUS=$?
# Model loading is chatty on stderr; only surface it when something went wrong.
[ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 2 ] && tail -20 "$LOG"
exit "$STATUS"
