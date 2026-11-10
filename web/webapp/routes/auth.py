"""Sign-in: what the sign-in page offers, registering, signing in, a new password, a device's link and signing out.
Failed sign-ins and registrations are throttled in memory (one web process), by username and by client address."""
import html
import json
from typing import Annotated
from urllib.parse import parse_qs

import anyio
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, StrictStr, StringConstraints

from .. import APP_NAME, auth, start
from ..api import _address, _secure, error_body
from .state import COOKIE, POST, AppState, St, User, confirming, tx

router = APIRouter()

# (attempts, seconds): failed sign-ins per username and per address; registrations per address
# and across everyone
LOGIN_PER_NAME = (10, 15 * 60)
LOGIN_PER_ADDRESS = (50, 15 * 60)
REGISTER_PER_ADDRESS = (10, 60 * 60)   # every attempt counts, taken names too
REGISTER_ALL = (50, 60 * 60)
CONFIRM_PER_USER = (10, 15 * 60)       # wrong passwords a signed-in user may give (a new password, deleting the account)


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[StrictStr, StringConstraints(max_length=200)]
    password: Annotated[StrictStr, StringConstraints(max_length=auth.PASSWORD_MAX)]


class NewPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current: Annotated[StrictStr, StringConstraints(max_length=auth.PASSWORD_MAX)] | None = None
    new: Annotated[StrictStr, StringConstraints(max_length=auth.PASSWORD_MAX)]


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


def _refused(status: int, message: str, field: str) -> JSONResponse:
    """A refusal about one box of a form: `detail` says why, as every refusal does, and `field` names the box (the
    request's own key: "username", "password", "current", "new"), so the page can say it there."""
    return JSONResponse(error_body(status, message, field=field), status)


def signed_in(st: AppState, token: str, status: int = 204) -> Response:
    r = Response(status_code=status)
    r.set_cookie(COOKIE, token, max_age=st.settings.session_days * 86400, path="/",
                 secure=_secure(st.settings), httponly=True, samesite="lax")
    return r


@router.get("/api/auth")
def auth_info(st: St):
    """What the sign-in page offers."""
    return {"app_name": APP_NAME, "registration": st.settings.registration, "version": st.version}


@router.post("/api/register", status_code=201, **POST)
def register(st: St, request: Request, body: Annotated[Credentials, Body()]):
    if not st.settings.registration:
        raise HTTPException(403, "New accounts are closed for now.")
    addr = _address(request)
    if st.throttles["reg_addr"].full(addr) or st.throttles["reg_all"].full("all"):
        raise HTTPException(429, "Too many new accounts just now. Try again in an hour.")
    st.throttles["reg_addr"].hit(addr)
    try:
        with tx(st) as conn:
            token = auth.register(conn, st.settings, body.username, body.password)
    except auth.Invalid as e:
        return _refused(400, str(e), e.field)
    except auth.Taken:
        return _refused(409, "That username is taken.", "username")
    st.throttles["reg_all"].hit("all")
    return signed_in(st, token, 201)


@router.post("/api/sign-in", status_code=204, **POST)
def sign_in(st: St, request: Request, body: Annotated[Credentials, Body()]):
    name, addr = body.username.strip().lower(), _address(request)
    if st.throttles["login_name"].full(name) or st.throttles["login_addr"].full(addr):
        raise HTTPException(429, "Too many tries. Wait 15 minutes and try again.")
    try:
        with tx(st) as conn:
            token = auth.sign_in(conn, st.settings, body.username, body.password)
    except auth.WrongPassword:
        st.throttles["login_name"].hit(name)
        st.throttles["login_addr"].hit(addr)
        raise HTTPException(400, "Wrong username or password.") from None
    return signed_in(st, token)


@router.post("/api/password", status_code=204, **POST)
def password(st: St, request: Request, uk: User, body: Annotated[NewPassword, Body()]):
    key = confirming(st, uk)
    try:
        with tx(st) as conn:
            auth.set_password(conn, uk.user_id, body.current, body.new,
                              keep_session=request.cookies.get(COOKIE))
    except auth.Invalid as e:
        return _refused(400, str(e), "new" if e.field == "password" else e.field)
    except auth.WrongPassword:
        st.throttles["confirms"].hit(key)
        return _refused(400, "Your current password isn't right.", "current")
    return Response(status_code=204)


@router.get("/link/{token}", response_class=HTMLResponse)
def link_page(token: str):
    """A page whose button signs in; opening it (as a link preview does) uses nothing up."""
    return HTMLResponse(_link_page(token), headers={"Cache-Control": "no-store"})


@router.post("/api/link/redeem", **POST)
async def redeem(st: St, request: Request):
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
        with tx(st) as conn:
            return auth.redeem(conn, st.settings, token)
    try:
        session_token = await anyio.to_thread.run_sync(work)
    except auth.Refused:
        if is_json:
            return JSONResponse(error_body(410, "This link has expired or was already used."), 410)
        return HTMLResponse(_refused_page(), 410, headers={"Cache-Control": "no-store"})
    r = RedirectResponse("/", status_code=303)
    r.set_cookie(COOKIE, session_token, max_age=st.settings.session_days * 86400, path="/",
                 secure=_secure(st.settings), httponly=True, samesite="lax")
    return r


@router.post("/api/sign-out", status_code=204, **POST)
def sign_out(st: St, request: Request, uk: User):
    with tx(st) as conn:
        auth.sign_out(conn, request.cookies[COOKIE])
    start.forget(uk.user_id)
    r = Response(status_code=204)
    r.delete_cookie(COOKIE, path="/", secure=_secure(st.settings), httponly=True, samesite="lax")
    return r


@router.post("/api/device-link", **POST)
def device_link(st: St, uk: User):
    with tx(st) as conn:
        link = auth.device_link(conn, st.settings, uk.user_id)
    return {"url": link.url, "expires_at": link.expires_at.isoformat()}
