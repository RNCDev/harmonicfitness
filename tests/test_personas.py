"""Coaches as persona folders (me/coaches/<slug>/, and the stock ones): clip, settings, pace and service voices.
No models: the fixture coach is half a second of a tone (tests/fixtures/stock/coach-test)."""
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
import personas  # noqa: E402

FIXTURE = personas.paths.SHIPPED   # the stock coaches the tests see (tests/fixtures/stock: ./harmonicfitness test sets HARMONICFITNESS_SHIPPED)


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
        import audition
        from fakes import FakeService
        with FakeService(lambda r: (201, {}, b"<html>saved, probably</html>")) as fake, \
                mock.patch.dict(os.environ, {"HARMONICFITNESS_FISH_URL": fake.url}):
            with self.assertRaises(cloud.ServiceError) as got:
                audition.keep_web("2026-10-25-1/A", "Coach Maya")
        self.assertIn("harmonicfitness Coach Maya", str(got.exception))
        with open(self.cands, encoding="utf-8") as f:
            self.assertEqual(json.load(f)[0]["saving"], "Coach Maya")   # the paid save is never forgotten
        self.assertFalse(os.path.exists(personas.folder_for("Coach Maya", "fish")))
        said = "\n".join(audition.forget_audition("2026-10-25-1"))
        self.assertIn('look for "harmonicfitness Coach Maya"', said)
        self.assertNotIn("nothing was saved", said)

    def test_an_audition_outside_its_folder_or_malformed_is_refused(self):
        """forget and keep reach only inside coaches/.auditions/ (a full path there still works), and a
        candidates.json naming a file outside its audition, or of the wrong shape, is refused by name."""
        import audition
        stray = os.path.join(self.d, "elsewhere", "not-an-audition")
        shutil.copytree(self.audition, stray)
        for ref in (stray, os.path.relpath(stray, os.path.join(self.d, "coaches", ".auditions")),
                    "../../elsewhere/not-an-audition"):
            with self.subTest(ref=ref):
                with self.assertRaises(errors.CoachError):
                    audition.forget_audition(ref)
                with self.assertRaises(errors.CoachError):
                    audition.keep_web(ref + "/A", "Coach Maya")
                self.assertTrue(os.path.isfile(os.path.join(stray, "candidates.json")))
        with self.assertRaises(errors.CoachError):   # never the auditions folder itself
            audition.forget_audition(".")
        self.assertTrue(os.path.isdir(self.audition))
        good = {"letter": "A", "service": "fish", "k": 1, "wav": "fish-1.wav", "mp3": None}
        for bad in ({"letter": "A"}, [good, "B"], [dict(good, letter=1)], [dict(good, service="nope")],
                    [dict(good, k="1")], [dict(good, k=True)], [dict(good, wav="../../x.wav")],
                    [dict(good, mp3="/etc/x.mp3")]):
            with self.subTest(bad=bad):
                with open(self.cands, "w", encoding="utf-8") as f:
                    json.dump(bad, f)
                with self.assertRaises(errors.CoachError) as got:
                    audition.forget_audition("2026-10-25-1")
                self.assertIn("candidates.json", str(got.exception))
                with self.assertRaises(errors.CoachError):
                    audition.keep_web("2026-10-25-1/A", "Coach Maya")
                self.assertTrue(os.path.isdir(self.audition))
        with open(self.cands, "w", encoding="utf-8") as f:
            f.write("[{not json")
        with self.assertRaises(errors.CoachError):
            audition.keep_web("2026-10-25-1/A", "Coach Maya")
        with open(self.cands, "w", encoding="utf-8") as f:
            json.dump([good], f)
        self.assertIn("Removed", " ".join(audition.forget_audition(self.audition)))   # the path audition prints
        self.assertFalse(os.path.exists(self.audition))


class Make(unittest.TestCase):
    """coaches make: a pending stock web coach designed and saved once, however many builds ask at once."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import tone_pcm, tone_wav
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        folder = persona_home(self.d)
        self.designs, self.spoken = [], []
        self.speaks = lambda text: tone_pcm(0.3)
        wav = tone_wav(0.5)
        case = self

        class Fake:
            @staticmethod
            def design(description, line, n, label):
                self.designs.append(label)
                return [{"wav": wav, "text": line}]

            @staticmethod
            def save(candidate, name, description, wav):
                return "voice-1"

            @staticmethod
            def speaker(voice):
                def say(text, seed, previous_text=None, next_text=None):
                    case.spoken.append(text)
                    return case.speaks(text)
                return say

        import cloud
        for patch in (mock.patch.object(personas.paths, "PERSONAS", folder),
                      mock.patch.object(cloud, "service_module", lambda s: Fake)):
            patch.start()
            self.addCleanup(patch.stop)

    def test_a_second_make_finds_the_coach_made_and_designs_nothing(self):
        import coachmake
        stale = personas.lookup("Coach Reed")   # what a second build saw before the first finished
        self.assertTrue(stale.pending)
        said = []
        self.assertEqual(coachmake.make("Coach Reed", report=said.append), "voice-1")
        real = personas.lookup
        calls = []

        def lookup(name, *a, **k):   # the second make's first look is the stale one
            calls.append(name)
            return stale if len(calls) == 1 else real(name, *a, **k)

        with mock.patch.object(personas, "lookup", lookup):
            self.assertEqual(coachmake.make("Coach Reed", report=said.append), "voice-1")
        self.assertEqual(len(self.designs), 1)
        self.assertFalse(personas.lookup("Coach Reed").pending)
        with self.assertRaises(errors.CoachError):   # asked plainly, a made coach is still refused
            coachmake.make("Coach Reed")

    def test_a_sample_that_fails_leaves_the_coach_made(self):
        import cloud
        import coachmake

        def refuses(text):
            raise cloud.ServiceError("unavailable", "fish", "down for a moment")
        self.speaks = refuses
        said = []
        self.assertEqual(coachmake.make("Coach Reed", report=said.append), "voice-1")
        self.assertFalse(personas.lookup("Coach Reed").pending)
        self.assertTrue(os.path.exists(personas.lookup("Coach Reed").sample))   # the design line's stays
        self.assertTrue(any('coaches sample "Coach Reed"' in line for line in said))

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
        import audition
        import coaches

        class Broken:
            @staticmethod
            def design(*a):
                raise TypeError("a bug in the service module")

        with mock.patch.object(cloud, "service_module", lambda s: Broken):
            with self.assertRaises(TypeError):
                audition._run_audition(self.narrative, ["fish"], report=lambda line: None)
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

    def test_the_web_client_never_makes_a_coach(self):
        import cli
        import coaches
        with mock.patch.object(coaches.paths, "WEB", True):
            for argv in (["audition", "narrative.md"], ["keep", "2026-10-31-1/A", "--name", "Coach Dana"]):
                self.assertEqual(cli.run(coaches.main, argv), errors.USAGE, argv)

if __name__ == "__main__":
    unittest.main()
