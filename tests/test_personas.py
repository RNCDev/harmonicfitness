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

FIXTURE = personas.paths.SHIPPED   # the stock coaches the tests see (tests/fixtures/stock: ./sweatcast test sets SWEATCAST_SHIPPED)
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
                      mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test-key", "SWEATCAST_RETRY_WAIT": "0"})):
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
                mock.patch.dict(os.environ, {"SWEATCAST_FISH_URL": fake.url}):
            with self.assertRaises(cloud.ServiceError) as got:
                coaches.keep_web("2026-10-25-1/A", "Coach Maya")
        self.assertIn("sweatcast Coach Maya", str(got.exception))
        with open(self.cands, encoding="utf-8") as f:
            self.assertEqual(json.load(f)[0]["saving"], "Coach Maya")   # the paid save is never forgotten
        self.assertFalse(os.path.exists(personas.folder_for("Coach Maya", "fish")))
        said = "\n".join(coaches.forget_audition("2026-10-25-1"))
        self.assertIn('look for "sweatcast Coach Maya"', said)
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


if __name__ == "__main__":
    unittest.main()
