"""Postgres connection and the migration runner."""
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent / "migrations"
_LOCK_KEY = 7_340_001  # arbitrary; serialises concurrent migrators


def connect(url: str, schema: str | None = None) -> psycopg.Connection:
    """A connection with autocommit off; callers commit. `schema` (tests) sets search_path."""
    if schema:
        return psycopg.connect(url, options=f"-c search_path={schema}")
    return psycopg.connect(url)


def migrate(conn: psycopg.Connection) -> list[str]:
    """Apply migrations/*.sql not yet recorded, in name order, each in its own transaction.

    Needs autocommit off (what `connect` gives). Safe when two processes start at once:
    every step takes the advisory lock first, in the same transaction as its work.
    """
    if conn.autocommit:
        raise ValueError("migrate needs a connection with autocommit off")
    conn.commit()
    applied = []
    for path in sorted(MIGRATIONS.glob("*.sql")):
        try:
            conn.execute("select pg_advisory_xact_lock(%s)", (_LOCK_KEY,))
            conn.execute("create table if not exists schema_migrations ("
                         "name text primary key, applied_at timestamptz not null default now())")
            done = conn.execute("select 1 from schema_migrations where name = %s",
                                (path.name,)).fetchone()
            if not done:
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("insert into schema_migrations (name) values (%s)", (path.name,))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        if not done:
            applied.append(path.name)
    return applied
