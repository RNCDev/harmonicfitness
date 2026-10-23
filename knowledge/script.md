# Writing the script

What goes into a workout script, from the welcome to the sign-off. How it should sound (the coach's two registers, the name, the arc, varied openings, friendly handoffs) is in `knowledge/tts-rules.md`, Coaching voice, along with the rules for text a voice reads well. The movements, their coaching notes, today's limits and the dose guidance come from `./sweatcast brief`.

## The draft

- It starts with one line, `movements: <every movement the script uses, by its name in the brief's menu, comma separated>`, which is never spoken. Then the `@@ <seconds> | <label>` segments, which add up to exactly the session's seconds. `./sweatcast build` checks both against the menu the brief saved, and stops when a movement isn't on it.
- You choose the segments. A segment can be one set, a pair, a round, an interval block or the whole warm-up; what matters is that the time each one holds is the time its work, rest and talk need. Long segments are fine for continuous work; short ones suit timed intervals, where each change gets a `[chime]`.
- Draft to about the measured words a minute times the seconds over sixty per segment. The lint predicts each segment's spoken length for the chosen voice, and only the total must land within three percent of plan; a segment with time to spare ends a little early, and one that runs long is paid back by the next ones. Don't polish segments that are close.
- Keep every paragraph under about twenty seconds spoken, about fifty words; the lint flags any over twenty-two. Long clips drift and glitch. Use `[pause]` for getting into position or breathing, three or four seconds at most.

## Timed work

- Inside one segment, mark each change of an interval (work starts, rest starts) with `[chime]`, and say it too: "At the bell, go. [chime] Push."
- Put `[hold]` where the listener works in silence: the segment keeps its full length and its spare time goes quiet there, so a short effort needs a few cues, not nonstop talk. Time the work with a fixed hold (`[hold 20s]`) and give the rest one bare `[hold]`. Never use a hold to pad a story or a long strength rest.
- Say the rest the segment actually holds, not a number it can't contain.
- The lint's table shows a held segment's spare seconds, which it spends in silence. More than about ten in a strength rest or a stretch sounds like a dropped earbud: fill it with coaching, or move the time to where the work is.

## Opening

- Greet the listener by the profile's `name` in the first line, warmly and briefly ("Hey Sam, good to have you back."), and say how today fits the week from the brief's Today in the week ("Second one this week.").
- In the morning, preview the day in a sentence or two from the weather `./sweatcast feeds` printed, and from the calendar if a calendar connector is available (just the shape of the day, such as "two meetings this morning and a free afternoon", never names, attendees or details). In the evening, recap it.
- Then the plan in a sentence or two, the safety rules, and time to set up.
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

## Filler: headlines, science, the deep dive, the quiz

- Filler comes only from the research sheet (which draws on the feeds sheet), the video sheet and the weather. Never invent scores, prices, quotes or events. Script around a gap with coaching.
- Use a few quick headlines, two current science and technology breakthroughs from the research sheet, and one deep-dive thread told across several segments. "Science" in a session means those breakthroughs; form cues stay cues, with no study facts behind them.
- Tell a deep-dive beat as two or three short paragraphs. Credit a video deep dive to its channel when it starts ("This one comes from Asianometry's latest video"), and paraphrase it rather than quoting. A series part opens with a two-sentence recap of the earlier parts, says which part it is ("Part two of three."), and ends with a one-line hook for the next ("Next time: Y two K.").
- One quiz beat a session: ask in one segment and answer two or three segments later. Use the research sheet's puzzle when it has one, credited by source ("A puzzle from the channel Mind Your Decisions.", "From Will Shortz's Sunday Puzzle on NPR."): state it in two or three short paragraphs, then give the answer and its one-line reason. Otherwise draw it from the session's own material.
- Stories live in the rests and the steady work, never in the middle of a cue the listener needs.

## Close

- Box breathing with a short cue and a `[pause]` for each four-second count (see tts-rules, Pacing).
- A recap that names what they did today specifically, one reason to come back (the next part of the story, the next step up), and a sign-off by name.
