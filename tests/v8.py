"""The clips sweatcast 8 shipped, read from the v8.0.1 git tag (the migration's own source once
tools/migrate-assets/ was removed in 10.0.0). Tests that need them skip outside a git clone."""
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _show(path):
    return subprocess.run(["git", "-C", ROOT, "show", f"v8.0.1:{path}"], capture_output=True)


def _has_tag():
    try:
        return _show("voices/Chatterbox Coach.json").returncode == 0
    except OSError:
        return False


HAS_V8_TAG = _has_tag()


def v8_file(stem, ext):
    """The bytes of voices/<stem><ext> at v8.0.1."""
    out = _show(f"voices/{stem}{ext}")
    if out.returncode != 0:
        raise FileNotFoundError(f"v8.0.1:voices/{stem}{ext}")
    return out.stdout
