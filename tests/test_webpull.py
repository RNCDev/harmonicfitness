"""./harmonicfitness pull: signs in to the web app as the listener and saves their files, the latest conversation
and its MP3s under me/web/, against a fake app on this computer. Every credential here is made up."""
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import errors  # noqa: E402
import keys  # noqa: E402
import redact  # noqa: E402
import webpull  # noqa: E402

PASSWORD = "pw-NEVERPRINT-0123456789"


def _zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("me/workouts/2026-10-29-strength-25/a.draft.txt", "@@ 30 | Welcome\nHi.")
        z.writestr("me/../escape.txt", "outside")
        z.writestr("me/.env", "NOPE=1")
    return buf.getvalue()


class FakeApp(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def _send(self, status, body=b"", headers=()):
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _signed_in(self):
        return self.headers.get("Cookie") == "wt_session=tok"

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        FakeApp.seen.append(("POST", self.path, self.headers.get("Origin")))
        if self.path == "/api/sign-in":
            creds = json.loads(body)
            if (creds["username"], creds["password"]) != ("harmonic1", PASSWORD):
                return self._send(400, b'{"detail": "Wrong username or password."}')
            return self._send(204, headers=[("Set-Cookie", "wt_session=tok; Path=/; HttpOnly")])
        if self.path == "/api/sign-out":
            return self._send(204)
        self._send(404)

    def do_GET(self):
        FakeApp.seen.append(("GET", self.path, None))
        if not self._signed_in():
            return self._send(401)
        if self.path == "/api/export":
            return self._send(200, _zip())
        if self.path in ("/api/conversations/latest", "/api/conversations/7"):
            conv = {"id": 7, "state": "idle", "updated_at": "2026-10-29T14:00:00+00:00", "lines": [
                {"role": "user", "text": "a 25 minute workout"},
                {"role": "agent", "text": "", "audio": {"id": "m1", "name": "Strength 25"}},
                {"role": "agent", "text": "", "audio": {"id": "m2", "name": "../Old"}}]}
            return self._send(200, json.dumps(conv).encode())
        if self.path == "/api/media/m1?download=1":
            return self._send(200, b"ID3 fake mp3")
        self._send(404, b'{"detail": "expired"}')


class Pull(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeApp)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        FakeApp.seen = []

    def account(self, password=PASSWORD):
        return {"HARMONIC_USERNAME": "harmonic1", "HARMONIC_PASSWORD": password, "HARMONIC_URL": self.url}

    def test_saves_files_conversation_and_mp3_then_signs_out(self):
        got = webpull.pull(self.account(), dest_root=self.d)
        dest = got["folder"]
        with open(os.path.join(dest, "me", "workouts", "2026-10-29-strength-25", "a.draft.txt")) as f:
            self.assertEqual(f.read(), "@@ 30 | Welcome\nHi.")
        with open(os.path.join(dest, "Strength 25.mp3"), "rb") as f:
            self.assertEqual(f.read(), b"ID3 fake mp3")
        with open(os.path.join(dest, "conversation.json")) as f:
            self.assertEqual(json.load(f)["id"], 7)
        self.assertEqual((got["files"], got["expired"], len(got["mp3s"])), (1, 1, 1))
        everything = [os.path.join(r, n) for r, _, ns in os.walk(self.d) for n in ns]
        self.assertFalse([p for p in everything if p.endswith((".env", "escape.txt"))], everything)
        self.assertEqual(FakeApp.seen[0], ("POST", "/api/sign-in", self.url))   # the app's same-origin rule
        self.assertEqual(FakeApp.seen[-1], ("POST", "/api/sign-out", self.url))

    def test_a_wrong_password_is_exit_4_and_never_shown(self):
        with self.assertRaises(webpull.SignInRefused) as e:
            webpull.pull(self.account("wrong-password-xyz"), dest_root=self.d)
        self.assertEqual(e.exception.exit_code, errors.SERVICE)
        self.assertNotIn("wrong-password-xyz", str(e.exception))
        self.assertEqual(os.listdir(self.d), [])

    def test_missing_credentials_are_named(self):
        with self.assertRaises(errors.UsageError) as e:
            webpull.pull({"HARMONIC_USERNAME": "harmonic1"}, dest_root=self.d)
        self.assertIn("HARMONIC_PASSWORD", str(e.exception))
        self.assertEqual(FakeApp.seen, [])

    def test_only_https_or_this_computer(self):
        self.assertEqual(webpull.base_url(None), "https://harmonicfitness.fly.dev")
        self.assertEqual(webpull.base_url("https://x.test/"), "https://x.test")
        for bad in ("http://x.test", "ftp://x.test", "x.test"):
            with self.assertRaises(errors.UsageError):
                webpull.base_url(bad)

    def test_account_read_from_env_file_and_password_scrubbed(self):
        env = os.path.join(self.d, ".env")
        with open(env, "w") as f:
            f.write(f"HARMONIC_USERNAME=harmonic1\nHARMONIC_PASSWORD={PASSWORD}\n")
        clean = {k: v for k, v in os.environ.items() if k not in keys.ACCOUNT_VARS}
        with mock.patch.dict(os.environ, clean, clear=True):
            self.assertEqual(keys.web_account(env), {"HARMONIC_USERNAME": "harmonic1",
                                                     "HARMONIC_PASSWORD": PASSWORD, "HARMONIC_URL": None})
            with mock.patch.object(keys.paths, "ENV_FILE", env):
                self.assertEqual(redact.scrub(f"oops {PASSWORD}"), "oops <key>")


if __name__ == "__main__":
    unittest.main()
