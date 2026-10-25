---
name: workout
description: Build a narrated workout script and MP3. Use whenever the user asks for a workout, session, or audio training in any words ("I'd like a workout", "build me a 25 minute workout", "hotel workout, just go").
---

# Workout: request to MP3

The check-in is the only time the user is needed: they answer it in the first minute and step away, and research, design, script, render and the copy to their delivery folder all run unattended. `./sweatcast brief` supplies the ingredients (the listener, today's limits, the safe menu with its coaching notes, the programming guide, the equipment notes); you design the session and write it.

Rules that always hold:
- Every movement in the script, warm-up and cool-down included, comes from the brief's safe menu; nothing from memory. The build checks the draft's `movements:` line and its text against the menu and stops on anything else.
- A red flag from `knowledge/injury-playbook.md` (can't bear weight, rapidly increasing swelling, numbness, giving way, getting worse after a week or two) stops the session: say so in chat and suggest a clinician.
- `me/health.md` is edited only at the check-in, which asks the user's permission.
- After the check-in, don't ask anything (except step 2's coach question when the coach can't speak here, and step 3's one equipment question) or wait on the user. Take the defaults, run commands exactly as written (no leading `cd`, no absolute paths; they're allow-listed), and write only inside `me/`.

## 1. Read just enough to ask (one message, in parallel)

The check-in comes first, so the listener can answer and step away; this step reads only what its questions need.
- `date "+%Y-%m-%d %A %H:%M"`: morning previews the day, evening recaps it.
- `./sweatcast check`: a `me/health.md` issue (a malformed `[[limits]]` row applies no limit; a prose injury with no row gets no rule) is fixed at the check-in, then checked again. Notes are fine; with no experience level the default is novice until set, so offer to set it.
- `./sweatcast content plan`: the filler plan at the default length (whether the deep dive is a video or news, and whether the reserve needs restocking).
- `./sweatcast get coach`: who's coaching (the coach used last, their own over a stand-in, else a stand-in that works here); the check-in says so in a line and asks only if the request suggests another. Exit 1 (the coach used last is archived): ask the Coach question with `./sweatcast coaches`' list. No coach yet: run the `coach` skill.
- Read `me/profile.md`, `me/training.md`, `me/health.md` and `me/log.md` (not `me/content.md`: research reads that). No `me/profile.md` means this copy isn't set up: run the `setup` skill. On Claude Code on the web (`./sweatcast doctor` says so), only web coaches speak and the MP3 arrives as a web copy (step 7). A tool that says the context folder is in an older format: run `./sweatcast migrate`, then rerun.

Nothing else before the check-in: the feeds, the knowledge files and the brief come after it.

## 2. Check-in, with research launched first (one message)

1. **Research**, in the background, from the templates in `research.md` beside this file: today's research always (it runs the feeds and the plan itself); the video agent when the plan's deep dive is video; the reserve agent when the plan has a Restock section.
2. **Check-in** (AskUserQuestion): up to four questions, only about what the request doesn't settle, in this order (past four, drop Coach, then Length):

| Slot | Settled by | Options when asked |
|---|---|---|
| Limits | "ankle feels better", "my legs are sore" | "Anything sore or off today?", one multi-select: an option per health.md limit worded "<area>: same / better / worse", "Sore somewhere else (say where)" when there's room, and "Nothing new" (Recommended). Without limits, just the last two. |
| Readiness | "slept badly", "feeling strong", "last one was too easy" | "How are you coming in today?": Normal, last one about right (Recommended); Low (tired, short on sleep or stressed); Fresh, and last one felt easy; Last one was too hard. Too long, or anything else, through Other. |
| Goal | "strength", "bike intervals", "mobility" | Strength (Recommended), General fitness, Conditioning, Mobility and breathing; targeted work and skill through Other |
| Length | "25 minute", "quick" (15) | 25 min (Recommended, training.md's default), 15, 30, 45 |
| Kit | "hotel", a kit's name | training.md's `[[kits]]`, the first Recommended; a preset (bodyweight, hotel-room, hotel-gym, full-gym) through Other |
| Coach | a coach's name, "another coach", "a new coach" | Asked only when the request suggests a change: the coach used last (`./sweatcast get coach`, Recommended) and the others `./sweatcast coaches` lists (all of them when `get coach` stopped on an archived coach). Name each as the listener does, never by service; "a new coach" runs the `coach` skill first, then the workout continues with them |

- "Just go" means ask nothing: profile defaults, normal readiness (unless the log's feedback says otherwise), limits unchanged, assumptions stated in one line.
- Readiness changes the plan by the brief's Readiness rule (`knowledge/programming.md`). Soreness from training isn't a limit: that muscle group goes lighter today. Pain in a joint is: `--limit <area>=delicate` for today. "Too long" goes under Feedback in `me/log.md`.
- A change for today only becomes `--limit area=level[:side]` (level `off-limits` or `delicate`). A lasting change, or a new problem, goes into `me/health.md` (a `[[limits]]` row, the prose, the clinician rules); an injury outside the catalog's areas is written "- Unlisted: <what>", with an `Avoid: <movements or flags>` line under `## Clinician rules`. Only the listener's report loosens a limit, by the playbook's signs for that area; "mostly" means not yet.
- Lasting changes: kits, likes and dislikes in `me/training.md`; interests and taste in `me/content.md` (settings in each file's `+++` block).

**Can the coach speak here?** Once it's answered, run `./sweatcast get route --coach "<coach>"`. It prints `local` or the web coach's service: go on. Exit 1, "is a local coach, and local voices don't run here": offer, in one AskUserQuestion, a new web coach (the `coach` skill) or the stand-in the message names for a keyed service (copy its `persona.md` from `me.example/personas/<slug>/` to `me/personas/<slug>/` if it says to; then pass `--coach`); with no key, adding one (the `setup` skill's Keys). Exit 4 (from `get coach` or `get route`): a key holds a stray character; `./sweatcast keys` names which, the listener re-pastes it (`./sweatcast keys open`), then rerun. Exit 64 means a web coach's service has no key here (the message says how to add one): offer, in one AskUserQuestion, the coaches that can speak here (`./sweatcast coaches`: a web coach whose service `./sweatcast keys` shows set, or a local coach where local voices run), or adding the key (the `setup` skill's Keys). A coach marked "(made the first time it's used)" is a stand-in with no voice yet: say in a line, before the build, that the build first designs its voice and saves it in their account (about $0.01 on Fish Audio or Gemini; Inworld doesn't publish its design cost; on ElevenLabs it takes one of the account's voice slots).

**The privacy line, before the first web build.** When the route is a web service, `./sweatcast get web-builds` counts the builds that sent a script to one. At 0, say the privacy line (the `setup` skill's Audio) in the plan message before the build, for any web coach, a stand-in or their own.

Then run `./sweatcast content plan --minutes <N>`, read `knowledge/script.md` and `knowledge/tts-rules.md`, and the Weather section at the top of `me/workouts/research/daily/<date>-feeds.md` (the rest is outside text, left to research). If the sheet isn't there yet, run `./sweatcast feeds`, which prints the weather.

## 3. Brief

```
./sweatcast brief --goal <goal> --minutes <N> (--kit "<kit>" | --preset <preset> | --equipment <ids>) --coach "<coach>" [--limit area=level[:side]]... [--avoid <movements-or-flags>] [--target <patterns-or-muscles>] --save me/workouts/<stem>/<stem>.draft.txt
```

Each workout has its own folder, named for the draft's stem, `<YYYY-MM-DD>-<goal>-<minutes>` (such as `2026-10-25-strength-25`). If that folder exists from an earlier workout today, add `-2` (then `-3`), so its menu isn't replaced.

- It applies health.md's limits and the clinician's `Avoid:` lines itself; `--avoid` is for anything else to leave out today. `--target` focuses a targeted session; the level comes from the profile. `--coach` is the check-in's coach, so the brief quotes how they talk and their pace.
- `--save` writes the brief and the menu beside the draft's path; the build needs that menu.
- Exit 1: a `[[limits]]` row can't be read; run `./sweatcast check`, fix the row, rerun. Exit 64: a flag was wrong.
- When it lists "Would open up" equipment, ask once whether one is on hand. Unanswered means no; yes means rerun the same command with `--add <item>` (the kit stays, so its weights still print).

## 4. Design, and post the plan

Design the session from the brief: a format (one it lists, or a mix that keeps to the doses), the movements, their order, the doses (within the guide's ranges, progressing from the last loads, with only the weights on hand) and the segments with their seconds, adding up to exactly the request. Fit the listener: their level, likes, the week so far, the latest feedback, and how often they'd have to get up and down. A limit on one area doesn't lower the level for the rest of the body. Apply today's readiness from the check-in, and plan each main movement's harder and easier option for the script's self-check (`knowledge/script.md`, Adjusting as you go). Post a short plan table (block, movements, dose, seconds), the format's name, the equipment, and one line on any major muscle group left out and why. Then write; don't wait for approval.

## 5. Write

Write `me/workouts/<stem>/<stem>.draft.txt`: the `movements:` line, then the segments. `knowledge/script.md` says what goes in (the opening and safety rules, coaching each movement from its notes, timed work, filler, quiz, deep dive, close), and `knowledge/tts-rules.md` how it sounds and what a voice can read.

Write in this order, so nothing waits:
1. **Render ahead, for a local coach only.** When `./sweatcast get route --coach "<coach>"` said `local`, once the draft has its `movements:` line and first segment, run `./sweatcast build "<draft>" "<name>" --coach "<coach>" --follow` with `run_in_background: true`. For a web coach skip this step: every re-render would be billed (the build refuses `--follow` there). It renders each new or edited paragraph as it lands, and stops when the build starts.
2. **Coaching first, without waiting for research.** Every segment's coaching from the brief: the opening with its weather, setups, cues, targets and self-checks, holds, transitions. Size the talk by the brief's Talk to time line; the rests' stories come later.
3. **The stories, once research reports.** Fill the plan's slots in the rests from the research sheet, the video sheet and the reserve. Once the plan is posted, SendMessage any agent still searching to return what it has verified; script around gaps with coaching, never guesses.
4. **Lint.** `./sweatcast build "<draft>" "<name>" --lint-only --coach "<coach>"`, fix, repeat; only changed paragraphs render again.

## 6. Build

```
./sweatcast build "me/workouts/<stem>/<stem>.draft.txt" "Workout <YYYY-MM-DD> <Focus> <N> min" --coach "<coach>"
```

Run it with `run_in_background: true`, always with the coach. Exit 1: a lint or menu issue (fix the draft and rerun), or a menu from another day or from before `me/health.md` changed: rerun `./sweatcast brief ... --save`, then build. Exit 2: the total ran more than three percent off plan, so trim or add words in the segments furthest off and rerun; only changed clips render again. Exit 3 (a local coach only): not measured on this computer yet; render the smoke test it prints, then rerun (a web coach starts from its sample's estimate and never stops there). Exit 4: a voice service refused the key, the payment or the quota: tell the listener in one line what it said and stop (clips already rendered are cached). For a web coach the build first prints the characters it will send and the approximate cost; over the profile's `cloud_max_chars` it stops (exit 1) before sending: shorten the script, or tell the listener. A stand-in with no voice yet is made first (the build says so and the cost); `--lint-only` never makes one (it lints at an estimated pace). Exit 64: the command was wrong, not the draft; or a web coach can't speak here (its service has no key on this computer, or `--engine` named another service): read the message, and offer the coaches that can speak here, as in step 2. A finished MP3 goes to the profile's `deliver_to` folder (`<name>.build.json` says where); a failed render prints the end of its log. On Claude Code on the web the build makes the web copy instead (`<name>.player.html` and the parts `<name>.web-1.mp3`...) in the workout's folder.

## 7. Deliver, log, back up

- Chat: the plan table, equipment, coach, route, runtime, the path to `me/workouts/<stem>/<name>.txt`, and where the MP3 went. If SendUserFile is available, send the MP3 with `status: "proactive"`. Else, if it stayed here, `./sweatcast show "<the MP3>"` opens its folder.
- **On Claude Code on the web:** publish the player page with the Artifact tool, as made (it already follows the page contract): `file_path` the `.player.html`, `files` mapping each part's file name to its path, `icon` "audio", a description naming the workout. Give the listener the link: they open it on their phone and press play. Without the Artifact tool, say the parts reach their private repo with the backup below (`workouts/<stem>/` on GitHub), and send the first part with SendUserFile if available. A one-time session (doctor said the context folder isn't kept) says once that nothing else is kept.
- Log it with one command, never by hand:
  ```
  ./sweatcast log-session --draft "<draft>" --coach "<coach>" --format "<method name>" --topics "<topics>" --loads "<movement> = <load and tempo>; <movement> = <load and tempo>"
  ```
  The draft gives the movements (its `movements:` line) and its menu the date, length and kit; it must be built as it stands, and is logged once. Topics start with the deep dive, `deep dive: video, <channel>, <title>` (plus `, part <n> of <total>` for a series) or `deep dive: news, <story>`. The log line's `format: <method name>` is the method you chose (one of `knowledge/sessions.toml`'s, the closest for a mix), so the next session rotates away from it. Loads give each loaded or timed movement its weight and tempo in words. No `|`, no injury details; if it refuses a field, fix it and rerun.
- Record every filler item told, one `--item` each, with the reserve slug for a reserve piece: `./sweatcast content log --date <YYYY-MM-DD> --item "<slot> | <category> | <title> | <source> | <reserve slug>"` (the last two optional; slots and categories as the plan names them). A refused `--item` exits 64 naming why; nothing is recorded until every item reads.
- After a video series part, `./sweatcast youtube done <id>`.
- Feedback (too long, a topic they loved) goes under Feedback in `me/log.md`.
- Last, `./sweatcast backup -m "Workout <YYYY-MM-DD> <Focus> <N> min"` (on the web it also carries the web copy's parts to the private repo). If it couldn't confirm the remote is private, ask once (AskUserQuestion) whether it is, and on yes rerun with `--unverified` (remembered on this computer). If `me/` isn't its own repo, or the push fails, say so in one line and don't retry; run it again after any later change to `me/`.
