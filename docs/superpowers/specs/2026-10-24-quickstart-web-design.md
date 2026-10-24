# sweatcast 9.1.0: quick start, Coach Demo, Claude on the web, a folder per workout

Decided with the listener-developer on 2026-10-24, after a review of 9.0.0 from a stranger's side.

## Why

9.0.0 runs on any computer with Claude Code, but a stranger's first workout is far away: a long interview,
feeds, and a coach to design (a 4.5 GB download on a Mac, a paid key, or a clip they bring) before the
smoke test. Claude Code on the web is refused outright, though cloud voices no longer need a graphics
card. And `me/workouts/` has become a pile: drafts in one folder, scripts, build records, test builds and
stray files in another.

## Decisions

1. **Coach Demo ships** in `me.example/personas/coach-demo/`: Coach Julius's clip (the one sweatcast 8
   shipped publicly, a designed voice, byte for byte from `tools/migrate-assets/v8-voices/Chatterbox Coach.wav`),
   with its measured pace for Chatterbox Turbo (MLX and PyTorch) and Fish Audio, so a new listener renders
   without the smoke test. It is marked `placeholder = true`: `./sweatcast check` says so in a note, and a
   build with no coach named prefers any other coach. A listener's own coach replaces it in use, not on disk.
2. **Quick-start setup** is the default: one round of questions (name, experience, kit, injuries), the
   audio route only when local voices don't run here, Coach Demo, a ten-minute first workout. The rest
   (interests, taste, feeds, YouTube, delivery folder, their own coach) is "finish setting me up". The
   profile says `setup = "quick"` until then, and `./sweatcast check` reports the template lines still
   unfilled as notes, not issues.
3. **A one-question coach**: pick one of three named sketches (or describe one), one take, keep it. On a
   cloud designer it takes seconds; locally it is the 4.5 GB designer the first time.
4. **Claude Code on the web runs, with cloud voices only.** No local engine, models or local design there.
   The key is an environment variable in the cloud environment's settings (the tools already read the
   environment first). The voice service's host goes on the environment's network allowlist; doctor names
   the hosts. The context folder is the listener's private `sweatcast-me` repo attached to the session (found
   beside the engine, or named by `SWEATCAST_HOME`); without one, setup explains that this is a one-time
   session with Coach Demo and nothing is kept.
5. **Getting the MP3 on the web, both ways**: a speech-bitrate copy (mono, 48 kbps, split into parts of at
   most 14 MB, about 38 minutes each) with a player page the workout skill publishes as a private artifact;
   and the same parts committed to the private repo by `./sweatcast backup`. Locally, nothing changes unless
   `--web` is passed.
6. **A folder per workout** (`me/workouts/<stem>/`: draft, brief, menu, script, build record, and the MP3
   until delivered); test builds and smoke tests in `me/workouts/checks/`; the day's research and feeds in
   `research/daily/`. A layout change, so schema 5 (released as a minor version at the developer's call); `./sweatcast migrate` moves the old
   files.
7. **Small fixes**: the build record says where the MP3 was delivered (or why not); the README says where
   sweatcast runs and where it doesn't; the GitHub description drops "with a local voice"; backup's public-repo
   check works without `gh` (GitHub's unauthenticated API answers for public repos).

## Out of scope

Network secrets (the proxy adds the key header, so the tools would send with no key): later. Removing
`tools/migrate-assets/v8-voices/` stays planned for 10.0.0; this release keeps it, since the 3 to 4 migration still
needs it.
