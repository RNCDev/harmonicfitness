"""Invite links, sign-in sessions and "add a device" links.

Tokens are 32 random bytes, URL-safe base64; only their sha256 is stored.
"""
import base64
import hashlib
import secrets
from uuid import UUID

from . import crypto, folder, store

DEVICE_MINUTES = 10


class Refused(Exception):
    """An invite that is unknown, used or expired (never says which)."""


def _token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _email(email: str) -> str:
    e = email.strip().lower() if isinstance(email, str) else ""
    local, sep, domain = e.partition("@")
    if not sep or not local or not domain or "@" in domain:
        raise ValueError("not an email address")
    return e


def _link(settings, token: str) -> str:
    return f"{settings.base_url.rstrip('/')}/invite/{token}"


def _new_invite(conn, settings, user_id, interval: str, param) -> str:
    token = _token()
    conn.execute(
        f"insert into invites (token_hash, user_id, expires_at) "
        f"values (%s, %s, now() + {interval})", (_hash(token), user_id, param))
    return _link(settings, token)


def invite(conn, settings, email: str) -> str:
    email = _email(email)
    try:
        row = conn.execute("select id from users where email = %s", (email,)).fetchone()
        if row is None:
            plain, wrapped = crypto.new_data_key(settings.master_key)
            row = conn.execute(
                "insert into users (email, wrapped_key) values (%s, %s) "
                "on conflict (email) do nothing returning id", (email, wrapped)).fetchone()
            if row is not None:
                uk = store.UserKey(user_id=UUID(str(row[0])), key=plain)
                files = folder.seed(settings.engine_root)
                if store.write_back(conn, uk, dict(files), {}):
                    raise RuntimeError("seeding a new user conflicted")
            else:  # lost a race to another invite for the same email
                row = conn.execute("select id from users where email = %s", (email,)).fetchone()
        link = _new_invite(conn, settings, row[0], "make_interval(days => %s)",
                           settings.invite_days)
        conn.commit()
        return link
    except Exception:
        conn.rollback()
        raise


def device_link(conn, settings, user_id) -> str:
    try:
        link = _new_invite(conn, settings, user_id, "make_interval(mins => %s)", DEVICE_MINUTES)
        conn.commit()
        return link
    except Exception:
        conn.rollback()
        raise


def redeem(conn, settings, token: str) -> str:
    try:
        row = conn.execute(
            "update invites set used_at = now() where token_hash = %s and used_at is null "
            "and expires_at > now() returning user_id", (_hash(str(token)),)).fetchone()
        if row is None:
            conn.rollback()
            raise Refused("This link has expired or was already used.")
        session = _token()
        conn.execute(
            "insert into sessions (token_hash, user_id, expires_at) "
            "values (%s, %s, now() + make_interval(days => %s))",
            (_hash(session), row[0], settings.session_days))
        conn.commit()
        return session
    except Refused:
        raise
    except Exception:
        conn.rollback()
        raise


def user_for(conn, settings, session_token: str):
    h = _hash(str(session_token))
    try:
        row = conn.execute("select user_id, expires_at > now(), renewed_at < now() - interval "
                           "'1 day' from sessions where token_hash = %s", (h,)).fetchone()
        if row is None:
            conn.rollback()
            return None
        user_id, live, stale = row
        if not live:
            conn.execute("delete from sessions where token_hash = %s", (h,))
            conn.commit()
            return None
        if stale:
            conn.execute("update sessions set expires_at = now() + make_interval(days => %s), "
                         "renewed_at = now() where token_hash = %s",
                         (settings.session_days, h))
        conn.commit()
        return user_id
    except Exception:
        conn.rollback()
        raise


def sign_out(conn, session_token: str) -> None:
    conn.execute("delete from sessions where token_hash = %s", (_hash(str(session_token)),))
    conn.commit()
