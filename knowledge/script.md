# Writing the script

A script has two jobs: get the listener through today's workout so it does what it's for (the goal, the doses, good form), and keep them glad they pressed play. Safety is the only hard rule, along with what the build checks. Everything else is up to you: write it the way this coach would talk to this person.

The ingredients come from `./harmonicfitness brief`: the listener and their week, today's limits, the safe menu with each movement's coaching notes, the doses, and the coach with their character and pace. `./harmonicfitness content plan` says what the session carries besides the coaching, and how its pieces sit together. `knowledge/tts-rules.md` says what a voice can read.

## Safety: the rules

- **Only the menu.** Every movement, warm-up and cool-down included, comes from the brief's safe menu. Nothing from memory. The build stops on anything else.
- **The rules, said in the opening.** Use one of two lengths:
  - **Full:** a sentence per rule, each said once. Each limit's opening line from the brief (your words if you like, every part kept), then each clinician rule in the clinician's words and credited to them, then the stop rule (pain stays around two or three out of ten; sharp pain or new swelling means stop that movement; numbness, tingling, dizziness or a joint giving way means stop for today) and the heart rule (chest pain or pressure, feeling faint, or a racing or pounding heart means stop the whole session and get help), with the signs a limit's "Heart rule, add" line gives (a neck's sudden headache), in the short rules too. Say each thing once: a limit line or cue that says what a clinician rule says is folded into it, two limits on one side can share a sentence, and a stop sign the stop rule already names isn't said twice. Use it when anything changed: the first session, a check-in answer other than "same as last time", a loosened or tightened limit, a new clinician rule, a new problem, or fourteen days or more since the last session. In a session of fifteen minutes or less the rules may run on into the warm-up, said over easy movement, so the welcome still has room to know them; each limit's opening line stays in the welcome, where the build looks for it.
  - **Short:** otherwise, one or two sentences that still name every rule ("Usual rules. The right knee stays out of deep bends, nothing jumps, sharp pain means stop that movement, and chest pain or feeling faint means stop altogether and get help."). It drops words, never a rule.
- **Made by AI, said in every opening.** One plain sentence near the rules, in the coach's voice and never apologetic: the session was written by AI, not by a certified trainer or a clinician, so the listener's own judgment and their clinician's advice come first ("This session was put together by AI, not a certified trainer or a clinician, so your body and your doctor have the final say.").
- **One sign, one action, every time.** A limit's "Stop that movement on" signs end that movement for today, at any score out of ten, and the session goes on without it; they're never answered with an easier version. Its "Stop for today on" signs end the session, as numbness or a joint giving way does. The usual two or three out of ten still holds in a limited area unless a line is stricter. Where a clinician says no pain, or no pushing through pain, or the brief's lines allow none there (an area off limits), say the split once: that area, no pain; anywhere else, the usual two or three. Without such a line there's no split to say, so never "anywhere else": the usual two or three holds in the limited area too, alongside its stop signs. Where the line is "no worse" (an elbow, a rib, a low back off limits), say that instead: that area no worse than when you started. Whatever a sign means in the opening, it means in every check-in after.
- **The limit lines are for different jobs.** In the brief, each limit's opening line is spoken in the opening; its "Today" line is for you, how to plan and set up the work; its stop signs are said again at the first set that loads the area (for an area off limits, the first working set); its "Say" line is a reason to give, only when its condition fits the plan, and after the limit it explains has been said, best at the work it explains (two limits' reasons that say the same thing are said once). The limit cues are spoken word for word the first time in a movement, the part that fits the position when a cue covers several; a later reminder may be a short form of it ("breathe out", "that hand stays out of it").
- **Limit cues where they matter.** Say the brief's limit cues wherever a movement or a transition touches a limited area (head position, where the resting foot goes, getting down and up): each one that fits the movement at its first set (a twist cue where there's a twist, a floor cue where the floor comes in), then the one that matters most at each later set. The menu's "load on today's limits" says where; an area off limits has none, so its cues go at the transitions and at the first set of each movement where the area could come into it (a hand that might reach for the floor or a knee), not at a march or a seated breath. A movement that loads a limited area stays light.
- **A limit cue beats a movement's setup.** Where a setup asks for something a limit cue rules out (feet planted for drive, a wide stance), adapt the setup out loud or choose another movement.
- **Nothing standing includes fetching the kit.** When a limit rules out standing, plan only with what's within reach of where they sit, or what the opening asks someone else to set out; never "pause me and get it", and never send them across the room on foot.
- **One side only, when the menu says so.** Otherwise both sides do the same work. When a movement is listed for one side only, say why the other side rests (training the healthy side still helps the injured one a little), in the segment before the set: in a segment that names the movement, the build refuses any word for the other side or for both ("each side", "switch", "the other leg", "ten a side", "the sore arm"), outside the brief's limit cues, its stop signs said as the brief gives them ("Stop that movement on any pain in the right shoulder.") and the stories.
- **Adjustments never add load to a limited area.** A harder option stays off it, and under a limit the self-check asks about the area too ("Ankle quiet? Stay there. Anything above a three, take the easier version. A sharp twinge, and that one's done for today."). Where nothing in the plan loads the area, the check just asks that it's still quiet. On low readiness, offer only holding steady or the easier option, and say that's the plan for today.
- **Only the weights on hand, and say which.** Name the load at each loaded movement's first set from the brief's Loads on hand ("the fifteens", "set the bell to thirty-five"), never one the kit doesn't have, and never "your dumbbells" alone: a listener with no screen needs the number. When the brief says no weights are listed, name the load by effort instead ("one you could press about fifteen times").
<!-- web: skip -->
- **Their calendar, only its shape.** With a calendar connector, say only the shape of the day ("two meetings this morning and a free afternoon"), never names, attendees or details: a web coach's script goes to its voice service.
<!-- web: end -->
- **Never invent facts.** Scores, prices, quotes and events come only from the research sheets, the stock, the weather and pages a search returned. A topic with nothing verified gives its time to another topic or to coaching. When a segment runs short, lengthen its coaching or ask the listener a question; never pad a story with details (a relative, a degree, a moment, a quote, play-by-play, someone's praise) the source didn't give. A story whose source has a number keeps at least one, and a rest tells only the plan's topics (or a format that needs none), never a story from outside them.

## Getting the workout done

The listener has no screen, no mirror and no clock. The coach's voice is all of those.

- **Coach from the movement's notes** (`./harmonicfitness movements --about <ids>`): the setup, what one rep is the first time it appears (and whether reps count per side), where they should feel it, and the main fault's fix as a mid-set check ("If the hips sag, squeeze and brace.").
- **Set it up, then keep them company.** The instructions come before the go: the movement, its one or two form points, the target, what to watch for. The first time a movement appears, that's the lesson (setup, the rep, the feel, the fault), as much of it as the brief's Level line says to explain; after that, the target and the one point that matters ("Same as before, chest up, a minute at a pace you could hold."). After the go, one cue in the first seconds sets the tempo. Then steady timed work is where the coach talks with them: a story, the serial's next beat, inside the move (the content plan's In the work), broken by the time checks ("halfway", "last ten seconds") and one form reminder where tiredness bites, usually near the end. Nobody needs a form cue every few seconds, and constant cueing is what makes audio coaching sound like a drill. Safety lines never shrink: the self-check under a limit, every cue the listener must catch, and the limit cues, as the safety rules set out for limit cues (where a limit cue is itself a form cue, such as the breath, it replaces the movement's own).
- **Hard work and counted sets keep the coach's whole attention.** A hard effort (an all-out interval, a heavy set's last reps, the named peak) gets short cues and encouragement, nothing to follow. A counted set gets cues only: a listener counting reps can't follow a story too. Where the session should carry talk, plan timed work (the brief lists timed methods), and keep counted sets for the heavy strength work.
- **Stay with them through the work.** No quiet runs past eight seconds (twenty with the pulse bed, `bed = "pulse"` in their settings), so a set always has a voice in it: the talk in steady work, short cues in a counted set or a hard effort. A timed set keeps its full time with a bare `[hold]` before its last cue, so a piece that runs short leaves a moment of quiet, not an early end.
- **Fit the set to its time.** Each movement's line gives its seconds a rep, already at the pace listeners really move: twelve reps at two and a quarter seconds is twenty-seven seconds of work, per side where it counts per side. Don't stretch a set past it; a listener who finishes first and waits in silence hears a coach behind them. Say the rest a segment actually holds.
- **Paced breathing gets its time.** A breath counted in ("in for four, out for six") is followed by a hold at least as long as the count, so the voice never talks over the breath; give the in-breath and the out-breath each their own hold, so no silence runs past the limit; and a number of cycles said is a number scripted.
- **Tell them where they are.** The time, the round, what's next and what to pick up. Timed work gets `[chime]` at each change and a `[count]` into the work.
- **Give them a target and a way to adjust.** A main set has a target ("Ten reps, two left in the tank"). After the first working set, ask how it felt and give an if-then with both the harder and the easier option from the brief (only the easier one where a limit touches the movement), preferring changes that don't lengthen the set. When they're unsure, lean to the harder option (programming.md, Readiness), except where a limit or a clinician's rule touches the movement: there, unsure means holding steady. Later rounds call back to their choice.
- **Mind the floor.** Getting down, up and between places takes time and, under a lower-leg limit, care. Group work done in one place, and give each move its seconds out loud.

For example, twelve single-leg bridges at two and a quarter seconds a rep, about half a minute of work with the count in, for a local coach:

    Twelve on the right, and you should have two left at the end. [count 3 go] [reps 12]
    Lift through the heel, squeeze at the top, and lower. [hold 2s]
    Keep the hips level, like a tray of water. [hold 3s]
    About halfway now, breathe out as you lift. [hold 3s]
    Last few, and slow on the way down. [hold 3s]
    Last one, all the way up, and rest.

## Keeping them engaged

One coach with one person they know: a good podcast host who happens to be coaching, not an app reading a list.

- **The coach's voice.** Talk the way the brief's character talks: contractions, plain words, their humor, the listener's name now and then, their week and last feedback. Praise effort and the plan, never what only eyes would know ("that looked smoother", "best set yet", "great control"): the coach can't see them, so ask how it felt, or plan from the log. End a story on its point, not a stock tag line ("always good to keep an eye on that").
- **Tell it the way a friend would.** Why it's theirs (their team, their city, a show they loved), what happened, the one detail or number that makes it land, and the coach's own reaction or what it means for them. The content plan's formats say how each kind is told and what it ends on, and its How they sit together how they mix: never name a format or announce a segment ("on this day", "news from the ice"), never two news items in a row, and a link from one piece to the next when it's true. Anything it lists as told stays untold. A moment with nothing worth telling gets the coach's own chat, their progress, the breath or what's next, never padding.
- **Their taste counts as much as the news:** an upcoming show at their venues or near them (who, where, which night, from the listing; never a price or "sold out" not seen there), a recommendation from their Taste, a callback to something they enjoyed.
- **Where stories go.** Steady timed work and the easy work (the warm-up, the cool-down, a walk between stations) carry the longer listening: easy to follow while moving, a story's beat rather than a quiz or a run of numbers. A rest is for recovering first (the breath, how that felt, what's next), then a piece told whole: a story's next beat, a quiz asked or answered, a myth checked, a quick hit; after a hard set, keep it short. Its word budget is its time, not a quota of talk: a breath given its own `[pause 3s]` counts toward it. Never in a hard effort, a counted set or its last reps, or in place of a safety line. Wrap each story in `[story]` and `[/story]`: never spoken, and the build reads past them, so a story may name a movement off the menu or say left or right, but it never tells the listener to do anything, never names an off-menu movement in a sentence that speaks to them ("you", "your", "let's": the build refuses that), holds no marker but `[pause]` (`knowledge/tts-rules.md`, Markers), and closes in the segment it opens in. A segment's stories say at most four figures (a number with hundred, thousand, million or percent, or in digits): the build refuses more, since the ear can't hold them.
- **Time-proof it.** The listener may press play an hour later. The brief says when it was written: give an event its day and time ("the Sixers host the Knicks tonight at seven thirty"), never "right now" or "in half an hour"; the weather is "this afternoon's".
- **Weave threads.** A quiz asked in one rest and answered two later, an open thread from the plan brought back and closed, one left open for next time when it's worth it (`./harmonicfitness content thread`, after the build), the close echoing the welcome.
<!-- web: skip -->
Log every researched item told (`./harmonicfitness content log`).
<!-- web: end -->
- **A shape:** a welcome under a minute that knows them (the day, the weather, how today fits the week), a build, a named peak, an easing off, and a close that says what they did, gives one reason to come back, and asks in a sentence how hard it felt.

## Worked examples

Each is a segment as it would sit in a draft, for a local coach with recorded counts; a test lints every one, so they keep to the rules. Make them your own: they show the shape, not lines to reuse, and their facts are made up, where a script's come only from the research sheets.

A welcome that knows them, with the rules in the short form:

<!-- example -->
    @@ 60 | Welcome
    Morning, Sam. Grey and cool out there, about fifty degrees, so this is a good one to do inside with the window cracked.

    Third session this week, and the first with the new dumbbells, so today is upper body and a little core, about twenty-five minutes.

    Usual rules. The left knee stays out of deep bends, nothing jumps, sharp pain means stop that movement, and chest pain or feeling faint means stop altogether and get help. Made by AI, as always, not a certified trainer or a clinician, so your body and your doctor have the final say.

    And keep this in your back pocket, because I'm asking at the end. Three words: lantern, pepper, harbor.

A strength rest that carries a story, then hands back to the work:

<!-- example -->
    @@ 75 | Rest after set two
    Set them down, and shake the arms out. That's two of three.

    [story] Your Flyers won last night, four to two in Boston, and the rookie scored the winner on a backhand in the third. It was his first goal at home this season, and the bench emptied onto the ice to mob him. [/story]

    [story] Here's the part I liked. He told reporters he'd been shooting backhands after practice every day for a month, a hundred a day, because the coaches said it was the one shot goalies don't read. [/story]

    A hundred a day. We're doing twelve. Pick the dumbbells back up when you're ready, same weight, and same tempo, slow on the way down.

A timed set set up before the go, then carrying a story between its time checks:

<!-- example -->
    @@ 55 | Round two, goblet squat, forty-five seconds
    Goblet squat for forty-five seconds, at a pace you could hold the whole way. Same fifteen, held tight to the chest, and sit between the heels. [count 3 go]
    Smooth and steady, and drive up through the whole foot.

    [story] While you find your rhythm, the Flyers. That rookie from last week scored again last night, his third in four games, and this one came on the power play. [/story]

    [story] What I like is how. The coaches moved him onto the second unit on Tuesday, and he scored on his first shift there. Sometimes a player just needs the puck more. [/story]

    Halfway. Chest proud, and keep breathing.

    [story] They're home against Boston on Saturday, the team that beat them twice already this year, and the coach says the kid stays on that unit. So that's the one to watch. [/story]

    [hold]
    Last ten seconds, slow and controlled on the way down. [cue rest]

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

<!-- web: skip -->
## Last: read it through and rewrite

Once every segment and story is in, read the whole draft top to bottom as the listener will hear it, then rewrite it as one piece:
- Threads that carry through: the puzzle answered, an earlier story called back, their self-check choice remembered, the close echoing the welcome.
- Handoffs that flow from one segment into the next.
- One coach's voice from start to finish.
- Fewer stiff short commands where a sentence would do (`knowledge/tts-rules.md`, Local and web voices).

Keep every safety line intact. When a build runs off plan, rewrite around the segments that are furthest off rather than trimming or padding words.
<!-- web: end -->
