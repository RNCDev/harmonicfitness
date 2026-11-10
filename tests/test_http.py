"""The engine's web requests: what each module does with a redirect and which base addresses it accepts (pinned before
they moved onto tools/http.py, 0.76.2), and tools/http.py's own pieces."""
import hashlib
import http.server
import os
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (puts tools/ on the path)

import backup  # noqa: E402
import bucket  # noqa: E402
import cloud  # noqa: E402
import errors  # noqa: E402
import media  # noqa: E402
import net  # noqa: E402
import ready  # noqa: E402
import webpull  # noqa: E402

BODY = b'{"private": false}'
SHA = hashlib.sha256(BODY).hexdigest()


class _Redirects(http.server.BaseHTTPRequestHandler):
    """/elsewhere answers 200 with BODY; every other path is a 302 to the server's /elsewhere, or with ?host=localhost
    to the same server named localhost (another host, as a redirect sees it)."""

    def log_message(self, *args):
        pass

    def _answer(self):
        port = self.server.server_address[1]
        if self.path.startswith("/elsewhere"):
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            self.wfile.write(BODY)
            return
        host = "localhost" if "host=localhost" in self.path else "127.0.0.1"
        to = "ftp://127.0.0.1/elsewhere" if "to=ftp" in self.path else f"http://{host}:{port}/elsewhere"
        self.send_response(302)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = do_PUT = do_POST = _answer


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Redirects)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


class Redirects(ServerCase):
    """What each module does with a redirect today."""

    def test_cloud_refuses_a_redirect(self):
        with self.assertRaises(cloud.ServiceError) as cm:
            cloud.request("GET", self.base + "/x", {}, None, service="fish", tries=1)
        self.assertEqual(cm.exception.kind, "unavailable")
        self.assertEqual(cm.exception.status, 302)
        self.assertEqual(str(cm.exception), "Fish Audio: redirected to 127.0.0.1; not followed (HTTP 302)")

    def test_webpull_refuses_a_redirect(self):
        with self.assertRaises(errors.HarmonicFitnessError) as cm:
            webpull.App(self.base)._request("GET", "/api/x")
        self.assertIs(type(cm.exception), errors.HarmonicFitnessError)
        port = self.server.server_address[1]
        self.assertEqual(str(cm.exception), f"The web app redirected to 127.0.0.1:{port}; not followed (HTTP 302). "
                                            "Check HARMONIC_URL.")

    def test_bucket_takes_a_redirect_as_a_refusal(self):
        with mock.patch.object(bucket, "_credentials", return_value=("a", "s", "b", self.base)):
            with self.assertRaises(errors.HarmonicFitnessError) as cm:
                bucket.put("k.mp3", b"x")
        self.assertIs(type(cm.exception), errors.HarmonicFitnessError)
        self.assertEqual(str(cm.exception), "The bucket refused k.mp3: HTTP 302.")

    def test_media_follows_a_redirect(self):
        with tempfile.TemporaryDirectory() as d, helpers.home(d):
            out = media.sample_file("coach-x", m={"url": self.base, "samples": {"coach-x": {"sha256": SHA}}})
            with open(out, "rb") as f:
                self.assertEqual(f.read(), BODY)

    def test_ready_follows_a_redirect(self):
        listing = {"version": 1, "url": self.base, "workouts": [{"slug": "w", "sha256": SHA, "title": "T"}]}
        with tempfile.TemporaryDirectory() as d, helpers.home(d):
            with open(ready.file("w", listing=listing), "rb") as f:
                self.assertEqual(f.read(), BODY)

    def test_backup_follows_a_redirect(self):
        self.assertEqual(backup._api_visibility("o/r", api=self.base + "/repos/"), "PUBLIC")


# each module's answer for a base address: True accepted, False refused. Before 0.76.2 only webpull took http://[::1];
# now each decides with net.allowed_base, so all three agree
BASES = {
    "https://x": (True, True, True),
    "HTTPS://x": (True, True, True),
    "http://localhost:8000": (True, True, True),
    "http://[::1]:8000": (True, True, True),
    "http://example.org": (False, False, False),
    "ftp://x": (False, False, False),
}


class Bases(unittest.TestCase):
    """Which base addresses cloud, webpull and media accept: (cloud, webpull, media)."""

    def accepts(self, url):
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": url, "HARMONICFITNESS_MEDIA_URL": url}):
            out = []
            for call, refusal in ((lambda: cloud.base_url("fish"), cloud.ServiceError),
                                  (lambda: webpull.base_url(url), errors.UsageError),
                                  (lambda: media.base_url({"url": "", "samples": {}}), errors.UsageError)):
                try:
                    call()
                    out.append(True)
                except refusal:
                    out.append(False)
            return tuple(out)

    def test_each_module_accepts_the_bases_it_did(self):
        for url, want in BASES.items():
            self.assertEqual(self.accepts(url), want, url)


class Opener(ServerCase):
    """tools/net.py: the one place the engine opens a web address."""

    def test_never_raises_redirected_with_the_target(self):
        with self.assertRaises(net.Redirected) as cm:
            net.opener("never").open(self.base + "/x", timeout=10)
        self.assertEqual(cm.exception.url, self.base + "/elsewhere")
        self.assertEqual(cm.exception.status, 302)
        self.assertIsInstance(cm.exception, OSError)

    def test_same_host_follows_only_to_the_same_host(self):
        with net.opener("same-host").open(self.base + "/x", timeout=10) as r:
            self.assertEqual(r.read(), BODY)
        with self.assertRaises(net.Redirected):
            net.opener("same-host").open(self.base + "/x?host=localhost", timeout=10)

    def test_web_follows_only_to_http_or_https(self):
        with net.opener("web").open(self.base + "/x?host=localhost", timeout=10) as r:
            self.assertEqual(r.read(), BODY)
        with self.assertRaises(ValueError):
            net.opener("web").open(self.base + "/x?to=ftp", timeout=10)

    def test_any_follows_anywhere(self):
        with net.opener("any").open(self.base + "/x?host=localhost", timeout=10) as r:
            self.assertEqual(r.read(), BODY)

    def test_an_unknown_follow_is_refused(self):
        with self.assertRaises(ValueError):
            net.opener("sometimes")

    def test_a_callers_https_handler_is_the_only_one(self):
        """feeds' vetted handler must be the one that opens https: a second, plain one would go round its check."""
        import urllib.request

        class Mine(urllib.request.HTTPSHandler):
            pass
        o = net.opener("never", Mine(context=net.tls_context()))
        self.assertEqual([type(h) for h in o.handlers if isinstance(h, urllib.request.HTTPSHandler)], [Mine])
        plain = net.opener("never")
        self.assertEqual(len([h for h in plain.handlers if isinstance(h, urllib.request.HTTPSHandler)]), 1)

    def test_tls_context_is_made_once(self):
        import ssl
        self.assertIsInstance(net.tls_context(), ssl.SSLContext)
        self.assertIs(net.tls_context(), net.tls_context())

    def test_read_capped(self):
        import io
        self.assertEqual(net.read_capped(io.BytesIO(b"12345"), 5), b"12345")
        with self.assertRaises(net.TooLarge):
            net.read_capped(io.BytesIO(b"123456"), 5)

    def test_allowed_base(self):
        for url, want in (("https://x", True), ("HTTPS://x", True), ("http://localhost:8000", True),
                          ("http://127.0.0.1:9", True), ("http://[::1]:8000", True), ("http://example.org", False),
                          ("ftp://x", False), ("", False)):
            self.assertEqual(net.allowed_base(url), want, url)


if __name__ == "__main__":
    unittest.main()
