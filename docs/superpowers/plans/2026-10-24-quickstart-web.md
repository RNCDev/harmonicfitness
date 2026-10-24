# sweatcast 9.1.0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A stranger gets a first workout in minutes (Coach Demo, quick-start setup), Claude Code on the web runs with cloud voices only, and `me/workouts/` holds one folder per workout.

**Architecture:** Coach Demo is template content in `me.example/`. Quick start is a profile setting that `./sweatcast check` honors, plus skill text. The web is a cloud-session branch in `doctor.sh` (no local voices), `paths.py` (find the attached private repo) and `build.py` (a speech-bitrate copy and a player page). The layout lives in a new `tools/workouts.py`, with a schema 4 to 5 migration step.

**Tech Stack:** Python 3.11 (unittest), POSIX sh, ffmpeg via `tools/ffmpeg.py`.

**Spec:** `docs/superpowers/specs/2026-10-24-quickstart-web-design.md`

## Global Constraints

- Every tool is run through `./sweatcast`; tests run with `./sweatcast test` (single class: `.venv/bin/python -m unittest tests.test_x.Class -v`).
- Nothing personal in the engine: Coach Demo's files come from `tools/migrate-assets/v8-voices/` and the measured pace numbers only (no hostnames, no `speed` entries).
- Claude never reads, prints or copies `me/.env`.
- `context.SCHEMA` becomes 5; every context file's `+++` block says `schema = 5`.
- A cloud session is `CLAUDE_CODE_REMOTE=true`. `SWEATCAST_ALLOW_CLOUD_SESSION` is retired.
- Web copy: mono, `48k`, parts of at most `14_000_000` bytes, named `<name>.web-<n>.mp3`; the page is `<name>.player.html`.
- Plain-language messages, in the voice of the existing tools.

## Review Focus

- A listener who makes their own coach but never logs a session with it: the next build must still pick theirs over Coach Demo (Task 1 test `test_default_prefers_non_placeholder`).
- A 4.x `me/` with a top-level `x.txt`, a `.txt` with no build record and two drafts on the same date: migration must not guess; ambiguous files go to `checks/` (Task 3 test `test_ambiguous_goes_to_checks`).
- A cloud session with no private repo and no `me/`: setup still makes a one-time `me/` with Coach Demo, and doctor says nothing will be kept (Task 5 test `test_remote_without_home_says_one_time`).
- A workout longer than one part (over ~38 minutes): the page must play the parts in order (Task 4 test `test_split_parts_and_page_lists_them_in_order`).
- `gh` missing on the web: backup must still refuse a public remote (Task 5 test `test_visibility_without_gh`).

---

### Task 1: Coach Demo

**Files:**
- Create: `me.example/personas/coach-demo/persona.md`, `clip.wav` (copy of `tools/migrate-assets/v8-voices/Chatterbox Coach.wav`), `clip.txt` (copy of `Chatterbox Coach.txt`), `pace.json`
- Modify: `tools/personas.py` (`default`), `tools/context.py` (`check_coaches`), `tools/coaches.py` (list marks a placeholder)
- Test: `tests/test_personas.py`

**Interfaces:**
- Produces: `Persona.placeholder -> bool` (from `placeholder = true` in persona.md's settings).

- [ ] **Step 1: Write the files.** `persona.md`: `schema = 5`, `name = "Coach Demo"`, `placeholder = true`, `description = "A stand-in coach to start with: a man in his forties, warm baritone, a seasoned trainer. Make your own any time (\"I want a new coach\")."`, `[local] engine = "chatterbox"`; body `## How this coach talks` with two generic lines (calm and focused, light humor, no hype; notices effort plainly). `pace.json`: the three keys `e5488e8c8349|chatterbox|mlx-community/chatterbox-turbo-fp16`, `e5488e8c8349|chatterbox|ResembleAI/chatterbox-turbo`, `e5488e8c8349|fish|s2.1-pro` with `weight` and `seconds` only (values from `me/personas/coach-julius/pace.json`) and `"name": "Coach Demo"`. Check the private-paths hook doesn't match `me.example/` (it matches `^me/`, so it doesn't).
- [ ] **Step 2: Failing tests** in `tests/test_personas.py`:
  - `test_demo_ships_measured`: copy `me.example` to a temp home; `./sweatcast coaches measured "Coach Demo" --engine fish` exits 0; same for `local` with the MLX model on a Mac backend.
  - `test_default_prefers_non_placeholder`: personas `coach-demo` (placeholder) and `coach-maya`, empty log: `personas.default().name == "Coach Maya"`; with only demo, it's `"Coach Demo"`; with a log line naming Coach Demo last, it's `"Coach Demo"`.
  - `test_check_notes_placeholder`: `context.check_coaches()` on the fresh home returns one issue with `note=True` mentioning "placeholder".
- [ ] **Step 3: Implement**: `Persona.placeholder`; `default()` falls back to the first non-placeholder coach before `found[0]`; `check_coaches` adds the note "Coach Demo is a stand-in: say \"I want a new coach\" to make your own"; `coaches` list appends " (stand-in)".
- [ ] **Step 4: Run** `./sweatcast test` → all pass (the FreshFork class must still pass with a coach present).
- [ ] **Step 5: Commit** `Coach Demo ships ready, with its pace measured`.

### Task 2: Quick-start setup and the one-question coach

**Files:**
- Modify: `tools/context.py` (`_check_profile`, plus `setup_stage(profile) -> str`), `me.example/profile.md` (settings comment + `setup = "quick"`), `.claude/skills/setup/SKILL.md`, `.claude/skills/coach/SKILL.md`
- Test: `tests/test_tools.py` class `Context`

**Interfaces:**
- Produces: `context.setup_stage(p) -> "quick" | "full"` (missing setting → `"full"`).

- [ ] **Step 1: Failing tests**: `test_quick_setup_unfilled_are_notes` (profile with `setup = "quick"`, an unfilled feed, an unfilled interest and a body `[hint]` line: every issue is `note=True`, and one note says "finish setting me up"); `test_full_setup_unfilled_are_issues` (same profile without the setting: those are issues, as today).
- [ ] **Step 2: Implement** `setup_stage` and, in `_check_profile`, turn "isn't filled in yet" issues into notes when quick, and append the note `setup's second half is still to do (interests, feeds, delivery, your own coach): say "finish setting me up"`.
- [ ] **Step 3: Skills.** Setup: Step 0 unchanged; a **Quick start** (default for a new listener): one AskUserQuestion round of four (what the coach calls them, through Other; experience; kit as a preset or "what's at home" through Other; injuries: "None" or describe through Other, then the `[[limits]]` walk only for what they named). Audio: local where doctor says it works (download in the background), else ask which cloud voice and walk the key. Coach Demo is their coach; offer the one-question coach after the first workout. Write `setup = "quick"`. A ten-minute first workout. **Finish setting me up** runs today's Steps 2.3, 2.5, 2.7, Step 3's feeds and removes `setup`. Coach skill: a **Quick coach** section before step 1 (one question: three named sketches plus Other; `--takes 1`; keep; the smoke test only on a route Coach Demo's pace doesn't cover, since a new clip needs measuring: say it's about a minute).
- [ ] **Step 4: Run** `./sweatcast test` → pass. **Commit** `Quick-start setup and a one-question coach`.

### Task 3: A folder per workout (schema 5)

**Files:**
- Create: `tools/workouts.py`, `tests/test_migrate5.py` (with `tests/fixtures/v9-home/`: an invented 4.x `me/` with drafts, outputs, a smoke test, `x.txt`)
- Modify: `tools/paths.py` (`CHECKS`, `DAILY`), `tools/build.py` (output folder), `tools/feeds.py` (writes to `DAILY`), `tools/context.py` (`SCHEMA = 5`), `tools/migrate.py` (`to_5`, layout move), `me.example/` (schema 5 everywhere, `workouts/checks/.gitkeep`, no `drafts/`), `.claude/skills/workout/SKILL.md` and `research.md` (draft at `me/workouts/<stem>/<stem>.draft.txt`, sheets at `research/daily/`)

**Interfaces:**
- Produces: `workouts.session_dir(stem: str) -> str` (`WORKOUTS/<basename of stem>`); `workouts.out_dir(draft: str) -> str` (the draft's folder when it is a direct child of `WORKOUTS` other than `checks`, `research` or a dot folder; else `CHECKS`); `workouts.reorganize(home: str, dry_run=False) -> list[tuple[str, str]]`.

- [ ] **Step 1: Failing tests**:
  - `test_out_dir`: draft in `WORKOUTS/2026-10-25-strength-25/` → that folder; `knowledge/smoke-test.draft.txt` → `CHECKS`; a draft in `/tmp` → `CHECKS`.
  - `test_reorganize_moves_by_build_record`: drafts/`2026-10-23-general-circuit.{draft.txt,brief.md,menu.json}` and top-level `Workout 2026-10-23 General 30 min.{txt,build.json}` whose record's `draft` is that draft → all five in `workouts/2026-10-23-general-circuit/`.
  - `test_smoke_goes_to_checks`: `smoke-test.{txt,mp3,build.json}` → `checks/`.
  - `test_name_date_matches_single_draft`: `Workout 2026-10-19 Bench Only 15 min.txt` with no record and one draft dated 2026-10-19 → that draft's folder.
  - `test_ambiguous_goes_to_checks`: `x.txt`, and a dated `.txt` with two drafts that date → `checks/`.
  - `test_research_daily`: `research/2026-10-21.md` and `2026-10-21-feeds.md` → `research/daily/`; `told.jsonl`, `pantry/`, `videos/` stay.
  - `test_migrate_4_to_5`: `./sweatcast migrate` on the fixture: files say `schema = 5`, the layout moved, `drafts/` removed when empty, a backup made; a second run says nothing to do.
  - In `tests/test_tools.py` `BuildScript`: the build of a draft in `WORKOUTS/<stem>/` writes `<name>.txt` there.
- [ ] **Step 2: Implement** `workouts.py`; `build.py` uses `workouts.out_dir(draft)`; `feeds.py` default path `DAILY/<date>-feeds.md`; `to_5` bumps the schema line; `migrate()` calls `workouts.reorganize(home)` once when any file crosses 4 to 5 (the dry run lists the moves). Never overwrite: a name already at the destination gets ` (2)`.
- [ ] **Step 3: Run** `./sweatcast test` (update fixtures and tests that assume schema 4 or the old paths) → pass. **Commit** `A folder per workout (schema 5)`.

### Task 4: Delivery record and the web copy

**Files:**
- Create: `tools/webcopy.py`, `tests/test_webcopy.py`
- Modify: `tools/build.py` (`deliver` returns where it went; `--web`; record), `me.example/.gitignore` (`!*.web-*.mp3`), `tools/migrate.py` `GITIGNORE_ADD` (same line, for existing folders)

**Interfaces:**
- Produces: `webcopy.make(mp3: str, name: str, out_dir: str, max_bytes=14_000_000, bitrate="48k") -> list[str]` (part paths, in order); `webcopy.page(name: str, parts: list[str], out_path: str) -> str` (a self-contained HTML player: one `<audio>` playing the parts in order, a download link per part, light and dark colors, no external scripts); `build.deliver(mp3, out_dir) -> dict` (`{"delivered_to": [folders], "kept_local": bool, "reason": str}`).

- [ ] **Step 1: Failing tests**: `test_single_part` (a 20 s tone MP3 → one part `X.web-1.mp3`, mono, ~48 kbps per ffprobe-free check: size ≈ 20×6000 bytes ±30%); `test_split_parts_and_page_lists_them_in_order` (`max_bytes` small enough for three parts → three parts whose durations sum to the input within 1 s, and the page lists `web-1`, `web-2`, `web-3` in order); `test_record_has_delivery` in `BuildScript` (a fake render; the `.build.json` gains `delivered_to`, and with no folder `"reason": "no delivery folder"`).
- [ ] **Step 2: Implement.** Split by duration: parts = ceil(estimated bytes / max_bytes), equal lengths, re-encoded from the full MP3. `build.py`: `--web` (on by default when `CLAUDE_CODE_REMOTE=true`) makes the parts and the page in `out_dir`, prints both paths, and in a cloud session removes the full MP3 after; the delivery result is merged into `<name>.build.json`.
- [ ] **Step 3: Run** `./sweatcast test` → pass. **Commit** `The build records where the MP3 went, and makes a web copy and player page`.

### Task 5: Claude Code on the web, cloud voices only

**Files:**
- Modify: `sweatcast` and `tools/setup.sh` (drop the decline), `tools/doctor.sh` (remote → `LOCAL=no`, `LOCAL_HW=no`, reason; a "Claude Code on the web" section), `tools/doctor.py` (hosts to allow, the context folder and whether it's kept), `tools/paths.py` (find the attached repo), `tools/routes.py` (`hosts(route) -> list[str]` from `services.toml` addresses), `tools/coaches.py` (`download` refused in a cloud session), `tools/keys.py` (`init` in a cloud session explains the environment setting instead), `tools/backup.py` (`visibility` falls back to `https://api.github.com/repos/<slug>`: 200 with `"private": false` → `PUBLIC`)
- Test: `tests/test_setup.py`, `tests/test_routes.py`, `tests/test_backup.py`, `tests/test_tools.py` `Wrapper`

**Interfaces:**
- Produces: `paths.find_home(root, env) -> str` (SWEATCAST_HOME; else `root/me` if it has `profile.md`; else, in a cloud session, the one sibling of `root` holding `profile.md` and `personas/`; else `root/me`). `paths.REMOTE: bool`, `paths.KEPT: bool` (false in a cloud session when HOME isn't inside a git repo with a remote). `routes.FEED_HOSTS: list[str]` (the hosts `tools/feeds.py` fetches from: ESPN, Open-Meteo, Wikipedia, YouTube and the RSS hosts in the profile's feeds, read from `feeds.py`'s URLs).

- [ ] **Step 1: Failing tests**: `test_remote_facts_no_local` (`CLAUDE_CODE_REMOTE=true` with faked Mac arm64: `local=no`, `local_hw=no`); `test_wrapper_runs_in_cloud` (`./sweatcast help` and `check` don't print the decline); `test_find_home_sibling` (temp root with sibling `sweatcast-me/profile.md` and `personas/`: found only when remote; two candidates → `root/me`); `test_remote_without_home_says_one_time` (doctor in a cloud session with a `me/` that isn't a repo prints "one-time"); `test_hosts` (`routes.hosts("fish") == ["api.fish.audio"]`); `test_visibility_without_gh` (a fake HTTP server returning `{"private": false}` → `PUBLIC`; 404 → `None`); `test_download_refused_in_cloud`.
- [ ] **Step 2: Implement.** Doctor's web section lists: the key as an environment variable in the cloud environment's settings (`FISH_AUDIO_API_KEY=...`, never in the chat); the hosts to allow (the route's, plus `routes.FEED_HOSTS` for feeds, which can be skipped); the context folder and whether it's kept.
- [ ] **Step 3: Run** `./sweatcast test` → pass. **Commit** `Claude Code on the web, with cloud voices only`.

### Task 6: Skills, docs and release

**Files:** `.claude/skills/{setup,workout,coach}/SKILL.md`, `README.md`, `CLAUDE.md`, `knowledge/voices.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`

- [ ] **Step 1:** Setup skill: a cloud-session branch (private repo attached → use it; none → explain once, plainly, that this is a one-time session with Coach Demo, nothing kept, and how to keep it next time; a cloud voice key as an environment variable; the hosts). Workout skill: on the web, publish `<name>.player.html` with the Artifact tool (`files` mapping each part), and `./sweatcast backup` commits the parts; where no Artifact tool is available, say the parts are in the private repo.
- [ ] **Step 2:** README: "Where it runs" (Claude Code on your computer: CLI, IDE or the Desktop app's Code tab; Claude Code on the web with a cloud voice; not the plain Claude chat), quick start, the new layout. CLAUDE.md: the new files, layout, schema 5, the web.
- [ ] **Step 3:** CHANGELOG 9.1.0 with "For forks" (`./sweatcast migrate` moves workouts; Coach Demo appears only in new folders; copy `me.example/personas/coach-demo/` to get it). VERSION and pyproject → 9.1.0.
- [ ] **Step 4:** `./sweatcast test` → pass. **Commit** `Release 9.1.0 docs`.

### Task 7: Rehearsals, then release

- [ ] **Step 1: Stranger rehearsal, local.** Fresh clone in the scratchpad, `models` symlinked to the real one, `SWEATCAST_HOME` in the scratchpad: walk the quick start as an invented listener to a ten-minute MP3 with Coach Demo, no smoke test. Fix what snags.
- [ ] **Step 2: Cloud-session rehearsal on this Mac.** `CLAUDE_CODE_REMOTE=true` in the fresh clone: doctor, setup (no local engine), a build on Fish with the listener-developer's key supplied by them (never read from `me/.env`), parts and page made.
- [ ] **Step 3: Migrate the real `me/`** (`./sweatcast migrate --dry-run`, show the moves, then migrate; backup made).
- [ ] **Step 4: Release**: tag `v9.1.0`, push with tags, `gh release create`, `gh repo edit --description "Your own workout podcast: narrated, injury-aware workouts as MP3s, in your own coach's voice, made with Claude Code"`.
- [ ] **Step 5: Ask the listener-developer** to try a Claude Code on the web session (environment: key variable, `api.fish.audio` allowed, `sweatcast-me` attached) and report back.
