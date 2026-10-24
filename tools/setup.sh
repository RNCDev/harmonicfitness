#!/bin/sh
# Set up sweatcast on this Mac or Windows PC: the Python environment, your context folder, and the
# voice models. Safe to rerun; it skips what's already done. Run it as ./sweatcast setup.
#
#   ./sweatcast setup               # environment, me/ from me.example/, the default voice's model
#   ./sweatcast setup --all         # every voice's model
#   ./sweatcast setup --no-models   # everything but the models (the setup skill runs this
#                                   # first, then fetches the voice the user picks)
#
# Voice models download once from Hugging Face (no account needed) into
# ~/.cache/huggingface/hub: about 3.3 GB for Chatterbox Coach (the model plus its
# speech tokenizer) and 4.2 GB for Qwen3 Coach on a Mac, and about 4 GB for Chatterbox
# Coach on Windows. Rendering works offline after that.
# Rerun after changing the default voice in me/profile.md to fetch its model.
# Existing context folders are brought up to this version's format (./sweatcast migrate).
#
# Needs an Apple Silicon Mac with Homebrew's ffmpeg, or a Windows PC with an NVIDIA GPU
# (RTX 20 series or later), Git Bash and ffmpeg; and uv (https://docs.astral.sh/uv/) on
# either. uv fetches the right Python itself, so the system Python doesn't matter.
# On Windows only the Chatterbox voices render so far; the lint and research tools all work.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONTEXT="${SWEATCAST_HOME:-$ROOT/me}"
cd "$ROOT"
if [ "${CLAUDE_CODE_REMOTE:-}" = true ] && [ -z "${SWEATCAST_ALLOW_CLOUD_SESSION:-}" ]; then
  sh "$HERE/doctor.sh" decline
  exit 1
fi

case "$(uname -s)" in
  Darwin)
    [ "$(uname -m)" = "arm64" ] \
      || echo "Warning: the voices run on MLX, which needs an Apple Silicon Mac. Lint and research tools still work."
    FFMPEG_HINT="brew install ffmpeg"; UV_HINT="brew install uv" ;;
  MINGW*|MSYS*|CYGWIN*)
    command -v nvidia-smi >/dev/null \
      || echo "Warning: no NVIDIA GPU found (nvidia-smi); the voices run on CUDA here. Lint and research tools still work."
    FFMPEG_HINT="winget install Gyan.FFmpeg.Essentials"; UV_HINT="winget install astral-sh.uv" ;;
  *)
    echo "Warning: the voices render on an Apple Silicon Mac or a Windows PC with an NVIDIA GPU. Lint and research tools still work."
    FFMPEG_HINT="install ffmpeg"; UV_HINT="see https://docs.astral.sh/uv/" ;;
esac
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing: $FFMPEG_HINT"; exit 1; }
UV="$(command -v uv || true)"
[ -n "$UV" ] || [ ! -x "$HOME/.local/bin/uv" ] || UV="$HOME/.local/bin/uv"
[ -n "$UV" ] || { echo "uv is missing: $UV_HINT (or see https://docs.astral.sh/uv/)"; exit 1; }

echo "1. Python environment (.venv, pinned by uv.lock)"
"$UV" sync --frozen
PY=".venv/bin/python"
[ -x "$PY" ] || PY=".venv/Scripts/python.exe"   # Windows

echo "2. Your context folder ($CONTEXT)"
if [ -e "$CONTEXT/profile.md" ]; then
  echo "   already there; brought up to this version's format if it was older (backed up first):"
  "$PY" tools/migrate.py | sed 's/^/   /' || true
  if [ ! -e "$CONTEXT/.gitignore" ]; then
    cp "$ROOT/me.example/.gitignore" "$CONTEXT/.gitignore"
    echo "   added .gitignore, for keeping it as its own private repo (./sweatcast backup)"
  fi
else
  mkdir -p "$CONTEXT"
  cp -R "$ROOT/me.example/." "$CONTEXT/"
  find "$CONTEXT" -name .gitkeep -delete
  echo "   copied from me.example/. Fill it in by asking Claude Code to \"set me up\"."
fi

echo "3. Privacy guard (a git pre-push hook that refuses to push me/ in any commit)"
git config core.hooksPath tools/hooks

echo "4. Voice models (once, from Hugging Face into ~/.cache/huggingface/hub; no account needed,"
echo "   and its 'unauthenticated requests' warning is harmless)"
if [ "$1" = "--no-models" ]; then
  echo "   skipped (--no-models)"
elif [ "$1" = "--all" ]; then
  "$PY" tools/voices.py download
else
  DEFAULT_VOICE="$("$PY" tools/context.py get default-voice 2>/dev/null || true)"
  "$PY" tools/voices.py download "${DEFAULT_VOICE:-Chatterbox Coach}"
fi

echo
echo "Done. Next:"
echo "  - In Claude Code, ask to \"set me up\" if you haven't filled in $CONTEXT yet"
echo "    (./sweatcast check lists anything still to fill in)."
echo "  - Render the smoke test with your voice, which also measures its pace:"
echo "      ./sweatcast build voices/smoke-test.draft.txt \"smoke-test\""
echo "  - Then ask for a workout."
