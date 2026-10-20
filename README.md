# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news and stories, and renders it to an MP3 with a local voice. The audio is the timer: every segment starts on the clock.

## First run

1. **Install.** On a Mac, install [VoiceStudio](https://github.com/debpalash/VoiceStudio), open it once, and let it finish downloading its voice model (about 3 GB). Also install `ffmpeg` (`brew install ffmpeg`) and Claude Code. No separate Python is needed; the tools run on VoiceStudio's bundled one.
2. **Make the profile yours.** `knowledge/profile.md` describes the listener: neighborhood, equipment, injuries and the rules around them, interests, and tone. Every workout is planned from it, and the copy here describes the author, so replace it with your own details before your first session.
3. **Add the voices.** In VoiceStudio's Gallery, click **Use voice** on each voice listed under Voices in `knowledge/profile.md`, or make your own (see `knowledge/voices.md`) and edit that list. The first voice is the default. `python3 tools/voices.py` shows the voices sweatcast can find.
4. **Quit VoiceStudio.** Renders don't need it, and two copies of the voice model at once can run short of memory.

Then ask for a workout, as below.

## How it works

1. In Claude Code, open this folder and ask for a workout ("I'd like a workout", "25 minutes at the hotel, just go"). The `workout` skill (`.claude/skills/workout/SKILL.md`) asks only for what you didn't say.
2. A background agent researches the filler (sports, local news, tech, on this day) while you answer.
3. Claude writes a segmented draft (`@@ <seconds> | <label>` before each segment), sized to fill each segment's seconds.
4. `tools/build.sh` lints the draft for text-to-speech problems, predicts each segment's spoken length for the chosen voice, exports a clean `.txt`, and renders a loudness-normalized `.mp3` into `workouts/`.

Rendering runs at about 0.7 times the length of the speech on an M3 (a 25-minute workout takes about 17 minutes). Edits re-render only the clips that changed.

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
