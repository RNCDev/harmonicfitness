"""The listener's records survive a crash and two writers at once: JSONL appends seal a torn line and take a
lock, the lock is re-entrant within a thread, every engine write is atomic, and a hand-edited private movement
can't crash the commands that load the catalog. Also the small boundary checks: player links, feed links."""
import json
import os
import re
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (puts tools/ on the path)
import catalog  # noqa: E402
import check  # noqa: E402
import feeds  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402
import webcopy  # noqa: E402


def lines(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append(None)
    return out


class Appends(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.path = os.path.join(self.d, "sub", "builds.jsonl")

    def test_a_torn_last_line_is_sealed_so_the_next_record_survives(self):
        os.makedirs(os.path.dirname(self.path))
        with open(self.path, "w", encoding="utf-8") as f:
            f.write('{"n": 1}\n{"n": 2, "out": "half')   # a crash mid-write
        fileio.append_jsonl(self.path, {"n": 3})
        self.assertEqual(lines(self.path), [{"n": 1}, None, {"n": 3}])

    def test_several_records_and_a_new_file(self):
        fileio.append_jsonl(self.path, [{"n": 1}, {"n": "é"}])
        fileio.append_jsonl(self.path, [])
        self.assertEqual(lines(self.path), [{"n": 1}, {"n": "é"}])

    def test_two_writers_at_once_lose_nothing(self):
        def write(tag):
            for i in range(150):
                fileio.append_jsonl(self.path, {"w": tag, "i": i, "pad": "x" * 500})
        threads = [threading.Thread(target=write, args=(t,)) for t in "ab"]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        got = lines(self.path)
        self.assertNotIn(None, got)
        self.assertEqual(len(got), 300)

    def test_the_lock_is_reentrant_within_a_thread(self):
        with locks.file_lock(self.path):
            with locks.file_lock(self.path):   # would wait forever on itself without the depth count
                fileio.append_jsonl(self.path, {"n": 1})
        self.assertEqual(lines(self.path), [{"n": 1}])
        self.assertEqual(locks._held, {})


class AtomicWrites(unittest.TestCase):
    # Engine modules that may open a file for writing themselves: fileio itself, a .part file renamed into place
    # (render, coaches), the build log (appended, never rewritten), WAV writers, the harness's exact copies,
    # the key file (created 0600 then appended), and the lock files.
    ALLOWED = {"fileio.py", "build.py", "render.py", "cloud.py", "voices.py", "coaches.py", "harness.py",
               "keys.py", "locks.py"}

    def test_engine_writes_go_through_fileio(self):
        tools = os.path.join(paths.ROOT, "tools")
        found = []
        for name in sorted(os.listdir(tools)):
            if not name.endswith(".py") or name in self.ALLOWED:
                continue
            with open(os.path.join(tools, name), encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    if re.search(r"""open\([^)]*["'](w|a|wb|ab)\+?["']""", line):
                        found.append(f"{name}:{n}: {line.strip()}")
        self.assertEqual(found, [], "write these with fileio.atomic_write / write_json / append_jsonl")


class PrivateMovements(unittest.TestCase):
    def load_with(self, toml):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "movements.toml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(toml)
        with mock.patch.object(catalog.paths, "MY_MOVEMENTS", path):
            return catalog.load(), path

    def test_a_movement_with_no_id_is_left_out_and_named(self):
        cat, path = self.load_with('[[movement]]\nname = "garage drag"\npatterns = ["locomotion"]\n')
        self.assertIn("air-squat", cat.movements)
        self.assertTrue(any("no id" in p and "garage drag" in p for p in catalog.problems(cat)))
        self.assertTrue(any("no id" in i.message for i in check.check_movements(path)))

    def test_a_single_table_reads_as_one_movement(self):
        cat, _ = self.load_with('[movement]\nid = "garage-drag"\nname = "garage drag"\npatterns = ["locomotion"]\n')
        self.assertIn("garage-drag", cat.movements)

    def test_wrong_types_are_left_out_not_split_into_letters(self):
        cat, path = self.load_with('[[movement]]\nid = "garage-drag"\nname = "garage drag"\naliases = "drag"\n'
                                   'patterns = ["locomotion"]\nseconds_per_rep = "fast"\nloads = 2\n')
        self.assertNotIn("garage-drag", cat.movements)
        faults = " ".join(catalog.problems(cat))
        for word in ("aliases must be a list", "seconds_per_rep must be a number", "loads must be a table"):
            self.assertIn(word, faults)
        self.assertTrue(check.check_movements(path))


class Boundaries(unittest.TestCase):
    def test_player_links_survive_a_hash_in_the_name(self):
        with tempfile.TemporaryDirectory() as d:
            page = webcopy.page("Workout #3", [os.path.join(d, "Workout #3.web-1.mp3"),
                                                os.path.join(d, "Workout #3.web-2.mp3")], os.path.join(d, "p.html"))
            with open(page, encoding="utf-8") as f:
                text = f.read()
        self.assertIn('href="Workout%20%233.web-1.mp3"', text)
        self.assertIn('"Workout%20%233.web-2.mp3"', text)
        self.assertNotIn('href="Workout #3', text)

    def test_feed_links_are_plain_web_addresses(self):
        self.assertEqual(feeds.web_link(" https://example.com/a?b=1 "), "https://example.com/a?b=1")
        for bad in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,x", "https://a b", ""):
            self.assertEqual(feeds.web_link(bad), "", bad)


if __name__ == "__main__":
    unittest.main()
