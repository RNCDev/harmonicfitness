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
- `knowledge/script.md` (what goes in a script) and `knowledge/tts-rules.md` (how it sounds, and what
  a voice can read: no digits, no symbols except the `[pause 3s]`, `[chime]` and `[hold]` markers).
- For each case: the listener folder `docs/eval/listeners/<listener>/` (profile.md, health.md, log.md)
  and the brief `docs/eval/out/<id>.brief.md`, which holds everything else: the listener, the week, the
  limits and their cues, the safe menu with each movement's coaching notes, the programming guide and
  the equipment notes. Design from it, not from memory.

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
- No research, no feeds: where `knowledge/script.md` calls for topic beats (headlines, science, deep
  dive, quiz), write a single one-line placeholder paragraph such as `Topic beat: a short science story
  goes here.` Keep placeholders to a small share of the time; fill most of it with coaching. Don't
  invent scores, quotes or events.
- Health: speak the full safety rules (first-session length) from the brief's limits and clinician
  rules, and its limit cues wherever a movement or a transition touches a limit.
- Voice: follow `knowledge/tts-rules.md`, Coaching voice, in full: greet the listener by the name in
  the brief, two to four times in all; talk like a person around the work; use the brief's Today in the
  week for one or two continuity lines (a first session gets a first-session welcome); vary the segment
  openings; hand off to topic placeholders the way a person would; close specifically and personally.

## Script habits judges have marked down; avoid them
- Cue during the work; don't spend a short set on set calls. Say "rack it" only when a weight is in hand.
- On one-sided movements say "per side" (or "each leg"), and do both sides unless the menu lists the
  movement for one side only.
- Say the rest a segment actually holds, not a number it can't contain.
- Don't repeat filler lines word for word; vary praise.
- Timed work inside one segment: `[chime]` at each work start and stop, said too ("At the bell, go.
  [chime] Push."), and `[hold]` where the listener works or recovers in silence (`[hold 20s]` times
  the work; one bare `[hold]` takes the rest). Never use a hold to pad a story or a strength rest.
- Getting up and down costs time and, under a lower-leg limit, risk: group work done in one place.

## Lint (must pass for each script)
```sh
HARMONICFITNESS_HOME=docs/eval/listeners/<listener> ./harmonicfitness build docs/eval/out/<id>.draft.txt "eval-<id>" --lint-only
```
The build name (`"eval-<id>"`) is required; without it a render starts. The lint checks the draft
against the brief's menu (`docs/eval/out/<id>.menu.json`): a movement declared or named that isn't on
it, or segments that don't add up, fail it. Fix every issue until it exits 0 (total within three percent
of plan); clear the menu warnings too. If a lint failure seems to be the harness's fault, say so in the
writer notes.

## Report back
For each case: the lint result (exit code, predicted total against plan), the format and movements you
chose, and the three most important points from your writer notes. Keep the report under 300 words.
