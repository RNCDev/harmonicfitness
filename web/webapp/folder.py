"""A user's context files on disk for one engine run: write out, harvest, seed.

Pure filesystem code; no database. The engine runs with HARMONICFITNESS_HOME pointed
at the folder materialize wrote, and harvest returns what it changed.
"""
import fnmatch
import hashlib
import os

from .store import check_path

# Glob-style patterns matched against the relative POSIX path. A pattern ending
# in "/" means anything under that folder. A pattern without "/" (such as
# "*.mp3") matches the file name at any depth; one with "/" matches the whole
# path from the root. "*" does not stop at "/" (fnmatch), which is harmless here.
SKIP = (
    ".env", ".env.*", "*.env", "*.lock", "workouts/.audio-cache/",
    "*.mp3", "*.wav", "*.log", "*.log.1", ".gitignore", ".DS_Store", ".cache/",
)

# A coach's audition spans turns (the candidates, then the listener's pick), so its files are kept until
# forget-audition removes them: the narrative beside the auditions, and in each audition's folder its
# candidates list, narrative and each candidate's WAV (which keep sends to the service) and MP3.
AUDITIONS = "coaches/.auditions/"
AUDITION_FILES = (".md", ".json", ".wav", ".mp3")


def audition_file(path: str) -> bool:
    """A file of a coach's audition: `coaches/.auditions/<narrative>.md`, or a candidates list, narrative,
    WAV or MP3 directly inside `coaches/.auditions/<audition>/`."""
    if not path.startswith(AUDITIONS):
        return False
    rest = path[len(AUDITIONS):].split("/")
    name = rest[-1]
    if name.startswith(".") or not name.endswith(AUDITION_FILES) or rest[0].startswith("."):
        return False
    return (len(rest) == 1 and name.endswith(".md")) or len(rest) == 2


def skipped(path: str) -> bool:
    if path.startswith(AUDITIONS):
        return not audition_file(path)
    parts = path.split("/")
    for pat in SKIP:
        if pat.endswith("/"):
            prefix = pat.split("/")[:-1]
            if parts[:len(prefix)] == prefix and len(parts) > len(prefix):
                return True
        elif "/" in pat:
            if fnmatch.fnmatchcase(path, pat):
                return True
        elif fnmatch.fnmatchcase(parts[-1], pat):
            return True
    return False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def materialize(files: dict[str, bytes], root: str) -> dict[str, str]:
    """Write each file under root; return path -> sha256 of what was written.

    root must be a fresh, empty folder. Files are opened with O_NOFOLLOW, so a
    symlink already in place is never written through (OSError)."""
    for path in files:
        check_path(path)
    root = os.path.abspath(root)
    written = {}
    for path, data in files.items():
        dest = os.path.join(root, *path.split("/"))
        if os.path.commonpath([root, os.path.abspath(dest)]) != root:
            raise ValueError(f"bad path: {path!r}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        written[path] = _sha(data)
    return written


def _walk(root: str):
    """Yield (relative POSIX path, full path) of regular files, never following links."""
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(base, d)))
        for name in sorted(names):
            full = os.path.join(base, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            yield rel, full


def harvest(root: str, written: dict[str, str],
            never: frozenset[str] = frozenset()) -> dict[str, bytes | None]:
    """Files new or changed since `written`; None for ones deleted. Skips links,
    SKIP paths and anything in `never`."""
    out: dict[str, bytes | None] = {}
    seen = set()
    for rel, full in _walk(root):
        if rel in never or skipped(rel):
            continue
        try:
            check_path(rel)
        except ValueError:
            continue
        seen.add(rel)
        with open(full, "rb") as f:
            data = f.read()
        if written.get(rel) != _sha(data):
            out[rel] = data
    for rel in written:
        if rel not in seen and rel not in never and not skipped(rel):
            out[rel] = None
    return out


def seed(engine_root: str) -> dict[str, bytes]:
    """Every file in <engine_root>/me.example/ as path -> bytes, minus SKIP."""
    base = os.path.join(engine_root, "me.example")
    if not os.path.isdir(base):
        raise FileNotFoundError(base)
    out = {}
    for rel, full in _walk(base):
        if skipped(rel):
            continue
        with open(full, "rb") as f:
            out[rel] = f.read()
    return out
