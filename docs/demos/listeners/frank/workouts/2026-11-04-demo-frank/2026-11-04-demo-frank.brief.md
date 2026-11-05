# Today's brief: targeted, 40 minutes, the home kit
2026-11-04, Wednesday. Ingredients, not a plan: design the session from these (method, movements, order, doses, timing), post the plan, then write it.

Written at 20:14. The MP3 may be played later tonight or another day: say an event's day and time ("tonight at seven thirty"), never "in half an hour" or "right now", and an event that starts before the workout is likely played (a game already under way) is "tonight's game", not a preview (knowledge/script.md, Time-proof it).

## The listener
- Name: Frank (greet them by it; two to four times a session).
- Level: experienced, in their words "I've trained before and know the basic moves, but I'm no expert." How much to explain: the whole setup the first time a movement appears, then the target and one point a set; the safety lines, the limit cues and the self-check under a limit are said in full whatever the level.
- Coach: Coach Priya (Late 30s, physiotherapist turned trainer. ElevenLabs's stock voice Lily: velvety, warm, British. Calm, precise, reassuring.)
- Tone: Calm and precise, a physio who coaches; thinks about joints and control, and explains why
- Encouragement: Praises control and good positions more than speed, and says what a careful choice protects
  In this coach's own words, but never as if they watched: praise turns on what the listener can feel or the plan guarantees ("if the last two felt clean, that's the standard", "three sets in the bank"). This voice is what makes the session theirs: every coaching line should sound like this coach, not any trainer.
- Cueing: Exact but plain cues, one at a time, with the breath
- Never says: Push through it; No pain, no gain; Beast mode
- Sign off: Gentle and specific; names how the body should feel now
- Usual length: forty minutes
- Time of day: varies.
- Preferred format: straight sets.
- Intensity: moderate, about six out of ten.

## Today in the week
- No sessions logged yet: this is the first one, so welcome them to it.

## Today's limits
- **shoulder off-limits, right side**: nothing that loads the right shoulder, and no impact work. Note: Six weeks after surgery: nothing that loads the right shoulder until the surgeon clears it.
  - Opening (say it in the opening, in your words if you like, every part kept): "Your right arm rests today, nothing pushing, pulling or leaning on it. Any pain in that shoulder means stop that move, and if it's still worse than when you started after a short rest, we stop for today."
  - Today, for you: The arm rests by the side or in the lap: nothing pushes, pulls or bears weight through it, getting up and down included.
  - Stop that movement on: any pain in the right shoulder.
  - Stop for today on: pain in that shoulder that's still worse than when you started after a short rest.

Clinician rules (say them in the clinician's words, attributed to the clinician; follow them literally, and where one is stricter than the general stop rule, such as no pushing through pain, it wins for that area every time it comes up; the menu applies only Avoid: lines, so leave out yourself what a rule forbids, such as a movement flagged overhead under no overhead work):
- No weight in the right hand, and no lifting the right arm above shoulder height, until the surgeon clears it.

Also left out of the menu today (by Avoid: lines, the request or the limits; not words to quote): overhead.

Limit cues (the catalog's spoken lines; say them wherever a movement or a transition touches the limit):
- shoulder off limits, right side:
  - Keep the right arm out of the work, resting by your side or in your lap.
  - Get up and down without putting any weight through the right arm.

Red flags, for the check-in, in chat (they stop the session before it starts, and suggest a clinician soon; the audio carries the opening's stop rule and heart rule instead): can't bear weight; rapidly increasing swelling; numbness or tingling; a joint that gives way or locks; pain that keeps getting worse after a week or two; dizziness that doesn't settle with rest; breathlessness that's suddenly getting worse; throbbing pain or swelling in one calf or thigh, with red, darkened or warm skin.
Emergencies, for the check-in, in chat (stop, and call emergency services now): chest pain, pressure or tightness, maybe spreading to the arm, neck or jaw; fainting or nearly fainting during exercise; a racing or irregular heartbeat with chest pain, breathlessness or feeling faint; leg pain or swelling with breathlessness or chest pain.

## Safe menu
Every movement in the script comes from this list, warm-up and cool-down included: 49 today (246 left out: equipment 190, shoulder off limits 39, impact 12, avoided 10, fast 10, level 6, lying on one side 3, rehab 3). Nothing from memory. `./harmonicfitness build` checks the draft's `movements:` line and its text against it.
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
  Harder: reverse lunge, bulgarian split squat
- **bulgarian split squat** (`bulgarian-split-squat`): standing, one side at a time; bench or chair; 2.25 s a rep, 10 s to set up; strength, experienced; quads, glutes, adductors; flags: single-leg.
  Easier: split squat
- **step-up** (`step-up`): standing, one side at a time; box or bench or chair or stairs; 2.25 s a rep, 10 s to set up; strength, novice; quads, glutes, calves; flags: single-leg.
- **forward lunge** (`forward-lunge`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, experienced; quads, glutes, adductors, hamstrings; flags: single-leg.
  Easier: reverse lunge, split squat
  Harder: walking lunge
- **walking lunge** (`walking-lunge`): standing; bodyweight; 2.25 s a rep, 10 s to set up; strength, experienced; quads, glutes, adductors, hamstrings, core; flags: single-leg.
  Easier: forward lunge, reverse lunge
- **lateral lunge** (`lateral-lunge`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, experienced; quads, glutes, adductors; flags: single-leg, lateral.
- **split squat hold** (`split-squat-hold`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; strength, novice; quads, glutes, adductors; flags: single-leg.
  Harder: split squat, bulgarian split squat

### rotation
- **bicycle crunch** (`bicycle-crunch`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; core; flags: floor, spine-flexion, spine-twist.
  Easier: reverse crunch

### anti-extension
- **hollow hold** (`hollow-hold`): lying; bodyweight; timed, 30 s a hold, 10 s to set up; strength, experienced; core; flags: floor, spine-flexion.
- **reverse crunch** (`reverse-crunch`): lying; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; core; flags: floor, spine-flexion.

### locomotion
- **marching in place** (`marching-in-place`): standing; bodyweight; timed, 60 s a hold, 10 s to set up; conditioning, easy effort, novice; quads, glutes, calves.

### balance
- **hip airplane** (`hip-airplane`): standing, one side at a time; bodyweight; 3 s a rep, 10 s to set up; strength, experienced; glutes, abductors, hamstrings, core; flags: single-leg, spine-twist.

### hips
- **straight-leg raise** (`straight-leg-raise`): lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; quads, core; flags: floor.
- **banded clamshell** (`banded-clamshell`): side-lying, one side at a time; mini-band or band; 2.25 s a rep, 15 s to set up; strength, novice; glutes, abductors; flags: floor, lying-side.
  Easier: clamshell
- **monster walk** (`monster-walk`): standing; mini-band or band; 1.5 s a rep, 15 s to set up; strength, novice; glutes, abductors, quads; flags: lateral.
  Easier: banded clamshell
- **clamshell** (`clamshell`): side-lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, abductors; flags: floor, lying-side.
  Harder: banded clamshell
- **side-lying leg raise** (`side-lying-leg-raise`): side-lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; glutes, abductors; flags: floor, lying-side.
  Easier: clamshell
- **standing calf raise** (`standing-calf-raise`): standing; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; calves.
  Harder: single-leg calf raise
- **single-leg calf raise** (`single-leg-calf-raise`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, experienced; calves; flags: single-leg.
  Easier: standing calf raise
- **side-lying hip adduction** (`side-lying-hip-adduction`): side-lying, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; strength, novice; adductors, core; flags: floor, lying-side.
- **tibialis raise** (`tibialis-raise`): standing; bodyweight; 1.5 s a rep, 10 s to set up; strength, novice; calves.
- **reverse nordic** (`reverse-nordic`): kneeling; bodyweight; 3 s a rep, 10 s to set up; strength, experienced; quads, core; flags: kneeling, floor.
  Easier: wall sit

### mobility
- **leg swings** (`leg-swings`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; hamstrings, glutes, adductors; flags: single-leg.
- **cat-cow** (`cat-cow`): all-fours; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, core; flags: floor, kneeling, spine-flexion.
- **ninety-ninety hip switches** (`ninety-ninety-hip-switch`): seated; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, adductors, abductors; flags: floor.
- **child's pose** (`childs-pose`): kneeling; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, lats, glutes; flags: floor, kneeling, spine-flexion.
- **supine twist** (`supine-twist`): lying, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, glutes; flags: floor, spine-twist.
- **figure-four stretch** (`figure-four-stretch`): lying, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, abductors; flags: floor.
- **seated figure four** (`seated-figure-four`): seated, one side at a time; chair or bench; timed, 30 s a hold, 10 s to set up; mobility, novice; glutes, abductors.
  Harder: figure-four stretch
- **seated hamstring stretch** (`seated-hamstring-stretch`): seated, one side at a time; chair or bench; timed, 30 s a hold, 10 s to set up; mobility, novice; hamstrings.
- **knees to chest** (`knees-to-chest`): lying; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; back, glutes; flags: floor, spine-flexion.
- **half-kneeling hip flexor stretch** (`half-kneeling-hip-flexor-stretch`): kneeling, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; quads, glutes, core; flags: floor, kneeling.
- **standing quad stretch** (`standing-quad-stretch`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; quads; flags: single-leg.
- **standing calf stretch** (`standing-calf-stretch`): standing, one side at a time; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; calves.
- **seated twist** (`seated-twist`): seated; chair or bench; timed, 30 s a hold, 10 s to set up; mobility, novice; back, core; flags: spine-twist.
- **knee to wall ankle mobilization** (`knee-to-wall-ankle-mobilization`): standing, one side at a time; bodyweight; 2.25 s a rep, 10 s to set up; mobility, novice; calves.

### breathing
- **box breathing** (`box-breathing`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core.
- **long exhale breathing** (`long-exhale-breathing`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core.
- **belly breathing** (`belly-breathing`): seated; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core.
- **ninety-ninety breathing** (`ninety-ninety-breathing`): lying; bodyweight; timed, 60 s a hold, 10 s to set up; breathing, novice; core; flags: floor.

### Healthy side only
Only the named side works; say in the audio why the other side rests, and that training the healthy side still helps the injured one a little (programming.md, One-sided training).
- **doorway chest stretch** (`doorway-chest-stretch`): standing, left side only; bodyweight; timed, 30 s a hold, 10 s to set up; mobility, novice; chest, shoulders.

- Would open up more movements: dumbbells (+11), kettlebell (+10), band (+6). Ask once at the check-in if one is on hand; otherwise plan without it.

## Programming guide
Guidance, not a plan: choose a shape inside it that suits this listener today. Where a dose range and a rule below disagree, the range is the level's and the rule says where in it to land.

Doses at the experienced level (knowledge/sessions.toml):
- Strength: sets 3 to 4; reps 6 to 10; rest (s) 90 to 120; hard sets a session 10 to 16; reps with no load 10 to 15; a timed set (s) 40 to 60.
- Conditioning: work (s) 30 to 45; rest (s) 30 to 45; rounds 4 to 8; hard efforts a session 8 to 16.
- All-out sprints (an effort run flat out, 20 s or less) rest at least 4 times their work, and stay few. The conditioning doses and a Tabata block's twenty seconds are hard, not flat out: they keep their own rests.

Time (2400 s in all, house defaults): warm-up about 360 s, cool-down about 240 s, a finisher of about 240 s, if you want one; the work gets the rest.

Formats that suit a 40 minute targeted session at this level with this kit (any of them, or a mix, as long as the doses fit):
- straight-sets: One movement at a time, every set of it with rest between, then the next movement. (work: sets)
- paired-sets: Two movements in turn, a push with a pull or an upper with a lower, so one side rests while the other works. (work: pairs)
- timed-sets: A short loop of movements, each for a set time at a steady pace, a few rounds, the coach setting each one up before the go and talking with them through it. (work: timed; rest 30 to 60 s between stations)

Focus today: quads, glutes, hamstrings, core. Give it at least half the work, and keep the rest of the body ticking over.

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
- One-sided training: train both sides by default. When an injury rules out one side, training the healthy side still helps the injured one a little; say so in the audio, and never present it as a replacement for the injured side's own rehab.

## Equipment notes
**Mat and mobility.** A mat, and perhaps a foam roller and a stretching strap, for floor work, mobility and box breathing.

**Resistance bands.** Two kinds, listed apart: long bands or tube bands (`band`), which need a solid anchor (a closed door with a door anchor, or a heavy post) for rows, presses, chops and the ankle drills; and small loop bands (`mini-band`) worn around the legs for clamshells and side steps. A long band tied into a loop does a loop band's work, so those movements take either. Banded ankle rehab (eversion, inversion, dorsiflexion) is used only when the ankle's limit allows it or names it under `rehab`.

## Writing it
- First line of the draft: `movements: <every movement the script uses, by its name above, comma separated>`. Then the `@@ <seconds> | <label>` segments, adding up to exactly 2400 s. You choose the segments: one can be a set, a pair, a whole round or the whole warm-up.
- Coach each movement from its notes (`movements --about`) (setup, cues, what one rep is, where to feel it, the faults and their fixes): fully the first time it appears, then a short reminder, so the rests and the easy work have room for the listener's world. Safety is the one hard rule (knowledge/script.md); beyond it, get the workout done and keep them engaged. What a voice can read: knowledge/tts-rules.md.
- Talk to time: Coach Priya speaks about 161 words a minute (estimated; not measured on this computer yet), so twenty seconds of talk is about 54 words. Holds, pauses and chimes take their own seconds. Write the skeleton first (the `movements:` line and the `@@` lines with their counts, holds and `[reps N]` after each counted set's go, and an empty `[story] [/story]` after the go of each steady timed set that will carry a piece, no words yet): its build gives each segment's word budget, the reps' quiet left out, and every segment is written to its budget.
- Counts: write a countdown as `[count 5]` (five down to one) or `[count 3 go]` (then the cue; the cues are go, rest, switch, switch sides, stop and hold), and a cue said alone as `[cue rest]`. Coach Priya has no recorded counts, so the voice says it in words ("Three, two, one, go."), quickly: one per segment.
- Voice: Coach Priya is a web voice that reads a whole paragraph at once, so short cues sound fine.
