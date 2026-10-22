# Session Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace prose programming rules and the phase-based injury ban table with structured building blocks (annotated exercises, equipment, session methods, dose rules) and one tool, `./sweatcast session`, that composes a session skeleton from them plus the listener's profile, health limits and log.

**Architecture:** The catalog (`knowledge/movements.toml`) moves to format 2 with per-area loads, flags, timing and patterns on every entry; `tools/catalog.py` loads, checks and filters it against equipment, level and `[[limits]]`. A new `knowledge/sessions.toml` holds methods and dose rules, read by `tools/sessions.py`. `tools/session.py` picks a method, fills slots, times them in the draft's own seconds, ranks candidates and prints a skeleton. Context schema 3 adds experience, likes, dislikes, kits and limits; `tools/migrate.py` gets a step. A forty-case judged grid in `docs/eval/` gates the 4.0.0 release.

**Tech Stack:** Python 3.11 standard library (`tomllib`, `dataclasses`, `unittest`), run through `./sweatcast`; exit codes from `tools/cli.py`.

**Spec:** `docs/superpowers/specs/2026-10-21-session-builder-design.md`

## Global Constraints

- Python 3.11 standard library only; every tool runs through `./sweatcast`; exit codes `cli.OK` 0, `cli.ISSUES` 1, `cli.USAGE` 64; argument parsing through `cli.ArgumentParser`.
- The engine is public. No personal details (health, places, log, loads, feedback) in engine files, tests, fixtures, examples or commit messages. Examples and fixtures use invented listeners. Reread every changed file before committing; the privacy hook checks paths only.
- Spoken fields (`setup`, `cues`, method `about`) obey `knowledge/tts-rules.md`: no digits, symbols or brackets; `catalog._spoken_fault` is the check.
- Context files are read and written only through `tools/context.py`; paths only through `tools/paths.py`.
- A context format change bumps `context.SCHEMA` to 3, adds `migrate.to_3`, and ships as the major release 4.0.0 with a "For forks" section. 3.2.0 is not released.
- Research cites only sources actually opened. `knowledge/sessions.toml` marks every number as sourced (with the URL) or as a house default.
- Run `./sweatcast test` after every task. Do not change `.claude/settings.json`.
- Every catalog entry, draft or not, carries `patterns`. A non-draft entry carries every new field.
- The skeleton speaks the draft's units: `@@ <seconds> | <title>`; no second timing model. Planned total within `draft.TOTAL_TOLERANCE` (3 percent) of the request.
- Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Stop and ask before every tag and push.

## Review Focus

1. A limit with a side on an unsided movement that loads that area (left knee delicate; air squat, `loads.knee = 3`): the movement is excluded, never "healthy side only". Test in Task 3.
2. A request shorter than the floor dose fits (ten minutes, straight sets): slots drop until it fits, the output says which dropped, and the total never exceeds the tolerance; never a silent overrun. Test in Task 7.
3. A migrated health file with injuries still in prose and an empty `limits` list: `./sweatcast check` notes it and `./sweatcast session` prints a warning line before the skeleton. Tests in Tasks 5 and 7.
4. A private `me/movements.toml` entry in the old format (has `groups` and `tags`, no `patterns`): loads as a draft with `patterns = []`, and `problems` names it; it is never selected. Test in Task 1.
5. An unknown `--goal`, `--level`, `--method`, `--target` or `--limit` value exits `cli.USAGE` with a message naming the valid choices. Test in Task 7.

---

## File structure

| File | Responsibility |
|---|---|
| `knowledge/movements.toml` | format 2: fixed lists (`patterns`, `muscles`, `areas`, `flags`, `levels`, `intensities`), equipment, presets, every movement |
| `knowledge/sessions.toml` | methods and dose rules, each number sourced or marked house default |
| `tools/catalog.py` | load, `problems`, `resolve`, `Limit`, `select`, `kit_equipment` |
| `tools/sessions.py` | load `sessions.toml`, `problems`, `choose_method`, `dose` |
| `tools/session.py` | `./sweatcast session`: slots, timing, ranking, output, `--draft` |
| `tools/movements.py` | `./sweatcast movements`: the plain filter, by primary pattern |
| `tools/coverage.py` | `./sweatcast coverage`: by pattern |
| `tools/context.py` | schema 3: profile settings, `limits`, `clinician_lines`, `check`, `rpe:` in `Session` |
| `tools/migrate.py` | `to_3` |
| `tools/paths.py` | `SESSIONS`; `INJURY_RULES` removed |
| `tools/sweatcast.py` | `session` command |
| `tests/test_catalog.py`, `tests/fixtures/movements.toml` | rewritten for format 2 |
| `tests/test_session.py`, `tests/fixtures/listener/` | the composer, against an invented listener |
| `tests/test_tools.py` | Coverage class by pattern; context schema 3 and migrate tests |
| `me.example/profile.md`, `me.example/health.md` | schema 3 templates |
| `knowledge/injury-playbook.md` | rewritten short: red flags, per-area loosening signs |
| `docs/eval/cases.toml`, `docs/eval/judge.md`, `docs/eval/listeners/`, `docs/eval/results-<date>.md` | the judged grid |

Spec amendment (ruling, recorded here): the pattern list gains `arms` and `hips` for isolation work the spec's list cannot place (curls, triceps, clamshells, adductor squeezes). Final list: `squat, hinge, lunge, horizontal-push, vertical-push, horizontal-pull, vertical-pull, carry, rotation, anti-rotation, anti-extension, locomotion, balance, arms, hips, mobility, breathing, skill`.

---

### Task 1: Catalog format 2, loader and checks

**Files:**
- Modify: `knowledge/movements.toml` (header lists; every entry mechanically converted)
- Modify: `tools/catalog.py`
- Rewrite: `tests/fixtures/movements.toml`, `tests/test_catalog.py` (classes `CatalogFormat`, `RealCatalog`; drop `InjuryRules` and the `Filter` class for now, Task 3 brings `Filter` back)

**Interfaces:**
- Produces `catalog.Movement` fields: `id, name, aliases, needs, position, sided, measure, patterns: List[str], muscles: List[str], loads: Dict[str,int], support: Dict[str,int], flags: List[str], intensity: str, level: str, seconds_per_rep: int, hold_seconds: int, transition_seconds: int, rehab: bool, draft: bool, setup, cues, easier, harder, private`. Missing numeric fields load as 0; missing `intensity`/`level` as `""`.
- Produces `catalog.Catalog` fields: `patterns, muscles, areas, flags, levels, intensities: List[str]`, `equipment, presets, movements, entries` as now. `groups`, `kinds`, `tags` gone.
- Produces module constants `LEVELS = ("novice", "experienced", "advanced")`, `INTENSITIES = ("strength", "conditioning", "mobility", "skill", "breathing")`, `LOAD_MAX = 3`.
- Removes `select`, `Selection`, `load_rules`, `rule_problems`, `PHASES`, `RULE_LISTS` (Task 3 adds the new `select`).

- [ ] **Step 1: Rewrite the fixture** `tests/fixtures/movements.toml` as format 2: `format = 2`, the six fixed lists, the same equipment table, the four presets, and eight movements: `goblet-squat` (squat, loads knee 3 hip 2 ankle 2 low-back 1, level novice, reps 3 s, transition 15), `split-squat` (sided, lunge, loads knee 3, support knee 1 ankle 1), `air-squat` (unsided, squat, knee 3, draft = false), `glute-bridge` (hinge, knee 1, flags floor), `push-up` (horizontal-push, wrist 2 shoulder 2, flags floor), `one-arm-row` (sided, horizontal-pull, needs dumbbells, support low-back 1), `bike-easy-spin` (locomotion, intensity conditioning, measure time, hold 60, needs bike), `old-style` (draft = true with only `patterns = ["arms"]`, no other new fields).

- [ ] **Step 2: Write the failing tests** in `tests/test_catalog.py`:

```python
def test_loads_fixture(self):
    cat = catalog.load(FIXTURE)
    self.assertEqual(cat.patterns[0], "squat")
    self.assertEqual(cat.movements["goblet-squat"].loads["knee"], 3)
    self.assertEqual(cat.movements["goblet-squat"].loads.get("wrist", 0), 0)
    self.assertTrue(cat.movements["old-style"].draft)

def test_fixture_is_clean(self):
    self.assertEqual(catalog.problems(catalog.load(FIXTURE)), [])

def test_non_draft_entry_must_carry_every_field(self):
    bad = [{"id": "x", "name": "x", "position": "standing", "measure": "reps", "patterns": ["squat"],
            "setup": "Stand.", "cues": ["Go."]}]
    msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
    for word in ("loads", "intensity", "level", "seconds_per_rep", "transition_seconds", "muscles"):
        self.assertIn(word, msgs)

def test_every_entry_needs_patterns(self):   # Review Focus 4
    old = [{"id": "legacy", "name": "legacy", "kind": "strength", "groups": ["quads"], "tags": ["standing"],
            "position": "standing", "measure": "reps", "setup": "Stand.", "cues": ["Go."]}]
    cat = catalog.load(FIXTURE, extra=old)
    self.assertTrue(cat.movements["legacy"].draft)
    self.assertTrue(any("legacy" in p and "patterns" in p for p in catalog.problems(cat)))

def test_unknown_values_are_named(self):
    bad = [{"id": "y", "name": "y", "draft": True, "patterns": ["wiggle"], "loads": {"tail": 2},
            "flags": ["wobbly"], "level": "wizard", "intensity": "vibes", "position": "standing", "measure": "reps",
            "setup": "Stand.", "cues": ["Go."]}]
    msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
    for word in ("wiggle", "tail", "wobbly", "wizard", "vibes"):
        self.assertIn(word, msgs)

def test_load_out_of_range_and_support_on_unsided(self):
    bad = [{"id": "z", "name": "z", "draft": True, "patterns": ["squat"], "loads": {"knee": 4},
            "support": {"knee": 1}, "sided": False, "position": "standing", "measure": "reps",
            "setup": "Stand.", "cues": ["Go."]}]
    msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
    self.assertIn("4", msgs)
    self.assertIn("support", msgs)
```
Keep the existing resolve, duplicate and spoken-text tests, adjusted to the new fixture ids. In `RealCatalog`, keep `test_real_catalog_is_clean`, `test_real_catalog_has_the_fixed_lists` (asserting `cat.patterns == [list above]`, `cat.areas == ["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "low-back", "rib", "shoulder", "elbow", "wrist", "neck"]`, `cat.flags == ["impact", "single-leg", "kneeling", "floor", "lying-side", "hanging", "overhead", "spine-flexion", "spine-twist", "lateral", "fast", "grip"]`), and `test_every_real_entry_has_patterns` (no entry with empty `patterns`).

- [ ] **Step 3: Run** `./sweatcast test -k test_catalog` and see the new tests fail on missing fields.

- [ ] **Step 4: Implement format 2 in `tools/catalog.py`.** Replace the `Movement` and `Catalog` dataclasses with the fields above; `_movement` reads the new keys with the defaults above and sets `draft = bool(raw.get("draft", False)) or "patterns" not in raw`. `problems(cat)` checks: every entry has non-empty `patterns` in `cat.patterns`; `muscles` in `cat.muscles`; `loads` and `support` keys in `cat.areas` with values 0 to `LOAD_MAX`; `support` only on `sided` entries; `flags` in `cat.flags`; `intensity` in `INTENSITIES` and `level` in `LEVELS` when given; for a non-draft entry: `loads` present (may be empty table), `muscles` non-empty, `intensity`, `level`, `transition_seconds > 0`, and `seconds_per_rep > 0` when `measure == "reps"` or `hold_seconds > 0` when `measure == "time"`; a non-draft `rehab` entry is fine. Keep duplicate, position, measure, needs, easier/harder and spoken checks. Delete `select`, `Selection`, `load_rules`, `rule_problems`, `PHASES`, `RULE_LISTS`. Update the module docstring.

- [ ] **Step 5: Convert `knowledge/movements.toml` mechanically.** `format = 2`; replace `groups`, `kinds` and `[tags]` with the six fixed lists (`patterns` as amended, `muscles = ["quads", "hamstrings", "glutes", "adductors", "abductors", "calves", "chest", "back", "lats", "shoulders", "biceps", "triceps", "forearms", "core", "neck"]`, `areas`, `flags`, `levels`, `intensities`). On every entry: `draft = true`; replace `groups` with `patterns` using this default map and the entry's name as a tie-breaker: horizontal push→horizontal-push; horizontal pull→horizontal-pull; hip hinge or glutes→hinge; hamstrings→hinge; quads→squat (lunges, split squats and step-ups→lunge); hip abductors and adductors→hips; anti-extension core→anti-extension; lateral or anti-rotation core→anti-rotation (carries→carry; woodchops→rotation); arms→arms; kind cardio→locomotion; mobility→mobility; breathing→breathing; skill→skill; rehab→the pattern its name says (balance drills→balance, ankle and knee drills→hips or mobility); finisher→locomotion or rotation by name. Remove `kind` and `tags`; keep a `rehab = true` field where `kind` was `rehab`. The header comment explains format 2 in the same voice as today. Write a throwaway script in the scratchpad for the conversion; do not commit it.

- [ ] **Step 6: Remove the injury-rules references** that break the import: delete `INJURY_RULES` from `tools/paths.py` and `knowledge/injury-rules.toml`; `tools/movements.py` and `tools/coverage.py` will not run until Tasks 3 and 4 (they still import `select` and `groups`): stub them minimally so `./sweatcast test` collects (`movements.py` prints "movements: rewritten in the next task" and exits `cli.USAGE`; `coverage.py` `groups_of` returns `found.patterns`). Delete the `Coverage` class from `tests/test_tools.py`; Task 4 writes it anew by pattern.

- [ ] **Step 7: Run** `./sweatcast test` and see everything pass.

- [ ] **Step 8: Commit** `Catalog format 2: patterns, loads, flags and timing fields; injury rules removed`.

### Task 2: Annotate the first sixty exercises

**Files:**
- Modify: `knowledge/movements.toml`
- Modify: `tests/test_catalog.py` (class `RealCatalog`)

**Interfaces:**
- Consumes Task 1's fields.
- Produces: at least one non-draft entry for every (preset, core pattern, level) triple, where core patterns are `squat, hinge, lunge, horizontal-push, horizontal-pull, anti-extension, anti-rotation, locomotion, mobility, breathing`, and `vertical-push, vertical-pull, carry` on every preset but bodyweight and hotel-room.

- [ ] **Step 1: Write the failing test**

```python
def test_every_preset_covers_the_core_patterns_at_every_level(self):
    cat = catalog.load()
    core = ["squat", "hinge", "lunge", "horizontal-push", "horizontal-pull", "anti-extension",
            "anti-rotation", "locomotion", "mobility", "breathing"]
    loaded = ["vertical-push", "vertical-pull", "carry"]
    for preset, equipment in cat.presets.items():
        want = core + (loaded if preset not in ("bodyweight", "hotel-room") else [])
        for pattern in want:
            for level in catalog.LEVELS:
                ok = [m for m in cat.movements.values() if not m.draft and m.patterns[0] == pattern
                      and catalog.LEVELS.index(m.level) <= catalog.LEVELS.index(level)
                      and all(any(alt in equipment for alt in need.split("|")) for need in m.needs)]
                self.assertTrue(ok, f"{preset} has no {pattern} at {level}")

def test_at_least_sixty_entries_are_annotated(self):
    cat = catalog.load()
    self.assertGreaterEqual(sum(not m.draft for m in cat.movements.values()), 60)
```

- [ ] **Step 2: Run it** and see it fail on the first preset.

- [ ] **Step 3: Annotate.** Pick the entries so the test passes with the fewest entries, favouring the ones the log is most likely to name (squats, hinges, push-ups, rows, bridges, planks, carries, bike work, the breathing and mobility holds, the stickhandling drills). For each: `draft = false`, `muscles`, `loads` (rate the working side; 3 for the joint the movement is about under load, 2 for a joint bending deep or bearing weight, 1 for a joint that stabilises, nothing for the rest), `support` on sided entries, `flags`, `intensity`, `level` (novice for anything bodyweight and simple, experienced for loaded compound lifts and intervals, advanced for barbell lifts, swings, sprints and single-leg loaded work), `seconds_per_rep` (3 for controlled strength reps, 2 for fast or small reps, 4 for slow eccentrics), `hold_seconds` (30 for planks and stretches, 60 for easy cardio blocks, 20 for sprints), `transition_seconds` (10 bodyweight, 15 dumbbell or band, 25 barbell or machine). Rehab entries keep `rehab = true`. Record the rating rule in the catalog's header comment so later annotation follows it.

- [ ] **Step 4: Run** `./sweatcast test` and see it pass, including `test_real_catalog_is_clean`.

- [ ] **Step 5: Commit** `Catalog: annotate the first sixty movements with loads, flags and timing`.

### Task 3: Selection against equipment, level and limits; the plain filter

**Files:**
- Modify: `tools/catalog.py`, `tools/movements.py`
- Test: `tests/test_catalog.py` (class `Select`, class `Filter`)

**Interfaces:**
- Produces `catalog.Limit(NamedTuple)`: `area: str, side: str ("left"|"right"|"both"), level: str ("off-limits"|"delicate"), flags: List[str], rehab: List[str], note: str`.
- Produces `catalog.Selection(NamedTuple)`: `allowed: List[Movement], healthy_side_only: List[Movement], left_out: Dict[str, List[str]]` (reasons: `"draft"`, `"equipment"`, `"level"`, `"disliked"`, `"avoided"`, `"<area> off limits"`, `"<area> delicate"`, `"rehab"`).
- Produces `catalog.select(cat, equipment: Set[str], level: str, limits: List[Limit], avoid: Set[str] = frozenset(), dislikes: Set[str] = frozenset()) -> Selection`. `avoid` holds movement ids or flags.
- Produces `catalog.threshold(limit) -> int`: 1 for off-limits, 2 for delicate. Delicate also excludes flags `impact` and `fast`; both exclude `limit.flags`.
- Produces `movements.equipment_keys` unchanged; `movements.render(cat, sel, only)` grouped by primary pattern in `cat.patterns` order, then "Healthy side only", then the "Left out today" line as now.

- [ ] **Step 1: Write the failing tests**

```python
def test_level_and_draft_and_equipment(self):
    cat = catalog.load(FIXTURE)
    sel = catalog.select(cat, {"dumbbells"}, "novice", [])
    ids = {m.id for m in sel.allowed}
    self.assertIn("goblet-squat", ids)
    self.assertEqual(sel.left_out["old-style"], ["draft"])
    self.assertEqual(sel.left_out["bike-easy-spin"], ["equipment"])
    sel = catalog.select(cat, {"dumbbells"}, "novice", [], dislikes={"goblet-squat"})
    self.assertEqual(sel.left_out["goblet-squat"], ["disliked"])

def test_off_limits_excludes_any_load_and_delicate_moderate(self):
    cat = catalog.load(FIXTURE)
    off = [catalog.Limit("knee", "both", "off-limits", [], [], "")]
    self.assertIn("glute-bridge", catalog.select(cat, {"mat"}, "novice", off).left_out)   # knee = 1
    soft = [catalog.Limit("knee", "both", "delicate", [], [], "")]
    sel = catalog.select(cat, {"mat"}, "novice", soft)
    self.assertIn("glute-bridge", {m.id for m in sel.allowed})
    self.assertEqual(sel.left_out["goblet-squat"], ["knee delicate"])

def test_sided_limit_on_unsided_movement_excludes(self):   # Review Focus 1
    cat = catalog.load(FIXTURE)
    left = [catalog.Limit("knee", "left", "delicate", [], [], "")]
    sel = catalog.select(cat, {"dumbbells", "mat"}, "novice", left)
    self.assertIn("air-squat", sel.left_out)
    self.assertIn("split-squat", {m.id for m in sel.healthy_side_only})   # support knee = 1 < 2

def test_sided_limit_checks_the_support_side(self):
    cat = catalog.load(FIXTURE)
    left = [catalog.Limit("knee", "left", "off-limits", [], [], "")]
    sel = catalog.select(cat, {"dumbbells", "mat"}, "novice", left)
    self.assertIn("split-squat", sel.left_out)   # support knee = 1 >= 1

def test_limit_flags_and_rehab(self):
    cat = catalog.load(FIXTURE)
    lim = [catalog.Limit("wrist", "both", "delicate", ["floor"], ["old-style"], "")]
    sel = catalog.select(cat, {"mat"}, "novice", lim)
    self.assertIn("floor", sel.left_out["glute-bridge"])
    self.assertNotIn("old-style", sel.left_out)   # named as rehab, so offered even though draft
```
In `Filter` (real catalog, through `./sweatcast movements`): `test_preset_prints_by_pattern` (output's first heading is `squat`), `test_avoid_flag_and_id`, `test_unknown_equipment_is_usage` (exit 64).

- [ ] **Step 2: Run** `./sweatcast test -k Select` and see it fail.

- [ ] **Step 3: Implement `select` and `Limit` in `tools/catalog.py`.** Order of reasons per movement: draft (unless named in a limit's `rehab`, which also bypasses the limit checks for that entry), equipment, level (`LEVELS.index(m.level) > LEVELS.index(level)`), disliked, avoided (id or any flag in `avoid`), then each limit: flags in `limit.flags`, delicate's `impact`/`fast`, then loads: for `side == "both"` or an unsided movement, `m.loads.get(area, 0) >= threshold` excludes; for a sided limit on a sided movement, `m.support.get(area, 0) >= threshold` excludes, else if `m.loads.get(area, 0) >= threshold` it goes to `healthy_side_only`. A `rehab = true` entry not named by any limit gets reason `"rehab"`.

- [ ] **Step 4: Rewrite `tools/movements.py`** on the new `select`: `--preset | --equipment`, `--avoid` (ids or flags), `--level` (default `experienced`), `--group` renamed `--pattern`. Docstring updated.

- [ ] **Step 5: Run** `./sweatcast test` and see it pass.

- [ ] **Step 6: Commit** `Catalog: select by equipment, level and limits; movements filter by pattern`.

### Task 4: Coverage by pattern, and the log's `rpe:` field

**Files:**
- Modify: `tools/coverage.py`, `tools/context.py` (`Session`, `parse_session`)
- Test: `tests/test_tools.py` (class `Coverage`, class `LogSession` or the existing log tests)

**Interfaces:**
- Produces `coverage.patterns_of(movement: str, cat=None) -> List[str]` (catalog's `patterns`, else the keyword fallback table now keyed by pattern), `coverage.coverage(movements, cat=None) -> ({pattern: [movements]}, unmapped)`, `coverage.week(sessions, today, days=7, cat=None) -> {pattern: count}` over `cat.patterns`, `coverage.last_loads` unchanged. `groups_of` and `GROUPS` removed.
- Produces `context.Session.rpe: Dict[str, str]` parsed from `| rpe: <m> = <n>; ...`, accepted by `./sweatcast log-session --rpe "goblet squat = 7"`, written by `to_line`. Nothing reads it yet (v2).
- Output: "Coverage, N session(s), <span>:" then one line per pattern in catalog order; "Prioritize:" lists patterns with no hit, then patterns with fewer than 2 sessions this week; "Last 7 days, sessions per pattern:"; the rest unchanged.

- [ ] **Step 1: Write the failing tests** (invented sessions, as the class already uses): `test_patterns_and_gaps` (a log with goblet squats and push-ups covers `squat` and `horizontal-push`, misses `hinge`), `test_week_counts_sessions_per_pattern`, `test_rpe_round_trips` (`parse_session(Session(..., rpe={"goblet squat": "7"}).to_line()).rpe == {"goblet squat": "7"}`), `test_rpe_rejects_separators` (a value with `;` is a problem).

- [ ] **Step 2: Run** and see them fail.

- [ ] **Step 3: Implement.** In `coverage.py` the fallback table maps the old regexes to patterns (push-up/press→horizontal-push; row→horizontal-pull; bridge/deadlift/hinge→hinge; squat/lunge/step-up→squat; plank/dead bug→anti-extension; side plank/pallof→anti-rotation; curl/triceps→arms; bike/row erg/run→locomotion; stretch/mobility→mobility; breathing→breathing). In `context.py` add `rpe` after `loads` in `Session`, `parse_session`, `to_line`, `problems`, and the `log-session` subcommand's arguments; the docstring line format gains `| rpe: <m> = <n>`.

- [ ] **Step 4: Run** `./sweatcast test`; pass.

- [ ] **Step 5: Commit** `Coverage by pattern; log lines may carry rpe for later progress tracking`.

### Task 5: Context schema 3, migration and examples

**Files:**
- Modify: `tools/context.py`, `tools/migrate.py`, `me.example/profile.md`, `me.example/health.md`
- Test: `tests/test_tools.py` (classes `Context3`, `Migrate3`; `FreshFork` keeps passing)

**Interfaces:**
- `context.SCHEMA = 3`.
- Produces `context.experience(p) -> Optional[str]` (one of `catalog.LEVELS`, else None), `context.likes(p) -> List[str]`, `context.dislikes(p) -> List[str]`, `context.kits(p) -> Dict[str, List[str]]` from `[[kits]]` (`name`, `equipment`).
- Produces `context.Health(settings, body, path)` and `context.health(path=None)`, `context.limits(h) -> List[catalog.Limit]` (a `[[limits]]` row with a bad `area`, `side` or `level` is dropped and reported by `check`), `context.clinician_lines(h) -> List[str]` (each limit's `note`, then every non-empty line under `## Clinician rules`).
- Produces `context.prose_injuries(h) -> bool`: True when `## Active injuries and limitations` has a bullet other than "None right now".
- `check`: profile notes empty or unknown `experience` ("no experience level: novice, experienced or advanced"), unknown ids in `likes`/`dislikes` (resolved through the catalog, note), kit equipment not in the catalog; health: bad limit rows (issue), and `prose_injuries and not limits` as a note "injuries written in prose have no [[limits]] entry, so the session tool applies no rule for them" (Review Focus 3).
- `migrate.to_3(text, path)`: profile gains `experience = ""`, `likes = []`, `dislikes = []` after `words_per_minute` with `SETTINGS_COMMENTS` lines; health gains `limits = []` with a comment line above it saying each injury below needs a `[[limits]]` entry; other files only change the schema number. `STEPS[2] = to_3`; the docstring gains the step.

- [ ] **Step 1: Write the failing tests** against invented text: `test_profile_settings` (experience, likes, dislikes, a kit named "garage"), `test_health_limits_and_clinician_lines` (one limit row plus a `## Clinician rules` line), `test_bad_limit_row_is_reported`, `test_prose_injuries_without_limits_is_a_note`, `test_migrate_2_to_3_adds_the_keys` (run `migrate.to_3` on the schema-2 example texts; assert the keys and the schema), `test_example_is_schema_3` (`me.example` passes `check` with only notes).

- [ ] **Step 2: Run** and see them fail.

- [ ] **Step 3: Implement** the readers, `check` additions, `to_3`, and update `me.example/profile.md` (add the three settings with comments, one `[[kits]]` example `name = "home"`, `equipment = ["dumbbells", "band", "mat"]`) and `me.example/health.md` (schema 3; `limits = []` in the block; the comment example in the prose becomes a `[[limits]]` example with an invented area; a `## Clinician rules` section with a hint line). `./sweatcast get` gains `experience`.

- [ ] **Step 4: Run** `./sweatcast test`; pass (including `FreshFork`).

- [ ] **Step 5: Commit** `Context schema 3: experience, likes, dislikes, kits and limits; migrate step`.

### Task 6: Session methods and dose rules

**Files:**
- Create: `knowledge/sessions.toml`, `tools/sessions.py`
- Modify: `tools/paths.py` (`SESSIONS`), `knowledge/programming.md` (template table replaced by a pointer)
- Test: `tests/test_session.py` (class `Methods`)

**Interfaces:**
- File shape (`format = 1`): `goals = ["strength", "general", "targeted", "conditioning", "mobility", "skill"]`; `[methods.<name>]` with `about` (spoken-safe), `goals`, `minutes = [least, most]`, `levels`, `warmup = { share, seconds = [least, most] }`, `cooldown = { share, seconds = [least, most] }`, optional `finisher = { share, seconds = [least, most], from_minutes }`, `work` in `("sets", "pairs", "rounds", "intervals", "holds")`, `blocks = [{ intensity, patterns, share }]`, optional `fixed = { work_seconds, rest_seconds, rounds }` for presets; `[dose.strength.<level>]` with `sets, reps, rest_seconds, hard_sets_per_session` as `[least, most]`; `[dose.conditioning.<level>]` with `work_seconds, rest_seconds, rounds`; `[dose.mobility.<level>]` with `hold_seconds, rounds`; `[dose.skill.<level>]` with `drill_seconds, rounds`. Every table has a `# source:` or `# house default:` comment.
- Methods, in file order: `straight-sets` (strength, targeted, general; 25 to 60; pattern order `squat, hinge, horizontal-push, horizontal-pull, lunge, vertical-push, vertical-pull, anti-extension`), `paired-sets` (same goals; 20 to 60; same patterns; `work = "pairs"`), `circuit` (general, conditioning; 10 to 45; `work = "rounds"`; no finisher), `intervals` (conditioning; 10 to 45; `work = "intervals"`; patterns `locomotion`), `tabata` (conditioning; 10 to 30; `fixed = { work_seconds = 20, rest_seconds = 10, rounds = 8 }`), `bike-intervals` (conditioning; 15 to 45; `fixed = { work_seconds = 30, rest_seconds = 90, rounds = 5 }`; requires `bike|air-bike`, as a `needs` field on the method), `flow` (mobility; 15 to 45; `work = "holds"`; patterns `mobility, breathing`), `skill` (skill; 15 to 45; `work = "rounds"`; blocks `skill` share 0.6 then `strength` share 0.4).
- House defaults (from `programming.md`'s template table and load-range section; the builder checks each against the cited sections and marks any that a source supports): warm-up share 0.15 within 120 to 360 s; cool-down 0.10 within 120 to 300 s; finisher 0.10 within 90 to 300 s from 25 minutes. Strength dose: novice sets 2–3, reps 8–12, rest 60–90, hard sets 6–12; experienced 3–4, 6–10, 90–120, 10–16; advanced 3–5, 4–8, 120–180, 12–20. Conditioning: novice work 20–30, rest 40–60, rounds 4–6; experienced 30–45, 30–45, 6–8; advanced 30–60, 15–30, 8–10. Mobility: hold 30–60, rounds 2–3 at every level. Skill: drill 45–60, rounds 4–8.
- Produces `sessions.Method` dataclass (`name` plus the fields as the file), `sessions.load(path=None) -> Sessions` (`goals, methods: Dict[str, Method], dose: Dict[str, Dict[str, dict]]`), `sessions.problems(s, cat) -> List[str]` (unknown goal, level, pattern, intensity or need; `about` spoken fault; a level missing from a dose table; minutes or ranges inverted), `sessions.choose_method(s, goal, minutes, level, last_format: Optional[str], equipment: Set[str]) -> Optional[Method]` (file order, first fitting whose name differs from `last_format`; if every fitting one equals it, the first fitting), `sessions.dose(s, intensity, level) -> dict`.

- [ ] **Step 1: Write the failing tests**: `test_real_file_is_clean`, `test_choose_rotates_away_from_last_format` (strength, 30, experienced, last `straight-sets` gives `paired-sets`; last `paired-sets` gives `straight-sets`), `test_choose_respects_minutes_and_needs` (strength at 15 minutes is not `straight-sets`; `bike-intervals` needs a bike), `test_choose_returns_none_when_nothing_fits` (conditioning at 5 minutes), `test_dose_has_every_level`.

- [ ] **Step 2: Run** and see them fail.

- [ ] **Step 3: Write `knowledge/sessions.toml` and `tools/sessions.py`**; add `SESSIONS` to `paths.py`; in `programming.md` replace the Session templates table with two sentences pointing at `sessions.toml` and keep the two cited studies above it.

- [ ] **Step 4: Run** `./sweatcast test`; pass.

- [ ] **Step 5: Commit** `Session methods and dose rules in sessions.toml`.

### Task 7: `./sweatcast session`, the composer

**Files:**
- Create: `tools/session.py`, `tests/fixtures/listener/{profile.md,health.md,log.md,exercise-science.md}` (schema 3, invented: experienced, kit "home" with dumbbells, band and mat, likes goblet-squat, dislikes push-up, one limit `wrist left delicate` with a note, two logged sessions in the last week with `format: straight-sets`)
- Modify: `tools/sweatcast.py` (`"session": ("session", None, "a session skeleton: method, timing and ranked movements for a request")`)
- Test: `tests/test_session.py` (class `Compose`, class `Cli`)

**Interfaces:**
- Consumes `catalog.select`, `catalog.Limit`, `sessions.choose_method`, `sessions.dose`, `context.profile/health/limits/clinician_lines/prose_injuries/kits/experience/likes/dislikes/sessions`, `coverage.week`, `draft.TOTAL_TOLERANCE`.
- Produces `session.Slot(NamedTuple)`: `pattern, intensity, dose: dict, seconds: int, candidates: List[Tuple[Movement, str]]` (movement, reason).
- Produces `session.Skeleton(NamedTuple)`: `method: Method, minutes: int, warmup: int, blocks: List[Tuple[str, List[Slot]]], finisher: int, cooldown: int, dropped: List[str], warnings: List[str], would_open: List[Tuple[str, int]]`.
- Produces `session.slot_seconds(m: Movement, dose: dict, work: str) -> int`: `transition_seconds + sets * work_each + (sets - 1) * rest` where `work_each = reps * seconds_per_rep` or `hold_seconds`; for `pairs` the two movements' transitions and work add and one rest follows each pair; for `rounds` one transition per movement per round and one rest per round; for `intervals` `rounds * (work + rest)`; for `holds` `rounds * hold + transition`.
- Produces `session.compose(request: dict, cat, sess, profile, health, log, today) -> Skeleton` and `session.render(sk) -> List[str]`, `session.render_draft(sk) -> List[str]`. Draft granularity: one `@@` segment for the warm-up; for `sets` and `pairs` one per slot (its sets and rests inside); for `rounds` one per round; for `intervals` one per work-and-rest pair; for `holds` one per slot; one for the finisher when present; one for the cool-down. Each title names the slot's default movement.
- CLI: `--goal` (required, from `sess.goals`), `--minutes` (required, int), one of `--preset | --kit | --equipment`, `--method`, `--level`, `--target` (comma-separated patterns or muscles), `--limit area=level[:side]` (repeatable), `--avoid`, `--draft`, `--log`, `--today YYYY-MM-DD` (tests). Unknown values exit `cli.USAGE` naming the choices (Review Focus 5). Exit `cli.ISSUES` when no method fits or fewer than three slots fit.
- Output order: clinician lines (prefixed "Health: "), warnings, the method line ("Method: paired-sets, because ..."), the skeleton with seconds per block, each slot's pattern, dose and top three candidates with reasons, "Dropped:" if any, "Would open up:" with up to three equipment items and counts.

- [ ] **Step 1: Write the failing tests** against the fixture listener (`--home` via `SWEATCAST_HOME` in `run_session` helper, like `run_movements`) and the real catalog:

```python
def test_total_within_tolerance(self):
    sk = compose_for(goal="strength", minutes=30)
    total = sk.warmup + sum(s.seconds for _, slots in sk.blocks for s in slots) + sk.finisher + sk.cooldown
    self.assertLessEqual(abs(total - 1800), 1800 * draft.TOTAL_TOLERANCE)

def test_rotates_away_from_last_format(self):
    self.assertEqual(compose_for(goal="strength", minutes=30).method.name, "paired-sets")

def test_wrist_limit_shapes_candidates(self):
    sk = compose_for(goal="general", minutes=30)
    offered = [(m, r) for _, slots in sk.blocks for s in slots for m, r in s.candidates]
    for m, _ in offered:
        if not m.sided:
            self.assertLess(m.loads.get("wrist", 0), 2, m.id)
    self.assertTrue(any("healthy side only" in r for _, r in offered))

def test_liked_ranks_first_and_disliked_never_appears(self):
    sk = compose_for(goal="strength", minutes=45)
    squat = next(s for _, slots in sk.blocks for s in slots if s.pattern == "squat")
    self.assertEqual(squat.candidates[0][0].id, "goblet-squat")
    self.assertFalse(any(m.id == "push-up" for _, slots in sk.blocks for s in slots for m, _ in s.candidates))

def test_short_request_drops_slots_not_time(self):   # Review Focus 2
    sk = compose_for(goal="general", minutes=12)
    self.assertGreaterEqual(len(sk.dropped), 1)
    total = ...  # as above
    self.assertLessEqual(total, 720 * (1 + draft.TOTAL_TOLERANCE))

def test_prose_injuries_without_limits_warns(self):   # Review Focus 3
    # a copy of the fixture home with limits = [] and a prose injury bullet
    self.assertTrue(any("no [[limits]]" in w for w in sk.warnings))

def test_draft_lines_are_markers(self):
    lines = session.render_draft(compose_for(goal="strength", minutes=30))
    self.assertTrue(all(draft.MARKER.match(l) for l in lines if l.startswith("@@")))
    self.assertEqual(lines[0].split("|")[1].strip().lower()[:7], "warm-up")

def test_would_open_up_names_equipment(self):
    sk = compose_for(goal="strength", minutes=30, preset="bodyweight")
    self.assertTrue(sk.would_open and all(isinstance(n, int) for _, n in sk.would_open))
```
`Cli`: `test_usage_on_unknown_goal` (exit 64, "strength" in stderr), `test_runs_with_draft` (exit 0, output starts with "Health: " line from the fixture's note).

- [ ] **Step 2: Run** and see them fail.

- [ ] **Step 3: Implement `tools/session.py`.** Algorithm, in this order: load everything; equipment from the request (kit names resolve through `context.kits`); level from `--level` or `context.experience`, else `experienced` with a warning; limits from health plus `--limit`; `catalog.select`; `choose_method` (or the named one, which must fit the goal); warm-up, cool-down and finisher seconds as `clamp(share * total, least, most)`; main = total minus those; slot patterns: the method's block patterns, with `--target` patterns or muscles moved to the front (a muscle target selects patterns whose candidates list that muscle first), then any pattern with `week` count 0 moved ahead of the rest in its own order; candidates per slot: allowed and healthy-side entries whose primary pattern matches (secondary matches fill when fewer than three), ranked by (not in the last session's movements, in likes, lower sum of `loads` when any limit is set, catalog order); dose starts at the top of its ranges; the slot count grows while the next slot fits at the top dose, capped at the number of block patterns; then if over budget step the dose down (sets, then reps or work, then rest) to its floor; if still over, drop the last slot into `dropped` and start again; spare seconds go to rests between slots up to 30 each, then the cool-down. "Would open up": for each equipment item not on hand, count non-draft entries ruled out by equipment alone that it would admit; top three. Reasons are the strings: "liked", "fresh (not last session)", "healthy side only", "light on the <area>", "<pattern> neglected this week", "rehab, named in health".

- [ ] **Step 4: Add the command** to `tools/sweatcast.py`; run `./sweatcast session --goal strength --minutes 30 --preset full-gym` against the fixture home by hand and read the output once for sense.

- [ ] **Step 5: Run** `./sweatcast test`; pass.

- [ ] **Step 6: Commit** `Add ./sweatcast session: method, timing and ranked movements from the building blocks`.

### Task 8: Knowledge and docs for the new shape

**Files:**
- Rewrite: `knowledge/injury-playbook.md`
- Modify: `knowledge/kits.md` (any sentence naming tags or phases), `CLAUDE.md` (Files list: `movements.toml` sentence, remove `injury-rules.toml` mention if any, add `sessions.toml`, `tools/sessions.py`, `tools/session.py`, `docs/eval/`; `knowledge/injury-playbook.md` sentence), `README.md` (same), `docs/superpowers/plans/2026-10-21-programming-knowledge.md` (one line at the top: superseded from Phase 2 by this plan)
- Test: `tests/test_catalog.py` (class `KnowledgeFiles`)

- [ ] **Step 1: Write the failing test** `test_playbook_has_a_section_per_area_and_no_phases`: every `cat.areas` entry has a `## ` heading in the playbook (title-cased, "Low back"); the words "protect", "rebuild" and "ban_ids" do not appear; a `## Red flags` section exists. And `test_docs_name_no_removed_files`: `CLAUDE.md`, `README.md`, `kits.md` do not mention `injury-rules.toml`.

- [ ] **Step 2: Run**; fail.

- [ ] **Step 3: Rewrite the playbook** (about 600 words): "Red flags" (the current file's stop-the-session list, kept), then one short section per area: what "off limits" and "delicate" mean for it in one sentence each, and the signs that let the listener loosen a limit (carry the current file's `advance_when` criteria and their sources over, condensed; cite only sources already in the current file). Update the other docs' sentences.

- [ ] **Step 4: Run** `./sweatcast test`; pass. Reread every changed file for personal details.

- [ ] **Step 5: Commit** `Injury playbook by area and tolerance; docs name the new files`.

### Task 9: Skills

**Files:**
- Modify: `.claude/skills/workout/SKILL.md` (Step 1 check-in, Step 2 plan, Step 3 where it names groups), `.claude/skills/setup/SKILL.md` (experience, kits, limits)
- Test: `tests/test_catalog.py` (class `KnowledgeFiles`): `test_skills_call_session_not_rules` (workout skill text contains `./sweatcast session` and not `injury-rules` or `--avoid` tag lists; setup skill contains `[[limits]]` and `experience`).

- [ ] **Step 1: Write the test; run; fail.**

- [ ] **Step 2: Edit the workout skill.** Step 1 check-in gains: goal, minutes, kit or preset, today's limits (`--limit`), and the "Would open up" question. Step 2 becomes: run `./sweatcast coverage` and `./sweatcast session <flags> --draft` (one message); show the skeleton; pick one candidate per slot (the first unless the check-in said otherwise); the `--draft` lines are the segment markers to write under. Remove the nine-group checklist, format rotation prose (the tool rotates), and every instruction to read the injury rules. Step 5's log line records `format: <method name>`. Keep research, script rules and build unchanged.

- [ ] **Step 3: Edit the setup skill.** Ask experience level (three choices, in the listener's words), kits (`[[kits]]`), likes and dislikes, and walk each injury into a `[[limits]]` row (area from the catalog's list, side, off-limits or delicate, the clinician's words into `note` and `## Clinician rules`). The phase questions go.

- [ ] **Step 4: Run** `./sweatcast test`; pass. Commit `Skills: plan from ./sweatcast session; setup collects experience, kits and limits`.

### Task 10: The judged grid, files and skeletons

**Files:**
- Create: `docs/eval/README.md` (how to run it, three commands), `docs/eval/cases.toml`, `docs/eval/judge.md`, `docs/eval/listeners/{a,b,c,d}/{profile.md,health.md,log.md,exercise-science.md}` (four invented listeners: novice bodyweight no limits; experienced hotel-gym with left ankle delicate; advanced full-gym with low-back off limits; experienced hotel-room with likes and dislikes and an empty log)
- Test: `tests/test_session.py` (class `Eval`): `test_cases_are_forty_and_valid` (parse `cases.toml`; 40 `[[case]]` rows with `id, listener, goal, minutes, preset, level?, target?, limit?`; every goal and level and preset count matches the spec's rule: nine goal-and-level cells times two kits times two lengths is 36, plus four mobility or targeted; every kit in at least four cells; every third case has a limit), `test_every_case_composes` (run `compose` for each case with its listener; exit not USAGE; at least three slots).

- [ ] **Step 1: Write the tests; run; fail.**

- [ ] **Step 2: Write the files.** `judge.md` is the reviewer's prompt: read the case, the skeleton and the script; score 1 to 5 on safety (any excluded load or flag in the script is a 1), efficacy for the goal, likely adherence, ease of construction (how much the writer invented beyond the skeleton); one line of reason each; output a table row per case. `README.md`: generate skeletons with a shell loop over the cases into `docs/eval/out/<id>.skeleton.txt` (`out/` git-ignored), write scripts into `docs/eval/out/<id>.draft.txt`, judge into `docs/eval/results-<date>.md`.

- [ ] **Step 3: Generate the forty skeletons** with the loop; commit the eval files (not `out/`). Commit `Eval grid: forty cases, four invented listeners, judge prompt`.

### Task 11: Write the forty scripts and judge them

**Files:**
- Create: `docs/eval/out/*.draft.txt` (git-ignored), `docs/eval/results-2026-10-21.md` (committed)

- [ ] **Step 1: Write the scripts.** Dispatch script writers in batches of five cases each, each with the workout skill's Step 3 rules and the case's skeleton; no research, no feeds, no build: the topic beats are a one-line placeholder. Each script is linted with `./sweatcast build <draft> --lint-only` against the listener's home and must pass.

- [ ] **Step 2: Judge.** One reviewing agent on the most capable model, with `judge.md`, every case, skeleton and script. Write `results-2026-10-21.md`: the table, then the five lowest-scoring cases with the reason, then what the scores say about the catalog, the dose rules and the methods.

- [ ] **Step 3: Commit** `Eval: first judged run`.

### Task 12: One fix wave from the judging

**Files:** whatever the results name, expected: `knowledge/movements.toml` annotations, `knowledge/sessions.toml` numbers, `tools/session.py` ranking.

- [ ] **Step 1:** Rule on each finding in the results: fix, or record as deferred with a reason in the results file.
- [ ] **Step 2:** Fix; rerun the affected cases' skeletons; `./sweatcast test`.
- [ ] **Step 3:** Commit `Eval fixes: <what changed>`.

### Task 13: Release 4.0.0

**Files:**
- Modify: `CHANGELOG.md`, `VERSION`, `pyproject.toml`, `uv.lock`, `CLAUDE.md` (any last sentence)

- [ ] **Step 1:** CHANGELOG section `## 4.0.0 - 2026-10-21`: the building blocks, `./sweatcast session`, schema 3, the eval grid; "For forks": `./sweatcast migrate`, then `./sweatcast check` lists the experience level and limits to fill in; the `./sweatcast movements --group` flag is now `--pattern`; private movements need `patterns`. Bump `VERSION` and `pyproject.toml`, refresh `uv.lock` (`uv lock`).
- [ ] **Step 2:** Reread every file changed since v3.1.0 for personal details: `git diff v3.1.0 --name-only | xargs grep -n ...` for anything from `me/`.
- [ ] **Step 3:** `./sweatcast test`; commit `Release 4.0.0`.
- [ ] **Step 4:** STOP. Ask before `git tag -a v4.0.0`, push, and `gh release create`.
