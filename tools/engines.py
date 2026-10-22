"""The voice engines: load a voice's model and speak a line with it.

Everything that depends on another library's internals lives here, so an upgrade
breaks in one place: mlx-audio's model classes, huggingface_hub's download function
(patched while a model loads, to hold its extra downloads to their pinned revisions),
MLX's memory cache, and on Windows Resemble AI's PyTorch Chatterbox Turbo
(chatterbox-tts) on CUDA. render.py calls speaker(), runtime() and release(), and
nothing else touches mlx, mlx_audio, torch, chatterbox or huggingface_hub's loaders.

Which one runs is the voice's "backend" (tools/voices.py: mlx on a Mac, torch on
Windows), and with it the model: each voice's .json pins both.

The engines are tested with the mlx-audio version in uv.lock (TESTED_MLX_AUDIO; a
test keeps the two in step). Another version still runs, with a one-line warning.
"""
import contextlib
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voices import ENGINE_EXTRAS, TORCH_ENGINES, TORCH_PATTERNS  # noqa: E402

SR = 24000                     # every engine's output rate, in samples per second
TESTED_MLX_AUDIO = "0.5.0"     # the mlx-audio version uv.lock pins
TRIM_DB = -40.0                # engine silence below this level is trimmed from each clip's ends
TRIM_KEEP = 0.04               # seconds of it kept at each end


def mlx_audio_version():
    """The installed mlx-audio's version, or None where it isn't installed (tests, CI)."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version("mlx-audio")
    except (ImportError, PackageNotFoundError):
        return None
    except Exception:   # an odd install shouldn't stop a lint or a cache lookup
        return None


def _version(package):
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version(package)
    except (ImportError, PackageNotFoundError):
        return None
    except Exception:
        return None


def runtime(voice):
    """What speaks the voice, with versions, for the clip cache key and the build record.
    On a Mac it stays "mlx-audio <version>", as it always was, so cached clips still match."""
    if voice.get("backend") == "torch":
        return f"chatterbox-tts {_version('chatterbox-tts')} torch {_version('torch')}"
    return f"mlx-audio {mlx_audio_version()}"


def trim(a):
    """Cut the engine's lead-in and tail silence, keeping a short natural edge."""
    import numpy as np
    loud = np.flatnonzero(np.abs(a) > 10 ** (TRIM_DB / 20))
    if not len(loud):
        return a
    keep = int(TRIM_KEEP * SR)
    return a[max(loud[0] - keep, 0):loud[-1] + keep]


@contextlib.contextmanager
def pinned_extras(engine, hub=None):
    """While a model loads, fetch the repos its engine pulls in on its own (Chatterbox
    Turbo's speech tokenizer) at the revisions tools/voices.py pins. mlx-audio asks for
    their latest version and only warns if that fails, which would leave the voice
    quietly wrong; this fetches the pinned one first, failing loudly, and points
    mlx-audio's own request at it."""
    if hub is None:
        import huggingface_hub as hub
    pins = dict(ENGINE_EXTRAS.get(engine, []))
    for repo, rev in pins.items():
        try:
            hub.snapshot_download(repo, revision=rev)
        except Exception as e:
            raise SystemExit(f"Couldn't fetch {repo} at {rev[:8]}, which {engine} needs: {e}. "
                             "Check the network and rerun; ./sweatcast setup downloads it ahead of time.")
    if pins and not callable(getattr(hub, "hf_hub_download", None)):
        raise SystemExit("huggingface_hub no longer has hf_hub_download, which tools/engines.py pins "
                         "the engine's extra downloads through. Rerun ./sweatcast setup to restore the "
                         "locked versions.")
    original = hub.hf_hub_download

    def pinned(*args, **kwargs):
        repo = kwargs.get("repo_id", args[0] if args else None)
        if repo in pins:
            kwargs["revision"] = pins[repo]
        return original(*args, **kwargs)

    hub.hf_hub_download = pinned
    try:
        yield
    finally:
        hub.hf_hub_download = original


def to_pcm(a):
    """Float samples to 16-bit mono PCM, with the engine's edge silence trimmed."""
    import numpy as np
    return (np.clip(trim(np.asarray(a, dtype=np.float32).reshape(-1)), -1.0, 1.0) * 32767).astype("<i2").tobytes()


def speaker(voice):
    """Load the voice's model (Qwen3-TTS or Chatterbox through mlx-audio, or Chatterbox
    Turbo through PyTorch) and return say(text, seed) -> 16-bit mono PCM at SR, cloning
    the voice's reference clip."""
    if voice.get("backend") == "torch":
        return _torch_speaker(voice)
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    found = mlx_audio_version()
    if found and found != TESTED_MLX_AUDIO:
        print(f"Warning: mlx-audio {found} is installed; sweatcast is tested with {TESTED_MLX_AUDIO}. "
              "Rerun ./sweatcast setup to restore the locked version if a voice sounds wrong.", file=sys.stderr)
    engine = voice["engine"]
    with pinned_extras(engine):
        model = load_model(voice["model"], revision=voice["revision"])
    gen = voice.get("generate") or {}   # per-voice engine settings, from voices/<name>.json
    # Chatterbox Turbo re-encodes the reference clip on every call that passes it
    # (about half a second each) and keeps the result on the model. So pass it on the
    # first clip only: the same code path computes the same conditioning, once.
    # The full-size Chatterbox keeps nothing (without the clip it falls back to its
    # built-in voice), and Qwen3 caches its reference codes itself, so both pass it
    # every time. mlx-audio has no public flag for this, so it's told by class name.
    keeps_conditioning = type(model).__name__ == "ChatterboxTurboTTS"
    primed = []

    def say(text, seed):
        mx.random.seed(seed)
        if engine == "qwen3":
            results = model.generate(text=text, ref_audio=voice["ref_audio"], ref_text=voice["ref_text"],
                                     verbose=False, **gen)
        elif keeps_conditioning and primed:
            results = model.generate(text=text, verbose=False, **gen)
        else:
            results = model.generate(text=text, ref_audio=voice["ref_audio"], verbose=False, **gen)
            primed.append(True)
        with contextlib.redirect_stdout(io.StringIO()):   # the models print progress per clip
            results = list(results)
        if results[0].sample_rate != SR:
            raise SystemExit(f"{engine} returned {results[0].sample_rate} Hz audio; expected {SR}")
        a = np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in results])
        return (np.clip(trim(a), -1.0, 1.0) * 32767).astype("<i2").tobytes()
    return say


def _torch_speaker(voice):
    """Chatterbox Turbo on an NVIDIA GPU, with Resemble AI's own PyTorch release. The
    reference clip is encoded once and kept on the model, as the MLX path does."""
    if voice["engine"] not in TORCH_ENGINES or not voice["model"]:
        raise SystemExit(f"{voice['name']} runs on {voice['engine']}, which has no PyTorch model here yet, "
                         "so it only renders on a Mac. On this PC, pick a Chatterbox voice with --voice.")
    import numpy as np
    import torch
    if not torch.cuda.is_available():
        raise SystemExit("PyTorch can't see an NVIDIA GPU (CUDA). Check the graphics driver with nvidia-smi, "
                         "then rerun ./sweatcast setup.")
    # tools/ is on sys.path, so its coverage.py would pass for the coverage package that
    # numba (under librosa) probes for, and break its import. Mark that package absent.
    if "coverage" not in sys.modules:
        sys.modules["coverage"] = None
    from huggingface_hub import snapshot_download
    try:
        path = snapshot_download(voice["model"], revision=voice["revision"], allow_patterns=TORCH_PATTERNS)
    except Exception as e:
        raise SystemExit(f"Couldn't fetch {voice['model']} at {(voice['revision'] or 'latest')[:8]}: {e}. "
                         "Check the network and rerun; ./sweatcast setup downloads it ahead of time.")
    from chatterbox.tts_turbo import ChatterboxTurboTTS
    with contextlib.redirect_stdout(io.StringIO()):
        model = ChatterboxTurboTTS.from_local(path, "cuda")
        model.prepare_conditionals(voice["ref_audio"])
    if model.sr != SR:
        raise SystemExit(f"chatterbox returned {model.sr} Hz audio; expected {SR}")
    gen = voice.get("generate") or {}

    def say(text, seed):
        torch.manual_seed(seed)   # seeds the GPU too
        with torch.inference_mode(), contextlib.redirect_stdout(io.StringIO()):
            wav = model.generate(text, **gen)
        return to_pcm(wav.squeeze(0).cpu().numpy())
    return say


def design_takes(model_repo, revision, description, line, takes, seed):
    """Qwen3-TTS VoiceDesign: `takes` takes of `line` spoken by a voice made from
    `description`, as 16-bit mono PCM at SR. Each take uses its own seed."""
    from voices import BACKEND
    if BACKEND != "mlx":
        raise SystemExit("Designing a voice needs Qwen3-TTS VoiceDesign on MLX, so it runs on a Mac only for now.")
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    model = load_model(model_repo, revision=revision)
    out = []
    for n in range(takes):
        mx.random.seed(seed + n)
        with contextlib.redirect_stdout(io.StringIO()):
            results = list(model.generate(text=line, instruct=description, verbose=False))
        if not results or results[0].sample_rate != SR:
            raise SystemExit("The design model returned no audio, or not at 24 kHz.")
        a = np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in results])
        out.append((np.clip(trim(a), -1.0, 1.0) * 32767).astype("<i2").tobytes())
    del model
    release()
    return out


def release():
    """Hand the model's memory back once the last reference to say() is gone, so
    assembling and encoding the MP3 don't run with the model still loaded."""
    import gc
    gc.collect()
    if "torch" in sys.modules:
        try:
            sys.modules["torch"].cuda.empty_cache()
        except Exception:
            pass
    try:
        import mlx.core as mx
        clear = getattr(mx, "clear_cache", None) or getattr(getattr(mx, "metal", None), "clear_cache", None)
        if clear:
            clear()
    except Exception:
        pass
