# sweatcast

Your own workout podcast, made fresh each session. Ask Claude Code for a workout, and sweatcast checks in on how you feel, builds a plan around your injuries and equipment, writes a narrated script with real news, science and stories, and turns it into an MP3 for your earbuds in a natural coach's voice. The audio is the timer: no screen, every segment starts on the clock.

## Start here

**The easy way: ask Claude.** You need [Claude Code](https://claude.com/claude-code) on your own computer, which comes with a paid Claude plan (Pro is fine). The simplest is the **Code** tab of the [Claude desktop app](https://claude.com/download):

1. Open the Claude desktop app and click **Code**. It asks for a folder to work in: pick your home folder (the one with your name).
2. Say: **Can you use https://github.com/RNCDev/sweatcast and set me up?** Click **Allow** when Claude asks to run something.
3. Claude downloads sweatcast into a new `sweatcast` folder in your home folder, then asks you to start a **new** Code session in that folder. Do that (New session, then choose the `sweatcast` folder) and say **set up sweatcast**.

From there it's a few minutes: four questions (your name, your experience, your equipment, any injuries), a short test clip of your stand-in coach, then a ten-minute workout. In a terminal or an IDE (VS Code, Cursor, JetBrains) it's the same: clone the repo (below), open the folder in Claude Code, and say "set up sweatcast".

**What you need:**
- **Claude Code on your own computer** (Mac, Windows or Linux). Nothing else to install by hand: Claude sets up the rest (Python, the audio tools), asking first where it matters.
- **A voice.** On an Apple Silicon Mac, or a Windows or Linux PC with an NVIDIA card, the coach's voice can be made on your own computer, free and private, after a one-time 3 to 4 GB download. On any computer, a web coach speaks through a voice service with a key of your own, pay-as-you-go with no subscription; Claude recommends Fish Audio (about $0.30 a workout, no minimum) and walks you through getting the key. Claude checks your computer first and tells you which applies.
- **About 5 GB of free disk** for a voice on your computer (well under 1 GB for a web coach).
- **No GitHub account, no programming.** A GitHub account is only for keeping a private backup of your profile.

**After setup,** ask for a workout any time, in your own words: "I'd like a workout", "25 minutes at the hotel, just go". Claude checks in on how you feel, writes the session, makes the MP3 and puts it in a folder that syncs to your phone (iCloud Drive, Google Drive or Dropbox; setup asks which after your first workout). Two more things to say when you're ready:
- **"Finish setting me up"**: your teams, interests and favorite shows, which the workout's stories come from.
- **"I want a new coach"**: a coach of your own, with a name and a voice you pick by ear from an audition, in a few minutes.

**Doing it yourself instead:** download this repo (`git clone https://github.com/RNCDev/sweatcast.git`, or **Code > Download ZIP** on GitHub), put the folder somewhere that isn't synced to the cloud (your home folder is good), open it in Claude Code, and say "set up sweatcast".

## Send this to a friend

Paste this to someone who has the Claude desktop app and a paid plan:

> Want a workout podcast made just for you? Open the Claude desktop app, click **Code**, and pick your home folder when it asks for one. Then paste: *Can you use https://github.com/RNCDev/sweatcast and set me up?* Click **Allow** when it asks to run things. When Claude tells you to, start a new Code session in the new **sweatcast** folder and say *set up sweatcast*. Ten minutes later you'll have your first workout to listen to.

## Where it runs

| Where | Works? |
|---|---|
| Claude Code on your own computer: the Code tab of the Claude desktop app, a terminal, or an IDE | Yes, with a voice made on your computer or a web coach |
| Claude Code on the web (claude.ai/code) | Not for setting up: use your own computer |
| The plain Claude chat (claude.ai, or the chat in the desktop app) | No: it can't run sweatcast's commands. Use Claude Code |

## For Claude: setting someone up from this link

If someone asks you to use this repository and set them up, and your session isn't already open in a copy of it:

1. **You need to run commands on their own computer.** In a plain chat with no shell, or on Claude Code on the web (`CLAUDE_CODE_REMOTE=true`), say that sweatcast runs in Claude Code on their own computer: the **Code** tab of the Claude desktop app (https://claude.com/download), where they pick their home folder and ask again. Then stop.
2. **Pick the folder:** `~/sweatcast` (on Windows, the home folder in Git Bash, the same path). Never inside iCloud Drive, Dropbox, OneDrive, Google Drive or a synced Documents folder: the voice model and Python environment are several gigabytes. If `~/sweatcast` already holds sweatcast, use it (`git -C ~/sweatcast pull` if it's a checkout).
3. **Download it, no account needed.** With git (`command -v git`; on a Mac, `xcode-select -p` too, since a bare `git` there can open an installer): `git clone https://github.com/RNCDev/sweatcast.git ~/sweatcast`. Without git, the ZIP: download `https://github.com/RNCDev/sweatcast/archive/refs/heads/main.zip`, unzip it, and move the `sweatcast-main` folder to `~/sweatcast`. A ZIP copy works fully; only the privacy hook, which needs git, is skipped.
4. **Hand over to a session in that folder.** Ask them to open `~/sweatcast` in Claude Code and say "set up sweatcast", in literal steps: in the desktop app, "click **New session** in the Code tab, choose the **sweatcast** folder in your home folder, and type *set up sweatcast*"; in an IDE, open the `sweatcast` folder and start Claude Code there; in a terminal, `cd ~/sweatcast && claude`. Say why in a line: sweatcast's own instructions and safety settings (among them the rule that keeps API keys out of the chat) load only in a session opened there. Don't run setup from the session you're in.

Current version: see `VERSION` and `CHANGELOG.md`.

# How it works

## Setup, step by step

What "set up sweatcast" does, so nothing is a surprise:

1. **The readiness check** (`./sweatcast doctor`): your system, memory, disk and graphics, what's installed, and whether local voices work here. Then Claude lays out the one big choice: a voice made on your computer (free and private, a one-time download, slower to render) or a web coach (no download, fast, pay-as-you-go), which way this computer starts, and how to switch or add the other later.
2. **The tools:** uv (which makes the project's Python environment, about 430 MB) is installed with Astral's official installer if it's missing, after Claude asks. ffmpeg comes with the environment if you don't have it, and git is optional: a zip download works, minus the hook that keeps your details out of a push.
3. **The quick start:** four questions (your name, experience, equipment, injuries), and how the audio is made where it isn't obvious (local, or a web coach with a key of your own: Claude recommends Fish Audio, gives you the links, and opens a file in your computer's text editor where you paste the key yourself, never into the chat). A stand-in is your coach, and you hear a short test clip of him first: Coach Andy on your computer's own voice (his clip ships with him), or the default web coach of the service you added a key for, whose voice Claude designs and saves in your account before the first workout (about a cent; Claude says so first), then plays you its clip. A ten-minute workout checks everything end to end, and Claude shows you where the MP3 is (`./sweatcast show` opens its folder), then asks which folder syncs to your phone, so later workouts land there on their own.
4. **Later, when you like:** "finish setting me up" asks about your interests, teams and taste, and finds feeds for them; "I want a new coach" makes a coach of your own in a few minutes (one question, then an audition of voices from every service you have a key for).

The quick start takes a few minutes, plus the voice model's download for a local voice (3 to 4 GB). To fork instead of clone, fork first (a fork keeps the link to upstream, so you can pull improvements).

## Commands

Claude Code runs these for you, but they work on their own too. `./sweatcast help` lists them all:

| Command | What it does |
|---|---|
| `./sweatcast doctor` | What this computer can do: system, prerequisites, whether local voices work, models, delivery folders (works before setup) |
| `./sweatcast setup` | First-run setup; safe to rerun (it also migrates `me/` after a major upgrade) |
| `./sweatcast check` | Checks `me/`: anything still to fill in, or that the tools can't read |
| `./sweatcast build <draft> "<name>"` | Lints a draft, renders the MP3, copies it to your phone's folder (`--lint-only` to just lint) |
| `./sweatcast coaches` | Your coaches and where each speaks; `audition` and `keep` make a web coach from a description, `archive` retires one; `design` and `keep` make a local coach's clip |
| `./sweatcast show <file>` | Opens the folder holding a file (a workout's MP3) with it selected |
| `./sweatcast keys`, `models` | Which voice services have a key set (never the key), `init` and `open` to add one; the local models in `models/`, and `adopt` for ones already downloaded |
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
| **You**: profile, health, workout log and feedback, your coaches, drafts, research, rendered MP3s, private movements, and voice service keys (`.env`, never backed up) | `me/` (or wherever `SWEATCAST_HOME` points) | No: ignored, and the pre-push hook and CI block it |

Pulling upstream changes never touches `me/`, so merges stay clean. When a release changes a context file's format, `./sweatcast migrate` (or rerunning `./sweatcast setup`) brings `me/` up to date, backing up the originals first. Your settings (audio routes, delivery folder, kits, feeds, YouTube channels) sit in a TOML block at the top of `me/profile.md`; everything below it is free-form prose for Claude.

### Back up `me/`

Without a GitHub account, `me/` simply stays on your computer, and everything works; to keep a copy, copy the `me` folder now and then to somewhere private (it holds your health notes). With one, a private repo backs it up after every workout:

Keep `me/` as its own private git repo, inside the engine's folder but separate from it: the engine's git ignores `me/`, and `me/` has its own history and remote. Then the workout skill's last step, `./sweatcast backup`, commits the session and pushes it, and another machine gets your profile and log by cloning it into `me/`. Not a submodule, which would record your private repo in the public one.

```
cd me && git init && gh repo create sweatcast-me --private --source . --push
```

`me/.gitignore` (from `me.example/`, and added by rerunning `./sweatcast setup`) leaves out `.env`, the rendered clips, MP3s and render logs, and keeps your coaches with their samples and measured pace (auditions in progress are left out). `./sweatcast backup` does nothing when `me/` isn't its own repo, and refuses to push to a repo GitHub reports as public.

| Folder | What |
|---|---|
| `.claude/skills/` | `workout` (request to MP3), `setup` (onboarding and profile changes) and `coach` (a new trainer) |
| `knowledge/` | The movement catalog (`movements.toml`), session methods and doses (`sessions.toml`), programming, the injury playbook, equipment kits, what goes in a script, text-to-speech rules, coaches and voices, the web voice services (`services.toml`), the smoke-test draft |
| `tools/` | One Python or shell file per job, all run through `./sweatcast`; `CLAUDE.md` lists what each does |
| `me.example/` | The template for `me/` |
| `tests/` | Fast checks with no models, network or personal files (`./sweatcast test`), run by CI on every push |
| `docs/eval/` | The judged grid behind each release's quality (forty cases and extras), with each run's results |
| `docs/research/` | The research notes the session rules cite |

## Coaches and voices

Stand-ins ship so you can start at once; make your own whenever you like, and keep several ("I want a new coach"). A coach is a person's name, how they talk, and how they sound, and each lives in `me/personas/<name>/`. There are two kinds:
- **A web coach:** an original voice a service designs from your description and saves in your own account there. You hear an audition of candidates from every service you have a key for, pick by ear, and name each one you keep; a workout then uses it by name, always on the service that made it. Four default web coaches ship, one per service, and each is designed the first time it's used.
- **A local coach:** a ten-second clip that your computer's own voice engine copies. Coach Andy is the local stand-in.

| Where the voice comes from | Engine or service | Cost | Notes |
|---|---|---|---|
| Local, Apple Silicon | Chatterbox Turbo or Qwen3-TTS through MLX | Free | About 0.7 times real time on an M3; a 3.3 to 4.2 GB model |
| Local, NVIDIA (Windows or Linux) | Chatterbox Turbo on CUDA | Free | About 0.5 times real time on an RTX 2080 Super; Linux not yet tried |
| Local, processor only | The same, on the processor | Free | Experimental and slow; the smoke test measures it |
| Fish Audio | A designed voice, saved as a private model | About $0.30 a workout | Prepaid credit, no minimum; about $0.01 a design |
| Gemini | A designed voice | About $0.27 a workout until the end of 2026, about $0.54 from 2027 | A Google AI Studio key; its free tier uses requests for training |
| Inworld | A designed voice, published in your workspace | About $0.50 a workout | On-Demand plan, prepaid credit |
| ElevenLabs | A designed voice, saved in your account | About $1.60 a workout ($0.80 on the faster model) | Free keeps 3 voices and a small monthly allowance; not yet tried on a Free account; the key needs Text to Speech and Voices: write |

No subscription anywhere. Prices are approximate and change. A web build says what it will send and cost before sending, stops above a ceiling you set, and sends only the final script; the script can mention your injuries, so setup says so first. More in [knowledge/voices.md](knowledge/voices.md).

## How a session works

1. The `workout` skill asks only for what you didn't say: how each injury feels, how you're coming in today, the goal, length and kit.
2. `./sweatcast content plan` says what the rests will carry: quick items from today, current science, a deep dive (alternating between a news story and a video from your favorite YouTube channels; a long video becomes a series), a quiz that works by ear, something to enjoy in the spirit of your favorites, and something to learn. Each slot rotates through your interests, the one told longest ago first, and nothing told in the last month is told again. Background agents research today's items from `./sweatcast feeds` (your teams, the weather, local, science, TV, books, music and food headlines, podcasts, puzzles and Wikipedia's day), while evergreen pieces come from a reserve stocked ahead of time.
3. `./sweatcast brief` gathers the ingredients: who you are and how the week has gone, today's limits with your clinician's rules, the safe menu (every movement your kit, level and injury limits allow, each with its coaching notes), and the programming guide for your goal and level. Claude designs the session from it (the format, the movements, their order, doses and timing), posts the plan, writes the coaching while research finishes, and renders each paragraph as it's written (for a local coach; a web coach renders once, at the end).
4. `./sweatcast build` checks that every movement the draft declares or names is on today's menu, lints it for text-to-speech problems, predicts each segment's spoken length for the voice, renders a loudness-normalized MP3, and moves it to the folder your profile names (anything that syncs to your phone), keeping the script's text in the workout's own folder in `me/workouts/` as history.

A soft chime marks the start of each segment and each change inside an interval, and a rising three-note tone marks the end. A segment with spare seconds widens its paragraph breaks, then ends early rather than going quiet, unless it holds timed work: a `[hold]` keeps that segment its full length, silent where you work. The whole workout lands within three percent of plan. With a local coach on an Apple Silicon Mac, a 30-minute workout renders in under 20 minutes in the background, starting while the script is still being written (`--follow`), and edits re-render only the clips that changed.

## Health and safety

sweatcast is not medical advice. It programs conservatively around injuries you describe, using a general playbook, and anything a doctor or physical therapist has told you overrides it: write it in `me/health.md` and it's followed literally. Every session has a stop rule (sharp pain, new swelling, numbness or giving way means stop that movement), and red flags such as not being able to bear weight stop the session and suggest a clinician.

## Coaches and consent

A web coach is always designed, never copied: a service made the voice from a written description, not from anyone's recording, and sweatcast never offers voices that imitate real people or characters. A local coach's clip is designed the same way, or one you bring: if you bring a clip of a real person, use your own voice or one whose owner has agreed; it stays in `me/`, which is private, and is used only by your computer's own engine.

## Versioning

sweatcast follows [Semantic Versioning](https://semver.org). Each release is tagged `vX.Y.Z` and published on the GitHub releases page; `CHANGELOG.md` says what changed, and a release's "For forks" note says what to do after pulling it.

## License

MIT, see [LICENSE](LICENSE). `tools/char_weight.py` is vendored from [OmniVoice](https://github.com/k2-fsa/OmniVoice) under the Apache License 2.0, with its header kept. The voice models are downloaded, not distributed here: Chatterbox Turbo ([ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo), MIT, used as is on Windows through Resemble's `chatterbox-tts`; MLX build [mlx-community/chatterbox-turbo-fp16](https://huggingface.co/mlx-community/chatterbox-turbo-fp16), Apache 2.0) and Qwen3-TTS ([Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base), Apache 2.0; MLX build [mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16)).
