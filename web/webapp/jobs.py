"""The job queue: one table, claimed with FOR UPDATE SKIP LOCKED.

A job's args, result and events are JSON sealed with its user's data key; `error` is plain text
and holds only wording of the web layer's own (never the engine's output or anything personal).
The database keeps one running job per user (the partial unique index one_running_job_per_user).
A job that dies is failed by `reap`, never requeued: it may already have reached a paid service.

Transactions: every function that writes (enqueue, claim, heartbeat, finish, complete, fail, reap,
event) commits its own work. The readers (args, result, events, status) run in the caller's transaction
and don't commit.
"""
import json
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

import psycopg

from . import crypto
from .store import UserKey


@dataclass(frozen=True)
class Job:
    id: int
    user_id: UUID
    kind: str


def _aad(uk: UserKey, job_id: int, what: str) -> bytes:
    return f"{uk.user_id}:jobs:{job_id}:{what}".encode()


def _event_aad(uk: UserKey, job_id: int) -> bytes:
    return f"{uk.user_id}:job_events:{job_id}".encode()


def _seal(uk: UserKey, value: dict, aad: bytes) -> bytes:
    return crypto.seal(uk.key, json.dumps(value).encode("utf-8"), aad)


def _open(uk: UserKey, sealed, aad: bytes) -> dict:
    return json.loads(crypto.open_(uk.key, bytes(sealed), aad).decode("utf-8"))


def _done(conn, fn):
    """Run fn in a transaction and commit; roll back on any error."""
    try:
        out = fn()
        conn.commit()
        return out
    except Exception:
        conn.rollback()
        raise


def enqueue(conn, uk: UserKey, kind: str, args: dict) -> int:
    """Queue a job and wake the workers (NOTIFY jobs_queued). Commits."""
    def work():
        job_id = conn.execute(
            "insert into jobs (user_id, kind, args, state) values (%s, %s, %s, 'queued') returning id",
            (uk.user_id, kind, b"")).fetchone()[0]
        conn.execute("update jobs set args = %s where id = %s",
                     (_seal(uk, args, _aad(uk, job_id, "args")), job_id))
        conn.execute("select pg_notify('jobs_queued', '')")
        return job_id
    return _done(conn, work)


def claim(conn) -> Job | None:
    """The oldest queued job whose user has none running, now running; None if there is none. Commits.

    Two workers claiming jobs of one user at once: the loser hits the unique index and gets None."""
    try:
        row = conn.execute(
            "select id, user_id, kind from jobs j where state = 'queued' and not exists "
            "(select 1 from jobs r where r.user_id = j.user_id and r.state = 'running') "
            "order by id for update of j skip locked limit 1").fetchone()
        if row is None:
            conn.commit()
            return None
        conn.execute("update jobs set state = 'running', started_at = now(), heartbeat_at = now() "
                     "where id = %s", (row[0],))
        conn.commit()
    except psycopg.errors.UniqueViolation:
        conn.rollback()
        return None
    except Exception:
        conn.rollback()
        raise
    return Job(id=row[0], user_id=UUID(str(row[1])), kind=row[2])


def heartbeat(conn, job_id: int) -> bool:
    """Mark a running job alive. Commits."""
    return _done(conn, lambda: conn.execute(
        "update jobs set heartbeat_at = now() where id = %s and state = 'running'",
        (job_id,)).rowcount == 1)


def finish(conn, uk: UserKey, job_id: int, result: dict) -> bool:
    """A running job done, with its sealed result; False if it was no longer running. Commits."""
    return _done(conn, lambda: conn.execute(
        "update jobs set state = 'done', result = %s, finished_at = now() "
        "where id = %s and user_id = %s and state = 'running'",
        (_seal(uk, result, _aad(uk, job_id, "result")), job_id, uk.user_id)).rowcount == 1)


def fail(conn, uk: UserKey | None, job_id: int, error: str, result: dict | None = None) -> bool:
    """A queued or running job failed. `error` is plain text: the web layer's own words, nothing
    personal and nothing from the engine; what the engine said goes in the sealed `result` (which
    needs `uk`; with no result, `uk` may be None, as when the user's key couldn't be read). Commits."""
    sealed = None if result is None else _seal(uk, result, _aad(uk, job_id, "result"))
    return _done(conn, lambda: conn.execute(
        "update jobs set state = 'failed', error = %s, result = %s, finished_at = now() "
        "where id = %s and state in ('queued', 'running')",
        (error, sealed, job_id)).rowcount == 1)


def reap(conn, stale_after: int = 120) -> list[int]:
    """Fail every running job whose heartbeat is older than `stale_after` seconds ("interrupted"),
    freeing its user. Never requeues. Commits."""
    return _done(conn, lambda: sorted(r[0] for r in conn.execute(
        "update jobs set state = 'failed', error = 'interrupted', finished_at = now() "
        "where state = 'running' and heartbeat_at < now() - make_interval(secs => %s) returning id",
        (stale_after,)).fetchall()))


def _insert_event(conn, uk: UserKey, job_id: int, body: dict) -> int:
    event_id = conn.execute(
        "insert into job_events (job_id, body) values (%s, %s) returning id",
        (job_id, _seal(uk, body, _event_aad(uk, job_id)))).fetchone()[0]
    conn.execute("select pg_notify('job_events', %s)", (str(job_id),))   # delivered on commit
    return event_id


def event(conn, uk: UserKey, job_id: int, body: dict) -> int:
    """Record a sealed event and NOTIFY job_events with the job id. Commits (with whatever else the
    connection has pending), so a stream sees it now."""
    return _done(conn, lambda: _insert_event(conn, uk, job_id, body))


def complete(conn, uk: UserKey, job_id: int, result: dict,
             apply: Callable[[], list[dict]] | None = None) -> bool:
    """Finish a running job in ONE transaction with its side effects: lock the job's row; if it is no
    longer running (reaped, say), roll back and return False, so nothing of `apply` happens. Else run
    `apply()` (such as a write-back of the user's files) in the same transaction, record the events it
    returns, set the job done with its sealed result and commit. Commits or rolls back."""
    try:
        row = conn.execute("select 1 from jobs where id = %s and state = 'running' for update",
                           (job_id,)).fetchone()
        if row is None:
            conn.rollback()
            return False
        for body in (apply() if apply else []):
            _insert_event(conn, uk, job_id, body)
        conn.execute("update jobs set state = 'done', result = %s, finished_at = now() where id = %s",
                     (_seal(uk, result, _aad(uk, job_id, "result")), job_id))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def events(conn, uk: UserKey, job_id: int, after: int = 0) -> list[tuple[int, dict]]:
    """The job's events after event id `after`, oldest first. Only the job's own user's. No commit."""
    rows = conn.execute(
        "select e.id, e.body from job_events e join jobs j on j.id = e.job_id "
        "where e.job_id = %s and j.user_id = %s and e.id > %s order by e.id",
        (job_id, uk.user_id, after)).fetchall()
    return [(i, _open(uk, b, _event_aad(uk, job_id))) for i, b in rows]


def _row(conn, uk: UserKey, job_id: int, column: str):
    row = conn.execute(f"select {column} from jobs where id = %s and user_id = %s",
                       (job_id, uk.user_id)).fetchone()
    if row is None:
        raise LookupError("no such job")
    return row[0]


def args(conn, uk: UserKey, job_id: int) -> dict:
    """The job's arguments. No commit."""
    return _open(uk, _row(conn, uk, job_id, "args"), _aad(uk, job_id, "args"))


def result(conn, uk: UserKey, job_id: int) -> dict | None:
    """The job's result (on failure, what the engine said), or None. No commit."""
    sealed = _row(conn, uk, job_id, "result")
    return None if sealed is None else _open(uk, sealed, _aad(uk, job_id, "result"))


def status(conn, uk: UserKey, job_id: int) -> dict:
    """{'kind', 'state', 'error'} of the user's job. No commit."""
    row = conn.execute("select kind, state, error from jobs where id = %s and user_id = %s",
                       (job_id, uk.user_id)).fetchone()
    if row is None:
        raise LookupError("no such job")
    return {"kind": row[0], "state": row[1], "error": row[2]}
