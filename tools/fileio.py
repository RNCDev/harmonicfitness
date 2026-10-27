"""One way to write a file so a crash never leaves it half-written: to a temporary file beside it, then
renamed into place (os.replace is atomic on every system sweatcast runs on). Text or bytes. And one way
to add a line to a JSONL record (builds.jsonl, told.jsonl) so a torn line never takes the next one with it."""
import json
import os
import tempfile

import locks


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
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
