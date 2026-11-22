"""The site's books, for the admin screen (0.87.0): what it earned (minute packs sold through Stripe), what it cost
(OpenRouter for the writing and the voices, Fly for the machines), and how it's used.

Money in is `sales` (migrations/026_books.sql): each pack at what was paid, kept when its account is deleted. Stripe's
fee isn't known here, so it's an estimate at its standard rate. Money out is `costs` (what OpenRouter reported for
each turn and recording) and `provider_spend` (OpenRouter's own daily count for the key: the difference is spend no
turn claimed); Fly is an estimate from what runs (webapp.fly). A cost that isn't tracked is None, never 0, and the
profit says it's incomplete.

Every day is a UTC day. Nothing here commits."""
import datetime
from dataclasses import dataclass

from . import minutes

STRIPE_RATE = 0.029     # Stripe's standard card fee: 2.9 percent and 30 cents a payment (an estimate here)
STRIPE_FIXED = 0.30
LISTENERS = 200         # rows in the listeners table, the best-paying first
WINDOWS = (7, 30, 90, 0)   # the screen's ranges in days; 0 is everything


def stripe_fee(dollars: float) -> float:
    return round(dollars * STRIPE_RATE + STRIPE_FIXED, 4) if dollars > 0 else 0.0


@dataclass(frozen=True)
class Fly:
    """What Fly costs, as estimated: dollars a month and what the estimate leaves out; or why there's none."""
    monthly: float | None
    lines: tuple[dict, ...] = ()
    left_out: tuple[str, ...] = ()
    why: str | None = None

    def per_day(self) -> float | None:
        return None if self.monthly is None else self.monthly * 12 / 365


def _start(conn, days: int) -> datetime.date:
    """The first day counted: `days` back including today, or the first day anything happened."""
    today = conn.execute("select (now() at time zone 'utc')::date").fetchone()[0]
    if days:
        return today - datetime.timedelta(days=days - 1)
    first = conn.execute(
        "select least((select min(created_at) from users), (select min(at) from sales), (select min(at) from costs))"
    ).fetchone()[0]
    return first.astimezone(datetime.timezone.utc).date() if first else today


def _f(x) -> float:
    return round(float(x or 0), 4)


def summary(conn, days: int, fly: Fly) -> dict:
    """Everything the admin screen shows for the last `days` days (0: all time)."""
    start = _start(conn, days)
    today = conn.execute("select (now() at time zone 'utc')::date").fetchone()[0]
    n_days = (today - start).days + 1
    since = datetime.datetime.combine(start, datetime.time(), datetime.timezone.utc)

    # money in, by day: sales on the day they were paid, refunds on the day they were refunded
    sold = {d: (float(c), int(n)) for d, c, n in conn.execute(
        "select (at at time zone 'utc')::date, sum(cents) / 100.0, count(*) from sales where at >= %s group by 1",
        (since,))}
    back = {d: float(c) for d, c in conn.execute(
        "select (refunded_at at time zone 'utc')::date, sum(cents) / 100.0 from sales "
        "where refunded_at >= %s group by 1", (since,))}
    fees = {d: float(f) for d, f in conn.execute(
        "select (at at time zone 'utc')::date, sum(cents / 100.0 * %s + %s) from sales "
        "where at >= %s and cents > 0 group by 1", (STRIPE_RATE, STRIPE_FIXED, since))}
    # money out: what turns and recordings reported, and OpenRouter's own daily count
    spent = {}
    for d, kind, usd, est in conn.execute(
            "select (at at time zone 'utc')::date, kind, sum(usd), bool_or(estimated) from costs where at >= %s "
            "group by 1, 2", (since,)):
        spent.setdefault(d, {})[kind] = (float(usd), bool(est))
    counted = {d: float(u) for d, u in conn.execute(
        "select day, usd from provider_spend where day >= %s", (start,))}
    tracking = conn.execute("select min(at) from costs").fetchone()[0]
    checked = conn.execute("select min(day) from provider_spend").fetchone()[0]

    fly_day = fly.per_day()
    daily, voice_estimated = [], False
    for i in range(n_days):
        d = start + datetime.timedelta(days=i)
        s, _ = sold.get(d, (0.0, 0))
        write, w_est = spent.get(d, {}).get("write", (0.0, False))
        voice, v_est = spent.get(d, {}).get("voice", (0.0, False))
        voice_estimated |= v_est or w_est
        known = d in counted
        extra = max(0.0, counted[d] - write - voice) if known else None
        tracked = (tracking is not None and d >= tracking.astimezone(datetime.timezone.utc).date()) or known
        daily.append({"day": d.isoformat(), "sales": _f(s), "refunds": _f(back.get(d)), "fees": _f(fees.get(d)),
                      "write": _f(write) if tracked else None, "voice": _f(voice) if tracked else None,
                      "unattributed": _f(extra) if known else None,
                      "fly": round(fly_day, 4) if fly_day is not None else None})

    def total(key):
        """The days that are tracked, added up; None when none are (a partial range is named in `missing`)."""
        vals = [r[key] for r in daily if r[key] is not None]
        return _f(sum(vals)) if vals else None

    def gap(key) -> str | None:
        """The first day counted from, where earlier days in the range aren't tracked."""
        known = [r["day"] for r in daily if r[key] is not None]
        return known[0] if known and known[0] != daily[0]["day"] else None

    sales_total = _f(sum(r["sales"] for r in daily))
    refunds_total = _f(sum(r["refunds"] for r in daily))
    fees_total = _f(sum(r["fees"] for r in daily))
    net = _f(sales_total - refunds_total)
    write_total, voice_total = total("write"), total("voice")
    extra_total, fly_total = total("unattributed"), total("fly")
    # what is known, and what isn't: a profit with a missing cost says so instead of looking better than it is
    missing = []
    for name, key, v in (("OpenRouter writing", "write", write_total), ("OpenRouter voices", "voice", voice_total),
                         ("Fly", "fly", fly_total)):
        if v is None:
            missing.append(name)
        elif gap(key):
            missing.append(f"{name} before {gap(key)}")
    if extra_total is None:
        missing.append("OpenRouter's own count")
    known_costs = sum(v for v in (write_total, voice_total, extra_total, fly_total) if v is not None)
    profit = _f(net - fees_total - known_costs)

    return {
        "days": days, "from": start.isoformat(), "to": today.isoformat(),
        "money": {
            "sales": sales_total, "refunds": refunds_total, "net": net, "fees": fees_total,
            "write": write_total, "voice": voice_total, "voice_estimated": voice_estimated,
            "unattributed": extra_total, "fly": fly_total, "profit": profit,
            "margin": round(profit / net, 4) if net > 0 else None, "missing": missing,
            "costs_since": tracking.astimezone(datetime.timezone.utc).date().isoformat() if tracking else None,
            "checked_since": checked.isoformat() if checked else None,
        },
        "fly": {"monthly": fly.monthly, "lines": list(fly.lines), "left_out": list(fly.left_out), "why": fly.why},
        "daily": daily,
        "units": _units(conn, since, tracking, write_total, voice_total),
        "usage": _usage(conn, since, days),
        "listeners": _listeners(conn, since),
    }


def _units(conn, since, tracking, write_total, voice_total) -> dict:
    """What a minute sells for and what one costs to make. A cost a minute divides what was spent by the minutes
    recorded while costs were tracked, never by minutes from before."""
    sold_min, sold_usd, sales = conn.execute(
        "select coalesce(sum(minutes), 0), coalesce(sum(cents), 0) / 100.0, count(*) from sales "
        "where at >= %s and refunded_at is null", (since,)).fetchone()
    recorded, recordings = conn.execute(
        "select coalesce(-sum(minutes), 0), count(*) from minute_ledger "
        "where kind = 'record' and kept and at >= %s", (since,)).fetchone()
    given = conn.execute("select coalesce(sum(minutes), 0) from minute_ledger where kind = 'grant' and at >= %s",
                         (since,)).fetchone()[0]
    cost = None if write_total is None or voice_total is None else write_total + voice_total
    counted_from = max(since, tracking) if tracking is not None else since
    made_min, made = conn.execute(
        "select coalesce(-sum(minutes), 0), count(*) from minute_ledger "
        "where kind = 'record' and kept and at >= %s", (counted_from,)).fetchone()
    return {
        "packs": [{"id": p.id, "minutes": p.minutes, "price": p.cents / 100,
                   "per_minute": round(p.cents / 100 / p.minutes, 4),
                   "after_fee": round((p.cents / 100 - stripe_fee(p.cents / 100)) / p.minutes, 4)}
                  for p in minutes.PACKS],
        "minutes_sold": int(sold_min), "sales": int(sales),
        "per_minute_sold": round(float(sold_usd) / sold_min, 4) if sold_min else None,
        "minutes_recorded": int(recorded), "recordings": int(recordings), "minutes_given": int(given),
        "cost_per_minute": round(cost / made_min, 4) if cost is not None and made_min else None,
        "write_per_recording": round(write_total / made, 4) if write_total is not None and made else None,
        "voice_per_minute": round(voice_total / made_min, 4) if voice_total is not None and made_min else None,
    }


def _usage(conn, since, days: int) -> dict:
    """Who's using it: accounts, who came back, who paid. Turns are counted only as far back as jobs are kept."""
    from .retention import JOB_DAYS
    accounts, new = conn.execute(
        "select count(*), count(*) filter (where created_at >= %s) from users", (since,)).fetchone()
    turns_since = max(since, datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=JOB_DAYS))
    turns, talking = conn.execute(
        "select count(*), count(distinct user_id) from jobs where kind = 'turn' and created_at >= %s",
        (turns_since,)).fetchone()
    active = conn.execute(
        "select count(*) from (select user_id from jobs where kind = 'turn' and created_at >= %s "
        "union select user_id from minute_ledger where kind = 'record' and at >= %s) a", (since, since)).fetchone()[0]
    payers_ever = conn.execute("select count(distinct user_id) from sales where user_id is not null").fetchone()[0]
    payers = conn.execute("select count(distinct user_id) from sales where at >= %s and user_id is not null",
                          (since,)).fetchone()[0]
    repeat = conn.execute("select count(*) from (select user_id from sales where user_id is not null "
                          "group by user_id having count(*) > 1) r").fetchone()[0]
    recorders = conn.execute("select count(distinct user_id) from minute_ledger where kind = 'record' and kept"
                             ).fetchone()[0]
    return {
        "accounts": int(accounts), "new_accounts": int(new), "active": int(active),
        "turns": int(turns), "talking": int(talking),
        "turn_days": min(days or JOB_DAYS, JOB_DAYS),
        "payers": int(payers), "payers_ever": int(payers_ever), "repeat_payers": int(repeat),
        "recorders_ever": int(recorders),
        "paid_share": round(payers_ever / accounts, 4) if accounts else None,
        "recorded_share": round(recorders / accounts, 4) if accounts else None,
    }


def _listeners(conn, since) -> list[dict]:
    """Each listener with any activity in the range: what they paid, what they used, what they cost. Username and
    numbers only."""
    rows = conn.execute("""
        with paid as (select user_id, coalesce(sum(cents) filter (where refunded_at is null), 0) / 100.0 as usd,
                             coalesce(sum(minutes) filter (where refunded_at is null), 0) as bought, count(*) as n
                      from sales where at >= %(s)s and user_id is not null group by user_id),
             used as (select user_id, coalesce(-sum(minutes), 0) as rec_min, count(*) as recs
                      from minute_ledger where kind = 'record' and kept and at >= %(s)s group by user_id),
             cost as (select user_id, sum(usd) as usd from costs where at >= %(s)s and user_id is not null
                      group by user_id),
             seen as (select user_id from jobs where kind = 'turn' and created_at >= %(s)s)
        select u.username, u.created_at, u.minutes, coalesce(p.usd, 0), coalesce(p.bought, 0), coalesce(p.n, 0),
               coalesce(r.rec_min, 0), coalesce(r.recs, 0), c.usd
        from users u left join paid p on p.user_id = u.id left join used r on r.user_id = u.id
             left join cost c on c.user_id = u.id
        where p.user_id is not null or r.user_id is not null or c.user_id is not null
              or u.created_at >= %(s)s or u.id in (select user_id from seen)
        order by coalesce(p.usd, 0) desc, coalesce(r.rec_min, 0) desc, u.created_at desc
        limit %(n)s""", {"s": since, "n": LISTENERS}).fetchall()
    out = []
    for name, joined, balance, paid, bought, packs, rec_min, recs, cost in rows:
        paid = float(paid)
        fee = sum(stripe_fee(paid / packs) for _ in range(packs)) if packs else 0.0
        out.append({"username": name, "joined": joined.astimezone(datetime.timezone.utc).date().isoformat(),
                    "balance": int(balance), "paid": _f(paid), "bought": int(bought), "packs": int(packs),
                    "recorded": int(rec_min), "recordings": int(recs),
                    "cost": _f(cost) if cost is not None else None,
                    "profit": _f(paid - fee - float(cost or 0))})
    return out
