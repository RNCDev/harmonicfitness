# The judged grid

Forty requests over four invented listeners, used to judge sessions before a release: for each case a
writer designs and writes a session from `./sweatcast brief`'s ingredients, the way the workout skill
does, and reviewers score the scripts for safety, efficacy, adherence, ease of construction and warmth.

- `cases.toml`: the forty cases. Strength, general and conditioning at the novice, experienced and
  advanced levels make nine cells; each runs at two kit presets and two lengths (ten to twenty minutes
  and thirty to forty five), which is thirty six, plus two mobility and two targeted cases. Every third
  case adds a `--limit`. `tests/test_session.py` (class `Eval`) checks the grid and that every case composes.
- `extra-cases.toml`: cases beyond the forty, in the same fields (a `limit` may be a list), such as c41,
  an off-limits ankle with a delicate foot on the same side.
- `listeners/{a,b,c,d}/`: the listeners, each a complete context folder (`SWEATCAST_HOME`), all invented,
  with invented first names (Maya, Theo, Priya and Sam) for the coach to use.
  a is a novice with a mat and no limits; b is experienced in hotel gyms with a delicate neck; c is advanced
  in a full gym with the low back off limits; d is experienced in hotel rooms, with likes and dislikes and
  no log yet.
- `briefs.sh`: each case's brief and menu. `skeletons.sh`: the composer's skeletons, the baseline
  before 7.0.0 (its writers narrated them).
- `writer.md`: the writer's brief (a few cases a writer). `judge.md`: the reviewer's prompt.
- `out/` (git-ignored): the generated briefs and menus, scripts, writer notes, lints and judges' parts.

Run each command from the repo root.

## 1. Generate the briefs

```sh
docs/eval/briefs.sh            # every case
docs/eval/briefs.sh c06 c41    # just these
```

For each case it runs `SWEATCAST_HOME=docs/eval/listeners/<listener> ./sweatcast brief --goal ... --minutes
... --preset ... [--level ...] [--target ...] [--limit ...] --today 2026-10-21 --save docs/eval/out/<id>.draft.txt`,
which writes `docs/eval/out/<id>.brief.md` and `<id>.menu.json` (its stderr into `<id>.brief.stderr.txt`).
The date is fixed, so the briefs are the same on every run until the catalog, the dose rules or the
knowledge files change.

## 2. Write and lint the scripts

Writers follow `writer.md`: design the session from the brief, put the plan and every place they had to
invent something in `docs/eval/out/<id>.writer-notes.md`, write `docs/eval/out/<id>.draft.txt` (its
`movements:` line, then the segments), and lint it. Two or three cases a writer keeps each brief in view.
The build name (`"eval-<id>"`) is required: without it `--lint-only` is taken as the name and a render
starts. The lint checks the draft against its menu, and exports a `.txt` into the listener's `workouts/`,
which is git-ignored.

```sh
SWEATCAST_HOME=docs/eval/listeners/<listener> ./sweatcast build docs/eval/out/<id>.draft.txt "eval-<id>" --lint-only
```

## 3. Judge

Give reviewers `docs/eval/judge.md` as their prompt, a few cases each in case order, with the case files,
the listeners and `docs/eval/out/` to read; each writes its part to `docs/eval/out/judge-<n>.md`. Their rows
make `docs/eval/results-<YYYY-MM-DD>.md` (a row per case, the lowest cases, and what the scores say about the
catalog and menu, the programming guide and the design); a second run on the same day adds `-run2`, and so
on. Keep the table's columns (id, listener, goal, minutes, preset, method, safety, efficacy, adherence,
ease, warmth, note) so runs can be compared row by row; warmth was added in release 6.2.0, so earlier runs
have none, and 7.0.0's ease measures what the writer invented beyond the brief, not beyond a skeleton.
Copy `out/`'s drafts aside (as `out-before-<version>/`, git-ignored) before the next run if it will be
compared with this one. The results file is committed; `out/` is not.
