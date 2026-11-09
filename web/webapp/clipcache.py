"""The engine's clip cache (workouts/.audio-cache/), kept a week per listener so re-recording a workout
sends only the lines that changed: clips and their take checks, and the coach's measured pace. Sealed with
the user's data key. Only a recording turn loads and saves it. Nothing commits here except prune.

A clip's `used_at` moves only when a build used it (0.76.0): loading the cache marks nothing, and a clip the
engine read (it touches each one it uses, for its own prune) is marked used without being sent again. At the
listener's MAX_TOTAL, the clips used longest ago make room for the new ones, so the cache keeps working."""
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
    """Write the user's kept clips into the folder's cache; {name: mtime} as written, to tell new ones later.
    The rows come one at a time: a week of clips is up to MAX_TOTAL, and held all at once (2026-11-03) it kept
    the worker so large that the engine's encode ran the 1 GB machine out of memory."""
    folder = os.path.join(home, FOLDER)
    os.makedirs(folder, exist_ok=True)
    rows = conn.cursor().stream("select path, body from clip_cache where user_id = %s", (uk.user_id,))
    written = {}
    for path, body in rows:
        if not _ok(path):
            continue
        full = os.path.join(folder, path)
        with open(full, "wb") as f:
            f.write(crypto.open_(uk.key, bytes(body), _aad(uk, path)))
        written[path] = os.path.getmtime(full)
    return written


PACE = "voice-pace.json"   # the stock coaches' measured pace (the engine's paths.PACE_FILE), kept with the clips


def load_pace(conn, uk: UserKey, home: str) -> bool:
    """Only the measured pace, into the folder's cache, for a turn that writes a script but doesn't record: the
    lint plans a stock web coach's words by it, where without it the coach's sample pace stands in (a 30-minute
    script planned that way came in 5.4 percent short, 2026-11-01). Whether there was one."""
    row = conn.execute("update clip_cache set used_at = now() where user_id = %s and path = %s returning body",
                       (uk.user_id, PACE)).fetchone()
    if row is None:
        return False
    folder = os.path.join(home, FOLDER)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, PACE), "wb") as f:
        f.write(crypto.open_(uk.key, bytes(row[0]), _aad(uk, PACE)))
    return True


def current(home: str) -> dict[str, float]:
    """{name: mtime} of the folder's cache files now: after a save, what counts as already kept."""
    folder = os.path.join(home, FOLDER)
    try:
        return {n: os.path.getmtime(os.path.join(folder, n)) for n in os.listdir(folder) if _ok(n)}
    except OSError:
        return {}


def _evict(conn, uk: UserKey, need: int, keep: list[str]) -> int:
    """Delete the listener's clips used longest ago, never the pace or one in `keep`, until `need` bytes are free
    (or none is left to delete); the bytes freed."""
    freed, gone = 0, []
    rows = conn.execute("select path, bytes from clip_cache where user_id = %s and path <> %s and "
                        "not (path = any(%s)) order by used_at, path", (uk.user_id, PACE, keep)).fetchall()
    for path, size in rows:
        if freed >= need:
            break
        gone.append(path)
        freed += size
    if gone:
        conn.execute("delete from clip_cache where user_id = %s and path = any(%s)", (uk.user_id, gone))
    return freed


def save(conn, uk: UserKey, home: str, before: dict[str, float]) -> int:
    """Keep the cache files the build added or changed, and mark used the clips it read; how many were sent.

    A clip loaded from the store (in `before`) whose time moved was read by the build: marked used, not sent again.
    Any other file that's new or changed is sent, and the pace and take checks whenever they changed. Past
    MAX_TOTAL, the clips used longest ago go first."""
    folder = os.path.join(home, FOLDER)
    if not os.path.isdir(folder):
        return 0
    hits, new = [], []
    for name in sorted(os.listdir(folder)):
        full = os.path.join(folder, name)
        if not _ok(name) or os.path.islink(full) or not os.path.isfile(full):
            continue
        if before.get(name) == os.path.getmtime(full):
            continue
        if name in before and name.endswith(".pcm"):
            hits.append(name)
        elif os.path.getsize(full) <= MAX_FILE:
            new.append((name, os.path.getsize(full)))
    if hits:
        conn.execute("update clip_cache set used_at = now() where user_id = %s and path = any(%s)", (uk.user_id, hits))
    total = conn.execute("select coalesce(sum(bytes), 0) from clip_cache where user_id = %s and not (path = any(%s))",
                         (uk.user_id, [name for name, _ in new])).fetchone()[0]
    need = sum(size for _, size in new)
    if total + need > MAX_TOTAL:
        total -= _evict(conn, uk, total + need - MAX_TOTAL, hits + [name for name, _ in new])
    n = 0
    for name, size in new:
        if total + size > MAX_TOTAL:
            continue
        with open(os.path.join(folder, name), "rb") as f:
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
