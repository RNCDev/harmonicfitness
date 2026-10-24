# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news, science and stories, and turns it into an MP3 for your earbuds in a natural coach's voice. The audio is the timer: no screen, every segment starts on the clock.

All you need is [Claude Code](https://claude.com/claude-code) (in a terminal, an IDE or the desktop app) on your own computer; Claude handles the rest, and tells you up front what your computer can do. The voices render on an Apple Silicon Mac, or on a Windows PC with an NVIDIA card.

**To start:** clone or download this repo, open the folder in Claude Code, and say **"set up sweatcast"**. Then ask for a workout: "I'd like a workout", "25 minutes at the hotel, just go".

Current version: see `VERSION` and `CHANGELOG.md`.

# How it works

## Setup, step by step

What "set up sweatcast" does, so nothing is a surprise:

1. **The readiness check** (`./sweatcast doctor`): your system, memory, disk and graphics, what's installed, and whether local voices work here. In a Claude Code cloud session it stops there: audio needs your own computer, and the cloud machine would forget your profile when the session ends.
2. **The tools:** uv (which makes the project's Python environment, about 430 MB) is installed with Astral's official installer if it's missing, after Claude asks. ffmpeg comes with the environment if you don't have it, and git is optional: a zip download works, minus the hook that keeps your details out of a push.
3. **The interview:** your name, equipment, injuries, interests and teams, voice, and where MP3s should go. Claude fills in `me/`, checks your feeds, downloads your voice's model (see Voices below) and renders a one-minute smoke test, which also measures the voice's pace. It can design you a voice of your own, too.

Setup takes 30 to 60 minutes, mostly downloads. To fork instead of clone, fork first (a fork keeps the link to upstream, so you can pull improvements).

## Commands

Claude Code runs these for you, but they work on their own too. `./sweatcast help` lists them all:

| Command | What it does |
|---|---|
| `./sweatcast doctor` | What this computer can do: system, prerequisites, whether local voices work, models, delivery folders (works before setup) |
| `./sweatcast setup` | First-run setup; safe to rerun (it also migrates `me/` after a major upgrade) |
| `./sweatcast check` | Checks `me/`: anything still to fill in, or that the tools can't read |
| `./sweatcast build <draft> "<name>"` | Lints a draft, renders the MP3, copies it to your phone's folder (`--lint-only` to just lint) |
| `./sweatcast voices` | Lists voices; `design` and `keep` make a new one from a description |
| `./sweatcast brief --goal strength --minutes 30 --preset hotel-room` | Today's ingredients: you, the week, your limits, the safe menu of movements (with coaching notes) your kit, level and `me/health.md` allow, the programming guide and equipment notes; `--save <draft>` writes the menu the build checks |
| `./sweatcast movements --preset hotel-room` | Browses the movements a kit allows, by movement pattern; it applies no health limits, so plans come from `./sweatcast brief`; `--about <ids>` prints a movement's coaching notes |
| `./sweatcast feeds`, `content`, `youtube`, `log-session` | What the workout skill uses to research, plan the filler and log |
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

1. The `workout` skill asks only for what you didn't say: how each injury feels, how you're coming in today, the goal, length and kit.
2. `./sweatcast content plan` says what the rests will carry: quick items from today, current science, a deep dive (alternating between a news story and a video from your favorite YouTube channels; a long video becomes a series), a quiz that works by ear, something to enjoy in the spirit of your favorites, and something to learn. Each slot rotates through your interests, the one told longest ago first, and nothing told in the last month is told again. Background agents research today's items from `./sweatcast feeds` (your teams, the weather, local, science, TV, books, music and food headlines, podcasts, puzzles and Wikipedia's day), while evergreen pieces come from a pantry stocked ahead of time.
3. `./sweatcast brief` gathers the ingredients: who you are and how the week has gone, today's limits with your clinician's rules, the safe menu (every movement your kit, level and injury limits allow, each with its coaching notes), and the programming guide for your goal and level. Claude designs the session from it (the format, the movements, their order, doses and timing), posts the plan, writes the coaching while research finishes, and renders each paragraph as it's written.
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
