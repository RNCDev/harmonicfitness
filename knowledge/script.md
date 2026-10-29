# Writing the script

What goes into a workout script, from the welcome to the sign-off. How it should sound (the coach's two registers, the name, the arc, varied openings, friendly handoffs) is in `knowledge/tts-rules.md`, Coaching voice, along with the rules for text a voice reads well. The movements, their coaching notes, today's limits and the dose guidance come from `./harmonicfitness brief`.

## The draft

- It starts with one line, `movements: <every movement the script uses, by its name in the brief's menu, comma separated>`, which is never spoken. Then the `@@ <seconds> | <label>` segments, which add up to exactly the session's seconds. `./harmonicfitness build` checks both against the menu the brief saved, and stops when a movement isn't on it.
- You choose the segments. A segment can be one set, a pair, a round, an interval block or the whole warm-up; what matters is that the time each one holds is the time its work, rest and talk need. Long segments are fine for continuous work; short ones suit timed intervals, where each change gets a `[chime]`.
- Draft to about the measured words a minute times the seconds over sixty per segment. The lint predicts each segment's spoken length for the chosen coach, and only the total must land within three percent of plan; a segment with time to spare ends a little early, and one that runs long is paid back by the next ones. Don't polish segments that are close.
- Paragraph length and `[pause]`: `knowledge/tts-rules.md`, Pacing and pauses.

## Timed work

- Inside one segment, mark each change of an interval (work starts, rest starts) with `[chime]`, and say it too: "At the bell, go. [chime] Push."
- Count into the work with the coach's recorded counts when the brief's Counts line says it has them: "Pick up the dumbbells. [count 3 go] [chime] Push." (`knowledge/tts-rules.md`, Pacing).
- **The coach stays with them through every set.** A listener with no screen hears a long silence as a dropped earbud, and a set of "go", thirty seconds of nothing, then "rest" as no coach at all. The lint refuses any silence over eight seconds, anywhere. Coach the set as a string of short cues with short holds between: lead the first two or three reps to set the tempo ("Lift. Squeeze at the top. And lower."), then a cue every five to eight seconds (a form check from the notes, the breath, a limit cue, about how far through they are, "last few"), then count them out. A timed hold (a plank, a hollow hold, a stretch) is the same: the breath, what to keep, the seconds left.
- **Size the set from the brief.** Each movement's line gives its seconds a rep: twelve reps at three seconds is thirty-six seconds of work, per side when it counts per side. The cues and holds between "go" and "rest" add up to that, never fewer seconds than the reps need ("Twelve reps" in twenty seconds leaves them mid-set at "rest").
- `[hold 5s]` is exactly that much silence; a bare `[hold]` takes the segment's spare time and keeps it its full length. Use a bare hold, if at all, where a few spare seconds do no harm (the end of a rest): the lint counts its share against the eight seconds. A segment without a bare hold ends early when its words run out, so the total comes up short until the coaching and the listener's content fill it (Filler, below: the plan's counts are the least, not the most). Never use a hold to pad a story or a long strength rest.
- **Every rest opens with the person, then the story.** A word on the set they just did, or a check-in by feel ("How was the ankle on that one?", "That last round was honest."), before any filler; the filler is told to them, not read at them (`knowledge/tts-rules.md`, Coaching voice).
- Say the rest the segment actually holds, not a number it can't contain.

A coached set, for twelve single-leg bridges at three seconds a rep (about thirty-six seconds of work):

    Twelve on the right. You should have two left at the end. [count 3 go]
    Lift through the heel. Squeeze at the top. And lower slow. [hold 2s]
    Again. Up, squeeze, and down. [hold 3s]
    Hips level, like a tray of water. [hold 5s]
    Left foot stays soft on the mat. [hold 5s]
    About halfway. Breathe out as you lift. [hold 5s]
    Keep that squeeze honest at the top. [hold 4s]
    Last few. Slow on the way down. [hold 4s]
    Last one, all the way up. And rest.

## Opening

- Greet the listener by name in the first line (how often to use it: `knowledge/tts-rules.md`, The name), and say how today fits the week from the brief's Today in the week ("Second one this week.").
- The coach rarely says their own name: once in a first session with a new coach ("I'm Maya, and I'll be with you today."), otherwise not at all. How they talk comes from the brief's coach lines (their `persona.md`), which can differ from coach to coach.
- In the morning, preview the day in a sentence or two from the feeds sheet's weather, and from the calendar if a calendar connector is available (just the shape of the day, such as "two meetings this morning and a free afternoon", never names, attendees or details). In the evening, recap it.
- Then the plan in a sentence or two (with any change readiness made: "You're short on sleep, so same weights, one round fewer."), the safety rules, and time to set up.
- The safety rules come in one of two lengths:
  - **Full**, a short paragraph per rule: each limit, each clinician rule in the clinician's words and attributed to them, then the stop rule (pain stays around two or three out of ten; sharp pain or new swelling means stop that movement). Use it when anything changed: the first session, a check-in answer other than "same as last time", a loosened or tightened limit, a new clinician rule, a new problem, or more than fourteen days since the last session.
  - **Short**, otherwise: one or two sentences that still name every rule ("Usual rules. The right knee stays out of deep bends, nothing jumps, and sharp pain means stop that movement."). The short version drops words, never a rule.
- A clinician's rule beats the general stop rule. Where it says no pain, or no pushing through pain, in an area, the two-or-three-out-of-ten allowance never applies there, in the opening or in any check-in later ("Any neck pain at all, stop, that's your physio's rule").
- Keep the opening tight in a short warm-up, so the warm-up still warms up.

## Coaching each movement

- Coach from the movement's notes in the brief, not from memory: the setup and cues as given or lightly reworded, what one rep is the first time it appears (and whether reps count per side), one "you should feel it in..." check, and the most important fault's fix as a mid-set check-in ("If the hips sag, squeeze and brace.").
- The listener has no screen and no mirror; these lines are how they know they're doing it right.
- Under a limit, say the brief's limit cues wherever a movement or a transition touches it (head position, where the resting foot goes, getting down and up), as short cues of their own. The menu's "load on today's limits" says where they're needed, and a movement with a load there stays light.
- Where a movement's setup asks for something a limit cue rules out (feet planted for drive, a wide stance, the tops of the feet on the floor), the limit cue wins: adapt the setup out loud, or choose another movement from the menu.
- When a limit rules out standing, fetching the kit counts. Ask for everything the session uses to be set out within reach in the setup time, and never send the listener across the room on foot.
- Both sides, both limbs, the same work, unless a movement is listed for one side only; then the audio says why the other side rests, and that training the healthy side still helps the injured one a little.
- Name the load from the brief's Loads on hand ("the fifteens"), never a weight the kit doesn't have, and say what changed since last time ("Same fifteens as Tuesday, but three seconds down").
- Getting to and from the floor, a bench or a machine takes time. Group work done in one place, and give each move between places its seconds, out loud.

## Adjusting as you go

A coach in the room watches the last two reps and changes the next set. The listener has no coach watching, so the script asks them to judge, and tells them what to do with the answer.
- **A target for every main set**: reps and how much should be left. "Ten reps. You should have two left at the end."
- **A self-check after the first working set** of each main movement, not every set, at the start of its rest: one question by feel, then an if-then for the sets after it. "How many more could you have done? Three or more, next set goes three seconds down. If the last two were a fight, stay right where you are." On light weights people usually have more left than they think (programming.md, Readiness), so when the listener is unsure, the cue leans to the harder option.
- **The options come from the brief**: the movement's harder and easier versions in its notes, and the progression order (a slower lowering, a pause, one arm or one leg, then the next dumbbell). Name the exact weight from Loads on hand, and only one set out within reach.
- **The options fit the time the set has.** Prefer changes that don't lengthen the set (a heavier dumbbell, a slower lowering with a rep or two fewer, a pause in place of two reps), so the hold that follows stays right for both choices.
- **Under a limit, the check includes the area.** "Ankle quiet? Stay there. Anything above a three, switch to the easier version." A harder option never adds load to a limited area, and a clinician's no-pain rule stays absolute.
- **On low readiness**, offer only holding steady or the easier option, and say that's the plan for today.
- Later rounds call back to the choice rather than asking again ("Same as you picked last round."), and the close names it ("If you moved up today, tell me it felt easy at the next check-in, and we start from there.").

## Filler: the plan, the deep dive, the quiz

- `./harmonicfitness content plan --minutes <N>` says what the rests carry: how many items of each slot (today, science, deep dive, quiz, delight, learn) and the category due for each. Tell those, from the research sheet, the video sheet and the reserve; a slot with nothing verified gives its time to coaching. Never tell an item the plan lists as told in the last month; a follow-up says what's new ("They're three and one since that opener").
- Filler comes only from those sheets and the weather. Never invent scores, prices, quotes or events.
- Open each item with its hook, the line that ties it to the listener (their team, their city, a show they loved), then tell it plainly. A recommendation names why they'd like it ("It has the same slow-burn dread as the last show you loved"), and never one they've rated three or less. "Science" in a session means the plan's science items; form cues stay cues, with no study facts behind them.
- Tell a deep-dive beat as two or three short paragraphs. Credit a video deep dive to its channel when it starts ("This one comes from Asianometry's latest video"), and paraphrase it rather than quoting. A series part opens with a two-sentence recap of the earlier parts, says which part it is ("Part two of three."), and ends with a one-line hook for the next ("Next time: Y two K.").
- One quiz beat a session: ask in one rest and answer two or three later, credited by source ("A puzzle from the channel Mind Your Decisions.", "From Will Shortz's Sunday Puzzle on NPR."): the question in two or three short paragraphs, then the answer and its one-line reason.
- **The plan's counts are the least a session carries, never the most.** Time left once the coaching is written goes to more of the listener's own content, never to silence: a longer deep-dive beat (the research gathers five minutes or more), the research sheet's spare items, or more pieces from the reserve (delight, learn). Still one quiz a session, and nothing told in the last month. Log every extra told like any other item.
- Stories live in the rests and the steady work, never in the middle of a cue the listener needs. Easy, steady work (the warm-up's mobility, a stretch, the cool-down, a long easy hold) can carry a story alongside it: set the position first, then tell it, with a form or breath cue between its paragraphs. A hard set keeps to its cues; the story waits for the rest.
- After the build, every item told goes on the record (`./harmonicfitness content log`), so the next session moves on.

## Close

- Box breathing, cued as `knowledge/tts-rules.md`, Pacing and pauses, shows.
- A recap that names what they did today specifically, one reason to come back (the next part of the story, the next step up), and the sign-off.
