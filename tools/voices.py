"""Voices: how long a coach will speak, the local model it renders with, and its download.

A local coach (tools/personas.py) is one of the ten shipped in coaches/: a clip, its words and the Pocket TTS
voice state made from it; a voice here is that coach on one engine, as the dict render.py takes.

Pocket TTS and the cloud voices decide a clip's length as they speak, so the prediction is the voice's
measured rate (weighted characters per second, recorded by each render into the coach's pace.json, one entry
per engine and model) applied to the text. It is an estimate, typically within a few percent over a whole
segment; render.py absorbs the difference in the next segments' spare time. A shipped coach's pace.json comes
measured, from its sample; a coach no render has measured yet is seeded from the other coaches' rates. The
character weights are vendored in char_weight.py. Each render also records this computer's render speed.
"""
import contextlib
import hashlib
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

ENGINES = ("pocket",)
# Every local voice runs on PyTorch: an Apple Silicon Mac's processor, a PC's processor or an NVIDIA card.
BACKEND = "torch"
# Pocket TTS (Kyutai, CC-BY-4.0): the public model, which can't clone a clip but loads a coach's saved voice
# state (pocket.safetensors, made once by the maintainer: tools/coachmaker/export_pocket.py). The voice files
# belong to this model and language config, so neither moves without exporting all ten again.
POCKET_VERSION = "4.0.1"
POCKET_LANGUAGE = "english_2026-10"
POCKET_REPO = "kyutai/pocket-tts-without-voice-cloning"
GATED_POCKET = "kyutai/pocket-tts"     # the cloning model: never loaded in a listener's build
# The local model each engine renders with, pinned to the revision tested; part of every pace and clip key.
LOCAL_MODELS = {"pocket": (POCKET_REPO, "a7056f505a4a8ca72d8b5fb1440071d6f1a35739")}
# The files the language config loads (pocket_tts/config/english_2026-10.yaml), each at its own revision:
# setup fetches exactly these, and a test checks the installed config still names them.
POCKET_FILES = [(POCKET_REPO, "languages/english_2026-10/model.safetensors", "a7056f505a4a8ca72d8b5fb1440071d6f1a35739"),
                (POCKET_REPO, "languages/english_2026-09/tokenizer.json", "00eac05ed3d16bdc3f6b5d598874019c34a89214")]
# The speech recognizer that checks each local take (tools/verify.py): Parakeet TDT 0.6B v3 through ONNX, on
# the processor, the same on every computer. Kept as a plain folder in models/, since
# onnxruntime won't load weights through the Hugging Face cache's links.
CHECK_MODEL = ("istupakov/parakeet-tdt-0.6b-v3-onnx", "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce")
CHECK_FILES = ["config.json", "vocab.txt", "nemo128.onnx", "encoder-model.onnx", "encoder-model.onnx.data",
               "decoder_joint-model.onnx"]
CHECK_DIR = os.path.join(paths.MODELS, "parakeet-tdt-0.6b-v3-onnx")
# The line a web service's voice design speaks (tools/coaches.py's auditions).
DESIGN_LINE = ("Okay, set your feet. Chest up, elbows in, and press. Good. Stay with it, two more. "
               "Breathe out as you drive. That's the pace we want.")
SIZES_GB = {POCKET_REPO: 0.4, CHECK_MODEL[0]: 2.5}   # download sizes, for the message
EDGE = 0.08              # render.py trims engine silence to 40 ms at each end
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


_locked = locks.file_lock   # held while the pace file is read, changed and written


def _rate_key(v):
    return f"{v['key']}|{v['engine']}|{v['model']}"   # the model differs by backend, so each is measured


def speed_key(v):
    """This computer and what it renders on, for the render speed (pace travels; speed doesn't). The computer
    is a short hash of its name, so pace.json (backed up) never holds the hostname."""
    import platform
    computer = hashlib.sha256((platform.node() or "this computer").encode("utf-8")).hexdigest()[:8]
    return f"{computer}|{v.get('device') or v.get('backend') or 'torch'}"


def _write_rates(path, data):
    import fileio
    fileio.write_json(path, data)


def _with_seed(v, path, data):
    """A stock coach's pace before this computer's first render: its entry from the shipped pace.json
    (v["pace_seed"]), added to what `path` (the shared voice-pace.json) holds for the other voices."""
    if v.get("pace_seed") and path == v.get("pace_file") and _rate_key(v) not in data:
        rec = _recorded(v["pace_seed"]).get(_rate_key(v))
        if rec:
            data = dict(data, **{_rate_key(v): dict(rec)})
    return data


def record_rate(v, weight, seconds, path=None, render_seconds=None):
    """Fold a render's measured speech into the voice's rate (called by render.py), and with
    render_seconds, this computer's render speed (seconds of rendering per second of speech).
    The coach's own pace.json when the voice names one. Locked, and written to a temporary
    file then renamed, so it's never half-written. A record that is only an estimate (a web coach's
    approved sample) is replaced by the first real measurement, not added to."""
    path = path or v.get("pace_file") or PACE_FILE
    with _locked(path):
        data = _with_seed(v, path, _recorded(path, strict=True))
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


def forget_pace(path, key):
    """Drop every record of voice identity `key` (any engine or model) from pace file `path`: a re-voiced
    coach's old voice. Returns how many went."""
    if not os.path.exists(path):
        return 0
    with _locked(path):
        data = _recorded(path, strict=True)
        gone = [k for k in data if k.startswith(f"{key}|")]
        for k in gone:
            del data[k]
        if gone:
            _write_rates(path, data)
    return len(gone)


def seed_pace(data):
    """A starting rate for a voice no render has measured: the median of the measured
    rates on file (entries with enough speech behind them), else DEFAULT_PACE. The
    reference clip's own rate is not used: for Chatterbox Coach it was 10.3 chars/s
    against a measured 14.6."""
    rates = [r["weight"] / r["seconds"] for r in data.values()
             if isinstance(r, dict) and r.get("weight") and not r.get("estimate")
             and ((r.get("seconds") or 0) > MIN_MEASURED or r.get("shipped"))]
    return statistics.median(rates) if rates else DEFAULT_PACE


def _every_coach_measured():
    """Every coach's measured entries, merged, for seeding a coach not measured yet."""
    out = {}
    for folder in (paths.SHIPPED, paths.PERSONAS):   # this computer's copy of a shipped coach's pace wins
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
    data = _with_seed(v, path, _recorded(path))
    rec = data.get(_rate_key(v))
    if rec and rec.get("estimate") and rec.get("seconds"):
        return rec["weight"] / rec["seconds"], False
    if rec and (rec.get("seconds", 0) > MIN_MEASURED or rec.get("shipped")):   # a shipped coach comes measured
        return rec["weight"] / rec["seconds"], True
    return seed_pace(_every_coach_measured() if v.get("pace_file") else data), False


def speed(v, path=None):
    """This computer's measured render speed for the voice (seconds per second of speech), or None."""
    path = path or v.get("pace_file")
    rec = _with_seed(v, path, _recorded(path)).get(_rate_key(v)) or {}
    return (rec.get("speed") or {}).get(speed_key(v))


def clip_seconds(text, v, rate=None):
    """Predicted length of one clip of `text`, including its trimmed edges. Pass `rate`
    (from pace()) when predicting many clips, so the pace file is read once."""
    return weight(text) / (rate if rate is not None else pace(v)[0]) + EDGE


def download(v=None):
    """Fetch the local voice's model files and the take checker at their pinned revisions, into models/. Files
    already there aren't fetched again."""
    from huggingface_hub import hf_hub_download, snapshot_download
    print(f"Pocket TTS ({POCKET_REPO}, about {SIZES_GB[POCKET_REPO]} GB)", flush=True)
    for repo, filename, rev in POCKET_FILES:
        hf_hub_download(repo, filename, revision=rev)
    print(f"The take checker ({CHECK_MODEL[0]}, about {SIZES_GB[CHECK_MODEL[0]]} GB)", flush=True)
    snapshot_download(CHECK_MODEL[0], revision=CHECK_MODEL[1], local_dir=CHECK_DIR, allow_patterns=CHECK_FILES)


def downloaded():
    """Whether the local voice's files and the take checker are all in models/."""
    from huggingface_hub import try_to_load_from_cache
    have = all(isinstance(try_to_load_from_cache(repo, f, revision=rev), str) for repo, f, rev in POCKET_FILES)
    return have and all(os.path.exists(os.path.join(CHECK_DIR, f)) for f in CHECK_FILES)


def write_wav(path, pcm, rate=24000):
    """16-bit mono PCM to a .wav file."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
