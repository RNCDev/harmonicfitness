# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news, science and stories, and renders it to an MP3 in a natural coach's voice on your own Mac or Windows PC. The audio is the timer: every segment starts on the clock.

Current version: see `VERSION` and `CHANGELOG.md`.

## Get started

You need [Claude Code](https://claude.com/claude-code) and either an Apple Silicon Mac with Homebrew, or a Windows PC with an NVIDIA GPU (RTX 20 series or later, 8 GB) and Git for Windows, whose Git Bash runs `./sweatcast`. On Windows only the Chatterbox voices render so far; everything else works the same.

1. **Install the two tools** sweatcast needs: on a Mac, `brew install ffmpeg uv`; on Windows, `winget install Gyan.FFmpeg.Essentials astral-sh.uv`.
2. **Fork** this repo (a fork keeps the link to upstream, so you can pull improvements), clone it, and open the folder in Claude Code.
3. **Say "set me up".** The `setup` skill runs `./sweatcast setup` for you (the project's Python environment, about 430 MB; `me/` from `me.example/`; a git hook that refuses to push `me/`), interviews you (neighborhood, equipment, injuries, interests and teams, voice, where MP3s should go), fills in `me/`, checks your feeds, downloads your voice's model (see Voice models below) and renders a one-minute smoke test, which also measures the voice's pace. It can design you a voice of your own, too.
4. **Ask for a workout**: "I'd like a workout", "25 minutes at the hotel, just go".

Setup takes 30 to 60 minutes, mostly downloads.

## Commands

Claude Code runs these for you, but they work on their own too. `./sweatcast help` lists them all:

| Command | What it does |
|---|---|
| `./sweatcast setup` | First-run setup; safe to rerun (it also migrates `me/` after a major upgrade) |
| `./sweatcast check` | Checks `me/`: anything still to fill in, or that the tools can't read |
| `./sweatcast build <draft> "<name>"` | Lints a draft, renders the MP3, copies it to your phone's folder (`--lint-only` to just lint) |
| `./sweatcast voices` | Lists voices; `design` and `keep` make a new one from a description |
| `./sweatcast brief --goal strength --minutes 30 --preset hotel-room` | Today's ingredients: you, the week, your limits, the safe menu of movements (with coaching notes) your kit, level and `me/health.md` allow, the programming guide and equipment notes; `--save <draft>` writes the menu the build checks |
| `./sweatcast movements --preset hotel-room` | Browses the movements a kit allows, by movement pattern; it applies no health limits, so plans come from `./sweatcast brief`; `--about <ids>` prints a movement's coaching notes |
| `./sweatcast feeds`, `coverage`, `youtube`, `log-session` | What the workout skill uses to research, plan and log |
| `./sweatcast backup` | Commits `me/` and pushes it to its own private repo (the workout skill runs it after each session) |
| `./sweatcast migrate`, `cache prune`, `test` | Upkeep |

## How it's organized

Three layers, so your own details never mix with the code:

| Layer | Where | In git? |
|---|---|---|
| **Engine**: the command, tools, skills, tests and shared knowledge (the movement catalog, session methods and doses, programming and injury references, text-to-speech rules) | `sweatcast`, `tools/`, `.claude/`, `tests/`, `knowledge/` | Yes, public |
| **Voices**: each voice's ten-second reference clip, transcript and settings, with the model pinned to an exact revision | `voices/` | Yes, about 1 MB; model weights download to `~/.cache/huggingface/hub` |
| **You**: profile, health, workout log and feedback, drafts, research, rendered MP3s, private voices and movements | `me/` (or wherever `SWEATCAST_HOME` points) | No: ignored, and the pre-push hook and CI block it |

Pulling upstream changes never touches `me/`, so merges stay clean. When a release changes a context file's format, `./sweatcast migrate` (or rerunning `./sweatcast setup`) brings `me/` up to date, backing up the originals first. Your settings (voices, delivery folder, kits, feeds, YouTube channels) sit in a TOML block at the top of `me/profile.md`; everything below it is free-form prose for Claude.

### Back up `me/`

Keep `me/` as its own private git repo, inside the engine's folder but separate from it: the engine's git ignores `me/`, and `me/` has its own history and remote. Then the workout skill's last step, `./sweatcast backup`, commits the session and pushes it, and another machine gets your profile and log by cloning it into `me/`. Not a submodule, which would record your private repo in the public one.

```
cd me && git init && gh repo create sweatcast-me --private --source . --push
```

`me/.gitignore` (from `me.example/`, and added by rerunning `./sweatcast setup`) leaves out the rendered clips, MP3s and render logs, and keeps the voices' measured pace. `./sweatcast backup` does nothing when `me/` isn't its own repo, and refuses to push to a repo GitHub reports as public.

| Folder | What |
|---|---|
| `.claude/skills/` | `workout` (request to MP3) and `setup` (onboarding and profile changes) |
| `knowledge/` | The movement catalog (`movements.toml`), session methods and doses (`sessions.toml`), programming, the injury playbook, equipment kits, what goes in a script, text-to-speech rules, how voices work |
| `tools/` | One Python or shell file per job, all run through `./sweatcast`; `CLAUDE.md` lists what each does |
| `voices/`, `me.example/` | The shipped voices and the smoke-test draft; the template for `me/` |
| `tests/` | Fast checks with no models, network or personal files (`./sweatcast test`), run by CI on every push |
| `docs/eval/` | The judged grid behind each release's quality (forty cases and extras), with each run's results |
| `docs/research/` | The research notes the session rules cite |

## Voices

Two voices ship, each named for the model that speaks it; a voice is a ten-second reference clip the model copies for every line:

| Voice | Model | Sound | Download | Render speed (M3) |
|---|---|---|---|---|
| Chatterbox Coach (default) | Chatterbox Turbo | Warm baritone, a trainer talking to one client; the most natural | About 3.3 GB | About 0.7 times real time |
| Qwen3 Coach | Qwen3-TTS | A focused class instructor; the clearest diction | About 4.2 GB | About 1.3 to 1.45 times |

`./sweatcast setup` downloads the default voice's model once (`--all` for both); no account is needed and rendering works offline afterwards. A voice of your own is a description away: `./sweatcast voices design "<name>" "<who they are and how they sound>"` renders takes (a 4.5 GB designer model), and `./sweatcast voices keep <take> --default` makes your pick a private voice. Or ask Claude Code to "design me a new coach voice". More in [knowledge/voices.md](knowledge/voices.md).

## How a session works

1. The `workout` skill asks only for what you didn't say: how each injury feels, length, kit, how the last session went.
2. `./sweatcast feeds` pulls your teams' results and schedules, the weather, recent local, science and tech headlines, and the week's podcasts and puzzles in about a second, while background agents research the rest: two current breakthroughs, on this day, and a deep dive that alternates between a news story and a video from your favorite YouTube channels (a long video becomes a series). The quiz uses a puzzle that works by ear.
3. `./sweatcast brief` gathers the ingredients: who you are and how the week has gone, today's limits with your clinician's rules, the safe menu (every movement your kit, level and injury limits allow, each with its coaching notes), and the programming guide for your goal and level. Claude designs the session from it (the format, the movements, their order, doses and timing), posts the plan, writes the script, and starts rendering the first half while it writes the rest.
4. `./sweatcast build` checks that every movement the draft declares or names is on today's menu, lints it for text-to-speech problems, predicts each segment's spoken length for the voice, renders a loudness-normalized MP3, and moves it to the folder your profile names (anything that syncs to your phone), keeping the script's text in `me/workouts/` as history.

A soft chime marks the start of each segment and each change inside an interval, and a rising three-note tone marks the end. A segment with spare seconds widens its paragraph breaks, then ends early rather than going quiet, unless it holds timed work: a `[hold]` keeps that segment its full length, silent where you work. The whole workout lands within three percent of plan. With the default voice, a 30-minute workout renders in under 20 minutes in the background, starting while the script is still being written (`--follow`), and edits re-render only the clips that changed.

## Health and safety

sweatcast is not medical advice. It programs conservatively around injuries you describe, using a general playbook, and anything a doctor or physical therapist has told you overrides it: write it in `me/health.md` and it's followed literally. Every session has a stop rule (sharp pain, new swelling, numbness or giving way means stop that movement), and red flags such as not being able to bear weight stop the session and suggest a clinician.

## Voices and consent

The two shipped coach voices are synthetic: Qwen3-TTS VoiceDesign made them from a written description, not from a recording of anyone. If you clone a real voice, use your own or one whose owner has agreed, and keep it in `me/voices/`, which stays private.

## Versioning

sweatcast follows [Semantic Versioning](https://semver.org). Each release is tagged `vX.Y.Z` and published on the GitHub releases page; `CHANGELOG.md` says what changed, and a release's "For forks" note says what to do after pulling it.

## License

MIT, see [LICENSE](LICENSE). `tools/char_weight.py` is vendored from [OmniVoice](https://github.com/k2-fsa/OmniVoice) under the Apache License 2.0, with its header kept. The voice models are downloaded, not distributed here: Chatterbox Turbo ([ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo), MIT, used as is on Windows through Resemble's `chatterbox-tts`; MLX build [mlx-community/chatterbox-turbo-fp16](https://huggingface.co/mlx-community/chatterbox-turbo-fp16), Apache 2.0) and Qwen3-TTS ([Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base), Apache 2.0; MLX build [mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16)).
