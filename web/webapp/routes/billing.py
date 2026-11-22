"""Minutes: the balance, the packs, a pack's Checkout page, and Stripe's webhook, the only thing that credits a
purchase. The webhook is the one POST with no session and no same-origin check: Stripe's signature stands in."""
from typing import Annotated

import anyio
from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StrictStr, StringConstraints

from .. import billing, minutes
from .state import POST, St, User, read, tx

router = APIRouter()

NO_MINUTES = "no_minutes"   # the page offers the packs when it reads this code


class NoMinutes(HTTPException):
    """The refusal when a balance doesn't cover what was asked, said the same way wherever it's refused (402,
    with the code the page reads)."""
    code = NO_MINUTES

    def __init__(self, need: int, have: int):
        super().__init__(402, f"That needs {need} {'minute' if need == 1 else 'minutes'} and you have {have}. "
                              "Add minutes in Settings, then try again.")


class PackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pack: Annotated[StrictStr, StringConstraints(max_length=64)]


@router.get("/api/minutes")
def get_minutes(st: St, uk: User):
    """The balance, what's for sale and what happened lately."""
    with read(st) as conn:
        have = minutes.balance(conn, uk.user_id)
        rows = minutes.history(conn, uk.user_id)
    return {"minutes": have, "can_buy": st.billing is not None,
            "packs": [{"id": p.id, "minutes": p.minutes, "cents": p.cents} for p in minutes.PACKS],
            "history": rows}


@router.post("/api/minutes/checkout", **POST)
def checkout(st: St, uk: User, body: Annotated[PackBody, Body()]):
    """Where to pay for a pack: the address of its Stripe Checkout page. Nothing is credited here."""
    pack = minutes.pack(body.pack)
    if pack is None:
        raise HTTPException(404, "no such pack")
    if st.billing is None:
        raise HTTPException(404, "Minutes aren't sold on this site.")
    try:
        return {"url": st.billing.checkout(uk.user_id, pack)}
    except billing.Unavailable:
        raise HTTPException(503, "The checkout page isn't answering just now. Try again in a minute.") from None


@router.post("/api/stripe/webhook")
async def webhook(st: St, request: Request):
    """Stripe's word that a pack was paid for, or refunded. Credited once however often Stripe sends it (the
    ledger's own rule); anything unsigned is refused, anything else is acknowledged and ignored."""
    if st.billing is None:
        raise HTTPException(404, "not found")
    payload = await request.body()
    try:
        event = st.billing.event(payload, request.headers.get("stripe-signature"))
    except billing.BadSignature:
        raise HTTPException(400, "bad signature") from None

    def work() -> None:
        with tx(st) as conn:
            # an account deleted since it paid has nothing left to credit, but the books still keep the money
            if conn.execute("select 1 from users where id = %s for update", (event.user_id,)).fetchone() is None:
                if event.kind == "paid":
                    minutes.sold(conn, None, event.pack, event.ref, event.cents)
                else:
                    minutes.refunded(conn, event.ref)
                return
            if event.kind == "paid":
                minutes.purchase(conn, event.user_id, event.pack.minutes, event.ref, event.pack.label)
                minutes.sold(conn, event.user_id, event.pack, event.ref, event.cents)
            else:
                minutes.refund(conn, event.user_id, event.ref)
                minutes.refunded(conn, event.ref)
    if event is not None:
        await anyio.to_thread.run_sync(work)
    return {"received": True}
