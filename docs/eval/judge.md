# Judge: the session builder's grid

You are reviewing workout scripts written from `./sweatcast session` skeletons. Each case is one
request from one invented listener; a writer turned the case's skeleton into a narrated script. Your job
is to score how well the skeleton and the script serve that listener, and what the scores say about
the engine.

## What to read, for each case in `docs/eval/cases.toml`

1. The case row: `id`, `listener`, `goal`, `minutes`, `preset`, and any `level`, `target` and `limit`.
   The level is the listener's (`experience` in their `profile.md`) unless the case names one.
2. The listener's limits: the `[[limits]]` rows and the clinician rules in
   `docs/eval/listeners/<listener>/health.md`, plus the case's `limit`, which adds one more for this
   session (`area=level[:side]`; off-limits means nothing that loads the area, delicate only light loads).
   `knowledge/injury-playbook.md` says what each area and level rules out.
3. The skeleton: `docs/eval/out/<id>.skeleton.txt` (the method, the blocks, each slot's dose and
   candidate movements with reasons, the total).
4. The script: `docs/eval/out/<id>.draft.txt`.

Look up any movement you are unsure of in `knowledge/movements.toml` (its `loads`, `flags`, `patterns`
and `level`).

## Score each case from 1 to 5 on four things, with one line of reason each

- **Safety.** Does the script respect every limit (health.md's and the case's), the listener's level,
  and the kit? Any excluded load or flag in the script, any movement that loads an off-limits area,
  or more than a light load on a delicate one, is a 1, whatever else is good. Movements the kit can't
  support, or cues that invite poor form, cost points.
- **Efficacy for the goal.** Would this session do what the goal asks (strength, general fitness,
  conditioning, mobility, or the named target) at this level and length? Judge the dose (sets, reps,
  rest, work and rest seconds, rounds), the balance of patterns, and the progression across the session.
- **Likely adherence.** Would this listener finish it and want the next one? Pace, variety, clarity of
  instructions with no screen, fit with the listener's likes and dislikes, and whether the time feels used.
- **Ease of construction.** How much did the writer have to invent beyond the skeleton? A 5 means the
  skeleton gave everything (movements, doses, order, timing) and the writer only narrated; a 1 means the
  writer had to replace movements, rework doses or restructure the session to make it usable.

## Output

Write `docs/eval/results-<YYYY-MM-DD>.md` with:

1. One table row per case, in case order:

   | id | safety | efficacy | adherence | ease | note |
   |----|--------|----------|-----------|------|------|

   The note holds the four one-line reasons, shortest first, separated by semicolons.

2. **The five lowest cases**, by the sum of their four scores (safety breaks ties), each with what went
   wrong and whether the fault lies in the skeleton or in the script.

3. **What the scores say** about:
   - the catalog (movements missing for a kit, level or limit; loads or flags that look wrong);
   - the dose rules in `knowledge/sessions.toml` (doses too heavy, too light, rests too long or short);
   - the methods (a method chosen where another would serve better; methods that fit poorly at some lengths).

Judge only what is in the files. Don't rewrite the scripts.
