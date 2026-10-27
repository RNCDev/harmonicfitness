"""Play an audio file with the system's own player, so a listener can hear a take or a sample.

A Mac plays it in turn with afplay; Linux hands it to the default app (xdg-open); Windows opens
it in the default player. In Claude Code, the skills send the file with SendUserFile first, and
fall back to this, then to the path. `show` (./sweatcast show <file>) opens the file's folder with the
file selected (Finder, Explorer, or the file manager), so a listener can play it, AirDrop it or drag it.
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


def show(path):
    """Open the folder holding `path`, with it selected where the system allows; False when there's no way."""
    path = os.path.abspath(path)
    if sys.platform == "darwin" and shutil.which("open"):
        return subprocess.call([shutil.which("open"), "-R", path]) == 0
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])   # explorer's exit code means nothing
        return True
    opener = shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, os.path.dirname(path)])
        return True
    return False


def main(argv=None):
    import cli
    ap = cli.ArgumentParser(prog="sweatcast show",
                                 description="Open the folder holding a file (a workout's MP3), with it selected.")
    ap.add_argument("file")
    a = ap.parse_args(argv)
    if not os.path.exists(a.file):
        print(f"No such file: {a.file}", file=sys.stderr)
        return 1
    if not show(a.file):
        print(f"No file manager to open here; the file is {os.path.abspath(a.file)}", file=sys.stderr)
        return 1
    print(f"Opened its folder: {os.path.abspath(a.file)}")
    return 0
