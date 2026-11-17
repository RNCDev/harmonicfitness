"""The listener's records survive a crash and two writers at once: JSONL appends seal a torn line and take a
lock, the lock is re-entrant within a thread, every engine write is atomic, and a hand-edited private movement
can't crash the commands that load the catalog, and a build leaves one outcome line however it stops. Also the
small boundary checks: feed links, --today."""
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
    # (render), the build log (appended, never rewritten), WAV writers, the key file (created 0600 then
    # appended), and the lock files.
    ALLOWED = {"fileio.py", "build.py", "render.py", "cloud.py", "voices.py",
               "keys.py", "locks.py", "clipcache.py", "wav.py"}

    def test_atomic_write_takes_text_and_bytes_leaving_no_part_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "sub", "x.json")
            fileio.atomic_write(p, '{"a": 1}\n')   # makes the folder
            with open(p, encoding="utf-8") as f:
                self.assertEqual(f.read(), '{"a": 1}\n')
            fileio.atomic_write(p, b"\x00\x01")
            with open(p, "rb") as f:
                self.assertEqual(f.read(), b"\x00\x01")
            self.assertEqual(os.listdir(os.path.dirname(p)), ["x.json"])

    def test_atomic_copy(self):
        d = tempfile.mkdtemp()
        src, dst = os.path.join(d, "a.mp3"), os.path.join(d, "out", "b.mp3")
        with open(src, "wb") as f:
            f.write(b"ID3" + bytes(range(256)) * 50)
        fileio.atomic_copy(src, dst)
        with open(src, "rb") as a, open(dst, "rb") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual(os.listdir(os.path.dirname(dst)), ["b.mp3"])   # no .part left behind
        with self.assertRaises(FileNotFoundError):
            fileio.atomic_copy(os.path.join(d, "missing"), dst)
        self.assertEqual(os.listdir(os.path.dirname(dst)), ["b.mp3"])

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


class WindowsReplace(unittest.TestCase):
    """fileio.replace: on Windows a file another program holds open (last time's MP3 in a player) is tried
    again for a moment before the build gives up; elsewhere a refusal is final at once."""

    def attempt(self, os_name, failures):
        results = [PermissionError("in use")] * failures + [None]
        with mock.patch.object(fileio.os, "name", os_name), \
                mock.patch.object(fileio.os, "replace", side_effect=results) as rep, \
                mock.patch.object(fileio.time, "sleep") as sleep:
            try:
                fileio.replace("a.part", "a.mp3")
                return True, rep.call_count, sleep.call_count
            except PermissionError:
                return False, rep.call_count, sleep.call_count

    def test_a_held_file_is_tried_again_on_windows_only(self):
        self.assertEqual(self.attempt("nt", 2), (True, 3, 2))
        self.assertEqual(self.attempt("nt", 10), (False, 10, 9))
        self.assertEqual(self.attempt("posix", 1), (False, 1, 0))


class PrivateMovements(unittest.TestCase):
    def load_with(self, toml):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "movements.toml")
        with open(path, "w", encoding="utf-8") as f:
            f.write(toml)
        with mock.patch.object(catalog.paths, "MY_MOVEMENTS", path):
            return catalog.load(), path

    def test_a_hand_edited_movement_is_read_or_left_out_and_named(self):
        cat, path = self.load_with('[[movement]]\nname = "garage drag"\npatterns = ["locomotion"]\n')
        self.assertIn("air-squat", cat.movements)
        self.assertTrue(any("no id" in p and "garage drag" in p for p in catalog.problems(cat)))
        self.assertTrue(any("no id" in i.message for i in check.check_movements(path)))
        cat, _ = self.load_with('[movement]\nid = "garage-drag"\nname = "garage drag"\npatterns = ["locomotion"]\n')
        self.assertIn("garage-drag", cat.movements)   # a single table reads as one movement
        cat, path = self.load_with('[[movement]]\nid = "garage-drag"\nname = "garage drag"\naliases = "drag"\n'
                                   'patterns = ["locomotion"]\nseconds_per_rep = "fast"\nloads = 2\n')
        self.assertNotIn("garage-drag", cat.movements)   # wrong types: left out, not split into letters
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

    def test_a_setting_in_the_wrong_shape_is_read_as_meant_and_noted(self):
        import context
        import personas
        p = self.profile({"likes": "goblet squat", "youtube_favorites": "@ch", "render": "fish",
                          "deliver_to": "~/Drive"})
        self.assertEqual(context.likes(p), ["goblet squat"])   # a bare string is one item, never its letters
        self.assertEqual(context.handles(p, "YouTube favorites"), ["ch"])
        self.assertEqual(context.routes(p), ["fish"])
        self.assertEqual(len(context.delivery_patterns(p)), 1)
        notes = context.shape_problems(p.settings)
        self.assertEqual([k for k, _, note in notes], ["likes", "youtube_favorites"])
        self.assertTrue(all(note for _, _, note in notes))
        p = self.profile({"kits": {"name": "home", "equipment": "dumbbells", "weights": {"dumbbells": [10, 20]}}})
        self.assertEqual(context.kits(p), {"home": ["dumbbells"]})   # a single table is one row
        self.assertEqual(context.kit_weights(p), {"home": ("lb", {"dumbbells": [10, 20]})})
        self.assertIn("[[kits]]", context.shape_problems(p.settings)[0][1])
        self.assertIn("equipment is one item", context.kit_problems(p.settings["kits"])[0])
        found = context.shape_problems({"likes": 3, "feeds": ["x"], "deliver_to": 7})   # wrong types are issues
        self.assertEqual(sorted(k for k, _, note in found if not note), ["deliver_to", "feeds", "likes"])
        coach = personas.Persona(slug="coach-x", folder="/nowhere", settings={"aliases": "Maya"}, prose="")
        self.assertEqual(coach.aliases, ["Maya"])


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


class TypedRecords(unittest.TestCase):
    """builds.jsonl's lines name their kind (mp3, failed, outcome) from 0.19.0 on; a line from before then is read
    by what its fields imply, and a hand-edited line with a field of the wrong type is skipped."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.log = os.path.join(self.d, ".logs", "builds.jsonl")

    def raw(self):
        with open(self.log, encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def test_every_new_line_names_its_kind(self):
        import time
        import records
        out = os.path.join(self.d, "W.mp3")
        records.save_build_record({"draft_sha256": "a", "route": "local"}, out, self.log)
        voice = {"name": "Coach Pin", "key": "k", "engine": "fish", "service": "fish", "model": "s2.1-pro",
                 "route": "fish"}
        with mock.patch.object(paths, "BUILDS", self.log):
            records.save_failed_record(voice, out, os.path.join(self.d, "x.draft.txt"), "b",
                                       {"started": 10, "chars": 4}, time.time(), RuntimeError("cut"), "id1")
            records.note("delivered", build_id="id2", kind="ignored")
        self.assertEqual([r["kind"] for r in self.raw()], ["mp3", "failed", "outcome"])
        self.assertTrue(self.raw()[1]["failed"])   # still there for an engine before 0.19.0
        with open(os.path.join(self.d, "W.build.json"), encoding="utf-8") as f:
            self.assertNotIn("kind", json.load(f))   # the record beside the MP3 is as it was
        self.assertEqual([r["kind"] for r in records.build_records(self.log)], ["mp3", "failed", "outcome"])
        self.assertTrue(records.built("a", self.log))
        self.assertFalse(records.built("b", self.log))
        self.assertEqual(records.web_builds(self.log), 1)   # the failed render sent text; the local MP3 didn't

    def test_a_hand_edited_line_that_cant_be_its_kind_is_skipped(self):
        import records
        bad = [{"draft_sha256": "a", "route": 5},                      # route not text
               {"draft_sha256": "a", "route": "fish", "failed": "yes"},  # failed not true or false
               {"kind": "mp3", "draft_sha256": "a", "route": "fish", "failed": True},   # the kind contradicts it
               {"kind": "receipt", "draft_sha256": "a", "route": "fish"},
               {"kind": "failed", "failed": True, "route": "fish"},      # no draft_sha256
               {"route": "fish"},                                        # an MP3 with no draft_sha256
               {"kind": "outcome", "route": "fish"},                     # an outcome with no event
               {"draft_sha256": "a", "route": "fish", "chars_sent": True}]
        for rec in bad:
            self.assertIsNone(records.parse(rec), rec)
            self.assertFalse(records.is_mp3(rec), rec)
        fileio.append_jsonl(self.log, bad)
        self.assertEqual(list(records.build_records(self.log)), [])
        self.assertEqual(records.web_builds(self.log), 0)
        self.assertFalse(records.built("a", self.log))
        self.assertEqual(records.parse('{"draft_sha256": "a"}')["kind"], "mp3")   # a line, as text
        self.assertIsNone(records.parse("not json"))
        with open(self.log, "wb") as f:
            f.write(b'{"a": 1}\n\n   \nnot json\n[1, 2]\n"text"\n{"b": 2, "torn\n{"c": "\xff\xfe"}\n'
                    + '{"d": "café"}\n'.encode("utf-8") + b'{"e": 5}')
        self.assertEqual(list(fileio.read_jsonl(self.log)), [{"a": 1}, {"d": "café"}, {"e": 5}])
        self.assertEqual(list(fileio.read_jsonl(self.log, lambda r: r if "a" not in r else None)),
                         [{"d": "café"}, {"e": 5}])
        self.assertEqual(list(fileio.read_jsonl(os.path.join(self.d, "none.jsonl"))), [])   # read_jsonl skips what holds no record


class ReadJson(unittest.TestCase):
    """fileio.read_json: a missing file is the caller's to answer (FileNotFoundError); a damaged one, or one of
    the wrong top-level shape, is a ContextError naming the file; and the readers that once trusted json.load
    answer through it."""

    def setUp(self):
        import shutil
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def put(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_shapes_and_damage(self):
        import errors
        self.assertEqual(fileio.read_json(self.put("a.json", '{"x": 1}')), {"x": 1})
        self.assertEqual(fileio.read_json(self.put("b.json", "[1]"), shape=list), [1])
        with self.assertRaises(FileNotFoundError):
            fileio.read_json(os.path.join(self.tmp, "none.json"))
        for name, text in (("torn.json", '{"x": '), ("list.json", "[1, 2]"), ("null.json", "null")):
            path = self.put(name, text)
            with self.assertRaises(errors.ContextError) as got:
                fileio.read_json(path)
            self.assertIn(name, str(got.exception))
        with self.assertRaises(errors.ContextError) as got:
            fileio.read_json(self.put("obj.json", "{}"), shape=list)
        self.assertIn("array", str(got.exception))
        import draft as draftmod   # the menu gate names a damaged menu
        import menu
        d = self.put("2026-10-25-x.draft.txt", "movements: \n")
        with open(draftmod.menu_path(d), "w", encoding="utf-8") as f:
            f.write('"a string"')
        issues, _ = menu.gate(catalog.default(), d, "", [])
        self.assertEqual(len(issues), 1)
        self.assertIn("can't be read", issues[0])

class BuildTrail(unittest.TestCase):
    """Every exit of a full build leaves exactly one outcome line ("stopped", "measured" or "delivered") in
    builds.jsonl, carrying its build_id; a lint-only run leaves none. The lint and the render are stood in for;
    the coach, the menu, the delivery and the records are real. The build log gets the engine's own lines and a
    bug's traceback."""

    def setUp(self):
        import contextlib
        import shutil
        import render
        import tts_build
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "me")
        shutil.copytree(paths.EXAMPLE, self.home)
        self.phone = os.path.join(self.tmp, "phone")
        os.makedirs(self.phone)
        prof = os.path.join(self.home, "settings.toml")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(re.sub(r"^deliver_to = .*$", "deliver_to = " + json.dumps(self.phone.replace(os.sep, "/")),
                           text, flags=re.M))
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(helpers.home(self.home))
        self.draft = os.path.join(self.home, "workouts", "2026-10-25-test-25", "2026-10-25-test-25.draft.txt")
        helpers.draft_with_menu(os.path.join(paths.ROOT, "tests", "fixtures", "example.draft.txt"), self.draft,
                                self.home)
        stack.enter_context(mock.patch.dict(os.environ, {"HARMONICFITNESS_FAKE_LOCAL_ENGINE": "1"}))
        stack.enter_context(mock.patch.object(tts_build, "lint", side_effect=lambda *a, **k: tts_build.Report(
            rows=[], strict=False, wpm=185.0)))
        stack.enter_context(mock.patch.object(render, "run", side_effect=self.fake_run))
        self.drift, self.fails, self.ids = 0.0, None, []

    def fake_run(self, segments, voice, out, **kw):
        self.ids.append(kw["build_id"])
        print("rendering for a test")   # the engine's own progress: on the terminal and in the log
        if self.fails:
            raise self.fails
        with open(out, "w", encoding="utf-8") as f:
            f.write("x")
        with open(os.path.splitext(out)[0] + ".build.json", "w", encoding="utf-8") as f:
            json.dump({"route": "local", "build_id": kw["build_id"]}, f)
        return self.drift

    def build(self, *extra, draft_path=None, estimated=True):
        import contextlib
        import io
        import build
        import cli
        argv = [draft_path or self.draft, "Test build", *(["--allow-estimated"] if estimated else []), *extra]
        self.out = io.StringIO()
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.out):
            return cli.run(lambda: build.main(argv))

    def events(self):
        import records
        return [r for r in records.build_records() if r.get("event")]

    def one_event(self, event, stage=None):
        (line,) = self.events()
        self.assertEqual(line["event"], event, self.out.getvalue())
        if stage:
            self.assertEqual(line["stage"], stage)
        self.assertRegex(line["build_id"], r"^[0-9a-f]{12}$")
        if self.ids:
            self.assertEqual(line["build_id"], self.ids[-1])
        return line

    def read_log(self):
        with open(os.path.join(paths.LOGS, "Test build.log"), encoding="utf-8") as f:
            return f.read()

    def test_delivered(self):
        self.assertEqual(self.build(), 0, self.out.getvalue())
        self.one_event("delivered")
        self.assertIn("rendering for a test", self.out.getvalue())
        self.assertIn("rendering for a test", self.read_log())   # stdout is teed into the build log

    def test_a_render_that_stops(self):
        self.fails = SystemExit("the engine stopped")
        self.assertEqual(self.build(), 1)
        self.assertEqual(self.one_event("stopped", "render")["reason"], "the engine stopped")
        self.assertIn("stopped at render: the engine stopped", self.read_log())
        self.assertIn(f"({self.ids[-1]}) stopped at render", self.read_log())

    def test_a_bug_is_70_with_its_traceback_in_the_log(self):
        self.fails = KeyError("a bug in the render")
        self.assertEqual(self.build(), 70)
        self.one_event("stopped", "render")
        log = self.read_log()
        self.assertIn("Traceback", log)
        self.assertIn("a bug in the render", log)

    def test_a_voice_saved_but_not_written_reaches_the_terminal(self):
        """The first build with a stock web coach saves its voice at the service; if writing the coach then
        fails, the voice's ID and what to do reach the listener's terminal (say), not only the build log."""
        import build
        import cloud
        import coachmake
        import contextlib
        import io
        from fakes import tone_wav

        class Saves:
            @staticmethod
            def design(description, line, n, label):
                return [{"wav": tone_wav(0.5), "text": line}]

            @staticmethod
            def save(candidate, name, description, wav):
                return "voice-left-behind-7"

        said, self.out = [], io.StringIO()
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test-key"}), \
                mock.patch.object(cloud, "service_module", lambda s: Saves), \
                mock.patch.object(coachmake, "_write_sample", side_effect=OSError("disk full")), \
                contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.out):
            with self.assertRaises(OSError):
                build.run_build(build.BuildOptions(draft=self.draft, name="Test build", coach="Coach Reed"),
                                say=said.append)
        self.assertTrue(any("voice-left-behind-7" in line and "Fish Audio" in line for line in said), said)
        self.one_event("stopped", "design")
        self.assertIn("voice-left-behind-7", self.out.getvalue())   # and on stderr (the log, from the command line)

    def test_lint_only_leaves_none(self):
        self.assertEqual(self.build("--lint-only"), 0)
        helpers.menu_for(self.draft, self.home, today="2026-10-20")
        self.build("--lint-only", "--coach", "Nobody At All")
        self.assertEqual(self.events(), [])


class DeliveryPlan(unittest.TestCase):
    def test_a_failed_copy_keeps_its_reason(self):
        import build
        d = tempfile.mkdtemp()
        mp3 = os.path.join(d, "x.mp3")
        with open(mp3, "w", encoding="utf-8") as f:
            f.write("x")

        def refused(src, dst):
            raise PermissionError(13, "Permission denied")
        said = []
        with mock.patch.object(build.shutil, "copyfile", side_effect=refused):
            got = build.deliver(mp3, d, [os.path.join(d, "phone")], say=said.append)
        self.assertTrue(got["kept_local"])
        self.assertIn("Permission denied", got["reason"])
        self.assertIn("Permission denied", said[0])


class LockFilesStayPrivate(unittest.TestCase):
    def test_migrate_adds_the_lock_rule_to_an_old_gitignore(self):
        import contextlib
        import io
        import shutil
        import migrate
        d = tempfile.mkdtemp()
        home = os.path.join(d, "me")
        shutil.copytree(paths.EXAMPLE, home)
        ignore = os.path.join(home, ".gitignore")
        with open(ignore, encoding="utf-8") as f:
            old = f.read().replace("*.lock\n", "")
        with open(ignore, "w", encoding="utf-8") as f:
            f.write(old)
        with helpers.home(home), contextlib.redirect_stdout(io.StringIO()) as out:
            migrate.main([])
            migrate.main([])   # once only
        with open(ignore, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count("\n*.lock\n"), 1)
        self.assertEqual(out.getvalue().count("added *.lock"), 1)


class Boundaries(unittest.TestCase):
    def test_feed_links_are_plain_web_addresses(self):
        self.assertEqual(feeds.web_link(" https://example.com/a?b=1 "), "https://example.com/a?b=1")
        for bad in ("javascript:alert(1)", "file:///etc/passwd", "data:text/html,x", "https://a b", ""):
            self.assertEqual(feeds.web_link(bad), "", bad)


class OneRule(unittest.TestCase):
    def test_today_is_a_date_or_exit_64(self):
        import datetime
        import cli
        ap = cli.ArgumentParser(prog="x")
        cli.today_arg(ap)
        self.assertEqual(ap.parse_args(["--today", "2026-10-27"]).today, datetime.date(2026, 10, 27))
        self.assertIsNone(ap.parse_args([]).today)
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as got:
            ap.parse_args(["--today", "tomorrow"])
        self.assertEqual(got.exception.code, cli.USAGE)


if __name__ == "__main__":
    unittest.main()
