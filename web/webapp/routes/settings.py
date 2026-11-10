"""Settings: the keys (listed, saved, deleted), the writer, the coach, recording without asking and the sky.
A key is sealed as it's saved and never opened here: only the worker opens one."""
import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from pydantic import AfterValidator, BaseModel, ConfigDict, StrictBool, StrictStr, StringConstraints

from .. import enginelib, keystore, providers
from .state import POST, AppState, Day, St, User, read, tx

router = APIRouter()

KEY_MIN = 16     # shorter values escape engine.scrub (8+ only) and are never real keys
KEY_MAX = 1024


class KeyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Annotated[StrictStr, StringConstraints(max_length=KEY_MAX)]


class WriterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: Annotated[StrictStr, StringConstraints(max_length=64)]


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


@router.get("/api/keys")
def list_keys(st: St, uk: User):
    with read(st) as conn:
        have = keystore.listing(conn, uk)
        chosen = keystore.writer(conn, uk)
    # the writer shown: the one the listener chose (its key may still be missing), else the one that would write
    writes = chosen if chosen in st.settings.providers else providers.pick(st.settings.providers, have, None)
    writer_service = providers.key_service(writes) if writes else None
    # A provider sharing a voice service's key (Gemini) is listed under that service's id, so the
    # page shows one row for one key.
    # billing_page: where the account's balance is seen; reports: whether a balance check can say it (a
    # shared key's model row says what its voice service says)
    def billing(service: str, fallback: str) -> tuple[str, bool]:
        v = st.services.get(service)
        return (v["billing_page"], v["reports"]) if v else (fallback, False)
    rows = [(providers.key_service(p), providers.PROVIDERS[p].name, providers.PROVIDERS[p].key_page,
             *billing(providers.key_service(p), providers.PROVIDERS[p].billing_page), "model",
             providers.stored_key(have, p)) for p in st.settings.providers]
    rows += [(s, v["name"], v["key_page"], v["billing_page"], v["reports"], "voice",
              have.get(s) or next((have.get(p) for p, t in providers.SHARED_KEY.items() if t == s), None))
             for s, v in st.services.items()]
    return [{"service": s, "name": n, "key_page": page, "billing_page": bill, "reports": reports, "kind": kind,
             "set": at is not None, "updated_at": at.isoformat() if at is not None else None,
             **({"writer": s == writer_service} if kind == "model" else {})}
            for s, n, page, bill, reports, kind, at in rows]


@router.put("/api/writer", status_code=204, **POST)
def put_writer(st: St, uk: User, body: Annotated[WriterBody, Body()]):
    """Which offered language model writes the listener's workouts, by the id its key is listed under."""
    provider = providers.provider_of(body.service)
    if provider not in st.settings.providers:
        raise HTTPException(404, "no such provider")
    with tx(st) as conn:
        keystore.set_writer(conn, uk, provider)
    return Response(status_code=204)


@router.put("/api/coach", status_code=204, **POST)
def put_coach(st: St, uk: User, body: Annotated[CoachBody, Body()]):
    """The coach chosen on the web app (Settings or the first screen's sentence): the first screen's coach
    from then on, while it can speak and until a workout logged on a later day used another."""
    with tx(st) as conn:
        keystore.set_coach(conn, uk, body.slug, body.day)
    return Response(status_code=204)


@router.put("/api/auto-record", status_code=204, **POST)
def put_auto_record(st: St, uk: User, body: Annotated[AutoRecordBody, Body()]):
    """Record without asking: a checked, priced script records at once, within today's allowance."""
    with tx(st) as conn:
        keystore.set_auto_record(conn, uk, body.on)
    return Response(status_code=204)


@router.put("/api/sky", status_code=204, **POST)
def put_sky(st: St, uk: User, body: Annotated[SkyBody, Body()]):
    """The web app's animated background: "flow" or "field"."""
    with tx(st) as conn:
        keystore.set_sky(conn, uk, body.sky)
    return Response(status_code=204)


def known(st: AppState, service: str) -> dict:
    if service in st.settings.providers and service not in providers.SHARED_KEY:
        spec = providers.PROVIDERS[service]
        return {"name": spec.name, "key_var": f"{service.upper()}_API_KEY"}
    if service not in st.services:
        raise HTTPException(404, "no such service")
    return st.services[service]


@router.put("/api/keys/{service}", status_code=204, **POST)
def put_key(st: St, uk: User, service: str, body: Annotated[KeyBody, Body()]):
    info = known(st, service)
    value = enginelib.clean_key(st.settings.engine_root, info["key_var"], body.key)
    if not value or len(value) < KEY_MIN:
        raise HTTPException(400, f"That doesn't look like a {info['name']} key: it has a space, "
                                 "a line break or a symbol in it. Paste it again.")
    with tx(st) as conn:
        keystore.put(conn, uk, service, value)
    return Response(status_code=204)


@router.delete("/api/keys/{service}", status_code=204, **POST)
def delete_key(st: St, uk: User, service: str):
    known(st, service)
    with tx(st) as conn:
        keystore.delete(conn, uk, service)
        for legacy, shared in providers.SHARED_KEY.items():   # the same key, stored before 0.25.2
            if shared == service:
                keystore.delete(conn, uk, legacy)
    return Response(status_code=204)
