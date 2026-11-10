"""The Logs page: the logged workouts, a script, feedback (and the enrich job it starts), a rating and a delete."""
import datetime
from typing import Annotated, Literal

import anyio
from fastapi import APIRouter, Body, HTTPException
from fastapi import Path as PathParam
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .. import jobs, keystore, media, providers, store, workouts
from .state import MAX_QUEUED, POST, AppState, St, User, read, tx

router = APIRouter()


class FeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: Annotated[str, Field(min_length=1, max_length=1000)]


class RatingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Literal["positive", "neutral", "negative", "none"]


def workout_call(st: AppState, uk: store.UserKey, call, *args, change: bool = False):
    """Run a Logs-page call on the listener's files; a change is written back against the versions read
    (a conflict, from a turn saving at the same moment, is a 409 to try again)."""
    with read(st) as conn:
        held = store.read_all(conn, uk)
    files = {p: body for p, (_, body) in held.items()}
    try:
        out = call(st.settings.engine_root, files, *args)
    except workouts.Refused as e:
        raise HTTPException({"not_found": 404, "failed": 502}.get(e.kind, 400), str(e)) from None
    if not change:
        return out
    with tx(st) as conn:
        if store.write_back(conn, uk, out, {p: v for p, (v, _) in held.items()}):
            raise HTTPException(409, "Your files changed at the same moment. Try again.")
    return None


@router.get("/api/workouts")
async def list_workouts(st: St, uk: User):
    """The logged workouts, newest first: date, length, kit, coach, format, movements, topics, build id,
    feedback, rating, whether a script is kept, and its MP3 while the site keeps it (`audio`: the three newest)."""
    rows = await anyio.to_thread.run_sync(lambda: workout_call(st, uk, workouts.listing))

    def kept() -> dict[str, dict]:
        with read(st) as conn:
            return media.by_build(conn, uk)
    audio = await anyio.to_thread.run_sync(kept)
    for row in rows:   # the MP3 still kept (the newest three workouts') for a workout, to play or download from Logs
        if isinstance(row, dict) and row.get("build_id") in audio:
            row["audio"] = audio[row["build_id"]]
    return {"workouts": rows}


@router.get("/api/workouts/{ref}/script")
async def workout_script(st: St, uk: User, ref: Annotated[str, PathParam(max_length=40)]):
    text = await anyio.to_thread.run_sync(lambda: workout_call(st, uk, workouts.script, ref))
    return {"script": text}


@router.post("/api/workouts/{ref}/feedback", status_code=202, **POST)
async def workout_feedback(st: St, uk: User, ref: Annotated[str, PathParam(max_length=40)],
                           body: Annotated[FeedbackBody, Body()]):
    """The feedback line, saved; then an enrich job, in its own lane, works out what it teaches (interests the
    next workouts lean on) on the listener's writer key. {"job_id"}: poll /api/jobs/{id} for its summary."""
    await anyio.to_thread.run_sync(lambda: workout_call(st, uk, workouts.add_feedback, ref, body.text,
                                                         change=True))

    def queue() -> int | None:
        with tx(st) as conn:   # without a writer key there's no one to work it out: nothing queued
            if providers.pick(st.settings.providers, keystore.listing(conn, uk), keystore.writer(conn, uk)) is None:
                return None
            # within the queued-jobs cap, as every other job is (0.76.0): the feedback itself is saved either way
            conn.execute("select 1 from users where id = %s for update", (uk.user_id,))
            if conn.execute("select count(*) from jobs where user_id = %s and state = 'queued' and kind = 'enrich'",
                            (uk.user_id,)).fetchone()[0] >= MAX_QUEUED:
                return None
            return jobs.add(conn, uk, "enrich", {"ref": workouts.check_ref(ref), "text": body.text,
                                                 "today": datetime.date.today().isoformat()})
    return {"job_id": await anyio.to_thread.run_sync(queue)}


@router.put("/api/workouts/{ref}/rating", status_code=204, **POST)
async def workout_rating(st: St, uk: User, ref: Annotated[str, PathParam(max_length=40)],
                         body: Annotated[RatingBody, Body()]):
    await anyio.to_thread.run_sync(lambda: workout_call(st, uk, workouts.rate, ref, body.rating, change=True))
    return Response(status_code=204)


@router.delete("/api/workouts/{ref}", status_code=204, **POST)
async def workout_delete(st: St, uk: User, ref: Annotated[str, PathParam(max_length=40)]):
    await anyio.to_thread.run_sync(lambda: workout_call(st, uk, workouts.delete, ref, change=True))
    return Response(status_code=204)
