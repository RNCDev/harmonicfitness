#!/bin/sh
# One step from draft to deliverables: lint + export the .txt, then render the .mp3.
# Run it as ./sweatcast build (which runs this script).
#
#   ./sweatcast build <draft> "<name>" [--voice <name>] [--lint-only] [render options...]
#   ./sweatcast build me/workouts/drafts/x.draft.txt "Workout 2026-10-19 Bench 25 min" --voice "Chatterbox Coach"
#
# Writes me/workouts/<name>.txt and me/workouts/<name>.mp3 (the context folder is
# SWEATCAST_HOME if set). Stops after the lint if it finds issues (fix and rerun).
# --lint-only skips rendering. Without --voice, uses the first voice in the
# profile's settings. After a render, copies the MP3 to the deliver_to folder
# the settings name, if any. The profile is read through
# tools/context.py, which also checks the context folder's format.
#
# --clips-only renders and caches the clips of whatever the draft holds so far, with
# no lint, MP3 or copy: start it in the background on the first half of a draft,
# and the full build later renders only what's new or edited. A build started while
# it's still running waits for it.
#
# --tolerance <fraction> sets how far the total may run off plan, for the lint and
# the render alike (default three percent).
#
# Exit codes (tools/cli.py): 0 done, 1 issues to fix, 2 the rendered total ran more
# than the tolerance off plan (the MP3 is written but not copied), 3 the voice's pace
# hasn't been measured yet (render the smoke test with it first, which measures it,
# or pass --allow-estimated), 64 the command was wrong (a mistyped option, an unknown
# voice): fix the command, not the draft. The render's stderr (model loading, errors)
# goes to me/workouts/.logs/<name>.log, and its last lines print on a failure.
set -e
[ $# -ge 2 ] || { echo "usage: ./sweatcast build <draft> \"<name>\" [--voice <name>] [--lint-only] [render options]" >&2; exit 64; }
DRAFT="$1"; NAME="$2"; shift 2
# The build's own flags; everything else goes to the render.
LINT_ONLY=""; ALLOW_ESTIMATED=""
for ARG do
  shift
  case "$ARG" in
    --lint-only) LINT_ONLY=1 ;;
    --allow-estimated) ALLOW_ESTIMATED=1 ;;
    *) set -- "$@" "$ARG" ;;
  esac
done
case "$NAME" in */*) echo "The name can't contain a slash: $NAME" >&2; exit 64 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONTEXT="${SWEATCAST_HOME:-$ROOT/me}"
PROFILE="$CONTEXT/profile.md"
OUT_DIR="$CONTEXT/workouts"
VENV_PY="$ROOT/.venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="$ROOT/.venv/Scripts/python.exe"   # Windows (Git Bash)
PY="${SWEATCAST_PYTHON:-$VENV_PY}"

[ -f "$PROFILE" ] || { echo "No profile at $PROFILE. Run ./sweatcast setup first (it copies me.example/ to me/)."; exit 1; }
[ -x "$PY" ] || { echo "No Python environment at $PY. Run ./sweatcast setup first (it makes .venv with uv)."; exit 1; }
[ -f "$DRAFT" ] || { echo "No draft at $DRAFT" >&2; exit 64; }

# The default voice lives in the profile; context.py stops here, with the fix, if the
# context folder needs migrating.
DEFAULT_VOICE="$("$PY" "$HERE/context.py" get default-voice)"

# The lint predicts spoken length, so it needs the same voice and tolerance as the render.
VOICE=""; PREV=""; CLIPS_ONLY=""; TOLERANCE=""
for ARG in "$@"; do
  [ "$PREV" = "--voice" ] && VOICE="$ARG"
  [ "$PREV" = "--tolerance" ] && TOLERANCE="$ARG"
  [ "$ARG" = "--clips-only" ] && CLIPS_ONLY=1
  PREV="$ARG"
done
SMOKE=""; [ "$(basename "$DRAFT")" = "smoke-test.draft.txt" ] && SMOKE=1
if [ -z "$VOICE" ]; then
  [ -n "$DEFAULT_VOICE" ] || { echo "No --voice given, and no default voice found in $PROFILE."
    echo "Expected at least one [[voices]] entry in the settings at the top of the profile; the first is the default."; exit 1; }
  VOICE="$DEFAULT_VOICE"; set -- "$@" --voice "$VOICE"
fi
mkdir -p "$OUT_DIR/.logs"
LOG="$OUT_DIR/.logs/$NAME.log"

show_log() { echo "--- last lines of $LOG:" >&2; tail -20 "$LOG" >&2; }

if [ -n "$CLIPS_ONLY" ]; then
  # Rendering ahead while the rest of the draft is written: no lint, no MP3.
  set +e
  "$PY" "$HERE/render.py" "$DRAFT" "$@" 2>"$LOG"
  STATUS=$?
  [ "$STATUS" -ne 0 ] && show_log
  exit "$STATUS"
fi

if [ -z "$SMOKE" ] && [ -z "$LINT_ONLY" ]; then
  set +e
  "$PY" "$HERE/voices.py" measured "$VOICE"
  MEASURED=$?
  set -e
  if [ "$MEASURED" -eq 64 ]; then
    echo "Voices in your profile: $("$PY" "$HERE/context.py" get voices | tr '\n' ',' | sed 's/,$//; s/,/, /g') (all voices: ./sweatcast voices)."
    exit 64
  fi
  if [ "$MEASURED" -ne 0 ] && [ -z "$ALLOW_ESTIMATED" ]; then
    echo "$VOICE's speaking rate hasn't been measured yet, so this draft's timing is a guess."
    echo "Render the smoke test with it first, which measures it, then rerun:"
    echo "  ./sweatcast build voices/smoke-test.draft.txt \"smoke-test\" --voice \"$VOICE\""
    echo "(or pass --allow-estimated to render anyway)"
    exit 3
  fi
fi

# The smoke test exists to measure a voice, so its lint never blocks the render. Every other
# draft needs the menu ./sweatcast brief --save wrote beside it: the lint checks each movement
# the draft declares or names against today's limits, and stops the build without one.
REQUIRE_MENU="--require-menu"; [ -n "$SMOKE" ] && REQUIRE_MENU=""
"$PY" "$HERE/tts_build.py" "$DRAFT" --voice "$VOICE" \
  ${TOLERANCE:+--total-tolerance "$TOLERANCE"} --out "$OUT_DIR/$NAME.txt" ${SMOKE:+--force} $REQUIRE_MENU
[ -n "$LINT_ONLY" ] && exit 0

set +e
"$PY" "$HERE/render.py" "$DRAFT" --out "$OUT_DIR/$NAME.mp3" "$@" 2>"$LOG"
STATUS=$?
# Model loading is chatty on stderr, so it goes to the log; show it on any failure but drift.
[ "$STATUS" -ne 0 ] && [ "$STATUS" -ne 2 ] && show_log
[ -n "$SMOKE" ] && exit "$STATUS"   # a voice check, not a workout: no copy
[ "$STATUS" -eq 0 ] || exit "$STATUS"

# A finished MP3 goes to the profile's delivery folders: any path, such as a Google
# Drive, iCloud Drive or Dropbox folder that syncs to the phone. context.py expands a
# leading ~ and any *, prints the folders that exist, and says why when none do. Once
# every copy is in place and matches, the local MP3 is removed: the delivery folder
# holds the finished audio, and me/workouts/ keeps the .txt and .build.json as history.
FOUND=""; FAILED=""
DIRS="$("$PY" "$HERE/context.py" deliver)"
OLD_IFS="$IFS"; IFS='
'
for DEST in $DIRS; do
  FOUND=1
  if cp "$OUT_DIR/$NAME.mp3" "$DEST/" && cmp -s "$OUT_DIR/$NAME.mp3" "$DEST/$NAME.mp3"; then
    echo "Copied to $DEST/$NAME.mp3"
  else
    FAILED=1
    echo "Couldn't copy to $DEST; the MP3 is in $OUT_DIR"
  fi
done
IFS="$OLD_IFS"
if [ -n "$FOUND" ] && [ -z "$FAILED" ]; then
  rm -f "$OUT_DIR/$NAME.mp3"
  echo "Removed the local copy; the text and build record stay in $OUT_DIR"
elif [ -z "$FOUND" ]; then
  echo "The MP3 is in $OUT_DIR"
fi
exit 0
