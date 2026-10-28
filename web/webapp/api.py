"""The web server: sign-in, the signed-in JSON API, a job's event stream and the built client.

    uvicorn webapp.api:create_app_from_env --factory --no-access-log   (run from web/)

Every route under /api but the invite redeem needs the session cookie `wt_session` (else 401).
Every POST needs an Origin (or, without one, a Referer) of WT_BASE_URL's origin (else 403).
A job or file of another user is 404, the same as one that doesn't exist. Nothing here logs a
token, a job's arguments, its events or its result.

Connections: requests borrow one from a small pool (or, in tests, open one with the injected
`connect`), never sharing one between requests. An event stream holds one connection of its own
for its whole life, in autocommit: it LISTENs on job_events and reads the job's status and events
on that same connection (each read its own transaction, so it sees every commit), and closes it
when the stream ends or the client goes away.
"""
import html
import json
import os
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Callable, Literal
from urllib.parse import parse_qs, urlsplit

import anyio
import psycopg
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, \
    RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, StringConstraints

from . import APP_NAME, auth, config, db, engine, jobs, store, worker

COOKIE = "wt_session"
MINUTES = [10, 15, 20, 25, 30, 45]
MAX_QUEUED = 3            # queued jobs a user may have at once (a guard against a stuck button)
KEEP_ALIVE = 15           # seconds between keep-alive comments on an event stream
POLL_EVERY = 5            # seconds between status reads without a NOTIFY (fail and reap send none)
WAIT_SLICE = 1.0          # seconds a stream blocks at most, so a client gone away is noticed soon
CLIENT_DIST = Path(__file__).resolve().parent.parent / "client" / "dist"
JOB_ID = PathParam(ge=1, le=2**63 - 1)


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


class _Headers:
    """Security headers on every response (pure ASGI, so streams aren't buffered or broken)."""

    BASE = ((b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"same-origin"), (b"x-robots-tag", b"noindex"))

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        api = scope.get("path", "").startswith("/api/")

        async def sending(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                have = {k.lower() for k, _ in headers}
                extra = list(self.BASE) + ([(b"cache-control", b"no-store")] if api else [])
                headers += [(k, v) for k, v in extra if k not in have]
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, sending)


def _invite_page(token: str) -> str:
    t = html.escape(token, quote=True)
    title = html.escape(f"Sign in to {APP_NAME}")
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex">'
            f"<title>{title}</title></head>\n<body>"
            f'<form method="post" action="/api/invite/redeem">'
            f'<input type="hidden" name="token" value="{t}">'
            f'<button type="submit">{title}</button></form></body></html>\n')


def _refused_page() -> str:
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="robots" content="noindex">'
            f"<title>{html.escape(APP_NAME)}</title></head>\n<body><p>This link has expired or "
            f"was already used. Ask for a new one.</p></body></html>\n")


def create_app(settings: config.Settings, connect: Callable[[], psycopg.Connection] | None = None,
               client_dist: str | os.PathLike | None = None) -> FastAPI:
    """The app. `connect` (tests) opens a connection; without it requests use a pool of
    settings.database_url and an event stream opens its own connection to it."""
    goals, presets = worker.engine_lists(settings.engine_root)
    options = {"minutes": list(MINUTES), "goals": sorted(goals), "presets": sorted(presets)}
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
    app.add_middleware(_Headers)

    # ---- dependencies ---------------------------------------------------------------------

    def same_origin(request: Request) -> None:
        """CSRF: a POST must come from our own origin."""
        sent = request.headers.get("origin")
        if sent is None:
            referer = request.headers.get("referer")
            sent = _origin(referer) if referer else None
        if sent is None or sent.lower() != origin:
            raise HTTPException(403, "cross-origin request refused")

    def session(request: Request) -> store.UserKey:
        token = request.cookies.get(COOKIE)
        if not token:
            raise HTTPException(401, "not signed in")
        with connection() as conn:
            user_id = auth.user_for(conn, settings, token)
            if user_id is None:
                raise HTTPException(401, "not signed in")
            uk = store.user_key(conn, settings, user_id)
            conn.rollback()
            return uk

    User = Annotated[store.UserKey, Depends(session)]
    post = {"dependencies": [Depends(same_origin)]}

    @app.get("/healthz")
    def healthz():
        """For the host's health check: no session, no database."""
        return {"ok": True}

    # ---- sign-in ----------------------------------------------------------------------------

    @app.get("/invite/{token}", response_class=HTMLResponse)
    def invite_page(token: str):
        """A page whose button signs in; opening it (as a link preview does) uses nothing up."""
        return HTMLResponse(_invite_page(token), headers={"Cache-Control": "no-store"})

    @app.post("/api/invite/redeem", **post)
    async def redeem(request: Request):
        raw = await request.body()
        is_json = request.headers.get("content-type", "").split(";")[0].strip() == "application/json"
        try:
            if is_json:
                token = json.loads(raw).get("token")
            else:
                token = (parse_qs(raw.decode("utf-8")).get("token") or [None])[0]
        except (ValueError, AttributeError):
            token = None
        if not isinstance(token, str) or not token:
            raise HTTPException(400, "a token is needed")

        def work():
            with connection() as conn:
                return auth.redeem(conn, settings, token)
        try:
            session_token = await anyio.to_thread.run_sync(work)
        except auth.Refused:
            if is_json:
                return JSONResponse({"detail": "This link has expired or was already used."}, 410)
            return HTMLResponse(_refused_page(), 410, headers={"Cache-Control": "no-store"})
        r = RedirectResponse("/", status_code=303)
        r.set_cookie(COOKIE, session_token, max_age=settings.session_days * 86400, path="/",
                     secure=_secure(settings), httponly=True, samesite="lax")
        return r

    @app.post("/api/sign-out", status_code=204, **post)
    def sign_out(request: Request, uk: User):
        with connection() as conn:
            auth.sign_out(conn, request.cookies[COOKIE])
        r = Response(status_code=204)
        r.delete_cookie(COOKIE, path="/", secure=_secure(settings), httponly=True, samesite="lax")
        return r

    @app.post("/api/device-link", **post)
    def device_link(uk: User):
        with connection() as conn:
            link = auth.device_link(conn, settings, uk.user_id)
        return {"url": link.url, "expires_at": link.expires_at.isoformat()}

    # ---- the signed-in API ------------------------------------------------------------------

    @app.get("/api/me")
    def me(uk: User):
        with connection() as conn:
            email = conn.execute("select email from users where id = %s",
                                 (uk.user_id,)).fetchone()[0]
            conn.rollback()
        return {"app_name": APP_NAME, "email": email}

    @app.get("/api/options")
    def get_options(uk: User):
        return options

    @app.get("/api/context")
    def context(uk: User):
        with connection() as conn:
            try:
                rows = store.listing(conn, uk)
            finally:
                conn.rollback()
        return [{"path": p, "version": v, "updated_at": u.isoformat()} for p, v, u in rows]

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
        return {"id": job_id, "state": st["state"], "error": st["error"], "result": res}

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

    # ---- the built client -------------------------------------------------------------------

    @app.get("/{path:path}", include_in_schema=False)
    def client(path: str):
        if path == "api" or path.startswith(("api/", "invite/")):
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
                    end = {"state": st["state"], "error": st["error"]}
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
