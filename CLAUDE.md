# HarmonicFitness: a workout podcast, made fresh each session

**Code introspection:** a codegraph index (`.codegraph/`, git-ignored) covers the engine; use the codegraph MCP tool (`codegraph_explore`) to find and read code, its callers and what a change touches, before grepping or reading files. After moving or renaming files, run `codegraph init` again to refresh it. This file holds the rules and the map; what each function does is in the code.

HarmonicFitness turns a request for a workout into a narrated MP3 for earbuds, with no screen and no timer. The audio is the workout: it tells the listener what to do, keeps them company, and moves them along on time. The coach coaches a movement fully the first time and briefly after, so the rests carry the listener's world, each story wrapped in `[story]` ... `[/story]`. Only the total is held to plan, within five percent either way: a natural voice matters more than exact timing.

Priorities, in order: safe for the listener's body today, clean to the ear, worth listening to.

The README is for people (what it is, how to start, costs); `docs/index.html` is the one-page map of how the parts connect, and `docs/style-guide.html` the house style for words, terms and visuals.

## What runs when

- **Any request for a workout, in any words,** runs the `workout` skill (`.claude/skills/workout/SKILL.md`): check-in (asked first, from the profile, health and log alone), research, the brief, design, script, build, log and backup.
- **Getting started** ("set up harmonicfitness", "set me up", "finish setting me up"), **or changing the profile, injuries, topics ("update my interests"), feeds, audio route or delivery,** runs the `setup` skill, as does a workout request when `me/profile.md` doesn't exist yet. Its quick start is one round of questions, one web key where local voices don't run (`keys init`, then `keys open`), a coach chosen by ear from samples, and a ten-minute workout; the rest waits for "finish setting me up" (`setup = "quick"` in `me/settings.toml` until then).
- **"I want a new coach", in any words, at any point,** runs the `coach` skill: "switch coach" picks another stock coach by ear; a coach of their own is a web coach (keys, describe, audition across every keyed service, approve and name). Local coaches are chosen, never made.
- **A request from outside a copy of this repo** ("use https://github.com/RNCDev/harmonicfitness and set me up") follows the README's "For Claude" section: download to `~/harmonicfitness`, then hand over to a session opened in that folder, where these instructions and the safety settings load. A new listener is set up only on their own computer, never on Claude Code on the web. Keep that section, the README's Start here and the setup skill in step.

Rules that always hold:
- **Never read, print or copy `me/.env`**: it holds the listener's voice keys, pasted into that file by the listener, never into the chat. Only the engine reads it, when it sends to a voice service.
- **During a session, write only inside `me/`.** Never put personal details (health, location, the log, drafts, a listener's name) in the engine, its tests, its examples or `docs/`; the pre-push hook in `tools/hooks/` and CI both refuse them.

## Two assistants

HarmonicFitness runs under Claude Code and under ChatGPT's Codex, on the listener's own computer.
- **Claude Code's files are the source:** this file, `.claude/skills/` and `.claude/settings.json` (which allows `./harmonicfitness` and denies Claude's file reads of `me/.env`). Skills name Claude Code's tools.
- **Codex reads `AGENTS.md` and `.agents/skills/`,** both written by `./harmonicfitness harness sync` (`tools/harness.py`): `AGENTS.md` sends Codex here and says what to use in place of each Claude Code tool; `.agents/skills/<name>/` is an exact copy of `.claude/skills/<name>/`. **After editing a skill, run `./harmonicfitness harness sync`**; the tests fail until it's done.
- **`.codex/config.toml`** turns on the sandbox's network and **`.codex/rules/harmonicfitness.rules`** lets `./harmonicfitness` run outside Codex's sandbox, as `.claude/settings.json` allows it here; the harness check keeps the two naming the same command. Inside the sandbox (`CODEX_SANDBOX` set) uv's cache moves to `.cache/uv`, a local render that can't see the GPU says to run outside it, and setup skips the privacy hook when git's settings can't be written.

## The layers

1. **Engine** (this repo, public, versioned): `harmonicfitness`, `tools/`, `.claude/`, `AGENTS.md`, `.agents/`, `.codex/`, `tests/`, `knowledge/`, `docs/` (plain HTML sharing one `docs.css`), the template `me.example/`, the brand in `assets/brand/` (every file from its `make.py`, maintainer only) and the web client in `web/` (its own `web/README.md`).
2. **Coaches.** A persona folder: a person's name, how they talk (`[character]`, which the script follows) and how they sound (`[voice]`, which a service designs from). Two kinds:
   - **Local** (`kind = "local"`): the ten stock coaches in `coaches/` (Andy, Marcus, Theo, Sam, Callum; Maya, Claire, Rosa, Helen, Kate), spoken on this computer by Pocket TTS from `pocket.safetensors`, with recorded counts and cues (`cues/`), a measured `pace.json` and a 45-second `sample.mp3`. Coach Andy is the stand-in when no coach was ever chosen. `coaches/roster.toml` says how each was made; `tools/coachmaker/` remakes them (maintainer only).
   - **Web** (`kind = "web"`): speaks only through its service, with the listener's key. Twelve ready-made ones ship, six on OpenRouter and six on Gemini, each a voice of that service's own with a sample and a pace estimate. Three stock ones (Reed on Fish Audio, Ellis on ElevenLabs, Owen on Inworld) are `placeholder = true`, `pending = "design"`: the quick start or the first build that needs one designs its voice in the listener's account, saying so first, and writes it to `me/coaches/<slug>/`. Where a service has several, the first by name is its stand-in.
   - The listener's own coaches live in `me/coaches/` and win over a stock coach of the same name. Local model weights download into `models/` (git-ignored, pinned revisions), never into git.
3. **The listener's context** (private): `me/`, ignored by git (`HARMONICFITNESS_HOME` moves it), template `me.example/`. Kept as its own private repo, nested but never a submodule; `./harmonicfitness backup` commits and pushes it.

## The listener's files, as the tools see them

- **One reader and writer.** Paths come from `tools/paths.py`; the context files are read and written only through `tools/context.py` and the modules it delegates to (`frontmatter`, `store`, `health`, `sessionlog`, `records`), each reached in its own module, never through `context` (`test_imports` checks).
- **Format.** Each Markdown file opens with a TOML block between `+++` lines naming its format (`schema = 6`); `settings.toml` is plain TOML. A format change raises `SCHEMA` in `tools/context.py` and adds a step to `tools/migrate.py`, except a format the web client must keep reading (it can't migrate): that one reads both ways and migrate converts it as a folder step with no schema change.
- **The profile is four files** that `context.profile()` reads as one; each setting has a home file (`SETTING_HOMES`), which wins, and `check` notes a setting written twice:
  - `profile.md`: `name`, `experience`, and who they are.
  - `training.md`: `likes`, `dislikes`, `[[kits]]` (with `weights` and `unit`), the default session.
  - `content.md`, read only by research and the story tools: `youtube_favorites`, `puzzles`, `skip_formats`, `[[feeds]]`, and the sections `## Topics`, `## Venues`, `## Never bring up`, `## Taste`.
  - `settings.toml`: `setup`, `render` (routes in order), `cloud_max_chars`, `deliver_to`, `words_per_minute`, `bed` (`"pulse"`).
- **`health.md`**: a `[[limits]]` row per injury (area, side, level `off-limits` or `delicate`, optional `flags`, `rehab` and `cleared`, note) that the brief applies, and prose with `## Clinician rules`, followed literally. A row with `cleared = <date>` is no limit: the screen skips it and the brief carries the area's after-clearing rule for its weeks. Changed only at the check-in, with the listener's permission.
- **`log.md`**: sessions, added only by `./harmonicfitness log-session`, and feedback under `## Feedback`.
- **`workouts/<stem>/`**, one folder per workout (`tools/workouts.py`): the draft, its brief and menu, and the build's `.txt` and `.build.json`. Beside them: `checks/` (smoke tests), `research/` (`daily/`, `videos/`, `puzzles/`, `reserve/` the researched stock, `told.jsonl`, `threads.jsonl`, `interests.jsonl`), `.audio-cache/` and `.logs/` (render logs and `builds.jsonl`, one line per MP3, failed web render or build outcome, each carrying its `build_id` and `kind`, read only through `records.parse`).
- **`coaches/<slug>/`**: `persona.md` (persona schema 5), `pace.json`, a web coach's `sample.mp3`; `coaches/.auditions/` holds one in progress, `coaches/.archive/` retired ones.
- **`.env`**: the web voice keys and, optionally, the web app account `pull` and `sync` sign in with. Made by `keys init`, opened by `keys open`, filled in by the listener.
- **`movements.toml`** (optional): private catalog entries; a shipped id wins.

## Knowledge (`knowledge/`)

Each file is read only through its tool, never parsed elsewhere:
- `movements.toml` (`tools/catalog.py`): every movement's equipment, patterns, joint loads, flags, level, timing and spoken coaching; the fixed vocabularies, kit presets, `[limit_cues]`, and `[unlisted]` (real movements it doesn't hold, which the build refuses).
- `sessions.toml` (`tools/sessions.py`): session methods, doses by intensity and level, `[all_out]`, `[timing] rep_pace`, the caps; every number marked sourced or house default, sourced from `programming.md`.
- `content.toml` (`tools/content.py`): story formats, topics a session touches by length, the stock's targets, `[interests]`.
- `services.toml` (`tools/cloud.py`): the one list of web services. A new service is a section here and a module in `tools/services/` keeping the contract in `tools/services/__init__.py`.
- `script.md` (safety, the build's checks, the aims, the read-through) and `tts-rules.md` (what a voice can read, the draft's format and markers): the writer's two guides, also split into the web writers' prompts.
- `limits.toml` (`tools/playbook.py`): what each limit means, by area and level: the session and stop signs the brief quotes for today's level, the check-in's loosening signs (`./harmonicfitness get limits`), what carries on after a limit clears, and the red flags. `injury-playbook.md` is its evidence: which lines are sourced, which house judgment, and how the screen applies limits.
- `kits.md`, `programming.md`, `voices.md`: references; where any knowledge file and `me/health.md` disagree, the strictest wins.
- `research/`: dated evidence notes behind the numbers. No tool reads it.

## Engine conventions

- **One entry point.** Every tool runs as `./harmonicfitness <command>` (`tools/harmonicfitness.py` dispatches; `setup` and `doctor` are shell scripts so they run before the environment exists), in `.venv` (Python 3.11) or `HARMONICFITNESS_PYTHON`, never the system `python3`. Skills and docs call tools only this way, so one permission rule covers them.
- **Exit codes** (`tools/errors.py`, re-exported by `cli`): 0 done; 1 issues to fix; 2 the total ran more than five percent off plan (the MP3 is still made and delivered); 3 a local coach isn't measured on this route; 4 a web service refused the key, payment or quota; 64 the command was wrong, or a web coach can't speak here; 70 a bug in the engine; 130 interrupted.
- **`cli.run` wraps every `main`**, mapping what it raises to those codes (an unexpected exception is 70 with its traceback on stderr), with every key scrubbed from what it prints (`redact.scrub`). Library code never exits or imports `cli`: it raises a typed error from `tools/errors.py` (or `cloud.ServiceError`, `screen.Unfit`), and a caller that carries on catches the kind it means or `errors.PROBLEMS`.
- **Options.** Numeric values go through `cli.positive_int` and its siblings (so `--minutes 0` is 64 everywhere); `--date` is a day on record, `--today` only "pretend today is"; `--json` prints the same facts as one object. A report goes to stdout, the reason a command failed to stderr.
- **Writes.** Every record, menu and context file goes through `tools/fileio.py`: `atomic_write` (temp file, then rename), `replace`, `atomic_copy`, `read_jsonl`, `append_jsonl` (under `locks.file_lock`, sealing a torn line), `read_json(path, shape)`. One render at a time: `locks.render_lock`.
- **Web services.** A 429 asking to wait over two minutes is a quota (exit 4), never slept through; a design or save is never retried once sent; redirects are never followed; a `HARMONICFITNESS_<SERVICE>_URL` override counts only at https or this computer; a key holding a stray character is refused by name before it's sent.
- **The enforcers:** `tests/test_contract.py` (exit codes, flag rules, no `SystemExit` in library code), `tests/test_imports.py` (voice dict shapes and cache keys, import cycles, names reached in their own modules), `tests/test_integrity.py` (atomic writes, locked appends), `tests/test_harness.py` (the two assistants' files).

## How a workout is built

- **Brief** (`tools/brief.py`, `tools/screen.py`): today's ingredients in Markdown: the listener and coach, the week, today's limits with clinician rules and limit cues, the safe menu (what kit, level, limits, `Avoid:` lines and dislikes allow), loads on hand, the programming guide. It plans nothing. `--save` writes `<stem>.brief.md` and `<stem>.menu.json` beside a draft in `me/workouts/`. A dropped rule protects nothing, so an unknown `Avoid:` word or `[[limits]]` value stops the screen.
- **Draft** (`tools/draft.py`, format in `knowledge/tts-rules.md`): a `movements:` line, then `@@ <seconds> | <label>` segments with `[pause]`, `[chime]`, `[hold]`, `[count 5 go]`, `[cue rest]` and `[story]`. A skeleton (the clock, no words) lints to each segment's word budget and stops with "no words yet" (exit 1); the writer writes to those budgets.
- **Build** (`tools/build.py`, `./harmonicfitness build <draft> "<name>" --coach "<coach>"`): one process reads the draft once, then lints, gates the menu, renders and delivers. Any stop of a full build leaves exactly one outcome line in `builds.jsonl`. `--lint-only` stops after the lint and menu gate; `--follow` (render ahead while writing) and `--clips-only` are local only, since every web re-render is billed.
- **What the lint holds:**
  - **No silence over eight seconds** (twenty with the pulse bed): with no screen, silence sounds like a dropped earbud, and a set of "go", silence, "rest" sounds like no coach. The render checks again from the real clips and warns.
  - **The total within five percent**, aiming inside it (`tts_build.LINT_HEADROOM`). A segment with spare time widens its breaks, then ends early; only a bare `[hold]` keeps a segment its full length, however late it starts, and lateness passes to the next unheld segments.
  - **Only what a voice can read:** no digits, symbols or ellipses (a tested voice dropped "and rest" after "Three... two... one..."), no one-word clips, paragraphs short enough for one clip; with recorded counts, no countdown in words.
  - **Warnings, not stops:** a sentence of six words or more repeated from the last five drafts (`tools/repeats.py`), and any line claiming to have seen the listener.
- **The menu gate** (`tools/menu.py`): the menu must be today's and made from `health.md` as it stands (a hash), and a full build re-screens it against today's health.md. It refuses a declared or spoken movement off the menu, a catalog `[unlisted]` name, and, for a one-sided movement, any other-side or both-sides wording in its segment outside the shipped limit cues. Story text is read past, but a story sentence that speaks to the listener and names an off-menu movement is refused. The smoke test (`knowledge/smoke-test.draft.txt`, known by its place) needs no menu.
- **Coach and route** (`tools/coachpick.py`, `tools/routes.py`): default coach is the one used last, else the listener's own, else a stand-in that can speak here; web mode (`HARMONICFITNESS_WEB=1`, set by the web client's worker) never falls back to a local one. A web coach always speaks through its own service, a local one locally. A `pending` default coach is made first.
- **Render** (`tools/render.py`, `tools/audio.py`, `tools/clipcache.py`): each paragraph voiced through the clip cache, leveled, compressed, loudness-normalized, with chimes and an end tone. A web render prints characters and cost first and stops above `cloud_max_chars` (or a lower `--max-chars`).
- **The take check** (local only, `tools/verify.py`): a speech recognizer (Parakeet, ONNX on the processor) hears each clip; a take that drops a cue word (go, rest, switch, left, right, a count) is rendered again, up to four takes, and a line that drops it every time stops the build. Verdicts are cached with the clip. Web takes aren't checked: each is billed.
- **Deliver:** the MP3 is copied to each `deliver_to` folder and the local copy removed (a failed copy keeps it, with the reason in the build record). `--web` (default on Claude Code on the web) makes a mono web copy in parts with a `.player.html`. The web client keeps the MP3 for the app to upload.
- **On the web client,** the agent writes the skeleton and three writers fill it (`web/webapp/agent/writers.py`): a personal content writer (started when the brief is saved) and a coach writer side by side, each reading only its own parts of `script.md` and `tts-rules.md`, then a final script writer that edits the assembled script against the lint. `HARMONICFITNESS_WRITERS=one` has the agent write it in passes instead.

## Audio

- **A local coach** speaks with Pocket TTS (Kyutai's `pocket-tts`, PyTorch, CC-BY 4.0) through the public model `kyutai/pocket-tts-without-voice-cloning`; `engines.public_only` refuses its gated cloning model, so no login is ever needed. On the processor on an Apple Silicon Mac (about 0.15 times the speech's length) or a PC (about 0.43), or an NVIDIA card (about 0.29); no Intel Mac. Pocket speaks in short pieces, each started fresh, so a local script joins short cues into fuller sentences.
- **A web coach** speaks through its own service with the listener's key, by the voice saved there; no clip is sent. Its pace starts as an estimate from its sample.
- Every engine returns `say(text, seed)`: 16-bit mono PCM at 24 kHz, so the cache, layout and record don't know which spoke. The cache key holds the voice's identity and runtime, never a key or a name.
- **On Windows,** `./harmonicfitness` runs from Git Bash. **On Claude Code on the web,** only web coaches speak: the key is an environment variable in the cloud environment's settings, and the service's host goes on its network allowlist.

## The other tools, by job

- **Computer:** `doctor` (readiness; `--facts` feeds `tools/machine.py`), `setup` (environment, `me/`, privacy hook, local engine as a uv extra remembered in `.venv/.harmonicfitness-extra`), `models`, `tools/voices.py` (model pins), `tools/ffmpeg.py`, `harness`.
- **Coaches:** `coaches` (list, last, measured, audition, keep, make, archive, set, download), `tools/personas.py` (lookup, merge), `tools/audition.py`, `tools/coachmake.py`, `tools/cloud.py` and `tools/services/`, `keys` (names set, never values), `balances`.
- **Context:** `check`, `get`, `log-session` (`tools/logsession.py`), `migrate`, `workouts` (list, show, feedback, rate, delete), `backup` (refuses a key file and a public remote), `cache prune`, `pull` and `sync` (the web app's copy of `me/`).
- **Planning and research:** `brief`, `movements` (`--about` for coaching notes), `coverage`, `feeds`, `content` (plan, log, thread, reserve, trending), `interests` (learned likes, fading by half-life), `youtube`.
- **Privacy:** `tools/hooks/` (the pre-push hook, `check-private.sh` shared with CI, and `private-paths`, the one list of paths never pushed).

## Tests

`./harmonicfitness test` (or `test engine`, `test web`) after changing a tool. The tests need no models, network or personal files: they point `HARMONICFITNESS_HOME` at an absent folder, `tests/helpers.py` redirects every path to a temporary home, and `HARMONICFITNESS_SHIPPED` points at `tests/fixtures/stock/` so only `test_stock` sees the real coaches. Web services are faked in `tests/fakes.py`. CI runs a privacy job, then the engine's tests (skipped when a push changes only `web/`, the changelog or the version), the web app's tests and, on main, the Fly deploy.

## Releases

Semantic Versioning in its 0.x form (pre-1.0; the numbering restarted at 0.16.0, `CHANGELOG.md` has the table). The version lives in `VERSION`, `pyproject.toml`, `uv.lock` and `CHANGELOG.md`, tagged `vX.Y.Z` on GitHub (RNCDev/harmonicfitness). The maintainer decides the level:
- **Minor (0.X.0):** breaks how drafts, coaches, commands, exit codes or the `me/` layout work, so something must be migrated; its CHANGELOG section says what to do under "For forks".
- **Patch (0.x.Y):** everything else: new capabilities, fixes, tuning, doc corrections.

To release: a dated section in `CHANGELOG.md`, the version bumped, commit, `git tag -a vX.Y.Z -m "..."`, push with tags, `gh release create vX.Y.Z --notes-file <that section>`. Ask before pushing if it's unclear whether the work is done.
