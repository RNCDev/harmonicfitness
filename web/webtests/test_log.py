"""The worker's failure lines say where, never what was in hand (0.76.0)."""
import io
import os
import sys
import unittest
from contextlib import redirect_stderr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import log  # noqa: E402


def _inner(words):
    raise ValueError(words)


def _outer(words):
    _inner(words)


class Failure(unittest.TestCase):
    def test_the_frames_are_logged_and_the_message_never(self):
        try:
            _outer("my left knee hurts, Sam")
        except ValueError as e:
            out = io.StringIO()
            with redirect_stderr(out):
                log.failure("job 7 stopped", e)
        line = out.getvalue()
        self.assertTrue(line.startswith("worker: job 7 stopped: ValueError ["), line)
        self.assertIn("web/webtests/test_log.py:", line)
        self.assertIn("_outer > web/webtests/test_log.py:", line)
        self.assertTrue(line.rstrip().endswith("_inner]"), line)
        self.assertNotIn("knee", line)
        self.assertNotIn("Sam", line)
        self.assertEqual(line.count("\n"), 1)

    def test_an_exception_never_raised_has_no_frames(self):
        out = io.StringIO()
        with redirect_stderr(out):
            log.failure("x", KeyError("secret"))
        self.assertEqual(out.getvalue(), "worker: x: KeyError\n")


if __name__ == "__main__":
    unittest.main()
