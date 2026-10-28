"""The coach designer's worker (maintainer only): runs inside one designer's own environment
(coaches/roster.toml names it) and imports nothing from harmonicfitness.

  python design_worker.py <job.json>

The job names the designer, its local model folder, and the takes to make: for each, a coach's slug, the
description, the text and a seed. Each take is written as a WAV at the designer's own rate to
<out>/<slug>/<designer>-<seed>.raw.wav, and <out>/<designer>-render.json records how each went.
"""
import contextlib
import io
import json
import os
import sys
import time
import traceback
import wave

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]


def _write_wav(path, samples, sr):
    import numpy as np
    a = np.clip(np.asarray(samples, dtype=np.float32).reshape(-1), -1.0, 1.0)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes((a * 32767).astype("<i2").tobytes())
    return len(a) / sr


def _quiet():
    return contextlib.redirect_stdout(io.StringIO())


def qwen3(job):
    """Qwen3-TTS VoiceDesign through mlx-audio on the Mac, the description as the instruction. Coaches are made
    once, by the maintainer, so the designer runs nowhere else."""
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    model = load_model(job["model_dir"])

    def say(description, text, seed):
        mx.random.seed(seed)
        with _quiet():
            results = list(model.generate(text=text, instruct=description, verbose=False))
        a = np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in results])
        return a, results[0].sample_rate
    return say


DESIGNERS = {"qwen3": qwen3}


def main(job_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    designer = job["designer"]
    import importlib.metadata as md
    record = {"designer": designer, "model_dir": job["model_dir"], "runtime": f"mlx-audio {md.version('mlx-audio')}",
              "gpu": "Apple GPU (MLX)", "takes": []}
    path = os.path.join(job["out"], f"{designer}-render.json")

    def save():
        os.makedirs(job["out"], exist_ok=True)
        with open(path + ".part", "w", encoding="utf-8") as f:
            json.dump(record, f, indent=1)
        os.replace(path + ".part", path)

    t0 = time.time()
    say = DESIGNERS[designer](job)
    record["load_s"] = round(time.time() - t0, 1)
    print(f"{designer}: loaded in {record['load_s']}s", flush=True)
    for n, t in enumerate(job["takes"], 1):
        take = {"slug": t["slug"], "seed": t["seed"]}
        started = time.time()
        try:
            a, sr = say(t["description"], t["text"], t["seed"])
            wav = os.path.join(job["out"], t["slug"], f"{designer}-{t['seed']}.raw.wav")
            take.update(audio_s=round(_write_wav(wav, a, sr), 2), sr=int(sr), wav=wav)
        except Exception as e:
            take["error"] = f"{type(e).__name__}: {e}"[:500]
            take["traceback"] = traceback.format_exc()[-2000:]
        take["render_s"] = round(time.time() - started, 1)
        record["takes"].append(take)
        save()
        print(f"  [{n}/{len(job['takes'])}] {t['slug']} seed {t['seed']}: "
              + (f"{take['audio_s']}s in {take['render_s']}s" if "audio_s" in take else take["error"]), flush=True)
    save()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
