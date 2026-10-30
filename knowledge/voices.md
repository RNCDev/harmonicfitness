# Coaches and voices

A coach is a person: a name ("Coach Maya", never a model's or a service's name), how they talk, and how they sound. There are two kinds, set by `kind` in the coach's `persona.md`:

- **A local coach** (`kind = "local"`): one of the ten HarmonicFitness ships, made once by the maintainer and spoken on this computer by Pocket TTS from the coach's saved voice file. Listeners choose one; they don't make one. A local coach renders only locally.
- **A web coach** (`kind = "web"`): an original voice a web service designed from a description and saved in the listener's own account there (Fish Audio, ElevenLabs, Gemini or Inworld). It speaks only through that service, by its saved voice, and a service's voice is the same voice on every request, so the coach sounds like the same person from session to session. It's never copied from a recording. A listener makes their own with the coach skill.

A coach is not a tuned model: the models are used exactly as published.

**The stock coaches** ship in `coaches/` at the engine's root (public, versioned with the engine, so a release that improves one reaches every listener):
- **Ten local coaches**, five men and five women, each designed from a description (`coaches/roster.toml`): Coach Andy (mid-40s, a low, warm baritone, calm authority; his alias Coach Demo still finds him), Marcus (early 30s, bright tenor, upbeat), Theo (late 20s, relaxed, conversational), Sam (early 60s, deep and gravelly, wry), Callum (late 30s, firm mid-baritone, direct), Maya (early 30s, full mezzo, energetic), Claire (mid-40s, smooth alto, calm and precise), Rosa (late 20s, warm, unhurried), Helen (mid-50s, rich alto, steady and kind) and Kate (mid-30s, clear and cheerful). Each folder holds the coach's clip, its Pocket voice file, its recorded counts and cues, its measured pace and a 45-second `sample.mp3` for choosing by ear. Every one was heard and approved by ear.
- **Four stock web coaches**, one per service, all from one description (a man in his forties, a low, warm baritone, a seasoned trainer): Coach Reed (Fish Audio), Coach Ellis (ElevenLabs), Coach Nolan (Gemini) and Coach Owen (Inworld), `placeholder = true`. None can ship ready, since a designed voice belongs to the account that made it, so each ships with `pending = "design"` and no voice. The first build that needs one designs its voice from the description, saves the first candidate in the listener's account (no audition) and writes the made coach to `me/coaches/<slug>/`, which is used from then on; it says so first: about $0.01 on Fish Audio and Gemini; Inworld doesn't publish its design cost; on ElevenLabs it uses one of the account's custom voice slots (Free keeps 3). `./harmonicfitness coaches make "<name>"` does the same by hand; `--lint-only` never makes one.

With no coach named, a build takes the coach used last (from the log); with none yet, the listener's own web coach; else the first stand-in that can speak here (a stock web coach whose service has a key, in the order above, then Coach Andy where local voices run). If the coach used last has been archived, it stops and asks for a coach by name.

## Where coaches live

```
coaches/coach-maya-local/      a stock local coach (in the engine; never edited for one listener)
  persona.md          settings: name, gender, description, [voice], [character] (coaches/roster.toml makes it)
  clip.wav, clip.txt  the voice it was made from (about 24 seconds, 24 kHz mono) and its words
  pocket.safetensors  its Pocket TTS voice state, which every build speaks with
  cues/               its recorded counts and cues, with cues.toml
  pace.json           its pace, measured from its sample
  sample.mp3          45 seconds of it, for choosing
coaches/coach-reed-fish/       a stock web coach: persona.md only, until it's made

me/coaches/coach-dana-fish/    a web coach of the listener's own (part of the private me/ backup)
  persona.md     settings ([voice], [character]) and free notes
  sample.mp3     the approved audition candidate
  pace.json      pace, one entry per service, model and voice
me/coaches/.auditions/         auditions in progress (not backed up)
me/coaches/.archive/           coaches no longer in use (backed up; old log lines still find them)
```

`me/coaches/` was `me/coaches/` before 0.15.0; `./harmonicfitness migrate` renames it. `me/coaches/` holds only the listener's own coaches; a stock coach is used straight from `coaches/`, by name. The one exception is a stock web coach once it's used: its voice is made in the listener's account, so the made copy goes to `me/coaches/<slug>/` and wins over the stock one.

A web coach's `persona.md`:

```toml
+++
schema = 5
name = "Coach Maya"
aliases = []
kind = "web"
service = "inworld"              # fish | elevenlabs | gemini | inworld
voice_id = "..."                 # the saved voice at the service (written by keep; never shown to the listener)
model = "inworld-tts-2"          # optional; default from knowledge/services.toml
style = ""                       # leave empty: Gemini's API takes no style setting yet (checked live 2026-10-25)
made = "2026-10-25"

[voice]                          # what the services design from
who = "A woman in her thirties, a strength coach talking to one client"
sound = "Warm, mid-low, American accent, crisp diction"
energy = "Steady, calm authority"
pace = "Natural; brisk during work"
avoid = "Hype, shouting, announcer voice, sleepy delivery"

[character]                      # what the script writer follows; the brief quotes each line
tone = "Calm and focused; light humor now and then, no hype"
encouragement = "Notices the effort plainly, and says why a movement is there"
pushes = "Asks for one more only when form is clean; backs off at pain"
never_says = ["Crush it", "Beast mode", "No pain, no gain"]
sign_off = "Brief and warm; names one thing done well"
+++
- Notes: free notes on how this coach talks, as "- Label: text" lines (the brief quotes those).
```

The description a service designs from is `[voice]` joined in order: "who. sound. energy. Pace: pace. Avoid: avoid." `[character]` takes any `key = "text"` (or a list of texts). A stock local coach's `persona.md` has `kind = "local"`, `gender`, a `description`, `[local] engine = "pocket"`, `[voice]` and `[character]`, which the brief quotes the same way. `aliases` are older names that still find the coach: a migrated coach keeps its HarmonicFitness 0.8 voice names, so old log lines still name them.

`./harmonicfitness coaches` lists the coaches with where each speaks (`web · Fish Audio`, `local · pocket`), marks the one a build uses when none is named, and says which are stand-ins and which are made the first time they're used. `./harmonicfitness build` takes `--coach`. `./harmonicfitness coaches archive "<name>"` moves a coach of the listener's own to `.archive/`: out of the list, still found by name for old log lines, its voice left at the service (a stock coach can't be archived).

## Making a web coach

The `coach` skill runs it: **keys, describe, audition, approve and name, the stable.**

1. **Keys.** `./harmonicfitness keys` says which services have a key (never the key). Each key is the listener's own, pay-as-you-go: no subscription anywhere.
2. **Describe.** Claude writes the narrative, a file in `persona.md`'s format with `[voice]` and `[character]`, to `me/coaches/.auditions/<slug>.md`.
3. **Audition.** `./harmonicfitness coaches audition <narrative>` designs on every keyed service at once (asking Fish Audio for two candidates, ElevenLabs three, Gemini one, Inworld two; a service may return fewer, as Inworld once did live), each saying the coaching line below, and lands them in `me/coaches/.auditions/<date>-<n>/` as `<service>-<k>.wav` and `.mp3`, lettered A, B, C... in that service order, with each one's approximate cost a workout. A service that fails is one line; the others still land. `--services fish,gemini` auditions only those. Nothing is saved at Fish Audio, ElevenLabs or Inworld; Gemini stores each voice as it designs it (it has to), and is named "harmonicfitness audition <id> <letter>" there.
4. **Approve and name.** `./harmonicfitness coaches keep <audition>/<letter> --name "Coach Maya"` saves the voice at its service as "harmonicfitness Coach Maya" (Fish Audio a private model, ElevenLabs a voice in the account, Inworld a published voice; Gemini's is already stored), and writes the coach's folder with the candidate as `sample.mp3` and a pace estimated from it. Several candidates from one audition can each become a coach. `./harmonicfitness coaches forget-audition <audition>` then closes it: Gemini's voices not kept are deleted, and the folder is removed.
5. **The stable.** A workout uses a coach by name.

- **How they talk** is an edit to `[character]` or the notes: no audition, no cost.
- **How they sound** is a new audition on that coach's own service, from an edited `[voice]`: `./harmonicfitness coaches audition --coach "Coach Maya"`, then `keep <audition>/<letter> --name "Coach Maya"`, which replaces the voice and `sample.mp3` and clears the old voice's pace. `--replace-old` also deletes the old voice at the service (ask the listener first).
- A coach stays on the service that made it. The same description can make a second coach elsewhere.
- Never a voice that imitates a real person or a character. Fish Audio's public library is skipped for that reason: only 58 of its voices carry a license flag, and its most popular ones imitate celebrities and game announcers.

Describe the person and the role, not adjectives alone, and say what to avoid. The line every candidate and take says: "Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. Breathe out as you drive. That's the pace we want."

The descriptions that made HarmonicFitness 0.8's coaches (now Coach Julius and Coach Solo for the listener who had them):
- Coach Julius (formerly Chatterbox Coach): "A man in his forties with a low, warm baritone voice and an American accent. A seasoned personal trainer talking to one client: direct, encouraging and focused. No hype, nothing silly. Clear diction, natural pace."
- Coach Solo (formerly Qwen3 Coach): "A man in his thirties with a lower-moderate pitch and an American accent, like a cycling instructor in a focused moment: purposeful, motivating, confident, steady energy. Not shouting, not goofy. Crisp diction."
- Shortlisted, then removed: "A man in his late thirties with a deep, low-pitched, resonant voice and an American accent. An experienced strength coach: grounded, confident and steady. Motivates through calm authority, not excitement. Crisp, clear diction. Natural, even pace."

What didn't work: "upbeat, natural energy, like leading a class" came out goofy and high-pitched; "calm, relaxed, unhurried" came out sleepy, or far too slow.

## The web services

Checked 2026-10-25; the rates the cost estimate uses are in `knowledge/services.toml`, with that date. Every figure shown to the listener is approximate, and prices change. A workout is about 20,000 characters.

| Service | Billing (no subscription) | How a coach is made | Cost a workout | Status |
|---|---|---|---|---|
| Fish Audio | Prepaid credit, no minimum; by UTF-8 bytes | Designed (about $0.01 a design), then saved as a private model | About $0.30 (`s2.1-pro`) | Tried live |
| ElevenLabs | Free account (3 custom voices, a monthly allowance of about 10,000 characters, non-commercial), or prepaid pay-as-you-go ($5 minimum, lasts 12 months) | Designed (three previews, billed as their text), then saved in the account | About $1.60 (`eleven_v4`), $0.80 (`eleven_v4_turbo`) | Tried live on a Starter account; not yet tried on a Free account |
| Gemini (an AI Studio key, not Google Cloud) | Prepaid credit ($5 minimum); a free tier exists | Designed and stored in one call (a year, renewed by each use; 200 a project) | About $0.27 (`gemini-3.8-flash-tts`) until 2026-12-31, about $0.54 from 2027 | Tried live |
| Inworld | On-Demand: $0 a month, prepaid credit ($10 minimum) | Designed, then published in the workspace (100 custom voices) | About $0.50 (`inworld-tts-2`), $0.30 (`inworld-tts-2-flash`) | Tried live |

- **Fish Audio:** speech by the saved voice's ID, no clip sent. It takes no seed, so a re-render is a new take; the clip cache keeps what's rendered. Its older `s1` model retires 2026-12-31.
- **ElevenLabs:** gets each paragraph's real neighbors (`previous_text`, `next_text`) and a seed, for smoother joins. On Free, design is the only way to a voice (library voices are blocked from the API there), and each coach takes one of the 3 slots; deleting a coach's old voice (`--replace-old`) frees one. A key needs two permissions when it's made: Text to Speech, and Voices: write.
- **Gemini:** the API takes no style setting yet (every placement was refused, live, 2026-10-25), and an instruction in the text is read aloud, so `style` stays empty (`./harmonicfitness check` flags one) and the text goes as written. It pauses about a second after each short sentence, so it runs about 35 percent slower than the others, and the same line varied about 9 percent across three renders; pace is measured per coach, so the timing holds. Terms: the free tier's requests are used for training with human review; the terms say "not for consumer use"; 18 and over.
- **Inworld:** 2,000 characters a request (a longer paragraph is refused before sending), the previous paragraph sent as context for the join (unbilled), design limited to 2 a minute. Its design cost isn't published.

- **The key** lives in `me/.env` (`FISH_AUDIO_API_KEY`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `INWORLD_API_KEY`): `./harmonicfitness keys init <service>` adds the line and `./harmonicfitness keys open` opens the file in the system's editor, where the listener pastes the key. It's never committed or backed up, never printed (`./harmonicfitness keys` says only whether one is set), and read only by the engine as it sends. Claude Code is denied the file. On Claude Code on the web the key is an environment variable in the cloud environment's settings, and the service's host (`api.fish.audio`, `api.elevenlabs.io`, `generativelanguage.googleapis.com`, `api.inworld.ai`) goes on its network allowlist.
- **What goes to the service:** the description at design, and the workout's script at every build, which can mention the listener's injuries ("easy on that left knee"). Setup says so once, before the first web build, with Gemini's free-tier training.
- **Cost:** before sending, a build prints the characters it will send (only the paragraphs not already cached) and the approximate cost, and stops if that's over `cloud_max_chars` in `me/settings.toml` (30,000 by default). An audition prints each candidate's cost a workout. The build record logs the characters sent.
- **No rendering ahead:** `--follow` and `--clips-only` are refused for a web coach, since every re-render would be billed. Only the final build sends, after the lint and the menu check pass, a few requests at a time.
- **Failures:** rate limits and dropped connections are retried; a refused key, payment or quota stops the build with exit code 4. Clips already rendered stay cached, so a rerun sends only the rest. A web coach whose service has no key on this computer stops the build with exit code 64 and says how to add it.

Set aside on 2026-10-24 and 2026-10-25: MiniMax (clones deleted after a week unused), OpenAI (every model on its speech endpoint shuts down on 2027-01-06), Google Chirp 3 (allowlist only), Hume (its TTS API ends November 13, 2026), Resemble AI (hosted voices' commercial terms unclear), and services whose voices need a subscription to be original or are stock voices only. PlayHT shut down in July 2025.

## Local coaches

A route is how a local coach's workout becomes audio on this computer. The `render` setting in `me/settings.toml` lists the routes in order of preference (`["local"]`); a web coach always speaks through its own service and a local coach always renders locally, so it matters only with no coach to go by. `./harmonicfitness doctor` shows whether local voices work here.

| Computer | Engine | Speed (render time over speech time) |
|---|---|---|
| Apple Silicon Mac | Pocket TTS on PyTorch, the processor | About 0.15 (M5, 2026-10-26): a 30-minute workout in about five minutes |
| Windows or Linux, processor only | The same | About 0.43 (2026-10-26) |
| Windows or Linux with an NVIDIA card | The same on CUDA | About 0.29 on an RTX 2080 Super |
| Intel Mac (no PyTorch build), or under the memory or disk floor | None | A web coach instead |

**Pocket TTS** (Kyutai, `pocket-tts` 4.0.1, CC-BY 4.0) runs its public model, `kyutai/pocket-tts-without-voice-cloning` (about 0.6 GB, at a pinned revision, language config `english_2026-10`). The public model can't clone a recording, but it loads a saved voice state, so each stock coach ships one (`pocket.safetensors`): the maintainer made it once from the coach's clip with Kyutai's gated cloning model, which no listener needs or downloads, and no Hugging Face login is ever asked for. Pocket tries the gated model first when a login allows it, so the engine refuses that request and checks the model it got (`tools/engines.py`). A voice file belongs to the Pocket model and language config it was made with: a new Pocket means exporting all ten again (`tools/coachmaker/`).

Chosen by a blind listening test on 2026-10-26, Pocket against Chatterbox Turbo on each coach's voice: Pocket for six coaches, Turbo for three, one even. On the audio bench (HarmonicFitness 0.14.2; its results are in git history) Pocket never dropped a cue word in 176 takes and renders two to six times faster than Turbo, on every computer, in a third of the memory. Pocket copies the pace of the clip a voice was made from (about a tenth faster), so each clip was made at 135 to 175 words a minute.

The engine and the take checker are an optional part of the environment (the `cpu` or `cuda` extra), installed by `./harmonicfitness setup` only where the readiness check says it runs (`--local` asks for it). They download into `models/` at the repo root (git-ignored; it may be a symlink to a shared place, or set `HARMONICFITNESS_MODELS`), at the revisions `tools/voices.py` pins. `./harmonicfitness models` lists them, and the models older versions downloaded that nothing uses now (Chatterbox Turbo, Qwen3-TTS, the MLX recognizer), with their sizes, to delete. `HARMONICFITNESS_DEVICE=cpu` or `cuda` overrides where Pocket runs.

Every local take is heard by a speech recognizer, Parakeet TDT 0.6B v3 through ONNX (`istupakov/parakeet-tdt-0.6b-v3-onnx`, about 2.5 GB, CC-BY 4.0), the same on every computer: a take that drops a cue word, stalls, runs on or gets too many words wrong is rendered again with the next seed, up to four takes (`CLAUDE.md`, "The take check").

**Counts and cues.** A countdown spoken by a voice runs two or three times too fast to move to, and a one-word cue is the line a local voice garbles most. So each stock coach ships recorded counts (ten down to one) and cues (go, rest, switch, switch sides, stop, hold), made once on Pocket from the coach's voice, checked by the recognizer and approved by ear; a draft's `[count 5 go]` plays them a second apart, and `[cue rest]` plays one cue (`knowledge/tts-rules.md`, Pacing). They sound the same in every workout and on every computer.

**How the ten were made** (maintainer only, `tools/coachmaker/`, on an Apple Silicon Mac): Qwen3-TTS VoiceDesign 1.7B (Apache 2.0, through mlx-audio in its own environment) designed three or four takes of each coach reading one 63-word script, from the roster's description; the take approved by ear became `clip.wav`; the gated Pocket model exported it to `pocket.safetensors`; `cues.py` made the counts and cues and `sample.py` the sample, each approved by ear; `persona.py` writes each `persona.md` from the roster. Qwen3 doesn't make accents (asked for Scottish, southern English and Australian, every take came out without one), so no description asks for one; women's takes sometimes came out girlish and high, so every woman's description asks for an adult voice, low to medium in pitch. VoxCPM2 was tried as the designer and rejected by ear (2026-10-26).

Since 0.15.0 a listener can't design a local coach or bring a clip: a voice of their own is a web coach. Tried and dropped earlier: OmniVoice's gallery voices (mechanical), Kokoro (flat), Qwen3-TTS preset speakers (fine, but too slow), Chatterbox at 8-bit and 4-bit (no better than Turbo, and slower), and Chatterbox Turbo and Qwen3-TTS as the local engines (HarmonicFitness 0.9 to 14).

**Why a local script reads stiffer, and what didn't fix it** (2026-10-29, Coach Claire, five paragraphs from a real mobility script, each take heard by the recognizer). Pocket was trained on single sentences: it speaks a paragraph in chunks of about fifty tokens (`max_tokens`, a sentence or a few), each started fresh from the voice state, and Kyutai's own code calls this simplistic. A chunk of many short sentences comes out clipped and lost its tail ("Last few. Keep the shape."). Chunks of up to two hundred tokens looped ("the low bot, the low bot..."); carrying the state from one chunk into the next (`copy_state=False`) dropped whole sentences; a temperature of 0.6 over 0.3 looped worse. The 24-layer model in the same public repo (`english_2026-09_24l`) rendered about three times slower (0.31 of real time on an M5), dropped lines in both passages, and would need every coach's `pocket.safetensors` exported again through the gated model (the voice state is the 6-layer model's cache). The same content written as fuller sentences, cues joined with commas and "and", came through clean and sounded better by ear, so the fix went into the writing (`knowledge/tts-rules.md`, Local and web voices), not the engine.

Chatterbox Turbo was tried again the same evening (`chatterbox-tts` 0.1.7, PyTorch on the Mac's graphics chip, cloned from Coach Claire's `clip.wav`), on a full ten-minute script written to the new guidance. It read every line accurately on the first take, but it took about nine minutes to render the ten minutes against Pocket's two, and by ear it was fine but not materially better than Pocket. It stays dropped.

## Pace

No engine decides a clip's length in advance, so the lint predicts it from the coach's rate (in `pace.json`, recorded by every render) and the render lays segments on the plan's clock, ending a short one early and paying back a long one from the next. The whole workout is held within three percent of plan.

- **A web coach** starts from a pace estimated from its approved sample (the coaching line's weighted characters over its trimmed seconds), so its first workout needs no smoke test. The first real render replaces the estimate with measured pace, kept per service, model and voice; a new voice starts again from its sample.
- **A stock local coach** ships measured: its `pace.json` comes from its approved sample, and is read until this computer's first render with that coach, which adds to it in the shared `me/workouts/.audio-cache/voice-pace.json` (so `me/coaches/` holds only the listener's own coaches). A local coach without a measured pace (one from before 0.15.0) won't render a session (exit 3; `--allow-estimated` overrides); the smoke test, `./harmonicfitness build knowledge/smoke-test.draft.txt "smoke-test" --coach "<name>"`, measures one, and checks a computer end to end.
