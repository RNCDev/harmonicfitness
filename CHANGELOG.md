# Changelog

All notable changes to sweatcast. The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

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
