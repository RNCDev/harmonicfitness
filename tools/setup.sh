#!/bin/sh
# Set up sweatcast on this computer: the Python environment, your context folder, the privacy
# hook and the voice models. Safe to rerun; it skips what's already done. Run it as ./sweatcast setup.
#
#   ./sweatcast setup               # environment, me/ from me.example/, the default voice's model
#   ./sweatcast setup --all         # every voice's model
#   ./sweatcast setup --no-models   # everything but the models (the setup skill runs this
#                                   # first, then fetches the voice the user picks)
#   ./sweatcast setup --install-uv  # first install uv with Astral's official installer (no admin
#                                   # rights needed), then set up as above
#
# It starts with the readiness check (./sweatcast doctor), which says what this computer can do.
# Needs uv (https://docs.astral.sh/uv/), which fetches the right Python itself. ffmpeg comes with
# the Python environment when it isn't installed, and git is needed only for the privacy hook and
# ./sweatcast backup, so a zip download sets up too.
#
# Voice models download once from Hugging Face (no account needed) into
# ~/.cache/huggingface/hub: about 3.3 GB for Chatterbox Coach (the model plus its speech
# tokenizer) and 4.2 GB for Qwen3 Coach on a Mac, and about 4 GB for Chatterbox Coach on
# Windows. Rendering works offline after that. Rerun after changing the default voice in
# me/profile.md to fetch its model. An existing context folder is brought up to this version's
# format (./sweatcast migrate), backed up first.
#
# Test-only: SWEATCAST_UV is the uv to run, and SWEATCAST_PYTHON the Python the tools run under.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONTEXT="${SWEATCAST_HOME:-$ROOT/me}"
cd "$ROOT"
if [ "${CLAUDE_CODE_REMOTE:-}" = true ] && [ -z "${SWEATCAST_ALLOW_CLOUD_SESSION:-}" ]; then
  sh "$HERE/doctor.sh" decline
  exit 1
fi

find_uv() {
  if [ -n "${SWEATCAST_UV:-}" ]; then echo "$SWEATCAST_UV"; return; fi
  for c in "$(command -v uv 2>/dev/null || true)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "$HOME/.local/bin/uv.exe"; do
    if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return; fi
  done
}

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) UV_INSTALL='powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' ;;
  *) UV_INSTALL='curl -LsSf https://astral.sh/uv/install.sh | sh' ;;
esac

if [ "$1" = "--install-uv" ]; then
  shift
  if [ -n "$(find_uv)" ]; then
    echo "uv is already installed: $(find_uv)"
  else
    echo "Installing uv with Astral's official installer: $UV_INSTALL"
    sh -c "$UV_INSTALL"
  fi
fi

echo "0. This computer (./sweatcast doctor)"
sh "$HERE/doctor.sh" --short | sed 's/^/   /'

UV="$(find_uv)"
if [ -z "$UV" ]; then
  echo
  echo "uv is missing. It's the tool that makes sweatcast's Python environment, and it installs"
  echo "without admin rights: ./sweatcast setup --install-uv (Claude Code can run it for you), which runs"
  echo "Astral's official installer: $UV_INSTALL"
  exit 1
fi

echo "1. Python environment (.venv, pinned by uv.lock)"
"$UV" sync --frozen   # also rebuilds a .venv copied from another computer, whose Python is gone
PY="${SWEATCAST_PYTHON:-.venv/bin/python}"
[ -x "$PY" ] || PY=".venv/Scripts/python.exe"   # Windows
"$PY" tools/ffmpeg.py | sed 's/^/   /' || true

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
if ! command -v git >/dev/null 2>&1; then
  echo "   skipped: git isn't installed. Only this hook and ./sweatcast backup need it."
elif [ "$(git rev-parse --show-prefix 2>/dev/null || echo none)" != "" ]; then
  echo "   skipped: this folder isn't a git checkout (a zip download?), so there's nothing to push from it."
  echo "   ./sweatcast backup needs git too."
else
  git config core.hooksPath tools/hooks
fi

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
