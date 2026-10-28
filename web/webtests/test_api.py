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

from webapp import api, auth, config, db, folder, jobs, store, worker  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import MASTER, DBCase  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
BASE = "https://wt.test"


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def token_of(link):
    return link.rsplit("/invite/", 1)[1]


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
        r = client.post("/api/invite/redeem", json={"token": t}, headers=self.origin(),
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
        self.assertEqual((r.status_code, r.json()), (200, {"ok": True}))

    def test_requires_session(self):
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        for path in ("/api/options", "/api/context", "/api/jobs/1", "/api/jobs/1/events"):
            self.assertEqual(self.client.get(path).status_code, 401, path)
        for path in ("/api/jobs", "/api/sign-out", "/api/device-link"):
            self.assertEqual(self.client.post(path, json={}, headers=self.origin()).status_code,
                             401, path)

    def test_invite_get_does_not_redeem(self):
        link = auth.invite(self.conn, self.settings, "page@example.test")
        t = token_of(link)
        for _ in range(2):
            r = self.client.get(f"/invite/{t}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("<title>Sign in to Working Title</title>", r.text)
            self.assertIn('action="/api/invite/redeem"', r.text)
            self.assertIn(t, r.text)
            self.assertNotIn("<script", r.text.lower())
            self.assertEqual(r.headers["cache-control"], "no-store")
            self.assertEqual(r.headers["x-frame-options"], "DENY")
            # not no-referrer: with it a browser sends "Origin: null" on the form's POST
            self.assertEqual(r.headers["referrer-policy"], "same-origin")
        used = self.conn.execute("select used_at from invites i join users u on u.id = i.user_id "
                                 "where u.email = 'page@example.test'").fetchall()
        self.conn.rollback()
        self.assertEqual(used, [(None,)])
        self.assertNotIn("wt_session", self.client.cookies)

    def test_invite_sets_cookie(self):
        t = token_of(auth.invite(self.conn, self.settings, "cookie@example.test"))
        r = self.client.post("/api/invite/redeem", data={"token": t}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(r.headers["location"], "/")
        cookie = r.headers["set-cookie"]
        self.assertTrue(cookie.startswith("wt_session="), cookie)
        for flag in ("HttpOnly", "Path=/", "SameSite=lax", "Max-Age=7776000", "Secure"):
            self.assertIn(flag, cookie)
        self.assertEqual(self.client.get("/api/me").json(),
                         {"app_name": "Working Title", "email": "cookie@example.test"})
        r = self.client.post("/api/invite/redeem", data={"token": t}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 410)
        r = self.client.post("/api/invite/redeem", json={"token": "nope"}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 410)
        self.assertNotIn("nope", r.text)

    def test_redeem_needs_a_token(self):
        for kw in ({"json": {}}, {"json": {"token": 5}}, {"data": {}}, {"content": b"{bad"}):
            r = self.client.post("/api/invite/redeem", headers=self.origin(), **kw)
            self.assertIn(r.status_code, (400, 410), kw)

    def test_csrf_origin_must_match(self):
        t = token_of(auth.invite(self.conn, self.settings, "csrf@example.test"))
        for headers in ({}, {"Origin": "https://evil.test"}, {"Origin": "null"},
                        {"Referer": "https://evil.test/invite/x"},
                        {"Origin": "http://wt.test"}):
            r = self.client.post("/api/invite/redeem", data={"token": t}, headers=headers,
                                 follow_redirects=False)
            self.assertEqual(r.status_code, 403, headers)
        # the invite is still good, and a Referer of our own origin counts when Origin is absent
        r = self.client.post("/api/invite/redeem", data={"token": t},
                             headers={"Referer": f"{BASE}/invite/{t}"}, follow_redirects=False)
        self.assertEqual(r.status_code, 303)
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
        self.assertTrue(body["url"].startswith(f"{BASE}/invite/"))
        expires = datetime.datetime.fromisoformat(body["expires_at"])
        left = (expires - datetime.datetime.now(datetime.timezone.utc)).total_seconds()
        self.assertTrue(9 * 60 < left <= 10 * 60, left)
        other = self.other_client()
        r = other.post("/api/invite/redeem", data={"token": token_of(body["url"])},
                       headers=self.origin(), follow_redirects=False)
        self.assertEqual(r.status_code, 303)
        me = self.conn.execute("select email from users where id = %s", (user_id,)).fetchone()[0]
        self.conn.rollback()
        self.assertEqual(other.get("/api/me").json()["email"], me)

    def test_security_headers(self):
        for path in ("/api/me", "/", "/invite/x"):
            r = self.client.get(path)
            self.assertEqual(r.headers["x-content-type-options"], "nosniff", path)
            self.assertEqual(r.headers["x-frame-options"], "DENY", path)
            self.assertEqual(r.headers["x-robots-tag"], "noindex", path)
        self.assertEqual(self.client.get("/api/me").headers["referrer-policy"], "same-origin")
        self.assertIn('<meta name="robots" content="noindex">', self.client.get("/invite/x").text)


class LocalCookie(ApiCase):
    base_url = "http://localhost:8000"

    def test_cookie_not_secure_on_localhost(self):
        t = token_of(auth.invite(self.conn, self.settings, "local@example.test"))
        r = self.client.post("/api/invite/redeem", data={"token": t}, headers=self.origin(),
                             follow_redirects=False)
        self.assertEqual(r.status_code, 303)
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
