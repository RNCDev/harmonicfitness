"""Play an audio file with the system's own player, so a listener can hear a take or a sample.

A Mac plays it in turn with afplay; Linux hands it to the default app (xdg-open); Windows opens
it in the default player. In Claude Code, the skills send the file with SendUserFile first, and
fall back to this, then to the path.
"""
import os
import shutil
import subprocess
import sys


def play(path):
    """Play `path`; False when this system has no player to hand it to."""
    if sys.platform == "darwin" and shutil.which("afplay"):
        subprocess.Popen([shutil.which("afplay"), path]).wait()   # in turn, so takes don't overlap
        return True
    if sys.platform == "win32":
        os.startfile(path)   # the default player; it plays alongside rather than in turn
        return True
    opener = shutil.which("xdg-open") or shutil.which("open")
    if opener:
        subprocess.Popen([opener, path])
        return True
    return False
