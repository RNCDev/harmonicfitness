"""The audio bench's worker: runs inside one model's own throwaway environment (tools/bench.py starts it
with `uv run --isolated`), so each model brings the libraries it needs without touching sweatcast's
environment or another model's. It imports nothing from sweatcast.

  python bench_worker.py render <job.json>   load one model, speak every line once per seed, cloning the
                                             job's reference clip; each take a WAV at the model's own rate
                                             under <out>/<seed>/<id>.wav, and <out>/render.json, rewritten
                                             after every take so a run cut short keeps what it did
  python bench_worker.py asr <job.json>      transcribe WAVs with Parakeet TDT 0.6B v3 through ONNX (the
                                             same recognizer on a Mac and a PC) into <out>
"""
import contextlib
import io
import json
import os
import sys
import time
import traceback
import wave

# This file sits in tools/, whose modules (coverage.py among them) would shadow the libraries the models
# import, so its own folder comes off the path. It imports nothing from sweatcast.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]


def _versions(names):
    from importlib.metadata import PackageNotFoundError, version
    out = {}
    for n in names:
        try:
            out[n] = version(n)
        except PackageNotFoundError:
            pass
    return out


def _peak_rss():
    """The process's peak resident memory in bytes."""
    try:
        import psutil
        info = psutil.Process().memory_info()
        if getattr(info, "peak_wset", None):   # Windows
            return info.peak_wset
    except ImportError:
        pass
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak if sys.platform == "darwin" else peak * 1024
    except ImportError:
        return None


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
    """Hide the models' own progress printing from the log's take lines."""
    return contextlib.redirect_stdout(io.StringIO())


# --- one speaker per engine: say(text, seed) -> (float samples, sample rate) ---------------------------

def mlx_speaker(job):
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    model = load_model(job["repo"], revision=job.get("revision"))
    gen = job.get("generate") or {}
    primed = []

    def say(text, seed):
        mx.random.seed(seed)
        kw = dict(text=text, verbose=False, **gen)
        if not (job.get("prime_once") and primed):   # Chatterbox Turbo keeps the clip after the first call
            kw["ref_audio"] = job["ref_audio"]
            primed.append(True)
        if job.get("ref_text_needed"):
            kw["ref_text"] = job["ref_text"]
        with _quiet():
            res = list(model.generate(**kw))
        return np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in res]), res[0].sample_rate

    def peak():
        get = getattr(mx, "get_peak_memory", None) or getattr(getattr(mx, "metal", None), "get_peak_memory", None)
        return {"mlx_peak_bytes": get() if get else None}
    return say, peak


def _torch_device(job):
    import torch
    if job["device"] == "cuda" and not torch.cuda.is_available():
        raise SystemExit("PyTorch can't see the NVIDIA card in this environment (CPU-only wheels?)")
    return job["device"]


def _torch_peak():
    import torch
    out = {}
    if torch.cuda.is_available():
        out["cuda_peak_bytes"] = torch.cuda.max_memory_allocated()
        out["gpu"] = torch.cuda.get_device_name(0)
    return out


def _local(job):
    """The job's model, downloaded at its pinned revision; the local folder's path."""
    from huggingface_hub import snapshot_download
    return snapshot_download(job["repo"], revision=job.get("revision"))


def _half(torch):
    """bf16 where the card has it (from the RTX 30 series on), else fp16 (an RTX 20 series card)."""
    return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16


def chatterbox_speaker(job):
    import torch
    from huggingface_hub import snapshot_download
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    device = _torch_device(job)
    path = snapshot_download(job["repo"], revision=job.get("revision"),
                             allow_patterns=["*.safetensors", "*.json", "*.txt", "*.pt", "*.model"])
    with _quiet():
        model = ChatterboxTurboTTS.from_local(path, device)
        model.prepare_conditionals(job["ref_audio"])

    def say(text, seed):
        torch.manual_seed(seed)
        with torch.inference_mode(), _quiet():
            wav = model.generate(text)
        return wav.squeeze(0).float().cpu().numpy(), model.sr
    return say, _torch_peak


def qwen_tts_speaker(job):
    """Qwen3-TTS, and Lure (a Qwen3-TTS-format model), through Qwen's own PyTorch package."""
    import torch
    from qwen_tts import Qwen3TTSModel
    device = _torch_device(job)
    dtype = _half(torch) if device == "cuda" else torch.float32
    model = Qwen3TTSModel.from_pretrained(_local(job),
                                          device_map="cuda:0" if device == "cuda" else "cpu", dtype=dtype,
                                          attn_implementation="sdpa")

    def say(text, seed):
        torch.manual_seed(seed)
        with _quiet():
            wavs, sr = model.generate_voice_clone(text=text, language="English", ref_audio=job["ref_audio"],
                                                  ref_text=job["ref_text"])
        return wavs[0], sr
    return say, _torch_peak


def ming_speaker(job):
    """Ming-3.0 from its own GitHub code (no pip package), checked out by tools/bench.py."""
    import tempfile
    import torch
    import soundfile as sf
    sys.path.insert(0, job["repo_dir"])
    os.chdir(job["repo_dir"])   # it finds its own data files (the speaker-embedding model) from here
    from ming_tts import MingTTS
    device = _torch_device(job)
    # No text normalization: its normalizer needs pynini, which has no Windows wheel, and a sweatcast
    # script has its numbers spelled out already.
    model = MingTTS(_local(job), device="cuda:0" if device == "cuda" else "cpu", text_normalization=False)
    tmp = tempfile.mkdtemp()

    def say(text, seed):
        torch.manual_seed(seed)
        out = os.path.join(tmp, "take.wav")
        kw = dict(task="TTS", language_id="English", text=text, prompt_wav_path=job["ref_audio"],
                  prompt_text=job["ref_text"], use_spk_emb=True, output_path=out)
        with _quiet():
            model.synthesize(**kw)
        a, sr = sf.read(out, dtype="float32")
        return (a.mean(axis=1) if a.ndim > 1 else a), sr
    return say, _torch_peak


def pocket_speaker(job):
    import torch
    from pocket_tts import TTSModel
    device = _torch_device(job)
    model = TTSModel.load_model(language=job.get("language"))
    if job.get("public_only") and model.has_voice_cloning:
        raise SystemExit("The gated Pocket model loaded; this run must use the public one, as listeners do.")
    if device == "cuda":
        model = model.to("cuda")
    state = model.get_state_for_audio_prompt(job["ref_audio"])

    def say(text, seed):
        torch.manual_seed(seed)
        with _quiet():
            audio = model.generate_audio(state, text)
        return audio.float().cpu().numpy(), model.sample_rate
    return say, _torch_peak


SPEAKERS = {"mlx": mlx_speaker, "chatterbox": chatterbox_speaker, "qwen-tts": qwen_tts_speaker,
            "ming": ming_speaker, "pocket": pocket_speaker}
PACKAGES = ["mlx-audio", "mlx", "torch", "chatterbox-tts", "qwen-tts", "pocket-tts", "transformers", "numpy",
            "onnx-asr", "onnxruntime"]


def render(job):
    out = job["out"]
    os.makedirs(out, exist_ok=True)
    record = {"model": job["model"], "device": job["device"], "engine": job["engine"], "repo": job["repo"],
              "revision": job.get("revision"), "python": sys.version.split()[0], "packages": _versions(PACKAGES),
              "load_s": None, "takes": [], "error": None, "peak": {}}
    path = os.path.join(out, "render.json")

    def save():
        record["peak"]["rss_bytes"] = _peak_rss()
        with open(path + ".part", "w", encoding="utf-8") as f:
            json.dump(record, f, indent=1)
        os.replace(path + ".part", path)

    started = time.time()
    try:
        say, peak = SPEAKERS[job["engine"]](job)
    except BaseException as e:   # an install or load failure is a result too
        record["error"] = f"load: {type(e).__name__}: {e}"[:2000]
        record["traceback"] = traceback.format_exc()[-4000:]
        save()
        print(record["error"], file=sys.stderr)
        return 1
    record["load_s"] = round(time.time() - started, 2)
    print(f"{job['model']} on {job['device']}: loaded in {record['load_s']}s", flush=True)
    save()
    for seed in job["seeds"]:
        for n, line in enumerate(job["lines"], 1):
            take = {"id": line["id"], "seed": seed}
            t0 = time.time()
            try:
                a, sr = say(line["text"], seed)
                take["render_s"] = round(time.time() - t0, 3)
                take["audio_s"] = round(_write_wav(os.path.join(out, str(seed), line["id"] + ".wav"), a, sr), 3)
                take["sr"] = int(sr)
            except Exception as e:
                take["render_s"] = round(time.time() - t0, 3)
                take["error"] = f"{type(e).__name__}: {e}"[:500]
            record["takes"].append(take)
            try:
                record["peak"].update(peak() or {})
            except Exception:
                pass
            save()
            print(f"  seed {seed} [{n}/{len(job['lines'])}] {line['id']}: "
                  + (f"{take['audio_s']:.1f}s in {take['render_s']:.1f}s" if "audio_s" in take else take["error"]),
                  flush=True)
    record["total_s"] = round(time.time() - started, 1)
    save()
    return 0


def asr(job):
    import onnx_asr
    from huggingface_hub import snapshot_download
    # Into a plain folder: onnxruntime refuses a model whose weights it reaches through the Hugging Face
    # cache's links. Full precision, on the processor, so a Mac and a PC hear alike.
    path = snapshot_download(job["asr_repo"], revision=job["asr_revision"], local_dir=job["asr_dir"],
                             allow_patterns=["config.json", "vocab.txt", "nemo128.onnx", "encoder-model.onnx",
                                             "encoder-model.onnx.data", "decoder_joint-model.onnx"])
    model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", path, providers=["CPUExecutionProvider"])
    out = {"asr_model": "nemo-parakeet-tdt-0.6b-v3", "asr_repo": job["asr_repo"],
           "asr_revision": job["asr_revision"], "providers": ["CPUExecutionProvider"],
           "packages": _versions(PACKAGES), "heard": {}}
    started = time.time()
    for n, path in enumerate(job["files"], 1):
        try:
            text = model.recognize(path)
            out["heard"][path] = text if isinstance(text, str) else str(text)
        except Exception as e:
            out["heard"][path] = None
            print(f"  couldn't transcribe {path}: {e}", file=sys.stderr)
        if n % 25 == 0:
            print(f"  heard {n}/{len(job['files'])}", flush=True)
    out["asr_s"] = round(time.time() - started, 1)
    with open(job["out"], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return 0


if __name__ == "__main__":
    mode, job_path = sys.argv[1], sys.argv[2]
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    sys.exit({"render": render, "asr": asr}[mode](job))
