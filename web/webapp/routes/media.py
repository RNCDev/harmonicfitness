"""Kept MP3s: the listener's own, and the private podcast feed (its link, its RSS and its episodes), which needs no
session: a podcast app can't sign in, so its unguessable token is the key."""
import datetime
import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.responses import Response, StreamingResponse

from .. import feed, media, store
from .state import POST, AppState, St, User, read, tx

router = APIRouter()


def _byte_range(header: str | None, size: int):
    """(start, end) inclusive for one "bytes=a-b" range, () when it can't be met, None for the whole body."""
    if not header or not header.startswith("bytes=") or "," in header:
        return None
    a, _, b = header[6:].strip().partition("-")
    try:
        if a == "":
            n = int(b)
            if n <= 0:
                return ()
            start, end = max(0, size - n), size - 1
        else:
            start = int(a)
            end = int(b) if b else size - 1
    except ValueError:
        return None
    end = min(end, size - 1)
    return () if start > end or start >= size else (start, end)


def mp3(st: AppState, request: Request, uk: store.UserKey, mid: str, found, download: bool = False) -> Response:
    """A kept MP3 (media.describe's), inline for a player or as a download, honouring a byte range (Safari's player
    and podcast apps ask for them). The browser may keep it until it expires, or a day for a workout's (private:
    never a shared cache). Streamed a chunk at a time, each read on a pooled connection of its own, so a slow
    player never holds one; a HEAD gets the headers alone."""
    name, size, expires, chunk = found
    left = 86_400 if expires is None else \
        max(0, int((expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()))
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "workout"
    headers = {"Cache-Control": f"private, max-age={left}", "Accept-Ranges": "bytes",
               "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{safe}.mp3"'}
    part = _byte_range(request.headers.get("range"), size)
    if part == ():
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    status, (start, end) = (200, (0, size - 1)) if part is None else (206, part)
    if status == 206:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    headers["Content-Length"] = str(end - start + 1 if size else 0)
    if request.method == "HEAD" or not size:
        return Response(status_code=status, media_type="audio/mpeg", headers=headers)

    def pieces():
        at = start
        while at <= end:
            to = min(end, (at // chunk + 1) * chunk - 1)
            with read(st) as conn:
                data = media.read_range(conn, uk, mid, at, to)
            if not data:   # replaced by a newer workout meanwhile: the answer ends short
                return
            yield data
            at += len(data)
    return StreamingResponse(pieces(), status_code=status, media_type="audio/mpeg", headers=headers)


@router.get("/api/media/{mid}")
def get_media(st: St, uk: User, request: Request, mid: Annotated[str, PathParam(max_length=40)],
              download: bool = False):
    """An MP3, the user's own, while it's kept (a workout's until three newer ones replace it, any other for
    24 hours): inline for the player, or as a download."""
    with read(st) as conn:
        found = media.describe(conn, uk, mid)
    if found is None:
        raise HTTPException(404, "That audio is no longer kept, or isn't yours.")
    return mp3(st, request, uk, mid, found, download)


# ---- the private podcast feed -----------------------------------------------------------

@router.get("/api/feed")
def get_feed(st: St, uk: User):
    """The listener's private podcast feed link, or null while it's off."""
    with read(st) as conn:
        t = feed.token(conn, uk)
    return {"url": feed.url(st.settings.base_url, t) if t else None}


@router.post("/api/feed", **POST)
def make_feed(st: St, uk: User):
    """Turn the feed on, or give it a new link: the old one stops working."""
    with tx(st) as conn:
        t = feed.make(conn, uk)
    return {"url": feed.url(st.settings.base_url, t)}


@router.delete("/api/feed", status_code=204, **POST)
def stop_feed(st: St, uk: User):
    """Turn the feed off: its link stops working."""
    with tx(st) as conn:
        feed.stop(conn, uk)
    return Response(status_code=204)


feed_token = re.compile(feed.TOKEN)
gone_feed = "No such feed: it may have been turned off or given a new link in Settings."


def feed_user(st: AppState, conn, token: str) -> store.UserKey | None:
    """The feed's owner, by its token alone (a podcast app can't sign in), or None."""
    if not feed_token.fullmatch(token):
        return None
    user_id = feed.user_for(conn, token)
    return store.user_key(conn, st.settings, user_id) if user_id is not None else None


@router.api_route("/feed/{token}.xml", methods=["GET", "HEAD"], include_in_schema=False)
def podcast_feed(st: St, token: Annotated[str, PathParam(max_length=64)]):
    """The feed's RSS: the workout MP3s the site keeps, newest first."""
    with read(st) as conn:
        uk = feed_user(st, conn, token)
        items = feed.episodes(conn, uk) if uk else None
    if items is None:
        raise HTTPException(404, gone_feed)
    return Response(feed.rss(st.settings.base_url, token, items), media_type="application/rss+xml; charset=utf-8",
                    headers={"Cache-Control": "private, no-cache"})


@router.api_route("/feed/{token}/{mid}.mp3", methods=["GET", "HEAD"], include_in_schema=False)
def podcast_episode(st: St, request: Request, token: Annotated[str, PathParam(max_length=64)],
                    mid: Annotated[str, PathParam(max_length=40)]):
    """One of the feed's workouts, while the site keeps it."""
    with read(st) as conn:
        uk = feed_user(st, conn, token)
        found = media.describe(conn, uk, mid) if uk else None
    # a workout's only: a coach's sample in the chat isn't in the feed
    if found is None or found[2] is not None:
        raise HTTPException(404, "That workout is no longer kept, or the feed's link has changed.")
    return mp3(st, request, uk, mid, found)
