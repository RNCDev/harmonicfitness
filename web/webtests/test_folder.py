import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class FolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def put(self, rel, data=b"x"):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)

    def test_round_trip_finds_only_changes(self):
        files = folder.seed(ROOT)
        written = folder.materialize(files, self.root)
        self.assertEqual(set(written), set(files))
        self.put("health.md", b"changed")
        self.put("workouts/x/x.brief.md", b"brief")
        got = folder.harvest(self.root, written)
        self.assertEqual(got, {"health.md": b"changed", "workouts/x/x.brief.md": b"brief"})

    def test_harvest_skips_unsafe_and_bulky(self):
        written = folder.materialize({"a.md": b"a"}, self.root)
        self.put(".env", b"k")
        self.put("workouts/.audio-cache/a.wav")
        self.put("coaches/.auditions/1/c.json")
        self.put("x.lock")
        self.put("a.mp3")
        self.put("deep/dir/b.mp3")
        self.put("r.log")
        self.put("r.log.1")
        self.put(".DS_Store")
        self.put(".gitignore")
        os.symlink("/etc/hosts", os.path.join(self.root, "evil"))
        os.symlink("/etc", os.path.join(self.root, "evildir"))
        self.assertEqual(folder.harvest(self.root, written), {})

    def test_deleted_file_is_none(self):
        written = folder.materialize({"a.md": b"a", "b.md": b"b"}, self.root)
        os.remove(os.path.join(self.root, "a.md"))
        self.assertEqual(folder.harvest(self.root, written), {"a.md": None})

    def test_never_set_is_respected(self):
        written = folder.materialize({"health.md": b"h", "b.md": b"b"}, self.root)
        self.put("health.md", b"changed")
        os.remove(os.path.join(self.root, "b.md"))
        got = folder.harvest(self.root, written, never=frozenset({"health.md", "b.md"}))
        self.assertEqual(got, {})

    def test_materialize_refuses_escape(self):
        for bad in ("../x", "/abs", "a/../../x", "a\\b", ""):
            with self.assertRaises(ValueError):
                folder.materialize({bad: b""}, self.root)

    def test_seed_is_the_template(self):
        s = folder.seed(ROOT)
        self.assertIn("profile.md", s)
        self.assertIn("health.md", s)
        self.assertIn("workouts/checks/.gitkeep", s)
        self.assertNotIn(".gitignore", s)
        for k, v in s.items():
            with open(os.path.join(ROOT, "me.example", k), "rb") as f:
                self.assertEqual(f.read(), v)


if __name__ == "__main__":
    unittest.main()
