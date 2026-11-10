"""A workout's MP3 for the listener, sealed with their data key, played or downloaded through the API with their
session. A workout's (one with a build id) is kept until they have three newer ones; any other MP3 (a coach's sample
in the chat) for 24 hours. None of these commit, except sweep: the caller does.

Since 0.77.0 an MP3 is kept in chunks of CHUNK bytes (media_chunks), each sealed bound to its place, so a byte range
opens only the chunks it covers. A row kept before then holds the whole MP3 in media.body (chunk_bytes null); both
are read. 0.77.0 writes media.body too, for the web processes still on 0.76.2 during its deploy."""
import datetime
import uuid

from . import crypto
from .store import UserKey

KEEP = datetime.timedelta(hours=24)   # an MP3 that isn't a workout's
WORKOUTS = 3                          # a listener's newest workout MP3s kept; making another deletes the oldest
MAX_BYTES = 80_000_000   # a 60-minute workout at the engine's bitrate is well under this
CHUNK = 1_000_000        # bytes of MP3 in each sealed chunk
KEPT = "(expires_at is null or expires_at > now())"


def _aad(uk: UserKey, mid: uuid.UUID) -> bytes:
    """A whole MP3's, as kept before 0.77.0."""
    return f"{uk.user_id}:media:{mid}".encode()


def _chunk_aad(uk: UserKey, mid: uuid.UUID, n: int) -> bytes:
    return f"{uk.user_id}:media:{mid}:{n}".encode()


def _id(mid: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(mid)
    except ValueError:
        return None


def _iso(t: datetime.datetime | None) -> str | None:
    return t.isoformat() if t else None


def put(conn, uk: UserKey, name: str, body: bytes, build_id: str | None = None) -> dict:
    """Keep an MP3; its id, name and expiry (null for a workout's), as a chat line's `audio` holds them.
    `build_id` names the build that made a workout's MP3, for the Logs page; keeping it deletes the listener's
    workout MP3s past the newest three."""
    if len(body) > MAX_BYTES:
        raise ValueError("that MP3 is too large to keep")
    mid = uuid.uuid4()
    build = build_id[:64] if build_id else None
    # clock_timestamp, not now(): two kept in one transaction still sort newest first
    row = conn.execute(
        "insert into media (id, user_id, name, body, bytes, chunk_bytes, created_at, expires_at, build_id) "
        "values (%s, %s, %s, %s, %s, %s, clock_timestamp(), "
        "case when %s::text is null then now() + %s end, %s) returning expires_at",
        # kept whole as well, for 0.77.0 only: a 0.76.2 web process, still serving during the deploy, reads only
        # media.body; nothing of 0.77.0 reads it for a chunked row. The next release stops writing it.
        (mid, uk.user_id, name[:200], crypto.seal(uk.key, body, _aad(uk, mid)), len(body), CHUNK, build, KEEP,
         build)).fetchone()
    with conn.cursor() as cur:
        cur.executemany("insert into media_chunks (media_id, n, body) values (%s, %s, %s)",
                        [(mid, n, crypto.seal(uk.key, body[at:at + CHUNK], _chunk_aad(uk, mid, n)))
                         for n, at in enumerate(range(0, len(body), CHUNK))])
    if build:
        conn.execute("delete from media where user_id = %s and build_id is not null and id not in "
                     "(select id from media where user_id = %s and build_id is not null "
                     "order by created_at desc, id limit %s)", (uk.user_id, uk.user_id, WORKOUTS))
    return {"id": str(mid), "name": name[:200], "expires_at": _iso(row[0])}


def by_build(conn, uk: UserKey) -> dict[str, dict]:
    """{build_id: the newest MP3 it made that's still kept, as put() returns it}: what the Logs page can play."""
    rows = conn.execute(f"select build_id, id, name, expires_at from media where user_id = %s and build_id is not null "
                        f"and {KEPT} order by created_at", (uk.user_id,)).fetchall()
    return {b: {"id": str(i), "name": n, "expires_at": _iso(e)} for b, i, n, e in rows}


def gone(conn, uk: UserKey, lines: list) -> set[str]:
    """The ids of the MP3s a conversation's lines play that are no longer kept (replaced by newer workouts, or
    past their time), so the page can say so instead of offering a player that can't load."""
    ids = {a["id"] for x in lines if isinstance(x, dict) and isinstance(a := x.get("audio"), dict)
           and isinstance(a.get("id"), str)}
    if not ids:
        return set()
    valid = set()
    for i in ids:
        try:
            valid.add(uuid.UUID(i))
        except ValueError:
            pass
    kept = {str(r[0]) for r in conn.execute(f"select id from media where user_id = %s and id = any(%s) and {KEPT}",
                                            (uk.user_id, list(valid))).fetchall()} if valid else set()
    return ids - kept


def describe(conn, uk: UserKey, mid: str) -> tuple[str, int, datetime.datetime | None, int] | None:
    """(name, its size in bytes, when it expires: None for a workout's, the bytes in each chunk: its size when it's
    kept whole) for the user's own kept media, else None. Opens nothing."""
    key = _id(mid)
    if key is None:
        return None
    row = conn.execute(f"select name, bytes, expires_at, chunk_bytes from media where id = %s and user_id = %s "
                       f"and {KEPT}", (key, uk.user_id)).fetchone()
    return None if row is None else (row[0], row[1], row[2], row[3] or max(row[1], 1))


def read_range(conn, uk: UserKey, mid: str, start: int, end: int) -> bytes | None:
    """Bytes `start` to `end` (inclusive) of the user's own kept MP3, opening only the chunks they're in; None when
    it's no longer kept."""
    key = _id(mid)
    if key is None:
        return None
    row = conn.execute(f"select chunk_bytes, case when chunk_bytes is null then body end from media "
                       f"where id = %s and user_id = %s and {KEPT}", (key, uk.user_id)).fetchone()
    if row is None:
        return None
    size, whole = row
    if size is None:   # kept whole, before 0.77.0
        return crypto.open_(uk.key, bytes(whole), _aad(uk, key))[start:end + 1]
    first, last = start // size, end // size
    rows = conn.execute("select n, body from media_chunks where media_id = %s and n between %s and %s order by n",
                        (key, first, last)).fetchall()
    data = b"".join(crypto.open_(uk.key, bytes(b), _chunk_aad(uk, key, n)) for n, b in rows)
    return data[start - first * size:end - first * size + 1]


def get(conn, uk: UserKey, mid: str) -> tuple[str, bytes, datetime.datetime | None] | None:
    """(name, the whole MP3, when it expires: None for a workout's) for the user's own kept media, else None."""
    found = describe(conn, uk, mid)
    if found is None:
        return None
    name, size, expires, _ = found
    body = read_range(conn, uk, mid, 0, size - 1) if size else b""
    return None if body is None else (name, body, expires)


def sweep(conn) -> int:
    """Delete every MP3 past its time (a workout's has none: a newer one replaces it); commits."""
    n = conn.execute("delete from media where expires_at <= now()").rowcount
    conn.commit()
    return n
