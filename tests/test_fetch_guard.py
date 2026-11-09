"""On the web client's worker, feeds and topics fetch only public addresses, and youtube only YouTube's (0.76.0)."""
import http.server
import os
import sys
import threading
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import errors  # noqa: E402
import feeds  # noqa: E402
import paths  # noqa: E402
import youtube  # noqa: E402


class _Hello(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - the standard library's name
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"hello")

    def log_message(self, *args):
        pass


class Guard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Hello)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_on_a_computer_this_machine_is_fetched(self):
        with mock.patch.object(paths, "WEB", False):
            self.assertEqual(feeds.fetch(self.url), b"hello")

    def test_on_the_web_a_private_address_is_never_fetched(self):
        with mock.patch.object(paths, "WEB", True):
            for url in (self.url, f"http://localhost:{self.server.server_port}/", "http://app.internal/x",
                        "http://db.flycast/", "http://[::1]:9/", "http://169.254.169.254/latest/"):
                with self.subTest(url=url), self.assertRaises(OSError) as got:
                    feeds.fetch(url)
                reason = getattr(got.exception, "reason", got.exception)
                self.assertIsInstance(reason, feeds.PrivateAddress, url)

    def test_an_address_that_resolves_privately_is_refused(self):
        fake = [(2, 1, 6, "", ("10.0.0.5", 80))]
        with mock.patch.object(paths, "WEB", True), mock.patch.object(feeds.socket, "getaddrinfo", return_value=fake):
            with self.assertRaises(urllib.error.URLError) as got:
                feeds.fetch("http://looks-public.example/")
        self.assertIsInstance(got.exception.reason, feeds.PrivateAddress)


class YouTube(unittest.TestCase):
    def test_on_the_web_only_youtube_addresses_are_opened(self):
        with mock.patch.object(paths, "WEB", True):
            self.assertEqual(youtube.video_url("dQw4w9WgXcQ"), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
            self.assertEqual(youtube.video_url("https://youtu.be/dQw4w9WgXcQ"), "https://youtu.be/dQw4w9WgXcQ")
            with self.assertRaises(errors.UsageError):
                youtube.video_url("http://app.internal:8080/")
        with mock.patch.object(paths, "WEB", False):
            self.assertEqual(youtube.video_url("https://example.org/v"), "https://example.org/v")


if __name__ == "__main__":
    unittest.main()
