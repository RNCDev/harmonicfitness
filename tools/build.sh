#!/bin/sh
# One step from draft to deliverables: lint + export the .txt, then render the .mp3.
#
#   tools/build.sh <draft> "<name>" [--voice <name>] [render options...]
#   tools/build.sh workouts/drafts/x.draft.txt "Workout 2026-10-19 Bench 25 min" --voice Coach
#
# Writes workouts/<name>.txt and workouts/<name>.mp3. Stops after the lint if it
# finds issues (fix and rerun). Set LINT_ONLY=1 to skip rendering. Without
# --voice, uses the first voice listed under Voices in knowledge/profile.md.
#
# --clips-only renders and caches the clips of whatever the draft holds so far, with
# no lint, MP3 or Drive copy: start it in the background on the first half of a
# draft, and the full build later renders only what's new or edited.
#
# A voice no render has measured yet would be timed from a guess, so a session
# render refuses it: render the smoke test with it first
# (workouts/drafts/smoke-test.draft.txt, which measures it), or set ALLOW_ESTIMATED=1.
set -e
[ $# -ge 2 ] || { echo "usage: tools/build.sh <draft> \"<name>\" [--voice <name>] [render options]"; exit 64; }
DRAFT="$1"; NAME="$2"; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
PROFILE="$ROOT/knowledge/profile.md"
VS_PY="$HOME/Library/Application Support/VoiceStudio/runtime/project/.venv/bin/python"

# The drafting guide (words per minute), the default voice and the Drive folder live in
# the profile. If a line is reworded so it can't be found, say so instead of guessing.
[ -f "$PROFILE" ] || { echo "Profile not found at $PROFILE"; exit 1; }
WPM="$(sed -n 's/^- Measured words per minute[^:]*: \([0-9][0-9]*\).*/\1/p' "$PROFILE" | head -1)"
DEFAULT_VOICE="$(awk '/^- Voices/ {v=1; next} v && /^  - / {sub(/^  - /, ""); sub(/:.*/, ""); print; exit} v && !/^  / {exit}' "$PROFILE")"

# The lint predicts spoken length, so it needs the same voice and speed as the render.
VOICE=""; SPEED=""; PREV=""; CLIPS_ONLY=""
for ARG in "$@"; do
  case "$PREV" in --voice) VOICE="$ARG" ;; --speed) SPEED="$ARG" ;; esac
  [ "$ARG" = "--clips-only" ] && CLIPS_ONLY=1
  PREV="$ARG"
done
SMOKE=""; [ "$(basename "$DRAFT")" = "smoke-test.draft.txt" ] && SMOKE=1
if [ -z "$VOICE" ]; then
  [ -n "$DEFAULT_VOICE" ] || { echo "No --voice given, and no default voice found in $PROFILE."
    echo "Expected a '- Voices' line followed by indented '  - <name>: ...' lines; the first is the default."; exit 1; }
  VOICE="$DEFAULT_VOICE"; set -- "$@" --voice "$VOICE"
fi
[ -n "$WPM" ] || echo "Note: no '- Measured words per minute ...: <n>' line in the profile; the word guide assumes 185."

# Both steps run on VoiceStudio's bundled Python, so no other Python is needed.
[ -x "$VS_PY" ] || { echo "VoiceStudio runtime not found at $VS_PY (open the VoiceStudio app once to install it)"; exit 1; }
LOG="${TMPDIR:-/tmp}/workout-render.log"

if [ -n "$CLIPS_ONLY" ]; then
  # Rendering ahead while the rest of the draft is written: no lint, no MP3.
  set +e
  "$VS_PY" "$HERE/render.py" "$DRAFT" "$@" 2>"$LOG"
  STATUS=$?
  [ "$STATUS" -ne 0 ] && tail -20 "$LOG"
  exit "$STATUS"
fi

if [ -z "$SMOKE" ] && [ -z "$ALLOW_ESTIMATED" ] && [ -z "$LINT_ONLY" ] \
   && ! "$VS_PY" "$HERE/voices.py" --measured "$VOICE"; then
  echo "$VOICE's speaking rate hasn't been measured yet, so this draft's timing is a guess."
  echo "Render the smoke test with it first, which measures it, then rerun:"
  echo "  tools/build.sh workouts/drafts/smoke-test.draft.txt \"smoke-test\" --voice \"$VOICE\""
  echo "(or set ALLOW_ESTIMATED=1 to render anyway)"
  exit 3
fi

# The smoke test exists to measure a voice, so its lint never blocks the render.
"$VS_PY" "$HERE/tts_build.py" "$DRAFT" --voice "$VOICE" ${SPEED:+--speed "$SPEED"} \
  --wpm "${WPM:-185}" --out "$ROOT/workouts/$NAME.txt" ${SMOKE:+--force}
[ -n "$LINT_ONLY" ] && exit 0

set +e
"$VS_PY" "$HERE/render.py" "$DRAFT" --out "$ROOT/workouts/$NAME.mp3" "$@" 2>"$LOG"
STATUS=$?
# Model loading is chatty on stderr; only surface it when something went wrong.
[ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 2 ] && tail -20 "$LOG"
[ -n "$SMOKE" ] && exit "$STATUS"   # a voice check, not a workout: no Drive copy

# A finished MP3 also goes to the profile's Google Drive folder, which syncs to the phone.
DRIVE_FOLDER="$(sed -n 's/^- Google Drive folder[^:]*: \([^.]*\)\..*/\1/p' "$PROFILE" | head -1)"
if [ "$STATUS" -eq 0 ] && [ -z "$DRIVE_FOLDER" ]; then
  echo "No Drive copy: no '- Google Drive folder ...: <folder>.' line found in the profile; the MP3 is only in workouts/"
fi
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
