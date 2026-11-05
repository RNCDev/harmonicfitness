"""The media bucket (tools/bucket.py, tools/media.py): stock samples listed in coaches/samples.json and fetched once
for choosing by ear, uploads signed with Signature Version 4, and the demos' clips uploaded with their card. No
network: every request goes to a fake."""
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
import demos  # noqa: E402
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

    def test_a_listed_sample_has_its_address(self):
        self.assertTrue(media.has_sample("coach-x", self.m))
        self.assertFalse(media.has_sample("coach-y", self.m))
        self.assertEqual(media.sample_url("coach-x", self.m), "https://media.example/coaches/coach-x/sample.mp3")
        self.assertEqual(media.manifest(os.path.join(self.tmp, "none.json")), {"url": "", "samples": {}})

    def test_a_sample_is_fetched_once_and_checked(self):
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

    def test_an_override_address_must_be_https_or_this_computer(self):
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_MEDIA_URL": "http://example.com"}):
            with self.assertRaises(errors.UsageError):
                media.sample_url("coach-x", self.m)
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_MEDIA_URL": "http://127.0.0.1:9"}):
            self.assertEqual(media.sample_url("coach-x", self.m), "http://127.0.0.1:9/coaches/coach-x/sample.mp3")


class Upload(unittest.TestCase):
    def test_a_request_is_signed_and_never_carries_the_secret(self):
        now = datetime.datetime(2026, 11, 4, 12, 0, tzinfo=datetime.timezone.utc)
        h = bucket.signed_headers("PUT", "https://fly.storage.tigris.dev/b/demos/v1/jo.mp3", b"abc", "tid_test",
                                  KEYS["AWS_SECRET_ACCESS_KEY"], "audio/mpeg", now=now)
        self.assertEqual(h["x-amz-date"], "20261104T120000Z")
        self.assertEqual(h["x-amz-content-sha256"], hashlib.sha256(b"abc").hexdigest())
        self.assertTrue(h["authorization"].startswith(
            "AWS4-HMAC-SHA256 Credential=tid_test/20261104/auto/s3/aws4_request, "
            "SignedHeaders=content-type;host;x-amz-content-sha256;x-amz-date, Signature="))
        self.assertNotIn(KEYS["AWS_SECRET_ACCESS_KEY"], json.dumps(h))
        again = bucket.signed_headers("PUT", "https://fly.storage.tigris.dev/b/demos/v1/jo.mp3", b"abc", "tid_test",
                                      KEYS["AWS_SECRET_ACCESS_KEY"], "audio/mpeg", now=now)
        self.assertEqual(h, again)   # the same request signs the same way

    def test_put_sends_to_the_bucket_and_returns_the_public_address(self):
        sent = []

        class Opener:
            def open(self, req, timeout=None):
                sent.append(req)
                return _Answer(b"")
        url = bucket.put("demos/v1/jo.mp3", b"ID3", env=KEYS, opener=Opener())
        self.assertEqual(url, "https://b.fly.storage.tigris.dev/demos/v1/jo.mp3")
        self.assertEqual((sent[0].full_url, sent[0].get_method()), ("https://fly.storage.tigris.dev/b/demos/v1/jo.mp3", "PUT"))

    def test_missing_keys_or_a_plain_endpoint_send_nothing(self):
        with self.assertRaises(errors.UsageError):
            bucket.put("x", b"", env={})
        with self.assertRaises(errors.UsageError):
            bucket.put("x", b"", env=dict(KEYS, AWS_ENDPOINT_URL_S3="http://fly.storage.tigris.dev"))


class DemoUpload(unittest.TestCase):
    def test_every_staged_clip_and_its_card_go_up_together(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        with helpers.home(os.path.join(tmp, "me")), mock.patch.object(paths, "DEMOS", os.path.join(tmp, "demos")):
            os.makedirs(demos.clips_dir())
            with open(os.path.join(demos.clips_dir(), "bo.mp3"), "wb") as f:
                f.write(b"ID3bo")
            m = {"version": 2, "demo": [{"slug": "ann", "order": 1}, {"slug": "bo", "order": 2, "ask": "Push me.",
                                                                        "clip": {"story": "number"}}]}
            put = mock.Mock(side_effect=lambda key, body, kind: f"https://b/{key}")
            with mock.patch.object(demos, "manifest", return_value=m):
                done = demos.upload(put=put)
        self.assertEqual([k for k, _ in done], ["demos/v2/bo.mp3", "demos/v2/demos.json"])
        cards = json.loads(put.call_args_list[-1].args[1])
        self.assertEqual(cards["version"], 2)
        self.assertEqual([c["slug"] for c in cards["demos"]], ["bo"])   # only demos with a clip
        self.assertEqual((cards["demos"][0]["ask"], cards["demos"][0]["audio"]), ("Push me.", "https://b/demos/v2/bo.mp3"))


if __name__ == "__main__":
    unittest.main()
