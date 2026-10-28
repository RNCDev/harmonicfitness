"""The voice engine: load a coach's voice and speak a line with it.

Everything that depends on another library's internals lives here, so an upgrade breaks in one place: Kyutai's
Pocket TTS (pocket_tts) on PyTorch, and the take check's recognizer (onnx_asr). render.py calls speaker(),
listener(), runtime() and release(), and nothing else touches pocket_tts, torch or onnx_asr.

Pocket runs the public model (voices.POCKET_REPO), which can't clone a clip but loads a coach's saved voice
state (pocket.safetensors). Pocket tries the gated cloning model first and falls back to the public one only
when that fails, so a listener with a Hugging Face login that accepted the gated model's terms would get it
silently; public_only() makes that first try fail, and speaker() refuses a model that can clone anyway.
"""
import contextlib
import io
import os
import sys
import warnings

# The engines warn about their own dependencies; in a render log that buried the lines that matter.
os.environ.setdefault("TQDM_DISABLE", "1")
for _message in ("pkg_resources is deprecated",):
    warnings.filterwarnings("ignore", message=_message)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import voices  # noqa: E402

SR = 24000                     # the engine's output rate, in samples per second
TRIM_DB = -40.0                # engine silence below this level is trimmed from each clip's ends
TRIM_KEEP = 0.04               # seconds of it kept at each end


def _version(package):
    """The installed version of `package`, or None where it isn't installed (tests, CI)."""
    try:
        from importlib.metadata import PackageNotFoundError, version
        return version(package)
    except (ImportError, PackageNotFoundError):
        return None
    except Exception:   # an odd install shouldn't stop a lint or a cache lookup
        return None


def runtime(voice):
    """What speaks the voice, with versions, for the clip cache key and the build record."""
    if voice.get("backend") == "cloud":
        return f"{voice['service']} {voice['model']}"
    return (f"pocket-tts {_version('pocket-tts')} {voice.get('language') or voices.POCKET_LANGUAGE} "
            f"torch {_version('torch')} {voice.get('device') or 'cpu'}")


def trim(a):
    """Cut the engine's lead-in and tail silence, keeping a short natural edge."""
    import numpy as np
    loud = np.flatnonzero(np.abs(a) > 10 ** (TRIM_DB / 20))
    if not len(loud):
        return a
    keep = int(TRIM_KEEP * SR)
    return a[max(loud[0] - keep, 0):loud[-1] + keep]


def to_pcm(a):
    """Float samples to 16-bit mono PCM, with the engine's edge silence trimmed."""
    import numpy as np
    return (np.clip(trim(np.asarray(a, dtype=np.float32).reshape(-1)), -1.0, 1.0) * 32767).astype("<i2").tobytes()


def cuda_available():
    """Whether PyTorch sees an NVIDIA card; False where PyTorch isn't installed."""
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False


def torch_device(cuda_available):
    """Where PyTorch renders: the NVIDIA card when it can see one, else the processor. HARMONICFITNESS_DEVICE=cpu or
    cuda overrides."""
    forced = os.environ.get("HARMONICFITNESS_DEVICE", "").strip().lower()
    if forced in ("cpu", "cuda"):
        return forced
    return "cuda" if cuda_available else "cpu"


@contextlib.contextmanager
def public_only(module=None):
    """While Pocket loads, refuse its request for the gated model's files, so it takes the public model whatever
    login this computer has."""
    if module is None:
        import pocket_tts.models.tts_model as module
    original = module.download_if_necessary
    gated = f"hf://{voices.GATED_POCKET}/"

    def public(path, *args, **kwargs):
        if str(path).startswith(gated):
            raise PermissionError("harmonicfitness uses the public Pocket TTS model only")
        return original(path, *args, **kwargs)

    module.download_if_necessary = public
    try:
        yield
    finally:
        module.download_if_necessary = original


def speaker(voice):
    """Load the coach's voice and return say(text, seed) -> 16-bit mono PCM at SR."""
    if voice.get("backend") == "cloud":
        import cloud
        return cloud.speaker(voice)
    import torch
    try:
        from pocket_tts import TTSModel
    except ImportError as e:
        raise errors.EngineError("Pocket TTS isn't installed in this environment: run ./harmonicfitness setup.") from e
    found = _version("pocket-tts")
    if found and found != voices.POCKET_VERSION:
        raise errors.EngineError(f"pocket-tts {found} is installed; the coaches' voice files are made for "
                         f"{voices.POCKET_VERSION}. Run ./harmonicfitness setup to restore the locked version.")
    device = voice.get("device") or torch_device(torch.cuda.is_available())
    try:
        with public_only(), contextlib.redirect_stdout(io.StringIO()):
            model = TTSModel.load_model(language=voice.get("language") or voices.POCKET_LANGUAGE)
    except Exception as e:
        raise load_error("Pocket TTS", voices.POCKET_REPO, e, "./harmonicfitness setup downloads it ahead of time") from e
    if model.has_voice_cloning:
        raise errors.EngineError("Pocket TTS loaded its gated cloning model, not the public one HarmonicFitness uses. "
                         "Run ./harmonicfitness setup again, then retry.")
    if model.sample_rate != SR:
        raise errors.EngineError(f"Pocket TTS returned {model.sample_rate} Hz audio; expected {SR}")
    if device == "cuda":
        model = model.to("cuda")
    state = model.get_state_for_audio_prompt(voice["voice_state"])

    def say(text, seed):
        torch.manual_seed(seed)   # seeds the GPU too
        with contextlib.redirect_stdout(io.StringIO()):   # no inference_mode: Pocket's own threads
            audio = model.generate_audio(state, text)          # don't inherit torch.inference_mode)
        return to_pcm(audio.float().cpu().numpy())
    return say


def network_error(e):
    """Whether `e` (or what caused it) is a download that couldn't reach Hugging Face."""
    import socket
    import urllib.error
    while e is not None:
        if isinstance(e, (ConnectionError, TimeoutError, socket.timeout, socket.gaierror, urllib.error.URLError)):
            return True
        if type(e).__module__.startswith(("requests", "urllib3", "httpx")) or type(e).__name__ in (
                "HfHubHTTPError", "LocalEntryNotFoundError", "OfflineModeIsEnabled"):
            return True
        e = e.__cause__ or e.__context__
    return False


def load_error(what, where, e, fix):
    """An EngineError for a model that wouldn't load: the network's advice only when it was the network, and
    otherwise what actually went wrong (out of memory, a damaged file, a library that changed), by name."""
    if network_error(e):
        return errors.EngineError(f"Couldn't load {what} ({where}): {e}. Check the network and rerun; {fix}.")
    if isinstance(e, MemoryError) or "out of memory" in str(e).lower():
        return errors.EngineError(f"Couldn't load {what}: this computer ran out of memory. Close other apps and "
                                  "rerun.")
    return errors.EngineError(f"Couldn't load {what} ({where}): {type(e).__name__}: {e}. If its files are "
                              f"damaged, ./harmonicfitness setup fetches them again; {fix}.")


def listener():
    """Load the speech recognizer that checks local takes (voices.CHECK_MODEL, Parakeet through ONNX, on the
    processor) and return hear(pcm) -> the words it heard in 16-bit mono PCM at SR."""
    import numpy as np
    try:
        import onnx_asr
    except ImportError as e:
        raise errors.EngineError("The take checker isn't installed in this environment: run ./harmonicfitness setup, or "
                         "build with --no-check.") from e
    missing = [f for f in voices.CHECK_FILES if not os.path.exists(os.path.join(voices.CHECK_DIR, f))]
    if missing:
        try:
            voices.download()
        except Exception as e:
            raise errors.EngineError(f"Couldn't fetch the take checker ({voices.CHECK_MODEL[0]}): {e}. Check the network "
                             "and rerun (./harmonicfitness setup downloads it ahead of time), or build with --no-check.")
    try:
        model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", voices.CHECK_DIR, providers=["CPUExecutionProvider"])
    except Exception as e:
        raise load_error("the take checker", voices.CHECK_DIR, e, "or build with --no-check") from e

    def hear(pcm):
        a = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        text = model.recognize(a, sample_rate=SR)
        return (text if isinstance(text, str) else str(text)).strip()
    return hear


def release():
    """Hand the model's memory back once the last reference to say() is gone, so assembling and encoding the MP3
    don't run with the model still loaded."""
    import gc
    gc.collect()
    if "torch" in sys.modules:
        try:
            sys.modules["torch"].cuda.empty_cache()
        except Exception:
            pass
