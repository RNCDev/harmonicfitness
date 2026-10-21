# Changelog

All notable changes to sweatcast. The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

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
