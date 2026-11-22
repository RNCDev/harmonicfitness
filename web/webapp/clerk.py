"""Sign-in through Clerk (0.85.0): checking a Clerk session token and reading a Clerk user.

The browser signs in with Clerk's own page parts and hands this site a short-lived session token (a JWT signed
with the instance's RS256 key). `verify` checks it here, with the instance's public keys and no call to Clerk
beyond fetching those: its signature, its times, that this instance issued it and that it was made for this
site's page. The site then keeps its own session cookie, so nothing else changes for a signed-in listener.

`send(method, url, headers) -> (status, body)` is the one way out, so the tests fake Clerk. Nothing is retried,
no redirect is followed, and no message here holds a token or the secret key."""
import base64
import binascii
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

API = "https://api.clerk.com/v1"
LEEWAY = 10                 # seconds a token's times may be off by
KEYS_FOR = 60 * 60          # seconds the instance's public keys are kept
TOKEN_MAX = 8_192
HOST = re.compile(r"^[a-z0-9]([a-z0-9.-]{0,251}[a-z0-9])?$")
ID = re.compile(r"^user_[A-Za-z0-9]{8,64}$")


class Refused(Exception):
    """A token that isn't a live session of this instance for this site (never says which part failed)."""


class Unavailable(Exception):
    """Clerk didn't answer, or answered with something unexpected."""


@dataclass(frozen=True)
class Person:
    id: str
    username: str | None
    external_id: str | None
    email: str | None = field(default=None, repr=False)   # their primary address when it's verified: used for
                                                          # one digest (minutes.who), never stored or logged


def frontend_api(publishable_key: str) -> str:
    """The instance's own host, which a publishable key carries: pk_test_<base64 of "host$">."""
    try:
        part = publishable_key.split("_", 2)[2]
        host = base64.b64decode(part + "=" * (-len(part) % 4), validate=True).decode("ascii").rstrip("$").lower()
    except (IndexError, ValueError, binascii.Error):
        raise ValueError("CLERK_PUBLISHABLE_KEY isn't a Clerk publishable key") from None
    if not HOST.match(host) or "." not in host:
        raise ValueError("CLERK_PUBLISHABLE_KEY isn't a Clerk publishable key")
    return host


def _b64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def _send(method: str, url: str, headers: dict) -> tuple[int, object]:
    import httpx
    try:
        r = httpx.request(method, url, headers=headers, timeout=10, follow_redirects=False)
    except httpx.HTTPError:
        raise Unavailable("Clerk didn't answer") from None
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


class Client:
    def __init__(self, publishable_key: str, secret_key: str, origin: str,
                 send: Callable[[str, str, dict], tuple[int, object]] = _send, clock=time.time):
        self.host = frontend_api(publishable_key)
        self.issuer = f"https://{self.host}"
        self.secret, self.origin, self.send, self.clock = secret_key, origin, send, clock
        self.keys: dict[str, rsa.RSAPublicKey] = {}
        self.fetched = 0.0
        self.lock = threading.Lock()

    # ---- the session token ------------------------------------------------------------------

    def _key(self, kid: str) -> rsa.RSAPublicKey | None:
        with self.lock:
            now = self.clock()
            # an unknown key id fetches again (Clerk rotated), at most once a minute
            if (kid in self.keys and now - self.fetched < KEYS_FOR) or (kid not in self.keys
                                                                         and now - self.fetched < 60):
                return self.keys.get(kid)
            status, body = self.send("GET", f"{self.issuer}/.well-known/jwks.json", {})
            if status != 200 or not isinstance(body, dict):
                raise Unavailable("Clerk's keys couldn't be read")
            keys = {}
            for k in body.get("keys") or []:
                try:
                    if k.get("kty") == "RSA" and k.get("kid"):
                        n = int.from_bytes(_b64(k["n"]), "big")
                        e = int.from_bytes(_b64(k["e"]), "big")
                        keys[str(k["kid"])] = rsa.RSAPublicNumbers(e, n).public_key()
                except (KeyError, ValueError, TypeError, AttributeError):
                    continue
            self.keys, self.fetched = keys, now
            return keys.get(kid)

    def verify(self, token: str) -> str:
        """The Clerk user id a live session token is for, else Refused."""
        if not isinstance(token, str) or len(token) > TOKEN_MAX or token.count(".") != 2:
            raise Refused()
        head_b64, claims_b64, sig_b64 = token.split(".")
        try:
            head, claims, sig = json.loads(_b64(head_b64)), json.loads(_b64(claims_b64)), _b64(sig_b64)
        except (ValueError, binascii.Error):
            raise Refused() from None
        if not isinstance(head, dict) or not isinstance(claims, dict) or head.get("alg") != "RS256":
            raise Refused()     # only the algorithm Clerk signs with: never "none", never a shared-secret one
        key = self._key(str(head.get("kid") or ""))
        if key is None:
            raise Refused()
        try:
            key.verify(sig, f"{head_b64}.{claims_b64}".encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
        except (InvalidSignature, ValueError):
            raise Refused() from None
        now = self.clock()
        exp, nbf, sub = claims.get("exp"), claims.get("nbf", 0), claims.get("sub")
        if not isinstance(exp, (int, float)) or not isinstance(nbf, (int, float)) or isinstance(exp, bool):
            raise Refused()
        if now > exp + LEEWAY or now < nbf - LEEWAY:
            raise Refused()
        if claims.get("iss") != self.issuer:
            raise Refused()
        # azp: the page the session token was made for. Ours, or the token was made for another site's page.
        if str(claims.get("azp") or "").lower().rstrip("/") != self.origin:
            raise Refused()
        if claims.get("sts") == "pending" or not isinstance(sub, str) or not ID.match(sub):
            raise Refused()
        return sub

    # ---- the Backend API ----------------------------------------------------------------------

    def _api(self, method: str, path: str) -> tuple[int, object]:
        return self.send(method, f"{API}{path}", {"authorization": f"Bearer {self.secret}"})

    def person(self, clerk_id: str) -> Person:
        if not ID.match(clerk_id):
            raise Refused()
        status, body = self._api("GET", f"/users/{clerk_id}")
        if status == 404:
            raise Refused()
        if status != 200 or not isinstance(body, dict):
            raise Unavailable("Clerk couldn't say who that is")
        primary = body.get("primary_email_address_id")
        email = next((e.get("email_address") for e in body.get("email_addresses") or []
                      if isinstance(e, dict) and primary and e.get("id") == primary
                      and (e.get("verification") or {}).get("status") == "verified"), None)
        name, ext = body.get("username"), body.get("external_id")
        return Person(id=clerk_id, username=name if isinstance(name, str) and name else None,
                      external_id=ext if isinstance(ext, str) and ext else None,
                      email=email if isinstance(email, str) and email else None)

    def delete(self, clerk_id: str) -> None:
        """Delete the Clerk user (when the account here is deleted). A user already gone is fine."""
        if not ID.match(clerk_id):
            return
        status, _ = self._api("DELETE", f"/users/{clerk_id}")
        if status not in (200, 404):
            raise Unavailable("Clerk couldn't delete that user")
