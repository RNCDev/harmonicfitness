# sweatcast

Your own workout podcast, made fresh each session. Ask for a workout and sweatcast checks in on how you feel, plans around your equipment and any injuries, writes a narrated script with news, science and stories you care about, and turns it into an MP3 in a coach's voice. The audio is the workout: no screen, no timer, and the whole session lands within three percent of the length you asked for.

It runs inside an AI assistant that can work with files on your own computer: **Claude Code** (the Code tab of the Claude desktop app) or **ChatGPT's Codex** (Codex in the ChatGPT desktop app).

## Invite a friend

Copy and send:

> I've been using sweatcast, a workout podcast made fresh for me each time: it asks how I'm feeling, plans around my equipment and any injuries, and turns the session into an MP3 with a coach's voice and stories I care about. To try it, open the Claude desktop app (the **Code** tab; needs a paid plan) or the ChatGPT desktop app (**Codex**; any plan), open your home folder, and paste: *Can you use https://github.com/RNCDev/sweatcast and set me up?* It walks you through the rest.

## Start here

**With Claude** (a paid Claude plan; Pro is fine):
1. Open the [Claude desktop app](https://claude.com/download) and click **Code**. When it asks for a folder, pick your home folder (the one with your name).
2. Paste: **Can you use https://github.com/RNCDev/sweatcast and set me up?** Click **Allow** when it asks to run something.
3. Claude downloads sweatcast into a `sweatcast` folder in your home folder, then asks you to start a **new** Code session there: click New session, choose the `sweatcast` folder, and say **set up sweatcast**.

**With ChatGPT** (any plan, Free included):
1. Open the [ChatGPT desktop app](https://chatgpt.com/download), choose **Codex** at the top left, and open your home folder.
2. Paste: **Can you use https://github.com/RNCDev/sweatcast and set me up?** Approve it when it asks to run something.
3. Codex downloads sweatcast into a `sweatcast` folder, then asks you to open that folder in Codex. Do that (if it asks whether to trust the folder, say yes: that lets sweatcast's own commands run without a prompt each time) and say **set up sweatcast**.

**In a terminal or an editor** (VS Code, Cursor, JetBrains): `git clone https://github.com/RNCDev/sweatcast.git ~/sweatcast` (or GitHub's **Code > Download ZIP**), open the folder in Claude Code or Codex, and say "set up sweatcast". Keep the folder out of iCloud Drive, Dropbox and other synced folders: it grows to several gigabytes.

**Setup** asks four questions (your name, experience, equipment, injuries), plays a short test clip of your stand-in coach, and makes a ten-minute first workout. Once you've answered the questions you can step away: the assistant researches, writes and renders the workout on its own, then shows you where the MP3 is and asks which folder syncs to your phone (iCloud Drive, Google Drive or Dropbox), so later workouts land there.

**What you need:**
- **A Mac or a Windows PC.** Linux runs with Claude Code (the tests run there), though local voices there are not yet tried. On Windows, `./sweatcast` runs in Git Bash, which comes with [Git for Windows](https://git-scm.com/download/win); Claude Code needs it anyway. Codex has been tried end to end on a Mac, not yet on Windows.
- **A voice**, one of two kinds:
  - **On your own computer** (an Apple Silicon Mac, or a Windows or Linux PC with an NVIDIA card): free and private, after a one-time download of the voice engine and model (about 4 GB on a Mac, up to 8 GB on Windows or Linux). The readiness check wants at least 6 GB free.
  - **A web coach**, on any computer: a voice service with a pay-as-you-go key of your own, no subscription. The assistant suggests Fish Audio (about $0.30 a workout, no minimum) and walks you through getting the key.
- **No programming, and no GitHub account** (that's only for a private backup of your profile).
- **With ChatGPT,** turn off "Improve the model for everyone" (Settings, Data Controls) if you'd rather your health notes weren't used for training. Codex reminds you before the first workout.

**After setup,** ask for a workout any time, in your own words: "I'd like a workout", "25 minutes at the hotel, just go". Two more things to say when you're ready:
- **"Finish setting me up"**: your teams, interests and favorite shows, which the workout's stories come from.
- **"I want a new coach"**: a coach of your own, with a name and a voice you pick by ear from an audition of web voices (it needs at least one voice service key).

## Where it runs

| Where | Works? |
|---|---|
| Claude Code on your own computer: the Code tab of the Claude desktop app, a terminal or an editor | Yes |
| ChatGPT's Codex on your own computer: Codex in the ChatGPT desktop app, the Codex CLI or an editor | Yes (tried end to end with the Codex the ChatGPT app ships, on the Free plan's model; the app's own prompts not yet tried by hand) |
| Claude Code on the web (claude.ai/code) | Not for setting up. A listener already set up, with their private profile repo attached, can keep using web coaches there |
| A plain Claude or ChatGPT chat, or Codex cloud tasks | No: they can't run sweatcast's commands on your computer |

## For Claude (or ChatGPT's Codex): setting someone up from this link

If someone asks you to use this repository and set them up, and your session isn't already open in a copy of it:

1. **You need to run commands on their own computer.** In a plain chat, on Claude Code on the web (`CLAUDE_CODE_REMOTE=true`) or in a cloud task, say that sweatcast runs on their own computer, in the **Code** tab of the Claude desktop app (https://claude.com/download) or **Codex** in the ChatGPT desktop app (https://chatgpt.com/download), where they open their home folder and ask again. Then stop.
2. **Pick the folder:** `~/sweatcast` (on Windows, the same path in Git Bash). Never inside iCloud Drive, Dropbox, OneDrive, Google Drive or a synced Documents folder: the voice model and Python environment take several gigabytes. If `~/sweatcast` already holds sweatcast, use it (`git -C ~/sweatcast pull` if it's a checkout).
3. **Download it, no account needed.** With git (`command -v git`; on a Mac, `xcode-select -p` too, since a bare `git` there can open an installer): `git clone https://github.com/RNCDev/sweatcast.git ~/sweatcast`. Without git: download `https://github.com/RNCDev/sweatcast/archive/refs/heads/main.zip`, unzip it, and move the `sweatcast-main` folder to `~/sweatcast`. A ZIP copy works fully, except the privacy hook, which needs git.
4. **Hand over to a session in that folder.** sweatcast's instructions and safety settings (among them the rule that keeps API keys out of the chat) load only in a session opened there, so don't run setup from the session you're in. Give literal steps:
   - Claude desktop app: "click **New session** in the Code tab, choose the **sweatcast** folder in your home folder, and type *set up sweatcast*".
   - ChatGPT desktop app: "open the **sweatcast** folder in your home folder in Codex, trust it if asked, and type *set up sweatcast*".
   - An editor: open the `sweatcast` folder and start Claude Code or Codex there. A terminal: `cd ~/sweatcast && claude` (or `codex`).

# How it works

## Setup, step by step

1. **The readiness check** (`./sweatcast doctor`): your system, memory, disk and graphics, what's installed, and whether a voice can be made on this computer. Then the one big choice: a voice made on your computer (free and private, a one-time download, slower to render) or a web coach (no download, fast, pay-as-you-go), which one this computer starts with, and how to add the other later.
2. **The tools:** uv, which builds the project's Python environment (about half a gigabyte), is installed with Astral's official installer if it's missing, after the assistant asks. ffmpeg comes with that environment. git is optional: without it, setup skips the privacy hook (which keeps your details out of a push), and `./sweatcast backup` can't run.
3. **The quick start:** the four questions, and, where it's a web coach, the key: the assistant gives you the service's links and opens a file in your computer's text editor where you paste the key yourself, never into the chat. Your stand-in coach plays a short test clip first: Coach Andy for a voice on your computer (his clip ships with him), or the web service's default coach, whose voice is designed and saved in your account before the first workout (about a cent on Fish Audio or Gemini; Inworld doesn't publish the price; on ElevenLabs it takes one of the account's voice slots). Then the ten-minute workout, end to end.
4. **Later:** "finish setting me up" covers interests, teams and taste, and finds news feeds for them; "I want a new coach" auditions voices from every service you have a key for.

## How a session works

1. **Check-in:** the `workout` skill asks only what you didn't say: how each injury feels, how you're coming in today, the goal, length and kit.
2. **What fills the rests:** `./sweatcast content plan` picks the stories: quick items from today, current science, a deep dive (a news story or a video from your favorite YouTube channels; a long video becomes a series), a quiz that works by ear, something to enjoy and something to learn. Each slot rotates through your interests, and nothing told in the last thirty days is told again. Today's items are researched from `./sweatcast feeds` (your teams, the weather, local and science headlines, podcasts, puzzles, Wikipedia's day); evergreen pieces come from a reserve researched ahead of time.
3. **The plan:** `./sweatcast brief` gathers who you are, how the week has gone, today's limits with your clinician's rules, the safe menu (every movement your kit, level and limits allow, with coaching notes) and the programming guide. The assistant designs the session from it, posts the plan, and writes the script.
4. **The build:** `./sweatcast build` refuses any movement that isn't on today's menu, checks the script reads cleanly aloud, predicts each segment's spoken length for the coach, renders a loudness-normalized MP3, and copies it to your phone's folder. The script's text stays in the workout's folder in `me/workouts/`; the local MP3 is removed once the copy lands.

A soft chime opens each segment after the first, and a rising three-note tone ends the workout. A segment with time to spare widens its pauses and then ends early rather than going quiet, except timed work (`[hold]`), which keeps its full length. Only the total is held to plan. With a voice on an Apple Silicon Mac, Chatterbox Turbo renders a 30-minute workout in about 20 minutes (Qwen3 takes about twice as long), starting while the script is still being written; a web coach renders in a minute or two, once the script is done.

## Commands

The assistant runs these for you, but they work on their own too; `./sweatcast help` lists them all.

| Command | What it does |
|---|---|
| `./sweatcast doctor` | What this computer can do: system, prerequisites, whether local voices work, models, delivery folders (works before setup) |
| `./sweatcast setup` | First-run setup; safe to rerun (it also brings `me/` up to date after an upgrade) |
| `./sweatcast check` | Checks `me/`: anything still to fill in, or that the tools can't read |
| `./sweatcast build <draft> "<name>"` | Checks a draft, renders the MP3 and copies it to your phone's folder (`--lint-only` to just check) |
| `./sweatcast coaches` | Your coaches and where each speaks; `audition` and `keep` make a web coach, `archive` retires one; `design` and `keep` make a local coach's clip |
| `./sweatcast show <file>` | Opens the folder holding a file, such as a workout's MP3 (selecting it on a Mac or Windows) |
| `./sweatcast keys`, `models` | Which voice services have a key set (never the key), with `init` and `open` to add one; the local models, with `adopt` for ones already downloaded |
| `./sweatcast brief --goal strength --minutes 30 --preset hotel-room` | Today's ingredients: you, the week, your limits, the safe menu and the programming guide; `--save <draft>` writes the menu the build checks |
| `./sweatcast movements --preset hotel-room` | Browses the movements a kit allows (no health limits applied; plans come from `brief`); `--about <ids>` prints coaching notes |
| `./sweatcast feeds`, `content`, `youtube`, `log-session` | What the workout skill uses to research, plan the stories and log |
| `./sweatcast backup` | Commits `me/` and pushes it to its own private repo (the workout skill runs it after each session) |
| `./sweatcast harness` | Checks that ChatGPT's Codex files match the Claude Code ones; `sync` rewrites them |
| `./sweatcast migrate`, `cache prune`, `test` | Upkeep (`migrate` brings a `me/` from sweatcast 9 or later up to date; an older one goes through v12.0.0 first) |

## How it's organized

Three layers keep your details apart from the code:

| Layer | Where | In git? |
|---|---|---|
| **Engine**: the command, tools, skills, tests, shared knowledge and the template for `me/` | `sweatcast`, `tools/`, `.claude/`, `.agents/`, `.codex/`, `AGENTS.md`, `tests/`, `knowledge/`, `me.example/`, `docs/` | Yes, public |
| **Models**: the local voice models, pinned to exact revisions | `models/` | No: downloaded by setup |
| **You**: profile, health, log and feedback, coaches, drafts, research, MP3s, and voice service keys (`me/.env`, never backed up) | `me/` (or wherever `SWEATCAST_HOME` points) | No: ignored, and a pre-push hook and CI refuse it |

| Folder | What |
|---|---|
| `.claude/skills/` | The `workout` (request to MP3), `setup` (onboarding and profile changes) and `coach` (a new trainer) skills |
| `AGENTS.md`, `.agents/skills/`, `.codex/` | The same for ChatGPT's Codex: `AGENTS.md` points to `CLAUDE.md`, the skills are copies of `.claude/skills/` (`./sweatcast harness sync` writes both), and `.codex/` turns on the network and lets `./sweatcast` run outside Codex's sandbox |
| `knowledge/` | The movement catalog, session methods and doses, programming and injury references, equipment kits, what goes in a script, text-to-speech rules, coaches and voices, the web voice services |
| `tools/` | One file per job, all run through `./sweatcast`; `CLAUDE.md` says what each does |
| `tests/` | Fast checks with no models, network or personal files (`./sweatcast test`), run by CI on every push |
| `docs/` | The judged eval grid behind each release's quality, and the research the session rules cite |

Your profile is four files, split by how often each part changes:

| File | Holds | Changes |
|---|---|---|
| `me/profile.md` | Who you are: name, experience, basics | Rarely |
| `me/training.md` | Your kits and weights, the movements you like and dislike, your usual session | With new gear, or what you say at check-ins |
| `me/content.md` | What fills the rests: interests, feeds, YouTube channels, puzzles, taste | Often; only the research reads it |
| `me/settings.toml` | The tools' settings: setup stage, audio route, delivery folder, web spending ceiling | Rarely; setup writes it |

Next to them, `me/health.md` holds your injuries and your clinician's rules, and `me/log.md` your sessions and feedback. Each Markdown file has its settings in a block at the top, and prose below it for the assistant. Pulling updates never touches `me/`. When a release changes a file's format, `./sweatcast migrate` (or rerunning `./sweatcast setup`) brings `me/` up to date, backing up the originals first.

### Back up `me/`

Without a GitHub account, `me/` stays on your computer and everything works; copy the folder somewhere private now and then (it holds your health notes). With one, keep `me/` as its own private repo, inside the engine's folder but separate from it (never a submodule), and the workout skill's last step, `./sweatcast backup`, pushes each session. With the [GitHub CLI](https://cli.github.com) installed and logged in:

```
cd me && git init && git add -A && git commit -m "My sweatcast" && gh repo create sweatcast-me --private --source . --push
```

`me/.gitignore` leaves out the key file, rendered clips, MP3s and render logs. `./sweatcast backup` does nothing when `me/` isn't its own repo, and refuses a repo GitHub reports as public. Another computer gets your profile by cloning that repo into `me/`.

## Coaches and voices

A coach is a person's name, how they talk and how they sound, in `me/personas/<coach>-<where>/` (such as `coach-andy-local`). Stand-ins ship so you can start at once: Coach Andy for a voice on your computer, and one default web coach per service (Coach Reed on Fish Audio, Ellis on ElevenLabs, Nolan on Gemini, Owen on Inworld), each designed in your account the first time it's used. Make your own whenever you like, and keep several.
- **A web coach** is an original voice a service designs from your description and saves in your account. You hear candidates from every service you have a key for, pick by ear, and name the ones you keep.
- **A local coach** is a ten-second clip that your computer's voice engine copies.

| Where the voice comes from | Engine or service | Cost | Notes |
|---|---|---|---|
| Apple Silicon Mac | Chatterbox Turbo, or Qwen3-TTS, through MLX | Free | Chatterbox about 0.7 times the length of the speech on an M3, Qwen3 about 1.3 to 1.45 |
| Windows or Linux with an NVIDIA card | Chatterbox Turbo on CUDA | Free | About 0.5 times on an RTX 2080 Super; Linux not yet tried |
| Windows or Linux, processor only | The same, on the processor | Free | Experimental and slow; the smoke test measures it |
| Fish Audio | A designed voice, saved as a private model | About $0.30 a workout | Prepaid credit, no minimum; about $0.01 a design |
| Gemini | A designed voice | About $0.27 a workout through 2026, about $0.54 from 2027 | A Google AI Studio key; its free tier uses requests for training |
| Inworld | A designed voice, in your workspace | About $0.50 a workout | On-Demand plan, prepaid credit |
| ElevenLabs | A designed voice, in your account | About $1.60 a workout ($0.80 on the faster model) | Free keeps 3 voices and a small monthly allowance (not yet tried on Free); the key needs Text to Speech and Voices: write |

Prices are approximate, for a 30-minute workout, and change. A web build says what it will send and cost before sending, stops above a ceiling you set, and sends only the final script; that script can mention your injuries, so setup says so first. More in [knowledge/voices.md](knowledge/voices.md).

## Health and safety

sweatcast is not medical advice. It programs conservatively around the injuries you describe, and anything a doctor or physical therapist has told you overrides it: write it in `me/health.md` and it's followed literally. Every session has a stop rule (sharp pain, new swelling, numbness or giving way stops that movement), and red flags such as not being able to bear weight stop the session and suggest a clinician.

## Coaches and consent

A web coach's voice is designed from a written description, never copied from a recording, and sweatcast never offers voices that imitate real people or characters. A local coach's clip comes from the local voice designer, or from a recording you bring: your own voice, or someone's who has agreed. It stays in `me/` and is used only by your computer's own engine.

## Support

sweatcast is free and open source. If it gets you moving, you can [buy me a coffee on Ko-fi](https://ko-fi.com/devrc) or [sponsor it on GitHub](https://github.com/sponsors/RNCDev).

## Versioning

sweatcast follows [Semantic Versioning](https://semver.org). Each release is tagged `vX.Y.Z` on GitHub; `CHANGELOG.md` says what changed, and a release's "For forks" note says what to do after pulling it.

## License

MIT, see [LICENSE](LICENSE). `tools/char_weight.py` is vendored from [OmniVoice](https://github.com/k2-fsa/OmniVoice) under the Apache License 2.0, with its header kept. The voice models are downloaded, not distributed here: Chatterbox Turbo ([ResembleAI/chatterbox-turbo](https://huggingface.co/ResembleAI/chatterbox-turbo), MIT, used as is on Windows and Linux through Resemble's `chatterbox-tts`; MLX build [mlx-community/chatterbox-turbo-fp16](https://huggingface.co/mlx-community/chatterbox-turbo-fp16), Apache 2.0, with its tokenizer [mlx-community/S3TokenizerV2](https://huggingface.co/mlx-community/S3TokenizerV2)) and Qwen3-TTS ([Qwen/Qwen3-TTS-12Hz-1.7B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base), Apache 2.0; MLX build [mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16)).
