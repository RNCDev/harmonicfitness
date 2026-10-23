# The judged grid

Forty requests for `./sweatcast session`, over four invented listeners, used to judge the session
builder before a release: each case's skeleton is turned into a script, and a reviewer scores the
scripts for safety, efficacy, adherence, ease of construction and warmth.

- `cases.toml`: the forty cases. Strength, general and conditioning at the novice, experienced and
  advanced levels make nine cells; each runs at two kit presets and two lengths (ten to twenty minutes
  and thirty to forty five), which is thirty six, plus two mobility and two targeted cases. Every third
  case adds a `--limit`. `tests/test_session.py` (class `Eval`) checks the grid and that every case composes.
- `listeners/{a,b,c,d}/`: the listeners, each a complete context folder (`SWEATCAST_HOME`), all invented,
  with invented first names (Maya, Theo, Priya and Sam) for the coach to use.
  a is a novice with a mat and no limits; b is experienced in hotel gyms with a delicate neck; c is advanced
  in a full gym with the low back off limits; d is experienced in hotel rooms, with likes and dislikes and
  no log yet.
- `writer.md`: the script writer's brief (five cases a writer).
- `judge.md`: the reviewer's prompt (ten cases a judge).
- `skeletons.sh`: the generation loop.
- `out/` (git-ignored): the generated skeletons, markers, scripts and lints.

Run each command from the repo root.

## 1. Generate the skeletons

```sh
docs/eval/skeletons.sh
```

For each case it runs `SWEATCAST_HOME=docs/eval/listeners/<listener> ./sweatcast session --goal ...
--minutes ... --preset ... [--level ...] [--target ...] [--limit ...] --today 2026-10-21` into
`docs/eval/out/<id>.skeleton.txt` (its stderr into `<id>.skeleton.stderr.txt`), and the same with `--draft` into `docs/eval/out/<id>.markers.txt`
(the `@@` markers a script is written under). The date is fixed, so the skeletons are the same on
every run until the catalog, the dose rules or the composer change.

## 2. Write and lint the scripts

Write each case's script under its markers into `docs/eval/out/<id>.draft.txt`, following
`writer.md` (which points at the `workout` skill's script step), with the writer's notes beside it in
`<id>.writer-notes.md`, then lint it. Eight writers of five cases each is the usual split. The build
name (`"eval-<id>"`) is required: without it `--lint-only` is taken as the name and a render starts.
The lint also exports a `.txt` into the listener's `workouts/`, which is git-ignored.

```sh
for f in docs/eval/out/c*.draft.txt; do
  id=$(basename "$f" .draft.txt)
  listener=$(grep -A1 "id = \"$id\"" docs/eval/cases.toml | sed -n 's/^listener = "\(.*\)"/\1/p')
  SWEATCAST_HOME=docs/eval/listeners/$listener ./sweatcast build "$f" "eval-$id" --lint-only || echo "$id: lint failed"
done
```

## 3. Judge

Give four reviewers `docs/eval/judge.md` as their prompt, ten cases each in case order (c01 to c10,
c11 to c20 and so on, so part means line up across runs), with `cases.toml`, the listeners and
`docs/eval/out/` to read. Their rows make `docs/eval/results-<YYYY-MM-DD>.md` (a row per case, the five
lowest, and what the scores say about the catalog, the dose rules and the methods); a second run on the
same day adds `-run2`, and so on. Keep the table's columns (id, listener, goal, minutes, preset, method,
safety, efficacy, adherence, ease, warmth, note) so runs can be compared row by row; warmth was added in
release 6.2.0, so earlier runs have none, and totals compare on the first four. Copy `out/`'s drafts aside
before the next run if it will be compared with this one. The results file is committed; `out/` is not.
