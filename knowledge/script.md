# Writing the script

A script has two jobs: get the listener through today's workout so it does what it's for (the goal, the doses, good form), and keep them glad they pressed play. Safety is the only hard rule, along with what the build checks. Everything else is up to you: write it the way this coach would talk to this person.

The ingredients come from `./harmonicfitness brief`: the listener and their week, today's limits, the safe menu with each movement's coaching notes, the doses, and the coach with their character and pace. `./harmonicfitness content plan` says what the rests should carry. `knowledge/tts-rules.md` says what a voice can read.

## Safety: the rules

- **Only the menu.** Every movement, warm-up and cool-down included, comes from the brief's safe menu. Nothing from memory. The build stops on anything else.
- **The rules, said in the opening.** Use one of two lengths:
  - **Full:** a short paragraph per rule. Say each limit, then each clinician rule in the clinician's words and credited to them, then the stop rule (pain stays around two or three out of ten; sharp pain or new swelling means stop that movement). Use it when anything changed: the first session, a check-in answer other than "same as last time", a loosened or tightened limit, a new clinician rule, a new problem, or more than fourteen days since the last session.
  - **Short:** otherwise, one or two sentences that still name every rule ("Usual rules. The right knee stays out of deep bends, nothing jumps, and sharp pain means stop that movement."). It drops words, never a rule.
- **A clinician's rule beats the stop rule.** Where it says no pain, or no pushing through pain, in an area, the two-or-three-out-of-ten allowance never applies there, in the opening or in any check-in later ("Any neck pain at all, stop, that's your physio's rule").
- **Limit cues where they matter.** Say the brief's limit cues wherever a movement or a transition touches a limited area (head position, where the resting foot goes, getting down and up). The menu's "load on today's limits" says where. A movement that loads a limited area stays light.
- **A limit cue beats a movement's setup.** Where a setup asks for something a limit cue rules out (feet planted for drive, a wide stance), adapt the setup out loud or choose another movement.
- **Nothing standing includes fetching the kit.** When a limit rules out standing, have everything set out within reach during setup, and never send them across the room on foot.
- **One side only, when the menu says so.** Otherwise both sides do the same work. When a movement is listed for one side only, say why the other side rests (training the healthy side still helps the injured one a little). The build checks the side words.
- **Adjustments never add load to a limited area.** A harder option stays off it, and under a limit the self-check asks about the area too ("Ankle quiet? Stay there. Anything above a three, switch to the easier version."). On low readiness, offer only holding steady or the easier option, and say that's the plan for today.
- **Only the weights on hand.** Name loads from the brief's Loads on hand ("the fifteens"), never one the kit doesn't have.
- **Their calendar, only its shape.** With a calendar connector, say only the shape of the day ("two meetings this morning and a free afternoon"), never names, attendees or details: a web coach's script goes to its voice service.
- **Never invent facts.** Scores, prices, quotes and events come only from the research sheets, the reserve and the weather. A slot with nothing verified gives its time to coaching.

## What the build checks

The `movements:` line, segments that add up to the session's seconds, a total within three percent of plan, no silence over eight seconds, paragraphs a voice can say in one go, and text a voice can read (`knowledge/tts-rules.md`). The draft format is in that file too.

## Getting the workout done

The listener has no screen, no mirror and no clock. The coach's voice is all of those.

- **Coach from the brief's notes:** the setup, what one rep is the first time it appears (and whether reps count per side), where they should feel it, and the main fault's fix as a mid-set check ("If the hips sag, squeeze and brace.").
- **Stay with them through the work.** Lead the first reps to set the tempo, then keep cueing (form, the breath, how far through, the last few). Thirty seconds of quiet sounds like a dropped earbud.
- **Fit the set to its time.** Each movement's line gives its seconds a rep: twelve reps at three seconds is thirty-six seconds of work, per side where it counts per side. Say the rest a segment actually holds.
- **Tell them where they are.** The time, the round, what's next and what to pick up. Timed work gets `[chime]` at each change and a `[count]` into the work.
- **Give them a target and a way to adjust.** A main set has a target ("Ten reps, two left in the tank"). After the first working set, ask how it felt and give an if-then from the brief's harder and easier options, preferring changes that don't lengthen the set. When they're unsure, lean to the harder option (programming.md, Readiness). Later rounds call back to their choice.
- **Mind the floor.** Getting down, up and between places takes time and, under a lower-leg limit, care. Group work done in one place, and give each move its seconds out loud.

For example, twelve single-leg bridges at three seconds a rep, about thirty-six seconds of work, for a local coach:

    Twelve on the right, and you should have two left at the end. [count 3 go]
    Lift through the heel, squeeze at the top, and lower slow. [hold 2s]
    Again, up, squeeze, and down. [hold 3s]
    Keep the hips level, like a tray of water. [hold 5s]
    Left foot stays soft on the mat. [hold 5s]
    About halfway now, breathe out as you lift. [hold 5s]
    Keep that squeeze honest at the top. [hold 4s]
    Last few, and slow on the way down. [hold 4s]
    Last one, all the way up, and rest.

## Keeping them engaged

This is one coach with one person they know, not a fitness app reading a list.

- **The coach's character** from the brief: how they talk, their humor, what encouragement works for this listener. Use the listener's name a few times, not every paragraph. Bring in their week and their last feedback.
- **The rests carry their world.** The content plan says what's due (today, science, deep dive, quiz, delight, learn) and what was told in the last month, which stays untold. Its counts are the least, not the most: spare time goes to more of their content, never to silence. Open each item with why it's theirs (their team, their city, a show they loved), and tell it like a friend would. Ask the quiz early and answer it later. Credit a video to its channel. A series part recaps the earlier parts and ends on a hook. Log every item told (`./harmonicfitness content log`).
- **Stories wait for the rests and the easy work.** A hard set gets cues only.
- **A shape:** a welcome that knows them (the day, the weather, how today fits the week), a build, a named peak, an easing off, and a close that says what they did specifically and gives one reason to come back.
- **No sameness:** segments that all open alike, stock praise on repeat, and lines that sound like a checklist all read as a template.

## Last: read it through and rewrite

Once every segment and story is in, read the whole draft top to bottom as the listener will hear it, then rewrite it as one piece:
- Threads that carry through: the puzzle answered, an earlier story called back, their self-check choice remembered, the close echoing the welcome.
- Handoffs that flow from one segment into the next.
- One coach's voice from start to finish.
- Fewer stiff short commands where a sentence would do (`knowledge/tts-rules.md`, Local and web voices).

Keep every safety line intact. When a build runs off plan, rewrite around the segments that are furthest off rather than trimming or padding words.
