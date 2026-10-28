"""The encrypted, versioned store of each user's context files."""
import posixpath
from dataclasses import dataclass, field
from uuid import UUID

from . import crypto


@dataclass(frozen=True)
class UserKey:
    user_id: UUID
    key: bytes = field(repr=False)


def user_key(conn, settings, user_id) -> UserKey:
    row = conn.execute("select wrapped_key from users where id = %s", (user_id,)).fetchone()
    if row is None:
        raise LookupError("no such user")
    return UserKey(user_id=user_id, key=crypto.unwrap(settings.master_key, bytes(row[0])))


def _check(path: str) -> str:
    if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path
            or path.startswith("/") or posixpath.normpath(path) != path
            or ".." in path.split("/")):
        raise ValueError(f"bad path: {path!r}")
    return path


def _aad(uk: UserKey, path: str) -> bytes:
    return f"{uk.user_id}:context_files:{path}".encode()


def read_all(conn, uk: UserKey) -> dict[str, tuple[int, bytes]]:
    rows = conn.execute("select path, version, body from context_files where user_id = %s "
                        "order by path", (uk.user_id,)).fetchall()
    return {p: (v, crypto.open_(uk.key, bytes(b), _aad(uk, p))) for p, v, b in rows}


def write_back(conn, uk: UserKey, changes: dict[str, bytes | None],
               base: dict[str, int]) -> list[str]:
    """Apply changes in the caller's transaction; return the paths that conflicted."""
    for path in changes:
        _check(path)
    conflicts = []
    for path in sorted(changes):
        body = changes[path]
        at = base.get(path)
        if body is None:
            n = 0
            if at is not None:
                n = conn.execute("delete from context_files where user_id = %s and path = %s "
                                 "and version = %s", (uk.user_id, path, at)).rowcount
        else:
            sealed = crypto.seal(uk.key, body, _aad(uk, path))
            if at is None:
                n = conn.execute(
                    "insert into context_files (user_id, path, version, body) "
                    "values (%s, %s, 1, %s) on conflict do nothing",
                    (uk.user_id, path, sealed)).rowcount
            else:
                n = conn.execute(
                    "update context_files set body = %s, version = version + 1, "
                    "updated_at = now() where user_id = %s and path = %s and version = %s",
                    (sealed, uk.user_id, path, at)).rowcount
        if n != 1:
            conflicts.append(path)
    return conflicts


def put(conn, uk: UserKey, path: str, body: bytes) -> int:
    """A direct edit: always wins, bumps the version, returns it."""
    _check(path)
    sealed = crypto.seal(uk.key, body, _aad(uk, path))
    return conn.execute(
        "insert into context_files (user_id, path, version, body) values (%s, %s, 1, %s) "
        "on conflict (user_id, path) do update set body = excluded.body, "
        "version = context_files.version + 1, updated_at = now() returning version",
        (uk.user_id, path, sealed)).fetchone()[0]
