#!/bin/sh
# Generate the judged grid's skeletons: for each case in docs/eval/cases.toml, run the session
# composer (./sweatcast session) as that case's invented listener and write
#   docs/eval/out/<id>.skeleton.txt   the skeleton (methods, doses, candidates, health lines)
#   docs/eval/out/<id>.skeleton.stderr.txt   that run's warnings and errors
#   docs/eval/out/<id>.markers.txt    the same with --draft: only the @@ markers, for the script
# The composer was retired in 7.2.0 and is kept only as the eval's baseline, so this runs it from the
# v7.1.0 tag: a temporary git worktree of that tag, with this checkout's Python environment, cases and
# listeners (SWEATCAST_HOME), removed when the script ends. The worktree's catalog and dose rules are
# 7.1.0's, which is the baseline. Run from anywhere; docs/eval/out/ is git-ignored.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PY=${SWEATCAST_PYTHON:-$ROOT/.venv/bin/python}
[ -x "$PY" ] || PY="$ROOT/.venv/Scripts/python.exe"   # Windows (Git Bash)
OUT="$ROOT/docs/eval/out"
mkdir -p "$OUT"

OLD=$(mktemp -d)
rmdir "$OLD"   # git worktree add makes it
git worktree add --quiet --detach "$OLD" v7.1.0
trap 'git -C "$ROOT" worktree remove --force "$OLD"' EXIT

# One line per case: id, listener, then the session flags, tab-separated.
"$PY" - <<'PYEOF' > "$OUT/cases.tsv"
import sys
import tomllib
sys.stdout.reconfigure(newline="\n")   # no \r on Windows: it would stick to the last flag
with open("docs/eval/cases.toml", "rb") as f:
    cases = tomllib.load(f)["case"]
for c in cases:
    flags = ["--goal", c["goal"], "--minutes", str(c["minutes"]), "--preset", c["preset"]]
    for key in ("level", "target", "limit", "method"):
        if c.get(key):
            flags += [f"--{key}", c[key]]
    print("\t".join([c["id"], c["listener"], *flags]))
PYEOF

failed=0
while IFS="$(printf '\t')" read -r id listener flags; do
    # The flags hold no spaces, so the shell splits them on tabs and spaces alike.
    # shellcheck disable=SC2086
    set -- $flags
    home="$ROOT/docs/eval/listeners/$listener"
    if SWEATCAST_PYTHON="$PY" SWEATCAST_HOME="$home" "$OLD/sweatcast" session "$@" --today 2026-10-21 \
            > "$OUT/$id.skeleton.txt" 2> "$OUT/$id.skeleton.stderr.txt" &&
       SWEATCAST_PYTHON="$PY" SWEATCAST_HOME="$home" "$OLD/sweatcast" session "$@" --today 2026-10-21 --draft \
            > "$OUT/$id.markers.txt" 2> "$OUT/$id.markers.stderr.txt"; then
        echo "$id: ok"
    else
        echo "$id: failed, see docs/eval/out/$id.skeleton.stderr.txt" >&2
        failed=1
    fi
done < "$OUT/cases.tsv"
exit $failed
