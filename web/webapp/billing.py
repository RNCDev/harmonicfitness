"""Minute packs, bought through Stripe Checkout (0.85.0).

The site never sees a card: `checkout` asks Stripe for a Checkout page for one pack and sends the listener there;
Stripe then tells the site the payment went through with a signed webhook, and only that credits the minutes
(`event` checks the signature and says what the event means). The price of each pack lives in Stripe, found by its
lookup key (webapp.stripe_setup makes them); the minutes a pack gives come from minutes.PACKS, never from the
request or from Stripe.

`send(method, url, headers, form) -> (status, body)` is the one way out, so the tests fake Stripe. A Checkout
session is never asked for twice: nothing is retried, no redirect is followed, and no message holds a key."""
import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Callable

from . import minutes

API = "https://api.stripe.com/v1"
TOLERANCE = 5 * 60      # seconds a webhook's timestamp may be from now (a replayed one is older)


class Unavailable(Exception):
    """Stripe didn't answer, or doesn't have the pack's price."""


class BadSignature(Exception):
    """A webhook that Stripe didn't sign with our secret, or an old one sent again."""


@dataclass(frozen=True)
class Event:
    kind: str               # "paid" or "refunded"
    user_id: uuid.UUID
    ref: str                # the purchase's own id, made here when its Checkout page was asked for
    pack: minutes.Pack | None
    cents: int | None = None   # what a paid one came to before tax, after any promotion code (the books' figure)


def _send(method: str, url: str, headers: dict, form: list | None) -> tuple[int, object]:
    import httpx
    try:
        r = httpx.request(method, url, headers=headers, data=dict(form) if form else None, timeout=20,
                          follow_redirects=False)
    except httpx.HTTPError:
        raise Unavailable("Stripe didn't answer") from None
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


class Client:
    def __init__(self, secret_key: str, webhook_secret: str, base_url: str,
                 send: Callable[[str, str, dict, list | None], tuple[int, object]] = _send, clock=time.time):
        self.secret, self.webhook_secret, self.base = secret_key, webhook_secret, base_url.rstrip("/")
        self.send, self.clock = send, clock
        self.prices: dict[str, str] = {}
        self.lock = threading.Lock()

    def _api(self, method: str, path: str, form: list | None = None, extra: dict | None = None):
        return self.send(method, f"{API}{path}", {"authorization": f"Bearer {self.secret}", **(extra or {})}, form)

    def _price(self, pack: minutes.Pack) -> str:
        """The Stripe price a pack is sold at, by its lookup key; refused unless it's the pack's own amount, so
        a price changed in Stripe never sells minutes at another price than the page showed."""
        with self.lock:
            if pack.id in self.prices:
                return self.prices[pack.id]
        status, body = self._api("GET", f"/prices?lookup_keys[]={pack.id}&active=true&limit=1")
        rows = body.get("data") if status == 200 and isinstance(body, dict) else None
        if not rows or not isinstance(rows[0], dict):
            raise Unavailable("Stripe has no price for that pack")
        price = rows[0]
        if price.get("unit_amount") != pack.cents or price.get("currency") != "usd" or not price.get("id"):
            raise Unavailable("Stripe's price for that pack isn't the pack's")
        with self.lock:
            self.prices[pack.id] = str(price["id"])
        return self.prices[pack.id]

    def checkout(self, user_id, pack: minutes.Pack) -> str:
        """The address of a Checkout page for `pack`, bought by this user."""
        ref = secrets.token_hex(16)
        meta = {"user": str(user_id), "pack": pack.id, "ref": ref}
        form = [("mode", "payment"), ("client_reference_id", str(user_id)),
                ("line_items[0][price]", self._price(pack)), ("line_items[0][quantity]", "1"),
                ("success_url", f"{self.base}/?minutes=bought"), ("cancel_url", f"{self.base}/?minutes=cancelled"),
                ("allow_promotion_codes", "true")]   # the page's "Add promotion code" box, for a code made in Stripe
        # the same three facts on the session and on its payment, so a refund's event carries them too
        form += [(f"metadata[{k}]", v) for k, v in meta.items()]
        form += [(f"payment_intent_data[metadata][{k}]", v) for k, v in meta.items()]
        status, body = self._api("POST", "/checkout/sessions", form, {"idempotency-key": ref})
        url = body.get("url") if status == 200 and isinstance(body, dict) else None
        if not isinstance(url, str) or not url.startswith("https://"):
            raise Unavailable("Stripe couldn't open a checkout page")
        return url

    def event(self, payload: bytes, signature: str | None) -> Event | None:
        """What a webhook means, once its signature is checked (BadSignature otherwise): a paid pack, a refunded
        one, or None for an event the site does nothing with."""
        sent, stamp = [], None
        for part in (signature or "").split(","):
            k, _, v = part.strip().partition("=")
            if k == "t":
                stamp = v
            elif k == "v1":
                sent.append(v)
        try:
            age = abs(self.clock() - int(stamp or ""))
        except ValueError:
            raise BadSignature() from None
        want = hmac.new(self.webhook_secret.encode(), stamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
        if age > TOLERANCE or not any(hmac.compare_digest(want, s) for s in sent):
            raise BadSignature()
        try:
            body = json.loads(payload)
            kind, obj = body["type"], body["data"]["object"]
            meta = obj.get("metadata") or {}
        except (ValueError, KeyError, TypeError, AttributeError):
            return None
        if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            # paid, or nothing to pay (a promotion code for the whole price); a slow payment method's minutes come
            # with async_payment_succeeded
            if obj.get("payment_status") not in ("paid", "no_payment_required"):
                return None
            what = "paid"
        elif kind == "charge.refunded" and obj.get("refunded") is True:
            what = "refunded"   # the whole payment; a part refund is the maintainer's to settle by hand
        else:
            return None
        try:
            user_id, ref = uuid.UUID(str(meta.get("user"))), str(meta.get("ref") or "")
        except ValueError:
            return None
        pack = minutes.pack(str(meta.get("pack") or ""))
        # the pack's own price before any discount: a code lowers what's paid, never which pack's minutes are given
        if not ref or (what == "paid" and (pack is None or obj.get("amount_subtotal") != pack.cents)):
            return None
        if what != "paid":
            return Event(what, user_id, ref, pack)
        details = obj.get("total_details")
        off = details.get("amount_discount") if isinstance(details, dict) else 0
        off = off if isinstance(off, int) and not isinstance(off, bool) and 0 <= off <= pack.cents else 0
        return Event(what, user_id, ref, pack, pack.cents - off)
