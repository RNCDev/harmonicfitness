"""Each user's voice service keys, sealed with the user's data key, and which language model writes their workouts.

The web process seals a key on entry and never opens one; `open_all` is for the worker only.
None of these commit: the caller does.
"""
from datetime import datetime

from . import crypto
from .store import UserKey


def _aad(uk: UserKey, service: str) -> bytes:
    return f"{uk.user_id}:user_keys:{service}".encode()


def put(conn, uk: UserKey, service: str, value: str) -> None:
    """Store (or replace) a service's key, sealed; moves updated_at."""
    sealed = crypto.seal(uk.key, value.encode("utf-8"), _aad(uk, service))
    conn.execute(
        "insert into user_keys (user_id, service, secret) values (%s, %s, %s) "
        "on conflict (user_id, service) do update set secret = excluded.secret, "
        "updated_at = now()", (uk.user_id, service, sealed))


def delete(conn, uk: UserKey, service: str) -> bool:
    """Remove a service's key; whether a row went."""
    return conn.execute("delete from user_keys where user_id = %s and service = %s",
                        (uk.user_id, service)).rowcount == 1


def listing(conn, uk: UserKey) -> dict[str, datetime]:
    """service -> updated_at; never opens a key."""
    rows = conn.execute("select service, updated_at from user_keys where user_id = %s",
                        (uk.user_id,)).fetchall()
    return dict(sorted(rows))


def open_all(conn, uk: UserKey) -> dict[str, str]:
    """service -> key. For the worker only: the web process never opens a key."""
    rows = conn.execute("select service, secret from user_keys where user_id = %s",
                        (uk.user_id,)).fetchall()
    return {s: crypto.open_(uk.key, bytes(b), _aad(uk, s)).decode("utf-8")
            for s, b in sorted(rows)}


def writer(conn, uk: UserKey) -> str | None:
    """The provider the user chose to write their workouts (a providers.PROVIDERS id), or None."""
    row = conn.execute("select writer from users where id = %s", (uk.user_id,)).fetchone()
    return row[0] if row else None


def set_writer(conn, uk: UserKey, provider: str) -> None:
    conn.execute("update users set writer = %s where id = %s", (provider, uk.user_id))
