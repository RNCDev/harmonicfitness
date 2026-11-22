"""Each user's web app preferences, on their row in users: the coach they chose, the background, and whether a
checked script records without asking. None of these commit: the caller does.
"""
from .store import UserKey


# "arcs" went in 0.46.2, "lissajous" in 0.50.3 and "strands" in 0.50.4; an account still set to one reads as the default
SKIES = ("flow", "field", "waves", "bloom", "woven", "garden")


def sky(conn, uk: UserKey) -> str:
    """The web app's animated background the user chose: "flow" (the default), "field", "waves",
    "bloom", "woven" or "garden". Anything else stored (such as the retired "arcs", "lissajous" or "strands") reads as "flow"."""
    row = conn.execute("select sky from users where id = %s", (uk.user_id,)).fetchone()
    return row[0] if row and row[0] in SKIES else SKIES[0]


def set_sky(conn, uk: UserKey, value: str) -> None:
    if value not in SKIES:
        raise ValueError(f"unknown sky: {value!r}")
    conn.execute("update users set sky = %s where id = %s", (value, uk.user_id))


def coach(conn, uk: UserKey) -> tuple[str, str] | None:
    """The coach the user chose on the web app, as (slug, the listener's day it was chosen, YYYY-MM-DD), or None."""
    row = conn.execute("select coach, coach_day from users where id = %s", (uk.user_id,)).fetchone()
    if not row or not row[0] or row[1] is None:
        return None
    return row[0], row[1].isoformat()


def set_coach(conn, uk: UserKey, slug: str, day: str) -> None:
    conn.execute("update users set coach = %s, coach_day = %s where id = %s", (slug, day, uk.user_id))


def auto_record(conn, uk: UserKey) -> bool:
    """Whether a checked, priced script records at once (Settings' Record without asking), within today's
    allowance, rather than waiting for the Record button."""
    row = conn.execute("select auto_record from users where id = %s", (uk.user_id,)).fetchone()
    return bool(row and row[0])


def set_auto_record(conn, uk: UserKey, on: bool) -> None:
    conn.execute("update users set auto_record = %s where id = %s", (bool(on), uk.user_id))
