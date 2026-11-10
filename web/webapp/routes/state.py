"""What every router shares: the app's state, the session and same-origin dependencies, and the two ways a route
holds a transaction (tx commits on the way out, read never does; either rolls back on any raise)."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Callable, Iterator

import psycopg
from fastapi import Depends, HTTPException, Request
from fastapi import Path as PathParam

from .. import auth, config, store
from ..api import _origin

if TYPE_CHECKING:
    from ..api import Throttle

COOKIE = "wt_session"
MAX_QUEUED = 3            # queued jobs a user may have at once (a guard against a stuck button)
JOB_ID = PathParam(ge=1, le=2**63 - 1)


@dataclass
class AppState:
    settings: config.Settings
    connection: Callable[[], Any]         # a contextmanager: a pooled connection, or the tests' own
    open_stream: Callable[[], psycopg.Connection]   # an event stream's own connection
    options: dict
    services: dict[str, dict]
    version: str
    dist: Path
    origin: str
    throttles: "dict[str, Throttle]"      # login_name, login_addr, reg_addr, reg_all, confirms


def state(request: Request) -> AppState:
    return request.app.state.hf


St = Annotated[AppState, Depends(state)]


@contextmanager
def tx(st: AppState) -> Iterator[psycopg.Connection]:
    """A connection whose work commits when the block ends, and rolls back on any raise (a refusal too)."""
    with st.connection() as conn:
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


@contextmanager
def read(st: AppState) -> Iterator[psycopg.Connection]:
    """A connection for reading: whatever the block did is rolled back as it ends."""
    with st.connection() as conn:
        try:
            yield conn
        finally:
            conn.rollback()


def same_origin(request: Request) -> None:
    """CSRF: a POST must come from our own origin."""
    sent = request.headers.get("origin")
    if sent is None:
        referer = request.headers.get("referer")
        sent = _origin(referer) if referer else None
    if sent is None or sent.lower() != state(request).origin:
        raise HTTPException(403, "cross-origin request refused")


def session(request: Request) -> store.UserKey:
    st = state(request)
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "not signed in")
    with st.connection() as conn:
        user_id = auth.user_for(conn, st.settings, token)
        if user_id is None:
            raise HTTPException(401, "not signed in")
        uk = store.user_key(conn, st.settings, user_id)
        conn.rollback()
        return uk


User = Annotated[store.UserKey, Depends(session)]
POST = {"dependencies": [Depends(same_origin)]}


def confirming(st: AppState, uk: store.UserKey) -> str:
    """The throttle's key for a signed-in user's password checks; 429 once they've given too many wrong."""
    key = str(uk.user_id)
    if st.throttles["confirms"].full(key):
        raise HTTPException(429, "Too many tries. Wait 15 minutes and try again.")
    return key
