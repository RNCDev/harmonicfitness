#!/usr/bin/env python3
"""Voices: look one up, predict how long it will speak, and fetch its model.

A voice is a reference clip plus its transcript, kept as three files:
<name>.wav, <name>.txt (what the clip says) and <name>.json, which names its
engine (chatterbox or qwen3), the model repo and the pinned revision on Hugging
Face, and optionally "aliases" (older names that still find it) and "generate",
extra settings passed to the engine for each clip. A voice is not a tuned model: the
model is used as published, and copies the reference clip's voice for every line.
Shipped voices live in the repo's voices/ folder; private ones (a cloned real voice,
say) go in me/voices/, which is looked in first.

Chatterbox and Qwen3-TTS decide a clip's length as they speak, so the prediction
is the voice's measured rate (weighted characters per second, recorded by each
render) applied to the text. It is an estimate, typically within a few percent over
a whole segment; render.py absorbs the difference in the next segments' spare time.
Until a voice's first render, its rate is seeded from the other voices' measured
rates: a reference clip's own rate came out about 30 percent slow for Chatterbox Coach.
The character weights are vendored in char_weight.py.

    python3 tools/voices.py                      # list voices with their engine and pace
    python3 tools/voices.py --measured "Qwen3 Coach"    # exit 0 if measured, 1 if estimated, 64 if no such voice
    .venv/bin/python tools/voices.py --download "Chatterbox Coach"   # fetch its pinned model (setup.sh does this)
"""
import contextlib
import fcntl
import hashlib
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from char_weight import weight  # noqa: E402,F401  (re-exported for render.py)
import cli  # noqa: E402
from paths import PACE_FILE, ROOT, VOICE_DIRS, show  # noqa: E402,F401

ENGINES = ("qwen3", "chatterbox")
# The engine's standard model when a voice names none, and the extra repos an
# engine loads on its own (Chatterbox Turbo's speech tokenizer), pinned so a
# fresh machine downloads exactly what was tested.
STANDARD_MODELS = {"qwen3": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
                   "chatterbox": "mlx-community/Chatterbox-TTS-fp16"}
ENGINE_EXTRAS = {"chatterbox": [("mlx-community/S3TokenizerV2", "e0c9886f0e1c35ae85b1f27277416fb19fc72bec")]}
SIZES_GB = {"mlx-community/chatterbox-turbo-fp16": 2.8, "mlx-community/S3TokenizerV2": 0.5,
            "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16": 4.2}   # download sizes, for the message
MLX_EDGE = 0.08          # render.py trims engine silence to 40 ms at each end
MIN_MEASURED = 30.0      # seconds of rendered speech before a voice's rate counts as measured
DEFAULT_PACE = 14.5      # weighted chars/s for a new voice when no voice has been measured yet


def _files():
    """{lowercased name: (name, folder)} for every voice; me/voices wins a name clash."""
    found = {}
    for folder in reversed(VOICE_DIRS):
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                name, ext = os.path.splitext(f)
                if ext == ".wav":
                    found[name.lower()] = (name, folder)
    return found


def _aliases(files):
    """{lowercased alias: (name, folder)} from each voice's "aliases" setting."""
    out = {}
    for name, folder in files.values():
        try:
            with open(os.path.join(folder, name + ".json"), encoding="utf-8") as j:
                for alias in json.load(j).get("aliases") or []:
                    out.setdefault(alias.lower(), (name, folder))
        except (OSError, ValueError):
            pass
    return out


def names():
    return sorted(name for name, _ in _files().values())


def lookup(voice):
    """A voice by name or one of its aliases (case doesn't matter). Stops with a message
    when there's no such voice or its settings are broken."""
    files = _files()
    hit = files.get(voice.lower()) or _aliases(files).get(voice.lower())
    if not hit:
        raise SystemExit(f"No voice '{voice}'. Available: {', '.join(names()) or 'none'} "
                         f"(in {', '.join(show(d) for d in VOICE_DIRS)}).")
    name, folder = hit
    path = os.path.join(folder, name + ".wav")
    with open(os.path.join(folder, name + ".txt"), encoding="utf-8") as t:
        ref_text = t.read().strip()
    with open(path, "rb") as a:
        audio_hash = hashlib.sha256(a.read()).hexdigest()
    settings = os.path.join(folder, name + ".json")
    if not os.path.exists(settings):
        raise SystemExit(f"{show(settings)} is missing: it names the voice's engine "
                         f"({' or '.join(ENGINES)}) and model.")
    with open(settings, encoding="utf-8") as j:
        conf = json.load(j)
    engine = conf.get("engine")
    if engine not in ENGINES:
        raise SystemExit(f"{show(settings)}: engine must be one of {', '.join(ENGINES)}")
    return {"name": name, "engine": engine,
            "model": conf.get("model") or STANDARD_MODELS[engine], "revision": conf.get("revision"),
            "generate": conf.get("generate") or {},
            "ref_audio": path, "ref_text": ref_text,
            "key": hashlib.sha256(f"{audio_hash}|{ref_text}".encode()).hexdigest()[:12]}


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
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _rate_key(v):
    return f"{v['key']}|{v['engine']}|{v['model']}"


def record_rate(v, weight, seconds, path=None):
    """Fold a render's measured speech into the voice's rate (called by render.py).
    Locked, and written to a temporary file then renamed, so it's never half-written."""
    path = path or PACE_FILE
    with _locked(path):
        data = _recorded(path, strict=True)
        rec = data.get(_rate_key(v), {"weight": 0.0, "seconds": 0.0})
        rec["name"] = v["name"]
        rec["weight"] += weight
        rec["seconds"] += seconds
        data[_rate_key(v)] = rec
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


def seed_pace(data=None, path=None):
    """A starting rate for a voice no render has measured: the median of the measured
    rates on file (entries with enough speech behind them), else DEFAULT_PACE. The
    reference clip's own rate is not used: for Chatterbox Coach it was 10.3 chars/s
    against a measured 14.6."""
    data = _recorded(path) if data is None else data
    rates = [r["weight"] / r["seconds"] for r in data.values()
             if isinstance(r, dict) and r.get("weight") and (r.get("seconds") or 0) > MIN_MEASURED]
    return statistics.median(rates) if rates else DEFAULT_PACE


def pace(v, path=None):
    """Weighted characters per second: the voice's speaking rate, and whether it's measured.
    Reads the pace file once."""
    data = _recorded(path)
    rec = data.get(_rate_key(v))
    if rec and rec.get("seconds", 0) > MIN_MEASURED:
        return rec["weight"] / rec["seconds"], True
    return seed_pace(data), False


def clip_seconds(text, v, rate=None):
    """Predicted length of one clip of `text`, including its trimmed edges. Pass `rate`
    (from pace()) when predicting many clips, so the pace file is read once."""
    return weight(text) / (rate if rate is not None else pace(v)[0]) + MLX_EDGE


def download(v):
    """Fetch the voice's model at its pinned revision, plus what its engine loads on its
    own, into the shared Hugging Face cache. Needs the project's environment. Files
    already in the cache aren't fetched again."""
    from huggingface_hub import snapshot_download
    for repo, rev in [(v["model"], v["revision"]), *ENGINE_EXTRAS.get(v["engine"], [])]:
        size = f", about {SIZES_GB[repo]} GB" if repo in SIZES_GB else ""
        print(f"{v['name']}: {repo}" + (f" at {rev[:8]}" if rev else " (latest; no revision pinned)") + size,
              flush=True)
        snapshot_download(repo, revision=rev)


def main():
    args = sys.argv[1:]
    if args[:1] == ["--measured"]:
        if len(args) != 2:
            print("usage: python3 tools/voices.py --measured <voice>", file=sys.stderr)
            return cli.USAGE
        try:
            v = lookup(args[1])
        except SystemExit as e:   # an unknown voice or broken settings: a command mistake
            print(e.code, file=sys.stderr)
            return cli.USAGE
        return cli.OK if pace(v)[1] else cli.ISSUES
    if args[:1] == ["--download"]:
        for name in args[1:] or names():
            download(lookup(name))
        return 0
    if args:
        print("usage: python3 tools/voices.py [--measured <voice> | --download [<voice>...]]", file=sys.stderr)
        return cli.USAGE
    print(f"{'name':24} {'engine':10} {'pace':16} model")
    estimated = False
    for name in names():
        try:
            v = lookup(name)
        except SystemExit as e:
            print(f"{name:24} {e}")
            continue
        p, exact = pace(v)
        estimated = estimated or not exact
        print(f"{v['name'][:24]:24} {v['engine']:10} {p:5.2f} chars/s{'' if exact else '*':1}   {v['model']}")
    if estimated:
        print("* estimated until the voice's first render (render the smoke test with it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
