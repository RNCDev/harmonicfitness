# Coaches and voices

A coach is a person the listener creates: a name ("Coach Maya", never a model's name), how they talk, and how they sound. The sound is a short reference clip with its exact words, which every engine copies for every line of the workout. It copies the clip's delivery as well as its sound: a sleepy clip clones sleepy, an announcer clip clones like an announcer. So the reference line is written the way a coach talks, and the clip is picked by ear.

A coach is not a tuned model. The models are used exactly as published; what makes a coach is the clip. Nothing ever renders from a description alone: a description makes takes, the listener keeps one, and that clip is the coach from then on, on every engine. One stand-in ships, Coach Demo (`me.example/personas/coach-demo/`, copied into a new `me/` by setup): sweatcast 8's Chatterbox Coach clip, a designed voice, with its pace measured on Chatterbox Turbo (MLX and PyTorch) and Fish Audio, so a new listener's first workout needs no design and no smoke test. Its `persona.md` says `placeholder = true`: `./sweatcast check` notes it, and a build with no coach named picks any other coach before it. Each listener makes their own when they like (the coach skill's quick coach is one question and one take), and can keep several.

## Where coaches live

Each coach is one folder in `me/personas/`, part of the private `me/` backup:

```
me/personas/coach-maya/
  persona.md     settings (name, aliases, description, one table per engine), then how the coach talks
  clip.wav       the sound: about ten seconds, 16-bit mono at 24 kHz
  clip.txt       exactly what the clip says
  pace.json      measured pace, one entry per engine and model, and each computer's render speed
  services.json  voice IDs a cloud service made from the clip, keyed by service and the clip's hash
  takes/         designed takes, before one is kept (not backed up)
```

`persona.md` opens with a TOML block, like the other context files:

```toml
+++
schema = 4
name = "Coach Maya"
aliases = []
description = "A woman in her thirties, warm and mid-low, a strength coach."

[local]
engine = "chatterbox"          # or qwen3 (clearest diction; renders locally only on a Mac)

[elevenlabs]
model = "eleven_multilingual_v2"

[deepgram]
voice = "aura-2-thalia-en"     # Deepgram has stock voices only
+++
## How this coach talks
- Tone: calm and focused. Keep humor light and occasional, with no hype.
- How the coach talks to me: ...
```

The prose under `## How this coach talks` is what the brief quotes for the writer, so two coaches can talk differently, not just sound different. The tables are optional; without one, an engine uses its default (`knowledge/services.toml` for the cloud services). `aliases` are older names that still find the coach: a migrated coach keeps its sweatcast 8 voice names, so old log lines still name them.

`./sweatcast coaches` lists the coaches and marks the one used last. A workout uses the coach used last (from the log), unless the listener names another or asks for a new one; with no sessions yet, it's the first. `./sweatcast build` takes `--coach` (`--voice` is the old name).

## How a workout becomes audio: routes

A route is local (this computer's own engine) or a cloud service with the listener's own key. The profile's `render` setting lists them in order of preference, say `["local", "fish"]`; each build takes the first that works on the computer it runs on, so one synced profile works on a fast Mac and on a laptop with no graphics card. `./sweatcast doctor` shows which routes work here and which a build would pick; `./sweatcast build --engine <route>` overrides the list for one build.

### Local engines

| Computer | Engine | Status |
|---|---|---|
| Apple Silicon Mac | Chatterbox Turbo or Qwen3-TTS through MLX (`mlx-audio`) | Tested |
| Windows with an NVIDIA card | Chatterbox Turbo, Resemble AI's PyTorch release on CUDA | Tested |
| Linux with an NVIDIA card | The same | Not yet tried |
| Windows or Linux without one | The same on the processor | Experimental, speed unknown, likely slow |
| Intel Mac, or under the memory or disk floor | None | A cloud voice instead |

The local engine is an optional part of the environment, installed by `./sweatcast setup` only where the readiness check says it runs (`--local` asks for it). The models download from Hugging Face into `models/` at the repo root (git-ignored; it may be a symlink to a shared place, or set `SWEATCAST_MODELS`), pinned to exact revisions in `tools/voices.py` (`LOCAL_MODELS`, plus Chatterbox Turbo's speech tokenizer). `./sweatcast models adopt` moves ones already in `~/.cache/huggingface/hub` instead of downloading again.

| Engine | Strength | Speed | Download |
|---|---|---|---|
| Chatterbox Turbo (`mlx-community/chatterbox-turbo-fp16`, with `mlx-community/S3TokenizerV2`) | Most natural, human delivery | About 0.7 times the speech's length on an M3 | About 3.3 GB |
| Qwen3-TTS (`mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16`) | Clearest diction | About 1.3 to 1.45 times on an M3 | About 4.2 GB |
| Chatterbox Turbo on PyTorch (`ResembleAI/chatterbox-turbo`) | The same model and clip, so very close to the Mac's; Resemble's package adds its inaudible Perth watermark | About 0.52 times on an RTX 2080 Super, after a 40-second load | About 4 GB |

On the processor, PyTorch renders Chatterbox Turbo too; how slowly depends on the computer, and nobody has measured it yet. The smoke test records this computer's render speed beside the pace, and the readiness check then quotes the expected time for a 30-minute workout, suggesting a cloud voice when it runs far past an hour. `SWEATCAST_DEVICE=cpu` or `cuda` overrides the choice.

The models aren't gated, so no Hugging Face account is needed (the "unauthenticated requests" warning is harmless), and once downloaded, rendering needs no network. Chatterbox Turbo is MIT upstream (its MLX build is tagged Apache 2.0) and Qwen3-TTS is Apache 2.0.

### Cloud voices

| Service | How the coach's clip travels | Designs coaches | Approx. cost a workout (20,000 characters) | Status |
|---|---|---|---|---|
| Fish Audio | Inline: the clip and its words go with every request | Yes, about $0.01 a design | About $0.30 | Tried live (2026-10-24) |
| ElevenLabs | Cloned once (Starter plan and up), kept by its voice ID | Yes | About $0.80 (Flash) to $1.60 (multilingual) | Not yet tried live |
| Cartesia | Cloned once (Pro plan), kept by its voice ID | No | About $1.00 | Not yet tried live |
| Deepgram Aura-2 | Doesn't: stock voices only, so the coach sounds different there | No | About $0.60 | Not yet tried live |

Prices change; `knowledge/services.toml` holds the rates the cost estimate uses, with the date they were checked, and every figure shown to the listener is marked approximate. PlayHT shut down in July 2025.

- **The key** lives in `me/.env` (`FISH_AUDIO_API_KEY`, `ELEVENLABS_API_KEY`, `CARTESIA_API_KEY`, `DEEPGRAM_API_KEY`), which `./sweatcast keys init <service>` makes and the listener pastes the key into. It's never committed or backed up, never printed (`./sweatcast keys` says only whether one is set), and read only by the engine as it sends. Claude Code is denied the file.
- **What goes to the service:** the script, which can mention the listener's injuries ("easy on that left knee"), and for the clip-copying services the coach's clip. Setup says so once, before the first cloud build.
- **Cost:** before sending, a build prints the characters it will send (only the paragraphs not already cached) and the approximate cost, and stops if that's over the profile's `cloud_max_chars` (30,000 by default). The build record logs the characters sent.
- **No rendering ahead:** `--follow` and `--clips-only` are refused on a cloud route, since every re-render would be billed. Only the final build sends, after the lint and the menu check pass. Requests run a few at a time instead.
- **Failures:** rate limits and dropped connections are retried; a refused key, payment or quota stops the build with exit code 4. Clips already rendered stay cached, so a rerun sends only the rest.
- **Clones:** ElevenLabs and Cartesia make their own voice from the clip on the first build and the ID is kept in the coach's `services.json`; a changed clip makes a new one. ElevenLabs asks the uploader to hold the rights to the voice: for a designed coach that's the listener, and for a recording of a real person it's that person's consent. No service's terms speak to AI-designed voices directly.
- **Joins:** ElevenLabs gets each paragraph's real neighbors (`previous_text`, `next_text`) for smoother delivery. Fish, Cartesia and Deepgram take no seed, so a re-render there is a new take; the clip cache keeps what's rendered.

### Pace

Neither a local nor a cloud engine decides a clip's length in advance, so the lint predicts it from the coach's measured rate on that engine (recorded by every render into the coach's `pace.json`) and the render lays segments on the plan's clock, ending a short one early and paying back a long one from the next. The whole workout is held within three percent of plan.

Each engine and model is measured on its own, by the smoke test: `./sweatcast build knowledge/smoke-test.draft.txt "smoke-test" --coach "<name>" --engine <route>` (about 1,000 characters on a cloud voice). Until then the lint assumes the median rate of the coaches already measured; a reference clip's own rate is a poor guess (for the clip sweatcast 8 shipped, about 30 percent slow), so `./sweatcast build` won't render a session for an unmeasured coach on a route (exit 3; `--allow-estimated` overrides).

## Creating a coach

The `coach` skill runs it: name the coach, describe how they sound and how they talk, render a few takes, listen, keep one, and say what's wrong if none is right. The takes come from the first designer that works here, or `--designer`:

1. **Local:** Qwen3-TTS VoiceDesign on MLX (`mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`, pinned, about 4.5 GB; delete it from `models/` when you're done), on an Apple Silicon Mac.
2. **Fish Audio** or **ElevenLabs** design, with the listener's key. The kept take becomes `clip.wav`, so it travels to every engine like any other clip.
3. **A clip the listener brings:** about ten seconds of a voice with its exact words. A real person's voice needs that person's consent.

There's no local designer on Windows or Linux: Qwen's own PyTorch package (`qwen-tts`) pins a transformers version that conflicts with Chatterbox's (checked 2026-10-24), so they can't share an environment.

```
./sweatcast coaches design "Coach Maya" "A woman in her thirties with a warm, mid-low voice and an American accent. An experienced strength coach: grounded, encouraging and steady. Calm authority, no hype. Crisp diction, natural pace." --play
./sweatcast coaches keep "me/personas/coach-maya/takes/2.wav"
./sweatcast build knowledge/smoke-test.draft.txt "smoke-test" --coach "Coach Maya"
```

- `--takes 3` makes more; `--seed` gives different takes of the same description; `--line` changes what they say. Earlier takes are kept, numbered on.
- `keep` writes `clip.wav` (converted to 24 kHz mono if it isn't), `clip.txt`, and for a new coach `persona.md` with the template's `## How this coach talks`, to fill in. `--engine qwen3` picks Qwen3 for local renders on a Mac; Chatterbox Turbo is the default and the most natural.
- A brought clip: `./sweatcast coaches keep my-recording.wav --name "Coach Sam" --words "exactly what it says"`.
- A Deepgram coach picks a stock voice: `./sweatcast coaches samples deepgram` renders a line in each, then `./sweatcast coaches set "<coach>" deepgram.voice <voice>`.

Describe the person and the role, not adjectives alone, and say what to avoid. The line the takes say: "Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. Breathe out as you drive. That's the pace we want."

The descriptions that made sweatcast 8's coaches (now Coach Julius and Coach Solo for the listener who had them):
- Coach Julius (formerly Chatterbox Coach): "A man in his forties with a low, warm baritone voice and an American accent. A seasoned personal trainer talking to one client: direct, encouraging and focused. No hype, nothing silly. Clear diction, natural pace."
- Coach Solo (formerly Qwen3 Coach): "A man in his thirties with a lower-moderate pitch and an American accent, like a cycling instructor in a focused moment: purposeful, motivating, confident, steady energy. Not shouting, not goofy. Crisp diction."
- Shortlisted, then removed: "A man in his late thirties with a deep, low-pitched, resonant voice and an American accent. An experienced strength coach: grounded, confident and steady. Motivates through calm authority, not excitement. Crisp, clear diction. Natural, even pace."

What didn't work: "upbeat, natural energy, like leading a class" came out goofy and high-pitched; "calm, relaxed, unhurried" came out sleepy, or far too slow.

Tried and dropped on 2026-10-20: OmniVoice's gallery voices (mechanical), Kokoro (flat), Qwen3-TTS preset speakers (fine, but too slow), VoxCPM2 (good but nearly four times real time), Chatterbox at 8-bit and 4-bit (no better than Turbo, and slower). Cloud services set aside on 2026-10-24: MiniMax (clones deleted after a week unused), OpenAI (custom voices need a recording of the human speaker), Google Chirp 3 (allowlist only), Hume (its TTS API ends November 13, 2026) and Resemble AI (hosted voices' commercial terms unclear).
