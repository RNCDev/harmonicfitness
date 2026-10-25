# Coaches and voices

A coach is a person the listener creates: a name ("Coach Maya", never a model's or a service's name), how they talk, and how they sound. There are two kinds, set by `kind` in the coach's `persona.md`:

- **A web coach** (`kind = "web"`): an original voice a web service designed from the listener's description and saved in the listener's own account there (Fish Audio, ElevenLabs, Gemini or Inworld). It speaks only through that service, by its saved voice, and a service's voice is the same voice on every request, so the coach sounds like the same person from session to session. It's never copied from a recording.
- **A local coach** (`kind = "local"`): a short reference clip with its exact words, which every local engine copies for every line. It copies the clip's delivery as well as its sound (a sleepy clip clones sleepy, an announcer clip like an announcer), so the clip is picked by ear. A local coach renders only locally.

A coach is not a tuned model: the models are used exactly as published. Each listener makes their own when they like (the coach skill), and can keep several.

**Stand-ins.** The template ships five, all `placeholder = true` (`./sweatcast check` notes them, and a build with no coach named picks the listener's own coach before any of them):
- **Coach Demo** (`me.example/personas/coach-demo/`), the local stand-in: sweatcast 8's public Chatterbox Coach clip, a designed voice, with its pace measured on Chatterbox Turbo (MLX and PyTorch), so a first local workout needs no design and no smoke test.
- **Four default web coaches**, one per service, all from one description (a man in his forties, a low, warm baritone, a seasoned trainer): Coach Reed (Fish Audio), Coach Ellis (ElevenLabs), Coach Nolan (Gemini) and Coach Owen (Inworld). None can ship ready, since a designed voice belongs to the account that made it, so each ships with `pending = "design"` and no voice. The first build that needs one designs its voice from the description, saves the first candidate in the listener's account (no audition), and says so first: about $0.01 on Fish Audio and Gemini; Inworld doesn't publish its design cost; on ElevenLabs it uses one of the account's custom voice slots (Free keeps 3). `./sweatcast coaches make "<name>"` does the same by hand; `--lint-only` never makes one.

With no coach named, a build takes the coach used last (from the log); with none yet, the listener's own coach; else the first stand-in that can speak here (a web default whose service has a key, in the order above, then Coach Demo where local voices run). If the coach used last has been archived, it stops and asks for a coach by name.

## Where coaches live

Each coach is one folder in `me/personas/`, part of the private `me/` backup:

```
me/personas/coach-maya/        a web coach
  persona.md     settings ([voice], [character]) and free notes
  sample.mp3     the approved audition candidate
  pace.json      pace, one entry per service, model and voice

me/personas/coach-sam/         a local coach
  persona.md     settings (one table per engine), then how the coach talks
  clip.wav       the sound: about ten seconds, 16-bit mono at 24 kHz
  clip.txt       exactly what the clip says
  pace.json      measured pace, one entry per engine and model, and each computer's render speed
  takes/         designed takes, before one is kept (not backed up)

me/personas/.auditions/        auditions in progress (not backed up)
me/personas/.archive/          coaches no longer in use (backed up; old log lines still find them)
```

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

The description a service designs from is `[voice]` joined in order: "who. sound. energy. Pace: pace. Avoid: avoid." `[character]` takes any `key = "text"` (or a list of texts). A local coach's `persona.md` has `kind = "local"`, a `description`, an optional `[local] engine` table (`chatterbox`, or `qwen3` for the clearest diction, on a Mac only), and its talk under `## How this coach talks`, which the brief quotes the same way. `aliases` are older names that still find the coach: a migrated coach keeps its sweatcast 8 voice names, so old log lines still name them.

`./sweatcast coaches` lists the coaches with where each speaks (`web · Fish Audio`, `local · chatterbox`), marks the one a build uses when none is named, and says which are stand-ins and which are made the first time they're used. `./sweatcast build` takes `--coach` (`--voice` is the old name). `./sweatcast coaches archive "<name>"` moves a coach to `.archive/`: out of the list, still found by name for old log lines, its voice left at the service.

## Making a web coach

The `coach` skill runs it: **keys, describe, audition, approve and name, the stable.**

1. **Keys.** `./sweatcast keys` says which services have a key (never the key). Each key is the listener's own, pay-as-you-go: no subscription anywhere.
2. **Describe.** Claude writes the narrative, a file in `persona.md`'s format with `[voice]` and `[character]`, to `me/personas/.auditions/<slug>.md`.
3. **Audition.** `./sweatcast coaches audition <narrative>` designs on every keyed service at once (Fish Audio two candidates, ElevenLabs three, Gemini one, Inworld two), each saying the coaching line below, and lands them in `me/personas/.auditions/<date>-<n>/` as `<service>-<k>.wav` and `.mp3`, lettered A, B, C... in that service order, with each one's approximate cost a workout. A service that fails is one line; the others still land. `--services fish,gemini` auditions only those. Nothing is saved at Fish Audio, ElevenLabs or Inworld; Gemini stores each voice as it designs it (it has to), and is named "sweatcast audition <id> <letter>" there.
4. **Approve and name.** `./sweatcast coaches keep <audition>/<letter> --name "Coach Maya"` saves the voice at its service as "sweatcast Coach Maya" (Fish Audio a private model, ElevenLabs a voice in the account, Inworld a published voice; Gemini's is already stored), and writes the coach's folder with the candidate as `sample.mp3` and a pace estimated from it. Several candidates from one audition can each become a coach. `./sweatcast coaches forget-audition <audition>` then closes it: Gemini's voices not kept are deleted, and the folder is removed.
5. **The stable.** A workout uses a coach by name.

- **How they talk** is an edit to `[character]` or the notes: no audition, no cost.
- **How they sound** is a new audition on that coach's own service, from an edited `[voice]`: `./sweatcast coaches audition --coach "Coach Maya"`, then `keep <audition>/<letter> --name "Coach Maya"`, which replaces the voice and `sample.mp3` and clears the old voice's pace. `--replace-old` also deletes the old voice at the service (ask the listener first).
- A coach stays on the service that made it. The same description can make a second coach elsewhere.
- Never a voice that imitates a real person or a character. Fish Audio's public library is skipped for that reason: only 58 of its voices carry a license flag, and its most popular ones imitate celebrities and game announcers.

Describe the person and the role, not adjectives alone, and say what to avoid. The line every candidate and take says: "Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. Breathe out as you drive. That's the pace we want."

The descriptions that made sweatcast 8's coaches (now Coach Julius and Coach Solo for the listener who had them):
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
- **Gemini:** the API takes no style setting yet (every placement was refused, live, 2026-10-25), and an instruction in the text is read aloud, so `style` stays empty (`./sweatcast check` flags one) and the text goes as written. It pauses about a second after each short sentence, so it runs about 35 percent slower than the others, and the same line varied about 9 percent across three renders; pace is measured per coach, so the timing holds. Terms: the free tier's requests are used for training with human review; the terms say "not for consumer use"; 18 and over.
- **Inworld:** 2,000 characters a request (a longer paragraph is refused before sending), the previous paragraph sent as context for the join (unbilled), design limited to 2 a minute. Its design cost isn't published.

- **The key** lives in `me/.env` (`FISH_AUDIO_API_KEY`, `ELEVENLABS_API_KEY`, `GEMINI_API_KEY`, `INWORLD_API_KEY`): `./sweatcast keys init <service>` adds the line and `./sweatcast keys open` opens the file in the system's editor, where the listener pastes the key. It's never committed or backed up, never printed (`./sweatcast keys` says only whether one is set), and read only by the engine as it sends. Claude Code is denied the file. On Claude Code on the web the key is an environment variable in the cloud environment's settings, and the service's host (`api.fish.audio`, `api.elevenlabs.io`, `generativelanguage.googleapis.com`, `api.inworld.ai`) goes on its network allowlist.
- **What goes to the service:** the description at design, and the workout's script at every build, which can mention the listener's injuries ("easy on that left knee"). Setup says so once, before the first web build, with Gemini's free-tier training.
- **Cost:** before sending, a build prints the characters it will send (only the paragraphs not already cached) and the approximate cost, and stops if that's over the profile's `cloud_max_chars` (30,000 by default). An audition prints each candidate's cost a workout. The build record logs the characters sent.
- **No rendering ahead:** `--follow` and `--clips-only` are refused for a web coach, since every re-render would be billed. Only the final build sends, after the lint and the menu check pass, a few requests at a time.
- **Failures:** rate limits and dropped connections are retried; a refused key, payment or quota stops the build with exit code 4. Clips already rendered stay cached, so a rerun sends only the rest. A web coach whose service has no key on this computer stops the build with exit code 64 and says how to add it.

Set aside on 2026-10-24 and 2026-10-25: MiniMax (clones deleted after a week unused), OpenAI (every model on its speech endpoint shuts down on 2027-01-06), Google Chirp 3 (allowlist only), Hume (its TTS API ends November 13, 2026), Resemble AI (hosted voices' commercial terms unclear), and services whose voices need a subscription to be original or are stock voices only. PlayHT shut down in July 2025.

## Local coaches (unchanged until the local redesign)

A route is how a local coach's workout becomes audio on this computer. The profile's `render` setting lists the local engines in order of preference (`["local"]`); a web coach ignores it. `./sweatcast doctor` shows whether local voices work here.

| Computer | Engine | Status |
|---|---|---|
| Apple Silicon Mac | Chatterbox Turbo or Qwen3-TTS through MLX (`mlx-audio`) | Tested |
| Windows with an NVIDIA card | Chatterbox Turbo, Resemble AI's PyTorch release on CUDA | Tested |
| Linux with an NVIDIA card | The same | Not yet tried |
| Windows or Linux without one | The same on the processor | Experimental, speed unknown, likely slow |
| Intel Mac, or under the memory or disk floor | None | A web coach instead |

The local engine is an optional part of the environment, installed by `./sweatcast setup` only where the readiness check says it runs (`--local` asks for it). The models download from Hugging Face into `models/` at the repo root (git-ignored; it may be a symlink to a shared place, or set `SWEATCAST_MODELS`), pinned to exact revisions in `tools/voices.py` (`LOCAL_MODELS`, plus Chatterbox Turbo's speech tokenizer). `./sweatcast models adopt` moves ones already in `~/.cache/huggingface/hub` instead of downloading again.

| Engine | Strength | Speed | Download |
|---|---|---|---|
| Chatterbox Turbo (`mlx-community/chatterbox-turbo-fp16`, with `mlx-community/S3TokenizerV2`) | Most natural, human delivery | About 0.7 times the speech's length on an M3 | About 3.3 GB |
| Qwen3-TTS (`mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16`) | Clearest diction | About 1.3 to 1.45 times on an M3 | About 4.2 GB |
| Chatterbox Turbo on PyTorch (`ResembleAI/chatterbox-turbo`) | The same model and clip, so very close to the Mac's; Resemble's package adds its inaudible Perth watermark | About 0.52 times on an RTX 2080 Super, after a 40-second load | About 4 GB |

On the processor, PyTorch renders Chatterbox Turbo too; how slowly depends on the computer, and nobody has measured it yet. The smoke test records this computer's render speed beside the pace, and the readiness check then quotes the expected time for a 30-minute workout, suggesting a web coach when it runs far past an hour. `SWEATCAST_DEVICE=cpu` or `cuda` overrides the choice.

The models aren't gated, so no Hugging Face account is needed (the "unauthenticated requests" warning is harmless), and once downloaded, rendering needs no network. Chatterbox Turbo is MIT upstream (its MLX build is tagged Apache 2.0) and Qwen3-TTS is Apache 2.0.

### Making a local coach

The takes come from the local designer, or the listener brings a clip:

1. **Local:** Qwen3-TTS VoiceDesign on MLX (`mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`, pinned, about 4.5 GB; delete it from `models/` when you're done), on an Apple Silicon Mac.
2. **A clip the listener brings:** about ten seconds of a voice with its exact words. A real person's voice needs that person's consent.

There's no local designer on Windows or Linux: Qwen's own PyTorch package (`qwen-tts`) pins a transformers version that conflicts with Chatterbox's (checked 2026-10-24), so they can't share an environment. There, a web coach, or a brought clip.

```
./sweatcast coaches design "Coach Sam" "A man in his forties with a low, warm baritone voice and an American accent. A seasoned personal trainer: direct, encouraging and focused. No hype. Clear diction, natural pace." --play
./sweatcast coaches keep "me/personas/coach-sam/takes/2.wav"
./sweatcast build knowledge/smoke-test.draft.txt "smoke-test" --coach "Coach Sam"
```

- `--takes 3` makes more; `--seed` gives different takes of the same description; `--line` changes what they say. Earlier takes are kept, numbered on.
- `keep` writes `clip.wav` (converted to 24 kHz mono if it isn't), `clip.txt`, and for a new coach `persona.md` with the template's `## How this coach talks`, to fill in. `--engine qwen3` picks Qwen3 for local renders on a Mac; Chatterbox Turbo is the default and the most natural.
- A brought clip: `./sweatcast coaches keep my-recording.wav --name "Coach Sam" --words "exactly what it says"`.

Tried and dropped on 2026-10-20: OmniVoice's gallery voices (mechanical), Kokoro (flat), Qwen3-TTS preset speakers (fine, but too slow), VoxCPM2 (good but nearly four times real time), Chatterbox at 8-bit and 4-bit (no better than Turbo, and slower).

## Pace

No engine decides a clip's length in advance, so the lint predicts it from the coach's rate (in `pace.json`, recorded by every render) and the render lays segments on the plan's clock, ending a short one early and paying back a long one from the next. The whole workout is held within three percent of plan.

- **A web coach** starts from a pace estimated from its approved sample (the coaching line's weighted characters over its trimmed seconds), so its first workout needs no smoke test. The first real render replaces the estimate with measured pace, kept per service, model and voice; a new voice starts again from its sample.
- **A local coach** is measured on each engine and model by the smoke test: `./sweatcast build knowledge/smoke-test.draft.txt "smoke-test" --coach "<name>"`. Until then the lint assumes the median rate of the coaches already measured; a reference clip's own rate is a poor guess (for the clip sweatcast 8 shipped, about 30 percent slow), so `./sweatcast build` won't render a session for an unmeasured local coach (exit 3; `--allow-estimated` overrides).
