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
5. The writer's notes: `docs/eval/out/<id>.writer-notes.md`, every place the writer left the skeleton or
   had to invent something. They are evidence for ease and for whether a fault lies in the skeleton or
   the script.

The scripts are written without research, so topic beats are one-line placeholders: score adherence on
the coaching (pace, cues, variety, fit with the listener), not on the topics.

Look up any movement you are unsure of in `knowledge/movements.toml` (its `loads`, `flags`, `patterns`
and `level`).

## Score each case from 1 to 5 on five things, with one line of reason each

- **Safety.** Does the script respect every limit (health.md's and the case's), the listener's level,
  and the kit? Any excluded load or flag in the script, any movement that loads an off-limits area,
  or more than a light load on a delicate one, is a 1, whatever else is good. Movements the kit can't
  support, or cues that invite poor form, cost points.
- **Efficacy for the goal.** Would this session do what the goal asks (strength, general fitness,
  conditioning, mobility, or the named target) at this level and length? Judge the dose (sets, reps,
  rest, work and rest seconds, rounds), the balance of patterns, and the progression across the session.
- **Likely adherence.** Would this listener finish it and want the next one? Pace, variety, clarity of
  instructions with no screen, fit with the listener's likes and dislikes, and whether the time feels used.
- **Warmth.** Does it sound like one coach beside one person they know, rather than a machine or an
  announcer? Look for: a greeting by the listener's `name` (in their `profile.md`) and the name used two
  to four times; a person's register around the work (contractions, "let's", a line of why, the effort
  noticed plainly, not stock praise); continuity from the listener's log (the week so far, last
  feedback, last loads); varied segment openings; stories handed off like a friend, not a newsreader;
  an arc from welcome to a specific, personal close. Cues during the work should still be short: warmth
  that blurs a safety or form cue costs points. A 5 sounds like a coach you'd want back; a 1 is a
  template read aloud.
- **Ease of construction.** How much did the writer have to invent beyond the skeleton? A 5 means the
  skeleton gave everything (movements, doses, order, timing) and the writer only narrated; a 1 means the
  writer had to replace movements, rework doses or restructure the session to make it usable.

## Output

Write `docs/eval/results-<YYYY-MM-DD>.md` with:

1. One table row per case, in case order:

   | id | safety | efficacy | adherence | ease | warmth | note |
   |----|--------|----------|-----------|------|--------|------|

   The note holds the five one-line reasons, in the order safety, efficacy, adherence, ease, warmth, separated by semicolons.

2. **The five lowest cases**, by the sum of their scores (safety breaks ties), each with what went
   wrong and whether the fault lies in the skeleton or in the script.

3. **What the scores say** about:
   - the catalog (movements missing for a kit, level or limit; loads or flags that look wrong);
   - the dose rules in `knowledge/sessions.toml` (doses too heavy, too light, rests too long or short);
   - the methods (a method chosen where another would serve better; methods that fit poorly at some lengths).

Judge only what is in the files. Don't rewrite the scripts.

## Comparing with an earlier run

When the run is compared with an earlier one, score blind first, as above. Then read the earlier
results file's rows for your cases (and its scripts, if they were kept), and add a `## Changes` section:
one line per case where a score moved, naming each moved score (old to new) and its cause, **skeleton**
(the skeleton changed), **script** (the writer did something differently) or **calibration** (judged
differently). Don't change the blind scores.
