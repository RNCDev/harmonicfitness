# A thin web UI for sweatcast, on Railway

Status (2026-10-27): planned, not started. The working copy of this plan is a Claude Doc
(https://claude.ai/artifact/77hrNAuFQYRoES9gUAFg6Q), with an architecture diagram; this file is its copy
in the repo. Layout mockups: `web-ui-mockups.html` beside this file
(published at https://claude.ai/artifact/3hpnyuzQQxhshG4qGmLEhJ).

## Summary

We'll build a thin web UI for sweatcast on Railway, for invited users only. The screen is split: a multimodal
chat with the coach on the left, and on the right a panel that shows whichever stock control the conversation
needs.

- **Layout:** split screen (Option A in the mockups). On a phone the panel becomes a bottom sheet.
- **Host:** Railway, with Postgres plus one volume for each user's `me/` folder.
- **Voices:** web coaches only on Railway. Local coaches stay on listeners' own computers.
- **Keys:** bring your own keys (Claude and voice services), kept encrypted in a key locker.
- **Auth:** email and password with invite codes. No password recovery and no email sender; an admin command
  resets passwords.
- **Audience:** the maintainer plus a few invited users. Proper sandboxing comes before any open sign-up.

## Layout

- **Left: multimodal chat.** Text, voice notes and photos. A photo of a hotel gym can fill in the day's kit; a
  voice note can answer the check-in.
- **Right: one panel at a time.** The agent opens a stock panel by name, prefilled with what it already knows.
  It never invents a layout.
- **One record.** Whatever is submitted in a panel is also posted into the chat as a short message.
- **Phones.** The panel slides up as a bottom sheet over the chat. Most listening happens on a phone, so this
  is the main target.
- **Tabs** above the panel open any panel directly, without asking the coach.

## Panels

Each reads and writes through the same `./sweatcast` commands and context files the CLI uses, so the engine's
checks still apply.

| Panel | What it does | Backed by |
| --- | --- | --- |
| Check-in | Minutes, goal, kit, sleep, soreness, each limit loosened or tightened | `brief`, `health.md` limits |
| Workout | Player, segment timeline, script, build progress | build record, web copy |
| Coaches | Stock web coaches and the user's own, with samples to play | `coaches list`, `sample.mp3` |
| Limits | Each injury row: area, side, level, note; clinician rules read-only | `health.md` `[[limits]]` |
| Log | Past sessions, feedback, this week's coverage | `log.md`, `coverage` |
| Profile | Name, experience, kits and weights, likes and dislikes | `profile.md`, `training.md` |
| Keys | Enter, test, replace or delete each key; write-only | key locker |
| Interests | The interest graph: topics by slot, feeds, favorites, never bring up, what's been told | `content.md`, `told.jsonl` |

- **Keys panel:** each service as set or not set, and when last tested. Never shows a key back, not even part
  of one. Save & test sends one small request: works, wrong key, or out of credit.
- **Interests panel:** a graph with the user at the centre; each node an `[[interests]]` row, coloured by slot
  (today, science, deep dive, quiz, delight, learn). Feeds and YouTube favorites hang off the topics they
  serve. Tapping a node edits it and shows times told and reactions. After a workout the coach can suggest new
  topics to add with one tap. "Never bring up" is its own tab.

## Architecture on Railway

One Railway service runs the web app and starts a separate agent process for each user's turn.

- **Web app:** login, sessions, invite codes; panels post facts and keys here; starts each user's agent turn.
- **Agent turn, one process per user:** Claude Code through the Claude Agent SDK, in a copy of the engine with
  its skills and settings; `SWEATCAST_HOME` set to that user's folder; only that user's keys in its
  environment; tools limited to `./sweatcast`.
- **Postgres:** users, sessions, invite codes, the key locker.
- **Volume:** `/data/users/<id>/me`, one per user (profile, health, log, drafts, MP3s).
- **Out:** the Claude API (the user's own key) and the coach's voice service (script text only).

Railway volumes attach to one instance, which is fine for a handful of users.

## Auth

- Passwords hashed with argon2id (or bcrypt) from a proven library.
- Sessions in secure cookies (httpOnly, Secure, SameSite=Lax), stored server-side so they can be revoked.
- Login limits per account and per IP address.
- Invite codes required to sign up.
- Admin reset through Railway's shell: `admin reset-password <email>` sets a temporary password, passed on in
  person, and ends that user's sessions.
- Given up: self-service reset and proof an address is real. Fine while every user is known personally.

## Key locker

1. The Keys panel posts the key straight to the server over HTTPS, never through the chat or the agent.
2. The server encrypts it with a master key held as a Railway variable (AES-GCM or libsodium's secretbox) and
   stores the ciphertext with the user id, service and a key version.
3. When a turn starts, the server decrypts that user's keys into the process environment:
   `ANTHROPIC_API_KEY` for the agent; `FISH_AUDIO_API_KEY`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`,
   `INWORLD_API_KEY` for the engine, which already reads the environment before `me/.env`.
4. `redact.scrub` keeps key values out of anything the engine prints.

The master key, not each user's password, locks the locker, so an admin reset leaves the user's keys working.

## Isolation and privacy

For invited users (v1):

- Each turn is its own process with `SWEATCAST_HOME` and keys for that user only.
- Each user has their own system user and a folder only they can read (mode 700).
- The agent's tools are limited to `./sweatcast` and its own `me/`. No general shell, no network tools.
- One render or agent turn per user at a time.

Before open sign-ups: a per-user sandbox (container or microVM) for each turn.

Health data: export of the whole `me/` as a ZIP, account and data deletion, Railway volume backups, a short
privacy note. No personal details in the engine, its tests or its examples, as now.

## Engine changes

- **Hosted mode:** a setting such as `SWEATCAST_HOSTED=1`, treated like `CLAUDE_CODE_REMOTE`: local voices off,
  the web copy on, no delivery folders, no `keys open` in an editor.
- **Panel tool:** the app gives the agent `show_panel(name, prefill)`; skills use it where they now use
  AskUserQuestion and SendUserFile.
- **Skills:** `setup` gets a hosted path (Keys panel, a stock web coach, no privacy hook or backup repo);
  `workout` finishes in the Workout panel.
- **Backup:** skipped in hosted mode; volume backups and export replace it.
- **House rule:** CLAUDE.md, the README's "For Claude" section and the setup skill say new listeners are set
  up only on their own computer; all three need a hosted exception.
- **Release:** minor-release-sized, with a "For forks" note.

## Build order

1. Skeleton: Railway service, Postgres, volume, login with invite codes, admin reset. One user's `me/`.
2. Chat: text chat on the Claude Agent SDK in the engine folder, `SWEATCAST_HOME` set, streamed replies.
3. Key locker and Keys panel; first end-to-end web-coach workout.
4. `show_panel`, then Check-in and Workout panels; skills switched to them in hosted mode.
5. Coaches, Limits, Log, Profile, Interests panels.
6. Voice notes and photos in the chat.
7. Second user: per-user system users, folder permissions, tool limits, export and delete; invite a few.
8. Before public sign-up: per-user sandboxes, then reconsider email recovery.

## Open questions

- Python (FastAPI) beside the engine, or TypeScript (Next.js) with the Agent SDK's TypeScript package?
- The app in this repo (`web/`) or its own repo pulling the engine as a pinned release?
- MP3s served from the volume behind login, or from S3-style storage with short-lived links?
- Past one Railway instance, what then?
- Chat history in Postgres, or only the outcomes already in `me/`?
- Can a user still run sweatcast locally against the same `me/` (export and import, or a sync)?
