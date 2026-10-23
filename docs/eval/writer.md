# Writer: the judged grid's scripts

You are one of the writers turning `./sweatcast session` skeletons into narrated workout scripts for
sweatcast's judged eval grid. Run every command from the repo root. The listeners are invented;
nothing here is personal data. Each writer takes five cases.

## Read first
- `docs/eval/README.md` (what the grid is), `docs/eval/cases.toml` (your case rows).
- `.claude/skills/workout/SKILL.md`, **Step 2 items 3 and 6 and all of Step 3** (the script rules).
- `knowledge/tts-rules.md` (follow it exactly: no digits, no symbols except `[pause Ns]` and `[chime]`).
- `knowledge/programming.md` for effort, rest, tempo cues.
- For each case: the listener folder `docs/eval/listeners/<listener>/` (profile.md, health.md, log.md),
  the skeleton `docs/eval/out/<id>.skeleton.txt` and the markers `docs/eval/out/<id>.markers.txt`.
- The skeleton's `Coaching` section for each first pick's setup, cues, rep, feel and faults; for any
  other candidate, `./sweatcast movements --about <ids>`. Coach from these, not from memory.

## Policy (keeps runs comparable)
- Take the **first candidate** in every slot, and for the warm-up, finisher and cool-down pick from the
  candidates printed under their lines (first ones by preference; several may be used in a warm-up or
  cool-down). Narrate the skeleton as printed: its doses (sets, reps, rest, work and rest seconds, rounds).
- Deviate only when the first candidate is unusable or unsafe for this listener (kit can't support it,
  limit conflict, a "hard effort" that obviously isn't hard, etc.). When you deviate, use another printed
  candidate, never a movement from memory.
- Record **every** deviation and every place where the skeleton left you to invent something (missing
  content, dose that doesn't fit the slot seconds, ambiguous sides, transitions between machines, etc.) in
  `docs/eval/out/<id>.writer-notes.md`: a short bullet list. Also note anything that made the skeleton
  hard to narrate. If nothing, write "No deviations."
- Write the script under **exactly** the `@@` lines from the markers file, in order, without changing the
  seconds. You may change a marker's title only when you picked a different candidate.
- No research, no feeds: where the skill calls for topic beats (headlines, science, deep dive, quiz),
  write a single one-line placeholder paragraph such as `Topic beat: a short science story goes here.`
  Keep placeholders to a minimum share of time; fill most time with coaching (setup, cues, breathing,
  check-ins, what's next). Don't invent scores, quotes or events.
- Health: speak the full safety rules (first-session length) from health.md's limits and clinician rules
  and the skeleton's `Health: today:` lines, and the skeleton's `Limit cues:` lines where they apply.
- Voice: follow `knowledge/tts-rules.md`, Coaching voice, in full: greet the listener by the `name` in
  their profile.md and use it two to four times, talk like a person around the work (contractions,
  "let's", a line of why, the effort noticed plainly), take one or two continuity lines from
  `SWEATCAST_HOME=docs/eval/listeners/<listener> ./sweatcast coverage` (it may say there's no log yet; then
  make it a first-session welcome), vary the segment openings, hand off to topic placeholders the way a
  person would, and close specifically and personally. The lint warns on the name, repeated openings and
  newsreader handoffs; clear those warnings too.

## Script habits judges have marked down; avoid them
- Cue **during** the work. No five-second set calls ("At the bell, go... Halfway... Rack it. Rest.") eating
  a short set. Say "rack it" only when a weight is in hand.
- No rest talk inside a little-rest circuit's stations; rest goes where the skeleton puts it.
- On sided (`each side`) entries say "per side" (or "each leg"), and do both sides unless the skeleton says
  "<side> side only".
- Say the rest the slot actually holds, not a number the slot can't contain.
- Don't repeat filler lines word for word within a script; vary praise.
- Intervals and timed work inside one segment: mark each work start and stop with `[chime]`, and the cue
  says it too ("At the bell, go. [chime] Push."). Each interval marker segment is one effort plus its
  recovery. Put `[hold]` where the listener works (or recovers) in silence: the segment then keeps its
  full length and its spare time goes quiet there, so a short effort needs a few cues, not nonstop talk.
  Time the work with a fixed hold (`[hold 20s]`) and give the rest one bare `[hold]`
  (`knowledge/tts-rules.md`, Orientation). Don't use it to pad stories or long rests in strength sets.
- Keep the opening safety text tight in a short warm-up so the warm-up still warms up.

## Lint (must pass for each script)
```sh
SWEATCAST_HOME=docs/eval/listeners/<listener> ./sweatcast build docs/eval/out/<id>.draft.txt "eval-<id>" --lint-only
```
The build name argument (`"eval-<id>"`) is required; without it a render starts. Fix flagged segments
until it exits 0 (total within three percent of plan). If a lint failure seems to be the harness's fault,
note it in the writer notes.

## Report back
For each case: lint result (exit code and predicted total vs plan), and the three most important
points from your writer notes. Keep the report under 300 words.
