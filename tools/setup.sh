#!/bin/sh
# Set up sweatcast on this Mac: the Python environment, your context folder, and the
# voice models. Safe to rerun; it skips what's already done.
#
#   tools/setup.sh            # environment, me/ from me.example/, the default voice's model
#   tools/setup.sh --all      # every voice's model
#   tools/setup.sh --no-models   # everything but the models (the setup skill runs this
#                                # first, then fetches the voice the user picks)
#
# Voice models download once from Hugging Face (no account needed) into
# ~/.cache/huggingface/hub: about 3.3 GB for Chatterbox Coach (the model plus its
# speech tokenizer) and 4.2 GB for Qwen3 Coach. Rendering works offline after that.
# Rerun after changing the default voice in me/profile.md to fetch its model.
#
# Needs an Apple Silicon Mac, Homebrew's ffmpeg and uv (https://docs.astral.sh/uv/).
# uv fetches the right Python itself, so the system Python doesn't matter.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONTEXT="${SWEATCAST_HOME:-$ROOT/me}"
cd "$ROOT"

[ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ] \
  || echo "Warning: the voices run on MLX, which needs an Apple Silicon Mac. Lint and research tools still work."
command -v ffmpeg >/dev/null || { echo "ffmpeg is missing: brew install ffmpeg"; exit 1; }
UV="$(command -v uv || true)"
[ -n "$UV" ] || [ ! -x "$HOME/.local/bin/uv" ] || UV="$HOME/.local/bin/uv"
[ -n "$UV" ] || { echo "uv is missing: brew install uv (or see https://docs.astral.sh/uv/)"; exit 1; }

echo "1. Python environment (.venv, pinned by uv.lock)"
"$UV" sync --frozen

echo "2. Your context folder ($CONTEXT)"
if [ -e "$CONTEXT/profile.md" ]; then
  echo "   already there; left as is"
else
  mkdir -p "$CONTEXT"
  cp -R "$ROOT/me.example/." "$CONTEXT/"
  find "$CONTEXT" -name .gitkeep -delete
  echo "   copied from me.example/. Fill it in by asking Claude Code to \"set me up\"."
fi

echo "3. Privacy guard (a git pre-push hook that refuses to push me/)"
git config core.hooksPath tools/hooks

echo "4. Voice models (once, from Hugging Face into ~/.cache/huggingface/hub; no account needed,"
echo "   and its 'unauthenticated requests' warning is harmless)"
if [ "$1" = "--no-models" ]; then
  echo "   skipped (--no-models)"
elif [ "$1" = "--all" ]; then
  .venv/bin/python tools/voices.py --download
else
  DEFAULT_VOICE="$(awk '/^- Voices/ {v=1; next} v && /^  - / {sub(/^  - /, ""); sub(/:.*/, ""); print; exit} v && !/^  / {exit}' "$CONTEXT/profile.md")"
  .venv/bin/python tools/voices.py --download "${DEFAULT_VOICE:-Chatterbox Coach}"
fi

echo
echo "Done. Next:"
echo "  - In Claude Code, ask to \"set me up\" if you haven't filled in $CONTEXT yet."
echo "  - Render the smoke test with your voice, which also measures its pace:"
echo "      tools/build.sh voices/smoke-test.draft.txt \"smoke-test\""
echo "  - Then ask for a workout."
