"""Coaches as persona folders (me/personas/<slug>/): clip, settings, pace and service voices.
No models: the fixture coach is half a second of a tone (tests/fixtures/personas/coach-test)."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import errors  # noqa: E402

import context  # noqa: E402
import check  # noqa: E402
import ffmpeg  # noqa: E402
import personas  # noqa: E402
import routes  # noqa: E402
import voices  # noqa: E402

FIXTURE = personas.paths.SHIPPED   # the stock coaches the tests see (tests/fixtures/stock: ./harmonicfitness test sets HARMONICFITNESS_SHIPPED)
FFMPEG = ffmpeg.exe()   # the MP3s need it; without it they're skipped, as in test_webcopy


def persona_home(d, *extra):
    """The listener's coaches folder, holding (name, settings) for each extra coach; the stock fixture coaches
    (Coach Test among them) come from paths.SHIPPED."""
    folder = os.path.join(d, "coaches")
    os.makedirs(folder, exist_ok=True)
    for name, settings in extra:
        slug = personas.slug(name)
        os.makedirs(os.path.join(folder, slug))
        shutil.copy(os.path.join(FIXTURE, "coach-test", "clip.wav"), os.path.join(folder, slug, "clip.wav"))
        with open(os.path.join(folder, slug, "clip.txt"), "w", encoding="utf-8") as f:
            f.write("Hello.\n")
        with open(os.path.join(folder, slug, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text(dict({"name": name}, **settings), "## How this coach talks\n"))
    return folder


class Personas(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def use(self, folder):
        patcher = mock.patch.object(personas.paths, "PERSONAS", folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_slug_and_lookup_with_accents_and_apostrophes(self):
        self.assertEqual(personas.slug("Coach Zoë"), "coach-zoe")
        self.assertEqual(personas.slug("Coach O'Neil"), "coach-oneil")
        self.assertEqual(personas.slug("Coach Ana María"), "coach-ana-maria")
        self.use(persona_home(self.d, ("Coach Zoë", {}), ("Coach O'Neil", {})))
        self.assertEqual(personas.lookup("coach-zoe").name, "Coach Zoë")
        self.assertEqual(personas.lookup("COACH ZOË").slug, "coach-zoe")
        self.assertEqual(personas.lookup("coach o'neil").slug, "coach-oneil")
        self.assertEqual(personas.lookup("test voice").name, "Coach Test")   # an alias
        with self.assertRaises(errors.PROBLEMS) as e:
            personas.lookup("Coach Nobody")
        self.assertIn("Coach Test", str(e.exception.code))
        self.assertEqual([p.name for p in personas.all(personas.paths.PERSONAS)], ["Coach O'Neil", "Coach Zoë"])
        self.assertIn("Coach Test", [p.name for p in personas.all()])   # the stock coaches are merged in

    def test_voice_for_local_keys_on_clip_words_and_voice_file(self):
        self.use(persona_home(self.d))
        p = personas.lookup("Coach Test")
        v = personas.voice_for(p, "local")
        with open(os.path.join(FIXTURE, "coach-test", "clip.wav"), "rb") as f:
            audio = hashlib.sha256(f.read()).hexdigest()
        with open(os.path.join(FIXTURE, "coach-test", "pocket.safetensors"), "rb") as f:
            state = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(v["key"], hashlib.sha256(
            f"{audio}|Set your feet. Chest up, and press.|{state}".encode()).hexdigest()[:12])
        self.assertEqual((v["model"], v["revision"]), voices.LOCAL_MODELS["pocket"])
        self.assertEqual((v["engine"], v["backend"], v["route"], v["name"]), ("pocket", "torch", "local", "Coach Test"))
        self.assertEqual(v["pace_file"], personas.paths.PACE_FILE)   # the shared pace file: me/coaches/ holds only their own
        self.assertEqual(v["voice_state"], os.path.join(FIXTURE, "coach-test", "pocket.safetensors"))

class KeepWeb(unittest.TestCase):
    """coaches keep <audition>/<letter>: the audition says a save went out before the service answers."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import tone_wav
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        folder = persona_home(self.d)
        for patch in (mock.patch.object(personas.paths, "PERSONAS", folder),
                      mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test-key", "HARMONICFITNESS_RETRY_WAIT": "0"})):
            patch.start()
            self.addCleanup(patch.stop)
        self.audition = os.path.join(folder, ".auditions", "2026-10-25-1")
        os.makedirs(self.audition)
        with open(os.path.join(self.audition, "fish-1.wav"), "wb") as f:
            f.write(tone_wav(0.5))
        with open(os.path.join(self.audition, "narrative.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Maya", "voice": {"who": "a coach", "sound": "warm"}}, ""))
        self.cands = os.path.join(self.audition, "candidates.json")
        with open(self.cands, "w", encoding="utf-8") as f:
            json.dump([{"letter": "A", "service": "fish", "k": 1, "draft_id": "c1", "signature": "s", "text": "Hi.",
                        "wav": "fish-1.wav", "mp3": None}], f)

    def test_an_unreadable_save_answer_leaves_a_mark(self):
        import cloud
        import coaches
        from fakes import FakeService
        with FakeService(lambda r: (201, {}, b"<html>saved, probably</html>")) as fake, \
                mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": fake.url}):
            with self.assertRaises(cloud.ServiceError) as got:
                coaches.keep_web("2026-10-25-1/A", "Coach Maya")
        self.assertIn("harmonicfitness Coach Maya", str(got.exception))
        with open(self.cands, encoding="utf-8") as f:
            self.assertEqual(json.load(f)[0]["saving"], "Coach Maya")   # the paid save is never forgotten
        self.assertFalse(os.path.exists(personas.folder_for("Coach Maya", "fish")))
        said = "\n".join(coaches.forget_audition("2026-10-25-1"))
        self.assertIn('look for "harmonicfitness Coach Maya"', said)
        self.assertNotIn("nothing was saved", said)

    def outside(self):
        """A folder outside the auditions tree that looks like an audition."""
        stray = os.path.join(self.d, "elsewhere", "not-an-audition")
        shutil.copytree(self.audition, stray)
        return stray

    def test_a_folder_outside_the_auditions_is_refused_and_left_in_place(self):
        import coaches
        stray = self.outside()
        for ref in (stray, os.path.relpath(stray, os.path.join(self.d, "coaches", ".auditions")),
                    "../../elsewhere/not-an-audition"):
            with self.subTest(ref=ref):
                with self.assertRaises(errors.CoachError):
                    coaches.forget_audition(ref)
                with self.assertRaises(errors.CoachError):
                    coaches.keep_web(ref + "/A", "Coach Maya")
                self.assertTrue(os.path.isfile(os.path.join(stray, "candidates.json")))
        with self.assertRaises(errors.CoachError):   # never the auditions folder itself
            coaches.forget_audition(".")
        self.assertTrue(os.path.isdir(self.audition))

    def test_a_full_path_inside_the_auditions_still_works(self):
        import coaches
        said = "\n".join(coaches.forget_audition(self.audition))   # the path audition prints
        self.assertIn("Removed", said)
        self.assertFalse(os.path.exists(self.audition))

    def test_a_malformed_candidates_file_is_refused_by_name(self):
        import coaches
        good = {"letter": "A", "service": "fish", "k": 1, "wav": "fish-1.wav", "mp3": None}
        for bad in ({"letter": "A"}, [good, "B"], [dict(good, letter=1)], [dict(good, service="nope")],
                    [dict(good, k="1")], [dict(good, k=True)], [dict(good, wav="../../x.wav")],
                    [dict(good, mp3="/etc/x.mp3")]):
            with self.subTest(bad=bad):
                with open(self.cands, "w", encoding="utf-8") as f:
                    json.dump(bad, f)
                with self.assertRaises(errors.CoachError) as got:
                    coaches.forget_audition("2026-10-25-1")
                self.assertIn("candidates.json", str(got.exception))
                self.assertTrue(os.path.isdir(self.audition))
        with open(self.cands, "w", encoding="utf-8") as f:
            f.write("[{not json")
        with self.assertRaises(errors.CoachError):
            coaches.keep_web("2026-10-25-1/A", "Coach Maya")


class Make(unittest.TestCase):
    """coaches make: a pending stock web coach designed and saved once, however many builds ask at once."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import tone_wav
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        folder = persona_home(self.d)
        self.designs = []
        wav = tone_wav(0.5)

        class Fake:
            @staticmethod
            def design(description, line, n, label):
                self.designs.append(label)
                return [{"wav": wav, "text": line}]

            @staticmethod
            def save(candidate, name, description, wav):
                return "voice-1"

        import cloud
        for patch in (mock.patch.object(personas.paths, "PERSONAS", folder),
                      mock.patch.object(cloud, "service_module", lambda s: Fake)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_second_make_finds_the_coach_made_and_designs_nothing(self):
        import coaches
        stale = personas.lookup("Coach Reed")   # what a second build saw before the first finished
        self.assertTrue(stale.pending)
        said = []
        self.assertEqual(coaches.make("Coach Reed", report=said.append), "voice-1")
        real = personas.lookup
        calls = []

        def lookup(name, *a, **k):   # the second make's first look is the stale one
            calls.append(name)
            return stale if len(calls) == 1 else real(name, *a, **k)

        with mock.patch.object(personas, "lookup", lookup):
            self.assertEqual(coaches.make("Coach Reed", report=said.append), "voice-1")
        self.assertEqual(len(self.designs), 1)
        self.assertFalse(personas.lookup("Coach Reed").pending)
        with self.assertRaises(errors.CoachError):   # asked plainly, a made coach is still refused
            coaches.make("Coach Reed")

    def test_report_takes_what_make_says(self):
        import contextlib
        import io
        import coaches
        said, out = [], io.StringIO()
        with contextlib.redirect_stdout(out):
            coaches.make("Coach Reed", report=said.append)
        self.assertEqual(out.getvalue(), "")
        self.assertTrue(any(line.startswith("Made Coach Reed") for line in said))
        self.assertTrue(any("designing a voice" in line for line in said))


class AuditionReport(unittest.TestCase):
    """An audition's failures are returned, not printed by _run_audition; the command prints them once."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        folder = persona_home(self.d)
        self.narrative = os.path.join(self.d, "maya.md")
        with open(self.narrative, "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Maya", "voice": {"who": "a coach", "sound": "warm"}}, ""))
        import cloud

        class Refuses:
            @staticmethod
            def design(*a):
                raise cloud.ServiceError("unavailable", "fish", "down for a moment")

        import keys
        for patch in (mock.patch.object(personas.paths, "PERSONAS", folder),
                      mock.patch.object(cloud, "service_module", lambda s: Refuses),
                      mock.patch.object(keys, "is_set", lambda s: s == "fish")):
            patch.start()
            self.addCleanup(patch.stop)

    def test_failures_are_said_once(self):
        import contextlib
        import io
        import coaches
        said = []
        folder, cands, failures = coaches._run_audition(self.narrative, ["fish"], report=said.append)
        self.assertEqual((folder, cands, [s for s, _ in failures]), (None, [], ["fish"]))
        self.assertFalse(any("down for a moment" in line for line in said))
        out = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(out):
            coaches.main(["audition", self.narrative, "--services", "fish"])
        self.assertEqual(out.getvalue().count("down for a moment"), 1)   # the failure: once, on stderr
        self.assertNotIn("down for a moment", stdout.getvalue())

    def test_no_key_anywhere_is_warned_not_printed(self):
        import contextlib
        import io
        import audition
        import keys
        said, warned, out = [], [], io.StringIO()
        with mock.patch.object(keys, "is_set", lambda s: False), contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(out):
            got = audition._run_audition(self.narrative, report=said.append, warn=warned.append)
        self.assertEqual(got, (None, [], []))
        self.assertTrue(any("No web service has a key" in line for line in warned))
        self.assertEqual(out.getvalue(), "")

    def test_a_bug_in_a_service_module_is_raised_not_a_failure(self):
        """A TypeError while designing is the engine's bug (exit 70), never "no candidates" (exit 1)."""
        import cli
        import cloud
        import coaches

        class Broken:
            @staticmethod
            def design(*a):
                raise TypeError("a bug in the service module")

        with mock.patch.object(cloud, "service_module", lambda s: Broken):
            with self.assertRaises(TypeError):
                coaches._run_audition(self.narrative, ["fish"], report=lambda line: None)
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cli.run(lambda: coaches.main(["audition", self.narrative, "--services", "fish"])),
                                 cli.BUG)


class MakeLeftBehind(unittest.TestCase):
    """A make that saved a voice and then couldn't write the coach says so, with the voice's ID, through warn."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import tone_wav
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        wav = tone_wav(0.5)

        class Saves:
            @staticmethod
            def design(description, line, n, label):
                return [{"wav": wav, "text": line}]

            @staticmethod
            def save(candidate, name, description, wav):
                return "voice-9"

        import cloud
        for patch in (mock.patch.object(personas.paths, "PERSONAS", persona_home(self.d)),
                      mock.patch.object(cloud, "service_module", lambda s: Saves)):
            patch.start()
            self.addCleanup(patch.stop)

    def make(self, failing):
        import contextlib
        import io
        import coachmake
        said, warned, out = [], [], io.StringIO()
        with mock.patch.object(coachmake, failing, side_effect=OSError("disk full")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out), self.assertRaises(OSError):
            coachmake.make("Coach Reed", report=said.append, warn=warned.append)
        self.assertEqual(out.getvalue(), "")   # nothing printed: the caller decides where it goes
        self.assertTrue(personas.lookup("Coach Reed").pending)
        return warned

    def test_saved_and_recorded(self):
        warned = self.make("_write_sample")
        self.assertTrue(any("voice-9" in w and "Fish Audio" in w and "next build" in w for w in warned), warned)

    def test_saved_but_not_recorded(self):
        warned = self.make("_record_made")
        self.assertTrue(any("voice-9" in w and 'Delete "harmonicfitness Coach Reed"' in w for w in warned), warned)

    def test_the_old_names_still_reach_the_new_modules(self):
        import audition
        import coachmake
        import coaches
        self.assertIs(coaches.make, coachmake.make)
        self.assertIs(coaches.keep_web, audition.keep_web)
        self.assertIs(coaches.forget_audition, audition.forget_audition)
        self.assertIs(coaches.audition, audition.audition)


class SetAndList(unittest.TestCase):
    """The rules behind ./harmonicfitness coaches set and the list, reachable without the command line."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        folder = persona_home(self.d, ("Coach Dana", {"kind": "web", "service": "fish", "voice_id": "v1"}),
                              ("Coach Mine", {"kind": "local"}))
        patcher = mock.patch.object(personas.paths, "PERSONAS", folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_set_setting(self):
        for name in ("Coach Test", "Coach Reed"):   # stock: local and web alike
            with self.assertRaises(errors.CoachError) as got:
                personas.set_setting(personas.lookup(name), "description", "x")
            self.assertIn("roster.toml", str(got.exception))
        with self.assertRaises(errors.CoachError):   # a local coach of their own: its sound is its voice file
            personas.set_setting(personas.lookup("Coach Mine"), "description", "x")
        dana = personas.lookup("Coach Dana")
        with self.assertRaises(errors.CoachError):
            personas.set_setting(dana, "local.engine", "pocket")
        personas.set_setting(dana, "fish.model", "s2")
        personas.set_setting(dana, "description", "Warm and quick.")
        dana = personas.lookup("Coach Dana")
        self.assertEqual((dana.table("fish").get("model"), dana.description), ("s2", "Warm and quick."))

    def test_listing(self):
        import coaches
        found = coaches.listing(personas.lookup("Coach Dana"))
        by = {c["name"]: c for c in found}
        self.assertEqual(sorted(by["Coach Dana"]), sorted(["name", "slug", "kind", "service", "service_name", "default",
                                                           "placeholder", "pending", "shipped", "speaks_here",
                                                           "description", "notes"]))
        self.assertTrue(by["Coach Dana"]["default"])
        self.assertEqual(by["Coach Dana"]["service_name"], "Fish Audio")
        self.assertIn("(made the first time it's used)", by["Coach Reed"]["notes"])
        self.assertTrue(any("migrate archives it" in n for n in by["Coach Mine"]["notes"]))
        lines = coaches.listing_lines(found)
        self.assertTrue(any(line.startswith("* Coach Dana") and "web · Fish Audio" in line for line in lines))
        self.assertTrue(lines[-1].startswith("* the coach a build uses"))
        self.assertIn("No coaches found", coaches.listing_lines([])[0])

    def test_listing_says_which_coaches_speak_here(self):
        import coaches
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        with mock.patch.dict(os.environ, {**env, "GEMINI_API_KEY": "AIzaabc123def456abcd"}, clear=True), \
                mock.patch.object(coaches.keys.paths, "ENV_FILE", os.path.join(self.d, "absent.env")):
            by = {c["name"]: c for c in coaches.listing(facts={"local": "no", "local_reason": "test"})}
            web = [c for c in by.values() if c["kind"] == "web"]
            self.assertTrue(web)
            for c in web:
                self.assertEqual(c["speaks_here"], c["service"] == "gemini", c["name"])
                self.assertEqual(any("key here" in n for n in c["notes"]), c["service"] != "gemini", c["name"])
            self.assertFalse(any(c["speaks_here"] for c in by.values() if c["kind"] == "local"))
            with mock.patch.object(coaches.paths, "WEB", True):
                self.assertFalse(any(c["speaks_here"] for c in coaches.listing() if c["kind"] == "local"))

    def test_measured_takes_route_and_the_old_engine(self):
        import cli
        import coaches
        for flag in ("--route", "--engine"):
            with mock.patch.object(coaches.voices, "pace", return_value=(14.0, True)), \
                    mock.patch.object(coaches.coachpick, "pick", return_value="local") as pick:
                self.assertEqual(coaches.main(["measured", "Coach Test", flag, "local"]), cli.OK)
            self.assertEqual(pick.call_args.kwargs["override"], "local")


class NoPrintInLibrary(unittest.TestCase):
    """Library modules this release cleaned say things through report/warn callbacks: print only in the
    default sinks (say, stderr) and main."""
    CLEAN = ("audition.py", "coachmake.py", "catalog.py", "logsession.py", "frontmatter.py", "fileio.py")
    SINKS = {"say", "stderr", "_stderr", "main"}

    def test_no_print_outside_the_sinks(self):
        import ast
        found = []
        for name in self.CLEAN:
            path = os.path.join(ROOT, "tools", name)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), path)
            for fn in ast.walk(tree):
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name not in self.SINKS:
                    for node in ast.walk(fn):
                        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
                            found.append(f"{name}:{node.lineno} in {fn.name}")
        self.assertEqual(found, [])

    def test_an_unreadable_private_movements_file_is_a_fault_not_a_print(self):
        import contextlib
        import io
        import catalog
        path = os.path.join(tempfile.mkdtemp(), "movements.toml")
        with open(path, "w", encoding="utf-8") as f:
            f.write("[[movement]\nid = ")
        out = io.StringIO()
        with mock.patch.object(catalog.paths, "MY_MOVEMENTS", path), contextlib.redirect_stderr(out):
            cat = catalog.load()
        self.assertEqual(out.getvalue(), "")
        self.assertTrue(any("can't be read" in f for f in cat.private_faults))
        self.assertTrue(any("can't be read" in p for p in catalog.problems(cat)))
        self.assertIn("air-squat", cat.movements)


if __name__ == "__main__":
    unittest.main()
