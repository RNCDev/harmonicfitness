"""The web server: sign-in, the signed-in JSON API, a job's event stream and the built client.

    uvicorn webapp.api:create_app_from_env --factory --no-access-log   (run from web/)

Every route under /api but sign-in, registration and a link's redeem needs the session cookie
`wt_session` (else 401). Failed sign-ins and registrations are throttled in memory (one web
process), by username and by client address.
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
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, \
    RedirectResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, StringConstraints

from . import APP_NAME, auth, config, conversations, db, engine, folder, jobs, keystore, media, providers, \
    store, \
    worker

COOKIE = "wt_session"
MINUTES = [10, 15, 20, 25, 30, 45]
MAX_QUEUED = 3            # queued jobs a user may have at once (a guard against a stuck button)
KEEP_ALIVE = 15           # seconds between keep-alive comments on an event stream
POLL_EVERY = 5            # seconds between status reads without a NOTIFY (fail and reap send none)
WAIT_SLICE = 1.0          # seconds a stream blocks at most, so a client gone away is noticed soon
CLIENT_DIST = Path(__file__).resolve().parent.parent / "client" / "dist"
JOB_ID = PathParam(ge=1, le=2**63 - 1)
# (attempts, seconds): failed sign-ins per username and per address; registrations per address
# and across everyone
LOGIN_PER_NAME = (10, 15 * 60)
LOGIN_PER_ADDRESS = (50, 15 * 60)
REGISTER_PER_ADDRESS = (10, 60 * 60)   # every attempt counts, taken names too
REGISTER_ALL = (50, 60 * 60)


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
Now = Annotated[StrictStr, StringConstraints(max_length=40)]   # the worker's check_turn says the rest
Line = Annotated[StrictStr, StringConstraints(min_length=1, max_length=2000)]

class TurnLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line: Line
    today: Day
    now: Now


STILL_WORKING = "Still working on the last message."


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[StrictStr, StringConstraints(max_length=200)]
    password: Annotated[StrictStr, StringConstraints(max_length=auth.PASSWORD_MAX)]


class NewPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current: Annotated[StrictStr, StringConstraints(max_length=auth.PASSWORD_MAX)] | None = None
    new: Annotated[StrictStr, StringConstraints(max_length=auth.PASSWORD_MAX)]


KEY_MIN = 16     # shorter values escape engine.scrub (8+ only) and are never real keys
KEY_MAX = 1024


class KeyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: Annotated[StrictStr, StringConstraints(max_length=KEY_MAX)]


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


def _link_page(token: str) -> str:
    t = html.escape(token, quote=True)
    title = html.escape(f"Sign in to {APP_NAME}")
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta name="robots" content="noindex">'
            f"<title>{title}</title></head>\n<body>"
            f'<form method="post" action="/api/link/redeem">'
            f'<input type="hidden" name="token" value="{t}">'
            f'<button type="submit">{title}</button></form></body></html>\n')


def _refused_page() -> str:
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="robots" content="noindex">'
            f"<title>{html.escape(APP_NAME)}</title></head>\n<body><p>This link has expired or "
            f"was already used.</p></body></html>\n")


def build_version(engine_root: str, env=os.environ) -> str:
    """What the page shows, so a deploy is visible: the engine's VERSION and the deployed commit
    (HARMONICFITNESS_COMMIT, baked in at build from Railway's RAILWAY_GIT_COMMIT_SHA), as "0.20.0 (75da105)"."""
    try:
        v = Path(engine_root, "VERSION").read_text().strip() or "unknown"
    except OSError:
        v = "unknown"
    sha = (env.get("HARMONICFITNESS_COMMIT") or env.get("RAILWAY_GIT_COMMIT_SHA") or "").strip()[:7]
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


IMPORT_MAX_ZIP = 10_000_000      # bytes of ZIP
IMPORT_MAX_FILE = 2_000_000      # bytes of one file, unpacked
IMPORT_MAX_TOTAL = 30_000_000    # bytes of every file, unpacked
IMPORT_MAX_FILES = 2_000


def folder_from_zip(data: bytes) -> tuple[dict[str, bytes], int]:
    """(path -> bytes, how many entries were left out) from a ZIP of a me/ folder. The ZIP may hold the
    folder's files at its top or inside one folder (me/, harmonicfitness-me/...). Raises ValueError with
    a sentence for a person."""
    import io
    import stat
    import zipfile
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValueError("That isn't a ZIP file.") from None
    entries = [i for i in z.infolist() if not i.is_dir()]
    if len(entries) > IMPORT_MAX_FILES:
        raise ValueError(f"That ZIP holds more than {IMPORT_MAX_FILES} files.")
    names = [i.filename for i in entries]
    tops = {n.split("/", 1)[0] for n in names if not n.startswith("__MACOSX/")}
    strip = ""
    if ("profile.md" not in names and len(tops) == 1 and next(iter(tops)) not in ("", ".", "..")
            and f"{next(iter(tops))}/profile.md" in names):
        strip = f"{next(iter(tops))}/"   # the folder itself was zipped
    files, left_out, total = {}, 0, 0
    for info in entries:
        path = info.filename[len(strip):] if info.filename.startswith(strip) else info.filename
        mode = info.external_attr >> 16
        parts = path.split("/")
        if (stat.S_ISLNK(mode) or folder.skipped(path) or parts[0].startswith(".backup") or parts[0] == ".git"
                or "__MACOSX" in parts or parts[-1].startswith("._")):
            left_out += 1
            continue
        try:
            store.check_path(path)
        except ValueError:
            left_out += 1
            continue
        if info.file_size > IMPORT_MAX_FILE:
            left_out += 1
            continue
        total += info.file_size
        if total > IMPORT_MAX_TOTAL:
            raise ValueError(f"That folder is over {IMPORT_MAX_TOTAL // 1_000_000} MB unpacked.")
        with z.open(info) as f:
            body = f.read(IMPORT_MAX_FILE + 1)
        if len(body) > IMPORT_MAX_FILE:
            left_out += 1
            continue
        files[path] = body
    if "profile.md" not in files:
        raise ValueError("That ZIP has no profile.md: zip the me folder itself.")
    return files, left_out

def create_app(settings: config.Settings, connect: Callable[[], psycopg.Connection] | None = None,
               client_dist: str | os.PathLike | None = None) -> FastAPI:
    """The app. `connect` (tests) opens a connection; without it requests use a pool of
    settings.database_url and an event stream opens its own connection to it."""
    goals, presets = worker.engine_lists(settings.engine_root)
    options = {"minutes": list(MINUTES), "goals": sorted(goals), "presets": sorted(presets)}
    services = worker.engine_services(settings.engine_root)
    version = build_version(settings.engine_root)
    worker.engine_keys(settings.engine_root)    # a broken import fails at startup
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

    @app.exception_handler(RequestValidationError)
    def invalid(_request: Request, e: RequestValidationError):
        """422 without pydantic's `input` (and `ctx`), which would echo a key or a password."""
        errors = [{k: v for k, v in err.items() if k not in ("input", "ctx")} for err in e.errors()]
        return JSONResponse({"detail": errors}, 422)

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
    login_name, login_addr = Throttle(*LOGIN_PER_NAME), Throttle(*LOGIN_PER_ADDRESS)
    reg_addr, reg_all = Throttle(*REGISTER_PER_ADDRESS), Throttle(*REGISTER_ALL)

    def signed_in(token: str, status: int = 204) -> Response:
        r = Response(status_code=status)
        r.set_cookie(COOKIE, token, max_age=settings.session_days * 86400, path="/",
                     secure=_secure(settings), httponly=True, samesite="lax")
        return r

    @app.get("/healthz")
    def healthz():
        """For the host's health check: no session, no database."""
        return {"ok": True, "version": version}

    # ---- sign-in ----------------------------------------------------------------------------

    @app.get("/api/auth")
    def auth_info():
        """What the sign-in page offers."""
        return {"app_name": APP_NAME, "registration": settings.registration, "version": version}

    @app.post("/api/register", status_code=201, **post)
    def register(request: Request, body: Annotated[Credentials, Body()]):
        if not settings.registration:
            raise HTTPException(403, "New accounts are closed for now.")
        addr = _address(request)
        if reg_addr.full(addr) or reg_all.full("all"):
            raise HTTPException(429, "Too many new accounts just now. Try again in an hour.")
        reg_addr.hit(addr)
        try:
            with connection() as conn:
                token = auth.register(conn, settings, body.username, body.password)
        except auth.Invalid as e:
            raise HTTPException(400, str(e)) from None
        except auth.Taken:
            raise HTTPException(409, "That username is taken.") from None
        reg_all.hit("all")
        return signed_in(token, 201)

    @app.post("/api/sign-in", status_code=204, **post)
    def sign_in(request: Request, body: Annotated[Credentials, Body()]):
        name, addr = body.username.strip().lower(), _address(request)
        if login_name.full(name) or login_addr.full(addr):
            raise HTTPException(429, "Too many tries. Wait 15 minutes and try again.")
        try:
            with connection() as conn:
                token = auth.sign_in(conn, settings, body.username, body.password)
        except auth.WrongPassword:
            login_name.hit(name)
            login_addr.hit(addr)
            raise HTTPException(400, "Wrong username or password.") from None
        return signed_in(token)

    @app.post("/api/password", status_code=204, **post)
    def password(request: Request, uk: User, body: Annotated[NewPassword, Body()]):
        try:
            with connection() as conn:
                auth.set_password(conn, uk.user_id, body.current, body.new,
                                  keep_session=request.cookies.get(COOKIE))
        except auth.Invalid as e:
            raise HTTPException(400, str(e)) from None
        except auth.WrongPassword:
            raise HTTPException(400, "Your current password isn't right.") from None
        return Response(status_code=204)

    @app.get("/link/{token}", response_class=HTMLResponse)
    def link_page(token: str):
        """A page whose button signs in; opening it (as a link preview does) uses nothing up."""
        return HTMLResponse(_link_page(token), headers={"Cache-Control": "no-store"})

    @app.post("/api/link/redeem", **post)
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
            name, pw = conn.execute("select username, password_hash is not null from users "
                                    "where id = %s", (uk.user_id,)).fetchone()
            conn.rollback()
        return {"app_name": APP_NAME, "username": name, "has_password": pw, "version": version}

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

    @app.post("/api/import", **post)
    async def import_folder(uk: User, request: Request):
        """A ZIP of the listener's me/ folder, brought in once: every file kept as it is, over the
        starter files of the same name. Key files, audio, caches, logs and backups are left out."""
        body = await request.body()
        if len(body) > IMPORT_MAX_ZIP:
            raise HTTPException(413, f"That ZIP is over {IMPORT_MAX_ZIP // 1_000_000} MB.")
        try:
            files, left_out = folder_from_zip(body)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        if not files:
            raise HTTPException(400, "That ZIP holds none of your folder's files.")

        def save() -> None:
            with connection() as conn:
                try:
                    for path in sorted(files):
                        store.put(conn, uk, path, files[path])
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
        await anyio.to_thread.run_sync(save)
        return {"imported": len(files), "left_out": left_out}

    @app.get("/api/media/{mid}")
    def get_media(uk: User, request: Request, mid: Annotated[str, PathParam(max_length=40)], download: bool = False):
        """A workout's MP3, the user's own, for 24 hours: inline for the player, or as a download. The
        browser may keep it until it expires (private: never a shared cache)."""
        with connection() as conn:
            try:
                found = media.get(conn, uk, mid)
            finally:
                conn.rollback()
        if found is None:
            raise HTTPException(404, "That audio has expired or isn't yours.")
        name, body, expires = found
        left = max(0, int((expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()))
        safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "workout"
        headers = {"Cache-Control": f"private, max-age={left}", "Accept-Ranges": "bytes",
                   "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{safe}.mp3"'}
        part = _byte_range(request.headers.get("range"), len(body))
        if part is None:
            return Response(body, media_type="audio/mpeg", headers=headers)
        if part == ():
            return Response(status_code=416, headers={"Content-Range": f"bytes */{len(body)}"})
        start, end = part   # Safari's player asks for ranges, and won't play without them
        return Response(body[start:end + 1], status_code=206, media_type="audio/mpeg",
                        headers={**headers, "Content-Range": f"bytes {start}-{end}/{len(body)}"})

    @app.get("/api/keys")
    def list_keys(uk: User):
        with connection() as conn:
            try:
                have = keystore.listing(conn, uk)
            finally:
                conn.rollback()
        rows = [(p, providers.PROVIDERS[p].name, providers.PROVIDERS[p].key_page, "model")
                for p in settings.providers]
        rows += [(s, v["name"], v["key_page"], "voice") for s, v in services.items()]
        return [{"service": s, "name": n, "key_page": page, "kind": kind, "set": s in have,
                 "updated_at": have[s].isoformat() if s in have else None}
                for s, n, page, kind in rows]

    def known(service: str) -> dict:
        if service in settings.providers:
            spec = providers.PROVIDERS[service]
            return {"name": spec.name, "key_var": f"{service.upper()}_API_KEY"}
        if service not in services:
            raise HTTPException(404, "no such service")
        return services[service]

    @app.put("/api/keys/{service}", status_code=204, **post)
    def put_key(uk: User, service: str, body: Annotated[KeyBody, Body()]):
        info = known(service)
        value = worker.clean_key(settings.engine_root, info["key_var"], body.key)
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

    # ---- conversations ----------------------------------------------------------------------

    def turn_args(cid: int, line: str | None, answer: dict | None, today: str, now: str) -> dict:
        args = {"conversation_id": cid, "line": line, "answer": answer, "today": today, "now": now}
        problem = worker.check_turn(args)
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
                queued = conn.execute("select count(*) from jobs where user_id = %s and "
                                      "state = 'queued'", (uk.user_id,)).fetchone()[0]
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

    def shown(c: conversations.Conversation) -> dict:
        """What the client sees: never the history; the job only while it works; when it last changed
        (ISO, so the client can show an earlier day's conversation as history)."""
        return {"id": c.id, "state": c.state, "job_id": c.job_id if c.state == "working" else None,
                "lines": c.lines, "question": c.question, "plan": c.plan,
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
            finally:
                conn.rollback()
        if not any(p in have for p in settings.providers):
            name = providers.PROVIDERS[settings.providers[0]].name
            raise HTTPException(409, f"Add a key for {name} in Keys first.")
        with turn_transaction(uk) as conn:
            cid = conversations.create(conn, uk, body.line)
            job_id = queue_turn(conn, uk, turn_args(cid, body.line, None, body.today, body.now))
        return {"id": cid, "job_id": job_id}

    @app.get("/api/conversations/latest")
    def latest_conversation(uk: User):
        with connection() as conn:
            try:
                c = conversations.latest(conn, uk)
                if c is not None:
                    c = conversations.heal(conn, uk, c)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return Response(status_code=204) if c is None else shown(c)

    @app.get("/api/conversations/{cid}")
    def get_conversation(uk: User, cid: Annotated[int, JOB_ID]):
        with connection() as conn:
            try:
                c = healed(conn, uk, cid)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return shown(c)

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
        if path == "api" or path.startswith(("api/", "link/")):
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
