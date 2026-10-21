#!/bin/sh
# One step from draft to deliverables: lint + export the .txt, then render the .mp3.
#
#   tools/build.sh <draft> "<name>" [--voice <name>] [render options...]
#   tools/build.sh me/workouts/drafts/x.draft.txt "Workout 2026-10-19 Bench 25 min" --voice "Chatterbox Coach"
#
# Writes me/workouts/<name>.txt and me/workouts/<name>.mp3 (the context folder is
# SWEATCAST_HOME if set). Stops after the lint if it finds issues (fix and rerun).
# Set LINT_ONLY=1 to skip rendering. Without --voice, uses the first voice listed
# under Voices in me/profile.md. After a render, copies the MP3 to the profile's
# "Copy finished MP3s to:" folder, if it names one.
#
# --clips-only renders and caches the clips of whatever the draft holds so far, with
# no lint, MP3 or copy: start it in the background on the first half of a draft,
# and the full build later renders only what's new or edited.
#
# A voice no render has measured yet would be timed from a guess, so a session
# render refuses it (exit 3): render the smoke test with it first
# (voices/smoke-test.draft.txt, which measures it), or set ALLOW_ESTIMATED=1.
set -e
[ $# -ge 2 ] || { echo "usage: tools/build.sh <draft> \"<name>\" [--voice <name>] [render options]"; exit 64; }
DRAFT="$1"; NAME="$2"; shift 2
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONTEXT="${SWEATCAST_HOME:-$ROOT/me}"
PROFILE="$CONTEXT/profile.md"
OUT_DIR="$CONTEXT/workouts"
PY="${SWEATCAST_PYTHON:-$ROOT/.venv/bin/python}"

[ -f "$PROFILE" ] || { echo "No profile at $PROFILE. Run tools/setup.sh first (it copies me.example/ to me/)."; exit 1; }
[ -x "$PY" ] || { echo "No Python environment at $PY. Run tools/setup.sh first (it makes .venv with uv)."; exit 1; }

# The drafting guide (words per minute), the default voice and the delivery folder live
# in the profile. If a line is reworded so it can't be found, say so instead of guessing.
WPM="$(sed -n 's/^- Measured words per minute[^:]*: \([0-9][0-9]*\).*/\1/p' "$PROFILE" | head -1)"
DEFAULT_VOICE="$(awk '/^- Voices/ {v=1; next} v && /^  - / {sub(/^  - /, ""); sub(/:.*/, ""); print; exit} v && !/^  / {exit}' "$PROFILE")"

# The lint predicts spoken length, so it needs the same voice as the render.
VOICE=""; PREV=""; CLIPS_ONLY=""
for ARG in "$@"; do
  [ "$PREV" = "--voice" ] && VOICE="$ARG"
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
mkdir -p "$OUT_DIR"
LOG="${TMPDIR:-/tmp}/sweatcast-render.log"

if [ -n "$CLIPS_ONLY" ]; then
  # Rendering ahead while the rest of the draft is written: no lint, no MP3.
  set +e
  "$PY" "$HERE/render.py" "$DRAFT" "$@" 2>"$LOG"
  STATUS=$?
  [ "$STATUS" -ne 0 ] && tail -20 "$LOG"
  exit "$STATUS"
fi

if [ -z "$SMOKE" ] && [ -z "$ALLOW_ESTIMATED" ] && [ -z "$LINT_ONLY" ] \
   && ! "$PY" "$HERE/voices.py" --measured "$VOICE"; then
  echo "$VOICE's speaking rate hasn't been measured yet, so this draft's timing is a guess."
  echo "Render the smoke test with it first, which measures it, then rerun:"
  echo "  tools/build.sh voices/smoke-test.draft.txt \"smoke-test\" --voice \"$VOICE\""
  echo "(or set ALLOW_ESTIMATED=1 to render anyway)"
  exit 3
fi

# The smoke test exists to measure a voice, so its lint never blocks the render.
"$PY" "$HERE/tts_build.py" "$DRAFT" --voice "$VOICE" \
  --wpm "${WPM:-185}" --out "$OUT_DIR/$NAME.txt" ${SMOKE:+--force}
[ -n "$LINT_ONLY" ] && exit 0

set +e
"$PY" "$HERE/render.py" "$DRAFT" --out "$OUT_DIR/$NAME.mp3" "$@" 2>"$LOG"
STATUS=$?
# Model loading is chatty on stderr; only surface it when something went wrong.
[ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 2 ] && tail -20 "$LOG"
[ -n "$SMOKE" ] && exit "$STATUS"   # a voice check, not a workout: no copy

# A finished MP3 also goes to the profile's delivery folder: any path, such as a
# Google Drive, iCloud Drive or Dropbox folder that syncs to the phone. A leading ~
# means the home folder, and a * matches (for example, any Google account).
DELIVER="$(sed -n 's/^- Copy finished MP3s to: *//p' "$PROFILE" | head -1 | sed 's/[[:space:]]*$//')"
case "$DELIVER" in "~"*) DELIVER="$HOME${DELIVER#\~}" ;; esac
if [ "$STATUS" -eq 0 ] && [ -z "$DELIVER" ]; then
  echo "No copy made: the profile has no '- Copy finished MP3s to: <folder>' line; the MP3 is in $OUT_DIR"
fi
if [ "$STATUS" -eq 0 ] && [ -n "$DELIVER" ]; then
  FOUND=""
  OLD_IFS="$IFS"; IFS='
'
  for DEST in $DELIVER; do   # unquoted on purpose: expands the *, never splits on spaces
    [ -d "$DEST" ] || continue
    FOUND=1
    if cp "$OUT_DIR/$NAME.mp3" "$DEST/"; then
      echo "Copied to $DEST/$NAME.mp3"
    else
      echo "Couldn't copy to $DEST; the MP3 is in $OUT_DIR"
    fi
  done
  IFS="$OLD_IFS"
  [ -n "$FOUND" ] || echo "Delivery folder $DELIVER not found; the MP3 is in $OUT_DIR"
fi
exit "$STATUS"
