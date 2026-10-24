#!/bin/sh
# The readiness check: what this computer is, what's installed, and which audio routes work here.
# Runs before the Python environment exists, so it's a shell script. Run it as ./sweatcast doctor.
#
#   ./sweatcast doctor            # the report, in plain lines
#   sh tools/doctor.sh --facts    # key=value lines only (tools/doctor.py and the tests read these)
#   sh tools/doctor.sh --short    # the computer, prerequisites and local audio only (setup prints this)
#
# The floors below are cautious guesses, not measurements: under them, local voices aren't offered.
#
# Test-only: SWEATCAST_FAKE_OS (uname -s), SWEATCAST_FAKE_ARCH (uname -m), SWEATCAST_FAKE_GPU
# ("<NVIDIA name>, <GB>", empty for none), SWEATCAST_FAKE_MEM_GB and SWEATCAST_FAKE_DISK_GB stand in
# for what the computer reports, so the verdicts can be tested on any machine.
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
MEM_FLOOR=8    # GB of memory for a local voice model (a guess: the models need 3 to 5 GB)
DISK_FLOOR=6   # GB free for the local engine and one model (a guess: 2 to 4 GB of PyTorch or MLX, 3 to 4 GB of model)

decline() {   # the one place the cloud-session message lives (the ./sweatcast wrapper prints it too)
  cat <<'EOF'
This is a Claude Code cloud session, and sweatcast doesn't set up here:
  - the cloud machine has no graphics card, so making the audio would take a very long time;
  - the default network settings block downloading the voice model;
  - your profile, injuries and workout log would vanish when the session ends.
Open this folder in Claude Code on your own computer and say "set up sweatcast".
EOF
}
if [ "$1" = "decline" ]; then decline; exit 0; fi

# ---- what the computer is ----------------------------------------------------------------
UNAME_S="${SWEATCAST_FAKE_OS-$(uname -s 2>/dev/null)}"
UNAME_M="${SWEATCAST_FAKE_ARCH-$(uname -m 2>/dev/null)}"
case "$UNAME_S" in
  Darwin) OS=mac ;;
  Linux) OS=linux ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) OS=other ;;
esac
# A Mac's shell running under Rosetta reports x86_64 on Apple Silicon; the hardware says otherwise.
if [ "$OS" = mac ] && [ -z "${SWEATCAST_FAKE_ARCH+x}" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ]; then
  UNAME_M=arm64
fi
case "$UNAME_M" in
  arm64|aarch64) ARCH=arm64 ;;
  x86_64|amd64|AMD64) ARCH=x86_64 ;;
  *) ARCH=other ;;
esac

chip() {
  case "$OS" in
    mac) sysctl -n machdep.cpu.brand_string 2>/dev/null ;;
    linux) sed -n 's/^model name[[:space:]]*:[[:space:]]*//p' /proc/cpuinfo 2>/dev/null | head -1 ;;
    windows) echo "${PROCESSOR_IDENTIFIER:-}" ;;
  esac
}

mem_gb() {
  if [ -n "${SWEATCAST_FAKE_MEM_GB+x}" ]; then echo "$SWEATCAST_FAKE_MEM_GB"; return; fi
  case "$OS" in
    mac) sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d\n", $1 / 1073741824 + 0.5}' ;;
    linux) awk '/^MemTotal:/ {printf "%d\n", $2 / 1048576 + 0.5}' /proc/meminfo 2>/dev/null ;;
    windows) powershell.exe -NoProfile -Command \
      "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)" 2>/dev/null | tr -d '\r' ;;
  esac
}

disk_gb() {
  if [ -n "${SWEATCAST_FAKE_DISK_GB+x}" ]; then echo "$SWEATCAST_FAKE_DISK_GB"; return; fi
  df -Pk "$ROOT" 2>/dev/null | awk 'NR == 2 {printf "%d\n", $4 / 1048576}'
}

gpu() {   # "<name>, <GB>" for the first NVIDIA card, or nothing
  if [ -n "${SWEATCAST_FAKE_GPU+x}" ]; then echo "$SWEATCAST_FAKE_GPU"; return; fi
  command -v nvidia-smi >/dev/null 2>&1 || return 0
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d '\r' \
    | awk -F', *' 'NF >= 2 {printf "%s, %d\n", $1, $2 / 1024 + 0.5}'
}

find_uv() {
  if [ -n "${SWEATCAST_UV:-}" ]; then echo "$SWEATCAST_UV"; return; fi
  for c in "$(command -v uv 2>/dev/null)" "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "$HOME/.local/bin/uv.exe"; do
    if [ -n "$c" ] && [ -x "$c" ]; then echo "$c"; return; fi
  done
}

venv_python() {
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

CHIP="$(chip)"
MEM="$(mem_gb)"; MEM="${MEM:-0}"
DISK="$(disk_gb)"; DISK="${DISK:-0}"
GPU="$(gpu)"
GPU_NAME="${GPU%,*}"; GPU_MEM=""
[ -n "$GPU" ] && GPU_MEM="$(echo "$GPU" | sed 's/.*, *//')"
UV="$(find_uv)"
GIT="$(command -v git 2>/dev/null)"
FFMPEG="$(command -v ffmpeg 2>/dev/null)"
PY="$(venv_python)"
VENV=no; [ -n "$PY" ] && VENV=yes
INGIT="$(in_git)"
REMOTE=no; [ "${CLAUDE_CODE_REMOTE:-}" = true ] && REMOTE=yes

# ---- which local engine, if any ----------------------------------------------------------
LOCAL=no; LOCAL_ENGINE=""; LOCAL_REASON=""
if [ "$OS" = mac ] && [ "$ARCH" = arm64 ]; then
  LOCAL=fast; LOCAL_ENGINE=mlx
elif [ "$OS" = mac ]; then
  LOCAL_REASON="Neither MLX nor current PyTorch runs the voices on an Intel Mac; a cloud voice is coming in sweatcast 9."
elif [ "$OS" = windows ] && [ -n "$GPU_NAME" ]; then
  LOCAL=fast; LOCAL_ENGINE=cuda
else
  LOCAL_REASON="Local voices need an Apple Silicon Mac or a Windows PC with an NVIDIA card in this version."
fi
if [ "$LOCAL" != no ] && [ "$MEM" -lt "$MEM_FLOOR" ] 2>/dev/null; then
  LOCAL=no; LOCAL_ENGINE=""
  LOCAL_REASON="This computer has ${MEM} GB of memory; a local voice model needs about ${MEM_FLOOR} GB (a cautious guess)."
elif [ "$LOCAL" != no ] && [ "$DISK" -lt "$DISK_FLOOR" ] 2>/dev/null; then
  LOCAL=no; LOCAL_ENGINE=""
  LOCAL_REASON="Only ${DISK} GB is free here; a local voice needs about ${DISK_FLOOR} GB for its engine and model (a cautious guess)."
fi

if [ "$1" = "--facts" ]; then
  cat <<EOF
os=$OS
arch=$ARCH
chip=$CHIP
gpu=$GPU_NAME
gpu_mem_gb=$GPU_MEM
mem_gb=$MEM
disk_gb=$DISK
uv=$UV
git=$GIT
ffmpeg=$FFMPEG
venv=$VENV
in_git=$INGIT
remote=$REMOTE
local=$LOCAL
local_engine=$LOCAL_ENGINE
local_reason=$LOCAL_REASON
EOF
  exit 0
fi

# ---- the report --------------------------------------------------------------------------
case "$OS" in mac) SYSTEM="macOS" ;; linux) SYSTEM="Linux" ;; windows) SYSTEM="Windows (Git Bash)" ;; *) SYSTEM="$UNAME_S" ;; esac
case "$OS" in
  mac) UV_INSTALL="curl -LsSf https://astral.sh/uv/install.sh | sh" ;;
  windows) UV_INSTALL="powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"" ;;
  *) UV_INSTALL="curl -LsSf https://astral.sh/uv/install.sh | sh" ;;
esac

if [ "$REMOTE" = yes ] && [ -z "${SWEATCAST_ALLOW_CLOUD_SESSION:-}" ]; then decline; echo
elif [ "$REMOTE" = yes ]; then echo "(A Claude Code cloud machine, set up anyway: SWEATCAST_ALLOW_CLOUD_SESSION is set.)"; echo; fi
echo "This computer"
echo "  System:   $SYSTEM, $ARCH${CHIP:+ ($CHIP)}"
if [ "$OS" = mac ] && [ "$ARCH" = arm64 ]; then echo "  Graphics: built into the Apple Silicon chip"
else echo "  Graphics: ${GPU_NAME:-no NVIDIA card found}${GPU_MEM:+, $GPU_MEM GB}"; fi
echo "  Memory:   $MEM GB"
echo "  Free disk: $DISK GB where sweatcast is"
echo
echo "Prerequisites"
if [ -n "$UV" ]; then echo "  uv:     $UV"; else
  echo "  uv:     missing. It installs without admin rights: ./sweatcast setup --install-uv"
  echo "          (which runs Astral's official installer: $UV_INSTALL)"
fi
if [ -n "$GIT" ]; then
  [ "$INGIT" = yes ] && echo "  git:    $GIT" || echo "  git:    $GIT (this folder isn't a git checkout, so the privacy hook is skipped)"
else
  echo "  git:    missing; only the privacy hook and ./sweatcast backup need it"
fi
if [ -n "$FFMPEG" ]; then echo "  ffmpeg: $FFMPEG"; else
  echo "  ffmpeg: not installed; the Python environment brings its own"
fi
[ "$VENV" = yes ] && echo "  Python environment: ready" || echo "  Python environment: not made yet (./sweatcast setup makes it)"
echo
echo "Audio here"
case "$LOCAL" in
  fast) echo "  Local voices: yes, on $( [ "$LOCAL_ENGINE" = mlx ] && echo "Apple Silicon (MLX)" || echo "the NVIDIA card (CUDA)" )" ;;
  *) echo "  Local voices: no. $LOCAL_REASON" ;;
esac
[ "$1" = "--short" ] && exit 0   # setup prints this part; it reports the rest itself
echo
if [ "$VENV" = yes ]; then
  cd "$ROOT" && "$PY" "$ROOT/tools/doctor.py"
else
  echo "The rest is checked once ./sweatcast setup has made the environment."
fi
