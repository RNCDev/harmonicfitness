"""A user's context files on disk for one engine run: write out, harvest, seed.

Pure filesystem code; no database. The engine runs with HARMONICFITNESS_HOME pointed
at the folder materialize wrote, and harvest returns what it changed.
"""
import fnmatch
import hashlib
import os
import re

from .store import check_path

# Glob-style patterns matched against the relative POSIX path. A pattern ending
# in "/" means anything under that folder. A pattern without "/" (such as
# "*.mp3") matches the file name at any depth; one with "/" matches the whole
# path from the root. "*" does not stop at "/" (fnmatch), which is harmless here.
SKIP = (
    ".env", ".env.*", "*.env", "*.lock", "workouts/.audio-cache/",
    "*.mp3", "*.wav", "*.log", "*.log.1", ".gitignore", ".DS_Store", ".cache/",
)

# What `./harmonicfitness sync` keeps on the computer alone (tools/websync.py's LOCAL_ONLY, which test_sync holds in
# step): it refuses a whole sync whose listing names one, so the sync routes never list or read one. A copy synced
# before 0.71.2 still holds the backup's remote note, and listing it stopped every sync (0.77.1).
LOCAL_ONLY = ("web/", "coaches/.auditions/", ".git/", ".backup-*", "*.bundle", "workouts/.logs/backup-remote.json")


def local_only(path: str) -> bool:
    """Whether `sync` keeps this path to the computer, matched as websync.skipped matches it (case-blind too)."""
    for rel in {path, path.lower()}:
        parts = rel.split("/")
        for pat in LOCAL_ONLY:
            if pat.endswith("/"):
                prefix = pat.split("/")[:-1]
                if parts[:len(prefix)] == prefix and len(parts) > len(prefix):
                    return True
            elif "/" in pat:
                if fnmatch.fnmatchcase(rel, pat):
                    return True
            elif fnmatch.fnmatchcase(parts[-1], pat) or fnmatch.fnmatchcase(parts[0], pat):
                return True
    return False


# A coach's audition spans turns (the candidates, then the listener's pick), so its files are kept until
# forget-audition removes them: the narrative beside the auditions, and in each audition's folder its
# candidates list, narrative and each candidate's WAV (which keep sends to the service) and MP3.
AUDITIONS = "coaches/.auditions/"
AUDITION_FILES = (".md", ".json", ".wav", ".mp3")

# A web coach's sample, the one MP3 kept outside an audition: the Coaches page plays it. Not one in .archive/.
# tools/websync.py holds the same pattern (test_sync checks).
COACH_SAMPLE = re.compile(r"coaches/[^./][^/]*/sample\.mp3")


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
    if COACH_SAMPLE.fullmatch(path):
        return False
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


def digest(data: bytes) -> str:
    """A file's digest as `written` and harvest() compare them."""
    return _sha(data)


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


IMPORT_MAX_ZIP = 10_000_000      # bytes of ZIP
IMPORT_MAX_FILE = 2_000_000      # bytes of one file, unpacked
IMPORT_MAX_TOTAL = 30_000_000    # bytes of every file, unpacked
IMPORT_MAX_FILES = 2_000


def folder_from_zip(data: bytes) -> tuple[dict[str, bytes], int]:
    """(path -> bytes, how many entries were left out) from a ZIP of a me/ folder. The ZIP may hold the
    folder's files at its top or inside one folder (me/, harmonicfitness-me/...). Raises ValueError with
    a sentence for a person."""
    import io
    import stat
    import zipfile
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("That isn't a ZIP file.") from None
    entries = [i for i in z.infolist() if not i.is_dir()]
    if len(entries) > IMPORT_MAX_FILES:
        raise ValueError(f"That ZIP holds more than {IMPORT_MAX_FILES} files.")
    names = [i.filename for i in entries]
    tops = {n.split("/", 1)[0] for n in names if not n.startswith("__MACOSX/")}
    strip = ""
    if ("profile.md" not in names and len(tops) == 1 and next(iter(tops)) not in ("", ".", "..")
            and f"{next(iter(tops))}/profile.md" in names):
        strip = f"{next(iter(tops))}/"   # the folder itself was zipped
    files, left_out, total = {}, 0, 0
    for info in entries:
        path = info.filename[len(strip):] if info.filename.startswith(strip) else info.filename
        mode = info.external_attr >> 16
        parts = path.split("/")
        if (stat.S_ISLNK(mode) or skipped(path) or parts[0].startswith(".backup") or parts[0] == ".git"
                or "__MACOSX" in parts or parts[-1].startswith("._")):
            left_out += 1
            continue
        try:
            check_path(path)
        except ValueError:
            left_out += 1
            continue
        if info.file_size > IMPORT_MAX_FILE:
            left_out += 1
            continue
        total += info.file_size
        if total > IMPORT_MAX_TOTAL:
            raise ValueError(f"That folder is over {IMPORT_MAX_TOTAL // 1_000_000} MB unpacked.")
        with z.open(info) as f:
            body = f.read(IMPORT_MAX_FILE + 1)
        if len(body) > IMPORT_MAX_FILE:
            left_out += 1
            continue
        files[path] = body
    if "profile.md" not in files:
        raise ValueError("That ZIP has no profile.md: zip the me folder itself.")
    return files, left_out
