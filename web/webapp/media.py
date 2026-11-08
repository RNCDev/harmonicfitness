"""A workout's MP3 for the listener, sealed with their data key, played or downloaded through the API with their
session. A workout's (one with a build id) is kept until they have three newer ones; any other MP3 (a coach's sample
in the chat) for 24 hours. None of these commit, except sweep: the caller does."""
import datetime
import uuid

from . import crypto
from .store import UserKey

KEEP = datetime.timedelta(hours=24)   # an MP3 that isn't a workout's
WORKOUTS = 3                          # a listener's newest workout MP3s kept; making another deletes the oldest
MAX_BYTES = 80_000_000   # a 60-minute workout at the engine's bitrate is well under this
KEPT = "(expires_at is null or expires_at > now())"


def _aad(uk: UserKey, mid: uuid.UUID) -> bytes:
    return f"{uk.user_id}:media:{mid}".encode()


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
        "insert into media (id, user_id, name, body, bytes, created_at, expires_at, build_id) "
        "values (%s, %s, %s, %s, %s, clock_timestamp(), "
        "case when %s::text is null then now() + %s end, %s) returning expires_at",
        (mid, uk.user_id, name[:200], crypto.seal(uk.key, body, _aad(uk, mid)), len(body), build, KEEP,
         build)).fetchone()
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


def get(conn, uk: UserKey, mid: str) -> tuple[str, bytes, datetime.datetime | None] | None:
    """(name, the MP3, when it expires: None for a workout's) for the user's own kept media, else None."""
    try:
        key = uuid.UUID(mid)
    except ValueError:
        return None
    row = conn.execute(f"select name, body, expires_at from media where id = %s and user_id = %s and {KEPT}",
                       (key, uk.user_id)).fetchone()
    if row is None:
        return None
    return row[0], crypto.open_(uk.key, bytes(row[1]), _aad(uk, key)), row[2]


def sweep(conn) -> int:
    """Delete every MP3 past its time (a workout's has none: a newer one replaces it); commits."""
    n = conn.execute("delete from media where expires_at <= now()").rowcount
    conn.commit()
    return n
