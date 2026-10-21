# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news, science and stories, and renders it to an MP3 in a natural coach's voice on your own Mac. The audio is the timer: every segment starts on the clock.

Current version: see `VERSION` and `CHANGELOG.md`.

## Get started

You need an Apple Silicon Mac, [Claude Code](https://claude.com/claude-code), and Homebrew.

1. **Fork** this repo (a fork keeps the link to upstream, so you can pull improvements), clone it, and open the folder in Claude Code.
2. **Install the two tools** setup needs: `brew install ffmpeg uv`.
3. **Run `tools/setup.sh`.** It builds the project's Python environment from `uv.lock` (about 430 MB; uv fetches Python 3.11 itself), copies `me.example/` to `me/`, installs a git hook that refuses to push `me/`, and downloads the default voice's model (about 3 GB for Coach E; `--all` for every voice).
4. **Say "set me up"** in Claude Code. The `setup` skill interviews you (neighborhood, equipment, injuries, interests and teams, voice, where MP3s should go), fills in `me/`, checks your feeds, and renders a one-minute smoke test, which also measures the voice's pace.
5. **Ask for a workout**: "I'd like a workout", "25 minutes at the hotel, just go".

## How it's organized

Three layers, so your own details never mix with the code:

| Layer | Where | In git? |
|---|---|---|
| **Engine**: tools, skills, tests, shared knowledge (text-to-speech rules, injury playbook, equipment library, exercise science) | `tools/`, `.claude/`, `tests/`, `knowledge/` | Yes, public |
| **Voices**: each voice's ten-second reference clip, transcript and settings, with the model pinned to an exact revision | `voices/` | Yes, about 1 MB. Model weights download to `~/.cache/huggingface/hub` |
| **You**: profile, health, workout log and feedback, drafts, research, rendered MP3s, private voices | `me/` (or wherever `SWEATCAST_HOME` points) | No: ignored, and the pre-push hook and CI block it |

Pulling upstream changes never touches `me/`, so merges stay clean. To back up your context and keep its history, make `me/` its own private repo: `cd me && git init && git add -A && git commit -m "My sweatcast context"`, then push it to a private remote.

## How a session works

1. The `workout` skill (`.claude/skills/workout/SKILL.md`) asks only for what you didn't say: how each injury feels, length, kit, how the last session went.
2. `tools/feeds.py` pulls your teams' results and schedules, the weather, recent local, science and tech headlines, and the week's podcasts and puzzles from the feeds in your profile, in about a second. Background agents research the rest while you answer: two current science and technology breakthroughs, on this day, and a deep dive that alternates between a news story and a video from your favorite YouTube channels. A long video becomes a series, one part per session. The quiz uses a puzzle that works by ear when one turns up (The Fiddler, NPR's Sunday Puzzle, MindYourDecisions).
3. Claude plans a whole-body session around your injuries, progressing from the loads it logged last time, then writes a segmented draft (`@@ <seconds> | <label>` before each segment) in short paragraphs, and starts rendering the first half while it writes the rest.
4. `tools/build.sh` lints the draft for text-to-speech problems, predicts each segment's spoken length for the chosen voice, exports a clean `.txt`, renders a loudness-normalized `.mp3` into `me/workouts/`, and copies it to the folder your profile names (iCloud Drive, Google Drive, Dropbox: anything that syncs to your phone).

Each paragraph is voiced by cloning the voice's reference clip with Chatterbox Turbo or Qwen3-TTS through [mlx-audio](https://github.com/Blaizzy/mlx-audio). A soft chime marks the start of each segment and each change inside an interval, and a rising three-note tone marks the end. Spare seconds in a segment widen its paragraph breaks a little, then the segment ends early rather than going quiet; a segment that runs slightly long is paid back from the next ones' spare time. The whole workout lands within three percent of plan. With the default voice, a 30-minute workout renders in under 20 minutes in the background, and edits re-render only the clips that changed.

## Layout

| Path | What |
|---|---|
| `CLAUDE.md` | Project instructions for Claude, including the release process |
| `.claude/skills/` | `workout` (request to MP3) and `setup` (onboarding and profile changes) |
| `knowledge/` | Shared references: text-to-speech rules, injury playbook, equipment library, exercise science, how voices work |
| `voices/` | Shipped voices (clip, transcript, engine, model and revision) and the smoke-test draft |
| `me.example/` | The template for your context folder |
| `me/` | Your context (git-ignored) |
| `tools/setup.sh` | One-time setup: environment, `me/`, privacy hook, models |
| `tools/build.sh` | Draft to `.txt` and `.mp3` in one step, then the copy to your phone's folder |
| `tools/tts_build.py` | Draft linter (predicted spoken seconds per segment, paragraph length, coaching structure) and `.txt` exporter |
| `tools/render.py` | Renderer with clip cache, timing and loudness normalization |
| `tools/voices.py` | Voice lookup, spoken-length prediction and model download; run it to list voices |
| `tools/char_weight.py` | OmniVoice's character-weight rule (Apache 2.0), vendored for the prediction |
| `tools/feeds.py` | Fetches your feeds (results, schedules, weather, headlines, weekly podcasts and puzzles) into a dated sheet |
| `tools/youtube.py` | Picks a recent video from your favorite channels or continues a series, lists unused puzzles, saves a transcript |
| `tools/coverage.py` | Reads your log and lists the muscle groups the last session left out, its format and the last loads |
| `tools/paths.py` | Where everything lives; `SWEATCAST_HOME` moves your context folder |
| `tools/hooks/pre-push` | Refuses to push personal context |
| `tests/` | Fast checks with no models, network or personal files (`python3 -m unittest discover tests`), run by CI on every push |
| `pyproject.toml`, `uv.lock` | The pinned Python environment |
| `docs/research/` | Design notes |
| `VERSION`, `CHANGELOG.md` | Release number and history |

## Health and safety

sweatcast is not medical advice. It programs conservatively around injuries you describe, using a general playbook, and anything a doctor or physical therapist has told you overrides it: write it in `me/health.md` and it's followed literally. Every session has a stop rule (sharp pain, new swelling, numbness or giving way means stop that movement), and red flags such as not being able to bear weight stop the session and suggest a clinician.

## Voices and consent

The two shipped coach voices are synthetic: Qwen3-TTS VoiceDesign made them from a written description, not from a recording of anyone. If you clone a real voice, use your own or one whose owner has agreed, and keep it in `me/voices/`, which stays private.

## Versioning

sweatcast follows [Semantic Versioning](https://semver.org). Each release is tagged `vX.Y.Z` and published on the GitHub releases page; `CHANGELOG.md` says what changed, and a major release's "For forks" note says what to do after pulling it.

## License

MIT, see [LICENSE](LICENSE). `tools/char_weight.py` is vendored from [OmniVoice](https://github.com/k2-fsa/OmniVoice) under the Apache License 2.0, with its header kept. The voice models are downloaded, not distributed here: Chatterbox Turbo ([ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo), MIT; MLX build [mlx-community/chatterbox-turbo-fp16](https://huggingface.co/mlx-community/chatterbox-turbo-fp16), Apache 2.0) and Qwen3-TTS ([Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base), Apache 2.0; MLX build [mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16)).
