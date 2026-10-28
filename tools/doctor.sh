#!/bin/sh
# The readiness check: what this computer is, what's installed, and which audio routes work here.
# Runs before the Python environment exists, so it's a shell script. Run it as ./harmonicfitness doctor.
#
#   ./harmonicfitness doctor            # the report, in plain lines
#   sh tools/doctor.sh --facts    # key=value lines only (tools/doctor.py and the tests read these)
#   sh tools/doctor.sh --short    # the computer, prerequisites and local audio only (setup prints this)
#
# The floors below are cautious guesses, not measurements: under them, local voices aren't offered.
#
# Test-only: HARMONICFITNESS_FAKE_OS (uname -s), HARMONICFITNESS_FAKE_ARCH (uname -m), HARMONICFITNESS_FAKE_GPU
# ("<NVIDIA name>, <GB>", empty for none), HARMONICFITNESS_FAKE_MEM_GB and HARMONICFITNESS_FAKE_DISK_GB stand in
# for what the computer reports, so the verdicts can be tested on any machine.
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
. "$HERE/common.sh"
MEM_FLOOR=8    # GB of memory for a local voice model (a guess: the models need 3 to 5 GB)
DISK_FLOOR=6   # GB free for the local engine, its model and the take checker (about 1 to 3 GB of PyTorch, 0.6 GB of model, 2.5 GB of checker)

# ---- what the computer is ----------------------------------------------------------------
UNAME_S="${HARMONICFITNESS_FAKE_OS-$(uname -s 2>/dev/null)}"
UNAME_M="${HARMONICFITNESS_FAKE_ARCH-$(uname -m 2>/dev/null)}"
case "$UNAME_S" in
  Darwin) OS=mac ;;
  Linux) OS=linux ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) OS=other ;;
esac
# A Mac's shell running under Rosetta reports x86_64 on Apple Silicon; the hardware says otherwise.
if [ "$OS" = mac ] && [ -z "${HARMONICFITNESS_FAKE_ARCH+x}" ] && [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ]; then
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
  if [ -n "${HARMONICFITNESS_FAKE_MEM_GB+x}" ]; then echo "$HARMONICFITNESS_FAKE_MEM_GB"; return; fi
  case "$OS" in
    mac) sysctl -n hw.memsize 2>/dev/null | awk '{printf "%d\n", $1 / 1073741824 + 0.5}' ;;
    linux) awk '/^MemTotal:/ {printf "%d\n", $2 / 1048576 + 0.5}' /proc/meminfo 2>/dev/null ;;
    windows) powershell.exe -NoProfile -Command \
      "[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)" 2>/dev/null | tr -d '\r' ;;
  esac
}

disk_gb() {
  if [ -n "${HARMONICFITNESS_FAKE_DISK_GB+x}" ]; then echo "$HARMONICFITNESS_FAKE_DISK_GB"; return; fi
  df -Pk "$ROOT" 2>/dev/null | awk 'NR == 2 {printf "%d\n", $4 / 1048576}'
}

gpu() {   # "<name>, <GB>" for the first NVIDIA card, or nothing
  if [ -n "${HARMONICFITNESS_FAKE_GPU+x}" ]; then echo "$HARMONICFITNESS_FAKE_GPU"; return; fi
  command -v nvidia-smi >/dev/null 2>&1 || return 0
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d '\r' \
    | awk -F', *' 'NF >= 2 {printf "%s, %d\n", $1, $2 / 1024 + 0.5}'
}

CHIP="$(chip)"
MEM="$(mem_gb)"     # empty when the computer won't say: unknown, which no floor counts against
DISK="$(disk_gb)"
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
# Pocket TTS on PyTorch: the processor on an Apple Silicon Mac or a PC (about a sixth and under half of real
# time, measured 2026-10-26), or an NVIDIA card.
if [ "$OS" = mac ] && [ "$ARCH" = arm64 ]; then
  LOCAL=fast; LOCAL_ENGINE=cpu
elif [ "$OS" = mac ]; then
  LOCAL_REASON="PyTorch has no build for an Intel Mac any more, so the local voice can't run here; a cloud voice works here."
elif { [ "$OS" = windows ] || [ "$OS" = linux ]; } && [ -n "$GPU_NAME" ]; then
  LOCAL=fast; LOCAL_ENGINE=cuda
elif { [ "$OS" = linux ] && [ "$ARCH" != other ]; } || { [ "$OS" = windows ] && [ "$ARCH" = x86_64 ]; }; then
  LOCAL=fast; LOCAL_ENGINE=cpu
else
  LOCAL_REASON="PyTorch has no build for this system or processor ($UNAME_S, $UNAME_M); a cloud voice works here."
fi
# Claude Code on the web: a cloud machine with no graphics card, whose files last only as long as the
# session (what's in git aside). Cloud voices only; doctor.py says what to set up there.
if [ "$REMOTE" = yes ]; then
  LOCAL=no; LOCAL_ENGINE=""
  LOCAL_REASON="This is Claude Code on the web, with no graphics card for a local voice; a cloud voice works here."
fi
# What the hardware runs, before the floors: the floors decide whether to offer a first install, and never
# switch off an engine that's already installed (tools/routes.py and setup read local_hw for that).
LOCAL_HW="$LOCAL"; LOCAL_ENGINE_HW="$LOCAL_ENGINE"   # no on the web: nothing local is ever installed there
if [ "$LOCAL" != no ] && [ -n "$MEM" ] && [ "$MEM" -gt 0 ] 2>/dev/null && [ "$MEM" -lt "$MEM_FLOOR" ]; then
  LOCAL=no; LOCAL_ENGINE=""
  LOCAL_REASON="This computer has ${MEM} GB of memory; a local voice model needs about ${MEM_FLOOR} GB (a cautious guess)."
elif [ "$LOCAL" != no ] && [ -n "$DISK" ] && [ "$DISK" -lt "$DISK_FLOOR" ] 2>/dev/null; then
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
local_hw=$LOCAL_HW
local_engine_hw=$LOCAL_ENGINE_HW
EOF
  exit 0
fi

# ---- the report --------------------------------------------------------------------------
case "$OS" in mac) SYSTEM="macOS" ;; linux) SYSTEM="Linux" ;; windows) SYSTEM="Windows (Git Bash)" ;; *) SYSTEM="$UNAME_S" ;; esac
UV_INSTALL="$(uv_install_for "$OS")"

if [ "$REMOTE" = yes ]; then
  echo "This is Claude Code on the web: HarmonicFitness runs here with a cloud voice (your own key), not a local one."
  echo
fi
echo "This computer"
echo "  System:   $SYSTEM, $ARCH${CHIP:+ ($CHIP)}"
if [ "$OS" = mac ] && [ "$ARCH" = arm64 ]; then echo "  Graphics: built into the Apple Silicon chip"
else echo "  Graphics: ${GPU_NAME:-no NVIDIA card found}${GPU_MEM:+, $GPU_MEM GB}"; fi
echo "  Memory:   ${MEM:-unknown} GB"
echo "  Free disk: ${DISK:-unknown} GB where HarmonicFitness is"
case "$ROOT" in   # gigabytes of models and the environment would sync to every device
  *"Mobile Documents"*|*CloudStorage*|*Dropbox*|*"Google Drive"*|*OneDrive*)
    echo "  Warning: HarmonicFitness is inside a synced folder ($ROOT). Its models and Python environment"
    echo "  (several GB) would sync too; a folder outside it is better, or set HARMONICFITNESS_MODELS." ;;
esac
echo
echo "Prerequisites"
if [ -n "$UV" ]; then echo "  uv:     $UV"; else
  echo "  uv:     missing. It installs without admin rights: ./harmonicfitness setup --install-uv"
  echo "          (which runs Astral's official installer: $UV_INSTALL)"
fi
if [ -n "$GIT" ]; then
  [ "$INGIT" = yes ] && echo "  git:    $GIT" || echo "  git:    $GIT (this folder isn't a git checkout, so the privacy hook is skipped)"
else
  echo "  git:    missing; only the privacy hook and ./harmonicfitness backup need it"
fi
if [ -n "$FFMPEG" ]; then echo "  ffmpeg: $FFMPEG"; else
  echo "  ffmpeg: not installed; the Python environment brings its own"
fi
[ "$VENV" = yes ] && echo "  Python environment: ready" || echo "  Python environment: not made yet (./harmonicfitness setup makes it)"
echo
echo "Audio here"
case "$LOCAL" in
  fast) echo "  Local voices: yes (Pocket TTS), on $( [ "$LOCAL_ENGINE" = cuda ] && echo "the NVIDIA card (CUDA)" || echo "the processor" )" ;;
  experimental) echo "  Local voices: on the processor (no NVIDIA card): experimental, speed unknown, likely slow" ;;
  *) echo "  Local voices: no. $LOCAL_REASON" ;;
esac
[ "$1" = "--short" ] && exit 0   # setup prints this part; it reports the rest itself
echo
if [ "$VENV" = yes ]; then
  cd "$ROOT" && "$PY" "$ROOT/tools/doctor.py"
else
  echo "The rest is checked once ./harmonicfitness setup has made the environment."
fi
