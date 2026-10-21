# Productization research: a forkable sweatcast

Status: written 2026-10-21 against v0.6.0. Most of phases 0 to 3 shipped in v1.0.0: the three layers with `me/` and `me.example/`, `tools/paths.py`, the project's own `uv` environment with pinned model revisions (VoiceStudio and OmniVoice removed), delivery to any folder, the `setup` skill, the pre-push privacy guard, CI and synthetic test fixtures. Still open: the private podcast feed, the context schema version and `tools/migrate.py`, a rolling log summary, `tools/upgrade.sh`, the plugin, and the PyTorch backend. The rest of this document is the original exploration, kept as written.

## The question

sweatcast works well for one person, but it's that person's repo. Their profile, injuries, workout log, voices, Google Drive path and Mac are all wired into it. Could it become one standalone repository that anyone can fork and make their own, with:
- the voice models,
- personal context files that keep evolving,
- clean pulls of the improvements from upstream?

## Recommendation in brief

Split the repo into three layers, and keep each one easy to swap out.

1. **Engine** (public, versioned): tools, the workout skill, tests and the shared knowledge (the text-to-speech rules, injury playbook, equipment library and exercise science).
2. **Voices** (public, small): reference clips and settings for each voice, which are about 1 MB. Model weights stay out of git. Each voice pins its model and revision, and a setup step downloads them.
3. **Personal context** (private, evolving): one `me/` folder holding the profile, health notes, feeds, the log and feedback, workouts and research. The public template ignores it in git by default, and the user can back it up to a private repo.

Do it in four phases. First, separate the personal files inside this repo. Next, replace the VoiceStudio runtime with the project's own Python environment. Then add an onboarding skill and pluggable delivery. Last, package for forking, and optionally as a Claude Code plugin. Each phase works on its own, so the project never stops working along the way.

## What exists today

| Layer | Files | Generic? | Notes |
|---|---|---|---|
| Engine | `tools/*.py`, `tools/build.sh`, `tests/` | Mostly | Personal paths are hard-coded in five tools (see the appendix). |
| Skill | `.claude/skills/workout/SKILL.md`, `.claude/settings.json` | Mostly | The examples are the author's (the ankle's phase criteria, the Tata quiz, "he"). |
| Project instructions | `CLAUDE.md` | No | Written in the first person by the author ("I listen to narrated workouts..."), with the author's Mac (an M3 with 16 GB) and GitHub repo. |
| Shared knowledge | `knowledge/tts-rules.md`, `injury-playbook.md`, `equipment-library.md`, `exercise-science.md`, `voices.md` | Yes | Useful to everyone. `exercise-science.md` grows as sessions verify new facts, which is a commons worth sharing. |
| Personal context | `knowledge/profile.md`, `log.md`, `workouts/**` | No | Includes health details and a neighborhood. They're public today, because the repo was made public as-is. |
| Voices | `voices/Coach E.*`, `voices/Coach G.*` | Yes | Synthetic voices made with Qwen3-TTS VoiceDesign from a text description, not cloned from a real person, so they're safe to ship. |
| Runtime | VoiceStudio's bundled Python (`~/Library/Application Support/VoiceStudio/runtime/project/.venv`) | No | A third-party app is installed only for its Python environment: mlx-audio 0.5.0, mlx 0.32.1, yt-dlp, numpy. |
| Models | `~/.cache/huggingface/hub` | n/a | About 2.8 GB for Chatterbox Turbo, 0.5 GB for its S3 tokenizer and 4.2 GB for Qwen3-TTS Base. They download on first use. |
| Delivery | `tools/build.sh` copies to `~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>` | No | macOS and Google Drive for desktop only. |
| Hardware | MLX | No | Apple Silicon only. |

## Goals and non-goals

Goals:
- A stranger can fork the repo, run one setup command and one onboarding conversation, and get a first workout MP3 within about an hour, most of it spent downloading models.
- Personal context is private by default and never mixed into the engine's files, so pulling upstream changes never conflicts with it.
- The context keeps evolving as it does today: the log grows, feedback becomes standing rules, the profile changes with injuries and equipment, and exercise science adds facts. It also stays readable and editable by hand.
- Releases keep following semver, with a context schema version, so a fork knows when its `me/` folder needs migrating.

Non-goals for now:
- A hosted service, accounts or a web app. sweatcast stays local-first, running on the user's own machine through Claude Code.
- Supporting every text-to-speech engine. Two good engines and a clean backend interface are enough.
- Medical advice. The injury playbook stays a conservative guide with a stop rule and red flags, and the docs say so.

## Design questions

### 1. Where does personal context live?

| Option | How it works | Pros | Cons |
|---|---|---|---|
| A. Edit in place (today) | Fork and edit `knowledge/profile.md` and `log.md` directly. | Nothing to build. | Every upstream pull conflicts with the personal files. A public fork exposes health data by default, which is exactly what happened here. |
| B. Template plus ignored `me/` | Engine files are tracked. `me/` is in `.gitignore`, and `me.example/` ships with placeholders. | Clean upstream pulls, private by default, one folder. | The context has no backup or history unless the user adds one. |
| C. Engine plus a separate private context repo | `me/` is its own private git repo, cloned inside the engine (ignored by the engine) or kept elsewhere and pointed to by config. | Backup and full history of how the context evolved, no conflicts, and it can be shared across machines. | Two repos to manage, and a little more setup. |
| D. Claude Code plugin plus a context folder | The engine installs as a plugin, and the user's context lives in whatever folder they open. | Updates with `claude plugin install`, and the context folder is just files. | Plugins can't ship a permissions allow-list (see question 5), and the Python environment and models still need a setup step. |

Recommendation: build B now, and make C a documented option ("`git init` inside `me/` and push it to a private repo"). Whichever folder layout wins, resolve every personal path through one small config module (`tools/paths.py`, reading `SWEATCAST_HOME` or defaulting to `./me`). That keeps D possible later without rewriting tools.

This repo needs a decision of its own. The author's context is public now. Moving it into `me/` and the author's own private context repo (option C) would let this repo become the clean public template. Git history would still hold the old files unless it's rewritten or a fresh public repo is started.

### 2. How the personal context is organized and how it evolves

Proposed layout:

```
me/
  profile.md        stable facts: basics, listening setup, equipment kits, interests, tone
  health.md         injuries, current phase, clinician rules, phase criteria (sensitive)
  feeds.md          the Feeds list (teams, weather location, RSS, puzzles)
  voices.md         which voices to use, default first
  log.md            one line per session (append-only)
  feedback.md       dated feedback, plus a "Standing preferences" section promoted from it
  summary.md        a rolling summary of the log, for when it gets long
  knowledge/        personal additions or overrides (they win over the engine's knowledge/)
  workouts/         drafts, scripts, research sheets, puzzles, video sheets
  .audio-cache/     clips and measured voice pace (ignored)
```

Notes on how it evolves:
- **Split health out of the profile.** It changes most often, it's the most sensitive, and it has its own rules: the check-in updates it, red flags stop the session, and the strictest rule wins. Keeping it in its own file makes it easy to keep out of anything shared.
- **Feedback to standing rules.** Today, feedback such as "wants deep-tech science, not exercise science" lives in `log.md` and gets folded into the skill by hand. A `feedback.md` with a "Standing preferences" section gives Claude a clear place to promote a repeated piece of feedback into a rule. The skill reads that section every session.
- **Log growth.** `tools/coverage.py` reads only recent sessions, but the whole log is read into context every session. A rolling `summary.md` (totals, load progressions, topics already covered) can be refreshed every ten sessions or so, and the skill would then read the summary plus the last few lines.
- **Layered knowledge.** The engine's `knowledge/` is the shared baseline. `me/knowledge/` holds personal overrides and additions, such as a clinician's rule that's stricter than the playbook. The existing "strictest wins" rule extends naturally to these layers.
- **A commons that grows.** `exercise-science.md` gains verified facts every session, and those are useful to everyone. Facts could be added to `me/knowledge/` first, then offered upstream in a pull request.
- **Schema version.** Each `me/` file carries a `schema: 1` front-matter line. A change to the context format is a major release, and it ships a `tools/migrate.py` step plus a CHANGELOG note. The tools refuse to run against an older schema and print the migrate command, much as `tools/build.sh` refuses an unmeasured voice today.
- **Edits stay in `me/`.** `.claude/settings.json` already limits session edits to `workouts/`, `log.md` and two knowledge files. In the new layout, that becomes `me/**` only, so a workout session can never change the engine.

### 3. Runtime and voice models

**Replace VoiceStudio with the project's own environment.** Add a `pyproject.toml` and a `uv` lockfile pinning the versions in use today (mlx-audio 0.5.0, mlx 0.32.1, yt-dlp, numpy). `tools/setup.sh` then:
- creates `.venv`,
- checks for `ffmpeg`,
- downloads each voice's pinned model.

`tools/build.sh` and `tools/youtube.py` look for `.venv` first, then for `SWEATCAST_PYTHON`. VoiceStudio becomes optional, needed only for the OmniVoice engine, which no voice uses now and which could be retired.

**Don't commit model weights.** They're 3.3 to 4.7 GB per engine, which is far past GitHub's 100 MB file limit and would burn through Git LFS bandwidth on every clone. Instead:
- each `voices/<name>.json` pins `model` and a Hugging Face `revision`, so every fork renders with the same weights,
- setup downloads them with `huggingface_hub.snapshot_download`, and the cache is shared with other apps,
- setup can download every voice's model or only the default voice's.

**Licenses.** Both engines allow this:

| Model | Hugging Face repo | License tag | Gated |
|---|---|---|---|
| Chatterbox Turbo (upstream) | `ResembleAI/chatterbox-turbo` | MIT | No |
| Chatterbox Turbo, MLX build used here | `mlx-community/chatterbox-turbo-fp16` | Apache 2.0 | No |
| Qwen3-TTS Base (upstream) | `Qwen/Qwen3-TTS-12Hz-1.7B-Base` | Apache 2.0 | No |
| Qwen3-TTS Base, MLX build used here | `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16` | Apache 2.0 | No |

The MLX build of Chatterbox Turbo is tagged Apache 2.0 while upstream is MIT. Both are permissive, but check the model cards before release and credit both in the README.

**Voices and consent.** The shipped coach voices are synthetic, which is the safe default for a public repo. The docs should say plainly to clone only your own voice, or someone's with their consent. A voice cloned from a real person belongs in `me/voices/` (private), not in a public fork.

**Hardware.** MLX ties rendering to Apple Silicon. `tools/render.py` already has engine switches (`omnivoice`, `qwen3`, `chatterbox`), so a cleaner backend interface (`speak(text, voice) -> pcm`, plus a "measure pace" hook) would let a Linux or Windows backend plug in later. Chatterbox's own PyTorch package would work on CUDA or CPU, more slowly. The timing system needs no change: it already measures each voice's pace from its own renders and stores it per voice and model. It's per machine, too, because `.audio-cache/` stays local.

### 4. Delivery

The Google Drive copy depends on macOS and Google Drive for desktop. Make delivery a setting in `me/profile.md`, with a few small adapters:
- **Local folder** (default): the MP3 stays in `me/workouts/`.
- **Synced folder:** any path, such as iCloud Drive, Dropbox or Google Drive. It's today's behavior with the path as data.
- **Private podcast feed:** write a `feed.xml` next to the MP3s in a synced or hosted folder. Then any podcast app on the phone gets each new workout automatically, with chapters per segment. This fits the name and the earbuds use case best. Hosting has to be private, with an unguessable URL at minimum, because the episodes describe health details.

### 5. The Claude Code harness: project template or plugin?

From the current docs (checked 2026-10-21):
- **Plugin contents.** A plugin can bundle skills, commands, agents, hooks, MCP servers and a `bin/` folder that goes on the PATH. It can reference its own files with `${CLAUDE_PLUGIN_ROOT}`, and it gets a persistent data folder at `${CLAUDE_PLUGIN_DATA}`.
- **No permissions allow-list.** A plugin can't ship one; its settings honor only a couple of keys. sweatcast's unattended run depends on `.claude/settings.json` allowing `tools/build.sh`, the tools and edits to the log. A plugin user would have to add those rules themselves.
- **Files are reachable.** Plugin skills run in the session's working directory under the normal permission rules, so "plugin for the engine, user's folder for the context" works.
- **Setup hook.** A `SessionStart` hook could check the environment and persist variables. It runs every session, though, so a heavy install needs a marker file or has to live in a separate setup command.
- **CLAUDE.md imports.** `@path` imports work. A generic `CLAUDE.md` can import `@me/profile.md` and so on, or a gitignored `CLAUDE.local.md` can hold the personal imports.

Sources: [plugin components](https://code.claude.com/docs/en/plugins/components), [manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference), [marketplaces](https://code.claude.com/docs/en/plugins/create-marketplace), [hooks](https://code.claude.com/docs/en/hooks), [permissions](https://code.claude.com/docs/en/permissions), [memory and imports](https://code.claude.com/docs/en/memory). Still unverified: whether a hook can grant permissions indirectly, whether the plugin's install folder is writable, and how the one-time `Setup` hook behaves in an interactive session.

Recommendation: a **project template first** (fork the repo, open it in Claude Code, and everything works, permissions included). A plugin can come later as a second way to install, once the engine reads all its paths from config. It could live in a marketplace defined in this same repo.

Smaller harness points:
- The skill runs research on `sonnet` subagents. Keep the model choices as named settings, not hard-coded, so a fork can change them.
- `CLAUDE.md` should become generic, describing what sweatcast is and the release process, while the author's first-person framing moves to `me/profile.md`.
- The skill's examples should be generic, or drawn from the user's own profile at run time. The ankle's phase criteria, for example, should come from `me/health.md`.

### 6. Onboarding

A `setup` skill, so a new user can say "set me up" and answer a short interview. It writes `me/` from `me.example/`:
1. **Basics:** name or nickname, city or neighborhood (only for local news and weather; coordinates are rounded), training background and goals.
2. **Equipment kits:** home, travel and gym.
3. **Health:** current injuries and limitations, any clinician rules, and the current phase. Show a short disclaimer, and explain the stop rule and red flags.
4. **Interests and feeds:**
   - Teams, found through ESPN's public team list, so the user picks a team rather than typing an ID.
   - Local outlets, discovered from the city's outlets' RSS feeds and confirmed by fetching each one once.
   - Science feeds, YouTube favorites and puzzle sources.
   - Topics never to bring up.
5. **Voice:** play the shipped voices' reference clips, pick a default, and render the smoke test, which also measures its pace.
6. **Delivery:** a local folder, a synced folder or a private podcast feed.
7. **First session:** a ten-minute session at the end, as an end-to-end check.

Feeds already validate themselves: `tools/feeds.py` lists any source it couldn't fetch, so setup can run it once and fix what failed.

### 7. Safety and privacy

- **Private by default.** Ignore `me/` in the template's git. Add a check (a git pre-push hook, or a CI step on the public repo) that fails if anything under `me/` or a known personal file is about to be pushed to a public remote. Making this repo public as-is shows how easily that happens.
- **Health data.** Keep it in `me/health.md`, never in the engine, tests or examples. Logs already leave injury details out by rule; keep that.
- **Medical framing.** The README and the setup skill say plainly that sweatcast isn't medical advice, that a clinician's instructions override everything, and that red flags stop the session.
- **Third-party content.** Video transcripts are already kept out of git (v0.6.0). Research sheets paraphrase and link their sources, which should stay the rule. Feed text is treated as data, not instructions.

### 8. Upstream updates for forks

- Forks rather than "Use this template". A GitHub template copies the repo without keeping the link to upstream. A fork can pull updates, and with `me/` ignored, the merges stay clean.
- Semver stays as is, and the context `schema` adds one more trigger for a major version. Each release's CHANGELOG section gets a "For forks" line when there's anything to do, such as running a migration or downloading a new model.
- An optional `tools/upgrade.sh` would pull upstream, run any migrations, refresh the environment from the lockfile and run the tests.

### 9. Tests and CI

- Today's tests read the author's real drafts (`workouts/drafts/*.draft.txt`) as fixtures. Move them to `tests/fixtures/`, and have the tests use `me.example/`, so they pass on a fresh fork.
- Add a GitHub Actions workflow that runs `python3 -m unittest discover tests` on each push and pull request. The tests need no models or network, so a plain Ubuntu runner is enough.
- Add a "fresh fork" check: copy `me.example/` to `me/`, lint the example draft and parse fixture feeds (a small new option for `tools/feeds.py` to read saved feed files instead of fetching).

## Proposed repository layout

```
sweatcast/
  README.md  LICENSE  CHANGELOG.md  VERSION  CLAUDE.md (generic)
  pyproject.toml  uv.lock
  .claude/
    settings.json          allow-list scoped to tools and me/**
    skills/workout/        the session
    skills/setup/          onboarding
  tools/                   engine: build, lint, render, feeds, youtube, coverage, paths, migrate, setup.sh
  knowledge/               shared baseline: tts rules, injury playbook, equipment, exercise science, voices guide
  voices/                  shipped synthetic voices: clip, transcript, engine, pinned model and revision
  me.example/              placeholder context, schema 1
  me/                      the user's context (git-ignored; optionally its own private repo)
  tests/  tests/fixtures/
  docs/research/           design notes like this one
```

## Phased roadmap

| Phase | What | Rough size | Done when |
|---|---|---|---|
| 0. Separate | Add `tools/paths.py`, and move `knowledge/profile.md`, `log.md` and `workouts/` under `me/`. Split out `health.md` and `feedback.md`. Make `CLAUDE.md` and the skill examples generic. Move test fixtures. | One or two sessions | The author's sessions still run unchanged, and nothing personal sits outside `me/`. |
| 1. Own runtime | `pyproject.toml` and `uv.lock`, `tools/setup.sh`, pinned model revisions in `voices/*.json`, and `.venv` resolution in the tools, so VoiceStudio becomes optional. | One session | A clean Mac with only Homebrew and Claude Code renders the smoke test. |
| 2. Onboarding and delivery | The `setup` skill, `me.example/`, delivery adapters (local, synced folder, podcast feed), schema versioning and `migrate.py`. | Two or three sessions | A second person gets a first workout from a fresh fork in about an hour. |
| 3. Package | CI, the privacy guard, fork docs, the "For forks" changelog lines, and optionally a plugin and marketplace. | One or two sessions | The public repo is the template, and the author's context lives in a private repo. |
| 4. Reach | A PyTorch backend for Linux and Windows, more engines, and a way to share exercise-science facts upstream. | Open-ended | Driven by demand. |

## Open questions for the maintainer

1. **This repo's own history.** Keep this repo as the public template and move your context to a private repo, possibly with a history rewrite to drop the old personal files? Or start a fresh public repo and keep this one as your private instance?
2. **Template or plugin first?** The recommendation is template first. A plugin's main appeal is one-command updates, but the permissions gap weakens the unattended run.
3. **Platforms.** Apple Silicon only to start, or plan the PyTorch backend early?
4. **Delivery.** Is a private podcast feed worth building early, and where would it be hosted?
5. **Shared knowledge.** Should verified exercise-science facts flow back upstream from forks, and who reviews them?
6. **Names.** Is `me/` the right name, or `context/` or `profile/`? It shows up in every path and permission rule.

## Appendix: personal and platform couplings found in the code

| Where | Coupling |
|---|---|
| `tools/build.sh` (lines 23-24, 47-48, 88) | Profile path, the VoiceStudio Python path, and the macOS Google Drive path |
| `tools/youtube.py` (lines 35-39) | VoiceStudio Python, and the profile, video and puzzle folders |
| `tools/feeds.py` (lines 36-38) | Profile and research folders. The user agent names `github.com/RNCDev/sweatcast`. |
| `tools/coverage.py` (line 26) | `log.md` at the repo root |
| `tools/render.py` (line 41), `tools/voices.py` (lines 50-54) | The audio cache in `workouts/`, and VoiceStudio and OmniVoice data folders |
| `tools/tts_build.py` | Help text and the pause dialect named after VoiceStudio. It switches to VoiceStudio's Python. |
| `tests/test_tools.py` (line 30) | Reads the author's drafts as fixtures |
| `CLAUDE.md` | First-person author framing, the author's hardware, and the repo name |
| `.claude/skills/workout/SKILL.md` | Author-specific examples (ankle criteria, the Tata quiz, "he") |
