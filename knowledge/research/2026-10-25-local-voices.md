# Local voices: which open models, and how to keep their takes honest (2026-10-25)

This note covers open-weight text-to-speech models that run on an Apple Silicon Mac (here an M5 with 24 GB), and how to render, check and finish 20 to 45 minutes of one coach's voice. It doesn't cover web services (see `knowledge/voices.md`), and it ranks no model by listening yet. That is the bake-off's job.

**Source tags:**
- **[P]:** a primary source (model card, repo, paper, the installed mlx-audio code), opened during the research.
- **[S]:** secondhand.
- **[M]:** measured on this M5 on 2026-10-25.

## Measured: the two engines in use [M]

**The test:**
- **Lines:** six coaching lines (cue, story, countdown, effort call, form cue, cool-down), three seeds each.
- **Voice:** Coach Andy's reference clip.
- **Scoring:** each take transcribed by Parakeet TDT 0.6B v3 (mlx-audio), with digits read as words.

| | Chatterbox Turbo (fp16) | Qwen3-TTS 1.7B Base (bf16) |
|---|---|---|
| Takes with a word wrong | 5 of 18 | 1 of 18 |
| Render time ÷ audio length | about 0.5 | about 0.9 |
| Take-to-take level spread | about 4 dB RMS | about 4 dB RMS (and 3 to 4 dB louder overall) |

**The countdown "Three... two... one... and rest."** on Turbo:
- With the ellipses, it lost "and rest" in 3 takes of 5, seed 42 among them.
- Written "Three, two, one, and rest." or "Three. Two. One. And rest.", it lost nothing in 10 takes.

**Why the ellipsis matters [P]:**
- mlx-audio's Turbo `punc_norm` turns "…" into ", " and ":" into ",", but passes "..." through as is.
- Turbo ignores `exaggeration`, `cfg_weight` and `min_p`, and warns that it does (`chatterbox_turbo.py`).
- Turbo splits text over about 400 characters into sentences with no context between them. sweatcast's 22-second paragraph cap stays under that.

**What came of it:** 14.1.0's take check (`tools/verify.py`), clip leveling and compressor, and the lint's ellipsis rule.

## Candidates for the bake-off

All of these are in mlx-audio 0.5.0 unless noted. Speeds from elsewhere were measured on an M5 **Max**, so expect a base M5 to be slower.

| Model | License (weights) | Size | Voice | Why test it | Watch for |
|---|---|---|---|---|---|
| Higgs Audio v2 3B, q8 | Boson community license: commercial use under 100k annual users, with attribution [P] | about 6 GB | Clone from 5–15 s plus transcript | Strong emotion; repetition-avoiding sampling; 0.36 render ratio on an M5 Max [P, mlx-audio `docs/models/tts/higgs_audio.md`] | Keep the audio head bf16: quantizing it drifts the pitch [P] |
| MOSS-TTS Local v1.5 | Apache 2.0 [P] | 4.5B, 14.5 GB peak | Clone | Inline `[pause Ns]` and duration control; 0.49 on an M5 Max [P, mlx-audio PR 797] | Tight in 24 GB; long-form claims are the maker's own |
| Chatterbox Multilingual V3 | MIT [P] | about 0.7B | Clone | Turbo's family, with `exaggeration` back; claims fewer hallucinations [P] | No Mac speed published |
| Breeze TTS 2 | **Non-commercial** [P] | 3B | Design, clone, clone plus instruction | Second-best open model on the Artificial Analysis arena (1230) [P]; 0.61 on an M5 Max [P] | Personal use only |

**Leaderboard [P]** (https://artificialanalysis.ai/text-to-speech/leaderboard, opened 2026-10-25): open-weight entries are Fish Audio Drama 3 Preview 1246, Breeze TTS 2 1230, Ming-3.0-tts 1189, Fish Audio S2 Pro 1109, Voxtral TTS 1090, Kokoro 1063, Higgs Audio V3 1045 and Chatterbox (original) 1026.
- These are short clips in each model's own voices, which says nothing about a cloned voice over 30 minutes.
- Turbo, Qwen3-TTS (open weights), Higgs v2 and MOSS aren't on the board.

**Not now:**
- Fish Drama 3 needs more than 24 GB, and an open issue has takes falling silent.
- Ming-3.0 is days old and has an open runaway bug.
- Higgs v3 is non-commercial.
- VibeVoice adds background music and its code was pulled.
- Voxtral's open weights don't clone.
- TADA renders at about 4.7.
- Pocket TTS can't pause.
- These are ruled out by license: F5/E2, Llasa, MaskGCT, Spark-TTS, OuteTTS and S1-mini.
- These have no Mac path: IndexTTS 2 and CosyVoice 3.

## How the pipeline should work (practice)

**Check every take [S]:**
- Open audiobook tools transcribe each segment, retry with a new seed, and keep the fewest-errors take, because "by themselves, these models are unreliable at book scale" (https://github.com/zeropointnine/tts-audiobook-tool; https://github.com/petermg/Chatterbox-TTS-Extended).
- A fixed seed alone makes a bad take repeatable, not good.

**Short prompts misbehave on Chatterbox [S]:**
- Keep a clip above about five words (https://docs.nvidia.com/ace-for-games/chatterbox-tts/programming-guide-tts-chatterbox.html).
- This isn't enforced yet; a cue bank (fixed cue lines rendered once and checked) is a later option.

**Long single passes degrade [P, abstract]:**
- Qwen3-TTS "significantly deteriorates" on very long prompts (arXiv 2609.16989).
- Paragraph-sized clips with a check are the safe pattern.

**Loudness [P]:**
- Apple asks for about -16 LKFS, with the true peak at -1 dBFS or lower (https://podcasters.apple.com/support/audio-requirements).
- ffmpeg's `loudnorm` measures mono as mono unless `dual_mono` is set. Auphonic suggests -19 for mono [S].
- sweatcast stays at -16, louder, for use over gym noise.

**Quantizing [S]:**
- Qwen3 1.7B at 4-bit kept a 3.47% round-trip WER on an M5 Pro (https://soniqo.audio/benchmarks); the 0.6B degrades sharply.
- No published numbers exist for a quantized Chatterbox Turbo, so measure before switching.

## Not confirmed

- Every candidate's speed on a base M5.
- Any independent 30-minute stability test of an open model: the long-form claims are all the makers' own.
- Whether Fish Drama 3 at 3-bit runs in 24 GB.
- How speaker-similarity models (ECAPA, WavLM) and MOS predictors (UTMOS) perform on Apple Silicon.
- Any evidence for room tone over digital silence in rests.
