# Changelog

All notable changes to sweatcast. The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

## [1.1.0] - 2026-10-21

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

## [1.0.0] - 2026-10-21

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
- The clip cache key includes the model revision, so clips rendered before 1.0.0 render once more.

### Removed
- OmniVoice and every VoiceStudio dependency: the VoiceStudio voice database, OmniVoice's text helpers, the OmniVoice render options (`--steps`, `--guidance`, the temperatures, `--speed`) and the re-launch under VoiceStudio's Python.
- The author's profile, log, drafts, scripts and research from the public repo's current tree. They remain in the git history of earlier versions.

## [0.6.0] - 2026-10-21

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

## [0.5.0] - 2026-10-21

Timing that holds the whole workout to plan instead of every segment, and brain teasers for the quiz.

### Added
- `tools/youtube.py puzzles`: lists recent videos from a new Puzzles line in `knowledge/profile.md` (Presh Talwalkar's MindYourDecisions) that haven't been used as a quiz yet. The headlines agent picks one that works by ear, saves its transcript and writes `workouts/research/puzzles/<id>.md` (the puzzle as said aloud, the answer and the reason); a puzzle with a sheet isn't offered again. The session's quiz beat uses it when there is one, and falls back to the session's own material.
- `tts_build.layout`, one timing layout shared by the lint's prediction and the render, so they agree.
- Tests for the new timing and the puzzle list: 49 in all.

### Changed
- A segment with time to spare widens its paragraph breaks (up to about two seconds each), keeps a short tail and ends early instead of padding with silence. A segment that runs long is still paid back from the next ones' spare time.
- Only the whole workout is held to plan, within three percent either way. The lint prints the predicted length and blocks only when the total is off by more than that, or when a segment is far off its slot (under 80 or over 110 percent of it, down from 90 to 100). The render exits 2 only when the finished workout is more than three percent over or under plan; `--tolerance` now sets that total allowance.
- The workout skill, `CLAUDE.md`, `README.md`, `knowledge/tts-rules.md` and `knowledge/voices.md` describe the new timing and the puzzle quiz.

## [0.4.0] - 2026-10-21

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

## [0.3.0] - 2026-10-21

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

## [0.2.0] - 2026-10-20

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

## [0.1.0] - 2026-10-19

First working version.

### Added
- The `workout` skill: check-in, plan, background research, script, build and log.
- `tools/build.sh`: lint, `.txt` export, OmniVoice render with per-segment padding and loudness normalization, and a copy to Google Drive.
- Spoken-length prediction per VoiceStudio voice.
- `tools/youtube.py` for video deep dives from favorite channels.
- Profile, injury playbook, equipment library, exercise science and text-to-speech rules.
