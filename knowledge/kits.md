# Equipment Kits

What each kind of kit usually holds, and how to script around it. The movements themselves live in the catalog, `knowledge/movements.toml`, each with its equipment, spoken setup, cues and how much it loads each joint area. Don't pick from memory: after the check-in, run `./harmonicfitness brief` for today's request and kit and choose every movement, warm-up and cool-down included, from its safe menu; the build checks the draft against it. `./harmonicfitness movements` only browses the catalog and applies no health limits, so never plan from it.

## What the brief prints for a kit
- **Coaching** for every movement on the menu: the catalog's spoken setup, cues, what one rep is, where it should be felt and the common faults with their fixes. Write form cues from these, not from memory; `./harmonicfitness movements --about <ids>` prints the same for any movement.
- **Loads on hand**, when the kit's `[[kits]]` row in `me/training.md` gives its `weights` (for example `weights = { dumbbells = [10, 15, 20], kettlebell = [30] }` and `unit = "lb"`). Prescribe from those weights by name ("the fifteens"), never a weight the kit doesn't have. At the heaviest, progress by the order in `knowledge/programming.md` (reps, tempo, pauses, range, one side), not by promising a heavier weight.

## Choosing the kit
Four kits have a preset in the catalog: `--preset bodyweight`, `--preset hotel-room`, `--preset hotel-gym` and `--preset full-gym`. For any other kit, such as the one at home, pass its equipment instead: `--equipment dumbbells,bench,band`, using the keys or aliases in the catalog's `[equipment]` table ("resistance bands" and "band" both work). Floor and wall space are always assumed. `./harmonicfitness brief` applies the limits in `me/health.md` itself (the injury playbook explains them); `--avoid` takes any further movement ids or flags to rule out.

## No equipment
Bodyweight and some floor space. Everything still works: legs, glutes, core and pushing, with a chair or a wall to make it easier or harder. When standing is ruled out (an off-limits ankle or foot), seated conditioning (seated shadow boxing, arm pumps, speed bag) is what fills intervals and finishers; the brief's menu offers it once the limit removes the standing moves.

## Dumbbells
Fixed or adjustable dumbbells, often with a bench. Seated and bench-supported work keeps weight off a sore lower leg.
- Getting heavy dumbbells into place costs time and is where people strain: for a bench or floor press, sit with them on the thighs and roll back with them; to finish, bring them to the chest and roll up, never drop them out wide. Script that in the setup and give the transition its seconds.
- Adjustable dumbbells take fifteen to thirty seconds to change; fixed pairs on the floor take a few. A change of weight between sets belongs in the rest, said out loud ("Swap to the fifteens now").
- Name weights the way the listener says them ("the twenties"). With only a few pairs, the jump between them is large (ten to fifteen is half again), so a step up usually comes with fewer reps.

## Kettlebell
One or more kettlebells. Swings and get-ups need floor space and a clear area around the listener.
- One kettlebell of one weight is common: it is light for hinges and squats and heavy for pressing, so use it where it fits (goblet squats, deadlifts, carries, one-arm rows) and add reps or tempo rather than forcing it overhead.
- Held by the horns for goblet work, by the handle for carries and rows. Cue the grip; a sweaty handle slips.

## Stationary bike
Upright or recumbent. Intervals by cadence and resistance.
- Setup before the first effort: saddle at hip height standing beside it, a slight bend in the knee at the bottom of the stroke, handlebars where the back stays long. Saying it once in the warm-up saves a sore knee.
- Pedals: clip-in shoes lock the foot and need a twist out, which loads the ankle; cages or plain platform pedals with sneakers don't. A bike sold with clip-in pedals (most connected studio bikes) often takes platform pedals or a toe-cage adapter.
- Resistance scales differ by bike (a numbered dial, a percent, a knob with no numbers), so cue by feel: "enough that you could hold this cadence for ten minutes", "like riding up a steady hill", "the most you can turn over at seventy". A cadence in words is universal. Write cadence in words ("a cadence around ninety"). Effort language: easy, moderate, hard, all-out, as a number out of ten if helpful. Seated is ankle-friendly when resistance is low to moderate and the foot is centered; standing climbs and sprints load the ankle. Clip-in or cage removal: if the injured foot can't safely clip in or twist out, use the bike with sneakers on platform pedals or skip it. Cues: "Quiet upper body, relax the grip." "Smooth circles, not stomping." "Shoulders down away from the ears."

## Stick and dryland ball
A hockey stick and a dryland ball, for stickhandling: hand speed, coordination, and wrist and forearm endurance. Done seated, it makes good conditioning that spares the ankles; the catalog's skill movements list the seated and standing drills. Never wind up overhead or take slap-shot swings.

## Rowing machine
Full-body cardio. Strokes per minute in words. Cue "legs, then body, then arms; arms, body, then legs on the way back".
- Damper around three to five out of ten; a high damper feels harder but mostly loads the low back. Feet strapped across the ball of the foot.
- It loads the low back (the catalog rates it), so a delicate or off-limits low back rules it out.

## Treadmill
- The belt takes time to change speed (house judgment: several seconds for a jump of a few miles an hour on a home or hotel treadmill). A work-and-rest interval shorter than about thirty seconds on and thirty off spends most of its rest waiting for the belt. Prefer incline changes for short intervals, or a longer interval, or straddle the belt on the side rails for the rest (only when both feet and ankles are fine), and say which.
- Hands off the rails while walking or running; holding them cuts the work and twists the body. The safety clip goes on the clothing at the hip.

## Resistance bands
Long bands or loop bands. A long band needs a solid anchor: a closed door with a door anchor, or a heavy post. Banded ankle rehab (eversion, inversion, dorsiflexion) is used only when the ankle's limit allows it or names it under `rehab`.

## Bench
A flat or adjustable bench, for supported rows, presses, step-ups and seated work.

## Mat and mobility
A mat, and perhaps a foam roller and a stretching strap, for floor work, mobility and box breathing.

## Pull-up bar and dip station
A doorway or mounted pull-up bar, and parallel dip bars (freestanding or on a power tower). Everything on them is body weight hung from the hands, so the catalog flags it `hanging` and rates the shoulder, elbow and wrist; a delicate shoulder or elbow keeps it off the menu.
- A doorway bar is only as safe as the frame: test it with a bounce before the first set, and never kip or swing on one. The catalog refuses kipping and muscle-ups.
- Most people can't do many strict pull-ups. A chair or box under the bar turns the set into slow lowerings (negatives), and a dead hang or a shoulder-blade pull builds toward it. Cue a step down, never a drop, at the end of every set.
- Dips drive the shoulder into deep extension under body weight: script a shallow range ("stop when your upper arms are level with the floor").

## Suspension trainer
Straps with handles, anchored over a closed door (the door opening away from the listener) or to a beam. The body angle sets the load: walking the feet toward the anchor makes rows and presses harder, stepping away makes them easier, so one script suits every level when it says which way to step.
- Check the anchor before the first set and keep the straps taut throughout; a slack strap snaps tight under load.
- Lying work (hamstring curls with the heels in the straps) needs the cradles at mid-shin height, set before the segment starts.

## Medicine ball and slam ball
A medicine ball bounces and is for throws against a solid wall (a brick or concrete wall, never drywall or a window) and passes; a slam ball is soft and dead and is the only ball for slamming on the floor. Never slam a bouncing medicine ball: it rebounds into the face.
- Throws and slams are fast and load the shoulder, and slams the low back: a delicate area there keeps them out. Script a light ball, and the catch with soft elbows.
- Downstairs neighbors and hotel floors don't welcome slams; use them at a gym or on a ground floor.

## Box
A plyo box or a sturdy aerobic step. Step-ups and step-downs need only a step a little below knee height; jumps need a stable box that won't tip, a landing surface that doesn't slide, and only an advanced listener with no lower-leg limit (the catalog flags them `impact`). Always step down from a jump box, never jump down.

## Sliders
Gliding discs on a smooth floor, or a towel on a hard floor (the catalog accepts either). Carpet takes the plastic side up and a hard floor the felt side. Sliding work is slow and controlled: the slide loads the moving leg through its whole range, so cue a short slide first.

## Stability ball
A large inflatable ball, sized so the hips and knees bend to about a right angle when seated on it. Lying and bridging work with the feet on the ball loads the hamstrings without load on the spine; anything balanced on it needs space around the listener and a floor that doesn't slide. A ball that's soft or old can burst: check it's firm.

## Ab wheel
An ab roller wheel, rolled out from the knees (a mat or folded towel under them). It's hard on the low back if the hips sag: script a short roll toward a wall that stops the wheel, and a delicate low back or shoulder keeps it off the menu.

## Battle ropes
Heavy ropes anchored around a post or kettlebell, for waves and slams. Hard conditioning in short bursts (twenty to thirty seconds), loading the shoulders, grip and, through the hinge, the low back. Script a soft bend in the knees, a braced trunk and the rope's slack kept out of the anchor.

## Landmine and trap bar
A landmine holds one end of a barbell, so the other end moves in an arc: presses go up and forward rather than straight overhead, kinder to a shoulder that dislikes overhead work, and rows and squats load the front of the body. A trap bar puts the lifter inside the bar, so the deadlift loads the knee more and the low back less than a straight bar; it is still a heavy pull, with setup and plate loading inside the segment.

## Jump rope
A skipping rope, its length set so the handles reach the armpits with a foot on the middle. Impact work: the catalog flags it so, and any lower-leg limit keeps it out. Hotel rooms and low ceilings rule it out too.

## Hotel room (no gym)
Typically bodyweight, a chair, a bed edge, a towel, maybe a band. No mat: floor work goes on the carpet or a folded towel under the knees. A chair for support goes against a wall so it can't slide, and nothing pushes on a chair with wheels; the bed edge is fine for sitting and incline push-ups, too soft for step-ups. Towel rows go around a door handle only if the door is solid and closed toward the user; towel slides need a hard floor. Keep noise low; no jumping in hotel rooms.

## Hotel gym (assume basic)
Hotel gyms vary, so plan for the common minimum and offer a swap for anything less certain. Usually present: a dumbbell rack (often only up to about fifty pounds), an adjustable bench, a treadmill, an elliptical, an upright or recumbent bike, a mat area, and sometimes a cable machine or a Smith machine. The recumbent bike is the gentler option for a sore (delicate) ankle; an off-limits ankle rules pedaling out. Scripting notes: say "if your hotel has a cable machine, use it; if not, grab a dumbbell and do this instead" for anything beyond dumbbells and a bench. Heavy dumbbells may not exist, so program effort by reps and tempo ("pick a weight that leaves two reps in the tank") rather than specific pounds.

## Full gym
Assume a complete commercial gym: squat racks and barbells, plate-loaded and selectorized machines, cable stations, a full dumbbell rack, benches, rowers, bikes, treadmills, sometimes a ski erg, an air bike, a sled, and turf, and in the functional area a pull-up bar and dip station, suspension straps, medicine and slam balls, plyo boxes, sliders, stability balls, an ab wheel, battle ropes, a landmine, a trap bar and jump ropes. Machines are often the most injury-friendly options, and cables can be set up seated or half-kneeling to keep weight off a sore lower leg. Scripting notes: a gym is shared, so a station may be taken. For every main movement, name a fallback in the setup cue ("leg curl machine, or if it's busy, a dumbbell held between your feet on the bench"). Moving between areas of a big gym takes time; group movements by zone (cable zone, then machine row, then the bike) and give transitions at least twenty to thirty seconds. Barbell setup and plate loading takes a minute or more, so give barbell work longer segments with the setup inside the segment, or skip barbells in short sessions. Never script anything that requires a spotter.
