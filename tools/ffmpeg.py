"""Find ffmpeg (the one on PATH, else the copy imageio-ffmpeg brings into the environment), and run it.

Every ffmpeg the engine starts goes through run() (or to_mp3()), with a timeout: a failure or a hang stops
with errors.RenderStopped naming ffmpeg's version, its exit code and the end of what it said, never a
traceback, and never a build waiting forever under the render lock.

HarmonicFitness needs only ffmpeg itself (not ffprobe), with the MP3 encoder (libmp3lame) and the
loudness filter (loudnorm). imageio-ffmpeg 0.6.0's ffmpeg 7.1 has both on an Apple Silicon Mac
(checked 2026-10-24); ./harmonicfitness doctor checks whichever one is found, on every system.
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402


def exe():
    """The ffmpeg to run, or None."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        return path if path and os.path.exists(path) else None
    except Exception:   # not installed (CI, an old environment), or no binary for this system
        return None


def bundled(path):
    return "imageio_ffmpeg" in (path or "")


def capable(path):
    """(has the MP3 encoder, has the loudness filter) for the ffmpeg at `path`."""
    def listing(flag):
        try:
            return subprocess.run([path, "-hide_banner", flag], capture_output=True, text=True, timeout=30).stdout
        except (OSError, subprocess.SubprocessError):
            return ""
    return "libmp3lame" in listing("-encoders"), "loudnorm" in listing("-filters")


def version(path=None):
    """The first line of `ffmpeg -version` for the ffmpeg at `path` (else the one found), or None."""
    path = path or exe()
    if not path:
        return None
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=10).stdout
        return out.splitlines()[0] if out else None
    except (OSError, subprocess.SubprocessError):
        return None


def _text(out):
    return out.decode("utf-8", "replace") if isinstance(out, bytes) else (out or "")


def run(args, what, timeout, input=None, check=True):
    """Run ffmpeg: `args` is the whole command, the binary first. Text in and out, or bytes when `input` is
    bytes. A failure (with `check`) or a run past `timeout` seconds raises RenderStopped: "ffmpeg couldn't
    <what> (<version>, exit <n>): <the last 300 characters it said>"."""
    try:
        return subprocess.run(args, input=input, capture_output=True, text=not isinstance(input, bytes),
                              check=check, timeout=timeout)
    except subprocess.CalledProcessError as e:
        tail = _text(e.stderr).strip()[-300:]
        raise errors.RenderStopped(f"ffmpeg couldn't {what} ({version(args[0]) or 'ffmpeg'}, exit {e.returncode}): "
                                   f"{tail or 'no reason given'}") from None
    except subprocess.TimeoutExpired:
        raise errors.RenderStopped(f"ffmpeg couldn't {what} ({version(args[0]) or 'ffmpeg'}): it was still running "
                                   f"after {timeout:g} seconds, so it was stopped.") from None


def to_mp3(src, dst, bitrate="48k", mono=True, start=None, length=None, timeout=120, what=None, path=None):
    """Encode `src` as an MP3 at `bitrate` (mono unless told otherwise), from `start` seconds for `length`
    seconds when given, with the ffmpeg at `path` (else the one found). Raises RenderStopped as run() does."""
    path = path or exe()
    if not path:
        raise errors.RenderStopped(f"ffmpeg not found; install it ({install_hint()})")
    cmd = [path, "-hide_banner", "-loglevel", "error", "-y"]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", src]
    if length is not None:
        cmd += ["-t", f"{length:.3f}"]
    if mono:
        cmd += ["-ac", "1"]
    cmd += ["-c:a", "libmp3lame", "-b:a", str(bitrate), dst]
    return run(cmd, what or f"encode {os.path.basename(dst)}", timeout)


def install_hint():
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform == "win32":
        return "winget install Gyan.FFmpeg.Essentials"
    return "your system's package manager, for example sudo apt install ffmpeg"


def status():
    """One line on the ffmpeg found, for setup."""
    path = exe()
    if not path:
        return f"ffmpeg: not found; install it ({install_hint()})"
    mp3, loud = capable(path)
    where = "the environment's own copy" if bundled(path) else path
    if mp3 and loud:
        return f"ffmpeg: {where}, with MP3 encoding and loudness normalization"
    return f"ffmpeg: {where} can't encode MP3 or normalize loudness; install a full build ({install_hint()})"


if __name__ == "__main__":
    print(status())
