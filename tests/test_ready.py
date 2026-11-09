"""The ready-made workouts (tools/ready.py): the plan, the published list, a listener's copy fetched once and checked,
and the maintainer's upload of the whole set. No network: every request goes to a fake."""
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
import demos  # noqa: E402
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
         "minutes": 30, "about": "A strong middle.", "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()},
        {"slug": "ready-full-body", "order": 1, "title": "Full body", "kind": "full-body workout", "coach": "Coach Bea",
         "minutes": 30, "about": "Every major muscle.", "bytes": 1, "sha256": "0" * 64}]}


class Plan(unittest.TestCase):
    def test_the_shipped_plan_has_five_one_of_each_kind(self):
        p = ready.plan()
        kinds = [w["kind"] for w in p["workout"]]
        self.assertEqual(sorted(kinds), sorted(["full-body workout", "strength workout", "cardio workout",
                                                "mobility session", "core workout"]))
        for w in p["workout"]:
            self.assertTrue(w["slug"].startswith("ready-"), w)
            self.assertIn(w["kind"], demos.REQUEST_TYPES)   # the app's own words for a workout
            self.assertTrue(os.path.isfile(os.path.join(demos.home_of(w["slug"]), "profile.md")), w["slug"])
            self.assertIn("--avoid impact", w["brief"])        # low impact: any room, any floor
            for need in ("ask", "coach", "coach_file", "title", "about", "stories"):
                self.assertTrue(w.get(need), (w["slug"], need))
        rules = " ".join(p["writing_rules"])
        self.assertIn("isn't adapted to any injury", rules)
        self.assertIn("made by AI", rules)

    def test_demos_builds_a_ready_made_workout_as_it_does_a_demo(self):
        d = demos.demo("ready-core")
        self.assertEqual((d["coach"], d["minutes"]), ("Coach Priya", 30))
        with self.assertRaises(errors.UsageError):
            demos.demo("ready-nothing")


class Listener(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = helpers.home(os.path.join(self.tmp, "me"))
        self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)

    def test_nothing_published_yet(self):
        empty = ready.published(os.path.join(self.tmp, "none.json"))
        self.assertEqual(empty, {"version": 0, "url": "", "workouts": []})
        self.assertEqual(ready.status(empty), ["No ready-made workouts are published yet."])

    def test_a_copy_is_fetched_once_checked_and_named_for_the_listener(self):
        seen = []

        def opener(url, timeout=None):
            seen.append(url)
            return _Answer(BODY)
        path = ready.file("ready-core", listing(), opener=opener)
        self.assertEqual(os.path.basename(path), "Ready-made 30 min Core with Coach Priya.mp3")
        self.assertEqual(os.path.dirname(path), ready.local_dir())
        self.assertEqual(seen, ["https://media.example/ready/v2/ready-core.mp3"])
        ready.file("ready-core", listing(), opener=opener)   # already here and matching: not fetched again
        self.assertEqual(len(seen), 1)
        self.assertIn("(here)", ready.status(listing())[1])
        self.assertEqual(ready.status(listing())[-1], ready.WARNING)   # the list always says it isn't adapted

    def test_a_copy_that_doesnt_match_is_refused_and_not_kept(self):
        with self.assertRaises(errors.HarmonicFitnessError):
            ready.file("ready-core", listing(), opener=lambda url, timeout=None: _Answer(b"something else"))
        self.assertFalse(os.path.isdir(ready.local_dir()) and os.listdir(ready.local_dir()))
        with self.assertRaises(errors.UsageError):
            ready.file("ready-nothing", listing())


class Upload(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        stack = mock.patch.multiple(ready, staged_dir=lambda: os.path.join(self.tmp, "staged"),
                                    list_path=lambda: os.path.join(self.tmp, "ready.json"),
                                    web_file=lambda: os.path.join(self.tmp, "web.json"))
        stack.start()
        self.addCleanup(stack.stop)

    def test_the_set_is_published_whole(self):
        os.makedirs(ready.staged_dir())
        with open(os.path.join(ready.staged_dir(), "ready-core.mp3"), "wb") as f:
            f.write(BODY)
        with self.assertRaises(errors.HarmonicFitnessError) as e:
            ready.upload(put=lambda *a: "x")
        self.assertIn("ready-full-body", str(e.exception))

    def test_upload_puts_each_then_writes_both_lists(self):
        os.makedirs(ready.staged_dir())
        p = ready.plan()
        for w in p["workout"]:
            with open(os.path.join(ready.staged_dir(), w["slug"] + ".mp3"), "wb") as f:
                f.write(BODY + w["slug"].encode())
        put = []
        done = ready.upload(put=lambda key, body, kind: put.append((key, kind)) or f"https://bucket/{key}")
        self.assertEqual(len(done), 5)
        self.assertTrue(all(k.startswith(f"ready/v{p['version']}/") and t == "audio/mpeg" for k, t in put))
        listed = ready.published(ready.list_path())
        self.assertEqual([w["order"] for w in listed["workouts"]], [1, 2, 3, 4, 5])
        core = ready.find("ready-core", listed)
        self.assertEqual(core["sha256"], hashlib.sha256(BODY + b"ready-core").hexdigest())
        with open(ready.web_file(), encoding="utf-8") as f:
            web = json.load(f)
        self.assertEqual(web["warning"], ready.WARNING)
        self.assertNotIn("sha256", web["workouts"][0])
        self.assertEqual(web["workouts"][0]["audio"],
                         f"https://{p['bucket']}.fly.storage.tigris.dev/ready/v{p['version']}/ready-full-body.mp3")


class Command(unittest.TestCase):
    def test_list_and_json_before_anything_is_published(self):
        out = io.StringIO()
        with mock.patch.object(ready, "published", return_value={"version": 0, "url": "", "workouts": []}), \
                mock.patch("sys.stdout", out):
            self.assertEqual(ready.main([]), 0)
            self.assertEqual(ready.main(["--json"]), 0)
        self.assertIn("No ready-made workouts are published yet.", out.getvalue())
        self.assertIn('"workouts": []', out.getvalue())


if __name__ == "__main__":
    unittest.main()
