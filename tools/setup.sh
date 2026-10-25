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
# Local voice models download once from Hugging Face (no account needed) into models/ (or
# SWEATCAST_MODELS; ./sweatcast models adopt moves ones already in ~/.cache/huggingface/hub): about 3.3 GB for
# Chatterbox Turbo (the model plus its speech tokenizer) and 4.2 GB for Qwen3-TTS on a Mac, and
# about 4 GB for Chatterbox Turbo on Windows or Linux. Rendering works offline after that. Rerun
# after giving a coach another local engine to fetch its model. An existing context folder is brought up to this version's
# format (./sweatcast migrate), backed up first.
#
# On Claude Code on the web (CLAUDE_CODE_REMOTE=true) there's no local engine: cloud voices only.
#
# Test-only: SWEATCAST_UV is the uv to run, and SWEATCAST_PYTHON the Python the tools run under.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
CONTEXT="${SWEATCAST_HOME:-$ROOT/me}"
cd "$ROOT"
. "$HERE/common.sh"
UV_INSTALL="$(uv_install_for "$(detect_os)")"

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
    if [ "$LOCAL" = no ] && [ -z "$INSTALLED" ]; then
      echo "Local voices don't run on this computer: $LOCAL_REASON"
      exit 1
    fi
    WANT="${INSTALLED:-$LOCAL_ENGINE}"; [ "$LOCAL" = no ] || WANT="$LOCAL_ENGINE" ;;
  *) [ "$LOCAL" = no ] && WANT="$INSTALLED" || WANT="$LOCAL_ENGINE" ;;   # a floor never uninstalls an engine
esac
# A profile whose render list leaves out "local" (cloud voices only) gets no local engine from a plain
# run; one already installed stays. The tools read the list where an environment exists to run them; on a
# computer with none yet (a me/ restored from backup) the list is read from settings.toml itself.
PY_NOW="$(venv_python)"
if [ -n "$PY_NOW" ]; then RENDER_LIST="$("$PY_NOW" tools/context.py get routes 2>/dev/null | tr '\n' ' ' || true)"
else RENDER_LIST="$(render_routes_from_file "$CONTEXT/settings.toml" | tr '\n' ' ')"; fi
if [ -z "$1" ] && [ -n "$RENDER_LIST" ] && ! echo " $RENDER_LIST " | grep -q ' local '; then
  echo "   The render list (settings.toml) has no \"local\", so the local engine isn't installed (./sweatcast setup --local adds it)."
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
PY="$(venv_python)"
"$PY" tools/ffmpeg.py | sed 's/^/   /' || true
# The context folder as every tool finds it (tools/paths.py): SWEATCAST_HOME, else me/, else (on Claude
# Code on the web) the private repo attached beside the engine.
CONTEXT="$("$PY" -c "import sys; sys.path.insert(0, 'tools'); import paths; print(paths.HOME)" 2>/dev/null || echo "$CONTEXT")"

echo "2. Your context folder ($CONTEXT)"
if [ -e "$CONTEXT/profile.md" ]; then
  echo "   already there; brought up to this version's format if it was older (backed up first):"
  MIGRATE_OUT="$("$PY" tools/migrate.py 2>&1)" && MIGRATED=0 || MIGRATED=$?
  echo "$MIGRATE_OUT" | sed 's/^/   /'
  if [ "$MIGRATED" -ne 0 ] && ! echo "$MIGRATE_OUT" | grep -q "Backed up the originals\|already at schema"; then
    echo "   The context folder wasn't brought up to date, so setup stopped here: fix what it says above, then rerun."
    exit 1
  fi
  if [ ! -e "$CONTEXT/.gitignore" ]; then
    cp "$ROOT/me.example/.gitignore" "$CONTEXT/.gitignore"
    echo "   added .gitignore, for keeping it as its own private repo (./sweatcast backup)"
  fi
  if ! grep -qxF '.env' "$CONTEXT/.gitignore"; then
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
elif [ "$(in_git)" != yes ]; then
  echo "   skipped: this folder isn't a git checkout (a zip download?), so there's nothing to push from it."
  echo "   ./sweatcast backup needs git too."
else
  HOOKS_NOW="$(git config --get core.hooksPath 2>/dev/null || true)"
  if [ -n "$HOOKS_NOW" ] && [ "$HOOKS_NOW" != tools/hooks ]; then
    echo "   skipped: git already takes its hooks from $HOOKS_NOW; add tools/hooks/pre-push to yours to keep me/ out."
  elif ! git config core.hooksPath tools/hooks 2>/dev/null; then
    echo "   skipped: git's settings can't be changed from here (a sandbox, such as ChatGPT's Codex, protects them)."
    echo "   Rerun ./sweatcast setup outside it to add the hook."
  fi
fi

echo "4. Voice models (once, from Hugging Face into models/; no account needed, and its"
echo "   'unauthenticated requests' warning is harmless)"
if [ "$1" != "--no-models" ] && [ -n "$WANT" ]; then
  "$PY" tools/models.py adopt --dry-run --quiet | sed 's/^/   /' || true
fi
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
echo "  - In Claude Code, say \"set up sweatcast\": four questions, then a ten-minute workout with Coach Andy,"
echo "    a stand-in coach that's ready now (./sweatcast check lists anything still to fill in)."
echo "  - Later: \"finish setting me up\" for your interests and feeds, and \"I want a new coach\" for your own."
