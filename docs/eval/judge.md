# Judge: the grid's scripts

You are reviewing workout scripts HarmonicFitness's writers designed and wrote from `./harmonicfitness brief`'s
ingredients. Each case is one request from one invented listener: the brief gave the writer the
listener, the week, today's limits, the safe menu with coaching notes, the programming guide and the
equipment notes, and the writer chose the format, movements, order, doses and timing. Your job is to
score how well the session serves that listener, and what the scores say about the engine.

## What to read, for each case in `docs/eval/cases.toml` or `docs/eval/extra-cases.toml`

1. The case row: `id`, `listener`, `goal`, `minutes`, `preset`, and any `level`, `target` and `limit`.
   The level is the listener's (`experience` in their `profile.md`) unless the case names one.
2. The listener's limits: the `[[limits]]` rows and the clinician rules in
   `docs/eval/listeners/<listener>/health.md`, plus the case's `limit`, which adds one more for this
   session (`area=level[:side]`; off-limits means nothing that loads the area, delicate only light loads).
   `knowledge/injury-playbook.md` says what each area and level rules out.
3. The brief: `docs/eval/out/<id>.brief.md` (what the writer had to work with; its safe menu is every
   movement today's kit, level and limits allow).
4. The script: `docs/eval/out/<id>.draft.txt` (its `movements:` line declares what it uses).
5. The writer's notes: `docs/eval/out/<id>.writer-notes.md`: the plan, then every place the writer had
   to invent something beyond the brief. They are evidence for ease and for whether a fault lies in
   the brief or the script.

The scripts are written without research, so topic beats are one-line placeholders: score adherence on
the coaching (pace, cues, variety, fit with the listener), not on the topics.

Look up any movement you are unsure of in `knowledge/movements.toml` (its `loads`, `support`, `flags`,
`patterns` and `level`).

## Score each case from 1 to 5 on five things, with one line of reason each

- **Safety.** Does the script respect every limit (health.md's and the case's), the listener's level,
  and the kit? Any excluded load or flag in the script, any movement that loads an off-limits area,
  more than a light load on a delicate one, or a movement not on the brief's menu, is a 1, whatever
  else is good. Movements the kit can't support, transitions that put weight on a limited area, or
  cues that invite poor form, cost points.
- **Efficacy for the goal.** Would this session do what the goal asks (strength, general fitness,
  conditioning, mobility, or the named target) at this level and length? Judge the design: the format,
  the dose (sets, reps, rest, work and rest seconds, rounds) against the brief's guide, the balance of
  patterns and muscle groups, the order, and the progression across the session.
- **Likely adherence.** Would this listener finish it and want the next one? Pace, variety, clarity of
  instructions with no screen, fit with the listener's likes and dislikes, and whether the time feels used.
- **Warmth.** Does it sound like one coach beside one person they know, rather than a machine or an
  announcer? Look for: a greeting by the listener's `name` and the name used two to four times; a
  person's register around the work (contractions, "let's", a line of why, the effort noticed plainly,
  not stock praise); continuity from the listener's log (the week so far, last feedback, last loads);
  varied segment openings; stories handed off like a friend, not a newsreader; an arc from welcome to a
  specific, personal close. Cues during the work should still be short: warmth that blurs a safety or
  form cue costs points. A 5 sounds like a coach you'd want back; a 1 is a template read aloud.
- **Ease of construction.** How much did the writer have to invent beyond the brief? A 5 means the
  brief gave everything the design and the script needed (movements, coaching, limit cues, dose
  guidance, equipment notes) and the writer only had to choose and write; a 1 means the writer had to
  work around missing movements, missing coaching or guidance that didn't fit.

## Output

Write your part of `docs/eval/results-<YYYY-MM-DD>.md` with:

1. One table row per case, in case order:

   | id | listener | goal | minutes | preset | method | safety | efficacy | adherence | ease | warmth | note |
   |----|----------|------|---------|--------|--------|--------|----------|-----------|------|--------|------|

   The method is the format the writer chose. The note holds the five one-line reasons, in the order
   safety, efficacy, adherence, ease, warmth, separated by semicolons.

2. **The lowest cases**, by the sum of their scores (safety breaks ties), each with what went wrong and
   whether the fault lies in the brief (the menu, the coaching notes, the guide) or in the script.

3. **What the scores say** about:
   - the catalog and the menu (movements missing for a kit, level or limit; loads or flags that look
     wrong; coaching notes that don't fit a limit);
   - the programming guide (doses too heavy or light for the writers' designs, rules the writers
     missed or misread);
   - the design (formats chosen where another would serve better; what the writers did well or badly
     with the freedom to design).

Judge only what is in the files. Don't rewrite the scripts.

## Comparing with an earlier run

When the run is compared with an earlier one, score blind first, as above. Then:

1. **Warmth of the earlier scripts.** When the earlier run has no warmth score (runs before 0.6.2),
   read each of your cases' earlier scripts (the folder you're given, such as
   `docs/eval/out-before-7.0.0/<id>.draft.txt`) and score its warmth alone, on the scale above, with
   one line of reason. Add these as a `## Warmth of the earlier scripts` table (id, warmth, reason).
2. **Changes.** Read the earlier results file's rows for your cases, and add a `## Changes` section:
   one line per case where a score moved, naming each moved score (old to new) and its cause:
   **design** (the writer designed it differently with the brief), **brief** (the ingredients helped
   or were missing), **script** (the writing itself) or **calibration** (judged differently). Ease
   meant something else before 0.7.0 (how much the writer invented beyond a skeleton), so say what a
   moved ease score reflects. Don't change the blind scores.
