---
name: workout
description: Build a narrated workout script and MP3. Use whenever the user asks for a workout, session, or audio training in any words ("I'd like a workout", "build me a 25 minute workout", "hotel workout, just go").
---

# Workout: request to MP3

Goal: the check-in is the only time the user is needed. They answer it in the first minute and step away; research, script, render and the copy to Google Drive all run unattended, and the finished MP3 reaches their phone.

## Step 0: read (one message, in parallel; takes seconds)

In a single message, send all of these tool calls together:
- `date "+%Y-%m-%d %A %H:%M"`, so you know today's date and whether it's morning (preview the day) or evening (recap it).
- Read `knowledge/profile.md`, `knowledge/tts-rules.md`, `log.md`, `knowledge/injury-playbook.md`, `knowledge/equipment-library.md`, `knowledge/exercise-science.md`.

## Step 1: check-in first, with research launched alongside (one message)

In the next message, send these together, the Agent calls first (they return at once, so the question appears right away):
1. **Research**, in the background. It doesn't depend on the answers, so it runs while the user answers:
   - The deep dive alternates by session. If the last session in `log.md` had `deep dive: news` (or there's no session yet), this one's is a video, and the other way around.
   - **Headlines agent** (Agent tool, `general-purpose`, `model: "sonnet"`, `run_in_background: true`), using the headlines template at the bottom of this file. On a news session it also researches the deep dive.
   - **Video agent**, on a video session only (same settings), using the video template at the bottom of this file. It picks a video from the profile's YouTube favorites, saves the transcript and writes the deep-dive sheet.
2. **Check-in** (AskUserQuestion): everything the session needs from the user, in one call, so there's nothing to come back for.

Pull the following out of the request. Ask only about the ones it doesn't settle, as up to four questions:

| Slot | Settled by | If missing, ask with options |
|---|---|---|
| Length | "25 minute", "half hour", "quick" (15) | 25 min (Recommended, profile default), 15 min, 30 min, 45 min |
| Kit | "home", "hotel", "gym", "Fitler" | Home (Recommended), Hotel room, Hotel gym, Fitler Club |
| Each active injury in profile.md | "ankle feels better", "shoulder's fine" | Same as last time (Recommended); Better, and [the profile's criteria for the next phase]; Better, but not there yet; Worse. A new problem goes under Other. |
| Voice | "in the British voice", a voice's name | Ask only if fewer than four other questions are needed: the default (Recommended) and three others from profile.md; the rest are reachable through Other |

- Voice otherwise defaults to the first one under Voices in profile.md.
- "Just go" (or similar) means don't ask anything. Use profile defaults, assume injuries are unchanged, and state the assumptions in one line.
- Better, with the criteria met: move to the next phase. Better but not there yet: same phase. Worse, or a new problem: go gentler and say so.
- Any red flag from the playbook (can't bear weight, rapidly increasing swelling, numbness, giving way, getting worse after a week or two): say so in chat and suggest a clinician before building. This is the one case that stops the run.
- If the user reports lasting changes (a new phase, clinician rules, new equipment), update `knowledge/profile.md`.

## Unattended from here to the MP3

Once the check-in is answered, don't ask the user anything else or wait on them:
- Every choice from here has a default in this skill or the profile. Take it, and mention it in the final summary if it matters.
- Every command and file write this skill uses is allow-listed in `.claude/settings.json`, so nothing prompts for permission. Run commands exactly as written (no leading `cd`, no absolute paths), use Read rather than shell commands to look at files, and keep writes to `workouts/`, `log.md`, `knowledge/exercise-science.md` and `knowledge/profile.md`.
- Problems get fixed, not escalated: lint flags mean edit and rerun, and a render that exits 2 means trim and rerun.
- Time box research: once the plan is posted, if an agent still hasn't reported, SendMessage it to stop searching and return what it has verified. Script around any gaps with form cues; never fill them by guessing.

## Step 2: plan (show it, don't wait for approval)

Rules:
- Split: warm-up about 15 percent (at least three minutes), two main blocks about 30 percent each, finisher about 15 percent, cool-down with box breathing about 10 percent. Merge the main blocks under 15 minutes; add a block over 45.
- Rotate formats: rolling 60-second minutes, 45 work and 15 transition, long steady segments, circuits. Check `log.md` and use a different format than last time.
- Apply the injury playbook first, then pick only from what remains in today's kit. Where profile, playbook and library disagree, the strictest wins. Anything the profile bans is out.
- No repeated exercises within a session. Avoid the main movements from the last session in `log.md`.
- Cover the whole body. Check the plan against: horizontal push, horizontal pull, hip hinge or glutes, hamstrings, quads, hip abductors and adductors, anti-extension core (dead bug, plank), lateral or anti-rotation core, arms. A short session can pair two in one movement (a bridge with an adductor squeeze), and anything left out comes first next session. Post the coverage as one line under the plan.
- Bilateral by default: both sides, both limbs, same work. When an injury rules out one side's version, look first for a bilateral version that respects the rules (lying straight-leg raises on each side, a pillow squeeze between the knees, hip extension lying face down on the bench), then for the injured side's unloaded version (side-lying work lying on the healthy side works the injured-side hip), and only then train the healthy side alone. Say in the audio why a side is skipped. Training one side still carries some strength over to the other.

Post the plan as a short table (block, minutes, format, movements) plus the equipment list, then go straight to scripting. Don't wait for approval; the user may already have stepped away.

## Step 3: script

Wait for the research agents' notifications if they haven't arrived yet (see the time box in Step 0). Then write the draft to `workouts/drafts/<YYYY-MM-DD>-<slug>.draft.txt`:
- An `@@ <seconds> | <label>` line before every segment. Use one segment per spoken block (per minute for rolling minutes; work and transition can share a segment).
- Draft to about measured wpm × seconds ÷ 60 words per segment. That's only a guide: the lint predicts each segment's spoken seconds for the chosen voice, wants 90 to 100 percent of the slot, and its guide column gives each segment's word count at the rate that voice actually speaks the draft. Size fixes to the guide; voices differ by ten percent or more. Each 60-second segment splits roughly 20 / 60 / 20: locator ("Minute nine of twenty-five"), movement, equipment and setup; then narrative; then form cue, injury cue if relevant, one countdown, and what to grab next. Scale longer segments.
- Opening: the plan in a sentence or two, the injury rule, the stop rule (pain stays around two or three out of ten, sharp pain or new swelling means stop that movement), and setup time.
- Close: box breathing with a short cue and a `[pause]` for each four-second phase (see tts-rules), a one-line recap, a sign-off.
- Filler comes only from the research sheet, the video sheet and `knowledge/exercise-science.md`. Never invent scores, prices, quotes or events. Use a few quick headlines, two current science and technology breakthroughs from the research sheet, and one deep-dive thread told across several segments. "Science" in a session means those breakthroughs, not exercise science: a fact from `knowledge/exercise-science.md` is at most a one-sentence aside that explains a form cue, once or twice a session.
- Keep every paragraph under about twenty seconds spoken, about fifty words. Tell a deep-dive beat as two or three short paragraphs. Long clips drift and glitch; the lint flags any paragraph over twenty-two seconds. Use `[pause]` for getting into position or breathing, at most three or four seconds; a segment's spare time is spread over its paragraph breaks automatically. Credit a video deep dive to its channel when it starts ("This one comes from Asianometry's latest video"), and paraphrase it rather than quoting. Tone per profile: calm and focused, light humor, no hype.
- Follow `knowledge/tts-rules.md` exactly: no digits at all (spell years as spoken: "seventeen eighty-one"), no symbols or brackets except `[pause 3s]` markers, no abbreviations, paragraph breaks between cue, narrative and handoff. Safety and form cues get their own short sentences; they're what must survive the voice.

## Step 4: build (one command, in the background)

```
tools/build.sh "workouts/drafts/<file>.draft.txt" "Workout <YYYY-MM-DD> <Focus> <N> min" --voice "<voice>"
```
- Run it from the repo root exactly as written, with no leading `cd` and no absolute path, so the project's permission rule matches and there's no prompt. Leave out `--voice` for the default voice.
- Don't run the VoiceStudio app during a render; on 16 GB of memory, two voice models at once won't fit comfortably.
- The lint runs first and stops the script if anything is flagged. "Overruns by" means cut words from that segment; "dead air" means add a little. Check quickly with `LINT_ONLY=1 tools/build.sh ...` before committing to a render.
- Once the lint is clean, run it with `run_in_background: true`. Rendering takes about 0.75 times the length of the speech with Coach E (Chatterbox Turbo) and 1.3 with Coach G (Qwen3), so a 30-minute workout takes about 20 minutes with the default voice, and needs no server. Clips are cached, so reruns only render edits.
- If it exits with code 2 (a segment ran more than five percent over its slot), trim that segment's words and rerun; only the changed clips render again. Smaller overruns are absorbed by the next segment's padding.
- After a successful render it copies the MP3 to the profile's Google Drive folder (My Drive/Workouts), which syncs to the user's phone, and prints where it went.
- Options: `--voice <name>` (from Voices in profile.md), `--model <repo>` to try another build of the voice's engine, `--seed <n>` for a different take of every line.

While it renders, post the log line and anything else useful. Don't wait idle.

## Step 5: deliver and log

- Chat: plan table, equipment, voice, estimated runtime, paths to `workouts/<name>.txt` and `workouts/<name>.mp3`, and whether the build copied it to Google Drive (My Drive/Workouts). If SendUserFile is available, send the MP3 with `status: "proactive"` so it reaches the user's phone while they're away.
- Append to `log.md` under Sessions: `- <date> | <N> min | <kit> | <voice> | <main movements> | <topics>`. Topics start with the deep dive, as `deep dive: video, <channel>, <title>` or `deep dive: news, <story>`, so the next session knows which kind comes next and which channel to skip. No injury details.
- Feedback about a session (too long, too easy, a topic they loved) goes under Feedback in `log.md`, and applies from then on.

## Research prompt templates

Fill in the bracketed parts. Neighborhood, pillars and the never-bring-up list come from profile.md (Basics and Content), so the templates never drift from the profile. Keep the scope and the budget as written: a wide scope with no budget took ten minutes and seventy tool calls.

**Headlines agent.** Choose the three pillars yourself: Content pillars (not counting YouTube favorites) that don't appear in the last two log entries' topics, favoring sports in season. Include the bracketed news-session parts only on a news session.

> Research quick headlines for a narrated workout on [weekday, date], [morning: preview today / evening: recap today]. The listener lives in [neighborhood]. Cover exactly these pillars, one headline each: [three pillars, each with its detail from profile.md]; plus two science and technology breakthroughs announced in the last few weeks (chips, AI, computing, physics, biology, medicine, space or energy; at least one in deep tech), each with what was done, by whom, the key number, and why it matters, from the paper, the lab or company's own release, or a science news outlet; plus one on-this-day item for [month day]. [News session: Also one deep-dive story from [a fourth pillar], with enough verified material to tell across five or more minutes: how it started, the key turns, the numbers, what's next.] Never include: [the never-bring-up list, or "nothing, the list is empty"]. [If the kit is already known: Also one exercise-science fact each for at most two of these movements, which aren't in knowledge/exercise-science.md: [movements]. Append the confirmed ones to that file in its format.]
>
> Budget: at most twelve web searches and five page fetches in all [news session: eighteen and seven]. Stop as soon as you have what's listed. One authoritative source per item is enough: the team or league site, AP, ESPN, a company's own release, a city or transit agency page. For each item, give two to four sentences of facts with exact scores, numbers, names and dates, plus the source URL and its date. Never guess scores, prices or quotes; leave out anything you can't confirm within the budget. Write the sheet to workouts/research/[date].md and return it.

**Video agent** (video sessions only):

> Prepare the deep dive for a narrated workout from the listener's favorite YouTube channels. Run `python3 tools/youtube.py pick` to list recent unused videos. Choose one that works by ear alone (a story, a history, how something works; skip anything that depends on watching an equation or diagram), from a channel other than [the channel of the last video deep dive in log.md, or "any"], and preferably under an hour. Run `python3 tools/youtube.py transcript <id>` and read the saved transcript in full.
>
> Write workouts/research/videos/<id>.md: the title, channel, upload date and URL; then six to eight story beats in the video's order, each two to four sentences, using only facts, names, numbers and dates the video states; then two or three plain-language explanations of its key technical ideas, each short enough to say in thirty seconds. Paraphrase rather than quote. If the captions are automatic, flag any name or number that looks misheard instead of guessing. Return the sheet.
