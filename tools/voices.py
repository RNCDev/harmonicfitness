"""Voices: how long a coach will speak, the local models each engine renders with, and their download.

A coach (tools/personas.py) is a ten-second reference clip with its words, which every engine copies; a
voice here is that coach on one engine, as the dict render.py takes. The models are used as published.

Chatterbox, Qwen3-TTS and the cloud voices decide a clip's length as they speak, so the prediction
is the voice's measured rate (weighted characters per second, recorded by each render into the coach's
pace.json, one entry per engine and model) applied to the text. It is an estimate, typically within
a few percent over a whole segment; render.py absorbs the difference in the next segments' spare time.
Until a coach's first render on an engine, its rate is seeded from the other coaches' measured rates: a
reference clip's own rate came out about 30 percent slow for Chatterbox Turbo. The character weights
are vendored in char_weight.py. Each render also records this computer's render speed beside the pace.
"""
import contextlib
import json
import os
import statistics
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from char_weight import weight  # noqa: E402,F401  (re-exported for render.py)
import locks  # noqa: E402
import paths  # noqa: E402
from paths import PACE_FILE, ROOT, show  # noqa: E402,F401

ENGINES = ("qwen3", "chatterbox")
# What runs the local models here: MLX on a Mac, PyTorch (CUDA, or the processor) on Windows and Linux.
# SWEATCAST_BACKEND overrides the choice (the tests set it).
BACKENDS = ("mlx", "torch")
BACKEND = os.environ.get("SWEATCAST_BACKEND") or ("mlx" if sys.platform == "darwin" else "torch")
TORCH_ENGINES = ("chatterbox",)   # engines with a PyTorch path in tools/engines.py so far
# The local models each engine renders with, per backend, pinned to the revisions tested. A coach
# names only its engine; these strings are part of every pace and clip cache key, so they never change
# without a migration.
LOCAL_MODELS = {("chatterbox", "mlx"): ("mlx-community/chatterbox-turbo-fp16", "b2d0a13aa7cfff0a06d9acb247ae91c8f19a6d75"),
                ("chatterbox", "torch"): ("ResembleAI/chatterbox-turbo", "749d1c1a46eb10492095d68fbcf55691ccf137cd"),
                ("qwen3", "mlx"): ("mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16", "a6eb4f68e4b056f1215157bb696209bc82a6db48")}
# The extra repos an engine loads on its own (Chatterbox Turbo's speech tokenizer), pinned so a fresh
# machine downloads exactly what was tested.
ENGINE_EXTRAS = {"chatterbox": [("mlx-community/S3TokenizerV2", "e0c9886f0e1c35ae85b1f27277416fb19fc72bec")]}
# Qwen3-TTS VoiceDesign: makes a voice from a description, pinned like the rest.
VOICE_DESIGN = ("mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-bf16", "7d3824abff87e49756bb0f83fb5411de75d160c4")
DESIGN_LINE = ("Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. "
               "Breathe out as you drive. That's the pace we want.")
SIZES_GB = {"mlx-community/chatterbox-turbo-fp16": 2.8, "mlx-community/S3TokenizerV2": 0.5,
            "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16": 4.2,
            VOICE_DESIGN[0]: 4.5, "ResembleAI/chatterbox-turbo": 4.0}   # download sizes, for the message
# The files Resemble's own loader fetches from its Turbo repo (chatterbox.tts_turbo).
TORCH_PATTERNS = ["*.safetensors", "*.json", "*.txt", "*.pt", "*.model"]
MLX_EDGE = 0.08          # render.py trims engine silence to 40 ms at each end
MIN_MEASURED = 30.0      # seconds of rendered speech before a voice's rate counts as measured
DEFAULT_PACE = 14.5      # weighted chars/s for a new voice when no voice has been measured yet


def _recorded(path=None, strict=False):
    """Every voice's recorded speech, from the pace file. A missing file is empty. A file
    that won't parse is never silently treated as empty when it's about to be written
    (strict): it's set aside as voice-pace.json.corrupt-<time> and the tool stops, so one
    bad write can't erase every voice's measurements."""
    path = path or PACE_FILE
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        return data
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        if not strict:
            print(f"Warning: couldn't read {show(path)} ({e}); treating every voice as unmeasured.",
                  file=sys.stderr)
            return {}
        bad = f"{path}.corrupt-{time.strftime('%Y%m%d%H%M%S')}"
        os.replace(path, bad)
        raise SystemExit(f"{show(path)} was damaged ({e}), so it was moved to {show(bad)} rather than "
                         "overwritten. Fix it by hand and move it back, or delete it and render the "
                         "smoke test with each voice to measure them again.")


def check_pace_file(path=None):
    """Stop now, not after a long render, if the pace file can't be read (render.py calls this first)."""
    _recorded(path, strict=True)


@contextlib.contextmanager
def _locked(path):
    """An exclusive lock beside `path`, held while its contents are read, changed and written."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".lock", "a") as lock:
        locks.acquire(lock)
        try:
            yield
        finally:
            locks.release(lock)


def _rate_key(v):
    return f"{v['key']}|{v['engine']}|{v['model']}"   # the model differs by backend, so each is measured


def speed_key(v):
    """This computer and what it renders on, for the render speed (pace travels; speed doesn't)."""
    import platform
    return f"{platform.node() or 'this computer'}|{v.get('device') or v.get('backend') or 'mlx'}"


def _write_rates(path, data):
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def record_rate(v, weight, seconds, path=None, render_seconds=None):
    """Fold a render's measured speech into the voice's rate (called by render.py), and with
    render_seconds, this computer's render speed (seconds of rendering per second of speech).
    The coach's own pace.json when the voice names one. Locked, and written to a temporary
    file then renamed, so it's never half-written. A record that is only an estimate (a web coach's
    approved sample) is replaced by the first real measurement, not added to."""
    path = path or v.get("pace_file") or PACE_FILE
    with _locked(path):
        data = _recorded(path, strict=True)
        rec = data.get(_rate_key(v))
        if not rec or rec.get("estimate"):
            rec = {"weight": 0.0, "seconds": 0.0}
        rec["name"] = v["name"]
        rec["weight"] += weight
        rec["seconds"] += seconds
        if render_seconds and seconds > 0:
            rec.setdefault("speed", {})[speed_key(v)] = round(render_seconds / seconds, 3)
        data[_rate_key(v)] = rec
        _write_rates(path, data)


def record_estimate(v, weight, seconds, path=None):
    """A web coach's starting pace, from its approved sample: `weight` (char_weight units) over the sample's
    trimmed `seconds`. pace() uses it, unmeasured, until the first real render replaces it."""
    path = path or v.get("pace_file") or PACE_FILE
    with _locked(path):
        data = _recorded(path, strict=True)
        data[_rate_key(v)] = {"name": v["name"], "weight": weight, "seconds": seconds, "estimate": True}
        _write_rates(path, data)


def seed_pace(data):
    """A starting rate for a voice no render has measured: the median of the measured
    rates on file (entries with enough speech behind them), else DEFAULT_PACE. The
    reference clip's own rate is not used: for Chatterbox Coach it was 10.3 chars/s
    against a measured 14.6."""
    rates = [r["weight"] / r["seconds"] for r in data.values()
             if isinstance(r, dict) and r.get("weight") and not r.get("estimate")
             and (r.get("seconds") or 0) > MIN_MEASURED]
    return statistics.median(rates) if rates else DEFAULT_PACE


def _every_coach_measured():
    """Every coach's measured entries, merged, for seeding a coach not measured yet."""
    out = {}
    folder = paths.PERSONAS
    if os.path.isdir(folder):
        for slug in sorted(os.listdir(folder)):
            pace_file = os.path.join(folder, slug, "pace.json")
            if os.path.exists(pace_file):
                out.update({f"{slug}|{k}": r for k, r in _recorded(pace_file).items()})
    return out


def pace(v, path=None):
    """Weighted characters per second: the voice's speaking rate, and whether it's measured.
    A coach's comes from its own pace.json, seeded from the other coaches until measured."""
    path = path or v.get("pace_file")
    data = _recorded(path)
    rec = data.get(_rate_key(v))
    if rec and rec.get("estimate") and rec.get("seconds"):
        return rec["weight"] / rec["seconds"], False
    if rec and rec.get("seconds", 0) > MIN_MEASURED:
        return rec["weight"] / rec["seconds"], True
    return seed_pace(_every_coach_measured() if v.get("pace_file") else data), False


def speed(v, path=None):
    """This computer's measured render speed for the voice (seconds per second of speech), or None."""
    rec = _recorded(path or v.get("pace_file")).get(_rate_key(v)) or {}
    return (rec.get("speed") or {}).get(speed_key(v))


def clip_seconds(text, v, rate=None):
    """Predicted length of one clip of `text`, including its trimmed edges. Pass `rate`
    (from pace()) when predicting many clips, so the pace file is read once."""
    return weight(text) / (rate if rate is not None else pace(v)[0]) + MLX_EDGE


def download(v):
    """Fetch the voice's model at its pinned revision, plus what its engine loads on its
    own, into the shared Hugging Face cache. Files already in the cache aren't fetched again."""
    from huggingface_hub import snapshot_download
    if not v["model"]:
        print(f"{v['name']}: no {v['backend']} model for its engine ({v['engine']}) yet; skipped.", flush=True)
        return
    torch = v.get("backend") == "torch"
    extras = [] if torch else ENGINE_EXTRAS.get(v["engine"], [])   # the MLX port's own extra downloads
    for repo, rev in [(v["model"], v["revision"]), *extras]:
        size = f", about {SIZES_GB[repo]} GB" if repo in SIZES_GB else ""
        print(f"{v['name']}: {repo}" + (f" at {rev[:8]}" if rev else " (latest; no revision pinned)") + size,
              flush=True)
        snapshot_download(repo, revision=rev, allow_patterns=TORCH_PATTERNS if torch else None)


def write_wav(path, pcm, rate=24000):
    """16-bit mono PCM to a .wav file."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
