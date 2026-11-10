"""Jobs: a brief, a balance check, a job's status and its event stream.

An event stream holds one connection of its own for its whole life, in autocommit: it LISTENs on job_events and
reads the job's status and events on that same connection (each read its own transaction, so it sees every commit),
and closes it when the stream ends or the client goes away."""
import json
import time
from typing import Annotated, Callable, Literal

import anyio
import psycopg
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, StringConstraints

from .. import codes, jobs, store
from .state import JOB_ID, MAX_QUEUED, POST, St, User

router = APIRouter()

KEEP_ALIVE = 15           # seconds between keep-alive comments on an event stream
POLL_EVERY = 5            # seconds between status reads without a NOTIFY (fail and reap send none)
WAIT_SLICE = 1.0          # seconds a stream blocks at most, so a client gone away is noticed soon


class BriefJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["brief"]
    goal: StrictStr
    minutes: StrictInt
    preset: StrictStr
    today: Annotated[StrictStr, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]


@router.post("/api/jobs", status_code=202, **POST)
def post_job(st: St, uk: User, body: Annotated[BriefJob, Body()]):
    args = {"goal": body.goal, "minutes": body.minutes, "preset": body.preset,
            "today": body.today}
    with st.connection() as conn:
        try:
            # the user's row, locked, serialises this count against the user's other posts
            conn.execute("select 1 from users where id = %s for update", (uk.user_id,))
            queued = conn.execute("select count(*) from jobs where user_id = %s and "
                                  "state = 'queued'", (uk.user_id,)).fetchone()[0]
        except Exception:
            conn.rollback()
            raise
        if queued >= MAX_QUEUED:
            conn.rollback()
            raise HTTPException(429, "too many jobs waiting")
        job_id = jobs.enqueue(conn, uk, body.kind, args)   # commits, releasing the lock
    return {"id": job_id, "job_id": job_id}   # job_id as every other route names it; id kept for older pages


@router.post("/api/balances", status_code=202, **POST)
def post_balances(st: St, uk: User):
    """Ask what's left on each keyed voice service's account: a worker job (only the worker opens a key),
    read with GET /api/jobs/{id}. One at a time: a check already waiting or running is returned as it is."""
    with st.connection() as conn:
        try:
            conn.execute("select 1 from users where id = %s for update", (uk.user_id,))
            row = conn.execute("select id from jobs where user_id = %s and kind = 'balances' and "
                               "state in ('queued', 'running') order by id desc limit 1",
                               (uk.user_id,)).fetchone()
            if row is not None:
                conn.rollback()
                return {"id": row[0]}
            queued = conn.execute("select count(*) from jobs where user_id = %s and "
                                  "state = 'queued'", (uk.user_id,)).fetchone()[0]
        except Exception:
            conn.rollback()
            raise
        if queued >= MAX_QUEUED:
            conn.rollback()
            raise HTTPException(429, "too many jobs waiting")
        job_id = jobs.enqueue(conn, uk, "balances", {})   # commits, releasing the lock
    return {"id": job_id}


@router.get("/api/jobs/{job_id}")
def get_job(st: St, uk: User, job_id: Annotated[int, JOB_ID]):
    with st.connection() as conn:
        try:
            status = jobs.status(conn, uk, job_id)
            res = jobs.result(conn, uk, job_id)
        except LookupError:
            raise HTTPException(404, "no such job") from None
        finally:
            conn.rollback()
    return {"id": job_id, "state": status["state"], "error": status["error"], "code": codes.of_status(status),
            "result": res}


@router.get("/api/jobs/{job_id}/events")
def job_events(st: St, request: Request, uk: User, job_id: Annotated[int, JOB_ID]):
    with st.connection() as conn:
        try:
            jobs.status(conn, uk, job_id)
        except LookupError:
            raise HTTPException(404, "no such job") from None
        finally:
            conn.rollback()
    try:
        after = max(0, int(request.headers.get("last-event-id", "0")))
    except ValueError:
        after = 0
    return StreamingResponse(_stream(st.open_stream, uk, job_id, after),
                             media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


async def _stream(open_conn: Callable[[], psycopg.Connection], uk: store.UserKey, job_id: int,
                  after: int):
    """The job's events after `after`, then a `state` event once it is done or failed.

    LISTEN comes before the first read, so an event committed between them still wakes us. Each
    round reads the status first and the events after it: complete() writes its events in the
    same transaction that marks the job done, so a done status means every event is readable."""
    run = anyio.to_thread.run_sync
    conn = await run(open_conn)
    try:
        conn.autocommit = True
        await run(lambda: conn.execute("listen job_events"))
        channel = str(job_id)

        def read():
            st = jobs.status(conn, uk, job_id)
            return st, jobs.events(conn, uk, job_id, after)

        def wait(seconds: float) -> bool:
            return any(n.payload == channel
                       for n in conn.notifies(timeout=seconds, stop_after=1))

        check, last_read, last_sent = True, 0.0, time.monotonic()
        while True:
            if check:
                try:
                    st, evs = await run(read)
                except LookupError:
                    return
                last_read = time.monotonic()
                for event_id, body in evs:
                    after = event_id
                    last_sent = time.monotonic()
                    yield f"id: {event_id}\ndata: {json.dumps(body)}\n\n"
                if st["state"] in ("done", "failed"):
                    end = {"state": st["state"], "error": st["error"], "code": codes.of_status(st)}
                    yield f"event: state\ndata: {json.dumps(end)}\n\n"
                    return
            notified = await run(wait, min(WAIT_SLICE, POLL_EVERY, KEEP_ALIVE))
            now = time.monotonic()
            check = notified or now - last_read >= POLL_EVERY
            if now - last_sent >= KEEP_ALIVE:
                last_sent = now
                yield ": keep-alive\n\n"
    finally:
        conn.close()
