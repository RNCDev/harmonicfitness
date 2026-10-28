"""The encrypted, versioned store of each user's context files.

A row holds no plain path: `path_hash` (an HMAC of the path under a subkey of the user's data key)
finds it, `path` is the path sealed, and the body is sealed bound to the plain path, so a body
can't be moved to another path.
"""
import hashlib
import hmac
import posixpath
from dataclasses import dataclass, field
from uuid import UUID

from . import crypto


@dataclass(frozen=True)
class UserKey:
    user_id: UUID
    key: bytes = field(repr=False)


def user_key(conn, settings, user_id) -> UserKey:
    row = conn.execute("select wrapped_key, key_version from users where id = %s",
                       (user_id,)).fetchone()
    if row is None:
        raise LookupError("no such user")
    uid = UUID(str(user_id))
    return UserKey(user_id=uid, key=crypto.unwrap(settings.master_key, bytes(row[0]), uid, row[1]))


def check_path(path: str) -> str:
    if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path
            or path.startswith("/") or posixpath.normpath(path) != path
            or ".." in path.split("/")):
        raise ValueError(f"bad path: {path!r}")
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError(f"bad path: {path!r}") from None
    return path


def _aad(uk: UserKey, path: str) -> bytes:
    return f"{uk.user_id}:context_files:{path}".encode()


def _path_aad(uk: UserKey) -> bytes:
    return f"{uk.user_id}:context_files:path".encode()


def _path_hash(uk: UserKey, path: str) -> bytes:
    subkey = hmac.new(uk.key, b"wt:path-hash", hashlib.sha256).digest()
    return hmac.new(subkey, path.encode("utf-8"), hashlib.sha256).digest()


def _seal_path(uk: UserKey, path: str) -> bytes:
    return crypto.seal(uk.key, path.encode("utf-8"), _path_aad(uk))


def _open_path(uk: UserKey, sealed) -> str:
    return crypto.open_(uk.key, bytes(sealed), _path_aad(uk)).decode("utf-8")


def read_all(conn, uk: UserKey) -> dict[str, tuple[int, bytes]]:
    rows = conn.execute("select path, version, body from context_files where user_id = %s",
                        (uk.user_id,)).fetchall()
    out = {}
    for sealed_path, v, b in rows:
        p = _open_path(uk, sealed_path)
        out[p] = (v, crypto.open_(uk.key, bytes(b), _aad(uk, p)))
    return dict(sorted(out.items()))


def listing(conn, uk: UserKey) -> list[tuple[str, int, object]]:
    """(path, version, updated_at) of each file, by path; bodies are not opened."""
    rows = conn.execute("select path, version, updated_at from context_files where user_id = %s",
                        (uk.user_id,)).fetchall()
    return sorted((_open_path(uk, p), v, u) for p, v, u in rows)


def write_back(conn, uk: UserKey, changes: dict[str, bytes | None],
               base: dict[str, int]) -> list[str]:
    """Apply changes in the caller's transaction; return the paths that conflicted.

    Deleting a path with no base version counts as a conflict.
    """
    for path in changes:
        check_path(path)
    conflicts = []
    for path in sorted(changes):
        body = changes[path]
        at = base.get(path)
        h = _path_hash(uk, path)
        if body is None:
            n = 0
            if at is not None:
                n = conn.execute("delete from context_files where user_id = %s and path_hash = %s "
                                 "and version = %s", (uk.user_id, h, at)).rowcount
        else:
            sealed = crypto.seal(uk.key, body, _aad(uk, path))
            if at is None:
                n = conn.execute(
                    "insert into context_files (user_id, path_hash, path, version, body) "
                    "values (%s, %s, %s, 1, %s) on conflict do nothing",
                    (uk.user_id, h, _seal_path(uk, path), sealed)).rowcount
            else:
                n = conn.execute(
                    "update context_files set body = %s, version = version + 1, "
                    "updated_at = now() where user_id = %s and path_hash = %s and version = %s",
                    (sealed, uk.user_id, h, at)).rowcount
        if n != 1:
            conflicts.append(path)
    return conflicts


def put(conn, uk: UserKey, path: str, body: bytes) -> int:
    """A direct edit: always wins, bumps the version, returns it."""
    check_path(path)
    sealed = crypto.seal(uk.key, body, _aad(uk, path))
    return conn.execute(
        "insert into context_files (user_id, path_hash, path, version, body) "
        "values (%s, %s, %s, 1, %s) "
        "on conflict (user_id, path_hash) do update set body = excluded.body, "
        "version = context_files.version + 1, updated_at = now() returning version",
        (uk.user_id, _path_hash(uk, path), _seal_path(uk, path), sealed)).fetchone()[0]
