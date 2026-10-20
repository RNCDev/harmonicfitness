# Workout audio studio

I listen to narrated workouts through earbuds, with no screen and no timer. The audio is the workout: it tells me what to do, keeps me company, and moves me along on time. Every segment is padded to its planned seconds, and the lint predicts each segment's spoken length for the chosen voice, so a segment can't overrun or go quiet unnoticed.

Priorities, in order: safe for my body today, clean to the ear, worth listening to.

**Any request for a workout, in any words, runs the `workout` skill** (`.claude/skills/workout/SKILL.md`). It covers check-in, plan, research, script, build and log.

## Files
- `knowledge/profile.md`: stable facts about me (setup, voices, equipment kits, interests, standing rules for each injury). Update it when something lasting changes.
- `knowledge/tts-rules.md`: how to write for text-to-speech.
- `knowledge/voices.md`: how to make a voice in VoiceStudio and add it to the profile.
- `knowledge/injury-playbook.md`, `knowledge/equipment-library.md`: programming references. Where they disagree with the profile, the strictest wins, and anything the profile bans is out.
- `log.md`: session log and my feedback. Feedback I give at any time ("too long", "loved that topic") goes here.
- `knowledge/exercise-science.md`: verified facts per movement, reused across sessions so research doesn't repeat them.
- `tools/build.sh`: draft to `.txt` and `.mp3` in one step (lint with `tools/tts_build.py`, then render with `tools/render.py`), then a copy of the MP3 to the Google Drive folder named in the profile. `tools/voices.py` looks up voices and predicts spoken length; `python3 tools/voices.py` lists them.
- `tools/youtube.py`: lists recent unused videos from the profile's YouTube favorites and saves a video's transcript, for the deep dive every other session.
- `workouts/`: deliverables. `workouts/drafts/` holds `@@`-marked drafts, `workouts/research/` holds filler fact sheets (`videos/` holds transcripts and video deep-dive sheets), and `workouts/.audio-cache/` holds rendered clips and each voice's measured pace (safe to delete).

## Audio
`tools/render.py` runs OmniVoice in-process with VoiceStudio's bundled Python (`~/Library/Application Support/VoiceStudio/runtime/project/.venv`). The VoiceStudio app and server are not needed, and the app's settings don't affect renders; only its saved voices do. Any voice saved in the app can be used by name or profile id; the default is the first under Voices in profile.md. On this M3, at the default twelve decoding steps, it renders at about 0.7 times the length of the speech after a load of about five seconds. Don't run the VoiceStudio app during a render (16 GB of memory, a 3 GB model).
