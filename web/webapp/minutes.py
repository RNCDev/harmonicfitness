"""Minutes: what a listener on the hosted site pays for a recording with (0.85.0).

The balance is users.minutes, never below zero; every change is a row in minute_ledger written in the same
transaction, and (user, kind, ref) is unique, so each thing happens once however often it's asked for: a Stripe
webhook delivered twice credits once, a hold released twice hands back once.

A recording costs its planned length, rounded up to a whole minute, held when Record is pressed (the hold is the
charge). The hold is kept when the recording's MP3 is stored, and handed back when the turn ends without one. The
first time a script is recorded again (a fix after hearing it) costs nothing; after that each recording is charged.

Nothing here commits: the caller owns the transaction."""
import hashlib
import hmac
import math
from dataclasses import dataclass

WELCOME = 20            # minutes a new account starts with, once
FREE_AGAIN = 1          # recordings of an already-paid script that cost nothing
STALE_MINUTES = 10      # a hold younger than this is never swept: its turn may be about to start
DAILY_TURNS = 40        # turns a listener may start in 24 hours on the hosted site (the site pays for each)


@dataclass(frozen=True)
class Pack:
    id: str             # the Stripe price's lookup key
    minutes: int
    cents: int

    @property
    def label(self) -> str:
        return f"{self.minutes} minutes"


# Priced from what a recorded minute costs the site (about 3 cents: the voice at 1.3 to 1.6, the writing at 1.1 to
# 1.4 and rising in 2027), Stripe's 30 cents and 2.9 percent, and the minutes given away. webapp.stripe_setup
# makes the same three in Stripe, by these lookup keys.
PACKS = (Pack("hf_minutes_60", 60, 500), Pack("hf_minutes_140", 140, 1000), Pack("hf_minutes_320", 320, 2000))


def pack(pack_id: str) -> Pack | None:
    return next((p for p in PACKS if p.id == pack_id), None)


def needed(seconds) -> int:
    """The minutes a recording of `seconds` costs: its length rounded up, never less than one."""
    try:
        return max(1, math.ceil(float(seconds) / 60))
    except (TypeError, ValueError):
        return 1


def tag(uk, stem: str | None) -> str | None:
    """A workout's folder name as the ledger holds it: a digest keyed with the listener's own key, so the ledger
    can tell two recordings of one script apart from two scripts without holding a name."""
    if not stem:
        return None
    return hmac.new(uk.key, f"minutes:{stem}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def balance(conn, user_id) -> int:
    row = conn.execute("select minutes from users where id = %s", (user_id,)).fetchone()
    return row[0] if row else 0


def _credit(conn, user_id, kind: str, minutes: int, ref: str, note: str | None = None) -> bool:
    """Add `minutes` once for (kind, ref); whether this call was the one that added them."""
    row = conn.execute(
        "insert into minute_ledger (user_id, kind, minutes, ref, note) values (%s, %s, %s, %s, %s) "
        "on conflict (user_id, kind, ref) do nothing returning id", (user_id, kind, minutes, ref, note)).fetchone()
    if row is None:
        return False
    conn.execute("update users set minutes = minutes + %s where id = %s", (minutes, user_id))
    return True


def grant(conn, user_id, minutes: int, ref: str, note: str | None = None) -> bool:
    """Minutes given, once per `ref` (an admin's gift names its own)."""
    return minutes > 0 and _credit(conn, user_id, "grant", minutes, ref, note)


def who(master_key: bytes, email: str) -> bytes:
    """A verified email address as the `welcomed` table holds it: a digest keyed with the site's master key."""
    return hmac.new(master_key, f"welcomed:{email.strip().lower()}".encode("utf-8"), hashlib.sha256).digest()


def welcome(conn, user_id, who: bytes | None = None) -> bool:
    """The minutes an account starts with, once per account and, with `who` (see who), once per person: an
    account deleted and made again starts with none."""
    if conn.execute("select 1 from minute_ledger where user_id = %s and kind = 'grant' and ref = 'welcome'",
                    (user_id,)).fetchone():
        return False
    if who is not None and conn.execute("insert into welcomed (who) values (%s) on conflict do nothing returning 1",
                                        (who,)).fetchone() is None:
        return False
    return grant(conn, user_id, WELCOME, "welcome")


def purchase(conn, user_id, minutes: int, ref: str, note: str | None = None) -> bool:
    """A paid pack's minutes, once per Checkout session."""
    return minutes > 0 and _credit(conn, user_id, "purchase", minutes, ref, note)


def sold(conn, user_id, p: Pack, ref: str) -> None:
    """The sale behind a purchase, for the books: the pack and what was paid, once per ref (0.87.0)."""
    conn.execute("insert into sales (ref, user_id, pack, minutes, cents) values (%s, %s, %s, %s, %s) "
                 "on conflict (ref) do nothing", (ref, user_id, p.id, p.minutes, p.cents))


def refunded(conn, ref: str) -> None:
    """A sale refunded in full, for the books, once: its money is taken back whatever minutes were left to take."""
    conn.execute("update sales set refunded_at = now() where ref = %s and refunded_at is null", (ref,))


def refund(conn, user_id, ref: str) -> int:
    """Take back a refunded purchase's minutes, once, as far as the balance goes; the minutes taken."""
    conn.execute("select 1 from users where id = %s for update", (user_id,))
    bought = conn.execute("select minutes from minute_ledger where user_id = %s and kind = 'purchase' and ref = %s",
                          (user_id, ref)).fetchone()
    if bought is None:
        return 0
    taken = min(bought[0], balance(conn, user_id))
    row = conn.execute(
        "insert into minute_ledger (user_id, kind, minutes, ref) values (%s, 'refund', %s, %s) "
        "on conflict (user_id, kind, ref) do nothing returning id", (user_id, -taken, ref)).fetchone()
    if row is None:
        return 0
    conn.execute("update users set minutes = minutes - %s where id = %s", (taken, user_id))
    return taken


def owed(conn, user_id, script: str | None, minutes: int) -> int:
    """What recording `minutes` of the script tagged `script` (see tag) costs now: nothing the first time an
    already-paid script is recorded again, else all of it."""
    if not script:
        return minutes
    paid, again = conn.execute(
        "select count(*) filter (where minutes < 0), count(*) filter (where minutes = 0) from minute_ledger "
        "where user_id = %s and kind = 'record' and kept and tag = %s", (user_id, script)).fetchone()
    return 0 if paid and again < FREE_AGAIN else minutes


def hold(conn, user_id, ref, minutes: int, script: str | None = None) -> bool:
    """Take a recording's minutes from the balance, as the hold `ref` (the turn's job id); False, with nothing
    changed, when the balance doesn't cover it. Asked again for the same `ref`, it holds nothing more."""
    ref = str(ref)
    conn.execute("select 1 from users where id = %s for update", (user_id,))
    if conn.execute("select 1 from minute_ledger where user_id = %s and kind = 'record' and ref = %s",
                    (user_id, ref)).fetchone():
        return True
    charge = owed(conn, user_id, script, max(1, int(minutes)))
    if conn.execute("update users set minutes = minutes - %s where id = %s and minutes >= %s",
                    (charge, user_id, charge)).rowcount != 1:
        return False
    conn.execute("insert into minute_ledger (user_id, kind, minutes, ref, tag) values (%s, 'record', %s, %s, %s)",
                 (user_id, -charge, ref, script))
    return True


def keep(conn, user_id, ref) -> None:
    """The hold's recording was made and stored: it's never handed back."""
    conn.execute("update minute_ledger set kept = true where user_id = %s and kind = 'record' and ref = %s",
                 (user_id, str(ref)))


def release(conn, user_id, ref) -> int:
    """Hand back a hold whose recording was never kept, once; the minutes handed back."""
    ref = str(ref)
    row = conn.execute("select minutes from minute_ledger where user_id = %s and kind = 'record' and ref = %s "
                       "and not kept for update", (user_id, ref)).fetchone()
    if row is None:
        return 0
    return -row[0] if _credit(conn, user_id, "release", -row[0], ref) else 0


def sweep(conn) -> int:
    """Hand back every hold left by a turn that never finished (a worker that died, a job reaped): one that's
    neither kept nor released, whose job is no longer queued or running. The holds handed back."""
    rows = conn.execute(
        "select h.user_id, h.ref from minute_ledger h where h.kind = 'record' and not h.kept "
        "and h.at < now() - make_interval(mins => %s) "
        "and not exists (select 1 from minute_ledger r where r.user_id = h.user_id and r.kind = 'release' "
        "                and r.ref = h.ref) "
        "and not exists (select 1 from jobs j where j.id::text = h.ref and j.user_id = h.user_id "
        "                and j.state in ('queued', 'running'))", (STALE_MINUTES,)).fetchall()
    for user_id, ref in rows:
        release(conn, user_id, ref)
    return len(rows)


def turns_today(conn, user_id) -> int:
    """Turns this listener started in the last 24 hours."""
    return conn.execute("select count(*) from jobs where user_id = %s and kind = 'turn' "
                        "and created_at > now() - interval '24 hours'", (user_id,)).fetchone()[0]


WORDS = {"grant": "Minutes to start with", "purchase": "Minutes bought", "record": "A recording",
         "release": "Handed back: no recording was made", "refund": "A refunded purchase"}


def history(conn, user_id, limit: int = 30) -> list[dict]:
    """The newest ledger rows, as the page shows them (a hold that cost nothing and one handed back are left out
    with their release, so the list reads as what was bought and what was recorded)."""
    rows = conn.execute(
        "select l.at, l.kind, l.minutes, l.note from minute_ledger l where l.user_id = %s "
        "and l.kind <> 'release' and not (l.kind = 'record' and not l.kept) order by l.at desc, l.id desc limit %s",
        (user_id, limit)).fetchall()
    return [{"at": at.isoformat(), "kind": kind, "minutes": n, "what": note or WORDS[kind]}
            for at, kind, n, note in rows]
