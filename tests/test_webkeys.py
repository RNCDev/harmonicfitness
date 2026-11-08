"""keys upload: the keys in me/.env sent to the web app's key store, never printed."""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import keys  # noqa: E402
import webkeys  # noqa: E402
import webpull  # noqa: E402
from fakes import FakeService  # noqa: E402

FISH = "fish-key-NEVERPRINT-1"
ROUTER = "sk-or-NEVERPRINT-2"
CLAUDE = "sk-ant-NEVERPRINT-3"
ACCOUNT = {"HARMONIC_USERNAME": "harmonic1", "HARMONIC_PASSWORD": "pw-NEVERPRINT", "HARMONIC_URL": None}


class StubApp:
    """The web app as webkeys sees it: the keys it holds, and what was sent."""

    def __init__(self, there=(), refuse=None):
        self.there, self.refuse, self.puts, self.calls = set(there), refuse or {}, {}, []

    def sign_in(self, username, password):
        self.calls.append("sign_in")

    def get(self, path, ok=(200,)):
        self.calls.append(("GET", path))
        rows = [{"service": s, "set": s in self.there, "kind": "voice"} for s in keys.SERVICE_VARS]
        rows += [{"service": s, "set": s in self.there, "kind": "model"} for s in ("anthropic", "openai")]
        return 200, json.dumps(rows).encode()

    def _request(self, method, path, body=None):
        service = path.rsplit("/", 1)[-1]
        if service in self.refuse:
            return self.refuse[service], {}, b'{"detail": "That doesn\'t look like a key."}'
        self.puts[service] = body["key"]
        return 204, {}, b""

    _detail = staticmethod(webpull.App._detail)

    def sign_out(self):
        self.calls.append("sign_out")


class Upload(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        with open(self.env, "w", encoding="utf-8") as f:
            f.write(f"FISH_AUDIO_API_KEY={FISH}\nOPENROUTER_API_KEY={ROUTER}\nANTHROPIC_API_KEY={CLAUDE}\n"
                    "GEMINI_API_KEY=\n")
        clean = {v: "" for v in keys.SECRET_VARS}
        for p in (mock.patch.object(keys.paths, "ENV_FILE", self.env), mock.patch.dict(os.environ, clean)):
            p.start()
            self.addCleanup(p.stop)

    def test_sends_what_the_app_lacks_and_keeps_what_it_has(self):
        app = StubApp(there={"fish"})
        got = webkeys.upload(ACCOUNT, app=app)
        self.assertEqual(app.puts, {"openrouter": ROUTER, "anthropic": CLAUDE})
        self.assertEqual((got["sent"], got["kept"]), (["openrouter", "anthropic"], ["fish"]))
        self.assertEqual((app.calls[0], app.calls[-1]), ("sign_in", "sign_out"))
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(webkeys.report(got), errors.OK)
        for secret in (FISH, ROUTER, CLAUDE):
            self.assertNotIn(secret, out.getvalue())
        self.assertIn("openrouter: sent", out.getvalue())

    def test_replace_dry_run_and_only(self):
        app = StubApp(there={"fish"})
        got = webkeys.upload(ACCOUNT, replace=True, dry_run=True, app=app)
        self.assertEqual((app.puts, got["would_send"]), ({}, ["fish", "openrouter", "anthropic"]))
        app = StubApp(there={"fish"})
        webkeys.upload(ACCOUNT, only="fish, openrouter", replace=True, app=app)
        self.assertEqual(app.puts, {"fish": FISH, "openrouter": ROUTER})
        with self.assertRaises(errors.UsageError):
            webkeys.upload(ACCOUNT, only="nope", app=StubApp())

    def test_a_refusal_is_named_and_exit_1(self):
        got = webkeys.upload(ACCOUNT, app=StubApp(refuse={"openrouter": 400}))
        self.assertIn("look like a key", got["refused"]["openrouter"])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(webkeys.report(got), errors.ISSUES)

    def test_needs_the_sign_in_and_sends_nothing_without_keys(self):
        with self.assertRaises(errors.UsageError):
            webkeys.upload({"HARMONIC_USERNAME": "harmonic1"}, app=StubApp())
        with open(self.env, "w", encoding="utf-8") as f:
            f.write("FISH_AUDIO_API_KEY=\n")
        app = StubApp()
        self.assertTrue(webkeys.upload({}, app=app)["none"])
        self.assertEqual(app.calls, [])   # no sign-in when there's nothing to send

    def test_writer_keys_are_scrubbed_like_voice_keys(self):
        import redact
        self.assertNotIn(CLAUDE, redact.scrub(f"oops {CLAUDE}"))


class SameOrigin(unittest.TestCase):
    def test_a_put_carries_the_origin_the_app_requires(self):
        with FakeService(lambda r: (204, {}, b"")) as fake:
            app = webpull.App(fake.url)
            app._request("PUT", "/api/keys/fish", {"key": "x"})
            app._request("GET", "/api/keys")
        self.assertEqual(fake.requests[0].headers.get("origin"), fake.url)
        self.assertIsNone(fake.requests[1].headers.get("origin"))


if __name__ == "__main__":
    unittest.main()
