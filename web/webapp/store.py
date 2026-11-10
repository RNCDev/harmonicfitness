"""The encrypted, versioned store of each user's context files.

A row holds no plain path: `path_hash` (an HMAC of the path under a subkey of the user's data key)
finds it, `path` is the path sealed, and the body is sealed bound to the plain path, so a body
can't be moved to another path.

Transactions: nothing here commits or rolls back. That's the rule for every function in webapp/ that reads or
writes data: its caller owns the transaction (a route through routes.state's tx or read, the worker loop for its
jobs). Only the job queue's single-step units of work, the sweeps and the migrations commit their own (jobs.py).
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


def _digest_aad(uk: UserKey, path: str) -> bytes:
    return f"{uk.user_id}:context_files:digest:{path}".encode()


def _seal_digest(uk: UserKey, path: str, body: bytes) -> bytes:
    """The body's SHA-256, sealed: never stored in plain, where it would confirm a guess at what a file says."""
    return crypto.seal(uk.key, hashlib.sha256(body).digest(), _digest_aad(uk, path))


def read_all(conn, uk: UserKey) -> dict[str, tuple[int, bytes]]:
    rows = conn.execute("select path, version, body from context_files where user_id = %s",
                        (uk.user_id,)).fetchall()
    out = {}
    for sealed_path, v, b in rows:
        p = _open_path(uk, sealed_path)
        out[p] = (v, crypto.open_(uk.key, bytes(b), _aad(uk, p)))
    return dict(sorted(out.items()))


def read_many(conn, uk: UserKey, paths) -> dict[str, tuple[int, bytes]]:
    """{path: (version, body)} of the named files the user has, by path; the rest are left out."""
    wanted = {_path_hash(uk, check_path(p)): p for p in paths}
    if not wanted:
        return {}
    rows = conn.execute("select path_hash, version, body from context_files where user_id = %s and path_hash = any(%s)",
                        (uk.user_id, list(wanted))).fetchall()
    out = {}
    for h, v, b in rows:
        p = wanted[bytes(h)]
        out[p] = (v, crypto.open_(uk.key, bytes(b), _aad(uk, p)))
    return dict(sorted(out.items()))


def read_where(conn, uk: UserKey, keep) -> dict[str, tuple[int, bytes]]:
    """{path: (version, body)} of the files whose path `keep` takes: the paths are opened first, and only the kept
    bodies are read and opened."""
    rows = conn.execute("select path_hash, path from context_files where user_id = %s", (uk.user_id,)).fetchall()
    wanted = {bytes(h): p for h, sealed in rows if keep(p := _open_path(uk, sealed))}
    if not wanted:
        return {}
    rows = conn.execute("select path_hash, version, body from context_files where user_id = %s and path_hash = any(%s)",
                        (uk.user_id, list(wanted))).fetchall()
    out = {}
    for h, v, b in rows:
        p = wanted[bytes(h)]
        out[p] = (v, crypto.open_(uk.key, bytes(b), _aad(uk, p)))
    return dict(sorted(out.items()))


def digests(conn, uk: UserKey) -> dict[str, tuple[int, str]]:
    """{path: (version, the body's SHA-256 in hex)} of every file, by path: from the sealed digest, or the body for
    a row written before 0.77.0."""
    rows = conn.execute("select path, version, digest, case when digest is null then body end from context_files "
                        "where user_id = %s", (uk.user_id,)).fetchall()
    out = {}
    for sealed, v, d, b in rows:
        p = _open_path(uk, sealed)
        if d is not None:
            out[p] = (v, crypto.open_(uk.key, bytes(d), _digest_aad(uk, p)).hex())
        else:
            out[p] = (v, hashlib.sha256(crypto.open_(uk.key, bytes(b), _aad(uk, p))).hexdigest())
    return dict(sorted(out.items()))


def read_one(conn, uk: UserKey, path: str) -> tuple[int, bytes] | None:
    """(version, body) of one file, or None when the user has none at that path."""
    check_path(path)
    row = conn.execute("select version, body from context_files where user_id = %s and path_hash = %s",
                       (uk.user_id, _path_hash(uk, path))).fetchone()
    return None if row is None else (row[0], crypto.open_(uk.key, bytes(row[1]), _aad(uk, path)))


def listing(conn, uk: UserKey) -> list[tuple[str, int, object]]:
    """(path, version, updated_at) of each file, by path; bodies are not opened."""
    rows = conn.execute("select path, version, updated_at from context_files where user_id = %s",
                        (uk.user_id,)).fetchall()
    return sorted((_open_path(uk, p), v, u) for p, v, u in rows)


def fingerprint(conn, uk: UserKey) -> str:
    """A digest of which files the user has and each one's version, from the rows alone (no path or body is
    opened): it changes whenever a file is written, added or removed."""
    rows = conn.execute("select path_hash, version, updated_at from context_files where user_id = %s "
                        "order by path_hash", (uk.user_id,)).fetchall()
    h = hashlib.sha256()
    for path_hash, v, u in rows:
        h.update(bytes(path_hash) + f":{v}:{u.isoformat()}\n".encode())
    return h.hexdigest()


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
                    "insert into context_files (user_id, path_hash, path, version, body, digest) "
                    "values (%s, %s, %s, 1, %s, %s) on conflict do nothing",
                    (uk.user_id, h, _seal_path(uk, path), sealed, _seal_digest(uk, path, body))).rowcount
            else:
                n = conn.execute(
                    "update context_files set body = %s, digest = %s, version = version + 1, "
                    "updated_at = now() where user_id = %s and path_hash = %s and version = %s",
                    (sealed, _seal_digest(uk, path, body), uk.user_id, h, at)).rowcount
        if n != 1:
            conflicts.append(path)
    return conflicts


def put(conn, uk: UserKey, path: str, body: bytes) -> int:
    """A direct edit: always wins, bumps the version, returns it."""
    check_path(path)
    sealed = crypto.seal(uk.key, body, _aad(uk, path))
    return conn.execute(
        "insert into context_files (user_id, path_hash, path, version, body, digest) "
        "values (%s, %s, %s, 1, %s, %s) "
        "on conflict (user_id, path_hash) do update set body = excluded.body, digest = excluded.digest, "
        "version = context_files.version + 1, updated_at = now() returning version",
        (uk.user_id, _path_hash(uk, path), _seal_path(uk, path), sealed, _seal_digest(uk, path, body))).fetchone()[0]
