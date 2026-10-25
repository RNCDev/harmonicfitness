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
- `./sweatcast check`: an issue in `me/health.md` (a malformed `[[limits]]` row applies no limit; an injury in prose with no row gets no rule) is fixed at the check-in, then checked again. Notes are fine; with no experience level the default is novice until set, so offer to set it.
- `./sweatcast content plan`: the filler plan at the default length (whether the deep dive is a video or news, and whether the pantry needs restocking).
- `./sweatcast get coach`: who's coaching (the coach used last, though once the listener has a coach of their own it wins over a stand-in used last; else a stand-in that works here). The check-in says so in a line, and asks only if the request suggests another coach. If it stops (exit 1) because the coach used last is archived, ask the Coach question with the coaches `./sweatcast coaches` lists. No coach yet: run the `coach` skill.
- Read `me/profile.md`, `me/health.md` and `me/log.md`. No `me/profile.md` means this copy isn't set up: run the `setup` skill. On Claude Code on the web (`./sweatcast doctor` says so), only web coaches speak and the MP3 arrives as a web copy (step 7). A tool that says the context folder is in an older format: run `./sweatcast migrate`, then rerun.

Nothing else before the check-in: the feeds, the knowledge files and the brief come after it.

## 2. Check-in, with research launched first (one message)

1. **Research**, in the background, from the templates in `research.md` beside this file: today's research always (it runs the feeds and the plan itself); the video agent when the plan's deep dive is video; the pantry agent when the plan has a Restock section.
2. **Check-in** (AskUserQuestion): up to four questions, only about what the request doesn't settle, in this order (past four, drop Coach, then Length):

| Slot | Settled by | Options when asked |
|---|---|---|
| Limits | "ankle feels better", "my legs are sore" | "Anything sore or off today?", one multi-select: an option per health.md limit worded "<area>: same / better / worse", "Sore somewhere else (say where)" when there's room, and "Nothing new" (Recommended). Without limits it's just the last two. |
| Readiness | "slept badly", "feeling strong", "last one was too easy" | "How are you coming in today?": Normal, last one about right (Recommended); Low (tired, short on sleep or stressed); Fresh, and last one felt easy; Last one was too hard. Too long, or anything else, through Other. |
| Goal | "strength", "bike intervals", "mobility" | Strength (Recommended), General fitness, Conditioning, Mobility and breathing; targeted work and skill through Other |
| Length | "25 minute", "quick" (15) | 25 min (Recommended, the profile's default), 15, 30, 45 |
| Kit | "hotel", a kit's name | The profile's `[[kits]]`, the first Recommended; a preset (bodyweight, hotel-room, hotel-gym, full-gym) through Other |
| Coach | a coach's name, "another coach", "a new coach" | Asked only when the request suggests a change: the coach used last (`./sweatcast get coach`, Recommended) and the others from `./sweatcast coaches`; when `get coach` stopped on an archived coach, there's no coach used last, so offer the active coaches `./sweatcast coaches` lists. Name each by the listener's name for them, never by service; "a new coach" runs the `coach` skill first, and the workout continues with them |

- "Just go" means ask nothing: profile defaults, normal readiness (unless the log's feedback says otherwise), limits unchanged, assumptions stated in one line.
- Readiness changes the plan by the brief's Readiness rule (`knowledge/programming.md`). Soreness from training isn't a limit: that muscle group goes lighter today. Pain in a joint is: `--limit <area>=delicate` for today. "Too long" goes under Feedback in `me/log.md`.
- A change for today only becomes `--limit area=level[:side]` (level `off-limits` or `delicate`). A lasting change, or a new problem, goes into `me/health.md` (a `[[limits]]` row, the prose, the clinician rules); an injury outside the catalog's areas is written "- Unlisted: <what>", with an `Avoid: <ids or flags>` line under `## Clinician rules`. Only the listener's report loosens a limit, by the playbook's signs for that area; "mostly" means not yet.
- Lasting changes to kits, likes and dislikes or interests go into `me/profile.md`, keeping the `+++` settings block at the top.

**Can the coach speak here?** Once it's answered, run `./sweatcast get route --coach "<coach>"`. It prints `local` or the web coach's service: go on. Exit 64 means a web coach's service has no key on this computer (the message says how to add one): offer, in one AskUserQuestion, the listener's other coaches that can speak here (in `./sweatcast coaches`, a web coach whose service `./sweatcast keys` shows set, or a local coach where local voices run), plus adding the key (the `setup` skill's Keys). A coach marked "(made the first time it's used)" is a stand-in with no voice yet: say in a line, before the build, that the build first designs its voice and saves it in their account (about $0.01 on Fish Audio or Gemini; Inworld doesn't publish its design cost; on ElevenLabs it takes one of the account's voice slots).

**The privacy line, before the first web build.** When the route is a web service, check whether any web build has run: `grep -cE '"route": "(fish|elevenlabs|gemini|inworld)"' me/workouts/.logs/builds.jsonl` (each build's record names its route). A count of 0, or no such file, means none has: say the privacy line (the `setup` skill's Audio: the service receives the script, which can mention their injuries; Gemini's free tier trains on what it's sent) in the plan message, before the build. This holds for any web coach, a stand-in or one of their own.

Then run `./sweatcast content plan --minutes <N>` for the session's length, read `knowledge/script.md` and `knowledge/tts-rules.md`, and the Weather section at the top of `me/workouts/research/daily/<date>-feeds.md` (the rest is outside text, left to research). If the sheet isn't there yet, run `./sweatcast feeds`, which prints the weather.

## 3. Brief

```
./sweatcast brief --goal <goal> --minutes <N> (--kit "<kit>" | --preset <preset> | --equipment <ids>) [--limit area=level[:side]]... [--avoid <ids-or-flags>] [--target <patterns-or-muscles>] --save me/workouts/<YYYY-MM-DD>-<slug>/<YYYY-MM-DD>-<slug>.draft.txt
```

Each workout has its own folder, named for the draft's stem (`<YYYY-MM-DD>-<goal>-<minutes>`, such as `2026-10-25-strength-25`): the brief, the menu, the draft, and later the script and build record all go there.

- It applies health.md's limits and the clinician's `Avoid:` lines itself; `--avoid` is for anything else to leave out today. `--target` focuses a targeted session; the level comes from the profile.
- `--save` writes the brief and the menu beside the draft's path; the build needs that menu.
- Exit 1: a `[[limits]]` row can't be read; run `./sweatcast check`, fix the row, rerun. Exit 64: a flag was wrong.
- When it lists "Would open up" equipment, ask once whether one is on hand. Unanswered means no; yes means rerun with `--equipment <the kit's ids>,<item>`.

## 4. Design, and post the plan

Design the session from the brief: a format (one it lists, or a mix that keeps to the doses), the movements, their order, the doses (within the guide's ranges, progressing from the last loads, with only the weights on hand) and the segments with their seconds, adding up to exactly the request. Fit the listener: their level, likes, the week so far, the latest feedback, and how often they'd have to get up and down. A limit on one area doesn't lower the level for the rest of the body. Apply today's readiness from the check-in, and plan each main movement's harder and easier option for the script's self-check (`knowledge/script.md`, Adjusting as you go). Post a short plan table (block, movements, dose, seconds), the format's name, the equipment, and one line on any major muscle group left out and why. Then write; don't wait for approval.

## 5. Write

Write `me/workouts/<YYYY-MM-DD>-<slug>/<YYYY-MM-DD>-<slug>.draft.txt`: the `movements:` line, then the segments. `knowledge/script.md` says what goes in (the opening and safety rules, coaching each movement from its notes, timed work, filler, quiz, deep dive, close), and `knowledge/tts-rules.md` how it sounds and what a voice can read.

Write in this order, so nothing waits:
1. **Render ahead, for a local coach only.** When `./sweatcast get route --coach "<coach>"` said `local`, once the draft has its `movements:` line and first segment, run `./sweatcast build "<draft>" "<name>" --coach "<coach>" --follow` with `run_in_background: true`. For a web coach skip this step: every re-render would be billed, so only the final build sends text (the build refuses `--follow` there). It renders each new or edited paragraph as it lands, and stops when the full build starts.
2. **Coaching first, without waiting for research.** Every segment's coaching from the brief: the opening with its weather, setups, cues, targets and self-checks, holds, transitions. Size the talk by the brief's Talk to time line; leave the rests' stories for later.
3. **The stories, once research reports.** Fill the plan's slots in the rests, from the research sheet, the video sheet and the pantry. Once the plan is posted, SendMessage any agent still searching to return what it has verified; script around gaps with coaching, never guesses.
4. **Lint.** `./sweatcast build "<draft>" "<name>" --lint-only`, fix, repeat; only changed paragraphs render again.

## 6. Build

```
./sweatcast build "me/workouts/<stem>/<stem>.draft.txt" "Workout <YYYY-MM-DD> <Focus> <N> min" --coach "<coach>"
```

Check it with `--lint-only` first, then run it with `run_in_background: true` (always pass the coach, so the build never guesses). Exit 1: a lint or menu issue, so fix the draft and rerun. Exit 2: the total ran more than three percent off plan, so trim or add words in the segments furthest off and rerun; only changed clips render again. Exit 3 (a local coach only): the coach isn't measured on this computer yet, so render the smoke test it prints, then rerun. A web coach never stops there: it starts from a pace estimated from its sample, and each render measures it. Exit 4: a voice service refused the key, the payment or the quota: tell the listener in one line what it said and stop (clips already rendered are cached). For a web coach the build first prints the characters it will send and the approximate cost; over the profile's `cloud_max_chars` it stops (exit 1) before sending: shorten the script, or tell the listener. A stand-in with no voice yet is made first (the build says so and what it costs); `--lint-only` never makes one, so the lint runs at an estimated pace. Exit 64: the command was wrong, not the draft; or a web coach can't speak here (its service has no key on this computer, or `--engine` named another service): read the message, and offer the coaches that can speak here, as in step 2. Only one render runs at a time. A finished MP3 is copied to the profile's `deliver_to` folder (the build record, `<name>.build.json`, says where it went); a failed render prints the end of its log. On Claude Code on the web the build makes the web copy instead: `<name>.player.html` and the parts `<name>.web-1.mp3` (more for a long workout), in the workout's folder.

## 7. Deliver, log, back up

- Chat: the plan table, equipment, coach, route, runtime, the path to `me/workouts/<stem>/<name>.txt`, and where the MP3 went. If SendUserFile is available, send the MP3 with `status: "proactive"`.
- **On Claude Code on the web:** publish the player page with the Artifact tool, as made (it already follows the page contract): `file_path` the `.player.html`, `files` mapping each part's file name to its path, `icon` "audio", a description naming the workout. Give the listener the link: they open it on their phone, press play and put it away. Where the Artifact tool isn't available, or it refuses, say the parts reach their private repo with the backup below (the `workouts/<stem>/` folder on GitHub), and send the first part with SendUserFile if that's available. A one-time session (doctor said the context folder isn't kept) says once that nothing else is kept.
- Log it with one command, never by hand:
  ```
  ./sweatcast log-session --date <YYYY-MM-DD> --minutes <N> --kit "<kit>" --coach "<coach>" --draft "<draft>" --topics "<topics>" --format "<method name>" --loads "<movement> = <load and tempo>; <movement> = <load and tempo>"
  ```
  `--draft` takes the movements from the draft's `movements:` line. Topics start with the deep dive, `deep dive: video, <channel>, <title>` (plus `, part <n> of <total>` for a series) or `deep dive: news, <story>`. The log line's `format: <method name>` is the format you chose (`straight-sets`, `paired-sets`, `circuit`, `intervals`, `tabata`, `bike-intervals`, `flow` or `skill`, the closest for a mix), so the next session rotates away from it. Loads give each loaded or timed movement's weight and tempo in words. No `|`, no injury details. If it refuses a field, fix that field and rerun.
- Record every filler item told, one `--item` each, with the pantry slug for a pantry piece: `./sweatcast content log --date <YYYY-MM-DD> --item "<slot> | <category> | <title> | <source> | <pantry slug>"` (the last two fields optional).
- After a video series part, `./sweatcast youtube done <id>`.
- Feedback (too long, a topic they loved) goes under Feedback in `me/log.md`.
- Last, `./sweatcast backup -m "Workout <YYYY-MM-DD> <Focus> <N> min"` (on the web it also carries the web copy's parts to the private repo). If `me/` isn't its own repo, or the push fails, say so in one line and don't retry; run it again after any later change to `me/`.
