# The judged grid

Forty requests for `./sweatcast session`, over four invented listeners, used to judge the session
builder before a release: each case's skeleton is turned into a script, and a reviewer scores the
scripts for safety, efficacy, adherence and ease of construction.

- `cases.toml`: the forty cases. Strength, general and conditioning at the novice, experienced and
  advanced levels make nine cells; each runs at two kit presets and two lengths (ten to twenty minutes
  and thirty to forty five), which is thirty six, plus two mobility and two targeted cases. Every third
  case adds a `--limit`. `tests/test_session.py` (class `Eval`) checks the grid and that every case composes.
- `listeners/{a,b,c,d}/`: the listeners, each a complete context folder (`SWEATCAST_HOME`), all invented.
  a is a novice with a mat and no limits; b is experienced in hotel gyms with a delicate neck; c is advanced
  in a full gym with the low back off limits; d is experienced in hotel rooms, with likes and dislikes and
  no log yet.
- `judge.md`: the reviewer's prompt.
- `skeletons.sh`: the generation loop.
- `out/` (git-ignored): the generated skeletons, markers, scripts and lints.

Run each command from the repo root.

## 1. Generate the skeletons

```sh
docs/eval/skeletons.sh
```

For each case it runs `SWEATCAST_HOME=docs/eval/listeners/<listener> ./sweatcast session --goal ...
--minutes ... --preset ... [--level ...] [--target ...] [--limit ...] --today 2026-10-21` into
`docs/eval/out/<id>.skeleton.txt`, and the same with `--draft` into `docs/eval/out/<id>.markers.txt`
(the `@@` markers a script is written under). The date is fixed, so the skeletons are the same on
every run until the catalog, the dose rules or the composer change.

## 2. Write and lint the scripts

Write each case's script under its markers into `docs/eval/out/<id>.draft.txt`, following the
`workout` skill's script step (`.claude/skills/workout/SKILL.md`) for that listener, then lint it:

```sh
for f in docs/eval/out/c*.draft.txt; do
  id=$(basename "$f" .draft.txt)
  listener=$(grep -A1 "id = \"$id\"" docs/eval/cases.toml | sed -n 's/^listener = "\(.*\)"/\1/p')
  SWEATCAST_HOME=docs/eval/listeners/$listener ./sweatcast build "$f" "eval-$id" --lint-only --allow-estimated || echo "$id: lint failed"
done
```

## 3. Judge

Give a reviewer `docs/eval/judge.md` as its prompt, with `cases.toml`, the listeners and `docs/eval/out/`
to read; it writes `docs/eval/results-<YYYY-MM-DD>.md` (a row per case, the five lowest, and what the
scores say about the catalog, the dose rules and the methods). The results file is committed; `out/` is not.
