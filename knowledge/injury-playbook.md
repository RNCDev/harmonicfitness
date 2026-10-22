# Injury Playbook

How to program around an injury or limitation. This is a general guide for a healthy adult working around a known, already-assessed problem, not a substitute for a clinician.

**A clinician's rules always win.** Anything a doctor or physical therapist has told the listener overrides this file and `knowledge/injury-rules.toml`. Record those instructions in the injury's entry in `me/health.md`, in their words, and follow them literally. Where this file, the rules file, `knowledge/kits.md` and `me/health.md` disagree, the strictest wins, and anything the health file bans is out.

## How the rules and this file fit together
`knowledge/injury-rules.toml` holds, for each body area and phase, what's banned (by the tags in `knowledge/movements.toml`, plus the movements the tags miss), what's allowed only under a condition, which rehab movements to add, and what the listener should be able to do before moving on. This file holds the reasons: why each area is handled the way it is, what each phase is for, how to judge the criteria at the check-in, and where the evidence comes from. It never repeats the ban lists; read them in the rules file.

Most of the bans are conservative judgment, carried over from this file's earlier lists and tightened where a movement slipped past the tags, not rules a study set. Where a source supports a phase's purpose or a criterion, the area's section says so and says what the source doesn't show. Where nothing was confirmed, the section says that too.

## Procedure for every active injury
1. Identify the body area, side, what happened, and roughly when. The area is one of the rules file's areas (the headings below); anything else is an unlisted injury.
2. Determine the phase from the listener's report today, and check it against the criteria for the phase they were in (that phase's `advance_when` in the rules file):
   - Protect (first days, or pain at rest, visible swelling, limping): keep load off the area. Train everything else.
   - Restore (pain only with certain movements, swelling settling): gentle, pain-free range of motion for the injured area; normal training elsewhere within the rules.
   - Rebuild (walking normally, mild or no pain): progressive, controlled loading of the area, still avoiding high-speed or impact work.
   - Return (cleared, or symptom-free in daily life): reintroduce impact and speed gradually, one variable at a time.
   Move on only when the listener meets every criterion for the phase they're in. If unsure, choose the more conservative phase and say so in chat. A phase can also go backwards: a flare-up, new swelling or a bad next morning drops it one phase.
3. Build the movement list from the rules. For each active injury, take its area and phase in the rules file: pass that phase's `ban` tags to `./sweatcast movements --avoid`, plus its `ban_injured_side` tags when the injury has a side (the tool doesn't know the side yet, so it leaves those movements out on both sides; a healthy-side version can come back by hand). Then strike that phase's `ban_ids` from the list, keep each `caution` movement only with its condition, and add the `include` rehab movements, which belong in the session even when one of their tags is banned. Put `me/health.md` on top. Pick only from what's left, including the warm-up and finisher. Hidden culprits are common: burpees, mountain climbers, jumping jacks, lunges and standing kettlebell swings all load the ankle and knee. If something looks wrong for the injury, leave it out.
4. Choose substitutions that train the same quality without the banned stress. A movement under `caution` goes in only with its condition spoken in the setup cue.
5. Script safety cues into the audio: one mention in the opening segment, and a short reminder in any segment where the injured area is near the action ("keep that left foot planted and quiet").
6. Include a stop rule in the opening: pain should stay mild, around two or three out of ten at most, and should not be worse the next morning. Sharp pain, new swelling, numbness, or giving way means stop that movement.
7. Red flags to mention in chat (not in the audio) if the listener reports them: inability to bear weight, rapidly increasing swelling, numbness or tingling, a joint that gives way, or pain that keeps getting worse after a week or two. These deserve a clinician visit before more training.

## Judging the criteria
The criteria are things the listener can answer at the check-in from daily life: walking, stairs, sleep, lifting a cup, how the area felt the morning after the last session. Ask about them in plain words ("Can you walk around the house without limping?"), and take "mostly" as "not yet". The morning-after check matters most: a session that leaves the area worse the next day was too much, whatever the phase. Only the listener's report moves a phase; the plan never assumes progress because time has passed.

## Ankle
A consensus paper calls the lateral ankle sprain the most common sports injury, with a high rate of recurrence, and balance training is one of the two things with evidence for preventing a second one (bracing is the other). So the early phases keep weight off the ankle and keep everything else training, and the later phases rebuild balance on purpose before speed and impact come back.

- **Protect** keeps the ankle unloaded: seated, lying and floor work, and upper-body cardio. Anything that puts weight through the foot waits, including the quiet ways it happens: toes on the floor in a full push-up or plank (do them from the knees), the bottom foot in a full side plank, kneeling with the foot pointed under the body, feet driving a loaded bridge or a hamstring curl. The ankle rehab movements and all pedalling wait for restore too. The guideline below says a short time of immobilisation can ease pain and swelling, but the ankle does best with an exercise programme soon after, so protect should be short.
- **Restore** still keeps weight off the foot, as protect does, and adds back only what helps it move: gentle seated range of motion (the alphabet, circles, band work, and a gentle band calf press, which the rules include even though it pushes through the ball of the foot), easy seated pedalling at light resistance with the foot centred, bridges with both feet down, and supported squats to a box if pain-free (also included by the rules). Band work that rolls the foot inward and deep kneeling on a pointed foot wait for rebuild.
- **Rebuild** loads the ankle progressively on both feet: squats such as the goblet squat, double-leg calf raises (seated, since that's the catalog's version), split squats with the injured leg behind, moderate seated pedalling, and supported single-leg balance on the injured side, starting with fingertips on a wall and made harder over sessions (fingertips off, eyes closed, a soft surface). The rules include the balance, calf raises and split squats even though their tags are still banned; other single-leg and push-off work (lunges, step-ups, the sled, stairs, an incline walk, the leg press) waits for return. The balance training is what lowers the chance of a second sprain, so it belongs in every rebuild session, not as an extra.
- **Return** brings back single-leg and push-off work, then hops on two feet, then on one, then side-to-side movement, one at a time across sessions. Keep a short balance block in sessions for months afterwards.

How to judge the criteria: limping and swelling decide protect and restore. For rebuild, compare the two legs: single-leg balance and single-leg calf raises on the injured side should be close to the other side, with no pain through the day and no swelling the morning after. The return-to-sport consensus below names pain over the last day, ankle range and strength, confidence in the ankle, balance, and hopping as what to check before full sport; the listener can judge each one roughly at home.

- The lateral ankle sprain is the most common sports injury, with a high recurrence rate. Source: https://pubmed.ncbi.nlm.nih.gov/34158354/ (the abstract's background). It gives no figures for how often sprains recur.
- Short immobilisation may relieve pain and swelling, but after an ankle ligament rupture people do best with a brace or tape plus an exercise programme; supervised exercise is preferred over passive treatment, and braces are an effective way to prevent another sprain. Source: https://pubmed.ncbi.nlm.nih.gov/29514819/ (the guideline's abstract, read through PubMed). It doesn't give phase lengths, a list of movements to avoid, or criteria for moving on.
- An overview of systematic reviews found strong evidence for early mobilisation after an acute sprain, and moderate evidence that neuromuscular (balance) training prevents another sprain; bracing has strong evidence for the same. Source: https://pubmed.ncbi.nlm.nih.gov/28053200/ (abstract). It doesn't say which balance exercises, how much, or for how long, and it doesn't cover the order in which to bring back impact.
- An international expert consensus (a Delphi survey, not a trial) agreed sixteen checks for returning to sport after an ankle sprain, in five groups: pain during sport and over the last day, ankle range of motion and strength, the athlete's confidence and readiness, balance and position sense, and hopping, jumping, agility and full training. Source: https://pubmed.ncbi.nlm.nih.gov/34158354/ (abstract). It's expert opinion from elite field and court sports, gives no pass marks, and isn't written for home workouts.

## Knee
The rules assume that deep bending under load, twisting and landing are what aggravate a sore knee. So the early phases keep the knee out of deep bends, kneeling, landing and pivoting, and hip work does much of the leg training; for kneecap pain, the consensus below recommends hip and knee exercise together over knee exercise alone.

- **Protect** keeps the knee unloaded: lying and seated work, hip work that doesn't bend the knee deeply, and only the easiest seated pedalling, with the seat set slightly high, if it's pain-free. Loaded hamstring curls, harder bike work, and machines that press pads against the knee wait for restore; a heavy barbell bridge waits too.
- **Restore** brings back standing on both legs, hamstring curls and hip hinges if pain-free, and light pedalling. Deep knee bends, loaded straightening and kneeling still wait.
- **Rebuild** loads the knee progressively: squats, split squats and step-ups through a range that stays pain-free, deepening over sessions, plus loaded straightening at light weights. The guidance below found that exercise helps whether or not it's done standing, so there's no need to rush weight-bearing.
- **Return** brings back landing, pivoting (including the back-foot pivot in a woodchop), kneeling and ballistic work, one at a time.

How to judge the criteria: walking without a limp and no pain at rest end protect. Stairs and getting up from a chair without pain end restore. For rebuild, a full-range squat and stairs going down (the harder direction) without pain, and no extra pain the morning after a loaded session.

- For patellofemoral pain (pain around or behind the kneecap), an expert consensus recommends exercise to reduce pain and improve function, and recommends combining hip and knee exercises over knee exercises alone; it found exercise works whether or not it's done standing. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4975825/. It covers long-standing kneecap pain, not acute injuries such as ligament or meniscus tears, and it says nothing about knee angles, pain during exercise or how to progress.

## Lower back
The guideline below encourages people with low back pain to continue normal activities and to exercise. So nothing here keeps the listener still: walking, easy pedalling and core work in a neutral spine carry on throughout. The rules assume that what strains a sore back most is curling the spine against resistance, heavy hinging, twisting under load, and pressing overhead while standing, on the view that it arches the low back. Seated presses with the back supported are fine. Favour neutral spine and bracing cues: ribs down, the low back quiet, and the back flat on the pad in a leg press or a pullover.

- **Protect** keeps the back in neutral and the session gentle: dead bugs, bird dogs and side planks if pain-free, glute bridges, rows with the chest on a bench, walking or easy bike. Running, jumping and other impact wait for return, and the forearm plank waits for restore, since it arches a tired low back easily.
- **Restore** brings back the forearm plank, still without loaded curling, hinging, twisting or impact.
- **Rebuild** brings back hinging with light weights and standing overhead pressing, with a flat back and ribs down, progressing over sessions. Swings, like running and jumping, are fast and wait for return.
- **Return** brings back loaded curling and twisting, swings, running and jumping, one at a time.

How to judge the criteria: getting out of bed and up from a chair without a sharp catch, and walking ten minutes without the pain building, end protect. Bending to pick something light up from the floor, and no worse the morning after a session, end restore. A light hinge with no pain during or the next morning, and a normal day of sitting and standing, end rebuild.

- The NICE guideline recommends advice that encourages people with low back pain to continue normal activities, and suggests considering a group exercise programme (biomechanical, aerobic, mind–body or a mix) for an episode or flare-up, chosen around the person's needs, preferences and abilities. It also says to look for other causes, such as cancer, infection, trauma or inflammatory disease, especially with new or changed symptoms. Source: https://www.nice.org.uk/guidance/ng59/chapter/Recommendations. It doesn't say which movements to avoid, or give phases or criteria for progressing.

## Shoulder
The rules treat load overhead, end-range positions (dips, wide-grip pressing, anything behind the neck), hanging and lying on the sore side as what aggravates a sore shoulder. For rotator cuff pain, the review below found exercise helps and light loads work about as well as heavy ones, so there's no reason to push through pain early.

- **Protect** keeps load off the shoulder: pressing, raises, weight on the hands, and arm-driven cardio (punching, jacks, the air bike's handles, the sled) all wait. Heavy gripping waits too, because a heavy weight in the hand hangs from the shoulder; that is stricter than this file's earlier list, and it means deadlifts, swings and carries wait for restore even though they're lower-body work. Lying on either side waits, since the rules can't tell the sides apart. Light rows to the lower ribs, a neutral-grip floor press, band external rotation and shoulder-blade work are allowed only if pain-free. Lower-body and core training carry on, with dead bugs in place of planks and the arms kept down in stretches and crunches.
- **Restore** brings back weight on the hands, gripping, light band pressing and planks if they don't hurt. Overhead work, end-range positions, hanging, most pressing and fast arm work still wait.
- **Rebuild** brings back overhead pressing, push-ups and bench pressing at light loads, progressing as the shoulder allows. End-range positions, hanging and fast arm work (punching drills, jumping jacks, swings) still wait.
- **Return** brings back end-range work, hanging and fast arm work, one at a time.

How to judge the criteria: no pain at rest or at night, and lifting the arm to shoulder height without pain, end protect. Raising the arm overhead without weight, sleeping without pain, and light rows and floor presses that are fine the next day, end restore. A light overhead press without pain, near-equal strength on both sides, and no pain the morning after an upper-body session, end rebuild.

- A systematic review found that exercise reduces pain and improves function in rotator cuff tendinopathy; several kinds worked (eccentric, conventional, shoulder-blade and cuff strengthening), none was better than the others, and high loads were no better than low loads. It suggests choosing by the person's tolerance and adherence. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC9904825/. It doesn't address progression, overhead positions or avoiding painful ranges, and it's a small review in a regional journal.
- A 2025 clinical practice guideline covers assessment, non-surgical care, rehabilitation and return to sport for rotator cuff tendinopathy, including partial tears. Source: https://pubmed.ncbi.nlm.nih.gov/40165544/ (abstract). Only the abstract was read, which states its scope; its graded recommendations weren't confirmed, so nothing here rests on them.

## Wrist and hand
The rules treat these as what loads a sore wrist: weight on the hands with the wrist bent back (push-ups, planks on the hands, all fours, a front-rack hold), heavy or long gripping, and hanging. Anything held in both hands at once (a bar, a cable or band handle, a machine's grips, a single weight held two-handed) loads the injured hand too, so the rules keep those out early. The rules can't see which hand holds a dumbbell, so in protect and restore keep weights out of the injured hand in the script: one-arm work on the healthy side, or a goblet hold cradled on the forearms.

- **Protect and restore** keep weight and grip off the hand: forearm planks, lower-body work, the bike. Restore adds gentle wrist range of motion. They ban the same things; what moves the listener from one to the other is pain at rest and swelling.
- **Rebuild** brings back weight on the hands (push-ups on dumbbell handles first, with the wrist straight) and gripping at light loads. Hanging and swings still wait.
- **Return** brings back hanging, swings and heavy grip work.

How to judge the criteria: no pain at rest and a loose fist without sharp pain end protect. Full wrist range and holding a light dumbbell without pain end restore. A pain-free push-up position and grip close to the other hand end rebuild.

- No wrist-specific evidence on phases or criteria was confirmed in this research; the bans and criteria are conservative judgment.
- A 2024 clinical practice guideline covers rehabilitation after a broken wrist (distal radius fracture): prognosis, examination and interventions, graded by evidence. Source: https://pubmed.ncbi.nlm.nih.gov/39213418/ (abstract). Only the abstract was read; it confirms the guideline exists and its scope, not any recommendation, and a fracture isn't a sprain.
- For soft-tissue injuries in general, the PEACE and LOVE authors argue that care should run from immediate care through later loading and exercise, rather than stopping at rest and ice as older acronyms did. Source: https://blogs.bmj.com/bjsm/2019/04/26/soft-tissue-injuries-simply-need-peace-love/. The page is a short summary; it gives no timings, criteria or area-specific advice.

## Neck
The rules treat these as what aggravates a sore neck: load on it (shrugs and heavy carries hang weight from the upper back), overhead loading, crunches that pull on the head, a bar across the shoulders next to the neck, and fast head turns. The catalog has no shrug yet; if one is ever added it needs the `neck-load` tag. Keep the head neutral in everything; cue "chin gently tucked, eyes on the floor a few feet ahead", and keep the head steady in punching drills and turning stretches.

- **Protect** keeps load and fast movement off the neck: most lower-body and core work in a neutral head position, without heavy gripping, overhead work, hanging, crunches or jarring impact.
- **Restore** brings back gripping, light carries with the shoulders down, and crunches that don't pull on the head. Impact still waits.
- **Rebuild** brings back overhead work and a bar on the shoulders, at light loads. Impact still waits.
- **Return** brings back impact, direct neck loading and fast head movement, one at a time.

How to judge the criteria: turning the head slowly both ways without sharp pain, and no numbness or tingling in the arms, end protect (numbness or tingling is a red flag for a clinician, not a phase question). Most of the head's range without pain, and light rows and carries without neck pain, end restore. Full, pain-free head movement and no neck pain the day after light overhead work end rebuild.

- No neck-specific evidence on phases or criteria was confirmed in this research; the bans and criteria are conservative judgment.
- A clinical practice guideline on neck pain (2017 revision) reviews the literature and makes recommendations. Source: https://pubmed.ncbi.nlm.nih.gov/28666405/ (abstract). Only the abstract was read; it states the guideline's purpose and none of its recommendations.
- The general soft-tissue source in the Wrist and hand section (PEACE and LOVE) applies here too, with the same limits.

## Hip
The rules treat sharp bending under load, wide stances and deep side-to-side motion, kicking, landing and lying on the sore side as what aggravates a sore hip. For hip impingement, the consensus below lists conservative care and rehabilitation among the suitable treatments.

- **Protect** keeps load off the hip: partial-range bridges with body weight only, upper body, core in neutral, and only the easiest seated pedalling with a high seat if pain-free. Nothing standing, no lying on either side (the rules can't tell the sides apart), no stretching the front of the hip, and no loaded or single-leg bridges.
- **Restore** brings back standing on both legs, lying on the healthy side, light loaded bridges through a partial range, and light pedalling, still without deep bends, wide stances, kicking or impact.
- **Rebuild** brings back squats and hinges through a pain-free range, wide-stance and abductor work at light loads, and single-leg balance. Swings, being fast hinges, wait for return.
- **Return** brings back landing, swings, side-to-side movement and kicking, one at a time.

How to judge the criteria: no pain at rest or at night, and walking without a limp, end protect. Stairs and a full-range bridge without pain end restore. A loaded squat and hinge without pain, steady single-leg balance on the injured side, and no pain the morning after, end rebuild.

- An international consensus on hip impingement (FAI syndrome) agreed that suitable treatments are conservative care, rehabilitation, and surgery. Source: https://pubmed.ncbi.nlm.nih.gov/27629403/ (abstract). It covers impingement only, and the abstract gives no exercise content, phases or criteria; the bans here are conservative judgment.

## Elbow
The rules treat gripping, hanging, weight on the hands, and arm work that bends, straightens or braces the elbow under load as what aggravates a sore elbow. Tendon pain on the outside of the elbow comes back often, per the guideline below, so the later phases rebuild slowly and heavy gripping stays out until return. This area is new; there was no earlier elbow list to carry over.

- **Protect** keeps load off the elbow. Lower body, core and arm-free cardio carry on, and light band work for the shoulder blades is allowed with a loose grip. Hold any weight for a leg movement close to the body, and skip it if the elbow complains.
- **Restore** brings back light dumbbell pressing and rows, still without grip-heavy work, curls, triceps work or punching drills.
- **Rebuild** brings back curls and triceps work at light loads, lowering slowly, plus push-ups if pain-free. Heavy gripping, hanging and punching drills still wait.
- **Return** brings back heavy grip work, hanging and punching drills.

How to judge the criteria: no pain at rest, and lifting a full cup or turning a door handle without sharp pain, end protect. Gripping and lifting light things through the day, and light presses and rows that leave no pain the next morning, end restore. Grip close to the other side without pain, and moderate curls and presses with no pain the next day, end rebuild.

- A clinical practice guideline on lateral elbow tendinopathy notes that although it's often called self-limiting, high recurrence rates and long sick leave make effective non-surgical treatment matter. Source: https://pubmed.ncbi.nlm.nih.gov/36453071/ (abstract). Only the abstract was read; its graded recommendations on exercise, bracing and activity weren't confirmed, and the bans and criteria here are conservative judgment.
- The general soft-tissue source in the Wrist and hand section (PEACE and LOVE) applies here too, with the same limits.

## Searched without a confirmed source
- The graded recommendations of the neck, elbow, rotator cuff, hip osteoarthritis and broken-wrist guidelines: only their abstracts were read.
- PEACE and LOVE's letter-by-letter advice (how long to protect, loading guided by pain).
- A meta-analysis of balance training and bracing after ankle sprains, and the length of a balance programme in weeks.
- Pain-monitoring limits for shoulder exercise.
- Any evidence on phases or criteria for wrist, hand or neck injuries, and any source that sets ban lists by phase for any area. None was found, so every ban list is conservative judgment.

## Unlisted injuries
The rules file has no area for it, so nothing in it applies: ask what movement hurts and what doesn't, then choose the tags that load, stretch or jar the injured tissue and pass them to `./sweatcast movements --avoid` yourself. Ban anything that loads, stretches, or impacts the injured tissue; train around it; keep it conservative; and recommend checking with a clinician if it's new, severe, or not improving. Write the injury and its rules in `me/health.md`, so the next session applies them the same way.
