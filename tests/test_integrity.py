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
               "keys.py", "locks.py", "clipcache.py", "wav.py"}

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


class SettingShapes(unittest.TestCase):
    """A hand-edited setting in the wrong shape is read the way it was meant, and check says so."""

    def profile(self, settings):
        import context
        return context.Profile(settings=settings, body="", path="p") if hasattr(context, "Profile") else \
            type("P", (), {"settings": settings, "path": "p"})()

    def test_a_bare_string_is_one_item_never_its_letters(self):
        import context
        p = self.profile({"likes": "goblet squat", "youtube_favorites": "@ch", "render": "fish",
                          "deliver_to": "~/Drive"})
        self.assertEqual(context.likes(p), ["goblet squat"])
        self.assertEqual(context.handles(p, "YouTube favorites"), ["ch"])
        self.assertEqual(context.routes(p), ["fish"])
        self.assertEqual(len(context.delivery_patterns(p)), 1)
        notes = context.shape_problems(p.settings)
        self.assertEqual([k for k, _, note in notes], ["likes", "youtube_favorites"])
        self.assertTrue(all(note for _, _, note in notes))

    def test_a_single_table_is_one_row(self):
        import context
        p = self.profile({"kits": {"name": "home", "equipment": "dumbbells", "weights": {"dumbbells": [10, 20]}}})
        self.assertEqual(context.kits(p), {"home": ["dumbbells"]})
        self.assertEqual(context.kit_weights(p), {"home": ("lb", {"dumbbells": [10, 20]})})
        self.assertIn("[[kits]]", context.shape_problems(p.settings)[0][1])
        self.assertIn("equipment is one item", context.kit_problems(p.settings["kits"])[0])

    def test_wrong_types_are_issues(self):
        import context
        found = context.shape_problems({"likes": 3, "feeds": ["x"], "deliver_to": 7})
        self.assertEqual(sorted(k for k, _, note in found if not note), ["deliver_to", "feeds", "likes"])

    def test_a_coach_alias_given_as_one_name(self):
        import personas
        p = personas.Persona(slug="coach-x", folder="/nowhere", settings={"aliases": "Maya"}, prose="")
        self.assertEqual(p.aliases, ["Maya"])


class CatalogCache(unittest.TestCase):
    def test_the_index_finds_what_a_scan_finds(self):
        cat = catalog.load()

        def scan(name):   # resolve as it was before the index, for comparison
            said = " ".join(name.lower().split())
            for side in catalog.SIDE_WORDS:
                if said.startswith(side):
                    said = said[len(side):]
                    break
            if said in cat.movements:
                return cat.movements[said]
            key = catalog.plain(said)
            forms = {key} | ({key[:-2]} if key.endswith("es") else set()) | \
                ({key[:-1]} if key.endswith("s") and not key.endswith("ss") else set())
            for m in cat.movements.values():
                if any(catalog.plain(k) in forms for k in [m.name, m.id] + m.aliases):
                    return m
            return None
        words = {w for m in cat.movements.values() for w in [m.name, m.id, *m.aliases]}
        words |= {w + "s" for w in words} | {"left " + w for w in list(words)[:40]} | {"nothing like this"}
        for w in sorted(words):
            self.assertIs(catalog.resolve(cat, w), scan(w), w)

    def test_default_loads_once_and_again_when_the_file_changes(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "movements.toml")
        with open(path, "w", encoding="utf-8") as f:
            f.write('[[movement]]\nid = "garage-drag"\nname = "garage drag"\npatterns = ["locomotion"]\n')
        with mock.patch.object(catalog.paths, "MY_MOVEMENTS", path):
            first = catalog.default()
            self.assertIs(catalog.default(), first)
            self.assertIn("garage-drag", first.movements)
            with open(path, "w", encoding="utf-8") as f:
                f.write('[[movement]]\nid = "garage-sled"\nname = "garage sled"\npatterns = ["locomotion"]\n\n')
            again = catalog.default()
        self.assertIsNot(again, first)
        self.assertIn("garage-sled", again.movements)


class Apostrophes(unittest.TestCase):
    def test_the_matchers_fold_every_apostrophe_alike(self):
        import menu
        import verify
        cat = catalog.load()
        mid = next(m.id for m in cat.movements.values() if "'" in m.name) if any(
            "'" in m.name for m in cat.movements.values()) else None
        for quote in ("\u2019", "\u2018", "\u02bc"):
            self.assertEqual(verify.words(f"farmer{quote}s carry"), ["farmer's", "carry"])
            self.assertEqual(catalog.plain(f"Farmer{quote}s Carry"), "farmer's carry")
            if mid:
                name = cat.movements[mid].name.replace("'", quote)
                self.assertIn(mid, [m for m, _, _ in menu.mentions(cat, f"Now the {name}.")])


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
