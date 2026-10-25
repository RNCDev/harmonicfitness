#!/bin/sh
# Shared by ./sweatcast, tools/setup.sh and tools/doctor.sh (sourced, never run): where uv and the
# environment's Python are, how uv installs on this system, and whether this folder is a git checkout.
# Expects ROOT, the repo root. Test-only: SWEATCAST_UV is the uv to run, SWEATCAST_PYTHON the Python.

find_uv() {
  if [ -n "${SWEATCAST_UV:-}" ]; then echo "$SWEATCAST_UV"; return; fi
  for c in "$(command -v uv 2>/dev/null || true)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "$HOME/.local/bin/uv.exe"; do
    if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return; fi
  done
}

venv_python() {   # the environment's Python (.venv), or SWEATCAST_PYTHON; nothing when there's no environment yet
  if [ -n "${SWEATCAST_PYTHON:-}" ]; then echo "$SWEATCAST_PYTHON"; return; fi
  for c in "$ROOT/.venv/bin/python" "$ROOT/.venv/Scripts/python.exe"; do
    if [ -x "$c" ]; then echo "$c"; return; fi
  done
}

in_git() {   # yes when this folder is the top of a git checkout (not a zip, not a copy inside another repo)
  command -v git >/dev/null 2>&1 || { echo no; return; }
  prefix="$(git -C "$ROOT" rev-parse --show-prefix 2>/dev/null)" || { echo no; return; }
  [ -z "$prefix" ] && echo yes || echo no
}

detect_os() {   # mac, linux, windows or other (SWEATCAST_FAKE_OS stands in for uname in the tests)
  case "${SWEATCAST_FAKE_OS-$(uname -s 2>/dev/null)}" in
    Darwin) echo mac ;;
    Linux) echo linux ;;
    MINGW*|MSYS*|CYGWIN*) echo windows ;;
    *) echo other ;;
  esac
}

uv_install_for() {   # Astral's official installer for $1 (an OS from detect_os); no admin rights needed
  case "$1" in
    windows) echo 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"' ;;
    *) echo 'curl -LsSf https://astral.sh/uv/install.sh | sh' ;;
  esac
}

render_routes_from_file() {   # the profile's render list read from settings.toml itself ($1), one route per line, for
  # a computer with no environment yet (a me/ restored from backup); with one, ./sweatcast get routes is the reader
  [ -f "$1" ] || return 0
  sed -n 's/^render[[:space:]]*=[[:space:]]*\[\([^]]*\)\].*$/\1/p' "$1" | head -1 | tr ',' '\n' | tr -d '" \t' | sed '/^$/d'
}
