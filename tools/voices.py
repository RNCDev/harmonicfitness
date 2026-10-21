#!/usr/bin/env python3
"""Voices: look one up, and predict how long it will speak.

A voice is a reference clip plus its transcript: one saved in the VoiceStudio app,
or one kept in this repo's voices/ folder (<name>.wav, <name>.txt, and optionally
<name>.json naming its engine: omnivoice, qwen3 or chatterbox; omnivoice if absent;
optionally the engine's model repo and "generate", extra settings for each clip).

For OmniVoice voices:

OmniVoice fixes each clip's length before it generates anything: the text's
weighted character count divided by the reference clip's pace
(omnivoice/utils/duration.py). So spoken seconds can be predicted from the text
and the voice alone, with no model load. This file mirrors that arithmetic using
OmniVoice's own estimator and chunker, imported by path (both are stdlib-only),
so it runs on the system python3 as well as VoiceStudio's.

The prediction is an upper bound. It was within about two percent on normal
paragraphs, but a cue of one to three words can come out up to a second shorter
with some voices, because OmniVoice stretches very short text and then trims the
silence it leaves.

Qwen3-TTS and Chatterbox decide their length as they speak, so for them the
prediction is the voice's measured rate (weighted characters per second, recorded
by each render) applied to the text. It is an estimate, typically within a few
percent over a whole segment; render.py absorbs the difference in the padding.
Until a voice's first render, its rate is seeded from the other voices' measured
rates: a reference clip's own rate came out about 30 percent slow for Coach E.
The character weights are vendored in char_weight.py, so this path needs no
VoiceStudio files.

    python3 tools/voices.py                     # list voices with their engine and pace
    python3 tools/voices.py --measured "Coach G"   # exit 0 if its rate is measured, 1 if estimated
"""
import functools
import hashlib
import importlib.util
import json
import os
import re
import sqlite3
import statistics
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from char_weight import weight  # noqa: E402  (OmniVoice's weights, vendored)

VS_DATA = os.path.expanduser("~/Library/Application Support/OmniVoice")
VS_PROJECT = os.path.expanduser("~/Library/Application Support/VoiceStudio/runtime/project")
VS_PYTHON = os.path.join(VS_PROJECT, ".venv", "bin", "python")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACE_FILE = os.path.join(ROOT, "workouts", ".audio-cache", "voice-pace.json")
VOICES_DIR = os.path.join(ROOT, "voices")
ENGINES = ("omnivoice", "qwen3", "chatterbox")
MLX_EDGE = 0.08          # render.py trims engine silence to 40 ms at each end
MIN_MEASURED = 30.0      # seconds of rendered speech before a voice's rate counts as measured
DEFAULT_PACE = 14.5      # weighted chars/s for a new voice when no voice has been measured yet

FRAME_RATE = 25          # OmniVoice audio tokens per second
EDGE_PAD = 0.2           # fade_and_pad_audio adds 0.1 s of silence at each end
CHUNK_THRESHOLD = 30.0   # OmniVoiceGenerationConfig.audio_chunk_threshold
CHUNK_DURATION = 15.0    # OmniVoiceGenerationConfig.audio_chunk_duration
CHUNK_GAP = 0.3          # cross_fade_chunks silence between chunks


def use_voicestudio_python():
    """OmniVoice's text helpers need Python 3.11 or newer, and stock macOS ships 3.9.
    When a tool is run directly on an older Python, rerun it under VoiceStudio's."""
    if sys.version_info < (3, 11) and os.access(VS_PYTHON, os.X_OK):
        os.execv(VS_PYTHON, [VS_PYTHON, *sys.argv])


@functools.lru_cache(maxsize=None)
def _omnivoice_util(name):
    path = os.path.join(VS_PROJECT, "omnivoice", "utils", f"{name}.py")
    if not os.path.exists(path):
        raise SystemExit(f"OmniVoice not found at {path} (open the VoiceStudio app once to install it)")
    spec = importlib.util.spec_from_file_location(f"_omnivoice_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@functools.lru_cache(maxsize=None)
def _estimator():
    return _omnivoice_util("duration").RuleDurationEstimator()


@functools.lru_cache(maxsize=None)
def _design_sample_script():
    """What a designed voice's sample says when it was saved without a custom line
    (the app stores an empty transcript for it; archetypes.py _FALLBACK_SCRIPT)."""
    path = os.path.join(VS_PROJECT, "backend", "api", "routers", "archetypes.py")
    try:
        with open(path, encoding="utf-8") as f:
            m = re.search(r'^_FALLBACK_SCRIPT = "(.+)"$', f.read(), re.MULTILINE)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "Here's a quick sample of this voice so you can hear how it sounds."


def _repo_voice(voice):
    """A voice kept in this repo: voices/<name>.wav plus its transcript, voices/<name>.txt."""
    for f in os.listdir(VOICES_DIR) if os.path.isdir(VOICES_DIR) else []:
        name, ext = os.path.splitext(f)
        if ext == ".wav" and name.lower() == voice.lower():
            path = os.path.join(VOICES_DIR, f)
            with open(os.path.join(VOICES_DIR, name + ".txt"), encoding="utf-8") as t:
                ref_text = t.read().strip()
            with open(path, "rb") as a:
                audio_hash = hashlib.sha256(a.read()).hexdigest()
            engine, model, generate = "omnivoice", None, {}
            settings = os.path.join(VOICES_DIR, name + ".json")
            if os.path.exists(settings):
                with open(settings, encoding="utf-8") as j:
                    conf = json.load(j)
                engine, model = conf.get("engine", engine), conf.get("model")
                generate = conf.get("generate") or {}
            if engine not in ENGINES:
                raise SystemExit(f"{settings}: engine must be one of {', '.join(ENGINES)}")
            return {"id": name, "name": name, "kind": "repo", "engine": engine, "model": model,
                    "generate": generate,
                    "ref_audio": path, "ref_text": ref_text,
                    "instruct": "", "vd_states": None, "seed": None,
                    "key": hashlib.sha256(f"{audio_hash}|{ref_text}".encode()).hexdigest()[:12]}
    return None


def lookup(voice):
    """A voice by name: one kept in this repo's voices/ folder, else a VoiceStudio
    voice profile by id or name, resolved the way the app does."""
    found = _repo_voice(voice)
    if found:
        return found
    db = os.path.join(VS_DATA, "omnivoice.db")
    if not os.path.exists(db):
        here = sorted(os.path.splitext(f)[0] for f in os.listdir(VOICES_DIR) if f.endswith(".wav")) \
            if os.path.isdir(VOICES_DIR) else []
        raise SystemExit(f"No voice '{voice}' in voices/ ({', '.join(here) or 'none'}), "
                         "and no VoiceStudio voice database to look in.")
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM voice_profiles WHERE id=? OR name=? COLLATE NOCASE",
                           (voice, voice)).fetchone()
        if not row:
            names = [f"{r['name']} ({r['id']})" for r in conn.execute("SELECT id, name FROM voice_profiles")]
            raise SystemExit(f"No VoiceStudio voice '{voice}'. Available: {', '.join(names)}")
    # A locked take wins; otherwise the clone recording or the design's rendered sample.
    audio = row["locked_audio_path"] if row["is_locked"] and row["locked_audio_path"] else row["ref_audio_path"]
    if not audio:
        raise SystemExit(f"Voice '{row['name']}' has no audio sample yet. Open it once in VoiceStudio "
                         "(it renders the sample on first use), quit the app, and rerun.")
    path = os.path.join(VS_DATA, "voices", audio)
    with open(path, "rb") as f:
        audio_hash = hashlib.sha256(f.read()).hexdigest()
    ref_text = row["ref_text"] or ""
    if not ref_text and (row["kind"] or "clone") == "design" and audio == row["ref_audio_path"]:
        # Without a transcript, OmniVoice would fall back to a dummy pace and try to
        # auto-transcribe with a model that isn't installed.
        ref_text = _design_sample_script()
    if not ref_text:
        raise SystemExit(f"Voice '{row['name']}' has no transcript. Add one to it in VoiceStudio and rerun.")
    return {
        "id": row["id"], "name": row["name"], "kind": row["kind"] or "clone", "engine": "omnivoice",
        "ref_audio": path, "ref_text": ref_text,
        "instruct": row["instruct"] or "", "vd_states": row["vd_states"], "seed": row["seed"],
        "key": hashlib.sha256(f"{audio_hash}|{ref_text}".encode()).hexdigest()[:12],
    }


def _audio_seconds(path):
    try:
        with wave.open(path) as w:
            return w.getnframes() / w.getframerate()
    except (wave.Error, EOFError):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                              "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
        return float(out.stdout.strip())


def _recorded():
    try:
        with open(PACE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def record(v, ref_text, ref_tokens):
    """Save the exact reference length the model measured (called by render.py)."""
    data = _recorded()
    data[v["key"]] = {"name": v["name"], "ref_text": ref_text, "ref_tokens": int(ref_tokens)}
    os.makedirs(os.path.dirname(PACE_FILE), exist_ok=True)
    with open(PACE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def reference(v):
    """(ref_text, ref_tokens, exact). Exact once a render has recorded it; until then
    the raw clip length, which is never shorter than the trimmed one the model uses,
    so the estimate errs toward longer speech."""
    rec = _recorded().get(v["key"])
    if rec:
        return rec["ref_text"], rec["ref_tokens"], True
    text = _omnivoice_util("text").add_punctuation(v["ref_text"])
    return text, _audio_seconds(v["ref_audio"]) * FRAME_RATE, False


def _rate_key(v):
    return f"{v['key']}|{v['engine']}|{v.get('model') or 'standard'}"


def record_rate(v, weight, seconds):
    """Fold a render's measured speech into the voice's rate (non-OmniVoice engines)."""
    data = _recorded()
    rec = data.get(_rate_key(v), {"name": v["name"], "weight": 0.0, "seconds": 0.0})
    rec["weight"] += weight
    rec["seconds"] += seconds
    data[_rate_key(v)] = rec
    os.makedirs(os.path.dirname(PACE_FILE), exist_ok=True)
    with open(PACE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)


def seed_pace(data=None):
    """A starting rate for a voice no render has measured: the median of the measured
    rates on file (only entries with both weight and seconds; OmniVoice entries hold
    reference tokens instead), else DEFAULT_PACE. The reference clip's own rate is
    not used: for Coach E it was 10.3 chars/s against a measured 14.6."""
    data = _recorded() if data is None else data
    rates = [r["weight"] / r["seconds"] for r in data.values()
             if isinstance(r, dict) and r.get("weight") and (r.get("seconds") or 0) > MIN_MEASURED]
    return statistics.median(rates) if rates else DEFAULT_PACE


def pace(v):
    """Weighted characters per second: the voice's speaking rate, and whether it's measured."""
    if v["engine"] != "omnivoice":
        rec = _recorded().get(_rate_key(v))
        if rec and rec["seconds"] > MIN_MEASURED:
            return rec["weight"] / rec["seconds"], True
        return seed_pace(), False
    ref_text, ref_tokens, exact = reference(v)
    return _estimator().calculate_total_weight(ref_text) / (ref_tokens / FRAME_RATE), exact


def _tokens(text, ref_text, ref_tokens, speed):
    # Mirrors OmniVoice._estimate_target_tokens.
    est = _estimator().estimate_duration(text, ref_text, ref_tokens)
    if speed and speed != 1.0:
        est = est / speed
    return max(1, int(est))


def clip_seconds(text, v, speed=None):
    """Predicted length of one generate() call on `text`, including edge padding."""
    if v["engine"] != "omnivoice":
        return weight(text) / pace(v)[0] + MLX_EDGE
    ref_text, ref_tokens, _ = reference(v)
    tokens = _tokens(text, ref_text, ref_tokens, speed)
    if tokens <= CHUNK_THRESHOLD * FRAME_RATE:
        return tokens / FRAME_RATE + EDGE_PAD
    # Long text is split at punctuation into chunks of about fifteen seconds, each
    # estimated on its own, and joined with short silences (OmniVoice._generate_chunked).
    chunk_len = int(CHUNK_DURATION * FRAME_RATE / (tokens / len(text)))
    chunks = _omnivoice_util("text").chunk_text_punctuation(text=text, chunk_len=chunk_len, min_chunk_len=3)
    total = sum(_tokens(c, ref_text, ref_tokens, speed) for c in chunks) / FRAME_RATE
    return total + CHUNK_GAP * (len(chunks) - 1) + EDGE_PAD


def main():
    if sys.argv[1:2] == ["--measured"]:
        if len(sys.argv) != 3:
            raise SystemExit("usage: python3 tools/voices.py --measured <voice>")
        return 0 if pace(lookup(sys.argv[2]))[1] else 1
    db = os.path.join(VS_DATA, "omnivoice.db")
    ids = []
    if os.path.exists(db):
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            ids = [r[0] for r in conn.execute("SELECT id FROM voice_profiles ORDER BY created_at")]
    if os.path.isdir(VOICES_DIR):
        ids = sorted(os.path.splitext(f)[0] for f in os.listdir(VOICES_DIR) if f.endswith(".wav")) + ids
    print(f"{'name':28} {'id':10} {'engine':10} pace")
    for vid in ids:
        try:
            v = lookup(vid)
        except SystemExit as e:
            print(f"{vid:39} {e}")
            continue
        p, exact = pace(v)
        print(f"{v['name'][:28]:28} {v['id'][:10]:10} {v['engine']:10} {p:5.2f} chars/s"
              + ("" if exact else " (estimated until its first render)"))


if __name__ == "__main__":
    use_voicestudio_python()
    sys.exit(main())
