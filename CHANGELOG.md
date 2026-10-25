# Changelog

All notable changes to sweatcast. The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

## [12.0.0] - 2026-10-25

The profile is four files, split by how often each part changes and who reads it, so a workout reads a few dozen lines about you instead of a few hundred, and adding a feed can't touch your kits.

### Changed
- **The profile splits** (context schema 6):
  - `me/profile.md`: who you are (`name`, `experience`, the Basics and Listening setup prose). Rarely changes; every workout reads it.
  - `me/training.md`: how you train (`likes`, `dislikes`, `[[kits]]` with their weights, the Default session and Equipment kits notes). Changes with new gear or check-in feedback; every workout reads it.
  - `me/content.md`: what fills the rests (`youtube_favorites`, `puzzles`, `[[interests]]`, `[[feeds]]`, the Content and Taste prose). Changes most; only research and the story tools read it.
  - `me/settings.toml`: the tools' own settings (`setup`, `render`, `cloud_max_chars`, `deliver_to`, `words_per_minute`), plain TOML.
- **One reader:** `context.profile()` merges the four files' settings and joins their prose, so every tool reads them as before. A setting still counts in any of the four files, but each has a home file, which wins if it's written twice; `./sweatcast check` notes the duplicate and names each issue's file.
- **The template** (`me.example/`) comes in the four files, made by the same split, and its Equipment kits section no longer repeats the kit settings.
- **The skills** read and write the right file: a workout reads `profile.md` and `training.md` (research reads `content.md`), setup writes each setting to its home, and `setup = "quick"` lives in `settings.toml`.
- **Docs:** the README has a table of your files; CLAUDE.md describes the four files and their homes; the `render` setting's comment says it lists audio routes.

### Fixed
- `./sweatcast setup` reads `render` from `settings.toml` (an older folder's `profile.md` still works) when deciding whether to install the local engine.
- Messages that pointed at `profile.md` for feeds, YouTube channels and the web ceiling point at their new files.

### For forks
Run `./sweatcast migrate` once (or rerun `./sweatcast setup`, which runs it). It backs up `me/` first, splits `profile.md` into the four files and bumps `health.md` and `log.md` to schema 6. Each setting keeps its value; the settings' comments become the template's (your originals are in the backup). Any `## ` section of your profile other than Equipment kits, Default session, Content and Taste stays in `profile.md`. If `training.md`, `content.md` or `settings.toml` is already in `me/` (copied from the new template, say), migrate replaces it; the original goes to the backup.

## [11.0.1] - 2026-10-25

The README, CLAUDE.md and AGENTS.md are rewritten to be shorter and checked claim by claim against the code, and sweatcast can now be supported.

### Added
- **Support:** a Sponsor button on the repo (GitHub Sponsors and Ko-fi, `.github/FUNDING.yml`) and a line at the end of the README.
- **Invite a friend:** one message at the top of the README that works for someone with Claude or ChatGPT.

### Fixed
- **README:** segments don't all start on the clock (a segment with spare time ends early; only the total is held to plan); the disk and download figures now match the readiness check (6 GB free; about 4 GB on a Mac, up to 8 GB on Windows or Linux); the backup command commits before pushing and says it needs the GitHub CLI; Qwen3's render speed is no longer folded into Chatterbox's; Windows needs Git for Windows; an audition needs a voice key; coach folder names; and the license list covers Linux and the MLX tokenizer.
- **CLAUDE.md:** reorganized (what runs when, the listener's files, knowledge, tools by area, tests, audio, releases) with the errors fixed: the `render` setting lists routes, not engines; the lint doesn't read `words_per_minute`; the default web coach is made during setup's quick start; the feeds sheet's path; the `render` command and `test_tools.py`; the release rule now covers 11.0.0.
- **AGENTS.md:** tighter, and it gives every reason `./sweatcast` runs outside Codex's sandbox.
- **The setup skill** quotes the same download sizes as the README.
- **The profile template's `words_per_minute` comment** said the lint uses it; it doesn't.

## [11.0.0] - 2026-10-25

sweatcast runs under ChatGPT's Codex as well as Claude Code: Codex in the ChatGPT desktop app (any plan, Free included), the Codex CLI or an IDE, on the listener's own computer. Tried end to end with the Codex the ChatGPT app ships, on the Free plan's model: setup, then a ten-minute workout with Coach Andy on the local voice.

### Added
- **Codex's files.** `AGENTS.md` sends Codex to `CLAUDE.md` and says what to use in place of Claude Code's own tools (a numbered question for a multiple-choice one, `./sweatcast show` to hand over a file, research done in turn rather than by background agents), and never to read `me/.env`. `.agents/skills/` holds exact copies of the setup, workout and coach skills (the ChatGPT app's own import of Claude skills makes the same copy, so it changes nothing). `.codex/config.toml` turns on the sandbox's network, and `.codex/rules/sweatcast.rules` lets `./sweatcast` run outside Codex's sandbox, as `.claude/settings.json` allows it in Claude Code (both are read once the folder is trusted).
- **`./sweatcast harness`** checks that Codex's files match Claude Code's; `./sweatcast harness sync` rewrites them. Claude Code's files stay the one source: edit a skill there, then sync. The tests fail when they're out of step, and when the Codex rule and the Claude allow list stop naming the same command.
- **The README's ChatGPT path:** Start here, a message to send a friend with ChatGPT, where it runs, and the For Claude handoff for Codex.

### Changed
- **Inside Codex's sandbox without the rule** (an untrusted folder): `./sweatcast` keeps uv's cache in the project (`.cache/uv`, git-ignored), setup skips the privacy hook with the reason instead of stopping, and a local render that can't see the GPU says to run it again outside the sandbox.
- **Before the first workout under ChatGPT,** Codex says that ChatGPT may use what it reads, health notes included, for training unless "Improve the model for everyone" is off.

### For forks
Nothing to migrate: `me/` and every command work as before. If you change a skill, run `./sweatcast harness sync` and commit `AGENTS.md` and `.agents/skills/` with it.

### Known limits
- The key in `me/.env` is kept from Codex by instruction, as it is from Claude Code's shell commands; Codex followed it in every test. A system-level block is possible in Codex, but it stops sweatcast's own engine reading the key too, so web coaches couldn't speak.
- Not yet tried by hand in the ChatGPT app's window: its trust prompt, its multiple-choice questions, and its approval prompts.

## [10.4.0] - 2026-10-25

Onboarding is tidied for the two ways people actually start: a developer in an IDE or terminal, and a friend with the Claude desktop app. Claude Code on the web no longer sets up a new listener.

### Added
- **`./sweatcast show <file>`** opens the folder holding a file with it selected (Finder, Explorer or the file manager). Setup and the workout skill use it when the MP3 or a test clip can't be sent into the chat, so a listener never gets just a path.
- **Send this to a friend:** a README section with a message to paste to someone who has the Claude desktop app.

### Changed
- **The desktop path, step by step.** The README's Start here says which folder to pick when the Code tab asks (the home folder), to click Allow, and how to start the second session in the new `sweatcast` folder; the For Claude handoff uses the same literal steps.
- **One recommended voice service.** When a web coach is needed, setup recommends Fish Audio for a first key and walks through it with links (sign up, add credit, make a key), listing the other three with their key pages as more choices.
- **The phone folder comes right after the first workout,** as one question (iCloud Drive, Google Drive, Dropbox, or keep them on this computer), instead of waiting for "finish setting me up".
- **Claude Code on the web doesn't set up a new listener.** Setup and the README's For Claude section point to the desktop app instead. A listener already set up, with their private context repo attached, keeps working there.

## [10.3.0] - 2026-10-25

A new listener hears their stand-in coach before the first workout, and coach folders say where each coach speaks.

### Added
- **A test clip before the first workout.** Coach Andy, the local stand-in, ships with `sample.mp3`, fifteen seconds rendered on Chatterbox Turbo, which setup plays first. A web stand-in is made right after the key step (`./sweatcast coaches make`, its cost said first) rather than at the first build, and setup plays the clip that saves; a designed voice belongs to the account that made it, so each listener's is their own. Either way: if he isn't right, "I want a new coach". The setup skill, README, voices guide and CLAUDE.md say so.

### Changed
- **Coach Demo is Coach Andy**, in `me.example/personas/coach-andy-local/`, with "Coach Demo" kept as an alias, so log lines naming him still find him.
- **Coach folders name where the coach speaks:** the web stand-ins are `coach-reed-fish/`, `coach-ellis-elevenlabs/`, `coach-nolan-gemini/` and `coach-owen-inworld/`, and a coach kept from now on gets `coach-<name>-<service>` or `coach-<name>-local` (`personas.folder_for`). A coach already in a folder keeps it, and lookup by the plain slug (`coach-maya`) still finds `coach-maya-fish`.

### For forks
Nothing to migrate: folders in `me/personas/` keep their names, and renaming one by hand to the new pattern is safe (pace and sample move with it; cached clips are keyed by the voice, not the folder). The new stand-ins come only with a new `me/`; to have Coach Andy's clip, copy `me.example/personas/coach-andy-local/sample.mp3` beside your Coach Demo.

## [10.2.0] - 2026-10-25

The pantry is now the reserve: the evergreen filler (quizzes, things to enjoy, things to learn) researched ahead of time.

### Changed
- **The reserve.** `me/workouts/research/reserve/` holds the evergreen pieces, `./sweatcast content reserve` lists the unused ones, the plan prints "Reserve" and "The reserve is low", `knowledge/content.toml`'s per-slot target is `reserve`, and `./sweatcast content log` writes a piece's slug under `reserve`. The workout skill, its research templates, the script guide, the README and CLAUDE.md say the same.
- **CLAUDE.md** opens with the codegraph index: use the codegraph tool to find and read code, its callers and what a change touches, before grepping.

### For forks
Nothing to migrate. A `research/pantry/` folder is still read beside `research/reserve/` (a slug in both counts once), a record item logged with `pantry` still marks its piece as told, and `./sweatcast content pantry` still works as an alias. New pieces go to `reserve/`; move the old sheets over whenever you like.

## [10.1.0] - 2026-10-25

Setup now opens with the one big choice: where the coach's voice is made.

### Added
- **The fork, said first.** Right after the readiness check and before any question, the setup skill lays out local versus web in a few plain lines: on this computer (free and private, a one-time 3 to 4 GB download, about 0.7 times the speech's length to render on Apple Silicon) or a web coach (no download, a 30-minute workout in a minute or two, about $0.27 to $1.60 a workout with a key of your own, and the script goes to the service). It says which way this computer starts, and how to revisit it: nothing is locked in, both kinds can live side by side, and "I want a new coach", "add a voice key" or "set up local voices" changes it at any time. The README's Start here says the same.

### Changed
- **A renamed context folder stays private.** The engine's `.gitignore` now ignores `me.*/` (such as `me.real/` or `me.test/`, kept aside while trying the new-listener flow), with `me.example/` still part of the engine.

## [10.0.0] - 2026-10-25

Web coaches: describe, audition, approve, keep. A web coach is an original voice a service designs from the listener's description and saves in the listener's own account, at Fish Audio, ElevenLabs, Gemini or Inworld, pay-as-you-go with no subscription anywhere. One audition makes candidates on every service with a key, lettered and priced a workout; the listener picks by ear, names each one they keep, and a workout then uses it by name, always on the service that made it. Four default web coaches ship, one per service, designed the first time they're used. Copying a clip on the web is gone, and so are Cartesia and Deepgram: a clip-based coach is now a local coach, which renders only on the computer's own engine.

### For forks
This release changes the coach files (persona schema 4 to 5), the routes, the keys and the coach commands. After pulling it:
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it). Every coach's `persona.md`, archived ones too, gains `kind = "local"` and `schema = 5`, and nothing else in it changes; `me/.gitignore` gains `!personas/*/sample.mp3` and `!personas/.archive/*/sample.mp3` (a web coach's approved sample is kept, archived or not), `personas/.auditions/` (auditions in progress aren't) and `personas/*/.made.json` and `.made.wav` (a make between saving a voice and writing the coach). Changed files are backed up first, never `.env`.
- **Your existing coaches are local coaches now.** A clip-based coach renders locally only: clip copying on Fish Audio (the clip sent with every request) and ElevenLabs (a clone of the clip) is removed, along with `services.json`. A coach you used on Cartesia or Deepgram renders locally, or make a web coach with an audition ("I want a new coach", or `./sweatcast coaches audition`).
- **The profile's `render` list orders local engines only.** A web coach always speaks through its own service, whatever the list says; a service named there no longer renders a local coach. A local coach tries the local engine even when the list leaves it out; where local voices don't run (say Claude Code on the web, with `["fish"]` and only local coaches), `get route` and the build stop (exit 1) and name the way out: make a web coach, or copy the stand-in for a service with a key (`me.example/personas/coach-reed/` for Fish Audio, and so on) into `me/personas/`. The readiness check on the web says "No web coach yet" with the same way out, and the workout skill offers both. `cloud_max_chars` still caps what one build sends.
- **Keys:** `GEMINI_API_KEY` and `INWORLD_API_KEY` are new (`./sweatcast keys init gemini`, `init inworld`); `CARTESIA_API_KEY` and `DEEPGRAM_API_KEY` are no longer read, so delete their lines from `me/.env`. `./sweatcast keys open` opens `me/.env` in the system's editor. On Claude Code on the web, the network allowlist gains `generativelanguage.googleapis.com` and `api.inworld.ai`.
- **The four default web coaches come only with a new `me/`.** To have them, copy `me.example/personas/coach-reed/`, `coach-ellis/`, `coach-nolan/` and `coach-owen/` into `me/personas/`; each is made the first time a build uses it.
- **A sweatcast 8 folder migrates only from a git clone** with the `v8.0.1` tag (`git fetch --tags`): `tools/migrate-assets/v8-voices/` is gone, as promised for 10.0.0, and the migration reads the clips sweatcast 8 shipped from the tag. A ZIP download can't migrate one.
- **Commands:** `./sweatcast coaches samples deepgram` is gone, and `coaches design` uses the local designer only (Fish Audio and ElevenLabs no longer design local coaches' clips). New: `coaches audition`, `coaches keep <audition>/<letter> --name`, `coaches forget-audition`, `coaches make`, `coaches archive`, `keys open`.
- **`tools/msgpack_min.py` is gone** (Fish Audio now takes JSON), with `tools/services/cartesia.py` and `tools/services/deepgram.py`.
- A customized coach, setup or workout skill needs merging: the coach skill is rewritten around auditions, setup gains the keys step and the default web coaches, and the workout skill checks the coach can speak here (exit 64) and offers the stable when the coach used last is archived.

### Added
- **Web coaches** (`kind = "web"` in `persona.md`): a voice designed and saved at a service, spoken by its saved voice ID, with `[voice]` (who, sound, energy, pace, avoid: what services design from) and `[character]` (how they talk, which the brief quotes), `sample.mp3` and a pace estimated from the sample, so the first workout needs no smoke test.
- **Auditions** (`./sweatcast coaches audition <narrative> [--services ...] [--coach "<name>"] [--play]`): candidates from every keyed service in parallel (Fish Audio 2, ElevenLabs 3, Gemini 1, Inworld 2), lettered A, B, C..., each saying the same coaching line, each with its approximate cost a workout, in `me/personas/.auditions/<date>-<n>/`. A service that fails is one line; the others still land. Nothing is saved at a service except Gemini's, which stores as it designs.
- **Keep, forget, make, archive:** `coaches keep <audition>/<letter> --name "<name>"` saves the voice at its service as "sweatcast <name>" and writes the coach (several from one audition, each its own coach); with an audition made by `--coach`, it re-voices that coach, and `--replace-old` deletes the old voice at the service. `coaches forget-audition` deletes Gemini's unkept voices and the folder. `coaches make "<name>"` designs and saves a pending default's voice (builds run it). `coaches archive "<name>"` moves a coach to `me/personas/.archive/`: out of the list, still found by name for old log lines.
- **Gemini** (an AI Studio key; `gemini-3.8-flash-tts`, about $0.27 a workout until 2026-12-31, about $0.54 from 2027) and **Inworld** (On-Demand; `inworld-tts-2`, about $0.50 a workout), both tried live. Gemini takes no style setting yet (`./sweatcast check` flags a `style`), runs about 35 percent slower (pace is measured per coach), and its free tier uses requests for training with human review.
- **Four default web coaches** in `me.example/personas/`, from one description (a man in his forties, a warm baritone, a seasoned trainer): Coach Reed (Fish Audio), Coach Ellis (ElevenLabs), Coach Nolan (Gemini), Coach Owen (Inworld), each `placeholder = true` and `pending = "design"`. The first build that needs one designs it and saves the first candidate, saying so first (about $0.01 on Fish Audio and Gemini; Inworld's design cost is unpublished; one of ElevenLabs Free's 3 voice slots); `--lint-only` never does.
- **`./sweatcast keys open`:** opens `me/.env` in the system's editor (`open -e`, `notepad`, `xdg-open`) without reading it (where there's no opener, it prints the file's path); on the web, it says to use the environment's settings.

### Changed
- **Routes:** a web coach speaks only through its own service; with no key for it here, `get route` and `build` exit 64 with the fix, as does `--engine` naming another service. A local coach renders only locally. The routes are local, fish, elevenlabs, gemini and inworld.
- **The default coach:** with none named, a build takes the coach used last; if that one is archived it stops and names the stable (exit 1), and if it was a stand-in and the listener now has a coach of their own, it takes theirs; with no sessions, the listener's own coach, then a stand-in that can speak here (a web default whose key is set, then Coach Demo where local runs).
- **Exit 3 is for local coaches only:** a web coach renders from its sample's estimate, and each render measures it.
- **Fish Audio** speaks by the saved voice (`reference_id`, JSON) on `s2.1-pro`, designs and saves private models; **ElevenLabs** designs three previews and saves the chosen one, on `eleven_v4` (or `eleven_v4_turbo`), labeled "not yet tried on a Free account" (Free keeps 3 voices and a monthly allowance). `knowledge/services.toml`: rates checked 2026-10-25, `design_usd`, a `note`, all four tried live.
- `./sweatcast coaches` shows where each coach speaks (`web · Fish Audio`, `local · chatterbox`) and which are made the first time they're used. `./sweatcast check` notes a pending default, and flags a web coach with no voice or with a `style`.
- The coach, setup and workout skills, `knowledge/voices.md`, the README and CLAUDE.md describe web coaches: the keys step with each service's cost and terms, the privacy line (every service receives the script, which can mention injuries; Gemini's free tier trains on it), the quick start with the keyed service's default web coach, and the workout's offer of other coaches when one can't speak here.

### Removed
- **Cartesia and Deepgram** (`tools/services/cartesia.py`, `tools/services/deepgram.py`, their keys and hosts, `coaches samples deepgram`): Cartesia's cloning needs a subscription, and Deepgram has stock voices only, so neither could make an original coach without one.
- **Clip copying on the web:** Fish Audio's inline clip, the ElevenLabs clone, `services.json` and the clone-once code; and Fish Audio and ElevenLabs as designers of local coaches' clips.
- **`tools/migrate-assets/`** (the clips sweatcast 8 shipped; the migration reads them from the `v8.0.1` tag) and **`tools/msgpack_min.py`**.

## [9.1.2] - 2026-10-24

ElevenLabs and Cartesia tried live, and setup says plainly that both need a monthly subscription.

### Changed
- **ElevenLabs and Cartesia are tried live** (`knowledge/services.toml`): a smoke test and a 10-minute workout on each, from a Mac, both within 1% of plan. Only Deepgram is still "not yet tried live".
- **Subscriptions:** copying the coach's voice from a clip (cloning) isn't on either service's free or pay-as-you-go plan: ElevenLabs needs Starter (about $6 a month) and Cartesia Pro (about $5 a month). The setup skill says so before the listener picks one, and the README and `knowledge/voices.md` show it. Fish Audio needs no subscription for this.
- An ElevenLabs key needs two permissions when it's made, Text to Speech and Voices: write; the setup skill and README say so.

## [9.1.1] - 2026-10-24

The README now starts where a new listener starts: "Can you use https://github.com/RNCDev/sweatcast and set me up?"

### Changed
- **README:** a Start here section (asking Claude with the link, what you need, what to say after setup, doing it yourself), a "Where it runs" table that says Claude Code on the web needs a GitHub account, and a "For Claude" section: how a Claude session outside a copy of the repo downloads it to `~/sweatcast` (git or the ZIP, no GitHub account needed) and hands over to a session opened in that folder, where the project's instructions and safety settings load.
- No GitHub account is fine: the README and the setup skill say `me/` then stays on the computer, and how to keep a copy.
- CLAUDE.md points to the README's "For Claude" section.

## [9.1.0] - 2026-10-24

A stranger's first workout in minutes, Claude Code on the web, and a folder per workout. Setup's quick start asks four questions and starts the listener with Coach Demo, a stand-in coach that ships measured, so the first ten-minute workout needs no voice design and no smoke test. Claude Code on the web runs sweatcast with a cloud voice, and the workout arrives as a page with a player. Each workout's files now live together in their own folder.

### For forks
This release moves files in `me/workouts/` (schema 4 to 5). It changes the `me/` layout, which the project's rules call a major release; it's released as a minor one at the maintainer's call, since `./sweatcast migrate` does everything. After pulling it:
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it; `--dry-run` lists the moves first). Each draft in `workouts/drafts/` moves with its brief and menu to `workouts/<stem>/`, and each build's script and record moves beside the draft its record names (or the one draft from the same date). Smoke tests, and anything that can't be placed for sure, go to `workouts/checks/`; each day's research sheet and feeds go to `workouts/research/daily/`. Nothing is overwritten (a clash gets " (2)"). The context files change only their schema number; `me/.gitignore` gains `!*.web-*.mp3`.
- **Coach Demo** comes only with a new `me/`. To have it in yours, copy `me.example/personas/coach-demo/` into `me/personas/`.
- A customized workout skill needs its paths updated: the draft is `me/workouts/<stem>/<stem>.draft.txt`, and the feeds sheet `me/workouts/research/daily/<date>-feeds.md`. `SWEATCAST_ALLOW_CLOUD_SESSION` is gone.

### Added
- **Coach Demo** in `me.example/personas/coach-demo/`: sweatcast 8's public Chatterbox Coach clip with its measured pace on Chatterbox Turbo (MLX and PyTorch) and Fish Audio. It's marked `placeholder = true`: `./sweatcast check` notes it, `./sweatcast coaches` marks it a stand-in, and a build with no coach named picks any other coach before it.
- **A quick start** in the setup skill: one round of four questions (name, experience, kit, injuries), the audio route only when local voices don't run here, Coach Demo, and a ten-minute workout. "Finish setting me up" runs the rest. The profile's new `setup = "quick"` makes `./sweatcast check` report what's left as notes, not issues.
- **A quick coach** in the coach skill: three named sketches or their own, one take, keep it.
- **Claude Code on the web, with cloud voices only.** The readiness check turns local voices off there and says what to set: the key as an environment variable in the cloud environment's settings (`./sweatcast keys init` prints the line), the service's host for the network allowlist (and the feeds' hosts, optional), and whether the context folder is kept. The context folder is found beside the engine when the listener attaches their private `sweatcast-me` repo (or named by `SWEATCAST_HOME`); without one, setup explains it's a one-time session. `coaches download` and `setup --local` refuse there.
- **A web copy** (`tools/webcopy.py`, `build --web`, on by default on the web): the MP3 mono at 48 kbps in parts of at most 14 MB (about 38 minutes each) and a player page that plays them in order, which the workout skill publishes as a private artifact; `./sweatcast backup` commits the parts to the private repo.
- **A folder per workout** (`tools/workouts.py`): the build writes into the draft's own folder, or `checks/` for the smoke test and drafts outside one.
- The build record says where the MP3 went (`delivered_to`, `kept_local`, `reason`).
- `routes.hosts()` and `routes.feed_hosts()`: the hosts each route and the feeds reach.

### Changed
- `./sweatcast` no longer declines a Claude Code cloud session.
- `./sweatcast backup`'s check for a public remote works without `gh`, through GitHub's API.
- The README says where sweatcast runs: Claude Code on your own computer (terminal, IDE or the desktop app's Code tab) and Claude Code on the web, not the plain Claude chat.

## [9.0.0] - 2026-10-24

A standalone sweatcast: any reasonable computer, any voice engine, and coaches of the listener's own. Local audio now runs on Linux too, and on the processor where there's no NVIDIA card (experimental); a cloud voice with the listener's own key works on any computer, an Intel Mac included. Voices become coaches: a person's name, how they talk and a clip every engine copies, kept in `me/personas/`, so the same coach sounds the same locally or in the cloud.

### For forks
This release changes the `me/` layout (schema 3 to 4), the commands and the environment. After pulling it:
- **Run `./sweatcast setup`.** It migrates `me/` (backing up the changed files to `me/.backup-<time>/` first, never `.env`), installs the local engine as an extra where this computer runs one, and suggests moving models you already have.
- **Voices become coaches.** Each voice in the profile's `[[voices]]` becomes a folder in `me/personas/`, with its clip, words and measured pace: Chatterbox Coach becomes Coach Julius and Qwen3 Coach becomes Coach Solo, keeping their old names as aliases, so old log lines and `--voice "Chatterbox Coach"` still find them. The profile's `## Narrator` lines become how each coach talks (`## How this coach talks` in `persona.md`). Cached clips stay valid. A private voice named for a model needs a person's name: `./sweatcast migrate --name "<old>=Coach <Name>"`. `me/voices/` and `workouts/.audio-cache/voice-pace.json` move into the backup.
- **The profile** loses `[[voices]]` and gains `render = ["local"]`, the audio routes in order of preference; add a cloud service there (`["local", "fish"]`) to use one where local doesn't work. `cloud_max_chars` (default 30,000) caps what one build sends.
- **Commands:** `--voice` is now `--coach` on build, render, lint, brief and log-session (the old name still works); `./sweatcast voices` is now `./sweatcast coaches`; `./sweatcast get default-voice` is `get coach`. New: `doctor`, `keys`, `models`, `coaches`, `get route`, `build --engine`. The smoke test moved to `knowledge/smoke-test.draft.txt`. `voices/` is gone; the clips sweatcast 8 shipped wait in `tools/migrate-assets/v8-voices/` for the migration, until 10.0.0.
- **Models** download into `models/` at the repo root (git-ignored; a symlink or `SWEATCAST_MODELS` points it elsewhere) instead of `~/.cache/huggingface/hub`: `./sweatcast models adopt` moves the ones you have.
- **The environment:** the local engines are optional extras (`mlx`, `cuda`, `cpu`); `./sweatcast setup` picks one and remembers it in `.venv/.sweatcast-extra`. Run `uv sync` yourself only with `--extra <it>`, or it uninstalls the engine.
- **Keys** for cloud voices go in `me/.env` (`./sweatcast keys init <service>`), which `me/.gitignore` and `./sweatcast backup` keep out of the private repo. A customized setup or workout skill needs merging: setup gains the audio route and the coach step; the workout skill passes `--coach`, renders ahead only on a local route, and handles exit 4.

### Added
- **Cloud voices with the listener's own key** (`tools/cloud.py`, `tools/services/`): Fish Audio (the clip goes with every request; tried live), ElevenLabs (a clone made once, with each paragraph's neighbors for smoother joins), Cartesia (a clone made once) and Deepgram Aura-2 (stock voices only). ElevenLabs, Cartesia and Deepgram are built against local fakes of their documented APIs and labeled "not yet tried live". Before sending, a build prints the characters and approximate cost (rates in `knowledge/services.toml`, dated) and stops above `cloud_max_chars`; only the final build sends, a few requests at a time, retrying rate limits; a refused key, payment or quota exits 4; rendered clips stay cached, so a rerun sends only the rest. The build record logs the characters sent. Keys are never printed, logged, recorded or part of a cache key.
- **Coaches** (`tools/personas.py`, `./sweatcast coaches`, the `coach` skill): design takes from a description (Qwen3 VoiceDesign on an Apple Silicon Mac, or Fish Audio or ElevenLabs design), keep one, or bring a clip with its words; several coaches, the one used last by default; `set` for a coach's settings; Deepgram stock-voice samples.
- **Routes** (`tools/routes.py`): each build takes the first route in the profile's `render` list that works on the computer it runs on; `./sweatcast get route` and the readiness check say which.
- **`./sweatcast keys`** (`tools/keys.py`): which services have a key set, never the key; `init` makes the line for the listener to paste into. `.claude/settings.json` denies Claude reading or writing `me/.env`.
- **`./sweatcast models`** (`tools/models.py`): the models in `models/`, and `adopt`, which moves sweatcast's models out of Hugging Face's cache, shared blobs and all.
- **Local audio on more computers:** Linux with an NVIDIA card (not yet tried), and Windows or Linux on the processor (experimental, speed unknown until this computer's smoke test measures it; the readiness check then quotes a 30-minute workout's render time). Each render records the computer's render speed beside the pace.
- The readiness check reports the audio routes, the models folder, models waiting to be adopted, and a repo inside a synced folder.

### Changed
- The brief quotes the chosen coach's `persona.md` (who's coaching and how they talk) where it quoted the profile's Narrator, and its words-a-minute line uses that coach's pace on the route a build would take.
- `./sweatcast check` reports a missing coach, a coach without a clip or still showing a hint, and a route the profile names that isn't one.
- `log-session --coach` (with `--voice` kept); the workout skill's check-in says who's coaching and asks only when the request suggests a change.

### Not added
- A local voice designer on Windows or Linux: Qwen's PyTorch package (`qwen-tts`) pins transformers 4.57.3 against Chatterbox's 5.2.0, so they can't share an environment. Those computers design with Fish Audio or ElevenLabs, or bring a clip.

## [8.1.0] - 2026-10-24

Setup that a stranger can't trip over. Someone who clones sweatcast and says "set up sweatcast" in Claude Code is told up front what their computer can do, and setup no longer stops halfway for a missing prerequisite.

### For forks
Nothing to migrate: `me/` keeps schema 3. A customized setup skill gains a Step 0 (`./sweatcast doctor`, the cloud-session stop and the uv offer); merge it if you changed that skill.

### Added
- `./sweatcast doctor` (`tools/doctor.sh`, then `tools/doctor.py`): the readiness check. The system, chip, graphics, memory and free disk; uv, git, ffmpeg and the Python environment; whether local voices work on this computer and, when not, why; the voice models on disk; `me/` and its schema; each delivery folder, there or not on this computer; and whether ffmpeg can encode MP3 and normalize loudness. It runs before setup has made anything, and setup prints its first half as step 0. The memory and disk floors (8 GB, 6 GB free) are cautious guesses, said as such.
- Claude Code cloud sessions are declined: with `CLAUDE_CODE_REMOTE=true`, every command but `help`, `test` and `doctor` stops with the reasons (no graphics card, the model download blocked, nothing kept after the session) and suggests the listener's own computer. `SWEATCAST_ALLOW_CLOUD_SESSION=1` lets a developer through.
- `./sweatcast setup --install-uv` installs uv with Astral's official installer (no admin rights); the setup skill asks before running it.
- ffmpeg comes with the Python environment (`imageio-ffmpeg` 0.6.0, whose ffmpeg 7.1 has libmp3lame and loudnorm) when it isn't installed (`tools/ffmpeg.py`).
- `tools/player.py`: takes play with the system's own player (afplay on a Mac, xdg-open on Linux, the default player on Windows).

### Changed
- Setup no longer stops for a missing ffmpeg, and outside a git checkout (a zip download) it skips the privacy hook, says why, and carries on to the voice models. It always runs `uv sync`, which rebuilds a `.venv` copied from another computer.
- The setup skill answers "set up sweatcast", "setup sweatcast", "install sweatcast" and "get started", starts with the readiness check, and names the right installer for each system; the skills send samples with SendUserFile or the system's player, never `afplay` alone.
- The README starts from "open it in Claude Code and say set up sweatcast".

## [8.0.1] - 2026-10-23

### Fixed
- On Windows, `./sweatcast` prints in UTF-8, so a video title or headline with an emoji no longer crashes `./sweatcast youtube pick` (the console's default code page couldn't encode it).
- The pantry research template said "he" for the listener in one place; it says "they" like the rest.

## [8.0.0] - 2026-10-23

The filler between exercises gets a plan, a memory and a pantry. Each session's rests carry a planned mix (quick items from today, current science, a deep dive, a quiz, something to enjoy and something to learn), each slot rotating through the listener's interests, the one told longest ago first. A record of every item told keeps a story from being told twice. Evergreen pieces are researched ahead of time into a pantry, so session-day research covers only the news. The feeds reach further: Wikipedia's day, and whatever the listener's taste calls for.

### For forks
The research step changed, so a customized workout skill needs merging:
- The research templates moved out of the workout skill into `.claude/skills/workout/research.md`, rewritten around `./sweatcast content plan`: today's research (every session), a pantry agent (when the plan says to restock) and the video agent (when the plan's deep dive is video). The deep dive's video or news alternation now comes from the plan, not the log's topics.
- After each build, the skill records every filler item told: `./sweatcast content log --date <date> --item "<slot> | <category> | <title> [| <source> [| <pantry slug>]]"`. Sessions from before this release aren't in the record; add them the same way if you want them counted.
- `me/` keeps schema 3; nothing to migrate. Optional additions to `me/profile.md`: `[[interests]]` rows in the settings (name, slot, detail; without any, `knowledge/content.toml`'s defaults apply), a `## Taste` section of favorites with ratings, and `[[feeds]]` of the new `wikipedia` kind (`value = "featured"`). The setup skill now asks for interests and taste.

### Added
- `./sweatcast content` (`tools/content.py`): `plan --minutes N` prints what a session's rests carry, by slot and category, with the listener's detail for each, the last thirty days of items told, the pantry's unused pieces and what to restock; `log` records a session's items; `pantry` lists the unused pieces.
- `knowledge/content.toml`: the slots, how many of each a session carries by length (fifteen, thirty and longer), each evergreen slot's pantry target, and default categories.
- The record of what's been told, `me/workouts/research/told.jsonl`, and the pantry, `me/workouts/research/pantry/<slug>.md` (a piece is used once the record names its slug).
- Profile `[[interests]]` (checked by `./sweatcast check`: each needs a name and a known slot) and a `## Taste` section; the script guide says to recommend in their spirit, open each item with a hook tied to the listener, and never recommend something they rated three or less.
- A `wikipedia` feed kind: the day's featured article, the most-read pages, in the news, and did you know.

### Changed
- `knowledge/script.md`'s filler section follows the plan, and a slot with nothing verified gives its time to coaching.
- `./sweatcast youtube puzzles` also skips puzzle videos already in the pantry or the record.
- The workout skill reads the plan before the check-in, and again for the chosen length after it.

## [7.2.0] - 2026-10-23

Faster from check-in to MP3, with the same audio, and a smaller engine. The coaching is written while research runs, and the voice renders each paragraph as it lands in the draft, so the render mostly overlaps the writing instead of following it. The old session composer is retired: about 900 fewer lines of tools and 600 fewer of tests.

### For forks
- `./sweatcast session` is gone. The workout skill hasn't used it since 7.0.0 (`./sweatcast brief` plans); `docs/eval/skeletons.sh` runs it from the v7.1.0 tag as the eval's baseline. Code that imported `tools/session.py` for the safety screen imports `tools/screen.py` (`screen`, `Screen`, `Unfit`, and the helpers under public names: `ids`, `clamp`, `healthy_side`, `would_open`, `cue_lines`, `loads_line`, `parse_limit`, `words`).
- `./sweatcast build` is Python now (`tools/build.py`); `tools/build.sh` is gone. Its options and exit codes are unchanged.
- Nothing to migrate in `me/`. Cached clips are still used.

### Added
- `./sweatcast build <draft> <name> --follow` (`render.py --follow`): renders ahead while the draft is written. It keeps the voice loaded, rereads the draft between clips, renders each new or edited paragraph, and steps aside after its current clip when the full build starts (which renders only what's left), or after `--idle` seconds (fifteen minutes by default) with nothing new.
- The brief's Writing it section gives the voice's words a minute on this computer ("Talk to time"), from its measured pace, so segments come out the right length the first time; `--voice` picks a voice other than the profile's default.

### Changed
- The workout skill writes in this order: start `--follow`, write all the coaching from the brief without waiting for research, add the stories once research reports, then lint. `--clips-only` stays for a one-off render of what a draft holds.
- The voice engines no longer write a progress bar per clip or their dependency warnings into the render log (a 25-minute render's log was about 150 KB of bars; it's now only what matters).

### Removed
- `tools/session.py` (the composer) and its tests; the screen's tests moved to `tests/test_screen.py` and the session methods' to `tests/test_sessions.py`.
- `tools/build.sh`.

### Fixed
- `docs/eval/briefs.sh` and `skeletons.sh` run on Windows (the venv's Python path, and no `\r` on the case lines).

## [7.1.0] - 2026-10-23

The check-in comes first, and the session adjusts to the listener: before it starts, from how they're coming in today, and during it, from a self-check after each main movement's first set.

### For forks
Nothing to migrate. If you customized the workout skill, its first two steps changed: step 1 reads only the profile, health and log (plus `./sweatcast check`), and the headlines agent now runs `./sweatcast feeds` itself.

### Added
- A Readiness question in the check-in ("How are you coming in today?": normal, low, fresh after an easy session, or last one too hard), taking the place of the Last session question. The Limits question also offers "Sore somewhere else".
- `knowledge/programming.md`, Readiness and adjusting on the day: low readiness keeps the length but drops about a third of the hard sets, holds the loads, stops further from failure and skips all-out work; muscle soreness keeps that group light, and joint pain is a delicate limit for today. The brief prints the rule with the others.
- `knowledge/script.md`, Adjusting as you go: a target on every main set (reps and reps left), and after each main movement's first set a self-check by feel with one harder and one easier option for the sets after it, from the movement's notes and the progression order, within the set's time, never adding load to a limited area, and easier-only on a low day.

### Changed
- The workout skill asks the check-in straight after reading the profile, health and log; the feeds, the knowledge files and the brief wait until it's answered, so the listener can answer within seconds and step away.
- Past four open questions, the check-in drops Voice, then Length.

## [7.0.0] - 2026-10-23

Ingredients, not skeletons. The harness supplies what a session is built from, and the writer designs it: `./sweatcast brief` gathers the listener, the week, today's limits and the safe menu of movements with their coaching notes, the programming guide and the kit's notes, and the workout skill chooses the format, the movements, their order, doses and timing, then writes the script. The hard checks stay only where something must never go wrong: every movement from today's safe menu, text a voice reads cleanly, paragraphs short enough for one clip, and the total within three percent.

Judged on eleven cases against the previous run (`docs/eval/results-2026-10-23.md`): warmth 2.45 to 4.45, efficacy 3.64 to 4.09, adherence 3.82 to 4.18; safety 4.91 to 4.73, from three gaps the brief left the writer to fill (a clinician's rule softened later in a script, a carry heavier than a delicate neck allows, a walk to the rack under "nothing standing"), each fixed in this release.

### For forks
Nothing to migrate in `me/`; the context files stay schema 3 and the catalog format 3. What changes is the workflow and the draft:
- Plan with `./sweatcast brief --goal <goal> --minutes <N> (--kit | --preset | --equipment) [--limit ...] --save <draft path>` in place of `./sweatcast session`, which stays as an optional example shape. `--save` writes `<stem>.brief.md` and `<stem>.menu.json` beside the draft.
- A draft starts with a `movements:` line naming every movement it uses (by its menu name), then its segments, which add up to exactly the request. `./sweatcast build` won't build a draft without its menu, or with a movement the menu doesn't hold; only the voice smoke test builds without one. A draft you're halfway through from an older release needs a `brief --save` for its path and a `movements:` line.
- `./sweatcast log-session --draft <path>` logs the declared movements.
- The lint no longer warns on structure (locators, countdowns, praise, the name, openings, newsreader handoffs); that is guidance in `knowledge/tts-rules.md`. A segment far off its slot shows in the table without blocking (`--strict` makes it count).
- If you customized the workout skill, its script rules moved to `knowledge/script.md`.

### Added
- `./sweatcast brief` (`tools/brief.py`): today's ingredients in Markdown. The listener (name, level, likes and dislikes, the profile's Narrator and Default session lines); how today fits the week from the log; today's limits with what each means, the clinician's rules, the limit cues with the side filled in, the playbook's paragraph per area and the red flags; the safe menu, every movement the kit, level, limits, Avoid lines and dislikes allow, by primary pattern, each with its facts, its load on today's limited areas and its full coaching notes, healthy-side-only ones marked; the weights on hand; the programming guide (the level's doses, the sprint rest rule, the time shares, the formats that fit, every rule in `programming.md`); and the kit's notes from `kits.md`. It plans nothing.
- The menu check (`tools/menu.py`), run by the lint and required by the build: a declared movement off the menu, a catalog movement the text names that's off the menu, nothing declared, or segments that don't add up to the request stop the build, whatever `--force` says. Plain one-word names ("squat", "swing"), a shortened name of a declared movement ("the bench press") and "no neck rolls today" don't count; a menu movement named but not declared is a warning.
- The draft's `movements:` header line (`tools/draft.py`), never spoken, and where a draft's brief and menu sit beside it.
- `knowledge/script.md`: what goes in a script, from the welcome to the sign-off, moved out of the workout skill and added to (a clinician's rule beats the general stop rule; a limit cue beats a movement's own setup; under "nothing standing", the kit is set out within reach before the work starts).
- The lint's table shows each held segment's spare seconds, spent in silence, so a quiet strength rest is easy to spot.
- Eval: `docs/eval/briefs.sh`, `extra-cases.toml` (c41), the writer and judge briefs for the brief path, and run 5's results.

### Changed
- The workout skill is a page of procedure (from about 5,800 words to about 1,400, plus the research templates): read, check in and launch research, brief, design and post the plan, write, build, deliver, log and back up.
- `./sweatcast session` shares its safety screen with the brief (`session.screen`) and is an optional reference and the eval's baseline; it isn't extended.
- The lint keeps only what must hold: the text-to-speech line checks, the paragraph length, the total within three percent, and the menu check. Segment fill flags show without blocking.
- Catalog: carries rate a light neck load (a delicate neck allows them, marked; an off-limits neck rules them out); step jacks rate groin 2 (a side step is what loosens a groin limit); shadow boxing rates a light low-back load, so a delicate back screens it as fast work; the towel door row says the handle on your side.
- Docs harmonized around the brief: CLAUDE.md, the README, the setup skill, `kits.md`, the injury playbook, `programming.md`, `tts-rules.md`, the profile and health templates and the eval listeners (whose prose no longer names someone other than their `name`).

### Removed
- The lint's structure warnings and the workout skill's skeleton steps (`session --draft` markers, first candidates, per-slot rules).

## [6.2.0] - 2026-10-22

Scripts that sound like a coach who knows the listener, not a template read aloud: a name, a person's register around the work, continuity from the log, a session arc, and lint checks that catch the mechanical patterns. Plus the engine fixes the last eval left open.

This release was not judged on the eval grid; all forty skeletons compose and the tests pass. The next major release moves session design from the composer to the writer (a brief of safe ingredients in place of a fixed skeleton), so the composer changes below may be short-lived.

### For forks
Nothing to migrate; the context files stay schema 3. Optional: add `name = "<first name>"` to the profile's settings so the coach greets the listener by it (`./sweatcast check` notes when it's missing), and fill in the two new Narrator lines in the profile's prose.

### Added
- `name` in the profile's settings: the coach greets the listener by it in the opening line and uses it at the hardest set and the sign-off, two to four times. The setup skill asks for it.
- `knowledge/tts-rules.md`, Coaching voice, rewritten: short cues during the work, a person talking around it (contractions, "let's", one line of why per movement, the effort noticed plainly, continuity from the log), the session arc (welcome, build, peak, ease off, a specific and personal close), varied locators, and stories handed off the way a friend would.
- `./sweatcast coverage` prints the days since the last session, the sessions in the last seven days and the latest feedback, for the script's continuity lines.
- Lint warnings (not blocking): a set name that never comes up, isn't in the welcome or comes up more than five times; three or more segments in a row opening alike; newsreader handoffs ("Today's story is", "In other news"). The locator check accepts "two to go", "one more", "here we go", "back to" and "again".
- The profile template's Narrator section asks how the coach should talk to the listener and what encouragement works for them.
- Eval: the judge scores a fifth thing, warmth; the four invented listeners have first names.

- `[limit_cues]` in the catalog: one to three spoken cues for each area at each limit level (head and eye position for the neck, where the resting foot goes and how to get to and from the floor for an ankle or foot, brace and roll to the side for the low back, and so on), printed by `./sweatcast session` as a `Limit cues` block for each active limit, with its side.
- `[all_out]` in `knowledge/sessions.toml`: an all-out sprint (hard, timed, twenty seconds or less) rests at least four times its work, from `programming.md`'s sourced rule, with fewer rounds to fit; the finisher ranks sprints last.
- Two hard machine entries, `elliptical-surge` and `treadmill-hill-walk`, so a hotel gym's intervals can leave the bike.

### Changed
- The workout skill's opening greets by name and says how today fits the week; its close names what was done, gives a reason to come back and signs off by name. Under a limit, the script uses the skeleton's limit cues.
- A circuit groups its stations by place (standing, seat or bench, floor), so a round changes place as little as the movements allow (one change instead of four in the judged floor-and-bench case).
- Every set's segment holds its reps at the movement's pace (both sides of a one-sided move, plus a side change) and a few seconds to start, carried by the last set; the fitting lowers reps by about one where time is short.
- Intervals with several machines go round them: a hard movement on a machine nothing has led on yet comes before a second block on the same machine, and the steady block prefers an unused machine and is skipped when a machine change would leave it under ninety seconds.

## [6.1.0] - 2026-10-22

Better context for writing a script: the coaching a listener without a screen or a mirror needs for each movement, half of the unfinished catalog finished, sourced physiology for rest, effort, stretching, coverage and ankle rehab, and the kit's real weights.

### For forks
Nothing to migrate; the catalog stays format 3 and the context files schema 3. Optional: add `weights` (equipment id = the weights you have, lightest to heaviest) and `unit` (`"lb"` or `"kg"`) to a `[[kits]]` row, such as `weights = { dumbbells = [10, 15, 20] }`, so the session tool prints what's on hand. A private movement in `me/movements.toml` may add `rep`, `feel` and `faults`.

### Added
- Catalog coaching fields on every finished movement: `rep` (what one rep is, per side or not; for a timed entry what is held and a talk test), `feel` (where it should be felt and where not) and `faults` (one to three common mistakes, each with its fix). Spoken text, checked like `setup` and `cues`.
- `./sweatcast session` prints a Coaching section for its first picks (setup, cues, rep, feel, faults, easier and harder), a `Muscles:` line (the major groups the plan trains and the ones it leaves out) and, when the kit gives its weights, a `Loads on hand:` line. `./sweatcast movements --about <ids>` prints the coaching for any movement. The workout skill coaches from these, not from memory.
- Fifty movements finished from drafts (94 drafts down to 44), each reviewed for its joint ratings: seated conditioning (seated march, shadow boxing, arm pumps, speed bag), the eight stickhandling drills, ankle and foot rehab (band eversion, inversion, dorsiflexion and plantar flexion, towel scrunch, ankle alphabet and circles, single-leg balance, seated calf raise), seated mobility, curls, kickbacks, band external rotation, seated and band rows, band pull-apart, incline press, reverse crunch, bench dead bug, dumbbell and barbell hip thrust and bridge, clamshells, donkey kick, the hip and leg-curl machines, the lying dumbbell hamstring curl, sled push, rower intervals and ski erg.
- `[[kits]]` takes optional `weights` and `unit`; `./sweatcast check` lists a fault in them, and the setup skill asks for them.
- `knowledge/programming.md`: sourced sections on muscle coverage and recovery, exercise order, rest between intervals (an all-out effort gets at least four times its length in rest), effort by ear (the talk test and a ten-point scale) and stretching dose (about thirty seconds a hold, on as many days as the week allows), and a warm-up study that found no extra reps.
- `knowledge/injury-playbook.md`: the ankle's order of loading after a sprain, from the 2021 clinical practice guideline, and a balance-programme trial; sources for the foot, calf, hamstring and groin, which had none.
- `knowledge/kits.md`: what the session tool prints for a kit, and equipment notes for dumbbells (handling, changing weights, naming them), the single kettlebell, bike setup and pedals, resistance scales by feel, the rower's damper, the treadmill's belt-change time, and a hotel room without a mat.

### Changed
- The session tool reads the clinician's `Avoid:` lines in `me/health.md` itself, on every run; the skill no longer copies them into `--avoid` by hand, and `./sweatcast check` names any word in them that isn't a movement or flag. (Copied by hand, a ban was easy to leave off, and the plan then offered the movements it banned.)
- When straight sets would drop a movement pattern for time and paired sets drop fewer, the session runs paired sets and names what they still drop, so a short strength or general session covers more of the major groups. A targeted session keeps its own method.
- Paired-set markers count only the pairs ("Pair 1 of 2"), not a lone last slot.
- Safety: a delicate area still rules out all impact work, but fast work only when it loads that area, counting the foot, ankle and calf as one chain: fast seated punching stays in for a delicate foot, while a fast pedal stroke stays out for a delicate calf. With an off-limits ankle and a delicate foot, the finisher and intervals had no movement at all; they now get seated conditioning.
- Intervals add the strength fallback when fewer than two movements reach the level's leading effort (hard above novice), not when fewer than two are anything but easy, so one hard movement no longer leads every interval.
- Safety ratings, from a review of the new entries and a check against an off-limits ankle: push-ups, pike push-ups and the forearm plank rate ankle 1 and foot 2 (the toes bear weight), bridges and hip thrusts ankle 1 and foot 1 (the feet press the floor), so an off-limits ankle leaves the one-leg bridge on the healthy side; the world's greatest stretch rates the front ankle and foot and carries `overhead`; the half-kneeling stretch and press rate the front foot; the rower, air bike, sled push, ski erg and stick drills gain the wrist, elbow, shoulder, neck or foot loads they had left out. Curls rate wrist 1, like the rows that hold the same dumbbell. Band external rotation is done seated. The supine twist rates ankle 1, since dropping the knees rolls the foot onto its outer edge. The bike's standing climb rates ankle 2 and calf 2, like the stair climber. The treadmill run's setup says the hard pace its effort grade means.
- `programming.md` no longer points at the removed `exercise-science.md`, and a test checks it.
- Eval: `docs/eval/results-2026-10-22-run4.md`, a targeted run of the ten cases whose skeletons changed most plus an off-limits-ankle case: every case safe, and the ten cases' mean total rose from 15.2 to 16.4; the writer's brief coaches from the new notes.

### Not yet
- Interval doses don't yet follow the new rest rule: a twenty-second sprint inside a forty-five and thirty interval rests under three times its length, where `programming.md` now asks four.
- A circuit doesn't group floor stations and bench stations, so a listener who can't push through one foot makes many floor transitions.
- Coaching notes have no limit-specific lines (head position under a delicate neck, the injured foot's place), so the script adds them from the health lines.
- Forty-four drafts remain (barbell and machine extras, some mobility, the overhead seated punches); `./sweatcast movements` lists none of them.

## [6.0.0] - 2026-10-22

sweatcast renders on a Windows PC with an NVIDIA GPU as well as on an Apple Silicon Mac. Chatterbox Coach runs there from Resemble AI's own PyTorch Chatterbox Turbo on CUDA, cloned from the same reference clip.

### For forks
Breaking: the Python environment and the voice settings change shape.
1. Rerun `./sweatcast setup` after pulling. `pyproject.toml` now gives MLX to macOS and PyTorch to Windows, and `uv.lock` resolves for those two systems only, so an environment synced on any other system needs `SWEATCAST_PYTHON` (as CI does) or a fork of its own. The Mac's locked versions are unchanged.
2. A voice's `.json` may carry a `"torch"` table (`model`, `revision`, optional `generate`) for Windows; the top-level settings stay the Mac's. A private Chatterbox voice in `me/voices/` gets one from `voices keep`; add it by hand to an existing one (copy it from `voices/Chatterbox Coach.json`) to render that voice on Windows.
3. On Windows, render the smoke test once per voice: each backend's model is measured on its own.
4. Context files don't change format; there is nothing to migrate. `deliver_to` may now be a list, one folder per computer.

### Added
- A PyTorch backend in `tools/engines.py`: Chatterbox Turbo (`ResembleAI/chatterbox-turbo`, pinned) through `chatterbox-tts` 0.1.7 on CUDA 12.4 builds of PyTorch 2.6, with the reference clip encoded once per render. On an RTX 2080 Super it rendered at about 0.52 times the speech's length.
- `tools/voices.py` picks the backend from the system (`SWEATCAST_BACKEND` overrides it), takes each voice's model for it, lists it in `./sweatcast voices`, and downloads it with `voices download`.
- `tools/locks.py`: one exclusive file lock for the render lock and the pace file, flock on a Mac and msvcrt on Windows.
- `deliver_to` takes a list of folders; each build copies to the ones that exist on the computer it runs on.
- The build record names the backend and its runtime versions.

### Changed
- `./sweatcast`, `build.sh` and `setup.sh` find the Windows venv's Python (`.venv/Scripts/python.exe`); `./sweatcast build` and `setup` run through Git Bash's `sh` on Windows and keep their exit codes. Setup checks for an NVIDIA GPU on Windows and names the winget packages for ffmpeg and uv.
- A render on Windows marks the `coverage` package absent before loading the model, since `tools/coverage.py` would otherwise pass for it and break numba's import under librosa.
- The build-script tests run on Windows too (no `execv` in the stub, forward slashes in the test profile's TOML); the read-only-folder test is skipped there. The tests pin the Mac backend unless a test asks for PyTorch.
- README, CLAUDE.md, `knowledge/voices.md` and the setup skill describe both systems.

### Not yet on Windows
- Qwen3 Coach and voice design (`voices design`) stay Mac-only: a Qwen3 voice lints on Windows, and its render says to pick a Chatterbox voice.

## [5.4.0] - 2026-10-22

### For forks
Nothing to migrate. To back up your context, make `me/` its own private repo (README, "Back up `me/`"); rerunning `./sweatcast setup` adds `me/.gitignore` if it has none.

### Added
- `./sweatcast backup` (`tools/backup.py`): commits everything in `me/` and pushes it, when `me/` is its own git repo, nested in the engine's folder and ignored by the engine's git. It changes nothing when `me/` isn't its own repo, and refuses to push to a repo GitHub reports as public.
- The workout skill's last step runs it, after the build and the log, so each session lands in the listener's private repo.
- `me.example/.gitignore`: leaves the clip cache (but not the voices' measured pace), MP3s, render logs, unkept voice takes and migration backups out of that repo. Setup copies it into a new `me/` and adds it to an existing one.

## [5.3.0] - 2026-10-22

### Changed
- Safety: an off-limits ankle or foot now rules out anything done standing, which puts weight through both feet whatever the catalog rates the ankle, and the seated bikes and air bikes rate ankle 1 and foot 1, so an off-limits ankle keeps them out while a delicate one still allows them. A case `--limit` line says "and nothing done standing", and the injury playbook says both.

## [5.2.0] - 2026-10-22

### Changed
- `./sweatcast build` removes the local MP3 once every copy in the profile's `deliver_to` folder is in place and matches; `me/workouts/` keeps the script's `.txt` and `.build.json` as history. A failed copy, or no delivery folder, keeps the MP3 in `me/workouts/`.
- The setup skill's delivery step says so, and a request to change where workouts go runs that step alone; the profile template's `deliver_to` comment matches.

## [5.1.0] - 2026-10-22

Intervals that fit their movements and leave the work quiet, and a cleaner engine. Re-judged, the twelve conditioning cases rose from a mean total of 13.4 to 16.3 (efficacy 2.67 to 3.67, adherence 3.17 to 3.92, ease 2.75 to 3.67, safety 4.83 to 5.00); `docs/eval/results-2026-10-22-run3.md` has the run.

### For forks
Nothing to migrate. `knowledge/exercise-science.md` is gone and the tools no longer read `me/exercise-science.md`; `./sweatcast check` notes a leftover copy, which you can delete once anything worth keeping is copied out.

### Added
- `[hold]` in a draft: a segment with a hold keeps its full planned length, its spare time silent at its bare holds, so timed work isn't talked through; `[hold 20s]` is exactly that much silence. A held segment is never flagged short. The lint, the layout and the render share it, and `knowledge/tts-rules.md` and the workout skill say how to use it.
- An intervals block whose strength fallback is all on the floor runs as a circuit: one interval of each movement a round ("Round 2 of 4, glute bridge").

### Changed
- A timed movement shorter than the interval's work (a twenty-second sprint) works for its own seconds and rests the rest of the interval.
- Above novice, an interval block repeats the strongest hard movement before a moderate one leads it; the steady block goes on a machine, even one an interval used, before floor work.
- The workout skill and research agent no longer draw exercise-science asides; form cues stay cues.
- README and CLAUDE.md tightened: the README's layout is by folder, its voice section points at `knowledge/voices.md`, and both describe `[hold]`.
- `./sweatcast build` no longer passes the profile's `words_per_minute`, which only `./sweatcast lint` without a voice uses; the template and the check say so.

### Removed
- `knowledge/exercise-science.md`, `me.example/exercise-science.md` and the listeners' copies; the completed plans and specs in `docs/superpowers/` and the old productization notes in `docs/research/` (the session-structure research the session rules cite stays).
- Dead code: `paths.DRAFTS`, `paths.VENV_PYTHON`, `sessions.choose_method` (tests use `ranked`) and an unused branch of `voices.seed_pace`.

## [5.0.0] - 2026-10-22

The fixes from the second judged run of the grid: interval work that is hard enough, warm-ups that start easy, paired sets that can be spoken as pairs, rests that match the clock, and caps on volume. The catalog and the session rules each move up a format.

### For forks
Breaking: the catalog moves to format 3, `knowledge/sessions.toml` to format 2, and paired-sets drafts get a marker per pair set. After pulling:
1. If you keep private movements in `me/movements.toml`, they are now loaded (4.x ignored the file). Run `./sweatcast check`: every finished conditioning entry needs `effort = "easy"`, `"moderate"` or `"hard"`, and it lists any entry missing one or carrying another fault. Until it is fixed, a faulty entry is held back as a draft and never planned.
2. A fork that edits `knowledge/movements.toml` or `knowledge/sessions.toml`: set `format = 3` and `format = 2`, add `effort` to every finished conditioning movement, and keep the new dose keys (`bodyweight_reps` above novice, `efforts_per_session`) in every conditioning level. `./sweatcast test` names anything missing.
3. Drafts written under 4.x markers still render. A new paired-sets draft is written under one marker per pair set ("Pair 1 of 3, set 2 of 3: ..."), a circuit round's marker names the rest that ends it, and interval markers are numbered by block.
4. No context file changes; there is nothing to migrate.

### Added
- `effort` on every conditioning movement (easy, moderate, hard). Interval work never takes an easy movement; above novice the hard ones rank first.
- An interval fallback: when fewer than two locomotion movements are hard enough today (a thin kit, a delicate limit), timed squat, lunge, hinge and core work joins the intervals, with a warning.
- A steady block after the intervals for the time past the new `efforts_per_session` cap, and the `hard_sets_per_session` cap now holds for straight and paired sets.
- A printed finisher dose (`Finisher: 240 s, 4 rounds of 30 s on, 30 s off`), in the skeleton and its marker.
- `bodyweight_reps` above novice (10 to 15 experienced, 12 to 20 advanced), used for any movement with no load equipment.
- A case `--limit` prints what it rules out ("light loads only on the left calf, no impact or fast work").
- `me/movements.toml` is loaded, and `./sweatcast check` lists problems in it.
- Finished entries: step jacks, air bike steady and sprint, stair climber, standing climb, leg extension, arm circles, shoulder rolls, leg swings, standing calf stretch.
- `docs/eval/writer.md`, the script writers' brief, and `docs/eval/results-2026-10-22-run2.md`, the second judged run: safety 4.72, efficacy 3.05, adherence 3.45, ease 3.00 (first run 4.70, 2.33, 2.80, 3.52). Its ten lowest cases, rewritten and re-judged after these fixes, rose from a mean total of 11.7 to 14.6 (efficacy 2.3 to 3.2, adherence 2.7 to 3.6, ease 2.3 to 3.4, safety level at 4.4); two of the three safety points they still lost (low back loads on the half-kneeling press and the treadmill run) are fixed in the catalog since, and step jacks now carry a light groin rating.

### Changed
- Candidate ranking: with load on hand, strength movements that use it rank ahead of bodyweight ones at the same level (goblet squat before air squat, face pull before the towel door row); with a cardio machine on hand, conditioning on it ranks ahead of the floor.
- The warm-up list starts with easy locomotion and never offers hard, fast or impact work; the finisher list takes hard, then moderate conditioning; the cool-down leads with box breathing; none leads with a movement the work uses.
- Paired sets: one marker per pair set, a printed rest after each pair set, each station's transition every set, and pairs that cross families to the end.
- Straight sets print the rest their seconds hold; a circuit prints the rest between its rounds, now its own 45 to 90 s, and its patterns add vertical push, vertical pull and anti-rotation.
- Intervals keep one machine's blocks together, give thirty seconds to change equipment, number markers by block, repeat no movement while another remains, and raise the rest before the work. Interval rounds per movement start at three or four. A circuit takes no barbell lift.
- Targeted sessions give each target pattern two slots; a muscle target matches a movement's first two muscles. Patterns holding a liked movement come right after the targets.
- A healthy-side-only slot is timed for one side.
- Flow runs two mobility drills to each breathing one.
- Safety: a low back off limits also rules out spine flexion and twisting; the overhead presses rate neck 2, so a delicate neck rules them out; the face pull rates wrist 1; treadmill runs, jumping jacks, high knees, the standing climb and the half-kneeling press rate low back 1; step jacks rate groin 1. The playbook says the first two.
- An unreadable `me/movements.toml` is skipped with a warning instead of stopping every tool.
- The towel door row's setup names the door to use (an inside door that opens away from you, never the room's entry door); the world's greatest stretch keeps the head in line.
- The judge prompt reads the writer's notes, scores adherence on the coaching alone, and compares with an earlier run only after scoring blind. The workout skill describes the new markers and attributes clinician rules to the clinician.

## [4.0.0] - 2026-10-22

Sessions built from atomic movement data: the catalog says what each movement loads, a tool picks the method, the timing and the candidates, and a judged grid of forty cases measures how the result reads.

### For forks
Breaking: the context files move to schema 3, the catalog's tags and groups are gone, and one command flag changes. After pulling:
1. Run `./sweatcast migrate` (`./sweatcast setup` runs it too). It backs up your folder first, then adds the new fields to `profile.md` and `health.md`.
2. Run `./sweatcast check`. It lists the experience level to fill in (novice, experienced or advanced; a profile with none is planned as a novice until it is set) and each injury that needs a `[[limits]]` row in `health.md`. It exits 1 until they are written. An injury outside the thirteen areas takes no row: list it as "- Unlisted: <what>" and put any movement ids or flags to avoid on an "Avoid:" line under `## Clinician rules`.
3. `./sweatcast movements --group` is now `--pattern`, and `--avoid` takes movement ids or flags, not tags.
4. A private `me/movements.toml` entry needs `patterns`, and the other new fields, to leave draft.
5. The log's `format:` now records the method's name.

### Added
- `./sweatcast session`: given a goal, minutes and a kit (`--kit`, `--preset` or `--equipment`), it prints the health limits and warnings, the method, the timed slots with ranked candidates, the warm-up, finisher and cool-down candidates (screened against the limits), the patterns dropped for time and the equipment that would open up more movements. `--draft` prints only the `@@ <seconds> | <title>` markers. Options: `--method`, `--level`, `--target`, `--limit area=level[:side]` and `--avoid`.
- `knowledge/sessions.toml` and `tools/sessions.py`: the session methods (straight-sets, paired-sets, circuit, intervals, tabata, bike-intervals, flow, skill) and the dose rules per intensity and level, every number marked as sourced or a house default.
- `[[limits]]` rows in `health.md`: an area, side, level (off-limits or delicate), optional `flags` and `rehab` (both validated), and a note. Both-side limits also check the load on the resting side.
- The profile's `[[kits]]`, `experience`, `likes` and `dislikes`, and `./sweatcast get experience`.
- An optional `rpe:` on log lines, reserved for later progress tracking.
- The judged eval grid in `docs/eval/`: forty cases over four invented listeners, a judge prompt, and `results-2026-10-22.md`. Means over the forty cases: safety 4.70, efficacy 2.33, adherence 2.80, ease 3.53. No case scored safety 1.
- `knowledge/programming.md`: the programming reference behind the dose rules.

### Changed
- Catalog format 2: each movement carries its patterns, muscles, how much it loads each joint area (with `support` for the resting side), flags, intensity, level and timing; unfinished entries are drafts.
- `./sweatcast movements` filters by pattern, with `--level`, `--pattern` and `--avoid` (ids or flags). `./sweatcast coverage` reports by pattern.
- The injury playbook is organized by area and tolerance: what off-limits and delicate mean, the signs that let a limit loosen, and the red flags that stop a session.
- The workout skill plans from `./sweatcast session`; the setup skill collects experience, kits and limits. One check-in rule, and the check runs first.
- `./sweatcast check` lists a missing experience level, malformed limit rows, and prose injuries without a limit (an issue).

### Removed
- `knowledge/injury-rules.toml` and the phase model, the catalog's tags and groups, and `./sweatcast movements --group`.

## [3.1.0] - 2026-10-21

### Added
- The movement catalog, `knowledge/movements.toml`: every movement a session can use, with its equipment, muscle groups, spoken setup and cues, and tags for what it loads, plus kit presets. `tools/catalog.py` reads and checks it.
- `./sweatcast movements`: lists the movements a kit allows (`--preset` or `--equipment`), minus any `--avoid` tags, by group.
- Weekly counts in `./sweatcast coverage`: a group the last seven days neglected comes first, even when the last session touched it.
- Plural-tolerant name matching: a logged "goblet squats" or "right glute bridge" resolves to the catalog movement.

### Changed
- The equipment library is now `knowledge/kits.md`: what each kit usually holds and how to script around it. Its movement lists moved to the catalog.
- The workout skill picks movements from the filter's output, avoiding the injury playbook's new "Tags to avoid early" for each injury in an early phase, then applies the health file and the playbook on top.

## [3.0.1] - 2026-10-21

### Fixed
- Inconsistent injury tags in `knowledge/equipment-library.md`: a movement now carries the same tags everywhere it appears (the strictest set), and movements that load a joint but had no tags now have them.
- Removed listener-specific names: a named gym and a bike brand left two headings, which now read "Full gym" and "Stationary bike".

## [3.0.0] - 2026-10-21

Simpler to set up and to run: one `./sweatcast` command, the profile's settings in one block at the top, a check that says what's still to fill in, and a voice designer for a coach that sounds the way you want.

### For forks
Breaking: commands, the profile's format and the Python they run on all change. After pulling:
1. Run `./sweatcast setup`. It migrates `me/` (backing it up to `me/.backup-<date and time>/` first). In `profile.md`, the Voices list, "Copy finished MP3s to:", "Measured words per minute", the YouTube favorites and Puzzles handles, and the Feeds section move into a TOML block between `+++` lines at the top. Their lines leave the prose, and one sentence says where they went. The other context files only change their front matter. `./sweatcast migrate --dry-run` shows what would change. A 1.x folder migrates in the same run.
2. Run `./sweatcast check`. It lists anything the tools can't read and any line still showing the template's `[hint]`.
3. Call tools as `./sweatcast <command>`: `python3 tools/feeds.py` is `./sweatcast feeds`, `tools/build.sh` is `./sweatcast build`, `LINT_ONLY=1 tools/build.sh` is `./sweatcast build ... --lint-only`, `ALLOW_ESTIMATED=1` is `--allow-estimated`, `python3 tools/context.py log-session` is `./sweatcast log-session`, and `voices.py --measured` and `--download` are `voices measured` and `voices download`. `./sweatcast help` lists everything. The project permissions now allow `./sweatcast` instead of each tool.
4. The tools need Python 3.11 (the project's `.venv`); the Mac's own `python3` no longer runs them. Tests run with `./sweatcast test`.

### Added
- **`./sweatcast`**, one command for everything, run in the project's environment: `setup`, `build`, `lint`, `render`, `voices`, `feeds`, `coverage`, `youtube`, `check`, `get`, `deliver`, `log-session`, `migrate`, `cache`, `test`. `./sweatcast setup` needs no Python first. One permission rule covers every command the skills run.
- **Voice design:** `./sweatcast voices design "<name>" "<description>"` renders takes of a coaching line in a voice made from a written description (Qwen3-TTS VoiceDesign, pinned; about 4.5 GB the first time). `./sweatcast voices keep <take> --engine chatterbox --default` makes the chosen take a private voice in `me/voices/` and adds it to the profile. The setup skill offers it during the interview, for a woman's voice, say, or another accent; `knowledge/voices.md` has a "Design a voice" section.
- `./sweatcast check` flags every profile line still showing the template's `[hint]`, any feed not filled in, and a missing voice. It also notes, without failing, a missing delivery folder or no feeds.
- Schema 2 and its migration step, chained after 2.0.0's, with tests that migrate 1.x and 2.x folders.
- Tests for the wrapper, voice design and keeping, adding a voice without losing the settings' comments, and the new check: 102 in all.

### Changed
- The profile's settings live in TOML front matter (`+++`), read with Python's own `tomllib`: `voices` (`[[voices]]` name and description; the first is the default), `deliver_to`, `words_per_minute`, `youtube_favorites`, `puzzles` and `[[feeds]]` (label, kind, value). The tools no longer depend on how a line in the prose is worded.
- `./sweatcast feeds` skips feeds that aren't filled in yet, rather than listing them as failures.
- `tools/youtube.py` no longer restarts itself under `.venv`; `./sweatcast` runs everything there.
- The README's getting started is three steps: install ffmpeg and uv, clone, say "set me up". There's also a commands table.
- The setup skill writes the settings block, offers a designed voice, and runs `./sweatcast check` until it passes. The workout skill uses `./sweatcast` throughout.

### Removed
- Running the tools with the system `python3`, the `LINT_ONLY` and `ALLOW_ESTIMATED` environment switches, and `voices.py --measured` and `--download`.

## [2.0.0] - 2026-10-21

The engine's audit, fixed: one owner for the listener's files with a versioned format and a migration, safer state on disk, a privacy guard that checks every commit, consistent exit codes, and a record of how each MP3 was made.

### For forks
Breaking: the context files now carry a format version, and tools refuse an older folder until it's migrated. After pulling:
1. Run `tools/setup.sh` (or `python3 tools/migrate.py`). It backs up `profile.md`, `health.md`, `log.md` and `exercise-science.md` to `me/.backup-<date and time>/`, then adds a three-line front matter (`---`, `schema: 1`, `---`) to the top of each. Nothing else in them changes. `--dry-run` shows what it would do.
2. Run `python3 tools/context.py check`. It lists any line the tools can't read, such as a log line with a field missing, with its line number.
3. Clips cached before 2.0.0 render once more, since the cache key now includes the mlx-audio version. Right after upgrading, `python3 tools/cache.py prune --days 0` frees the old ones (it removes every cached clip, so run it before your next build, not after).
4. If you call the tools from your own scripts: a mistyped command now exits 64, not 2. The lint's word-count option is `--word-tolerance` (it was `--tolerance`). `tools/feeds.py` prints only the weather unless you pass `--print`. The draft functions (`parse`, `plan`, `spans`, `layout` and the timing constants) moved from `tts_build.py` to `tools/draft.py`, and the engine code from `render.py` to `tools/engines.py`.

### Added
- `tools/context.py`, the one reader and writer of the context files: the schema check, `get default-voice | wpm | voices`, `deliver` (the delivery folders that exist), `log-session` (adds a checked session line to `me/log.md`) and `check`. `build.sh`, `setup.sh`, `coverage.py`, `feeds.py` and `youtube.py` read the profile and log through it instead of six separate parsers. The workout skill logs sessions with `log-session` instead of editing the log by hand.
- `tools/migrate.py`, with a backup and `--dry-run`. `tools/setup.sh` runs it when a context folder already exists.
- A record of each build: `<name>.build.json` beside the MP3 and a line in `me/workouts/.logs/builds.jsonl`, with the draft's hash, voice, model and revision, mlx-audio and ffmpeg versions, seed, clip counts, timing and drift. Each build's render log is `me/workouts/.logs/<name>.log` instead of one shared temporary file.
- `tools/cache.py`: the clip cache's size, and `prune [--days 45]` for clips no build has read in that long. Renders mark each clip they read.
- `tools/cli.py`: the exit codes in one place (0 done, 1 issues, 2 drift, 3 unmeasured voice, 64 command mistake) and an argument parser that exits 64.
- `tools/draft.py` (the draft model and timing layout) and `tools/engines.py` (everything tied to mlx-audio and huggingface_hub internals, with a warning when the installed mlx-audio isn't the tested one).
- `tts_build.lint()` returns a `Report` (rows, issues, drift, warnings), so the lint's findings can be checked without reading its printout. The printed output is unchanged.
- Tests for all of the above, `build.sh`'s exit codes (through a stand-in Python), the pace file, the privacy hook on temporary repositories, the render lock, migration, and the feed limits: 94 in all, passing on Python 3.9 to 3.14.

### Changed
- Only one render runs at a time: a second one, such as a full build started while the prerender is still going, waits for the first and then reuses its clips.
- `tools/feeds.py` prints only the weather and any failed sources. Headlines and captions are outside text, so they stay in the sheet for the research agent, and the main session no longer reads them. The workout skill takes the weather from that printout. `--print` prints the whole sheet.
- Editing `me/health.md` asks for permission (an `ask` rule in `.claude/settings.json`). The workout skill only edits it at the check-in, while the listener is there, so the unattended part of a session still runs without prompts.
- The render releases the voice model's memory before assembling and encoding the MP3.
- `--tolerance` passed to `tools/build.sh` now sets the allowance for the lint as well as the render.

### Fixed
- One damaged write to `voice-pace.json` could erase every voice's measured pace: an unreadable file was treated as empty, then overwritten. The pace file is now written under a lock, to a temporary file that's renamed into place. A damaged one is moved aside as `voice-pace.json.corrupt-<time>` instead of overwritten, and the render checks it before loading a model rather than after rendering.
- The pre-push hook checked only the last commit of a push, so a personal file committed and then removed in a later commit still went out. It now checks every pushed commit, and so does CI. The three copies of the private-path list (hook, CI, test) are now one file, `tools/hooks/private-paths`. CI and the test had been missing the old-layout `knowledge/health.md`. A commit that only deletes such a file is allowed, so a leak can be cleaned up.
- A mistyped render option exited 2, which `build.sh` and the skill read as "the workout ran long". It now exits 64 and shows the error. An unknown voice exits 64 with the list of voices, instead of reporting that the voice "hasn't been measured".
- The lint re-read the pace file twice for every clip. It now reads it once per lint, so a render finishing mid-lint can't change the prediction partway through.
- `tools/feeds.py` fetches only http and https addresses, reads at most 5 MB of each, and builds its TLS settings on first use rather than on import.
- `tools/youtube.py` refuses a video id with path characters, finds `@handles` under Content first, and writes transcripts as UTF-8.
- The render finds ffmpeg's loudness figures by their keys and explains a failure, rather than taking the last `{` in its output.

## [1.1.0] - 2026-10-21

The voices are named for the models that speak them, the model downloads are explained, and Chatterbox's speech tokenizer is held to its pinned version at render time too.

### For forks
Nothing has to change: the old names still work. To use the new ones, rename the voices under Voices in `me/profile.md` (keep the `  - <name>: ...` format). Measured pace and cached clips carry over, since they're keyed by the voice's clip, not its name.

### Changed
- Coach E is now **Chatterbox Coach** and Coach G is **Qwen3 Coach** (`voices/`, the docs, the skills and `me.example/`). A voice is a reference clip spoken by an unmodified model, so the name says which model and what role. The old names are kept as aliases in each voice's `.json`.
- The `setup` skill runs `tools/setup.sh --no-models` first and downloads only the voice the user picks, after saying how big it is, instead of fetching the default voice's model before the interview.
- `tools/voices.py --download` prints each download's size; `tools/setup.sh` explains that no Hugging Face account is needed.

### Added
- A "Voice models" section in the README and "Downloading the models" in `knowledge/voices.md`: what each voice downloads and how big it is (about 3.3 GB for Chatterbox Coach, 4.2 GB for Qwen3 Coach), when downloads happen, that no account is needed, offline use, freeing space, and licenses.
- `tools/setup.sh --no-models`.
- An `"aliases"` setting for voices: older names that still find the voice.
- Tests for aliases and the tokenizer pin: 60 in all.

### Fixed
- Chatterbox Turbo's speech tokenizer is loaded at the revision `tools/voices.py` pins. mlx-audio asked for its latest version at every render, so the pin only applied to setup's download, and a failed load was only a warning that could leave the voice quietly wrong. A render now fetches the pinned version first and stops with a clear message if it can't.

## [1.0.0] - 2026-10-21

sweatcast becomes a forkable product: three layers (engine, voices, your context), its own Python environment instead of VoiceStudio's, and an onboarding skill.

### For forks
Breaking: the listener's files moved into `me/`, and VoiceStudio is no longer used. After pulling:
1. Move your files first: `mkdir me`, then `knowledge/profile.md` to `me/profile.md`, its "Active injuries and limitations" section into `me/health.md` (see `me.example/health.md`), `log.md` to `me/log.md`, `workouts/` to `me/workouts/` (including `.audio-cache/`, which holds your voices' measured pace), and `me.example/exercise-science.md` to `me/`. Then `git rm -r --cached knowledge/profile.md log.md workouts` so git stops tracking them.
2. `brew install uv` (and `ffmpeg`, if it's missing), then run `tools/setup.sh`. It builds `.venv` from `uv.lock`, leaves your existing `me/` alone, and installs the pre-push hook. Your downloaded models are reused.
3. In `me/profile.md`, replace the "Google Drive folder (My Drive) for finished MP3s: <folder>." line with `- Copy finished MP3s to: ~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>` (any synced folder works now).
4. A voice whose `.json` named no model now names one explicitly; its measured pace is filed under the model's name, so render the smoke test with it once (`tools/build.sh voices/smoke-test.draft.txt "smoke-test" --voice "<name>"`). Voices saved in the VoiceStudio app (OmniVoice) no longer work; recreate one as a reference clip in `me/voices/` (see `knowledge/voices.md`).
5. The VoiceStudio app can be uninstalled.

### Added
- **Your context in `me/`** (git-ignored; `SWEATCAST_HOME` moves it): `profile.md`, `health.md` (injuries, split out of the profile), `log.md`, `exercise-science.md` (facts verified in your sessions), `workouts/` and private `voices/`. `me.example/` is the template.
- `tools/paths.py`: one place for every path, so no tool hard-codes a personal file.
- **Own runtime:** `pyproject.toml`, `uv.lock` and `.python-version` pin Python 3.11, mlx-audio 0.5.0, mlx 0.32.1, numpy 2.2.6 and yt-dlp; `tools/setup.sh` builds `.venv`, copies `me.example/`, installs the privacy hook and downloads the default voice's model (`--all` for every voice).
- **Pinned models:** each voice's `.json` names its model and Hugging Face revision, and Chatterbox Turbo's speech tokenizer is pinned in `tools/voices.py`, so every copy renders with the same weights. `tools/voices.py --download` fetches them.
- **Delivery to any folder:** the profile's `- Copy finished MP3s to: <path>` line (iCloud Drive, Google Drive, Dropbox or any folder; `~` and `*` allowed) replaces the Google Drive-only copy.
- **`setup` skill:** "set me up" interviews a new listener (basics, kits, health with a not-medical-advice note, interests and feeds, voice, delivery), writes `me/`, checks the feeds, and renders the smoke test.
- **Privacy guard:** `tools/hooks/pre-push` refuses to push `me/` or an old-layout profile, log or workouts folder; CI checks the same.
- **CI:** a GitHub Actions workflow runs the tests on every push and pull request.
- Tests for voice lookup (private voices first, pinned revisions on shipped voices), a fresh copy running on `me.example/`, a missing context folder, and nothing personal being tracked. Test drafts are synthetic fixtures in `tests/fixtures/`: 55 tests in all.

### Changed
- `tools/build.sh`, `tools/render.py` and `tools/youtube.py` run on the project's `.venv` (or `SWEATCAST_PYTHON`) instead of VoiceStudio's bundled Python. Renders are unchanged: Coach E still renders at about 0.68 times real time.
- The workout skill reads `me/` and the shared knowledge, takes kit options and injury phase criteria from your own files instead of the author's, and writes only inside `me/`. `.claude/settings.json` allows edits to `me/**` only.
- `CLAUDE.md` and the README describe the product and the three layers rather than one listener; the author's first-person framing moved to their own profile.
- The smoke test moved to `voices/smoke-test.draft.txt` and no longer mentions any one person's injuries.
- The clip cache key includes the model revision, so clips rendered before 1.0.0 render once more.

### Removed
- OmniVoice and every VoiceStudio dependency: the VoiceStudio voice database, OmniVoice's text helpers, the OmniVoice render options (`--steps`, `--guidance`, the temperatures, `--speed`) and the re-launch under VoiceStudio's Python.
- The author's profile, log, drafts, scripts and research from the public repo's current tree. They remain in the git history of earlier versions.

## [0.6.0] - 2026-10-21

New content sources, a weekly feed kind for them, and an open-source license.

### Added
- A `weekly` feed kind in `tools/feeds.py`: the newest two items from the last eight days, for weekly podcasts and puzzles that the 72-hour news window would miss.
- New feeds in `knowledge/profile.md`: The Fiddler and NPR's Sunday Puzzle (puzzles), BBC's More or Less (numbers in the news) and No Such Thing As A Fish (fun facts).
- New YouTube favorites for deep dives: Freakonomics Radio and Marginal Revolution University.
- The quiz can now use a puzzle from The Fiddler or the Sunday Puzzle as well as MindYourDecisions. Since their answers come out a week later, research takes the earlier puzzle that the newest post solves, and credits the source.
- `LICENSE` (MIT), and a License section in the README.
- A test for the weekly feed kind: 50 tests in all.

### Changed
- Video transcripts (`workouts/research/videos/*.txt`) are kept out of git, since they're the channels' own text. The deep-dive summary sheets are still committed.

## [0.5.0] - 2026-10-21

Timing that holds the whole workout to plan instead of every segment, and brain teasers for the quiz.

### Added
- `tools/youtube.py puzzles`: lists recent videos from a new Puzzles line in `knowledge/profile.md` (Presh Talwalkar's MindYourDecisions) that haven't been used as a quiz yet. The headlines agent picks one that works by ear, saves its transcript and writes `workouts/research/puzzles/<id>.md` (the puzzle as said aloud, the answer and the reason); a puzzle with a sheet isn't offered again. The session's quiz beat uses it when there is one, and falls back to the session's own material.
- `tts_build.layout`, one timing layout shared by the lint's prediction and the render, so they agree.
- Tests for the new timing and the puzzle list: 49 in all.

### Changed
- A segment with time to spare widens its paragraph breaks (up to about two seconds each), keeps a short tail and ends early instead of padding with silence. A segment that runs long is still paid back from the next ones' spare time.
- Only the whole workout is held to plan, within three percent either way. The lint prints the predicted length and blocks only when the total is off by more than that, or when a segment is far off its slot (under 80 or over 110 percent of it, down from 90 to 100). The render exits 2 only when the finished workout is more than three percent over or under plan; `--tolerance` now sets that total allowance.
- The workout skill, `CLAUDE.md`, `README.md`, `knowledge/tts-rules.md` and `knowledge/voices.md` describe the new timing and the puzzle quiz.

## [0.4.0] - 2026-10-21

Feeds before research, faster renders, a voice that's measured before it's trusted, and more variety: bells inside intervals, session types, video series and load tracking.

### Added
- `tools/feeds.py`: fetches the feeds listed in a new Feeds section of `knowledge/profile.md` (team results and next games from ESPN's schedules, weather from Open-Meteo, local, science and tech headlines from RSS, and Wikipedia's on-this-day events) into `workouts/research/<date>-feeds.md` in about a second. The workout skill runs it first, and the headlines agent reads it before searching, on a smaller search budget (eight searches, down from twelve).
- A `[chime]` marker that rings the segment bell inside a segment, for the changes in an interval. The lint counts its time.
- A three-note rising tone at the end of every MP3, so the end of the workout can't be mistaken for a dropped earbud. `--no-chime` leaves it out with the segment bells.
- `--clips-only` for `tools/build.sh` and `tools/render.py`: render and cache a draft's clips with no lint or MP3. The skill starts it on the first half of a draft while it writes the second.
- Structure warnings in the lint: a segment that opens without a locator, more than one countdown in a segment, more than two exclamation points, or a short praise line used three or more times. They don't block a build; `--strict` makes them count.
- `format:` and `loads:` fields in each `log.md` session line. `tools/coverage.py` prints the last format, so the next one differs, and each movement's last load, so the plan progresses from it. The two logged sessions are backfilled.
- Video series: a long video's sheet can be split into parts (`- Parts: 3`), `tools/youtube.py pick` lists a series in progress first, and `tools/youtube.py done <id>` marks a part told.
- Workout skill: session types (strength, mobility and breathing, stickhandling skills, seated bike intervals, a ten-minute snack); a "how did last session feel" check-in question when there's room; a quiz beat each session; the books pillar in rotation; a morning weather preview, plus the shape of the day from the calendar when a calendar connector is available.
- `tools/voices.py --measured <voice>`, which exits 0 once a voice's speaking rate has been measured.
- Tests for all of the above: 46 in all, still with no models or network.

### Changed
- Chatterbox Turbo encodes the voice's reference clip once per render instead of once per clip. The clips are byte-identical, and a render takes about 6 percent less time.
- An unmeasured voice's speaking rate now starts at the median of the measured voices instead of its reference clip's own rate, which was about 30 percent slow. Coach G was predicted at 9.8 characters a second that way; it measures 14.8.
- `tools/build.sh` refuses a session render with a voice whose rate hasn't been measured (exit code 3) and prints the smoke-test command that measures it. The smoke test itself always renders, skips the Drive copy, and its lint never blocks it. `ALLOW_ESTIMATED=1` overrides the refusal.
- The lint's character weights are vendored from OmniVoice into `tools/char_weight.py` (Apache 2.0, header kept), so the lint runs on any Python 3 for Chatterbox and Qwen3 voices. A test checks the copy still matches OmniVoice's whenever VoiceStudio is installed.
- `tools/youtube.py` loads yt-dlp only for the commands that need it, so it can be imported and tested anywhere.
- Coach G's model is downloaded and its rate measured with the smoke test. Its render speed is about 1.45 times the speech's length, not 1.3.
- The smoke test's close opens with "That was the whole test", so it passes the new locator check.

## [0.3.0] - 2026-10-21

A chime that marks each segment, coach-style cues, a coverage check from the log, and tests.

### Added
- A soft two-note chime at the start of every segment after the first, so you can keep time by ear even when a cue comes out garbled. The lint counts its time. `--no-chime` leaves it out.
- `tools/coverage.py`: reads `log.md`, maps each logged movement to the whole-body checklist, and lists the groups the last session left out and the movements to avoid. The workout skill runs it before planning.
- `tests/`: fast checks for parsing, pauses, the lint, segment timing, the chime and coverage, with no models (`python3 -m unittest discover tests`).
- A `"generate"` field in `voices/<name>.json` for per-voice engine settings.
- Coaching voice guidance in `knowledge/tts-rules.md` and the skill: short cue sentences, mid-set check-ins, long sentences only for stories.

### Changed
- The workout opening uses a one-line version of the safety rules when nothing has changed since the last session. The full version is still used for the first session, any change at check-in, or a gap of more than fourteen days. Both versions name every rule.
- Engine settings and clip trimming are now part of each clip's cache key, so changing them re-renders instead of reusing old clips. Existing cached clips re-render once.
- `tools/build.sh` stops with a clear message when it can't find the default voice in the profile, and says why when it skips the Google Drive copy, instead of quietly falling back.
- `tools/render.py`: segment layout moved into its own function, `assemble`, so it can be tested.

### Fixed
- Coach E's expressiveness settings (`exaggeration`, `cfg_weight`) were hard-coded for Chatterbox, but Turbo ignores them, so they never had any effect. They're gone from Coach E, and `knowledge/voices.md` explains how to use them with the full-size model.

## [0.2.0] - 2026-10-20

A natural coach's voice, cleaner timing, and better content, after the first full listen.

### Added
- Chatterbox Turbo and Qwen3-TTS engines in `tools/render.py`, through `mlx-audio` in VoiceStudio's bundled Python. Chatterbox Turbo renders at about 0.75 times the length of the speech on an M3.
- Voices kept in the repo (`voices/<name>.wav`, `.txt`, `.json`), with the engine and model per voice. Two coach voices: Coach E (Chatterbox Turbo, the default) and Coach G (Qwen3-TTS).
- Measured speaking rate per voice and model, recorded by each render and used by the lint to predict length.
- Lint check for paragraphs over twenty-two seconds, where engines drift and glitch.
- `--model`, `--guidance`, `--class-temperature` and `--position-temperature` render options.
- Workout skill: a whole-body coverage check (push, pull, hinge, hamstrings, quads, hip abductors and adductors, anti-extension and lateral core, arms) and a both-sides-by-default rule with injury-safe alternatives.
- Workout skill: two current science and technology breakthroughs in each session's research; exercise science becomes a one-line aside.
- `VERSION`, `CHANGELOG.md` and a release process in `CLAUDE.md`.

### Changed
- A segment's spare seconds are spread over its paragraph breaks instead of sitting at the end, and a segment that runs slightly long borrows from the next one's padding.
- Engine silence is trimmed from each clip's ends.
- Render timing excludes the model load.
- Docs rewritten for the new voices and engines: `README.md`, `CLAUDE.md`, `knowledge/voices.md`, `knowledge/tts-rules.md`, the workout skill.

### Removed
- The VoiceStudio Gallery voices from the profile; they sounded mechanical on OmniVoice. OmniVoice still renders voices saved in the app.

## [0.1.0] - 2026-10-19

First working version.

### Added
- The `workout` skill: check-in, plan, background research, script, build and log.
- `tools/build.sh`: lint, `.txt` export, OmniVoice render with per-segment padding and loudness normalization, and a copy to Google Drive.
- Spoken-length prediction per VoiceStudio voice.
- `tools/youtube.py` for video deep dives from favorite channels.
- Profile, injury playbook, equipment library, exercise science and text-to-speech rules.
