import datetime
import json
import os
import re
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from webapp import routes  # noqa: E402
import webapp.routes.account  # noqa: E402,F401
import webapp.routes.auth  # noqa: E402,F401
from webapp import api, auth, config, conversations, db, enginelib, feed, folder, jobs, keystore, spend, store, turns  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import MASTER, DBCase, committed, enqueue  # noqa: E402


ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


VERSION = open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip()


BASE = "https://wt.test"


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def token_of(link):
    return link.rsplit("/link/", 1)[1]


class ApiCase(DBCase):
    base_url = BASE

    def setUp(self):
        self.settings = config.Settings(database_url=dbcase.URL, master_key=MASTER,
                                        base_url=self.base_url, engine_root=ROOT)
        self.conn.rollback()
        self.conn.execute("delete from jobs")
        self.conn.commit()
        self.dist = tempfile.mkdtemp(prefix="wt-dist-")
        os.rmdir(self.dist)                   # no client built, unless a test makes one
        self.app = api.create_app(self.settings, connect=self.connect, client_dist=self.dist)
        self.client = TestClient(self.app, base_url=self.base_url)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def connect(self):
        return db.connect(dbcase.URL, schema=self.schema)

    def origin(self):
        return {"Origin": self.base_url}

    def signed_in(self, client=None):
        """A user and a client carrying its session cookie."""
        user_id, uk = self.make_user()
        client = client or self.client
        t = token_of(committed(auth.device_link, self.conn, self.settings, user_id).url)
        r = client.post("/api/link/redeem", json={"token": t}, headers=self.origin(),
                        follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        return user_id, uk

    def other_client(self):
        c = TestClient(self.app, base_url=self.base_url)
        c.__enter__()
        self.addCleanup(c.__exit__, None, None, None)
        return c


class SignIn(ApiCase):
    def test_requires_session(self):
        with self.subTest("needs a session"):
            self.assertEqual(self.client.get("/api/me").status_code, 401)
            for path in ("/api/sync", "/api/jobs/1", "/api/jobs/1/events"):
                self.assertEqual(self.client.get(path).status_code, 401, path)
            for path in ("/api/jobs", "/api/sign-out", "/api/device-link", "/api/password"):
                self.assertEqual(self.client.post(path, json={}, headers=self.origin()).status_code,
                                 401, path)
        with self.subTest("the sign-in page's facts need none"):
            self.assertEqual(self.client.get("/api/auth").json(),
                             {"app_name": "HarmonicFitness", "registration": True, "version": VERSION})

    def register(self, name="newbie", pw="long enough", client=None, **headers):
        client = client or self.client
        return client.post("/api/register", json={"username": name, "password": pw},
                           headers={**self.origin(), **headers})

    def test_register_signs_in(self):
        r = self.register("Fresh.One")
        self.assertEqual(r.status_code, 201, r.text)
        cookie = r.headers["set-cookie"]
        self.assertTrue(cookie.startswith("wt_session="), cookie)
        for flag in ("HttpOnly", "Path=/", "SameSite=lax", "Max-Age=7776000", "Secure"):
            self.assertIn(flag, cookie)
        self.assertEqual(self.client.get("/api/me").json(),
                         {"app_name": "HarmonicFitness", "username": "fresh.one",
                          "has_password": True, "version": VERSION, "sky": "flow", "auto_record": False})
        self.assertIn("profile.md", [f["path"] for f in self.client.get("/api/sync").json()["files"]])
        r = self.register("FRESH.ONE", client=self.other_client())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json(), {"detail": "That username is taken.", "field": "username",
                                    "error": {"code": "conflict", "message": "That username is taken.",
                                              "field": "username"}})
        r = self.register("pw", "short", client=self.other_client())
        self.assertEqual((r.status_code, r.json()["field"]), (400, "username"))   # the name is checked first
        r = self.register("another.one", "short", client=self.other_client())
        self.assertEqual((r.status_code, r.json()["field"]), (400, "password"))
        r = self.register("okname", "short", client=self.other_client())
        self.assertEqual(r.json()["detail"], "Use a password of at least 8 characters.")
        for body in ({"username": "a"}, {"username": 5, "password": "long enough"},
                     {"username": "abc", "password": "long enough", "extra": 1}):
            r = self.other_client().post("/api/register", json=body, headers=self.origin())
            self.assertEqual(r.status_code, 422, body)

    def test_registration_closed(self):
        import dataclasses
        app = api.create_app(dataclasses.replace(self.settings, registration=False),
                             connect=self.connect, client_dist=self.dist)
        with TestClient(app, base_url=self.base_url) as c:
            self.assertFalse(c.get("/api/auth").json()["registration"])
            r = self.register("closedout", client=c)
            self.assertEqual((r.status_code, r.json()["detail"]),
                             (403, "New accounts are closed for now."))
            self.register("shutdoor", client=self.other_client())   # the open app still takes one
            r = c.post("/api/sign-in", json={"username": "shutdoor", "password": "long enough"},
                       headers=self.origin())
            self.assertEqual(r.status_code, 204)         # sign-in still works when closed

    def test_registration_throttled_per_address(self):
        for i in range(routes.auth.REGISTER_PER_ADDRESS[0]):
            r = self.register(f"many{i}", client=self.other_client(),
                              **{"X-Forwarded-For": "6.6.6.6, 10.0.0.1"})
            self.assertEqual(r.status_code, 201)
        r = self.register("onemore", client=self.other_client(),
                          **{"X-Forwarded-For": "1.1.1.1, 10.0.0.1"})
        self.assertEqual(r.status_code, 429)            # the proxy's address (last) counts
        r = self.register("another", client=self.other_client(),
                          **{"X-Forwarded-For": "10.0.0.2"})
        self.assertEqual(r.status_code, 201)

    def test_sign_in(self):
        self.register("signme", client=self.other_client())
        r = self.client.post("/api/sign-in", json={"username": " SignMe ", "password": "long enough"},
                             headers=self.origin())
        self.assertEqual(r.status_code, 204)
        self.assertIn("Secure", r.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/me").json()["username"], "signme")
        c = self.other_client()
        for name, pw in (("signme", "wrong one!"), ("ghost", "long enough")):
            r = c.post("/api/sign-in", json={"username": name, "password": pw}, headers=self.origin())
            self.assertEqual((r.status_code, r.json()["detail"]),
                             (400, "Wrong username or password."))
            self.assertNotIn("set-cookie", r.headers)

    def test_sign_in_throttled_per_username(self):
        self.register("target", client=self.other_client())
        c = self.other_client()
        body = {"username": "target", "password": "wrong guess"}
        for _ in range(routes.auth.LOGIN_PER_NAME[0]):
            self.assertEqual(c.post("/api/sign-in", json=body, headers=self.origin()).status_code, 400)
        body["password"] = "long enough"
        r = c.post("/api/sign-in", json=body, headers=self.origin())
        self.assertEqual(r.status_code, 429)           # even the right password waits
        r = c.post("/api/sign-in", json={"username": "other", "password": "x" * 9},
                   headers=self.origin())
        self.assertEqual(r.status_code, 400)           # another username isn't blocked

    def test_throttle_window_slides(self):
        now = [0.0]
        t = api.Throttle(2, 10, clock=lambda: now[0])
        t.hit("a"); t.hit("a")
        self.assertTrue(t.full("a"))
        self.assertFalse(t.full("b"))
        now[0] = 10.5
        self.assertFalse(t.full("a"))
        self.assertEqual(t.hits, {})

    def test_change_password_and_first_password_after_reset(self):
        with self.subTest("change"):
            self.register("mover")
            r = self.client.post("/api/password", json={"current": "nope nope", "new": "brand new pw"},
                                 headers=self.origin())
            self.assertEqual((r.status_code, r.json()["detail"]),
                             (400, "Your current password isn't right."))
            r = self.client.post("/api/password", json={"current": "long enough", "new": "brand new pw"},
                                 headers=self.origin())
            self.assertEqual(r.status_code, 204)
            self.assertEqual(self.client.get("/api/me").status_code, 200)   # still signed in here
            r = self.other_client().post("/api/sign-in", json={"username": "mover",
                                         "password": "brand new pw"}, headers=self.origin())
            self.assertEqual(r.status_code, 204)
        with self.subTest("first after a reset"):
            client = self.other_client()
            self.make_user("resetme")
            link = committed(auth.reset_link, self.conn, self.settings, "resetme")
            r = client.post("/api/link/redeem", data={"token": token_of(link.url)},
                            headers=self.origin(), follow_redirects=False)
            self.assertEqual(r.status_code, 303)
            self.assertFalse(client.get("/api/me").json()["has_password"])
            r = client.post("/api/password", json={"new": "set at last"}, headers=self.origin())
            self.assertEqual(r.status_code, 204)
            self.assertTrue(client.get("/api/me").json()["has_password"])

    def test_link_get_does_not_redeem(self):
        user_id, _ = self.make_user()
        t = token_of(committed(auth.device_link, self.conn, self.settings, user_id).url)
        for _ in range(2):
            r = self.client.get(f"/link/{t}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("<title>Sign in to HarmonicFitness</title>", r.text)
            self.assertIn('action="/api/link/redeem"', r.text)
            self.assertIn(t, r.text)
            self.assertNotIn("<script", r.text.lower())
            self.assertEqual(r.headers["cache-control"], "no-store")
            self.assertEqual(r.headers["x-frame-options"], "DENY")
            # not no-referrer: with it a browser sends "Origin: null" on the form's POST
            self.assertEqual(r.headers["referrer-policy"], "same-origin")
        used = self.conn.execute("select used_at from sign_in_links where user_id = %s",
                                 (user_id,)).fetchall()
        self.conn.rollback()
        self.assertEqual(used, [(None,)])
        self.assertNotIn("wt_session", self.client.cookies)

    def test_link_redeem(self):
        user_id, _ = self.make_user()
        t = token_of(committed(auth.device_link, self.conn, self.settings, user_id).url)
        r = self.client.post("/api/link/redeem", data={"token": t}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual((r.status_code, r.headers["location"]), (303, "/"))
        self.assertIn("HttpOnly", r.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        r = self.client.post("/api/link/redeem", data={"token": t}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 410)
        r = self.client.post("/api/link/redeem", json={"token": "nope"}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 410)
        self.assertNotIn("nope", r.text)
        for kw in ({"json": {}}, {"json": {"token": 5}}, {"data": {}}, {"content": b"{bad"}):
            with self.subTest(no_token=kw):
                r = self.client.post("/api/link/redeem", headers=self.origin(), **kw)
                self.assertIn(r.status_code, (400, 410), kw)

    def test_csrf_origin_must_match(self):
        self.register("csrf", client=self.other_client())
        body = {"username": "csrf", "password": "long enough"}
        for headers in ({}, {"Origin": "https://evil.test"}, {"Origin": "null"},
                        {"Referer": "https://evil.test/link/x"},
                        {"Origin": "http://wt.test"}):
            for path in ("/api/sign-in", "/api/register", "/api/link/redeem"):
                r = self.client.post(path, json=body, headers=headers, follow_redirects=False)
                self.assertEqual(r.status_code, 403, (path, headers))
        # a Referer of our own origin counts when Origin is absent
        r = self.client.post("/api/sign-in", json=body, headers={"Referer": f"{BASE}/"})
        self.assertEqual(r.status_code, 204)
        r = self.client.post("/api/sign-out", headers={"Origin": "https://evil.test"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/me").status_code, 200)

    def test_sign_out(self):
        self.signed_in()
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        cookie = self.client.cookies["wt_session"]
        r = self.client.post("/api/sign-out", headers=self.origin())
        self.assertEqual(r.status_code, 204)
        self.assertIn("wt_session=", r.headers["set-cookie"])
        self.client.cookies.set("wt_session", cookie)
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_device_link_needs_session(self):
        r = self.client.post("/api/device-link", headers=self.origin())
        self.assertEqual(r.status_code, 401)
        user_id, _ = self.signed_in()
        r = self.client.post("/api/device-link", headers=self.origin())
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["url"].startswith(f"{BASE}/link/"))
        expires = datetime.datetime.fromisoformat(body["expires_at"])
        left = (expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        self.assertTrue(9 * 60 < left <= 10 * 60, left)
        other = self.other_client()
        r = other.post("/api/link/redeem", data={"token": token_of(body["url"])},
                       headers=self.origin(), follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        me = self.conn.execute("select username from users where id = %s", (user_id,)).fetchone()[0]
        self.conn.rollback()
        self.assertEqual(other.get("/api/me").json()["username"], me)

    def test_security_headers(self):
        for path in ("/api/me", "/", "/link/x", "/api/auth"):
            r = self.client.get(path)
            self.assertEqual(r.headers["x-content-type-options"], "nosniff", path)
            self.assertEqual(r.headers["x-frame-options"], "DENY", path)
            self.assertEqual(r.headers["x-robots-tag"], "noindex", path)
        self.assertEqual(self.client.get("/api/me").headers["referrer-policy"], "same-origin")
        self.assertIn('<meta name="robots" content="noindex">', self.client.get("/link/x").text)


class LocalCookie(ApiCase):
    base_url = "http://localhost:8000"

    def test_cookie_not_secure_and_no_hsts_on_localhost(self):
        r = self.client.post("/api/register", json={"username": "local", "password": "long enough"},
                             headers=self.origin())
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("Secure", r.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        self.assertNotIn("strict-transport-security", self.client.get("/healthz").headers)


class Hsts(ApiCase):
    def test_https_asks_browsers_to_keep_to_it(self):
        self.assertEqual(self.client.get("/healthz").headers["strict-transport-security"], "max-age=31536000")


class Api(ApiCase):
    def test_post_job_validates_shape(self):
        self.signed_in()
        good = {"kind": "brief", "goal": "strength", "minutes": 20, "preset": "bodyweight",
                "today": today()}
        for bad in ({**good, "kind": "build"}, {**good, "minutes": "20"},
                    {**good, "today": "27/10/2026"}, {**good, "extra": 1},
                    {k: v for k, v in good.items() if k != "goal"}):
            r = self.client.post("/api/jobs", json=bad, headers=self.origin())
            self.assertEqual(r.status_code, 422, bad)
        r = self.client.post("/api/jobs", json=good, headers=self.origin())
        self.assertEqual(r.status_code, 202)
        job_id = r.json()["id"]
        user_id = self.conn.execute("select user_id from jobs where id = %s", (job_id,)).fetchone()[0]
        uk = store.user_key(self.conn, self.settings, user_id)
        self.assertEqual(jobs.args(self.conn, uk, job_id),
                         {"goal": "strength", "minutes": 20, "preset": "bodyweight", "today": today()})
        self.conn.rollback()

    def test_queue_cap(self):
        self.signed_in()
        body = {"kind": "brief", "goal": "strength", "minutes": 20, "preset": "bodyweight",
                "today": today()}
        for _ in range(3):
            self.assertEqual(self.client.post("/api/jobs", json=body, headers=self.origin())
                             .status_code, 202)
        r = self.client.post("/api/jobs", json=body, headers=self.origin())
        self.assertEqual(r.status_code, 429)

    def test_other_users_job_is_404(self):
        _, uk_a = self.make_user()
        job = enqueue(self.conn, uk_a, "brief", {"goal": "strength"})
        jobs.event(self.conn, uk_a, job, {"stage": "folder"})
        self.signed_in()
        for path in (f"/api/jobs/{job}", f"/api/jobs/{job}/events", "/api/jobs/999999999",
                     "/api/jobs/999999999/events"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertEqual(self.client.get(f"/api/jobs/{2**70}").status_code, 422)


class Keys(ApiCase):
    def test_keys_and_balances_need_session_and_origin(self):
        with self.subTest("keys"):
            for m, p in (("get", "/api/keys"), ("put", "/api/keys/fish"), ("delete", "/api/keys/fish")):
                kw = {"json": {"key": "abc"}} if m == "put" else {}
                self.assertEqual(getattr(self.client, m)(p, headers=self.origin(), **kw).status_code, 401)
            self.signed_in()
            self.assertEqual(self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}).status_code, 403)
            self.assertEqual(self.client.delete("/api/keys/fish").status_code, 403)
        with self.subTest("balances: a job, one at a time"):
            c = self.other_client()
            self.assertEqual(c.post("/api/balances", headers=self.origin()).status_code, 401)
            _, uk = self.signed_in(c)
            self.assertEqual(c.post("/api/balances").status_code, 403)   # no origin: refused
            first = c.post("/api/balances", headers=self.origin())
            self.assertEqual(first.status_code, 202)
            again = c.post("/api/balances", headers=self.origin())
            self.assertEqual(again.json()["id"], first.json()["id"])   # the one waiting, not another
            self.assertEqual(jobs.status(self.conn, uk, first.json()["id"])["kind"], "balances")
            self.conn.rollback()

    def test_unoffered_provider_is_404(self):
        import dataclasses
        self.signed_in()
        c = TestClient(api.create_app(dataclasses.replace(self.settings, providers=("anthropic",)),
                                      connect=self.connect, client_dist=self.dist), base_url=self.base_url)
        c.cookies.update(self.client.cookies)
        self.assertEqual(c.put("/api/keys/openai", json={"key": "abc123def456abcd"},
                               headers=self.origin()).status_code, 404)
        self.assertEqual(c.delete("/api/keys/openai", headers=self.origin()).status_code, 404)
        self.assertEqual(c.put("/api/writer", json={"service": "openai"}, headers=self.origin()).status_code, 404)

    def test_record_without_asking_is_off_until_turned_on(self):
        _, uk = self.signed_in()
        self.assertIs(self.client.get("/api/me").json()["auto_record"], False)
        self.assertEqual(self.client.put("/api/auto-record", json={"on": True}, headers=self.origin()).status_code, 204)
        self.assertTrue(keystore.auto_record(self.conn, uk))
        self.conn.rollback()
        self.assertIs(self.client.get("/api/me").json()["auto_record"], True)
        for bad in ({"on": "yes"}, {"on": 1}, {}, {"on": True, "more": 1}):
            self.assertEqual(self.client.put("/api/auto-record", json=bad, headers=self.origin()).status_code, 422, bad)
        self.assertEqual(self.client.put("/api/auto-record", json={"on": False}).status_code, 403)   # no Origin
        self.assertEqual(self.client.put("/api/auto-record", json={"on": False}, headers=self.origin()).status_code, 204)
        self.assertFalse(keystore.auto_record(self.conn, uk))
        self.conn.rollback()

    def test_put_key_strips_and_refuses(self):
        user_id, uk = self.signed_in()
        put = lambda svc, key: self.client.put(f"/api/keys/{svc}", json={"key": key},  # noqa: E731
                                               headers=self.origin())
        with self.subTest("listed as set, never shown"):
            self.assertEqual(put("fish", "abc123def456abcd").status_code, 204)
            r = self.client.get("/api/keys")
            fish = next(k for k in r.json() if k["service"] == "fish")
            self.assertTrue(fish["set"])
            self.assertIsNotNone(fish["updated_at"])
            self.assertNotIn("abc123def456abcd", r.text)
        self.assertEqual(put("fish", "abc123def456abcd\n").status_code, 204)
        self.assertEqual(keystore.open_all(self.conn, uk)["fish"], "abc123def456abcd")
        self.conn.rollback()
        r = put("fish", "abc 123")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Fish Audio", r.json()["detail"])
        self.assertNotIn("abc 123", r.text)
        self.assertEqual(put("fish", "a" * 15).status_code, 400)
        self.assertEqual(keystore.open_all(self.conn, uk)["fish"], "abc123def456abcd")   # nothing replaced
        self.conn.rollback()
        self.assertEqual(put("fish", "a" * 16).status_code, 204)
        self.assertEqual(put("fish", "").status_code, 400)
        self.assertEqual(put("fish", "  \n").status_code, 400)
        long = "a" * 1025
        r = put("fish", long)
        self.assertEqual(r.status_code, 422)
        self.assertNotIn(long, r.text)
        r = self.client.put("/api/keys/fish", json={"key": "abc123def456abcd", "x": 1},
                            headers=self.origin())
        self.assertEqual(r.status_code, 422)
        self.assertNotIn("abc123def456abcd", r.text)
        self.assertEqual(put("nope", "abc123def456abcd").status_code, 404)

    def test_keys_are_per_user_and_deleted(self):
        with self.subTest("per user"):
            _, uk_a = self.signed_in()
            self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
            b = self.other_client()
            self.signed_in(b)
            fish = next(k for k in b.get("/api/keys").json() if k["service"] == "fish")
            self.assertFalse(fish["set"])
            self.assertEqual(b.delete("/api/keys/fish", headers=self.origin()).status_code, 204)
            self.assertIn("fish", keystore.open_all(self.conn, uk_a))
            self.conn.rollback()
        with self.subTest("delete"):
            self.signed_in()
            self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
            self.assertEqual(self.client.delete("/api/keys/fish", headers=self.origin()).status_code, 204)
            self.assertEqual(self.client.delete("/api/keys/fish", headers=self.origin()).status_code, 204)
            self.assertEqual(self.client.delete("/api/keys/nope", headers=self.origin()).status_code, 404)
            fish = next(k for k in self.client.get("/api/keys").json() if k["service"] == "fish")
            self.assertFalse(fish["set"])

    def test_engine_bug_is_a_500_and_stores_nothing(self):
        _, uk = self.signed_in()
        keys = enginelib.keys(ROOT)
        quiet = TestClient(self.app, base_url=self.base_url, raise_server_exceptions=False)
        quiet.cookies.update(self.client.cookies)
        with mock.patch.object(keys, "clean_value", side_effect=RuntimeError("boom")):
            r = quiet.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
        self.assertEqual(r.status_code, 500)
        self.assertEqual(keystore.open_all(self.conn, uk), {})

    def gemini_app(self):
        """An app offering Gemini as the language model, whose key is also the Gemini voice's."""
        import dataclasses
        app = api.create_app(dataclasses.replace(self.settings, providers=("google",)), connect=self.connect,
                             client_dist=self.dist)
        c = TestClient(app, base_url=self.base_url)
        c.cookies.update(self.client.cookies)
        return c

    def test_removing_gemini_removes_a_key_stored_before_the_merge(self):
        _, uk = self.signed_in()
        keystore.put(self.conn, uk, "google", "AIzaold123def456abcd")   # the model key, from before 0.25.2
        self.conn.commit()
        c = self.gemini_app()
        self.assertTrue(all(k["set"] for k in c.get("/api/keys").json() if k["service"] == "gemini"))
        self.assertEqual(c.delete("/api/keys/gemini", headers=self.origin()).status_code, 204)
        self.assertEqual(keystore.open_all(self.conn, uk), {})
        self.conn.rollback()
        self.assertFalse(any(k["set"] for k in c.get("/api/keys").json()))

    def test_api_never_opens_keys(self):
        here = os.path.dirname(api.__file__)
        for name in ["api.py"] + [os.path.join("routes", n) for n in os.listdir(os.path.join(here, "routes"))
                                  if n.endswith(".py")]:
            with open(os.path.join(here, name), encoding="utf-8") as f:
                self.assertNotIn("open_all", f.read(), name)


QUESTION = {"questions": [
    {"id": "limits", "prompt": "Anything sore or off today?", "multi": True, "other": True,
     "options": [{"label": "Nothing new", "recommended": True}, {"label": "Knee"}]},
    {"id": "length", "prompt": "Length", "multi": False, "other": False,
     "options": [{"label": "25 min", "recommended": True}, {"label": "30 min"}]}],
    "tool_call_id": "call_1"}


class Conversations(ApiCase):
    def keyed(self, client=None):
        user_id, uk = self.signed_in(client)
        keystore.put(self.conn, uk, "anthropic", "sk-ant-abc123def456abcd")
        self.conn.commit()
        return user_id, uk

    def turn(self, **body):
        return {"today": today(), "now": f"{today()} Wednesday 08:00", **body}

    def start(self, client=None, line="a 20-minute strength workout"):
        r = (client or self.client).post("/api/conversations", json=self.turn(line=line),
                                         headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        return r.json()

    def settle(self, uk, cid, state="waiting", question=QUESTION, job_state="done"):
        """The turn's job ended and the conversation moved to `state` (with `question`)."""
        c = conversations.load(self.conn, uk, cid)
        self.conn.execute("update jobs set state = %s, finished_at = now() where id = %s",
                          (job_state, c.job_id))
        c.state, c.question = state, question
        self.assertTrue(conversations.save(self.conn, uk, c, c.version))
        self.conn.commit()

    def turn_jobs(self, user_id):
        return [r[0] for r in self.conn.execute(
            "select id from jobs where user_id = %s and kind = 'turn' order by id", (user_id,))]

    def test_a_message_with_kit_photos(self):
        """0.83.0: re-saved and kept beside the job until its turn, the count in its args and on the chat line."""
        import base64
        import io
        from PIL import Image
        from webapp import photos
        from webtests.test_photos import GPS, jpeg

        def b64(raw):
            return base64.b64encode(raw).decode()
        _, uk = self.keyed()
        sent = [b64(jpeg(2400, 1800)), b64(jpeg(800, 600, gps=False))]
        r = self.client.post("/api/conversations", json=self.turn(line="Here's my garage.", photos=sent),
                             headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        job_id, cid = r.json()["job_id"], r.json()["id"]
        args = jobs.args(self.conn, uk, job_id)
        self.assertEqual(args["photos"], 2)
        self.assertNotIn(sent[1][:40], json.dumps(args))
        self.assertIsNone(turns.check(args))
        kept = photos.take(self.conn, uk, job_id)
        self.conn.rollback()
        self.assertEqual(len(kept), 2)
        with Image.open(io.BytesIO(kept[0])) as im:
            self.assertEqual(max(im.size), photos.EDGE)
            self.assertNotIn(GPS, im.getexif())
        self.assertEqual(self.client.get(f"/api/conversations/{cid}").json()["lines"][0],
                         {"role": "user", "text": "Here's my garage.", "photos": 2})
        self.settle(uk, cid)
        r = self.client.post(f"/api/conversations/{cid}/messages", json=self.turn(line="And the rack.", photos=[sent[1]]),
                             headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        self.assertEqual(len(photos.take(self.conn, uk, r.json()["job_id"])), 1)
        self.conn.rollback()
        for bad in ([b64(b"not a photo")], [sent[1]] * (photos.MOST + 1)):
            r = self.client.post("/api/conversations", json=self.turn(line="x", photos=bad), headers=self.origin())
            self.assertEqual(r.status_code, 422, r.text)

    def offered(self, chars=2000):
        user_id, uk = self.keyed()
        cid = self.start()["id"]
        c = conversations.load(self.conn, uk, cid)
        self.conn.execute("update jobs set state = 'done', finished_at = now() where id = %s", (c.job_id,))
        c.state, c.offer = "idle", {"draft": "me/workouts/w/w.draft.txt", "name": "Workout", "coach": "Coach Reed",
                                    "chars": chars, "usd": 0.03, "service": "fish", "design": False}
        self.assertTrue(conversations.save(self.conn, uk, c, c.version))
        self.conn.commit()
        return user_id, uk, cid

    def test_record_reserves_todays_allowance_and_refuses_past_it(self):
        with self.subTest("reserved, then queued"):
            user_id, uk, cid = self.offered()
            r = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
            self.assertEqual(r.status_code, 202, r.text)
            job = r.json()["job_id"]
            self.assertEqual(jobs.args(self.conn, uk, job)["record"], True)
            self.assertEqual(spend.used(self.conn, uk, today()), 2000)
            self.conn.rollback()
            c = self.client.get(f"/api/conversations/{cid}").json()
            self.assertEqual((c["state"], c["lines"][-1]["text"], c["offer"]), ("working", "Yes, record it.", None))
            again = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
            self.assertEqual(again.status_code, 409)
        with self.subTest("over the daily allowance"):
            _, uk, cid = self.offered(chars=spend.DEFAULT_DAILY_CHARS + 1)
            r = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
            self.assertEqual(r.status_code, 409)
            self.assertIn("today's allowance", r.json()["detail"])
            self.assertEqual(spend.used(self.conn, uk, today()), 0)
            self.conn.rollback()

    def later_at(self, hours=2.0, offset=-300):
        zone = datetime.timezone(datetime.timedelta(minutes=offset))
        return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).astimezone(zone) \
            .replace(second=0, microsecond=0)

    def planned_for_later(self):
        """A conversation for later whose check-in is done: its plan's estimate saved, as the worker saves it."""
        user_id, uk = self.keyed()
        at = self.later_at()
        r = self.client.post("/api/conversations", json=self.turn(line="a 15-minute workout, at 7:00 AM",
                                                                  start_at=at.isoformat()), headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        cid = r.json()["id"]
        c = conversations.load(self.conn, uk, cid)
        self.assertEqual((c.later["offset"], c.later["local"]), (-300, at.strftime("%Y-%m-%d %A %H:%M")))
        self.conn.execute("update jobs set state = 'done', finished_at = now() where id = %s", (c.job_id,))
        c.state = "idle"
        c.later = dict(c.later, minutes=15, coach="Coach Reed", chars=9750, usd=0.15, ceiling_chars=12000,
                       ceiling_usd=0.18)
        self.assertTrue(conversations.save(self.conn, uk, c, c.version))
        self.conn.commit()
        return user_id, uk, cid, at

    def schedule(self, cid):
        r = self.client.post(f"/api/conversations/{cid}/schedule", json=self.turn(), headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        return r.json()["job_id"]

    def test_schedule_it_queues_the_turn_fifteen_minutes_before_and_cancel_takes_it_back(self):
        _, uk, cid, at = self.planned_for_later()
        later = self.client.get(f"/api/conversations/{cid}").json()["later"]
        self.assertEqual((later["usd"], later["ceiling_usd"], later["coach"]), (0.15, 0.18, "Coach Reed"))
        self.assertNotIn("ceiling_chars", later)
        job = self.schedule(cid)
        due = self.conn.execute("select not_before from jobs where id = %s", (job,)).fetchone()[0]
        self.assertAlmostEqual((at - due).total_seconds(), 15 * 60, delta=5)
        args = jobs.args(self.conn, uk, job)
        self.assertEqual((args["scheduled"], args["offset"]), (True, -300))
        self.assertIn("12,000 characters", args["line"])
        self.assertIsNone(turns.check(args))
        self.conn.rollback()
        claimed = jobs.claim(self.conn)
        self.assertTrue(claimed is None or claimed.id != job)   # not due: no worker takes it
        c = self.client.get(f"/api/conversations/{cid}").json()
        self.assertEqual((c["state"], c["job_id"]), ("scheduled", None))
        self.assertIn("Schedule it for", c["lines"][-1]["text"])
        self.assertEqual(self.client.post(f"/api/conversations/{cid}/messages", json=self.turn(line="hi"),
                                          headers=self.origin()).status_code, 409)   # Cancel first
        self.assertEqual(self.client.post(f"/api/conversations/{cid}/schedule", json=self.turn(),
                                          headers=self.origin()).status_code, 409)
        r = self.client.post(f"/api/conversations/{cid}/cancel", headers=self.origin())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["state"], "idle")
        self.assertEqual(r.json()["lines"][-1]["text"], conversations.CANCELLED)
        self.assertEqual(self.conn.execute("select state, error from jobs where id = %s", (job,)).fetchone(),
                         ("failed", "cancelled"))
        self.conn.rollback()
        self.schedule(cid)   # the plan is kept: it can be scheduled again

    def test_a_time_inside_the_lead_runs_now_and_one_past_a_day_is_refused(self):
        _, uk = self.keyed()
        soon = self.later_at(hours=0.1)
        r = self.client.post("/api/conversations", json=self.turn(start_at=soon.isoformat(), line="a workout"),
                             headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        self.assertIsNone(conversations.load(self.conn, uk, r.json()["id"]).later)
        self.conn.rollback()
        far = self.later_at(hours=30)
        r = self.client.post("/api/conversations", json=self.turn(start_at=far.isoformat(), line="a workout"),
                             headers=self.origin())
        self.assertEqual(r.status_code, 422)

    def test_stop_asks_the_running_job_to_stop(self):
        _, uk = self.keyed()
        started = self.start()
        r = self.client.post(f"/api/conversations/{started['id']}/stop", headers=self.origin())
        self.assertEqual((r.status_code, r.json()), (202, {"stopping": True}))
        self.assertTrue(jobs.stop_requested(self.conn, started["job_id"]))
        other = self.other_client()
        self.signed_in(client=other)
        self.assertEqual(other.post(f"/api/conversations/{started['id']}/stop", headers=self.origin()).status_code, 404)

    def test_needs_session_and_origin(self):
        for path in ("/api/conversations/latest", "/api/conversations/1"):
            self.assertEqual(self.client.get(path).status_code, 401, path)
        for path in ("/api/conversations", "/api/conversations/1/messages"):
            self.assertEqual(self.client.post(path, json={}, headers=self.origin()).status_code,
                             401, path)
        self.keyed()
        self.assertEqual(self.client.post("/api/conversations", json=self.turn(line="hi"))
                         .status_code, 403)

    def test_start_queue_cap(self):
        user_id, uk = self.keyed()
        for _ in range(3):
            self.start()
        r = self.client.post("/api/conversations", json=self.turn(line="hi"), headers=self.origin())
        self.assertEqual(r.status_code, 429)
        self.assertEqual(len(self.turn_jobs(user_id)), 3)
        self.assertEqual(self.conn.execute("select count(*) from conversations where user_id = %s",
                                           (user_id,)).fetchone()[0], 3)
        self.conn.rollback()

    def test_get_never_returns_history(self):
        _, uk = self.keyed()
        self.assertEqual(self.client.get("/api/conversations/latest").status_code, 204)
        body = self.start()
        c = conversations.load(self.conn, uk, body["id"])
        c.history = '[{"secret": "the model\'s history"}]'
        c.plan = {"format": "Straight sets"}
        conversations.save(self.conn, uk, c, c.version)
        self.conn.commit()
        for path in (f"/api/conversations/{body['id']}", "/api/conversations/latest"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            got = r.json()
            stamp = got.pop("updated_at")
            self.assertEqual(got, {"id": body["id"], "state": "working", "job_id": body["job_id"],
                                   "lines": [{"role": "user", "text": "a 20-minute strength workout"}],
                                   "question": None, "plan": {"format": "Straight sets"}, "offer": None,
                                   "later": None})
            when = datetime.datetime.fromisoformat(stamp)
            self.assertIsNotNone(when.tzinfo)
            self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc) - when).total_seconds()), 300)
            self.assertNotIn("history", r.text)
        self.settle(uk, body["id"], state="idle", question=None)
        self.assertIsNone(self.client.get(f"/api/conversations/{body['id']}").json()["job_id"])
        self.assertEqual(self.client.get(f"/api/conversations/{2**70}").status_code, 422)

    def test_a_conversation_whose_job_died_is_healed(self):
        with self.subTest("read: failed, not left working"):
            _, uk = self.keyed()
            for how in ("failed", "done", "gone"):
                with self.subTest(how=how):
                    body = self.start()
                    if how == "gone":
                        self.conn.execute("delete from jobs where id = %s", (body["job_id"],))
                    else:
                        self.conn.execute("update jobs set state = %s where id = %s", (how, body["job_id"]))
                    self.conn.commit()
                    path = f"/api/conversations/{body['id']}" if how != "done" else "/api/conversations/latest"
                    got = self.client.get(path).json()
                    self.assertEqual(got["state"], "failed")
                    self.assertEqual(got["lines"][-1],
                                     {"role": "agent", "text": "That didn't work: interrupted"})
                    c = conversations.load(self.conn, uk, body["id"])
                    self.assertEqual(c.state, "failed")
                    self.conn.rollback()
            live = self.start()
            for state in ("queued", "running"):
                self.conn.execute("update jobs set state = %s where id = %s", (state, live["job_id"]))
                self.conn.commit()
                self.assertEqual(self.client.get(f"/api/conversations/{live['id']}").json()["state"],
                                 "working")
        with self.subTest("a message heals it before it begins"):
            user_id, uk = self.keyed()
            body = self.start()
            self.conn.execute("update jobs set state = 'failed', error = 'interrupted' where id = %s",
                              (body["job_id"],))
            self.conn.commit()
            r = self.client.post(f"/api/conversations/{body['id']}/messages",
                                 json=self.turn(line="try again"), headers=self.origin())
            self.assertEqual(r.status_code, 202, r.text)
            c = conversations.load(self.conn, uk, body["id"])
            self.assertEqual(c.state, "working")
            self.assertEqual([ln["text"] for ln in c.lines],
                             ["a 20-minute strength workout", "That didn't work: interrupted", "try again"])
            self.conn.rollback()
        with self.subTest("a scheduled workout whose job died"):
            _, uk, cid, _ = self.planned_for_later()
            job = self.schedule(cid)
            self.conn.execute("update jobs set state = 'failed', error = 'interrupted' where id = %s", (job,))
            self.conn.commit()
            self.assertEqual(self.client.get(f"/api/conversations/{cid}").json()["state"], "failed")

    def test_message_while_working_is_409(self):
        user_id, uk = self.keyed()
        body = self.start()
        r = self.client.post(f"/api/conversations/{body['id']}/messages",
                             json=self.turn(line="and also"), headers=self.origin())
        self.assertEqual((r.status_code, r.json()["detail"]), (409, "Still working on the last message."))
        self.assertEqual(self.turn_jobs(user_id), [body["job_id"]])
        self.settle(uk, body["id"], state="idle", question=None)
        for bad in (self.turn(line=""), self.turn(line="  "), self.turn(line="hi", now="noon")):
            r = self.client.post(f"/api/conversations/{body['id']}/messages", json=bad,
                                 headers=self.origin())
            self.assertEqual(r.status_code, 422, bad)
        r = self.client.post(f"/api/conversations/{body['id']}/messages",
                             json=self.turn(line="and also"), headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        job = r.json()["job_id"]
        self.assertEqual(set(r.json()), {"job_id"})
        self.assertEqual(self.turn_jobs(user_id), [body["job_id"], job])
        self.assertEqual(jobs.args(self.conn, uk, job)["line"], "and also")
        c = conversations.load(self.conn, uk, body["id"])
        self.assertEqual((c.state, c.job_id, c.lines[-1]),
                         ("working", job, {"role": "user", "text": "and also"}))
        self.conn.rollback()

    def test_the_model_history_is_its_owner_s_alone(self):
        _, uk = self.keyed()
        cid = self.start()["id"]
        self.assertEqual(self.client.get(f"/api/conversations/{cid}/history").json(), {"id": cid, "history": []})
        c = conversations.load(self.conn, uk, cid)
        c.history = '[{"kind": "request", "parts": []}]'
        self.assertTrue(conversations.save(self.conn, uk, c, c.version))
        self.conn.commit()
        self.assertEqual(self.client.get(f"/api/conversations/{cid}/history").json(),
                         {"id": cid, "history": [{"kind": "request", "parts": []}]})
        self.assertNotIn("history", self.client.get(f"/api/conversations/{cid}").json())   # the page never sees it
        other = self.other_client()
        self.signed_in(other)
        self.assertEqual(other.get(f"/api/conversations/{cid}/history").status_code, 404)
        self.assertEqual(self.client.get("/api/conversations/999999999/history").status_code, 404)

    def test_other_users_conversation_is_404(self):
        _, uk_a = self.make_user()
        cid = conversations.create(self.conn, uk_a, "mine")
        c = conversations.load(self.conn, uk_a, cid)
        c.state, c.question = "waiting", QUESTION
        conversations.save(self.conn, uk_a, c, c.version)
        self.conn.commit()
        user_id, _ = self.keyed()
        self.assertEqual(self.client.get(f"/api/conversations/{cid}").status_code, 404)
        self.assertEqual(self.client.get("/api/conversations/latest").status_code, 204)
        for path, body in ((f"/api/conversations/{cid}/messages", self.turn(line="hi")),
                           ("/api/conversations/999999999/messages", self.turn(line="hi"))):
            r = self.client.post(path, json=body, headers=self.origin())
            self.assertEqual(r.status_code, 404, path)
        self.assertEqual(self.turn_jobs(user_id), [])
        self.assertEqual(conversations.load(self.conn, uk_a, cid).state, "waiting")
        self.conn.rollback()


def zip_of(entries: dict) -> bytes:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in entries.items():
            z.writestr(name, body)
    return buf.getvalue()


class Import(ApiCase):
    FOLDER = {"me/profile.md": "+++\nschema = 6\n+++\nmine\n", "me/log.md": "log", "me/.env": "FISH_AUDIO_API_KEY=x",
              "me/workouts/a/a.mp3": "audio", "me/workouts/.audio-cache/c.wav": "c", "me/.backup-1/profile.md": "old",
              "me/.git/config": "g", "__MACOSX/me/._profile.md": "junk", "me/coaches/c/persona.md": "coach"}

    def test_import_replaces_the_starter_files_and_refuses_a_bad_zip(self):
        with self.subTest('replaces the starter files'):
            user_id, uk = self.signed_in()
            r = self.client.post("/api/import", content=zip_of(self.FOLDER),
                                 headers={**self.origin(), "Content-Type": "application/zip"})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json(), {"imported": 3, "left_out": 6})
            files = store.read_all(self.conn, uk)
            self.conn.rollback()
            self.assertEqual(files["profile.md"][1], b"+++\nschema = 6\n+++\nmine\n")
            self.assertNotIn(".env", files)
        with self.subTest('a bad zip is 400'):
            self.signed_in()
            r = self.client.post("/api/import", content=b"nope", headers=self.origin())
            self.assertEqual((r.status_code, r.json()["detail"]), (400, "That isn't a ZIP file."))

    def test_reads_only_the_folder_from_a_zip(self):
        with self.subTest('the folder, the rest left out'):
            files, left_out = folder.folder_from_zip(zip_of(self.FOLDER))
            self.assertEqual(sorted(files), ["coaches/c/persona.md", "log.md", "profile.md"])
            self.assertEqual(left_out, 6)
            self.assertNotIn(".env", files)
        with self.subTest('files at the top'):
            files, _ = folder.folder_from_zip(zip_of({"profile.md": "p", "health.md": "h"}))
            self.assertEqual(sorted(files), ["health.md", "profile.md"])
        with self.subTest('not a folder'):
            for data in (b"not a zip", zip_of({"notes.txt": "x"}), zip_of({"../profile.md": "x"})):
                with self.assertRaises(ValueError):
                    folder.folder_from_zip(data)

    def test_import_needs_session_and_origin(self):
        self.assertEqual(self.client.post("/api/import", content=b"x", headers=self.origin()).status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.post("/api/import", content=zip_of(self.FOLDER)).status_code, 403)


class BodyLimit(ApiCase):
    """No body over its route's limit is read into memory (0.76.0)."""

    def test_a_body_within_the_limit_reaches_the_route_whole(self):
        with self.subTest('a sign-in link'):
            user_id, _ = self.make_user()
            t = token_of(committed(auth.device_link, self.conn, self.settings, user_id).url)
            r = self.client.post("/api/link/redeem", content=f"token={t}".encode(), follow_redirects=False,
                                 headers={**self.origin(), "Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(r.status_code, 303)
        with self.subTest('the largest sync read'):
            self.signed_in()
            paths = [f"workouts/{i:03d}/" + "a" * 380 + ".md" for i in range(500)]
            r = self.client.post("/api/sync/read", json={"paths": paths}, headers=self.origin())
            self.assertEqual(r.status_code, 200, r.text)

    def test_a_body_over_the_limit_is_refused_before_the_route(self):
        with self.subTest('declared length'):
            r = self.client.post("/api/link/redeem", content=b"x" * 70_000, headers=self.origin())
            self.assertEqual((r.status_code, r.json()["detail"], r.json()["error"]["code"]),
                             (413, "That request is too large.", "too_large"))
            self.assertEqual(r.headers["x-content-type-options"], "nosniff")
        with self.subTest('chunked'):
            def chunks():
                for _ in range(20):
                    yield b"x" * 10_000
            r = self.client.post("/api/link/redeem", content=chunks(), headers=self.origin())
            self.assertEqual(r.status_code, 413)

    def test_the_import_keeps_its_own_words(self):
        self.signed_in()
        r = self.client.post("/api/import", content=b"x" * (folder.IMPORT_MAX_ZIP + 1), headers=self.origin())
        self.assertEqual((r.status_code, r.json()["detail"]), (413, "That ZIP is over 10 MB."))


class Errors(ApiCase):
    """Every refusal in one shape, and an unexpected error never shows what it held (0.76.0)."""

    def test_one_shape_and_an_unexpected_error_says_nothing_it_held(self):
        with self.subTest('each refusal has the same shape'):
            for r, status, code in ((self.client.get("/api/me"), 401, "not_signed_in"),
                                    (self.client.get("/api/nothing-here"), 404, "not_found"),
                                    (self.client.post("/api/sign-in", json={"username": 1}, headers=self.origin()),
                                     422, "invalid"),
                                    (self.client.post("/api/sign-in", json={}), 403, "forbidden")):
                with self.subTest(status=status):
                    self.assertEqual(r.status_code, status)
                    body = r.json()
                    self.assertIn("detail", body)
                    self.assertEqual(body["error"]["code"], code)
                    self.assertIsInstance(body["error"]["message"], str)
        with self.subTest('a 500 says nothing it held'):
            self.signed_in()
            with mock.patch.object(enginelib, "clean_key", side_effect=RuntimeError("sk-the-listener-key-1234")), \
                    mock.patch("sys.stderr") as err:
                r = self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
            self.assertEqual(r.status_code, 500)
            self.assertEqual(r.json()["error"]["code"], "internal")
            logged = "".join(str(c) for c in err.mock_calls)
            self.assertIn("RuntimeError [", logged)
            self.assertNotIn("sk-the-listener-key", logged + r.text)
            self.assertEqual(r.headers["x-content-type-options"], "nosniff")


class Media(ApiCase):
    MP3 = bytes(range(256)) * 40

    def test_keeps_the_three_newest_workouts_and_a_replaced_ones_chunks_go(self):
        with self.subTest('the three newest kept'):
            from webapp import media
            _, uk = self.signed_in()
            sample = self.kept(uk)   # no build: a coach's sample, kept 24 hours
            self.assertIsNotNone(sample["expires_at"])
            made = [media.put(self.conn, uk, f"Workout {n}", self.MP3, build_id=f"b{n}") for n in range(4)]
            self.conn.commit()
            self.assertTrue(all(a["expires_at"] is None for a in made))
            self.assertEqual(self.client.get(f"/api/media/{made[0]['id']}").status_code, 404)   # the oldest went
            for a in made[1:] + [sample]:
                r = self.client.get(f"/api/media/{a['id']}")
                self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers["cache-control"].split("max-age=")[1].isdigit(), True)
            self.assertEqual(sorted(media.by_build(self.conn, uk)), ["b1", "b2", "b3"])
            media.sweep(self.conn)   # a workout's MP3 has no time to pass: the sweep leaves it
            self.assertEqual(sorted(media.by_build(self.conn, uk)), ["b1", "b2", "b3"])
        with self.subTest("a replaced one's chunks go"):
            from webapp import media
            _, uk = self.signed_in()
            big, _ = self.chunked(uk)
            for n in range(3):
                media.put(self.conn, uk, f"Workout {n}", self.MP3, build_id=f"n{n}")
            self.conn.commit()
            self.assertEqual(self.conn.execute("select count(*) from media_chunks where media_id = %s",
                                               (big["id"],)).fetchone()[0], 0)
            self.assertEqual(self.conn.execute("select count(*) from media_chunks c join media m on m.id = c.media_id "
                                               "where m.user_id = %s", (uk.user_id,)).fetchone()[0], 3)
            self.conn.rollback()

    def kept(self, uk, body=None):
        from webapp import media
        audio = media.put(self.conn, uk, "Workout 2026-10-28 Mobility 5 min", body or self.MP3)
        self.conn.commit()
        return audio

    def test_another_users_or_expired_or_unknown_is_404(self):
        from webapp import media
        _, uk = self.signed_in()
        audio = self.kept(uk)
        other = self.other_client()
        self.signed_in(client=other)
        self.assertEqual(other.get(f"/api/media/{audio['id']}").status_code, 404)
        self.assertEqual(self.client.get("/api/media/not-a-uuid").status_code, 404)
        self.conn.execute("update media set expires_at = now() - interval '1 minute' where id = %s", (audio["id"],))
        self.conn.commit()
        self.assertEqual(self.client.get(f"/api/media/{audio['id']}").status_code, 404)
        self.assertEqual(media.sweep(self.conn), 1)

    def test_needs_a_session(self):
        self.assertEqual(self.client.get("/api/media/00000000-0000-0000-0000-000000000000").status_code, 401)

    def test_sealed_at_rest(self):
        """In chunks since 0.77.0: each sealed, none in plain."""
        _, uk = self.signed_in()
        self.kept(uk)
        rows = [bytes(b) for (b,) in self.conn.execute("select c.body from media_chunks c join media m on m.id = c.media_id "
                                                       "where m.user_id = %s", (uk.user_id,))]
        self.conn.rollback()
        self.assertTrue(rows)
        self.assertFalse(any(self.MP3[:64] in b for b in rows))

    def chunked(self, uk, size=10_000, chunk=1000):
        from webapp import media
        body = bytes((n * 7) % 251 for n in range(size))
        with mock.patch.object(media, "CHUNK", chunk):
            audio = media.put(self.conn, uk, "Workout", body, build_id="big")
        self.conn.commit()
        return audio, body

    def test_an_mp3_is_kept_in_chunks_and_a_range_opens_only_its_own(self):
        from webapp import media
        _, uk = self.signed_in()
        audio, body = self.chunked(uk)
        self.assertEqual(self.conn.execute("select count(*), min(n), max(n) from media_chunks where media_id = %s",
                                           (audio["id"],)).fetchone(), (10, 0, 9))
        # kept whole too, for one release, so a 0.76.2 web process still plays it during the deploy
        whole = self.conn.execute("select body from media where id = %s", (audio["id"],)).fetchone()[0]
        self.assertEqual(media.crypto.open_(uk.key, bytes(whole), f"{uk.user_id}:media:{audio['id']}".encode()), body)
        self.conn.rollback()
        opened = []
        real = media.crypto.open_

        def counting(key, sealed, aad):
            opened.append(aad)
            return real(key, sealed, aad)
        with mock.patch.object(media.crypto, "open_", counting):
            p = self.client.get(f"/api/media/{audio['id']}", headers={"Range": "bytes=1990-3010"})
        self.assertEqual((p.status_code, p.content), (206, body[1990:3011]))
        self.assertEqual((p.headers["content-range"], p.headers["content-length"]), (f"bytes 1990-3010/{len(body)}", "1021"))
        mine = f"{uk.user_id}:media:{audio['id']}:".encode()
        self.assertEqual(sorted(a[len(mine):] for a in opened if a.startswith(mine)), [b"1", b"2", b"3"])
        whole = self.client.get(f"/api/media/{audio['id']}")
        self.assertEqual((whole.status_code, whole.content, whole.headers["content-length"]), (200, body, "10000"))
        self.assertEqual(media.get(self.conn, uk, audio["id"])[1], body)
        self.assertEqual(self.client.get(f"/api/media/{audio['id']}", headers={"Range": "bytes=-5"}).content, body[-5:])


class Feed(ApiCase):
    MP3 = bytes(range(256)) * 40

    def test_a_token_is_unguessable_and_sealed_at_rest(self):
        with self.subTest('unknown or malformed are 404'):
            for path in ("/feed/" + "a" * 43 + ".xml", "/feed/nope.xml", "/feed/x", "/feed"):
                self.assertEqual(self.client.get(path).status_code, 404, path)
        with self.subTest("a new token is what the route accepts"):
            t = feed._token()
            self.assertRegex(t, f"^{feed.TOKEN}$")
            self.assertIsNone(re.fullmatch(feed.TOKEN, t + "x"))
            self.assertEqual(feed.url("https://example.test/", t), f"https://example.test/feed/{t}.xml")
        with self.subTest('sealed at rest'):
            self.signed_in()
            url = self.feed_url()
            token = url.rsplit("/", 1)[1][:-len(".xml")]
            row = self.conn.execute("select feed_hash, feed_token from users where feed_hash is not null").fetchone()
            self.conn.rollback()
            self.assertNotIn(token.encode(), bytes(row[0]) + bytes(row[1]))

    def test_off_until_turned_on_and_managed_only_with_a_session_and_our_origin(self):
        with self.subTest('off until turned on'):
            self.signed_in()
            self.assertEqual(self.client.get("/api/feed").json(), {"url": None})
            url = self.feed_url()
            self.assertTrue(url.startswith(f"{self.base_url}/feed/") and url.endswith(".xml"))
            self.assertEqual(self.client.get("/api/feed").json(), {"url": url})
        with self.subTest('needs a session and our origin'):
            self.assertEqual(self.other_client().get("/api/feed").status_code, 401)
            self.signed_in()
            self.assertEqual(self.client.post("/api/feed").status_code, 403)
            self.assertEqual(self.client.delete("/api/feed").status_code, 403)

    def feed_url(self) -> str:
        r = self.client.post("/api/feed", headers=self.origin())
        self.assertEqual(r.status_code, 200)
        return r.json()["url"]

    def test_lists_the_kept_workouts_and_plays_them_without_a_session(self):
        from webapp import media
        _, uk = self.signed_in()
        url = self.feed_url()
        made = [media.put(self.conn, uk, f"Workout {n}", self.MP3, build_id=f"b{n}") for n in range(4)]
        sample = media.put(self.conn, uk, "Coach sample", self.MP3)   # not a workout: never in the feed
        self.conn.commit()
        app = self.other_client()   # a podcast app: no cookie
        path = url[len(self.base_url):]
        r = app.get(path)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-type"].startswith("application/rss+xml"))
        self.assertEqual(r.text.count("<item>"), 3)   # the three newest; the oldest went
        self.assertLess(r.text.index("Workout 3"), r.text.index("Workout 1"))
        self.assertNotIn(made[0]["id"], r.text)
        self.assertNotIn(sample["id"], r.text)
        self.assertIn("<itunes:block>Yes</itunes:block>", r.text)
        token = path[len("/feed/"):-len(".xml")]
        ep = app.get(f"/feed/{token}/{made[3]['id']}.mp3")
        self.assertEqual((ep.status_code, ep.content, ep.headers["content-type"]), (200, self.MP3, "audio/mpeg"))
        part = app.get(f"/feed/{token}/{made[3]['id']}.mp3", headers={"Range": "bytes=0-9"})
        self.assertEqual((part.status_code, part.content), (206, self.MP3[:10]))
        self.assertEqual(app.get(f"/feed/{token}/{sample['id']}.mp3").status_code, 404)
        self.assertEqual(app.get(f"/feed/{token}/{made[0]['id']}.mp3").status_code, 404)

    def test_a_new_link_or_turning_it_off_stops_the_old_one(self):
        from webapp import media
        _, uk = self.signed_in()
        old = self.feed_url()[len(self.base_url):]
        audio = media.put(self.conn, uk, "Workout", self.MP3, build_id="b")
        self.conn.commit()
        new = self.feed_url()[len(self.base_url):]
        self.assertNotEqual(old, new)
        self.assertEqual(self.client.get(old).status_code, 404)
        self.assertEqual(self.client.get(f"{old[:-4]}/{audio['id']}.mp3").status_code, 404)
        self.assertEqual(self.client.get(new).status_code, 200)
        self.assertEqual(self.client.delete("/api/feed", headers=self.origin()).status_code, 204)
        self.assertEqual(self.client.get(new).status_code, 404)
        self.assertEqual(self.client.get("/api/feed").json(), {"url": None})

    def test_another_users_workout_isnt_in_my_feed(self):
        from webapp import media
        self.signed_in()
        url = self.feed_url()
        token = url[len(self.base_url) + len("/feed/"):-len(".xml")]
        _, other = self.make_user()
        theirs = media.put(self.conn, other, "Theirs", self.MP3, build_id="t")
        self.conn.commit()
        self.assertNotIn(theirs["id"], self.client.get(f"/feed/{token}.xml").text)
        self.assertEqual(self.client.get(f"/feed/{token}/{theirs['id']}.mp3").status_code, 404)


class Account(ApiCase):
    def test_export_is_the_folder_as_a_zip_and_needs_a_session(self):
        with self.subTest('needs a session'):
            self.assertEqual(self.client.get("/api/export").status_code, 401)
        with self.subTest('the folder as a zip'):
            import io
            import zipfile
            self.registered()
            r = self.client.get("/api/export")
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.headers["content-disposition"].startswith('attachment; filename="harmonicfitness-me-'))
            names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
            self.assertIn("me/profile.md", names)
            self.assertFalse(any(n.endswith(".env") for n in names))

    def registered(self, name=None, pw="long enough"):
        import uuid
        name = name or f"leaver{uuid.uuid4().hex[:8]}"
        r = self.client.post("/api/register", json={"username": name, "password": pw}, headers=self.origin())
        self.assertEqual(r.status_code, 201, r.text)
        return self.conn.execute("select id from users where username = %s", (name,)).fetchone()[0]

    def test_delete_needs_the_password_then_removes_everything(self):
        user_id = self.registered()
        self.conn.rollback()
        wrong = self.client.post("/api/account/delete", json={"password": "not it"}, headers=self.origin())
        self.assertEqual(wrong.status_code, 400)
        r = self.client.post("/api/account/delete", json={"password": "long enough"}, headers=self.origin())
        self.assertEqual(r.status_code, 204)
        for table in ("users", "context_files", "user_keys", "conversations", "media", "clip_cache", "spend"):
            column = "id" if table == "users" else "user_id"
            self.assertEqual(self.conn.execute(f"select count(*) from {table} where {column} = %s",
                                               (user_id,)).fetchone()[0], 0, table)
        self.conn.rollback()
        self.assertEqual(self.client.get("/api/me").status_code, 401)

    def test_wrong_passwords_on_a_session_are_throttled(self):
        self.registered()
        self.conn.rollback()
        for _ in range(routes.auth.CONFIRM_PER_USER[0]):
            r = self.client.post("/api/account/delete", json={"password": "not it"}, headers=self.origin())
            self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/account/delete", json={"password": "long enough"}, headers=self.origin())
        self.assertEqual(r.status_code, 429)   # even the right one, until the window passes
        r = self.client.post("/api/password", json={"current": "long enough", "new": "another long one"},
                             headers=self.origin())
        self.assertEqual(r.status_code, 429)
        self.assertEqual(self.client.get("/api/me").status_code, 200)   # the account is still there

    def test_delete_needs_the_origin(self):
        self.registered()
        self.assertEqual(self.client.post("/api/account/delete", json={"password": "long enough"}).status_code, 403)


class CoachSamples(ApiCase):
    def test_a_listed_sample_needs_an_https_address(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "coaches"))
            path = os.path.join(d, "coaches", "samples.json")
            for url, want in (("http://example.com", None), ("https://m.example", "https://m.example/coaches/coach-x/sample.mp3")):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"url": url, "samples": {"coach-x": {}}}, f)
                self.assertEqual(routes.account.stock_sample_url(d, "coach-x"), want)
            self.assertIsNone(routes.account.stock_sample_url(d, "coach-y"))
