# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news, science and stories, and renders it to an MP3 in a natural coach's voice on your own Mac. The audio is the timer: every segment starts on the clock.

Current version: see `VERSION` and `CHANGELOG.md`.

## First run

1. **Install.** On an Apple Silicon Mac, install [VoiceStudio](https://github.com/debpalash/VoiceStudio) and open it once so it sets up its bundled Python, which includes `mlx-audio`. Also install `ffmpeg` (`brew install ffmpeg`) and Claude Code. No separate Python is needed. The voice models (Chatterbox Turbo for Coach E, Qwen3-TTS for Coach G, a few GB each) download on first use.
2. **Make the profile yours.** `knowledge/profile.md` describes the listener: neighborhood, equipment, injuries and the rules around them, interests, feeds (teams, local news, science, weather location), and tone. Every workout is planned from it, and the copy here describes the author, so replace it with your own details before your first session.
3. **Voices.** Two coach voices ship in `voices/`. To make your own, see `knowledge/voices.md`, then list it under Voices in `knowledge/profile.md`; the first is the default. `python3 tools/voices.py` lists the voices sweatcast can find.
4. **Quit VoiceStudio** before rendering. Renders don't need it, and two voice models at once can run short of memory.

Then ask for a workout, as below.

## How it works

1. In Claude Code, open this folder and ask for a workout ("I'd like a workout", "25 minutes at the hotel, just go"). The `workout` skill (`.claude/skills/workout/SKILL.md`) asks only for what you didn't say.
2. `tools/feeds.py` pulls your teams' results and schedules, the weather, and recent local, science and tech headlines from the feeds listed in your profile in about a second. Background agents then research the rest while you answer: two current science and technology breakthroughs, on this day, and a deep dive that alternates between a news story and a video from your favorite YouTube channels. A long video becomes a series, one part per session.
3. Claude plans a whole-body session around your injuries, progressing from the loads it logged last time, then writes a segmented draft (`@@ <seconds> | <label>` before each segment) in short paragraphs, and starts rendering the first half while it writes the rest.
4. `tools/build.sh` lints the draft for text-to-speech problems, predicts each segment's spoken length for the chosen voice, exports a clean `.txt`, renders a loudness-normalized `.mp3` into `workouts/`, and copies it to a Google Drive folder that syncs to your phone.

Each paragraph is voiced by cloning the voice's ten-second reference clip. A soft chime marks the start of each segment and each change inside an interval, so you can keep time by ear even if a word comes out garbled, and a rising three-note tone marks the end. Spare seconds in a segment are spread over its paragraph breaks, and a segment that runs slightly long borrows from the next one's padding, so the whole workout lands within a few percent of plan. With the default voice, a 30-minute workout renders in under 20 minutes in the background. Edits re-render only the clips that changed.

## Layout

| Path | What |
|---|---|
| `CLAUDE.md` | Project instructions for Claude, including the release process |
| `knowledge/` | Profile, injury playbook, equipment library, exercise science, text-to-speech rules, how voices work |
| `voices/` | Voice reference clips, transcripts and engine settings |
| `log.md` | Session log and feedback |
| `tools/build.sh` | Draft to `.txt` and `.mp3` in one step |
| `tools/tts_build.py` | Draft linter (predicted spoken seconds per segment, paragraph length, coaching structure) and `.txt` exporter |
| `tools/voices.py` | Voice lookup and spoken-length prediction; run it to list voices |
| `tools/char_weight.py` | OmniVoice's character-weight rule (Apache 2.0), vendored for the prediction |
| `tools/render.py` | Renderer (Chatterbox Turbo or Qwen3-TTS via `mlx-audio`) with clip cache, timing and loudness normalization |
| `tools/youtube.py` | Picks a recent video from your favorite channels or continues a series, and saves its transcript |
| `tools/feeds.py` | Fetches the profile's feeds (results, schedules, weather, headlines) into a dated sheet |
| `tools/coverage.py` | Reads the log and lists the muscle groups the last session left out, its format and the last loads |
| `tests/` | Fast checks for the lint, timing layout, log, feeds and series (`python3 -m unittest discover tests`) |
| `workouts/` | Scripts, drafts, research sheets (MP3s are git-ignored) |
| `VERSION`, `CHANGELOG.md` | Release number and history |

## Versioning

sweatcast follows [Semantic Versioning](https://semver.org). Each release is tagged `vX.Y.Z` and published on the GitHub releases page; `CHANGELOG.md` says what changed.
