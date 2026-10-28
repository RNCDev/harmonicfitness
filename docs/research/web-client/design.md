# sweatcast web: design spec

Status: research, 2026-10-27. Not scheduled for a release. This spec covers what the web client does and how it is built. It takes no position on visual or interaction design: layouts, styling and component choices belong to the UI design files beside it in this folder.

## Intent

sweatcast works well as a CLI under Claude Code or Codex, but only for someone comfortable running an assistant in a terminal on their own computer. The web client opens it to a small group of people the maintainer knows: same engine, same safety rules, same kind of MP3, in a browser.

The product is one screen in two parts:
- **The chat** (multi-modal: text, plus whatever the user attaches or the agent shows): where the user says what they want and the agent talks back.
- **The panel**: what the chat needs the user to look at, check, fill in or edit (a profile form, a check-in, a workout plan, render progress, an audio player, coach samples, analytics). The agent decides what the panel shows; the user can also act in it directly.

Success: someone in the group goes from "build me a 25-minute hotel workout" to an MP3 in their ears with no terminal, no install and no files on their computer, and the workout is as safe and as good as one made with the CLI.

## Goals

1. **Recognise new and returning users.** A new user goes into setup. A returning user is asked "what do you want to do today?", with these doors:
   - **Build a new workout:** a chat whose open details (length, kit, goal, the check-in) are fillable in the panel.
   - **Edit my stuff:** profile, training, content and health in the panel.
   - **Something hurts:** a quick injury update that tightens limits, short of a full profile edit.
   - **Coaches ("tell me about my coaches"):** hear samples, switch, or make a web coach of their own.
   - **Show me around:** a guided tour of what sweatcast does.
   - **Analytics:** history and patterns from the log (sessions, patterns covered and neglected, loads over time, feedback).
   - **Feedback on older workouts:** when a user returns with workouts they haven't commented on, the app asks about them ("got any feedback on some of our older workouts?"). It replaces an immediate "how did it go?", because users often leave while a render runs.
2. **Same engine, same guarantees.** The brief, the safety screen, the menu gate, the lint and the render are the existing Python engine, unchanged in behaviour. A workout that the CLI would refuse is refused here too.
3. **Bring your own keys** for both the language model (Claude, OpenAI or Gemini: the user's choice) and the voice (Fish Audio, ElevenLabs, Gemini or Inworld: the services in `knowledge/services.toml`).
4. **Per-user isolation.** One user can never read or affect another's data, keys, jobs or audio.
5. **Work that survives a closed tab.** Research, writing and rendering run as background jobs; the user can leave and come back to a finished workout.
6. **Usable on a phone**, since people will open it right before training. How the two parts adapt to a small screen is for the UI designs.

## Non-goals

- **Local voices.** No Pocket TTS, no PyTorch, no take checker on the server. Web coaches only. The ten local coaches are not offered on the web.
- **Replaying past workouts.** Each workout carries that day's weather, news and filler; it is not meant to be played again. Past workouts appear in history and analytics, not as a library.
- **Week planning.** Filler content is tied to the day; no multi-day plan.
- **Permanent audio storage.** The MP3 is kept for a limited time for download, and the app says so.
- **Writing to a folder on the user's computer.** Delivery is a download.
- ~~**Public sign-up.**~~ Changed 2026-10-27 by the maintainer: anyone can make an account with a username and password, while registration is open; a setting (`WT_REGISTRATION=closed`) shuts it. The group is still meant to be small.
- **Replacing the CLI.** The CLI stays the primary product and keeps working exactly as it does.

## Anti-goals (a failure even if it technically works)

- A workout built from a movement the user's limits rule out, or any weakening of the menu gate, the safety screen or the red-flag stop, for any provider or model.
- A user's keys or health details visible to another user, or in plain text anywhere: a table, a log, an error report.
- The engine forked into a web copy that drifts from the CLI's.
- A user charged by a voice service for audio they never get (renders lost when they leave, a retry loop that re-bills).
- A system that only works with one language-model provider.

## Constraints

- **The engine is the source of truth.** Everything in `tools/` and `knowledge/` is used as is. Changes the web needs (a web-only mode, for example) go into the engine as general features, with tests, released by the CLAUDE.md rules, and must not change CLI behaviour.
- **The engine reads its context folder once per process.** `tools/paths.py` computes `HOME` and every path from `SWEATCAST_HOME` at import. So each user's engine work runs in its own process, never in a shared process switching folders.
- **Keys reach the engine as environment variables.** The engine reads the environment before `me/.env`, so no `.env` file is ever written to disk on the server.
- **Every engine write goes through the engine.** Log lines through `log-session`, filler through `content log`, health and profile through `tools/context.py`'s formats. The web layer may store the files but doesn't invent its own formats for them.
- **The context schema still applies.** Stored context files carry `schema = 6` (or later); `./sweatcast migrate` brings stored folders up to date when the engine version changes.
- **Hosted on Railway.**
- **Small group.** Optimise for simplicity and correctness, not scale. Tens of users, not thousands.

## The how, as decided

### Stack (option A)

- **Server:** Python, FastAPI. The engine is imported or run from it; one back-end language.
- **Agent loop:** Python, provider-agnostic tool calling across Anthropic, OpenAI and Gemini (Pydantic AI or a thin adapter of our own: the builder's call).
- **Worker:** a separate Python process for agent runs and renders, fed by a Postgres-backed job queue (no Redis).
- **Front end:** a React + TypeScript single-page app, built and served by the FastAPI service.
- **Database:** Postgres.
- **Object storage:** an S3-compatible bucket (Railway's own buckets or Cloudflare R2) for MP3s and other short-lived files, with an expiry rule.
- **Where the code lives:** `web/` in this repo, versioned and released with the engine, so every web release runs the engine of the same commit and "no drift" is enforced by one test suite. `./sweatcast test` and CI cover `web/`'s tests too, and the privacy hook and `check-private.sh` apply to it as to the rest of the engine: no personal details in its code, tests or fixtures. The Docker image is built from the repo root.
- **Migrations:** stored context folders are brought up to date with `./sweatcast migrate` lazily, at the start of a user's next job after a deploy that raised the schema *(spec author's call)*.

### Railway layout

- Services: `web` (FastAPI, API and static front end), `worker`, Postgres. Staging and production environments in one Railway project.
- A Dockerfile with ffmpeg, installing the engine with `uv sync --locked` **without** the local-voice extra (no PyTorch, no models).
- Files move between services only through Postgres and the bucket, never a shared disk (Railway volumes attach to one service).
- Progress reaches the browser through server-sent events from `web`, fed by Postgres `LISTEN/NOTIFY` from the worker.
- The worker needs outbound access to the language-model APIs, the voice services' hosts and the research sources (feeds, Wikipedia, YouTube).

### Per-user isolation and the engine

- Each user's context (the files that make up `me/`: the four profile files, `health.md`, `log.md`, `movements.toml`, their own `coaches/`, `workouts/` records, research sheets, `told.jsonl`, `builds.jsonl`) is stored in Postgres, keyed by user, every query scoped by user id.
- **A job:** the worker writes that user's context out to a fresh temporary folder, runs the engine in a subprocess with `SWEATCAST_HOME` pointing there and the user's decrypted keys in its environment, then saves what changed back to Postgres and deletes the folder.
- **One job per user at a time.** A user's jobs run in order, so two jobs never write back the same files.
- The stock coaches (`coaches/`) and `knowledge/` come from the engine in the image, read-only and shared.
- The temporary folder lives for the whole job, so the build's own retry loop (lint, build, exit 2, adjust, rebuild) reuses its clip cache and only changed paragraphs are billed again.

### Jobs and conversations (spec author's call)

- **The workout skill already separates the parts that need the user from the parts that don't.** The check-in (and setup's questions, and the edit and injury doors) are short interactive turns. Each turn is its own short job: write the folder out, run, write back. Nothing holds a worker while a reply is pending.
- **After the check-in, one long unattended job:** research, brief, design, write, lint, build, upload, log. The user can leave. Research runs here, after the check-in, rather than alongside it as in the CLI. That costs a minute of wall time and keeps every user's input out of the long job.
- **Questions inside the long job** (the brief's one "would open up" equipment question) are put to the panel with a short timeout, then the skill's default is taken ("unanswered means no").
- **Write-back is per file, with a version check.** Each stored file has a version. A job writes back only the files it changed, and only if their version hasn't moved since the job read them. Panel edits during a running job (say, `health.md` during a render) are saved at once. The job's write-back of a file the user also changed is a conflict, and the user's edit wins. The CLI rule that `health.md` changes only at the check-in means the long job never writes it. A health edit made mid-render takes effect from the next workout, and the panel says so.

### Keys

- Envelope encryption: each user's keys (language model and voice) are encrypted with a per-user data key, which is wrapped by a master key held only in a Railway environment variable, never in Postgres.
- Keys are decrypted only inside the worker, only for the length of a job, and passed only into the job's environment.
- The engine's key scrubbing (`redact.scrub`) already applies to everything it prints; the web layer scrubs its own logs and error reports the same way.
- Keys are never shown again after entry; the user can see which services have a key and replace or delete one.

### The agent

- One agent loop serves every provider. Its instructions are ported from the skills (`workout`, `setup`, `coach`) and the knowledge files they point to. Where the skills name Claude Code tools, the web agent has its own equivalents:
  - **Engine tools:** each `./sweatcast` command the skills use (`check`, `brief`, `build`, `get`, `coaches`, `content`, `coverage`, `feeds`, `youtube`, `log-session`, `movements`) is a typed tool. Exit codes and typed errors become structured tool results the model can act on, as the skills already describe.
  - **Asking the user** (AskUserQuestion in the skills) becomes a tool that puts a question or form in the panel and waits for the answer.
  - **Showing** (the plan table, a coach sample, render progress, the finished MP3) becomes a tool that puts a result in the panel.
  - **Writing the draft** is a tool that writes only the current workout's draft file.
  - **Research** (background agents in the skills) runs in turn inside the job, as the Codex harness already does. Web search uses each provider's own search tool (Anthropic's web search, OpenAI's web search, Gemini's Google Search grounding), behind the same adapter as tool calling, billed to the user's key. Page fetches are a server tool with the skill's budgets. *(Spec author's call: no third-party search key.)*
- The agent has no shell and no general file access.
- **The web instructions are generated from the skills, not hand-written** *(spec author's call)*: a generator in the engine, like `./sweatcast harness sync`, writes them from `.claude/skills/` plus a mapping of each Claude Code tool to its web equivalent. A test fails when they are out of step, as the harness test does for Codex.
- **Model quality** *(spec author's call)*: before a provider is offered, its recommended model runs the eval grid in `docs/eval/` with the same writer and judge briefs as a CLI release, judged by the same Claude model, paid for by the maintainer. It must score no lower than the CLI's last release run on any safety item, and within one point of it overall. The grid runs again for each provider at each minor release. Each provider has one recommended model.

### Workflows (behaviour, not presentation)

- **New user:** make an account (username and password), setup (the setup skill's quick start, web version): name, experience, kit, injuries, the disclaimer and red flags, a language-model key, a voice key, a stock web coach for that service (made in their account, saying so and the cost first), then a ten-minute workout. "Finish setting me up" stays available.
- **Import from the CLI (one time):** an existing CLI user can upload their `me/` folder (as a ZIP) once, during or instead of setup. The import runs `migrate` on it, then `check`, and shows what came in and what `check` found. It never takes `.env` (keys are entered in the app), the clip cache, render logs, auditions in progress or MP3s. After import, the web store and the CLI's folder are separate: no sync in either direction. Export (below) gives a folder back in the same format.
- **Build a workout:** the workout skill, in order: the check-in (limits, readiness, goal, length, kit, coach), research, the brief, design, the plan shown, write, lint, build, deliver, log. After the check-in, the user can leave. The privacy line comes before the first web build, and must now also cover the language-model provider, which sees the profile and health details too.
- **Edit my stuff:** the panel edits the context files through the engine's formats; `./sweatcast check` runs after a change and its findings are shown.
- **Something hurts:** the check-in's limits logic on its own. A lasting change goes into `health.md` with the user's permission; a red flag stops and suggests a clinician, as in the skill.
- **Coaches:** samples of the stock web coaches and their own; switch; make a web coach of their own (describe, audition across the keyed services, approve and name: the coach skill), with candidate audio served to the panel.
- **Feedback on older workouts:** delivered workouts with no feedback are offered on return; answers go under Feedback in `log.md`.
- **Analytics:** read-only views from `log.md`, `builds.jsonl` and `coverage --json`.
- **Show me around:** a guided tour; content to be written.

### Delivery and storage

- The finished MP3 goes to the bucket under the user's prefix and is downloaded through short-lived signed links. It expires after a limited time (24 hours unless decided otherwise), and the app says so before and after the render.
- The workout's script (`.txt`), draft, brief, menu and build record are kept permanently in the user's store.
- `deliver_to` and `backup` don't apply on the web; the build runs with no delivery folder and keeps the MP3 in the job folder, from which the worker uploads it.

### Data and privacy

- Health data, the log and the keys sit on the maintainer's infrastructure. **The standard is careful handling, not zero access:** the maintainer holds the master key and could technically decrypt, so the safeguards are that nothing personal is ever stored, logged or reported in plain text. Encrypted at the application level, beyond the database's own disk encryption: the keys, every context file, the chat history and stored agent transcripts (both hold health details), and workout scripts. Decryption happens only in the worker and in the request serving that user.
- Users can export everything (their context folder as files) and delete their account, which removes their rows, their bucket objects and their keys.
- A short privacy page says what is stored, what goes to which provider (the language model sees the profile, health and log; the voice service sees the script), and that keys are the user's own.

### Engine changes this needs (expected, to confirm while planning)

- **A web-only mode,** so the engine treats local voices as unavailable and routes to web coaches, as it already does on Claude Code on the web (`CLAUDE_CODE_REMOTE`), without pretending to be that environment.
- **No delivery folder** handled as a normal outcome on the web (the build record already supports `kept_local`).
- Possibly machine-readable output (`--json`) on the commands the agent calls that don't have it yet.

## Left to the builder

- Agent framework (Pydantic AI or a thin adapter), job-queue library, ORM and migrations tool.
- Sign-in method (decided 2026-10-27: username and password, open registration with a switch, no email).
- Schema details: how context files map to tables (one row per file is the simplest fit), chat history storage, the job and event tables.
- Whether the voice-pace file and the clip cache persist between a user's jobs (it would save re-billing a rebuild in a later job; within one job it is already kept).
- Streaming format between worker, server and browser.
- Rate and spend guards beyond the engine's `cloud_max_chars`.
- Error reporting and monitoring.
- Everything visual and interactive: see the UI design files in this folder.
