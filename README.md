# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news and stories, and renders it to an MP3 with a local voice. The audio is the timer: every segment starts on the clock.

## How it works

1. In Claude Code, open this folder and ask for a workout ("I'd like a workout", "25 minutes at the hotel, just go"). The `workout` skill (`.claude/skills/workout/SKILL.md`) asks only for what you didn't say.
2. A background agent researches the filler (sports, local news, tech, on this day) while you answer.
3. Claude writes a segmented draft (`@@ <seconds> | <label>` before each segment), sized to fill each segment's seconds.
4. `tools/build.sh` lints the draft for text-to-speech problems, predicts each segment's spoken length for the chosen voice, exports a clean `.txt`, and renders a loudness-normalized `.mp3`.

## Layout

| Path | What |
|---|---|
| `CLAUDE.md` | Project instructions for Claude |
| `knowledge/` | Profile, injury playbook, equipment library, text-to-speech rules, how to make voices |
| `log.md` | Session log and feedback |
| `tools/tts_build.py` | Draft linter (including predicted spoken seconds per segment) and `.txt` exporter |
| `tools/voices.py` | VoiceStudio voice lookup and OmniVoice's own length estimate; run it to list voices |
| `tools/render.py` | In-process OmniVoice renderer with clip cache, per-segment silence padding and loudness normalization |
| `tools/build.sh` | Draft to `.txt` and `.mp3` in one step |
| `workouts/` | Scripts, drafts, research sheets (MP3s are git-ignored) |

## Requirements

- macOS with [VoiceStudio](https://github.com/debpalash/VoiceStudio) installed and opened once, so its Python runtime and the OmniVoice model are present. The app itself doesn't need to be running.
- `ffmpeg` (`brew install ffmpeg`).
- Claude Code.

Rendering runs at about 0.7 times the length of the speech on an M3 (a 25-minute workout takes about 17 minutes). Edits re-render only the clips that changed.
