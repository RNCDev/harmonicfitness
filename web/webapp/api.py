"""The web server: sign-in, the signed-in JSON API, a job's event stream and the built client.

    uvicorn webapp.api:create_app_from_env --factory --no-access-log   (run from web/)

Every route under /api but sign-in, registration and a link's redeem needs the session cookie
`wt_session` (else 401). Failed sign-ins and registrations are throttled in memory (one web
process), by username and by client address.
The private podcast feed (/feed/<token>.xml and its MP3s) needs no session: a podcast app can't sign in, so
its unguessable token is the key, and Settings can replace or turn it off.
Every POST needs an Origin (or, without one, a Referer) of HARMONICFITNESS_BASE_URL's origin (else 403).
A job or file of another user is 404, the same as one that doesn't exist. Nothing here logs a
token, a job's arguments, its events or its result.

Connections: requests borrow one from a small pool (or, in tests, open one with the injected
`connect`), never sharing one between requests. An event stream holds one connection of its own
for its whole life, in autocommit: it LISTENs on job_events and reads the job's status and events
on that same connection (each read its own transaction, so it sees every commit), and closes it
when the stream ends or the client goes away.
"""
import collections
import datetime
import html
import json
import os
import re
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Callable, Literal
from urllib.parse import parse_qs, urlsplit

import anyio
import psycopg
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, \
    RedirectResponse, Response, StreamingResponse
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, StringConstraints

from . import APP_NAME, auth, codes, config, conversations, db, engine, enginelib, feed, folder, jobs, keystore, log, \
    media, providers, level, spend, start, store, turns, workouts
from .folder import IMPORT_MAX_TOTAL, IMPORT_MAX_ZIP

COOKIE = "wt_session"
MINUTES = [10, 15, 20, 25, 30, 45]
MAX_QUEUED = 3            # queued jobs a user may have at once (a guard against a stuck button)
KEEP_ALIVE = 15           # seconds between keep-alive comments on an event stream
POLL_EVERY = 5            # seconds between status reads without a NOTIFY (fail and reap send none)
WAIT_SLICE = 1.0          # seconds a stream blocks at most, so a client gone away is noticed soon
CLIENT_DIST = Path(__file__).resolve().parent.parent / "client" / "dist"
JOB_ID = PathParam(ge=1, le=2**63 - 1)
HSTS = (b"strict-transport-security", b"max-age=31536000")


class Throttle:
    """At most `limit` hits per key in a sliding window."""

    def __init__(self, limit: int, window: float, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.hits: dict[str, collections.deque] = {}
        self.lock = threading.Lock()

    def _live(self, key: str) -> collections.deque:
        q = self.hits.setdefault(key, collections.deque())
        cutoff = self.clock() - self.window
        while q and q[0] <= cutoff:
            q.popleft()
        return q

    def full(self, key: str) -> bool:
        with self.lock:
            full = len(self._live(key)) >= self.limit
            if not self.hits[key]:
                del self.hits[key]
            return full

    def hit(self, key: str) -> None:
        with self.lock:
            if len(self.hits) >= 10_000:      # keep memory bounded: forget keys gone quiet
                for k in [k for k in self.hits if not self._live(k)]:
                    del self.hits[k]
            self._live(key).append(self.clock())


def _address(request: Request) -> str:
    """The client's address: the last X-Forwarded-For entry (the one our host's proxy added),
    else the socket's peer."""
    fwd = request.headers.get("x-forwarded-for", "")
    last = fwd.split(",")[-1].strip()
    return last or (request.client.host if request.client else "")


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def _secure(settings: config.Settings) -> bool:
    return not settings.base_url.startswith(("http://localhost", "http://127.0.0.1"))


class BriefJob(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["brief"]
    goal: StrictStr
    minutes: StrictInt
    preset: StrictStr
    today: Annotated[StrictStr, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]


Day = Annotated[StrictStr, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$")]
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


class _Headers:
    """Security headers on every response (pure ASGI, so streams aren't buffered or broken)."""

    BASE = ((b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"same-origin"), (b"x-robots-tag", b"noindex"))

    def __init__(self, app, secure: bool = False):
        self.app, self.secure = app, secure

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        api = scope.get("path", "").startswith("/api/")

        async def sending(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                have = {k.lower() for k, _ in headers}
                # HSTS only where the site is served over https: never on a computer's own http://localhost
                extra = (list(self.BASE) + ([HSTS] if self.secure else [])
                         + ([(b"cache-control", b"no-store")] if api else []))
                headers += [(k, v) for k, v in extra if k not in have]
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, sending)


# Every refusal's body (0.76.0): `detail` as before (the words, or a validation error's list), and `error` beside it,
# the same shape on every route: a code the page can branch on, the words, and the form's box it's about. The page
# reads `code` and `field` at the top too, as it always has.
ERROR_CODES = {400: "invalid", 401: "not_signed_in", 403: "forbidden", 404: "not_found", 405: "not_allowed",
               409: "conflict", 410: "gone", 413: "too_large", 416: "bad_range", 422: "invalid", 429: "too_many",
               500: "internal"}
INTERNAL = "Something went wrong on the site's side. Try again in a minute."


def error_body(status: int, detail, code: str | None = None, field: str | None = None) -> dict:
    """A refusal's body: {"detail", "error": {"code", "message", "field"}}, with `code` and `field` at the top when
    given."""
    message = detail if isinstance(detail, str) else "That request isn't right."
    body = {"detail": detail, "error": {"code": code or ERROR_CODES.get(status, "error"), "message": message,
                                        "field": field}}
    if code:
        body["code"] = code
    if field:
        body["field"] = field
    return body


class _Errors:
    """An error no route caught is a 500 in the usual shape, logged by type and frames only (log.failure): never its
    message, which may hold a listener's words, never a traceback in the response (pure ASGI, so a stream is untouched).
    One raised after a response began is logged and the response ends."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = False

        async def sending(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)
        try:
            await self.app(scope, receive, sending)
        except Exception as e:  # noqa: BLE001 - the one place an unexpected error ends: logged, then a 500
            route = scope.get("route")
            log.failure(f"web {scope.get('method', '')} {getattr(route, 'path', 'a route')}", e)
            if started:
                return
            body = json.dumps(error_body(500, INTERNAL)).encode()
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})


class _BodyLimit:
    """No request body over its route's limit reaches the app, or the server's memory (pure ASGI, so a stream is
    untouched): a declared Content-Length over it is refused at once, and a body sent in chunks is read only up to
    it, then 413. A body within the limit is handed on as it came. Requests without a body (GET, HEAD, a stream)
    pass straight through."""

    DEFAULT = 64_000
    TOO_LARGE = "That request is too large."
    # path -> (bytes, the refusal's words); everything else takes DEFAULT
    LIMITS = {
        "/api/import": (IMPORT_MAX_ZIP, f"That ZIP is over {IMPORT_MAX_ZIP // 1_000_000} MB."),
        # base64 of IMPORT_MAX_TOTAL, with the JSON around it
        "/api/sync/write": (IMPORT_MAX_TOTAL * 4 // 3 + 2_000_000,
                            f"Over {IMPORT_MAX_TOTAL // 1_000_000} MB in one sync; send it in parts."),
        "/api/sync/read": (512_000, TOO_LARGE),   # up to 500 paths of 400 characters
    }

    def __init__(self, app):
        self.app = app

    @staticmethod
    async def _refuse(send, words: str) -> None:
        body = json.dumps(error_body(413, words)).encode()
        await send({"type": "http.response.start", "status": 413,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        limit, words = self.LIMITS.get(scope.get("path", ""), (self.DEFAULT, self.TOO_LARGE))
        declared = dict(scope.get("headers") or []).get(b"content-length")
        try:
            if declared is not None and int(declared) > limit:
                return await self._refuse(send, words)
        except ValueError:
            return await self._refuse(send, words)
        parts, size = [], 0
        while True:
            message = await receive()
            if message["type"] != "http.request":   # the client went away: let the app see it
                parts = None
                break
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                return await self._refuse(send, words)
            parts.append(chunk)
            if not message.get("more_body"):
                break
        if parts is None:
            return await self.app(scope, receive, send)
        body, sent = b"".join(parts), False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


def build_version(engine_root: str, env=os.environ) -> str:
    """What the page shows, so a deploy is visible: the engine's VERSION and the deployed commit
    (HARMONICFITNESS_COMMIT, baked in at build from GIT_COMMIT_SHA), as "0.20.0 (75da105)"."""
    try:
        v = Path(engine_root, "VERSION").read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        v = "unknown"
    sha = (env.get("HARMONICFITNESS_COMMIT") or "").strip()[:7]
    return f"{v} ({sha})" if sha else v


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


def create_app(settings: config.Settings, connect: Callable[[], psycopg.Connection] | None = None,
               client_dist: str | os.PathLike | None = None) -> FastAPI:
    """The app. `connect` (tests) opens a connection; without it requests use a pool of
    settings.database_url and an event stream opens its own connection to it."""
    goals, presets = enginelib.lists(settings.engine_root)
    options = {"minutes": list(MINUTES), "goals": sorted(goals), "presets": sorted(presets)}
    services = enginelib.services(settings.engine_root)
    version = build_version(settings.engine_root)
    enginelib.keys(settings.engine_root)    # a broken import fails at startup
    dist = Path(client_dist) if client_dist is not None else CLIENT_DIST
    origin = _origin(settings.base_url)
    pool = None
    if connect is None:
        from psycopg_pool import ConnectionPool
        pool = ConnectionPool(settings.database_url, min_size=1, max_size=10, open=False,
                              check=ConnectionPool.check_connection)
        open_stream = lambda: psycopg.connect(settings.database_url)  # noqa: E731
    else:
        open_stream = connect

    @contextmanager
    def connection():
        if pool is not None:
            with pool.connection() as conn:
                yield conn
            return
        conn = connect()
        try:
            yield conn
        finally:
            conn.close()

    @asynccontextmanager
    async def lifespan(_app):
        if pool is not None:
            pool.open()
        try:
            yield
        finally:
            if pool is not None:
                pool.close()

    app = FastAPI(title=APP_NAME, lifespan=lifespan, docs_url=None, redoc_url=None,
                  openapi_url=None)
    app.add_middleware(_BodyLimit)
    app.add_middleware(_Errors)
    app.add_middleware(_Headers, secure=_secure(settings))   # added last, so it runs first: a 413 or 500 gets them too

    @app.exception_handler(RequestValidationError)
    def invalid(_request: Request, e: RequestValidationError):
        """422 without pydantic's `input` (and `ctx`), which would echo a key or a password."""
        errors = [{k: v for k, v in err.items() if k not in ("input", "ctx")} for err in e.errors()]
        return JSONResponse(error_body(422, errors), 422)

    @app.exception_handler(StarletteHTTPException)
    def refused(_request: Request, e: StarletteHTTPException):
        """Every HTTPException in the one shape (error_body)."""
        return JSONResponse(error_body(e.status_code, e.detail), e.status_code, headers=getattr(e, "headers", None))

    # ---- dependencies ---------------------------------------------------------------------

    from .routes import account, auth as authroutes, files, logs, state as routestate
    st = routestate.AppState(
        settings=settings, connection=connection, open_stream=open_stream, options=options, services=services,
        version=version, dist=dist, origin=origin,
        throttles={"login_name": Throttle(*authroutes.LOGIN_PER_NAME),
                   "login_addr": Throttle(*authroutes.LOGIN_PER_ADDRESS),
                   "reg_addr": Throttle(*authroutes.REGISTER_PER_ADDRESS),
                   "reg_all": Throttle(*authroutes.REGISTER_ALL),
                   "confirms": Throttle(*authroutes.CONFIRM_PER_USER)})
    app.state.hf = st
    User = routestate.User
    post = routestate.POST


    @app.get("/healthz")
    def healthz():
        """For the host's health check: no session, no database."""
        return {"ok": True, "version": version}

    app.include_router(authroutes.router)


    # ---- the signed-in API ------------------------------------------------------------------

    app.include_router(account.router)


    app.include_router(files.router)
    app.include_router(logs.router)
    app.include_router(account.late)   # after the Logs routes, where these were


    def mp3(request: Request, found, download: bool = False) -> Response:
        """A kept MP3 (media.get's), inline for a player or as a download, honouring a byte range (Safari's player
        and podcast apps ask for them). The browser may keep it until it expires, or a day for a workout's (private:
        never a shared cache)."""
        name, body, expires = found
        left = 86_400 if expires is None else \
            max(0, int((expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()))
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "workout"
        headers = {"Cache-Control": f"private, max-age={left}", "Accept-Ranges": "bytes",
                   "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{safe}.mp3"'}
        part = _byte_range(request.headers.get("range"), len(body))
        if part is None:
            return Response(body, media_type="audio/mpeg", headers=headers)
        if part == ():
            return Response(status_code=416, headers={"Content-Range": f"bytes */{len(body)}"})
        start, end = part
        return Response(body[start:end + 1], status_code=206, media_type="audio/mpeg",
                        headers={**headers, "Content-Range": f"bytes {start}-{end}/{len(body)}"})

    @app.get("/api/media/{mid}")
    def get_media(uk: User, request: Request, mid: Annotated[str, PathParam(max_length=40)], download: bool = False):
        """An MP3, the user's own, while it's kept (a workout's until three newer ones replace it, any other for
        24 hours): inline for the player, or as a download."""
        with connection() as conn:
            try:
                found = media.get(conn, uk, mid)
            finally:
                conn.rollback()
        if found is None:
            raise HTTPException(404, "That audio is no longer kept, or isn't yours.")
        return mp3(request, found, download)

    # ---- the private podcast feed -----------------------------------------------------------

    @app.get("/api/feed")
    def get_feed(uk: User):
        """The listener's private podcast feed link, or null while it's off."""
        with connection() as conn:
            try:
                t = feed.token(conn, uk)
            finally:
                conn.rollback()
        return {"url": feed.url(settings.base_url, t) if t else None}

    @app.post("/api/feed", **post)
    def make_feed(uk: User):
        """Turn the feed on, or give it a new link: the old one stops working."""
        with connection() as conn:
            try:
                t = feed.make(conn, uk)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {"url": feed.url(settings.base_url, t)}

    @app.delete("/api/feed", status_code=204, **post)
    def stop_feed(uk: User):
        """Turn the feed off: its link stops working."""
        with connection() as conn:
            try:
                feed.stop(conn, uk)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    feed_token = re.compile(feed.TOKEN)
    gone_feed = "No such feed: it may have been turned off or given a new link in Settings."

    def feed_user(conn, token: str) -> store.UserKey | None:
        """The feed's owner, by its token alone (a podcast app can't sign in), or None."""
        if not feed_token.fullmatch(token):
            return None
        user_id = feed.user_for(conn, token)
        return store.user_key(conn, settings, user_id) if user_id is not None else None

    @app.api_route("/feed/{token}.xml", methods=["GET", "HEAD"], include_in_schema=False)
    def podcast_feed(token: Annotated[str, PathParam(max_length=64)]):
        """The feed's RSS: the workout MP3s the site keeps, newest first."""
        with connection() as conn:
            try:
                uk = feed_user(conn, token)
                items = feed.episodes(conn, uk) if uk else None
            finally:
                conn.rollback()
        if items is None:
            raise HTTPException(404, gone_feed)
        return Response(feed.rss(settings.base_url, token, items), media_type="application/rss+xml; charset=utf-8",
                        headers={"Cache-Control": "private, no-cache"})

    @app.api_route("/feed/{token}/{mid}.mp3", methods=["GET", "HEAD"], include_in_schema=False)
    def podcast_episode(request: Request, token: Annotated[str, PathParam(max_length=64)],
                        mid: Annotated[str, PathParam(max_length=40)]):
        """One of the feed's workouts, while the site keeps it."""
        with connection() as conn:
            try:
                uk = feed_user(conn, token)
                found = media.get(conn, uk, mid) if uk else None
            finally:
                conn.rollback()
        # a workout's only: a coach's sample in the chat isn't in the feed
        if found is None or found[2] is not None:
            raise HTTPException(404, "That workout is no longer kept, or the feed's link has changed.")
        return mp3(request, found)

    @app.get("/api/keys")
    def list_keys(uk: User):
        with connection() as conn:
            try:
                have = keystore.listing(conn, uk)
                chosen = keystore.writer(conn, uk)
            finally:
                conn.rollback()
        # the writer shown: the one the listener chose (its key may still be missing), else the one that would write
        writes = chosen if chosen in settings.providers else providers.pick(settings.providers, have, None)
        writer_service = providers.key_service(writes) if writes else None
        # A provider sharing a voice service's key (Gemini) is listed under that service's id, so the
        # page shows one row for one key.
        # billing_page: where the account's balance is seen; reports: whether a balance check can say it (a
        # shared key's model row says what its voice service says)
        def billing(service: str, fallback: str) -> tuple[str, bool]:
            v = services.get(service)
            return (v["billing_page"], v["reports"]) if v else (fallback, False)
        rows = [(providers.key_service(p), providers.PROVIDERS[p].name, providers.PROVIDERS[p].key_page,
                 *billing(providers.key_service(p), providers.PROVIDERS[p].billing_page), "model",
                 providers.stored_key(have, p)) for p in settings.providers]
        rows += [(s, v["name"], v["key_page"], v["billing_page"], v["reports"], "voice",
                  have.get(s) or next((have.get(p) for p, t in providers.SHARED_KEY.items() if t == s), None))
                 for s, v in services.items()]
        return [{"service": s, "name": n, "key_page": page, "billing_page": bill, "reports": reports, "kind": kind,
                 "set": at is not None, "updated_at": at.isoformat() if at is not None else None,
                 **({"writer": s == writer_service} if kind == "model" else {})}
                for s, n, page, bill, reports, kind, at in rows]

    @app.put("/api/writer", status_code=204, **post)
    def put_writer(uk: User, body: Annotated[WriterBody, Body()]):
        """Which offered language model writes the listener's workouts, by the id its key is listed under."""
        provider = providers.provider_of(body.service)
        if provider not in settings.providers:
            raise HTTPException(404, "no such provider")
        with connection() as conn:
            try:
                keystore.set_writer(conn, uk, provider)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    @app.put("/api/coach", status_code=204, **post)
    def put_coach(uk: User, body: Annotated[CoachBody, Body()]):
        """The coach chosen on the web app (Settings or the first screen's sentence): the first screen's coach
        from then on, while it can speak and until a workout logged on a later day used another."""
        with connection() as conn:
            try:
                keystore.set_coach(conn, uk, body.slug, body.day)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    @app.put("/api/auto-record", status_code=204, **post)
    def put_auto_record(uk: User, body: Annotated[AutoRecordBody, Body()]):
        """Record without asking: a checked, priced script records at once, within today's allowance."""
        with connection() as conn:
            try:
                keystore.set_auto_record(conn, uk, body.on)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    @app.put("/api/sky", status_code=204, **post)
    def put_sky(uk: User, body: Annotated[SkyBody, Body()]):
        """The web app's animated background: "flow" or "field"."""
        with connection() as conn:
            try:
                keystore.set_sky(conn, uk, body.sky)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    def known(service: str) -> dict:
        if service in settings.providers and service not in providers.SHARED_KEY:
            spec = providers.PROVIDERS[service]
            return {"name": spec.name, "key_var": f"{service.upper()}_API_KEY"}
        if service not in services:
            raise HTTPException(404, "no such service")
        return services[service]

    @app.put("/api/keys/{service}", status_code=204, **post)
    def put_key(uk: User, service: str, body: Annotated[KeyBody, Body()]):
        info = known(service)
        value = enginelib.clean_key(settings.engine_root, info["key_var"], body.key)
        if not value or len(value) < KEY_MIN:
            raise HTTPException(400, f"That doesn't look like a {info['name']} key: it has a space, "
                                     "a line break or a symbol in it. Paste it again.")
        with connection() as conn:
            try:
                keystore.put(conn, uk, service, value)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    @app.delete("/api/keys/{service}", status_code=204, **post)
    def delete_key(uk: User, service: str):
        known(service)
        with connection() as conn:
            try:
                keystore.delete(conn, uk, service)
                for legacy, shared in providers.SHARED_KEY.items():   # the same key, stored before 0.25.2
                    if shared == service:
                        keystore.delete(conn, uk, legacy)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return Response(status_code=204)

    @app.post("/api/jobs", status_code=202, **post)
    def post_job(uk: User, body: Annotated[BriefJob, Body()]):
        args = {"goal": body.goal, "minutes": body.minutes, "preset": body.preset,
                "today": body.today}
        with connection() as conn:
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

    @app.post("/api/balances", status_code=202, **post)
    def post_balances(uk: User):
        """Ask what's left on each keyed voice service's account: a worker job (only the worker opens a key),
        read with GET /api/jobs/{id}. One at a time: a check already waiting or running is returned as it is."""
        with connection() as conn:
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

    @app.get("/api/jobs/{job_id}")
    def get_job(uk: User, job_id: Annotated[int, JOB_ID]):
        with connection() as conn:
            try:
                st = jobs.status(conn, uk, job_id)
                res = jobs.result(conn, uk, job_id)
            except LookupError:
                raise HTTPException(404, "no such job") from None
            finally:
                conn.rollback()
        return {"id": job_id, "state": st["state"], "error": st["error"], "code": codes.of_status(st),
                "result": res}

    @app.get("/api/jobs/{job_id}/events")
    def job_events(request: Request, uk: User, job_id: Annotated[int, JOB_ID]):
        with connection() as conn:
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
        return StreamingResponse(_stream(open_stream, uk, job_id, after),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    # ---- conversations ----------------------------------------------------------------------

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
    def turn_transaction(uk: store.UserKey):
        """One transaction for a POST that queues a turn: the user's row locked (serialising the
        queued count against the user's other posts), 429 at the cap; commits on success."""
        with connection() as conn:
            try:
                conn.execute("select 1 from users where id = %s for update", (uk.user_id,))
                queued = conn.execute("select count(*) from jobs where user_id = %s and state = 'queued' "
                                      "and (not_before is null or not_before <= now())", (uk.user_id,)).fetchone()[0]
                if queued >= MAX_QUEUED:
                    raise HTTPException(429, "too many jobs waiting")
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

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

    @app.post("/api/conversations", status_code=202, **post)
    def start_conversation(uk: User, body: Annotated[TurnLine, Body()]):
        turn_args(0, body.line, None, body.today, body.now)
        with connection() as conn:
            try:
                have = keystore.listing(conn, uk)
                chosen = keystore.writer(conn, uk)
            finally:
                conn.rollback()
        if providers.pick(settings.providers, have, chosen) is None:
            name = providers.PROVIDERS[chosen if chosen in settings.providers else settings.providers[0]].name
            return JSONResponse(error_body(409, f"Add a key for {name} in Settings first.", code=codes.NO_KEY_CODE), 409)
        later = later_from(body.start_at)
        with turn_transaction(uk) as conn:
            cid = conversations.create(conn, uk, body.line, later)
            job_id = queue_turn(conn, uk, turn_args(cid, body.line, None, body.today, body.now))
        return {"id": cid, "job_id": job_id}

    @app.get("/api/conversations/latest")
    def latest_conversation(uk: User):
        with connection() as conn:
            try:
                c = conversations.latest(conn, uk)
                if c is not None:
                    c = conversations.heal(conn, uk, c)
                out = None if c is None else shown(conn, uk, c)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return Response(status_code=204) if out is None else out

    @app.get("/api/conversations/{cid}")
    def get_conversation(uk: User, cid: Annotated[int, JOB_ID]):
        with connection() as conn:
            try:
                c = healed(conn, uk, cid)
                out = shown(conn, uk, c)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return out

    @app.get("/api/conversations/{cid}/history")
    def conversation_history(uk: User, cid: Annotated[int, JOB_ID]):
        """The model's side of a conversation, for its owner only (`./harmonicfitness pull` saves it as
        history.json): every request and response, each tool call with its arguments and result, and their
        times. The page never shows it."""
        with connection() as conn:
            try:
                c = conversations.load(conn, uk, cid)
            except LookupError:
                raise HTTPException(404, "no such conversation") from None
            finally:
                conn.rollback()
        try:
            history = json.loads(c.history) if c.history else []
        except ValueError:
            history = []
        return {"id": c.id, "history": history}

    @app.post("/api/conversations/{cid}/record", status_code=202, **post)
    def record_offer(uk: User, cid: Annotated[int, JOB_ID], body: Annotated[TurnWhen, Body()]):
        """The listener approves the priced recording: its characters are reserved from today's allowance,
        then a turn records it, within that price."""
        args = turn_args(cid, RECORD_LINE, None, body.today, body.now, record=True)
        with turn_transaction(uk) as conn:
            c = healed(conn, uk, cid)
            if c.state not in ("idle", "failed") or not c.offer:
                raise HTTPException(409, "There's no recording waiting for you here.")
            cap = settings.daily_chars
            if not spend.reserve(conn, uk, body.today, int(c.offer.get("chars") or 0), cap):
                raise HTTPException(409, f"That's over today's allowance of {cap:,} characters of recording. "
                                         "A shorter workout fits, or try again tomorrow.")
            if not conversations.begin_turn(conn, uk, cid, RECORD_LINE, None):
                raise HTTPException(409, STILL_WORKING)
            job_id = queue_turn(conn, uk, args)
        return {"job_id": job_id}

    @app.post("/api/conversations/{cid}/schedule", status_code=202, **post)
    def schedule_later(uk: User, cid: Annotated[int, JOB_ID], body: Annotated[TurnWhen, Body()]):
        """The listener's Schedule it: the one approval for a workout at their time, up to its ceiling. The turn
        that writes and records it is queued, due fifteen minutes before."""
        with turn_transaction(uk) as conn:
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

    @app.post("/api/conversations/{cid}/cancel", **post)
    def cancel_later(uk: User, cid: Annotated[int, JOB_ID]):
        """Cancel a scheduled workout before its turn begins; once it has, Stop ends it instead."""
        with connection() as conn:
            try:
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
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return view

    @app.post("/api/conversations/{cid}/stop", status_code=202, **post)
    def stop_turn(uk: User, cid: Annotated[int, JOB_ID]):
        """The listener's Stop: the running turn's work is killed within a few seconds."""
        with connection() as conn:
            try:
                try:
                    c = conversations.load(conn, uk, cid)
                except LookupError:
                    raise HTTPException(404, "no such conversation") from None
                stopped = c.state == "working" and c.job_id is not None and jobs.request_stop(conn, uk, c.job_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return {"stopping": stopped}

    @app.post("/api/conversations/{cid}/messages", status_code=202, **post)
    def post_message(uk: User, cid: Annotated[int, JOB_ID], body: Annotated[TurnLine, Body()]):
        args = turn_args(cid, body.line, None, body.today, body.now)
        with turn_transaction(uk) as conn:
            healed(conn, uk, cid)
            if not conversations.begin_turn(conn, uk, cid, body.line, None):
                raise HTTPException(409, STILL_WORKING)
            job_id = queue_turn(conn, uk, args)
        return {"job_id": job_id}

    # ---- the built client -------------------------------------------------------------------

    @app.get("/{path:path}", include_in_schema=False)
    def client(path: str):
        if path in ("api", "feed") or path.startswith(("api/", "link/", "feed/")):
            raise HTTPException(404, "not found")
        if not dist.is_dir():
            if path == "":
                return PlainTextResponse(f"{APP_NAME}'s client isn't built yet: "
                                         "run npm run build in web/client.")
            raise HTTPException(404, "not found")
        root = dist.resolve()
        wanted = (root / path).resolve()
        if path and wanted.is_relative_to(root) and wanted.is_file():
            return FileResponse(wanted)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})

    return app


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


def create_app_from_env() -> FastAPI:
    """For uvicorn's --factory: settings from the environment, migrations applied once."""
    settings = config.load(os.environ)
    engine.not_dumpable()   # Linux: no engine child can read our environment via /proc
    conn = db.connect(settings.database_url)
    try:
        db.migrate(conn)
    finally:
        conn.close()
    return create_app(settings)
