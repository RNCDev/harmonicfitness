# Programming Knowledge Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three loosely linked knowledge files (equipment library, injury playbook, exercise science) with a movement catalog, an injury rules file, a programming reference and a tool that filters the catalog for today's kit and injuries. Planning a routine then rests on one movement vocabulary, sourced programming rules and a safety filter the code enforces.

**Architecture:** One TOML catalog (`knowledge/movements.toml`) holds every movement plus the fixed lists of equipment, load tags and muscle groups. A rules file (`knowledge/injury-rules.toml`) maps each body area and phase to banned tags. `tools/catalog.py` loads and checks both, and `./sweatcast movements` prints what's allowed today. Prose stays prose: `knowledge/programming.md` (new), `knowledge/injury-playbook.md` (the procedure and the reasons) and `knowledge/kits.md` (kit logistics, from the equipment library). Context schema 3 adds `[[kits]]` to the profile, `[[injuries]]` to the health file and an optional private `me/movements.toml`.

**Tech Stack:** Python 3.11 standard library only (`tomllib`, `dataclasses`, `unittest`), Markdown, TOML.

**Spec:** the Design section of this document. No separate spec exists.

## Global Constraints

- Python 3.11 standard library only. No new dependencies in `pyproject.toml`.
- Every tool runs through `./sweatcast <command>`. `.claude/settings.json` already allows `Bash(./sweatcast:*)`, so a new subcommand needs no permission change. Don't add one.
- Exit codes come from `tools/cli.py`: `OK` 0, `ISSUES` 1, `USAGE` 64. Parse arguments with `cli.ArgumentParser`.
- The listener's context files are read and written only through `tools/context.py`. Engine files in `knowledge/` are read by `tools/catalog.py`.
- No personal details anywhere in the engine, its tests, fixtures or this plan: no health details, places, gym or brand names tied to one listener, log entries, loads or feedback. `tools/hooks/check-private.sh` only checks paths, so nothing automated catches a personal detail inside a file. Reread every changed engine file for this before committing.
- Spoken text in the catalog (`setup`, `cues`) follows `knowledge/tts-rules.md`: no digits, no symbols, no brackets, no abbreviations.
- Plain language in docs and comments, in the voice of `CLAUDE.md`.
- Each phase ends with a release per `CLAUDE.md` (CHANGELOG section, `VERSION`, `pyproject.toml`, tag, push, GitHub release). Ask the owner before each push. Versions: Phase 0 is 3.0.1, Phase 1 is 3.1.0, Phase 2 is 3.2.0 and Phase 3 is 4.0.0.
- `./sweatcast test` passes at the end of every task.
- Research tasks never write a finding from memory. Each claim has one source URL that was opened and one line on what it doesn't show. Studies named in this plan are candidates to verify, not findings.

## Review Focus

1. **Log names with side words, capitals or extra detail** ("Right single-leg glute bridge", "seated bent-over rowing"): they should resolve to the catalog movement. Pinned in Task 1.4.
2. **A health file that lists an injury in prose but has no `[[injuries]]` block** (any folder migrated from schema 2 with an injury): the filter must refuse (exit 1) rather than treat it as "no injuries". Pinned in Task 3.3.
3. **An injury in an area the rules file doesn't cover** (an elbow, say): the tool must say so on its first line and apply only that injury's `extra_ban`, never pass silently. `check` flags it when `extra_ban` is empty. Pinned in Tasks 3.1 and 3.3.
4. **A private movement that reuses an engine id or names an unknown tag**: `check` reports it, and the filter exits 1 rather than loading a catalog it can't trust. Pinned in Task 3.2.
5. **A phase written with capitals or a wrong word** ("Protect", "rehab"): case is ignored; an unknown phase exits 1 naming the four valid ones. Pinned in Task 3.3.

---

## Design

### Why

- The equipment library lists movements by kit, `tools/coverage.py` maps them to muscle groups with its own regexes, the playbook bans them by name, and the science file is keyed by name again. None of these point at each other, so the same movement goes by several names.
- The injury tags in the equipment library are inconsistent. The same movement is tagged in one kit's section and untagged in another, so "pick only from what remains" can let a banned movement through.
- Nothing in `knowledge/` says how to dose a session (effort, sets, rest, tempo, progression). The only rules are a few lines in the workout skill's Step 2.
- Only one body area in the playbook has steps for each phase, and no area has criteria for moving to the next phase, though the setup skill and the check-in both ask for them.
- The per-session exercise-science lookup only runs when the kit is known before the check-in, which is rare, so it almost never runs.

### File layout after Phase 3

| File | Read by | Holds |
|---|---|---|
| `knowledge/movements.toml` | tools | Equipment, tags, groups and kit presets (the fixed lists), then every `[[movement]]` |
| `knowledge/injury-rules.toml` | tools | Each area's phases: banned tags, banned ids, cautions, rehab includes, criteria for moving on, sources |
| `knowledge/injury-playbook.md` | Claude | The procedure, stop rule, red flags, cue style, and per area the reasons and sources. It never repeats the bans. |
| `knowledge/programming.md` | Claude | How to dose and order a session, by type and length, with sources |
| `knowledge/kits.md` | Claude | Kit logistics: hotel room, hotel gym, full gym, bike and rower scripting language (the old equipment library minus its movement lists) |
| `knowledge/exercise-science.md` | Claude | Unchanged format; each entry's name resolves in the catalog |
| `me/movements.toml` | tools | Optional private additions, same `[[movement]]` format plus `schema = 3` |
| `me/profile.md` | both | Adds `[[kits]]` to the settings block |
| `me/health.md` | both | Adds `[[injuries]]` to the settings block |

### Catalog format (`knowledge/movements.toml`)

```toml
format = 1   # the catalog's own format; the context schema is separate

groups = ["horizontal push", "horizontal pull", "hip hinge or glutes", "hamstrings", "quads",
          "hip abductors and adductors", "anti-extension core", "lateral or anti-rotation core", "arms"]

kinds = ["strength", "cardio", "mobility", "breathing", "skill", "rehab", "finisher"]

[equipment]   # floor and wall are always available, so they aren't listed
dumbbells = { aliases = ["dumbbell", "dumbbells"], about = "fixed or adjustable dumbbells" }
# also: kettlebell, bench, band, mat, chair, towel, foam-roller, strap, bike, rower,
# cable, machines, barbell, rack, ski-erg, air-bike, sled, treadmill, elliptical,
# stair-climber, stick-and-ball

[tags]   # what a movement loads; the injury rules ban these
impact = "jumping, hopping, landing or running"
# the full list is below

[presets.hotel-room]
equipment = ["chair", "towel"]
# also: bodyweight (nothing), hotel-gym, full-gym

[[movement]]
id = "goblet-squat"                       # lowercase words joined by hyphens, unique
name = "goblet squat"                     # what the log and script call it
aliases = ["dumbbell goblet squat", "kettlebell goblet squat"]
kind = "strength"
needs = ["dumbbells|kettlebell"]          # every item required; "|" means either
position = "standing"                     # standing, seated, lying, side-lying, kneeling, all-fours
sided = false                             # true: done one side at a time, so both sides need time
measure = "reps"                          # reps or time
groups = ["quads", "hip hinge or glutes"]
tags = ["standing", "knee-deep-bend", "ankle-bend"]
setup = "Hold one weight upright at your chest, feet a little wider than your hips."
cues = ["Sit between your heels.", "Elbows inside the knees.", "Chest tall."]
easier = ["box-squat"]                    # ids that exist in the catalog
harder = []
```

The tag list (fixed; adding one is a catalog change with a reason in the CHANGELOG):

| Tag | Means |
|---|---|
| `impact` | jumping, hopping, landing or running |
| `standing` | weight on both feet |
| `single-leg-stance` | weight on one foot |
| `ankle-push` | pushing hard through the ball of the foot: calf raises, step-ups, standing pedal efforts, sled, leg press |
| `ankle-bend` | deep ankle bend under body weight: squats, lunges, split squats |
| `lateral` | side-to-side, shuffling or pivoting footwork |
| `knee-deep-bend` | knee bent past about ninety degrees under load |
| `knee-load` | loaded knee straightening or holding: leg extension, wall sit |
| `kneeling` | weight on a knee |
| `floor-transition` | getting down to the floor and back up |
| `spine-flexion` | curling the spine against resistance: crunches, sit-ups, reverse crunches, hollow holds |
| `spine-load` | hinging or bent-over loading of the low back |
| `spine-twist` | turning the trunk under load |
| `overhead` | arms overhead under load |
| `shoulder-end-range` | dips, wide-grip pressing, behind-the-neck work, loaded end-range stretch |
| `hanging` | hanging from the hands |
| `wrist-load` | weight on the hands with the wrist bent back: push-ups, planks on hands, all fours, front rack |
| `grip` | heavy or long gripping |
| `neck-load` | load on, or fast movement of, the neck |
| `hip-deep-bend` | hip bent sharply under load |
| `hip-wide` | wide stance or deep side-to-side hip motion |
| `kick` | kicking or fast leg swings |
| `lying-side` | lying on one side |

Tags don't name a side. Rules that matter for one side use `ban_injured_side` (below), and the tool lists those movements as "healthy side only" when the movement is `sided`.

### Injury rules format (`knowledge/injury-rules.toml`)

```toml
format = 1
phases = ["protect", "restore", "rebuild", "return"]

[areas.knee]
playbook = "Knee"                      # its ## heading in injury-playbook.md
[areas.knee.protect]
ban = ["impact", "knee-deep-bend", "kneeling", "lateral"]
ban_injured_side = ["single-leg-stance"]
ban_ids = []                           # anything the tags miss
caution = { glute-bridge = "Only if pain-free." }
include = []                           # rehab ids to add in this phase
advance_when = ["Walks and climbs stairs without pain."]
sources = ["https://..."]
# restore, rebuild, return follow, each with its full lists (not changes from the last)
```

Each phase lists its full `ban`, so a later phase can only ban the same or fewer tags than an earlier one. The tests check that. `return` has an empty `advance_when`.

### Context schema 3

Profile settings gain kits, each naming its equipment or a preset:

```toml
[[kits]]
name = "Home"
equipment = ["dumbbells", "bench", "mat"]

[[kits]]
name = "Travel"
preset = "hotel-room"
```

Health settings gain injuries. The block is the tools' source of truth; the prose keeps the history and the clinician's words.

```toml
[[injuries]]
area = "knee"          # an area in injury-rules.toml, or "other"
side = "right"         # left, right, both or none
phase = "restore"
since = 2026-01-05     # when this phase was set
extra_ban = []         # tags or ids from a clinician's rules, on top of the area's
```

`injuries = []` means no injuries. A missing `injuries` key means "not filled in yet", and the filter refuses to run.

### The filter's contract

`./sweatcast movements` narrows the choice, never widens it. Claude still applies the health file's prose and clinician rules on top, and the strictest rule wins. The tool prints, in order:
1. warnings (an area with no rules, an injury in prose only);
2. allowed movements under each group heading, in catalog group order;
3. "Healthy side only";
4. "Caution";
5. "Include for rehab";
6. a one-line count of what was left out and why.

Exit 1 with a fix when the injuries can't be read safely. Exit 64 for a kit name that isn't in the profile.

### Exercise-science lookup

The per-session lookup moves from the headlines agent's first prompt to Step 2. Once the plan is posted, if the headlines agent is still running, SendMessage it up to two planned movements that have no entry in either science file. If it has finished, skip the lookup. A one-time top-up (Task 2.3) adds the commonly planned movements.

---

## Phase 0: hygiene patch (3.0.1)

### Task 0.1: Fix inconsistent tags and remove listener-specific names

**Files:**
- Modify: `knowledge/equipment-library.md`
- Modify: `CHANGELOG.md`, `VERSION`, `pyproject.toml`

- [ ] **Step 1: Tag every movement consistently.** For each movement that appears in more than one section, give it the same tags everywhere (the strictest set). Tag every untagged movement that loads a joint. At least: seated calf raise (ankle) in Dumbbells; goblet squat (knee, ankle, standing), kettlebell deadlift (back, standing), suitcase carry (standing, ankle), halo (shoulder) and seated or half-kneeling press (knee, shoulder) in Kettlebell; box squats (knee, ankle, standing) in Bench; reverse crunches and hollow hold (back) in No equipment; ninety-ninety hip switches and world's greatest stretch checked in Mat and mobility.
- [ ] **Step 2: Remove the named club from the Full gym heading and the bike brand from the Stationary bike heading.** The headings become `## Full gym` and `## Stationary bike`.
- [ ] **Step 3: Verify.** Run `grep -n "^## " knowledge/equipment-library.md`. Expected: the two headings read exactly `## Full gym` and `## Stationary bike`, and no heading, skill or doc names a specific club or brand. Run `./sweatcast test`. Expected: all pass.
- [ ] **Step 4: Release 3.0.1.** Add the CHANGELOG section (Fixed: inconsistent injury tags; removed listener-specific names), bump `VERSION` and `pyproject.toml`, commit, and ask the owner before tagging and pushing. Note in the summary that the old text stays in git history; whether to rewrite it is the owner's call.

---

## Phase 1: the catalog (3.1.0)

### Task 1.1: Catalog loader and checks

**Files:**
- Create: `tools/catalog.py`
- Modify: `tools/paths.py` (add `MOVEMENTS = ROOT/knowledge/movements.toml`, `INJURY_RULES = ROOT/knowledge/injury-rules.toml`, `MY_MOVEMENTS = HOME/movements.toml`)
- Create: `tests/test_catalog.py`, `tests/fixtures/movements.toml` (synthetic: the full fixed lists, presets `bodyweight` and `full-gym`, and six movements: `goblet-squat` as in the Design, `box-squat`, `single-leg-balance` (no equipment, `sided`, tags `single-leg-stance`), `push-up` (`wrist-load`), `dead-bug`, `box-breathing` (kind `breathing`))

**Interfaces:**
- Produces:
  - `@dataclass Movement(id: str, name: str, aliases: List[str], kind: str, needs: List[str], position: str, sided: bool, measure: str, groups: List[str], tags: List[str], setup: str, cues: List[str], easier: List[str], harder: List[str], private: bool = False)`
  - `@dataclass Catalog(groups: List[str], kinds: List[str], equipment: Dict[str, dict], tags: Dict[str, str], presets: Dict[str, List[str]], movements: Dict[str, Movement])`
  - `load(path: str = paths.MOVEMENTS, extra: Optional[List[dict]] = None) -> Catalog` (`extra` are private `[[movement]]` tables, marked `private=True`)
  - `problems(cat: Catalog) -> List[str]`, one plain sentence each
  - `resolve(cat: Catalog, name: str) -> Optional[Movement]`

- [ ] **Step 1: Write the failing tests** in `tests/test_catalog.py`, class `CatalogFormat`, against the fixture:

```python
def test_loads_fixture(self):
    cat = catalog.load(FIXTURE)
    self.assertEqual(cat.groups[0], "horizontal push")
    self.assertIn("goblet-squat", cat.movements)

def test_problems_name_each_fault(self):
    bad = [{"id": "x", "name": "x", "kind": "strength", "needs": ["anvil"], "position": "standing",
            "sided": False, "measure": "reps", "groups": ["calves"], "tags": ["wobbly"],
            "setup": "Stand up 2 times.", "cues": ["Go."], "easier": ["nope"], "harder": []}]
    msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
    for word in ("anvil", "calves", "wobbly", "nope", "digit"):
        self.assertIn(word, msgs)

def test_duplicate_id_or_alias_is_a_problem(self):
    dup = dict(vars(catalog.load(FIXTURE).movements["goblet-squat"]))
    dup.pop("private")
    self.assertTrue(any("goblet-squat" in p for p in catalog.problems(catalog.load(FIXTURE, extra=[dup]))))

def test_resolve(self):
    cat = catalog.load(FIXTURE)
    for said in ("goblet squat", "Goblet Squat", "kettlebell goblet squat", "left goblet squat"):
        self.assertEqual(catalog.resolve(cat, said).id, "goblet-squat")
    self.assertIsNone(catalog.resolve(cat, "mystery move"))
```

- [ ] **Step 2: Run them.** `./sweatcast test -k CatalogFormat`. Expected: errors, `catalog` not found.
- [ ] **Step 3: Implement `tools/catalog.py`.** `problems` checks: unique ids, names and aliases (case-insensitive) across engine and private entries; `kind`, `position`, `measure`, `groups`, `tags` and each `needs` alternative are in the fixed lists; `easier` and `harder` ids exist; `setup` and every cue have no digits, brackets or symbols other than `.,'?!-` (the message says "digit" or "symbol"); every preset's equipment is known. `resolve` lowercases, strips a leading `left `, `right ` or `both sides `, then matches name or alias exactly.
- [ ] **Step 4: Run them.** `./sweatcast test -k CatalogFormat`. Expected: PASS.
- [ ] **Step 5: Commit.** `git add tools/catalog.py tools/paths.py tests/test_catalog.py tests/fixtures/movements.toml && git commit -m "Add the movement catalog loader and its checks"`

### Task 1.2: Port the strength movements

**Files:**
- Create: `knowledge/movements.toml` (fixed lists, presets, and the strength, core and arm movements)
- Test: `tests/test_catalog.py`, class `RealCatalog`

**Interfaces:**
- Consumes: `catalog.load`, `catalog.problems`, `catalog.resolve` (Task 1.1).

- [ ] **Step 1: Write the failing tests:**

```python
def test_real_catalog_has_no_problems(self):
    self.assertEqual(catalog.problems(catalog.load()), [])

def test_every_kind_of_strength_work_is_there(self):
    cat = catalog.load()
    for g in cat.groups:
        self.assertTrue(any(g in m.groups for m in cat.movements.values()), g)

def test_names_the_skill_and_tests_rely_on(self):
    cat = catalog.load()
    for said in ("seated bent-over rowing", "lying leg curl", "dead bug", "side plank from the knee",
                 "single-leg glute bridge", "clamshell", "straight-leg raise", "incline push-up",
                 "goblet squat", "farmer carry", "suitcase carry", "pallof press", "hammer curl"):
        self.assertIsNotNone(catalog.resolve(cat, said), said)
```

- [ ] **Step 2: Run them.** Expected: FAIL (no catalog file).
- [ ] **Step 3: Write the entries.** Port every strength, core and arm movement from the No equipment, Dumbbells, Kettlebell, Bench and Resistance bands sections of `knowledge/equipment-library.md`, and the machine, cable and barbell strength work from Full gym. Add the seated, lying and bench-supported variants that injury-friendly sessions need (seated bent-over row, chest-supported row, seated press, seated curl and kickback, floor press, lying hamstring curl with a dumbbell, face-down hip extension on the bench, pillow-squeeze bridge). Expect about seventy to ninety entries. Each gets a spoken `setup`, two or three cues and tags from the fixed list. Wherever the old library gave a movement different tags in different sections, use the strictest. Fill `easier` and `harder` where a natural step exists.
- [ ] **Step 4: Run them.** `./sweatcast test -k RealCatalog`. Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "Port strength movements into the catalog"`

### Task 1.3: Port cardio, mobility, breathing, skills and rehab

**Files:**
- Modify: `knowledge/movements.toml`
- Test: `tests/test_catalog.py`, class `RealCatalog`

- [ ] **Step 1: Write the failing test:**

```python
def test_non_strength_kinds_and_presets(self):
    cat = catalog.load()
    kinds = {m.kind for m in cat.movements.values()}
    self.assertTrue({"cardio", "mobility", "breathing", "skill", "rehab", "finisher"} <= kinds)
    self.assertEqual(set(cat.presets), {"bodyweight", "hotel-room", "hotel-gym", "full-gym"})
    self.assertIsNotNone(catalog.resolve(cat, "box breathing"))
    self.assertIsNotNone(catalog.resolve(cat, "seated ankle alphabet"))
```

- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Write the entries.** Port the cardio and warm-up moves, the Stationary bike, Rowing machine and Mat and mobility sections, the stick-and-ball drills (kind `skill`), the band ankle work and seated ankle alphabet and circles (kind `rehab`), and the seated punching and arm-drill finishers. Presets: `bodyweight` (no equipment), `hotel-room` (chair, towel), `hotel-gym` (dumbbells, bench, treadmill, elliptical, bike, mat) and `full-gym` (everything except stick-and-ball).
- [ ] **Step 4: Run it.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "Port cardio, mobility, skills and rehab into the catalog"`

### Task 1.4: Coverage reads the catalog, and counts the week

**Files:**
- Modify: `tools/coverage.py`
- Test: `tests/test_tools.py`, class `Coverage` (existing assertions stay as they are)

**Interfaces:**
- Consumes: `catalog.load`, `catalog.resolve`.
- Produces: `groups_of(movement: str, cat: Optional[Catalog] = None) -> List[str]` (catalog first, then the existing regex `GROUPS` as a fallback for free-text names); `week(sessions, today: date, days: int = 7) -> Dict[str, int]` (sessions per group in the last `days` days).

- [ ] **Step 1: Write the failing tests** (added to `Coverage`):

```python
def test_catalog_groups_match_the_checklist(self):
    self.assertEqual(catalog.load().groups, [g for g, _ in coverage.GROUPS])

def test_side_words_and_capitals_resolve(self):
    self.assertEqual(coverage.groups_of("Right Single-Leg Glute Bridge"),
                     coverage.groups_of("single-leg glute bridge"))
    self.assertIn("hamstrings", coverage.groups_of("right single-leg glute bridge"))

def test_finishers_and_skills_are_not_unmapped(self):
    _, unmapped = coverage.coverage(["seated punching finisher", "box breathing", "mystery move"])
    self.assertEqual(unmapped, ["mystery move"])

def test_week_counts_sessions_per_group(self):
    counts = coverage.week(context.sessions(self.path), dt.date(2026, 10, 21))
    self.assertEqual(counts["horizontal pull"], 1)
    self.assertEqual(counts["arms"], 1)
```

- [ ] **Step 2: Run them.** `./sweatcast test -k Coverage`. Expected: the new ones FAIL; the old ones PASS.
- [ ] **Step 3: Implement.** A movement whose catalog kind isn't `strength` counts as on purpose, like today's `NOT_STRENGTH`. The output adds, after "Prioritize": `Last 7 days, sessions per group:` and one line per group, `  <n>  <group>`. Groups under two sessions come first today, after the ones the last session left out.
- [ ] **Step 4: Run them.** Expected: all `Coverage` tests and `FreshFork` PASS.
- [ ] **Step 5: Commit.** `git commit -m "coverage reads the catalog and counts the week"`

### Task 1.5: `./sweatcast movements` (explicit equipment and tags)

**Files:**
- Create: `tools/movements.py`
- Modify: `tools/sweatcast.py` (`COMMANDS["movements"] = ("movements", None, "movements allowed today, by group, for a kit and injuries")`)
- Modify: `tools/catalog.py`
- Test: `tests/test_catalog.py`, class `Filter`

**Interfaces:**
- Produces:
  - `catalog.Selection = NamedTuple("Selection", allowed=List[Movement], healthy_side_only=List[Movement], left_out=Dict[str, List[str]])` (`left_out`: id to the tags or reasons that ruled it out)
  - `catalog.select(cat, equipment: Set[str], avoid: Set[str], avoid_injured_side: Set[str] = frozenset(), ban_ids: Set[str] = frozenset()) -> Selection`
  - `catalog.kit_equipment(cat, kit: dict) -> Set[str]` (a kit dict has `equipment` or `preset`)
  - CLI: `./sweatcast movements (--preset NAME | --equipment a,b) [--avoid tag,tag] [--group G]`

- [ ] **Step 1: Write the failing tests** against the fixture:

```python
def test_equipment_and_tags_narrow(self):
    sel = catalog.select(self.cat, {"dumbbells"}, {"knee-deep-bend"})
    ids = {m.id for m in sel.allowed}
    self.assertNotIn("goblet-squat", ids)
    self.assertIn("knee-deep-bend", sel.left_out["goblet-squat"])

def test_needs_alternatives(self):
    self.assertIn("goblet-squat", {m.id for m in catalog.select(self.cat, {"kettlebell"}, set()).allowed})

def test_injured_side_only_affects_sided_movements(self):
    sel = catalog.select(self.cat, set(), set(), avoid_injured_side={"single-leg-stance"})
    self.assertIn("single-leg-balance", {m.id for m in sel.healthy_side_only})

def test_unknown_tag_or_preset_exits_64(self):
    for args in (["--preset", "castle"], ["--equipment", "dumbbells", "--avoid", "wobbly"]):
        self.assertEqual(run_movements(args).returncode, 64)

def test_output_is_grouped_in_checklist_order(self):
    out = run_movements(["--preset", "full-gym"]).stdout
    self.assertLess(out.index("horizontal push"), out.index("arms"))
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** Each allowed line reads `  <name> (<position>[, one side at a time]): <setup> Cues: <cues joined by spaces> [Easier: <names>] [Harder: <names>]`. Movements of other kinds go under their kind as a heading after the groups. The last line is `Left out today: <n> (<tag>: <count>, ...)`.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "Add ./sweatcast movements"`

### Task 1.6: The equipment library becomes `kits.md`; skills use the catalog

**Files:**
- Rename: `knowledge/equipment-library.md` to `knowledge/kits.md` (`git mv`)
- Modify: `knowledge/injury-playbook.md` (each area section gets one line, `Tags to avoid early: ...`, from the fixed list; interim until Phase 2)
- Modify: `.claude/skills/workout/SKILL.md` (Step 0 reads `knowledge/kits.md`; Step 2 runs the filter)
- Modify: `CLAUDE.md`, `README.md` (file lists)
- Modify: `CHANGELOG.md`, `VERSION`, `pyproject.toml`

- [ ] **Step 1: Strip the movement lists from `kits.md`.** Keep what each kit usually contains, and the scripting notes: bike cadence and effort language, clip-in note, rower stroke cue, hotel noise and towel-row door rule, hotel gym swaps, full gym zones, fallbacks, barbell setup time and the no-spotter rule. Point to the catalog for movements.
- [ ] **Step 2: Rewrite the skill's Step 2 selection rule.** It becomes: after the check-in, run `./sweatcast movements --preset <preset> | --equipment <the kit's equipment from the profile prose>` with `--avoid` set to the playbook's "Tags to avoid early" for each active injury, then apply the health file's rules on top; strictest wins. Log movements by their catalog names.
- [ ] **Step 3: Verify.** `git grep -n "equipment-library"` returns only CHANGELOG lines. `./sweatcast test` passes. Run `./sweatcast movements --preset hotel-room` and check that the output reads sensibly.
- [ ] **Step 4: Release 3.1.0.** CHANGELOG Added (catalog, `./sweatcast movements`, weekly counts in coverage), Changed (the equipment library is now `kits.md`). Commit, then ask before tagging and pushing.

---

## Phase 2: research (3.2.0)

Tasks 2.1 and 2.3 don't depend on the tag list and can run in parallel with Phase 1. Task 2.2 needs Task 1.2.

Each research task works under a budget: at most twenty web searches and twelve page fetches. Every claim opens its source. Use primary papers, systematic reviews, position stands or clinical practice guidelines first. Each claim is written in the science file's style: what was found, in plain words; a `Source:` URL; and what it doesn't show. Anything not confirmed within the budget is left out and listed under "Searched without a confirmed source" at the end of the file.

### Task 2.1: `knowledge/programming.md`

**Files:**
- Create: `knowledge/programming.md`
- Modify: `.claude/skills/workout/SKILL.md` (Step 2 keeps the session-flow rules: split, rotation, no repeats, bilateral, coverage; dose and progression move out and point here)
- Test: `tests/test_catalog.py`, class `KnowledgeFiles`

Questions to answer, one section each:
1. **Effort.** How close to failure sets should go for strength and muscle, and how to say it by ear (reps in reserve, effort out of ten).
2. **Load range.** Whether light loads taken near failure match heavy ones, which matters for home kits with few dumbbells.
3. **Weekly dose.** Hard sets per muscle per week and how often to train each muscle, and what a fifteen, twenty-five and forty-five minute session can hold.
4. **Rest and pairing.** Rest between sets, and pairing opposing muscles or upper with lower to save time.
5. **Tempo.** What slower lowering and pauses do, and what range is fine.
6. **Progression.** The order of steps when load is capped (reps, tempo, pause, range, one-side work, then load), and how "too easy" and "too hard" should change the next session.
7. **Warm-up, finisher, cool-down.** What a short warm-up needs before strength work, and what the breathing close does and doesn't do.
8. **One-sided training.** How much strength carries over to the untrained side (cross-education), including during immobilization.
9. **Session templates.** For each session type in the skill (strength, mobility and breathing, skills, bike intervals, ten-minute snack): block shapes and dose at fifteen, twenty-five and forty-five minutes.

Candidates to verify (confirm or discard): Schoenfeld and colleagues on weekly volume (2017), load range (2017), training frequency (2016) and repetition duration (2015); Refalo and colleagues on proximity to failure (2023); Iversen and colleagues on minimal effective dose (2021); the ACSM resistance-training position stand; Manca and colleagues (2017) and Hendy and colleagues (2012) on cross-education.

- [ ] **Step 1: Write the failing test:**

```python
def test_programming_reference_is_sourced(self):
    text = open(os.path.join(ROOT, "knowledge", "programming.md")).read()
    for heading in ("## Effort", "## Load range", "## Weekly dose", "## Rest and pairing", "## Tempo",
                    "## Progression", "## Warm-up, finisher and cool-down", "## One-sided training",
                    "## Session templates"):
        self.assertIn(heading, text)
    self.assertGreaterEqual(text.count("Source: https://"), 8)
```

- [ ] **Step 2: Run it.** Expected: FAIL.
- [ ] **Step 3: Research and write.** Keep the file under about two thousand words. Each section ends with the rule Claude follows when planning, in one or two sentences.
- [ ] **Step 4: Update the skill's Step 2** to point to `knowledge/programming.md` for dose, effort and progression, and add it to Step 0's read list.
- [ ] **Step 5: Run the tests.** Expected: PASS. Commit: `git commit -m "Add the programming reference"`

### Task 2.2: `knowledge/injury-rules.toml` and the playbook rewrite

**Files:**
- Create: `knowledge/injury-rules.toml`
- Modify: `knowledge/injury-playbook.md` (drop the per-phase lists and the interim tag lines; keep the procedure, stop rule, red flags and cue style; per area, the reasons, what each phase is for, how to judge the criteria, and sources)
- Modify: `tools/catalog.py` (`load_rules`, `rule_problems`)
- Modify: `.claude/skills/workout/SKILL.md` (the check-in's "Better, and [criteria]" comes from `advance_when`) and `.claude/skills/setup/SKILL.md` (phase and criteria from the rules file)
- Test: `tests/test_catalog.py`, class `InjuryRules`

**Interfaces:**
- Produces: `load_rules(path: str = paths.INJURY_RULES) -> Dict[str, dict]` (area to `{"playbook": str, phase: {"ban", "ban_injured_side", "ban_ids", "caution", "include", "advance_when", "sources"}}`); `rule_problems(rules, cat: Catalog, playbook_text: str) -> List[str]`.

Areas: ankle, knee, lower back, shoulder, wrist and hand, neck, hip, plus elbow (a common gap). For each area and phase: what to ban, what to add, and evidence-based criteria for moving on. For the ankle's rebuild and return, find the evidence on balance training to prevent a second sprain. Candidates to verify: the 2018 BJSM ankle sprain clinical practice guideline (Vuurberg and colleagues); the 2020 "PEACE and LOVE" soft-tissue guidance (Dubois and Esculier); the 2016 patellofemoral pain consensus (Crossley and colleagues); guidance on low back pain and exercise (NICE NG59); rotator cuff tendinopathy loading guidance. Clinician rules in a listener's health file always override.

- [ ] **Step 1: Write the failing tests:**

```python
def test_rules_have_no_problems(self):
    playbook = open(os.path.join(ROOT, "knowledge", "injury-playbook.md")).read()
    self.assertEqual(catalog.rule_problems(catalog.load_rules(), catalog.load(), playbook), [])

def test_later_phases_never_ban_more(self):
    for area, r in catalog.load_rules().items():
        for a, b in zip(PHASES, PHASES[1:]):
            self.assertLessEqual(set(r[b]["ban"]), set(r[a]["ban"]), f"{area} {b}")

def test_every_phase_but_return_says_when_to_move_on(self):
    for area, r in catalog.load_rules().items():
        for p in PHASES[:-1]:
            self.assertTrue(r[p]["advance_when"], f"{area} {p}")
            self.assertTrue(r[p]["sources"], f"{area} {p}")
```

`rule_problems` reports unknown tags or ids, a missing phase, an area whose `playbook` heading isn't a `## ` line in the playbook, and a `caution` or `include` id that isn't in the catalog.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Research, write the rules file and rewrite the playbook.** The protect phase must stay at least as strict as today's playbook for every area.
- [ ] **Step 4: Update both skills' wording** for phase and criteria.
- [ ] **Step 5: Run the tests.** Expected: PASS. Commit: `git commit -m "Add injury rules by area and phase, with criteria and sources"`

### Task 2.3: Exercise-science top-up and the lookup trigger

**Files:**
- Modify: `knowledge/exercise-science.md`
- Modify: `.claude/skills/workout/SKILL.md` (remove the "[If the kit is already known ...]" clause from the headlines template; add the SendMessage rule from the Design to Step 2)
- Test: `tests/test_catalog.py`, class `KnowledgeFiles`

Add about ten movements that sessions plan often and that have no entry yet: goblet squat, Romanian deadlift, push-up, floor press, chest-supported row, Pallof press, farmer carry, face pull, hip thrust, bird dog. Each fact should help explain a cue or a choice. Keep the "don't search again" list, adding what fails.

- [ ] **Step 1: Write the failing test:**

```python
def test_science_entries_name_catalog_movements_and_cite(self):
    cat = catalog.load()
    entries = re.findall(r"^- \*\*(.+?):\*\* (.+)$", open(SCIENCE).read(), re.M)
    self.assertGreaterEqual(len(entries), 15)
    for name, body in entries:
        self.assertIsNotNone(catalog.resolve(cat, name), name)
        self.assertIn("Source: https://", body)
```

- [ ] **Step 2: Run it.** Expected: FAIL (too few entries; some names may not resolve, so add aliases to the catalog where needed).
- [ ] **Step 3: Research and write the entries; edit the skill.**
- [ ] **Step 4: Run the tests.** Expected: PASS. Commit: `git commit -m "Top up exercise science; look up facts after the plan"`
- [ ] **Step 5: Release 3.2.0.** CHANGELOG Added (the programming reference, the injury rules, more science). Ask before tagging and pushing.

---

## Phase 3: context schema 3 and the automatic filter (4.0.0)

### Task 3.1: Kits and injuries in the settings blocks; migration

**Files:**
- Modify: `tools/context.py` (`SCHEMA = 3`; `kits(p) -> List[dict]`; `injuries(path=None) -> Optional[List[dict]]` (`None` when the key is missing); check issues)
- Modify: `tools/migrate.py` (`to_3`, `STEPS[2] = to_3`, docstring)
- Modify: `me.example/profile.md`, `me.example/health.md` (schema 3, a `[[kits]]` example, `injuries = []`)
- Test: `tests/test_tools.py`, classes `Context` and `Migrate`

**Interfaces:**
- Consumes: `catalog.load()` for the equipment aliases used in kit inference, and `catalog.load_rules()` for checks.
- Produces: `context.kits(p) -> List[dict]`, `context.injuries(path=None) -> Optional[List[dict]]`, `context.PHASES = ("protect", "restore", "rebuild", "return")`.

`to_3`: in `profile.md`, each line under `## Equipment kits` becomes a `[[kits]]` table. The name is the text before the colon. The equipment is every catalog equipment key whose alias appears in the line (whole words, ignoring case). The line stays in the prose. In `health.md`, write `injuries = []` only when the Active injuries section is exactly `- None right now.`; otherwise add no key. Other files only change their schema number.

- [ ] **Step 1: Write the failing tests:**

```python
def test_migrate_infers_kits(self):            # Migrate
    # profile prose "- Home: a pair of dumbbells, a bench and a mat" becomes
    self.assertEqual(kits[0], {"name": "Home", "equipment": ["dumbbells", "bench", "mat"]})

def test_migrate_never_invents_no_injuries(self):
    # health.md with an injury listed in prose: no injuries key after migrating
    self.assertIsNone(context.injuries(health_path))

def test_migrate_none_right_now(self):
    self.assertEqual(context.injuries(health_path), [])

def test_check_flags_prose_injury_without_block(self):     # Context
    self.assertTrue(any("[[injuries]]" in i.message and not i.note for i in context.check([health_path])))

def test_check_flags_unknown_area_without_extra_ban(self):
    # [[injuries]] area = "elbow-ish", side = "left", phase = "protect", extra_ban = []
    issues = context.check([health_path])
    self.assertTrue(any("elbow-ish" in i.message and not i.note for i in issues))

def test_check_notes_a_kit_with_no_equipment(self):
    # [[kits]] name = "Travel", equipment = []
    issues = context.check([profile_path])
    self.assertTrue(any("Travel" in i.message and i.note for i in issues))
```

Update the existing `Migrate` tests that list file names or expect schema 2 so they expect schema 3.

- [ ] **Step 2: Run them.** `./sweatcast test -k Migrate -k Context`. Expected: the new ones FAIL.
- [ ] **Step 3: Implement.** Issues: a kit with neither `equipment` nor `preset`, or with an unknown item (error); an empty kit (note); an injury with an unknown phase, side or area, or an `other` or unknown area with no `extra_ban` (error); a missing `injuries` key while the prose lists anything but "None right now." (error, with the message "add an [[injuries]] block to health.md's settings; the check-in fills it in").
- [ ] **Step 4: Run them.** Expected: PASS, including `FreshFork`.
- [ ] **Step 5: Commit.** `git commit -m "Schema 3: kits and injuries in the settings blocks"`

### Task 3.2: Private movements, `me/movements.toml`

**Files:**
- Modify: `tools/context.py` (`my_movements(path=paths.MY_MOVEMENTS) -> List[dict]`: reads a plain TOML file with `schema = 3` and `[[movement]]` tables; missing file gives `[]`; a wrong schema raises the usual migrate message; `check()` validates it through `catalog.problems`)
- Create: `me.example/movements.toml` (`schema = 3` and a commented example entry)
- Test: `tests/test_tools.py`, class `Context`

`context.files()` stays Markdown-only. `check()` and `migrate.plan()` add `paths.MY_MOVEMENTS` through a separate `toml_files()` list.

- [ ] **Step 1: Write the failing tests:** a private entry loads with `private=True`; one reusing an engine id is an issue naming the id; one with an unknown tag is an issue naming the tag; a missing file is fine.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "Private movements in me/movements.toml"`

### Task 3.3: The filter reads the kit and injuries itself

**Files:**
- Modify: `tools/movements.py`, `tools/catalog.py`
- Test: `tests/test_catalog.py`, class `Filter`

**Interfaces:**
- Consumes: `context.profile`, `context.kits`, `context.injuries`, `context.my_movements`, `catalog.load_rules`.
- Produces: `catalog.today(rules, injuries: List[dict]) -> Today` with `Today = NamedTuple(avoid: Set[str], avoid_injured_side: Set[str], ban_ids: Set[str], cautions: Dict[str, str], include: List[str], warnings: List[str])`. CLI: `./sweatcast movements --kit NAME [--group G]`, and `./sweatcast movements --injuries`, which prints each injury's area, side, phase, since, and `advance_when`. `--preset`, `--equipment` and `--avoid` stay for trying things out.

- [ ] **Step 1: Write the failing tests:**

```python
def test_prose_only_injury_refuses(self):
    out = run_movements(["--kit", "Home"], home=self.home_with_prose_injury)
    self.assertEqual(out.returncode, 1)
    self.assertIn("[[injuries]]", out.stdout + out.stderr)

def test_unlisted_area_warns_first_and_applies_extra_ban(self):
    out = run_movements(["--kit", "Home"], home=self.home_with({"area": "other", "side": "left",
                        "phase": "protect", "extra_ban": ["grip"]}))
    self.assertTrue(out.stdout.splitlines()[0].startswith("Warning:"))
    self.assertNotIn("farmer carry", out.stdout.split("Left out today")[0])

def test_phase_case_and_unknown_phase(self):
    self.assertEqual(run_movements(["--kit", "Home"], home=self.home_with({"area": "knee", "side": "right",
                     "phase": "Protect"})).returncode, 0)
    out = run_movements(["--kit", "Home"], home=self.home_with({"area": "knee", "side": "right", "phase": "rehab"}))
    self.assertEqual(out.returncode, 1)
    self.assertIn("protect, restore, rebuild, return", out.stdout + out.stderr)

def test_unknown_kit_is_64_and_lists_kits(self):
    out = run_movements(["--kit", "Castle"], home=self.home)
    self.assertEqual(out.returncode, 64)
    self.assertIn("Home", out.stderr)

def test_bans_union_across_injuries(self):
    t = catalog.today(catalog.load_rules(), [{"area": "knee", "side": "right", "phase": "protect"},
                                             {"area": "shoulder", "side": "left", "phase": "protect"}])
    self.assertIn("knee-deep-bend", t.avoid)
    self.assertIn("overhead", t.avoid)
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** `today` combines all injuries' bans, adds each injury's `extra_ban` (split into tags and ids), and for an unknown area adds a warning, `Warning: no rules for <area>; only its extra_ban applies. Judge by hand from the playbook's Unlisted injuries.`. The output follows the filter's contract in the Design.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** `git commit -m "movements reads the kit and injuries from me/"`

### Task 3.4: Skills, docs and the 4.0.0 release

**Files:**
- Modify: `.claude/skills/workout/SKILL.md`, `.claude/skills/setup/SKILL.md`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`, `docs/research/productization-research.md` (status line only)

- [ ] **Step 1: Workout skill.**
  - Step 0 adds `./sweatcast movements --injuries`. Its criteria fill the check-in's "Better, and [criteria]".
  - Step 1: an answer that changes a phase updates `phase` and `since` in health.md's `[[injuries]]` block as well as the prose. If `check` or the filter reports a prose-only injury, the check-in writes the block; that's the one moment health.md edits are allowed.
  - Step 2 runs `./sweatcast movements --kit "<kit>"` and picks only from its output, with the health file's rules applied on top.
  - The check-in's session types are those whose kinds appear in the kit's output (skills only when the kit has a skill movement), replacing the hard-coded "(stickhandling)".
  - Step 0 no longer reads the catalog or `kits.md` in full: `kits.md` only when the kit is a hotel or gym kit.
- [ ] **Step 2: Setup skill.** The equipment question writes `[[kits]]` (offering the presets). The health question writes `[[injuries]]` with the area, side, phase from `knowledge/injury-rules.toml` and its criteria. `./sweatcast check` runs until clean.
- [ ] **Step 3: CLAUDE.md and README.** Update the file lists (catalog, rules, programming, kits, `me/movements.toml`, the new command, the tests).
- [ ] **Step 4: Verify.** `./sweatcast test` passes. On a copy of `me.example/` (`SWEATCAST_HOME` set to a temporary folder), `./sweatcast check`, `./sweatcast movements --injuries` and `./sweatcast movements --kit Home` all succeed. `./sweatcast migrate --dry-run` on a schema 2 copy says what would change.
- [ ] **Step 5: Release 4.0.0.** The CHANGELOG's "For forks" section covers:
  - run `./sweatcast migrate` (schema 3; backs up first);
  - check the inferred `[[kits]]`;
  - if health.md lists an injury, the next workout's check-in writes its `[[injuries]]` block, or ask setup to;
  - private movements go in `me/movements.toml`.

  Ask before tagging and pushing.
