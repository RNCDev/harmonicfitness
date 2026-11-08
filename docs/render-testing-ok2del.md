# Render speed and thinking levels: a test plan (OK to delete once done)

Two timing questions left open after 0.69.0. Each part is measured on the maintainer's own keys, decided by a rule set before the runs, and shipped as a patch release only if it passes.

1. **Requests at once for Gemini's voice.** Gemini voices a web coach two requests at a time (`concurrency = 2` under `[gemini]` in `knowledge/services.toml`). A 10-minute workout makes about 80 requests and takes 150 to 165 s to record. Would 4, 8 or 16 cut that without hitting Gemini's rate limits?
2. **How hard each writer thinks.** The web app's writers' room runs at `LEVEL = {"research": "LOW", "trainer": "MEDIUM", "host": "MEDIUM", "review": "LOW"}` (`web/webapp/agent/writers.py:60`). In the 0.69.0 walk the host took 115 s in one run and 26 s in the next. In both runs the room's check failed twice on the script's total length before the review fixed it. Does a lower level hold quality and save time?

Nothing personal goes in this file or in any commit. Every run's folder goes under `.bench/`, which git ignores and the privacy hook refuses.

## Part 1: requests at once for Gemini

### What's measured

The same 30-minute script, recorded once at each setting of 2 (today's), 4, 8 and 16, each from an empty clip cache so every line is really sent:
- how long the recording took;
- how many requests Gemini answered with "slow down" (HTTP 429), and whether any build stopped on a used-up quota (exit 4);
- the MP3's length, which must match across runs (the setting changes speed, never the audio).

### The script

Mo, one of the demos' invented listeners (`docs/demos/listeners/mo/`, `docs/demos/demos.toml`): the 30-minute kettlebell strength workout in `workouts/2026-11-04-demo-mo/`. With **Coach Fraser** (Gemini's stand-in) it lints clean and sends 16,540 characters, about $0.24 a recording, so the whole part costs about $1. (Ben's, Jo's, Ravi's, Ines's and Frank's scripts run 2.5 to 5 percent short at Fraser's pace and won't build; Lena's lints too, at 21,027 characters.)

### Before the runs

1. **Make retries visible.** A 429 is retried silently today (`tools/cloud.py`, the retry loop in `request`), so a render that hits the limit only looks slow. Add one line to stderr each time a request waits on a rate limit, e.g. `(gemini asked to slow down: waiting 4 s)`, naming the service and the wait, never the text or the key. Add a test in `tests/test_cloud.py` beside the 429 tests (around lines 68, 878 and 894), and ship it with whatever Part 1 decides: it's worth having anyway.
2. **The key.** The build reads the Gemini key from the maintainer's own `me/.env` when `HARMONICFITNESS_KEYS` names it, as `demos run` does. Set the variable to that file's path. Never open, print or copy the file.
3. **The setting** is a local edit of `concurrency` under `[gemini]` in `knowledge/services.toml`, made before each run and undone with `git checkout knowledge/services.toml` at the end. It's never committed as part of the test.

### Each run

From the repository root, for N in 2, 4, 8, 16:

```sh
H=.bench/render/c$N
mkdir -p .bench/render && cp -R docs/demos/listeners/mo "$H"
rm -rf "${H:?}/workouts/.audio-cache" "${H:?}/workouts/.logs"
D="$H/workouts/2026-11-04-demo-mo/2026-11-04-demo-mo.draft.txt"
# today's menu beside the draft (the build refuses a menu from another day)
HARMONICFITNESS_HOME="$H" ./harmonicfitness brief --goal strength --minutes 30 --kit kettlebell --save "$D"
# set concurrency = N under [gemini] in knowledge/services.toml, then:
time HARMONICFITNESS_HOME="$H" HARMONICFITNESS_KEYS="<path to me/.env>" \
  ./harmonicfitness build "$D" "Render test c$N" --coach "Coach Fraser" 2> "$H/stderr.txt" | tee "$H/stdout.txt"
```

Record, for each run:
- the build's own "rendered X min of speech in Y min" line;
- the wall time from `time`;
- the exit code;
- how many "asked to slow down" lines `stderr.txt` holds;
- the MP3's length (it's left in the workout's folder, since Mo has no delivery folder).

Leave at least two minutes between runs, so one run's rate-limit window doesn't spill into the next. Run them in order, 2 first, and stop going higher once a run exits 4.

### Deciding

Set before the runs:
- **Pick the highest setting with:** exit 0, no more than a handful of "slow down" waits, and a recording at least 25 percent faster than the next setting down. Smaller gaps are noise, since request times swing. If 8 and 16 differ by less than that, take 8: it's gentler on the limit and nearly as fast.
- **Any exit 4 (quota) rules that setting out,** and anything above it.
- **The MP3s must match** within a second or two. If they don't, something other than speed changed: stop and find out why before changing anything.
- **This measures a paid key.** If the maintainer can make a free Gemini key, run 2 and the chosen setting on it too. If the chosen setting trips the free key's limit, don't ship a fixed number. Raise it with an adaptive limit instead: start at the chosen setting, halve the number of requests at once on each "slow down", and carry on rather than stop. That change goes in `tools/render.py`'s render loop (around line 388) and `tools/cloud.py`, with tests.

### Shipping

Change `concurrency` under `[gemini]` and the comment above it, saying how it was measured (as `[openrouter]`'s does). Then:
- update the pin in `tests/test_cloud.py` (`"gemini": (2, 0)`, around line 314);
- add the results to `knowledge/voices.md` beside Gemini's notes;
- run `./harmonicfitness test changed`;
- release a patch (0.69.x) as CLAUDE.md's Releases says.

## Part 2: thinking levels

### The bench

`web/bench/` (read its README first) runs the web app's script writing from the brief to the price, with no database and no recording, on the maintainer's own Gemini key, and summarizes each run:
- the seconds in each step and for each writer;
- the review's passes;
- must-say lines left out;
- story names nobody researched.

`--set LEVEL.<writer>=<LEVEL>` changes one writer's level for a batch. The first batch of the day copies `me/` to `.bench/base`, without the key file.

### The runs

Four settings, three 10-minute runs each (about $0.30 a run, $3.60 in all):

```sh
web/bench/batch.sh think-base  10 3
web/bench/batch.sh think-host  10 3 --set LEVEL.host=LOW
web/bench/batch.sh think-train 10 3 --set LEVEL.trainer=LOW
web/bench/batch.sh think-both  10 3 --set LEVEL.host=LOW --set LEVEL.trainer=LOW
.venv/bin/python web/bench/summarize.py think-base think-host think-train think-both
```

Run the batches one after another, not together: the bench README notes that Gemini's per-minute input cap was hit when fifteen runs started at once. Don't start near midnight.

For each run, also read the room's log lines the bench keeps (`room` in each run's result) (as of 0.69.0, a failed room check names its kind: "total too long", "total too short", "digits", ...). That's where the total-length failures show.

### What history says

- **The host at LOW** wrote scripts that ran long, with silences (`writers.py:59`, from the 0.58.0 bench).
- **The trainer at LOW** dropped the self-check that a limit adds (`writers.py:56`).
- **Since then,** the host's prompt changed in 0.59.0 and 0.69.0, so both may have moved.

Read the scripts, not just the times.

### Deciding

Set before the runs, as the bench README's rule:
- **A change is kept only if the median time to the price drops by at least 25 percent** (smaller is noise with Gemini's thinking times) **and quality holds in every run:**
  - priced;
  - every must-say line in;
  - the sides right;
  - no story fact outside its notes;
  - one voice start to finish;
  - no more review passes than the baseline;
  - the total within its limit after the room.
- **Any run of a setting that fails one of these rules the setting out**, however fast it is.
- **If none passes,** the levels stay. Note what each setting cost and what went wrong in the bench README's Results, so it isn't tried blind again.

### Shipping

Change `LEVEL` in `web/webapp/agent/writers.py`, with a comment giving the run's date, medians and what held. Then:
- add a dated section to the bench README's Results;
- run `./harmonicfitness test web`;
- release a patch as CLAUDE.md's Releases says.

## When both parts are done

- **Delete this file** in the release that ships the results.
- **Clear the run folders:** `.bench/render/` and `.bench/out/think-*`.
- **Record the outcome** in the CHANGELOG, and for anything decided against, in `knowledge/voices.md` (Part 1) or the bench README (Part 2).
