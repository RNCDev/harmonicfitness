"""The ready-made workouts (tools/ready.py): a listener's copy is checked against the published list, and a copy that
doesn't match is refused and not kept. No network: every request goes to a fake."""
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import errors  # noqa: E402
import ready  # noqa: E402
import helpers  # noqa: E402


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


BODY = b"ID3" + b"r" * 700


def listing(body=BODY):
    return {"version": 2, "url": "https://media.example", "workouts": [
        {"slug": "ready-core", "order": 5, "title": "Core", "kind": "core workout", "coach": "Coach Priya",
         "minutes": 30, "about": "A strong middle.", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}]}


class Listener(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = helpers.home(os.path.join(self.tmp, "me"))
        self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)

    def test_a_copy_that_doesnt_match_is_refused_and_not_kept(self):
        with self.assertRaises(errors.HarmonicFitnessError):
            ready.file("ready-core", listing(), opener=lambda url, timeout=None: _Answer(b"something else"))
        self.assertFalse(os.path.isdir(ready.local_dir()) and os.listdir(ready.local_dir()))
        with self.assertRaises(errors.UsageError):
            ready.file("ready-nothing", listing())


if __name__ == "__main__":
    unittest.main()
