---
name: setup
description: Set up sweatcast for a new listener, or update their context. Use when someone asks to "set me up", "set up sweatcast", "setup sweatcast", "install sweatcast", "get started", "finish setting me up", "let's create a routine" on a copy that isn't set up, onboard, or change their profile, injuries, feeds, audio route, cloud voice key or delivery folder, and whenever a workout is requested but me/profile.md doesn't exist yet.
---

# Setup: a new listener's context

Goal: a stranger hears their first workout within minutes. The **quick start** asks one round of questions, uses Coach Demo (a stand-in coach that ships ready), and ends with a ten-minute workout. Everything else (interests, taste, feeds, the delivery folder, their own coach) is **finish setting me up**, whenever they like. Everything personal goes in `me/` (git-ignored); never edit the engine (tools, skills, `knowledge/`) for one listener.

The listener may be a stranger who has read nothing: explain each step in a line, in plain words, and never send them to the README.

## Step 0: what this computer can do

Run `./sweatcast doctor` first and relay what matters in two or three plain lines: the computer, whether local voices work here, and anything missing.
- **Claude Code on the web** (doctor's report starts "This is Claude Code on the web"): see "On Claude Code on the web" below before anything else.
- **uv missing:** ask once (AskUserQuestion) whether to install it with Astral's official installer, which needs no admin rights; it runs a downloaded script, so ask first. On yes, `./sweatcast setup --install-uv --no-models` (it installs uv, then carries on as in Step 1).
- **No local voices here** (an Intel Mac, or below the memory or disk floor): say so now, with doctor's reason. Audio then comes from a cloud voice with the listener's own key. **The processor only** (Windows or Linux without an NVIDIA card): local voices work but are experimental, speed unknown and likely slow; offer a cloud voice too.
- ffmpeg isn't a prerequisite: the Python environment brings its own. git isn't either: outside a git checkout (a zip download), setup skips only the privacy hook.

## Step 1: the machine

Run `./sweatcast setup --no-models` with `run_in_background: true`, and ask the quick start's questions while it runs. It makes the Python environment with uv, copies `me.example/` to `me/` if there's no `me/profile.md` yet (Coach Demo included, and `setup = "quick"` in the profile), or brings an existing one up to this version's format (backing it up first), and installs the git hook that refuses to push `me/`. The local engine and its model come later, once the audio route is settled. If it stops, relay its one-line fix and rerun it once they say it's done.

If `me/profile.md` already has real answers, this is an update: ask only about what they want to change (the reference sections below say how each part is written), and skip the rest.

## The quick start (a new listener)

1. **One AskUserQuestion round, four questions:**
   - **Name:** what the coach should call them (options: "Use my first name" and "No name", with their name through Other). It goes in the settings as `name`.
   - **Experience:** novice (new to training, or back after a long break), experienced (trains regularly, knows the common lifts), advanced (trains hard, wants harder variations). It becomes `experience`.
   - **Kit:** bodyweight only, a hotel room, a gym, or "what's at home" through Other (dumbbells, bands, a bench...). It becomes the first `[[kits]]` row (Kits, below).
   - **Injuries:** "None" (Recommended) or describe them through Other. Say plainly, once: sweatcast isn't medical advice, a clinician's instructions override everything, and red flags (can't bear weight, rapidly increasing swelling, numbness, giving way, getting worse after a week or two) mean seeing a clinician before training. Each injury they name becomes a `[[limits]]` row (Health, below); ask a follow-up only if the area or the side isn't clear.
2. **Audio,** without a question where doctor settles it: local where it works fast (Apple Silicon, or an NVIDIA card), started now (Step 4.1 below) so it downloads during the first workout's research. Where local doesn't run, or runs only on the processor, ask which cloud voice (Audio, below) and walk the key.
3. **Write** `name`, `experience`, the kit and any limits (Writing the files, below). Leave the other template lines as they are: with `setup = "quick"`, `./sweatcast check` lists them as notes, not issues.
4. **Coach Demo** is their coach for now: a warm baritone trainer, measured already on the local engine and on Fish Audio, so no smoke test is needed there. On ElevenLabs or Cartesia, run the smoke test with Coach Demo first (about a minute, about 1,000 characters). On Deepgram, which has stock voices only, give Coach Demo one (`./sweatcast coaches samples deepgram`, then `./sweatcast coaches set "Coach Demo" deepgram.voice <voice>`) and run the smoke test.
5. **A ten-minute first workout:** run the `workout` skill, strength at ten minutes (the check-in asks only how they're coming in today). It's the end-to-end check, the copy to a phone folder aside.
6. **Then, in two lines:** they can say "I want a new coach" for a coach of their own (a minute or two: one question, one take), and "finish setting me up" for interests, teams, feeds and a folder that syncs to their phone. Suggest backing up `me/` (Keep it safe, below).

## Finish setting me up

Runs the rest of the interview, AskUserQuestion with at most three rounds of up to four questions, in this order: likes and dislikes, interests and taste, delivery, their own coach (the `coach` skill's quick coach), and a neighborhood and city for local news and weather. Then Feeds and `./sweatcast check` (Writing the files), and remove the `setup = "quick"` line and its comment from the profile's settings, so check holds every line to the full standard again.

## On Claude Code on the web

Claude Code on the web is a cloud machine with no graphics card, and its files last only as long as the session, except what's in git. sweatcast runs there with a cloud voice only. Doctor's "Claude Code on the web" section says what's set and what isn't; relay it in plain lines:
- **The key** goes in the cloud environment's settings, under Environment variables, as one line such as `FISH_AUDIO_API_KEY=<key>`, never in the chat; `./sweatcast keys init <service>` prints the exact line. A new session picks it up. Fish Audio is the one to suggest: the cheapest (about $0.30 a workout), and tried live.
- **The network:** the environment's network access needs the voice service's host (doctor names it, such as `api.fish.audio`): Custom, with the default list kept. The feeds' hosts are optional; research searches without them.
- **Keeping their profile.** If doctor says the context folder is their own private repo, everything is kept: `./sweatcast backup` pushes after each workout. If not, ask once (AskUserQuestion): **a one-time session** (Recommended for trying it out), or **keep it in a private repo**. For one time, say plainly: this session uses Coach Demo and a short quick start, the workout arrives as a page with a player, and the profile, log and coach vanish when the session ends; to keep them next time, they make a private GitHub repo called `sweatcast-me`, attach it to the session beside sweatcast, and say "set me up" again. For keeping it: after setup, make `me/` a repo, ask them to create an empty private `sweatcast-me` repo on GitHub and attach it to the environment, then push to it (`./sweatcast backup`).
- The quick start then runs as above, with `render = ["fish"]` (or their service) and `cloud_max_chars` set. Rendering ahead (`--follow`) is off on a cloud voice, and the workout's MP3 comes as a web copy: a player page the workout skill publishes, and the parts in the private repo.

## Reference: how each part is written

**Kits.** Each kit becomes one `[[kits]]` row in the profile's settings: a `name` and the `equipment` ids it holds, from the catalog's equipment list (near the top of `knowledge/movements.toml`; the `[presets.*]` tables there are kits to start from: bodyweight, hotel-room, hotel-gym, full-gym). The first kit is the default. For free weights, ask which weights are there and write them as `weights` (equipment id = the weights, lightest to heaviest) with `unit` (`"lb"` or `"kg"`), for example `weights = { dumbbells = [10, 15, 20], kettlebell = [30] }`, so the brief prints what's on hand and the session prescribes only those. Also copy each kit into the prose under Equipment kits.

**Likes and dislikes.** Movements they enjoy or want left out. Resolve each name against the catalog (`./sweatcast movements --equipment <ids>` prints movement names, which the catalog resolves to ids) and put the ids in `likes` and `dislikes`; a name the catalog doesn't know goes in the profile's prose, not in the list.

**Health.** Walk each injury into one `[[limits]]` row in the settings block of `me/health.md` (the template, `me.example/health.md`, shows one):
- `area`, from the catalog's list of thirteen: foot, ankle, calf, knee, hamstring, hip, groin, low-back, rib, shoulder, elbow, wrist, neck. Spell it as written here, with the hyphen in low-back.
- `side`: left, right or both.
- `level`: off-limits means nothing that loads the area at all; delicate means nothing that loads it hard, no impact and no fast work. Offer both in those words and let the clinician's words decide; when unsure, off-limits.
- `note`: the clinician's words, short. Put them word for word under `## Clinician rules` too; each is followed literally. An injury in none of the thirteen areas gets no row: write it in the prose list as "- Unlisted: <what>", and put any movement ids or flags to avoid for it under `## Clinician rules` as a line "Avoid: <ids or flags>" (ids from the catalog, flags from its `flags` list), which `./sweatcast brief` applies on every run. The playbook's "Unlisted injuries" says what to do.
- `rehab` and `flags` stay empty unless the clinician named a rehab movement or something else to avoid; `flags` values come from the catalog's fixed `flags` list.
Add the injury and its programming to the prose list under Active injuries too. No injuries: leave "None right now." and no rows. Writing `me/health.md` asks the listener's permission; that's expected, since it's the most private file.

**Interests and taste.** Teams, topics, YouTube channels for deep dives, puzzles, books, local news, and anything never to bring up; then favorite shows, books, music, comedians, restaurants and drinks, with ratings if they have them. Interests become `[[interests]]` rows in the profile's settings (name, slot from `knowledge/content.toml`, detail); favorites go under `## Taste`; and find a feed for each taste area that has one.

**Audio.** How the workouts become audio. Offer what doctor's Audio routes section says works here:
- **Local** (where it works): free, private, on this computer; the engine and model are a 3 to 4 GB download, and Apple Silicon renders a 30-minute workout in about 20 minutes. On the processor, say it's experimental and slow.
- **A cloud voice with their own key:** Fish Audio (about $0.30 a workout, the cheapest; it copies the coach's clip on every request), ElevenLabs (about $0.80 with Flash, $1.60 with the more natural multilingual model; suggest the natural one), Cartesia (about $1.00; a paid plan for cloning) or Deepgram (about $0.60; stock voices only, so the coach sounds different there). ElevenLabs, Cartesia and Deepgram are "not yet tried live": say so.
- For a cloud voice, say once, plainly: the script goes to the service and can mention their injuries ("easy on that left knee"); roughly what a workout costs there (approximate; prices change); and the key is stored in `me/.env` on this computer only (on the web, in the environment's settings), never backed up or shown, and removed by deleting its line. Then `./sweatcast keys init <service>`, give them the file's path (a clickable link in an IDE) and ask them to paste the key after the `=` and save. Never ask for the key in the chat, and never open, print or copy `me/.env`. `./sweatcast keys` confirms it's set.
- The choice is the profile's `render` list, in order of preference, such as `["local", "fish"]` (each build takes the first that works on the computer it runs on). Enabling a cloud voice also writes `cloud_max_chars = 30000` (a 40-minute workout with room for retakes, about $0.45 on Fish, $2.40 on ElevenLabs multilingual): tell them the figure and that a build over it stops before sending.

**Delivery.** Where finished MP3s should go: a folder that syncs to their phone (iCloud Drive is `~/Library/Mobile Documents/com~apple~CloudDocs/<folder>`, Google Drive for desktop is `~/Library/CloudStorage/GoogleDrive-*/My Drive/<folder>` on a Mac and usually `G:/My Drive/<folder>` on Windows (forward slashes), Dropbox is `~/Library/CloudStorage/Dropbox/<folder>`), or nowhere, keeping them in each workout's folder in `me/workouts/`. Say that once a build's copy lands there, the local MP3 is removed and only the script's text stays, so this folder is where the audio lives. Check the folder exists with `ls`, and offer to create the subfolder. It is the profile's `deliver_to` setting, a folder or a list of them, one per computer the listener renders on (each build copies to the ones that exist there); a request to change where workouts go runs this part alone. On the web there's no such folder: the player page is the delivery.

**Writing the files.**
- `me/profile.md` and `me/health.md`: fill in the placeholders the answers cover (the template is `me.example/`), and delete lines the user has nothing for (the quick start leaves the rest for later). Keep the `+++` block at the top of each file. In `me/profile.md` that block is TOML and holds every setting the tools read: `name`, `setup`, `experience`, `likes`, `dislikes`, `deliver_to`, `words_per_minute`, `youtube_favorites` and `puzzles` (@handles without the @), `render` (the audio routes, in order) and, with a cloud voice, `cloud_max_chars`, one `[[kits]]` table per kit (`name`, `equipment`, and for free weights `weights` and `unit`), and one `[[feeds]]` table per feed (`label`, `kind`, `value`). Edit those values in place; the prose below the block is for Claude only.
- **Feeds** (finish setting me up). Weather: the neighborhood's latitude and longitude, rounded to two decimals. Teams: find each team's ESPN path (the `sport/league/team` part of its ESPN team page URL, such as `hockey/nhl/nj` or `soccer/usa.1/10739`) with a web search. Local news: one or two outlets' RSS feeds for the city. Keep the shipped science and puzzle feeds unless the user doesn't want them. YouTube handles: check each one resolves (`https://www.youtube.com/@<handle>`).
- Then run `./sweatcast check`. It lists every line still showing the template's `[hint]`, any feed not filled in, a missing experience level, likes or dislikes the catalog doesn't know, kit equipment not in the catalog, a malformed `[[limits]]` row (which would apply no limit at all), an unknown rehab id or one that isn't a rehab movement, a bad `flags` value, an injury written in prose with no `[[limits]]` row, and anything the tools can't read, with line numbers; fix each issue until there are none (notes, such as no delivery folder, Coach Demo being a stand-in, or what the quick start left for later, are fine). After filling in feeds, run `./sweatcast feeds` once, fix or remove any source it lists under "Couldn't fetch", and run it again.

## Step 4: the local engine, when the route includes local

If doctor (or `./sweatcast models adopt --dry-run`) found sweatcast's models already downloaded elsewhere, offer to move them (`./sweatcast models adopt`) rather than download again. Say the size (3.3 GB for Chatterbox Turbo on a Mac, 4 GB on Windows or Linux, plus the engine itself), then run `./sweatcast setup --local` with `run_in_background: true`. It skips what's done. On a processor-only computer, the smoke test (`./sweatcast build knowledge/smoke-test.draft.txt "smoke-test"`) measures this computer's render speed, and doctor then quotes the time a 30-minute workout takes; past an hour, suggest a cloud voice and let them choose.

## Keep it safe

- Ask whether they have a GitHub account. Without one, say `me/` stays on this computer and everything works; to keep a copy, they can copy the `me` folder now and then to somewhere private (it holds their health notes). With one, suggest backing up `me/` as its own private git repo: `git init` inside `me/`, commit, and push to a private remote (`gh repo create sweatcast-me --private --source . --push`). The engine's git ignores `me/`, so the two never mix, and the pre-push hook blocks `me/` from the public repo. That repo is also how Claude Code on the web keeps their profile.
- Summarize what was written, in a few lines, and where to change it later ("ask me to update your profile").
