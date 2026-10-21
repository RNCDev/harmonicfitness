# Voices

A voice is a short reference clip plus its transcript. The engine clones it for every line of the workout, and it copies the clip's delivery as well as its sound: a sleepy clip clones sleepy, an announcer clip clones like an announcer. So the reference line is written the way a coach talks, and the clip is picked by ear.

## Where voices live

`voices/` in this repo, three files per voice:
- `<name>.wav`: the reference clip, about ten seconds.
- `<name>.txt`: exactly what the clip says.
- `<name>.json`: the engine, `{"engine": "chatterbox"}` or `{"engine": "qwen3"}`, and optionally `"model"` (a Hugging Face repo) to use a different build of that engine and `"generate"`, extra settings passed to the engine for every clip, such as `{"exaggeration": 0.55, "cfg_weight": 0.5}` for the full-size Chatterbox. Chatterbox Turbo ignores `exaggeration` and `cfg_weight`. Changing any of these re-renders the voice's clips instead of reusing cached ones.

`python3 tools/voices.py` lists them with their engine and measured pace. Voices saved in the VoiceStudio app also still work, rendered with OmniVoice, but they sounded mechanical next to these.

## Engines

Both run on this Mac through `mlx-audio` in VoiceStudio's bundled Python. Their weights download from Hugging Face on first use into `~/.cache/huggingface/hub`.

| Engine | Strength | Speed on this M3 |
|---|---|---|
| Chatterbox Turbo (`mlx-community/chatterbox-turbo-fp16`), Coach E's default | Most natural, human delivery | About 0.7 times the speech's length |
| Chatterbox (`mlx-community/Chatterbox-TTS-fp16`), the full-size model | Sounds as good as Turbo; also takes an expressiveness setting | About 1.8 times |
| Qwen3-TTS (`mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16`) | Clearest diction | About 1.45 times |

Neither decides a clip's length in advance, so the lint predicts it from each voice's measured rate (recorded by every render) and the render pads or borrows a little from the next segment. Expect each segment within a few percent of plan.

Until a voice's first render, the lint assumes the median rate of the voices already measured (both coach voices measure about 14.6 to 14.8 weighted characters a second). A reference clip's own rate is a poor guess: for Coach E it said 10.3, about 30 percent slow, which would script a session a third short. So `tools/build.sh` won't render a session with an unmeasured voice; render the smoke test with it first.

Chatterbox Turbo encodes the reference clip once per render and reuses it for every clip (it takes about half a second each time). The full-size Chatterbox and Qwen3 are given the clip on every call, since the full-size model forgets it between calls and Qwen3 caches it internally. There's no quantized Turbo build on Hugging Face; the 8-bit and 4-bit builds of the full-size model were slower than Turbo.

Tried and dropped on 2026-10-20: the VoiceStudio Gallery voices on OmniVoice (mechanical), Kokoro (flat), Qwen3-TTS preset speakers (fine, but Ryan far too slow), VoxCPM2 (good but nearly four times real time), Chatterbox at 8-bit and 4-bit (no better than Turbo, and slower).

## How the coach voices were made

Qwen3-TTS's VoiceDesign model (`mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16`, about 4 GB, deleted after use; it downloads again if needed) reads one coaching line in a voice built from a description. Two takes per description, then the best take is kept as the reference.

The line: "Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. Breathe out as you drive. That's the pace we want."

The descriptions that worked:
- Coach D (shortlisted, then removed): "A man in his late thirties with a deep, low-pitched, resonant voice and an American accent. An experienced strength coach: grounded, confident and steady. Motivates through calm authority, not excitement. Crisp, clear diction. Natural, even pace."
- Coach E: "A man in his forties with a low, warm baritone voice and an American accent. A seasoned personal trainer talking to one client: direct, encouraging and focused. No hype, nothing silly. Clear diction, natural pace."
- Coach G: "A man in his thirties with a lower-moderate pitch and an American accent, like a cycling instructor in a focused moment: purposeful, motivating, confident, steady energy. Not shouting, not goofy. Crisp diction."

What didn't: "upbeat, natural energy, like leading a class" came out goofy and high-pitched; "calm, relaxed, unhurried" came out sleepy, or far too slow.

## Make a new one

1. Design takes as above, or record ten to fifteen seconds of a real person (only yourself, or someone who has agreed) reading a coaching line in a quiet room.
2. Save the clip as `voices/<name>.wav`, its words as `voices/<name>.txt`, and the engine as `voices/<name>.json`.
3. Add it under Voices in `profile.md`; the first listed is the default.
4. Render the smoke test with it: `tools/build.sh workouts/drafts/smoke-test.draft.txt "smoke-test" --voice "<name>"`. The first render downloads the engine's weights if needed and records the voice's pace. Session builds refuse the voice until this has run (exit code 3); `ALLOW_ESTIMATED=1` overrides that.
