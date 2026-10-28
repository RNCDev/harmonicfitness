"""Each listener's daily allowance for recordings: characters a voice service may be sent, reserved when
they approve a recording. Nothing commits here: the caller does."""
import datetime
import os

DEFAULT_DAILY_CHARS = 60_000   # a 30-minute workout is about 20,000; HARMONICFITNESS_DAILY_CHARS changes it


def used(conn, uk, day: str) -> int:
    row = conn.execute("select chars from spend where user_id = %s and day = %s",
                       (uk.user_id, datetime.date.fromisoformat(day))).fetchone()
    return row[0] if row else 0


def reserve(conn, uk, day: str, chars: int, cap: int) -> bool:
    """Reserve `chars` for `day` if it stays within `cap`; whether it did."""
    d = datetime.date.fromisoformat(day)
    conn.execute("insert into spend (user_id, day) values (%s, %s) on conflict do nothing", (uk.user_id, d))
    return conn.execute("update spend set chars = chars + %s where user_id = %s and day = %s and chars + %s <= %s",
                        (chars, uk.user_id, d, chars, cap)).rowcount == 1


def daily_cap(env=os.environ) -> int:
    try:
        return max(0, int(env.get("HARMONICFITNESS_DAILY_CHARS", DEFAULT_DAILY_CHARS)))
    except ValueError:
        return DEFAULT_DAILY_CHARS
