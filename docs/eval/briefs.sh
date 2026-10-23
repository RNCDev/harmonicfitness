#!/bin/sh
# Generate the judged grid's briefs (the 7.0.0 path): for each case in docs/eval/cases.toml and
# docs/eval/extra-cases.toml, or only the ids given, run ./sweatcast brief --save as that case's
# invented listener and write
#   docs/eval/out/<id>.brief.md          the brief the writer designs the session from
#   docs/eval/out/<id>.menu.json         the menu the lint checks docs/eval/out/<id>.draft.txt against
#   docs/eval/out/<id>.brief.stderr.txt  that run's warnings and errors
# The date is fixed, so the briefs are the same on every run until the catalog, the dose rules or the
# knowledge files change. Run from anywhere; docs/eval/out/ is git-ignored.
#   docs/eval/briefs.sh                  # every case
#   docs/eval/briefs.sh c06 c41          # just these
set -eu
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PY=${SWEATCAST_PYTHON:-.venv/bin/python}
[ -x "$PY" ] || PY=.venv/Scripts/python.exe   # Windows (Git Bash)
OUT=docs/eval/out
mkdir -p "$OUT"

# One line per case: id, listener, then the brief's flags, tab-separated.
"$PY" - "$@" <<'PYEOF' > "$OUT/briefs.tsv"
import sys
import tomllib
sys.stdout.reconfigure(newline="\n")   # no \r on Windows: it would stick to the last flag
want = set(sys.argv[1:])
cases = []
for path in ("docs/eval/cases.toml", "docs/eval/extra-cases.toml"):
    with open(path, "rb") as f:
        cases += tomllib.load(f)["case"]
unknown = want - {c["id"] for c in cases}
if unknown:
    sys.exit(f"unknown case ids: {', '.join(sorted(unknown))}")
for c in cases:
    if want and c["id"] not in want:
        continue
    flags = ["--goal", c["goal"], "--minutes", str(c["minutes"]), "--preset", c["preset"]]
    for key in ("level", "target"):
        if c.get(key):
            flags += [f"--{key}", c[key]]
    limits = c.get("limit") or []
    for limit in [limits] if isinstance(limits, str) else limits:
        flags += ["--limit", limit]
    print("\t".join([c["id"], c["listener"], *flags]))
PYEOF

failed=0
while IFS="$(printf '\t')" read -r id listener flags; do
    # The flags hold no spaces, so the shell splits them on tabs and spaces alike.
    # shellcheck disable=SC2086
    set -- $flags
    if SWEATCAST_HOME="docs/eval/listeners/$listener" ./sweatcast brief "$@" --today 2026-10-21 \
            --save "$OUT/$id.draft.txt" > /dev/null 2> "$OUT/$id.brief.stderr.txt"; then
        echo "$id: ok"
    else
        echo "$id: failed, see $OUT/$id.brief.stderr.txt" >&2
        failed=1
    fi
done < "$OUT/briefs.tsv"
exit $failed
