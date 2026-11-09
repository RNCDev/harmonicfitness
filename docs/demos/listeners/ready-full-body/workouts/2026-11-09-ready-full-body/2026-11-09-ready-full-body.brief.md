# Today's brief: general, 30 minutes, the home kit
2026-11-09, Monday. Ingredients, not a plan: design the session from these (method, movements, order, doses, timing), post the plan, then write it.

## The listener
- No name in the profile: no name in the audio.
- Level: novice, in their words "I'm new to this, or it's been a long while." How much to explain: walk them through every setup, step by step in plain words, and say what any gym term means; the safety lines, the limit cues and the self-check under a limit are said in full whatever the level.
- Coach: Coach Bea (Mid-50s, community fitness teacher. ElevenLabs's stock voice Matilda: knowledgeable, warm, American. Patient and good-humoured.)
- Tone: Patient and warm, the teacher you'd send a nervous friend to; plain words, never talks down, and a born storyteller
- Encouragement: Notices the small wins out loud and makes starting out sound normal
  In this coach's own words, but never as if they watched: praise turns on what the listener can feel or the plan guarantees ("if the last two felt clean, that's the standard", "three sets in the bank"). This voice is what makes the session theirs: every coaching line should sound like this coach, not any trainer.
- Cueing: Sets each movement up step by step before the go: feet, hands, then the move
- Never says: Easy, right?; No excuses; Crush it
- Sign off: Warm and proud; tells them what they did today in one line
- Usual length: thirty minutes
- Time of day: any.
- Preferred format: mix it up.
- Intensity: moderate, about six out of ten, with a harder option said for each movement.

## Today in the week
- No sessions logged yet: this is the first one, so welcome them to it.

## Today's limits
- No limits today.

Clinician rules (say them in the clinician's words, attributed to the clinician; follow them literally, and where one is stricter than the general stop rule, such as no pushing through pain, it wins for that area every time it comes up; the menu applies only Avoid: lines, so leave out yourself what a rule forbids, such as a movement flagged overhead under no overhead work):
- None given.

Also left out of the menu today (by Avoid: lines, the request or the limits; not words to quote): impact.

Red flags, for the check-in, in chat (they stop the session before it starts, and suggest a clinician soon; the audio carries the opening's stop rule and heart rule instead): can't bear weight; rapidly increasing swelling; numbness or tingling; a joint that gives way or locks; pain that keeps getting worse after a week or two; dizziness that doesn't settle with rest; breathlessness that's suddenly getting worse; throbbing pain or swelling in one calf or thigh, with red, darkened or warm skin.
Emergencies, for the check-in, in chat (stop, and call emergency services now): chest pain, pressure or tightness, maybe spreading to the arm, neck or jaw; fainting or nearly fainting during exercise; a racing or irregular heartbeat with chest pain, breathlessness or feeling faint; leg pain or swelling with breathlessness or chest pain.

## Safe menu
Every movement in the script comes from this list, warm-up and cool-down included: 70 today (229 left out: equipment 187, level 34, avoided 12, rehab 4). Nothing from memory. `./harmonicfitness build` checks the draft's `movements:` line and its text against it.
Coaching notes: after designing, run `./harmonicfitness movements --about <the ids you chose, comma separated>` and coach from them.

### squat
- **air squat** (`air-squat`): standing; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; quads, glutes, adductors, core.
  Easier: box squat
- **box squat** (`box-squat`): standing; bench or chair or box; 2.25 s a rep, 10 s to set up; strength, novice; quads, glutes, adductors.
  Harder: air squat
- **wall sit** (`wall-sit`): standing; bodyweight; timed, 30 s a hold, 10 s to set up; strength, novice; quads, glutes.

### hinge
- **glute bridge** (`glute-bridge`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, hamstrings, core; flags: floor.
  Harder: single-leg glute bridge
- **single-leg glute bridge** (`single-leg-glute-bridge`): lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, hamstrings, core; flags: floor, single-leg.
  Easier: glute bridge
- **pillow-squeeze bridge** (`pillow-squeeze-bridge`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, adductors, hamstrings, core; flags: floor.
  Easier: glute bridge
- **glute bridge march** (`glute-bridge-march`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, hamstrings, core; flags: floor, single-leg.
  Easier: glute bridge
  Harder: single-leg glute bridge

### lunge
- **reverse lunge** (`reverse-lunge`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; quads, glutes, adductors, hamstrings; flags: single-leg.
  Easier: split squat
- **split squat** (`split-squat`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; quads, glutes, adductors; flags: single-leg.
  Harder: reverse lunge
- **step-up** (`step-up`): standing, one side at a time; box or bench or chair or stairs; 2.25 s a rep, 10 s to set up; strength, novice; quads, glutes, calves; flags: single-leg.
- **split squat hold** (`split-squat-hold`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; strength, novice; quads, glutes, adductors; flags: single-leg.
  Harder: split squat

### horizontal-push
- **incline push-up** (`incline-push-up`): standing; bench or chair; 2.25 s a rep, 10 s to set up; strength, novice; chest, triceps, shoulders, core.
  Easier: wall push-up
- **wall push-up** (`wall-push-up`): standing; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; chest, triceps, shoulders, core.
  Harder: incline push-up
- **wall push-up plus** (`wall-push-up-plus`): standing; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; shoulders, chest, back.

### horizontal-pull
- **towel door row** (`towel-door-row`): standing; towel; 2.25 s a rep, 10 s to set up; strength, novice; back, lats, biceps, forearms; flags: grip.
- **prone y t w raise** (`prone-y-t-w-raise`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; back, shoulders; flags: floor, overhead.
- **reverse snow angel** (`reverse-snow-angel`): lying; bodyweight; 3 s a rep, 10 s to set up; strength, novice; back, shoulders, lats; flags: floor, overhead.

### vertical-pull
- **prone lat pulldown** (`prone-lat-pulldown`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; lats, back, shoulders; flags: floor, overhead.

### rotation
- **bicycle crunch** (`bicycle-crunch`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; core; flags: floor, spine-flexion, spine-twist.
  Easier: reverse crunch, dead bug

### anti-rotation
- **side plank from the knee** (`side-plank-from-the-knee`): side-lying, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; strength, novice; core, shoulders, glutes, abductors; flags: floor, lying-side.

### anti-extension
- **dead bug** (`dead-bug`): lying; bodyweight; 3.75 s a rep, 10 s to set up; strength, novice; core; flags: floor.
- **bird dog** (`bird-dog`): all-fours; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; core, glutes, back; flags: floor, kneeling.
- **forearm plank** (`forearm-plank`): all-fours; bodyweight; timed, 30 s a hold, 10 s to set up; strength, novice; core, shoulders, glutes; flags: floor.
- **reverse crunch** (`reverse-crunch`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; core; flags: floor, spine-flexion.
  Easier: dead bug

### locomotion
- **marching in place** (`marching-in-place`): standing; bodyweight; timed, 60 s a hold, 10 s to set up; conditioning, easy effort, novice; quads, glutes, calves.
  Easier: seated march
- **seated march** (`seated-march`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; conditioning, easy effort, novice; quads, core, shoulders.
  Harder: marching in place
- **step jacks** (`step-jack`): standing; bodyweight; timed, 30 s a hold, 10 s to set up; conditioning, moderate effort, novice; quads, glutes, calves, shoulders; flags: overhead.
- **shadow boxing** (`shadow-boxing`): standing; bodyweight; timed, 60 s a hold, 10 s to set up; conditioning, moderate effort, novice; shoulders, core, calves; flags: fast, spine-twist.
  Easier: seated shadow boxing
- **seated shadow boxing** (`seated-shadow-boxing`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; conditioning, moderate effort, novice; shoulders, triceps, core; flags: fast.
  Easier: seated arm pumping
  Harder: shadow boxing
- **seated arm pumping** (`seated-arm-pump`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; conditioning, moderate effort, novice; shoulders, back, core; flags: fast.
  Harder: seated shadow boxing
- **seated speed bag** (`seated-speed-bag`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; conditioning, hard effort, novice; shoulders, core; flags: fast.
  Easier: seated arm pumping
- **seated overhead punches** (`seated-overhead-punches`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; conditioning, hard effort, novice; shoulders, triceps, core; flags: overhead, fast.
  Easier: seated speed bag

### hips
- **straight-leg raise** (`straight-leg-raise`): lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; quads, core; flags: floor.
- **donkey kick** (`donkey-kick`): all-fours, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, hamstrings, core; flags: floor, kneeling.
- **clamshell** (`clamshell`): side-lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, abductors; flags: floor, lying-side.
- **side-lying leg raise** (`side-lying-leg-raise`): side-lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, abductors; flags: floor, lying-side.
  Easier: clamshell
- **standing calf raise** (`standing-calf-raise`): standing; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; calves.
- **side-lying hip adduction** (`side-lying-hip-adduction`): side-lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; adductors, core; flags: floor, lying-side.
- **tibialis raise** (`tibialis-raise`): standing; bodyweight; 1.5 s a rep, 10 s to set up; strength, novice; calves.

### mobility
- **wall slide** (`wall-slide`): standing; bodyweight; 3 s a rep, 10 s to set up; mobility, novice; shoulders, back; flags: overhead.
- **arm circles** (`arm-circles`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; shoulders.
- **leg swings** (`leg-swings`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; hamstrings, glutes, adductors; flags: single-leg.
- **world's greatest stretch** (`worlds-greatest-stretch`): kneeling, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, adductors, hamstrings, back; flags: floor, kneeling, spine-twist, overhead.
- **cat-cow** (`cat-cow`): all-fours; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, core; flags: floor, kneeling, spine-flexion.
- **thread the needle** (`thread-the-needle`): all-fours, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, shoulders; flags: floor, kneeling, spine-twist.
- **ninety-ninety hip switches** (`ninety-ninety-hip-switch`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, adductors, abductors; flags: floor.
- **child's pose** (`childs-pose`): kneeling; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, lats, glutes; flags: floor, kneeling, spine-flexion.
- **supine twist** (`supine-twist`): lying, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, glutes; flags: floor, spine-twist.
- **figure-four stretch** (`figure-four-stretch`): lying, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, abductors; flags: floor.
- **seated figure four** (`seated-figure-four`): seated, one side at a time; chair or bench; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, abductors.
  Harder: figure-four stretch
- **hamstring stretch with a strap** (`strap-hamstring-stretch`): lying, one side at a time; strap or towel; timed, 30 s a hold, 10 s to set up; mobility, novice; hamstrings, calves; flags: floor.
- **seated hamstring stretch** (`seated-hamstring-stretch`): seated, one side at a time; chair or bench; timed, 30 s a hold, 10 s to set up; mobility, novice; hamstrings.
- **knees to chest** (`knees-to-chest`): lying; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, glutes; flags: floor, spine-flexion.
- **sphinx stretch** (`sphinx-stretch`): lying; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, core; flags: floor.
- **half-kneeling hip flexor stretch** (`half-kneeling-hip-flexor-stretch`): kneeling, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; quads, glutes, core; flags: floor, kneeling.
- **standing quad stretch** (`standing-quad-stretch`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; quads; flags: single-leg.
- **standing calf stretch** (`standing-calf-stretch`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; calves.
- **doorway chest stretch** (`doorway-chest-stretch`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; chest, shoulders.
- **cross-body shoulder stretch** (`cross-body-shoulder-stretch`): seated, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; shoulders, back.
- **shoulder rolls** (`shoulder-rolls`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; shoulders, neck.
- **half neck circles** (`neck-rolls`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; neck, shoulders.
- **seated side bend** (`seated-side-bend`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; lats, core; flags: overhead, spine-flexion.
- **seated twist** (`seated-twist`): seated; chair or bench; timed, 30 s a hold, 10 s to set up; mobility, novice; back, core; flags: spine-twist.
- **wall angel** (`wall-angel`): standing; bodyweight; 3 s a rep, 10 s to set up; mobility, novice; shoulders, back, core; flags: overhead.
- **side-lying open book** (`side-lying-open-book`): side-lying, one side at a time; bodyweight; 3 s a rep, 10 s to set up; mobility, novice; back, chest, shoulders; flags: floor, lying-side, spine-twist.
- **knee to wall ankle mobilization** (`knee-to-wall-ankle-mobilization`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; mobility, novice; calves.

### breathing
- **box breathing** (`box-breathing`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core.
- **long exhale breathing** (`long-exhale-breathing`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core.
- **belly breathing** (`belly-breathing`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core.
- **ninety-ninety breathing** (`ninety-ninety-breathing`): lying; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core; flags: floor.

- Would open up more movements: dumbbells (+23), band (+15), kettlebell (+14). Ask once at the check-in if one is on hand; otherwise plan without it.

## Programming guide
Guidance, not a plan: choose a shape inside it that suits this listener today. Where a dose range and a rule below disagree, the range is the level's and the rule says where in it to land.

Doses at the novice level (knowledge/sessions.toml):
- Strength: sets 2 to 3; reps 8 to 12; rest (s) 60 to 90; hard sets a session 6 to 12; a timed set (s) 40 to 60.
- Conditioning: work (s) 20 to 30; rest (s) 40 to 60; rounds 3 to 6; hard efforts a session 6 to 12.
- All-out sprints (an effort run flat out, 20 s or less) rest at least 4 times their work, and stay few. The conditioning doses and a Tabata block's twenty seconds are hard, not flat out: they keep their own rests.
- A whole-body session (general, or strength with no target) covers a push, a pull, a squat or lunge, and a hinge, plus core when there's room; the patterns the week hasn't trained come first.

Time (1800 s in all, house defaults): warm-up about 270 s, cool-down about 180 s; the work gets the rest.
- This session's work: about 11 hard sets in its 1350 s (a counted set with its rest is about two minutes; a timed set of forty-five seconds with its rest about a minute and a half, so about 15 of those): three sets of each main movement when the time holds them, never two, and no more movements than leaves room for that. Rests and timed sets are the dose's, never longer to fit a story, and the welcome stays under a minute: a story fits its moment, not the moment the story.

Formats that suit a 30 minute general session at this level with this kit (any of them, or a mix, as long as the doses fit):
- timed-sets: A short loop of movements, each for a set time at a steady pace, a few rounds, the coach setting each one up before the go and talking with them through it. (work: timed; rest 30 to 60 s between stations)
- circuit: A short loop of movements, one after another with little rest, repeated for a few rounds. (work: rounds; rest 45 to 90 s between rounds)
- straight-sets: One movement at a time, every set of it with rest between, then the next movement. (work: sets)
- paired-sets: Two movements in turn, a push with a pull or an upper with a lower, so one side rests while the other works. (work: pairs)

Timing: one set takes its reps times the seconds a rep (the menu's, already at the pace listeners really move: ten reps at two and a quarter seconds is under half a minute; both sides for one-sided work, plus about five seconds to switch), plus its setup the first time. A set with its rest takes about two minutes, about a minute and a half when paired (a minute between the halves). Plan from the lint's spoken column, not from the word guess.

What a good session looks like (the rules in knowledge/programming.md that bear on today):
- Effort: end working sets with about one to three reps left ("effort eight or nine out of ten"), and take only the last set of a simple movement close to failure. Never cue failure on a movement an injury rule limits. A movement that touches a delicate area is light (house default): twelve to fifteen reps with three or more left, its self-check offering only lighter or steady, and the day's harder work goes to movements that don't touch the area.
- Load range: with light dumbbells, use higher reps (15 to 30) and take sets closer to failure than with a heavy weight. Don't promise one-rep strength from light kit; promise muscle and working strength.
- Load range: a timed set runs forty to sixty seconds at a steady pace, with a load that leaves two or three reps in reserve at the end. The effort rule holds as for counted sets. Timed sets suit steady whole-body work, where the coach talks with the listener through the set; heavy sets near the top of the load range stay counted.
- Rest and pairing: pair opposing muscles (push with pull) or upper with lower, so one rests while the other works, and give about a minute between the two halves of a pair. Unpaired sets get one to two minutes.
- Exercise order: put the multi-joint movements (squat, hinge, press, row) first, while fresh, unless the session's priority is a single-joint movement such as a rehab exercise, which then goes first. For muscle size alone, order is free.
- Tempo: keep each rep between about two and eight seconds in total (a three-second lowering is fine); never cue a single rep longer than about eight seconds. A slower lowering is a way to make a light weight harder, not a goal in itself.
- The order of steps when load is capped is house policy: a few more reps, a slower lowering, a pause at the hard point, more range, one arm or one leg, and only then the next dumbbell. Change one variable at a time.
- Progression: "too easy" moves the next session one step along that list; "too hard" moves one step back, or trims a set. Say in the audio what changed.
- Readiness and adjusting on the day: the check-in's readiness changes the plan. Normal: plan as usual, from the last loads. Low (tired, short on sleep, stressed): keep the length and the kind of work, drop about a third of the hard sets (a round, or a set per movement), hold last time's loads, end every set with three or four reps left, and leave out all-out efforts and the finisher; give the time to longer rests and easy mobility, and say why in the opening. Fresh, last one felt easy: one step along the progression order. Last one too hard: one step back, or a set fewer. Soreness from training keeps that muscle group light and well short of failure today; pain in a joint is a delicate limit for today. During the session, each main movement's first working set gets a target (reps and reps left) and ends with a self-check that offers one harder and one easier option for the sets after it, from the movement's notes and the progression order; on low readiness, offer only the easier option or holding steady. Never offer a harder option that loads a limited area more.
- Warm-up, finisher and cool-down: keep the warm-up short and specific: easy movement, then a lighter first set of the main movements, as a rehearsal and a check that the movement feels right today (not a promise of more reps). Close with slow breathing because it calms and ends the session well, and never claim it prevents soreness or injury. The finisher is a short, simple burst (house policy, not a study) and stays inside the injury rules.
- Rest between intervals: genuine all-out efforts of 10 to 30 seconds get at least four times their length in easy movement, and five or six times when the listener should hit the next one as hard (a 20-second sprint gets about 2 minutes); expect the later ones to fade and say so, and keep them few. Hard efforts of 30 to 60 seconds that are not all-out take about equal to double their length in rest while fitness builds, and an advanced listener's as little as half (house defaults, as `knowledge/sessions.toml`'s conditioning doses set them); Tabata's twenty seconds are hard, not all-out, on its own ten-second rests; steady blocks need only a short breather.
- Effort by ear: for steady work, cue by talk: "you can speak in sentences" is moderate, "only a few words at a time" is above the first threshold. For intervals, where the talk test doesn't fit, cue a 0-to-10 effort: about 7 to 8 for hard intervals, 9 to 10 only for genuine sprints, and 3 to 4 for the recovery between (house mapping, anchored on the studies above).

## Equipment notes
**No equipment.** Bodyweight and some floor space. Everything still works: legs, glutes, core and pushing, with a chair or a wall to make it easier or harder. When standing is ruled out (an off-limits ankle or foot), seated conditioning (seated shadow boxing, arm pumps, speed bag) is what fills intervals and finishers; the brief's menu offers it once the limit removes the standing moves.

## Writing it
- First line of the draft: `movements: <every movement the script uses, by its name above, comma separated>`. Then the `@@ <seconds> | <label>` segments, adding up to exactly 1800 s. You choose the segments: one can be a set, a pair, a whole round or the whole warm-up.
- Coach each movement from its notes (`movements --about`) (setup, cues, what one rep is, where to feel it, the faults and their fixes): fully the first time it appears, then a short reminder, so the rests and the easy work have room for the listener's world. Safety is the one hard rule (knowledge/script.md); beyond it, get the workout done and keep them engaged. What a voice can read: knowledge/tts-rules.md.
- Talk to time: Coach Bea speaks about 162 words a minute (estimated; not measured on this computer yet), so twenty seconds of talk is about 54 words. Holds, pauses and chimes take their own seconds. Write the skeleton first (the `movements:` line and the `@@` lines with their counts, holds and `[reps N]` after each counted set's go, and an empty `[story] [/story]` after the go of each steady timed set that will carry a piece, no words yet): its build gives each segment's word budget, the reps' quiet left out, and every segment is written to its budget.
- Counts: write a countdown as `[count 5]` (five down to one) or `[count 3 go]` (then the cue; the cues are go, rest, switch, switch sides, stop and hold), and a cue said alone as `[cue rest]`. Coach Bea has no recorded counts, so the voice says it in words ("Three, two, one, go."), quickly: one per segment.
- Voice: Coach Bea is a web voice that reads a whole paragraph at once, so short cues sound fine.
