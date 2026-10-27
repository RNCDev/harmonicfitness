"""What the coach tools share (maintainer only): Pocket TTS and the take checker's recognizer, in the engine's own
environment (.venv), as a listener's build runs them.

speak() returns Pocket's untrimmed audio, as the takes were always judged: the engine trims each clip's quiet
edges at -40 dB, which would clip the soft start of a lone number ("six"); cues.py trims its own way.
"""
import contextlib
import io
import os
import subprocess
import sys
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
COACHES = os.path.join(ROOT, "coaches")
sys.path.insert(0, TOOLS)
import engines  # noqa: E402
import ffmpeg as ffmpeg_tool  # noqa: E402
import paths  # noqa: E402,F401  (points Hugging Face at models/)
import voices  # noqa: E402

LANGUAGE = voices.POCKET_LANGUAGE
SR = engines.SR


def folder(slug):
    return os.path.join(COACHES, f"coach-{slug}-local")


def pcm_24k(path):
    """A file as 16-bit mono PCM at 24 kHz (ffmpeg resamples)."""
    out = subprocess.run([ffmpeg_tool.exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le",
                          "-"], capture_output=True, check=True)
    return out.stdout


def write_wav(path, pcm):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm)


def speak(slug, lines, seeds, out):
    """Pocket (the public model, as listeners run it) speaks each line of `lines` ([{"id", "text"}]) in each seed,
    with coach `slug`'s voice file: out/<seed>/<id>.wav, untrimmed."""
    import numpy as np
    import torch
    from pocket_tts import TTSModel
    with engines.public_only(), contextlib.redirect_stdout(io.StringIO()):
        model = TTSModel.load_model(language=LANGUAGE)
    if model.has_voice_cloning:
        raise SystemExit("Pocket loaded its gated model; the coach tools must hear what listeners hear.")
    state = model.get_state_for_audio_prompt(os.path.join(folder(slug), "pocket.safetensors"))
    for seed in seeds:
        for line in lines:
            torch.manual_seed(seed)
            with contextlib.redirect_stdout(io.StringIO()):
                a = model.generate_audio(state, line["text"]).float().cpu().numpy().reshape(-1)
            pcm = (np.clip(a, -1.0, 1.0) * 32767).astype("<i2").tobytes()
            write_wav(os.path.join(out, str(seed), line["id"] + ".wav"), pcm)
        print(f"  {slug} seed {seed}: {len(lines)} line(s)", flush=True)


def transcribe(wavs):
    """{wav path: what the take checker's recognizer heard}."""
    if not wavs:
        return {}
    print(f"Transcribing {len(wavs)} take(s) with Parakeet 0.6B (ONNX)", flush=True)
    hear = engines.listener()
    return {w: hear(pcm_24k(w)) for w in wavs}
