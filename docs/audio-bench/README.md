# Audio bench

The audio bench reads one five-minute workout script with each candidate local voice model, on a Mac and on a PC. It measures and scores every take the same way on both, so we can choose the next local voice on evidence. Nothing a workout uses changes.

## Running it

| Say | On | Runs |
|---|---|---|
| "run the MAC audio test harness" | The Apple Silicon Mac | `./sweatcast bench`, then commits `docs/audio-bench/results/<date>-mac/` and pushes |
| "run the PC audio test harness" | The Windows PC (Git Bash), after `git pull` | `./sweatcast bench`, then commits `docs/audio-bench/results/<date>-pc/` and pushes |

**Run order:**
- Run `./sweatcast bench --quick` first: three lines and one seed, in a few minutes. It confirms that every model installs and speaks on this computer.
- Then run the full bench with no options.
- `--models lure,pocket` reruns only some models.
- `--seeds N` sets the takes per line. The default is 2, or 1 on a PC's processor.

**Before the first run:**
- **uv and ffmpeg:** `./sweatcast setup` already installs both.
- **About 15 GB free for downloads:** each model's weights go into `models/`, and each model's environment into uv's cache.
- **Pocket TTS needs a Hugging Face account, once per computer.** Its voice-cloning weights are gated (approved automatically). Accept the terms at https://huggingface.co/kyutai/pocket-tts, then run `uvx hf auth login`. Without that, the bench records Pocket TTS as gated and goes on.

**Time:** about an hour on the Mac. On the PC, about an hour on the graphics card plus up to an hour and a half on the processor.

## The candidates

| Model | Mac | PC (NVIDIA card) | PC (processor) |
|---|---|---|---|
| Chatterbox Turbo (`turbo`), today's engine | mlx-audio 0.6.1 | chatterbox-tts 0.1.7 | chatterbox-tts 0.1.7 |
| Qwen3-TTS 1.7B Base (`qwen3`) | mlx-audio 0.6.1 | qwen-tts 0.1.1 | too large; not run |
| Lure 0.6B (`lure`), a Qwen3-TTS-format model | mlx-audio 0.6.1 | qwen-tts 0.1.1 | qwen-tts 0.1.1 |
| Ming-3.0-tts 0.5B (`ming`) | mlx-audio 0.6.1 | its GitHub code (`028c1ea`), no text normalizer | not run |
| Pocket TTS 100M (`pocket`) | pocket-tts 4.0.1 on the processor | pocket-tts 4.0.1 | pocket-tts 4.0.1 |

**Every model, on every computer:**
- clones the same voice: Coach Andy's clip (`me.example/personas/coach-andy-local/clip.wav`) and its words;
- is pinned to one model revision (`tools/bench.py`);
- runs in its own environment: `uv run --isolated` on the Mac; on the PC, a small uv project that takes PyTorch 2.6.0 from PyTorch's CUDA 12.4 or CPU index.

A model that fails to install or load is recorded with the reason, and the bench moves on to the next.

## What it measures

**Per take:**
- render seconds and audio seconds;
- the words heard;
- word errors, and any missed cue words (go, rest, switch, left, right, a count);
- audio problems: a runaway, a cut-off, a long silence or clipping;
- speech level and peak.

**Per model:**
- load time and render ratio (seconds of rendering per second of speech);
- peak memory: MLX, CUDA and the process;
- takes that fail the build's pass rule;
- word error rate, overall and by kind of line;
- spread of speech level;
- package versions.

**One recognizer scores both computers:** Parakeet TDT 0.6B v3 through ONNX (`onnx-asr`), with the scoring in `tools/verify.py`. The numbers can be compared across machines, though not exactly with a build's take check, which runs Parakeet through MLX.

**The script** is `script.toml`: 44 lines, about four and a half minutes of speech. Each line has a kind (welcome, safety, cue, countdown, short, form, numbers, energy, story, breath or close), so results can be compared on cues and countdowns, which matter most.

## Results

Each run writes `results/<date>-<mac|pc>/`:
- `run.json`: the computer (no name), versions, settings and each model's summary;
- `takes.jsonl`: one row per take;
- `summary.md`: the table;
- `listen/<model>-<device>.mp3`: each model's first seed, end to end, at 48 kbps mono. These are for the blind listening in the analysis.

The takes themselves stay in `.cache/bench/`, which git ignores.
