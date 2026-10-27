"""16-bit mono PCM as WAV: the one writer the engine and the maintainer's coach tools share. Standard library
only, so any module can use it without importing the engine."""
import io
import os
import wave


def wav_bytes(pcm, rate=24000):
    """A WAV file's bytes holding 16-bit mono `pcm` at `rate`."""
    buf = io.BytesIO()
    _write(buf, pcm, rate)
    return buf.getvalue()


def write_wav(path, pcm, rate=24000):
    """16-bit mono `pcm` at `rate` to a .wav file at `path`, making its folder."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    _write(path, pcm, rate)


def _write(target, pcm, rate):
    with wave.open(target, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(pcm)
