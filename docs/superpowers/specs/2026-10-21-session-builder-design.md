# Session builder: atomic exercise data, and a tool that composes a session from it

Date: 2026-10-21. Status: approved for planning once the listener signs off. Supersedes the plan in `docs/superpowers/plans/2026-10-21-programming-knowledge.md` from its Phase 2 onward.

## Intent

Today the engine knows exercises (the movement catalog) but the rules for turning a request into a session live in prose (`knowledge/programming.md`, `knowledge/injury-playbook.md`, the skill's own text) and in a hand-written ban table per injury area and phase (`knowledge/injury-rules.toml`). The agent reads all of it and reasons its way to a plan each time. That is slow to construct, hard to test, and the ban table encodes by hand what the exercises themselves should say.

The new shape is a small set of structured building blocks the engine owns, two thin layers of data about the person and the session, and one tool that composes them into a session skeleton. The agent writes the narration from the skeleton. The blocks can be researched and expanded one at a time without touching the composer.

Building blocks (engine, public):

1. **Exercises**, each with enough metadata that a tool can budget its time, judge what it loads, and place it in a session.
2. **Equipment**, with named kits. Exercises point at equipment, so "what can I do on this" is a query.
3. **Session structures**: the methods a coach picks from (straight sets, circuits, intervals, mobility flow), each as blocks with timing rules.
4. **Dose rules**: sets, reps or work time, and rest, by goal and experience level.

Layers (private, in `me/`):

5. **Person**: experience level, kits, likes and dislikes, joint tolerances.
6. **Session**: the request. Goal, time, equipment on hand, injuries today, method if the listener has a view.
7. **History**: the log as it is. Progress tracking is v2 (see the end).

## Goals, non-goals, anti-goals

Goals:
- A request like "thirty minutes, hotel room, knee is sore" becomes a skeleton with structure, timing and ranked candidates per slot, in one command, with a reason beside every choice.
- Safety falls out of exercise metadata and the person's joint tolerances, not out of a ban list.
- The blocks are small enough to read in one sitting, and each can grow on its own: more exercises, finer load ratings, another method.
- Forty text sessions across a fixed grid of requests can be generated and judged, and judged again after every change.

Non-goals (this version):
- Progress tracking across weeks. Fields are reserved; no logic.
- Rendering the forty judged sessions to audio. Text only.
- Rehab programming by phase. Clinician rules in `me/health.md` are followed literally, as now.
- A full 176-exercise annotation. Start with the exercises needed to cover every pattern on every kit.

Anti-goals (what would make this a failure):
- A session that uses an exercise the listener's joint tolerances exclude. Safety is the first judge criterion.
- A second timing model. The skeleton speaks the draft's own units (`@@ <seconds> | title`) so the lint and render stay as they are.
- Prose the agent must interpret to be safe. Anything safety-bearing is a field.

## Constraints

- Python 3.11 standard library only; every tool runs through `./sweatcast`; exit codes from `tools/cli.py`.
- The engine is public. No personal details in engine files, tests, fixtures, examples or commit messages. Examples use invented joints and invented likes.
- Spoken fields (setup, cues) follow `knowledge/tts-rules.md`: no digits, symbols or brackets.
- The context folder is private and versioned by `schema`; a format change bumps it, adds a migrate step, and is a major release.
- Research cites only sources actually opened. What the sources say is kept apart from what was decided.

## The building blocks

### 1. Exercises: `knowledge/movements.toml`, format 2

Every existing entry stays (the log and `./sweatcast coverage` resolve logged names against it). Each gains these fields. An entry the builder may use is fully annotated; one that is not yet carries `draft = true`, which exempts it from selection and from every new field except `patterns`, which every entry must carry so that coverage over the listener's real history stays right. The first release annotates enough entries to cover every pattern on every kit at every experience level, about sixty, and the rest are `draft = true` until someone annotates them.

New fields per movement:

| Field | Meaning | Example |
|---|---|---|
| `patterns` | movement patterns trained, first is primary; from the fixed list | `["squat"]` |
| `muscles` | primary then secondary, from the fixed list | `["quads", "glutes", "core"]` |
| `loads` | load on each area in the fixed list, 0 none, 1 low, 2 moderate, 3 high; an area left out is 0; for a `sided` entry this rates the working side | `{ knee = 3, ankle = 2, hip = 2, low-back = 1 }` |
| `support` | for a `sided` entry only: the load on the other side (the back leg of a split squat, the planted arm of a one-arm row), same scale, default all 0 | `{ knee = 1, ankle = 1 }` |
| `flags` | qualities a tolerance or a request may exclude, from the fixed list | `["impact", "single-leg"]` |
| `intensity` | what it is for: `strength`, `conditioning`, `mobility`, `skill`, `breathing` | `"strength"` |
| `level` | least experience it suits: `novice`, `experienced`, `advanced` | `"novice"` |
| `seconds_per_rep` | atomic length for `measure = "reps"` | `3` |
| `hold_seconds` | atomic length for `measure = "time"`; the default hold | `30` |
| `transition_seconds` | time to get set and to leave it, spoken setup included | `15` |

Fixed lists, at the top of the file as now:

- `patterns = ["squat", "hinge", "lunge", "horizontal-push", "vertical-push", "horizontal-pull", "vertical-pull", "carry", "rotation", "anti-rotation", "anti-extension", "locomotion", "balance", "mobility", "breathing", "skill"]`. The research draft confirms or amends this list before it is final.
- `muscles`: quads, hamstrings, glutes, adductors, abductors, calves, chest, back, lats, shoulders, biceps, triceps, forearms, core, neck.
- `areas = ["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "low-back", "rib", "shoulder", "elbow", "wrist", "neck"]`. Joints and the soft tissues that get strained on their own; `loads` and `[[limits]]` both key on this list.
- `flags`: impact, single-leg, kneeling, floor, lying-side, hanging, overhead, spine-flexion, spine-twist, lateral, fast, grip. These replace the 23 tags. A tag that rated load (knee-deep-bend, spine-load) becomes a number in `loads`; a tag that named a position or quality becomes a flag.

Fields removed: `groups` and `tags` (replaced; `patterns` is required on every entry, draft or not), `kind` (replaced by `intensity`; the `rehab` and `finisher` kinds become `intensity` plus a `rehab = true` field so rehab moves are only offered when health names them).

Kept as they are: `id`, `name`, `aliases`, `needs`, `position`, `sided`, `measure`, `setup`, `cues`, `easier`, `harder`.

`tools/catalog.py` keeps its loader, `resolve`, and the problems check, extended to the new fields: unknown pattern, muscle, joint, flag, level; a non-draft entry missing a required field; `easier` and `harder` pointing at a draft entry are allowed. Private entries in `me/movements.toml` follow the same format; a private entry missing the new fields is loaded as `draft = true` and the check says so.

### 2. Equipment and kits

The `[equipment]` table stays, and so do the presets. `needs` keeps its `"a|b"` alternatives, which is enough substitution for now; a separate substitutes table is not built.

The person's own kits move from prose to the profile's front matter (section 5). A request names a preset, a kit, or a list of equipment.

### 3. Session structures: `knowledge/sessions.toml`

One file, format 1, holding the methods and the dose rules. Each `[methods.X]` entry has:

| Field | Meaning |
|---|---|
| `about` | one line, spoken-safe, so the plan can name it |
| `goals` | goals it suits, in order of fit |
| `minutes` | `[least, most]` session lengths it suits |
| `levels` | experience levels it suits |
| `warmup` | fraction of the session, with `[least_seconds, most_seconds]` |
| `cooldown` | the same |
| `blocks` | ordered list of block shapes, each `{ kind, patterns_or_intensity, share }` where `share` is the fraction of the main time |
| `work` | how a block runs: `sets`, `rounds`, or `intervals`, with `work_seconds` and `rest_seconds` ranges where fixed by the method (intervals), otherwise taken from the dose rules |

The methods for the first release: straight sets, paired sets (supersets of non-competing patterns), circuit, intervals (with named presets: tabata at twenty on and ten off, and bike intervals), flow (mobility and breathing), and skill (drill rounds, then supporting strength, for the stick-and-ball work the catalog already has). A strength, general or targeted method whose session is twenty-five minutes or longer ends its main time with a short finisher block before the cool-down; the ten-minute snack is simply a circuit at ten to twelve minutes with no finisher. The skill's current format rotation (rolling minutes, forty-five on and fifteen off, long steady segments) lives inside the methods as `work` shapes, and the session's chosen method is what the log's `format:` records. The warm-up and cool-down fractions and their floors and ceilings come from the research draft where it found a source, otherwise from `knowledge/programming.md`'s existing templates, and the file says which.

What the research confirmed, and what is house policy. A research pass on session structure opened nine sources (notes committed at `docs/research/2026-10-21-session-structure-notes.md`; the builder copies the sources it uses into `sessions.toml` comments). Confirmed, and encoded as rules: block order is power or plyometric work first, right after the warm-up and only when the listener is ready for it, then multi-joint, then single-joint (NSCA guidance as summarised by the DoD's Human Performance Resources page; ACE IFT phases 3 and 4); a strength or general session holds four to six resistance exercises with push and pull roughly equal (the same HPRC page); advancement is gated by readiness and pain, not the calendar (NASM OPT; Cook and colleagues on the Functional Movement Screen, PMC4060319); shallower squat range lowers knee load (Escamilla 2001, PMID 11194098), which is why a delicate knee keeps `loads.knee = 3` entries out and offers `easier` ones; circuit resistance training improves strength and cardiorespiratory fitness together (Ramos-Campo 2022, PMID 34627129); interval sessions are defined by work intensity and length, rest, and series count (Buchheit and Laursen 2013, PMID 23539308). Not confirmed, so house defaults carried over from `programming.md`'s template table and marked as such in the file: warm-up and cool-down lengths by session length, the work-to-rest shapes for tabata and circuits, the mobility method's dose, and per-rep timing. The pattern list above is a house taxonomy; no professional body's list was confirmed, and the two published lists found differ from each other.

Method selection is a rule in the same file: for a goal, time and level, the methods whose `goals` include the goal, whose `minutes` span the time and whose `levels` include the level, in file order; the first one that is not the last session's `format:` wins, so two sessions in a row differ when more than one method fits. The request can name a method and skip the rule.

Slots. A block's `patterns_or_intensity` names the patterns it wants, in priority order, and the tool takes as many as the main time allows under the dose rules, in that order: for strength, general and targeted sessions the order is squat, hinge, horizontal-push, horizontal-pull, lunge or balance, vertical-push, vertical-pull, then one of anti-extension, anti-rotation or carry. Twenty minutes fits about four slots, thirty about five, forty-five about six, which is the four-to-six exercises the research confirmed, with push and pull kept equal by that order. A targeted session puts its `--target` patterns or muscles first and keeps one push, one pull and one hinge or squat as a floor. Last session's left-out patterns and the week's neglected ones are ranking signals, not forced slots; the skill's nine-group checklist is retired.

Goals are a fixed list: `strength`, `general`, `targeted`, `conditioning`, `mobility`, `skill`.

### 4. Dose rules: in `knowledge/sessions.toml`

`[dose.<intensity>.<level>]`, keyed by the exercise intensity the block runs at, not the goal: `strength` has `sets`, `reps`, `rest_seconds` and `hard_sets_per_session` ranges; `conditioning` has `work_seconds`, `rest_seconds` and `rounds`; `mobility` has `hold_seconds` and `rounds`; `skill` has `drill_seconds` and `rounds`. Strength, general and targeted goals run their main blocks at strength intensity. The numbers come from `knowledge/programming.md`'s cited sections (effort, load range, rest and pairing, tempo), which stays as the rationale. Its session-template table is replaced by a pointer to `sessions.toml`.

### Tool: `./sweatcast session`

`tools/session.py`. Input: `--goal`, `--minutes`, and one of `--preset`, `--kit <name>` or `--equipment a,b`; optional `--method`, `--level` (overrides the profile), `--target <pattern or muscle>` (for the targeted goal), `--limit <area>=<off-limits|delicate>` (today's injuries, added to the health file's), `--avoid <ids or flags>`, `--home` as other tools. Output, in order:

1. The method chosen and why, in one line.
2. The skeleton: warm-up, each block, cool-down, with planned seconds each, totalling the request within the draft's tolerance. Each block lists its slots.
3. Per slot: the pattern it fills, the dose, and the top three candidates with one reason each ("neglected this week", "liked", "healthy side only", "lighter: knee delicate"). The agent picks one; the first is the default.
4. "Would open up": for a preset or kit, up to three pieces of equipment not on hand, with how many excluded candidates each would admit. This is what the check-in asks about.
5. `--draft` prints the skeleton as `@@ <seconds> | <title>` lines with the chosen defaults named, ready to write under. One segment for the warm-up, one per slot (all its sets and rests) for straight and paired sets, one per round for circuits and skill, one per work-and-rest pair for intervals, one per hold group for flow, one for the finisher and one for the cool-down.

Selection, in order:
1. Exclude draft entries, entries needing equipment not on hand, entries above the level, entries the person dislikes, and entries `--avoid` names.
2. Apply tolerances. A joint that is off limits excludes every entry with `loads.<joint> >= 1`, and every flag the health entry names. A delicate joint excludes `loads.<joint> >= 2`, the `impact` and `fast` flags, and whatever flags the health entry names. A sided limit on a `sided` entry keeps it as "healthy side only" when the entry's `support` load on that area is under the same threshold, and excludes it otherwise; on an unsided entry with load on that area, the entry is out. Rehab entries are offered only when the health entry names them.
3. Fill slots from the structure. Rank candidates per slot: pattern match, then not used in the last session, then its pattern neglected in the last seven days (from the log through `tools/coverage.py`), then liked, then lower total joint load when any tolerance is set. Ties keep catalog order.
4. Time each slot from the dose and the atomic lengths: reps times seconds per rep plus transition, times sets, plus rest between sets; for intervals, the method's work and rest. Scale the dose down from the top of its range until the blocks fit the main time; if the floor does not fit, drop the last slot and say so. Seconds left over go first to the rests between slots, up to thirty seconds each, then to the cool-down.

The tool never widens a rule. Anything the health file bans in prose (clinician rules) the agent still applies when it picks; the tool prints each limit's `note` and every line under the health file's `## Clinician rules` heading above the skeleton so they are in view. The template gains that heading.

`tools/movements.py` stays as the plain filter (`--preset`, `--equipment`, `--avoid`), grouped by primary pattern instead of group. `tools/coverage.py` reports by pattern instead of group, with the same seven-day window and the same "left out" and "neglected" lists.

## The layers

### 5. Person: context schema 3

`me/profile.md` front matter gains:

```toml
experience = "experienced"      # novice, experienced or advanced
likes = ["goblet-squat"]        # movement ids the listener enjoys; ranked up
dislikes = ["burpee"]           # never offered

[[kits]]
name = "garage"
equipment = ["dumbbells", "band", "mat"]
```

`me/health.md` front matter gains:

```toml
[[limits]]
area = "knee"                   # from the catalog's area list
side = "left"                   # left, right or both
level = "delicate"              # off-limits or delicate
flags = ["kneeling"]            # extra flags to exclude, optional
rehab = ["terminal-knee-extension"]   # rehab entries to offer, optional
note = "Physio says no deep bend under load until pain-free on stairs."
```

The prose below the block keeps the clinician's words and the dated history, as now. The check-in asks about each limit: still off limits, now delicate, or clear. The guidance on when to loosen a limit lives in `knowledge/injury-playbook.md`, rewritten short: red flags that stop a session, and one section per joint with the signs that a joint can move from off limits to delicate to clear, carrying over the sources the current playbook already verified. The phase-by-phase ban lists and `knowledge/injury-rules.toml` are deleted.

`tools/context.py` raises `SCHEMA` to 3, reads the new settings, and `./sweatcast check` flags an empty `experience` as a hint to fill. Experience is a profile setting; `--level` on the request overrides it for one session. `tools/migrate.py` step 2 to 3: adds `experience = ""`, empty `likes`, `dislikes`, and `[[kits]]` from nothing (the setup skill asks); adds an empty `limits` list and leaves the prose injuries untouched with a note at the top of the block that each needs a `[[limits]]` entry. Migration never invents a tolerance.

### 6. Session: the request

The workout skill's Step 2 becomes: read the check-in's answers into `./sweatcast session` flags, run it, show the skeleton, pick per slot, then write. The skill's prose about picking movements by group and reading the injury rules goes. The setup skill asks for experience level and kits, and walks each injury into a `[[limits]]` entry.

### 7. History, and what v2 adds

The log keeps `format:` and `loads:`. v2 reserves `rpe:` (a number per movement, as spoken by the listener at check-in) and would compute next session's load from `loads:` and `rpe:` against the dose rules. Nothing is built for it now; `./sweatcast log-session` accepts `rpe:` and stores it, so logs written in v1 are usable by v2.

## Disposition of what exists

| Artifact | Disposition |
|---|---|
| `knowledge/movements.toml` | kept; format 2 with the fields above; `groups`, `tags`, `kind` removed |
| the 23 tags | replaced by `loads` and `flags` |
| `knowledge/injury-rules.toml` | deleted |
| `knowledge/injury-playbook.md` | rewritten short: red flags and per-joint loosening signs, sources carried over |
| `knowledge/programming.md` | kept as the cited rationale; its template table replaced by a pointer to `sessions.toml` |
| `knowledge/kits.md` | kept |
| `knowledge/exercise-science.md` | kept, unchanged |
| `knowledge/sessions.toml` | new |
| `tools/catalog.py` | format 2 loader and checks; `select`, `load_rules`, `rule_problems` removed |
| `tools/movements.py` | kept, grouped by pattern |
| `tools/coverage.py` | by pattern instead of group |
| `tools/session.py` | new |
| `tools/context.py`, `tools/migrate.py` | schema 3 and its migration |
| `tests/test_catalog.py`, `tests/fixtures/movements.toml` | rewritten against format 2, not patched; the injury-rules tests go |
| `.claude/skills/workout`, `.claude/skills/setup` | Step 2 and the injury steps rewritten as above |
| `me.example/` | schema 3 with invented examples |
| commits after v3.1.0 on main (programming.md, injury rules) | programming.md ships in the new release; the injury rules never ship. 3.2.0 is not released. |

Release: 4.0.0, with a "For forks" section: run `./sweatcast migrate`, then `./sweatcast check` lists what to fill in. 3.2.0 is not released (decided). The release waits for the forty judged sessions below: generate, score, fix what the scores show, then tag (decided).

## Judging the harness

`docs/eval/cases.toml` lists the cases; `docs/eval/judge.md` is the reviewer prompt. Neither is product code. A case is the flags for `./sweatcast session` plus a one-line invented listener (level, kit, likes, limits). The grid: goals strength, conditioning, general; levels novice, experienced, advanced; kits bodyweight, hotel-room, hotel-gym, full-gym; lengths twenty and forty-five minutes. The full grid is seventy-two cases. The sample: for each goal and level pair (nine cells), two kits chosen so that every kit appears in at least four cells, both lengths, giving thirty-six; plus four cases for mobility and targeted goals. Every third case carries one invented limit. Forty cases, fixed in the file.

Each case names a stand-in listener, one of four invented context folders under `docs/eval/listeners/`, passed to the tool with `--home`. For each case the skeleton is generated with the tool and a text script written by the workout skill from it. A separate reviewing agent scores both on, in order: safety against the case's limits, efficacy for the goal, likely adherence, and ease of construction (how much the writer had to invent beyond the skeleton). Scores go in `docs/eval/results-<date>.md` so releases can be compared. The first run gates 4.0.0.

## Left to the builder

- Exact warm-up and cool-down fractions and the dose numbers, taken from the research draft and `programming.md` and recorded in `sessions.toml` with their source.
- Which sixty exercises are annotated first, chosen to cover every pattern on every kit at every level.
- The reason strings and the output layout, within the order above.
- Test design, following the existing test files' style.

## Calls I made

- All 176 entries stay, with `draft = true` on the unannotated, so the log keeps resolving.
- Tolerances per area replace injury phases. Clinician prose still wins.
- `support` loads on sided entries, so "healthy side only" is checked, not assumed.
- `patterns` on every entry, drafts included, so coverage over real history is right.
- Method choice rotates away from the last session's format; finisher, snack, bike intervals and skills live inside the methods.
- Dose is keyed by intensity, not goal.
- Soft-tissue areas (calf, hamstring, groin, foot, rib) join the joints in one area list.
- Method selection is a lookup, not a score.
- The judge stays in docs.
- 3.2.0 is skipped.
