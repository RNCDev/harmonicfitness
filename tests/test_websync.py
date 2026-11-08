"""./harmonicfitness sync: the three-way plan, and a sync against a fake site held in memory (no network)."""
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import websync  # noqa: E402

ACCOUNT = {"HARMONIC_USERNAME": "lee", "HARMONIC_PASSWORD": "pw", "HARMONIC_URL": "https://example.org"}


def h(data):
    return hashlib.sha256(data).hexdigest()


class FakeSite:
    """The web app's sync calls, as store.write_back does them: a write lands only over the version given."""

    def __init__(self, files=None):
        self.files = {p: (1, b) for p, b in (files or {}).items()}   # path -> (version, bytes)

    def listing(self):
        return {p: (v, h(b)) for p, (v, b) in self.files.items()}

    def read(self, paths):
        return {p: self.files[p] for p in paths if p in self.files}

    def write(self, changes):
        written, conflicts = {}, []
        for path, base, data in changes:
            have = self.files.get(path)
            if (have[0] if have else None) != base:
                conflicts.append(path)
            elif data is None:
                del self.files[path]
                written[path] = None
            else:
                self.files[path] = ((have[0] if have else 0) + 1, data)
                written[path] = self.files[path][0]
        return written, conflicts, []


class Plan(unittest.TestCase):
    def test_each_case(self):
        s = {"a": {"version": 1, "sha": "x"}, "b": {"version": 1, "sha": "x"}, "c": {"version": 1, "sha": "x"},
             "d": {"version": 1, "sha": "x"}, "e": {"version": 1, "sha": "x"}, "f": {"version": 1, "sha": "x"}}
        local = {"a": "y", "b": "x", "c": "y", "e": "x", "g": "n"}
        remote = {"a": (1, "x"), "b": (2, "z"), "c": (2, "z"), "d": (1, "x"), "f": (2, "w"), "h": (1, "m")}
        got = websync.plan(local, remote, s)
        self.assertEqual(got["push"], ["a", "g"])           # changed here; new here
        self.assertEqual(got["pull"], ["b", "f", "h"])      # changed there; deleted here but edited there; new there
        self.assertEqual(got["conflict"], ["c"])            # both changed
        self.assertEqual(got["delete_there"], ["d"])        # deleted here, untouched there
        self.assertEqual(got["delete_here"], ["e"])         # deleted there, untouched here
        self.assertEqual(websync.plan(local, remote, s, prefer="web")["pull"], ["b", "c", "f", "h"])
        self.assertIn("c", websync.plan(local, remote, s, prefer="local")["push"])

    def test_a_first_sync_deletes_nothing_and_calls_a_difference_a_conflict(self):
        got = websync.plan({"a": "x", "b": "y", "c": "s"}, {"a": (1, "x"), "b": (1, "z"), "d": (3, "q")}, {})
        self.assertEqual((got["same"], got["conflict"], got["push"], got["pull"]), (["a"], ["b"], ["c"], ["d"]))
        self.assertEqual(got["delete_here"] + got["delete_there"], [])

    def test_never_synced(self):
        for rel in (".env", "keys.env", "workouts/w/Workout.mp3", "workouts/.audio-cache/x.json", "x.lock",
                    "workouts/.logs/W.log", "web/sync-state.json", "web/2026-10-31/me/log.md",
                    "coaches/.auditions/a.md", ".git/config", ".backup-2026/log.md", ".gitignore", "a.bundle",
                    "coaches/.archive/coach-x/sample.mp3", "coaches/coach-x/take.mp3",
                    "workouts/.logs/backup-remote.json"):
            self.assertTrue(websync.skipped(rel), rel)
        for rel in ("log.md", "workouts/w/w.draft.txt", "workouts/.logs/builds.jsonl", "coaches/coach-x/persona.md",
                    "workouts/research/told.jsonl", "coaches/coach-x/sample.mp3"):
            self.assertFalse(websync.skipped(rel), rel)


class Sync(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hf-sync-")
        self.addCleanup(__import__("shutil").rmtree, self.home, True)
        with open(os.path.join(self.home, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(".env\n")

    def put(self, rel, data):
        path = os.path.join(self.home, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)

    def get(self, rel):
        path = os.path.join(self.home, *rel.split("/"))
        if not os.path.exists(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    def sync(self, site, **kw):
        return websync.sync(ACCOUNT, home=self.home, site=site, **kw)

    def test_both_ways_then_in_step(self):
        self.put("profile.md", b"me")
        self.put("log.md", b"here")
        self.put(".env", b"SECRET=1")
        self.put("workouts/w/W.mp3", b"ID3")
        site = FakeSite({"log.md": b"there", "workouts/w/w.draft.txt": b"draft"})
        got = self.sync(site)
        self.assertEqual((got["push"], got["pull"], got["conflict"]), (["profile.md"], ["workouts/w/w.draft.txt"], ["log.md"]))
        self.assertEqual(site.files["profile.md"][1], b"me")
        self.assertNotIn(".env", site.files)
        self.assertNotIn("workouts/w/W.mp3", site.files)
        self.assertEqual(self.get("workouts/w/w.draft.txt"), b"draft")
        self.assertEqual(self.get("log.md"), b"here")                     # this computer's copy stays
        aside = got["conflict_folder"]
        with open(os.path.join(aside, "log.md"), "rb") as f:
            self.assertEqual(f.read(), b"there")                           # the site's, beside it
        self.assertIn("web/", self.get(".gitignore").decode())             # never backed up

        got = self.sync(site)                                              # the next sync sends this computer's
        self.assertEqual(got["push"], ["log.md"])
        self.assertEqual(site.files["log.md"][1], b"here")
        got = self.sync(site)
        self.assertEqual(sum(len(got[k]) for k in ("push", "pull", "conflict", "delete_here", "delete_there")), 0)

    def test_edits_and_deletes_travel(self):
        site = FakeSite({"a.md": b"1", "b.md": b"1", "c.md": b"1"})
        self.sync(site)
        self.put("a.md", b"2")                                            # edited here
        site.files["b.md"] = (2, b"2")                                    # edited there
        os.remove(os.path.join(self.home, "c.md"))                        # deleted here
        got = self.sync(site)
        self.assertEqual((got["push"], got["pull"], got["delete_there"]), (["a.md"], ["b.md"], ["c.md"]))
        self.assertEqual((site.files["a.md"][1], self.get("b.md")), (b"2", b"2"))
        self.assertNotIn("c.md", site.files)
        del site.files["a.md"]                                            # deleted there
        self.assertEqual(self.sync(site)["delete_here"], ["a.md"])
        self.assertIsNone(self.get("a.md"))

    def test_a_dry_run_changes_nothing(self):
        self.put("x.md", b"x")
        site = FakeSite({"y.md": b"y"})
        got = self.sync(site, dry_run=True)
        self.assertEqual((got["push"], got["pull"]), (["x.md"], ["y.md"]))
        self.assertEqual(site.files, {"y.md": (1, b"y")})
        self.assertIsNone(self.get("y.md"))
        self.assertFalse(os.path.exists(os.path.join(self.home, websync.STATE)))

    def test_another_account_starts_over(self):
        site = FakeSite({"a.md": b"1"})
        self.sync(site)
        os.remove(os.path.join(self.home, "a.md"))
        other = dict(ACCOUNT, HARMONIC_USERNAME="sam")
        got = websync.sync(other, home=self.home, site=site)
        self.assertEqual((got["pull"], got["delete_there"]), (["a.md"], []))   # no record for sam: nothing deleted

    def test_a_change_on_the_site_during_the_sync_waits(self):
        site = FakeSite({"a.md": b"1"})
        self.sync(site)
        self.put("a.md", b"2")
        real = site.write

        def racing(changes):
            site.files["a.md"] = (5, b"site")   # a turn saved it a moment before
            return real(changes)
        site.write = racing
        got = self.sync(site)
        self.assertEqual(got["lost"], ["a.md"])
        site.write = real
        self.assertEqual(self.sync(site)["conflict"], ["a.md"])            # the next sync sees both changed

    def test_credentials_are_needed(self):
        with self.assertRaises(websync.errors.UsageError):
            websync.sync({}, home=self.home, site=FakeSite())


if __name__ == "__main__":
    unittest.main()
