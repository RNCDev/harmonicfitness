# Roadmap

What's planned beyond the current release, in rough order. Each section is a future release. None of it is promised or dated, and each one is shaped further before it's built. What has shipped is in `CHANGELOG.md`.

## Smarter workouts: progress you can feel

Each workout is carefully planned and screened for safety, but little carries from one week to the next. The brief passes the language model the last loads, the newest feedback line and the past seven days' counts, and leaves progression to it. This release makes the weeks add up.

### 1. Close the loop after each workout
- **Now:**
  - The script asks "how hard did that feel?" at the close, but nothing hears the answer.
  - The loads logged are the ones prescribed, not the ones done (`log-session --loads`).
  - `rpe` is stored in the log but never read (`tools/sessionlog.py`).
- **Plan:**
  - Add a short card after each workout, on the web and as a check-in question locally, with three questions:
    - How hard was it, 0 to 10?
    - Did you finish every set? (yes, most, no)
    - One thing to change.
  - Write the answers into the log: effort to `rpe`, plus what was actually done beside what was prescribed.
  - Progress from what was done.
  - Turn "too hard" or "too easy" into the effort signal automatically (`interests add --source feedback`), so it no longer depends on the language model remembering to.
- **Where:** `tools/logsession.py`, `tools/sessionlog.py`, `tools/workoutlog.py`, `tools/brief.py`, the web app's Logs page and a post-recording card in the chat.

### 2. A training block, not just a session
- **Now:** nothing plans across weeks. There's no phase, no deload, no goal with a horizon, and weekly volume is counted as sessions per pattern rather than hard sets per muscle (`tools/coverage.py`).
- **Plan:**
  - A block model kept in `me/`: a goal, a phase of 4 to 6 weeks, and a lighter week every Nth.
  - Weekly hard sets counted per muscle against `programming.md`'s targets.
  - The brief prints it ("Week 3 of 5, building; next week lighter"), and the menu and doses follow it.
  - Keep it in code (`tools/sessions.py`, `knowledge/sessions.toml`), not prose, so Claude Code, Codex and the web app plan the same way.
  - Every number is marked sourced or house default, as the knowledge files already do.

### 3. Feedback that sticks
- **Now:** the brief shows only the newest feedback line (`tools/brief.py`). A rating is itself written as a feedback line, so rating a workout can push out a real comment such as "too long".
- **Plan:**
  - Show the last three comments.
  - Keep ratings apart from comments.
  - Let a negative rating plus a reason feed the effort and length signals.

## Music

The coach talks over silence or the optional pulse bed. Many people train to their own music.

- **Plan:**
  - Music under the coach, ducked while it speaks.
  - Either the listener's own playlists through a music service, or a "play alongside" mode that leaves their music app running and keeps the coach clear over it.
  - Pick the approach once the services' terms and APIs for mixing are checked: most streaming services don't allow their audio to be mixed into a file, so "alongside" may be the only way.
- **Open questions:**
  - Which services?
  - Mixed into the MP3, or played live beside it?
  - How does it fit with a podcast app as the player?

## Tuning (to be shaped)

Ways for the listener to tune what a session sounds like. Not yet thought through; these are candidates to choose from:

- **How much story:** stories in the rests (today), "just coach me" (cues and form only), or music in their place (see Music).
- **Readiness in one tap:** Fresh, Normal or Low beside the request on the web, where the check-in never asks how they feel, so the readiness rules in `knowledge/programming.md` apply there too.
- **Level and pace that learn:**
  - Suggest moving up a level after a run of workouts rated easy.
  - Learn the listener's own rep pace from "finished early" or "waited", in place of one number for everyone (`sessions.toml`'s `rep_pace`).
  - Have the lint warn when a counted set's cues ask for slow reps, pauses or holds that its clock (about 2.25 s a rep) can't fit. The ready-made workouts' review found this in four of five scripts: a listener who follows "slow on the way down" hears "last one" around rep six.

## Later, not yet planned
- **Sharing a workout:** for now, download the MP3 and send it.
- **Chapters** in the MP3 and on the lock screen, to skip a story or repeat a set.
- **Programs** with a named goal ("a first pull-up in six weeks").
- **Readiness from a watch:** Apple Health or Google Fit data such as resting heart rate, sleep and steps.
