# Equipment Kits

What each kind of kit usually holds, and how to script around it. The movements themselves live in the catalog, `knowledge/movements.toml`, each with its equipment, spoken setup, cues and how much it loads each joint area. Don't pick from memory: after the check-in, run `./sweatcast session` for today's request and kit (or `./sweatcast movements` to browse) and choose from what it prints.

## Choosing the kit for the filter
Four kits have a preset in the catalog: `--preset bodyweight`, `--preset hotel-room`, `--preset hotel-gym` and `--preset full-gym`. For any other kit, such as the one at home, pass its equipment instead: `--equipment dumbbells,bench,band`, using the keys or aliases in the catalog's `[equipment]` table ("resistance bands" and "band" both work). Floor and wall space are always assumed. `./sweatcast session` applies the limits in `me/health.md` itself (the injury playbook explains them); `--avoid` takes any further movement ids or flags to rule out.

## No equipment
Bodyweight and some floor space. Everything still works: legs, glutes, core and pushing, with a chair or a wall to make it easier or harder.

## Dumbbells
Fixed or adjustable dumbbells, often with a bench. Seated and bench-supported work keeps weight off a sore lower leg.

## Kettlebell
One or more kettlebells. Swings and get-ups need floor space and a clear area around the listener.

## Stationary bike
Upright or recumbent. Intervals by cadence and resistance. Write cadence in words ("a cadence around ninety"). Effort language: easy, moderate, hard, all-out, as a number out of ten if helpful. Formats: steady endurance, sixty-second surges with sixty easy, tabata-style twenty on ten off (harder to script; announce each change), resistance ladders, cadence pyramids. Seated is ankle-friendly when resistance is low to moderate and the foot is centered; standing climbs and sprints load the ankle. Clip-in or cage removal: if the injured foot can't safely clip in or twist out, use the bike with sneakers on platform pedals or skip it. Cues: "Quiet upper body, relax the grip." "Smooth circles, not stomping." "Shoulders down away from the ears."

## Stick and dryland ball
A hockey stick and a dryland ball, for stickhandling: hand speed, coordination, and wrist and forearm endurance. Done seated, it makes good conditioning that spares the ankles; the catalog's skill movements list the seated and standing drills. Never wind up overhead or take slap-shot swings.

## Rowing machine
Full-body cardio. Strokes per minute in words. Cue "legs, then body, then arms; arms, body, then legs on the way back".

## Resistance bands
Long bands or loop bands. A long band needs a solid anchor: a closed door with a door anchor, or a heavy post. Banded ankle rehab (eversion, inversion, dorsiflexion) is used only when the ankle's limit allows it or names it under `rehab`.

## Bench
A flat or adjustable bench, for supported rows, presses, step-ups and seated work.

## Mat and mobility
A mat, and perhaps a foam roller and a stretching strap, for floor work, mobility and box breathing.

## Hotel room (no gym)
Typically bodyweight, a chair, a bed edge, a towel, maybe a band. Towel rows go around a door handle only if the door is solid and closed toward the user; towel slides need a hard floor. Keep noise low; no jumping in hotel rooms.

## Hotel gym (assume basic)
Hotel gyms vary, so plan for the common minimum and offer a swap for anything less certain. Usually present: a dumbbell rack (often only up to about fifty pounds), an adjustable bench, a treadmill, an elliptical, an upright or recumbent bike, a mat area, and sometimes a cable machine or a Smith machine. The recumbent bike is the gentler option for an injured ankle. Scripting notes: say "if your hotel has a cable machine, use it; if not, grab a dumbbell and do this instead" for anything beyond dumbbells and a bench. Heavy dumbbells may not exist, so program effort by reps and tempo ("pick a weight that leaves two reps in the tank") rather than specific pounds.

## Full gym
Assume a complete commercial gym: squat racks and barbells, plate-loaded and selectorized machines, cable stations, a full dumbbell rack, benches, rowers, bikes, treadmills, sometimes a ski erg, an air bike, a sled, and turf. Machines are often the most injury-friendly options, and cables can be set up seated or half-kneeling to keep weight off a sore lower leg. Scripting notes: a gym is shared, so a station may be taken. For every main movement, name a fallback in the setup cue ("leg curl machine, or if it's busy, a dumbbell held between your feet on the bench"). Moving between areas of a big gym takes time; group movements by zone (cable zone, then machine row, then the bike) and give transitions at least twenty to thirty seconds. Barbell setup and plate loading takes a minute or more, so give barbell work longer segments with the setup inside the segment, or skip barbells in short sessions. Never script anything that requires a spotter.
