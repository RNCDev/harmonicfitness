"""The engine's clip cache (workouts/.audio-cache/), kept a week per listener so re-recording a workout
sends only the lines that changed: clips and their take checks, and the coach's measured pace. Sealed with
the user's data key. Only a recording turn loads and saves it. Nothing commits here except prune."""
import os

from . import crypto
from .store import UserKey

FOLDER = os.path.join("workouts", ".audio-cache")
KEEP_DAYS = 7
MAX_FILE = 20_000_000          # bytes: one clip
MAX_TOTAL = 400_000_000        # bytes a listener's cache may hold; past it, new clips aren't kept


def _aad(uk: UserKey, path: str) -> bytes:
    return f"{uk.user_id}:clip_cache:{path}".encode()


def _ok(path: str) -> bool:
    return bool(path) and "/" not in path and "\\" not in path and not path.startswith(".") and len(path) <= 200


def load(conn, uk: UserKey, home: str) -> dict[str, float]:
    """Write the user's kept clips into the folder's cache; {name: mtime} as written, to tell new ones later."""
    folder = os.path.join(home, FOLDER)
    os.makedirs(folder, exist_ok=True)
    rows = conn.execute("update clip_cache set used_at = now() where user_id = %s returning path, body",
                        (uk.user_id,)).fetchall()
    written = {}
    for path, body in rows:
        if not _ok(path):
            continue
        full = os.path.join(folder, path)
        with open(full, "wb") as f:
            f.write(crypto.open_(uk.key, bytes(body), _aad(uk, path)))
        written[path] = os.path.getmtime(full)
    return written


def save(conn, uk: UserKey, home: str, before: dict[str, float]) -> int:
    """Keep the cache files the build added or changed; how many."""
    folder = os.path.join(home, FOLDER)
    if not os.path.isdir(folder):
        return 0
    total = conn.execute("select coalesce(sum(bytes), 0) from clip_cache where user_id = %s",
                         (uk.user_id,)).fetchone()[0]
    n = 0
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if not _ok(name) or os.path.islink(full) or not os.path.isfile(full):
            continue
        if before.get(name) == os.path.getmtime(full):
            continue
        size = os.path.getsize(full)
        if size > MAX_FILE or total + size > MAX_TOTAL:
            continue
        with open(full, "rb") as f:
            body = f.read()
        conn.execute("insert into clip_cache (user_id, path, body, bytes) values (%s, %s, %s, %s) "
                     "on conflict (user_id, path) do update set body = excluded.body, bytes = excluded.bytes, "
                     "used_at = now()", (uk.user_id, name, crypto.seal(uk.key, body, _aad(uk, name)), size))
        total += size
        n += 1
    return n


def prune(conn) -> int:
    """Delete clips unused for a week; commits."""
    n = conn.execute("delete from clip_cache where used_at < now() - make_interval(days => %s)",
                     (KEEP_DAYS,)).rowcount
    conn.commit()
    return n
