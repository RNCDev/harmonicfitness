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

    def test_voice_for_local_keeps_todays_keys(self):
        self.use(persona_home(self.d))
        p = personas.lookup("Coach Test")
        v = personas.voice_for(p, "local")
        with open(os.path.join(FIXTURE, "coach-test", "clip.wav"), "rb") as f:
            audio = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(v["key"], hashlib.sha256(f"{audio}|Set your feet. Chest up, and press.".encode()).hexdigest()[:12])
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


if __name__ == "__main__":
    unittest.main()
