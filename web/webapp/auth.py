"""Accounts (username and password), sign-in sessions and one-time sign-in links.

Passwords are hashed with scrypt (the standard library's). Session and link tokens are 32 random
bytes, URL-safe base64; only their sha256 is stored. A one-time link signs a device in ("add a
device", 10 minutes) or lets someone who forgot their password set a new one (made by the admin
command, 24 hours); either way it ends in an ordinary session.
"""
import base64
import datetime
import hashlib
import hmac
import re
import secrets
import threading
import uuid
from typing import NamedTuple

from . import crypto, folder, store

DEVICE_MINUTES = 10
RESET_HOURS = 24
KEY_VERSION = 1   # the version a new user's data key is wrapped under
PASSWORD_MIN = 8
PASSWORD_MAX = 1024
USERNAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")
# scrypt at n=2**15, r=8: about 32 MB and a few tens of milliseconds per hash
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
# at most this many hashes at once, so a burst of sign-ins can't take the server's memory
_HASHING = threading.BoundedSemaphore(4)


class SignInLink(NamedTuple):
    url: str
    expires_at: datetime.datetime


class Refused(Exception):
    """A link that is unknown, used or expired (never says which)."""


class Invalid(ValueError):
    """A username or password that can't be used; the message says why, for the person."""


class Taken(Exception):
    """The username belongs to someone else."""


class WrongPassword(Exception):
    """Unknown username or wrong password (never says which)."""


def _token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def username(raw) -> str:
    name = raw.strip().lower() if isinstance(raw, str) else ""
    if not USERNAME.match(name):
        raise Invalid("A username is 3 to 32 letters, digits, dots, dashes or underscores, "
                      "starting with a letter or digit.")
    return name


def _check_password(pw) -> str:
    if not isinstance(pw, str) or len(pw) < PASSWORD_MIN:
        raise Invalid(f"Use a password of at least {PASSWORD_MIN} characters.")
    if len(pw) > PASSWORD_MAX:
        raise Invalid(f"Use a password of at most {PASSWORD_MAX} characters.")
    return pw


def _scrypt(pw: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    if n > 2**20 or r > 16 or p > 4:      # a damaged stored hash never asks for more
        raise ValueError("scrypt parameters out of range")
    with _HASHING:
        return hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32,
                              maxmem=128 * r * n * 2)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(pw, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${b64(salt)}${b64(digest)}"


def verify_password(pw: str, stored: str | None) -> bool:
    """True when pw matches; a missing hash still costs one hash, so timing doesn't tell."""
    if not stored:
        _scrypt(pw, b"\0" * 16, SCRYPT_N, SCRYPT_R, SCRYPT_P)
        return False
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        got = _scrypt(pw, base64.b64decode(salt), int(n), int(r), int(p))
    except ValueError:
        return False
    return hmac.compare_digest(got, base64.b64decode(digest))


def _session(conn, settings, user_id) -> str:
    token = _token()
    conn.execute("insert into sessions (token_hash, user_id, expires_at) "
                 "values (%s, %s, now() + make_interval(days => %s))",
                 (_hash(token), user_id, settings.session_days))
    return token


def register(conn, settings, raw_username, password) -> str:
    """A new account, its seeded files and a session token. Raises Invalid or Taken."""
    name = username(raw_username)
    pw_hash = hash_password(_check_password(password))
    try:
        new_id = uuid.uuid4()
        plain, wrapped = crypto.new_data_key(settings.master_key, new_id, KEY_VERSION)
        row = conn.execute(
            "insert into users (id, username, password_hash, wrapped_key, key_version) "
            "values (%s, %s, %s, %s, %s) on conflict (username) do nothing returning id",
            (new_id, name, pw_hash, wrapped, KEY_VERSION)).fetchone()
        if row is None:
            conn.rollback()
            raise Taken(name)
        uk = store.UserKey(user_id=new_id, key=plain)
        if store.write_back(conn, uk, dict(folder.seed(settings.engine_root)), {}):
            raise RuntimeError("seeding a new user conflicted")
        token = _session(conn, settings, new_id)
        conn.commit()
        return token
    except Taken:
        raise
    except Exception:
        conn.rollback()
        raise


def sign_in(conn, settings, raw_username, password) -> str:
    """A session token for a right username and password, else WrongPassword."""
    try:
        name = username(raw_username)
    except Invalid:
        name = None
    pw = password if isinstance(password, str) and len(password) <= PASSWORD_MAX else ""
    try:
        row = None
        if name is not None:
            row = conn.execute("select id, password_hash from users where username = %s",
                               (name,)).fetchone()
        if not verify_password(pw, row[1] if row else None):
            conn.rollback()
            raise WrongPassword()
        token = _session(conn, settings, row[0])
        conn.commit()
        return token
    except WrongPassword:
        raise
    except Exception:
        conn.rollback()
        raise


def set_password(conn, user_id, current, new, keep_session: str | None = None) -> None:
    """Change the password; `current` is needed only when one is set. Every other session ends."""
    pw_hash = hash_password(_check_password(new))
    try:
        stored = conn.execute("select password_hash from users where id = %s for update",
                              (user_id,)).fetchone()[0]
        if stored is not None and not verify_password(current if isinstance(current, str)
                                                      else "", stored):
            conn.rollback()
            raise WrongPassword()
        conn.execute("update users set password_hash = %s where id = %s", (pw_hash, user_id))
        conn.execute("delete from sessions where user_id = %s and token_hash <> %s",
                     (user_id, _hash(keep_session or "")))
        conn.commit()
    except WrongPassword:
        raise
    except Exception:
        conn.rollback()
        raise


def _link(settings, token: str) -> str:
    return f"{settings.base_url.rstrip('/')}/link/{token}"


def _new_link(conn, settings, user_id, interval: str, amount) -> SignInLink:
    token = _token()
    expires = conn.execute(
        f"insert into sign_in_links (token_hash, user_id, expires_at) "
        f"values (%s, %s, now() + {interval}) returning expires_at",
        (_hash(token), user_id, amount)).fetchone()[0]
    return SignInLink(_link(settings, token), expires)


def device_link(conn, settings, user_id) -> SignInLink:
    """A one-time sign-in link for another device, and when it expires."""
    try:
        link = _new_link(conn, settings, user_id, "make_interval(mins => %s)", DEVICE_MINUTES)
        conn.commit()
        return link
    except Exception:
        conn.rollback()
        raise


def reset_link(conn, settings, raw_username) -> SignInLink:
    """For a forgotten password: clears it and returns a one-time sign-in link (LookupError if
    no such user). Signed in by the link, the person sets a new password without the old one."""
    name = username(raw_username)
    try:
        row = conn.execute("update users set password_hash = null where username = %s "
                           "returning id", (name,)).fetchone()
        if row is None:
            conn.rollback()
            raise LookupError(name)
        conn.execute("delete from sessions where user_id = %s", (row[0],))
        link = _new_link(conn, settings, row[0], "make_interval(hours => %s)", RESET_HOURS)
        conn.commit()
        return link
    except LookupError:
        raise
    except Exception:
        conn.rollback()
        raise


def redeem(conn, settings, token: str) -> str:
    try:
        row = conn.execute(
            "update sign_in_links set used_at = now() where token_hash = %s and used_at is null "
            "and expires_at > now() returning user_id", (_hash(str(token)),)).fetchone()
        if row is None:
            conn.rollback()
            raise Refused("This link has expired or was already used.")
        session = _session(conn, settings, row[0])
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
