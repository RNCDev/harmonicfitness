#!/bin/sh
# Set up sweatcast on this computer: the Python environment, your context folder, the privacy
# hook and the voice models. Safe to rerun; it skips what's already done. Run it as ./sweatcast setup.
#
#   ./sweatcast setup               # environment, me/ from me.example/, and where local voices run
#                                   # here, their engine and the default voice's model
#   ./sweatcast setup --local       # the same, but stop with the reason if local voices can't run here
#   ./sweatcast setup --all         # every voice's model
#   ./sweatcast setup --no-models   # the base environment (keeping a local engine already
#                                   # installed), me/ and the hook; no models (the setup skill
#                                   # runs this first, then fetches what the listener picks)
#   ./sweatcast setup --install-uv  # first install uv with Astral's official installer (no admin
#                                   # rights needed), then set up as above
#
# It starts with the readiness check (./sweatcast doctor), which says what this computer can do.
# Needs uv (https://docs.astral.sh/uv/), which fetches the right Python itself. ffmpeg comes with
# the Python environment when it isn't installed, and git is needed only for the privacy hook and
# ./sweatcast backup, so a zip download sets up too.
#
# Local voice models download once from Hugging Face (no account needed): about 3.3 GB for
# Chatterbox Turbo (the model plus its speech tokenizer) and 4.2 GB for Qwen3-TTS on a Mac, and
# about 4 GB for Chatterbox Turbo on Windows or Linux. Rendering works offline after that. Rerun
# after giving a coach another local engine to fetch its model. An existing context folder is brought up to this version's
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

# The local voice engine is an extra, installed where the readiness check says it runs: MLX on
# Apple Silicon, CUDA PyTorch with an NVIDIA card, processor PyTorch without one. It's remembered
# in .venv/.sweatcast-extra, since a sync without it would uninstall it.
FACTS="$(sh "$HERE/doctor.sh" --facts)"
fact() { echo "$FACTS" | sed -n "s/^$1=//p"; }
LOCAL="$(fact local)"; LOCAL_ENGINE="$(fact local_engine)"; LOCAL_REASON="$(fact local_reason)"
MARKER=".venv/.sweatcast-extra"
INSTALLED="$(cat "$MARKER" 2>/dev/null || true)"
if [ -z "$INSTALLED" ] && [ -d .venv ]; then   # an environment from before 9.0, which had no marker
  if [ -n "$(find .venv -maxdepth 6 -type d -name mlx_audio 2>/dev/null | head -1)" ]; then INSTALLED=mlx
  elif [ -n "$(find .venv -maxdepth 6 -type d -name chatterbox 2>/dev/null | head -1)" ]; then
    INSTALLED="$LOCAL_ENGINE"; [ -n "$INSTALLED" ] || INSTALLED=cuda
  fi
fi
case "$1" in
  --no-models) WANT="$INSTALLED" ;;   # the base, keeping a local engine already installed
  --local)
    if [ "$LOCAL" = no ]; then
      echo "Local voices don't run on this computer: $LOCAL_REASON"
      exit 1
    fi
    WANT="$LOCAL_ENGINE" ;;
  *) [ "$LOCAL" = no ] && WANT="" || WANT="$LOCAL_ENGINE" ;;
esac
# A profile whose render list leaves out "local" (cloud voices only) gets no local engine from a plain
# rerun; one already installed stays.
RENDER_LINE="$(sed -n '/^+++/,/^+++/s/^render[[:space:]]*=//p' "$CONTEXT/profile.md" 2>/dev/null | head -1)"
if [ -z "$1" ] && [ -n "$RENDER_LINE" ] && ! echo "$RENDER_LINE" | grep -q '"local"'; then
  echo "   The profile's render list has no \"local\", so the local engine isn't installed (./sweatcast setup --local adds it)."
  WANT="$INSTALLED"
fi

echo "1. Python environment (.venv, pinned by uv.lock)${WANT:+, with the local voices ($WANT)}"
"$UV" sync --frozen ${WANT:+--extra "$WANT"}   # also rebuilds a .venv copied from another computer
if [ -n "$WANT" ]; then
  mkdir -p .venv && echo "$WANT" > "$MARKER"
fi
if [ "$LOCAL" = no ] && [ "$1" != "--no-models" ]; then
  echo "   No local voices on this computer: $LOCAL_REASON"
elif [ "$LOCAL" = experimental ] && [ -n "$WANT" ]; then
  echo "   Local voices run on the processor here: experimental, speed unknown, likely slow."
  echo "   The smoke test measures this computer's speed."
fi
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
  if ! grep -qx '.env' "$CONTEXT/.gitignore"; then
    printf '%s\n' "# API keys for cloud voices (./sweatcast keys): never committed, never pushed." ".env" >> "$CONTEXT/.gitignore"
    echo "   .gitignore now leaves out .env, where cloud voice keys go"
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
elif [ -z "$WANT" ]; then
  echo "   skipped: no local voices on this computer"
elif [ "$1" = "--all" ]; then
  "$PY" tools/coaches.py download --all
else
  "$PY" tools/coaches.py download   # the coaches' local model, or Chatterbox Turbo before there's a coach
fi

echo
echo "Done. Next:"
echo "  - In Claude Code, say \"set up sweatcast\" if you haven't filled in $CONTEXT yet; it also makes your"
echo "    coach (./sweatcast check lists anything still to fill in)."
echo "  - Render the smoke test with your coach, which also measures their pace:"
echo "      ./sweatcast build knowledge/smoke-test.draft.txt \"smoke-test\""
echo "  - Then ask for a workout."
