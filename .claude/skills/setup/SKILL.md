---
name: setup
description: Set up sweatcast for a new listener, or update their context. Use when someone asks to "set me up", get started, onboard, or change their profile, injuries, feeds, voice or delivery folder, and whenever a workout is requested but me/profile.md doesn't exist yet.
---

# Setup: a new listener's context

Goal: in one short conversation, turn `me.example/` into a filled-in `me/` folder, check the machine, and end with a short first workout as an end-to-end test. Everything personal goes in `me/` (git-ignored); never edit the engine (tools, skills, `knowledge/`, `voices/`) for one listener.

## Step 1: the machine

Run `./sweatcast setup --no-models`. It makes the Python environment with uv, copies `me.example/` to `me/` if there's no `me/profile.md` yet (or brings an existing one up to this version's format, backing it up first), and installs the git hook that refuses to push `me/` in any commit. The voice model comes later, once the user has picked a voice, so nothing large downloads for a voice they won't use. If it stops, relay its one-line fix (install ffmpeg or uv with Homebrew) and rerun it once they say it's done. It runs in the background while you interview: start it with `run_in_background: true`.

If `me/profile.md` already has real answers, this is an update: ask only about what the user wants to change, and skip to Step 3.

## Step 2: the interview (AskUserQuestion, at most three rounds of up to four questions)

Read `me.example/profile.md` and `me.example/health.md` first, so the questions match the files. Ask in this order, offering sensible options and leaving the rest to Other:

1. **Basics.** Name or nickname (optional), neighborhood and city (only for local news and weather), training background, current goals.
2. **Equipment kits.** What's at home, and when travelling or at a gym. Each kit becomes one line under Equipment kits; the first is the default.
3. **Health.** Any current injuries or limitations, what a clinician said about them, and how it feels today. Say plainly, once: sweatcast isn't medical advice, a clinician's instructions override everything, and red flags (can't bear weight, rapidly increasing swelling, numbness, giving way, getting worse after a week or two) mean seeing a clinician before training. Write each injury in `me/health.md` in the format its comment shows, with its phase from `knowledge/injury-playbook.md` and the criteria for the next phase. No injuries: leave "None right now."
4. **Interests.** Teams, topics, YouTube channels for deep dives, puzzles, books, local news, and anything never to bring up.
5. **Voice.** Each shipped voice is named for the model that speaks it: Chatterbox Coach (Chatterbox Turbo; warm, the most natural delivery; a 3.3 GB download, renders at about 0.7 times real time) and Qwen3 Coach (Qwen3-TTS; a crisp class instructor, the clearest diction; a 4.2 GB download, about 1.3 to 1.45 times real time). The models are used as published; the voice comes from a ten-second reference clip each model copies. Suggest the user plays the clips (`afplay "voices/Chatterbox Coach.wav"`, `afplay "voices/Qwen3 Coach.wav"`). Both are men; offer a designed voice too, such as a woman, an older or younger coach, or another accent. It's made from a description (see "Design a voice" in `knowledge/voices.md`), and the design model is a 4.5 GB download of its own. If they want one (the design model downloads on first use; the voice's own engine downloads in Step 4):
   - `./sweatcast voices design "<name>" "<description>"` with `run_in_background: true`. It renders two takes into `me/voices/.takes/`. Send the takes with SendUserFile if it's available (otherwise give their paths and `afplay` commands), and ask which sounds right.
   - `./sweatcast voices keep "<take path>" --engine chatterbox --default` makes the chosen take a private voice in `me/voices/` and lists it first in the profile. Use `--engine qwen3` for the clearest diction.
   - Not right yet: reword the description (see what worked and what didn't in `knowledge/voices.md`) or pass another `--seed`, and design again.
   A recording of a real person goes in `me/voices/` too, and only with their consent: save the clip and its words, then `keep` it.
6. **Delivery.** Where finished MP3s should go: a folder that syncs to their phone (iCloud Drive is `~/Library/Mobile Documents/com~apple~CloudDocs/<folder>`, Google Drive for desktop is `~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>`, Dropbox is `~/Library/CloudStorage/Dropbox/<folder>`), or nowhere, keeping them only in `me/workouts/`. Check the folder exists with `ls`, and offer to create the subfolder.

## Step 3: write the files

- `me/profile.md` and `me/health.md`: fill in every bracketed placeholder from the answers, and delete lines the user has nothing for. Keep the `+++` block at the top of each file. In `me/profile.md` that block is TOML and holds every setting the tools read: `deliver_to`, `words_per_minute`, `youtube_favorites` and `puzzles` (@handles without the @), one `[[voices]]` table per voice (`name`, `description`; the first is the default), and one `[[feeds]]` table per feed (`label`, `kind`, `value`). Edit those values in place; the prose below the block is for Claude only. Writing `me/health.md` asks the user for permission; that's expected, since it's the most private file.
- **Feeds.** Weather: the neighborhood's latitude and longitude, rounded to two decimals. Teams: find each team's ESPN path (the `sport/league/team` part of its ESPN team page URL, such as `hockey/nhl/nj` or `soccer/usa.1/10739`) with a web search. Local news: one or two outlets' RSS feeds for the city. Keep the shipped science and puzzle feeds unless the user doesn't want them. YouTube handles: check each one resolves (`https://www.youtube.com/@<handle>`).
- Then run `./sweatcast check`. It lists every line still showing the template's `[hint]`, any feed not filled in, and anything the tools can't read, with line numbers; fix or delete each until it passes (its notes, such as no delivery folder, are fine). Run `./sweatcast feeds` once, fix or remove any source it lists under "Couldn't fetch", and run it again.

## Step 4: first audio

1. Download the chosen voice's model: say its size first (above), then run `./sweatcast setup` with `run_in_background: true`. It skips everything already done and fetches the default voice's model at its pinned revision, from Hugging Face with no account needed (its "unauthenticated requests" warning is harmless). On a slow connection this takes a while; finish Step 3's feeds while it runs.
2. Once it has finished, render the smoke test with the chosen voice: `./sweatcast build voices/smoke-test.draft.txt "smoke-test" --voice "<voice>"`. It measures the voice's pace, which session builds require. Send `me/workouts/smoke-test.mp3` with SendUserFile if it's available, and ask how it sounds.
3. Offer a ten-minute first session (the `workout` skill, strength at ten minutes) as the end-to-end check, including the copy to the delivery folder.

## Step 5: keep it safe

- Suggest backing up `me/` as its own private git repo: `git init` inside `me/`, commit, and push to a private remote. The engine's git ignores `me/`, so the two never mix, and the pre-push hook blocks `me/` from the public repo.
- Summarize what was written, in a few lines, and where to change it later ("ask me to update your profile").
