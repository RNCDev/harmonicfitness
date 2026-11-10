"""Conversations: starting one, reading one (or the latest) and its history, the recording's approval, a workout
scheduled for later and its cancel, Stop, and each message after the first."""
import datetime
import json
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, StrictStr, StringConstraints

from .. import codes, conversations, jobs, keystore, media, providers, spend, store, turns
from ..api import error_body
from .state import JOB_ID, MAX_QUEUED, POST, AppState, Day, St, User, read, tx

router = APIRouter()

Now = Annotated[StrictStr, StringConstraints(max_length=40)]   # turns.check says the rest


Line = Annotated[StrictStr, StringConstraints(min_length=1, max_length=2000)]


class TurnWhen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    today: Day
    now: Now


RECORD_LINE = "Yes, record it."


class TurnLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line: Line
    today: Day
    now: Now
    # a workout for later (0.60.0): the time the listener picked, with their offset ("2026-11-04T07:00:00-05:00");
    # read only when a conversation starts
    start_at: Annotated[StrictStr, StringConstraints(max_length=40)] | None = None


LEAD = datetime.timedelta(minutes=15)    # a scheduled workout's turn starts this long before its time


FURTHEST = datetime.timedelta(hours=24)  # the furthest ahead: the check-in's "today" limits stay the day's


def later_from(start_at: str | None, utc: datetime.datetime | None = None) -> dict | None:
    """The plan for later a new conversation holds, from the page's picked time, or None for a workout now
    (none picked, or one inside the lead, which runs at once). 422 for a time that can't be read or is more
    than a day ahead."""
    if not start_at:
        return None
    try:
        at = datetime.datetime.fromisoformat(start_at)
    except ValueError:
        raise HTTPException(422, "start_at must be a time like 2026-11-04T07:00:00-05:00") from None
    off = at.utcoffset()
    if off is None or abs(off) > datetime.timedelta(hours=14):
        raise HTTPException(422, "start_at needs the listener's offset from UTC")
    now = utc or datetime.datetime.now(datetime.timezone.utc)
    if at <= now + LEAD:
        return None
    if at > now + FURTHEST + datetime.timedelta(minutes=5):
        raise HTTPException(422, "Pick a time in the next 24 hours.")
    return {"at": at.astimezone(datetime.timezone.utc).isoformat(), "local": at.strftime("%Y-%m-%d %A %H:%M"),
            "offset": int(off.total_seconds() // 60)}


STILL_WORKING = "Still working on the last message."


def turn_args(cid: int, line: str | None, answer: dict | None, today: str, now: str,
              record: bool = False) -> dict:
    args = {"conversation_id": cid, "line": line, "answer": answer, "today": today, "now": now}
    if record:
        args["record"] = True
    problem = turns.check(args)
    if problem is not None:
        raise HTTPException(422, problem)
    return args


@contextmanager
def turn_transaction(st: AppState, uk: store.UserKey):
    """One transaction for a POST that queues a turn: the user's row locked (serialising the
    queued count against the user's other posts), 429 at the cap; commits on success."""
    with tx(st) as conn:
        conn.execute("select 1 from users where id = %s for update", (uk.user_id,))
        queued = conn.execute("select count(*) from jobs where user_id = %s and state = 'queued' "
                              "and (not_before is null or not_before <= now())", (uk.user_id,)).fetchone()[0]
        if queued >= MAX_QUEUED:
            raise HTTPException(429, "too many jobs waiting")
        yield conn


def queue_turn(conn, uk: store.UserKey, args: dict) -> int:
    job_id = jobs.add(conn, uk, "turn", args)
    conversations.set_job(conn, uk, args["conversation_id"], job_id)
    return job_id


def shown(conn, uk: store.UserKey, c: conversations.Conversation) -> dict:
    """What the client sees: never the history; the job only while it works; when it last changed
    (ISO, so the client can show an earlier day's conversation as history); and each recording no longer kept
    (a newer workout replaced it) marked `gone`, so the page says so in place of a player."""
    lost = media.gone(conn, uk, c.lines)
    lines = [{**x, "audio": {**x["audio"], "gone": True}}
             if isinstance(x, dict) and isinstance(x.get("audio"), dict) and x["audio"].get("id") in lost else x
             for x in c.lines]
    return {"id": c.id, "state": c.state, "job_id": c.job_id if c.state == "working" else None,
            "lines": lines, "question": c.question, "plan": c.plan,
            "offer": {k: c.offer[k] for k in ("name", "coach", "chars", "usd", "service", "design", "plan", "first")
                      if k in c.offer} if c.offer and c.state in ("idle", "failed") else None,
            "later": {k: c.later[k] for k in ("at", "local", "due", "done", "minutes", "coach", "usd", "ceiling_usd")
                      if k in c.later} if c.later else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None}


def healed(conn, uk: store.UserKey, cid: int) -> conversations.Conversation:
    try:
        return conversations.heal(conn, uk, conversations.load(conn, uk, cid))
    except LookupError:
        raise HTTPException(404, "no such conversation") from None


@router.post("/api/conversations", status_code=202, **POST)
def start_conversation(st: St, uk: User, body: Annotated[TurnLine, Body()]):
    turn_args(0, body.line, None, body.today, body.now)
    with read(st) as conn:
        have = keystore.listing(conn, uk)
        chosen = keystore.writer(conn, uk)
    if providers.pick(st.settings.providers, have, chosen) is None:
        name = providers.PROVIDERS[chosen if chosen in st.settings.providers else st.settings.providers[0]].name
        return JSONResponse(error_body(409, f"Add a key for {name} in Settings first.", code=codes.NO_KEY_CODE), 409)
    later = later_from(body.start_at)
    with turn_transaction(st, uk) as conn:
        cid = conversations.create(conn, uk, body.line, later)
        job_id = queue_turn(conn, uk, turn_args(cid, body.line, None, body.today, body.now))
    return {"id": cid, "job_id": job_id}


@router.get("/api/conversations/latest")
def latest_conversation(st: St, uk: User):
    with tx(st) as conn:
        c = conversations.latest(conn, uk)
        if c is not None:
            c = conversations.heal(conn, uk, c)
        out = None if c is None else shown(conn, uk, c)
    return Response(status_code=204) if out is None else out


@router.get("/api/conversations/{cid}")
def get_conversation(st: St, uk: User, cid: Annotated[int, JOB_ID]):
    with tx(st) as conn:
        c = healed(conn, uk, cid)
        out = shown(conn, uk, c)
    return out


@router.get("/api/conversations/{cid}/history")
def conversation_history(st: St, uk: User, cid: Annotated[int, JOB_ID]):
    """The model's side of a conversation, for its owner only (`./harmonicfitness pull` saves it as
    history.json): every request and response, each tool call with its arguments and result, and their
    times. The page never shows it."""
    with read(st) as conn:
        try:
            c = conversations.load(conn, uk, cid)
        except LookupError:
            raise HTTPException(404, "no such conversation") from None
    try:
        history = json.loads(c.history) if c.history else []
    except ValueError:
        history = []
    return {"id": c.id, "history": history}


@router.post("/api/conversations/{cid}/record", status_code=202, **POST)
def record_offer(st: St, uk: User, cid: Annotated[int, JOB_ID], body: Annotated[TurnWhen, Body()]):
    """The listener approves the priced recording: its characters are reserved from today's allowance,
    then a turn records it, within that price."""
    args = turn_args(cid, RECORD_LINE, None, body.today, body.now, record=True)
    with turn_transaction(st, uk) as conn:
        c = healed(conn, uk, cid)
        if c.state not in ("idle", "failed") or not c.offer:
            raise HTTPException(409, "There's no recording waiting for you here.")
        cap = st.settings.daily_chars
        if not spend.reserve(conn, uk, body.today, int(c.offer.get("chars") or 0), cap):
            raise HTTPException(409, f"That's over today's allowance of {cap:,} characters of recording. "
                                     "A shorter workout fits, or try again tomorrow.")
        if not conversations.begin_turn(conn, uk, cid, RECORD_LINE, None):
            raise HTTPException(409, STILL_WORKING)
        job_id = queue_turn(conn, uk, args)
    return {"job_id": job_id}


@router.post("/api/conversations/{cid}/schedule", status_code=202, **POST)
def schedule_later(st: St, uk: User, cid: Annotated[int, JOB_ID], body: Annotated[TurnWhen, Body()]):
    """The listener's Schedule it: the one approval for a workout at their time, up to its ceiling. The turn
    that writes and records it is queued, due fifteen minutes before."""
    with turn_transaction(st, uk) as conn:
        c = healed(conn, uk, cid)
        later = c.later or {}
        if c.state != "idle" or not later.get("chars") or not later.get("at"):
            raise HTTPException(409, "There's nothing waiting to be scheduled here.")
        if conn.execute("select 1 from conversations where user_id = %s and state = 'scheduled'",
                        (uk.user_id,)).fetchone():
            raise HTTPException(409, "You've a workout scheduled already: cancel it first.")
        now = datetime.datetime.now(datetime.timezone.utc)
        at = datetime.datetime.fromisoformat(later["at"])
        if at <= now:
            raise HTTPException(409, "That time has passed: ask for the workout again.")
        due = max(now, at - LEAD)
        when = turns.said_when(later.get("local", ""))
        today, local_now = turns.local_clock(int(later.get("offset") or 0), now)
        line = (f"(From the site; the listener isn't here.) It's time for the workout they scheduled for {when}: "
                "write it now from the check-in above, then build it. Their Schedule it approved one recording "
                f"of up to {int(later.get('ceiling_chars') or 0):,} characters, so a clean price records on its "
                "own. Ask nothing: where anything is open, take your pick and say so in your last line.")
        args = dict(turn_args(cid, line, None, today, local_now), scheduled=True, offset=int(later.get("offset") or 0))
        problem = turns.check(args)
        if problem is not None:
            raise HTTPException(422, problem)
        if not conversations.schedule(conn, uk, cid, f"Schedule it for {when}.", due.isoformat()):
            raise HTTPException(409, STILL_WORKING)
        job_id = jobs.add(conn, uk, "turn", args, not_before=due)
        conversations.set_job(conn, uk, cid, job_id)
    return {"job_id": job_id, "due": due.isoformat()}


@router.post("/api/conversations/{cid}/cancel", **POST)
def cancel_later(st: St, uk: User, cid: Annotated[int, JOB_ID]):
    """Cancel a scheduled workout before its turn begins; once it has, Stop ends it instead."""
    with tx(st) as conn:
        try:
            c = conversations.load(conn, uk, cid)
        except LookupError:
            raise HTTPException(404, "no such conversation") from None
        if c.state != "scheduled":
            raise HTTPException(409, "Nothing's scheduled here.")
        if c.job_id is None or not jobs.cancel_queued(conn, uk, c.job_id):
            raise HTTPException(409, "It's being written now: use Stop to end it.")
        out = conversations.unschedule(conn, uk, cid)
        if out is None:
            raise HTTPException(409, "Nothing's scheduled here.")
        view = shown(conn, uk, out)
    return view


@router.post("/api/conversations/{cid}/stop", status_code=202, **POST)
def stop_turn(st: St, uk: User, cid: Annotated[int, JOB_ID]):
    """The listener's Stop: the running turn's work is killed within a few seconds."""
    with tx(st) as conn:
        try:
            c = conversations.load(conn, uk, cid)
        except LookupError:
            raise HTTPException(404, "no such conversation") from None
        stopped = c.state == "working" and c.job_id is not None and jobs.request_stop(conn, uk, c.job_id)
    return {"stopping": stopped}


@router.post("/api/conversations/{cid}/messages", status_code=202, **POST)
def post_message(st: St, uk: User, cid: Annotated[int, JOB_ID], body: Annotated[TurnLine, Body()]):
    args = turn_args(cid, body.line, None, body.today, body.now)
    with turn_transaction(st, uk) as conn:
        healed(conn, uk, cid)
        if not conversations.begin_turn(conn, uk, cid, body.line, None):
            raise HTTPException(409, STILL_WORKING)
        job_id = queue_turn(conn, uk, args)
    return {"job_id": job_id}
