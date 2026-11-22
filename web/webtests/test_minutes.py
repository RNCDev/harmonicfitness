"""Minutes, Clerk and Stripe (0.85.0): the money and sign-in rules. A purchase is credited once; a recording's
minutes are held with its Record, kept with its MP3 and handed back once without one; nothing records without
them; a sign-in is this instance's token for this site's page; and only the site's own key is used, and no dearer
voice records."""
import base64
import dataclasses
import hashlib
import hmac
import json
import os
import sys
import time
import types
import unittest
import uuid
from unittest import mock

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

from webapp import api, billing, clerk, conversations, hosted, jobs, minutes, spend  # noqa: E402
from webapp.agent import tools  # noqa: E402
from webtests import test_api  # noqa: E402
from webtests.dbcase import MASTER, DBCase, committed  # noqa: E402

BASE = test_api.BASE
HOST = "clerk.wt.test"
PUBLISHABLE = "pk_test_" + base64.b64encode(f"{HOST}$".encode()).decode().rstrip("=")
WEBHOOK_SECRET = "whsec_test"
SIGNER = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_SIGNER = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def token(sub="user_abcdefgh1234", signer=SIGNER, head=None, **claims) -> str:
    """A Clerk session token as Clerk signs one, for this site's page unless a claim says otherwise."""
    now = int(time.time())
    head = {"alg": "RS256", "kid": "k1", "typ": "JWT", **(head or {})}
    body = {"sub": sub, "iss": f"https://{HOST}", "azp": BASE, "exp": now + 60, "nbf": now - 5, **claims}
    signed = f"{b64(json.dumps(head).encode())}.{b64(json.dumps(body).encode())}"
    return f"{signed}.{b64(signer.sign(signed.encode(), padding.PKCS1v15(), hashes.SHA256()))}"


class FakeClerk:
    """Clerk's two faces: the instance's public keys, and the Backend API's users."""
    def __init__(self):
        self.people, self.deleted, self.asked = {}, [], []

    def __call__(self, method, url, headers):
        self.asked.append((method, url))
        if url.endswith("/.well-known/jwks.json"):
            n = SIGNER.public_key().public_numbers()
            return 200, {"keys": [{"kty": "RSA", "kid": "k1", "n": b64(n.n.to_bytes(256, "big")),
                                   "e": b64(n.e.to_bytes(3, "big"))}]}
        who = url.rsplit("/", 1)[1]
        if method == "DELETE":
            self.deleted.append(who)
            return 200, {}
        return (200, self.people[who]) if who in self.people else (404, None)

    def person(self, sub, email=None, username=None, external_id=None, verified=True):
        self.people[sub] = {"id": sub, "username": username, "external_id": external_id,
                            "primary_email_address_id": "e1" if email else None,
                            "email_addresses": [{"id": "e1", "email_address": email, "verification": {
                                "status": "verified" if verified else "unverified"}}] if email else []}
        return sub


def new_sub() -> str:
    return "user_" + uuid.uuid4().hex[:20]


class FakeStripe:
    def __init__(self):
        self.sessions, self.amount = [], {p.id: p.cents for p in minutes.PACKS}

    def __call__(self, method, url, headers, form):
        if "/prices?" in url:
            pack = url.split("lookup_keys[]=")[1].split("&")[0]
            return 200, {"data": [{"id": f"price_{pack}", "unit_amount": self.amount[pack], "currency": "usd"}]}
        self.sessions.append(dict(form))
        return 200, {"url": "https://checkout.stripe.test/c/1"}


def signed(payload: dict, secret=WEBHOOK_SECRET, at=None) -> tuple[bytes, dict]:
    """A webhook's body and its Stripe-Signature header."""
    raw, stamp = json.dumps(payload).encode(), str(int(at if at is not None else time.time()))
    sig = hmac.new(secret.encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {"stripe-signature": f"t={stamp},v1={sig}", "content-type": "application/json"}


def paid_event(user_id, pack=minutes.PACKS[0], ref="ref1", amount=None, kind="checkout.session.completed"):
    return {"type": kind, "data": {"object": {
        "payment_status": "paid", "amount_subtotal": pack.cents if amount is None else amount,
        "metadata": {"user": str(user_id), "pack": pack.id, "ref": ref}}}}


class Ledger(DBCase):
    def have(self, user_id) -> int:
        n = minutes.balance(self.conn, user_id)
        self.conn.rollback()
        return n

    def test_a_purchase_is_credited_once_and_a_refund_taken_once(self):
        user_id, _ = self.make_user()
        self.assertTrue(committed(minutes.purchase, self.conn, user_id, 60, "cs_1"))
        self.assertFalse(committed(minutes.purchase, self.conn, user_id, 60, "cs_1"))   # Stripe sent it again
        self.assertEqual(self.have(user_id), 60)
        self.assertTrue(committed(minutes.hold, self.conn, user_id, 7, 25))
        # a refund takes back what's left of what was bought, never below nothing, and only once
        self.assertEqual(committed(minutes.refund, self.conn, user_id, "cs_1"), 35)
        self.assertEqual(committed(minutes.refund, self.conn, user_id, "cs_1"), 0)
        self.assertEqual(committed(minutes.refund, self.conn, user_id, "never-bought"), 0)
        self.assertEqual(self.have(user_id), 0)

    def test_a_hold_is_the_charge_kept_with_the_recording_and_handed_back_once_without_one(self):
        user_id, _ = self.make_user()
        committed(minutes.grant, self.conn, user_id, 30, "gift")
        with self.subTest("too few minutes: nothing changes"):
            self.assertFalse(committed(minutes.hold, self.conn, user_id, 1, 31))
            self.assertEqual(self.have(user_id), 30)
        with self.subTest("held once for a turn, however often it's asked"):
            self.assertTrue(committed(minutes.hold, self.conn, user_id, 1, 20))
            self.assertTrue(committed(minutes.hold, self.conn, user_id, 1, 20))
            self.assertEqual(self.have(user_id), 10)
        with self.subTest("no recording: handed back, once"):
            self.assertEqual(committed(minutes.release, self.conn, user_id, 1), 20)
            self.assertEqual(committed(minutes.release, self.conn, user_id, 1), 0)
            self.assertEqual(self.have(user_id), 30)
        with self.subTest("a kept recording's minutes are spent"):
            self.assertTrue(committed(minutes.hold, self.conn, user_id, 2, 20))
            committed(minutes.keep, self.conn, user_id, 2)
            self.assertEqual(committed(minutes.release, self.conn, user_id, 2), 0)
            self.assertEqual(self.have(user_id), 10)

    def test_a_paid_script_records_again_free_once(self):
        user_id, uk = self.make_user()
        committed(minutes.grant, self.conn, user_id, 50, "gift")
        script = minutes.tag(uk, "2026-11-01-strength-20")
        for job, left in ((1, 30), (2, 30), (3, 10)):   # paid, the one fix after hearing it, then paid again
            self.assertTrue(committed(minutes.hold, self.conn, user_id, job, 20, script))
            committed(minutes.keep, self.conn, user_id, job)
            self.assertEqual(self.have(user_id), left, job)
        # a recording that was never kept earns no free one
        other = minutes.tag(uk, "2026-11-02-strength-20")
        self.assertTrue(committed(minutes.hold, self.conn, user_id, 4, 5, other))
        committed(minutes.release, self.conn, user_id, 4)
        self.assertEqual(minutes.owed(self.conn, user_id, other, 5), 5)
        self.conn.rollback()

    def test_the_sweep_hands_back_only_a_dead_turns_hold(self):
        user_id, uk = self.make_user()
        committed(minutes.grant, self.conn, user_id, 40, "gift")
        dead, live, kept = (committed(jobs.add, self.conn, uk, "turn", {}) for _ in range(3))
        for job in (dead, live, kept):
            self.assertTrue(committed(minutes.hold, self.conn, user_id, job, 10))
        committed(minutes.keep, self.conn, user_id, kept)
        self.conn.execute("update jobs set state = 'failed', finished_at = now() where id = any(%s)", ([dead, kept],))
        self.conn.execute("update minute_ledger set at = now() - interval '1 hour' where user_id = %s", (user_id,))
        self.conn.commit()
        self.assertEqual(committed(minutes.sweep, self.conn), 1)
        self.assertEqual(committed(minutes.sweep, self.conn), 0)
        self.assertEqual(self.have(user_id), 20)    # the dead turn's ten back; the queued one's and the kept one's held

    def test_the_minutes_to_start_with_come_once_a_person(self):
        first, _ = self.make_user()
        again, _ = self.make_user()
        who = minutes.who(MASTER, " Someone@Example.org ")
        self.assertEqual(who, minutes.who(MASTER, "someone@example.org"))
        self.assertTrue(committed(minutes.welcome, self.conn, first, who))
        self.assertFalse(committed(minutes.welcome, self.conn, first, who))
        self.assertFalse(committed(minutes.welcome, self.conn, again, who))   # deleted and made again: none
        self.assertEqual((self.have(first), self.have(again)), (minutes.WELCOME, 0))
        # the table holds a keyed digest, never the address
        self.assertNotIn(b"someone", bytes(self.conn.execute("select who from welcomed").fetchone()[0]))
        self.conn.rollback()


class Token(unittest.TestCase):
    def setUp(self):
        self.fake = FakeClerk()
        self.clerk = clerk.Client(PUBLISHABLE, "sk_test_x", BASE, send=self.fake)

    def test_only_this_instances_live_token_for_this_sites_page(self):
        self.assertEqual(self.clerk.verify(token()), "user_abcdefgh1234")
        now = int(time.time())
        unsigned = token().rsplit(".", 1)[0] + "."
        hs = token(head={"alg": "HS256"})
        refused = {
            "made for another site's page": token(azp="https://evil.test"),
            "no page named": token(azp=None),
            "another instance's": token(iss="https://clerk.other.test"),
            "expired": token(exp=now - 120),
            "not yet": token(nbf=now + 120),
            "signed by someone else": token(signer=OTHER_SIGNER),
            "no signature": unsigned,
            "alg none": token(head={"alg": "none"}),
            "a shared-secret algorithm": hs,
            "an unknown key": token(head={"kid": "k9"}),
            "a session still pending": token(sts="pending"),
            "no user": token(sub="org_abcdefgh1234"),
            "not a token": "abc",
        }
        for why, t in refused.items():
            with self.subTest(why):
                with self.assertRaises(clerk.Refused):
                    self.clerk.verify(t)

    def test_the_publishable_key_names_the_instance(self):
        self.assertEqual(clerk.frontend_api(PUBLISHABLE), HOST)
        for bad in ("", "pk_test_", "sk_test_abc", "pk_test_" + base64.b64encode(b"no dot$").decode()):
            with self.assertRaises(ValueError):
                clerk.frontend_api(bad)


class Webhook(unittest.TestCase):
    def setUp(self):
        self.stripe = FakeStripe()
        self.billing = billing.Client("sk_test_x", WEBHOOK_SECRET, BASE, send=self.stripe)
        self.user = uuid.uuid4()

    def test_only_what_stripe_signed_and_only_a_pack_at_its_own_price(self):
        event = self.billing.event(*self.sent(paid_event(self.user)))
        self.assertEqual((event.kind, event.user_id, event.ref, event.pack), ("paid", self.user, "ref1", minutes.PACKS[0]))
        with self.subTest("signed with another secret, old, or not at all"):
            for raw, headers in (signed(paid_event(self.user), secret="whsec_other"),
                                 signed(paid_event(self.user), at=time.time() - 3600),
                                 (json.dumps(paid_event(self.user)).encode(), {})):
                with self.assertRaises(billing.BadSignature):
                    self.billing.event(raw, headers.get("stripe-signature"))
            raw, headers = signed(paid_event(self.user))
            with self.assertRaises(billing.BadSignature):   # the body changed after it was signed
                self.billing.event(raw.replace(b"hf_minutes_60", b"hf_minutes_320"), headers["stripe-signature"])
        with self.subTest("credits nothing"):
            unpaid = paid_event(self.user)
            unpaid["data"]["object"]["payment_status"] = "unpaid"
            for payload in (paid_event(self.user, amount=1),                      # a pack's minutes at another price
                            paid_event(self.user, pack=minutes.Pack("hf_minutes_9999", 9999, 500)),
                            paid_event("not-a-user"), unpaid, {"type": "customer.created", "data": {"object": {}}}):
                self.assertIsNone(self.billing.event(*self.sent(payload)))

    def test_a_promotion_code_lowers_what_is_paid_never_the_minutes(self):
        off = paid_event(self.user)
        off["data"]["object"]["total_details"] = {"amount_discount": 125}
        event = self.billing.event(*self.sent(off))
        self.assertEqual((event.kind, event.pack, event.cents), ("paid", minutes.PACKS[0], minutes.PACKS[0].cents - 125))
        free = paid_event(self.user)   # a code for the whole price: nothing to pay, the pack's minutes still given
        free["data"]["object"].update(payment_status="no_payment_required", total_details={"amount_discount": 500})
        event = self.billing.event(*self.sent(free))
        self.assertEqual((event.kind, event.pack, event.cents), ("paid", minutes.PACKS[0], 0))

    def sent(self, payload):
        raw, headers = signed(payload)
        return raw, headers["stripe-signature"]

    def test_checkout_sells_a_pack_only_at_its_own_price(self):
        url = self.billing.checkout(self.user, minutes.PACKS[1])
        self.assertTrue(url.startswith("https://"))
        form = self.stripe.sessions[0]
        self.assertEqual((form["metadata[user]"], form["metadata[pack]"], form["line_items[0][price]"]),
                         (str(self.user), "hf_minutes_140", "price_hf_minutes_140"))
        self.assertEqual(form["metadata[ref]"], form["payment_intent_data[metadata][ref]"])   # a refund finds it
        self.assertEqual(form["allow_promotion_codes"], "true")   # a code made in Stripe can be entered
        self.stripe.amount["hf_minutes_320"] = 100      # someone changed the price in Stripe
        with self.assertRaises(billing.Unavailable):
            self.billing.checkout(self.user, minutes.PACKS[2])
        self.assertEqual(len(self.stripe.sessions), 1)


class SiteCase(test_api.ApiCase):
    """The app with Clerk and Stripe set up, both faked."""

    def setUp(self):
        super().setUp()
        self.fake_clerk, self.fake_stripe = FakeClerk(), FakeStripe()
        self.settings = dataclasses.replace(
            self.settings, clerk_publishable_key=PUBLISHABLE, clerk_secret_key="sk_test_x",
            stripe_secret_key="sk_test_y", stripe_webhook_secret=WEBHOOK_SECRET)
        self.app = api.create_app(self.settings, connect=self.connect, client_dist=self.dist,
                                  clerk_send=self.fake_clerk, stripe_send=self.fake_stripe)
        self.client = self.other_client()

    def session(self, t, client=None):
        return (client or self.client).post("/api/session", json={"token": t}, headers=self.origin())

    def have(self, user_id) -> int:
        n = minutes.balance(self.conn, user_id)
        self.conn.rollback()
        return n

    def user_of(self, sub):
        row = self.conn.execute("select id, username from users where clerk_id = %s", (sub,)).fetchone()
        self.conn.rollback()
        return row


class ClerkSignIn(SiteCase):
    def test_a_clerk_session_signs_in_and_passwords_are_off(self):
        sub = self.fake_clerk.person(new_sub(), email=f"{uuid.uuid4().hex}@example.org", username="Rowan.B")
        with self.subTest("the page is told to sign in with Clerk"):
            self.assertEqual(self.client.get("/api/auth").json()["clerk"], PUBLISHABLE)
        with self.subTest("a token for another site's page is refused"):
            self.assertEqual(self.session(token(sub, azp="https://evil.test")).status_code, 401)
            self.assertIsNone(self.user_of(sub))
        with self.subTest("a new account, with the minutes to start with"):
            r = self.session(token(sub))
            self.assertEqual(r.status_code, 204, r.text)
            self.assertIn("HttpOnly", r.headers["set-cookie"])
            me = self.client.get("/api/me").json()
            self.assertEqual((me["username"], me["clerk"], me["clerk_linked"], me["has_password"]),
                             ("rowan.b", True, True, False))
            user_id = self.user_of(sub)[0]
            self.assertEqual(self.have(user_id), minutes.WELCOME)
        with self.subTest("signing in again: the same account, no second gift, and Clerk isn't asked who"):
            asked = len(self.fake_clerk.asked)
            self.assertEqual(self.session(token(sub), self.other_client()).status_code, 204)
            self.assertEqual((self.user_of(sub)[0], self.have(user_id)), (user_id, minutes.WELCOME))
            self.assertEqual(len(self.fake_clerk.asked), asked)
        with self.subTest("the username and password routes are gone"):
            for path, body in (("/api/register", {"username": "someone", "password": "long enough"}),
                               ("/api/sign-in", {"username": "rowan.b", "password": "long enough"}),
                               ("/api/password", {"new": "long enough"})):
                self.assertEqual(self.client.post(path, json=body, headers=self.origin()).status_code, 404, path)
        with self.subTest("no email address is stored"):
            row = self.conn.execute("select row_to_json(u)::text from users u where id = %s", (user_id,)).fetchone()
            self.conn.rollback()
            self.assertNotIn("example.org", row[0])

    def test_an_unverified_address_gets_no_minutes(self):
        sub = self.fake_clerk.person(new_sub(), email=f"{uuid.uuid4().hex}@example.org", verified=False)
        self.assertEqual(self.session(token(sub)).status_code, 204)
        self.assertEqual(self.have(self.user_of(sub)[0]), 0)

    def test_an_exported_account_is_linked_once_and_never_handed_to_another(self):
        old, _ = self.make_user("legacy1")
        owner = self.fake_clerk.person(new_sub(), username="legacy1", external_id=str(old))
        thief = self.fake_clerk.person(new_sub(), username="thief", external_id=str(old))
        self.assertEqual(self.session(token(owner)).status_code, 204)
        self.assertEqual(self.user_of(owner), (old, "legacy1"))
        self.assertEqual(self.session(token(thief), self.other_client()).status_code, 204)
        self.assertNotEqual(self.user_of(thief)[0], old)    # an account of their own, not the linked one

    def test_closed_to_new_accounts_still_lets_the_known_in(self):
        known = self.fake_clerk.person(new_sub())
        self.assertEqual(self.session(token(known)).status_code, 204)
        self.settings = dataclasses.replace(self.settings, registration=False)
        self.app = api.create_app(self.settings, connect=self.connect, client_dist=self.dist,
                                  clerk_send=self.fake_clerk, stripe_send=self.fake_stripe)
        closed = self.other_client()
        self.assertEqual(self.session(token(known), closed).status_code, 204)
        stranger = self.fake_clerk.person(new_sub())
        self.assertEqual(self.session(token(stranger), closed).status_code, 403)
        self.assertIsNone(self.user_of(stranger))

    def test_deleting_the_account_needs_a_fresh_clerk_token_of_its_own(self):
        sub, other = self.fake_clerk.person(new_sub()), self.fake_clerk.person(new_sub())
        self.assertEqual(self.session(token(sub)).status_code, 204)
        for body in ({"token": token(other)}, {"password": "long enough"}, {}):
            r = self.client.post("/api/account/delete", json=body, headers=self.origin())
            self.assertEqual(r.status_code, 400, r.text)
        self.assertIsNotNone(self.user_of(sub))
        r = self.client.post("/api/account/delete", json={"token": token(sub)}, headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        self.assertIsNone(self.user_of(sub))
        self.assertEqual(self.fake_clerk.deleted, [sub])


class Packs(SiteCase):
    def webhook(self, payload, **kw):
        raw, headers = signed(payload, **kw)
        return self.client.post("/api/stripe/webhook", content=raw, headers=headers)

    def test_a_paid_pack_is_credited_by_stripes_signed_word_alone_and_once(self):
        user_id, _ = self.signed_in()
        with self.subTest("the checkout page credits nothing"):
            r = self.client.post("/api/minutes/checkout", json={"pack": "hf_minutes_60"}, headers=self.origin())
            self.assertEqual((r.status_code, r.json()), (200, {"url": "https://checkout.stripe.test/c/1"}))
            self.assertEqual(self.fake_stripe.sessions[0]["client_reference_id"], str(user_id))
            self.assertEqual(self.have(user_id), 0)
            r = self.client.post("/api/minutes/checkout", json={"pack": "hf_minutes_1"}, headers=self.origin())
            self.assertEqual(r.status_code, 404)
        with self.subTest("unsigned, or signed by another"):
            raw = json.dumps(paid_event(user_id)).encode()
            self.assertEqual(self.client.post("/api/stripe/webhook", content=raw).status_code, 400)
            self.assertEqual(self.webhook(paid_event(user_id), secret="whsec_other").status_code, 400)
            self.assertEqual(self.have(user_id), 0)
        with self.subTest("credited once, though Stripe sends it twice"):
            for _ in range(2):
                self.assertEqual(self.webhook(paid_event(user_id)).status_code, 200)
            n = minutes.PACKS[0].minutes
            self.assertEqual(self.have(user_id), n)
            got = self.client.get("/api/minutes").json()
            self.assertEqual((got["minutes"], got["can_buy"], [h["minutes"] for h in got["history"]]), (n, True, [n]))
        with self.subTest("a refund takes them back, once"):
            refund = {"type": "charge.refunded", "data": {"object": {
                "refunded": True, "metadata": {"user": str(user_id), "pack": "hf_minutes_60", "ref": "ref1"}}}}
            for _ in range(2):
                self.assertEqual(self.webhook(refund).status_code, 200)
            self.assertEqual(self.have(user_id), 0)
        with self.subTest("an account deleted since it paid: acknowledged, nothing written"):
            self.assertEqual(self.webhook(paid_event(uuid.uuid4(), ref="ref2")).status_code, 200)
            self.assertIsNone(self.conn.execute("select 1 from minute_ledger where ref = 'ref2'").fetchone())
            self.conn.rollback()


class Hosted(SiteCase):
    turn = test_api.Conversations.turn

    def listener(self, has=0):
        user_id, uk = self.signed_in()
        if has:
            committed(minutes.grant, self.conn, user_id, has, "gift")
        return user_id, uk

    def offered(self, has, need=20, chars=13000):
        user_id, uk = self.listener(has)
        r = self.client.post("/api/conversations", json=self.turn(line="a strength workout"), headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        cid = r.json()["id"]
        c = conversations.load(self.conn, uk, cid)
        self.conn.execute("update jobs set state = 'done', finished_at = now() where id = %s", (c.job_id,))
        c.state, c.offer = "idle", {"draft": "me/workouts/w/w.draft.txt", "name": "Workout", "coach": "Coach Dean",
                                    "chars": chars, "usd": 0.3, "service": "openrouter", "design": False,
                                    "minutes": need}
        self.assertTrue(conversations.save(self.conn, uk, c, c.version))
        self.conn.commit()
        return user_id, uk, cid

    def test_no_conversation_without_minutes(self):
        user_id, uk = self.listener()
        for path in ("/api/keys", "/api/keys/fish", "/api/writer", "/api/balances"):   # gone with listeners' keys
            self.assertIn(self.client.put(path, json={}, headers=self.origin()).status_code, (404, 405), path)
        with self.subTest("nothing is written without a minute to record it with"):
            r = self.client.post("/api/conversations", json=self.turn(line="a workout"), headers=self.origin())
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (402, "no_minutes"))
            self.assertIsNone(self.conn.execute("select 1 from jobs where user_id = %s", (user_id,)).fetchone())
            self.conn.rollback()
        with self.subTest("with one, it starts"):
            committed(minutes.grant, self.conn, user_id, 1, "gift")
            r = self.client.post("/api/conversations", json=self.turn(line="a workout"), headers=self.origin())
            self.assertEqual(r.status_code, 202, r.text)
            self.assertEqual(self.client.get("/api/me").json()["minutes"], 1)

    def test_record_holds_the_recordings_minutes(self):
        user_id, uk, cid = self.offered(has=25)
        shown = self.client.get(f"/api/conversations/{cid}").json()["offer"]
        self.assertEqual((shown["minutes"], shown["charge"]), (20, 20))
        r = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(self.have(user_id), 5)
        # the turn ended with no recording: its hold goes back (what the worker does as the turn ends)
        self.assertEqual(committed(minutes.release, self.conn, user_id, r.json()["job_id"]), 20)

    def test_record_without_the_minutes_is_refused_and_leaves_nothing_written(self):
        user_id, uk, cid = self.offered(has=5)
        before = conversations.load(self.conn, uk, cid)
        queued = self.conn.execute("select count(*) from jobs where user_id = %s", (user_id,)).fetchone()[0]
        self.conn.rollback()
        r = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (402, "no_minutes"))
        self.assertIn("20 minutes and you have 5", r.json()["detail"])
        after = conversations.load(self.conn, uk, cid)
        self.assertEqual((after.version, after.state, after.offer), (before.version, "idle", before.offer))
        self.assertEqual(self.conn.execute("select count(*) from jobs where user_id = %s", (user_id,)).fetchone()[0],
                         queued)
        self.assertEqual(spend.used(self.conn, uk, test_api.today()), 0)
        self.assertIsNone(self.conn.execute("select 1 from minute_ledger where user_id = %s and kind = 'record'",
                                            (user_id,)).fetchone())
        self.conn.rollback()
        self.assertEqual(self.have(user_id), 5)

    def test_a_days_turns_have_a_ceiling(self):
        user_id, uk, cid = self.offered(has=5)
        for _ in range(minutes.DAILY_TURNS):
            jobs.add(self.conn, uk, "turn", {})
        self.conn.execute("update jobs set state = 'done', finished_at = now() where user_id = %s", (user_id,))
        self.conn.commit()
        r = self.client.post("/api/conversations", json=self.turn(line="another"), headers=self.origin())
        self.assertEqual(r.status_code, 429, r.text)


class HostedWorker(unittest.TestCase):
    def test_the_sites_key_is_the_only_one_a_job_gets(self):
        from webapp import worker
        ctx = types.SimpleNamespace(settings=types.SimpleNamespace(openrouter_key="sk-or-site"), conn=None, uk=None)
        self.assertEqual(worker.Ctx.key_env(ctx), {"OPENROUTER_API_KEY": "sk-or-site"})   # no connection: nothing read


class HostedAgent(unittest.TestCase):
    """The site's voice: a minute is sold against one model's price, so no other records."""
    BUILD = ["build", "me/workouts/a/a.draft.txt", "Workout A", "--coach"]
    ROWS = [{"name": "Coach Dean", "slug": "coach-dean-openrouter", "service": "openrouter", "shipped": True,
             "model": hosted.VOICE_MODEL, "placeholder": False},
            {"name": "Coach Graham", "slug": "coach-graham-openrouter", "service": "openrouter", "shipped": True,
             "model": "elevenlabs/eleven-turbo-v2.5", "placeholder": False},
            {"name": "Coach Mine", "slug": "coach-mine", "service": "openrouter", "shipped": False,
             "model": hosted.VOICE_MODEL, "placeholder": False}]

    def engine(self, listing=True, model=hosted.VOICE_MODEL, seconds=1150):
        calls = []

        def run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            calls.append(argv)
            if argv[:2] == ["coaches", "list"]:
                return tools.engine.Result(0, json.dumps({"coaches": self.ROWS}) if listing else "not json", "")
            if argv[:2] == ["get", "cost"]:
                return tools.engine.Result(0, json.dumps({"service": "openrouter", "model": model, "chars": 12000,
                                                          "usd": 0.27}), "")
            if argv[:2] == ["get", "plan"]:
                return tools.engine.Result(0, json.dumps({"rows": [], "seconds": seconds}), "")
            if "--lint-only" in argv:
                return tools.engine.Result(0, "lint ok: the script speaks 12,000 characters", "")
            if argv[0] == "build":
                raise AssertionError("recorded without an approval")
            return tools.engine.Result(0, "{}", "")
        return mock.patch.object(tools.engine, "run", side_effect=run), calls

    def deps(self):
        return tools.Deps(engine_root=test_api.ROOT, home=os.path.join(test_api.ROOT, "me.example"), keys={},
                          today="2026-10-28", now="2026-10-28 Wednesday 08:00", writers="three")

    def test_only_the_sites_voice_is_offered_and_in_minutes(self):
        self.assertEqual([c["name"] for c in hosted.coaches(self.ROWS)], ["Coach Dean"])
        with self.subTest("a coach on a dearer voice, or a listener's own, is refused before anything is priced"):
            for name in ("Coach Graham", "Coach Mine", "Coach Reed"):
                deps = self.deps()
                patch, calls = self.engine()
                with patch:
                    r = tools.run(deps, [*self.BUILD, name])
                self.assertEqual((r.code, deps.offer), (64, None), name)
                self.assertNotIn(["get", "cost"], [c[:2] for c in calls])
        with self.subTest("the price's own check holds when the listing can't be read"):
            deps = self.deps()
            patch, _ = self.engine(listing=False, model="elevenlabs/eleven-turbo-v2.5")
            with patch:
                r = tools.run(deps, [*self.BUILD, "Coach Graham"])
            self.assertEqual((r.code, deps.offer), (64, None))
        with self.subTest("the site's own: offered for its minutes, with no price in money said"):
            deps = self.deps()
            patch, _ = self.engine()
            with patch:
                r = tools.run(deps, [*self.BUILD, "Coach Dean"])
            self.assertEqual((r.code, deps.offer["minutes"], deps.offer["coach"]), (0, 20, "Coach Dean"))
            self.assertNotIn("$", r.output)
        with self.subTest("no keys and no coach of their own"):
            for args in (["keys"], ["coaches", "make", "--slug", "x"]):
                patch, calls = self.engine()
                with patch:
                    self.assertEqual(tools.run(self.deps(), args).code, 64)
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
