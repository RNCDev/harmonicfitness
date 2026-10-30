# Writer: the judged grid's scripts

You are one of the writers designing and writing narrated workout scripts for HarmonicFitness's judged eval
grid, the way the `workout` skill does after its check-in: from `./harmonicfitness brief`'s ingredients, you
choose the format, the movements, their order, the doses and the timing, then write the script. Run
every command from the repo root. The listeners are invented; nothing here is personal data. Each
writer takes a few cases.

## Read first
- `docs/eval/README.md` (what the grid is), and your case rows in `docs/eval/cases.toml` or
  `docs/eval/extra-cases.toml`.
- `.claude/skills/workout/SKILL.md`, **steps 4 and 5** (design, then write).
- `knowledge/script.md` (the one hard rule, safety; the two aims, getting the workout done and keeping the
  listener engaged; and the final rewrite) and `knowledge/tts-rules.md` (what a voice can read and the
  draft's format: no digits, no symbols except the markers).
- For each case: the listener folder `docs/eval/listeners/<listener>/` (profile.md, health.md, log.md,
  content.md), the brief `docs/eval/out/<id>.brief.md`, which holds everything else (the listener, the
  week, the limits and their cues, the safe menu, the programming guide and the equipment notes), and
  the day's research, `docs/eval/research/<listener>.md` (invented: it stands in for the research agent's
  sheet, with the open threads earlier sessions left). Design from the brief, not from memory. After
  designing, read your chosen movements' coaching notes with
  `HARMONICFITNESS_HOME=docs/eval/listeners/<listener> ./harmonicfitness movements --about <ids>`, as the
  skill does (the brief carries only the notes of a movement that touches a limit or works one side).

## Policy (keeps runs comparable)
- **Design it yourself.** Pick a format the brief lists (or a mix that keeps to its doses), the
  movements, their order, the doses within its ranges and the segment timing that suit this listener
  today. A case's `target` is the session's focus. Every movement comes from the brief's safe menu,
  warm-up and cool-down included; nothing from memory.
- Write `docs/eval/out/<id>.draft.txt`: first line `movements: <every movement you use, by its menu
  name, comma separated>`, then the `@@ <seconds> | <label>` segments, adding up to exactly the request
  (minutes times sixty). You choose the segments.
- Before the script, put the plan at the top of `docs/eval/out/<id>.writer-notes.md`: a short table
  (block, movements, dose, seconds) and the format's name, as the skill posts it. Then a short bullet
  list of every place the brief left you to invent something (a movement you wanted that wasn't on
  the menu, a dose the guide didn't settle, how to place the resting foot, a transition, timing), and
  anything that made the brief hard to use. If nothing, write "Nothing invented."
- The stories come from `docs/eval/research/<listener>.md` only, told as if true (it's invented for the
  grid), each wrapped in `[story]` ... `[/story]`, in the formats and the weaving `knowledge/script.md`
  describes (Keeping them engaged, and its worked examples), with one open thread brought back where it
  fits. Coach each movement fully the first time, then briefly, so the rests carry the stories. Don't
  invent facts beyond the sheet. In the writer notes, list the items told and any thread you'd open for
  next time.
- Health: speak the full safety rules (first-session length) from the brief's limits and clinician
  rules, and its limit cues wherever a movement or a transition touches a limit.
- Voice: write it the way the brief's coach would talk to this listener (`knowledge/script.md`,
  Keeping them engaged), follow the brief's Voice line for a local or web coach, and finish with the
  read-through rewrite.

## Script habits judges have marked down; avoid them
- Cue during the work; don't spend a short set on set calls. Say "rack it" only when a weight is in hand.
- On one-sided movements say "per side" (or "each leg"), and do both sides unless the menu lists the
  movement for one side only.
- Say the rest a segment actually holds, not a number it can't contain.
- Don't repeat filler lines word for word; vary praise.
- Timed work inside one segment: `[chime]` at each work start and stop, said too ("At the bell, go.
  [chime] Push."), and short holds between cues while they work (`[hold 5s]`; one bare `[hold]` takes
  the segment's spare time). No quiet runs past eight seconds, holds, pauses and breaks added up; the
  eval listeners have no pulse bed. Never use a hold to pad a story or a strength rest.
- Getting up and down costs time and, under a lower-leg limit, risk: group work done in one place.

## Lint (must pass for each script)
```sh
HARMONICFITNESS_HOME=docs/eval/listeners/<listener> ./harmonicfitness build docs/eval/out/<id>.draft.txt "eval-<id>" --lint-only --today 2026-10-21
```
The build name (`"eval-<id>"`) is required; without it a render starts. The lint checks the draft
against the brief's menu (`docs/eval/out/<id>.menu.json`): a movement declared or named that isn't on
it, or segments that don't add up, fail it. Fix every issue until it exits 0 (total within three percent
of plan); clear the menu warnings too. If a lint failure seems to be the harness's fault, say so in the
writer notes.

## Report back
For each case: the lint result (exit code, predicted total against plan), the format and movements you
chose, and the three most important points from your writer notes. Keep the report under 300 words.
