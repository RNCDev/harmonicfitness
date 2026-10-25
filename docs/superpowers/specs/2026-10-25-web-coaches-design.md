# Web coaches: describe, audition, approve, keep

Status: for approval, 2026-10-25 (builder-checked). Scope: the web (cloud) path only. The local path (clips and local engines) is untouched by this design and is redesigned in a later session.

## Why

Making a coach today is built around a reference clip: design takes, keep one as `clip.wav`, and every engine copies that clip. On the web this forces a subscription at two of the four services (ElevenLabs and Cartesia need one to clone a clip), makes Fish send half a megabyte with every request, and asks the listener to think about clips, takes and smoke tests.

The listener wants one simple flow that works the same on every web service:

**describe → hear → approve → keep in the stable → use by name in a session.**

A web coach is a voice that lives at the service, designed or picked there from the listener's description, never a clip the listener supplies. A service's voice is the same voice on every request, so the coach sounds like the same person from session to session. Everything must work on pay-as-you-go: no subscription anywhere.

## Goals

- One flow for making a web coach, whatever the service.
- Audition across every service the listener has a key for, in one go; the listener picks a voice, never a vendor.
- Each approved voice becomes its own named coach, tied to one service. A listener may approve several from one audition (say one per service) and names each.
- A session uses a coach by the listener's name for it. The service's own voice name never shows.
- Pay-as-you-go only, with the cost of each audition and each workout shown before money is spent.

## Non-goals

- The local path. Local coaches, clips, Chatterbox and Qwen3 stay as they are until the local redesign.
- Moving a coach between services. A coach stays where it was made; the same description can make a second coach elsewhere.
- Voices copied from a clip on the web (cloning). Out of scope by decision.
- A shared "parent" narrative across coaches. Each coach keeps its own copy (decided: simpler, and coaches may grow apart).

## Anti-goals (a failure even if it works)

- Asking the listener to choose a vendor, a model or a voice ID.
- A coach that sounds noticeably like a different person from one workout to the next.
- A key in the chat, or any tool printing one.
- Offering voices that imitate real people or characters (the public Fish library's most popular voices are game announcers and celebrity imitations).
- Any step that quietly needs a subscription.

## The services (deep dive, 2026-10-24/25)

Everything below marked **live** was tested with the listener's own keys; the rest is from each service's docs on 2026-10-24.

| Service | Billing (no subscription) | How a coach is made | Saved voice | Cost of a 20,000-character workout | Notes |
|---|---|---|---|---|---|
| Fish Audio | Prepaid credit, no minimum; per million UTF-8 bytes | **Design** (`POST /v1/voice-design`, `model: voice-design-1`, $0.01 a call, up to 4 candidates), then **save** (`POST /model`, multipart: the candidate WAV, `texts`, `voice_design_signatures` from the candidate, `visibility=private`) | Private model `_id`, used as `reference_id` | About $0.30 on `s2.1-pro` ($15/M bytes) | **Live:** design, save (201, `state: trained`, `source: voice_design`), speech by `reference_id`. No seed on speech. `s1` retires 2026-12-31; the engine's model name must move to `s2.1-pro`. Concurrency 5 under $100 prepaid. |
| ElevenLabs | Free accounts can prepay ("Pay As You Go", $5 minimum, expires in 12 months); API $0.08 per 1,000 characters on v4/multilingual v2, $0.04 on v4 Turbo/Flash | **Design** (`POST /v1/text-to-voice/design`, three previews, billed as the preview text's characters), then **save** (`POST /v1/text-to-voice` with the chosen `generated_voice_id`) | Voice in the account; one of 3 custom slots on Free (10 on Starter) | About $1.60 on v4, $0.80 on v4 Turbo; Free includes 10,000 v4 characters a month | **Not verifiable live:** the listener's account is on Starter. Unconfirmed: design and save through the API on Free; the plan page's "$0.36 extra minute" (an app rate) against the API's $0.08/1k. Stock voices: Library voices are blocked from the API on Free, and default voices exist only for accounts made before March 2026 and expire 2026-12-31, so **design is the only path on Free**. Free is non-commercial. Seed and `previous_text`/`next_text` supported. Models live: `eleven_v4`, `eleven_v4_turbo`. |
| Gemini (API key from AI Studio, not Google Cloud) | Prepaid credits, $5 minimum; free tier exists | **Design** (`POST /v1beta/voices`, body `{"voice": {"type": "prompted", "display_name": ..., "prompted": {"input": <description>}}, "store": true}`; returns `id` and a `sample_audio` WAV) | `voice_...` ID; lasts a year, renewed by each use; 200 per project | About $0.27 on `gemini-3.8-flash-tts` until 2026-12-31, about $0.54 from 2027 (audio at 25 tokens a second); Lite about two thirds of that | **Live:** design (`voice_j84pg40buem8`), speech by that ID through `POST /v1beta/interactions` (`model`, `input: [{type: text, text}]`, `response_modalities: ["audio"]`, `generation_config.speech_config: [{"voice": id}]`), WAV at 24 kHz. Style goes in a short `speech_metadata.style` annotation, **never in the text** (live: an instruction in the text was read aloud). Delivery pauses about a second after each short sentence, so it runs about 35 percent slower than the others, and the same line varied about 9 percent across three renders. Terms: free-tier data is used for training with human review; the terms say "not for consumer use"; 18+. |
| Inworld | "On-Demand": $0 a month, prepaid credit ($10 minimum) | **Design** (`POST /voices/v1/voices:design`, up to 3 drafts with base64 previews), then **publish** (`POST /voices/v1/voices/{voiceId}:publish`) | `voiceId` in the workspace; 100 custom voices on On-Demand | About $0.50 on `inworld-tts-2` ($25/M characters), $0.30 on `inworld-tts-2-flash` | **Live:** design, publish, speech with the published voice on both `inworld-tts-2` and `inworld-tts-2-flash`. 2,000 characters a request; `synthesisContext.previousRequests` (unbilled) helps joins. `inworld-tts-1`/`1-max` were discontinued 2026-06-15 and 1.5 is deprecated. Design cost isn't published. Design calls are limited to 2 a minute. Concurrency 5. Auth: `Authorization: Basic <key as given>`. |

Dropped, with the reason:
- **Cartesia:** cloning needs a subscription and its plans are monthly bundles, not pay-as-you-go.
- **Deepgram:** stock voices only (no design or cloning), so its coaches couldn't be original. Dropped by the listener's decision on 2026-10-25, after a live test of its voice list and speech worked; `tools/services/deepgram.py` and `coaches samples deepgram` are removed.
- **OpenAI:** every model on its speech endpoint shuts down on 2027-01-06, and the named replacement is Realtime-only.
- **Fish's public library:** only 58 voices carry `licensed=true`, and the popular unlicensed ones imitate real people and characters. Fish coaches are designed instead.

**Every web coach is an original voice, designed from the listener's own description and saved at the service, with no subscription**: on Fish, Gemini and Inworld on pay-as-you-go, and on ElevenLabs within Free's 3 voices and monthly allowance (or prepaid usage). That is the claim sweatcast makes to the listener. The earlier idea that only local could make an original coach was wrong.

## The flow

### 0. Keys

The coach skill (and setup) starts with `./sweatcast keys`, which prints only "set" or "not set" per service. With no web key, it says once: an account and a pay-as-you-go key at one or more of Fish Audio, ElevenLabs, Gemini or Inworld, with a line each on cost and what's needed (Gemini: an AI Studio key; Inworld: On-Demand credit; ElevenLabs: Free works within 3 voices and its monthly allowance, or prepaid usage). Then how to add the key:

- **Claude Code on the listener's computer (terminal, VS Code or the desktop app):** `./sweatcast keys init <service>` adds an empty line to `me/.env`, then the new `./sweatcast keys open` opens that file in the computer's own text editor (`open -e` on a Mac, `notepad` on Windows, `xdg-open` on Linux). The listener pastes the key after the `=` and saves. Claude never reads the file; `./sweatcast keys` confirms.
- **Claude Code on the web:** the key goes in the cloud environment's settings as an environment variable, and the service's host on its network allowlist (as today). `doctor.py` already prints both; it gains the two new services.

The key goes nowhere near the chat. Two new key names: `GEMINI_API_KEY`, `INWORLD_API_KEY` (already in the listener's `me/.env`).

### 1. Describe

The listener describes the coach, or picks one of three sketches (as the quick coach does today). Claude turns it into the coach narrative (below). The `[voice]` part is what the services design from; the `[character]` part is what the script writer follows.

### 2. Audition

`./sweatcast coaches audition "<narrative file>"` makes one candidate per service with a key, in parallel, each saying the same coaching line (the line in `knowledge/voices.md`), and prints each one's approximate cost per workout:

- Fish: one design call, `n=2` (two candidates, one $0.01 call).
- ElevenLabs: one design call (three previews).
- Gemini: one prompted design (it returns its own sample; the coaching line is then spoken once with the new voice so every candidate says the same thing).
- Inworld: one design call, `numberOfSamples=2`.

Candidates land in `me/personas/.auditions/<date>-<n>/` as `<service>-<k>.mp3` plus `candidates.json` (service, the service's draft or generated ID, the design signature where needed, cost). Claude sends them (SendUserFile, else `--play`, else paths), labeled by a letter and the service's per-workout cost, never by voice ID.

Where a service keeps a voice only after an explicit save (Fish, ElevenLabs, Inworld), the audition does **not** save. Gemini's design call stores the voice as it designs (`store: true` is required); unapproved Gemini candidates are deleted (`DELETE /v1beta/voices/{id}`) when the audition is closed.

Not right? The listener says what's off; Claude edits `[voice]` and auditions again, on all services or only the ones named.

### 3. Approve and name

The listener approves one or more candidates and gives each a name ("B is Coach Maya, D is Coach Dana"). `./sweatcast coaches keep <audition>/<candidate> --name "Coach Maya"`:

- saves the voice at the service where it needs saving (Fish `POST /model`, ElevenLabs `POST /v1/text-to-voice`, Inworld `:publish`), named "sweatcast <coach name>";
- writes `me/personas/coach-maya/` (below), with the approved sample as `sample.mp3`.

### 4. The stable

`./sweatcast coaches` lists the coaches with their service and marks the one used last. Coach Julius, Coach Solo and Coach Demo move to `me/personas/.archive/` (decision 4) (still backed up, out of the list); log lines naming them stay valid (lookup searches the archive for old names, read-only).

### 5. A session

A workout uses the named coach, else the one used last. The build renders on **that coach's service**; the profile's `render` list no longer chooses for a web coach (it still orders routes for local coaches). If the coach's service has no key on this computer, the build stops with exit 64 and the workout skill offers the listener's other coaches whose service works here.

Before sending, the build prints characters and approximate cost and checks `cloud_max_chars`, as today.

## The coach file

```
me/personas/coach-maya/
  persona.md    settings + narrative
  sample.mp3    the approved audition sample
  pace.json     measured pace (by service + model + voice)
```

```toml
+++
schema = 5
name = "Coach Maya"
aliases = []
kind = "web"                     # web | local (local keeps today's clip files)
service = "inworld"              # fish | elevenlabs | gemini | inworld
voice_id = "funky-finch-6967__design-voice-a5809f1c"
model = "inworld-tts-2"          # optional; default from knowledge/services.toml
style = ""                       # Gemini only: a short constant style annotation, or empty
made = "2026-10-25"

[voice]                          # what the services design or match from
who = "A woman in her thirties, a strength coach"
sound = "Warm, mid-low, American accent, crisp diction"
energy = "Steady, calm authority"
pace = "Natural; brisk during work"
avoid = "Hype, shouting, announcer voice, sleepy delivery"

[character]                      # what the script writer follows (the brief quotes it)
background = "Ten years coaching clients one on one"
calls_you = "Ritujoy"
encouragement = "Notices effort plainly; says why a movement is there"
pushes = "Asks for one more only when form is clean; backs off at pain"
humor = "Dry, now and then"
cueing = "Short body cues and breath; counts only on timed work"
signature = ["Stay with it.", "That's the pace we want."]
never_says = ["Crush it", "Beast mode", "No pain, no gain"]
sign_off = "Brief and warm; names one thing done well"
+++
Free notes on how this coach talks.
```

- **Tweaking how they talk** is an edit to `[character]` or the notes: no audition, no cost.
- **Tweaking how they sound** is a new audition on that coach's service only, from an edited `[voice]`; approving replaces `voice_id` (and `sample.mp3`), deletes the old voice at the service where the API allows (asking first), and clears pace for the old voice.
- The brief quotes `[character]` and the notes where it quotes `## How this coach talks` today.

## Engine changes (for the builder)

- **Persona model** (`tools/personas.py`): `kind`, `service`, `voice_id`, `model`, `style`, `[voice]`, `[character]`. `has_clip` stays for local coaches. `voice_for(p, route)` for a web coach ignores `route` and returns the voice dict for `p.service`.
- **Identity for cache and pace keys:** for a web coach, `sha256(service | voice_id | model | style | settings)[:12]` replaces `clip_key`. `clip_hash` and `services.json` are local/clone-only and unused by web coaches.
- **Routes** (`tools/routes.py`): `ROUTES` gains `gemini`, `inworld`; loses `cartesia` and `deepgram`. `pick()` for a web coach returns its service if usable here, else stops with the reason (key missing).
- **Services** (`tools/services/`): one module each with `speaker(voice)` returning `say(text, seed, previous_text, next_text)` → 16-bit mono PCM at 24 kHz, plus `design(description, line, n)` → candidates, `save(candidate, name)` → voice ID, and `delete(voice_id)` where supported.
  - `fish.py`: speech by `reference_id` (JSON body, no inline clip), model `s2.1-pro`; design as today; save by `POST /model` multipart.
  - `elevenlabs.py`: speech by voice ID as today (keeps `previous_text`/`next_text`, seed); design returns three previews; save by `POST /v1/text-to-voice`; model `eleven_v4` default (or `eleven_v4_turbo` for half the price).
  - `gemini.py` (new): design `POST /v1beta/voices`; speech `POST /v1beta/interactions`; key in `x-goog-api-key`; `style` as a `speech_metadata` annotation when set; delete unapproved voices.
  - `inworld.py` (new): design, publish, speech `POST /tts/v1/voice` with `LINEAR16` at 24000, `synthesisContext.previousRequests` from the previous paragraph; `Authorization: Basic <key>`.
  - `cartesia.py`, `deepgram.py`: removed.
- **`knowledge/services.toml`:** rates, models, character limits and concurrency per the table above, with `rates_checked = "2026-10-25"` and `tried_live` true for Fish, Gemini, Inworld (ElevenLabs stays true from 2026-10-24, on Starter).
- **Keys** (`tools/keys.py`): `gemini` → `GEMINI_API_KEY`, `inworld` → `INWORLD_API_KEY`; drop `cartesia` and `deepgram`; new `keys open` (opens `me/.env` in the system editor, never reading it).
- **Coaches CLI** (`tools/coaches.py`): `audition`, `keep` (web), `list` showing service, `archive <name>`, `forget-audition`. The web path no longer uses `design --takes` or the clip-based `keep`; those stay for local. `samples deepgram` is removed.
- **Pace on the first workout:** a web coach is measured from its approved sample (characters in the coaching line ÷ trimmed speech seconds), recorded in `pace.json` as an estimate, and the build renders with it (no exit 3 for web coaches). Every render then records the measured pace, as today, and later builds use that. The smoke test is no longer required for web coaches.
- **Doctor** (`tools/doctor.py`): the web's host allowlist gains `generativelanguage.googleapis.com` and `api.inworld.ai`; loses Cartesia and Deepgram.
- **Privacy line before the first web build** gains: Gemini's free tier uses requests for training with human review, and every service receives the script, which can mention injuries.

## Skills and docs

- **Coach skill:** rewritten around the five steps for web coaches; the local path's text is kept but marked as unchanged pending its redesign.
- **Setup skill:** the keys step (above); the quick start uses the default web coach for the service whose key was added (decision 2).
- **Workout skill:** picks a coach from the stable by name; when the coach's service doesn't work here, offers the others.
- **`knowledge/voices.md`:** the web half rewritten from the table above; the clip-based web text removed.
- **CLAUDE.md, README:** coaches and routes paragraphs updated; Cartesia and OpenAI removed.
- **`./sweatcast migrate`:** schema 4 → 5 for personas: existing coaches become `kind = "local"`; Julius, Solo and Demo move to `.archive/` (per the listener's decision; for a fork, migration archives nothing and only adds `kind`).

## Release

A major version (10.0.0): coach files gain a schema, Cartesia and Deepgram are removed, and web coaches no longer carry clips. CHANGELOG "For forks": run `./sweatcast migrate`; Cartesia and Deepgram coaches render locally, or make a web coach with an audition; an existing clip-based coach now renders locally only (clip copying on Fish and ElevenLabs is removed); make a web coach with an audition, or use a default web coach.

## Probe leftovers in the listener's accounts

The deep dive left test voices: Gemini `voice_j84pg40buem8` (expires 2027-10-25), a Fish private model "sweatcast probe coach" (`fc2a4741ef7740e59e2cfcfd34f6c34e`), and in Inworld a published "sweatcast probe coach" plus drafts. The ElevenLabs clone "sweatcast Coach Julius" still uses a slot. Offer to delete them.

## Decisions after the builder check (2026-10-25)

1. **Clip copying on the web is removed now.** Fish's inline-clip speech, the ElevenLabs clone path, `services.json` and the clone-once code in `tools/cloud.py` go. A local coach renders only locally; a web coach only on its service. The profile's `render` list orders local engines only. Cloud *design* for local coaches (`coaches design` via Fish or ElevenLabs, making a clip) also goes; until the local redesign, local coaches are designed with the local designer or brought as a clip. (Listener's decision.)
2. **Four default web coaches replace Coach Demo**, one per service, all from one shared default description (a seasoned, calm, warm trainer), so they sound alike in spirit. (Listener's decision; the mechanics below are Claude's call.)
   - None can ship ready: a designed voice belongs to the account that made it, and stock voices would break the "every coach is original" claim. Each default ships in `me.example/personas/` as a coach file with no `voice_id` and `pending = "design"`. The first build that needs it designs from the shared description and saves the first candidate, with no audition, saying so first (about $0.01 on Fish and Gemini; Inworld's design cost is unpublished; one of ElevenLabs Free's 3 slots). (Claude's call, replacing an earlier plan to ship stock voices.)
   - Each default is `placeholder = true`; once the listener has a coach of their own, a build with no coach named prefers it. Names: one per service, chosen when building (Claude's call; the listener may rename).
   - Quick setup: one key, then the ten-minute workout with that service's default. An audition is offered after, never required.
3. **ElevenLabs is in the audition**, labeled "not yet tried on a Free account", with its 3-voice limit and monthly allowance stated. (Listener's decision.)
4. **Archiving** Julius, Solo and Demo is a one-time `./sweatcast coaches archive` run in the listener's session, not migration logic (the engine is public). `migrate` only adds `kind = "local"` to existing coaches. If the coach used last is archived, a build with no coach named stops and the workout skill offers the stable. (Claude's call.)
5. **This release is 10.0.0.** It also removes `tools/migrate-assets/v8-voices/` as CLAUDE.md promises for 10.0.0; the local redesign is a later release. (Claude's call.)

## Left to the builder

- Audition sample format (MP3 at 48 kbps mono is enough), parallelism, and retries (reuse `cloud.request`).
- Naming at the service ("sweatcast Coach Maya") and how `forget-audition` cleans up.
- Tests against local fakes for the two new services, as for the existing ones.
