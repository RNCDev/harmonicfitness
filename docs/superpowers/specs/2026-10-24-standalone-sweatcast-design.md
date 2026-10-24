# A standalone sweatcast: any reasonable computer, any voice engine

Status: approved 2026-10-24, ready for an implementation plan. Written against v8.0.1.

## Intent

A stranger clones `RNCDev/sweatcast`, opens it in Claude Code on their own computer (terminal, IDE extension or the desktop app), and types something like "setup sweatcast" or "let's create a routine". From that sentence to a workout MP3 in their earbuds, there should be no step that needs the README, no cryptic halfway failure, and no assumption that they own an Apple Silicon Mac or a Windows PC with an NVIDIA card.

Along the way they create their trainer: what the coach is like and how the coach sounds. That persona should belong to the listener, not to one audio engine, so they can render it on their own computer or send the script to a cloud voice service with their own API key, and hear the same coach either way.

Today's gaps, found on 2026-10-24:
- **Two prerequisites are installed by hand.** `tools/setup.sh` stops if `ffmpeg` or `uv` is missing and prints a Homebrew or winget command.
- **No git, no models.** Outside a git checkout (a GitHub zip download, or a copy without `.git`), setup's `git config core.hooksPath` fails under `set -e`. Setup then stops at step 3, before the voice model downloads.
- **Only two kinds of computer can make audio.** Rendering needs MLX on Apple Silicon or CUDA on Windows. `pyproject.toml` locks only `darwin` and `win32`, so `uv sync` fails on Linux.
- **No-GPU computers fail late.** On a Windows PC without NVIDIA, the render stops at load time ("PyTorch can't see an NVIDIA GPU").
- **Skills assume a Mac.** They use `afplay` to play voice samples.
- **Cloud sessions aren't recognized.** A Claude Code cloud session (web, mobile, desktop "Cloud") would try to set up and fail, or half-work and then lose everything.
- **A voice is welded to its engine.** Each voice's `.json` names one local engine, the shipped voices are named after their models ("Chatterbox Coach"), and designing a voice works only on a Mac.

## Goals

1. **First words to first MP3, with nothing read first.** Claude handles everything a stranger would otherwise need the README for.
2. **Know what this computer can do, and say it up front.** Before the interview, setup tells the listener which audio routes work here (local, cloud voice, or neither) and roughly how long a workout will take to render.
3. **A looser hardware bar for local audio.** It works on any reasonable 64-bit computer, fast with a supported graphics chip and slower without one.
4. **A cloud voice with the listener's own key (BYOK)**, as an option for anyone and the only route for computers below the bar.
5. **A trainer persona independent of the engine**, made by describing it, picking a take, and keeping that take as a clip.
6. **Existing installs keep working.** After `./sweatcast migrate`, today's listener on a Mac keeps their coaches (renamed as personas), cached clips, measured pace, downloaded models and delivery.

## Non-goals (for now)

- **Claude Code cloud sessions.** They're detected and declined (see Part A), even when a cloud voice would technically make audio possible there.
- **A sweatcast that writes workouts without Claude.** The CLI stays the toolbox Claude drives.
- **Local rendering on Intel Macs.** Neither MLX nor current PyTorch builds support them. Intel Macs get the cloud voice route.
- **AMD or Intel graphics acceleration** (ROCm, DirectML). Those computers render on the processor or use a cloud voice.
- **Several listeners in one folder, or sharing personas between people.**

## Anti-goals: failures even if it technically works

- **An API key ends up anywhere but `me/.env`.** That rules out the engine repo, the listener's private `me/` backup repo, a render log, a build record, the clip cache key, and the chat.
- **Health details reach a cloud service unannounced.** Setup says plainly, once, that the script goes to the service and can mention injuries ("easy on that left knee"), before any script goes there.
- **Surprise costs.** A listener should never learn what a workout cost from their bill.
- **The coach changes from line to line.** Nothing renders from a description alone. A persona always has something fixed: a clip, a saved voice ID at a service, or a stock voice.
- **Setup fails halfway with a message only a developer understands.** A computer that can't make audio is told so at the start, with the alternative.
- **Today's listener is broken.** No existing voice, cached clip, measured pace or setting stops working without a migration step that `./sweatcast migrate` performs.

## Constraints

- **Priorities**, in CLAUDE.md's order: safe for the listener's body today, clean to the ear, worth listening to.
- **Tools** run only through `./sweatcast`. Context files are read and written only through `tools/context.py`, and paths come only from `tools/paths.py`.
- **Engine contract.** An engine returns `say(text, seed)` producing 16-bit mono PCM at 24 kHz (`tools/engines.py`). `render.py`'s clip cache, loudness pass, timing layout and build record sit on top of that contract and should not need to know which engine spoke.
- **Pace is per voice and engine.** It's keyed by voice, engine and model in `voice-pace.json` (`voices._rate_key`). It moves into each persona's `pace.json` (Part D), and a new engine is measured by the existing smoke test before it renders a session (exit 3 until then).
- **Pinned environment.** Python 3.11 through uv, pinned by `uv.lock`, with Hugging Face models pinned to revisions. Cloud services are pinned to a named model ID where the API allows.
- **CI** runs the tests on Ubuntu with no models, no network and no personal files. New code is testable that way, for example with a local fake HTTP server for cloud engines.
- **Privacy.** `tools/hooks/private-paths` and the pre-push hook still guard the engine repo. `me/.gitignore` guards the private repo.
- **Release rules** follow CLAUDE.md. Personas, the profile's route list and the models folder change the context layout, so this is a major release with a "For forks" section and a `tools/migrate.py` step (`SCHEMA` 3 to 4).

## What the listener decided

- **Who it's for:** a stranger who cloned the repo, using Claude Code on their own computer, whose first words are casual ("setup sweatcast", "let's create a routine").
- **Cloud sessions are skipped for now.** When setup detects one, it explains that audio there would be unstable, very slow and not durable, suggests running locally, and sets nothing up.
- **Keep a minimum reasonable hardware bar, but loosen the NVIDIA requirement.**
- **A BYOK cloud voice route.** The key lives in an ignored `me/.env`. Setup tells the listener roughly what a workout costs, and that the script goes to the service and can mention their injuries.
- **The persona flow:** describe the trainer, listen to a few takes, keep one as the persona's clip in `me/`. Whatever engine renders, local or cloud, copies that clip. Stock voices stay as a quick option. A description alone is never used to render.
- **The cloud services to enable:** Cartesia, ElevenLabs, PlayHT, Fish Audio and Deepgram, each one that is possible (see "Cloud voice services").
- **Personas, not voices:**
  - Every coach has a person's name, and no starter personas ship.
  - Each persona is a folder in `me/personas/`, with the personality inside it.
  - The listener's current Chatterbox Coach becomes Coach Julius, and Qwen3 Coach becomes Coach Solo.
- **A stable of coaches:** a workout uses the last-used coach unless the listener asks for another or for a new one. "I want a new coach" starts the coach-design flow.
- **Models in a git-ignored `models/` folder** at the repo root, which can be a symlink to a central location.
- **Testing without extra hardware or accounts:**
  - There's no test computer beyond this Mac (and the existing Windows PC), so processor rendering ships as experimental.
  - The four cloud services are scaffolded and tested against a fake server, without buying accounts.
  - The listener has a Fish Audio key, so Fish Audio also gets a live test. It's already in their `me/.env` as `FISH_AUDIO_API_KEY`, and `.env` is now ignored by the private `me/` repo.
  - ElevenLabs, Cartesia and Deepgram are labeled "not yet tried live" (in the readiness check, setup, and docs) until someone runs a real workout through each.
- **The build happens in a new session**, from this design.

## The design

Four parts, in release order. Each can ship on its own.

### Part A: setup that a stranger can't trip over

**Readiness check.** A new command (my call: `./sweatcast doctor`) prints, in plain lines:
- the system, chip, graphics, memory and free disk
- whether `ffmpeg`, `uv`, `git` and the Python environment are present
- which voice models are downloaded
- whether `me/` exists
- **which audio routes work on this computer**: local (and how fast, once measured), cloud voice (whether a key is set), or neither, with the one thing that would change that

The readiness logic must work before the Python environment exists, so it runs from `tools/setup.sh` or another shell script. The Python tools can share the same checks once the environment is there. Setup and the setup skill both run it first.

**Cloud sessions.** Detect them with `CLAUDE_CODE_REMOTE=true`, which Claude Code sets in every cloud session and never locally (code.claude.com/docs/en/cloud-environments). Setup, the setup skill and the workout skill then stop before installing or interviewing. They explain, in a few plain lines:
- the cloud machine has no graphics card
- rendering would take a very long time
- downloading the voice model is blocked by the default network settings
- the listener's profile, injuries and log would vanish when the session ends

They then suggest opening the repo in Claude Code on the listener's own computer. A hidden override (an environment variable) lets a developer run setup there anyway for testing.

**Prerequisites.**
- **uv:** when it's missing, the setup skill offers to install it with Astral's official installer, which needs no admin rights. It asks first, since that runs a downloaded script.
- **ffmpeg (my call):** sweatcast uses only `ffmpeg` (loudnorm and libmp3lame), not `ffprobe`. So the environment can carry a pip-provided static ffmpeg (for example `imageio-ffmpeg`) as a fallback when none is installed, which removes the manual prerequisite. The builder verifies that the bundled binary has libmp3lame and loudnorm on every platform, and falls back to an install offer if not.
- **git:** setup checks for it and keeps going without it (see the next item).

**Outside git.** Setup skips the privacy-hook step when the folder isn't a git checkout. It says why, and continues to the models. `./sweatcast backup` and the hook already need git, and they explain themselves when it's missing.

**A copied folder.** `uv sync` already rebuilds a `.venv` whose Python is gone (tested 2026-10-24). Keep a test for it. When `me/` arrives with a copied folder, setup treats it as an update, as it does today. The readiness check notes any `deliver_to` folder that doesn't exist on this computer.

**Skills:**
- The setup skill's trigger description adds "set up sweatcast", "setup sweatcast", "install sweatcast" and "get started".
- The setup skill's Voice step becomes creating the listener's first coach (Part D). It comes after the route is settled, since the route decides which designer is available.
- The workout skill already sends a listener with no profile to setup.
- Replace `afplay` with SendUserFile when it's available. Otherwise use the system's player (`open`, `xdg-open` or `start`), or give the path.
- Where a skill names Homebrew, name the right installer for the system instead.

**README:** rewritten for the stranger. One paragraph on what it is, one on what you need (Claude Code; the rest is handled), then "open it in Claude Code and say set up sweatcast".

### Part B: local audio on more computers

| Computer | Local engine | Status |
|---|---|---|
| Apple Silicon Mac | MLX (Chatterbox Turbo, Qwen3) | Unchanged |
| Windows with NVIDIA | PyTorch Chatterbox Turbo on CUDA | Unchanged |
| Linux with NVIDIA | PyTorch Chatterbox Turbo on CUDA | New (my call; the listener said not to assume a Mac or Windows) |
| Windows or Linux without NVIDIA | PyTorch Chatterbox Turbo on the processor | New, slow |
| Intel Mac, or below the memory or disk floor | None | Cloud voice route |

- The PyTorch engine picks its device (CUDA, else the processor) instead of stopping when CUDA is missing.
- Add `sys_platform == 'linux'` to `[tool.uv] environments` and to the dependency markers, and relock.
- **The local engines become optional (my call).** Today `uv sync --frozen` fails on an Intel Mac (MLX is locked for arm64 only, and torch only for Windows), so the very computers sent to the cloud route couldn't install the lint and research tools. And a computer on the cloud route would still download 2 to 4 GB of PyTorch.
  - The base environment (lint, research, build, cloud engines) installs on every supported system, Intel Mac included.
  - The local engine packages are an optional extra installed only when the readiness check says local audio works here and the listener wants it: MLX on Apple Silicon, CUDA PyTorch with an NVIDIA card, CPU PyTorch without one. The builder chooses how, for example uv extras with conflicting indexes.
  - Setup's order becomes:
    1. the readiness check (shell)
    2. the base environment
    3. the interview, which settles the route
    4. the local engine extra and its model, when the route is local
  - The disk floor applies only to the local route.
- **Processor rendering ships as experimental.** It's untimed: the listener has no computer without a graphics card to measure it on.
  - Until a listener's own smoke test has run, the readiness check and setup say "experimental, speed unknown, likely slow" rather than quoting a time.
  - The smoke test records render speed (seconds of rendering per second of speech) alongside pace. After it, they quote an expected time for a 30-minute workout from this computer's own figure.
  - If that comes out far over an hour, setup recommends a cloud voice and leaves the choice to the listener.
- The memory and disk floors start as cautious guesses (about 8 GB of memory, and 6 GB free disk for the local route), stated as such. Below them, local audio isn't offered.

**Where the models live (the listener agreed).**
- Local models download into a `models/` folder at the repo root, ignored by git. It's engine-level, not inside `me/`: models aren't personal and stay out of the private backup.
- The tools point Hugging Face's cache there (`HF_HUB_CACHE`) for every download and load.
- `models/` may be a symlink to a shared location, for someone who keeps one central model cache. `SWEATCAST_MODELS` does the same job where symlinks are awkward (Windows needs admin rights or developer mode for them).
- The readiness check shows the folder's size and each model in it. It warns when the repo sits inside a synced folder (iCloud Drive, Dropbox, Google Drive, OneDrive), since gigabytes of models and `.venv` would sync.
- **Migration on this Mac:** about 7.5 GB already sits in `~/.cache/huggingface/hub` (Chatterbox Turbo, its tokenizer, Qwen3). Setup or migrate offers to move those model folders into `models/` rather than download them again. The pinned revisions are unchanged, so nothing re-downloads.
- Voice design's model goes there too, and is still removed after use as today.
- Qwen3 and local voice design stay Mac-only. Part D gives other computers a cloud designer.

### Part C: a cloud voice with the listener's own key

**Where the key lives.**
- The key goes in `me/.env`, one `NAME=value` per line, using each service's conventional variable name (for example `ELEVENLABS_API_KEY`).
- `me.example/.gitignore` and every existing `me/.gitignore` (added by `./sweatcast migrate` or setup) ignore `.env`.
- `./sweatcast backup` refuses to commit a `.env` even if the ignore rule is missing.
- The key is read only by the cloud engine, at render time. It's never printed, logged, put in a build record, or made part of a cache key.

**How the key gets there, without passing through the chat (my call).** A key pasted into Claude Code would sit in the transcript.
1. A small command (for example `./sweatcast keys init <service>`) creates `me/.env` if needed, with a commented line naming the variable and where to get the key.
2. Setup gives the listener the file's path (a clickable link in an IDE) and asks them to paste the key into the file themselves.
3. `./sweatcast keys` (and the readiness check) reports which services have a key set, never the key itself.
4. `.claude/settings.json` denies Claude `Read`, `Edit` and `Write` on `me/.env`, and the skills say never to print it.

**Choosing the route (my call: a preference list, so one synced profile works on every computer).**
- `me/` syncs between a listener's computers through `./sweatcast backup`, but `.env` deliberately doesn't. So the route is an ordered list in the profile, for example `render = ["local", "fish"]`, defaulting to `["local"]`.
- Each build uses the first route that works on this computer: local needs the hardware and the installed engine, and a service needs its key in this computer's `me/.env`. A fast Mac keeps rendering locally while a laptop without a graphics card uses Fish Audio, from the same profile.
- `./sweatcast build --engine <route>` overrides the list for one build.
- The readiness check reports which routes are usable here and which one a build would pick.
- With no usable route, setup walks the listener through getting a key.

**How a cloud engine fits.**
- It's an engine like the others, returning `say(text, seed)` with 24 kHz mono PCM.
- It requests raw PCM or WAV and resamples if the service can't do 24 kHz.
- It passes the seed where the API takes one.
- It uses the service's "previous text / next text" context where offered, so delivery flows across paragraphs.
- Everything above the engine is unchanged: the lint and its timing, `[hold]`, `[pause]`, the loudness pass, the MP3, the build record and delivery.
- `engines.runtime()` names the service and its model ID, so the clip cache and the pace file treat a cloud engine as a different speaker from the local one. Only changed paragraphs are sent again on a rebuild.

**Using the persona's clip.**
- **For a service that copies a clip:** the first build uploads the persona's clip and its words once to create the service's voice. It keeps the returned voice ID in the persona's `services.json` (Part D), keyed by the clip's hash and the service, so a changed clip creates a new voice.
- **For a service that renders from the clip on every request:** it sends the clip each time.
- **For a stock-voice service:** the persona names the stock voice and, where supported, a line of delivery instructions taken from the profile's Narrator section.

**Pace and cost.**
- The smoke test measures the voice on the cloud engine before the first session, as it does locally (exit 3 until then). It costs about 1,000 characters.
- **No rendering ahead on a cloud route (my call).** Today the workout skill starts `./sweatcast build --follow` as soon as the first segment is written, and every later edit renders that paragraph again. On a cloud route each of those would be billed, outside any estimate. So `--follow` and `--clips-only` are refused on cloud routes, and the workout skill skips its render-ahead step there. Only the final build sends text, after the lint and the menu check pass. Cloud requests run several at a time, so the overlap isn't needed for speed.
- Before sending anything, a build prints the characters it will send (only the paragraphs not already cached) and an estimated cost from a per-service rate in the engine's settings. Since only the final build sends, the estimate covers the whole workout.
- The build record logs the characters sent.
- **A spending ceiling by default (my call).** Builds run unattended after the check-in, so setup writes a per-build character ceiling into the profile when it enables a cloud route. A suggested 30,000 characters fits a 40-minute workout with room for retakes. Setup tells the listener the figure and its approximate cost, and a build that would exceed it stops before sending.
- **ElevenLabs' previous and next text:** the final build has every paragraph, so each request gets its real neighbors. Joins are best effort. A cached clip isn't sent again just because a neighboring paragraph changed.

**Failures.**
- Network errors and rate limits are retried with backoff.
- An authentication, quota or billing error stops the build with a plain message and a new exit code in `tools/cli.py`.
- Clips already rendered stay cached, so a rerun resumes where it stopped.
- Requests may run a few at a time, since no GPU is shared. The builder chooses how many, within the service's rate limits.

**What setup tells the listener, once, before the first cloud build:**
- the service and roughly what a workout costs there
- that the script goes to the service and can mention their injuries
- where the key is stored and how to remove it

**Which services ship first:** see "Cloud voice services" below.

### Part D: the trainer persona, independent of the engine

**What a persona is: a named coach, owned by the listener.** The listener decided:
- **No starter personas ship.** Every listener creates their own coach at setup.
- **Every coach has a person's name** ("Coach Julius", "Coach Maya"), never a model's name.

Each persona is one folder in the context folder:

```
me/personas/
  coach-julius/
    persona.md     +++ settings: name, description, per-engine settings
                   (preferred local model, each service's choices),
                   then prose: how this coach talks
    clip.wav       the sound: about ten seconds
    clip.txt       the clip's exact words
    pace.json      measured pace, one entry per engine and model (my call)
    services.json  voice IDs a service created from this clip, keyed by
                   clip hash and service (my call)
    takes/         design takes, before one is kept
```

- **The personality moves into the persona.** The profile's `## Narrator` section becomes the prose of the persona's `persona.md`, so two coaches can talk differently, not just sound different. The brief quotes the chosen persona's prose where it quotes Narrator today.
- **A stable of coaches, and the last one by default (the listener's rule).** A listener may keep several coaches. Each workout uses **the coach used last** unless the listener names another, or says they want a new coach.
  - "I want a new coach" (in any words, in setup or in a workout request) runs the coach-design flow below. It's one flow shared by both skills, so the builder may make it its own skill. A workout then continues with the new coach.
  - The last-used coach comes from the log. `./sweatcast log-session` records each session's coach (my call: the log, not the build records, since the log is the session's record and is backed up).
  - With no sessions yet, it's the coach made at setup.
  - The profile's `[[voices]]` list is replaced by the stable: every folder in `me/personas/`, so no ordering setting is needed.
  - The check-in doesn't ask which coach unless the request suggests a change. It just says who's coaching.
  - A build takes `--coach` (today's `--voice`, kept as an alias). The workout skill passes the resolved coach explicitly, so a build never guesses.
- **Whether the coach says their own name** in the welcome is left to `knowledge/script.md` (my call: sparingly, if at all).
- `persona.md` follows the context files' format (`+++` TOML block, `schema`) and is read and written only through `tools/context.py`. `me/personas/` is part of the private `me/` backup. `services.json` holds voice IDs, never keys.

**The shipped voices go away.**
- `voices/` stops holding coach clips. The engine repo ships no persona.
- The smoke-test draft moves somewhere neutral; the builder picks where.
- The tests use a small fixture clip in `tests/fixtures/`.
- CLAUDE.md's "Voices" layer, the README and `knowledge/voices.md` are rewritten to match.

**Creating a coach (a required setup step).** Setup can't finish without one, since nothing renders without a coach. The flow:
1. Name the coach.
2. Describe how they sound and how they talk.
3. Render a few takes.
4. Listen, keep one, and say what's wrong if none is right.

The takes come from the first of these that works on this computer:
1. **The local designer:** Qwen3 VoiceDesign on MLX, on an Apple Silicon Mac.
2. **A local PyTorch designer** on Windows or Linux. Qwen3-TTS was released for PyTorch and the MLX build is a port of it, so the builder checks whether the official VoiceDesign weights run under PyTorch (CUDA, or the processor slowly) and adds that path if they do.
3. **A cloud designer** with the listener's key: Fish Audio or ElevenLabs. The chosen take is downloaded and kept as `clip.wav`, so it travels like any other.
4. **A clip the listener brings:** about ten seconds of a voice with its words. A real person's voice needs that person's consent.

A listener on the Deepgram route picks a stock voice for the coach instead (see Cloud voice services). The persona then records that it has no portable clip.

**Switching engines** keeps the persona. Each engine copies the clip a little differently, and each needs its pace measured once (the smoke test).

**Migrating today's listener (this repo's owner).** `./sweatcast migrate` turns each voice the profile lists into a persona:
- **Chatterbox Coach** (formerly Coach E) becomes **`me/personas/coach-julius/`**, named "Coach Julius".
- **Qwen3 Coach** (formerly Coach G) becomes **`me/personas/coach-solo/`**, named "Coach Solo".
- The profile's `## Narrator` section moves into the default persona.
- Measured pace moves with each persona, and cached clips stay valid.

Since this release deletes the shipped clips from `voices/`, migrate has to get them somewhere else. The builder picks how, for example:
- keep them in a migration-only folder until the next major release, or
- read them with `git show v8.0.1:voices/...` when in a git checkout.

Migrate asks for a name for any listed voice it can't name. For forks, the CHANGELOG's "For forks" section explains the same steps.

## Cloud voice services

The listener asked for Cartesia, ElevenLabs, PlayHT, Fish Audio and Deepgram, each one that's possible. Research on 2026-10-24 from official docs and pricing pages (sources below) found four possible. PlayHT is not: Meta bought it (as PlayAI) in July 2025, its API was turned off that month, and play.ht no longer resolves.

Costs assume a 20,000-character workout. A 30-minute session's script runs about that long; recent 20 to 25 minute scripts ran 9,000 to 19,000 characters.

| Service | Carries the persona's clip | Designs from a description | Output | Seed | Context between paragraphs | Approx. cost per workout |
|---|---|---|---|---|---|---|
| **Fish Audio** | Yes, inline: the clip and its words go with every request (no saved voice to manage) | Yes, seeded, about $0.01 per request | WAV or PCM, sample rate chosen | Design only | Within one request only | About $0.30 ($15 per million bytes), pay as you go |
| **ElevenLabs** | Yes: an instant voice clone, uploaded once, used by voice ID (Starter plan and up) | Yes (`/text-to-voice/design`), seeded previews | `pcm_24000` | Yes, best effort | Yes: `previous_text` / `next_text` | About $0.80 (Flash) to $1.60 (multilingual or v3 models) |
| **Cartesia** | Yes: an instant voice clone, uploaded once, used by voice ID (Pro plan, $5, and up) | No | `pcm_s16le` at 24 kHz | No | Only over WebSocket (`context_id`), not plain HTTP | About $1.00 on plan, $1.30 on overage |
| **Deepgram Aura-2** | No: stock voices only | No | `linear16` at 24 kHz (default) | No | No | About $0.60, pay as you go |
| PlayHT | Shut down | | | | | |

What this means for the design:
- **All four possible services ship.** Each is a cloud engine behind the same `say(text, seed)` contract. Suggested build order: Fish Audio, ElevenLabs, Cartesia, Deepgram.
  - **Fish Audio** first: it's the cheapest by three to five times, it takes the same WAV and transcript the local engines use, and it can design voices.
  - **ElevenLabs** next: it has the smoothest joins (seed plus previous and next text) and can design voices.
  - **Cartesia** after that.
  - **Deepgram** last: it's the stock-voice route, so the persona doesn't travel there.
- **Fish Audio requests are MessagePack, not JSON.** The builder chooses between a small pinned dependency and a minimal encoder for the few types needed. Its free model (`s2.1-pro-free`) has an announced end date (the blog and changelog disagree: August 31 or November 30, 2026), so nothing should depend on it.
- **ElevenLabs and Cartesia clone once.** The first build uploads the clip and keeps the returned voice ID (Part C). ElevenLabs asks the uploader to confirm they hold the rights to the voice. For an AI-designed persona that's the listener. For a recording of a real person, it's that person's consent, which the setup skill already requires. No service's terms address AI-designed voices directly (unconfirmed), so setup states this plainly rather than claiming certainty.
- **Cartesia and Deepgram have no seed.** Rebuilding a paragraph there gives a different take. That's acceptable, since the clip cache keeps what's already rendered.
- **Choosing Deepgram means choosing a stock voice (my call: no shipped pick).** Setup plays a few Aura-2 samples and the listener picks one. The choice is stored in the persona's `persona.md` settings, and a Deepgram build with no pick stops with a message saying how to choose. Setup says the coach will sound different from the persona's clip, and doesn't offer Deepgram for designing a persona.
- **ElevenLabs' model is the listener's choice (my call).** Setup offers Flash (about $0.80 per workout) and the multilingual or v3 model (about $1.60, more natural), quoting both prices. It suggests the more natural one, since CLAUDE.md puts a natural voice ahead of exact timing. The choice is stored per persona and pinned by model ID.
- **Key names:** `FISH_AUDIO_API_KEY` (the name the listener's key already uses), `ELEVENLABS_API_KEY`, `CARTESIA_API_KEY` and `DEEPGRAM_API_KEY`. The last three follow each SDK's convention, though none appeared in the docs read. Deepgram's header is `Authorization: Token <key>`.
- **Rate limits** are comfortable for about 150 paragraphs per workout. Fish's paid tier allows 5 concurrent requests and answers a 429 with no Retry-After header. Cartesia's Pro plan allows 3. Concurrency should be a per-service setting.
- **Prices change.** The per-service rates the cost estimate uses live in one table in the engine's settings, dated, so a release can update them. Each one is marked as approximate when shown to the listener.

Others checked and set aside: MiniMax (clones are deleted after a week unused, so it would re-clone each time), OpenAI (custom voices need a recording of the human speaker, and its current TTS model shuts down on January 6, 2027), Google Chirp 3 (custom voices are allowlist-only and need a human consent statement), Hume (its TTS API ends November 13, 2026), and Resemble AI (hosted voices' commercial status is unclear). fal.ai and Replicate host Chatterbox with a reference clip and are worth revisiting later.

Sources: elevenlabs.io/pricing/api, elevenlabs.io/docs/api-reference/text-to-speech/convert, elevenlabs.io/docs/api-reference/text-to-voice/design, elevenlabs.io/use-policy, cartesia.ai/pricing, docs.cartesia.ai/api-reference/voices/clone, docs.cartesia.ai/api-reference/tts/bytes, docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits, docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech, docs.fish.audio/api-reference/endpoint/openapi-v1/voice-design, fish.audio/blog/s2-1-pro-free-api, deepgram.com/pricing, developers.deepgram.com/reference/text-to-speech/speak-request, techcrunch.com/2025/07/13/meta-acquires-voice-startup-play-ai, dev.hume.ai/docs/text-to-speech-tts/overview, developers.openai.com/api/docs/guides/custom-voices.

## Left to the builder

- **Module layout:** where the cloud engines live, and whether they use the standard library's HTTP client or a new dependency. Prefer none.
- **Mechanics:** retry, backoff, concurrency, and the file that remembers a service's voice IDs.
- **The readiness check:** its exact output, its thresholds, and how the shell and Python versions share logic.
- **Names:** the readiness command's name, the profile setting's name, and the new exit code's number.
- **Migration mechanics:** the persona layout and the profile's coach settings change `me/`, so this is a `SCHEMA` bump (3 to 4) with a `tools/migrate.py` step, and a major release. The builder chooses how migrate gets the shipped clips after `voices/` loses them (Part D).
- **The smoke-test draft's new home**, and the fixture clip for tests.
- **Release split:** whether Parts A to D ship as separate releases. Suggested: A as a minor, and B, C and D together as the major (9.0.0), since personas, the profile's route list and the models folder all change the layout at once.

## Verification

**Tests (CI, no network or models):**
- setup outside a git checkout
- readiness output on faked platforms (Apple Silicon, Intel Mac, Linux with and without NVIDIA, Windows without NVIDIA)
- `CLAUDE_CODE_REMOTE=true` declines
- `.env` ignored, backup refuses it, and the key never reaches a build record, log or cache key
- each of the four cloud engines against a local fake HTTP server that mimics its documented API:
  - request shape (MessagePack for Fish, `Authorization: Token` for Deepgram)
  - PCM out, and resampling
  - retries on 429
  - an authentication failure's exit code
  - voice-ID reuse keyed by clip hash
  - the character ceiling
  - `--follow` refused on a cloud route
- `.claude/settings.json` denies Claude access to `me/.env`
- the route list picks the first usable route on faked computers
- persona creation from a cloud-designed take, and from a brought clip
- the last-used coach resolved from the log
- migration of a v8 `me/`: `[[voices]]` and Narrator into `me/personas/`, Chatterbox Coach to coach-julius and Qwen3 Coach to coach-solo, pace and cache intact

**By hand, with what's available (this Mac, the Windows PC, and a Fish Audio key):**
- **Fish Audio live, with the listener's key** (`FISH_AUDIO_API_KEY` in `me/.env`; Claude never reads the file, the engine does at render time):
  1. the smoke test with Coach Julius, to measure pace on Fish
  2. one short workout, comparing its timing and sound with the same coach rendered locally
  3. the cost estimate against what Fish reports
  4. a cloud-designed take from Fish's design endpoint
- a fresh clone into an empty folder on the Mac, then "setup sweatcast" in Claude Code, creating a coach and ending in a first MP3
- the same from a GitHub zip
- the Windows PC with CUDA hidden (`CUDA_VISIBLE_DEVICES=""`) as a stand-in for a computer without a graphics card: does processor rendering work at all, and how slow is it there?
- a Claude Code cloud session, which should decline
- this Mac's `me/` after `./sweatcast migrate`: Coach Julius renders with cached clips reused, pace kept, and models moved into `models/` without downloading again

**Left for later, and labeled so:** a live workout through ElevenLabs, Cartesia and Deepgram, once someone has an account; Linux; an Intel Mac.
