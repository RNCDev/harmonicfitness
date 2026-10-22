# Voices

A voice is a short reference clip plus its transcript. The engine clones it for every line of the workout, and it copies the clip's delivery as well as its sound: a sleepy clip clones sleepy, an announcer clip clones like an announcer. So the reference line is written the way a coach talks, and the clip is picked by ear.

A voice is not a tuned model. The models are used exactly as published; what makes a voice is its clip. The shipped voices are named for the model that speaks them and their role (Chatterbox Coach, Qwen3 Coach), so a second voice on the same model gets a name of its own beside it (Chatterbox Calm, say). They were called Coach E and Coach G before 1.1.0, after the design takes they came from; those names still work as aliases.

## Where voices live

Three files per voice, in `voices/` for the voices that ship with sweatcast, or in `me/voices/` for private ones (a voice cloned from a real person belongs there, never in the public repo; `me/voices/` wins a name clash):
- `<name>.wav`: the reference clip, about ten seconds.
- `<name>.txt`: exactly what the clip says.
- `<name>.json`: the engine, `"chatterbox"` or `"qwen3"`; the `"model"` (a Hugging Face repo; without one, the engine's standard build); the `"revision"`, the model's commit on Hugging Face, so every copy of sweatcast renders with the same weights; and optionally `"generate"`, extra settings passed to the engine for every clip, such as `{"exaggeration": 0.55, "cfg_weight": 0.5}` for the full-size Chatterbox. Chatterbox Turbo ignores `exaggeration` and `cfg_weight`. Changing any of these re-renders the voice's clips instead of reusing cached ones. Those top-level settings are the Mac's (MLX); `"torch"` holds the Windows PC's PyTorch model and revision (and its own `"generate"` if any), for an engine that has one.

For example, Chatterbox Coach:

```json
{"engine": "chatterbox", "model": "mlx-community/chatterbox-turbo-fp16",
 "revision": "b2d0a13aa7cfff0a06d9acb247ae91c8f19a6d75",
 "torch": {"model": "ResembleAI/chatterbox-turbo",
           "revision": "749d1c1a46eb10492095d68fbcf55691ccf137cd"}}
```

`./sweatcast voices` lists the voices with their engine, measured pace and model. `./sweatcast setup` downloads the default voice's model at its pinned revision (`--all` for every voice), and `./sweatcast voices download "<name>"` fetches one.

## Engines

On a Mac both run on Apple Silicon through `mlx-audio`, in the project's own Python environment (`.venv`, made by `./sweatcast setup` from `uv.lock`). Their weights download from Hugging Face into `~/.cache/huggingface/hub`, shared with other apps; Chatterbox Turbo also loads a speech tokenizer (`mlx-community/S3TokenizerV2`), pinned in `tools/voices.py`.

On a Windows PC with an NVIDIA GPU, Chatterbox Turbo runs from Resemble AI's own PyTorch release (`chatterbox-tts`, on CUDA 12.4 builds of PyTorch 2.6), with the original weights (`ResembleAI/chatterbox-turbo`, about 4 GB, everything in one repo). It's the same model from the same reference clip, so the voice sounds very close to the Mac's, though not identical, and Resemble's package adds its inaudible Perth watermark to each clip. Each voice's pace is measured separately per model, so the Windows voice needs its own smoke test. Qwen3-TTS and voice design are Mac-only for now: on Windows a Qwen3 voice still lints, and its render says to pick a Chatterbox voice. `tools/voices.py` picks the backend from the system; `SWEATCAST_BACKEND=mlx` or `torch` overrides it.

| Engine | Strength | Speed on an M3 with 16 GB |
|---|---|---|
| Chatterbox Turbo (`mlx-community/chatterbox-turbo-fp16`), used by Chatterbox Coach | Most natural, human delivery | About 0.7 times the speech's length |
| Chatterbox (`mlx-community/Chatterbox-TTS-fp16`), the full-size model | Sounds as good as Turbo; also takes an expressiveness setting | About 1.8 times |
| Qwen3-TTS (`mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16`), used by Qwen3 Coach | Clearest diction | About 1.3 to 1.45 times |

On Windows, Chatterbox Turbo on an RTX 2080 Super (8 GB) rendered at about 0.52 times the speech's length, after a model load of about forty seconds.

Neither decides a clip's length in advance, so the lint predicts it from each voice's measured rate (recorded by every render) and the render lays segments on the plan's clock, ending a short one early and paying back a long one from the next. The whole workout is held within three percent of plan.

Until a voice's first render, the lint assumes the median rate of the voices already measured (both coach voices measure about 14.6 to 14.8 weighted characters a second). A reference clip's own rate is a poor guess: for Chatterbox Coach it said 10.3, about 30 percent slow, which would script a session a third short. So `./sweatcast build` won't render a session with an unmeasured voice; render the smoke test with it first.

Chatterbox Turbo encodes the reference clip once per render and reuses it for every clip (it takes about half a second each time). The full-size Chatterbox and Qwen3 are given the clip on every call, since the full-size model forgets it between calls and Qwen3 caches it internally. There's no quantized Turbo build on Hugging Face; the 8-bit and 4-bit builds of the full-size model were slower than Turbo.

Tried and dropped on 2026-10-20: OmniVoice's gallery voices (mechanical; OmniVoice support was removed in 1.0.0), Kokoro (flat), Qwen3-TTS preset speakers (fine, but Ryan far too slow), VoxCPM2 (good but nearly four times real time), Chatterbox at 8-bit and 4-bit (no better than Turbo, and slower).

## Downloading the models

Model weights never go in git. They download once from Hugging Face into `~/.cache/huggingface/hub`, shared with any other app that uses the same models:

| Voice | Downloads | Size |
|---|---|---|
| Chatterbox Coach | `mlx-community/chatterbox-turbo-fp16` and its speech tokenizer, `mlx-community/S3TokenizerV2` | About 3.3 GB |
| Qwen3 Coach | `mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16` | About 4.2 GB |
| Chatterbox Coach, on Windows | `ResembleAI/chatterbox-turbo` | About 4 GB |

- **When:** `./sweatcast setup` fetches the default voice's model (the first of the voices in `me/profile.md`'s settings); `--all` fetches every voice's, and rerunning it after changing the default fetches the new one. `./sweatcast voices download "<name>"` fetches one voice. A voice whose model isn't there yet downloads it on its first render, so a smoke test can take several minutes the first time.
- **No account:** the models aren't gated, so no Hugging Face account or token is needed. The "unauthenticated requests" warning during a download is harmless; setting `HF_TOKEN` only makes downloads faster.
- **Pinned:** each voice downloads the revision its `.json` names, and Chatterbox's tokenizer the revision `tools/voices.py` pins, so every copy of sweatcast renders with the same weights. A render stops with a clear message if a pinned file can't be fetched, rather than carrying on with the wrong one.
- **Offline:** once downloaded, rendering needs no network.
- **Freeing space:** delete a model's folder under `~/.cache/huggingface/hub` (they're named `models--<owner>--<repo>`) when no voice you use needs it; it downloads again if a voice asks for it.
- **Licenses:** Chatterbox Turbo is MIT upstream (its MLX build is tagged Apache 2.0) and Qwen3-TTS is Apache 2.0; both allow this use. See the README.

## How the coach voices were made

Qwen3-TTS's VoiceDesign model (`mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`, about 4.5 GB, deleted after use; it downloads again if needed) reads one coaching line in a voice built from a description. Two takes per description, then the best take is kept as the reference.

The line: "Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. Breathe out as you drive. That's the pace we want."

The descriptions that worked:
- Coach D (shortlisted, then removed): "A man in his late thirties with a deep, low-pitched, resonant voice and an American accent. An experienced strength coach: grounded, confident and steady. Motivates through calm authority, not excitement. Crisp, clear diction. Natural, even pace."
- Chatterbox Coach: "A man in his forties with a low, warm baritone voice and an American accent. A seasoned personal trainer talking to one client: direct, encouraging and focused. No hype, nothing silly. Clear diction, natural pace."
- Qwen3 Coach: "A man in his thirties with a lower-moderate pitch and an American accent, like a cycling instructor in a focused moment: purposeful, motivating, confident, steady energy. Not shouting, not goofy. Crisp diction."

What didn't: "upbeat, natural energy, like leading a class" came out goofy and high-pitched; "calm, relaxed, unhurried" came out sleepy, or far too slow.

## Design a voice

`./sweatcast voices design` does what's described above in one command: it loads Qwen3-TTS VoiceDesign (`mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`, pinned in `tools/voices.py`, about 4.5 GB the first time), renders two takes of the coaching line in a voice made from your description, and saves them in `me/voices/.takes/`. Only one model runs at a time, so a design waits for a render that's going.

```
./sweatcast voices design "Coach Maya" "A woman in her thirties with a warm, mid-low voice and an American accent. An experienced strength coach: grounded, encouraging and steady. Calm authority, no hype. Crisp diction, natural pace." --play
./sweatcast voices keep "me/voices/.takes/Coach Maya-2.wav" --engine chatterbox --default
./sweatcast build voices/smoke-test.draft.txt "smoke-test" --voice "Coach Maya"
```

- `--play` plays each take (macOS `afplay`); `--takes 3` makes more; `--seed` gives different takes of the same description; `--line` changes what they say.
- `keep` copies the take to `me/voices/<name>.wav` with its words in `.txt`, writes the `.json` with the engine you choose at the same model and revision as the shipped voice on that engine, and adds the voice to your profile's settings (`--default` lists it first). `--engine chatterbox` (Turbo) gives the most natural delivery and renders fastest; `--engine qwen3` the clearest diction.
- Describe the person and the role, not adjectives alone, and say what to avoid. What worked and what didn't for the coach voices is above.
- The smoke test measures the new voice's pace, which session builds need.
- When you're done designing, the design model can be deleted from `~/.cache/huggingface/hub` (`models--mlx-community--Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`); it downloads again if you design another voice.

## Make a new one by hand

1. Record ten to fifteen seconds of a real person (only yourself, or someone who has agreed) reading a coaching line in a quiet room, or design takes as above.
2. Save the clip as `<name>.wav` with its exact words in `<name>.txt` beside it, then `./sweatcast voices keep <name>.wav --engine chatterbox` (it writes the `.json` and adds the voice to your profile). Or write the three files in `me/voices/` yourself (copy a shipped voice's `.json`) and add a `[[voices]]` entry to the settings at the top of `me/profile.md`; the first listed is the default. A synthetic voice worth sharing can go in `voices/` instead, in a pull request.
3. Render the smoke test with it: `./sweatcast build voices/smoke-test.draft.txt "smoke-test" --voice "<name>"`. The first render downloads the engine's weights if needed and records the voice's pace. Session builds refuse the voice until this has run (exit code 3); `--allow-estimated` overrides that.
