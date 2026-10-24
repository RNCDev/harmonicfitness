# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news, science and stories, and turns it into an MP3 for your earbuds in a natural coach's voice. The audio is the timer: no screen, every segment starts on the clock.

All you need is [Claude Code](https://claude.com/claude-code) (in a terminal, an IDE or the desktop app) on your own computer; Claude handles the rest, and tells you up front what your computer can do. Audio renders on your own computer (fast on an Apple Silicon Mac or with an NVIDIA card, slower and experimental on the processor), or with a cloud voice using your own key (Fish Audio, ElevenLabs, Cartesia or Deepgram) on any computer, an Intel Mac included.

**To start:** clone or download this repo, open the folder in Claude Code, and say **"set up sweatcast"**. The quick start asks four questions (your name, experience, equipment and any injuries), starts you with Coach Demo, and plays you a ten-minute workout. Then ask for a workout any time: "I'd like a workout", "25 minutes at the hotel, just go". Say "finish setting me up" for your teams, interests and a folder that syncs to your phone, and "I want a new coach" for a coach of your own.

## Where it runs

| Where | Works? |
|---|---|
| Claude Code on your own computer: in a terminal, an IDE, or the Code tab of the Claude desktop app | Yes, with a local voice or a cloud voice |
| Claude Code on the web | Yes, with a cloud voice only (your own key, set in the cloud environment's settings, and the service's host allowed in its network settings). Your profile is kept when you attach your private `sweatcast-me` repo to the session; without one, it's a one-time session with Coach Demo. The workout arrives as a page with a player |
| The plain Claude chat (claude.ai, or the chat in the desktop app) | No: it can't run sweatcast's commands |

Current version: see `VERSION` and `CHANGELOG.md`.

# How it works

## Setup, step by step

What "set up sweatcast" does, so nothing is a surprise:

1. **The readiness check** (`./sweatcast doctor`): your system, memory, disk and graphics, what's installed, and whether local voices work here. On Claude Code on the web it also says what to set there: the key, the network, and whether your profile is kept.
2. **The tools:** uv (which makes the project's Python environment, about 430 MB) is installed with Astral's official installer if it's missing, after Claude asks. ffmpeg comes with the environment if you don't have it, and git is optional: a zip download works, minus the hook that keeps your details out of a push.
3. **The quick start:** four questions (your name, experience, equipment, injuries), and how the audio is made where it isn't obvious (local, or a cloud voice with your key: you paste the key into `me/.env` yourself, never into the chat). Coach Demo, a stand-in coach measured already, is your coach, and a ten-minute workout checks everything end to end.
4. **Later, when you like:** "finish setting me up" asks about your interests, teams and taste, finds feeds for them, and sets the folder that syncs to your phone; "I want a new coach" makes a coach of your own in a minute or two (one question, one take).

The quick start takes a few minutes, plus the voice model's download for a local voice (3 to 4 GB). To fork instead of clone, fork first (a fork keeps the link to upstream, so you can pull improvements).

## Commands

Claude Code runs these for you, but they work on their own too. `./sweatcast help` lists them all:

| Command | What it does |
|---|---|
| `./sweatcast doctor` | What this computer can do: system, prerequisites, whether local voices work, models, delivery folders (works before setup) |
| `./sweatcast setup` | First-run setup; safe to rerun (it also migrates `me/` after a major upgrade) |
| `./sweatcast check` | Checks `me/`: anything still to fill in, or that the tools can't read |
| `./sweatcast build <draft> "<name>"` | Lints a draft, renders the MP3, copies it to your phone's folder (`--lint-only` to just lint) |
| `./sweatcast coaches` | Your coaches; `design` and `keep` make a new one from a description or a clip you bring |
| `./sweatcast keys`, `models` | Which cloud voices have a key set (never the key); the local models in `models/`, and `adopt` for ones already downloaded |
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
| **Models**: the local voice models, pinned to exact revisions | `models/` | No: downloaded by setup, about 3 to 4 GB |
| **You**: profile, health, workout log and feedback, your coaches, drafts, research, rendered MP3s, private movements, and cloud voice keys (`.env`, never backed up) | `me/` (or wherever `SWEATCAST_HOME` points) | No: ignored, and the pre-push hook and CI block it |

Pulling upstream changes never touches `me/`, so merges stay clean. When a release changes a context file's format, `./sweatcast migrate` (or rerunning `./sweatcast setup`) brings `me/` up to date, backing up the originals first. Your settings (audio routes, delivery folder, kits, feeds, YouTube channels) sit in a TOML block at the top of `me/profile.md`; everything below it is free-form prose for Claude.

### Back up `me/`

Keep `me/` as its own private git repo, inside the engine's folder but separate from it: the engine's git ignores `me/`, and `me/` has its own history and remote. Then the workout skill's last step, `./sweatcast backup`, commits the session and pushes it, and another machine gets your profile and log by cloning it into `me/`. Not a submodule, which would record your private repo in the public one.

```
cd me && git init && gh repo create sweatcast-me --private --source . --push
```

`me/.gitignore` (from `me.example/`, and added by rerunning `./sweatcast setup`) leaves out `.env`, the rendered clips, MP3s and render logs, and keeps your coaches with their measured pace. `./sweatcast backup` does nothing when `me/` isn't its own repo, and refuses to push to a repo GitHub reports as public.

| Folder | What |
|---|---|
| `.claude/skills/` | `workout` (request to MP3), `setup` (onboarding and profile changes) and `coach` (a new trainer) |
| `knowledge/` | The movement catalog (`movements.toml`), session methods and doses (`sessions.toml`), programming, the injury playbook, equipment kits, what goes in a script, text-to-speech rules, coaches and voices, the cloud services (`services.toml`), the smoke-test draft |
| `tools/` | One Python or shell file per job, all run through `./sweatcast`; `CLAUDE.md` lists what each does |
| `me.example/` | The template for `me/` |
| `tests/` | Fast checks with no models, network or personal files (`./sweatcast test`), run by CI on every push |
| `docs/eval/` | The judged grid behind each release's quality (forty cases and extras), with each run's results |
| `docs/research/` | The research notes the session rules cite |

## Coaches and voices

Coach Demo ships as a stand-in, so you can start at once; make your own whenever you like, and keep several ("I want a new coach"). A coach is a person's name, how they talk, and a ten-second clip that every engine copies, so the same coach sounds the same locally or in the cloud. Each lives in `me/personas/<name>/`.

| Route | Where | Cost | Notes |
|---|---|---|---|
| Local, Apple Silicon | Chatterbox Turbo or Qwen3-TTS through MLX | Free | About 0.7 times real time on an M3; a 3.3 to 4.2 GB model |
| Local, NVIDIA (Windows or Linux) | Chatterbox Turbo on CUDA | Free | About 0.5 times real time on an RTX 2080 Super; Linux not yet tried |
| Local, processor only | The same, on the processor | Free | Experimental and slow; the smoke test measures it |
| Fish Audio | Copies your coach's clip | About $0.30 a workout | |
| ElevenLabs | A clone of the clip | About $0.80 to $1.60 | Not yet tried live |
| Cartesia | A clone of the clip | About $1.00 | Not yet tried live |
| Deepgram Aura-2 | Stock voices only | About $0.60 | Not yet tried live |

Prices are approximate and change. A cloud build says what it will send and cost before sending, stops above a ceiling you set, and sends only the final script; the script can mention your injuries, so setup says so first. More in [knowledge/voices.md](knowledge/voices.md).

## How a session works

1. The `workout` skill asks only for what you didn't say: how each injury feels, how you're coming in today, the goal, length and kit.
2. `./sweatcast content plan` says what the rests will carry: quick items from today, current science, a deep dive (alternating between a news story and a video from your favorite YouTube channels; a long video becomes a series), a quiz that works by ear, something to enjoy in the spirit of your favorites, and something to learn. Each slot rotates through your interests, the one told longest ago first, and nothing told in the last month is told again. Background agents research today's items from `./sweatcast feeds` (your teams, the weather, local, science, TV, books, music and food headlines, podcasts, puzzles and Wikipedia's day), while evergreen pieces come from a pantry stocked ahead of time.
3. `./sweatcast brief` gathers the ingredients: who you are and how the week has gone, today's limits with your clinician's rules, the safe menu (every movement your kit, level and injury limits allow, each with its coaching notes), and the programming guide for your goal and level. Claude designs the session from it (the format, the movements, their order, doses and timing), posts the plan, writes the coaching while research finishes, and renders each paragraph as it's written (locally; a cloud voice renders once, at the end).
4. `./sweatcast build` checks that every movement the draft declares or names is on today's menu, lints it for text-to-speech problems, predicts each segment's spoken length for the voice, renders a loudness-normalized MP3, and moves it to the folder your profile names (anything that syncs to your phone), keeping the script's text in the workout's own folder in `me/workouts/` as history (on Claude Code on the web it makes a page with a player instead).

A soft chime marks the start of each segment and each change inside an interval, and a rising three-note tone marks the end. A segment with spare seconds widens its paragraph breaks, then ends early rather than going quiet, unless it holds timed work: a `[hold]` keeps that segment its full length, silent where you work. The whole workout lands within three percent of plan. With the default voice, a 30-minute workout renders in under 20 minutes in the background, starting while the script is still being written (`--follow`), and edits re-render only the clips that changed.

## Health and safety

sweatcast is not medical advice. It programs conservatively around injuries you describe, using a general playbook, and anything a doctor or physical therapist has told you overrides it: write it in `me/health.md` and it's followed literally. Every session has a stop rule (sharp pain, new swelling, numbness or giving way means stop that movement), and red flags such as not being able to bear weight stop the session and suggest a clinician.

## Coaches and consent

A designed coach is synthetic: a model made the voice from a written description, not from anyone's recording. If you bring a clip of a real person, use your own voice or one whose owner has agreed; it stays in `me/`, which is private. ElevenLabs asks whoever uploads a clip to hold the rights to the voice.

## Versioning

sweatcast follows [Semantic Versioning](https://semver.org). Each release is tagged `vX.Y.Z` and published on the GitHub releases page; `CHANGELOG.md` says what changed, and a release's "For forks" note says what to do after pulling it.

## License

MIT, see [LICENSE](LICENSE). `tools/char_weight.py` is vendored from [OmniVoice](https://github.com/k2-fsa/OmniVoice) under the Apache License 2.0, with its header kept. The voice models are downloaded, not distributed here: Chatterbox Turbo ([ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo), MIT, used as is on Windows through Resemble's `chatterbox-tts`; MLX build [mlx-community/chatterbox-turbo-fp16](https://huggingface.co/mlx-community/chatterbox-turbo-fp16), Apache 2.0) and Qwen3-TTS ([Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base), Apache 2.0; MLX build [mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16)).
