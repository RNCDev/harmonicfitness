#!/bin/bash
# The script-writing bench: <runs> timed runs of one configuration, one started every 20 s (Gemini's paid tier 2
# caps input at 3,000,000 tokens a minute, which fifteen runs starting together passed), then a line each.
#
#   web/bench/batch.sh <label> <minutes> <runs> [run_one.py options: --engine <root>, --set NAME=VALUE]
#
# Output goes to .bench/out/<label>/<n>/ (git-ignored, and refused by the privacy hook: each run holds a copy of
# the listener's files). The first batch of the day prepares .bench/base-<home's folder name>: a copy of me/ without its key file or
# clip cache, with today's feeds fetched once, so every run reads the same sheet. Don't start a batch near
# midnight: a run's menu is dated by the day it began.
set -e
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
label=$1; minutes=$2; runs=$3; shift 3
HOME_DIR="${HARMONICFITNESS_HOME:-$REPO/me}"
BASE="$REPO/.bench/base-$(basename "$HOME_DIR")"   # one per home: Jo's copy and me/'s never share a folder
today="$(date +%Y-%m-%d)"
if [ ! -f "$BASE/.prepared-$today" ]; then
  rm -rf "$BASE"; mkdir -p "$REPO/.bench"
  rsync -a --exclude .env --exclude .audio-cache --exclude coaches "$HOME_DIR/" "$BASE/"
  HARMONICFITNESS_HOME="$BASE" ./harmonicfitness feeds > /dev/null
  touch "$BASE/.prepared-$today"
fi
export PYDANTIC_AI_NO_BANNER=1
for ((i = 1; i <= runs; i++)); do
  out="$REPO/.bench/out/$label/$i"
  rm -rf "$out"; mkdir -p "$out"
  .venv/bin/python web/bench/run_one.py "$out" "$minutes" --home "$HOME_DIR" --base "$BASE" "$@" \
    > "$out/summary.json" 2> "$out/stderr.txt" &
  [ "$i" -lt "$runs" ] && sleep 20
done
wait
for ((i = 1; i <= runs; i++)); do cat "$REPO/.bench/out/$label/$i/summary.json"; done
