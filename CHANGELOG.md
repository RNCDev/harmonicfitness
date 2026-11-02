# Changelog

All notable changes to HarmonicFitness (called sweatcast through 0.19.0). The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

## [0.50.4] - 2026-11-01

Woven Grid in place of Hex Strands, and a larger Bloom.

### Added
- **Web app, Woven Grid:** a coarse grid pushed slowly out of shape, each warped cell divided between its four corners into fine threads both ways, straight inside a cell and bending only where they cross into the next, going over and under like stretched cloth. After Book of Shapes' Woven Grid.

### Changed
- **Web app, Bloom** is half again as large, filling the page, with more strokes so their spacing holds (and those off the page left undrawn).

### Removed
- **Web app, Hex Strands** (0.50.3). An account still set to it shows Flow until another is chosen.

### For forks
- No migration. The `sky` setting takes `woven`, and no longer `strands`.

## [0.50.3] - 2026-11-01

Two new backgrounds for the web app, in place of Lissajous.

### Added
- **Web app, Hex Strands:** a hexagon grid that slowly swells in places and crowds in others (never overlapping), with bundles of parallel lines wandering from cell to cell until a wall stops them. After Book of Shapes' Hex Strands.
- **Web app, Node Garden:** points drifting over the page, each linked to its near neighbours by a line that fades as they part, so clusters gather and break up. After Book of Shapes' Node Garden.

### Changed
- **Web app, Bloom** is a quarter bigger, with more strokes so their spacing holds.

### Removed
- **Web app, Lissajous.** An account still set to it shows Flow until another is chosen.

### For forks
- No migration. The `sky` setting takes `strands` and `garden`, and no longer `lissajous`.

## [0.50.2] - 2026-11-01

Less to read, more held in code. A five-iteration script-writing loop (docs/eval/README.md) on the web coach, the same two 30-minute requests an iteration against one snapshot, two judges a script. The writer reads about 2,630 fewer words a workout turn (a gym brief with a knee limit about 1,200 fewer), and every change kept is code: a 30-minute script reached a priced, checked draft in 104 to 152 seconds (baseline 117 and 129), safety 4 (3 once, from the Copenhagen set-up fixed below), efficacy 3 to 4 and engagement 3 to 4 (baseline 4 / 4 / 3 on both): the gym session's stories got the loop's first 4 from both judges once the rests thought hardest. A fifth iteration, each rest named in the skeleton for the item it tells, doubled the time (236 and 277 s: three times the thinking) without holding the plan, and was dropped. A holdout (a 45-minute upper-body session in a hotel gym) scored 4.5 / 4 / 3 against the baseline's 4 / 4 / 3, at 207 seconds against 164, the difference a silence the writer couldn't find by its words; with that fixed (below) it ran at 188 seconds, 4 / 4 / 3, its silences fixed by segment number with no detour. The holdouts, like the two requests, show the gains are in time held, words removed and faults gone rather than in the scores, which moved within a run's noise. Engagement is still the score to move: stories told as headlines with a tag line after, one big item over three rests, a generic coach.

### Changed
- **Web app, less to read:** passages of the workout skill, `knowledge/script.md` and `knowledge/tts-rules.md` for a computer only (step 1, background research, the CLI's write order and read-through, delivery, backup, the local voice) are marked `<!-- web: skip -->` ... `<!-- web: end -->`, and the web's copy leaves them out (about 1,450 words a turn; the CLI reads them as before). The skill's coaching-first, stories, read-it-through order no longer sits beside the web's skeleton, rests, coaching, one fix.
- **The brief:** the LIGHT ONLY rule is said once above the menu (it was on every limited movement's line, 61 times in a gym brief), and equipment notes come only for equipment a movement on today's menu can use.
- **Web app, contractions:** a draft's stiff forms ("let us", "that is one", "do not") are contracted as it's written, in spoken lines only (never a marker or label, never before a pause or "let us know"): Gemini wrote two or three dozen a script, and every judge quoted them as stilted. The menu scan reads doesn't, can't and the rest as negations, as it read "not".
- **Web app, the ask for words:** a build's "add about N words" is shown twice over the first time, then scaled by how much of the last ask the writer delivered (at most three times): asked for 600 words, Gemini added a third. A draft 15 percent short landed in one fix (three before). The lint's too-short hint no longer suggests stories run fuller.
- **Web app, the rests think hardest:** the request that writes the rests, right after the skeleton, thinks at high (the rest stay at medium and low), at no measured cost in time.

### Fixed
- **Safety:** a movement lying on one side is no longer offered for one side only. With a left knee limit the brief offered the Copenhagen plank "right side only"; its working leg is the top one, the one-side check refuses "left" in its segment, and the writer said "lie on your right side, right knee on the bench" (both judges).
- A long silence's lint issue names its segment and, when it's the cause, its bare `[hold]`; the writer, fixing by segment number, missed one twice and rewrote the draft.
- Web app: an edit whose seconds drift off the clock gets the skeleton's back, as a write does (it was refused, and the writer reran the brief).
- Web app: a long paragraph is never split after initials ("U.S. / Soccer" was heard as a pause mid-name).

### For forks
- No migration. Mark any passage of your own skills that a web turn shouldn't read with `<!-- web: skip -->` and `<!-- web: end -->` on their own lines.

## [0.50.1] - 2026-11-01

The clock before the words. A five-iteration script-writing loop (docs/eval/README.md) on the web coach, two 30-minute requests an iteration against one snapshot, two judges a script: a 30-minute script now reaches a priced, checked draft in 104 to 138 seconds (from 135 and 156; the median run of the last two iterations 114 s), with whole rewrites down from two or three a run to one or none, safety 4 throughout, efficacy 3.5 to 4 (from 3 and 4) and engagement 3 unchanged. The last iteration also tried a one-sentence "shape of a story" in the skeleton's report and dropped it (the judges heard editorializing); the two requests' last runs carried that sentence. A holdout (a 20-minute hotel-room conditioning session) ran at 71 seconds with it in (4 / 3.5 / 3) and at 143 on the released state (4 / 3 / 3: a first draft a quarter short, then seven edits each adding about half the words the lint asked for; the writer's under-delivery on an edit is the next thing to hold in code). The loop found the time went to arithmetic the writer can't do (thirty segment lengths summed to the request, a first draft 15 to 20 percent off its length) and to the whole rewrites that followed; every fix below is a check or a budget in code, and the writer reads 86 fewer words of guidance than in 0.50.0.

### Added
- **The skeleton:** a draft written as its `movements:` line and `@@` lines alone (with the counts and holds each will have) lints to each segment's word budget at the coach's rate (`tts_build.unfinished_report`, the rate from the coach on the smoke test's coaching, `sample_wpm`, which the brief's Talk to time line now shares), so the words are written to the clock rather than fitted to it after. Segments still empty get the same report with the words so far; the draft builds once every segment has words.
- **Web app, the draft in passes:** the skeleton, then the rests (each to its budget, one story), then the coaching, then one fix; each pass with segments still empty is a lint whose report is the budgets, labelled "Planning the script's timing" and "Checking the script so far".
- **Web app, the clock is held in code:** a full draft whose seconds don't add up to the request isn't built; the write says how far off, and which of the skeleton's segments it dropped or added, for one edit (a writer told only the total rewrote the whole draft two or three times). A draft that keeps the skeleton's segments but not their seconds gets the skeleton's back. A skeleton within three percent of the request is settled over its rests, in steps of five seconds (the writer re-planned the skeleton five to seven times to land "add 15 s"); rests over two minutes are named.
- `brief --goal full-body` and `cardio` are `general` and `conditioning` (the page's words; a round trip each).

### Changed
- **Less to read:** the brief's word target ("write about 3,170 words… count them before the first lint": drafts missed it by fifteen percent either way) is the skeleton's budgets; script.md's "What the build checks" paragraph (the build says so), its figures and stacking sentences (both checks in code since 0.49.6) and the close's ask for "what else they're into" (every judge heard app-speak; content.md already says) are gone, as is the web instructions' Logs-page line for the close. The write result's "lengthen it before the first lint" (which read as "rewrite") is gone with the target.
- **Web app, the write tool's labels:** "Planning your script" while the skeleton is designed, "Writing your script" while the draft is.

### Fixed
- A `--lint-only` build of a draft with no words no longer counts every segment as a timing issue.

### For forks
- No migration. A draft is built as before; the skeleton is a new way to start one.

## [0.50.0] - 2026-11-01

The script-writing loop replaces the judged grid. Five loops on 30-minute scripts (0.49.4 to 0.49.6) found a better way to try a change to the writing: real sessions written by the web coach on this computer, timed, and scored by two independent judges against written anchors. The forty-case grid of invented listeners, and the six-part rubric that marked scripts down for faults a listener wouldn't notice, are gone.

### Added
- **`docs/eval/README.md`, the loop:** run a turn with `web/local_turn.py` on a copy of a context folder, time it, judge it, change one thing; prefer a check in code to a sentence of guidance, and fewer rules to more.
- **`docs/eval/timing.py`:** where one turn's time went, from its `history.json` (`web/local_turn.py`'s or a `pull`'s): each model request's seconds, tokens and tool calls, what each draft write added up to, and each build's spread of segment fills and distance from plan.

### Changed
- **`docs/eval/judge.md` is the calibrated three-score judge** (safety, efficacy, engagement, each with anchors; two judges a script, averaged), from 0.49.5's `judge-three.md`.

### Removed
- **The judged grid:** `docs/eval/cases.toml` and `extra-cases.toml`, the four invented listeners (`docs/eval/listeners/`) and their research sheets, `briefs.sh`, the writer's brief, the six-part judge and the last results file. The test that checked the grid went with it.
- **`brief --save` into `docs/eval/out/`:** a brief and its menu are written only beside a draft in the workouts folder.

### For forks
- Anything that ran `docs/eval/briefs.sh`, or saved a brief into `docs/eval/out/`, now gets exit 64 from `brief --save`: run the loop in `docs/eval/README.md` instead. No `me/` migration.

## [0.49.6] - 2026-11-01

Eval loops 3 to 5 on 30-minute scripts, judged with the calibrated three-score rubric (two judges a script, averaged). Loop 3, on 0.49.5 live: full-body at home 4.5/4.0/4.0 in 182 seconds, gym strength easy on the left knee 5.0/4.0/3.0 in 172 (both 50 seconds quicker than loop 2). Loop 4 ran the changes below on this computer, on the web app's own turn code, without a deploy: 5.0/4.0/3.0 in 137 seconds (one write, clean at the first build) and 4.5/4.0/3.5 in 163. A last local loop with everything below: 4.0/4.0/3.0 in 257 seconds (the writer read engine files and fought a figure limit set too tight, both fixed since) and 4.5/4.0/4.0 in 150. Every judge in every loop marked engagement down for the same two things, now held in code: a filing read out as a list of figures, and the coach's own voice missing.

### Changed
- **A short draft is told how many words to add, and where:** "To land on plan, add about 520 words in one edit: #2 +90, #9 +60...", the segments furthest under their guide first (loop 3's drafts came in 9 to 20 percent short and were lengthened "a little" at a time, four full rewrites in one turn).
- **A rest that reads out more than four figures is refused:** a list of numbers isn't something an ear can follow mid-set (every loop told one company's filing as five to nine figures a rest). Keep the one or two that make the point.
- **A full-body session that leaves out a push, a pull, a squat or lunge, or a hinge is warned,** for any of them today's menu allows (no 30-minute full-body script in the evals had a pull until loop 4).
- **The coach's encouragement, without eyes:** the brief follows each coach's encouragement line with how to say it as this coach without claiming to have watched ("if the last two felt clean, that's the standard"); about half the stock coaches' examples ("that was steady", "now that's a strong set") praise what was seen, so drafts dropped the coach's voice for stock praise.
- "Two more crisp reps" and "five more smooth reps" are targets, not claims to have seen the set.
- **Web app, straight to the script:** the coach reads no knowledge files or engine code before writing (the brief and the guides hold what it needs); one loop read three, half a minute.
- **Web app, a draft always builds as it's written:** without `build_name` and `coach`, `write_file` and `edit_segments` take the name from the draft's folder and the coach from the turn's brief (both of loop 3's first writes forgot them, a round trip each).

### Added
- `web/local_turn.py` (maintainer only): one web-app workout turn on this computer, on a copy of a context folder, with the worker's own agent, tools and step 1 and a Gemini key from the repo's `.env`, saving the turn's files and a history `pull`'s shape. Loops 4 and 5 ran on it, minutes apart, with no deploy between.

## [0.49.5] - 2026-11-01

Eval loop 2 on 30-minute scripts, on 0.49.4: 233 and 223 seconds to a priced script. Judged now with a calibrated three-score rubric (`docs/eval/judge-three.md`: anchors for each score, two independent judges a script, averaged), which also re-scored loop 1 as a baseline: the earlier one-judge "find eight problems" prompt marked the same scripts a point or two lower. Full-body at home 5.0/3.5/3.0 (loop 1: 5.0/4.0/3.5); gym strength easy on the left knee 4.5/4.0/3.0 (loop 1: 4.0/3.0/3.0): 0.49.4's hard-set line gave the gym session three sets of four lifts. This release is a simplification: fewer, plainer rules, and less to read before the first word.

### Changed
- **Engagement as a recipe, not a list of rules** (`knowledge/script.md`): one coach being a good podcast host. A rest holds one story, told the way a friend would: why it's theirs, what happened, the one detail or number that lands, what it means for them; never a list of figures (loop 2 read nine numbers from one filing across three rests), never a stock tag line to end it; their taste counts as much as the news; the coach's own voice, with contractions; a self-check offers the harder option too where no limit touches the movement. Fourteen bullets became seven, keeping the listener's quick hits in the work.
- **The brief is shorter:** the menu leaves every movement's coaching notes to `movements --about` (a limited movement's too; its load on the limit and LIGHT ONLY stay on its line), and the programming guide prints only the rules that bear on the session's goal. A 30-minute gym brief with a knee limit went from 12,071 words to 7,301.
- **Web app, less to read and less thinking:** the research templates (for a computer's research agents and sheets) no longer come with the skill; the research and writing instructions are a third as long; Gemini thinks at medium while designing, writing and fixing the script and low between (its default thought for 3,000 to 9,500 tokens a request: a 96-second write, two thirds of it thinking).

## [0.49.4] - 2026-11-01

Eval loop 1 on 30-minute scripts: full-body at home and gym strength easy on the left knee, on 0.49.3, timed to a priced script and judged blind on safety, efficacy and engagement: 213 seconds, 4/3/2; 284 seconds, 4/2/2. The time went to round trips (72 seconds before the first word, a full rewrite after a word-count nag, up to five fix rounds), and the scores to too little work and loose stories.

### Fixed
- **The feeds sheet on the web was never fetched again after the day's first:** a sheet's freshness came from its file's time, and the web app writes every file afresh at each job, so a morning sheet (fetched before 0.49.2's time-zone fix, in the server's UTC) was read all day, shifting game nights by one and calling the morning's weather "right now". Freshness now comes from the time in the sheet's own header, and a sheet dated ahead of now is stale.
- **"Eight to ten clean reps" isn't a claim to have seen the set:** the check skips a rep target, and now catches more claims that are ("great execution", "with fantastic control", "outstanding carry", "you held your posture clean").

### Changed
- **The lint's segments off their slots say "trim it" only when the total is off.** With the total in range they're a note ("leave them as they are"): loop 1's first script spent 35 seconds fixing 14 segments that needed nothing.
- **The brief says how much work fits:** "about 11 hard sets in its 1350 s: three sets of each main movement, never two", rests at the dose's length (never longer to fit a story), and a welcome under a minute (loop 1's gym session had two sets a lift and 90-second rests filled with three stories each). Experienced and advanced listeners start each main movement at the heaviest weight that fits its reps; a kit with no weights listed (a gym preset) names loads by effort, never by pounds from another kit.
- **The brief's word count is what a clean lint holds:** 72 percent of the coach's words a minute times the minutes, from 76 (drafts that linted clean at 30 minutes held 3,000 to 3,250 words; the brief asked for 3,350, and the nag sent a draft that was fine to a full rewrite).
- **Web app, a draft builds as it's written:** `write_file` and `edit_segments` take the build's name and coach and run the build (its lint, then its price when clean) in the same call: one round trip a fix, not two.
- **Web app, long paragraphs are split by the site:** a clip over 225 characters (about 20 seconds at the slowest web coach's pace) is split at a sentence break as the draft is written, rather than refused by the lint a round trip later (one in every lint of loop 1's second script).
- **Web app, quicker to the first word:** `run feeds` hands over the whole sheet, so it isn't read again; a research sheet a computer wrote today comes with step 1; the coach doesn't run `brief --help`, list folders step 1 named, or read earlier drafts (38 seconds in loop 1).
- **Web app, stories:** one to a rest; an edit never changes a story's names, numbers or dates (loop 1's comedy listing changed between drafts); no analysis the source didn't give, and no age, date or tally worked out from memory; nothing under "Already told today" again (a Devils result from the morning was retold); fix only the build's issues, and of its warnings only claims to see them, repeats and stacked stories.

## [0.49.3] - 2026-11-01

Eval loop 2: the same two 25-minute requests on 0.49.2, judged blind on safety, efficacy and engagement: full-body at home 4/3/2, gym strength easy on the left knee 1/3/3. The 1 was a "heavy dumbbell" for a suitcase carry under the knee limit, which 0.49.2's new check missed; it's caught now, and so is a wider gap it exposed.

### Fixed
- **A movement named in the plural of a "-y" word is recognised** ("suitcase carries", "farmer carries"). The menu's text scan matched "-s" and "-es" plurals only, so every check built on it (a movement off the menu, one side only, light under a limit) missed these. This was a safety gap in the build's menu check.
- **"Heavy" with a limited movement, wherever it's said:** the check now reads a segment's label too, and when a segment names no movement (a rest setting up the next set, "pick up one heavy dumbbell"; a second set that only says "that heavy bell"), the movement of the set it sets up or follows.

### Changed
- **A second session in a day keeps a whole-body session whole:** what the morning trained stays in, light and short, rather than left out (loop 2's full-body script had no pull and no hinge), and nothing the morning told is told again: the content plan lists it under "Already told today" (a hockey item was retold four hours later).
- **The weights by name:** each loaded movement's first set names its load from the kit ("the fifteens", "set the bell to thirty-five"), never "your dumbbells" alone.
- **Stories:** the build warns when a segment tells three or more stories (one story to a rest); a story keeps at least one of its source's numbers, adds no colour, quote or play-by-play the source didn't give, and comes only from the plan's topics. On the web, a topic whose search found nothing current gets no news (loop 2 told Yankees news the research had marked unconfirmed), and the feeds sheet wins over a search that disagrees.
- **Web app, a limit from the first screen's sentence is for today:** the coach passes it as `--limit` and never asks whether it should last (loop 2 stopped to ask), and doesn't recite the red flags unless the listener describes pain.
- **Web app, a draft far from the brief's word count is told so:** `write_file` and `edit_segments` compare the draft's words with the brief's count and say how far over or under, before the first lint (loop 2's first draft was 24 percent over).
- More claims the coach can't make are warned on: "solid discipline", "solid work", "crisp technique".

## [0.49.2] - 2026-11-01

Eval loop 1: two 25-minute web scripts (full-body at home; gym strength going easy on the left knee), judged blind on safety, efficacy and engagement: 4/3/3 and 3/3/3. What the engine now holds because of them, and quicker turns (231 and 242 seconds, 11 model requests each: a 60-second full rewrite after each first lint, and half a minute on a research sheet nothing reads).

### Changed
- **Light loads under a limit, checked:** the build refuses "heavy" (or "max load", "go big") in a segment's coaching that names a movement loading one of today's limited areas ("Pick up a heavy pair" for a farmer carry with a delicate knee); "nothing too heavy" passes. The brief marks each such movement on the menu "LIGHT ONLY today: twelve to fifteen reps with three or more in reserve".
- **A second session in a day:** when the last session was today, the brief says so, names the patterns it trained, and says to leave them out or keep them light and never call a same-day repeat progress (both scripts ignored a session from that morning; one repeated its hinge).
- **A whole-body session covers a push, a pull, a squat or lunge and a hinge** (the brief's programming guide; a "full-body" script had no pull, with pulling untrained all week).
- **No padding stories:** a short segment gets more coaching or a question, never a story detail the source didn't give (a relative, a degree); paced breathing gets a hold as long as its count.
- **More claims the coach can't make** are warned on: "executed with clean form", "completely protected", "crisp deadlifts".
- **Web app, the listener's clock:** every engine command in a turn runs in the listener's time zone (from the time their page sent), so the brief's "written at" and the day the brief and the build check are theirs, not the server's UTC.
- **Web app, quicker to a draft:** the brief gives the session's word count to write to (about three quarters of the coach's words a minute times the minutes: drafts written by feel came in nine to twelve percent short); `write_file` and `edit_segments` report the draft's words with its seconds; a lint's fixes always go in one batch (a full rewrite only when the plan changes); `content.md` and `settings.toml` come with step 1; and no research sheet is written on the web.

## [0.49.1] - 2026-11-01

Fewer round trips to a finished script on the web app.

A 20-minute script on 0.49.0 (job 65) took 256 seconds and 36 model requests: the first draft came in 12 percent short with its segments adding up to 19 minutes rather than 20, and Gemini then fixed the lint's complaints one segment a request, 27 requests at about four seconds each.

### Changed
- **Web app, `edit_segments` in place of `edit_segment`:** every fix one lint names goes in one call (each edit a segment's place and its whole new text), all or nothing. The coach is told never to fix one segment a call, and to write the whole draft again in one go when most segments are off.
- **Web app, a draft says what it adds up to:** `write_file` and `edit_segments` reply with the draft's segment count and total seconds, so a length that misses the request is fixed before the first lint.
- **Drafts are written to length:** the web coach's instructions and the brief's Talk to time line say first drafts come in 10 to 15 percent short and to write each segment to its full time (about 2.4 words a second at 144 a minute, less holds and counts).
- **Web app, step 1 names today's workout folders,** so the coach doesn't list them to pick the day's stem.

## [0.49.0] - 2026-11-01

The coach learns what you like. Feedback, ratings and the things you tell it you enjoyed become evidence that builds with each signal and fades without one, so a one-off mention drifts away in a few months while what keeps coming back rises: a year of comedy nights and the sessions lean that way.

### Added
- **Interests as evidence** (`tools/interests.py`, `./harmonicfitness interests`; `me/workouts/research/interests.jsonl`): each signal is a topic, venue, taste, movement or effort, weighted -2 to 2, from a mention, a feedback line or a rating, with its day and, for a person or narrow subject, its broader topic (a comedian's: stand-up comedy). Strength halves every 90 days and a parent gets half its children's, so related interests build each other up. `add` (at most twelve at once), `forget`, `apply`, `--json`. Tuning is in `knowledge/content.toml`'s `[interests]`, every number a house default.
- **What's learned is used:** learned topics join the content plan's rotation (never told first, then strength times the days since each was told, so a strong interest comes round sooner); learned venues join What's on and learned taste its recommendations; learned likes join the menu's, and a firm dislike leaves a movement off it; "too easy" or "too hard" leans the brief's doses that way for a while. Your own lines in content.md and training.md are pinned: they never fade or drop, and nothing under Never bring up is ever learned.
- **A "Learned from you" section** in content.md and training.md, rewritten after each change, strongest first, with where each came from. It's the coach's own section: your lines are never moved or rewritten.
- **Ratings teach a little:** a positive or negative rating is a small signal on each topic that workout told, replaced if you rate again; deleting a workout takes its evidence back.
- **Web app, feedback is worked out in the background:** a feedback line on the Logs page starts an `enrich` job on your writer key (one request, with web search to pin down a name), which records what it teaches and shows a short note under the workout ("Noted: more stand-up, and a little harder next time"). It runs in a lane of its own (a second worker loop, started again if it ever stops), so it never waits behind a workout or holds one up. Each feedback line costs one model request, and up to a couple of searches, on your writer key; without a writer key nothing is queued.
- **Web app, "Tell me what you enjoyed"** on the first screen fills in "Lately I enjoyed " for you to finish: a show, a meal, a game. The coach works out who and what it was (the comedian and the venue, the chef and the cuisine), records it, and says what it picked up.
- `./harmonicfitness workouts context <n>`: a workout and what's known about the listener, as JSON (the enrich job reads it).

### Changed
- Pain or soreness in feedback is raised at the next check-in, as if just said; feedback never changes health.md by itself (the enrich job's output has no field for it).

### For forks
- The web app's database gains migration 015 (the enrichment lane's unique indexes), applied on start; the worker runs a second loop for the `enrich` lane. `POST /api/workouts/{ref}/feedback` now answers 202 with `{"job_id"}` instead of 204.
- No `me/` migration: the evidence file and the Learned sections are new and optional, and a folder without them reads as before.

## [0.48.1] - 2026-11-01

Sets timed to how fast people really move, shows at your venues, quick hits in the work, a coach on the web that can search, and a close that asks for your word.

### Added
- **Web app, the coach can search the web:** the writer's own provider search (Gemini's Google Search, Claude's, ChatGPT's or OpenRouter's), billed by that provider on the listener's key, about six searches a workout after the check-in: the topics due the feeds don't cover, what's on near them, and quick hits for the work. Before, research on the web had only the feeds and the stock, and skipped a topic they didn't cover. The turn's log line counts the searches.
- **Venues** (`## Venues` in `me/content.md`, `context.venues()`): places whose upcoming shows, talks and exhibitions the listener wants to hear about, one `- name: note` line each. A kind of show they like (singer-songwriters, stand-up, talks, the arts) is a topic as before, and research also looks at the major venues near their neighborhood for it. The setup skill asks for venues with interests and taste, and "add the Bell House" puts one there.
- **A What's on format** (`whats_on` in `knowledge/content.toml`): an upcoming show near them, who, where, which night and why it's theirs, from a listing page; never a price or "sold out" not seen there. `content plan` lists the venues under What's on (`--json`: `venues`).
- **Quick hits in the work** (`quick` in each `[[band]]`: 2, 4 or 6 by length): once a movement has had its full coaching, a later set that isn't hard trades a repeated cue for one or two sentences (on this day, a number, what's on, a quick fact), in `[story]`; never in a hard set, its last reps, or in place of a safety line, limit cue or count. `content plan` says how many (`--json`: `quick`).
- **The close asks for their word:** how hard it felt and what else they're into, so the next stories fit better; on the web app, the Logs page and the chat. Said a new way each time.

### Changed
- **Reps are planned a quarter quicker** (`[timing] rep_pace = 0.75` in `knowledge/sessions.toml`): the brief multiplies each catalog `seconds_per_rep` by it, so ten reps of a three-second movement are planned at about 22 seconds, not 30 (listener feedback: sets often finished at twice the audio's pace). `knowledge/script.md`'s example set is shorter to match, and says not to stretch a set past its time.
- Today's research may search a little more (ten searches and six page fetches, from eight and five) for what's on and the quick hits.

## [0.48.0] - 2026-11-01

A faster script on the web app, recording without the Record button when you want it, and a look at what the coach did.

A web workout's script took about four and a half minutes (job 60, 2026-11-01: 65 seconds of one-at-a-time reads and checks, a 76-second first draft, then two failed lints, each answered by writing the whole script again, 44 and 33 seconds, then about 27 seconds to check and price it). The changes below take out the reads, the second and third full writes and two of the checks; the new log lines will say how much the next one saves.

### Added
- **Web app, Record without asking** (Settings, Recording; off unless turned on): once the script is checked and priced, the coach records it in the same turn, with no Record button and no wait. Today's allowance still applies: the characters are reserved first, as the Record button does, and past the allowance the Record button comes back and says why (`users.auto_record`, migration 014; `PUT /api/auto-record`; `GET /api/me`'s `auto_record`).
- **Web app, `edit_segment`:** the coach fixes a lint's complaint by replacing the segments it names (by the lint's # column), not by writing the whole script again.
- **`./harmonicfitness pull` saves `history.json`:** the model's side of the conversation, every request, tool call and result with their times, from `GET /api/conversations/{id}/history` (its owner only; the page never shows it).
- **The worker's log times each step:** every tool's line says how long it took, each model request has its own (`think 76.1s`), a command's subcommand is named (`run get web-builds`, `run build --lint-only`), and each turn ends with its seconds, model requests and tokens in and out. Never what was read, written or said.
- **A web voice's lint says what it sends** ("Sends 4,812 characters to the voice service"), so a build's price needs no second lint to count it.

### Changed
- **Web app, fewer round trips before the script:** step 1 also runs `get web-builds` and plans the rests for the length the request names (it used `25` and the model ran it again); `knowledge/script.md` and `knowledge/tts-rules.md` come with the skill in the instructions instead of being read one by one; and today's feeds start in the background on the first turn when a set-up listener's first message asks for a workout (the page's sentence is the check-in), rather than a turn later.
- **Web app, one check to a price:** the coach runs the build straight away (it lints first) rather than a `--lint-only` step and then the build, and a draft that just linted clean with the same coach isn't linted again to be priced. The draft is written once, read through as it's written, then fixed by segment.

### For forks
- The web app's database gains `users.auto_record` (migration 014, applied on start). The engine's commands and `me/` work as before; a web app older than 0.48.0 ignores the new lint line, and `pull` against one saves no `history.json`.

## [0.47.0] - 2026-11-01

A tidier first screen on the web app.

### Changed
- **Web app, the request sentence is larger and airier:** the "Hey, coach ..., I'd like a ..." sentence scales up to about 70px (from 62px) with more line height and a little space between its two lines.
- **Web app, the note after Plan my workout is gone** ("Your coach plans it with you, then records it once you say go."). "Add a voice key in Settings first." still shows when no voice is set up.

## [0.46.2] - 2026-11-01

One key does it all: OpenRouter writes the workouts and voices six ready-made coaches, and Gemini gets six ready-made coaches of its own in place of Coach Nolan. On the web app, a Coaches page beside Logs where coaches are chosen by ear, never made; a simpler Settings; a coach who asks one question at a time and does one job per request; two new backgrounds; and a little more room around the logo's H.

### Added
- **OpenRouter as a voice service** (`openrouter` in `knowledge/services.toml`, `tools/services/openrouter.py`, `OPENROUTER_API_KEY`). OpenRouter can't design or save a voice, so its coaches are stock voices: ElevenLabs' 21 (on `elevenlabs/eleven-v4-turbo` by default, about $0.80 a workout, or `eleven-v4`, $1.60) and Microsoft's 12 English MAI-Voice voices (`microsoft/mai-voice-2.1`, about $0.44). An audition offers the three closest to the coach's description (gender, accent, age and a few sound words), and keeping one saves nothing at the service. Speech is asked for as MP3 and read through ffmpeg. `balances` reads its credit left.
- **OpenRouter as a writer on the web app** (`web/webapp/providers.py`, model `anthropic/claude-sonnet-5.5`, no retries). Its key is stored under the same id as the voice service's, so one key and one row on the Keys page do both.
- **Six ready-made Gemini coaches** (Fraser, Freya, June, Miles, Ruby, Wade; `coaches/coach-<name>-gemini/`), each one of Gemini's own voices by id (its prebuilt voices and its voice library's, which `GET /v1beta/voices` lists with gender, accent and pitch): three American voices, a Glasgow, a Southern US and a Midwest one. Like OpenRouter's, they belong to no account, so they ship made with a sample and a pace estimate; `[[web_coach]]` rows take a `service` (openrouter unless named), and `tools/coachmaker/web_coaches.py gemini` makes one service's. `gemini.delete` never sends a delete for one of Gemini's own voices.
- A service module may name the model that speaks each of its voices (`voice_model`): an MAI voice is billed, keyed and spoken as MAI's even though the service's default model is ElevenLabs'.
- **Six ready-made OpenRouter coaches** (Rowan, Graham, Jonah, Leah, Nora, Tess; `coaches/coach-<name>-openrouter/`, from `coaches/roster.toml`'s `[[web_coach]]` tables by `tools/coachmaker/web_coaches.py`, maintainer only). A stock voice belongs to no account, so unlike every other web coach they ship made: each with its 45-second `sample.mp3` and a pace estimate (`pace.json`), which `voices.pace` reads until a render here measures it. They replace the stand-in Coach Rowan.
- **`./harmonicfitness keys upload`** (`tools/webkeys.py`): sends the keys in `me/.env` to the listener's key store on the web app, signing in as `pull` and `sync` do. A key the app already holds stays unless `--replace`; `--only` and `--dry-run`; no value is ever printed. It also sends `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` when `me/.env` holds them (the web app's writers; the engine never uses them, and they're scrubbed like the rest).
- **`coaches list --json`** says each coach's `tone`, whether a `sample` ships, and `usd_per_workout`.
- **Web app, the Coaches page** beside Logs: every coach as a card, with how they talk, a workout's cost, a sample where one ships (`GET /api/coaches/<slug>/sample.mp3`, the engine's own files only), and Choose, or the key it needs (which opens that key's row in Settings without changing who writes).
- **Web app, the first key decides the rest.** The welcome offers the four keys, OpenRouter and Gemini first (they also voice). With Gemini's or OpenRouter's key the first screen is ready, and the other voice keys wait behind "Add another voice". With Claude's or ChatGPT's, the first screen says "One more step: choose your coach" and opens the Coaches page.

### Changed
- **The logo's H meter stands a little apart from ARMONIC:** 12% of the cap height more room before the A (`H_GAP` in `assets/brand/make.py`), since the meter is heavier than a letter. The wordmark with the meter H (`assets/brand/wordmark-h*`, and the web app's header through `brand.ts`) was made again; the icons and lockups are unchanged.
- **Web app, the coach asks one question at a time:** each reply asks a single question (lettered options, its pick first, any answer in their own words) and waits, for setup and the check-in alike, in place of one numbered list of questions. A question whose answer is already known is skipped.
- **Web app, one request, one job:** "change my equipment", "update an injury" or "update my interests" (the first screen's shortcuts) does that job alone: its questions, the file written, `check`, a line on what changed; no check-in, plan or setup questions. A listener not set up yet gets the setup questions only with a workout request or when they ask to be set up (`agent.intent`), so a shortcut never starts the whole interview.
- **OpenRouter's coaches speak on ElevenLabs' Turbo model** (`elevenlabs/eleven-v4-turbo`), the same voices at half the price: about $0.80 a workout instead of $1.60. Their samples were recorded again on it. The web app says "OpenRouter, powered by ElevenLabs" above them (`coaches list --json`'s new `powered_by`, from the service module's optional `powered_by(model)`).
- **Coach Nolan is gone:** Gemini's stock coach, designed in the listener's account on first use, gives way to the six ready-made ones. A Nolan a listener already made stays theirs in `me/coaches/` and keeps working. Where a service ships several coaches, its stand-in is the first by name (`routes.stand_ins` now agrees with `coachpick.default`: Fraser on Gemini, Graham on OpenRouter).
- **Web app, the Coaches page shows only the coaches your keys can voice,** with one line naming the services whose key would add more. With no voice key yet (a Claude or ChatGPT key alone), it shows every coach grouped by service, samples playable, with one Add key button a service.
- **Web app, the first screen** puts "Finish setting me up" first while setup isn't finished, a little brighter than the rest (a cream rule, its arrow showing); it no longer offers "Pick a different coach" (the Coaches page does) or "Give feedback on my last workout" (the Logs page does).
- **Web app: coaches are chosen, never made.** The Coaches page replaces the coach list in Settings (keys only now). The assistant no longer auditions: `coaches audition` and `coaches keep` are refused in web mode (by the agent's tools and by the engine), and the coach skill loads only to close an audition left open. A coach someone made before stays theirs; a coach of their own is made on their own computer.
- On a phone, the header's Coaches and Logs show as icons.
- **Web app, Settings simplified:** OpenRouter and Gemini head the writers, each marked "+ voices"; each key row keeps its name left and its buttons right, with the date and balance beneath; an unset key shows just Add; shorter notes under Keys and Your files; the right column no longer stretches.
- **Web app, the Coaches page** uses the whole width, with compact cards (a description of three lines at most) and a small player of its own in each (one sample plays at a time). A tap anywhere on a card chooses that coach (it lifts under the pointer; the play button never chooses), and the cards stay in alphabetical order, so choosing one only rings it. Its one colour is a soft blue (`--blue`): the coaches' names, the samples, and the coach coaching you, ringed in blue with Active on its top edge.
- **Web app, backgrounds:** Arcs is gone (Book of Shapes' licence asks that its Brockmann Beethoven Arcs not be published); an account set to it shows Flow, with no migration. Two new ones, after Book of Shapes: **Bloom** (its Phyllotaxis Bloom: short strokes set out like a sunflower's seeds, large enough to run off the page, turning slowly, a soft pulse passing outward) and **Lissajous** (its Lissajous Field: a 2:3 figure in short dashes, large enough to run off the page, turning slowly). `PUT /api/sky` takes `flow`, `field`, `waves`, `bloom` or `lissajous`. Background now credits Book of Shapes and Nikolaj Sokolowski.

### Fixed
- **Web app:** a coach's sample is no longer cached for a day (`Cache-Control: private, no-cache`, answered with 304 when unchanged), so a re-recorded sample is heard at once.
- A refusal whose reason sits under `error.message` (OpenRouter's shape) is now said in words, not as raw JSON.

### Not yet tried
- A full workout on an OpenRouter coach, and a web app session written by OpenRouter. Speech on both voice families, the writer, `coaches make` and the balance were tried live on 2026-10-31.

### For forks
- Nothing to migrate. Coach Nolan is gone from `coaches/`: a listener who made him keeps their copy in `me/coaches/`, and one who never did gets the first of Gemini's six (Coach Fraser) as a stand-in, or names another.
- The web app offers OpenRouter as a writer only where `HARMONICFITNESS_PROVIDERS` is unset or names `openrouter`.

## [0.46.1] - 2026-10-31

A new logo: the H as a level meter.

### Changed
- **The logo** is now the wordmark with its H drawn as a stereo level meter: two channels of segments and a middle bar, half again as tall as the other capitals and centred on them, coloured Ember (deep coral at the foot, the brand's coral above, a pale flare at the peak). It replaces the coral trace from 0.43.0 in every file `assets/brand/make.py` writes: the lockups, the new `wordmark-h` files (the main logo), the mark alone in three sizes (`mark.svg`, the new `mark-mid.svg`, `mark-small.svg`), both app icons, the favicons and the web client's `brand.ts`. `make.py` now also needs `coloraide` (its README has the command).
- **The web app's logo moves where there's sound:** the header's H reads like a live meter while your coach is working or recording, and a small meter beside each workout's player, in the chat and on Logs, moves while it plays. It holds still otherwise, and for anyone whose system asks for reduced motion.

### For forks
- Nothing to migrate. A fork with its own brand keeps its `assets/brand/` and `brand.ts`; `Mark.tsx` now reads segments from `brand.ts` (`MARK`, `WORDMARK_H`) where it read one line.

## [0.46.0] - 2026-10-31

A tidy-up: Railway's leftovers gone now the web app runs on Fly, and the old names kept for one release removed.

### Removed
- **Railway:** `.railway/` (its infrastructure as code), the `RAILWAY_GIT_COMMIT_SHA` build argument in the `Dockerfile` and its fallback in the page's version, and the Railway notes in `.gitignore` and `.dockerignore`. The web app has run on Fly.io since 2026-10-28; `web/README.md`'s Deploy section now describes Fly (`fly.toml`, the CI deploy, `fly ssh console` for admin).
- **Old names, as promised for this minor release:** `personas.default`, `personas.resolve` and `routes.pick` (use `coachpick.default`, `coachpick.resolve` and `coachpick.pick`); the `coaches` module's re-exports of `tools/audition.py` and `tools/coachmake.py` (`coaches.keep_web`, `coaches.make`, `coaches.forget_audition`, `coaches.audition` and the rest: reach them in `audition` or `coachmake`); and `menu._part_of` (use `menu.part_of`). The `coaches` command itself is unchanged. Two import cycles went with them.

### For forks
- Code that called one of the removed names calls it in its own module (above). Nothing to migrate in `me/`; the web app's database is unchanged.
- A fork deploying on Railway keeps its own copy of `.railway/` and passes the commit as `--build-arg GIT_COMMIT_SHA=...`.

## [0.45.0] - 2026-10-31

`me/` on your computer and your files on the web app, kept in step.

### Added
- **`./harmonicfitness sync`** keeps `me/` in step with your files on the web app, both ways, signing in with `HARMONIC_USERNAME` and `HARMONIC_PASSWORD` from `me/.env` as `pull` does. A file changed on one side goes to the other (edits, new files and deletes alike); one changed on both is a conflict, where this computer's copy stays, the web app's is saved in `me/web/conflicts/<date>-<time>/`, and the next sync sends this computer's (`--prefer web` or `--prefer local` settles it at once). `--dry-run` says what would change. The first sync deletes nothing. It never sends `.env`, MP3s, WAVs, the clip cache, render logs, lock files, auditions in progress, backups or git, and keeps its record of the last sync in `me/web/sync-state.json`.
- **The web app's sync routes:** `GET /api/sync` (each file's path, version and sha256), `POST /api/sync/read` (bodies) and `POST /api/sync/write` (each change applied only over the version the computer last saw; a file changed on the site since is a conflict, left as it is). The listener's own session, as the browser has.

### Changed
- **`me/web/` is this computer's own:** `pull`'s copies, sync conflicts and the sync record. `me.example/.gitignore` leaves it out of a backup, and `migrate` (and the first `sync`) adds `web/` to an existing `me/.gitignore`.

### For forks
- Nothing to migrate: `./harmonicfitness migrate` (or the first `sync`) adds `web/` to `me/.gitignore`. A fork's web app needs no database change.

## [0.44.0] - 2026-10-31

A recording is final once it's made, nothing it made is lost after it, and a workout may run five percent off plan.

### Changed
- **Five percent, not three:** the whole workout is held within five percent of plan (`draft.TOTAL_TOLERANCE` 0.05), so the lint asks for four and a half with a measured pace and four with an estimated one. Exit 2 now means the total ran more than five percent off, and the MP3 is delivered as it is (copied to `deliver_to`, the web copy made, an outcome line `delivered` with its `drift`), where before it stayed in the workout folder; the workout skill no longer rewrites the script and builds again. The smoke test off plan still stops, measuring nothing.
- **One approval, one recording (web):** pressing Record approves one recording. Once it has made an MP3 (exit 0, or 2), the workout is final for the turn: the site refuses another build of it, or a rewrite of its draft, and a new recording needs a new price and Record. A recording that fails spends its approval too, so a retry is priced again.
- **Your daily recording allowance on the web app** is tripled, to 180,000 characters a day (`HARMONICFITNESS_DAILY_CHARS`).
- **Quieter steps:** a command the site refused (the coach's own mistake, which it fixes and retries) no longer shows as a failed step.

### Added
- **Logs plays a workout's MP3** while the site keeps it (24 hours after recording), with a download. Each kept MP3 names the build that made it, and the workout list carries it.

### Fixed
- **What a recording made is kept at once (web):** the files written back (a coach designed for the recording among them), the clips and the MP3 are saved the moment the recording finishes, so a turn that stops or fails afterwards loses none of it. Before, a turn that went on after recording and was then stopped lost everything, and the next recording designed the coach's voice again at the service.

### For forks
- The web app's database gains `media.build_id` (migration `013_media_build.sql`, run on start). Nothing to migrate in `me/`.
- A fork that relied on exit 2 at three percent passes `--tolerance 0.03` to `build`. A script that read exit 2 as "nothing delivered" now finds the MP3 delivered.

## [0.43.2] - 2026-10-31

The web app says more truthfully what a recording is doing.

### Changed
- **A recording counts as it goes:** while a web coach records, the step reads "Recording your workout: 18 of 40", from the pieces the build has sent (its log's `[n/m]` lines, read by the worker as they land, at most every two seconds).
- **A total off plan is done, not failed:** a build whose total ran more than three percent off plan (exit 2) still made the MP3, so the step ends done, as "Recording your workout (a little off its planned length)", not with the failure's coral dot.
- **After the recording, it's wrapping up:** files the coach reads once the recording is made (say, to see why its length was off) show as "Wrapping up", one line, not "Looking at your workout" and "Getting to know your coach" again.

### Fixed
- **The worker reconnects** when the database closes its connection (it did about hourly, "SSL connection has been closed unexpectedly"), rather than exiting and restarting the machine. A job running at that moment fails as any interrupted job does.

### For forks
- Nothing to migrate.

## [0.43.1] - 2026-10-31

Settings shows what's left on each voice service's account, where the service will say.

### Added
- **Balances in Settings:** a set Fish Audio key shows its API credit ("$12.50 left") and a set ElevenLabs key this period's credits left, each a link to the service's billing page (hover for used of limit and the reset day). Gemini, Inworld, Claude and ChatGPT don't report a balance to a plain API key, so their rows show a link icon to their billing pages instead. A key that's refused, or a check that takes longer than 90 seconds, falls back to the icon.
- **`./harmonicfitness balances [--json]`:** the same, on the command line, from `me/.env`. Each service module may have `balance()` (one GET that spends nothing); `knowledge/services.toml` gives every service a `billing_page`.
- **The web app:** `POST /api/balances` queues a `balances` worker job (the web process still never opens a key), `GET /api/keys` adds each row's `billing_page` and `reports`.

### For forks
- Nothing to migrate. A fork's own service in `services.toml` needs a `billing_page` (an https address), which `validate()` now checks. The Claude and ChatGPT billing addresses (`web/webapp/providers.py`) are the consoles' usual ones, not checked signed in.

## [0.43.0] - 2026-10-30

A new logo, for the web app's Moonrise look: one coral line, a burst of sound, and the name in the app's own display face.

### Changed
- **The mark** is one line in coral: a burst of sound that fades both ways, the loudest crest in the middle (a cosine under a Gaussian; `assets/brand/make.py` has the numbers). Five lobes below about 60 px, three below 40. The seven rounded sound bars are gone.
- **The wordmark** is HARMONICFITNESS in Big Shoulders Display Bold (SIL Open Font License), the face the web app's headings and request use, outlined so nothing needs the font; FITNESS at 62 %, as before. Inter Tight goes.
- **The web app's header** draws the new lockup (`web/client/src/Mark.tsx`, from `brand.ts`), its caps 19 px and the line 25 px tall; the favicon, the ICO and the Apple touch icon are remade.
- **`assets/brand/`:** the lockups, wordmarks, app icons and favicon are remade; `mark-reversed.svg` is gone, since the coral mark is the same on light and dark; the README has the new construction and colours (coral `#FF5A3C`, ink `#111215`, cream `#EDEAE0`).

### For forks
- Nothing to migrate: the brand is the engine's. A fork that copied `web/client/src/brand.ts`, `Mark.tsx` or the icons takes the new ones.

## [0.42.3] - 2026-10-30

### Changed
- **The web app's version** moved from the top header to the foot of Settings, under Account. The sign-in page still shows it.

## [0.42.2] - 2026-10-30

A Logs page in the web app: every workout you've done, its script, your feedback and a rating.

### Added
- **The Logs page:** a Logs button beside the settings gear opens your logged workouts, newest first: each one's date, length, format, kit, coach, movements and topics, the script it spoke (on request), your feedback, a rating (positive, neutral or negative; press it again to clear it), a box to add feedback, and delete (after a confirm, taking its log line, stories, feedback and files with it). Search, filter by rating, format and kit, and sort by date, length or rating. The chat stays as it was behind it.
- **`./harmonicfitness workouts --json`, `workouts show <n|build id>`** (the script a workout spoke) **and `workouts rate <n|build id> positive|neutral|negative|none`.** A rating is a feedback line ("rated positive"), so the coach reads it with the rest; rating again replaces it.
- **Web routes** for the page: `GET /api/workouts`, `GET /api/workouts/{ref}/script`, `POST /api/workouts/{ref}/feedback`, `PUT /api/workouts/{ref}/rating`, `DELETE /api/workouts/{ref}`.

### Fixed
- **`workouts delete --files` on the web** found no folder, since the build record's draft path pointed at an earlier run's temporary folder; a workout's folder is now found from its own `<name>.build.json`.

## [0.42.1] - 2026-10-30

The easy fixes from a thirty-script eval of 0.42.0 (`docs/eval/results-2026-10-30-run2.md`: safety 4.90, efficacy 4.17, adherence 4.43, ease 3.90, warmth 4.33, stories 4.43).

### Fixed
- **First drafts came up short:** the lint's guide column counted holds, counts and chimes into its words-a-minute, so a talk-only rest's guide ran a fifth to a third short; it now counts speech alone, around each segment's fixed time. The brief and `programming.md` now say a paired set takes about a minute and a half with its rest, not one. Writers had filled the gap with spare stories; the lint's "too short" advice now asks for fuller coaching and stories first.
- **An off-limits low back stripped all core work:** the dead bug (and its bench and ball versions), bird dog and Pallof press rate the low back 0, as the injury playbook's "neutral-spine core work continues" says.
- **An off-limits calf kept the bike, treadmill walk, elliptical and marching:** they rate the calf 1 now (a delicate calf keeps them).
- **Loaded overhead work rated the neck 1,** though the playbook says every overhead press rates 2: the overhead triceps extension, thruster, man-maker, Turkish get-up, overhead carry, landmine press and wall ball now do.
- **Hotel-room menus offered jumping** that the kit note rules out: a preset can carry an `avoid` list (`catalog.Catalog.preset_avoid`), and `hotel-room` avoids impact.
- **The dead bug's timing** is five seconds a rep, as its coaching says.

### Changed
- The low-back limit cues say how to get down to the floor as well as up, and to take weights up only once settled.
- `programming.md`: a movement touching a delicate area is light (twelve to fifteen reps, three or more left, only lighter or steady offered).
- The hotel-room kit note names the prone pulls for when a door can't be trusted for towel rows.
- The eval's listener a has no open threads, matching its empty log.

## [0.42.0] - 2026-10-30

Eight more kinds of equipment and 26 movements, and two equipment gaps closed that could put the wrong movement on a menu. Sources are in `knowledge/research/2026-10-30-movement-library.md`.

### For forks
- **`band` now means a long band** (or tube band) with a door anchor or a post, and the new **`mini-band`** a small loop band. Fifteen of the eighteen band movements need a long band and an anchor; clamshells and side steps take either. A kit that lists `band` keeps every band movement; a listener who has only a loop band should change their kit's `band` to `mini-band`. The aliases "mini band" and "loop band" now name `mini-band`.
- **The sprint needs `outdoors`.** It was coached as outdoors only but needed nothing, so it could land on an indoor menu.
- **The donkey kick rates the knee 2** (a knee on the floor bears weight), so a delicate knee now leaves it out.
- **The brief now prints the kit notes for the equipment added in 0.41.0** (`brief.KIT_SECTIONS` had missed them) and for this release's.
- **New shipped ids win over private ones** of the same id, as in 0.41.0: see the list below.
- `catalog.LOAD_EQUIPMENT` and `brief.BODY_ONLY` take the new keys.

### Added
- **New equipment**, each with a section in `knowledge/kits.md`: `mini-band`, `outdoors`, `stairs`, `ankle-weights`, `balance-pad` (a foam pad, wobble board or BOSU), `push-up-handles`, `weight-vest` and `smith-machine`. The full-gym preset takes all but the stairs and the outdoors.
- **New movements:**
  - Ankle weights: weighted straight-leg raises, side-lying leg raises and donkey kicks, standing hip abduction, seated knee extension and standing hamstring curls.
  - Weight vest: the vest walk, step-up and push-up.
  - Stairs: the stair climb, stair intervals, step-edge calf raises and the single-leg heel drop. Step-ups also take the stairs.
  - Outdoors: the outdoor run, hill repeats and the outdoor power walk.
  - Balance pad: single-leg stance, tandem stance and squat.
  - Push-up handles: the handle push-up, knee push-up and plank. They keep the floor version's wrist rating: no study shows handles lower the wrist's load.
  - Smith machine: squat, bench press, inverted row and split squat.

## [0.41.1] - 2026-10-30

Fourteen more movements for the thinnest spots in the small kits and for listeners working around an injury, researched and cited in `knowledge/research/2026-10-30-movement-library.md`.

### Added
- **Pulling and shoulders with no equipment:** the prone lat pulldown (the bodyweight kit's first pull-down move), wall angels, and the push-up plus with its easier wall version.
- **Joint-friendly holds and rehab drills:** the Spanish squat (a band behind the knees), the split squat hold and the knee-to-wall ankle mobilization.
- **Hamstrings and quads:** the Nordic hamstring curl (gym only: it needs a machine to anchor the heels) and the reverse Nordic.
- **Twisting and balance:** the side-lying open book and the hip airplane.
- **Carries:** the overhead carry and the front rack carry.
- **Cool-down:** 90/90 breathing, feet on a wall, a chair or the bed edge.

## [0.41.0] - 2026-10-30

A bigger movement library: every unfinished catalog entry finished, 63 new movements, and 13 new pieces of equipment, all researched and cited in `knowledge/research/2026-10-30-movement-library.md`.

### For forks
- **New shipped movement ids win over private ones:** a movement in your `me/movements.toml` whose id matches a new shipped one (`pull-up`, `chin-up`, `forward-lunge`, `walking-lunge`, `lateral-lunge`, `standing-calf-raise`, `good-morning` and the rest listed below) is now replaced by the shipped entry. Rename yours if you want to keep it.
- **The 49 drafts are finished,** so menus grow: they now offer movements such as the front squat, the Turkish get-up, the box jump and the cable work that were never planned from before. Some changed on the way: `bench-dip` is now an `arms` movement (out of push slots), `neck-rolls` is coached as half circles ("half neck circles"), `thruster` needs dumbbells only, `box-jump` needs a box, `jump-rope` needs a jump rope, and `towel-hamstring-curl` takes sliders or a towel. A menu saved before this release is still read, but rerun `./harmonicfitness brief ... --save` to see the new movements.
- **Aliases moved or dropped:** `burpee` gave "squat thrust" to the new `squat-thrust`; one-word aliases a story could say were dropped (pullover, halo, windmill, get-up, sphinx, bicycles, hyperextension, pull-through, shuffles), as were "double unders" from the jump rope. Those entries were drafts, never on a menu, so no log names them by those words; a logged "squat thrust" now reads as the squat thrust, not the burpee.
- **`[unlisted]` changed:** "forward lunge", "walking lunge", "side lunge" and "lateral lunge" are now real movements. Newly refused: neck circles, sissy squats, dragon flags, muscle-ups, kipping and butterfly pull-ups, power and hang cleans, barbell and kettlebell snatches, clean and jerk, Jefferson curls, behind-the-neck presses, upright rows and double unders.
- **The `full-gym` preset** now holds the new gym equipment.

### Added
- **New equipment** in the catalog's `[equipment]` table, each with a section in `knowledge/kits.md`: pull-up bar, dip station, suspension trainer, medicine ball, slam ball, box, sliders, stability ball, ab wheel, battle ropes, landmine, trap bar and jump rope.
- **New movements:**
  - Pull-up bar, dip station and suspension trainer: overhand pull-up, underhand chin-up, negative pull-up, scapular pull-up, dead hang, feet-supported hang, hanging knee raise, parallel bar dip, suspension row, chest press, face pull and hamstring curl, and the barbell inverted row.
  - Landmine, trap bar and ab wheel: landmine press, row, squat and rotation, the trap bar deadlift and the ab wheel rollout.
  - Box, sliders and stability ball: box step-down, lateral box step-up, slider reverse lunge, lateral lunge, mountain climber and body saw, and the stability ball hamstring curl, wall squat, dead bug, stir the pot, glute bridge and back extension. Step-ups and box squats also take a box.
  - Conditioning: battle rope alternating waves, double waves and slams, ball slams, wall ball shots, medicine ball chest passes and rotational throws, bear crawls, squat thrusts and plank shoulder taps.
  - The home kit: standing and single-leg calf raises, forward, walking and lateral lunges, the Cossack squat, single-leg and staggered-stance Romanian deadlifts, the dumbbell good morning, sumo kettlebell deadlift and sumo squat, the short-lever Copenhagen plank and side-lying hip adduction, the glute bridge march, wall slides, tibialis raises, the Arnold press, skull crushers, close-grip push-ups, dumbbell shrugs, bent-over reverse flies and front raises.
- **A research note** for all of it, with the sources opened, what set each load and level, and what wasn't confirmed (rated up).

## [0.40.3] - 2026-10-30

### Fixed
- **Scripts that went stale before they were played:** the brief now says when it was written, and `knowledge/script.md` says to give an event its day and time ("tonight at seven thirty"), never "in half an hour", and to treat anything starting within about an hour as under way. A script written at 8:19 had previewed a 7:30 tip-off.
- **The praise warning caught too little:** it now also names "that's where we want it", "and a strong first ride", "what a great climb", "nailed it" and "you're flying". What the plan guarantees ("that's all eight efforts done") still passes.

## [0.40.2] - 2026-10-30

### Fixed
- **`workouts delete --files` left the delivered MP3 behind:** the build record names the folder it copied into, and the file is `<name>.mp3` there; delete now removes that file.

## [0.40.1] - 2026-10-30

A way to delete a workout or leave feedback on one, and two fixes for a web coach's pace.

### Added
- **`./harmonicfitness workouts`** lists the workouts logged, newest first and numbered. **`workouts feedback 1 "too long; loved the quiz"`** adds a feedback line tied to that workout. **`workouts delete 1`** (or a build id, or `all`) takes a workout back as if it never happened: its log line, its feedback, the stories it told (so they can be told again) and the threads it opened or closed; `--files` also removes its folder and the MP3 copies it delivered. The workout skill deletes a workout that a redo replaces, and the web chat can run it too.
- **`content log --draft` and `content thread --draft`** tie told items and threads to the workout's build, so deleting it takes them back. A row from before has no build id and goes when no remaining workout shares its date.

### Fixed
- **The brief's talk rate** now counts each clip's edges and the breaks between paragraphs, as the lint does: it said about 225 words a minute for a web coach whose drafts fill time at about 215, so first drafts came out short.
- **A web coach's first render left long quiet:** with a pace still estimated from its sample, the lint now checks held rests as if the voice spoke 20 percent faster (a new Inworld voice did), since the spare time a fast voice leaves grows into quiet at the bare holds. Fixed pauses are checked as written.

## [0.40.0] - 2026-10-30

The fixes the 0.39.0 eval asked for: a coach that never claims to have seen the listener, one story to a rest, safer menus under an ankle or foot limit, and short names that follow the full ones.

### For forks
- **Menus change under some limits:** an off-limits ankle or foot now leaves out kneeling and all-fours movements too (`catalog.AREA_POSITIONS`), the bench presses with leg drive (dumbbell, incline dumbbell and barbell) load the ankle and foot 1, and mountain climbers load the groin 1. A menu saved before this release is still read, but the build's re-screen refuses a movement the new screen leaves out: rerun `./harmonicfitness brief ... --save`.
- **The menu check runs segment by segment** (`menu.check`), and `menu.short_for` excuses a short name that ends a declared movement's full name said earlier in the same segment.
- **`repeats.seen_claims`** is a second build warning, never an issue.

### Added
- **A warning when the coach claims to have seen the listener** ("that set looked smoother", "best set yet", "your back stayed flat every set", "not once"), in coaching outside `[story]`; `knowledge/script.md` says to notice effort as a question or a plan instead, never "you told me".
- **Short names after the full one:** once a segment has said "Bulgarian split squat", "romanian deadlift" or "seated shadow boxing", "split squats", "deadlift" and "shadow boxing" in that segment mean the same movement, even though each alone names another.
- **On a conditioning day,** the brief says the work intervals run at the guide's effort even when the profile likes moderate sessions; that preference sets the warm-up, steady work and easy spells.

### Changed
- **One story to a rest** (`knowledge/script.md`): tell about the plan's topic count, and give a longer rest a bigger story, not two or three stacked; spares are for a session that would run thin.
- **Nothing standing includes fetching the kit:** under an off-limits ankle or foot, the script plans only with what's within reach, or what someone sets out; never "pause me and get it".
- **The air squat's setup** says hip width, which no longer clashes with the groin's limit cue.
- **The eval grid:** listener d's research sheet no longer lists threads from sessions d never had; every sheet has a weather line; the writer runs `content plan` for the topic count.

## [0.39.0] - 2026-10-30

Scripts with more of the listener's world and less repeated coaching, a build that's safer about timing and quicker to check, and research that fits the session.

### For forks
- **`--lint-only` refuses a stale menu** (from another day, or older than `health.md`) as the full build does; it only warned before. Rerun `./harmonicfitness brief ... --save` when it says so. `build --today` pretends today is a date, for the eval grid's fixed briefs (its lint command now passes `--today 2026-10-21`).
- **The lint aims inside the render's tolerance:** the predicted total must land within 2.5 percent (2 with an estimated pace), not 3, so a draft that linted at 2.8 percent off now fails the lint. `tts_build.lint` takes `headroom=False` for the old behaviour.
- **A segment with a bare `[hold]` keeps its planned length however late it starts** (`draft.layout`); earlier talk that ran long is paid back by the next unheld segments, or lands in the total. A draft whose overrun used to be soaked up by a held rest may now run long (exit 1 at the lint, as predicted).
- **`[story]` and `[/story]` are markers:** a draft that spoke the words "[story]" literally would have been refused anyway (brackets); a story left open, or holding a timing marker, is a menu issue.
- **The brief's menu is compact:** a movement's coaching notes print only when it touches today's limits or works one side; `brief --full` prints them all, and `movements --about <ids>` prints the rest. `brief.build` and `brief.menu_lines` take `compact`.
- **`tts_build.silences` moved to `draft.silences`** (`tts_build` still imports the name). `audio.assemble` takes `quiet` and `max_silence`; `render.run` takes `bed` and `quiet`; `render.follow` takes `check`; `render.check_takes` takes `heard`.
- **`content plan --json` adds `threads` and `unreadable`.** `content.Piece` adds `bad_until`.
- **New settings and files:** `bed` in `settings.toml` (`"off"` or `"pulse"`; absent is off, no schema change) and `me/workouts/research/threads.jsonl`.

### Added
- **`[story]` ... `[/story]` around the listener's content.** Never spoken; the menu check, the one-side check and the written-countdown check read past it, so a story can mention "her deadlift record", "the other side of the river" or "ten, nine, eight, liftoff" without being refused. A story may hold no `[hold]`, `[count]`, `[cue]` or `[chime]` and closes in its segment; a story sentence that talks to the listener about a movement off today's menu is still refused, and with the tags wrong every word is checked as coaching.
- **The pulse bed** (`bed = "pulse"` in `settings.toml`, off by default): a soft tick each second through any quiet of two seconds or more, so a long hold sounds like a clock rather than a dropped earbud, and the silence limit rises from eight seconds to twenty.
- **Open threads** (`./harmonicfitness content thread --open "topic | kind | what"` and `--close <id>`): a quiz answered next session, a story to follow up, the coach's take on a this-or-that, a promise. The content plan lists them until closed, and research looks for follow-ups.
- **A repeat check:** the build warns about any sentence of six words or more said word for word in the last five workouts (safety lines and limit cues aside).
- **Worked examples in `knowledge/script.md`**: a welcome, a strength rest with a story, a quiz asked and answered, and a close; a test lints each one.
- **The eval grid scores the stories:** invented research sheets per listener (`docs/eval/research/`), the writers fill the rests from them, and the judges add a sixth score, Stories.

### Changed
- **Coach fully once, then briefly** (`knowledge/script.md`): a movement gets its setup, rep, feel and fault the first time, then a short reminder, so the rests and easy work carry the listener's topics. Safety lines never shrink.
- **Takes are checked while the render runs:** a worker thread hears each take as the next renders, so the check after the render has only retakes left (a one-minute check went from 4.7 seconds to 0.1, render and check together from 12.2 to 8.1). `--follow` now checks each take as it lands too, on a computer with at least 12 GB of memory.
- **The brief is about half the size** (about 6,600 words against 15,000 for a hotel-gym case): the menu keeps each movement's facts and easier and harder versions, and the skill reads the chosen movements' notes after designing.
- **The render re-checks silences as laid out** from the real clips and warns (never stops) about any over the limit, in the build output and the record's `long_silences`.
- **Research plans for the real length:** the workout skill sends the research agent the session's length once the check-in settles it (it planned for twenty-five minutes before). `./harmonicfitness feeds` reuses a sheet from the last three hours (`--refresh` fetches again), so the session and the agent don't fetch twice.
- **"Two left in the tank" and "five seconds left"** no longer count as a side for a movement allowed on one side only.

### Fixed
- **A stock piece whose `Good until` wasn't a date** ("Nov 15") was treated as evergreen and never expired; it's now left out, and the plan lists it to fix.
- **RSS 1.0 (RDF) feeds** came back empty; they read now.
- **ESPN:** a final with no score read as a draw; it's left out. A team name matching neither side no longer guesses who won.
- **yt-dlp** had no socket timeout; a stalled connection now gives up after twenty seconds.
- **The eval writer's brief** still timed work with `[hold 20s]`, which the lint refuses, and named the old topic beats; stale lines in `tts_build`'s docstring and `script.md` ("thirty seconds of quiet") are corrected.

## [0.38.0] - 2026-10-30

Switch coach from Settings, which now opens two columns wide on a desktop, with clearer actions and a quieter "Pick up where you left off".

### For forks
- **Migration 012 adds `users.coach` and `users.coach_day`** (the coach chosen on the web app, and the listener's own day it was chosen); it runs when the server starts. **`PUT /api/coach`** takes `{"slug", "day"}` (a coach's folder name, never a path; `day` as `YYYY-MM-DD`; anything else is 422).
- **`GET /api/start`'s current coach** is the chosen one while it can speak and no workout logged on a later day used another; otherwise the coach used last, as before. `start.gather` and `start.shape` take `chosen`; `start.names`, `start.chosen_holds` and `start.logged` are the shared rule.
- **The chat's first step names the chosen coach** (`Deps.picked`, read by the worker), when it differs from `get coach`'s, and checks its route.
- **`Starter`'s `onCoach`** now makes the pick the page's current coach (and saves it); without it, the pick stays in the sentence alone. `ContextColumn` takes `onCoach`.

### Added
- **Switch coach in Settings:** a coach whose service has a key is a row to tap. The current one is marked "Coaching you", and the first screen's sentence follows at once. The choice is saved, so it survives a refresh, and the chat uses that coach even for a request typed in your own words. A coach picked in the sentence is saved the same way. A coach without a key stays a plain row saying which key it needs.
- **CI runs the browser client's tests** (type check and Vitest), which it didn't before.

### Changed
- **Settings is two columns on a wide screen** (one on a phone, in the same order): your coaches and keys on the left; background, your files and account on the right, with deleting the account last. Spacing and type are tighter, so the drawer fits on one screen at a usual desktop size; the background tiles show the picture and name, with the description on hover.
- **Settings' actions are small outlined buttons** (download, bring in a folder, change password, sign in another device, sign out, delete), not underlined text. The account's are two rows: change password and another device, then sign out and delete. Anything a button opens comes below its row. The key rows' Add, Replace and Remove stay as links.
- **"Pick up where you left off" is a quiet line** above the request, no longer a boxed card.
- **CI runs side by side:** a privacy job first, then the engine's tests, the web app's tests and, on main, the Fly deploy at once, so a release goes live in about two minutes (was about four). The deploy no longer waits for the tests; a failure still shows on the run.
- **The engine's tests are skipped in CI when a push changed only `web/`,** the changelog, `VERSION` or a version line.
- **`./harmonicfitness test engine` and `test web`** run one half of the tests.

## [0.37.0] - 2026-10-30

The web app opens on its first screen after a refresh, and Stop, now beside Send, ends the chat.

### For forks
- **`useConversation` no longer reopens a waiting conversation on load.** It returns it as `waiting`, with `resume()` to open it; only a conversation still working reopens on its own. `Chat` takes `waiting` and `onResume` for the card that offers it. `halt()` now also closes the chat once the stop is sent.

### Changed
- **A refresh opens the first screen,** not the last chat. When today's chat is waiting on you (the coach asked something, or a workout is ready to record), a "Pick up where you left off" card above the sentence says so, with the time, and reopens it in one click; a new request starts a fresh chat instead. While the coach is still working, a refresh keeps that chat open, so you can follow it and stop it.
- **Stop ends the chat:** a button in the message box, beside Send, while the coach works (it was a small link beside "Your coach is working…"). It stops the coach's turn and goes back to the first screen; the stopped chat isn't offered again. If the stop can't be sent, the chat stays open with the error.

### Fixed
- **A job counts as working only while its chat is open,** so leaving a chat whose job is still finishing never leaves the page stuck as busy.

## [0.36.0] - 2026-10-30

The web app's Settings, reorganized: the background chooser moves to the bottom and gains two patterns after Book of Shapes.

### For forks
- **`PUT /api/sky` takes `arcs` and `waves`** as well as `flow` and `field`; `GET /api/me`'s `sky` can be any of the four. The column is unchanged (plain text), so there's no migration. The code, API and database still call it the sky; the page calls it Background.

### Added
- **Two backgrounds in the web app:** Arcs, after Book of Shapes' Brockmann Beethoven Arcs (concentric arcs, thicker outward, their turns stepped to 15 degrees, a few stepping round every couple of seconds), and Waves, after its Interference Mesh (level lines bent by two sources of ripples, moving outward slowly). Both hold still when the device asks for reduced motion, like Flow and Field.

### Changed
- **The Settings drawer, top to bottom:** your coaches; keys; account (who's signed in, change password, sign in another device, sign out, delete the account); your files (download them, bring in a folder); and last the background, now headed "Background" (was "Sky") with its four choices in a two-by-two grid. A rule separates each section.
- **Plainer wording** in the drawer: the coaches' note, the keys' notes and their storage line, and each file action now a link with one line under it ("Bring in a folder" replaces "Choose a ZIP").

## [0.35.0] - 2026-10-30

What fills the rests, rebuilt for any listener: a plain list of topics you like to stay current on and learn about, seventeen ways to tell them, research that judges how big each find is, a stock filled while the audio renders, and topic ideas from what's trending.

### For forks
- **Run `./harmonicfitness migrate`.** It turns `content.md`'s `[[interests]]` rows into lines under a new `## Topics` section ("- name: detail"), leaving out the rows that named a way of telling rather than a subject (video, news, puzzle, trivia), and backs the old file up as `content.md.before-topics`. It's a folder step with no schema change: an unmigrated folder still reads, its rows as topics, because the web client keeps listeners' folders and can't run migrate.
- **`knowledge/content.toml` is a list of formats** (`[[format]]`: id, name, group, what, words, research, across), `[[band]]` rows give `topics`, `spares` and `serial`, and `[stock]` the stock's targets. The slots (today, science, deep dive, quiz, delight, learn) and their default categories are gone.
- **`content log --item` is `"topic | format | title [| source [| stock slug]]"`** (was slot and category); the topic is one of the listener's, or `-`. Old `told.jsonl` lines still read, their category as the topic.
- **`content plan --json` has new keys:** minutes, topics, spares, serial, due, formats, skipped, recent_days, told_recent, reserve, restock (`slots` is gone).
- **A stock sheet's header** is `- Topic:`, `- Format:`, `- Source:`, `- Added:`, `- Good until:`; an old sheet's `- Slot:` and `- Category:` still read.

### Added
- **Topics:** `## Topics` in `me/content.md`, one line each, as many as you like, with an optional note in your own words ("Seattle Kraken: scores and previews; a big trade or a great long read is worth a fuller story"). No categories to fit them into. `context.topics()` reads them.
- **Seventeen formats,** open to any topic: quick hit, the big story, explainer, number of the day, myth or fact, on this day, serial, mini-profile, how they trained, quiz, this or that, memory game, brain teaser, language bite, recommendation, your progress and reflection. `skip_formats` in `content.md` leaves any out.
- **Research judges each find's size:** a routine result is a quick hit; a big move or a strong long read earns the big story or an explainer. A topic's note steers it only when the listener writes one.
- **The stock fills while the audio renders:** the workout skill launches the stock agent alongside the build when the plan has a Restock section, so the next session's research is short. Each piece carries a Good until date (or evergreen); stale pieces drop out of the plan.
- **`./harmonicfitness content trending`:** what's popular today, from Reddit's front page (safe for work only, one post per community) or, when Reddit refuses, Wikipedia's most read. **"Update my interests"** (the setup skill, and the web app's button) offers ten topic ideas from it, minus anything never to bring up or already listed.
- **The script guide's "Weave, don't insert":** callbacks across rests, a quiz or myth answered later, a memory list recalled in the cool-down, a story tied to the work when it fits.
- `./harmonicfitness check` notes an old `[[interests]]` block, a topic still showing the template's hint, an unknown `skip_formats` id, and no topics at all.

### Changed
- **The deep dive is now the serial,** told across the session from a video (when `youtube_favorites` lists channels) or a news story; log lines start `serial:`.
- **The eval listeners** have their own topics (birdwatching, Italian, Formula 1, gardening, personal finance among them), so the grid exercises more than one kind of listener.
- **The web app** loads the setup skill for "update my interests", "add a topic" and "suggest some topics", and its button now says what it does.

## [0.34.0] - 2026-10-30

A clearer first screen: a body chart for what's sore, the request across the full width, and the other asks anchored above the message box.

### For forks
- **Nothing to migrate.** The web client only.

### Changed
- **The body chart** replaces the body map: areas from head to feet in three groups (neck and arms, the trunk, the legs), a round L and R button for each side (one for the neck and the low back), each a three-way toggle: tap once for go easy (cream), twice for keep off (grey), again for OK. A two-column panel, centred on the page: the instructions, a key, a plain list of what's marked and Clear all and Done on the left, the chart on the right; on a phone they stack. Limits from `health.md` still can't be loosened, and a limit with no side holds both.
- **The request spans the full width**, a size smaller, and a long blank (a list of sore spots) wraps between words instead of running off the edge.
- **"Or ask for something else" sits just above the message box**, with the request alone at the top, and each ask lights up with an arrow on hover.
- **"Choose what I hear in the rests" is now "Update my interests."**

## [0.33.0] - 2026-10-29

The web app, redressed as Moonrise: a dark night sky behind every page, after Ansel Adams' "Moonrise, Hernandez", with a faint moving pattern you choose in Settings.

### For forks
- **The web service applies migration `011_sky.sql` on startup** (a `sky` column on `users`); nothing to run by hand.
- **The web app is dark only.** The light theme and the cobalt poster are gone, as is the Inter Tight font package (`@fontsource-variable/big-shoulders-display` and `@fontsource/ibm-plex-sans-condensed` replace it; the logo is outlined paths, so it doesn't need a font).

### Added
- **A choice of sky, in Settings:** Flow (fine lines drifting slowly sideways) or Field (a grid of dots that a ripple crosses every few seconds, spreading from the top right like sound from a speaker). It switches at once and is saved per account (`PUT /api/sky`; `GET /api/me` returns it), so it follows the listener to another device. Flow is the default. Both hold still when the device asks for reduced motion.
- **A line above the request** naming the day, its part and the coach: "Thursday night · Coach Reed, voiced by Fish Audio".

### Changed
- **The web app's look:** near-black ground and cream type; the request in tall, narrow capitals (Big Shoulders Display), all one size, its fixed words in the logo's coral and the parts you can change in cream and underlined (a "keep off" area with a brick underline); IBM Plex Sans Condensed for everything else; square cream buttons, cream marking the one action on each screen. The sky brightens a little while the coach works, where the poster's arcs used to sway.

### Removed
- **"See how my week is going"** from the first screen's other asks: it didn't start the right thing. Asking in the chat still works.

## [0.32.0] - 2026-10-29

The web app, redesigned: a cobalt poster of sound-ripple arcs beside a quiet work column, a plainer request sentence, a body map for what's sore, and a choice of which AI writes your workouts. The coach now says what it's thinking about while it works.

### For forks
- **The web service applies migration `010_writer.sql` on startup** (a `writer` column on `users`); nothing to run by hand.
- **`HARMONICFITNESS_PROVIDERS` now defaults to all three** (Claude, ChatGPT and Gemini). Set it to keep a narrower list; unset, every listener chooses.
- **The opening request reads differently:** "Hey, coach Reed, I'd like a 25-minute full-body workout at home. Go easy on my left knee today." `webapp/agent/instructions.md` reads both this and the older form.

### Added
- **A choice of writer.** Settings opens with "Who writes your workouts": Claude, ChatGPT or Gemini, each with its key; the pick is saved (`PUT /api/writer`), and the keys listing marks it. Gemini's one key also voices its coach. A listener with no key yet picks from three cards on the welcome screen.
- **The coach's thinking, said live.** While the model works between tools (reading the message, writing the script, fixing it after a failed check), a line says what it's thinking about, and goes once it's done (`agent.Narrated` wraps the turn's model; a step event with `think`). A running step shows its own clock after 8 seconds, and past 25 a line says why it's a long one.
- **A body map** for the request's second line: areas in three groups, each with its side (left, right, both) and "go easy" or "keep off"; limits from `health.md` come filled in and can be tightened, never loosened.
- **`web/dev.sh`:** the server and worker (and Vite with `hot`) in one terminal, stopped by one Ctrl-C; `web/dev.sh reset` deletes the local database and key.

### Changed
- **The web app's look:** a cobalt poster beside every page, with seven concentric arcs after Müller-Brockmann (the logo's bars bent into ripples) that draw in once and sway while the coach works, and the coach's name large below the logo; Inter Tight throughout, as in the wordmark; coral for planning a workout, sun for recording one. On a phone the poster is a band across the top.
- **Plainer words throughout:** the request sentence, "Plan my workout", "New workout", the other asks listed with a line each on what they do, and rewritten welcome, sign-in and error messages.
- **No "how are you feeling" question:** neither the request sentence nor the check-in asks about readiness on the web; an injury the listener mentions still gets its questions and red flags.
- **Step names say what's happening:** the coach guide, setup guide, voices, moves and pricing each named as such, the opening step named for the request, and "Working on it" gone.

### Fixed
- **"I want a new coach" on a new account** ran the whole setup questionnaire and check-in; the coach now comes first, and setup waits until it's made.
- **A phone opened the first screen scrolled to the bottom**, and a rolling word dropped its spaces.

## [0.31.0] - 2026-10-29

A logo: seven sound bars, the tallest in coral, and the wordmark "harmonicfitness". The web app wears it, with a favicon at last.

### For forks
- **Nothing to migrate.** New files only, and the web client's logo.

### Added
- **`assets/brand/`:** the mark, wordmark and lockups (light and reversed), app icons (SVG and 1024 px PNG), the favicon (SVG and a 16/32/48 px ICO), and a README with the colours (ink `#15171C`, coral `#FF5A3C`) and the construction. Every file comes from `assets/brand/make.py` (maintainer only), which outlines the wordmark from Inter Tight SemiBold (SIL Open Font License) so nothing needs the font.
- **The web app's favicon and Apple touch icon** (`web/client/public/`).

### Changed
- **The web app's logo** (`web/client/src/Mark.tsx`) is the sound-bar mark and the outlined wordmark, drawn in the text colour from `web/client/src/brand.ts` (written by `make.py`), in place of the yellow squircle and the name in type.

## [0.30.0] - 2026-10-29

Fewer rules for the script writer, a final rewrite pass, and local scripts written to flow.

A local build (Pocket) sounded stiffer than a web one. Tested on 2026-10-29 (`knowledge/voices.md`, Local coaches): Pocket speaks a paragraph in short chunks, each started fresh, so a string of two-word cues came out clipped and lost its last words. Every engine setting tried (longer chunks, carried state, a higher temperature, the 24-layer model) did worse. The same content written as fuller sentences came through clean and sounded better.

### For forks
- **Nothing to migrate.** Guidance, the workout skill, and one new line in the brief; `.agents/skills/` resynced.

### Changed
- **`knowledge/script.md` is rewritten around one hard rule, safety** (the menu, the opening's rules, clinician rules, limit cues, one side, adjustments, the weights on hand, the calendar's shape only, no invented facts). It adds what the build checks, and two aims: getting the workout done and keeping the listener engaged. The rest is the writer's call, written the way this coach would talk to this person.
- **`knowledge/tts-rules.md` is now what a voice can read:** the draft's format, characters, numbers, markers, counts, and how local and web voices differ. The style guidance (registers, arc, name counts, locators) is gone.
- **A final read-through and rewrite** before the lint (workout skill, step 5): rewrite the draft as one piece, with threads that carry through, handoffs that flow and one coach's voice, keeping every safety line. A total off plan is fixed by rewriting around the segments furthest off, not by trimming or padding words.
- **The brief's Voice line** tells the writer whether the coach is local (write fuller sentences, joining short cues with commas and "and", every cue and limit cue kept whole) or web (short cues are fine).
- **`knowledge/voices.md` records what was tried for a stiff local voice** (2026-10-29): Pocket's engine settings and its 24-layer model did worse, and Chatterbox Turbo, retried on a full script, read accurately but took about four times longer to render and was not materially better by ear.

## [0.29.1] - 2026-10-29

Time a session has left goes to more of the listener's own content, never to silence.

### For forks
- **Nothing to migrate.** Guidance and lint messages only; `.agents/skills/` resynced.

### Changed
- **The content plan's counts are the least a session carries** (`knowledge/script.md`, Filler): time left once the coaching is written goes to a longer deep-dive beat, the research sheet's spare items or more reserve pieces (still one quiz, nothing told in the last month, every extra logged).
- **Easy, steady work can carry a story** (the warm-up's mobility, a stretch, the cool-down): position first, then the story, with a cue between its paragraphs. Hard sets keep to their cues.
- **Research brings two spare items** beyond the plan, marked "spare" (`.claude/skills/workout/research.md`), so a session with time to fill has verified content to fill it with.
- **The lint's fixes name the listener's content:** a draft short on time says to add coaching in the sets or content in the rests; a silence over eight seconds in a rest or easy work, to tell more of their content.

## [0.29.0] - 2026-10-29

The coach talks the listener through every set: the lint refuses any silence over eight seconds, and spare time no longer goes quiet at the end of a set. And `./harmonicfitness pull` brings a workout made in the web app down to this computer.

A 25-minute session made in the web app on 0.28.0 (Coach Jess, Gemini) was safe and well chosen but hard to use: 733 of its 1,494 seconds were silence, in 29 gaps of 10 to 34 seconds. Every set was "three, two, one, go", twenty to thirty seconds of nothing, then "and rest", because the guidance said to put `[hold]` "where the listener works in silence" and a held segment spent all its spare time quiet. The set lengths didn't fit their reps either (twelve single-leg bridges at three seconds a rep, in twenty seconds).

### For forks
- **Nothing in `me/` to migrate, but drafts that built before may not now.** The lint refuses any stretch of silence over eight seconds (`draft.MAX_SILENCE`), counting pauses, fixed holds, a bare hold's share of the spare time and the breaks around them. A draft with `[hold 20s]` in a set, or a bare `[hold]` taking a long rest, stops at the lint; coach through the set in holds of a few seconds instead (`knowledge/script.md`, Timed work, has a worked example).
- **Only a bare `[hold]` keeps a segment its full length** (`draft.is_held`): a segment with only fixed holds ends early like any other, so a draft short on words now comes up short on the total until coaching fills it, rather than filling with silence.

### Added
- **`./harmonicfitness pull`** (`tools/webpull.py`): signs in to the web app as the listener, with `HARMONIC_USERNAME` and `HARMONIC_PASSWORD` from the environment or `me/.env` (`HARMONIC_URL`, default `https://harmonicfitness.fly.dev`), as the browser does, so it needs no server access. Saves the app's Export of their files, the latest conversation (or `--conversation N`) and that conversation's MP3s still kept into a new `me/web/<date>-<time>/`, never over `me/` itself, then signs out. A refused sign-in is exit 4, missing credentials 64. The password is read only through `keys.web_account()` and scrubbed from anything printed like a key.

### Changed
- **The lint refuses silence over eight seconds**, naming the line before it and how long it runs (`tts_build.silences`, laid out as the render lays it).
- **The writing guidance** (`knowledge/script.md`, `knowledge/tts-rules.md`): the coach stays with the listener through every set, a cue every five to eight seconds (lead the first reps to set the tempo, then form, the breath, how far through, "last few"); size the set from the brief's seconds a rep; every rest opens with the person (a word on the set, a check-in) before the story.

## [0.28.0] - 2026-10-28

Fixes from a browser walk of 0.27.0's redesign: a reload no longer drops a conversation the coach is waiting on, and the first screen settles once.

### For forks
- **Nothing in `me/` to migrate.** The page now reopens today's conversation when the coach spoke last or a Record offer is open (`resumable` in `web/client/src/conversation.ts`); a finished, failed, recorded or earlier day's one still gives the starter. New chat is in the top bar only while there is a conversation.

### Changed
- **A reload keeps a conversation that waits on the listener** (web): the coach's questions or an open Record offer come back, instead of the starter.
- **The starter's blanks roll in once** (web), with the listener's own words: the sentence waits for `/api/start`, now asked beside the keys rather than after them; plain defaults stand in if it fails.
- **New chat shows only once there is a conversation to clear** (web), instead of sitting greyed out on the fresh screen.
- The message box says "Add a key first" while it waits for one; each starter list has a name a screen reader can say ("How you feel", not "feel").

### Fixed
- **The coach bar was hidden on a reopened conversation:** scrolling to the newest line also scrolled the chat sheet; only the list of lines scrolls now, and it scrolls again when the coach bar arrives.

## [0.27.0] - 2026-10-28

The web client redesigned: a new look, a first screen that is one fill-in sentence, and Settings behind a gear. The page opens fresh instead of on the last conversation.

### For forks
- **Nothing in `me/` to migrate.** The web client's look and first screen changed, so a fork that styles or tests the client by its old greeting, its "Keys" button or its Zilla Slab and Figtree fonts needs updating: the client now uses Archivo (`@fontsource-variable/archivo`), and the messages that pointed at Keys now say Settings ("Add a key for Gemini in Settings first.").

### Added
- **The starter** (web): the first screen is a sentence with blanks, "Hey [Reed], I've got [25 minutes] [at home] for [strength work]. Easy on my [left knee] today, and I'm feeling [pick one]." Each blank opens its choices and the new word rolls in like a scoreboard (no motion with reduced motion on). The blanks are filled from the listener's coaches, kits, usual length, `health.md` limits and what their week has left out; a limit from `health.md` can be made stricter for the day, never removed; Start waits until they say how they feel. Below it, "Something else" starts the chat on gear, an injury, what fills the rests, a coach, feedback on the last workout or the week (and "Finish setting me up" while setup is quick). The text box stays for writing it yourself.
- **`GET /api/start`** (`web/webapp/start.py`): what the starter is filled in with, from the listener's files and `coaches list --json` and `coverage --json` run on a temporary copy; it changes nothing.
- **The agent takes the starter's sentence as the check-in, answered** (`agent/instructions.md`): it asks only what the sentence leaves open or what its answers raise.

### Changed
- **The look** (web): a deep blue field, a white sheet for the chat, Archivo upright and a little wide, yellow only for today's coach and for Record. A coach bar above the conversation names today's coach. No left bars or row highlights.
- **Keys is now Settings** (web): a gear button opens one panel with the listener's coaches, their keys and their account.
- **New chat** is a filled button with a plus, the clearest thing in the top bar; the logo is a yellow squircle for now.
- **The page opens fresh** (web): an earlier conversation isn't shown again. A conversation still working is followed, so a reload in the middle of a turn keeps its steps and Stop.

## [0.26.0] - 2026-10-28

The web client's first five minutes, from a walk of the live site as a new user: sign-up no longer says it failed, a new listener is asked for the one key they need and is set up before their first workout, and the wait shows what's happening.

### For forks
- **Nothing in `me/` to migrate.** `coaches list --json` gains `speaks_here` on each coach. On the web client, a Gemini model key and the Gemini voice key are now one key, stored under `gemini`; an old `google` row still counts for both and is removed with it. A job's step events carry `id` and `state` (`running`, `done`, `failed`); an event without them reads as a step already done.

### Added
- **`speaks_here` in `coaches list --json`:** a web coach whose service has a key here, or a local coach that renders here (never on the web client). The text list notes a web coach with no key.
- **A welcome card** (web): with no language-model key, the chat says what the app makes and which key it needs, and its button opens that key's row in Keys; the message box waits until the key is saved.
- **`.claude/browser-qat.md`:** how a browser walk serves the web client locally against a throwaway database, signs up and cleans up.
- **`web/qat_key.py`:** gives a local walk's throwaway account the Gemini key from the repo's root `.env` (now git-ignored) through the app's Keys API, so a walk can record without anyone pasting a key. It never prints the key and refuses any server but localhost.

### Changed
- **A new listener is set up first** (web): their first turn asks the setup skill's quick start and today's check-in as one numbered list, and writes the answers before the brief.
- **Only coaches that can speak are offered** (web): the agent is given the coaches with a key here; the others are mentioned only as "add a key in Keys for more voices".
- **Keys** (web): one row per key (Gemini once: it writes the workouts and can voice the coach), grouped as Required and Optional: more voices; the account settings sit under their own Account heading.
- **The privacy line on the web** says the key is stored encrypted on this site and removed in Keys, never a file. The price is said once, on the Record card, and the plan's table once, before it; the reply after recording is one line.
- **Progress** (web): each step shows while its tool runs and is ticked when it ends; a rewrite after a failed check reads "Tightening the script's timing", then "Checking the script again"; an approved recording shows "Designing <coach>'s voice" (when the coach is made then) and "Recording your workout" while it runs.
- **A coach's sample** is labelled with the coach's name, and left out when the same turn recorded the workout.
- The sign-in page says what the app is; a typed message survives a reload; buttons look like buttons again.

### Fixed
- **Sign-up showed "Couldn't reach the server" after it worked:** the client read register's empty 201 as JSON. An empty answer is now no body, whatever its status.
- **Three 401s on every page load:** the signed-in page now waits until the server says who is signed in.
- **Opening Keys left focus in the chat:** the drawer was still hidden at the moment it opened.

## [0.25.1] - 2026-10-28

### For forks
- **Nothing to migrate.**

### Added
- **`fly.toml`:** the web client runs on Fly.io as two process groups (web and worker) from the same image, beside Railway while it moves. The Dockerfile takes the deployed commit as `GIT_COMMIT_SHA` (`fly deploy --build-arg`) as well as Railway's `RAILWAY_GIT_COMMIT_SHA`.

### Changed
- **The check-in asks about the coach whenever it has room** (it holds four questions): the coach used last first, the others, then "A new coach of your own". It used to ask only when the request hinted at a change, so a listener never saw the choice.

## [0.25.0] - 2026-10-28

The web client's Railway project is defined in code: `.railway/railway.ts` replaces `railway.json`, which Railway retires on 2026-12-01.

### For forks
- **Nothing in `me/` to migrate.** A fork that deploys the web client on Railway: `railway config pull` imports its own project into `.railway/railway.ts` (its variables as `preserve()`, never their values), then `railway config plan` and `apply` (web/README.md, Deploy).

### Changed
- **Railway's settings as code.** `.railway/railway.ts` holds the project as Railway has it: the web and worker services built from the root Dockerfile and restarted on failure, the web's `/healthz` health check, Postgres and its volume, and the `media` bucket; every variable is named but kept as set in Railway. Railway's SDK is pinned in `.railway/package.json` (its `node_modules/` git-ignored), and `.railway/` stays out of the Docker image.

### Removed
- `railway.json`.

## [0.24.1] - 2026-10-28

### For forks
- **Nothing to migrate.**

### Changed
- **The check-in's coach question offers "A new coach of your own"** as its last option whenever a voice key is set, and when the coach used last can't speak here, so a listener can start the coach skill's quick coach from a workout request, on the web client and on a computer.

## [0.24.0] - 2026-10-28

A listener on the web client can make a coach of their own: an original voice designed from their description, auditioned on every voice service they have a key for (Fish Audio, ElevenLabs, Gemini, Inworld), and kept in their own account there.

### For forks
- **Nothing to migrate.** Only the web client changed; it needs no new database migration.

### Added
- **The coach skill on the site.** "I want a new coach", "a different voice" and the like bring the coach skill into the chat, as on a computer: the quick coach's one question, the narrative, an audition across every keyed service, then the listener's pick by letter, kept as their coach and named by them. The agent may now run `coaches audition` (one a turn, never `--play`), `keep`, `forget-audition` and `archive`.
- **The coach skill stays for the whole making:** a conversation remembers that a coach is being made, so the quick coach's answer ("Coach Dana") still has the skill, and an audition left open is closed before a workout.
- **Candidates play in the chat,** each as a player labeled "Candidate B, about $0.30 a workout", in letter order, never naming the service.

### Changed
- **An audition is kept between turns** with the listener's files (its narrative, candidates list and each candidate's WAV and MP3) until `forget-audition` closes it, since keeping a candidate sends its WAV to the service a turn later. The chat posts only audio a turn made, so an open audition's candidates aren't posted again.
- A voice design or save (`coaches make`, `audition`, `keep`) gets the build's 10-minute timeout.

## [0.23.0] - 2026-10-28

The web coach makes the whole workout: it records the audio once the listener approves the price, keeps it 24 hours to play or download, and stops on request. New listeners are set up in the chat, and an account can be exported or deleted.

### For forks
- **Nothing in `me/` to migrate.** The web client's database gains its tables on deploy (migrations 007 to 009).

### Added
- **The web coach records the audio.** The build runs in full on the site; each MP3 a turn makes is kept 24 hours, sealed with the listener's data key, and the chat shows it with a player and a download (`GET /api/media/{id}`: byte ranges for Safari, a private browser cache until it expires).
- **Recording waits for the listener's Record button,** with its price: a full build is first only priced (characters and dollars, the voice design included), and approving it reserves those characters from a daily allowance (`HARMONICFITNESS_DAILY_CHARS`, default 60,000) and records within that count.
- **Re-recording pays only for what changed:** recorded clips are kept a week per listener, sealed, and loaded for each recording.
- **Stop.** A Stop button ends a running turn within a few seconds: the model run is cancelled and the engine's processes are killed.
- **First-time setup on the site:** a new listener gets the setup skill's quick start in the chat (keys in Keys, the stock web coach for their service made and heard in the chat, a ten-minute first workout); "finish setting me up" runs the rest.
- **Export and delete:** the Keys drawer downloads every file as a ZIP laid out as `me/`, and deletes the account and everything in it, with the password.

### Changed
- **The check-in may change `health.md`** on the site, with the listener's permission, as on a computer.
- **The chat's steps say what they mean for the listener** ("Checking today's safety limits", "Writing your script", "Recording your workout"), never a command or a file's name; repeated steps show once.

### Removed
- The web client's scoping research and milestone plans (`docs/research/web-client/`) and the 0.15.0 plan (`docs/plans/`).

## [0.22.0] - 2026-10-28

The web coach answers sooner: the worker does the skill's first reads itself, all at once, and fetches the day's feeds in the background.

### For forks
- **Nothing to migrate.** Only the web client changed.

### Changed
- **The check-in arrives in one round trip.** On a conversation's first turn the worker runs step 1 of the workout skill (check, content plan, get coach, the coach's route, coaches list, and the profile, training, health and log files) before the first model request, in parallel, and hands the results to the model with the listener's first message. The model sees the same information as before, without a model request for each read.
- **Feeds run in the background.** On each turn after the first, the worker starts `feeds` as the turn begins (unless today's sheet is there), so the day's research is ready when the script needs it; the model's `run feeds` waits for that run. The coach no longer fetches feeds before the check-in.

## [0.21.0] - 2026-10-28

The web client, stripped back to a chat and Keys: the coach on the site works as Claude Code does on a listener's computer, following the workout skill itself. The engine gains the build checks the web needs (one side only, names the catalog doesn't hold, a character allowance and its price).

### For forks
- **The build's menu check is stricter.** A draft that speaks a one-sided movement with "each side", "switch", the other side's word or "the injured leg" in its segment is refused (exit 1), as is a movement name the catalog doesn't hold (`[unlisted]` in `knowledge/movements.toml`). An existing draft that passed before may need its wording changed; rerun the build and follow what it names.
- **A shipped limit cue changed words:** the groin's off-limits cue is now "No side lunges or wide stances, and no legs spread apart." Clips of the old line render once more.
- **Nothing in `me/` to migrate.**

### Added
- **Live steps in the web chat.** While the coach works, the chat shows a running clock and each step as it happens ("Reading me/profile.md", "Working out today's safe menu", "Checking the script"); the worker logs each tool and its exit code, never what it read.
- **The coach's replies render as Markdown** (tables, lists, bold) in the web chat; the listener's own lines stay plain text.
- **Bring in your folder.** The Keys drawer takes a ZIP of a listener's `me` folder and keeps its files over the starter ones (`POST /api/import`, at most 10 MB zipped, 2 MB a file); key files, audio, caches, logs, backups and git are left out.
- **A build's allowance and its cost.** `build --max-chars N` bounds a web build below the profile's `cloud_max_chars`: the lint stops a script over it (nothing is sent), and the render's own check names the flag when it was the lower bound; a local voice ignores it. `get cost --coach <coach> [--chars N] [--json]` prices a web build (`chars`, `usd`, `ceiling`, and the one-time voice design for a coach still to be made); a local coach, or a web coach with no key here, is exit 64.
- **A one-sided movement keeps to its side in the build.** When today's menu allows a movement on one side only, the build's menu check refuses a sentence that names it with another side's word, and a segment naming it that holds, in any sentence, a both-sides phrase ("each side", "alternating", "both legs", "switch", "other leg"...) any word naming the other side outside a shipped limit cue ("then ten on the left", "next, left", "now the injured leg"), or a turn without one ("change legs", "the other one", "ten a side", "the second leg", "apiece"); a colon or a parenthesis doesn't separate a dose from its name, and a negation doesn't excuse it. The rule moved from the web's plan check into `menu.side_problems`, so the build and the web refuse the same things. `menu.part_of` is public (`_part_of` stays as an alias for this release).
- **Names the catalog doesn't hold are refused.** The catalog's new `[unlisted]` table names real movements it doesn't hold ("pistol squat", "pistols", "forward lunge", "walking lunge", "side lunge", "lateral lunge", a bare "lunges"), singular or plural; a script that says one is refused, since it can't be on a menu, except a bare "lunges" after a declared lunge. The groin's off-limits cue now reads "No side lunges or wide stances, and no legs spread apart.", so its negation covers the name.
- **Web mode's key messages point at the app's Keys.** Under `HARMONICFITNESS_WEB=1` a missing, refused or malformed key says to add it in HarmonicFitness's settings, under Keys, and never mentions `keys init`, `keys open` or `me/.env`; the command line's wording is unchanged.
- **The web client's mode.** With `HARMONICFITNESS_WEB=1` (the web client's worker sets it) the engine has no local voice: a build with no coach named takes the first stock web coach, whose key the listener adds in the app, and a finished MP3 is kept in its workout folder for the app to upload, with no delivery folder asked for (`doctor` reports `web=yes`). Unset, nothing changes. A web coach with no key yet now shows its estimated pace in the brief instead of none.
- **Voice keys in the web app.** A listener enters each web voice service's key once in the app's Keys box; it is stored encrypted per user and never shown again. Only the worker opens the keys, for one job, and hands them to the engine under `services.toml`'s variable names, so the engine reads them instead of `me/.env`.
- **The web client is a chat and Keys.** The coach follows the workout skill itself, with four tools (run a `./harmonicfitness` command, read, write and list files, inside the listener's folder), asking its questions in the chat; the sentence band, check-in panel and plan table are gone. The build runs `--lint-only` for now: the audio comes later.
- **A language-model key in Keys.** Each listener adds their model key in the app's Keys box, stored like a voice key and used only by that job's model client.
- **The deployed version on the page.** The web client shows the engine's version and the deployed commit under the wordmark, on the sign-in page too, and `/healthz` returns it, so a deploy is visible at a glance ("0.20.0 (75da105)"; the commit is Railway's `RAILWAY_GIT_COMMIT_SHA`, baked in at build).

## [0.20.0] - 2026-10-27

sweatcast is now **HarmonicFitness**: the command, the package, the environment variables, the repositories and the web app all take the new name. Nothing about how a workout is built, heard or logged changes, and no context file changes its schema. The release also carries the first slice of the web client.

### For forks
- **The command is `./harmonicfitness`** (it was `./sweatcast`, which is gone: there is no shim). `tools/sweatcast.py` is `tools/harmonicfitness.py`, and Codex's rule file is `.codex/rules/harmonicfitness.rules`. Claude Code's allow rule is `Bash(./harmonicfitness:*)`.
- **Every `SWEATCAST_*` environment variable is `HARMONICFITNESS_*`** (`HARMONICFITNESS_HOME`, `HARMONICFITNESS_PYTHON`, `HARMONICFITNESS_DEVICE`, `HARMONICFITNESS_DEBUG`, `HARMONICFITNESS_<SERVICE>_URL`...). The old names are no longer read: a `SWEATCAST_HOME` left in a shell profile is ignored, so rename it.
- **The web client's `WT_*` variables are `HARMONICFITNESS_*`** (`HARMONICFITNESS_MASTER_KEY`, `HARMONICFITNESS_BASE_URL`, `HARMONICFITNESS_ROLE`, `HARMONICFITNESS_REGISTRATION`, `HARMONICFITNESS_ENGINE_ROOT`, `HARMONICFITNESS_TEST_DATABASE_URL`). Set the new names, with the same values, before deploying this release.
- **The Python package is `harmonicfitness`** and `errors.SweatcastError` is `errors.HarmonicFitnessError`. The local engine's marker is `.venv/.harmonicfitness-extra`: rerun `./harmonicfitness setup`, or rename the old `.venv/.sweatcast-extra` by hand.
- **The repositories are `RNCDev/harmonicfitness`** and, for the maintainer's context, `RNCDev/harmonicfitness-me`. GitHub redirects the old addresses; point a clone at the new one with `git remote set-url origin https://github.com/RNCDev/harmonicfitness.git`.
- **Nothing in `me/` to migrate.** Clip cache keys never held the name, so no clip renders again or is billed again.

### Changed
- New web voices are saved at the service as "harmonicfitness <name>". Voices saved before are still labeled "sweatcast <name>" there and keep working by their ID; the messages that say what to look for at the service name the new label.

### Added
- **The web client, Slice 1** (`web/`, the optional `web` extra; see `web/README.md`): a FastAPI server and a Python worker on Postgres, a React client, an encrypted per-file store for each listener's context, a job queue that runs `./harmonicfitness brief` in a sealed temporary context folder, and a live event stream. Sign-in is a username and password, with open registration behind `HARMONICFITNESS_REGISTRATION=open|closed` (default open). Deployed on Railway from this repository's `main`.

## [0.19.0] - 2026-10-27

The audit's remediation: money spent on web voices is guarded at every step, settings and names are checked where they come in, an engine bug is never mistaken for a draft to fix, and the coaches code is split by job. Workouts, drafts, coaches and the `me/` folder work as before; no context file changes its schema.

### For forks
- **Nothing in `me/` to migrate.** New `builds.jsonl` lines carry `kind` (`"mp3"`, `"failed"`, `"outcome"`); older lines are read by their fields and never rewritten, and older engines still read the new ones. A reader of its own should go through `records.build_records()` or `records.parse()` and branch on `rec["kind"]`.
- **Exit codes that changed, each to the one it should have been:**
  - 64 (the command was wrong) where a value was accepted before: a build name with `: ? * | " < >`, a control character, a trailing dot or space, or a Windows device name (`con`, `nul`...); `brief --save` outside `me/workouts/`; any numeric option of 0 or less (`--minutes`, `--recent`, `--hours`, `--last`, `--idle`; `--seed` and `cache --days` may be 0).
  - 1 (fix the file) where 64 was given before: `brief` or `content` with a damaged `sessions.toml`, `content.toml`, catalog or profile.
  - 1 where a silent default was used before: a malformed `cloud_max_chars` or `words_per_minute`, or a coach whose `kind` is neither local nor web.
  - 70 (an engine bug) where 1 was given before: an unexpected exception during a web render or an audition.
- **Moved:** auditions to `tools/audition.py` (`audition`, `keep_web`, `forget_audition`), making a stock web coach to `tools/coachmake.py` (`make`); `coaches.X` still works for this release, but patch `coachmake.make`, which the build now calls. `render` no longer re-exports the internals of `audio`, `clipcache` and `records`: import them from there. Renamed: `clipcache._cache_write` to `clipcache.write`, `_verdict` to `verdict`.
- **Signatures:** `logsession.log_session` takes keyword fields (`coach=`, `fmt=`, ...), not a parsed command line; `brief.main(argv)`; `cloud.request(..., deadline=)`; `cloud.audio_pcm(..., expect=, content_type=)`; `migrate.coaches_due` may list `("unreadable", coach)` (use `migrate.acting()` for the steps that change something).
- **`keys.BadKey` is an `errors.SweatcastError`** (still exit 4), so `except errors.PROBLEMS` catches it: the readiness check and the brief carry on past a key with a stray character. `keys` no longer imports `cli`; `tests/test_imports.py` fails on any import loop at load time.
- **`--route`** is the flag's name on `build`, `get route` and `coaches measured`; `--engine` still works.

### Fixed
- **The web spending cap can't be misread.** `cloud_max_chars = "5000"` (in quotes) no longer reads silently as the default 30,000: `./sweatcast check` names any single setting it can't use (`context.SCALARS`), and a build stops rather than guess.
- **A paid voice left behind is said on screen.** When the first build with a stock web coach saves its voice at the service but can't write the coach, the terminal names the service and the voice ID; before, only the build log did. A failed or interrupted design shows the log's last lines.
- **A slow web service can't hold a build for many minutes:** each paragraph gets five minutes in all, retries included, and three failures in a row stop the sending; the clips that came back are cached, so a rerun sends only the rest.
- **A reply that isn't audio is refused** (text, a cut-off or unreadable stream, under 0.1 s) instead of being cached, paid for once and replayed in every later build. Each service says what it asked for, and raw sound is accepted only where it was.
- **An empty or torn clip in the cache is rendered again**, and a clip that comes out empty stops the build naming its line. Clips are written atomically and flushed.
- **Ctrl-C during a web render says what was sent** (characters, clips cached, and that a rerun sends only the rest); any interrupted command says "Interrupted.".
- **A build name with a colon is refused on every system** ("Workout 1: Strength" hid the text in a Windows side stream); the build also checks the MP3 lands in its own folder.
- **On Windows, a build no longer fails at its last step** because a player has last time's MP3 open: replacing a file is retried for a moment. The Windows lock retries only on "busy", and its re-entry key ignores case.
- **Key values never print from the command line:** every message `cli.run` prints is scrubbed, a service's answer is scrubbed before it's shortened, and an unreadable `me/.env` still scrubs the environment's keys.
- An unreadable `me/movements.toml` is listed by `./sweatcast check` instead of printing a warning on every command; a coach file `migrate` can't read is named, never skipped silently or crashed on.
- A feed that declares a DOCTYPE or entities is refused unparsed; caption downloads are capped at 5 MB like feeds.

### Changed
- `tools/coaches.py` is the command line only; the list and `--json` are built from one `coaches.listing()`, and the rules for `coaches set` live in `personas.set_setting`.
- Library code reports through the callback it's given, never `print`; the delivery-folder note is `context.delivery_note`.
- Every numeric option is range-checked by one set of types (`cli.positive_int`, `non_negative_int`, `positive_float`, `non_negative_float`), and a test walks every parser to keep it so. `brief` checks its flags before it computes anything.
- A local build with the take check loads the voice model once; each repeated line is read once per build, and less audio is held in memory while the workout is assembled.
- Each build's part of its log ends with `--- end <build_id> <stage> <code>`. The sample, a made voice, audition files and the Codex skill copies are written atomically (`fileio.atomic_copy`, `fileio.replace`), and the `+++` block has one writer (`frontmatter.dump_block`).
- `builds.jsonl` and `told.jsonl` are read by one rule (`fileio.read_jsonl`), which skips a line a crash cut mid-character instead of failing the read.

### Added
- `SWEATCAST_DEBUG=1` prints a reported problem's scrubbed traceback, with what it was raised from.

## [0.18.0] - 2026-10-27

The safety gate can no longer be talked past, voice keys stay on their service's host, a replaced voice file is heard at once, every build leaves a trail to its end, and the middle of the engine is untangled. Workouts, drafts and coaches work as before; no context file changes its schema.

### For forks
- **Nothing in `me/` to migrate.** Things a listener notices once: every local coach's lines render again on the next build (the clip key now includes the voice file), every cached take is heard again once (verdicts now carry the checker's id), and a menu saved by an older brief asks for `brief --save` again (menus are daily anyway).
- **A new exit code, 70:** an unexpected exception (an engine bug) exits 70 with its scrubbed traceback on stderr, where it used to exit 1, the code for "fix the draft". A script that branched on 1 for every failure should treat 70 as "stop and report".
- **`log-session --draft` takes its coach from the build** when `--coach` is left out, refuses a different one, and ends the session line with `| build: <id>`; older lines read as before. `--coach` is still required without `--draft`.
- **Errors:** `personas.UnknownCoach` and `routes.WebCoachUnavailable` are now `errors.UsageError` (exit 64), no longer `SystemExit`; catch them with `except Exception` or `errors.PROBLEMS` (which no longer includes `cli.Usage`). Exit codes live in `errors.py` (`cli` re-exports them).
- **Moved:** `scrub` to `tools/redact.py` (`cloud.scrub` still works); coach choice (`default`, `resolve`, `pick`) to `tools/coachpick.py` (`personas.default`/`resolve` and `routes.pick` re-export it for this release); `doctor.facts`/`hub_dir` to `tools/machine.py`; `web_key` to `cloud`; log-session's logic to `tools/logsession.py`; `equipment_keys`/`about` to `catalog`. `context` no longer re-exports the health, store and session-log names: import them from `health`, `store`, `sessionlog`. Renamed public: `coverage.days_ago`, `personas.load_all`, `catalog.spoken_fault`.
- **Failure summaries moved to stderr** (a build's menu, lint, drift and unmeasured-coach lines; backup's refusals). The reports themselves stay on stdout.
- **A web service URL override** (`SWEATCAST_<SERVICE>_URL`) counts only for `https://` or `http://` to localhost.

### Fixed
- **The menu gate checks the menu itself.** `menu.validate` checks `menu.json`'s shape (a damaged menu is an issue, never a traceback), and a strict build re-runs the safety screen from the menu's request against today's `health.md`, profile and catalog, refusing any movement (or side) it doesn't allow: a movement added to the menu by hand no longer passes. The request can tighten health.md's limits, never loosen them. A missing `health.md` is named as such.
- **Voice keys never follow a redirect** to another host; feeds re-check http/https on every redirect hop. Voice IDs are URL-encoded and must look like one a service gives.
- **A local coach's clip cache key includes its voice file** (`pocket.safetensors`), so a remade voice is heard, not the old one's clips; the stock coaches' `pace.json` moved to the new keys (`tools/coachmaker/rekey_pace.py`).
- **Take verdicts carry the checker's id** (`verify.checker_id`), so a stricter checker hears cached lines again.
- `coaches forget-audition` and `keep` resolve an audition only inside the auditions folder (a folder elsewhere is never deleted); `candidates.json` is checked.
- Two builds can't design and pay for the same pending web coach (`coaches.make` holds a lock); a Gemini voice left behind after a failure is named.
- A local render that stops midway releases the model and keeps the pace it measured; a failed delivery records why (`couldn't copy to …: No space left on device`).
- Every ffmpeg call has a timeout (the final encode's grows with the audio), so a hung ffmpeg can't hold the render lock forever.

### Added
- **Every full build leaves one outcome line** in `builds.jsonl`: `stopped` with its stage (coach, pace, lint, menu, design, render, drift, web-copy, deliver), `measured` for the smoke test, or `delivered`. The render log now also holds the engine's own progress and, for a crash, its traceback; the build record has per-stage `timings`.
- `--json` on `coaches list`, `content plan`, `coverage` and `get`.
- `./sweatcast cache prune --logs-older DAYS` removes old render logs (never `builds.jsonl` or `told.jsonl`).
- `services.toml` is validated when read; `fileio.read_json` names a damaged JSON file.

### Changed
- `build.py` is split: `run_build(BuildOptions)` with `resolve_voice`, `gate`, `render_and_deliver` and a pure `delivery_plan`; `main` only parses.
- `tools/ffmpeg.py`'s `run` and `to_mp3` are the one way to run ffmpeg.
- The voice a build speaks with is built as a `LocalVoice` or `WebVoice` (`tools/voice.py`), passed on as today's dict.
- Import cycles cut from six to four, each with its reason; `tests/test_imports.py` keeps new ones out and pins the voice dicts and cache keys. Only command modules import `cli`, and no tool copies a path constant at import (both checked).
- One heading rule (`frontmatter.heading_index`), one movement key (`catalog.key`), one `--today` parser (`cli.today_arg`); `cli.py` states the `--date`/`--today` rule and a test holds every parser to it.
- The take check's clipping count and clip leveling use numpy.

## [0.17.0] - 2026-10-27

The engine, audited and reworked from the inside: the listener's records survive a crash or two writers at once, a hand-edited setting can no longer stop every command or be misread, errors are typed and reach stderr, the largest modules are split by job, and a build can be followed from its log to its delivery. Workouts, drafts, coaches, commands and exit codes work as before; briefs and exports come out byte-identical.

### For forks
- **Nearly nothing to migrate:** no context file changes its schema. `./sweatcast migrate` (which setup runs) adds `*.lock` to a `me/.gitignore` from before 0.5.4 that lacks it, so the new lock files beside `log.md`, `told.jsonl` and `builds.jsonl` never go into a backup.
- **Library code no longer raises `SystemExit`.** A fork's own code that called an engine function and caught `SystemExit` should catch `errors.PROBLEMS` (the typed errors and `cli.Usage`) or the kind it means (`errors.ContextError`, `CoachError`, `RenderStopped`...). Commands, and the exit codes the skills branch on, are unchanged.
- **Moved, still importable from where they were:** the front matter, the store, the health file and the session log from `context` (`frontmatter.py`, `store.py`, `health.py`, `sessionlog.py`); the PCM work, the clip cache and the build records from `render` (`audio.py`, `clipcache.py`, `records.py`). Both modules re-export every moved name.
- **Some errors moved from stdout to stderr** (a build stopped by a lost cue, the web cost ceiling, a web service's refusal, a missing profile or coach). A script that read them from stdout reads stderr.
- **`builds.jsonl` gains outcome lines** (`"event"`); a reader of its own that counts MP3s should skip them, as `records.is_mp3` does.

### Fixed
- **A crash mid-write no longer loses the next record.** `builds.jsonl` and `told.jsonl` are appended through `fileio.append_jsonl`: under the file's lock, flushed to disk, and a last line a crash left without its newline is sealed first, so the reader skips only that fragment (before, the next record was glued onto it and both were lost, and `log-session` could then refuse a session whose MP3 existed).
- **Two writers at once can't lose or double a record.** `log-session` holds `me/log.md`'s lock across its duplicate check and the write; `content log` holds `told.jsonl`'s across its "told once" check and the append; `migrate` holds it while it rewrites the file. The lock (`locks.file_lock`, the pace file's lock moved up) is re-entrant within a thread.
- **A hand-edited `me/movements.toml` can't stop every command.** An entry with no id, a list or table field of the wrong type, or a count that isn't a number is left out and named by `./sweatcast check` (before, `brief`, `build`, `movements` and `check` itself stopped with a traceback). A single `[movement]` table reads as one movement.
- **Every engine write is atomic:** the menu, the brief, the feeds sheet and the YouTube sheets now go through `fileio.atomic_write` (a test keeps it so); the pace file's hand-rolled copy uses it too.
- **A rate limit isn't a used-up quota.** A web service's 429 that names no wait is retried with backoff, even when its body says "quota"; only one that outlasts every try stops the build as the quota (exit 4).
- **The web player's links** survive a `#` or `?` in a workout's name (URL-encoded).
- The characters-sent count of a failed web render is exact (the workers' counter has a lock); the TLS context is built once per process.

- **A setting in the wrong shape is read as meant, and `check` says so.** A bare string where a list belongs (`likes = "goblet squat"`, `aliases = "Maya"`, a kit's `equipment = "dumbbells"`) is one item, never its letters (before, every letter became a like, or an alias, so a lookup for "a" found that coach); a single `[kits]`, `[feeds]` or `[interests]` table is one row (before, no kits at all). `./sweatcast check` notes each one and how to write it. `[[limits]]` stays strict: a malformed row still stops the brief.

### Added
- **A build can be followed end to end.** Each build has a `build_id`, in its log's header line, its record, a failed web render's line, and a new outcome line in `builds.jsonl`: `"event": "stopped"` (the stage, lint, menu or render, and why) when a full build stops, or `"delivered"` (where the MP3 went). Before, a local build that stopped on a dropped cue, the lint or the menu left no trace, and the delivery was only in the MP3's own `.build.json`. `log-session` and `get web-builds` skip the outcome lines, so they count as before.
- **`build --verbose`** leaves the engines' loading and rendering chatter on the terminal (it still goes in the log's header line).
- **A model that won't load says why:** the network's advice only when it was the network; otherwise out of memory, or the error by name (before, every failure said "check the network"). The take checker's load is caught the same way.
- Past 2 GB of clips, a build mentions `./sweatcast cache prune` (the cache is still never pruned on its own: a web coach's clips are paid for, and a render running ahead may be using them).

### Changed
- A build log past 1 MB starts over, its older lines kept once as `<name>.log.1`; a failure shows the last lines from its end instead of reading the whole log.
- **Errors are typed, and the engine never exits from library code.** `tools/errors.py` holds `SweatcastError` (exit 1 unless it says otherwise) and its kinds: `ContextError`, `LogRefused`, `CoachError`, `RouteUnavailable`, `EngineError`, `DraftError`, `RenderStopped`, `MigrateError`. The hundred-odd `raise SystemExit(...)` in the tools are now these, and the thirty-odd places that caught `SystemExit` to carry on catch the kind they mean, or `errors.PROBLEMS` (these and `cli.Usage`), so a real exit is never swallowed. Exit codes are unchanged; `tests/test_contract.py` pins them and keeps `SystemExit` out of the engine.
- **Errors go to stderr.** A build stopped by a cue lost in every take, the web cost ceiling, an over-long paragraph for a service, a web service's refusal, a missing profile or no coach now says so on stderr, through `cli.run`, instead of printing to stdout and exiting from inside the render.
- **The large modules are split by job, behind the names they had.** `context.py` keeps the profile, coach files and the command line; the front matter, the file store and its schema, the health file and the session log are `frontmatter.py`, `store.py`, `health.py` and `sessionlog.py`. `render.py` keeps the orchestration and the encode; the PCM work, the clip cache and `builds.jsonl` (its writers and `log-session`'s readers together) are `audio.py`, `clipcache.py` and `records.py`. Both re-export every moved name, so no caller changes; the moves are verbatim, and briefs, exports and both render routes come out as before.
- **One contract for the web voice services.** `cloud.service_module(name)` is the one lookup; `tools/services/__init__.py` states the contract (`speaker`, `design`, `save`, `delete`, in one argument order, checked by a test) and two optional flags, `STORES_DRAFTS` (Gemini) and `DESIGN_NOTE` (ElevenLabs), which replace the names `coaches.py` hard-coded. It also reads `knowledge/services.toml`, so `keys.py` no longer imports `cloud.py` and that import cycle is gone.
- **Shared helpers instead of copies:** one WAV writer (`tools/wav.py`, used by the engine and the maintainer's coach tools); `frontmatter.wrap` for every settings block `migrate` writes (it refuses one that doesn't parse); and one apostrophe folding (`catalog.fold`) for the menu scan, the name matcher and the take check, so "farmer’s", "farmer‘s" and "farmerʼs" read alike everywhere.
- **One reading of each setting.** `context.str_list` and `table_list` read the list settings for every tool, and `shape_problems` reports what they forgave; a kit's weights are read once (`kit_weight_table`) for both the brief and `check`, which used to keep its own copy of the rules.
- **The catalog is loaded once per command** (`catalog.default()`, reloaded when either catalog file changes), and `resolve` looks names up in an index instead of scanning every name and alias: `log-session` parsed the catalog four or five times and resolved every movement of every past session by a scan. A test holds the index to the scan's answers for every name in the catalog. The brief's menus are unchanged.
- A feed item's link goes into the research sheet only when it's a plain http(s) address.
- Stale names: a persona file's comments name Pocket for a local coach and cover Gemini and Inworld; docs say `me/coaches/`; `doctor.model_present` (unused) is gone; `locks.py` no longer claims the maintainer's coach tools take the render lock.
- `tests/test_contract.py` pins the command line's exit codes (help 0; a mistyped command or option 64 on every command); `tests/test_integrity.py` covers the above.

## [0.16.0] - 2026-10-27

Pocket TTS is settled as the local voice, so the research that chose it leaves the engine: the audio bench, its results and the voice research note. Nothing a workout uses changes.

**Version numbers restart at 0.16.0.** This release was first tagged 16.0.0; sweatcast is pre-1.0 in fact, so every release is renumbered in Semantic Versioning's 0.x form: old major X is now 0.X, and its releases count up as patches in order. The tags and GitHub releases were recreated under the new numbers on the same commits (each tagged commit's own `VERSION` file still shows the number it shipped with), and every version this changelog, the docs and the tools mention uses the new numbers.

| Old | New | Old | New | Old | New |
|---|---|---|---|---|---|
| 0.1.0–0.6.0 | 0.0.1–0.0.6 | 6.0.0, 6.1.0, 6.2.0 | 0.6.0, 0.6.1, 0.6.2 | 10.0.0–10.4.0 | 0.10.0–0.10.4 |
| 1.0.0, 1.1.0 | 0.1.0, 0.1.1 | 7.0.0, 7.1.0, 7.2.0 | 0.7.0, 0.7.1, 0.7.2 | 11.0.0, 11.0.1 | 0.11.0, 0.11.1 |
| 2.0.0 | 0.2.0 | 8.0.0, 8.0.1, 8.1.0 | 0.8.0, 0.8.1, 0.8.2 | 12.0.0, 13.0.0 | 0.12.0, 0.13.0 |
| 3.0.0, 3.0.1, 3.1.0 | 0.3.0, 0.3.1, 0.3.2 | 9.0.0, 9.1.0, 9.1.1, 9.1.2 | 0.9.0, 0.9.1, 0.9.2, 0.9.3 | 14.0.0, 14.1.0, 14.2.0 | 0.14.0, 0.14.1, 0.14.2 |
| 4.0.0 | 0.4.0 | 5.0.0–5.4.0 | 0.5.0–0.5.4 | 15.0.0, 16.0.0 | 0.15.0, 0.16.0 |

### For forks
- **Tags changed names.** `git fetch --tags --prune-tags --force` drops the old `v1.0.0`…`v16.0.0` tags and fetches the new ones. A checkout or script pinned to an old tag uses the new name from the table (`v12.0.0` is `v0.12.0`, which is where `./sweatcast migrate` sends a folder older than 0.9). The old `v0.3.0`…`v0.6.0` tags are now `v0.0.3`…`v0.0.6`, and the names `v0.3.0`…`v0.6.0` belong to old 3.0.0…6.0.0.
- **From here,** a 0.X.0 release may break something and says what to do here; a 0.x.Y release doesn't.
- **`./sweatcast bench` is gone,** with `tools/bench.py`, `tools/bench_worker.py`, `tests/test_bench.py` and `docs/audio-bench/` (the script, the 2026-10-26 results and their listening files). CLAUDE.md no longer has "run the MAC/PC audio test harness". Git history keeps all of it: `git checkout v0.15.0 -- tools/bench.py tools/bench_worker.py docs/audio-bench` brings it back.
- **`knowledge/research/2026-10-25-local-voices.md` is gone;** `knowledge/voices.md` keeps what it decided.
- **The maintainer's coach tools** (`tools/coachmaker/`) now run in the engine's own environment through `common.py` (Pocket, untrimmed, and the take checker's recognizer), not the bench's throwaway ones. `qa.py` and `embed_worker.py` are gone; the ear approvals and every build's take check cover what they measured. `export_pocket.py` loads the gated Pocket model in `.venv` (a Hugging Face login with its terms accepted, as before).
- **Disk:** a computer that ran the bench can delete `.cache/bench/` and `.cache/uv-bench/`; `./sweatcast models` names the models nothing uses.

## [0.15.0] - 2026-10-27

Ten local coaches ship with sweatcast, all on one local engine, Pocket TTS, on every computer. Each was designed once from a description, heard and approved by ear, and ships with its voice file, recorded counts and cues, a measured pace and a 45-second sample to choose by ear. Countdowns play those recorded numbers one second apart instead of a voice rushing through them. Local coaches are now chosen, not made: a voice of your own is a web coach.

### For forks
- **Run `./sweatcast migrate`** (setup runs it). `me/personas/` becomes `me/coaches/`. A local coach of your own moves to `me/coaches/.archive/`, since only the ten stock local coaches render now; old log lines still find it by name. An unmade copy of a stock web coach (Reed, Ellis, Nolan, Owen, still `pending = "design"`) goes to the backup, since the engine ships them now; a made one stays in `me/coaches/` and is used over the stock copy. `me/.gitignore`'s `personas/` rules become `coaches/` rules. No context file changes its schema.
- **The local engine is Pocket TTS on PyTorch everywhere**, the extras `cpu` (an Apple Silicon Mac, or a PC's processor) and `cuda`. MLX, Chatterbox Turbo, Qwen3-TTS and the local voice designer are gone from the engine. A `.venv/.sweatcast-extra` of `mlx` becomes `cpu`; rerun `./sweatcast setup`, which downloads Pocket's public model (about 0.6 GB) and the take checker (2.5 GB, now the ONNX Parakeet on every computer, so a PC's takes are checked too). No Hugging Face login is needed. The old models stay in `models/` until you delete them: `./sweatcast models` lists them with their sizes (about 30 GB on a Mac that ran everything). An Intel Mac has no local voices any more (PyTorch has no build for it).
- **Stock coaches live in the engine, in `coaches/`**, not in the template. This reverses 0.9.x's move of Coach Andy into `me.example/`: ten coaches with their voice files are public, versioned assets a release should be able to improve for everyone, and about 160 MB doesn't belong in each listener's private backup. The four stock web coaches moved there too. `personas.all()` merges `coaches/` with `me/coaches/`, yours winning on a name clash.
- **Removed commands:** `coaches design`, the local `coaches keep` (a take or a clip), `coaches set <coach> local.engine`, `coaches download --all` and `setup --all`. `coaches keep <audition>/<letter>` for web coaches is unchanged.
- **Countdowns are written as `[count 5 go]`.** With a coach that has recorded counts the lint refuses one written in words (three or more number words counting down); a coach without (a web coach) says the marker's count in words. With any coach, one word alone between markers ("Hold.") is refused too, since a local voice garbles it often; the message points to `[cue …]` where it's a cue. The smoke test changed to match; a fork's own drafts need the same change. The brief's new Counts line says how the coach counts.

### Added
- **The ten stock local coaches** (`coaches/coach-<name>-local/`): Andy, Marcus, Theo, Sam and Callum; Maya, Claire, Rosa, Helen and Kate. `coaches/roster.toml` holds each description and how it talks, and how each was made (designer, model revision, seed).
- **`[count N cue]` and `[cue x]`** in drafts (`tools/counts.py`): a coach's recorded five, four, three, two, one, a second apart, then go, rest, switch, switch sides, stop or hold; or one cue alone. The lint times them exactly from the clips; the render lays them on the beat; the transcript says them in words. A web coach says them in words.
- **Choosing a coach by ear:** setup's quick start and the coach skill's "switch coach" offer the ten by style, with their samples.
- **Maintainer tools** (`tools/coachmaker/`, not listener commands): `design.py` (Qwen3-TTS VoiceDesign through mlx-audio, in its own environment), `pick.py`, `export_pocket.py` (the gated Pocket model makes each `pocket.safetensors`), `qa.py`, `cues.py`, `sample.py` and `persona.py`.
- **`./sweatcast models`** lists the models older versions downloaded that nothing uses now.

### Changed
- **The take check runs on every computer** with Parakeet TDT 0.6B v3 through ONNX on the processor.
- **The engine refuses Pocket's gated cloning model** (`engines.public_only`), so a Hugging Face login never changes a coach's voice.
- **A stock local coach ships measured** (its pace from its sample), so no smoke test before a first workout; this computer's measurements go to the shared `me/workouts/.audio-cache/voice-pace.json`, so `me/coaches/` holds only your own coaches.
- **The audio bench** keeps cloning Andy's old clip, now `docs/audio-bench/voice/`, so runs stay comparable.

### Notes
- **Why Pocket alone:** in a blind test on 2026-10-26 Pocket was preferred over Chatterbox Turbo for six coaches, Turbo for three, one even; on the audio bench it never dropped a cue word in 176 takes and renders two to six times faster, in a third of the memory.
- **Not yet tried by hand:** a real build on the PC (its processor and its NVIDIA card), and the recognizer's speed on a PC's processor.

## [0.14.2] - 2026-10-26

The audio bench: every candidate local voice model reads the same five-minute script on a Mac and on a PC, measured and scored the same way, so the next local voice can be chosen on evidence. Nothing a workout uses changes.

### Added
- **`./sweatcast bench`** (`tools/bench.py`, `tools/bench_worker.py`, `docs/audio-bench/`):
  - **The candidates:** Chatterbox Turbo, Qwen3-TTS 1.7B, Lure 0.6B, Ming-3.0-tts 0.5B and Pocket TTS.
  - **The script:** `docs/audio-bench/script.toml`, 44 lines with a kind each.
  - **Where each model runs:**
    - on a Mac, through mlx-audio 0.6.1 (Pocket TTS on the processor);
    - on a PC, on the NVIDIA card, then the small ones on the processor;
    - each in its own throwaway uv environment, pinned to one model revision.
  - **The voice:** every model clones Coach Andy.
  - **Scoring:** one recognizer for both computers (Parakeet TDT 0.6B v3 through ONNX) and `verify.judge`.
  - **Results:** `docs/audio-bench/results/<date>-<mac|pc>/` holds `run.json`, `takes.jsonl`, `summary.md` and a listening MP3 per model.
  - `--quick` checks that every model installs and speaks; `--models` and `--seeds` narrow a run.
- **CLAUDE.md:** "run the MAC audio test harness" and "run the PC audio test harness" run the bench on that computer, then commit and push its results.
- Tests: `tests/test_bench.py`.

### Notes
- **Pocket TTS's voice-cloning weights are gated on Hugging Face.** Each computer needs its terms accepted and `uvx hf auth login` once; without that, the bench records it as gated.
- **Tried on an M5 Mac with `--quick`:**
  - Turbo, Qwen3, Lure and Ming each spoke three lines with no word errors.
  - The PC's PyTorch setups for Turbo and Lure ran on the Mac's processor.
  - Ming on CUDA and Pocket TTS are untried until the PC run.

## [0.14.1] - 2026-10-25

Every local take is now heard before it ships. A speech recognizer checks each clip against its line, renders a take that drops a cue word or breaks down again with the next seed, and stops the build only when four takes in a row lose the same cue. Clips are leveled to one speech level and lightly compressed before the loudness pass. Countdowns lose their ellipses, which made Chatterbox Turbo drop the words after them.

### For forks
- **A Mac downloads 2.5 GB more:** Parakeet TDT 0.6B v3 (`voices.CHECK_MODEL`, pinned), fetched with the coach's model by `./sweatcast setup` or `coaches download`, else on the first build. The readiness check now wants 9 GB free, up from 6.
- **The lint refuses an ellipsis** ("..." or "…") in spoken text. A draft with one fails until it uses commas or periods; `knowledge/tts-rules.md` and the smoke test changed to match. A customized `tts-rules.md` that teaches "Three... two... one..." needs the same change.
- **Exit 1 has a new cause:** a line whose cue word (go, rest, switch, stop, left, right, a count) the voice dropped in every take. The workout skill says to reword it; run `./sweatcast harness sync` after merging the skill.
- **The clip cache gains `<hash>.check.json` verdicts** beside the clips. Clips cached before this release are heard once on their next build, and only failed ones render again.

### Added
- **The take check** (`tools/verify.py`, `render.check_takes`, `engines.listener`):
  - Each new local clip is transcribed and aligned with its line. Digits are read as words, and a compound heard split or joined counts as said.
  - The audio itself is checked for a runaway or cut-off take against the coach's pace, a silence over a second and a half inside a clip, and clipping.
  - A take passes with every cue word said, no audio problem, and at most one word in twenty off. Otherwise the next seeds are tried, up to four takes, and the best is cached under the line's own key, so builds stay repeatable.
  - An unclear line keeps its best take and is listed; a line still missing a cue stops the build and names what was heard.
  - The build record says what was checked (`check`).
  - `./sweatcast build --no-check` skips the check. Web coaches aren't checked (each take is billed), nor is PyTorch on Windows or Linux yet.
- Tests: `tests/test_verify.py`.

### Changed
- **Clip leveling:** each clip's speech is brought to -24 dBFS (at most 12 dB either way, peaks under -1 dBFS) before assembly. Measured takes sat up to 4 dB apart, which the whole-file loudness pass couldn't even out.
- **A gentle compressor** (2.5:1 above -20 dBFS) runs ahead of both loudness passes, so quiet syllables stay audible over gym noise. The smoke test now measures a loudness range of 4.5 LU.
- **Countdowns use commas or periods.** On Chatterbox Turbo, "Three... two... one... and rest." lost "and rest" in three takes of five (seed 42, the default, among them); with commas or periods, nothing was lost in ten takes.
- `cache prune` removes a clip's verdict with it.

## [0.14.0] - 2026-10-25

A second review of the harness, after 0.13.0. The safety gate closes the holes that let an unsafe movement reach the MP3; nothing is paid for before the draft passes its checks, and nothing half-written is left in the delivery folder; the session log takes its facts from the menu and the build instead of retyping them; and two commands, a pantry fallback and the copies of the service list are gone.

### For forks
- **Commands gone:** `./sweatcast lint` (use `./sweatcast build <draft> "<name>" --lint-only`) and `./sweatcast render` (use `./sweatcast build`); both exit 64 naming the replacement. With them go lint without a coach and `--force`, `--strict`, `--wpm`, `--min-fill`, `--max-fill`, `--word-tolerance`, `--require-menu` and `--out`; also `content pantry` (use `content reserve`) and `coaches design --designer`.
- **Run `./sweatcast migrate`** once: it moves `me/workouts/research/pantry/` into `reserve/` (never overwriting; a sheet already in the reserve keeps its place and the pantry's copy goes to the backup unless the two are identical) and rewrites `told.jsonl`'s `pantry` keys. The tools no longer read the old name.
- **`log-session --draft`** now takes the date, length and kit from the draft's menu (a typed `--date`, `--minutes` or `--kit` that disagrees is refused; a session built with `brief --equipment` logs as `custom: <ids>`), needs a build record for that draft, requires `--format`, refuses a second line for the same date and movements, and writes `--loads` and `--rpe` names as the catalog's (a name that isn't one of the session's movements is refused). A customized workout skill's step 7 needs merging.
- **`health.md`:** an `Avoid:` line takes ids, flags (any case) or movement names, and an unknown word now stops the screen, as `--avoid` did; a `[[limits]]` row with an unknown key (`flag` for `flags`) stops it too; `check` notes an injury in the prose with no row. Run `./sweatcast check` after upgrading.
- **Drafts:** every one-word alias is scanned except a short list of everyday coaching words (`menu.EVERYDAY`), so "pushups" or "RDLs" now count; a "no" or "not" excuses a mention only right before it, with only small filler words between ("no rest between jumping jacks" counts). A draft that passed before may now name a movement to reword or declare.
- **Services:** `knowledge/services.toml` is the one list; a fork's own service section needs `key_var`, `key_page` and `candidates`. Skills that grepped `builds.jsonl` for a first web build use `./sweatcast get web-builds`; run `./sweatcast harness sync` after merging a skill.
- **Removed names:** `render.main`, `render.ffmpeg_exe` (use `ffmpeg.exe()`), `tts_build.main`, `tts_build.menu_check`, `personas.last_coach` (use `default`), `personas.WEB_SERVICES`, `context.ROUTE_NAMES`, `context.delivery`, `coaches.archive`, `coaches.last_line`, `coaches.DESIGNERS`, `paths.OLD_PANTRY`, `content.folders`, `content.used_slug`, `reserve(folders=)`. `render.run` and `build_record` now require `draft_path` and `draft_sha256`.

### Added
- **Jumping and sprint moves in the catalog:** burpee, mountain climber, jump squat, tuck jump, jump lunge and skater hop as full movements (impact-flagged, so they reach the menu only where it is safe), and box jump, broad jump, jump rope, running sprint and clap push-up as drafts (never on a menu, but named in a script they stop the build). Before, "twenty burpees" passed the scan for a delicate knee.
- **`./sweatcast get web-builds`:** how many web renders this computer has sent, for the skills' first-web-build notice.
- **`knowledge/research/`:** the evidence behind the knowledge files (training, biomechanics, exercises, equipment), one dated note per question, with an index of what each feeds; the session-structure research moved here from `docs/research/`.
- **A `failed` line in `builds.jsonl`** when a web render sent text and then failed, with the characters sent and the estimated cost.
- Tests: `tests/test_safety.py` (the scan, limits and Avoid lines), `tests/test_log.py` (the session and content log), and tests for every fix below, each failing before it.

### Changed
- **Off-limits rules out impact work, as delicate does.** Before, an off-limits neck, wrist, rib or groin kept jumping jacks, high knees and the treadmill run that a delicate one removed.
- **A pending web coach is designed only after the lint and the menu gate pass**, at its estimated pace; before, a draft that failed its checks had already paid for a voice.
- **The content log** checks each item's category against the ones the plan rotates for its slot, and refuses a reserve slug already told.
- **Backup asks GitHub on every push** whether the remote is private; a remembered answer is used only when GitHub can't say. Pushes run with `ssh -o BatchMode=yes` (unless you set `GIT_SSH_COMMAND`) and give up after five minutes.
- **The workout skill** names a workout's stem one way (`<date>-<goal>-<minutes>`, with `-2` when the folder exists), lints once, and logs with fewer flags; `script.md` points to `tts-rules.md` for paragraph length, names and box breathing instead of repeating them (its `[pause]` limit had disagreed).
- **Simpler code:** the service list in one place, `encode` reusing the render's preflight, and dead constants, wrappers and one-option abstractions removed (about 130 fewer lines in `tools/`).

### Fixed
- **`content plan` and `content reserve` crashed** (0.13.0): a parameter named `folders` hid the function of that name, so the workout skill's filler step failed every session.
- **A brought clip** in M4A, WebM, AIFF or another format was read as raw sound and saved as noise; every clip that isn't a 16-bit WAV now goes through ffmpeg.
- **A `@@ 0` segment** is refused when the draft is read; before, it crashed the render after every clip was rendered (and billed).
- **An unreadable answer from a voice service** (not JSON, or audio that isn't base64) and a dropped connection are service errors with their exit codes, not tracebacks; a dropped connection is retried for speech and never for a design or a save. Keeping an audition candidate marks it before the save is sent, so a voice saved at the service is never lost track of.
- **Delivery, encoding and the web copy are atomic:** the copy to `deliver_to` and ffmpeg's output are written beside the target and renamed, a failed one removed; an ffmpeg failure prints the end of its error. Rebuilding a web copy removes its old parts, and a timeout is a message.
- **Stopping a web render** (Ctrl-C or a failure) stops the retries at once instead of waiting out billed attempts.
- **`coaches measured`** answers 0 for a web coach, pending or made (it needs no smoke test); **`--tolerance`** accepts only a finite value from 0 to 0.5.
- **The profile split and the `.gitignore` update in `migrate`** write atomically.

### Removed
- `docs/superpowers/` and `docs/plans/` (shipped plans and specs; in the history), and `docs/eval/skeletons.sh` (the retired composer's baseline).

## [0.13.0] - 2026-10-25

A review of the whole harness, hardened where a check could be skipped and simplified where the same rule lived in several places. The build runs in one process; the menu is today's or the build stops; a key can't leak into a message; the tools exit with the documented codes from every entry point; and the code for sweatcast 0.8 and earlier is gone.

### For forks
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it) from a `me/` at sweatcast 0.9 or later. A folder from sweatcast 0.8 or earlier (context schema 3 or below) is no longer migrated here: check out `v0.12.0`, run `./sweatcast migrate` there, then come back and run it again; the tool says so.
- **Gone:** `--voice` (use `--coach`) on build, render, lint, brief and log-session; `./sweatcast voices` (use `coaches`); `./sweatcast get default-voice` and `get voices` (use `get coach` and `coaches`); the sweatcast 0.8 voice import and `migrate --name`; the profile template's `## Narrator` section (how a coach talks lives in `persona.md`). `./sweatcast check` is its own tool (`tools/check.py`); `context.py check` is no more.
- **The menu is today's.** `./sweatcast brief --save` now records the day and a hash of `me/health.md` in the menu, and a build (or `./sweatcast render`) stops on a menu from another day or from before `health.md` changed; `--lint-only` warns. Rerun the brief with `--save` and build again. A menu saved by 0.12.x has no hash, so the first build after upgrading asks for a fresh brief. `./sweatcast render` and `./sweatcast lint` now hold a draft to its menu as `build` does; only `knowledge/smoke-test.draft.txt` itself builds without one (a copy of it elsewhere doesn't).
- **Drafts:** the text scan now reads one-word movement names (deadlift, thruster, woodchop, clamshell, inchworm, elliptical), spaced plurals ("push ups", "step ups"), and a shortened name that is itself another movement ("push-ups" after a declared wall push-up, "shadow boxing" after a declared seated shadow boxing); a "no" or "not" excuses a mention only in its own clause. A draft that passed before may now name a movement to reword or declare.
- **`log-session`** refuses a coach that doesn't exist (archived ones still log), a kit that isn't one of the profile's or a preset, a format that isn't a `sessions.toml` method, and any line break in a field. **`content log`** accepts the slot as the plan names it ("deep dive") and refuses a reserve slug with no sheet.
- **The template** (`me.example/`): `health.md`'s clinician line is `- Rule: [...]`, `content.md`'s "Never bring up" takes a hint (write "nothing" for none), an empty `- Label:` line is noted as unfilled in every file (a note, so a 0.12.x folder's empty lines don't fail `check`); `knowledge/sessions.toml` drops the retired composer's `blocks`, `min_slots` and `fixed` keys (a fork's copy keeps working; the loader ignores them).
- A customized workout skill needs merging: the brief and the lint take `--coach`, the "Would open up" rerun uses `brief --add <item>`, and steps 6 and 7 explain a stale menu and a malformed `--item`. Run `./sweatcast harness sync` after.

### Added
- **`brief --add <ids>`:** equipment on hand today, added to the kit, so the kit's weights still print (in place of rerunning with `--equipment`).
- **`./sweatcast backup --unverified`:** pushes when GitHub won't say whether the remote is private (after you checked); without it, such a push is refused, as a public one is.
- **`tools/check.py`**, `tools/fileio.py` (one atomic writer for every record, menu and context file), `tools/common.sh` (what the shell scripts share), `tests/helpers.py` (test isolation: every path redirected to a temporary home; a fixture draft given its menu).
- **Tests** for every bypass and gap this review closed: the render command needs a menu, the smoke test is known by its place, a stale menu, a changed health file, the scan cases, a key with a stray character, the hook's path list, backup's refusals, a long `Retry-After`, an unclosed `+++` block, one bad coach file, `--no-web` in a cloud session, unknown build flags, `cache prune` under the lock.

### Changed
- **One build process.** `./sweatcast build` parses its flags with argparse (an unknown flag exits 64 before anything runs or costs money), resolves the coach and route once, reads the draft once, and runs the lint, the menu gate and the render on that same text, so nothing can slip in between the lint and the render. The render's native chatter is logged by pointing the standard error descriptor at `me/workouts/.logs/<name>.log`, which is appended to with a dated line. `render.run`, `render.clips` and `render.follow` are what it calls; `./sweatcast render` is a thin wrapper that enforces the same menu rule. In a cloud session, `--no-web` now keeps the MP3 instead of deleting it.
- **One exit-code mapper:** `cli.run` wraps every tool's `main`; an unknown coach, a missing draft, a web coach with no key here and a bad `--engine` exit 64 from every command (before, 1 or 64 depending on which tool caught it); a service's refusal exits 4 everywhere; `screen.Unfit` exits 1.
- **One place each** for the service names (`cloud.service_name`), the render list (`context.render_preferences`), coach matching and folder listing (`personas.find`, `personas.persona_dirs`), the smoke test (`draft.is_smoke`), the build record's path (`workouts.record_path`), float-to-PCM, the version lookup, and movement-name matching (`catalog.resolve`: side words, plurals, hyphen or space). The lint predicts no chime under `--no-chime`, computes each segment's paragraphs once, and uses the render's rule for a held segment.
- **The shell scripts** share `tools/common.sh`; setup reads the render list through `./sweatcast get routes` instead of `sed` over TOML, keeps a `core.hooksPath` it didn't set, and matches `.env` literally.
- **`knowledge/sessions.toml`** carries only what the writer sees; the brief prints each method's work and its own rest (a circuit's rest between rounds).
- **`./sweatcast movements`** defaults to the profile's level.
- **Research paths** (`feeds`, `youtube`, `content`) are read at call time, so a redirected home redirects them too.

### Fixed
- **Keys:** a key is stripped of the whitespace around it, one holding a line break, a space or a symbol is refused by name (never shown) where it would be used, and counts as "not set" to the coach list, the default coach and the readiness check (so one bad key for a service you don't use stops nothing else; `./sweatcast keys` names it), an inline `# comment` isn't part of it, and every message the engine prints is scrubbed of key values. Before, a key with a stray line ending in the environment made the HTTP client raise an error whose text held the whole key, which the render and the audition printed.
- **The pre-push hook** now covers a renamed context folder (`me.real/`), the old top-level layout's files, `.env`, `personas/` and `voices/`, and spares only `me.example/`; its pattern has a test with must-match and must-not-match lists.
- **Backup** refuses any file named like a key file, not only `.env`, and fails closed when a GitHub remote's visibility can't be read (`--unverified` pushes once you've checked, and the answer is remembered for that remote on this computer, as is a "private" GitHub gave; a `GH_TOKEN` or `GITHUB_TOKEN` in the environment lets the read see a private repo, as on Claude Code on the web); `git` never waits on a credential prompt.
- **An unclosed `+++` block**, or a byte order mark from a Windows editor, no longer reads as "an older format, run migrate" (which would have wrapped the settings as prose); `check` names the broken block. One coach file the tools can't read no longer hides the others.
- **A 429 with a long `Retry-After`** is a quota, exit 4, instead of being slept through (up to five waits of an hour). A 5xx page mentioning "payment" is an outage, not a billing refusal. Fish Audio, ElevenLabs and Inworld designs (billed) are never retried after sending.
- **Before a clip is rendered** (or billed), the render checks ffmpeg is here and the output name ends in `.mp3`, `.m4a` or `.wav`.
- **`cache prune`** waits for the render lock, so it never deletes a clip a render is reading.
- **Windows:** a delivery folder on another drive no longer crashes `paths.show`; a missing `sh` leaves the readiness facts readable instead of crashing every build.
- **`pace.json`** records a short hash of the computer's name, not the hostname.
- **`harness`** copies a binary file in a skill, removes a dropped skill's subfolders, writes the Codex rule path with forward slashes on every system, and checks the three `.env` deny rules are still in `.claude/settings.json`.
- **`check`** notes a setting no tool reads (`deliver-to`: did you mean `deliver_to`?) and finds the quick-start flag beside the files it checks.

### Removed
- Migration from context schemas 0 to 3 and the sweatcast 0.8 voice import (`to_1` to `to_4`, `plan_coaches`, `make_coaches`, the `v0.8.1` clips, `tests/test_migrate4.py`, `tests/v8.py`); `--voice`, `./sweatcast voices`, `get default-voice`, `get voices`; `context.voices`, `default_voice`, the schema-1 `---` front matter and the legacy profile parser; `sessions.all_out`; the unreachable `setup` and `doctor` branches in `tools/sweatcast.py`; the `## Narrator` section.

## [0.12.0] - 2026-10-25

The profile is four files, split by how often each part changes and who reads it, so a workout reads a few dozen lines about you instead of a few hundred, and adding a feed can't touch your kits.

### Changed
- **The profile splits** (context schema 6):
  - `me/profile.md`: who you are (`name`, `experience`, the Basics and Listening setup prose). Rarely changes; every workout reads it.
  - `me/training.md`: how you train (`likes`, `dislikes`, `[[kits]]` with their weights, the Default session and Equipment kits notes). Changes with new gear or check-in feedback; every workout reads it.
  - `me/content.md`: what fills the rests (`youtube_favorites`, `puzzles`, `[[interests]]`, `[[feeds]]`, the Content and Taste prose). Changes most; only research and the story tools read it.
  - `me/settings.toml`: the tools' own settings (`setup`, `render`, `cloud_max_chars`, `deliver_to`, `words_per_minute`), plain TOML.
- **One reader:** `context.profile()` merges the four files' settings and joins their prose, so every tool reads them as before. A setting still counts in any of the four files, but each has a home file, which wins if it's written twice; `./sweatcast check` notes the duplicate and names each issue's file.
- **The template** (`me.example/`) comes in the four files, made by the same split, and its Equipment kits section no longer repeats the kit settings.
- **The skills** read and write the right file: a workout reads `profile.md` and `training.md` (research reads `content.md`), setup writes each setting to its home, and `setup = "quick"` lives in `settings.toml`.
- **Docs:** the README has a table of your files; CLAUDE.md describes the four files and their homes; the `render` setting's comment says it lists audio routes.

### Fixed
- `./sweatcast setup` reads `render` from `settings.toml` (an older folder's `profile.md` still works) when deciding whether to install the local engine.
- Messages that pointed at `profile.md` for feeds, YouTube channels and the web ceiling point at their new files.

### For forks
Run `./sweatcast migrate` once (or rerun `./sweatcast setup`, which runs it). It backs up `me/` first, splits `profile.md` into the four files and bumps `health.md` and `log.md` to schema 6. Each setting keeps its value; the settings' comments become the template's (your originals are in the backup). Any `## ` section of your profile other than Equipment kits, Default session, Content and Taste stays in `profile.md`. If `training.md`, `content.md` or `settings.toml` is already in `me/` (copied from the new template, say), migrate replaces it; the original goes to the backup.

## [0.11.1] - 2026-10-25

The README, CLAUDE.md and AGENTS.md are rewritten to be shorter and checked claim by claim against the code, and sweatcast can now be supported.

### Added
- **Support:** a Sponsor button on the repo (GitHub Sponsors and Ko-fi, `.github/FUNDING.yml`) and a line at the end of the README.
- **Invite a friend:** one message at the top of the README that works for someone with Claude or ChatGPT.

### Fixed
- **README:** segments don't all start on the clock (a segment with spare time ends early; only the total is held to plan); the disk and download figures now match the readiness check (6 GB free; about 4 GB on a Mac, up to 8 GB on Windows or Linux); the backup command commits before pushing and says it needs the GitHub CLI; Qwen3's render speed is no longer folded into Chatterbox's; Windows needs Git for Windows; an audition needs a voice key; coach folder names; and the license list covers Linux and the MLX tokenizer.
- **CLAUDE.md:** reorganized (what runs when, the listener's files, knowledge, tools by area, tests, audio, releases) with the errors fixed: the `render` setting lists routes, not engines; the lint doesn't read `words_per_minute`; the default web coach is made during setup's quick start; the feeds sheet's path; the `render` command and `test_tools.py`; the release rule now covers 0.11.0.
- **AGENTS.md:** tighter, and it gives every reason `./sweatcast` runs outside Codex's sandbox.
- **The setup skill** quotes the same download sizes as the README.
- **The profile template's `words_per_minute` comment** said the lint uses it; it doesn't.

## [0.11.0] - 2026-10-25

sweatcast runs under ChatGPT's Codex as well as Claude Code: Codex in the ChatGPT desktop app (any plan, Free included), the Codex CLI or an IDE, on the listener's own computer. Tried end to end with the Codex the ChatGPT app ships, on the Free plan's model: setup, then a ten-minute workout with Coach Andy on the local voice.

### Added
- **Codex's files.** `AGENTS.md` sends Codex to `CLAUDE.md` and says what to use in place of Claude Code's own tools (a numbered question for a multiple-choice one, `./sweatcast show` to hand over a file, research done in turn rather than by background agents), and never to read `me/.env`. `.agents/skills/` holds exact copies of the setup, workout and coach skills (the ChatGPT app's own import of Claude skills makes the same copy, so it changes nothing). `.codex/config.toml` turns on the sandbox's network, and `.codex/rules/sweatcast.rules` lets `./sweatcast` run outside Codex's sandbox, as `.claude/settings.json` allows it in Claude Code (both are read once the folder is trusted).
- **`./sweatcast harness`** checks that Codex's files match Claude Code's; `./sweatcast harness sync` rewrites them. Claude Code's files stay the one source: edit a skill there, then sync. The tests fail when they're out of step, and when the Codex rule and the Claude allow list stop naming the same command.
- **The README's ChatGPT path:** Start here, a message to send a friend with ChatGPT, where it runs, and the For Claude handoff for Codex.

### Changed
- **Inside Codex's sandbox without the rule** (an untrusted folder): `./sweatcast` keeps uv's cache in the project (`.cache/uv`, git-ignored), setup skips the privacy hook with the reason instead of stopping, and a local render that can't see the GPU says to run it again outside the sandbox.
- **Before the first workout under ChatGPT,** Codex says that ChatGPT may use what it reads, health notes included, for training unless "Improve the model for everyone" is off.

### For forks
Nothing to migrate: `me/` and every command work as before. If you change a skill, run `./sweatcast harness sync` and commit `AGENTS.md` and `.agents/skills/` with it.

### Known limits
- The key in `me/.env` is kept from Codex by instruction, as it is from Claude Code's shell commands; Codex followed it in every test. A system-level block is possible in Codex, but it stops sweatcast's own engine reading the key too, so web coaches couldn't speak.
- Not yet tried by hand in the ChatGPT app's window: its trust prompt, its multiple-choice questions, and its approval prompts.

## [0.10.4] - 2026-10-25

Onboarding is tidied for the two ways people actually start: a developer in an IDE or terminal, and a friend with the Claude desktop app. Claude Code on the web no longer sets up a new listener.

### Added
- **`./sweatcast show <file>`** opens the folder holding a file with it selected (Finder, Explorer or the file manager). Setup and the workout skill use it when the MP3 or a test clip can't be sent into the chat, so a listener never gets just a path.
- **Send this to a friend:** a README section with a message to paste to someone who has the Claude desktop app.

### Changed
- **The desktop path, step by step.** The README's Start here says which folder to pick when the Code tab asks (the home folder), to click Allow, and how to start the second session in the new `sweatcast` folder; the For Claude handoff uses the same literal steps.
- **One recommended voice service.** When a web coach is needed, setup recommends Fish Audio for a first key and walks through it with links (sign up, add credit, make a key), listing the other three with their key pages as more choices.
- **The phone folder comes right after the first workout,** as one question (iCloud Drive, Google Drive, Dropbox, or keep them on this computer), instead of waiting for "finish setting me up".
- **Claude Code on the web doesn't set up a new listener.** Setup and the README's For Claude section point to the desktop app instead. A listener already set up, with their private context repo attached, keeps working there.

## [0.10.3] - 2026-10-25

A new listener hears their stand-in coach before the first workout, and coach folders say where each coach speaks.

### Added
- **A test clip before the first workout.** Coach Andy, the local stand-in, ships with `sample.mp3`, fifteen seconds rendered on Chatterbox Turbo, which setup plays first. A web stand-in is made right after the key step (`./sweatcast coaches make`, its cost said first) rather than at the first build, and setup plays the clip that saves; a designed voice belongs to the account that made it, so each listener's is their own. Either way: if he isn't right, "I want a new coach". The setup skill, README, voices guide and CLAUDE.md say so.

### Changed
- **Coach Demo is Coach Andy**, in `me.example/personas/coach-andy-local/`, with "Coach Demo" kept as an alias, so log lines naming him still find him.
- **Coach folders name where the coach speaks:** the web stand-ins are `coach-reed-fish/`, `coach-ellis-elevenlabs/`, `coach-nolan-gemini/` and `coach-owen-inworld/`, and a coach kept from now on gets `coach-<name>-<service>` or `coach-<name>-local` (`personas.folder_for`). A coach already in a folder keeps it, and lookup by the plain slug (`coach-maya`) still finds `coach-maya-fish`.

### For forks
Nothing to migrate: folders in `me/personas/` keep their names, and renaming one by hand to the new pattern is safe (pace and sample move with it; cached clips are keyed by the voice, not the folder). The new stand-ins come only with a new `me/`; to have Coach Andy's clip, copy `me.example/personas/coach-andy-local/sample.mp3` beside your Coach Demo.

## [0.10.2] - 2026-10-25

The pantry is now the reserve: the evergreen filler (quizzes, things to enjoy, things to learn) researched ahead of time.

### Changed
- **The reserve.** `me/workouts/research/reserve/` holds the evergreen pieces, `./sweatcast content reserve` lists the unused ones, the plan prints "Reserve" and "The reserve is low", `knowledge/content.toml`'s per-slot target is `reserve`, and `./sweatcast content log` writes a piece's slug under `reserve`. The workout skill, its research templates, the script guide, the README and CLAUDE.md say the same.
- **CLAUDE.md** opens with the codegraph index: use the codegraph tool to find and read code, its callers and what a change touches, before grepping.

### For forks
Nothing to migrate. A `research/pantry/` folder is still read beside `research/reserve/` (a slug in both counts once), a record item logged with `pantry` still marks its piece as told, and `./sweatcast content pantry` still works as an alias. New pieces go to `reserve/`; move the old sheets over whenever you like.

## [0.10.1] - 2026-10-25

Setup now opens with the one big choice: where the coach's voice is made.

### Added
- **The fork, said first.** Right after the readiness check and before any question, the setup skill lays out local versus web in a few plain lines: on this computer (free and private, a one-time 3 to 4 GB download, about 0.7 times the speech's length to render on Apple Silicon) or a web coach (no download, a 30-minute workout in a minute or two, about $0.27 to $1.60 a workout with a key of your own, and the script goes to the service). It says which way this computer starts, and how to revisit it: nothing is locked in, both kinds can live side by side, and "I want a new coach", "add a voice key" or "set up local voices" changes it at any time. The README's Start here says the same.

### Changed
- **A renamed context folder stays private.** The engine's `.gitignore` now ignores `me.*/` (such as `me.real/` or `me.test/`, kept aside while trying the new-listener flow), with `me.example/` still part of the engine.

## [0.10.0] - 2026-10-25

Web coaches: describe, audition, approve, keep. A web coach is an original voice a service designs from the listener's description and saves in the listener's own account, at Fish Audio, ElevenLabs, Gemini or Inworld, pay-as-you-go with no subscription anywhere. One audition makes candidates on every service with a key, lettered and priced a workout; the listener picks by ear, names each one they keep, and a workout then uses it by name, always on the service that made it. Four default web coaches ship, one per service, designed the first time they're used. Copying a clip on the web is gone, and so are Cartesia and Deepgram: a clip-based coach is now a local coach, which renders only on the computer's own engine.

### For forks
This release changes the coach files (persona schema 4 to 5), the routes, the keys and the coach commands. After pulling it:
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it). Every coach's `persona.md`, archived ones too, gains `kind = "local"` and `schema = 5`, and nothing else in it changes; `me/.gitignore` gains `!personas/*/sample.mp3` and `!personas/.archive/*/sample.mp3` (a web coach's approved sample is kept, archived or not), `personas/.auditions/` (auditions in progress aren't) and `personas/*/.made.json` and `.made.wav` (a make between saving a voice and writing the coach). Changed files are backed up first, never `.env`.
- **Your existing coaches are local coaches now.** A clip-based coach renders locally only: clip copying on Fish Audio (the clip sent with every request) and ElevenLabs (a clone of the clip) is removed, along with `services.json`. A coach you used on Cartesia or Deepgram renders locally, or make a web coach with an audition ("I want a new coach", or `./sweatcast coaches audition`).
- **The profile's `render` list orders local engines only.** A web coach always speaks through its own service, whatever the list says; a service named there no longer renders a local coach. A local coach tries the local engine even when the list leaves it out; where local voices don't run (say Claude Code on the web, with `["fish"]` and only local coaches), `get route` and the build stop (exit 1) and name the way out: make a web coach, or copy the stand-in for a service with a key (`me.example/personas/coach-reed/` for Fish Audio, and so on) into `me/personas/`. The readiness check on the web says "No web coach yet" with the same way out, and the workout skill offers both. `cloud_max_chars` still caps what one build sends.
- **Keys:** `GEMINI_API_KEY` and `INWORLD_API_KEY` are new (`./sweatcast keys init gemini`, `init inworld`); `CARTESIA_API_KEY` and `DEEPGRAM_API_KEY` are no longer read, so delete their lines from `me/.env`. `./sweatcast keys open` opens `me/.env` in the system's editor. On Claude Code on the web, the network allowlist gains `generativelanguage.googleapis.com` and `api.inworld.ai`.
- **The four default web coaches come only with a new `me/`.** To have them, copy `me.example/personas/coach-reed/`, `coach-ellis/`, `coach-nolan/` and `coach-owen/` into `me/personas/`; each is made the first time a build uses it.
- **A sweatcast 0.8 folder migrates only from a git clone** with the `v0.8.1` tag (`git fetch --tags`): `tools/migrate-assets/v8-voices/` is gone, as promised for 0.10.0, and the migration reads the clips sweatcast 0.8 shipped from the tag. A ZIP download can't migrate one.
- **Commands:** `./sweatcast coaches samples deepgram` is gone, and `coaches design` uses the local designer only (Fish Audio and ElevenLabs no longer design local coaches' clips). New: `coaches audition`, `coaches keep <audition>/<letter> --name`, `coaches forget-audition`, `coaches make`, `coaches archive`, `keys open`.
- **`tools/msgpack_min.py` is gone** (Fish Audio now takes JSON), with `tools/services/cartesia.py` and `tools/services/deepgram.py`.
- A customized coach, setup or workout skill needs merging: the coach skill is rewritten around auditions, setup gains the keys step and the default web coaches, and the workout skill checks the coach can speak here (exit 64) and offers the stable when the coach used last is archived.

### Added
- **Web coaches** (`kind = "web"` in `persona.md`): a voice designed and saved at a service, spoken by its saved voice ID, with `[voice]` (who, sound, energy, pace, avoid: what services design from) and `[character]` (how they talk, which the brief quotes), `sample.mp3` and a pace estimated from the sample, so the first workout needs no smoke test.
- **Auditions** (`./sweatcast coaches audition <narrative> [--services ...] [--coach "<name>"] [--play]`): candidates from every keyed service in parallel (Fish Audio 2, ElevenLabs 3, Gemini 1, Inworld 2), lettered A, B, C..., each saying the same coaching line, each with its approximate cost a workout, in `me/personas/.auditions/<date>-<n>/`. A service that fails is one line; the others still land. Nothing is saved at a service except Gemini's, which stores as it designs.
- **Keep, forget, make, archive:** `coaches keep <audition>/<letter> --name "<name>"` saves the voice at its service as "sweatcast <name>" and writes the coach (several from one audition, each its own coach); with an audition made by `--coach`, it re-voices that coach, and `--replace-old` deletes the old voice at the service. `coaches forget-audition` deletes Gemini's unkept voices and the folder. `coaches make "<name>"` designs and saves a pending default's voice (builds run it). `coaches archive "<name>"` moves a coach to `me/personas/.archive/`: out of the list, still found by name for old log lines.
- **Gemini** (an AI Studio key; `gemini-3.8-flash-tts`, about $0.27 a workout until 2026-12-31, about $0.54 from 2027) and **Inworld** (On-Demand; `inworld-tts-2`, about $0.50 a workout), both tried live. Gemini takes no style setting yet (`./sweatcast check` flags a `style`), runs about 35 percent slower (pace is measured per coach), and its free tier uses requests for training with human review.
- **Four default web coaches** in `me.example/personas/`, from one description (a man in his forties, a warm baritone, a seasoned trainer): Coach Reed (Fish Audio), Coach Ellis (ElevenLabs), Coach Nolan (Gemini), Coach Owen (Inworld), each `placeholder = true` and `pending = "design"`. The first build that needs one designs it and saves the first candidate, saying so first (about $0.01 on Fish Audio and Gemini; Inworld's design cost is unpublished; one of ElevenLabs Free's 3 voice slots); `--lint-only` never does.
- **`./sweatcast keys open`:** opens `me/.env` in the system's editor (`open -e`, `notepad`, `xdg-open`) without reading it (where there's no opener, it prints the file's path); on the web, it says to use the environment's settings.

### Changed
- **Routes:** a web coach speaks only through its own service; with no key for it here, `get route` and `build` exit 64 with the fix, as does `--engine` naming another service. A local coach renders only locally. The routes are local, fish, elevenlabs, gemini and inworld.
- **The default coach:** with none named, a build takes the coach used last; if that one is archived it stops and names the stable (exit 1), and if it was a stand-in and the listener now has a coach of their own, it takes theirs; with no sessions, the listener's own coach, then a stand-in that can speak here (a web default whose key is set, then Coach Demo where local runs).
- **Exit 3 is for local coaches only:** a web coach renders from its sample's estimate, and each render measures it.
- **Fish Audio** speaks by the saved voice (`reference_id`, JSON) on `s2.1-pro`, designs and saves private models; **ElevenLabs** designs three previews and saves the chosen one, on `eleven_v4` (or `eleven_v4_turbo`), labeled "not yet tried on a Free account" (Free keeps 3 voices and a monthly allowance). `knowledge/services.toml`: rates checked 2026-10-25, `design_usd`, a `note`, all four tried live.
- `./sweatcast coaches` shows where each coach speaks (`web · Fish Audio`, `local · chatterbox`) and which are made the first time they're used. `./sweatcast check` notes a pending default, and flags a web coach with no voice or with a `style`.
- The coach, setup and workout skills, `knowledge/voices.md`, the README and CLAUDE.md describe web coaches: the keys step with each service's cost and terms, the privacy line (every service receives the script, which can mention injuries; Gemini's free tier trains on it), the quick start with the keyed service's default web coach, and the workout's offer of other coaches when one can't speak here.

### Removed
- **Cartesia and Deepgram** (`tools/services/cartesia.py`, `tools/services/deepgram.py`, their keys and hosts, `coaches samples deepgram`): Cartesia's cloning needs a subscription, and Deepgram has stock voices only, so neither could make an original coach without one.
- **Clip copying on the web:** Fish Audio's inline clip, the ElevenLabs clone, `services.json` and the clone-once code; and Fish Audio and ElevenLabs as designers of local coaches' clips.
- **`tools/migrate-assets/`** (the clips sweatcast 0.8 shipped; the migration reads them from the `v0.8.1` tag) and **`tools/msgpack_min.py`**.

## [0.9.3] - 2026-10-24

ElevenLabs and Cartesia tried live, and setup says plainly that both need a monthly subscription.

### Changed
- **ElevenLabs and Cartesia are tried live** (`knowledge/services.toml`): a smoke test and a 10-minute workout on each, from a Mac, both within 1% of plan. Only Deepgram is still "not yet tried live".
- **Subscriptions:** copying the coach's voice from a clip (cloning) isn't on either service's free or pay-as-you-go plan: ElevenLabs needs Starter (about $6 a month) and Cartesia Pro (about $5 a month). The setup skill says so before the listener picks one, and the README and `knowledge/voices.md` show it. Fish Audio needs no subscription for this.
- An ElevenLabs key needs two permissions when it's made, Text to Speech and Voices: write; the setup skill and README say so.

## [0.9.2] - 2026-10-24

The README now starts where a new listener starts: "Can you use https://github.com/RNCDev/sweatcast and set me up?"

### Changed
- **README:** a Start here section (asking Claude with the link, what you need, what to say after setup, doing it yourself), a "Where it runs" table that says Claude Code on the web needs a GitHub account, and a "For Claude" section: how a Claude session outside a copy of the repo downloads it to `~/sweatcast` (git or the ZIP, no GitHub account needed) and hands over to a session opened in that folder, where the project's instructions and safety settings load.
- No GitHub account is fine: the README and the setup skill say `me/` then stays on the computer, and how to keep a copy.
- CLAUDE.md points to the README's "For Claude" section.

## [0.9.1] - 2026-10-24

A stranger's first workout in minutes, Claude Code on the web, and a folder per workout. Setup's quick start asks four questions and starts the listener with Coach Demo, a stand-in coach that ships measured, so the first ten-minute workout needs no voice design and no smoke test. Claude Code on the web runs sweatcast with a cloud voice, and the workout arrives as a page with a player. Each workout's files now live together in their own folder.

### For forks
This release moves files in `me/workouts/` (schema 4 to 5). It changes the `me/` layout, which the project's rules call a major release; it's released as a minor one at the maintainer's call, since `./sweatcast migrate` does everything. After pulling it:
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it; `--dry-run` lists the moves first). Each draft in `workouts/drafts/` moves with its brief and menu to `workouts/<stem>/`, and each build's script and record moves beside the draft its record names (or the one draft from the same date). Smoke tests, and anything that can't be placed for sure, go to `workouts/checks/`; each day's research sheet and feeds go to `workouts/research/daily/`. Nothing is overwritten (a clash gets " (2)"). The context files change only their schema number; `me/.gitignore` gains `!*.web-*.mp3`.
- **Coach Demo** comes only with a new `me/`. To have it in yours, copy `me.example/personas/coach-demo/` into `me/personas/`.
- A customized workout skill needs its paths updated: the draft is `me/workouts/<stem>/<stem>.draft.txt`, and the feeds sheet `me/workouts/research/daily/<date>-feeds.md`. `SWEATCAST_ALLOW_CLOUD_SESSION` is gone.

### Added
- **Coach Demo** in `me.example/personas/coach-demo/`: sweatcast 0.8's public Chatterbox Coach clip with its measured pace on Chatterbox Turbo (MLX and PyTorch) and Fish Audio. It's marked `placeholder = true`: `./sweatcast check` notes it, `./sweatcast coaches` marks it a stand-in, and a build with no coach named picks any other coach before it.
- **A quick start** in the setup skill: one round of four questions (name, experience, kit, injuries), the audio route only when local voices don't run here, Coach Demo, and a ten-minute workout. "Finish setting me up" runs the rest. The profile's new `setup = "quick"` makes `./sweatcast check` report what's left as notes, not issues.
- **A quick coach** in the coach skill: three named sketches or their own, one take, keep it.
- **Claude Code on the web, with cloud voices only.** The readiness check turns local voices off there and says what to set: the key as an environment variable in the cloud environment's settings (`./sweatcast keys init` prints the line), the service's host for the network allowlist (and the feeds' hosts, optional), and whether the context folder is kept. The context folder is found beside the engine when the listener attaches their private `sweatcast-me` repo (or named by `SWEATCAST_HOME`); without one, setup explains it's a one-time session. `coaches download` and `setup --local` refuse there.
- **A web copy** (`tools/webcopy.py`, `build --web`, on by default on the web): the MP3 mono at 48 kbps in parts of at most 14 MB (about 38 minutes each) and a player page that plays them in order, which the workout skill publishes as a private artifact; `./sweatcast backup` commits the parts to the private repo.
- **A folder per workout** (`tools/workouts.py`): the build writes into the draft's own folder, or `checks/` for the smoke test and drafts outside one.
- The build record says where the MP3 went (`delivered_to`, `kept_local`, `reason`).
- `routes.hosts()` and `routes.feed_hosts()`: the hosts each route and the feeds reach.

### Changed
- `./sweatcast` no longer declines a Claude Code cloud session.
- `./sweatcast backup`'s check for a public remote works without `gh`, through GitHub's API.
- The README says where sweatcast runs: Claude Code on your own computer (terminal, IDE or the desktop app's Code tab) and Claude Code on the web, not the plain Claude chat.

## [0.9.0] - 2026-10-24

A standalone sweatcast: any reasonable computer, any voice engine, and coaches of the listener's own. Local audio now runs on Linux too, and on the processor where there's no NVIDIA card (experimental); a cloud voice with the listener's own key works on any computer, an Intel Mac included. Voices become coaches: a person's name, how they talk and a clip every engine copies, kept in `me/personas/`, so the same coach sounds the same locally or in the cloud.

### For forks
This release changes the `me/` layout (schema 3 to 4), the commands and the environment. After pulling it:
- **Run `./sweatcast setup`.** It migrates `me/` (backing up the changed files to `me/.backup-<time>/` first, never `.env`), installs the local engine as an extra where this computer runs one, and suggests moving models you already have.
- **Voices become coaches.** Each voice in the profile's `[[voices]]` becomes a folder in `me/personas/`, with its clip, words and measured pace: Chatterbox Coach becomes Coach Julius and Qwen3 Coach becomes Coach Solo, keeping their old names as aliases, so old log lines and `--voice "Chatterbox Coach"` still find them. The profile's `## Narrator` lines become how each coach talks (`## How this coach talks` in `persona.md`). Cached clips stay valid. A private voice named for a model needs a person's name: `./sweatcast migrate --name "<old>=Coach <Name>"`. `me/voices/` and `workouts/.audio-cache/voice-pace.json` move into the backup.
- **The profile** loses `[[voices]]` and gains `render = ["local"]`, the audio routes in order of preference; add a cloud service there (`["local", "fish"]`) to use one where local doesn't work. `cloud_max_chars` (default 30,000) caps what one build sends.
- **Commands:** `--voice` is now `--coach` on build, render, lint, brief and log-session (the old name still works); `./sweatcast voices` is now `./sweatcast coaches`; `./sweatcast get default-voice` is `get coach`. New: `doctor`, `keys`, `models`, `coaches`, `get route`, `build --engine`. The smoke test moved to `knowledge/smoke-test.draft.txt`. `voices/` is gone; the clips sweatcast 0.8 shipped wait in `tools/migrate-assets/v8-voices/` for the migration, until 0.10.0.
- **Models** download into `models/` at the repo root (git-ignored; a symlink or `SWEATCAST_MODELS` points it elsewhere) instead of `~/.cache/huggingface/hub`: `./sweatcast models adopt` moves the ones you have.
- **The environment:** the local engines are optional extras (`mlx`, `cuda`, `cpu`); `./sweatcast setup` picks one and remembers it in `.venv/.sweatcast-extra`. Run `uv sync` yourself only with `--extra <it>`, or it uninstalls the engine.
- **Keys** for cloud voices go in `me/.env` (`./sweatcast keys init <service>`), which `me/.gitignore` and `./sweatcast backup` keep out of the private repo. A customized setup or workout skill needs merging: setup gains the audio route and the coach step; the workout skill passes `--coach`, renders ahead only on a local route, and handles exit 4.

### Added
- **Cloud voices with the listener's own key** (`tools/cloud.py`, `tools/services/`): Fish Audio (the clip goes with every request; tried live), ElevenLabs (a clone made once, with each paragraph's neighbors for smoother joins), Cartesia (a clone made once) and Deepgram Aura-2 (stock voices only). ElevenLabs, Cartesia and Deepgram are built against local fakes of their documented APIs and labeled "not yet tried live". Before sending, a build prints the characters and approximate cost (rates in `knowledge/services.toml`, dated) and stops above `cloud_max_chars`; only the final build sends, a few requests at a time, retrying rate limits; a refused key, payment or quota exits 4; rendered clips stay cached, so a rerun sends only the rest. The build record logs the characters sent. Keys are never printed, logged, recorded or part of a cache key.
- **Coaches** (`tools/personas.py`, `./sweatcast coaches`, the `coach` skill): design takes from a description (Qwen3 VoiceDesign on an Apple Silicon Mac, or Fish Audio or ElevenLabs design), keep one, or bring a clip with its words; several coaches, the one used last by default; `set` for a coach's settings; Deepgram stock-voice samples.
- **Routes** (`tools/routes.py`): each build takes the first route in the profile's `render` list that works on the computer it runs on; `./sweatcast get route` and the readiness check say which.
- **`./sweatcast keys`** (`tools/keys.py`): which services have a key set, never the key; `init` makes the line for the listener to paste into. `.claude/settings.json` denies Claude reading or writing `me/.env`.
- **`./sweatcast models`** (`tools/models.py`): the models in `models/`, and `adopt`, which moves sweatcast's models out of Hugging Face's cache, shared blobs and all.
- **Local audio on more computers:** Linux with an NVIDIA card (not yet tried), and Windows or Linux on the processor (experimental, speed unknown until this computer's smoke test measures it; the readiness check then quotes a 30-minute workout's render time). Each render records the computer's render speed beside the pace.
- The readiness check reports the audio routes, the models folder, models waiting to be adopted, and a repo inside a synced folder.

### Changed
- The brief quotes the chosen coach's `persona.md` (who's coaching and how they talk) where it quoted the profile's Narrator, and its words-a-minute line uses that coach's pace on the route a build would take.
- `./sweatcast check` reports a missing coach, a coach without a clip or still showing a hint, and a route the profile names that isn't one.
- `log-session --coach` (with `--voice` kept); the workout skill's check-in says who's coaching and asks only when the request suggests a change.

### Not added
- A local voice designer on Windows or Linux: Qwen's PyTorch package (`qwen-tts`) pins transformers 4.57.3 against Chatterbox's 5.2.0, so they can't share an environment. Those computers design with Fish Audio or ElevenLabs, or bring a clip.

## [0.8.2] - 2026-10-24

Setup that a stranger can't trip over. Someone who clones sweatcast and says "set up sweatcast" in Claude Code is told up front what their computer can do, and setup no longer stops halfway for a missing prerequisite.

### For forks
Nothing to migrate: `me/` keeps schema 3. A customized setup skill gains a Step 0 (`./sweatcast doctor`, the cloud-session stop and the uv offer); merge it if you changed that skill.

### Added
- `./sweatcast doctor` (`tools/doctor.sh`, then `tools/doctor.py`): the readiness check. The system, chip, graphics, memory and free disk; uv, git, ffmpeg and the Python environment; whether local voices work on this computer and, when not, why; the voice models on disk; `me/` and its schema; each delivery folder, there or not on this computer; and whether ffmpeg can encode MP3 and normalize loudness. It runs before setup has made anything, and setup prints its first half as step 0. The memory and disk floors (8 GB, 6 GB free) are cautious guesses, said as such.
- Claude Code cloud sessions are declined: with `CLAUDE_CODE_REMOTE=true`, every command but `help`, `test` and `doctor` stops with the reasons (no graphics card, the model download blocked, nothing kept after the session) and suggests the listener's own computer. `SWEATCAST_ALLOW_CLOUD_SESSION=1` lets a developer through.
- `./sweatcast setup --install-uv` installs uv with Astral's official installer (no admin rights); the setup skill asks before running it.
- ffmpeg comes with the Python environment (`imageio-ffmpeg` 0.6.0, whose ffmpeg 7.1 has libmp3lame and loudnorm) when it isn't installed (`tools/ffmpeg.py`).
- `tools/player.py`: takes play with the system's own player (afplay on a Mac, xdg-open on Linux, the default player on Windows).

### Changed
- Setup no longer stops for a missing ffmpeg, and outside a git checkout (a zip download) it skips the privacy hook, says why, and carries on to the voice models. It always runs `uv sync`, which rebuilds a `.venv` copied from another computer.
- The setup skill answers "set up sweatcast", "setup sweatcast", "install sweatcast" and "get started", starts with the readiness check, and names the right installer for each system; the skills send samples with SendUserFile or the system's player, never `afplay` alone.
- The README starts from "open it in Claude Code and say set up sweatcast".

## [0.8.1] - 2026-10-23

### Fixed
- On Windows, `./sweatcast` prints in UTF-8, so a video title or headline with an emoji no longer crashes `./sweatcast youtube pick` (the console's default code page couldn't encode it).
- The pantry research template said "he" for the listener in one place; it says "they" like the rest.

## [0.8.0] - 2026-10-23

The filler between exercises gets a plan, a memory and a pantry. Each session's rests carry a planned mix (quick items from today, current science, a deep dive, a quiz, something to enjoy and something to learn), each slot rotating through the listener's interests, the one told longest ago first. A record of every item told keeps a story from being told twice. Evergreen pieces are researched ahead of time into a pantry, so session-day research covers only the news. The feeds reach further: Wikipedia's day, and whatever the listener's taste calls for.

### For forks
The research step changed, so a customized workout skill needs merging:
- The research templates moved out of the workout skill into `.claude/skills/workout/research.md`, rewritten around `./sweatcast content plan`: today's research (every session), a pantry agent (when the plan says to restock) and the video agent (when the plan's deep dive is video). The deep dive's video or news alternation now comes from the plan, not the log's topics.
- After each build, the skill records every filler item told: `./sweatcast content log --date <date> --item "<slot> | <category> | <title> [| <source> [| <pantry slug>]]"`. Sessions from before this release aren't in the record; add them the same way if you want them counted.
- `me/` keeps schema 3; nothing to migrate. Optional additions to `me/profile.md`: `[[interests]]` rows in the settings (name, slot, detail; without any, `knowledge/content.toml`'s defaults apply), a `## Taste` section of favorites with ratings, and `[[feeds]]` of the new `wikipedia` kind (`value = "featured"`). The setup skill now asks for interests and taste.

### Added
- `./sweatcast content` (`tools/content.py`): `plan --minutes N` prints what a session's rests carry, by slot and category, with the listener's detail for each, the last thirty days of items told, the pantry's unused pieces and what to restock; `log` records a session's items; `pantry` lists the unused pieces.
- `knowledge/content.toml`: the slots, how many of each a session carries by length (fifteen, thirty and longer), each evergreen slot's pantry target, and default categories.
- The record of what's been told, `me/workouts/research/told.jsonl`, and the pantry, `me/workouts/research/pantry/<slug>.md` (a piece is used once the record names its slug).
- Profile `[[interests]]` (checked by `./sweatcast check`: each needs a name and a known slot) and a `## Taste` section; the script guide says to recommend in their spirit, open each item with a hook tied to the listener, and never recommend something they rated three or less.
- A `wikipedia` feed kind: the day's featured article, the most-read pages, in the news, and did you know.

### Changed
- `knowledge/script.md`'s filler section follows the plan, and a slot with nothing verified gives its time to coaching.
- `./sweatcast youtube puzzles` also skips puzzle videos already in the pantry or the record.
- The workout skill reads the plan before the check-in, and again for the chosen length after it.

## [0.7.2] - 2026-10-23

Faster from check-in to MP3, with the same audio, and a smaller engine. The coaching is written while research runs, and the voice renders each paragraph as it lands in the draft, so the render mostly overlaps the writing instead of following it. The old session composer is retired: about 900 fewer lines of tools and 600 fewer of tests.

### For forks
- `./sweatcast session` is gone. The workout skill hasn't used it since 0.7.0 (`./sweatcast brief` plans); `docs/eval/skeletons.sh` runs it from the v0.7.1 tag as the eval's baseline. Code that imported `tools/session.py` for the safety screen imports `tools/screen.py` (`screen`, `Screen`, `Unfit`, and the helpers under public names: `ids`, `clamp`, `healthy_side`, `would_open`, `cue_lines`, `loads_line`, `parse_limit`, `words`).
- `./sweatcast build` is Python now (`tools/build.py`); `tools/build.sh` is gone. Its options and exit codes are unchanged.
- Nothing to migrate in `me/`. Cached clips are still used.

### Added
- `./sweatcast build <draft> <name> --follow` (`render.py --follow`): renders ahead while the draft is written. It keeps the voice loaded, rereads the draft between clips, renders each new or edited paragraph, and steps aside after its current clip when the full build starts (which renders only what's left), or after `--idle` seconds (fifteen minutes by default) with nothing new.
- The brief's Writing it section gives the voice's words a minute on this computer ("Talk to time"), from its measured pace, so segments come out the right length the first time; `--voice` picks a voice other than the profile's default.

### Changed
- The workout skill writes in this order: start `--follow`, write all the coaching from the brief without waiting for research, add the stories once research reports, then lint. `--clips-only` stays for a one-off render of what a draft holds.
- The voice engines no longer write a progress bar per clip or their dependency warnings into the render log (a 25-minute render's log was about 150 KB of bars; it's now only what matters).

### Removed
- `tools/session.py` (the composer) and its tests; the screen's tests moved to `tests/test_screen.py` and the session methods' to `tests/test_sessions.py`.
- `tools/build.sh`.

### Fixed
- `docs/eval/briefs.sh` and `skeletons.sh` run on Windows (the venv's Python path, and no `\r` on the case lines).

## [0.7.1] - 2026-10-23

The check-in comes first, and the session adjusts to the listener: before it starts, from how they're coming in today, and during it, from a self-check after each main movement's first set.

### For forks
Nothing to migrate. If you customized the workout skill, its first two steps changed: step 1 reads only the profile, health and log (plus `./sweatcast check`), and the headlines agent now runs `./sweatcast feeds` itself.

### Added
- A Readiness question in the check-in ("How are you coming in today?": normal, low, fresh after an easy session, or last one too hard), taking the place of the Last session question. The Limits question also offers "Sore somewhere else".
- `knowledge/programming.md`, Readiness and adjusting on the day: low readiness keeps the length but drops about a third of the hard sets, holds the loads, stops further from failure and skips all-out work; muscle soreness keeps that group light, and joint pain is a delicate limit for today. The brief prints the rule with the others.
- `knowledge/script.md`, Adjusting as you go: a target on every main set (reps and reps left), and after each main movement's first set a self-check by feel with one harder and one easier option for the sets after it, from the movement's notes and the progression order, within the set's time, never adding load to a limited area, and easier-only on a low day.

### Changed
- The workout skill asks the check-in straight after reading the profile, health and log; the feeds, the knowledge files and the brief wait until it's answered, so the listener can answer within seconds and step away.
- Past four open questions, the check-in drops Voice, then Length.

## [0.7.0] - 2026-10-23

Ingredients, not skeletons. The harness supplies what a session is built from, and the writer designs it: `./sweatcast brief` gathers the listener, the week, today's limits and the safe menu of movements with their coaching notes, the programming guide and the kit's notes, and the workout skill chooses the format, the movements, their order, doses and timing, then writes the script. The hard checks stay only where something must never go wrong: every movement from today's safe menu, text a voice reads cleanly, paragraphs short enough for one clip, and the total within three percent.

Judged on eleven cases against the previous run (`docs/eval/results-2026-10-23.md`): warmth 2.45 to 4.45, efficacy 3.64 to 4.09, adherence 3.82 to 4.18; safety 4.91 to 4.73, from three gaps the brief left the writer to fill (a clinician's rule softened later in a script, a carry heavier than a delicate neck allows, a walk to the rack under "nothing standing"), each fixed in this release.

### For forks
Nothing to migrate in `me/`; the context files stay schema 3 and the catalog format 3. What changes is the workflow and the draft:
- Plan with `./sweatcast brief --goal <goal> --minutes <N> (--kit | --preset | --equipment) [--limit ...] --save <draft path>` in place of `./sweatcast session`, which stays as an optional example shape. `--save` writes `<stem>.brief.md` and `<stem>.menu.json` beside the draft.
- A draft starts with a `movements:` line naming every movement it uses (by its menu name), then its segments, which add up to exactly the request. `./sweatcast build` won't build a draft without its menu, or with a movement the menu doesn't hold; only the voice smoke test builds without one. A draft you're halfway through from an older release needs a `brief --save` for its path and a `movements:` line.
- `./sweatcast log-session --draft <path>` logs the declared movements.
- The lint no longer warns on structure (locators, countdowns, praise, the name, openings, newsreader handoffs); that is guidance in `knowledge/tts-rules.md`. A segment far off its slot shows in the table without blocking (`--strict` makes it count).
- If you customized the workout skill, its script rules moved to `knowledge/script.md`.

### Added
- `./sweatcast brief` (`tools/brief.py`): today's ingredients in Markdown. The listener (name, level, likes and dislikes, the profile's Narrator and Default session lines); how today fits the week from the log; today's limits with what each means, the clinician's rules, the limit cues with the side filled in, the playbook's paragraph per area and the red flags; the safe menu, every movement the kit, level, limits, Avoid lines and dislikes allow, by primary pattern, each with its facts, its load on today's limited areas and its full coaching notes, healthy-side-only ones marked; the weights on hand; the programming guide (the level's doses, the sprint rest rule, the time shares, the formats that fit, every rule in `programming.md`); and the kit's notes from `kits.md`. It plans nothing.
- The menu check (`tools/menu.py`), run by the lint and required by the build: a declared movement off the menu, a catalog movement the text names that's off the menu, nothing declared, or segments that don't add up to the request stop the build, whatever `--force` says. Plain one-word names ("squat", "swing"), a shortened name of a declared movement ("the bench press") and "no neck rolls today" don't count; a menu movement named but not declared is a warning.
- The draft's `movements:` header line (`tools/draft.py`), never spoken, and where a draft's brief and menu sit beside it.
- `knowledge/script.md`: what goes in a script, from the welcome to the sign-off, moved out of the workout skill and added to (a clinician's rule beats the general stop rule; a limit cue beats a movement's own setup; under "nothing standing", the kit is set out within reach before the work starts).
- The lint's table shows each held segment's spare seconds, spent in silence, so a quiet strength rest is easy to spot.
- Eval: `docs/eval/briefs.sh`, `extra-cases.toml` (c41), the writer and judge briefs for the brief path, and run 5's results.

### Changed
- The workout skill is a page of procedure (from about 5,800 words to about 1,400, plus the research templates): read, check in and launch research, brief, design and post the plan, write, build, deliver, log and back up.
- `./sweatcast session` shares its safety screen with the brief (`session.screen`) and is an optional reference and the eval's baseline; it isn't extended.
- The lint keeps only what must hold: the text-to-speech line checks, the paragraph length, the total within three percent, and the menu check. Segment fill flags show without blocking.
- Catalog: carries rate a light neck load (a delicate neck allows them, marked; an off-limits neck rules them out); step jacks rate groin 2 (a side step is what loosens a groin limit); shadow boxing rates a light low-back load, so a delicate back screens it as fast work; the towel door row says the handle on your side.
- Docs harmonized around the brief: CLAUDE.md, the README, the setup skill, `kits.md`, the injury playbook, `programming.md`, `tts-rules.md`, the profile and health templates and the eval listeners (whose prose no longer names someone other than their `name`).

### Removed
- The lint's structure warnings and the workout skill's skeleton steps (`session --draft` markers, first candidates, per-slot rules).

## [0.6.2] - 2026-10-22

Scripts that sound like a coach who knows the listener, not a template read aloud: a name, a person's register around the work, continuity from the log, a session arc, and lint checks that catch the mechanical patterns. Plus the engine fixes the last eval left open.

This release was not judged on the eval grid; all forty skeletons compose and the tests pass. The next major release moves session design from the composer to the writer (a brief of safe ingredients in place of a fixed skeleton), so the composer changes below may be short-lived.

### For forks
Nothing to migrate; the context files stay schema 3. Optional: add `name = "<first name>"` to the profile's settings so the coach greets the listener by it (`./sweatcast check` notes when it's missing), and fill in the two new Narrator lines in the profile's prose.

### Added
- `name` in the profile's settings: the coach greets the listener by it in the opening line and uses it at the hardest set and the sign-off, two to four times. The setup skill asks for it.
- `knowledge/tts-rules.md`, Coaching voice, rewritten: short cues during the work, a person talking around it (contractions, "let's", one line of why per movement, the effort noticed plainly, continuity from the log), the session arc (welcome, build, peak, ease off, a specific and personal close), varied locators, and stories handed off the way a friend would.
- `./sweatcast coverage` prints the days since the last session, the sessions in the last seven days and the latest feedback, for the script's continuity lines.
- Lint warnings (not blocking): a set name that never comes up, isn't in the welcome or comes up more than five times; three or more segments in a row opening alike; newsreader handoffs ("Today's story is", "In other news"). The locator check accepts "two to go", "one more", "here we go", "back to" and "again".
- The profile template's Narrator section asks how the coach should talk to the listener and what encouragement works for them.
- Eval: the judge scores a fifth thing, warmth; the four invented listeners have first names.

- `[limit_cues]` in the catalog: one to three spoken cues for each area at each limit level (head and eye position for the neck, where the resting foot goes and how to get to and from the floor for an ankle or foot, brace and roll to the side for the low back, and so on), printed by `./sweatcast session` as a `Limit cues` block for each active limit, with its side.
- `[all_out]` in `knowledge/sessions.toml`: an all-out sprint (hard, timed, twenty seconds or less) rests at least four times its work, from `programming.md`'s sourced rule, with fewer rounds to fit; the finisher ranks sprints last.
- Two hard machine entries, `elliptical-surge` and `treadmill-hill-walk`, so a hotel gym's intervals can leave the bike.

### Changed
- The workout skill's opening greets by name and says how today fits the week; its close names what was done, gives a reason to come back and signs off by name. Under a limit, the script uses the skeleton's limit cues.
- A circuit groups its stations by place (standing, seat or bench, floor), so a round changes place as little as the movements allow (one change instead of four in the judged floor-and-bench case).
- Every set's segment holds its reps at the movement's pace (both sides of a one-sided move, plus a side change) and a few seconds to start, carried by the last set; the fitting lowers reps by about one where time is short.
- Intervals with several machines go round them: a hard movement on a machine nothing has led on yet comes before a second block on the same machine, and the steady block prefers an unused machine and is skipped when a machine change would leave it under ninety seconds.

## [0.6.1] - 2026-10-22

Better context for writing a script: the coaching a listener without a screen or a mirror needs for each movement, half of the unfinished catalog finished, sourced physiology for rest, effort, stretching, coverage and ankle rehab, and the kit's real weights.

### For forks
Nothing to migrate; the catalog stays format 3 and the context files schema 3. Optional: add `weights` (equipment id = the weights you have, lightest to heaviest) and `unit` (`"lb"` or `"kg"`) to a `[[kits]]` row, such as `weights = { dumbbells = [10, 15, 20] }`, so the session tool prints what's on hand. A private movement in `me/movements.toml` may add `rep`, `feel` and `faults`.

### Added
- Catalog coaching fields on every finished movement: `rep` (what one rep is, per side or not; for a timed entry what is held and a talk test), `feel` (where it should be felt and where not) and `faults` (one to three common mistakes, each with its fix). Spoken text, checked like `setup` and `cues`.
- `./sweatcast session` prints a Coaching section for its first picks (setup, cues, rep, feel, faults, easier and harder), a `Muscles:` line (the major groups the plan trains and the ones it leaves out) and, when the kit gives its weights, a `Loads on hand:` line. `./sweatcast movements --about <ids>` prints the coaching for any movement. The workout skill coaches from these, not from memory.
- Fifty movements finished from drafts (94 drafts down to 44), each reviewed for its joint ratings: seated conditioning (seated march, shadow boxing, arm pumps, speed bag), the eight stickhandling drills, ankle and foot rehab (band eversion, inversion, dorsiflexion and plantar flexion, towel scrunch, ankle alphabet and circles, single-leg balance, seated calf raise), seated mobility, curls, kickbacks, band external rotation, seated and band rows, band pull-apart, incline press, reverse crunch, bench dead bug, dumbbell and barbell hip thrust and bridge, clamshells, donkey kick, the hip and leg-curl machines, the lying dumbbell hamstring curl, sled push, rower intervals and ski erg.
- `[[kits]]` takes optional `weights` and `unit`; `./sweatcast check` lists a fault in them, and the setup skill asks for them.
- `knowledge/programming.md`: sourced sections on muscle coverage and recovery, exercise order, rest between intervals (an all-out effort gets at least four times its length in rest), effort by ear (the talk test and a ten-point scale) and stretching dose (about thirty seconds a hold, on as many days as the week allows), and a warm-up study that found no extra reps.
- `knowledge/injury-playbook.md`: the ankle's order of loading after a sprain, from the 2021 clinical practice guideline, and a balance-programme trial; sources for the foot, calf, hamstring and groin, which had none.
- `knowledge/kits.md`: what the session tool prints for a kit, and equipment notes for dumbbells (handling, changing weights, naming them), the single kettlebell, bike setup and pedals, resistance scales by feel, the rower's damper, the treadmill's belt-change time, and a hotel room without a mat.

### Changed
- The session tool reads the clinician's `Avoid:` lines in `me/health.md` itself, on every run; the skill no longer copies them into `--avoid` by hand, and `./sweatcast check` names any word in them that isn't a movement or flag. (Copied by hand, a ban was easy to leave off, and the plan then offered the movements it banned.)
- When straight sets would drop a movement pattern for time and paired sets drop fewer, the session runs paired sets and names what they still drop, so a short strength or general session covers more of the major groups. A targeted session keeps its own method.
- Paired-set markers count only the pairs ("Pair 1 of 2"), not a lone last slot.
- Safety: a delicate area still rules out all impact work, but fast work only when it loads that area, counting the foot, ankle and calf as one chain: fast seated punching stays in for a delicate foot, while a fast pedal stroke stays out for a delicate calf. With an off-limits ankle and a delicate foot, the finisher and intervals had no movement at all; they now get seated conditioning.
- Intervals add the strength fallback when fewer than two movements reach the level's leading effort (hard above novice), not when fewer than two are anything but easy, so one hard movement no longer leads every interval.
- Safety ratings, from a review of the new entries and a check against an off-limits ankle: push-ups, pike push-ups and the forearm plank rate ankle 1 and foot 2 (the toes bear weight), bridges and hip thrusts ankle 1 and foot 1 (the feet press the floor), so an off-limits ankle leaves the one-leg bridge on the healthy side; the world's greatest stretch rates the front ankle and foot and carries `overhead`; the half-kneeling stretch and press rate the front foot; the rower, air bike, sled push, ski erg and stick drills gain the wrist, elbow, shoulder, neck or foot loads they had left out. Curls rate wrist 1, like the rows that hold the same dumbbell. Band external rotation is done seated. The supine twist rates ankle 1, since dropping the knees rolls the foot onto its outer edge. The bike's standing climb rates ankle 2 and calf 2, like the stair climber. The treadmill run's setup says the hard pace its effort grade means.
- `programming.md` no longer points at the removed `exercise-science.md`, and a test checks it.
- Eval: `docs/eval/results-2026-10-22-run4.md`, a targeted run of the ten cases whose skeletons changed most plus an off-limits-ankle case: every case safe, and the ten cases' mean total rose from 15.2 to 16.4; the writer's brief coaches from the new notes.

### Not yet
- Interval doses don't yet follow the new rest rule: a twenty-second sprint inside a forty-five and thirty interval rests under three times its length, where `programming.md` now asks four.
- A circuit doesn't group floor stations and bench stations, so a listener who can't push through one foot makes many floor transitions.
- Coaching notes have no limit-specific lines (head position under a delicate neck, the injured foot's place), so the script adds them from the health lines.
- Forty-four drafts remain (barbell and machine extras, some mobility, the overhead seated punches); `./sweatcast movements` lists none of them.

## [0.6.0] - 2026-10-22

sweatcast renders on a Windows PC with an NVIDIA GPU as well as on an Apple Silicon Mac. Chatterbox Coach runs there from Resemble AI's own PyTorch Chatterbox Turbo on CUDA, cloned from the same reference clip.

### For forks
Breaking: the Python environment and the voice settings change shape.
1. Rerun `./sweatcast setup` after pulling. `pyproject.toml` now gives MLX to macOS and PyTorch to Windows, and `uv.lock` resolves for those two systems only, so an environment synced on any other system needs `SWEATCAST_PYTHON` (as CI does) or a fork of its own. The Mac's locked versions are unchanged.
2. A voice's `.json` may carry a `"torch"` table (`model`, `revision`, optional `generate`) for Windows; the top-level settings stay the Mac's. A private Chatterbox voice in `me/voices/` gets one from `voices keep`; add it by hand to an existing one (copy it from `voices/Chatterbox Coach.json`) to render that voice on Windows.
3. On Windows, render the smoke test once per voice: each backend's model is measured on its own.
4. Context files don't change format; there is nothing to migrate. `deliver_to` may now be a list, one folder per computer.

### Added
- A PyTorch backend in `tools/engines.py`: Chatterbox Turbo (`ResembleAI/chatterbox-turbo`, pinned) through `chatterbox-tts` 0.1.7 on CUDA 12.4 builds of PyTorch 2.6, with the reference clip encoded once per render. On an RTX 2080 Super it rendered at about 0.52 times the speech's length.
- `tools/voices.py` picks the backend from the system (`SWEATCAST_BACKEND` overrides it), takes each voice's model for it, lists it in `./sweatcast voices`, and downloads it with `voices download`.
- `tools/locks.py`: one exclusive file lock for the render lock and the pace file, flock on a Mac and msvcrt on Windows.
- `deliver_to` takes a list of folders; each build copies to the ones that exist on the computer it runs on.
- The build record names the backend and its runtime versions.

### Changed
- `./sweatcast`, `build.sh` and `setup.sh` find the Windows venv's Python (`.venv/Scripts/python.exe`); `./sweatcast build` and `setup` run through Git Bash's `sh` on Windows and keep their exit codes. Setup checks for an NVIDIA GPU on Windows and names the winget packages for ffmpeg and uv.
- A render on Windows marks the `coverage` package absent before loading the model, since `tools/coverage.py` would otherwise pass for it and break numba's import under librosa.
- The build-script tests run on Windows too (no `execv` in the stub, forward slashes in the test profile's TOML); the read-only-folder test is skipped there. The tests pin the Mac backend unless a test asks for PyTorch.
- README, CLAUDE.md, `knowledge/voices.md` and the setup skill describe both systems.

### Not yet on Windows
- Qwen3 Coach and voice design (`voices design`) stay Mac-only: a Qwen3 voice lints on Windows, and its render says to pick a Chatterbox voice.

## [0.5.4] - 2026-10-22

### For forks
Nothing to migrate. To back up your context, make `me/` its own private repo (README, "Back up `me/`"); rerunning `./sweatcast setup` adds `me/.gitignore` if it has none.

### Added
- `./sweatcast backup` (`tools/backup.py`): commits everything in `me/` and pushes it, when `me/` is its own git repo, nested in the engine's folder and ignored by the engine's git. It changes nothing when `me/` isn't its own repo, and refuses to push to a repo GitHub reports as public.
- The workout skill's last step runs it, after the build and the log, so each session lands in the listener's private repo.
- `me.example/.gitignore`: leaves the clip cache (but not the voices' measured pace), MP3s, render logs, unkept voice takes and migration backups out of that repo. Setup copies it into a new `me/` and adds it to an existing one.

## [0.5.3] - 2026-10-22

### Changed
- Safety: an off-limits ankle or foot now rules out anything done standing, which puts weight through both feet whatever the catalog rates the ankle, and the seated bikes and air bikes rate ankle 1 and foot 1, so an off-limits ankle keeps them out while a delicate one still allows them. A case `--limit` line says "and nothing done standing", and the injury playbook says both.

## [0.5.2] - 2026-10-22

### Changed
- `./sweatcast build` removes the local MP3 once every copy in the profile's `deliver_to` folder is in place and matches; `me/workouts/` keeps the script's `.txt` and `.build.json` as history. A failed copy, or no delivery folder, keeps the MP3 in `me/workouts/`.
- The setup skill's delivery step says so, and a request to change where workouts go runs that step alone; the profile template's `deliver_to` comment matches.

## [0.5.1] - 2026-10-22

Intervals that fit their movements and leave the work quiet, and a cleaner engine. Re-judged, the twelve conditioning cases rose from a mean total of 13.4 to 16.3 (efficacy 2.67 to 3.67, adherence 3.17 to 3.92, ease 2.75 to 3.67, safety 4.83 to 5.00); `docs/eval/results-2026-10-22-run3.md` has the run.

### For forks
Nothing to migrate. `knowledge/exercise-science.md` is gone and the tools no longer read `me/exercise-science.md`; `./sweatcast check` notes a leftover copy, which you can delete once anything worth keeping is copied out.

### Added
- `[hold]` in a draft: a segment with a hold keeps its full planned length, its spare time silent at its bare holds, so timed work isn't talked through; `[hold 20s]` is exactly that much silence. A held segment is never flagged short. The lint, the layout and the render share it, and `knowledge/tts-rules.md` and the workout skill say how to use it.
- An intervals block whose strength fallback is all on the floor runs as a circuit: one interval of each movement a round ("Round 2 of 4, glute bridge").

### Changed
- A timed movement shorter than the interval's work (a twenty-second sprint) works for its own seconds and rests the rest of the interval.
- Above novice, an interval block repeats the strongest hard movement before a moderate one leads it; the steady block goes on a machine, even one an interval used, before floor work.
- The workout skill and research agent no longer draw exercise-science asides; form cues stay cues.
- README and CLAUDE.md tightened: the README's layout is by folder, its voice section points at `knowledge/voices.md`, and both describe `[hold]`.
- `./sweatcast build` no longer passes the profile's `words_per_minute`, which only `./sweatcast lint` without a voice uses; the template and the check say so.

### Removed
- `knowledge/exercise-science.md`, `me.example/exercise-science.md` and the listeners' copies; the completed plans and specs in `docs/superpowers/` and the old productization notes in `docs/research/` (the session-structure research the session rules cite stays).
- Dead code: `paths.DRAFTS`, `paths.VENV_PYTHON`, `sessions.choose_method` (tests use `ranked`) and an unused branch of `voices.seed_pace`.

## [0.5.0] - 2026-10-22

The fixes from the second judged run of the grid: interval work that is hard enough, warm-ups that start easy, paired sets that can be spoken as pairs, rests that match the clock, and caps on volume. The catalog and the session rules each move up a format.

### For forks
Breaking: the catalog moves to format 3, `knowledge/sessions.toml` to format 2, and paired-sets drafts get a marker per pair set. After pulling:
1. If you keep private movements in `me/movements.toml`, they are now loaded (0.4.x ignored the file). Run `./sweatcast check`: every finished conditioning entry needs `effort = "easy"`, `"moderate"` or `"hard"`, and it lists any entry missing one or carrying another fault. Until it is fixed, a faulty entry is held back as a draft and never planned.
2. A fork that edits `knowledge/movements.toml` or `knowledge/sessions.toml`: set `format = 3` and `format = 2`, add `effort` to every finished conditioning movement, and keep the new dose keys (`bodyweight_reps` above novice, `efforts_per_session`) in every conditioning level. `./sweatcast test` names anything missing.
3. Drafts written under 0.4.x markers still render. A new paired-sets draft is written under one marker per pair set ("Pair 1 of 3, set 2 of 3: ..."), a circuit round's marker names the rest that ends it, and interval markers are numbered by block.
4. No context file changes; there is nothing to migrate.

### Added
- `effort` on every conditioning movement (easy, moderate, hard). Interval work never takes an easy movement; above novice the hard ones rank first.
- An interval fallback: when fewer than two locomotion movements are hard enough today (a thin kit, a delicate limit), timed squat, lunge, hinge and core work joins the intervals, with a warning.
- A steady block after the intervals for the time past the new `efforts_per_session` cap, and the `hard_sets_per_session` cap now holds for straight and paired sets.
- A printed finisher dose (`Finisher: 240 s, 4 rounds of 30 s on, 30 s off`), in the skeleton and its marker.
- `bodyweight_reps` above novice (10 to 15 experienced, 12 to 20 advanced), used for any movement with no load equipment.
- A case `--limit` prints what it rules out ("light loads only on the left calf, no impact or fast work").
- `me/movements.toml` is loaded, and `./sweatcast check` lists problems in it.
- Finished entries: step jacks, air bike steady and sprint, stair climber, standing climb, leg extension, arm circles, shoulder rolls, leg swings, standing calf stretch.
- `docs/eval/writer.md`, the script writers' brief, and `docs/eval/results-2026-10-22-run2.md`, the second judged run: safety 4.72, efficacy 3.05, adherence 3.45, ease 3.00 (first run 4.70, 2.33, 2.80, 3.52). Its ten lowest cases, rewritten and re-judged after these fixes, rose from a mean total of 11.7 to 14.6 (efficacy 2.3 to 3.2, adherence 2.7 to 3.6, ease 2.3 to 3.4, safety level at 4.4); two of the three safety points they still lost (low back loads on the half-kneeling press and the treadmill run) are fixed in the catalog since, and step jacks now carry a light groin rating.

### Changed
- Candidate ranking: with load on hand, strength movements that use it rank ahead of bodyweight ones at the same level (goblet squat before air squat, face pull before the towel door row); with a cardio machine on hand, conditioning on it ranks ahead of the floor.
- The warm-up list starts with easy locomotion and never offers hard, fast or impact work; the finisher list takes hard, then moderate conditioning; the cool-down leads with box breathing; none leads with a movement the work uses.
- Paired sets: one marker per pair set, a printed rest after each pair set, each station's transition every set, and pairs that cross families to the end.
- Straight sets print the rest their seconds hold; a circuit prints the rest between its rounds, now its own 45 to 90 s, and its patterns add vertical push, vertical pull and anti-rotation.
- Intervals keep one machine's blocks together, give thirty seconds to change equipment, number markers by block, repeat no movement while another remains, and raise the rest before the work. Interval rounds per movement start at three or four. A circuit takes no barbell lift.
- Targeted sessions give each target pattern two slots; a muscle target matches a movement's first two muscles. Patterns holding a liked movement come right after the targets.
- A healthy-side-only slot is timed for one side.
- Flow runs two mobility drills to each breathing one.
- Safety: a low back off limits also rules out spine flexion and twisting; the overhead presses rate neck 2, so a delicate neck rules them out; the face pull rates wrist 1; treadmill runs, jumping jacks, high knees, the standing climb and the half-kneeling press rate low back 1; step jacks rate groin 1. The playbook says the first two.
- An unreadable `me/movements.toml` is skipped with a warning instead of stopping every tool.
- The towel door row's setup names the door to use (an inside door that opens away from you, never the room's entry door); the world's greatest stretch keeps the head in line.
- The judge prompt reads the writer's notes, scores adherence on the coaching alone, and compares with an earlier run only after scoring blind. The workout skill describes the new markers and attributes clinician rules to the clinician.

## [0.4.0] - 2026-10-22

Sessions built from atomic movement data: the catalog says what each movement loads, a tool picks the method, the timing and the candidates, and a judged grid of forty cases measures how the result reads.

### For forks
Breaking: the context files move to schema 3, the catalog's tags and groups are gone, and one command flag changes. After pulling:
1. Run `./sweatcast migrate` (`./sweatcast setup` runs it too). It backs up your folder first, then adds the new fields to `profile.md` and `health.md`.
2. Run `./sweatcast check`. It lists the experience level to fill in (novice, experienced or advanced; a profile with none is planned as a novice until it is set) and each injury that needs a `[[limits]]` row in `health.md`. It exits 1 until they are written. An injury outside the thirteen areas takes no row: list it as "- Unlisted: <what>" and put any movement ids or flags to avoid on an "Avoid:" line under `## Clinician rules`.
3. `./sweatcast movements --group` is now `--pattern`, and `--avoid` takes movement ids or flags, not tags.
4. A private `me/movements.toml` entry needs `patterns`, and the other new fields, to leave draft.
5. The log's `format:` now records the method's name.

### Added
- `./sweatcast session`: given a goal, minutes and a kit (`--kit`, `--preset` or `--equipment`), it prints the health limits and warnings, the method, the timed slots with ranked candidates, the warm-up, finisher and cool-down candidates (screened against the limits), the patterns dropped for time and the equipment that would open up more movements. `--draft` prints only the `@@ <seconds> | <title>` markers. Options: `--method`, `--level`, `--target`, `--limit area=level[:side]` and `--avoid`.
- `knowledge/sessions.toml` and `tools/sessions.py`: the session methods (straight-sets, paired-sets, circuit, intervals, tabata, bike-intervals, flow, skill) and the dose rules per intensity and level, every number marked as sourced or a house default.
- `[[limits]]` rows in `health.md`: an area, side, level (off-limits or delicate), optional `flags` and `rehab` (both validated), and a note. Both-side limits also check the load on the resting side.
- The profile's `[[kits]]`, `experience`, `likes` and `dislikes`, and `./sweatcast get experience`.
- An optional `rpe:` on log lines, reserved for later progress tracking.
- The judged eval grid in `docs/eval/`: forty cases over four invented listeners, a judge prompt, and `results-2026-10-22.md`. Means over the forty cases: safety 4.70, efficacy 2.33, adherence 2.80, ease 3.53. No case scored safety 1.
- `knowledge/programming.md`: the programming reference behind the dose rules.

### Changed
- Catalog format 2: each movement carries its patterns, muscles, how much it loads each joint area (with `support` for the resting side), flags, intensity, level and timing; unfinished entries are drafts.
- `./sweatcast movements` filters by pattern, with `--level`, `--pattern` and `--avoid` (ids or flags). `./sweatcast coverage` reports by pattern.
- The injury playbook is organized by area and tolerance: what off-limits and delicate mean, the signs that let a limit loosen, and the red flags that stop a session.
- The workout skill plans from `./sweatcast session`; the setup skill collects experience, kits and limits. One check-in rule, and the check runs first.
- `./sweatcast check` lists a missing experience level, malformed limit rows, and prose injuries without a limit (an issue).

### Removed
- `knowledge/injury-rules.toml` and the phase model, the catalog's tags and groups, and `./sweatcast movements --group`.

## [0.3.2] - 2026-10-21

### Added
- The movement catalog, `knowledge/movements.toml`: every movement a session can use, with its equipment, muscle groups, spoken setup and cues, and tags for what it loads, plus kit presets. `tools/catalog.py` reads and checks it.
- `./sweatcast movements`: lists the movements a kit allows (`--preset` or `--equipment`), minus any `--avoid` tags, by group.
- Weekly counts in `./sweatcast coverage`: a group the last seven days neglected comes first, even when the last session touched it.
- Plural-tolerant name matching: a logged "goblet squats" or "right glute bridge" resolves to the catalog movement.

### Changed
- The equipment library is now `knowledge/kits.md`: what each kit usually holds and how to script around it. Its movement lists moved to the catalog.
- The workout skill picks movements from the filter's output, avoiding the injury playbook's new "Tags to avoid early" for each injury in an early phase, then applies the health file and the playbook on top.

## [0.3.1] - 2026-10-21

### Fixed
- Inconsistent injury tags in `knowledge/equipment-library.md`: a movement now carries the same tags everywhere it appears (the strictest set), and movements that load a joint but had no tags now have them.
- Removed listener-specific names: a named gym and a bike brand left two headings, which now read "Full gym" and "Stationary bike".

## [0.3.0] - 2026-10-21

Simpler to set up and to run: one `./sweatcast` command, the profile's settings in one block at the top, a check that says what's still to fill in, and a voice designer for a coach that sounds the way you want.

### For forks
Breaking: commands, the profile's format and the Python they run on all change. After pulling:
1. Run `./sweatcast setup`. It migrates `me/` (backing it up to `me/.backup-<date and time>/` first). In `profile.md`, the Voices list, "Copy finished MP3s to:", "Measured words per minute", the YouTube favorites and Puzzles handles, and the Feeds section move into a TOML block between `+++` lines at the top. Their lines leave the prose, and one sentence says where they went. The other context files only change their front matter. `./sweatcast migrate --dry-run` shows what would change. A 0.1.x folder migrates in the same run.
2. Run `./sweatcast check`. It lists anything the tools can't read and any line still showing the template's `[hint]`.
3. Call tools as `./sweatcast <command>`: `python3 tools/feeds.py` is `./sweatcast feeds`, `tools/build.sh` is `./sweatcast build`, `LINT_ONLY=1 tools/build.sh` is `./sweatcast build ... --lint-only`, `ALLOW_ESTIMATED=1` is `--allow-estimated`, `python3 tools/context.py log-session` is `./sweatcast log-session`, and `voices.py --measured` and `--download` are `voices measured` and `voices download`. `./sweatcast help` lists everything. The project permissions now allow `./sweatcast` instead of each tool.
4. The tools need Python 3.11 (the project's `.venv`); the Mac's own `python3` no longer runs them. Tests run with `./sweatcast test`.

### Added
- **`./sweatcast`**, one command for everything, run in the project's environment: `setup`, `build`, `lint`, `render`, `voices`, `feeds`, `coverage`, `youtube`, `check`, `get`, `deliver`, `log-session`, `migrate`, `cache`, `test`. `./sweatcast setup` needs no Python first. One permission rule covers every command the skills run.
- **Voice design:** `./sweatcast voices design "<name>" "<description>"` renders takes of a coaching line in a voice made from a written description (Qwen3-TTS VoiceDesign, pinned; about 4.5 GB the first time). `./sweatcast voices keep <take> --engine chatterbox --default` makes the chosen take a private voice in `me/voices/` and adds it to the profile. The setup skill offers it during the interview, for a woman's voice, say, or another accent; `knowledge/voices.md` has a "Design a voice" section.
- `./sweatcast check` flags every profile line still showing the template's `[hint]`, any feed not filled in, and a missing voice. It also notes, without failing, a missing delivery folder or no feeds.
- Schema 2 and its migration step, chained after 0.2.0's, with tests that migrate 0.1.x and 0.2.x folders.
- Tests for the wrapper, voice design and keeping, adding a voice without losing the settings' comments, and the new check: 102 in all.

### Changed
- The profile's settings live in TOML front matter (`+++`), read with Python's own `tomllib`: `voices` (`[[voices]]` name and description; the first is the default), `deliver_to`, `words_per_minute`, `youtube_favorites`, `puzzles` and `[[feeds]]` (label, kind, value). The tools no longer depend on how a line in the prose is worded.
- `./sweatcast feeds` skips feeds that aren't filled in yet, rather than listing them as failures.
- `tools/youtube.py` no longer restarts itself under `.venv`; `./sweatcast` runs everything there.
- The README's getting started is three steps: install ffmpeg and uv, clone, say "set me up". There's also a commands table.
- The setup skill writes the settings block, offers a designed voice, and runs `./sweatcast check` until it passes. The workout skill uses `./sweatcast` throughout.

### Removed
- Running the tools with the system `python3`, the `LINT_ONLY` and `ALLOW_ESTIMATED` environment switches, and `voices.py --measured` and `--download`.

## [0.2.0] - 2026-10-21

The engine's audit, fixed: one owner for the listener's files with a versioned format and a migration, safer state on disk, a privacy guard that checks every commit, consistent exit codes, and a record of how each MP3 was made.

### For forks
Breaking: the context files now carry a format version, and tools refuse an older folder until it's migrated. After pulling:
1. Run `tools/setup.sh` (or `python3 tools/migrate.py`). It backs up `profile.md`, `health.md`, `log.md` and `exercise-science.md` to `me/.backup-<date and time>/`, then adds a three-line front matter (`---`, `schema: 1`, `---`) to the top of each. Nothing else in them changes. `--dry-run` shows what it would do.
2. Run `python3 tools/context.py check`. It lists any line the tools can't read, such as a log line with a field missing, with its line number.
3. Clips cached before 0.2.0 render once more, since the cache key now includes the mlx-audio version. Right after upgrading, `python3 tools/cache.py prune --days 0` frees the old ones (it removes every cached clip, so run it before your next build, not after).
4. If you call the tools from your own scripts: a mistyped command now exits 64, not 2. The lint's word-count option is `--word-tolerance` (it was `--tolerance`). `tools/feeds.py` prints only the weather unless you pass `--print`. The draft functions (`parse`, `plan`, `spans`, `layout` and the timing constants) moved from `tts_build.py` to `tools/draft.py`, and the engine code from `render.py` to `tools/engines.py`.

### Added
- `tools/context.py`, the one reader and writer of the context files: the schema check, `get default-voice | wpm | voices`, `deliver` (the delivery folders that exist), `log-session` (adds a checked session line to `me/log.md`) and `check`. `build.sh`, `setup.sh`, `coverage.py`, `feeds.py` and `youtube.py` read the profile and log through it instead of six separate parsers. The workout skill logs sessions with `log-session` instead of editing the log by hand.
- `tools/migrate.py`, with a backup and `--dry-run`. `tools/setup.sh` runs it when a context folder already exists.
- A record of each build: `<name>.build.json` beside the MP3 and a line in `me/workouts/.logs/builds.jsonl`, with the draft's hash, voice, model and revision, mlx-audio and ffmpeg versions, seed, clip counts, timing and drift. Each build's render log is `me/workouts/.logs/<name>.log` instead of one shared temporary file.
- `tools/cache.py`: the clip cache's size, and `prune [--days 45]` for clips no build has read in that long. Renders mark each clip they read.
- `tools/cli.py`: the exit codes in one place (0 done, 1 issues, 2 drift, 3 unmeasured voice, 64 command mistake) and an argument parser that exits 64.
- `tools/draft.py` (the draft model and timing layout) and `tools/engines.py` (everything tied to mlx-audio and huggingface_hub internals, with a warning when the installed mlx-audio isn't the tested one).
- `tts_build.lint()` returns a `Report` (rows, issues, drift, warnings), so the lint's findings can be checked without reading its printout. The printed output is unchanged.
- Tests for all of the above, `build.sh`'s exit codes (through a stand-in Python), the pace file, the privacy hook on temporary repositories, the render lock, migration, and the feed limits: 94 in all, passing on Python 3.9 to 3.14.

### Changed
- Only one render runs at a time: a second one, such as a full build started while the prerender is still going, waits for the first and then reuses its clips.
- `tools/feeds.py` prints only the weather and any failed sources. Headlines and captions are outside text, so they stay in the sheet for the research agent, and the main session no longer reads them. The workout skill takes the weather from that printout. `--print` prints the whole sheet.
- Editing `me/health.md` asks for permission (an `ask` rule in `.claude/settings.json`). The workout skill only edits it at the check-in, while the listener is there, so the unattended part of a session still runs without prompts.
- The render releases the voice model's memory before assembling and encoding the MP3.
- `--tolerance` passed to `tools/build.sh` now sets the allowance for the lint as well as the render.

### Fixed
- One damaged write to `voice-pace.json` could erase every voice's measured pace: an unreadable file was treated as empty, then overwritten. The pace file is now written under a lock, to a temporary file that's renamed into place. A damaged one is moved aside as `voice-pace.json.corrupt-<time>` instead of overwritten, and the render checks it before loading a model rather than after rendering.
- The pre-push hook checked only the last commit of a push, so a personal file committed and then removed in a later commit still went out. It now checks every pushed commit, and so does CI. The three copies of the private-path list (hook, CI, test) are now one file, `tools/hooks/private-paths`. CI and the test had been missing the old-layout `knowledge/health.md`. A commit that only deletes such a file is allowed, so a leak can be cleaned up.
- A mistyped render option exited 2, which `build.sh` and the skill read as "the workout ran long". It now exits 64 and shows the error. An unknown voice exits 64 with the list of voices, instead of reporting that the voice "hasn't been measured".
- The lint re-read the pace file twice for every clip. It now reads it once per lint, so a render finishing mid-lint can't change the prediction partway through.
- `tools/feeds.py` fetches only http and https addresses, reads at most 5 MB of each, and builds its TLS settings on first use rather than on import.
- `tools/youtube.py` refuses a video id with path characters, finds `@handles` under Content first, and writes transcripts as UTF-8.
- The render finds ffmpeg's loudness figures by their keys and explains a failure, rather than taking the last `{` in its output.

## [0.1.1] - 2026-10-21

The voices are named for the models that speak them, the model downloads are explained, and Chatterbox's speech tokenizer is held to its pinned version at render time too.

### For forks
Nothing has to change: the old names still work. To use the new ones, rename the voices under Voices in `me/profile.md` (keep the `  - <name>: ...` format). Measured pace and cached clips carry over, since they're keyed by the voice's clip, not its name.

### Changed
- Coach E is now **Chatterbox Coach** and Coach G is **Qwen3 Coach** (`voices/`, the docs, the skills and `me.example/`). A voice is a reference clip spoken by an unmodified model, so the name says which model and what role. The old names are kept as aliases in each voice's `.json`.
- The `setup` skill runs `tools/setup.sh --no-models` first and downloads only the voice the user picks, after saying how big it is, instead of fetching the default voice's model before the interview.
- `tools/voices.py --download` prints each download's size; `tools/setup.sh` explains that no Hugging Face account is needed.

### Added
- A "Voice models" section in the README and "Downloading the models" in `knowledge/voices.md`: what each voice downloads and how big it is (about 3.3 GB for Chatterbox Coach, 4.2 GB for Qwen3 Coach), when downloads happen, that no account is needed, offline use, freeing space, and licenses.
- `tools/setup.sh --no-models`.
- An `"aliases"` setting for voices: older names that still find the voice.
- Tests for aliases and the tokenizer pin: 60 in all.

### Fixed
- Chatterbox Turbo's speech tokenizer is loaded at the revision `tools/voices.py` pins. mlx-audio asked for its latest version at every render, so the pin only applied to setup's download, and a failed load was only a warning that could leave the voice quietly wrong. A render now fetches the pinned version first and stops with a clear message if it can't.

## [0.1.0] - 2026-10-21

sweatcast becomes a forkable product: three layers (engine, voices, your context), its own Python environment instead of VoiceStudio's, and an onboarding skill.

### For forks
Breaking: the listener's files moved into `me/`, and VoiceStudio is no longer used. After pulling:
1. Move your files first: `mkdir me`, then `knowledge/profile.md` to `me/profile.md`, its "Active injuries and limitations" section into `me/health.md` (see `me.example/health.md`), `log.md` to `me/log.md`, `workouts/` to `me/workouts/` (including `.audio-cache/`, which holds your voices' measured pace), and `me.example/exercise-science.md` to `me/`. Then `git rm -r --cached knowledge/profile.md log.md workouts` so git stops tracking them.
2. `brew install uv` (and `ffmpeg`, if it's missing), then run `tools/setup.sh`. It builds `.venv` from `uv.lock`, leaves your existing `me/` alone, and installs the pre-push hook. Your downloaded models are reused.
3. In `me/profile.md`, replace the "Google Drive folder (My Drive) for finished MP3s: <folder>." line with `- Copy finished MP3s to: ~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>` (any synced folder works now).
4. A voice whose `.json` named no model now names one explicitly; its measured pace is filed under the model's name, so render the smoke test with it once (`tools/build.sh voices/smoke-test.draft.txt "smoke-test" --voice "<name>"`). Voices saved in the VoiceStudio app (OmniVoice) no longer work; recreate one as a reference clip in `me/voices/` (see `knowledge/voices.md`).
5. The VoiceStudio app can be uninstalled.

### Added
- **Your context in `me/`** (git-ignored; `SWEATCAST_HOME` moves it): `profile.md`, `health.md` (injuries, split out of the profile), `log.md`, `exercise-science.md` (facts verified in your sessions), `workouts/` and private `voices/`. `me.example/` is the template.
- `tools/paths.py`: one place for every path, so no tool hard-codes a personal file.
- **Own runtime:** `pyproject.toml`, `uv.lock` and `.python-version` pin Python 3.11, mlx-audio 0.5.0, mlx 0.32.1, numpy 2.2.6 and yt-dlp; `tools/setup.sh` builds `.venv`, copies `me.example/`, installs the privacy hook and downloads the default voice's model (`--all` for every voice).
- **Pinned models:** each voice's `.json` names its model and Hugging Face revision, and Chatterbox Turbo's speech tokenizer is pinned in `tools/voices.py`, so every copy renders with the same weights. `tools/voices.py --download` fetches them.
- **Delivery to any folder:** the profile's `- Copy finished MP3s to: <path>` line (iCloud Drive, Google Drive, Dropbox or any folder; `~` and `*` allowed) replaces the Google Drive-only copy.
- **`setup` skill:** "set me up" interviews a new listener (basics, kits, health with a not-medical-advice note, interests and feeds, voice, delivery), writes `me/`, checks the feeds, and renders the smoke test.
- **Privacy guard:** `tools/hooks/pre-push` refuses to push `me/` or an old-layout profile, log or workouts folder; CI checks the same.
- **CI:** a GitHub Actions workflow runs the tests on every push and pull request.
- Tests for voice lookup (private voices first, pinned revisions on shipped voices), a fresh copy running on `me.example/`, a missing context folder, and nothing personal being tracked. Test drafts are synthetic fixtures in `tests/fixtures/`: 55 tests in all.

### Changed
- `tools/build.sh`, `tools/render.py` and `tools/youtube.py` run on the project's `.venv` (or `SWEATCAST_PYTHON`) instead of VoiceStudio's bundled Python. Renders are unchanged: Coach E still renders at about 0.68 times real time.
- The workout skill reads `me/` and the shared knowledge, takes kit options and injury phase criteria from your own files instead of the author's, and writes only inside `me/`. `.claude/settings.json` allows edits to `me/**` only.
- `CLAUDE.md` and the README describe the product and the three layers rather than one listener; the author's first-person framing moved to their own profile.
- The smoke test moved to `voices/smoke-test.draft.txt` and no longer mentions any one person's injuries.
- The clip cache key includes the model revision, so clips rendered before 0.1.0 render once more.

### Removed
- OmniVoice and every VoiceStudio dependency: the VoiceStudio voice database, OmniVoice's text helpers, the OmniVoice render options (`--steps`, `--guidance`, the temperatures, `--speed`) and the re-launch under VoiceStudio's Python.
- The author's profile, log, drafts, scripts and research from the public repo's current tree. They remain in the git history of earlier versions.

## [0.0.6] - 2026-10-21

New content sources, a weekly feed kind for them, and an open-source license.

### Added
- A `weekly` feed kind in `tools/feeds.py`: the newest two items from the last eight days, for weekly podcasts and puzzles that the 72-hour news window would miss.
- New feeds in `knowledge/profile.md`: The Fiddler and NPR's Sunday Puzzle (puzzles), BBC's More or Less (numbers in the news) and No Such Thing As A Fish (fun facts).
- New YouTube favorites for deep dives: Freakonomics Radio and Marginal Revolution University.
- The quiz can now use a puzzle from The Fiddler or the Sunday Puzzle as well as MindYourDecisions. Since their answers come out a week later, research takes the earlier puzzle that the newest post solves, and credits the source.
- `LICENSE` (MIT), and a License section in the README.
- A test for the weekly feed kind: 50 tests in all.

### Changed
- Video transcripts (`workouts/research/videos/*.txt`) are kept out of git, since they're the channels' own text. The deep-dive summary sheets are still committed.

## [0.0.5] - 2026-10-21

Timing that holds the whole workout to plan instead of every segment, and brain teasers for the quiz.

### Added
- `tools/youtube.py puzzles`: lists recent videos from a new Puzzles line in `knowledge/profile.md` (Presh Talwalkar's MindYourDecisions) that haven't been used as a quiz yet. The headlines agent picks one that works by ear, saves its transcript and writes `workouts/research/puzzles/<id>.md` (the puzzle as said aloud, the answer and the reason); a puzzle with a sheet isn't offered again. The session's quiz beat uses it when there is one, and falls back to the session's own material.
- `tts_build.layout`, one timing layout shared by the lint's prediction and the render, so they agree.
- Tests for the new timing and the puzzle list: 49 in all.

### Changed
- A segment with time to spare widens its paragraph breaks (up to about two seconds each), keeps a short tail and ends early instead of padding with silence. A segment that runs long is still paid back from the next ones' spare time.
- Only the whole workout is held to plan, within three percent either way. The lint prints the predicted length and blocks only when the total is off by more than that, or when a segment is far off its slot (under 80 or over 110 percent of it, down from 90 to 100). The render exits 2 only when the finished workout is more than three percent over or under plan; `--tolerance` now sets that total allowance.
- The workout skill, `CLAUDE.md`, `README.md`, `knowledge/tts-rules.md` and `knowledge/voices.md` describe the new timing and the puzzle quiz.

## [0.0.4] - 2026-10-21

Feeds before research, faster renders, a voice that's measured before it's trusted, and more variety: bells inside intervals, session types, video series and load tracking.

### Added
- `tools/feeds.py`: fetches the feeds listed in a new Feeds section of `knowledge/profile.md` (team results and next games from ESPN's schedules, weather from Open-Meteo, local, science and tech headlines from RSS, and Wikipedia's on-this-day events) into `workouts/research/<date>-feeds.md` in about a second. The workout skill runs it first, and the headlines agent reads it before searching, on a smaller search budget (eight searches, down from twelve).
- A `[chime]` marker that rings the segment bell inside a segment, for the changes in an interval. The lint counts its time.
- A three-note rising tone at the end of every MP3, so the end of the workout can't be mistaken for a dropped earbud. `--no-chime` leaves it out with the segment bells.
- `--clips-only` for `tools/build.sh` and `tools/render.py`: render and cache a draft's clips with no lint or MP3. The skill starts it on the first half of a draft while it writes the second.
- Structure warnings in the lint: a segment that opens without a locator, more than one countdown in a segment, more than two exclamation points, or a short praise line used three or more times. They don't block a build; `--strict` makes them count.
- `format:` and `loads:` fields in each `log.md` session line. `tools/coverage.py` prints the last format, so the next one differs, and each movement's last load, so the plan progresses from it. The two logged sessions are backfilled.
- Video series: a long video's sheet can be split into parts (`- Parts: 3`), `tools/youtube.py pick` lists a series in progress first, and `tools/youtube.py done <id>` marks a part told.
- Workout skill: session types (strength, mobility and breathing, stickhandling skills, seated bike intervals, a ten-minute snack); a "how did last session feel" check-in question when there's room; a quiz beat each session; the books pillar in rotation; a morning weather preview, plus the shape of the day from the calendar when a calendar connector is available.
- `tools/voices.py --measured <voice>`, which exits 0 once a voice's speaking rate has been measured.
- Tests for all of the above: 46 in all, still with no models or network.

### Changed
- Chatterbox Turbo encodes the voice's reference clip once per render instead of once per clip. The clips are byte-identical, and a render takes about 6 percent less time.
- An unmeasured voice's speaking rate now starts at the median of the measured voices instead of its reference clip's own rate, which was about 30 percent slow. Coach G was predicted at 9.8 characters a second that way; it measures 14.8.
- `tools/build.sh` refuses a session render with a voice whose rate hasn't been measured (exit code 3) and prints the smoke-test command that measures it. The smoke test itself always renders, skips the Drive copy, and its lint never blocks it. `ALLOW_ESTIMATED=1` overrides the refusal.
- The lint's character weights are vendored from OmniVoice into `tools/char_weight.py` (Apache 2.0, header kept), so the lint runs on any Python 3 for Chatterbox and Qwen3 voices. A test checks the copy still matches OmniVoice's whenever VoiceStudio is installed.
- `tools/youtube.py` loads yt-dlp only for the commands that need it, so it can be imported and tested anywhere.
- Coach G's model is downloaded and its rate measured with the smoke test. Its render speed is about 1.45 times the speech's length, not 1.3.
- The smoke test's close opens with "That was the whole test", so it passes the new locator check.

## [0.0.3] - 2026-10-21

A chime that marks each segment, coach-style cues, a coverage check from the log, and tests.

### Added
- A soft two-note chime at the start of every segment after the first, so you can keep time by ear even when a cue comes out garbled. The lint counts its time. `--no-chime` leaves it out.
- `tools/coverage.py`: reads `log.md`, maps each logged movement to the whole-body checklist, and lists the groups the last session left out and the movements to avoid. The workout skill runs it before planning.
- `tests/`: fast checks for parsing, pauses, the lint, segment timing, the chime and coverage, with no models (`python3 -m unittest discover tests`).
- A `"generate"` field in `voices/<name>.json` for per-voice engine settings.
- Coaching voice guidance in `knowledge/tts-rules.md` and the skill: short cue sentences, mid-set check-ins, long sentences only for stories.

### Changed
- The workout opening uses a one-line version of the safety rules when nothing has changed since the last session. The full version is still used for the first session, any change at check-in, or a gap of more than fourteen days. Both versions name every rule.
- Engine settings and clip trimming are now part of each clip's cache key, so changing them re-renders instead of reusing old clips. Existing cached clips re-render once.
- `tools/build.sh` stops with a clear message when it can't find the default voice in the profile, and says why when it skips the Google Drive copy, instead of quietly falling back.
- `tools/render.py`: segment layout moved into its own function, `assemble`, so it can be tested.

### Fixed
- Coach E's expressiveness settings (`exaggeration`, `cfg_weight`) were hard-coded for Chatterbox, but Turbo ignores them, so they never had any effect. They're gone from Coach E, and `knowledge/voices.md` explains how to use them with the full-size model.

## [0.0.2] - 2026-10-20

A natural coach's voice, cleaner timing, and better content, after the first full listen.

### Added
- Chatterbox Turbo and Qwen3-TTS engines in `tools/render.py`, through `mlx-audio` in VoiceStudio's bundled Python. Chatterbox Turbo renders at about 0.75 times the length of the speech on an M3.
- Voices kept in the repo (`voices/<name>.wav`, `.txt`, `.json`), with the engine and model per voice. Two coach voices: Coach E (Chatterbox Turbo, the default) and Coach G (Qwen3-TTS).
- Measured speaking rate per voice and model, recorded by each render and used by the lint to predict length.
- Lint check for paragraphs over twenty-two seconds, where engines drift and glitch.
- `--model`, `--guidance`, `--class-temperature` and `--position-temperature` render options.
- Workout skill: a whole-body coverage check (push, pull, hinge, hamstrings, quads, hip abductors and adductors, anti-extension and lateral core, arms) and a both-sides-by-default rule with injury-safe alternatives.
- Workout skill: two current science and technology breakthroughs in each session's research; exercise science becomes a one-line aside.
- `VERSION`, `CHANGELOG.md` and a release process in `CLAUDE.md`.

### Changed
- A segment's spare seconds are spread over its paragraph breaks instead of sitting at the end, and a segment that runs slightly long borrows from the next one's padding.
- Engine silence is trimmed from each clip's ends.
- Render timing excludes the model load.
- Docs rewritten for the new voices and engines: `README.md`, `CLAUDE.md`, `knowledge/voices.md`, `knowledge/tts-rules.md`, the workout skill.

### Removed
- The VoiceStudio Gallery voices from the profile; they sounded mechanical on OmniVoice. OmniVoice still renders voices saved in the app.

## [0.0.1] - 2026-10-19

First working version.

### Added
- The `workout` skill: check-in, plan, background research, script, build and log.
- `tools/build.sh`: lint, `.txt` export, OmniVoice render with per-segment padding and loudness normalization, and a copy to Google Drive.
- Spoken-length prediction per VoiceStudio voice.
- `tools/youtube.py` for video deep dives from favorite channels.
- Profile, injury playbook, equipment library, exercise science and text-to-speech rules.
