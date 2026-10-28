import datetime
import json
import os
import sys
import tempfile
import threading
import time
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi.testclient import TestClient  # noqa: E402

from webapp import api, auth, config, conversations, db, folder, jobs, keystore, spend, store, worker  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import MASTER, DBCase  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
VERSION = open(os.path.join(ROOT, "VERSION")).read().strip()
BASE = "https://wt.test"


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def token_of(link):
    return link.rsplit("/link/", 1)[1]


def sse(lines):
    """Parse an event stream's lines into [(id, event, data)] (comments skipped)."""
    out, cur = [], {}
    for line in lines:
        if line == "":
            if cur:
                out.append((cur.get("id"), cur.get("event", "message"), json.loads(cur["data"])))
            cur = {}
        elif not line.startswith(":"):
            k, _, v = line.partition(": ")
            cur[k] = v
    return out


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
        t = token_of(auth.device_link(self.conn, self.settings, user_id).url)
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
    def test_healthz_needs_nothing(self):
        r = self.client.get("/healthz")
        self.assertEqual((r.status_code, r.json()), (200, {"ok": True, "version": VERSION}))

    def test_version_names_the_commit(self):
        self.assertEqual(api.build_version(ROOT, {"RAILWAY_GIT_COMMIT_SHA": "75da1051234"}), f"{VERSION} (75da105)")
        self.assertEqual(api.build_version(ROOT, {}), VERSION)
        self.assertEqual(api.build_version("/no/such/folder", {}), "unknown")

    def test_requires_session(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        for path in ("/api/options", "/api/context", "/api/jobs/1", "/api/jobs/1/events"):
            self.assertEqual(self.client.get(path).status_code, 401, path)
        for path in ("/api/jobs", "/api/sign-out", "/api/device-link", "/api/password"):
            self.assertEqual(self.client.post(path, json={}, headers=self.origin()).status_code,
                             401, path)

    def register(self, name="newbie", pw="long enough", client=None, **headers):
        client = client or self.client
        return client.post("/api/register", json={"username": name, "password": pw},
                           headers={**self.origin(), **headers})

    def test_auth_info_needs_no_session(self):
        self.assertEqual(self.client.get("/api/auth").json(),
                         {"app_name": "HarmonicFitness", "registration": True, "version": VERSION})

    def test_register_signs_in(self):
        r = self.register("Fresh.One")
        self.assertEqual(r.status_code, 201, r.text)
        cookie = r.headers["set-cookie"]
        self.assertTrue(cookie.startswith("wt_session="), cookie)
        for flag in ("HttpOnly", "Path=/", "SameSite=lax", "Max-Age=7776000", "Secure"):
            self.assertIn(flag, cookie)
        self.assertEqual(self.client.get("/api/me").json(),
                         {"app_name": "HarmonicFitness", "username": "fresh.one",
                          "has_password": True, "version": VERSION})
        self.assertIn("profile.md", [f["path"] for f in self.client.get("/api/context").json()])
        r = self.register("FRESH.ONE", client=self.other_client())
        self.assertEqual((r.status_code, r.json()["detail"]), (409, "That username is taken."))
        r = self.register("pw", "short", client=self.other_client())
        self.assertEqual(r.status_code, 400)
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
        for i in range(api.REGISTER_PER_ADDRESS[0]):
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
        for _ in range(api.LOGIN_PER_NAME[0]):
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

    def test_change_password(self):
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

    def test_first_password_after_reset(self):
        user_id, _ = self.make_user("resetme")
        link = auth.reset_link(self.conn, self.settings, "resetme")
        r = self.client.post("/api/link/redeem", data={"token": token_of(link.url)},
                             headers=self.origin(), follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertFalse(self.client.get("/api/me").json()["has_password"])
        r = self.client.post("/api/password", json={"new": "set at last"}, headers=self.origin())
        self.assertEqual(r.status_code, 204)
        self.assertTrue(self.client.get("/api/me").json()["has_password"])

    def test_link_get_does_not_redeem(self):
        user_id, _ = self.make_user()
        t = token_of(auth.device_link(self.conn, self.settings, user_id).url)
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
        t = token_of(auth.device_link(self.conn, self.settings, user_id).url)
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

    def test_redeem_needs_a_token(self):
        for kw in ({"json": {}}, {"json": {"token": 5}}, {"data": {}}, {"content": b"{bad"}):
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

    def test_cookie_not_secure_on_localhost(self):
        r = self.client.post("/api/register", json={"username": "local", "password": "long enough"},
                             headers=self.origin())
        self.assertEqual(r.status_code, 201)
        self.assertNotIn("Secure", r.headers["set-cookie"])
        self.assertEqual(self.client.get("/api/me").status_code, 200)


class Api(ApiCase):
    def test_options_lists_goals(self):
        self.signed_in()
        body = self.client.get("/api/options").json()
        self.assertIn("strength", body["goals"])
        self.assertIn("bodyweight", body["presets"])
        self.assertEqual(body["minutes"], [10, 15, 20, 25, 30, 45])

    def test_context_lists_names_only(self):
        user_id, uk = self.signed_in()
        store.write_back(self.conn, uk, folder.seed(ROOT), {})
        self.conn.commit()
        body = self.client.get("/api/context").json()
        paths = {f["path"] for f in body}
        self.assertIn("profile.md", paths)
        for f in body:
            self.assertEqual(set(f), {"path", "version", "updated_at"})
            datetime.datetime.fromisoformat(f["updated_at"])

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
        job = jobs.enqueue(self.conn, uk_a, "brief", {"goal": "strength"})
        jobs.event(self.conn, uk_a, job, {"stage": "folder"})
        self.signed_in()
        for path in (f"/api/jobs/{job}", f"/api/jobs/{job}/events", "/api/jobs/999999999",
                     "/api/jobs/999999999/events"):
            self.assertEqual(self.client.get(path).status_code, 404, path)
        self.assertEqual(self.client.get(f"/api/jobs/{2**70}").status_code, 422)

    def test_job_status_and_result(self):
        _, uk = self.signed_in()
        job = jobs.enqueue(self.conn, uk, "brief", {"goal": "strength"})
        self.assertEqual(self.client.get(f"/api/jobs/{job}").json(),
                         {"id": job, "state": "queued", "error": None, "result": None})
        jobs.claim(self.conn)
        jobs.finish(self.conn, uk, job, {"brief_md": "# Today's brief"})
        self.assertEqual(self.client.get(f"/api/jobs/{job}").json(),
                         {"id": job, "state": "done", "error": None,
                          "result": {"brief_md": "# Today's brief"}})

    def read_stream(self, job, headers=None):
        with self.client.stream("GET", f"/api/jobs/{job}/events", headers=headers or {}) as r:
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.headers["content-type"].startswith("text/event-stream"))
            return sse(list(r.iter_lines()))

    def test_events_stream_until_done(self):
        user_id, uk = self.signed_in()
        store.write_back(self.conn, uk, folder.seed(ROOT), {})
        self.conn.commit()
        r = self.client.post("/api/jobs", headers=self.origin(), json={
            "kind": "brief", "goal": "strength", "minutes": 20, "preset": "bodyweight",
            "today": today()})
        job = r.json()["id"]

        def work():
            conn = self.connect()
            try:
                worker.run_one(conn, self.settings, connect=self.connect)
            finally:
                conn.close()
        t = threading.Thread(target=work)
        t.start()
        events = self.read_stream(job)
        t.join()
        self.assertEqual([e[2].get("stage") for e in events[:-1]], ["folder", "brief", "saved"])
        self.assertEqual(events[-1][1:], ("state", {"state": "done", "error": None}))
        ids = [int(e[0]) for e in events[:-1]]
        self.assertEqual(ids, sorted(ids))
        result = self.client.get(f"/api/jobs/{job}").json()["result"]
        self.assertTrue(result["brief_md"].startswith("# Today's brief"))
        # resuming after the second event gives only the third, then the end
        again = self.read_stream(job, {"Last-Event-ID": str(ids[1])})
        self.assertEqual([e[2].get("stage") for e in again[:-1]], ["saved"])
        self.assertEqual(again[-1][1], "state")

    def test_stream_ends_when_job_fails_without_notify(self):
        _, uk = self.signed_in()
        job = jobs.enqueue(self.conn, uk, "brief", {})
        jobs.claim(self.conn)

        def later():
            conn = self.connect()
            try:
                jobs.fail(conn, None, job, "interrupted")   # fail() sends no NOTIFY
            finally:
                conn.close()
        timer = threading.Timer(0.5, later)
        timer.start()
        with mock.patch.object(api, "POLL_EVERY", 0.2):
            events = self.read_stream(job)
        timer.join()
        self.assertEqual(events, [(None, "state", {"state": "failed", "error": "interrupted"})])

    def test_keep_alive(self):
        _, uk = self.signed_in()
        job = jobs.enqueue(self.conn, uk, "brief", {})
        jobs.claim(self.conn)
        def later():
            conn = self.connect()
            jobs.fail(conn, None, job, "x")
            conn.close()
        timer = threading.Timer(1.0, later)
        timer.start()
        with mock.patch.object(api, "KEEP_ALIVE", 0.3), mock.patch.object(api, "POLL_EVERY", 0.1):
            with self.client.stream("GET", f"/api/jobs/{job}/events") as r:
                lines = list(r.iter_lines())
        timer.join()
        self.assertIn(": keep-alive", lines)


class Keys(ApiCase):
    def test_keys_need_session(self):
        for m, p in (("get", "/api/keys"), ("put", "/api/keys/fish"), ("delete", "/api/keys/fish")):
            kw = {"json": {"key": "abc"}} if m == "put" else {}
            self.assertEqual(getattr(self.client, m)(p, headers=self.origin(), **kw).status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}).status_code, 403)
        self.assertEqual(self.client.delete("/api/keys/fish").status_code, 403)

    def test_list_shows_every_service_unset(self):
        self.signed_in()
        body = self.client.get("/api/keys").json()
        self.assertEqual([k["service"] for k in body if k["kind"] == "voice"],
                         list(worker.engine_services(ROOT)))
        for k in body:
            self.assertFalse(k["set"])
            self.assertIsNone(k["updated_at"])

    def test_model_keys_listed_first_and_only_offered(self):
        self.signed_in()
        body = self.client.get("/api/keys").json()
        self.assertEqual([k["service"] for k in body if k["kind"] == "model"], ["anthropic"])
        self.assertEqual(body[0]["service"], "anthropic")
        self.assertEqual(body[0]["name"], "Claude")
        self.assertIn("anthropic", body[0]["key_page"])
        self.assertTrue(all(k["kind"] == "voice" for k in body[1:]))
        self.assertEqual([k["service"] for k in body[1:]], list(worker.engine_services(ROOT)))

    def test_put_model_key(self):
        self.signed_in()
        r = self.client.put("/api/keys/anthropic", json={"key": "sk-ant-abc123def456abcd"}, headers=self.origin())
        self.assertEqual(r.status_code, 204)
        body = self.client.get("/api/keys")
        self.assertTrue(next(k for k in body.json() if k["service"] == "anthropic")["set"])
        self.assertNotIn("sk-ant-abc123def456abcd", body.text)
        r = self.client.put("/api/keys/anthropic", json={"key": "has a space in it 1234"}, headers=self.origin())
        self.assertEqual(r.status_code, 400)
        self.assertIn("That doesn't look like a Claude key", r.json()["detail"])
        self.assertEqual(self.client.delete("/api/keys/anthropic", headers=self.origin()).status_code, 204)

    def test_unoffered_provider_is_404(self):
        self.signed_in()
        self.assertEqual(self.client.put("/api/keys/openai", json={"key": "abc123def456abcd"},
                                         headers=self.origin()).status_code, 404)
        self.assertEqual(self.client.delete("/api/keys/openai", headers=self.origin()).status_code, 404)

    def test_put_then_list(self):
        self.signed_in()
        r = self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
        self.assertEqual(r.status_code, 204)
        r = self.client.get("/api/keys")
        fish = next(k for k in r.json() if k["service"] == "fish")
        self.assertTrue(fish["set"])
        self.assertIsNotNone(fish["updated_at"])
        self.assertNotIn("abc123def456abcd", r.text)

    def test_put_key_strips_and_refuses(self):
        user_id, uk = self.signed_in()
        put = lambda svc, key: self.client.put(f"/api/keys/{svc}", json={"key": key},  # noqa: E731
                                               headers=self.origin())
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

    def test_keys_are_per_user(self):
        _, uk_a = self.signed_in()
        self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
        b = self.other_client()
        self.signed_in(b)
        fish = next(k for k in b.get("/api/keys").json() if k["service"] == "fish")
        self.assertFalse(fish["set"])
        self.assertEqual(b.delete("/api/keys/fish", headers=self.origin()).status_code, 204)
        self.assertIn("fish", keystore.open_all(self.conn, uk_a))

    def test_delete_key(self):
        self.signed_in()
        self.client.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
        self.assertEqual(self.client.delete("/api/keys/fish", headers=self.origin()).status_code, 204)
        self.assertEqual(self.client.delete("/api/keys/fish", headers=self.origin()).status_code, 204)
        self.assertEqual(self.client.delete("/api/keys/nope", headers=self.origin()).status_code, 404)
        fish = next(k for k in self.client.get("/api/keys").json() if k["service"] == "fish")
        self.assertFalse(fish["set"])

    def test_guard_leaves_sys_path_alone(self):
        self.signed_in()
        worker.clean_key(ROOT, "FISH_AUDIO_API_KEY", " x ")
        tools = os.path.abspath(os.path.join(ROOT, "tools"))
        self.assertEqual(sys.path.count(tools), 1)
        self.assertEqual(sys.path[-1], tools)

    def test_engine_bug_is_a_500_and_stores_nothing(self):
        _, uk = self.signed_in()
        keys = worker.engine_keys(ROOT)
        quiet = TestClient(self.app, base_url=self.base_url, raise_server_exceptions=False)
        quiet.cookies.update(self.client.cookies)
        with mock.patch.object(keys, "clean_value", side_effect=RuntimeError("boom")):
            r = quiet.put("/api/keys/fish", json={"key": "abc123def456abcd"}, headers=self.origin())
        self.assertEqual(r.status_code, 500)
        self.assertEqual(keystore.open_all(self.conn, uk), {})

    def test_api_never_opens_keys(self):
        with open(api.__file__) as f:
            self.assertNotIn("open_all", f.read())


QUESTION = {"questions": [
    {"id": "limits", "prompt": "Anything sore or off today?", "multi": True, "other": True,
     "options": [{"label": "Nothing new", "recommended": True}, {"label": "Knee"}]},
    {"id": "length", "prompt": "Length", "multi": False, "other": False,
     "options": [{"label": "25 min", "recommended": True}, {"label": "30 min"}]}],
    "tool_call_id": "call_1"}
GOOD_ANSWER = {"limits": ["Nothing new"], "length": ["25 min"]}


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

    def test_the_offer_shows_without_its_draft_path(self):
        _, _, cid = self.offered()
        offer = self.client.get(f"/api/conversations/{cid}").json()["offer"]
        self.assertEqual(offer, {"name": "Workout", "coach": "Coach Reed", "chars": 2000, "usd": 0.03,
                                 "service": "fish", "design": False})

    def test_record_reserves_todays_allowance_and_queues_the_recording(self):
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

    def test_record_over_the_daily_allowance_is_refused(self):
        _, uk, cid = self.offered(chars=spend.DEFAULT_DAILY_CHARS + 1)
        r = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
        self.assertEqual(r.status_code, 409)
        self.assertIn("today's allowance", r.json()["detail"])
        self.assertEqual(spend.used(self.conn, uk, today()), 0)
        self.conn.rollback()

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

    def test_start_needs_model_key(self):
        user_id, uk = self.signed_in()
        keystore.put(self.conn, uk, "fish", "abc123def456abcd")    # a voice key isn't a model key
        self.conn.commit()
        r = self.client.post("/api/conversations", json=self.turn(line="hi"), headers=self.origin())
        self.assertEqual((r.status_code, r.json()["detail"]),
                         (409, "Add a key for Claude in Keys first."))
        self.assertEqual(self.turn_jobs(user_id), [])
        self.assertIsNone(conversations.latest(self.conn, uk))
        self.conn.rollback()

    def test_start_queues_turn(self):
        user_id, uk = self.keyed()
        body = self.start(line="a 20-minute strength workout")
        self.assertEqual(set(body), {"id", "job_id"})
        self.assertEqual(self.turn_jobs(user_id), [body["job_id"]])
        self.assertEqual(jobs.args(self.conn, uk, body["job_id"]),
                         {"conversation_id": body["id"], "line": "a 20-minute strength workout",
                          "answer": None, "today": today(), "now": f"{today()} Wednesday 08:00"})
        raw = bytes(self.conn.execute("select args from jobs where id = %s",
                                      (body["job_id"],)).fetchone()[0])
        self.assertNotIn(b"strength workout", raw)
        c = conversations.load(self.conn, uk, body["id"])
        self.assertEqual((c.state, c.job_id), ("working", body["job_id"]))
        self.conn.rollback()

    def test_start_validates(self):
        user_id, _ = self.keyed()
        yesterday_week = (datetime.date.fromisoformat(today()) - datetime.timedelta(days=7)).isoformat()
        for bad in (self.turn(line=""), self.turn(line="x" * 2001), self.turn(line="   "),
                    self.turn(line=5), self.turn(line="hi", extra=1), {"line": "hi"},
                    self.turn(line="hi", now="08:00"), self.turn(line="hi", today=yesterday_week),
                    self.turn(line="hi", now=f"{today()} Wednesday 08:00\n"),
                    self.turn(line="hi", now=f"{yesterday_week} Wednesday 08:00")):
            r = self.client.post("/api/conversations", json=bad, headers=self.origin())
            self.assertEqual(r.status_code, 422, bad)
            self.assertNotIn("x" * 50, r.text)
        self.assertEqual(self.turn_jobs(user_id), [])

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
                                   "question": None, "plan": {"format": "Straight sets"}, "offer": None})
            when = datetime.datetime.fromisoformat(stamp)
            self.assertIsNotNone(when.tzinfo)
            self.assertLess(abs((datetime.datetime.now(datetime.timezone.utc) - when).total_seconds()), 300)
            self.assertNotIn("history", r.text)
        self.settle(uk, body["id"], state="idle", question=None)
        self.assertIsNone(self.client.get(f"/api/conversations/{body['id']}").json()["job_id"])
        self.assertEqual(self.client.get(f"/api/conversations/{2**70}").status_code, 422)

    def test_get_heals_a_conversation_whose_job_died(self):
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

    def test_message_heals_before_it_begins(self):
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


class Client(ApiCase):
    def test_not_built(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("isn't built", r.text)

    def test_serves_dist_with_fallback(self):
        os.makedirs(os.path.join(self.dist, "assets"))
        self.addCleanup(__import__("shutil").rmtree, self.dist, True)
        with open(os.path.join(self.dist, "index.html"), "w") as f:
            f.write("<!doctype html><title>WT</title>")
        with open(os.path.join(self.dist, "assets", "app.js"), "w") as f:
            f.write("console.log(1)")
        app = api.create_app(self.settings, connect=self.connect, client_dist=self.dist)
        with TestClient(app, base_url=BASE) as c:
            self.assertIn("<title>WT</title>", c.get("/").text)
            self.assertIn("<title>WT</title>", c.get("/settings/coach").text)
            self.assertEqual(c.get("/assets/app.js").text, "console.log(1)")
            self.assertEqual(c.get("/api/nothing").status_code, 404)
            for path in ("/assets/../../../../../../etc/hosts",
                         "/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/hosts",
                         "/..%2f..%2f..%2f..%2f..%2f..%2fetc/hosts"):
                self.assertNotIn("localhost", c.get(path).text, path)



class Disconnect(ApiCase):
    """A real server (TestClient buffers a whole response, so it can't hang up mid-stream)."""

    def test_client_going_away_closes_the_stream_connection(self):
        import socket

        import httpx
        import uvicorn
        opened = []

        def tracking():
            conn = self.connect()
            opened.append(conn)
            return conn
        app = api.create_app(self.settings, connect=tracking, client_dist=self.dist)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False,
                                               lifespan="off"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 10)
        self.addCleanup(setattr, server, "should_exit", True)
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        user_id, uk = self.make_user()
        session = auth.redeem(self.conn, self.settings,
                              token_of(auth.device_link(self.conn, self.settings, user_id).url))
        job = jobs.enqueue(self.conn, uk, "brief", {})   # stays queued: the stream never ends
        with mock.patch.object(api, "KEEP_ALIVE", 0.1), mock.patch.object(api, "POLL_EVERY", 0.1):
            with httpx.Client(base_url=f"http://127.0.0.1:{port}",
                              cookies={"wt_session": session}) as c:
                with c.stream("GET", f"/api/jobs/{job}/events") as r:
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(next(r.iter_lines()), ": keep-alive")
                    stream_conn = opened[-1]
                    self.assertFalse(stream_conn.closed)
            deadline = time.monotonic() + 5
            while not stream_conn.closed and time.monotonic() < deadline:
                time.sleep(0.05)
        self.assertTrue(stream_conn.closed)
        self.assertTrue(all(conn.closed for conn in opened))


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

    def test_reads_the_folder_and_leaves_out_the_rest(self):
        files, left_out = api.folder_from_zip(zip_of(self.FOLDER))
        self.assertEqual(sorted(files), ["coaches/c/persona.md", "log.md", "profile.md"])
        self.assertEqual(left_out, 6)
        self.assertNotIn(".env", files)

    def test_files_at_the_top_work_too(self):
        files, _ = api.folder_from_zip(zip_of({"profile.md": "p", "health.md": "h"}))
        self.assertEqual(sorted(files), ["health.md", "profile.md"])

    def test_refuses_what_isnt_a_folder(self):
        for data in (b"not a zip", zip_of({"notes.txt": "x"}), zip_of({"../profile.md": "x"})):
            with self.assertRaises(ValueError):
                api.folder_from_zip(data)

    def test_import_replaces_the_starter_files(self):
        user_id, uk = self.signed_in()
        r = self.client.post("/api/import", content=zip_of(self.FOLDER),
                             headers={**self.origin(), "Content-Type": "application/zip"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"imported": 3, "left_out": 6})
        files = store.read_all(self.conn, uk)
        self.conn.rollback()
        self.assertEqual(files["profile.md"][1], b"+++\nschema = 6\n+++\nmine\n")
        self.assertNotIn(".env", files)

    def test_import_needs_session_and_origin(self):
        self.assertEqual(self.client.post("/api/import", content=b"x", headers=self.origin()).status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.post("/api/import", content=zip_of(self.FOLDER)).status_code, 403)

    def test_a_bad_zip_is_400(self):
        self.signed_in()
        r = self.client.post("/api/import", content=b"nope", headers=self.origin())
        self.assertEqual((r.status_code, r.json()["detail"]), (400, "That isn't a ZIP file."))


class Media(ApiCase):
    MP3 = bytes(range(256)) * 40

    def kept(self, uk, body=None):
        from webapp import media
        audio = media.put(self.conn, uk, "Workout 2026-10-28 Mobility 5 min", body or self.MP3)
        self.conn.commit()
        return audio

    def test_plays_downloads_and_ranges(self):
        _, uk = self.signed_in()
        audio = self.kept(uk)
        r = self.client.get(f"/api/media/{audio['id']}")
        self.assertEqual((r.status_code, r.content, r.headers["content-type"]), (200, self.MP3, "audio/mpeg"))
        self.assertTrue(r.headers["cache-control"].startswith("private, max-age="))
        self.assertTrue(r.headers["content-disposition"].startswith("inline"))
        d = self.client.get(f"/api/media/{audio['id']}?download=1")
        self.assertEqual(d.headers["content-disposition"], 'attachment; filename="Workout 2026-10-28 Mobility 5 min.mp3"')
        p = self.client.get(f"/api/media/{audio['id']}", headers={"Range": "bytes=10-19"})
        self.assertEqual((p.status_code, p.content), (206, self.MP3[10:20]))
        self.assertEqual(p.headers["content-range"], f"bytes 10-19/{len(self.MP3)}")
        self.assertEqual(self.client.get(f"/api/media/{audio['id']}", headers={"Range": "bytes=99999-"}).status_code, 416)

    def test_another_users_or_expired_or_unknown_is_404(self):
        from webapp import media
        _, uk = self.signed_in()
        audio = self.kept(uk)
        other = self.other_client()
        self.signed_in(client=other)
        self.assertEqual(other.get(f"/api/media/{audio['id']}").status_code, 404)
        self.assertEqual(self.client.get("/api/media/not-a-uuid").status_code, 404)
        self.conn.execute("update media set expires_at = now() - interval '1 minute'")
        self.conn.commit()
        self.assertEqual(self.client.get(f"/api/media/{audio['id']}").status_code, 404)
        self.assertEqual(media.sweep(self.conn), 1)

    def test_needs_a_session(self):
        self.assertEqual(self.client.get("/api/media/00000000-0000-0000-0000-000000000000").status_code, 401)

    def test_sealed_at_rest(self):
        _, uk = self.signed_in()
        self.kept(uk)
        body = bytes(self.conn.execute("select body from media").fetchone()[0])
        self.conn.rollback()
        self.assertNotIn(self.MP3[:64], body)


class Account(ApiCase):
    def registered(self, name=None, pw="long enough"):
        import uuid
        name = name or f"leaver{uuid.uuid4().hex[:8]}"
        r = self.client.post("/api/register", json={"username": name, "password": pw}, headers=self.origin())
        self.assertEqual(r.status_code, 201, r.text)
        return self.conn.execute("select id from users where username = %s", (name,)).fetchone()[0]

    def test_export_is_the_folder_as_a_zip(self):
        import io
        import zipfile
        self.registered()
        r = self.client.get("/api/export")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["content-disposition"].startswith('attachment; filename="harmonicfitness-me-'))
        names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
        self.assertIn("me/profile.md", names)
        self.assertFalse(any(n.endswith(".env") for n in names))

    def test_export_needs_a_session(self):
        self.assertEqual(self.client.get("/api/export").status_code, 401)

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

    def test_delete_needs_the_origin(self):
        self.registered()
        self.assertEqual(self.client.post("/api/account/delete", json={"password": "long enough"}).status_code, 403)
