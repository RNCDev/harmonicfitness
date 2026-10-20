---
name: workout
description: Build a narrated workout script and MP3. Use whenever the user asks for a workout, session, or audio training in any words ("I'd like a workout", "build me a 25 minute workout", "hotel workout, just go").
---

# Workout: request to MP3

Goal: get from request to finished MP3 with the fewest round-trips. Ask only for what the request didn't say, do research while the user answers, and render in the background.

## Step 0: kick off everything that doesn't need answers (one message, in parallel)

In a single message, send all of these tool calls together:
- `date "+%Y-%m-%d %A %H:%M"`, so you know today's date and whether it's morning (preview the day) or evening (recap it).
- Read `knowledge/profile.md`, `knowledge/tts-rules.md`, `log.md`, `knowledge/injury-playbook.md`, `knowledge/equipment-library.md`.

Then, in the next message, send these two together:
1. **Research agent** (Agent tool, `general-purpose`, `run_in_background: true`), using the prompt template at the bottom of this file. Research doesn't depend on the check-in answers, so it runs while the user is answering.
2. **Check-in** (AskUserQuestion), covered next.

## Step 1: check-in (ask only what's missing, in one AskUserQuestion call)

Pull the following out of the request. Ask only about the ones it doesn't settle, all as questions in a single AskUserQuestion call, up to four:

| Slot | Settled by | If missing, ask with options |
|---|---|---|
| Length | "25 minute", "half hour", "quick" (15) | 25 min (Recommended, profile default), 15 min, 30 min, 45 min |
| Kit | "home", "hotel", "gym", "Fitler" | Home (Recommended), Hotel room, Hotel gym, Fitler Club |
| Each active injury in profile.md | "ankle feels better", "shoulder's fine" | Same as last time (Recommended), Better, Worse, New problem |
| Voice | "in the British voice", a voice's name | Ask only if fewer than four other questions are needed: the default (Recommended) and three others from profile.md; the rest are reachable through Other |

- Voice otherwise defaults to the first one under Voices in profile.md.
- "Just go" (or similar) means don't ask anything. Use profile defaults, assume injuries are unchanged, and state the assumptions in one line.
- Worse, or new: go gentler and say so. Better: still don't advance a phase unless the profile's criteria are met (from the profile). If unsure, ask one follow-up.
- Any red flag from the playbook (can't bear weight, rapidly increasing swelling, numbness, giving way, getting worse after a week or two): say so in chat and suggest a clinician before building.
- If the user reports lasting changes (a new phase, clinician rules, new equipment), update `knowledge/profile.md`.

## Step 2: plan (show it, don't wait for approval)

Rules:
- Split: warm-up about 15 percent (at least three minutes), two main blocks about 30 percent each, finisher about 15 percent, cool-down with box breathing about 10 percent. Merge the main blocks under 15 minutes; add a block over 45.
- Rotate formats: rolling 60-second minutes, 45 work and 15 transition, long steady segments, circuits. Check `log.md` and use a different format than last time.
- Apply the injury playbook first, then pick only from what remains in today's kit. Where profile, playbook and library disagree, the strictest wins. Anything the profile bans is out.
- No repeated exercises within a session. Avoid the main movements from the last session in `log.md`.

Post the plan as a short table (block, minutes, format, movements) plus the equipment list, then go straight to scripting. The user can interrupt if they want changes.

## Step 3: script

Wait for the research agent's notification if it hasn't arrived yet. Then write the draft to `workouts/drafts/<YYYY-MM-DD>-<slug>.draft.txt`:
- An `@@ <seconds> | <label>` line before every segment. Use one segment per spoken block (per minute for rolling minutes; work and transition can share a segment).
- Draft to about measured wpm × seconds ÷ 60 words per segment. That's only a guide: the lint predicts each segment's spoken seconds for the chosen voice, wants 90 to 100 percent of the slot, and its guide column gives each segment's word count at the rate that voice actually speaks the draft. Size fixes to the guide; voices differ by ten percent or more. Each 60-second segment splits roughly 20 / 60 / 20: locator ("Minute nine of twenty-five"), movement, equipment and setup; then narrative; then form cue, injury cue if relevant, one countdown, and what to grab next. Scale longer segments.
- Opening: the plan in a sentence or two, the injury rule, the stop rule (pain stays around two or three out of ten, sharp pain or new swelling means stop that movement), and setup time.
- Close: box breathing with a short cue and a `[pause]` for each four-second phase (see tts-rules), a one-line recap, a sign-off.
- Filler comes only from the research sheet. Never invent scores, prices, quotes or events. Use a few quick headlines plus one deep-dive thread told across several segments, and tie science to the movement happening that minute. Tone per profile: calm and focused, light humor, no hype.
- Follow `knowledge/tts-rules.md` exactly: no digits at all (spell years as spoken: "seventeen eighty-one"), no symbols or brackets except `[pause 3s]` markers, no abbreviations, paragraph breaks between cue, narrative and handoff. Safety and form cues get their own short sentences; they're what must survive the voice.

## Step 4: build (one command, in the background)

```
tools/build.sh "workouts/drafts/<file>.draft.txt" "Workout <YYYY-MM-DD> <Focus> <N> min" --voice "<voice>"
```
- Run it from the repo root exactly as written, with no leading `cd` and no absolute path, so the project's permission rule matches and there's no prompt. Leave out `--voice` for the default voice.
- Don't open the VoiceStudio app during a render. On 16 GB of memory, two copies of the model won't fit comfortably.
- The lint runs first and stops the script if anything is flagged. "Overruns by" means cut words from that segment; "dead air" means add a little. Check quickly with `LINT_ONLY=1 tools/build.sh ...` before committing to a render.
- Once the lint is clean, run it with `run_in_background: true`. Rendering takes about 0.7 times the length of the speech (a 25-minute workout takes about 17 minutes) and needs no server. Clips are cached, so reruns only render edits.
- If it exits with code 2 (a segment overran its slot), trim that segment's words and rerun; it finishes in seconds. With the lint's prediction this should be rare; it can happen the first time a voice is used, before its exact pace is recorded.
- Options: `--voice <name or id>`, `--speed 1.05` (also slows or speeds the lint's prediction), `--steps 16` (the default 12 transcribed as clean as 16 or 32 in testing; 8 garbled cue words; time grows in proportion to steps).

While it renders, post the log line and anything else useful. Don't wait idle.

## Step 5: deliver and log

- Chat: plan table, equipment, voice, estimated runtime, and paths to `workouts/<name>.txt` and `workouts/<name>.mp3`. If SendUserFile is available, send the MP3 so it lands on the user's phone.
- Append to `log.md` under Sessions: `- <date> | <N> min | <kit> | <voice> | <main movements> | <topics>`. No injury details.
- Feedback about a session (too long, too easy, a topic they loved) goes under Feedback in `log.md`, and applies from then on.

## Research agent prompt template

Fill in the bracketed parts. Neighborhood, pillars and the never-bring-up list come from profile.md (Basics and Content), so the template never drifts from the profile:

> Research filler for a narrated workout on [weekday, date], [morning: preview today / evening: recap today]. The listener lives in [neighborhood]. Content pillars, rotated across sessions (recently used, so favor the others: [topics from the last two log entries]): [each Content pillar from profile.md, with its detail]; on this day in history ([month day]); fun facts. Never include: [the never-bring-up list, if any]. Also: one exercise-science fact for each of these movements: [movements, if known; otherwise skip].
>
> Search the web. Return a plain fact sheet: for each item, two to four sentences of verified facts with exact scores, numbers, names and dates, plus the source URL. Pick four or five pillars, about three quick headlines and one deep-dive story with enough material to tell across five or more minutes. Only include what you verified today. Never guess scores, prices or quotes; if a result isn't confirmed, leave it out. Write the sheet to workouts/research/[date].md and return it.
