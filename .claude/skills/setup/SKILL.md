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

1. **Basics.** Name or nickname (optional), neighborhood and city (only for local news and weather), current goals, and **experience level**, three choices in the listener's own words: novice (new to training, or back after a long break; simple movements, lighter loads), experienced (trains regularly and knows the common lifts), advanced (trains hard and wants harder variations). It becomes `experience` in the profile's settings.
2. **Equipment kits.** What's at home, and when travelling or at a gym. Each kit becomes one `[[kits]]` row in the profile's settings: a `name` and the `equipment` ids it holds, from the catalog's equipment list (the `equipment` list near the top of `knowledge/movements.toml`; the `[presets.*]` tables in that file are kit presets to start from). The first kit is the default. Also copy each kit into the prose under Equipment kits.
3. **Likes and dislikes.** Movements they enjoy or want left out. Resolve each name against the catalog (`./sweatcast movements --equipment <ids>` prints movement names, which the catalog resolves to ids) and put the ids in `likes` and `dislikes`; a name the catalog doesn't know goes in the profile's prose, not in the list.
4. **Health.** Any current injuries or limitations, what a clinician said about them, and how it feels today. Say plainly, once: sweatcast isn't medical advice, a clinician's instructions override everything, and red flags (can't bear weight, rapidly increasing swelling, numbness, giving way, getting worse after a week or two) mean seeing a clinician before training. Walk each injury into one `[[limits]]` row in the settings block of `me/health.md` (the template, `me.example/health.md`, shows one):
   - `area`, from the catalog's list of thirteen: foot, ankle, calf, knee, hamstring, hip, groin, low-back, rib, shoulder, elbow, wrist, neck. Spell it as written here, with the hyphen in low-back.
   - `side`: left, right or both.
   - `level`: off-limits means nothing that loads the area at all; delicate means nothing that loads it hard, no impact and no fast work. Offer both in those words and let the clinician's words decide; when unsure, off-limits.
   - `note`: the clinician's words, short. Put them word for word under `## Clinician rules` too; each is followed literally. An injury in none of the thirteen areas gets no row: write it in the prose list as "- Unlisted: <what>", and put any movement ids or flags to avoid for it under `## Clinician rules` as a line "Avoid: <ids or flags>" (ids from the catalog, flags from its `flags` list), which the workout passes to the session tool as `--avoid`. The playbook's "Unlisted injuries" says what to do.
   - `rehab` and `flags` stay empty unless the clinician named a rehab movement or something else to avoid; `flags` values come from the catalog's fixed `flags` list.
   Add the injury and its programming to the prose list under Active injuries too (an unlisted one as "- Unlisted: <what>", as above). No injuries: leave "None right now." and no rows.
5. **Interests.** Teams, topics, YouTube channels for deep dives, puzzles, books, local news, and anything never to bring up.
6. **Voice.** Each shipped voice is named for the model that speaks it: Chatterbox Coach (Chatterbox Turbo; warm, the most natural delivery; a 3.3 GB download, renders at about 0.7 times real time) and Qwen3 Coach (Qwen3-TTS; a crisp class instructor, the clearest diction; a 4.2 GB download, about 1.3 to 1.45 times real time). The models are used as published; the voice comes from a ten-second reference clip each model copies. Suggest the user plays the clips (`afplay "voices/Chatterbox Coach.wav"`, `afplay "voices/Qwen3 Coach.wav"`). Both are men; offer a designed voice too, such as a woman, an older or younger coach, or another accent. It's made from a description (see "Design a voice" in `knowledge/voices.md`), and the design model is a 4.5 GB download of its own. If they want one (the design model downloads on first use; the voice's own engine downloads in Step 4):
   - `./sweatcast voices design "<name>" "<description>"` with `run_in_background: true`. It renders two takes into `me/voices/.takes/`. Send the takes with SendUserFile if it's available (otherwise give their paths and `afplay` commands), and ask which sounds right.
   - `./sweatcast voices keep "<take path>" --engine chatterbox --default` makes the chosen take a private voice in `me/voices/` and lists it first in the profile. Use `--engine qwen3` for the clearest diction.
   - Not right yet: reword the description (see what worked and what didn't in `knowledge/voices.md`) or pass another `--seed`, and design again.
   A recording of a real person goes in `me/voices/` too, and only with their consent: save the clip and its words, then `keep` it.
7. **Delivery.** Where finished MP3s should go: a folder that syncs to their phone (iCloud Drive is `~/Library/Mobile Documents/com~apple~CloudDocs/<folder>`, Google Drive for desktop is `~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>` on a Mac and usually `G:/My Drive/<folder>` on Windows (forward slashes), Dropbox is `~/Library/CloudStorage/Dropbox/<folder>`), or nowhere, keeping them only in `me/workouts/`. Say that once a build's copy lands there, the local MP3 is removed and only the script's text stays in `me/workouts/`, so this folder is where the audio lives. Check the folder exists with `ls`, and offer to create the subfolder. It is the profile's `deliver_to` setting, a folder or a list of them, one per computer the listener renders on (each build copies to the ones that exist there); a request to change where workouts go runs this step alone.

## Step 3: write the files

- `me/profile.md` and `me/health.md`: fill in every bracketed placeholder from the answers (the template is `me.example/`), and delete lines the user has nothing for. Keep the `+++` block at the top of each file. In `me/profile.md` that block is TOML and holds every setting the tools read: `experience`, `likes`, `dislikes`, `deliver_to`, `words_per_minute`, `youtube_favorites` and `puzzles` (@handles without the @), one `[[voices]]` table per voice (`name`, `description`; the first is the default), one `[[kits]]` table per kit (`name`, `equipment`), and one `[[feeds]]` table per feed (`label`, `kind`, `value`). Edit those values in place; the prose below the block is for Claude only. Writing `me/health.md` asks the user for permission; that's expected, since it's the most private file.
- **Feeds.** Weather: the neighborhood's latitude and longitude, rounded to two decimals. Teams: find each team's ESPN path (the `sport/league/team` part of its ESPN team page URL, such as `hockey/nhl/nj` or `soccer/usa.1/10739`) with a web search. Local news: one or two outlets' RSS feeds for the city. Keep the shipped science and puzzle feeds unless the user doesn't want them. YouTube handles: check each one resolves (`https://www.youtube.com/@<handle>`).
- Then run `./sweatcast check`. It lists every line still showing the template's `[hint]`, any feed not filled in, a missing experience level, likes or dislikes the catalog doesn't know, kit equipment not in the catalog, a malformed `[[limits]]` row (which would apply no limit at all), an unknown rehab id or one that isn't a rehab movement, a bad `flags` value, an injury written in prose with no `[[limits]]` row, and anything the tools can't read, with line numbers; fix or delete each until it reports no issues (its notes, such as no delivery folder or an unknown like, are fine). Run `./sweatcast feeds` once, fix or remove any source it lists under "Couldn't fetch", and run it again.

## Step 4: first audio

1. Download the chosen voice's model: say its size first (above), then run `./sweatcast setup` with `run_in_background: true`. It skips everything already done and fetches the default voice's model at its pinned revision, from Hugging Face with no account needed (its "unauthenticated requests" warning is harmless). On a slow connection this takes a while; finish Step 3's feeds while it runs.
2. Once it has finished, render the smoke test with the chosen voice: `./sweatcast build voices/smoke-test.draft.txt "smoke-test" --voice "<voice>"`. It measures the voice's pace, which session builds require. Send `me/workouts/smoke-test.mp3` with SendUserFile if it's available, and ask how it sounds.
3. Offer a ten-minute first session (the `workout` skill, strength at ten minutes) as the end-to-end check, including the copy to the delivery folder.

## Step 5: keep it safe

- Suggest backing up `me/` as its own private git repo: `git init` inside `me/`, commit, and push to a private remote. The engine's git ignores `me/`, so the two never mix, and the pre-push hook blocks `me/` from the public repo.
- Summarize what was written, in a few lines, and where to change it later ("ask me to update your profile").
