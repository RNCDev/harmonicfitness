"""The web server: sign-in, the signed-in JSON API, a job's event stream and the built client.

    uvicorn webapp.api:create_app_from_env --factory --no-access-log   (run from web/)

The routes are in routes/, a router per area, included by create_app in the order they're matched; this module
holds the app itself: its middleware, its one shape of error, and its connections.

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
import json
import os
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import APP_NAME, config, db, engine, enginelib, log, streams
from .folder import IMPORT_MAX_TOTAL, IMPORT_MAX_ZIP

CLIENT_DIST = Path(__file__).resolve().parent.parent / "client" / "dist"
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


def create_app(settings: config.Settings, connect: Callable[[], psycopg.Connection] | None = None,
               client_dist: str | os.PathLike | None = None) -> FastAPI:
    """The app. `connect` (tests) opens a connection; without it requests use a pool of
    settings.database_url, and the job events listener (streams.Hub) opens its own connection to it."""
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
        open_stream = lambda: psycopg.connect(settings.database_url, connect_timeout=10, keepalives=1,  # noqa: E731
                                              keepalives_idle=60, keepalives_interval=10, keepalives_count=3)
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

    hub = streams.Hub(open_stream)

    @asynccontextmanager
    async def lifespan(_app):
        if pool is not None:
            pool.open()
        try:
            yield
        finally:
            hub.close()
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

    # ---- the routes, in the order they're matched -------------------------------------------

    from .routes import account, auth as authroutes, client, conversations as conversationroutes, files, \
        jobs as jobroutes, logs, media as mediaroutes, settings as settingroutes, state as routestate
    app.state.hf = routestate.AppState(
        settings=settings, connection=connection, open_stream=open_stream, services=services,
        version=version, dist=dist, origin=origin,
        throttles={"login_name": Throttle(*authroutes.LOGIN_PER_NAME),
                   "login_addr": Throttle(*authroutes.LOGIN_PER_ADDRESS),
                   "reg_addr": Throttle(*authroutes.REGISTER_PER_ADDRESS),
                   "reg_all": Throttle(*authroutes.REGISTER_ALL),
                   "confirms": Throttle(*authroutes.CONFIRM_PER_USER)},
        hub=hub)

    @app.get("/healthz")
    def healthz():
        """For the host's health check: no session, no database."""
        return {"ok": True, "version": version}

    app.include_router(authroutes.router)
    app.include_router(account.router)
    app.include_router(files.router)
    app.include_router(logs.router)
    app.include_router(account.late)   # after the Logs routes, where these always were
    app.include_router(mediaroutes.router)
    app.include_router(settingroutes.router)
    app.include_router(jobroutes.router)
    app.include_router(conversationroutes.router)   # /api/conversations/latest before /api/conversations/{cid}
    app.include_router(client.router)   # its catch-all last
    return app


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
