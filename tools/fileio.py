"""One way to write a file so a crash never leaves it half-written: to a temporary file beside it, then
renamed into place (os.replace is atomic on every system sweatcast runs on). Text or bytes. And one way
to add a line to a JSONL record (builds.jsonl, told.jsonl) so a torn line never takes the next one with it.
And one way to read a JSON file whose top level must be one shape (read_json)."""
import json
import os
import tempfile
import time

import errors
import locks


_JSON_NAME = {dict: "object", list: "array", str: "string", int: "number", float: "number",
              bool: "true or false", type(None): "null"}


def read_json(path, shape=dict):
    """The JSON at `path`, whose top level must be a `shape` (dict or list). A missing file raises
    FileNotFoundError as open() does, so each caller keeps its own answer for that; anything else that stops
    it being read (unreadable, not JSON, the wrong top level) raises ContextError naming the file."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise
    except (OSError, ValueError) as e:
        raise errors.ContextError(f"{path} can't be read as JSON ({e}).") from e
    if not isinstance(data, shape):
        raise errors.ContextError(f"{path} should hold a JSON {_JSON_NAME.get(shape, shape.__name__)}, "
                                  f"not {_JSON_NAME.get(type(data), type(data).__name__)}.")
    return data


def write_json(path, obj, indent=1):
    """`obj` as JSON at `path`, atomically, ending in a newline."""
    atomic_write(path, json.dumps(obj, indent=indent, ensure_ascii=False) + "\n")


def append_jsonl(path, records):
    """Add one record (a dict) or several (a list) to the JSONL file at `path`, one line each, under the file's
    lock, flushed to disk. A last line a crash left without its newline is sealed first, so the reader skips
    only that fragment and keeps every record after it."""
    records = records if isinstance(records, list) else [records]
    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode("utf-8")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with locks.file_lock(path):
        with open(path, "ab+") as f:
            f.seek(0, os.SEEK_END)
            if f.tell():
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    f.seek(0, os.SEEK_END)
                    f.write(b"\n")
            f.seek(0, os.SEEK_END)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())


REPLACE_TRIES = 10     # on Windows: tries at renaming over a file another program holds open
REPLACE_WAIT = 0.1     # seconds between them


def replace(src, dst):
    """os.replace(src, dst). On Windows, renaming over a file fails while another program has it open (a media
    player holding last time's MP3, a reader of the pace file), so a PermissionError is tried again, up to
    REPLACE_TRIES times REPLACE_WAIT seconds apart, before it's raised. Elsewhere it's os.replace as is."""
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if os.name != "nt" or attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(REPLACE_WAIT)


def atomic_write(path, data):
    """Write `data` (str as UTF-8, or bytes) to `path`, making its folder, so readers see the old file or the
    new one and never a partial one."""
    folder = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".part", dir=folder)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
            f.flush()
            os.fsync(f.fileno())
        replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def jsonl_record(line):
    """One JSONL line (str or bytes) as the dict it holds, or None for a line that holds none: blank, torn by a
    crash, not UTF-8, not JSON, or JSON that isn't an object. The one rule every JSONL reader skips by."""
    try:
        rec = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
    except ValueError:   # UnicodeDecodeError is one
        return None
    return rec if isinstance(rec, dict) else None


def read_jsonl(path, parse=None):
    """Each record in the JSONL file at `path`, oldest first, as a dict; a line that holds none is skipped
    (jsonl_record), and a missing file yields nothing. With `parse`, each dict goes through it and a None it
    returns is skipped too, so a reader can drop the records it can't use (records.parse for builds.jsonl)."""
    try:
        f = open(path, "rb")   # bytes: a line a crash cut mid-character is skipped, not fatal to the rest
    except FileNotFoundError:
        return
    with f:
        for line in f:
            rec = jsonl_record(line)
            if rec is not None and parse is not None:
                rec = parse(rec)
            if rec is not None:
                yield rec
