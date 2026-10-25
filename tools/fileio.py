"""One way to write a file so a crash never leaves it half-written: to a temporary file beside it, then
renamed into place (os.replace is atomic on every system sweatcast runs on). Text or bytes."""
import os
import tempfile


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
