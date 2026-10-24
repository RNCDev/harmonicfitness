"""Find ffmpeg: the one on PATH, else the copy imageio-ffmpeg brings into the environment.

sweatcast needs only ffmpeg itself (not ffprobe), with the MP3 encoder (libmp3lame) and the
loudness filter (loudnorm). imageio-ffmpeg 0.6.0's ffmpeg 7.1 has both on an Apple Silicon Mac
(checked 2026-10-24); ./sweatcast doctor checks whichever one is found, on every system.
"""
import os
import shutil
import subprocess
import sys


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


def install_hint():
    if sys.platform == "darwin":
        return "brew install ffmpeg"
    if sys.platform == "win32":
        return "winget install Gyan.FFmpeg.Essentials"
    return "your system's package manager, for example sudo apt install ffmpeg"
