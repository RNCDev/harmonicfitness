# Changelog

All notable changes to HarmonicFitness (called sweatcast through 0.19.0). The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- **The web coach records the audio.** The build runs in full on the site; each MP3 a turn makes is kept 24 hours, sealed with the listener's data key, and the chat shows it with a player and a download (`GET /api/media/{id}`: byte ranges for Safari, a private browser cache until it expires).
- **Recording waits for the listener's Record button,** with its price: a full build is first only priced (characters and dollars, the voice design included), and approving it reserves those characters from a daily allowance (`HARMONICFITNESS_DAILY_CHARS`, default 60,000) and records within that count.
- **Re-recording pays only for what changed:** recorded clips are kept a week per listener, sealed, and loaded for each recording.
- **Stop.** A Stop button ends a running turn within a few seconds: the model run is cancelled and the engine's processes are killed.
- **First-time setup on the site:** a new listener gets the setup skill's quick start in the chat (keys in Keys, the stock web coach for their service made and heard in the chat, a ten-minute first workout); "finish setting me up" runs the rest.
- **Export and delete:** the Keys drawer downloads every file as a ZIP laid out as `me/`, and deletes the account and everything in it, with the password.

### Changed
- **The check-in may change `health.md`** on the site, with the listener's permission, as on a computer.
- **The chat's steps say what they mean for the listener** ("Checking today's safety limits", "Writing your script", "Recording your workout"), never a command or a file's name; repeated steps show once.

### Removed
- The web client's scoping research and milestone plans (`docs/research/web-client/`) and the 0.15.0 plan (`docs/plans/`).

## [0.22.0] - 2026-10-28

The web coach answers sooner: the worker does the skill's first reads itself, all at once, and fetches the day's feeds in the background.

### For forks
- **Nothing to migrate.** Only the web client changed.

### Changed
- **The check-in arrives in one round trip.** On a conversation's first turn the worker runs step 1 of the workout skill (check, content plan, get coach, the coach's route, coaches list, and the profile, training, health and log files) before the first model request, in parallel, and hands the results to the model with the listener's first message. The model sees the same information as before, without a model request for each read.
- **Feeds run in the background.** On each turn after the first, the worker starts `feeds` as the turn begins (unless today's sheet is there), so the day's research is ready when the script needs it; the model's `run feeds` waits for that run. The coach no longer fetches feeds before the check-in.

## [0.21.0] - 2026-10-28

The web client, stripped back to a chat and Keys: the coach on the site works as Claude Code does on a listener's computer, following the workout skill itself. The engine gains the build checks the web needs (one side only, names the catalog doesn't hold, a character allowance and its price).

### For forks
- **The build's menu check is stricter.** A draft that speaks a one-sided movement with "each side", "switch", the other side's word or "the injured leg" in its segment is refused (exit 1), as is a movement name the catalog doesn't hold (`[unlisted]` in `knowledge/movements.toml`). An existing draft that passed before may need its wording changed; rerun the build and follow what it names.
- **A shipped limit cue changed words:** the groin's off-limits cue is now "No side lunges or wide stances, and no legs spread apart." Clips of the old line render once more.
- **Nothing in `me/` to migrate.**

### Added
- **Live steps in the web chat.** While the coach works, the chat shows a running clock and each step as it happens ("Reading me/profile.md", "Working out today's safe menu", "Checking the script"); the worker logs each tool and its exit code, never what it read.
- **The coach's replies render as Markdown** (tables, lists, bold) in the web chat; the listener's own lines stay plain text.
- **Bring in your folder.** The Keys drawer takes a ZIP of a listener's `me` folder and keeps its files over the starter ones (`POST /api/import`, at most 10 MB zipped, 2 MB a file); key files, audio, caches, logs, backups and git are left out.
- **A build's allowance and its cost.** `build --max-chars N` bounds a web build below the profile's `cloud_max_chars`: the lint stops a script over it (nothing is sent), and the render's own check names the flag when it was the lower bound; a local voice ignores it. `get cost --coach <coach> [--chars N] [--json]` prices a web build (`chars`, `usd`, `ceiling`, and the one-time voice design for a coach still to be made); a local coach, or a web coach with no key here, is exit 64.
- **A one-sided movement keeps to its side in the build.** When today's menu allows a movement on one side only, the build's menu check refuses a sentence that names it with another side's word, and a segment naming it that holds, in any sentence, a both-sides phrase ("each side", "alternating", "both legs", "switch", "other leg"...) any word naming the other side outside a shipped limit cue ("then ten on the left", "next, left", "now the injured leg"), or a turn without one ("change legs", "the other one", "ten a side", "the second leg", "apiece"); a colon or a parenthesis doesn't separate a dose from its name, and a negation doesn't excuse it. The rule moved from the web's plan check into `menu.side_problems`, so the build and the web refuse the same things. `menu.part_of` is public (`_part_of` stays as an alias for this release).
- **Names the catalog doesn't hold are refused.** The catalog's new `[unlisted]` table names real movements it doesn't hold ("pistol squat", "pistols", "forward lunge", "walking lunge", "side lunge", "lateral lunge", a bare "lunges"), singular or plural; a script that says one is refused, since it can't be on a menu, except a bare "lunges" after a declared lunge. The groin's off-limits cue now reads "No side lunges or wide stances, and no legs spread apart.", so its negation covers the name.
- **Web mode's key messages point at the app's Keys.** Under `HARMONICFITNESS_WEB=1` a missing, refused or malformed key says to add it in HarmonicFitness's settings, under Keys, and never mentions `keys init`, `keys open` or `me/.env`; the command line's wording is unchanged.
- **The web client's mode.** With `HARMONICFITNESS_WEB=1` (the web client's worker sets it) the engine has no local voice: a build with no coach named takes the first stock web coach, whose key the listener adds in the app, and a finished MP3 is kept in its workout folder for the app to upload, with no delivery folder asked for (`doctor` reports `web=yes`). Unset, nothing changes. A web coach with no key yet now shows its estimated pace in the brief instead of none.
- **Voice keys in the web app.** A listener enters each web voice service's key once in the app's Keys box; it is stored encrypted per user and never shown again. Only the worker opens the keys, for one job, and hands them to the engine under `services.toml`'s variable names, so the engine reads them instead of `me/.env`.
- **The web client is a chat and Keys.** The coach follows the workout skill itself, with four tools (run a `./harmonicfitness` command, read, write and list files, inside the listener's folder), asking its questions in the chat; the sentence band, check-in panel and plan table are gone. The build runs `--lint-only` for now: the audio comes later.
- **A language-model key in Keys.** Each listener adds their model key in the app's Keys box, stored like a voice key and used only by that job's model client.
- **The deployed version on the page.** The web client shows the engine's version and the deployed commit under the wordmark, on the sign-in page too, and `/healthz` returns it, so a deploy is visible at a glance ("0.20.0 (75da105)"; the commit is Railway's `RAILWAY_GIT_COMMIT_SHA`, baked in at build).

## [0.20.0] - 2026-10-27

sweatcast is now **HarmonicFitness**: the command, the package, the environment variables, the repositories and the web app all take the new name. Nothing about how a workout is built, heard or logged changes, and no context file changes its schema. The release also carries the first slice of the web client.

### For forks
- **The command is `./harmonicfitness`** (it was `./sweatcast`, which is gone: there is no shim). `tools/sweatcast.py` is `tools/harmonicfitness.py`, and Codex's rule file is `.codex/rules/harmonicfitness.rules`. Claude Code's allow rule is `Bash(./harmonicfitness:*)`.
- **Every `SWEATCAST_*` environment variable is `HARMONICFITNESS_*`** (`HARMONICFITNESS_HOME`, `HARMONICFITNESS_PYTHON`, `HARMONICFITNESS_DEVICE`, `HARMONICFITNESS_DEBUG`, `HARMONICFITNESS_<SERVICE>_URL`...). The old names are no longer read: a `SWEATCAST_HOME` left in a shell profile is ignored, so rename it.
- **The web client's `WT_*` variables are `HARMONICFITNESS_*`** (`HARMONICFITNESS_MASTER_KEY`, `HARMONICFITNESS_BASE_URL`, `HARMONICFITNESS_ROLE`, `HARMONICFITNESS_REGISTRATION`, `HARMONICFITNESS_ENGINE_ROOT`, `HARMONICFITNESS_TEST_DATABASE_URL`). Set the new names, with the same values, before deploying this release.
- **The Python package is `harmonicfitness`** and `errors.SweatcastError` is `errors.HarmonicFitnessError`. The local engine's marker is `.venv/.harmonicfitness-extra`: rerun `./harmonicfitness setup`, or rename the old `.venv/.sweatcast-extra` by hand.
- **The repositories are `RNCDev/harmonicfitness`** and, for the maintainer's context, `RNCDev/harmonicfitness-me`. GitHub redirects the old addresses; point a clone at the new one with `git remote set-url origin https://github.com/RNCDev/harmonicfitness.git`.
- **Nothing in `me/` to migrate.** Clip cache keys never held the name, so no clip renders again or is billed again.

### Changed
- New web voices are saved at the service as "harmonicfitness <name>". Voices saved before are still labeled "sweatcast <name>" there and keep working by their ID; the messages that say what to look for at the service name the new label.

### Added
- **The web client, Slice 1** (`web/`, the optional `web` extra; see `web/README.md`): a FastAPI server and a Python worker on Postgres, a React client, an encrypted per-file store for each listener's context, a job queue that runs `./harmonicfitness brief` in a sealed temporary context folder, and a live event stream. Sign-in is a username and password, with open registration behind `HARMONICFITNESS_REGISTRATION=open|closed` (default open). Deployed on Railway from this repository's `main`.

## [0.19.0] - 2026-10-27

The audit's remediation: money spent on web voices is guarded at every step, settings and names are checked where they come in, an engine bug is never mistaken for a draft to fix, and the coaches code is split by job. Workouts, drafts, coaches and the `me/` folder work as before; no context file changes its schema.

### For forks
- **Nothing in `me/` to migrate.** New `builds.jsonl` lines carry `kind` (`"mp3"`, `"failed"`, `"outcome"`); older lines are read by their fields and never rewritten, and older engines still read the new ones. A reader of its own should go through `records.build_records()` or `records.parse()` and branch on `rec["kind"]`.
- **Exit codes that changed, each to the one it should have been:**
  - 64 (the command was wrong) where a value was accepted before: a build name with `: ? * | " < >`, a control character, a trailing dot or space, or a Windows device name (`con`, `nul`...); `brief --save` outside `me/workouts/`; any numeric option of 0 or less (`--minutes`, `--recent`, `--hours`, `--last`, `--idle`; `--seed` and `cache --days` may be 0).
  - 1 (fix the file) where 64 was given before: `brief` or `content` with a damaged `sessions.toml`, `content.toml`, catalog or profile.
  - 1 where a silent default was used before: a malformed `cloud_max_chars` or `words_per_minute`, or a coach whose `kind` is neither local nor web.
  - 70 (an engine bug) where 1 was given before: an unexpected exception during a web render or an audition.
- **Moved:** auditions to `tools/audition.py` (`audition`, `keep_web`, `forget_audition`), making a stock web coach to `tools/coachmake.py` (`make`); `coaches.X` still works for this release, but patch `coachmake.make`, which the build now calls. `render` no longer re-exports the internals of `audio`, `clipcache` and `records`: import them from there. Renamed: `clipcache._cache_write` to `clipcache.write`, `_verdict` to `verdict`.
- **Signatures:** `logsession.log_session` takes keyword fields (`coach=`, `fmt=`, ...), not a parsed command line; `brief.main(argv)`; `cloud.request(..., deadline=)`; `cloud.audio_pcm(..., expect=, content_type=)`; `migrate.coaches_due` may list `("unreadable", coach)` (use `migrate.acting()` for the steps that change something).
- **`keys.BadKey` is an `errors.SweatcastError`** (still exit 4), so `except errors.PROBLEMS` catches it: the readiness check and the brief carry on past a key with a stray character. `keys` no longer imports `cli`; `tests/test_imports.py` fails on any import loop at load time.
- **`--route`** is the flag's name on `build`, `get route` and `coaches measured`; `--engine` still works.

### Fixed
- **The web spending cap can't be misread.** `cloud_max_chars = "5000"` (in quotes) no longer reads silently as the default 30,000: `./sweatcast check` names any single setting it can't use (`context.SCALARS`), and a build stops rather than guess.
- **A paid voice left behind is said on screen.** When the first build with a stock web coach saves its voice at the service but can't write the coach, the terminal names the service and the voice ID; before, only the build log did. A failed or interrupted design shows the log's last lines.
- **A slow web service can't hold a build for many minutes:** each paragraph gets five minutes in all, retries included, and three failures in a row stop the sending; the clips that came back are cached, so a rerun sends only the rest.
- **A reply that isn't audio is refused** (text, a cut-off or unreadable stream, under 0.1 s) instead of being cached, paid for once and replayed in every later build. Each service says what it asked for, and raw sound is accepted only where it was.
- **An empty or torn clip in the cache is rendered again**, and a clip that comes out empty stops the build naming its line. Clips are written atomically and flushed.
- **Ctrl-C during a web render says what was sent** (characters, clips cached, and that a rerun sends only the rest); any interrupted command says "Interrupted.".
- **A build name with a colon is refused on every system** ("Workout 1: Strength" hid the text in a Windows side stream); the build also checks the MP3 lands in its own folder.
- **On Windows, a build no longer fails at its last step** because a player has last time's MP3 open: replacing a file is retried for a moment. The Windows lock retries only on "busy", and its re-entry key ignores case.
- **Key values never print from the command line:** every message `cli.run` prints is scrubbed, a service's answer is scrubbed before it's shortened, and an unreadable `me/.env` still scrubs the environment's keys.
- An unreadable `me/movements.toml` is listed by `./sweatcast check` instead of printing a warning on every command; a coach file `migrate` can't read is named, never skipped silently or crashed on.
- A feed that declares a DOCTYPE or entities is refused unparsed; caption downloads are capped at 5 MB like feeds.

### Changed
- `tools/coaches.py` is the command line only; the list and `--json` are built from one `coaches.listing()`, and the rules for `coaches set` live in `personas.set_setting`.
- Library code reports through the callback it's given, never `print`; the delivery-folder note is `context.delivery_note`.
- Every numeric option is range-checked by one set of types (`cli.positive_int`, `non_negative_int`, `positive_float`, `non_negative_float`), and a test walks every parser to keep it so. `brief` checks its flags before it computes anything.
- A local build with the take check loads the voice model once; each repeated line is read once per build, and less audio is held in memory while the workout is assembled.
- Each build's part of its log ends with `--- end <build_id> <stage> <code>`. The sample, a made voice, audition files and the Codex skill copies are written atomically (`fileio.atomic_copy`, `fileio.replace`), and the `+++` block has one writer (`frontmatter.dump_block`).
- `builds.jsonl` and `told.jsonl` are read by one rule (`fileio.read_jsonl`), which skips a line a crash cut mid-character instead of failing the read.

### Added
- `SWEATCAST_DEBUG=1` prints a reported problem's scrubbed traceback, with what it was raised from.

## [0.18.0] - 2026-10-27

The safety gate can no longer be talked past, voice keys stay on their service's host, a replaced voice file is heard at once, every build leaves a trail to its end, and the middle of the engine is untangled. Workouts, drafts and coaches work as before; no context file changes its schema.

### For forks
- **Nothing in `me/` to migrate.** Things a listener notices once: every local coach's lines render again on the next build (the clip key now includes the voice file), every cached take is heard again once (verdicts now carry the checker's id), and a menu saved by an older brief asks for `brief --save` again (menus are daily anyway).
- **A new exit code, 70:** an unexpected exception (an engine bug) exits 70 with its scrubbed traceback on stderr, where it used to exit 1, the code for "fix the draft". A script that branched on 1 for every failure should treat 70 as "stop and report".
- **`log-session --draft` takes its coach from the build** when `--coach` is left out, refuses a different one, and ends the session line with `| build: <id>`; older lines read as before. `--coach` is still required without `--draft`.
- **Errors:** `personas.UnknownCoach` and `routes.WebCoachUnavailable` are now `errors.UsageError` (exit 64), no longer `SystemExit`; catch them with `except Exception` or `errors.PROBLEMS` (which no longer includes `cli.Usage`). Exit codes live in `errors.py` (`cli` re-exports them).
- **Moved:** `scrub` to `tools/redact.py` (`cloud.scrub` still works); coach choice (`default`, `resolve`, `pick`) to `tools/coachpick.py` (`personas.default`/`resolve` and `routes.pick` re-export it for this release); `doctor.facts`/`hub_dir` to `tools/machine.py`; `web_key` to `cloud`; log-session's logic to `tools/logsession.py`; `equipment_keys`/`about` to `catalog`. `context` no longer re-exports the health, store and session-log names: import them from `health`, `store`, `sessionlog`. Renamed public: `coverage.days_ago`, `personas.load_all`, `catalog.spoken_fault`.
- **Failure summaries moved to stderr** (a build's menu, lint, drift and unmeasured-coach lines; backup's refusals). The reports themselves stay on stdout.
- **A web service URL override** (`SWEATCAST_<SERVICE>_URL`) counts only for `https://` or `http://` to localhost.

### Fixed
- **The menu gate checks the menu itself.** `menu.validate` checks `menu.json`'s shape (a damaged menu is an issue, never a traceback), and a strict build re-runs the safety screen from the menu's request against today's `health.md`, profile and catalog, refusing any movement (or side) it doesn't allow: a movement added to the menu by hand no longer passes. The request can tighten health.md's limits, never loosen them. A missing `health.md` is named as such.
- **Voice keys never follow a redirect** to another host; feeds re-check http/https on every redirect hop. Voice IDs are URL-encoded and must look like one a service gives.
- **A local coach's clip cache key includes its voice file** (`pocket.safetensors`), so a remade voice is heard, not the old one's clips; the stock coaches' `pace.json` moved to the new keys (`tools/coachmaker/rekey_pace.py`).
- **Take verdicts carry the checker's id** (`verify.checker_id`), so a stricter checker hears cached lines again.
- `coaches forget-audition` and `keep` resolve an audition only inside the auditions folder (a folder elsewhere is never deleted); `candidates.json` is checked.
- Two builds can't design and pay for the same pending web coach (`coaches.make` holds a lock); a Gemini voice left behind after a failure is named.
- A local render that stops midway releases the model and keeps the pace it measured; a failed delivery records why (`couldn't copy to …: No space left on device`).
- Every ffmpeg call has a timeout (the final encode's grows with the audio), so a hung ffmpeg can't hold the render lock forever.

### Added
- **Every full build leaves one outcome line** in `builds.jsonl`: `stopped` with its stage (coach, pace, lint, menu, design, render, drift, web-copy, deliver), `measured` for the smoke test, or `delivered`. The render log now also holds the engine's own progress and, for a crash, its traceback; the build record has per-stage `timings`.
- `--json` on `coaches list`, `content plan`, `coverage` and `get`.
- `./sweatcast cache prune --logs-older DAYS` removes old render logs (never `builds.jsonl` or `told.jsonl`).
- `services.toml` is validated when read; `fileio.read_json` names a damaged JSON file.

### Changed
- `build.py` is split: `run_build(BuildOptions)` with `resolve_voice`, `gate`, `render_and_deliver` and a pure `delivery_plan`; `main` only parses.
- `tools/ffmpeg.py`'s `run` and `to_mp3` are the one way to run ffmpeg.
- The voice a build speaks with is built as a `LocalVoice` or `WebVoice` (`tools/voice.py`), passed on as today's dict.
- Import cycles cut from six to four, each with its reason; `tests/test_imports.py` keeps new ones out and pins the voice dicts and cache keys. Only command modules import `cli`, and no tool copies a path constant at import (both checked).
- One heading rule (`frontmatter.heading_index`), one movement key (`catalog.key`), one `--today` parser (`cli.today_arg`); `cli.py` states the `--date`/`--today` rule and a test holds every parser to it.
- The take check's clipping count and clip leveling use numpy.

## [0.17.0] - 2026-10-27

The engine, audited and reworked from the inside: the listener's records survive a crash or two writers at once, a hand-edited setting can no longer stop every command or be misread, errors are typed and reach stderr, the largest modules are split by job, and a build can be followed from its log to its delivery. Workouts, drafts, coaches, commands and exit codes work as before; briefs and exports come out byte-identical.

### For forks
- **Nearly nothing to migrate:** no context file changes its schema. `./sweatcast migrate` (which setup runs) adds `*.lock` to a `me/.gitignore` from before 0.5.4 that lacks it, so the new lock files beside `log.md`, `told.jsonl` and `builds.jsonl` never go into a backup.
- **Library code no longer raises `SystemExit`.** A fork's own code that called an engine function and caught `SystemExit` should catch `errors.PROBLEMS` (the typed errors and `cli.Usage`) or the kind it means (`errors.ContextError`, `CoachError`, `RenderStopped`...). Commands, and the exit codes the skills branch on, are unchanged.
- **Moved, still importable from where they were:** the front matter, the store, the health file and the session log from `context` (`frontmatter.py`, `store.py`, `health.py`, `sessionlog.py`); the PCM work, the clip cache and the build records from `render` (`audio.py`, `clipcache.py`, `records.py`). Both modules re-export every moved name.
- **Some errors moved from stdout to stderr** (a build stopped by a lost cue, the web cost ceiling, a web service's refusal, a missing profile or coach). A script that read them from stdout reads stderr.
- **`builds.jsonl` gains outcome lines** (`"event"`); a reader of its own that counts MP3s should skip them, as `records.is_mp3` does.

### Fixed
- **A crash mid-write no longer loses the next record.** `builds.jsonl` and `told.jsonl` are appended through `fileio.append_jsonl`: under the file's lock, flushed to disk, and a last line a crash left without its newline is sealed first, so the reader skips only that fragment (before, the next record was glued onto it and both were lost, and `log-session` could then refuse a session whose MP3 existed).
- **Two writers at once can't lose or double a record.** `log-session` holds `me/log.md`'s lock across its duplicate check and the write; `content log` holds `told.jsonl`'s across its "told once" check and the append; `migrate` holds it while it rewrites the file. The lock (`locks.file_lock`, the pace file's lock moved up) is re-entrant within a thread.
- **A hand-edited `me/movements.toml` can't stop every command.** An entry with no id, a list or table field of the wrong type, or a count that isn't a number is left out and named by `./sweatcast check` (before, `brief`, `build`, `movements` and `check` itself stopped with a traceback). A single `[movement]` table reads as one movement.
- **Every engine write is atomic:** the menu, the brief, the feeds sheet and the YouTube sheets now go through `fileio.atomic_write` (a test keeps it so); the pace file's hand-rolled copy uses it too.
- **A rate limit isn't a used-up quota.** A web service's 429 that names no wait is retried with backoff, even when its body says "quota"; only one that outlasts every try stops the build as the quota (exit 4).
- **The web player's links** survive a `#` or `?` in a workout's name (URL-encoded).
- The characters-sent count of a failed web render is exact (the workers' counter has a lock); the TLS context is built once per process.

- **A setting in the wrong shape is read as meant, and `check` says so.** A bare string where a list belongs (`likes = "goblet squat"`, `aliases = "Maya"`, a kit's `equipment = "dumbbells"`) is one item, never its letters (before, every letter became a like, or an alias, so a lookup for "a" found that coach); a single `[kits]`, `[feeds]` or `[interests]` table is one row (before, no kits at all). `./sweatcast check` notes each one and how to write it. `[[limits]]` stays strict: a malformed row still stops the brief.

### Added
- **A build can be followed end to end.** Each build has a `build_id`, in its log's header line, its record, a failed web render's line, and a new outcome line in `builds.jsonl`: `"event": "stopped"` (the stage, lint, menu or render, and why) when a full build stops, or `"delivered"` (where the MP3 went). Before, a local build that stopped on a dropped cue, the lint or the menu left no trace, and the delivery was only in the MP3's own `.build.json`. `log-session` and `get web-builds` skip the outcome lines, so they count as before.
- **`build --verbose`** leaves the engines' loading and rendering chatter on the terminal (it still goes in the log's header line).
- **A model that won't load says why:** the network's advice only when it was the network; otherwise out of memory, or the error by name (before, every failure said "check the network"). The take checker's load is caught the same way.
- Past 2 GB of clips, a build mentions `./sweatcast cache prune` (the cache is still never pruned on its own: a web coach's clips are paid for, and a render running ahead may be using them).

### Changed
- A build log past 1 MB starts over, its older lines kept once as `<name>.log.1`; a failure shows the last lines from its end instead of reading the whole log.
- **Errors are typed, and the engine never exits from library code.** `tools/errors.py` holds `SweatcastError` (exit 1 unless it says otherwise) and its kinds: `ContextError`, `LogRefused`, `CoachError`, `RouteUnavailable`, `EngineError`, `DraftError`, `RenderStopped`, `MigrateError`. The hundred-odd `raise SystemExit(...)` in the tools are now these, and the thirty-odd places that caught `SystemExit` to carry on catch the kind they mean, or `errors.PROBLEMS` (these and `cli.Usage`), so a real exit is never swallowed. Exit codes are unchanged; `tests/test_contract.py` pins them and keeps `SystemExit` out of the engine.
- **Errors go to stderr.** A build stopped by a cue lost in every take, the web cost ceiling, an over-long paragraph for a service, a web service's refusal, a missing profile or no coach now says so on stderr, through `cli.run`, instead of printing to stdout and exiting from inside the render.
- **The large modules are split by job, behind the names they had.** `context.py` keeps the profile, coach files and the command line; the front matter, the file store and its schema, the health file and the session log are `frontmatter.py`, `store.py`, `health.py` and `sessionlog.py`. `render.py` keeps the orchestration and the encode; the PCM work, the clip cache and `builds.jsonl` (its writers and `log-session`'s readers together) are `audio.py`, `clipcache.py` and `records.py`. Both re-export every moved name, so no caller changes; the moves are verbatim, and briefs, exports and both render routes come out as before.
- **One contract for the web voice services.** `cloud.service_module(name)` is the one lookup; `tools/services/__init__.py` states the contract (`speaker`, `design`, `save`, `delete`, in one argument order, checked by a test) and two optional flags, `STORES_DRAFTS` (Gemini) and `DESIGN_NOTE` (ElevenLabs), which replace the names `coaches.py` hard-coded. It also reads `knowledge/services.toml`, so `keys.py` no longer imports `cloud.py` and that import cycle is gone.
- **Shared helpers instead of copies:** one WAV writer (`tools/wav.py`, used by the engine and the maintainer's coach tools); `frontmatter.wrap` for every settings block `migrate` writes (it refuses one that doesn't parse); and one apostrophe folding (`catalog.fold`) for the menu scan, the name matcher and the take check, so "farmer’s", "farmer‘s" and "farmerʼs" read alike everywhere.
- **One reading of each setting.** `context.str_list` and `table_list` read the list settings for every tool, and `shape_problems` reports what they forgave; a kit's weights are read once (`kit_weight_table`) for both the brief and `check`, which used to keep its own copy of the rules.
- **The catalog is loaded once per command** (`catalog.default()`, reloaded when either catalog file changes), and `resolve` looks names up in an index instead of scanning every name and alias: `log-session` parsed the catalog four or five times and resolved every movement of every past session by a scan. A test holds the index to the scan's answers for every name in the catalog. The brief's menus are unchanged.
- A feed item's link goes into the research sheet only when it's a plain http(s) address.
- Stale names: a persona file's comments name Pocket for a local coach and cover Gemini and Inworld; docs say `me/coaches/`; `doctor.model_present` (unused) is gone; `locks.py` no longer claims the maintainer's coach tools take the render lock.
- `tests/test_contract.py` pins the command line's exit codes (help 0; a mistyped command or option 64 on every command); `tests/test_integrity.py` covers the above.

## [0.16.0] - 2026-10-27

Pocket TTS is settled as the local voice, so the research that chose it leaves the engine: the audio bench, its results and the voice research note. Nothing a workout uses changes.

**Version numbers restart at 0.16.0.** This release was first tagged 16.0.0; sweatcast is pre-1.0 in fact, so every release is renumbered in Semantic Versioning's 0.x form: old major X is now 0.X, and its releases count up as patches in order. The tags and GitHub releases were recreated under the new numbers on the same commits (each tagged commit's own `VERSION` file still shows the number it shipped with), and every version this changelog, the docs and the tools mention uses the new numbers.

| Old | New | Old | New | Old | New |
|---|---|---|---|---|---|
| 0.1.0–0.6.0 | 0.0.1–0.0.6 | 6.0.0, 6.1.0, 6.2.0 | 0.6.0, 0.6.1, 0.6.2 | 10.0.0–10.4.0 | 0.10.0–0.10.4 |
| 1.0.0, 1.1.0 | 0.1.0, 0.1.1 | 7.0.0, 7.1.0, 7.2.0 | 0.7.0, 0.7.1, 0.7.2 | 11.0.0, 11.0.1 | 0.11.0, 0.11.1 |
| 2.0.0 | 0.2.0 | 8.0.0, 8.0.1, 8.1.0 | 0.8.0, 0.8.1, 0.8.2 | 12.0.0, 13.0.0 | 0.12.0, 0.13.0 |
| 3.0.0, 3.0.1, 3.1.0 | 0.3.0, 0.3.1, 0.3.2 | 9.0.0, 9.1.0, 9.1.1, 9.1.2 | 0.9.0, 0.9.1, 0.9.2, 0.9.3 | 14.0.0, 14.1.0, 14.2.0 | 0.14.0, 0.14.1, 0.14.2 |
| 4.0.0 | 0.4.0 | 5.0.0–5.4.0 | 0.5.0–0.5.4 | 15.0.0, 16.0.0 | 0.15.0, 0.16.0 |

### For forks
- **Tags changed names.** `git fetch --tags --prune-tags --force` drops the old `v1.0.0`…`v16.0.0` tags and fetches the new ones. A checkout or script pinned to an old tag uses the new name from the table (`v12.0.0` is `v0.12.0`, which is where `./sweatcast migrate` sends a folder older than 0.9). The old `v0.3.0`…`v0.6.0` tags are now `v0.0.3`…`v0.0.6`, and the names `v0.3.0`…`v0.6.0` belong to old 3.0.0…6.0.0.
- **From here,** a 0.X.0 release may break something and says what to do here; a 0.x.Y release doesn't.
- **`./sweatcast bench` is gone,** with `tools/bench.py`, `tools/bench_worker.py`, `tests/test_bench.py` and `docs/audio-bench/` (the script, the 2026-10-26 results and their listening files). CLAUDE.md no longer has "run the MAC/PC audio test harness". Git history keeps all of it: `git checkout v0.15.0 -- tools/bench.py tools/bench_worker.py docs/audio-bench` brings it back.
- **`knowledge/research/2026-10-25-local-voices.md` is gone;** `knowledge/voices.md` keeps what it decided.
- **The maintainer's coach tools** (`tools/coachmaker/`) now run in the engine's own environment through `common.py` (Pocket, untrimmed, and the take checker's recognizer), not the bench's throwaway ones. `qa.py` and `embed_worker.py` are gone; the ear approvals and every build's take check cover what they measured. `export_pocket.py` loads the gated Pocket model in `.venv` (a Hugging Face login with its terms accepted, as before).
- **Disk:** a computer that ran the bench can delete `.cache/bench/` and `.cache/uv-bench/`; `./sweatcast models` names the models nothing uses.

## [0.15.0] - 2026-10-27

Ten local coaches ship with sweatcast, all on one local engine, Pocket TTS, on every computer. Each was designed once from a description, heard and approved by ear, and ships with its voice file, recorded counts and cues, a measured pace and a 45-second sample to choose by ear. Countdowns play those recorded numbers one second apart instead of a voice rushing through them. Local coaches are now chosen, not made: a voice of your own is a web coach.

### For forks
- **Run `./sweatcast migrate`** (setup runs it). `me/personas/` becomes `me/coaches/`. A local coach of your own moves to `me/coaches/.archive/`, since only the ten stock local coaches render now; old log lines still find it by name. An unmade copy of a stock web coach (Reed, Ellis, Nolan, Owen, still `pending = "design"`) goes to the backup, since the engine ships them now; a made one stays in `me/coaches/` and is used over the stock copy. `me/.gitignore`'s `personas/` rules become `coaches/` rules. No context file changes its schema.
- **The local engine is Pocket TTS on PyTorch everywhere**, the extras `cpu` (an Apple Silicon Mac, or a PC's processor) and `cuda`. MLX, Chatterbox Turbo, Qwen3-TTS and the local voice designer are gone from the engine. A `.venv/.sweatcast-extra` of `mlx` becomes `cpu`; rerun `./sweatcast setup`, which downloads Pocket's public model (about 0.6 GB) and the take checker (2.5 GB, now the ONNX Parakeet on every computer, so a PC's takes are checked too). No Hugging Face login is needed. The old models stay in `models/` until you delete them: `./sweatcast models` lists them with their sizes (about 30 GB on a Mac that ran everything). An Intel Mac has no local voices any more (PyTorch has no build for it).
- **Stock coaches live in the engine, in `coaches/`**, not in the template. This reverses 0.9.x's move of Coach Andy into `me.example/`: ten coaches with their voice files are public, versioned assets a release should be able to improve for everyone, and about 160 MB doesn't belong in each listener's private backup. The four stock web coaches moved there too. `personas.all()` merges `coaches/` with `me/coaches/`, yours winning on a name clash.
- **Removed commands:** `coaches design`, the local `coaches keep` (a take or a clip), `coaches set <coach> local.engine`, `coaches download --all` and `setup --all`. `coaches keep <audition>/<letter>` for web coaches is unchanged.
- **Countdowns are written as `[count 5 go]`.** With a coach that has recorded counts the lint refuses one written in words (three or more number words counting down); a coach without (a web coach) says the marker's count in words. With any coach, one word alone between markers ("Hold.") is refused too, since a local voice garbles it often; the message points to `[cue …]` where it's a cue. The smoke test changed to match; a fork's own drafts need the same change. The brief's new Counts line says how the coach counts.

### Added
- **The ten stock local coaches** (`coaches/coach-<name>-local/`): Andy, Marcus, Theo, Sam and Callum; Maya, Claire, Rosa, Helen and Kate. `coaches/roster.toml` holds each description and how it talks, and how each was made (designer, model revision, seed).
- **`[count N cue]` and `[cue x]`** in drafts (`tools/counts.py`): a coach's recorded five, four, three, two, one, a second apart, then go, rest, switch, switch sides, stop or hold; or one cue alone. The lint times them exactly from the clips; the render lays them on the beat; the transcript says them in words. A web coach says them in words.
- **Choosing a coach by ear:** setup's quick start and the coach skill's "switch coach" offer the ten by style, with their samples.
- **Maintainer tools** (`tools/coachmaker/`, not listener commands): `design.py` (Qwen3-TTS VoiceDesign through mlx-audio, in its own environment), `pick.py`, `export_pocket.py` (the gated Pocket model makes each `pocket.safetensors`), `qa.py`, `cues.py`, `sample.py` and `persona.py`.
- **`./sweatcast models`** lists the models older versions downloaded that nothing uses now.

### Changed
- **The take check runs on every computer** with Parakeet TDT 0.6B v3 through ONNX on the processor.
- **The engine refuses Pocket's gated cloning model** (`engines.public_only`), so a Hugging Face login never changes a coach's voice.
- **A stock local coach ships measured** (its pace from its sample), so no smoke test before a first workout; this computer's measurements go to the shared `me/workouts/.audio-cache/voice-pace.json`, so `me/coaches/` holds only your own coaches.
- **The audio bench** keeps cloning Andy's old clip, now `docs/audio-bench/voice/`, so runs stay comparable.

### Notes
- **Why Pocket alone:** in a blind test on 2026-10-26 Pocket was preferred over Chatterbox Turbo for six coaches, Turbo for three, one even; on the audio bench it never dropped a cue word in 176 takes and renders two to six times faster, in a third of the memory.
- **Not yet tried by hand:** a real build on the PC (its processor and its NVIDIA card), and the recognizer's speed on a PC's processor.

## [0.14.2] - 2026-10-26

The audio bench: every candidate local voice model reads the same five-minute script on a Mac and on a PC, measured and scored the same way, so the next local voice can be chosen on evidence. Nothing a workout uses changes.

### Added
- **`./sweatcast bench`** (`tools/bench.py`, `tools/bench_worker.py`, `docs/audio-bench/`):
  - **The candidates:** Chatterbox Turbo, Qwen3-TTS 1.7B, Lure 0.6B, Ming-3.0-tts 0.5B and Pocket TTS.
  - **The script:** `docs/audio-bench/script.toml`, 44 lines with a kind each.
  - **Where each model runs:**
    - on a Mac, through mlx-audio 0.6.1 (Pocket TTS on the processor);
    - on a PC, on the NVIDIA card, then the small ones on the processor;
    - each in its own throwaway uv environment, pinned to one model revision.
  - **The voice:** every model clones Coach Andy.
  - **Scoring:** one recognizer for both computers (Parakeet TDT 0.6B v3 through ONNX) and `verify.judge`.
  - **Results:** `docs/audio-bench/results/<date>-<mac|pc>/` holds `run.json`, `takes.jsonl`, `summary.md` and a listening MP3 per model.
  - `--quick` checks that every model installs and speaks; `--models` and `--seeds` narrow a run.
- **CLAUDE.md:** "run the MAC audio test harness" and "run the PC audio test harness" run the bench on that computer, then commit and push its results.
- Tests: `tests/test_bench.py`.

### Notes
- **Pocket TTS's voice-cloning weights are gated on Hugging Face.** Each computer needs its terms accepted and `uvx hf auth login` once; without that, the bench records it as gated.
- **Tried on an M5 Mac with `--quick`:**
  - Turbo, Qwen3, Lure and Ming each spoke three lines with no word errors.
  - The PC's PyTorch setups for Turbo and Lure ran on the Mac's processor.
  - Ming on CUDA and Pocket TTS are untried until the PC run.

## [0.14.1] - 2026-10-25

Every local take is now heard before it ships. A speech recognizer checks each clip against its line, renders a take that drops a cue word or breaks down again with the next seed, and stops the build only when four takes in a row lose the same cue. Clips are leveled to one speech level and lightly compressed before the loudness pass. Countdowns lose their ellipses, which made Chatterbox Turbo drop the words after them.

### For forks
- **A Mac downloads 2.5 GB more:** Parakeet TDT 0.6B v3 (`voices.CHECK_MODEL`, pinned), fetched with the coach's model by `./sweatcast setup` or `coaches download`, else on the first build. The readiness check now wants 9 GB free, up from 6.
- **The lint refuses an ellipsis** ("..." or "…") in spoken text. A draft with one fails until it uses commas or periods; `knowledge/tts-rules.md` and the smoke test changed to match. A customized `tts-rules.md` that teaches "Three... two... one..." needs the same change.
- **Exit 1 has a new cause:** a line whose cue word (go, rest, switch, stop, left, right, a count) the voice dropped in every take. The workout skill says to reword it; run `./sweatcast harness sync` after merging the skill.
- **The clip cache gains `<hash>.check.json` verdicts** beside the clips. Clips cached before this release are heard once on their next build, and only failed ones render again.

### Added
- **The take check** (`tools/verify.py`, `render.check_takes`, `engines.listener`):
  - Each new local clip is transcribed and aligned with its line. Digits are read as words, and a compound heard split or joined counts as said.
  - The audio itself is checked for a runaway or cut-off take against the coach's pace, a silence over a second and a half inside a clip, and clipping.
  - A take passes with every cue word said, no audio problem, and at most one word in twenty off. Otherwise the next seeds are tried, up to four takes, and the best is cached under the line's own key, so builds stay repeatable.
  - An unclear line keeps its best take and is listed; a line still missing a cue stops the build and names what was heard.
  - The build record says what was checked (`check`).
  - `./sweatcast build --no-check` skips the check. Web coaches aren't checked (each take is billed), nor is PyTorch on Windows or Linux yet.
- Tests: `tests/test_verify.py`.

### Changed
- **Clip leveling:** each clip's speech is brought to -24 dBFS (at most 12 dB either way, peaks under -1 dBFS) before assembly. Measured takes sat up to 4 dB apart, which the whole-file loudness pass couldn't even out.
- **A gentle compressor** (2.5:1 above -20 dBFS) runs ahead of both loudness passes, so quiet syllables stay audible over gym noise. The smoke test now measures a loudness range of 4.5 LU.
- **Countdowns use commas or periods.** On Chatterbox Turbo, "Three... two... one... and rest." lost "and rest" in three takes of five (seed 42, the default, among them); with commas or periods, nothing was lost in ten takes.
- `cache prune` removes a clip's verdict with it.

## [0.14.0] - 2026-10-25

A second review of the harness, after 0.13.0. The safety gate closes the holes that let an unsafe movement reach the MP3; nothing is paid for before the draft passes its checks, and nothing half-written is left in the delivery folder; the session log takes its facts from the menu and the build instead of retyping them; and two commands, a pantry fallback and the copies of the service list are gone.

### For forks
- **Commands gone:** `./sweatcast lint` (use `./sweatcast build <draft> "<name>" --lint-only`) and `./sweatcast render` (use `./sweatcast build`); both exit 64 naming the replacement. With them go lint without a coach and `--force`, `--strict`, `--wpm`, `--min-fill`, `--max-fill`, `--word-tolerance`, `--require-menu` and `--out`; also `content pantry` (use `content reserve`) and `coaches design --designer`.
- **Run `./sweatcast migrate`** once: it moves `me/workouts/research/pantry/` into `reserve/` (never overwriting; a sheet already in the reserve keeps its place and the pantry's copy goes to the backup unless the two are identical) and rewrites `told.jsonl`'s `pantry` keys. The tools no longer read the old name.
- **`log-session --draft`** now takes the date, length and kit from the draft's menu (a typed `--date`, `--minutes` or `--kit` that disagrees is refused; a session built with `brief --equipment` logs as `custom: <ids>`), needs a build record for that draft, requires `--format`, refuses a second line for the same date and movements, and writes `--loads` and `--rpe` names as the catalog's (a name that isn't one of the session's movements is refused). A customized workout skill's step 7 needs merging.
- **`health.md`:** an `Avoid:` line takes ids, flags (any case) or movement names, and an unknown word now stops the screen, as `--avoid` did; a `[[limits]]` row with an unknown key (`flag` for `flags`) stops it too; `check` notes an injury in the prose with no row. Run `./sweatcast check` after upgrading.
- **Drafts:** every one-word alias is scanned except a short list of everyday coaching words (`menu.EVERYDAY`), so "pushups" or "RDLs" now count; a "no" or "not" excuses a mention only right before it, with only small filler words between ("no rest between jumping jacks" counts). A draft that passed before may now name a movement to reword or declare.
- **Services:** `knowledge/services.toml` is the one list; a fork's own service section needs `key_var`, `key_page` and `candidates`. Skills that grepped `builds.jsonl` for a first web build use `./sweatcast get web-builds`; run `./sweatcast harness sync` after merging a skill.
- **Removed names:** `render.main`, `render.ffmpeg_exe` (use `ffmpeg.exe()`), `tts_build.main`, `tts_build.menu_check`, `personas.last_coach` (use `default`), `personas.WEB_SERVICES`, `context.ROUTE_NAMES`, `context.delivery`, `coaches.archive`, `coaches.last_line`, `coaches.DESIGNERS`, `paths.OLD_PANTRY`, `content.folders`, `content.used_slug`, `reserve(folders=)`. `render.run` and `build_record` now require `draft_path` and `draft_sha256`.

### Added
- **Jumping and sprint moves in the catalog:** burpee, mountain climber, jump squat, tuck jump, jump lunge and skater hop as full movements (impact-flagged, so they reach the menu only where it is safe), and box jump, broad jump, jump rope, running sprint and clap push-up as drafts (never on a menu, but named in a script they stop the build). Before, "twenty burpees" passed the scan for a delicate knee.
- **`./sweatcast get web-builds`:** how many web renders this computer has sent, for the skills' first-web-build notice.
- **`knowledge/research/`:** the evidence behind the knowledge files (training, biomechanics, exercises, equipment), one dated note per question, with an index of what each feeds; the session-structure research moved here from `docs/research/`.
- **A `failed` line in `builds.jsonl`** when a web render sent text and then failed, with the characters sent and the estimated cost.
- Tests: `tests/test_safety.py` (the scan, limits and Avoid lines), `tests/test_log.py` (the session and content log), and tests for every fix below, each failing before it.

### Changed
- **Off-limits rules out impact work, as delicate does.** Before, an off-limits neck, wrist, rib or groin kept jumping jacks, high knees and the treadmill run that a delicate one removed.
- **A pending web coach is designed only after the lint and the menu gate pass**, at its estimated pace; before, a draft that failed its checks had already paid for a voice.
- **The content log** checks each item's category against the ones the plan rotates for its slot, and refuses a reserve slug already told.
- **Backup asks GitHub on every push** whether the remote is private; a remembered answer is used only when GitHub can't say. Pushes run with `ssh -o BatchMode=yes` (unless you set `GIT_SSH_COMMAND`) and give up after five minutes.
- **The workout skill** names a workout's stem one way (`<date>-<goal>-<minutes>`, with `-2` when the folder exists), lints once, and logs with fewer flags; `script.md` points to `tts-rules.md` for paragraph length, names and box breathing instead of repeating them (its `[pause]` limit had disagreed).
- **Simpler code:** the service list in one place, `encode` reusing the render's preflight, and dead constants, wrappers and one-option abstractions removed (about 130 fewer lines in `tools/`).

### Fixed
- **`content plan` and `content reserve` crashed** (0.13.0): a parameter named `folders` hid the function of that name, so the workout skill's filler step failed every session.
- **A brought clip** in M4A, WebM, AIFF or another format was read as raw sound and saved as noise; every clip that isn't a 16-bit WAV now goes through ffmpeg.
- **A `@@ 0` segment** is refused when the draft is read; before, it crashed the render after every clip was rendered (and billed).
- **An unreadable answer from a voice service** (not JSON, or audio that isn't base64) and a dropped connection are service errors with their exit codes, not tracebacks; a dropped connection is retried for speech and never for a design or a save. Keeping an audition candidate marks it before the save is sent, so a voice saved at the service is never lost track of.
- **Delivery, encoding and the web copy are atomic:** the copy to `deliver_to` and ffmpeg's output are written beside the target and renamed, a failed one removed; an ffmpeg failure prints the end of its error. Rebuilding a web copy removes its old parts, and a timeout is a message.
- **Stopping a web render** (Ctrl-C or a failure) stops the retries at once instead of waiting out billed attempts.
- **`coaches measured`** answers 0 for a web coach, pending or made (it needs no smoke test); **`--tolerance`** accepts only a finite value from 0 to 0.5.
- **The profile split and the `.gitignore` update in `migrate`** write atomically.

### Removed
- `docs/superpowers/` and `docs/plans/` (shipped plans and specs; in the history), and `docs/eval/skeletons.sh` (the retired composer's baseline).

## [0.13.0] - 2026-10-25

A review of the whole harness, hardened where a check could be skipped and simplified where the same rule lived in several places. The build runs in one process; the menu is today's or the build stops; a key can't leak into a message; the tools exit with the documented codes from every entry point; and the code for sweatcast 0.8 and earlier is gone.

### For forks
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it) from a `me/` at sweatcast 0.9 or later. A folder from sweatcast 0.8 or earlier (context schema 3 or below) is no longer migrated here: check out `v0.12.0`, run `./sweatcast migrate` there, then come back and run it again; the tool says so.
- **Gone:** `--voice` (use `--coach`) on build, render, lint, brief and log-session; `./sweatcast voices` (use `coaches`); `./sweatcast get default-voice` and `get voices` (use `get coach` and `coaches`); the sweatcast 0.8 voice import and `migrate --name`; the profile template's `## Narrator` section (how a coach talks lives in `persona.md`). `./sweatcast check` is its own tool (`tools/check.py`); `context.py check` is no more.
- **The menu is today's.** `./sweatcast brief --save` now records the day and a hash of `me/health.md` in the menu, and a build (or `./sweatcast render`) stops on a menu from another day or from before `health.md` changed; `--lint-only` warns. Rerun the brief with `--save` and build again. A menu saved by 0.12.x has no hash, so the first build after upgrading asks for a fresh brief. `./sweatcast render` and `./sweatcast lint` now hold a draft to its menu as `build` does; only `knowledge/smoke-test.draft.txt` itself builds without one (a copy of it elsewhere doesn't).
- **Drafts:** the text scan now reads one-word movement names (deadlift, thruster, woodchop, clamshell, inchworm, elliptical), spaced plurals ("push ups", "step ups"), and a shortened name that is itself another movement ("push-ups" after a declared wall push-up, "shadow boxing" after a declared seated shadow boxing); a "no" or "not" excuses a mention only in its own clause. A draft that passed before may now name a movement to reword or declare.
- **`log-session`** refuses a coach that doesn't exist (archived ones still log), a kit that isn't one of the profile's or a preset, a format that isn't a `sessions.toml` method, and any line break in a field. **`content log`** accepts the slot as the plan names it ("deep dive") and refuses a reserve slug with no sheet.
- **The template** (`me.example/`): `health.md`'s clinician line is `- Rule: [...]`, `content.md`'s "Never bring up" takes a hint (write "nothing" for none), an empty `- Label:` line is noted as unfilled in every file (a note, so a 0.12.x folder's empty lines don't fail `check`); `knowledge/sessions.toml` drops the retired composer's `blocks`, `min_slots` and `fixed` keys (a fork's copy keeps working; the loader ignores them).
- A customized workout skill needs merging: the brief and the lint take `--coach`, the "Would open up" rerun uses `brief --add <item>`, and steps 6 and 7 explain a stale menu and a malformed `--item`. Run `./sweatcast harness sync` after.

### Added
- **`brief --add <ids>`:** equipment on hand today, added to the kit, so the kit's weights still print (in place of rerunning with `--equipment`).
- **`./sweatcast backup --unverified`:** pushes when GitHub won't say whether the remote is private (after you checked); without it, such a push is refused, as a public one is.
- **`tools/check.py`**, `tools/fileio.py` (one atomic writer for every record, menu and context file), `tools/common.sh` (what the shell scripts share), `tests/helpers.py` (test isolation: every path redirected to a temporary home; a fixture draft given its menu).
- **Tests** for every bypass and gap this review closed: the render command needs a menu, the smoke test is known by its place, a stale menu, a changed health file, the scan cases, a key with a stray character, the hook's path list, backup's refusals, a long `Retry-After`, an unclosed `+++` block, one bad coach file, `--no-web` in a cloud session, unknown build flags, `cache prune` under the lock.

### Changed
- **One build process.** `./sweatcast build` parses its flags with argparse (an unknown flag exits 64 before anything runs or costs money), resolves the coach and route once, reads the draft once, and runs the lint, the menu gate and the render on that same text, so nothing can slip in between the lint and the render. The render's native chatter is logged by pointing the standard error descriptor at `me/workouts/.logs/<name>.log`, which is appended to with a dated line. `render.run`, `render.clips` and `render.follow` are what it calls; `./sweatcast render` is a thin wrapper that enforces the same menu rule. In a cloud session, `--no-web` now keeps the MP3 instead of deleting it.
- **One exit-code mapper:** `cli.run` wraps every tool's `main`; an unknown coach, a missing draft, a web coach with no key here and a bad `--engine` exit 64 from every command (before, 1 or 64 depending on which tool caught it); a service's refusal exits 4 everywhere; `screen.Unfit` exits 1.
- **One place each** for the service names (`cloud.service_name`), the render list (`context.render_preferences`), coach matching and folder listing (`personas.find`, `personas.persona_dirs`), the smoke test (`draft.is_smoke`), the build record's path (`workouts.record_path`), float-to-PCM, the version lookup, and movement-name matching (`catalog.resolve`: side words, plurals, hyphen or space). The lint predicts no chime under `--no-chime`, computes each segment's paragraphs once, and uses the render's rule for a held segment.
- **The shell scripts** share `tools/common.sh`; setup reads the render list through `./sweatcast get routes` instead of `sed` over TOML, keeps a `core.hooksPath` it didn't set, and matches `.env` literally.
- **`knowledge/sessions.toml`** carries only what the writer sees; the brief prints each method's work and its own rest (a circuit's rest between rounds).
- **`./sweatcast movements`** defaults to the profile's level.
- **Research paths** (`feeds`, `youtube`, `content`) are read at call time, so a redirected home redirects them too.

### Fixed
- **Keys:** a key is stripped of the whitespace around it, one holding a line break, a space or a symbol is refused by name (never shown) where it would be used, and counts as "not set" to the coach list, the default coach and the readiness check (so one bad key for a service you don't use stops nothing else; `./sweatcast keys` names it), an inline `# comment` isn't part of it, and every message the engine prints is scrubbed of key values. Before, a key with a stray line ending in the environment made the HTTP client raise an error whose text held the whole key, which the render and the audition printed.
- **The pre-push hook** now covers a renamed context folder (`me.real/`), the old top-level layout's files, `.env`, `personas/` and `voices/`, and spares only `me.example/`; its pattern has a test with must-match and must-not-match lists.
- **Backup** refuses any file named like a key file, not only `.env`, and fails closed when a GitHub remote's visibility can't be read (`--unverified` pushes once you've checked, and the answer is remembered for that remote on this computer, as is a "private" GitHub gave; a `GH_TOKEN` or `GITHUB_TOKEN` in the environment lets the read see a private repo, as on Claude Code on the web); `git` never waits on a credential prompt.
- **An unclosed `+++` block**, or a byte order mark from a Windows editor, no longer reads as "an older format, run migrate" (which would have wrapped the settings as prose); `check` names the broken block. One coach file the tools can't read no longer hides the others.
- **A 429 with a long `Retry-After`** is a quota, exit 4, instead of being slept through (up to five waits of an hour). A 5xx page mentioning "payment" is an outage, not a billing refusal. Fish Audio, ElevenLabs and Inworld designs (billed) are never retried after sending.
- **Before a clip is rendered** (or billed), the render checks ffmpeg is here and the output name ends in `.mp3`, `.m4a` or `.wav`.
- **`cache prune`** waits for the render lock, so it never deletes a clip a render is reading.
- **Windows:** a delivery folder on another drive no longer crashes `paths.show`; a missing `sh` leaves the readiness facts readable instead of crashing every build.
- **`pace.json`** records a short hash of the computer's name, not the hostname.
- **`harness`** copies a binary file in a skill, removes a dropped skill's subfolders, writes the Codex rule path with forward slashes on every system, and checks the three `.env` deny rules are still in `.claude/settings.json`.
- **`check`** notes a setting no tool reads (`deliver-to`: did you mean `deliver_to`?) and finds the quick-start flag beside the files it checks.

### Removed
- Migration from context schemas 0 to 3 and the sweatcast 0.8 voice import (`to_1` to `to_4`, `plan_coaches`, `make_coaches`, the `v0.8.1` clips, `tests/test_migrate4.py`, `tests/v8.py`); `--voice`, `./sweatcast voices`, `get default-voice`, `get voices`; `context.voices`, `default_voice`, the schema-1 `---` front matter and the legacy profile parser; `sessions.all_out`; the unreachable `setup` and `doctor` branches in `tools/sweatcast.py`; the `## Narrator` section.

## [0.12.0] - 2026-10-25

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

## [0.11.1] - 2026-10-25

The README, CLAUDE.md and AGENTS.md are rewritten to be shorter and checked claim by claim against the code, and sweatcast can now be supported.

### Added
- **Support:** a Sponsor button on the repo (GitHub Sponsors and Ko-fi, `.github/FUNDING.yml`) and a line at the end of the README.
- **Invite a friend:** one message at the top of the README that works for someone with Claude or ChatGPT.

### Fixed
- **README:** segments don't all start on the clock (a segment with spare time ends early; only the total is held to plan); the disk and download figures now match the readiness check (6 GB free; about 4 GB on a Mac, up to 8 GB on Windows or Linux); the backup command commits before pushing and says it needs the GitHub CLI; Qwen3's render speed is no longer folded into Chatterbox's; Windows needs Git for Windows; an audition needs a voice key; coach folder names; and the license list covers Linux and the MLX tokenizer.
- **CLAUDE.md:** reorganized (what runs when, the listener's files, knowledge, tools by area, tests, audio, releases) with the errors fixed: the `render` setting lists routes, not engines; the lint doesn't read `words_per_minute`; the default web coach is made during setup's quick start; the feeds sheet's path; the `render` command and `test_tools.py`; the release rule now covers 0.11.0.
- **AGENTS.md:** tighter, and it gives every reason `./sweatcast` runs outside Codex's sandbox.
- **The setup skill** quotes the same download sizes as the README.
- **The profile template's `words_per_minute` comment** said the lint uses it; it doesn't.

## [0.11.0] - 2026-10-25

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

## [0.10.4] - 2026-10-25

Onboarding is tidied for the two ways people actually start: a developer in an IDE or terminal, and a friend with the Claude desktop app. Claude Code on the web no longer sets up a new listener.

### Added
- **`./sweatcast show <file>`** opens the folder holding a file with it selected (Finder, Explorer or the file manager). Setup and the workout skill use it when the MP3 or a test clip can't be sent into the chat, so a listener never gets just a path.
- **Send this to a friend:** a README section with a message to paste to someone who has the Claude desktop app.

### Changed
- **The desktop path, step by step.** The README's Start here says which folder to pick when the Code tab asks (the home folder), to click Allow, and how to start the second session in the new `sweatcast` folder; the For Claude handoff uses the same literal steps.
- **One recommended voice service.** When a web coach is needed, setup recommends Fish Audio for a first key and walks through it with links (sign up, add credit, make a key), listing the other three with their key pages as more choices.
- **The phone folder comes right after the first workout,** as one question (iCloud Drive, Google Drive, Dropbox, or keep them on this computer), instead of waiting for "finish setting me up".
- **Claude Code on the web doesn't set up a new listener.** Setup and the README's For Claude section point to the desktop app instead. A listener already set up, with their private context repo attached, keeps working there.

## [0.10.3] - 2026-10-25

A new listener hears their stand-in coach before the first workout, and coach folders say where each coach speaks.

### Added
- **A test clip before the first workout.** Coach Andy, the local stand-in, ships with `sample.mp3`, fifteen seconds rendered on Chatterbox Turbo, which setup plays first. A web stand-in is made right after the key step (`./sweatcast coaches make`, its cost said first) rather than at the first build, and setup plays the clip that saves; a designed voice belongs to the account that made it, so each listener's is their own. Either way: if he isn't right, "I want a new coach". The setup skill, README, voices guide and CLAUDE.md say so.

### Changed
- **Coach Demo is Coach Andy**, in `me.example/personas/coach-andy-local/`, with "Coach Demo" kept as an alias, so log lines naming him still find him.
- **Coach folders name where the coach speaks:** the web stand-ins are `coach-reed-fish/`, `coach-ellis-elevenlabs/`, `coach-nolan-gemini/` and `coach-owen-inworld/`, and a coach kept from now on gets `coach-<name>-<service>` or `coach-<name>-local` (`personas.folder_for`). A coach already in a folder keeps it, and lookup by the plain slug (`coach-maya`) still finds `coach-maya-fish`.

### For forks
Nothing to migrate: folders in `me/personas/` keep their names, and renaming one by hand to the new pattern is safe (pace and sample move with it; cached clips are keyed by the voice, not the folder). The new stand-ins come only with a new `me/`; to have Coach Andy's clip, copy `me.example/personas/coach-andy-local/sample.mp3` beside your Coach Demo.

## [0.10.2] - 2026-10-25

The pantry is now the reserve: the evergreen filler (quizzes, things to enjoy, things to learn) researched ahead of time.

### Changed
- **The reserve.** `me/workouts/research/reserve/` holds the evergreen pieces, `./sweatcast content reserve` lists the unused ones, the plan prints "Reserve" and "The reserve is low", `knowledge/content.toml`'s per-slot target is `reserve`, and `./sweatcast content log` writes a piece's slug under `reserve`. The workout skill, its research templates, the script guide, the README and CLAUDE.md say the same.
- **CLAUDE.md** opens with the codegraph index: use the codegraph tool to find and read code, its callers and what a change touches, before grepping.

### For forks
Nothing to migrate. A `research/pantry/` folder is still read beside `research/reserve/` (a slug in both counts once), a record item logged with `pantry` still marks its piece as told, and `./sweatcast content pantry` still works as an alias. New pieces go to `reserve/`; move the old sheets over whenever you like.

## [0.10.1] - 2026-10-25

Setup now opens with the one big choice: where the coach's voice is made.

### Added
- **The fork, said first.** Right after the readiness check and before any question, the setup skill lays out local versus web in a few plain lines: on this computer (free and private, a one-time 3 to 4 GB download, about 0.7 times the speech's length to render on Apple Silicon) or a web coach (no download, a 30-minute workout in a minute or two, about $0.27 to $1.60 a workout with a key of your own, and the script goes to the service). It says which way this computer starts, and how to revisit it: nothing is locked in, both kinds can live side by side, and "I want a new coach", "add a voice key" or "set up local voices" changes it at any time. The README's Start here says the same.

### Changed
- **A renamed context folder stays private.** The engine's `.gitignore` now ignores `me.*/` (such as `me.real/` or `me.test/`, kept aside while trying the new-listener flow), with `me.example/` still part of the engine.

## [0.10.0] - 2026-10-25

Web coaches: describe, audition, approve, keep. A web coach is an original voice a service designs from the listener's description and saves in the listener's own account, at Fish Audio, ElevenLabs, Gemini or Inworld, pay-as-you-go with no subscription anywhere. One audition makes candidates on every service with a key, lettered and priced a workout; the listener picks by ear, names each one they keep, and a workout then uses it by name, always on the service that made it. Four default web coaches ship, one per service, designed the first time they're used. Copying a clip on the web is gone, and so are Cartesia and Deepgram: a clip-based coach is now a local coach, which renders only on the computer's own engine.

### For forks
This release changes the coach files (persona schema 4 to 5), the routes, the keys and the coach commands. After pulling it:
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it). Every coach's `persona.md`, archived ones too, gains `kind = "local"` and `schema = 5`, and nothing else in it changes; `me/.gitignore` gains `!personas/*/sample.mp3` and `!personas/.archive/*/sample.mp3` (a web coach's approved sample is kept, archived or not), `personas/.auditions/` (auditions in progress aren't) and `personas/*/.made.json` and `.made.wav` (a make between saving a voice and writing the coach). Changed files are backed up first, never `.env`.
- **Your existing coaches are local coaches now.** A clip-based coach renders locally only: clip copying on Fish Audio (the clip sent with every request) and ElevenLabs (a clone of the clip) is removed, along with `services.json`. A coach you used on Cartesia or Deepgram renders locally, or make a web coach with an audition ("I want a new coach", or `./sweatcast coaches audition`).
- **The profile's `render` list orders local engines only.** A web coach always speaks through its own service, whatever the list says; a service named there no longer renders a local coach. A local coach tries the local engine even when the list leaves it out; where local voices don't run (say Claude Code on the web, with `["fish"]` and only local coaches), `get route` and the build stop (exit 1) and name the way out: make a web coach, or copy the stand-in for a service with a key (`me.example/personas/coach-reed/` for Fish Audio, and so on) into `me/personas/`. The readiness check on the web says "No web coach yet" with the same way out, and the workout skill offers both. `cloud_max_chars` still caps what one build sends.
- **Keys:** `GEMINI_API_KEY` and `INWORLD_API_KEY` are new (`./sweatcast keys init gemini`, `init inworld`); `CARTESIA_API_KEY` and `DEEPGRAM_API_KEY` are no longer read, so delete their lines from `me/.env`. `./sweatcast keys open` opens `me/.env` in the system's editor. On Claude Code on the web, the network allowlist gains `generativelanguage.googleapis.com` and `api.inworld.ai`.
- **The four default web coaches come only with a new `me/`.** To have them, copy `me.example/personas/coach-reed/`, `coach-ellis/`, `coach-nolan/` and `coach-owen/` into `me/personas/`; each is made the first time a build uses it.
- **A sweatcast 0.8 folder migrates only from a git clone** with the `v0.8.1` tag (`git fetch --tags`): `tools/migrate-assets/v8-voices/` is gone, as promised for 0.10.0, and the migration reads the clips sweatcast 0.8 shipped from the tag. A ZIP download can't migrate one.
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
- **`tools/migrate-assets/`** (the clips sweatcast 0.8 shipped; the migration reads them from the `v0.8.1` tag) and **`tools/msgpack_min.py`**.

## [0.9.3] - 2026-10-24

ElevenLabs and Cartesia tried live, and setup says plainly that both need a monthly subscription.

### Changed
- **ElevenLabs and Cartesia are tried live** (`knowledge/services.toml`): a smoke test and a 10-minute workout on each, from a Mac, both within 1% of plan. Only Deepgram is still "not yet tried live".
- **Subscriptions:** copying the coach's voice from a clip (cloning) isn't on either service's free or pay-as-you-go plan: ElevenLabs needs Starter (about $6 a month) and Cartesia Pro (about $5 a month). The setup skill says so before the listener picks one, and the README and `knowledge/voices.md` show it. Fish Audio needs no subscription for this.
- An ElevenLabs key needs two permissions when it's made, Text to Speech and Voices: write; the setup skill and README say so.

## [0.9.2] - 2026-10-24

The README now starts where a new listener starts: "Can you use https://github.com/RNCDev/sweatcast and set me up?"

### Changed
- **README:** a Start here section (asking Claude with the link, what you need, what to say after setup, doing it yourself), a "Where it runs" table that says Claude Code on the web needs a GitHub account, and a "For Claude" section: how a Claude session outside a copy of the repo downloads it to `~/sweatcast` (git or the ZIP, no GitHub account needed) and hands over to a session opened in that folder, where the project's instructions and safety settings load.
- No GitHub account is fine: the README and the setup skill say `me/` then stays on the computer, and how to keep a copy.
- CLAUDE.md points to the README's "For Claude" section.

## [0.9.1] - 2026-10-24

A stranger's first workout in minutes, Claude Code on the web, and a folder per workout. Setup's quick start asks four questions and starts the listener with Coach Demo, a stand-in coach that ships measured, so the first ten-minute workout needs no voice design and no smoke test. Claude Code on the web runs sweatcast with a cloud voice, and the workout arrives as a page with a player. Each workout's files now live together in their own folder.

### For forks
This release moves files in `me/workouts/` (schema 4 to 5). It changes the `me/` layout, which the project's rules call a major release; it's released as a minor one at the maintainer's call, since `./sweatcast migrate` does everything. After pulling it:
- **Run `./sweatcast migrate`** (or `./sweatcast setup`, which runs it; `--dry-run` lists the moves first). Each draft in `workouts/drafts/` moves with its brief and menu to `workouts/<stem>/`, and each build's script and record moves beside the draft its record names (or the one draft from the same date). Smoke tests, and anything that can't be placed for sure, go to `workouts/checks/`; each day's research sheet and feeds go to `workouts/research/daily/`. Nothing is overwritten (a clash gets " (2)"). The context files change only their schema number; `me/.gitignore` gains `!*.web-*.mp3`.
- **Coach Demo** comes only with a new `me/`. To have it in yours, copy `me.example/personas/coach-demo/` into `me/personas/`.
- A customized workout skill needs its paths updated: the draft is `me/workouts/<stem>/<stem>.draft.txt`, and the feeds sheet `me/workouts/research/daily/<date>-feeds.md`. `SWEATCAST_ALLOW_CLOUD_SESSION` is gone.

### Added
- **Coach Demo** in `me.example/personas/coach-demo/`: sweatcast 0.8's public Chatterbox Coach clip with its measured pace on Chatterbox Turbo (MLX and PyTorch) and Fish Audio. It's marked `placeholder = true`: `./sweatcast check` notes it, `./sweatcast coaches` marks it a stand-in, and a build with no coach named picks any other coach before it.
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

## [0.9.0] - 2026-10-24

A standalone sweatcast: any reasonable computer, any voice engine, and coaches of the listener's own. Local audio now runs on Linux too, and on the processor where there's no NVIDIA card (experimental); a cloud voice with the listener's own key works on any computer, an Intel Mac included. Voices become coaches: a person's name, how they talk and a clip every engine copies, kept in `me/personas/`, so the same coach sounds the same locally or in the cloud.

### For forks
This release changes the `me/` layout (schema 3 to 4), the commands and the environment. After pulling it:
- **Run `./sweatcast setup`.** It migrates `me/` (backing up the changed files to `me/.backup-<time>/` first, never `.env`), installs the local engine as an extra where this computer runs one, and suggests moving models you already have.
- **Voices become coaches.** Each voice in the profile's `[[voices]]` becomes a folder in `me/personas/`, with its clip, words and measured pace: Chatterbox Coach becomes Coach Julius and Qwen3 Coach becomes Coach Solo, keeping their old names as aliases, so old log lines and `--voice "Chatterbox Coach"` still find them. The profile's `## Narrator` lines become how each coach talks (`## How this coach talks` in `persona.md`). Cached clips stay valid. A private voice named for a model needs a person's name: `./sweatcast migrate --name "<old>=Coach <Name>"`. `me/voices/` and `workouts/.audio-cache/voice-pace.json` move into the backup.
- **The profile** loses `[[voices]]` and gains `render = ["local"]`, the audio routes in order of preference; add a cloud service there (`["local", "fish"]`) to use one where local doesn't work. `cloud_max_chars` (default 30,000) caps what one build sends.
- **Commands:** `--voice` is now `--coach` on build, render, lint, brief and log-session (the old name still works); `./sweatcast voices` is now `./sweatcast coaches`; `./sweatcast get default-voice` is `get coach`. New: `doctor`, `keys`, `models`, `coaches`, `get route`, `build --engine`. The smoke test moved to `knowledge/smoke-test.draft.txt`. `voices/` is gone; the clips sweatcast 0.8 shipped wait in `tools/migrate-assets/v8-voices/` for the migration, until 0.10.0.
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

## [0.8.2] - 2026-10-24

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

## [0.8.1] - 2026-10-23

### Fixed
- On Windows, `./sweatcast` prints in UTF-8, so a video title or headline with an emoji no longer crashes `./sweatcast youtube pick` (the console's default code page couldn't encode it).
- The pantry research template said "he" for the listener in one place; it says "they" like the rest.

## [0.8.0] - 2026-10-23

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

## [0.7.2] - 2026-10-23

Faster from check-in to MP3, with the same audio, and a smaller engine. The coaching is written while research runs, and the voice renders each paragraph as it lands in the draft, so the render mostly overlaps the writing instead of following it. The old session composer is retired: about 900 fewer lines of tools and 600 fewer of tests.

### For forks
- `./sweatcast session` is gone. The workout skill hasn't used it since 0.7.0 (`./sweatcast brief` plans); `docs/eval/skeletons.sh` runs it from the v0.7.1 tag as the eval's baseline. Code that imported `tools/session.py` for the safety screen imports `tools/screen.py` (`screen`, `Screen`, `Unfit`, and the helpers under public names: `ids`, `clamp`, `healthy_side`, `would_open`, `cue_lines`, `loads_line`, `parse_limit`, `words`).
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

## [0.7.1] - 2026-10-23

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

## [0.7.0] - 2026-10-23

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

## [0.6.2] - 2026-10-22

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

## [0.6.1] - 2026-10-22

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

## [0.6.0] - 2026-10-22

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

## [0.5.4] - 2026-10-22

### For forks
Nothing to migrate. To back up your context, make `me/` its own private repo (README, "Back up `me/`"); rerunning `./sweatcast setup` adds `me/.gitignore` if it has none.

### Added
- `./sweatcast backup` (`tools/backup.py`): commits everything in `me/` and pushes it, when `me/` is its own git repo, nested in the engine's folder and ignored by the engine's git. It changes nothing when `me/` isn't its own repo, and refuses to push to a repo GitHub reports as public.
- The workout skill's last step runs it, after the build and the log, so each session lands in the listener's private repo.
- `me.example/.gitignore`: leaves the clip cache (but not the voices' measured pace), MP3s, render logs, unkept voice takes and migration backups out of that repo. Setup copies it into a new `me/` and adds it to an existing one.

## [0.5.3] - 2026-10-22

### Changed
- Safety: an off-limits ankle or foot now rules out anything done standing, which puts weight through both feet whatever the catalog rates the ankle, and the seated bikes and air bikes rate ankle 1 and foot 1, so an off-limits ankle keeps them out while a delicate one still allows them. A case `--limit` line says "and nothing done standing", and the injury playbook says both.

## [0.5.2] - 2026-10-22

### Changed
- `./sweatcast build` removes the local MP3 once every copy in the profile's `deliver_to` folder is in place and matches; `me/workouts/` keeps the script's `.txt` and `.build.json` as history. A failed copy, or no delivery folder, keeps the MP3 in `me/workouts/`.
- The setup skill's delivery step says so, and a request to change where workouts go runs that step alone; the profile template's `deliver_to` comment matches.

## [0.5.1] - 2026-10-22

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

## [0.5.0] - 2026-10-22

The fixes from the second judged run of the grid: interval work that is hard enough, warm-ups that start easy, paired sets that can be spoken as pairs, rests that match the clock, and caps on volume. The catalog and the session rules each move up a format.

### For forks
Breaking: the catalog moves to format 3, `knowledge/sessions.toml` to format 2, and paired-sets drafts get a marker per pair set. After pulling:
1. If you keep private movements in `me/movements.toml`, they are now loaded (0.4.x ignored the file). Run `./sweatcast check`: every finished conditioning entry needs `effort = "easy"`, `"moderate"` or `"hard"`, and it lists any entry missing one or carrying another fault. Until it is fixed, a faulty entry is held back as a draft and never planned.
2. A fork that edits `knowledge/movements.toml` or `knowledge/sessions.toml`: set `format = 3` and `format = 2`, add `effort` to every finished conditioning movement, and keep the new dose keys (`bodyweight_reps` above novice, `efforts_per_session`) in every conditioning level. `./sweatcast test` names anything missing.
3. Drafts written under 0.4.x markers still render. A new paired-sets draft is written under one marker per pair set ("Pair 1 of 3, set 2 of 3: ..."), a circuit round's marker names the rest that ends it, and interval markers are numbered by block.
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

## [0.4.0] - 2026-10-22

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

## [0.3.2] - 2026-10-21

### Added
- The movement catalog, `knowledge/movements.toml`: every movement a session can use, with its equipment, muscle groups, spoken setup and cues, and tags for what it loads, plus kit presets. `tools/catalog.py` reads and checks it.
- `./sweatcast movements`: lists the movements a kit allows (`--preset` or `--equipment`), minus any `--avoid` tags, by group.
- Weekly counts in `./sweatcast coverage`: a group the last seven days neglected comes first, even when the last session touched it.
- Plural-tolerant name matching: a logged "goblet squats" or "right glute bridge" resolves to the catalog movement.

### Changed
- The equipment library is now `knowledge/kits.md`: what each kit usually holds and how to script around it. Its movement lists moved to the catalog.
- The workout skill picks movements from the filter's output, avoiding the injury playbook's new "Tags to avoid early" for each injury in an early phase, then applies the health file and the playbook on top.

## [0.3.1] - 2026-10-21

### Fixed
- Inconsistent injury tags in `knowledge/equipment-library.md`: a movement now carries the same tags everywhere it appears (the strictest set), and movements that load a joint but had no tags now have them.
- Removed listener-specific names: a named gym and a bike brand left two headings, which now read "Full gym" and "Stationary bike".

## [0.3.0] - 2026-10-21

Simpler to set up and to run: one `./sweatcast` command, the profile's settings in one block at the top, a check that says what's still to fill in, and a voice designer for a coach that sounds the way you want.

### For forks
Breaking: commands, the profile's format and the Python they run on all change. After pulling:
1. Run `./sweatcast setup`. It migrates `me/` (backing it up to `me/.backup-<date and time>/` first). In `profile.md`, the Voices list, "Copy finished MP3s to:", "Measured words per minute", the YouTube favorites and Puzzles handles, and the Feeds section move into a TOML block between `+++` lines at the top. Their lines leave the prose, and one sentence says where they went. The other context files only change their front matter. `./sweatcast migrate --dry-run` shows what would change. A 0.1.x folder migrates in the same run.
2. Run `./sweatcast check`. It lists anything the tools can't read and any line still showing the template's `[hint]`.
3. Call tools as `./sweatcast <command>`: `python3 tools/feeds.py` is `./sweatcast feeds`, `tools/build.sh` is `./sweatcast build`, `LINT_ONLY=1 tools/build.sh` is `./sweatcast build ... --lint-only`, `ALLOW_ESTIMATED=1` is `--allow-estimated`, `python3 tools/context.py log-session` is `./sweatcast log-session`, and `voices.py --measured` and `--download` are `voices measured` and `voices download`. `./sweatcast help` lists everything. The project permissions now allow `./sweatcast` instead of each tool.
4. The tools need Python 3.11 (the project's `.venv`); the Mac's own `python3` no longer runs them. Tests run with `./sweatcast test`.

### Added
- **`./sweatcast`**, one command for everything, run in the project's environment: `setup`, `build`, `lint`, `render`, `voices`, `feeds`, `coverage`, `youtube`, `check`, `get`, `deliver`, `log-session`, `migrate`, `cache`, `test`. `./sweatcast setup` needs no Python first. One permission rule covers every command the skills run.
- **Voice design:** `./sweatcast voices design "<name>" "<description>"` renders takes of a coaching line in a voice made from a written description (Qwen3-TTS VoiceDesign, pinned; about 4.5 GB the first time). `./sweatcast voices keep <take> --engine chatterbox --default` makes the chosen take a private voice in `me/voices/` and adds it to the profile. The setup skill offers it during the interview, for a woman's voice, say, or another accent; `knowledge/voices.md` has a "Design a voice" section.
- `./sweatcast check` flags every profile line still showing the template's `[hint]`, any feed not filled in, and a missing voice. It also notes, without failing, a missing delivery folder or no feeds.
- Schema 2 and its migration step, chained after 0.2.0's, with tests that migrate 0.1.x and 0.2.x folders.
- Tests for the wrapper, voice design and keeping, adding a voice without losing the settings' comments, and the new check: 102 in all.

### Changed
- The profile's settings live in TOML front matter (`+++`), read with Python's own `tomllib`: `voices` (`[[voices]]` name and description; the first is the default), `deliver_to`, `words_per_minute`, `youtube_favorites`, `puzzles` and `[[feeds]]` (label, kind, value). The tools no longer depend on how a line in the prose is worded.
- `./sweatcast feeds` skips feeds that aren't filled in yet, rather than listing them as failures.
- `tools/youtube.py` no longer restarts itself under `.venv`; `./sweatcast` runs everything there.
- The README's getting started is three steps: install ffmpeg and uv, clone, say "set me up". There's also a commands table.
- The setup skill writes the settings block, offers a designed voice, and runs `./sweatcast check` until it passes. The workout skill uses `./sweatcast` throughout.

### Removed
- Running the tools with the system `python3`, the `LINT_ONLY` and `ALLOW_ESTIMATED` environment switches, and `voices.py --measured` and `--download`.

## [0.2.0] - 2026-10-21

The engine's audit, fixed: one owner for the listener's files with a versioned format and a migration, safer state on disk, a privacy guard that checks every commit, consistent exit codes, and a record of how each MP3 was made.

### For forks
Breaking: the context files now carry a format version, and tools refuse an older folder until it's migrated. After pulling:
1. Run `tools/setup.sh` (or `python3 tools/migrate.py`). It backs up `profile.md`, `health.md`, `log.md` and `exercise-science.md` to `me/.backup-<date and time>/`, then adds a three-line front matter (`---`, `schema: 1`, `---`) to the top of each. Nothing else in them changes. `--dry-run` shows what it would do.
2. Run `python3 tools/context.py check`. It lists any line the tools can't read, such as a log line with a field missing, with its line number.
3. Clips cached before 0.2.0 render once more, since the cache key now includes the mlx-audio version. Right after upgrading, `python3 tools/cache.py prune --days 0` frees the old ones (it removes every cached clip, so run it before your next build, not after).
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

## [0.1.1] - 2026-10-21

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

## [0.1.0] - 2026-10-21

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
- The clip cache key includes the model revision, so clips rendered before 0.1.0 render once more.

### Removed
- OmniVoice and every VoiceStudio dependency: the VoiceStudio voice database, OmniVoice's text helpers, the OmniVoice render options (`--steps`, `--guidance`, the temperatures, `--speed`) and the re-launch under VoiceStudio's Python.
- The author's profile, log, drafts, scripts and research from the public repo's current tree. They remain in the git history of earlier versions.

## [0.0.6] - 2026-10-21

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

## [0.0.5] - 2026-10-21

Timing that holds the whole workout to plan instead of every segment, and brain teasers for the quiz.

### Added
- `tools/youtube.py puzzles`: lists recent videos from a new Puzzles line in `knowledge/profile.md` (Presh Talwalkar's MindYourDecisions) that haven't been used as a quiz yet. The headlines agent picks one that works by ear, saves its transcript and writes `workouts/research/puzzles/<id>.md` (the puzzle as said aloud, the answer and the reason); a puzzle with a sheet isn't offered again. The session's quiz beat uses it when there is one, and falls back to the session's own material.
- `tts_build.layout`, one timing layout shared by the lint's prediction and the render, so they agree.
- Tests for the new timing and the puzzle list: 49 in all.

### Changed
- A segment with time to spare widens its paragraph breaks (up to about two seconds each), keeps a short tail and ends early instead of padding with silence. A segment that runs long is still paid back from the next ones' spare time.
- Only the whole workout is held to plan, within three percent either way. The lint prints the predicted length and blocks only when the total is off by more than that, or when a segment is far off its slot (under 80 or over 110 percent of it, down from 90 to 100). The render exits 2 only when the finished workout is more than three percent over or under plan; `--tolerance` now sets that total allowance.
- The workout skill, `CLAUDE.md`, `README.md`, `knowledge/tts-rules.md` and `knowledge/voices.md` describe the new timing and the puzzle quiz.

## [0.0.4] - 2026-10-21

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

## [0.0.3] - 2026-10-21

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

## [0.0.2] - 2026-10-20

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

## [0.0.1] - 2026-10-19

First working version.

### Added
- The `workout` skill: check-in, plan, background research, script, build and log.
- `tools/build.sh`: lint, `.txt` export, OmniVoice render with per-segment padding and loudness normalization, and a copy to Google Drive.
- Spoken-length prediction per VoiceStudio voice.
- `tools/youtube.py` for video deep dives from favorite channels.
- Profile, injury playbook, equipment library, exercise science and text-to-speech rules.
