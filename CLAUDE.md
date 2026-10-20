# Workout audio studio

I listen to narrated workouts through earbuds, with no screen and no timer. The audio is the workout: it tells me what to do, keeps me company, and moves me along on time. Timing comes from word count, so word-count discipline matters.

Priorities, in order: safe for my body today, clean to the ear, worth listening to.

**Any request for a workout, in any words, runs the `workout` skill** (`.claude/skills/workout/SKILL.md`). It covers check-in, plan, research, script, build and log.

## Files
- `knowledge/profile.md`: stable facts about me (setup, voice and words per minute, equipment kits, interests, standing rules for each injury). Update it when something lasting changes.
- `knowledge/tts-rules.md`: how to write for text-to-speech.
- `knowledge/injury-playbook.md`, `knowledge/equipment-library.md`: programming references. Where they disagree with the profile, the strictest wins, and anything the profile bans is out.
- `log.md`: session log and my feedback. Feedback I give at any time ("too long", "loved that topic") goes here.
- `tools/build.sh`: draft to `.txt` and `.mp3` in one step (lint with `tools/tts_build.py`, then render with `tools/render.py`).
- `workouts/`: deliverables. `workouts/drafts/` holds `@@`-marked drafts, `workouts/research/` holds filler fact sheets, and `workouts/.audio-cache/` holds rendered paragraphs (safe to delete).
- `knowledge/original-project-instructions.md`: the original Claude.ai project instructions, for reference.

## Audio
`tools/render.py` runs OmniVoice in-process with VoiceStudio's bundled Python (`~/Library/Application Support/VoiceStudio/runtime/project/.venv`). The VoiceStudio app and server are not needed. Any voice saved in the VoiceStudio app can be used by its profile id. Set the default in profile.md under Listening setup. On this M3, with the default `balanced` quality, it renders at about 0.85 times real time after a load of about 10 seconds. Don't run the VoiceStudio app during a render (16 GB of memory, a 3 GB model).
