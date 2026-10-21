# sweatcast: a workout podcast, made fresh each session

sweatcast turns a request for a workout into a narrated MP3 for earbuds, with no screen and no timer. The audio is the workout: it tells the listener what to do, keeps them company, and moves them along on time. The lint predicts each segment's spoken length for the chosen voice, and the render lays segments on the plan's clock: a segment with time to spare breathes a little between paragraphs, then ends early rather than going quiet. Only the total is held to plan, within three percent either way; a natural, human voice matters more than exact timing.

Priorities, in order: safe for the listener's body today, clean to the ear, worth listening to.

**Any request for a workout, in any words, runs the `workout` skill** (`.claude/skills/workout/SKILL.md`). It covers check-in, plan, research, script, build and log. **A request to get started, "set me up", or to change the listener's profile, injuries, feeds, voice or delivery runs the `setup` skill** (`.claude/skills/setup/SKILL.md`), and so does a workout request when `me/profile.md` doesn't exist yet.

## Three layers

1. **Engine** (this repo, public, versioned): `tools/`, `.claude/skills/`, `tests/`, and the shared knowledge in `knowledge/`.
2. **Voices** (public, small): `voices/` holds each shipped voice's reference clip, transcript and settings, including the Hugging Face model and the revision it's pinned to. Model weights never go in git; `tools/setup.sh` downloads them.
3. **The listener's context** (private): `me/`, ignored by git, holds everything about one person. `me.example/` is its template. Set `SWEATCAST_HOME` to keep it elsewhere; every tool reads its paths from `tools/paths.py`.

During a session, write only inside `me/`. Never put personal details (health, location, the log, drafts) in the engine, its tests or its examples; the pre-push hook in `tools/hooks/` and CI both refuse them.

## Files
- `me/profile.md`: stable facts about the listener (setup, voices, delivery folder, equipment kits, interests, feeds, tone). Update it when something lasting changes.
- `me/health.md`: injuries and limitations, with the standing rules and phase for each. The check-in updates the phase.
- `me/log.md`: session log and the listener's feedback. Feedback given at any time ("too long", "loved that topic") goes here.
- `me/exercise-science.md`: facts verified during this listener's sessions, in the shared file's format.
- `me/workouts/`: deliverables. `drafts/` holds `@@`-marked drafts, `research/` holds filler fact sheets (`videos/` the video deep-dive sheets and transcripts, `puzzles/` the quiz puzzles used), and `.audio-cache/` holds rendered clips and each voice's measured pace (`voice-pace.json`; delete the clips freely, but the pace file saves re-measuring).
- `me/voices/`: private voices, looked in before `voices/`.
- `knowledge/tts-rules.md`: how to write for text-to-speech.
- `knowledge/voices.md`: how voices work, the engines, how the coach voices were made, and how to add one.
- `knowledge/injury-playbook.md`, `knowledge/equipment-library.md`: programming references. Where they disagree with `me/health.md`, the strictest wins, and anything health.md bans is out.
- `knowledge/exercise-science.md`: shared verified facts per movement, for the occasional one-line aside behind a form cue. Sessions add to `me/exercise-science.md`, not this file.
- `voices/`: the shipped voices, plus `smoke-test.draft.txt`, a one-minute check that also measures a new voice's pace.
- `tools/setup.sh`: one-time setup, safe to rerun: the Python environment (`uv sync` into `.venv`), `me/` from `me.example/`, the pre-push hook, and the default voice's model (`--all` for every voice).
- `tools/build.sh`: draft to `.txt` and `.mp3` in one step (lint with `tools/tts_build.py`, then render with `tools/render.py`), then a copy of the MP3 to the profile's "Copy finished MP3s to:" folder. `--clips-only` renders ahead while a draft is still being written. Exit 2 means the total ran more than three percent off plan; exit 3 means the voice hasn't been measured yet.
- `tools/voices.py`: lists voices with their engine, measured pace and model, and downloads a voice's pinned model. `tools/char_weight.py` is OmniVoice's character-weight rule (Apache 2.0), vendored; every measured pace is counted in it.
- `tools/coverage.py`: reads `me/log.md` and lists the muscle groups the last session left out, the movements to avoid, the last format and each movement's last load, for the plan.
- `tools/feeds.py`: fetches the profile's Feeds (team results and schedules, weather, local and science headlines, weekly podcasts and puzzles, on this day) into `me/workouts/research/<date>-feeds.md`, which research reads before it searches.
- `tools/youtube.py`: lists recent unused videos from the profile's YouTube favorites and any series in progress, saves a video's transcript, and marks a series part as told, for the deep dive every other session; `puzzles` lists recent unused puzzle videos for the quiz.
- `tools/paths.py`: where everything lives (the engine, and the context folder from `SWEATCAST_HOME` or `me/`).
- `tests/`: fast checks for the lint, the timing layout, voices, the log, the feed parsers, the YouTube series, and a fresh copy running on `me.example/`, with no models, network or personal files (fixtures in `tests/fixtures/`). Run `python3 -m unittest discover tests` after changing a tool; CI runs them on every push.
- `pyproject.toml`, `uv.lock`, `.python-version`: the pinned Python environment.
- `docs/research/`: design notes, such as the productization research behind this layout.
- `VERSION`, `CHANGELOG.md`: the release number and what changed in each release.

A codegraph index (`.codegraph/`, git-ignored) is available for semantic code search through the codegraph MCP tool; after moving or renaming files, run `codegraph init` again to refresh it.

## Audio
`tools/render.py` voices each paragraph by cloning the voice's reference clip, with Chatterbox Turbo or Qwen3-TTS through `mlx-audio`, in the project's own environment (`.venv`, Python 3.11, pinned by `uv.lock`; no other app needed). `tools/build.sh` uses `.venv/bin/python`, or `SWEATCAST_PYTHON` if set. The `python3 tools/...` commands the skills run are standard-library only, except `youtube.py`, which reruns itself in `.venv` for yt-dlp. The default voice is the first under Voices in `me/profile.md`. On an M3 with 16 GB, Chatterbox Turbo renders at about 0.7 times the length of the speech and Qwen3 at about 1.3 to 1.45, so a 30-minute workout takes under 20 minutes with Chatterbox Coach. Turbo's decoding keeps the GPU busy, so two renders at once barely beat one and may not fit in memory; render ahead with `--clips-only` instead. Model weights live in `~/.cache/huggingface/hub` (about 3.3 GB for Chatterbox Coach, 4.2 GB for Qwen3 Coach), downloaded by `tools/setup.sh` at pinned revisions; keep only the ones a voice in use needs. The voices are named for the model that speaks them; a voice is a reference clip, not a tuned model (`knowledge/voices.md`).

## Releases
Versions follow Semantic Versioning, tracked in `VERSION` (and `pyproject.toml`) and `CHANGELOG.md`, and tagged `vX.Y.Z` on GitHub (RNCDev/sweatcast).
- Major: a change that breaks how existing drafts, voices, commands or the `me/` layout work, so something has to be migrated. Its CHANGELOG section says how, under "For forks".
- Minor: a new capability, such as an engine, a voice, a skill step or a tool option.
- Patch: fixes, tuning and doc corrections.

Listener content (sessions, research sheets, log entries) lives in `me/` and is never part of the engine's git. When a set of tool, skill or doc changes is finished and working, release it: add a dated section to `CHANGELOG.md`, bump `VERSION` and `pyproject.toml`, commit, tag (`git tag -a vX.Y.Z -m "..."`), push with tags, and publish a GitHub release (`gh release create vX.Y.Z --notes-file <that changelog section>`). Ask before pushing if it's unclear whether the work is done.
