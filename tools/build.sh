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

# Both steps run on VoiceStudio's bundled Python, so no other Python is needed.
[ -x "$VS_PY" ] || { echo "VoiceStudio runtime not found at $VS_PY (open the VoiceStudio app once to install it)"; exit 1; }
"$VS_PY" "$HERE/tts_build.py" "$DRAFT" --voice "$VOICE" ${SPEED:+--speed "$SPEED"} \
  --wpm "${WPM:-185}" --out "$ROOT/workouts/$NAME.txt"
[ -n "$LINT_ONLY" ] && exit 0

LOG="${TMPDIR:-/tmp}/workout-render.log"
set +e
"$VS_PY" "$HERE/render.py" "$DRAFT" --out "$ROOT/workouts/$NAME.mp3" "$@" 2>"$LOG"
STATUS=$?
# Model loading is chatty on stderr; only surface it when something went wrong.
[ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 2 ] && tail -20 "$LOG"

# A finished MP3 also goes to the profile's Google Drive folder, which syncs to the phone.
DRIVE_FOLDER="$(sed -n 's/^- Google Drive folder[^:]*: \([^.]*\)\..*/\1/p' "$PROFILE" | head -1)"
if [ "$STATUS" -eq 0 ] && [ -n "$DRIVE_FOLDER" ]; then
  FOUND=""
  for DEST in "$HOME"/Library/CloudStorage/GoogleDrive-*/"My Drive/$DRIVE_FOLDER"; do
    [ -d "$DEST" ] || continue
    FOUND=1
    if cp "$ROOT/workouts/$NAME.mp3" "$DEST/"; then
      echo "Copied to Google Drive: My Drive/$DRIVE_FOLDER/$NAME.mp3"
    else
      echo "Couldn't copy to $DEST; the MP3 is only in workouts/"
    fi
  done
  [ -n "$FOUND" ] || echo "Google Drive folder My Drive/$DRIVE_FOLDER not found; the MP3 is only in workouts/"
fi
exit "$STATUS"
