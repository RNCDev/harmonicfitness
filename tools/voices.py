"""Voices: look one up, predict how long it will speak, fetch its model, and design new ones.

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

A new voice can be designed from a written description (Qwen3-TTS VoiceDesign, the
way the shipped coaches were made): `design` renders a few takes of a coaching line
in that voice, you listen and `keep` the best one, which becomes a private voice in
me/voices/ on the engine you choose and is added to your profile's voices.

    ./sweatcast voices                                  # list voices with their engine and pace
    ./sweatcast voices measured "Qwen3 Coach"           # exit 0 if measured, 1 if estimated, 64 if no such voice
    ./sweatcast voices download "Chatterbox Coach"      # fetch its pinned model (setup does this)
    ./sweatcast voices design "Coach Maya" "A woman in her thirties with a warm, mid-low voice ..." --play
    ./sweatcast voices keep "me/voices/.takes/Coach Maya-2.wav" --engine chatterbox --default
"""
import argparse
import contextlib
import hashlib
import json
import os
import shutil
import statistics
import sys
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from char_weight import weight  # noqa: E402,F401  (re-exported for render.py)
import cli  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402
import player  # noqa: E402
from paths import PACE_FILE, ROOT, VOICE_DIRS, show  # noqa: E402,F401

ENGINES = ("qwen3", "chatterbox")
# What runs the models here: MLX on a Mac, PyTorch (CUDA, or the processor) on Windows and Linux. A voice's .json
# names its MLX model at the top level and its PyTorch one under "torch", each pinned.
# SWEATCAST_BACKEND overrides the choice (the tests set it).
BACKENDS = ("mlx", "torch")
BACKEND = os.environ.get("SWEATCAST_BACKEND") or ("mlx" if sys.platform == "darwin" else "torch")
TORCH_ENGINES = ("chatterbox",)   # engines with a PyTorch path in tools/engines.py so far
# The engine's standard model when a voice names none, and the extra repos an
# engine loads on its own (Chatterbox Turbo's speech tokenizer), pinned so a
# fresh machine downloads exactly what was tested.
STANDARD_MODELS = {"qwen3": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
                   "chatterbox": "mlx-community/Chatterbox-TTS-fp16"}
# The local models each engine renders with, per backend, pinned to the revisions tested. A coach
# names only its engine; these strings are part of every pace and clip cache key, so they never change
# without a migration.
LOCAL_MODELS = {("chatterbox", "mlx"): ("mlx-community/chatterbox-turbo-fp16", "b2d0a13aa7cfff0a06d9acb247ae91c8f19a6d75"),
                ("chatterbox", "torch"): ("ResembleAI/chatterbox-turbo", "749d1c1a46eb10492095d68fbcf55691ccf137cd"),
                ("qwen3", "mlx"): ("mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16", "a6eb4f68e4b056f1215157bb696209bc82a6db48")}
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
    if BACKEND not in BACKENDS:
        raise SystemExit(f"SWEATCAST_BACKEND must be one of {', '.join(BACKENDS)}")
    if BACKEND == "torch":
        # No PyTorch model yet (Qwen3): the lint still works, and the render says why it can't.
        t = conf.get("torch") or {}
        model, revision, gen = t.get("model"), t.get("revision"), t.get("generate") or {}
    else:
        model, revision = conf.get("model") or STANDARD_MODELS[engine], conf.get("revision")
        gen = conf.get("generate") or {}
    return {"name": name, "engine": engine, "backend": BACKEND,
            "model": model, "revision": revision,
            "generate": gen,
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


def record_rate(v, weight, seconds, path=None, render_seconds=None):
    """Fold a render's measured speech into the voice's rate (called by render.py), and with
    render_seconds, this computer's render speed (seconds of rendering per second of speech).
    The coach's own pace.json when the voice names one. Locked, and written to a temporary
    file then renamed, so it's never half-written."""
    path = path or v.get("pace_file") or PACE_FILE
    with _locked(path):
        data = _recorded(path, strict=True)
        rec = data.get(_rate_key(v), {"weight": 0.0, "seconds": 0.0})
        rec["name"] = v["name"]
        rec["weight"] += weight
        rec["seconds"] += seconds
        if render_seconds and seconds > 0:
            rec.setdefault("speed", {})[speed_key(v)] = round(render_seconds / seconds, 3)
        data[_rate_key(v)] = rec
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)


def seed_pace(data):
    """A starting rate for a voice no render has measured: the median of the measured
    rates on file (entries with enough speech behind them), else DEFAULT_PACE. The
    reference clip's own rate is not used: for Chatterbox Coach it was 10.3 chars/s
    against a measured 14.6."""
    rates = [r["weight"] / r["seconds"] for r in data.values()
             if isinstance(r, dict) and r.get("weight") and (r.get("seconds") or 0) > MIN_MEASURED]
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


def design(name, description, line=DESIGN_LINE, takes=2, seed=7, folder=None, make_takes=None):
    """Render `takes` takes of `line` in a voice made from `description`. Each take is
    <name>-<n>.wav in me/voices/.takes, with <name>-<n>.txt holding the line and
    <name>-<n>.take.json how it was made. Returns the .wav paths. `make_takes` stands in
    for the model in tests."""
    folder = folder or paths.VOICE_TAKES
    os.makedirs(folder, exist_ok=True)
    if make_takes is None:
        import engines
        from render import render_lock

        def make_takes(desc, text, n, s):
            with render_lock(paths.CACHE):   # another model: one at a time in 16 GB
                return engines.design_takes(VOICE_DESIGN[0], VOICE_DESIGN[1], desc, text, n, s)
    out = []
    for n, pcm in enumerate(make_takes(description, line, takes, seed), 1):
        stem = os.path.join(folder, f"{name}-{n}")
        write_wav(stem + ".wav", pcm)
        with open(stem + ".txt", "w", encoding="utf-8") as f:
            f.write(line + "\n")
        with open(stem + ".take.json", "w", encoding="utf-8") as f:
            json.dump({"description": description, "line": line, "seed": seed + n - 1,
                       "model": VOICE_DESIGN[0], "revision": VOICE_DESIGN[1]}, f, indent=1)
        out.append(stem + ".wav")
    return out


def shipped_model(engine):
    """(model, revision) of the shipped voice on `engine`, so a new voice renders with
    the same tested weights."""
    folder = os.path.join(ROOT, "voices")
    for f in sorted(os.listdir(folder)):
        if f.endswith(".json"):
            with open(os.path.join(folder, f), encoding="utf-8") as j:
                conf = json.load(j)
            if conf.get("engine") == engine and conf.get("revision"):
                return conf.get("model") or STANDARD_MODELS[engine], conf["revision"]
    return STANDARD_MODELS[engine], None


def shipped_torch_model(engine):
    """The shipped voice's PyTorch model on `engine` ({"model", "revision"}), or None."""
    folder = os.path.join(ROOT, "voices")
    for f in sorted(os.listdir(folder)):
        if f.endswith(".json"):
            with open(os.path.join(folder, f), encoding="utf-8") as j:
                conf = json.load(j)
            if conf.get("engine") == engine and (conf.get("torch") or {}).get("model"):
                return {k: conf["torch"][k] for k in ("model", "revision") if k in conf["torch"]}
    return None


def keep(take, engine, name=None, description="", default=False, folder=None, profile_path=None, force=False):
    """Make a designed take (or any clip with a .txt of its words beside it) a private
    voice: me/voices/<name>.wav, .txt and .json, on `engine` at the shipped voice's
    model and revision, and add it to the profile's voices. Returns the voice's name."""
    import context
    if not os.path.exists(take):
        raise SystemExit(f"No take at {take}.")
    stem = os.path.splitext(take)[0]
    meta = {}
    if os.path.exists(stem + ".take.json"):
        with open(stem + ".take.json", encoding="utf-8") as f:
            meta = json.load(f)
    if not os.path.exists(stem + ".txt"):
        raise SystemExit(f"No {os.path.basename(stem)}.txt beside the take: it holds the clip's exact words.")
    name = name or os.path.basename(stem).rsplit("-", 1)[0]
    if engine not in ENGINES:
        raise SystemExit(f"engine must be one of {', '.join(ENGINES)}")
    folder = folder or paths.PRIVATE_VOICES
    dest = os.path.join(folder, name)
    if os.path.exists(dest + ".wav") and not force:
        raise SystemExit(f"{show(dest)}.wav already exists; pick another name or pass --force.")
    os.makedirs(folder, exist_ok=True)
    shutil.copyfile(take, dest + ".wav")
    shutil.copyfile(stem + ".txt", dest + ".txt")
    model, revision = shipped_model(engine)
    conf = {"engine": engine, "model": model, "revision": revision}
    torch_model = shipped_torch_model(engine)
    if torch_model:
        conf["torch"] = torch_model
    if meta.get("description"):
        conf["designed_from"] = meta["description"]
    with open(dest + ".json", "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=1)
    context.add_voice_to_profile(name, description or meta.get("description", ""), default,
                                 profile_path or paths.PROFILE)
    return name


def main():
    ap = cli.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="every voice with its engine, pace and model (the default)")
    m = sub.add_parser("measured", help="exit 0 if the voice's pace is measured, 1 if estimated, 64 if unknown")
    m.add_argument("voice")
    d = sub.add_parser("download", help="fetch voices' pinned models (all voices without a name)")
    d.add_argument("voice", nargs="*")
    g = sub.add_parser("design", help="render takes of a new voice made from a description")
    g.add_argument("name", help="the new voice's name, such as 'Coach Maya'")
    g.add_argument("description", help="who it is and how they sound (see knowledge/voices.md)")
    g.add_argument("--takes", type=int, default=2)
    g.add_argument("--line", default=DESIGN_LINE, help="what the takes say (the default is a coaching line)")
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--play", action="store_true", help="play each take after rendering, with the system's player")
    k = sub.add_parser("keep", help="make a take a voice in me/voices/ and add it to your profile")
    k.add_argument("take", help="the take's .wav (from design), or any clip with its words in a .txt beside it")
    k.add_argument("--engine", choices=ENGINES, default="chatterbox",
                   help="the model that speaks it: chatterbox (most natural, faster) or qwen3 (clearest)")
    k.add_argument("--name", help="the voice's name (default: the take's)")
    k.add_argument("--description", default="", help="for the check-in's voice question (default: the design description)")
    k.add_argument("--default", action="store_true", help="make it the default voice")
    k.add_argument("--force", action="store_true", help="replace a private voice of the same name")
    args = ap.parse_args()

    if args.cmd == "measured":
        try:
            v = lookup(args.voice)
        except SystemExit as e:   # an unknown voice or broken settings: a command mistake
            print(e.code, file=sys.stderr)
            return cli.USAGE
        return cli.OK if pace(v)[1] else cli.ISSUES
    if args.cmd == "download":
        for name in args.voice or names():
            download(lookup(name))
        return cli.OK
    if args.cmd == "design":
        print(f"Designing {args.name}: {args.takes} takes with {VOICE_DESIGN[0]} "
              f"(about {SIZES_GB[VOICE_DESIGN[0]]} GB the first time).", flush=True)
        takes = design(args.name, args.description, args.line, args.takes, args.seed)
        for t in takes:
            print(f"  {show(t)}")
            if args.play and not player.play(t):
                print("    (no audio player found here; open the file to listen)")
        print(f"Listen, then keep the best one, for example:\n"
              f"  ./sweatcast voices keep \"{show(takes[0])}\" --engine chatterbox --default\n"
              f"Not right? Run design again with a reworded description, or another --seed. The design "
              f"model can be removed from ~/.cache/huggingface/hub (models--{VOICE_DESIGN[0].replace('/', '--')}) "
              "once you're done.")
        return cli.OK
    if args.cmd == "keep":
        name = keep(args.take, args.engine, args.name, args.description, args.default, force=args.force)
        print(f"Kept {name} in {show(paths.PRIVATE_VOICES)} on {args.engine}, and added it to your profile"
              f"{' as the default voice' if args.default else ''}. Measure its pace with the smoke test:\n"
              f"  ./sweatcast build voices/smoke-test.draft.txt \"smoke-test\" --voice \"{name}\"")
        return cli.OK
    print(f"{'name':24} {'engine':10} {'pace':16} model ({BACKEND})")
    estimated = False
    for name in names():
        try:
            v = lookup(name)
        except SystemExit as e:
            print(f"{name:24} {e}")
            continue
        p, exact = pace(v)
        estimated = estimated or not exact
        print(f"{v['name'][:24]:24} {v['engine']:10} {p:5.2f} chars/s{'' if exact else '*':1}   "
              f"{v['model'] or 'none on ' + BACKEND + ' yet (the lint still works)'}")
    if estimated:
        print("* estimated until the voice's first render (render the smoke test with it)")
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
