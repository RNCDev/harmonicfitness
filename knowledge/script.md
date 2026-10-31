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
- **Nothing standing includes fetching the kit.** When a limit rules out standing, plan only with what's within reach of where they sit, or what the opening asks someone else to set out; never "pause me and get it", and never send them across the room on foot.
- **One side only, when the menu says so.** Otherwise both sides do the same work. When a movement is listed for one side only, say why the other side rests (training the healthy side still helps the injured one a little). The build checks the side words.
- **Adjustments never add load to a limited area.** A harder option stays off it, and under a limit the self-check asks about the area too ("Ankle quiet? Stay there. Anything above a three, switch to the easier version."). On low readiness, offer only holding steady or the easier option, and say that's the plan for today.
- **Only the weights on hand.** Name loads from the brief's Loads on hand ("the fifteens"), never one the kit doesn't have.
- **Their calendar, only its shape.** With a calendar connector, say only the shape of the day ("two meetings this morning and a free afternoon"), never names, attendees or details: a web coach's script goes to its voice service.
- **Never invent facts.** Scores, prices, quotes and events come only from the research sheets, the stock and the weather. A topic with nothing verified gives its time to another topic or to coaching.

## What the build checks

The `movements:` line, segments that add up to the session's seconds, a total within three percent of plan, no silence over eight seconds, paragraphs a voice can say in one go, and text a voice can read (`knowledge/tts-rules.md`). The draft format is in that file too.

## Getting the workout done

The listener has no screen, no mirror and no clock. The coach's voice is all of those.

- **Coach from the movement's notes** (`./harmonicfitness movements --about <ids>`, or the brief for one that touches a limit): the setup, what one rep is the first time it appears (and whether reps count per side), where they should feel it, and the main fault's fix as a mid-set check ("If the hips sag, squeeze and brace.").
- **Coach fully once, then trust them.** The first time a movement appears, give it everything: setup, the rep, the feel, the fault. After that a set needs its target, the count in, a cue or two and the finish ("Same as before, chest up, ten more."), not the whole lesson again. That leaves the rests and the easy work for the listener's world, which is what makes them press play next time. Safety lines never shrink: the limit cues, the self-check under a limit, and every cue the listener must catch.
- **Stay with them through the work.** Lead the first reps to set the tempo, then cue what matters (form, the breath, how far through, the last few). No quiet runs past eight seconds (twenty with the pulse bed, `bed = "pulse"` in their settings; the brief's Counts and Voice lines say which), so a long set still gets a word every few seconds, but it can be short.
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
- **The coach can't see them.** Never say what only eyes would know: "that set looked smoother", "best set yet", "your back stayed flat every rep", "not once", "that's where we want it", "a strong ride". What the plan guarantees is fine ("that's all eight efforts done", "fifteen minutes in the bank"); how well they did isn't known. Notice effort as a question or a plan instead ("How did that one feel? If the last two were a grind, stay at this weight."), or from what the log shows; they can't answer back, so never "you told me".
- **The rests carry their world.** The content plan names the topics due (what they like to stay current on and learn about), the formats to tell them in, and what was told in the last month, which stays untold. Tell about the plan's topic count: one story to a rest, and a longer rest gets a bigger story (more beats, the serial), not two or three stacked together. The spares are for a session that would otherwise run thin; leave the rest of the sheet untold (it isn't logged, so a good piece can go to the stock). A rest can also hold the coach's own chat, their progress from the log, the breath, or what's next. Each find is told at its size: a routine result is a quick hit; a big move or a great long read earns the big story, an explainer or the serial. Mix the formats so no two rests sound alike: a quick hit, then a this-or-that to chew on through a set, then a myth asked now and checked later. Open each item with why it's theirs (their team, their city, a show they loved), and tell it like a friend would, never like a news reader.
- **Time-proof it.** The listener may press play an hour later, or tomorrow. The brief says when it was written: give an event its day and time ("the Sixers host the Knicks tonight at seven thirty"), never "in half an hour" or "right now", and treat anything starting within about an hour of that as under way ("good luck to them tonight"), not a preview. The weather is "this evening's", not "right now".
- **Weave, don't insert.** The best rests reach back and forward: a quiz asked in one rest and answered two later, a memory list given in the warm-up and recalled in the cool-down, a serial that ends each beat on a hook, the coach's own take on the this-or-that. Tie a story to the work when it fits honestly (an athlete's training to today's movement, the physics of a swing), and bring in their progress from the log. Credit a video to its channel. A series part recaps the earlier parts. Log every researched item told (`./harmonicfitness content log`).
- **Wrap each story in `[story]` and `[/story]`.** The tags are never spoken. Inside them a story may name a movement that isn't on today's menu ("her deadlift record"), say left or right ("the other side of the river"), or count down ("ten, nine, eight, liftoff"), since the build reads past them; so a story never tells the listener to do anything, holds no `[hold]`, `[count]`, `[cue]` or `[chime]`, and closes in the segment it opens in. Coaching stays outside the tags.
- **Threads across sessions.** The content plan lists open threads from earlier sessions: a quiz to answer, a story to follow up, the coach's take (keep it the same), a promise ("next week we add weight"). Bring one back when it fits and close it. Leave one open for next time when it's worth it: a quiz answered next session is a reason to come back (`./harmonicfitness content thread`, after the build).
- **Stories wait for the rests and the easy work.** A hard set gets cues only.
- **A shape:** a welcome that knows them (the day, the weather, how today fits the week), a build, a named peak, an easing off, and a close that says what they did specifically and gives one reason to come back.
- **No sameness:** segments that all open alike, stock praise on repeat, and lines that sound like a checklist all read as a template. The build warns about any sentence said word for word in the last five workouts.

## Worked examples

Each is a segment as it would sit in a draft, for a local coach with recorded counts; a test lints every one, so they keep to the rules. Make them your own: they show the shape, not lines to reuse, and their facts are made up, where a script's come only from the research sheets.

A welcome that knows them, with the rules in the short form:

<!-- example -->
    @@ 60 | Welcome
    Morning, Sam. Grey and cool out there, about fifty degrees, so this is a good one to do inside with the window cracked.

    Third session this week, and the first with the new dumbbells, so today is upper body and a little core, about twenty-five minutes. Usual rules. The left knee stays out of deep bends, nothing jumps, and sharp pain means stop that movement.

    And keep this in your back pocket, because I'm asking at the end. Three words: lantern, pepper, harbor.

A strength rest that carries a story, then hands back to the work:

<!-- example -->
    @@ 75 | Rest after set two
    Set them down, and shake the arms out. That's two of three.

    [story] Your Flyers won last night, four to two in Boston, and the rookie scored the winner on a backhand in the third. It was his first goal at home this season, and the bench emptied onto the ice to mob him. [/story]

    [story] Here's the part I liked. He told reporters he'd been shooting backhands after practice every day for a month, a hundred a day, because the coaches said it was the one shot goalies don't read. [/story]

    A hundred a day. We're doing twelve. Pick the dumbbells back up when you're ready, same weight, and same tempo, slow on the way down.

A quiz asked in one rest and answered later, the coach's own take in between:

<!-- example -->
    @@ 45 | Rest after the first round
    Breathe it down, and here's one to chew on through the next round.

    [story] Which planet has a day longer than its year? It spins so slowly that the sun rises and sets less often than it goes round. Have a guess, and I'll tell you after the planks. [/story]

    Chime's coming, so find the floor and get set for the plank.

<!-- example -->
    @@ 40 | Rest after the planks
    Down onto the knees, and rest.

    [story] So, the planet. It's Venus. A day there lasts about two hundred and forty three Earth days, and its year only about two hundred and twenty five. My take, it's the strangest place in the solar system, and nobody can argue me out of it. [/story]

    One more round, then we ease off.

A close that says what they did, recalls the warm-up, and leaves one thread open:

<!-- example -->
    @@ 60 | Close
    That's the session, Sam. Three rounds, the first time with the fifteens on the floor press, and if that last set still had two in the tank, next time we go up to the twenties.

    Before you go, the three words from the start. Lantern, pepper, harbor. If you got all three while breathing that hard, that's a sharp head.

    Next time we'll add a set to the rows, and I'll have the end of that rookie's story, because he's up against his old team on Saturday. Good work today.

## Last: read it through and rewrite

Once every segment and story is in, read the whole draft top to bottom as the listener will hear it, then rewrite it as one piece:
- Threads that carry through: the puzzle answered, an earlier story called back, their self-check choice remembered, the close echoing the welcome.
- Handoffs that flow from one segment into the next.
- One coach's voice from start to finish.
- Fewer stiff short commands where a sentence would do (`knowledge/tts-rules.md`, Local and web voices).

Keep every safety line intact. When a build runs off plan, rewrite around the segments that are furthest off rather than trimming or padding words.
