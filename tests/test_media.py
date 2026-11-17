"""The media bucket (tools/bucket.py, tools/media.py): stock samples listed in coaches/samples.json and fetched once
for choosing by ear, checked by SHA-256 and fetched only from https or this computer; an upload never carries the secret. No network:
every request goes to a fake."""
import datetime
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import bucket  # noqa: E402
import errors  # noqa: E402
import media  # noqa: E402
import paths  # noqa: E402
import helpers  # noqa: E402

KEYS = {"AWS_ACCESS_KEY_ID": "tid_test", "AWS_SECRET_ACCESS_KEY": "tsec_not_a_real_secret", "BUCKET_NAME": "b"}


class _Answer(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Samples(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = helpers.home(os.path.join(self.tmp, "me"))
        self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)
        self.body = b"ID3" + b"x" * 500
        self.list = os.path.join(self.tmp, "samples.json")
        media.write_manifest("https://media.example", {"coach-x": {"bytes": len(self.body),
                                                                    "sha256": hashlib.sha256(self.body).hexdigest()}},
                             self.list)
        self.m = media.manifest(self.list)

    def test_a_sample_is_fetched_once_checked_by_sha256_and_only_from_https(self):
        seen = []

        def opener(url, timeout=None):
            seen.append(url)
            return _Answer(self.body)
        path = media.sample_file("coach-x", self.m, opener=opener)
        self.assertEqual(path, os.path.join(paths.PERSONAS, ".samples", "coach-x.mp3"))
        media.sample_file("coach-x", self.m, opener=opener)   # cached, and matching: not fetched again
        self.assertEqual(seen, ["https://media.example/coaches/coach-x/sample.mp3"])
        os.remove(path)
        with self.assertRaises(errors.HarmonicFitnessError):   # a body that doesn't match the list is refused
            media.sample_file("coach-x", self.m, opener=lambda url, timeout=None: _Answer(b"other"))
        self.assertFalse(os.path.exists(path))
        with self.assertRaises(errors.UsageError):
            media.sample_file("coach-y", self.m, opener=opener)
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_MEDIA_URL": "http://example.com"}):
            with self.assertRaises(errors.UsageError):
                media.sample_url("coach-x", self.m)
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_MEDIA_URL": "http://127.0.0.1:9"}):
            self.assertEqual(media.sample_url("coach-x", self.m), "http://127.0.0.1:9/coaches/coach-x/sample.mp3")


class Upload(unittest.TestCase):
    def test_a_request_never_carries_the_secret_nor_goes_out_plain(self):
        now = datetime.datetime(2026, 11, 4, 12, 0, tzinfo=datetime.timezone.utc)
        h = bucket.signed_headers("PUT", "https://fly.storage.tigris.dev/b/demos/v1/jo.mp3", b"abc", "tid_test",
                                  KEYS["AWS_SECRET_ACCESS_KEY"], "audio/mpeg", now=now)
        self.assertTrue(h["authorization"].startswith("AWS4-HMAC-SHA256 Credential=tid_test/20261104/auto/s3/"))
        self.assertNotIn(KEYS["AWS_SECRET_ACCESS_KEY"], json.dumps(h))
        with self.assertRaises(errors.UsageError):
            bucket.put("x", b"", env={})
        with self.assertRaises(errors.UsageError):
            bucket.put("x", b"", env=dict(KEYS, AWS_ENDPOINT_URL_S3="http://fly.storage.tigris.dev"))


if __name__ == "__main__":
    unittest.main()
