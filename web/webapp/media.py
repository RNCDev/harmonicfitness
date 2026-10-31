"""A workout's MP3 for the listener: kept 24 hours, sealed with their data key, played or downloaded
through the API with their session. None of these commit, except sweep: the caller does."""
import datetime
import uuid

from . import crypto
from .store import UserKey

KEEP = datetime.timedelta(hours=24)
MAX_BYTES = 80_000_000   # a 60-minute workout at the engine's bitrate is well under this


def _aad(uk: UserKey, mid: uuid.UUID) -> bytes:
    return f"{uk.user_id}:media:{mid}".encode()


def put(conn, uk: UserKey, name: str, body: bytes, build_id: str | None = None) -> dict:
    """Keep an MP3 for 24 hours; its id, name and expiry, as a chat line's `audio` holds them. `build_id`
    names the build that made a workout's MP3, for the Logs page."""
    if len(body) > MAX_BYTES:
        raise ValueError("that MP3 is too large to keep")
    mid = uuid.uuid4()
    row = conn.execute(
        "insert into media (id, user_id, name, body, bytes, expires_at, build_id) "
        "values (%s, %s, %s, %s, %s, now() + %s, %s) returning expires_at",
        (mid, uk.user_id, name[:200], crypto.seal(uk.key, body, _aad(uk, mid)), len(body), KEEP,
         build_id[:64] if build_id else None)).fetchone()
    return {"id": str(mid), "name": name[:200], "expires_at": row[0].isoformat()}


def by_build(conn, uk: UserKey) -> dict[str, dict]:
    """{build_id: the newest unexpired MP3 it made, as put() returns it}: what the Logs page can still play."""
    rows = conn.execute("select build_id, id, name, expires_at from media where user_id = %s and build_id is not null "
                        "and expires_at > now() order by created_at", (uk.user_id,)).fetchall()
    return {b: {"id": str(i), "name": n, "expires_at": e.isoformat()} for b, i, n, e in rows}


def get(conn, uk: UserKey, mid: str) -> tuple[str, bytes, datetime.datetime] | None:
    """(name, the MP3, when it expires) for the user's own unexpired media, else None."""
    try:
        key = uuid.UUID(mid)
    except ValueError:
        return None
    row = conn.execute("select name, body, expires_at from media where id = %s and user_id = %s "
                       "and expires_at > now()", (key, uk.user_id)).fetchone()
    if row is None:
        return None
    return row[0], crypto.open_(uk.key, bytes(row[1]), _aad(uk, key)), row[2]


def sweep(conn) -> int:
    """Delete every expired MP3; commits."""
    n = conn.execute("delete from media where expires_at <= now()").rowcount
    conn.commit()
    return n
