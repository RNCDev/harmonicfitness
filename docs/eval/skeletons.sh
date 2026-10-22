#!/bin/sh
# Generate the judged grid's skeletons: for each case in docs/eval/cases.toml, run
# ./sweatcast session as that case's invented listener and write
#   docs/eval/out/<id>.skeleton.txt   the skeleton (methods, doses, candidates, health lines)
#   docs/eval/out/<id>.skeleton.stderr.txt   that run's warnings and errors
#   docs/eval/out/<id>.markers.txt    the same with --draft: only the @@ markers, for the script
# Run from anywhere; it works from the repo root. docs/eval/out/ is git-ignored.
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PY=${SWEATCAST_PYTHON:-.venv/bin/python}
OUT=docs/eval/out
mkdir -p "$OUT"

# One line per case: id, listener, then the session flags, tab-separated.
"$PY" - <<'EOF' > "$OUT/cases.tsv"
import tomllib
with open("docs/eval/cases.toml", "rb") as f:
    cases = tomllib.load(f)["case"]
for c in cases:
    flags = ["--goal", c["goal"], "--minutes", str(c["minutes"]), "--preset", c["preset"]]
    for key in ("level", "target", "limit", "method"):
        if c.get(key):
            flags += [f"--{key}", c[key]]
    print("\t".join([c["id"], c["listener"], *flags]))
EOF

failed=0
while IFS="$(printf '\t')" read -r id listener flags; do
    # The flags hold no spaces, so the shell splits them on tabs and spaces alike.
    # shellcheck disable=SC2086
    set -- $flags
    if SWEATCAST_HOME="docs/eval/listeners/$listener" ./sweatcast session "$@" --today 2026-10-21 \
            > "$OUT/$id.skeleton.txt" 2> "$OUT/$id.skeleton.stderr.txt" &&
       SWEATCAST_HOME="docs/eval/listeners/$listener" ./sweatcast session "$@" --today 2026-10-21 --draft \
            > "$OUT/$id.markers.txt" 2> "$OUT/$id.markers.stderr.txt"; then
        echo "$id: ok"
    else
        echo "$id: failed, see $OUT/$id.skeleton.stderr.txt" >&2
        failed=1
    fi
done < "$OUT/cases.tsv"
exit $failed
