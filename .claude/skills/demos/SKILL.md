---
name: demos
description: Build, or re-make, the demo clips on the web app's home page (docs/demos/) - seven invented listeners, each a full workout written and linted, of which about two minutes are rendered on ElevenLabs and stored on the Fly bucket. Use when the maintainer says "build the demos", "make the demo clips", "re-make the demos", "redo the jo demo" or "update the home page demos". Never for a listener's own workout.
---

# Demos: the home page's clips

Seven invented listeners, each with one ask in their own words, built by the engine as any listener's workout is. The whole workout is written and linted, which costs nothing; only the two minutes the home page plays are rendered. `docs/demos/index.html` is the plan, `docs/demos/demos.toml` the seven, and `./harmonicfitness demos` the command (its `--help`).

Rules for the whole run:
- **Every command for a demo listener goes through `./harmonicfitness demos run <slug> <command> ...`.** It points the engine at the demo's own folder, `docs/demos/listeners/<slug>/`, and at the listener's own key file (`HARMONICFITNESS_KEYS`). Never read, print or copy `me/.env`, and never set either variable yourself.
- **Write only** in `docs/demos/` (and `web/client/src/demos.json`, through `demos web`); never in `me/`, which is the real listener's. Each demo listener's folder is `docs/demos/listeners/<slug>/`: its profile files, research, briefs, menus and drafts are committed with the plan; what the engine generates there (audio caches, logs, MP3s, build records, the installed coach) is git-ignored. The finished clips go to the Fly bucket (step 4).
- **No `log-session` and no `backup`** for a demo: its log stays empty, so a re-made demo never looks back on the last one. `content log` is fine.
- **One model:** `eleven_v4`, ElevenLabs's more natural one, never `eleven_v4_turbo`. `demos home` holds each coach to it.
- **Only the clip renders.** The full draft only ever runs with `--lint-only`.

## 1. Before anything is billed (one message)

Read `docs/demos/demos.toml` and run `./harmonicfitness demos` (how far each demo has got), `./harmonicfitness keys` (ElevenLabs must show set) and `./harmonicfitness balances`. Then tell the maintainer, in one message, what the run will spend: a 45-second sample a demo (about a cent each) and about ten thousand characters for the seven clips (about eighty cents on `eleven_v4`, at the rate in `knowledge/services.toml`). Go on only on a yes. Doing one demo ("redo the jo demo") skips straight to step 3 for it.

## 2. The three coaches: ElevenLabs stock voices

Each coach is one of ElevenLabs's own stock voices (Priya is Lily, Bea is Matilda, Desmond is Charlie), named by its voice ID in `docs/demos/coaches/<name>.md`. A stock voice has the same ID on every account and takes no voice slot, so nothing is designed. Designed voices were tried on 2026-11-04 and turned down by ear: tinny and breathy.

For each demo: `./harmonicfitness demos home <slug>` installs its coach from that file (held to `eleven_v4`), then `./harmonicfitness demos run <slug> coaches sample "<coach>"` speaks its 45-second sample, which also records the coach's pace in that demo's folder for the lint. To try another stock voice, have a few speak the same coaching line on `eleven_v4` and choose by ear: the voice that speaks a workout, not a design preview, is what to judge.

## 3. Each demo, in `order`

Follow the `workout` skill as that listener, with these differences:
- **The request is the demo's `ask`.** Ask no check-in: the answers are its `[demo.check_in]`.
- **Research** as the workout skill does it, for evergreen stories only. The format the clip names (`[demo.clip] story`) must be in the plan, for a topic of theirs.
- **Brief:** `./harmonicfitness demos run <slug> brief <its brief flags> --save docs/demos/listeners/<slug>/workouts/<stem>/<stem>.draft.txt`, the stem `<today>-demo-<slug>`.
- **Write the whole workout** to the brief and the workout skill's guides, with `writing_rules` from `demos.toml`. Arrange it so the segments `[demo.clip] segments` describes fall together, add up to about two minutes, and make sense heard alone. Under a one-sided limit (Jo, Frank), the clip starts at segment 1, the opening.
- **Lint the whole draft** until it's clean: `./harmonicfitness demos run <slug> build "<draft>" "Demo <slug>" --lint-only --coach "<coach>"`.
- **Cut the clip:** `./harmonicfitness demos excerpt "<draft>"` lists the segments, numbered. Then `./harmonicfitness demos excerpt "<draft>" --from <n> --to <m>` writes `<stem>-clip/<stem>-clip.draft.txt` with the menu beside it, and says if it runs outside ninety to a hundred and fifty seconds.
- **Lint the clip, then build it:** `./harmonicfitness demos run <slug> build "<clip draft>" "Demo <slug> v<version>" --coach "<coach>"`, first with `--lint-only`. The lint warns that the clip repeats sentences from its own full draft: expected, so pass over those. The build prints the cost before it sends anything.
- **Listen together.** Send the clip's MP3 (its `.build.json` says where it is). If it falls flat, rewrite those segments in the full draft, lint, cut and build again: only changed paragraphs are billed again.
- **Stage it:** `./harmonicfitness demos publish <slug> "<clip MP3>"` copies it to `docs/demos/clips/<slug>.mp3` (git-ignored).
- **Record it** in `demos.toml`: `from` and `to`, `moments` (two or three times inside the clip, with labels, by listening) and `changed` (one line from the brief's limits, or empty).

## 4. Close

`./harmonicfitness demos upload` sends every staged clip to the bucket named in `demos.toml` (`bucket`) as `demos/v<version>/<slug>.mp3`, publicly readable, with `demos.json` (each demo's ask, coach, card and clip address) beside them. It needs the bucket's keys in the shell (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `BUCKET_NAME`: the app's Fly secrets, from Tigris's dashboard), never printed or written to a file in the repo. Fill in `built` (today) and `engine` (`VERSION`) in `demos.toml`; when re-making the set, raise `version` first. Then `./harmonicfitness demos web` writes `web/client/src/demos.json`, the sign-in page's copy (each demo's request, card and clip address), and refuses a `[demo.request]` the app couldn't write: its `type` from the app's list of workouts, its `place` in the app's words for one of the listener's kits ("at home" for a kit named home, "with my <kit> kit" otherwise, or a preset's words), its `when` "right now" or a time, and its `care` none, easy or off with a body chart area. `./harmonicfitness demos` shows every demo published.
