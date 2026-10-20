# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news and stories, and renders it to an MP3 with a local voice. The audio is the timer: every segment starts on the clock.

## How it works

1. In Claude Code, open this folder and ask for a workout ("I'd like a workout", "25 minutes at the hotel, just go"). The `workout` skill (`.claude/skills/workout/SKILL.md`) asks only for what you didn't say.
2. A background agent researches the filler (sports, local news, tech, on this day) while you answer.
3. Claude writes a segmented draft (`@@ <seconds> | <label>` before each segment), sized by word count to your measured words per minute.
4. `tools/build.sh` lints the draft for text-to-speech problems, exports a clean `.txt`, and renders the `.mp3`.

## Layout

| Path | What |
|---|---|
| `CLAUDE.md` | Project instructions for Claude |
| `knowledge/` | Profile, injury playbook, equipment library, text-to-speech rules |
| `log.md` | Session log and feedback |
| `tools/tts_build.py` | Draft linter and `.txt` exporter |
| `tools/render.py` | In-process OmniVoice renderer with paragraph cache and per-segment silence padding |
| `tools/build.sh` | Draft to `.txt` and `.mp3` in one step |
| `workouts/` | Scripts, drafts, research sheets (MP3s are git-ignored) |

## Requirements

- macOS with [VoiceStudio](https://github.com/debpalash/VoiceStudio) installed and opened once, so its Python runtime and the OmniVoice model are present. The app itself doesn't need to be running.
- `ffmpeg` (`brew install ffmpeg`).
- Claude Code.

Rendering runs at about 0.85 times real time on an M3 (a 25-minute workout takes about 20 minutes). Edits re-render only the paragraphs that changed.
