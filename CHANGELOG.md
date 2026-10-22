# Changelog

All notable changes to sweatcast. The format follows [Keep a Changelog](https://keepachangelog.com), and versions follow [Semantic Versioning](https://semver.org).

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
