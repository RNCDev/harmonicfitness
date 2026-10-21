# Workout audio studio

I listen to narrated workouts through earbuds, with no screen and no timer. The audio is the workout: it tells me what to do, keeps me company, and moves me along on time. Every segment is padded to its planned seconds, and the lint predicts each segment's spoken length for the chosen voice, so a segment can't overrun or go quiet unnoticed. Within five percent of plan is fine; a natural, human voice matters more than exact timing.

Priorities, in order: safe for my body today, clean to the ear, worth listening to.

**Any request for a workout, in any words, runs the `workout` skill** (`.claude/skills/workout/SKILL.md`). It covers check-in, plan, research, script, build and log.

## Files
- `knowledge/profile.md`: stable facts about me (setup, voices, equipment kits, interests, standing rules for each injury). Update it when something lasting changes.
- `knowledge/tts-rules.md`: how to write for text-to-speech.
- `knowledge/voices.md`: how voices work, the engines, how the coach voices were made, and how to add one.
- `knowledge/injury-playbook.md`, `knowledge/equipment-library.md`: programming references. Where they disagree with the profile, the strictest wins, and anything the profile bans is out.
- `knowledge/exercise-science.md`: verified facts per movement, used for the occasional one-line aside behind a form cue.
- `voices/`: the voices (reference clip, transcript, engine settings).
- `log.md`: session log and my feedback. Feedback I give at any time ("too long", "loved that topic") goes here.
- `tools/build.sh`: draft to `.txt` and `.mp3` in one step (lint with `tools/tts_build.py`, then render with `tools/render.py`), then a copy of the MP3 to the Google Drive folder named in the profile. `python3 tools/voices.py` lists voices with their engine and measured pace.
- `tools/coverage.py`: reads `log.md` and lists the muscle groups the last session left out and the movements to avoid, for the plan.
- `tests/`: fast checks for the lint, the timing layout and the coverage script, with no models; run `python3 -m unittest discover tests` after changing a tool.
- `tools/youtube.py`: lists recent unused videos from the profile's YouTube favorites and saves a video's transcript, for the deep dive every other session.
- `workouts/`: deliverables. `drafts/` holds `@@`-marked drafts (`smoke-test.draft.txt` is a twenty-second check for a new voice), `research/` holds filler fact sheets (`videos/` holds transcripts and video deep-dive sheets), and `.audio-cache/` holds rendered clips and each voice's measured pace (safe to delete; the next render measures again).
- `VERSION`, `CHANGELOG.md`: the release number and what changed in each release.

## Audio
`tools/render.py` voices each paragraph by cloning the voice's reference clip from `voices/`, with Chatterbox Turbo or Qwen3-TTS through `mlx-audio` in VoiceStudio's bundled Python (`~/Library/Application Support/VoiceStudio/runtime/project/.venv`). The VoiceStudio app isn't needed and its settings don't affect renders; quit it during a render (16 GB of memory). The default voice is the first under Voices in profile.md. On this M3, Chatterbox Turbo renders at about 0.75 times the length of the speech and Qwen3 at about 1.3, so a 30-minute workout takes about 20 minutes with Coach E. Model weights live in `~/.cache/huggingface/hub`; keep only the ones a voice in `voices/` uses. Voices saved in the VoiceStudio app still render through OmniVoice, but none are in use.

## Releases
Versions follow Semantic Versioning, tracked in `VERSION` and `CHANGELOG.md` and tagged `vX.Y.Z` on GitHub (RNCDev/sweatcast).
- Major: a change that breaks how existing drafts, voices or commands work, so something has to be migrated.
- Minor: a new capability, such as an engine, a voice, a skill step or a tool option.
- Patch: fixes, tuning and doc corrections.

Workout sessions, research sheets and log entries are content, not releases: commit them freely without a version bump. When a set of tool, skill or doc changes is finished and working, release it: add a dated section to `CHANGELOG.md`, bump `VERSION`, commit, tag (`git tag -a vX.Y.Z -m "..."`), push with tags, and publish a GitHub release (`gh release create vX.Y.Z --notes-file <that changelog section>`). Ask before pushing if it's unclear whether the work is done.
