"""The coach designer's worker (maintainer only): runs inside one designer's own environment
(coaches/roster.toml names it) and imports nothing from sweatcast.

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
    """Qwen3-TTS VoiceDesign through Qwen's own package: the description as the instruction."""
    import torch
    from qwen_tts import Qwen3TTSModel
    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    model = Qwen3TTSModel.from_pretrained(job["model_dir"], device_map="cuda:0", dtype=dtype,
                                          attn_implementation="sdpa")

    def say(description, text, seed):
        torch.manual_seed(seed)
        with _quiet():
            wavs, sr = model.generate_voice_design(text=text, instruct=description, language="English")
        return wavs[0], sr
    return say


def voxcpm(job):
    """VoxCPM2: the description in parentheses before the text. No denoiser (no reference audio here) and no
    torch.compile (no Triton on Windows). The device is VoxCPM's own choice (CUDA, else Apple's MPS, else the
    processor) unless the job names one; a take made on one device won't match the same seed on another."""
    import torch
    from voxcpm import VoxCPM
    model = VoxCPM.from_pretrained(job["model_dir"], load_denoiser=False, optimize=False,
                                 device=job.get("device") or "auto")

    def say(description, text, seed):
        torch.manual_seed(seed)
        with _quiet():
            wav = model.generate(text=f"({description}){text}", cfg_value=job.get("cfg_value", 2.0),
                                 inference_timesteps=job.get("inference_timesteps", 10))
        return wav, model.tts_model.sample_rate
    return say


DESIGNERS = {"qwen3": qwen3, "voxcpm": voxcpm}


def main(job_path):
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    import torch
    designer = job["designer"]
    if designer == "qwen3" and not torch.cuda.is_available():
        raise SystemExit("PyTorch can't see the NVIDIA card in this environment.")
    gpu = (torch.cuda.get_device_name(0) if torch.cuda.is_available() else
           "Apple MPS" if torch.backends.mps.is_available() else "processor")
    record = {"designer": designer, "model_dir": job["model_dir"], "torch": torch.__version__,
              "gpu": gpu, "takes": []}
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
