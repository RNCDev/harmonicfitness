"""Settings: the coach, recording without asking and the sky."""
import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body
from fastapi.responses import Response
from pydantic import AfterValidator, BaseModel, ConfigDict, StrictBool, StrictStr, StringConstraints

from .. import prefs
from .state import POST, Day, St, User, tx

router = APIRouter()


class SkyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sky: Literal["flow", "field", "waves", "bloom", "woven", "garden"]


class AutoRecordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    on: StrictBool


class CoachBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # a coach's folder name: one from `coaches list`, or a folder brought in from a ZIP; never a path
    slug: Annotated[StrictStr, StringConstraints(min_length=1, max_length=128, pattern=r"^[^/\\\x00-\x1f]+$")]
    day: Annotated[Day, AfterValidator(lambda d: datetime.date.fromisoformat(d).isoformat())]   # the listener's own day, as the log's are


@router.put("/api/coach", status_code=204, **POST)
def put_coach(st: St, uk: User, body: Annotated[CoachBody, Body()]):
    """The coach chosen on the web app (Settings or the first screen's sentence): the first screen's coach
    from then on, while it can speak and until a workout logged on a later day used another."""
    with tx(st) as conn:
        prefs.set_coach(conn, uk, body.slug, body.day)
    return Response(status_code=204)


@router.put("/api/auto-record", status_code=204, **POST)
def put_auto_record(st: St, uk: User, body: Annotated[AutoRecordBody, Body()]):
    """Record without asking: a checked, priced script records at once, within today's allowance."""
    with tx(st) as conn:
        prefs.set_auto_record(conn, uk, body.on)
    return Response(status_code=204)


@router.put("/api/sky", status_code=204, **POST)
def put_sky(st: St, uk: User, body: Annotated[SkyBody, Body()]):
    """The web app's animated background: "flow" or "field"."""
    with tx(st) as conn:
        prefs.set_sky(conn, uk, body.sky)
    return Response(status_code=204)
