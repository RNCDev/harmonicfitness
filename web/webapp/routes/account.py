"""The listener's account: who they are, the job options, a coach's sample, the first screen, their level, and
deleting the account."""
import datetime
import json
import re
from pathlib import Path
from typing import Annotated, Literal

import anyio
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, StrictStr, StringConstraints

from .. import APP_NAME, auth, clerk, keystore, level, providers, start, store, workouts
from .logs import workout_call
from .state import COOKIE, POST, St, User, confirming, is_admin, read, tx

router = APIRouter()
late = APIRouter()   # included after the Logs routes, where these always were


class Confirm(BaseModel):
    """What proves it's them: the password, or, for an account that signs in through Clerk, a fresh Clerk session
    token from this browser."""
    model_config = ConfigDict(extra="forbid")
    password: Annotated[StrictStr, StringConstraints(min_length=1, max_length=1024)] | None = None
    token: Annotated[StrictStr, StringConstraints(min_length=1, max_length=clerk.TOKEN_MAX)] | None = None


class LevelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: Literal["novice", "experienced", "advanced"]


def stock_sample_url(engine_root: str, slug: str) -> str | None:
    """A stock coach's sample on the media bucket, from coaches/samples.json (tools/media.py writes it), or None.
    Only an https:// address counts."""
    try:
        data = json.loads(Path(engine_root, "coaches", "samples.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    url = str(data.get("url") or "").rstrip("/")
    if slug not in (data.get("samples") or {}) or not url.startswith("https://"):
        return None
    return f"{url}/coaches/{slug}/sample.mp3"


@router.get("/api/me")
def me(st: St, uk: User):
    with read(st) as conn:
        name, pw, linked, have = conn.execute(
            "select username, password_hash is not null, clerk_id is not null, minutes from users "
            "where id = %s", (uk.user_id,)).fetchone()
        sky = keystore.sky(conn, uk)
        auto = keystore.auto_record(conn, uk)
    # clerk: sign-in goes through Clerk here (no password to set or ask for); hosted: the site's own key writes and
    # speaks, paid for in minutes (no keys to add), and `minutes` is the balance
    return {"app_name": APP_NAME, "username": name, "has_password": pw, "version": st.version, "sky": sky,
            "auto_record": auto, "clerk": st.clerk is not None, "clerk_linked": linked,
            "hosted": st.settings.hosted, "minutes": have if st.settings.hosted else None,
            "admin": is_admin(st, uk)}


coach_slug = re.compile(r"coach-[a-z0-9-]{1,60}")


@router.get("/api/coaches/{slug}/sample.mp3")
def coach_sample(st: St, uk: User, slug: str, request: Request):
    """A coach's sample for the gallery: the listener's own copy (me/coaches/<slug>/sample.mp3, kept with
    their files), which wins as their coach does, else a stock coach's from the media bucket (a redirect to
    the address coaches/samples.json lists), which plays before the listener has a key."""
    if not coach_slug.fullmatch(slug):
        raise HTTPException(404, "no such coach")
    with read(st) as conn:
        own = store.read_one(conn, uk, f"coaches/{slug}/sample.mp3")
    # no-cache: the browser asks again each time (a 304 by its ETag when unchanged), so a re-recorded sample
    # is heard at once, never a day-old copy
    if own is not None:
        version, body = own
        tag = f'"own-{version:x}-{len(body):x}"'
    else:
        path = Path(st.settings.engine_root, "coaches", slug, "sample.mp3")
        if not path.is_file():   # a stock coach's sample is on the media bucket, listed in coaches/samples.json
            url = stock_sample_url(st.settings.engine_root, slug)
            if url is None:
                raise HTTPException(404, "no sample for this coach")
            return RedirectResponse(url, status_code=307, headers={"Cache-Control": "public, max-age=3600"})
        info = path.stat()
        tag = f'"{info.st_mtime_ns:x}-{info.st_size:x}"'
    headers = {"Cache-Control": "private, no-cache", "ETag": tag}
    if tag in (request.headers.get("if-none-match") or ""):
        return Response(status_code=304, headers=headers)
    if own is not None:
        return Response(own[1], media_type="audio/mpeg", headers=headers)
    return FileResponse(path, media_type="audio/mpeg", headers=headers)


@router.get("/api/start")
async def start_screen(st: St, uk: User):
    """What the first screen's sentence is filled in with: the web coaches (current first), the kits,
    the usual length, today's limits, a suggestion from the log, and whether setup is still quick. Kept
    per listener until a file, a key, the chosen coach or the day changes (start.cached)."""
    def work() -> dict:
        with read(st) as conn:
            mark = store.fingerprint(conn, uk)
            have = keystore.listing(conn, uk)
            chosen = keystore.coach(conn, uk)
            # as in GET /api/keys: a model key stored under a provider's own id voices its shared service too
            keyed = {s for s in st.services
                     if s in have or any(p in have for p, t in providers.SHARED_KEY.items() if t == s)}
            paid = st.settings.hosted   # the site's own coaches, whatever keys were stored before
            made_from = (mark, frozenset(keyed), chosen, datetime.date.today().isoformat(), paid)
            kept = start.cached(uk.user_id, made_from)
            if kept is not None:
                return kept
            files = {p: body for p, (_, body) in store.read_all(conn, uk).items()}
        answer = start.gather(st.settings.engine_root, files, keyed, chosen, paid)
        start.remember(uk.user_id, made_from, answer)
        return answer
    return await anyio.to_thread.run_sync(work)


@late.get("/api/level")
async def get_level(st: St, uk: User):
    """The listener's level (novice when none is set) and the three to choose from, each as they'd say it.
    Only the profile's files are read, not all of them: Settings asks for this on every page load."""
    def work() -> dict:
        with read(st) as conn:
            files = {p: got[1] for p in level.parts(st.settings.engine_root)
                     if (got := store.read_one(conn, uk, p)) is not None}
        return level.current(st.settings.engine_root, files)
    return await anyio.to_thread.run_sync(work)

@late.put("/api/level", status_code=204, **POST)
async def put_level(st: St, uk: User, body: Annotated[LevelBody, Body()]):
    """Set the level in the listener's profile, every other line kept."""
    await anyio.to_thread.run_sync(lambda: workout_call(st, uk, level.choose, body.level, change=True))
    return Response(status_code=204)

@late.post("/api/account/delete", status_code=204, **POST)
def delete_account(st: St, uk: User, body: Annotated[Confirm, Body()]):
    """Delete the account and everything it holds: files, keys, chats, audio, kept clips, jobs, and any minutes
    left. Needs the password, or, where sign-in goes through Clerk, a fresh Clerk session token for this account
    (its Clerk user is deleted too); nothing can bring it back."""
    key = confirming(st, uk)
    with tx(st) as conn:
        row = conn.execute("select password_hash, clerk_id from users where id = %s for update",
                           (uk.user_id,)).fetchone()
        if row is not None and st.clerk is not None and row[1]:
            try:
                proven = body.token is not None and st.clerk.verify(body.token) == row[1]
            except clerk.Refused:
                proven = False
            except clerk.Unavailable:
                raise HTTPException(503, "Sign-in isn't answering just now. Try again in a minute.") from None
            if not proven:
                st.throttles["confirms"].hit(key)
                raise HTTPException(400, "That didn't confirm it's you. Sign in again, then try once more.")
        elif row is None or not auth.verify_password(body.password or "", row[0]):
            st.throttles["confirms"].hit(key)
            raise HTTPException(400, "That password isn't right.")
        conn.execute("delete from users where id = %s", (uk.user_id,))
        if st.clerk is not None and row[1]:
            try:    # before the commit: if Clerk can't, nothing here is deleted either, and they can try again
                st.clerk.delete(row[1])
            except clerk.Unavailable:
                raise HTTPException(503, "The account couldn't be deleted just now. Try again in a minute.") from None
    start.forget(uk.user_id)
    workouts.forget(uk.user_id)
    r = Response(status_code=204)
    r.delete_cookie(COOKIE, path="/")
    return r
