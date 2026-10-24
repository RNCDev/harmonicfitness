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
os.environ.setdefault("SWEATCAST_BACKEND", "mlx")

import context  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "personas")


def persona_home(d, *extra):
    """A personas folder holding the fixture coach, plus (name, settings) for each extra coach."""
    folder = os.path.join(d, "personas")
    shutil.copytree(FIXTURE, folder)
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
        with self.assertRaises(SystemExit) as e:
            personas.lookup("Coach Nobody")
        self.assertIn("Coach Test", str(e.exception.code))
        self.assertEqual([p.name for p in personas.all()], ["Coach O'Neil", "Coach Test", "Coach Zoë"])

    def test_voice_for_local_keeps_todays_keys(self):
        self.use(persona_home(self.d))
        p = personas.lookup("Coach Test")
        v = personas.voice_for(p, "local")
        with open(os.path.join(FIXTURE, "coach-test", "clip.wav"), "rb") as f:
            audio = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(v["key"], hashlib.sha256(f"{audio}|Set your feet. Chest up, and press.".encode()).hexdigest()[:12])
        self.assertEqual((v["model"], v["revision"]), voices.LOCAL_MODELS[("chatterbox", "mlx")])
        self.assertEqual((v["engine"], v["backend"], v["route"], v["name"]), ("chatterbox", "mlx", "local", "Coach Test"))
        self.assertEqual(v["pace_file"], os.path.join(self.d, "personas", "coach-test", "pace.json"))

    def test_local_model_pins_match_the_shipped_voices(self):
        for f in ("Chatterbox Coach.json", "Qwen3 Coach.json"):
            path = os.path.join(ROOT, "voices", f)
            if not os.path.exists(path):
                path = os.path.join(ROOT, "tools", "migrate-assets", "v8-voices", f)
            with open(path) as j:
                conf = json.load(j)
            self.assertEqual(voices.LOCAL_MODELS[(conf["engine"], "mlx")], (conf["model"], conf["revision"]))
            if conf.get("torch"):
                self.assertEqual(voices.LOCAL_MODELS[(conf["engine"], "torch")],
                                 (conf["torch"]["model"], conf["torch"]["revision"]))

    def test_pace_lives_in_the_persona(self):
        self.use(persona_home(self.d))
        v = personas.voice_for(personas.lookup("Coach Test"), "local")
        voices.record_rate(v, 500.0, 40.0, render_seconds=28.0)
        with open(v["pace_file"]) as f:
            data = json.load(f)
        entry = data[voices._rate_key(v)]
        self.assertEqual((entry["weight"], entry["seconds"]), (500.0, 40.0))
        self.assertAlmostEqual(list(entry["speed"].values())[0], 0.7)
        self.assertEqual(voices.pace(v), (12.5, True))

    def test_an_unmeasured_coach_is_seeded_from_the_other_coaches(self):
        self.use(persona_home(self.d, ("Coach Two", {})))
        one = personas.voice_for(personas.lookup("Coach Test"), "local")
        two = personas.voice_for(personas.lookup("Coach Two"), "local")
        voices.record_rate(one, 600.0, 40.0)
        rate, measured = voices.pace(two)
        self.assertFalse(measured)
        self.assertEqual(rate, 15.0)

    def test_qwen3_local_off_a_mac_says_why(self):
        self.use(persona_home(self.d, ("Coach Q", {"local": {"engine": "qwen3"}})))
        with mock.patch.object(voices, "BACKEND", "torch"):
            with self.assertRaises(SystemExit) as e:
                personas.voice_for(personas.lookup("Coach Q"), "local")
        self.assertIn("Mac", str(e.exception.code))
        self.assertEqual(personas.voice_for(personas.lookup("Coach Q"), "local")["model"],
                         voices.LOCAL_MODELS[("qwen3", "mlx")][0])

    def test_a_stock_only_persona_renders_only_on_deepgram(self):
        folder = os.path.join(self.d, "personas")
        os.makedirs(os.path.join(folder, "coach-stock"))
        with open(os.path.join(folder, "coach-stock", "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Stock", "stock_only": True,
                                          "deepgram": {"voice": "aura-2-thalia-en"}}, ""))
        self.use(folder)
        p = personas.lookup("Coach Stock")
        self.assertFalse(p.has_clip)
        with self.assertRaises(SystemExit) as e:
            personas.voice_for(p, "local")
        self.assertIn("Deepgram", str(e.exception.code))

    def test_service_voice_ids_are_keyed_by_clip(self):
        self.use(persona_home(self.d))
        p = personas.lookup("Coach Test")
        self.assertIsNone(personas.services_get(p, "elevenlabs", "abc"))
        personas.services_put(p, "elevenlabs", "abc", "voice-1")
        personas.services_put(p, "cartesia", "abc", "voice-2")
        self.assertEqual(personas.services_get(p, "elevenlabs", "abc"), "voice-1")
        self.assertIsNone(personas.services_get(p, "elevenlabs", "changed-clip"))

    def test_persona_settings_edit_in_place(self):
        self.use(persona_home(self.d))
        p = personas.lookup("Coach Test")
        context.set_persona_setting(p.path, "deepgram", "voice", "aura-2-apollo-en")
        context.set_persona_setting(p.path, "local", "engine", "qwen3")
        again = personas.lookup("Coach Test")
        self.assertEqual(again.settings["deepgram"]["voice"], "aura-2-apollo-en")
        self.assertEqual(again.settings["local"]["engine"], "qwen3")
        self.assertIn("How this coach talks", again.prose)


class Coaches(unittest.TestCase):
    """./sweatcast coaches: design takes, keep one as a coach, and choose the coach for a build."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.folder = persona_home(self.d)
        self.log = os.path.join(self.d, "log.md")
        for target, attr, value in ((personas.paths, "PERSONAS", self.folder), (personas.paths, "LOG", self.log)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_persona_from_a_cloud_designed_take(self):
        import base64
        import coaches
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import FakeService, tone_wav
        candidate = base64.b64encode(tone_wav(1.0, rate=44100)).decode()
        answer = lambda r: (200, {}, json.dumps({"candidates": [{"audio_base64": candidate, "sample_rate": 44100,
                                                                 "text": "Okay, set your feet."}]}).encode())
        with FakeService(answer) as fake, mock.patch.dict(os.environ, {"SWEATCAST_FISH_URL": fake.url,
                                                                       "FISH_AUDIO_API_KEY": "test-key"}):
            takes = coaches.design("Coach Maya", "A warm coach in her forties.", designer="fish", takes=1, seed=7,
                                   line="Okay, set your feet.")
        self.assertEqual(takes, [os.path.join(self.folder, "coach-maya", "takes", "1.wav")])
        name = coaches.keep(takes[0])
        self.assertEqual(name, "Coach Maya")
        p = personas.lookup("Coach Maya")
        self.assertTrue(p.has_clip)
        self.assertEqual(p.settings["local"]["engine"], "chatterbox")
        self.assertEqual(p.settings["designed_from"], "A warm coach in her forties.")
        self.assertIn("How this coach talks", p.prose)
        import wave
        with wave.open(p.clip) as w:
            self.assertEqual((w.getframerate(), w.getnchannels(), w.getsampwidth()), (24000, 1, 2))
        with open(p.clip_words) as f:
            self.assertEqual(f.read().strip(), "Okay, set your feet.")
        again = coaches.design("Coach Maya", "Warmer.", designer="fish", takes=1, seed=8, line="Hi.",
                               make_takes=lambda *a: [(b"\x00\x01" * 2400, "Hi.")])
        self.assertTrue(again[0].endswith("2.wav"))   # earlier takes are kept

    def test_persona_from_a_brought_clip(self):
        import coaches
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import tone_wav
        clip = os.path.join(self.d, "my-voice.wav")
        with open(clip, "wb") as f:
            f.write(tone_wav(1.0, rate=44100, channels=2))
        name = coaches.keep(clip, name="Coach Brought", words="Hello there, set your feet.")
        p = personas.lookup("coach-brought")
        import wave
        with wave.open(p.clip) as w:
            self.assertEqual((w.getframerate(), w.getnchannels()), (24000, 1))
            self.assertAlmostEqual(w.getnframes() / 24000, 1.0, delta=0.01)
        self.assertEqual(name, "Coach Brought")
        with self.assertRaises(SystemExit):   # a clip needs its words
            coaches.keep(clip, name="Coach Silent")

    def test_a_24k_mono_clip_is_kept_byte_for_byte(self):
        import coaches
        src = os.path.join(FIXTURE, "coach-test", "clip.wav")
        coaches.keep(src, name="Coach Copy", words="Set your feet. Chest up, and press.")
        with open(src, "rb") as a, open(personas.lookup("Coach Copy").clip, "rb") as b:
            self.assertEqual(a.read(), b.read())

    def write_log(self, *voices_used):
        lines = ["+++", "schema = 3", "+++", "# Log", "", "## Sessions", ""]
        lines += [f"- 2026-10-{10 + i} | 20 min | home | {v} | goblet squat | deep dive: news, x" for i, v in enumerate(voices_used)]
        lines += ["", "## Feedback", ""]
        with open(self.log, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def test_last_used_coach_from_the_log(self):
        import context
        context.set_persona_setting(personas.lookup("Coach Test").path, None, "aliases", ["Test Voice", "Coach E"])
        persona_home_extra = os.path.join(self.folder, "coach-two")
        shutil.copytree(os.path.join(self.folder, "coach-test"), persona_home_extra)
        context.set_persona_setting(os.path.join(persona_home_extra, "persona.md"), None, "name", "Coach Two")
        context.set_persona_setting(os.path.join(persona_home_extra, "persona.md"), None, "aliases", [])
        self.write_log("Coach Two", "Coach E")
        self.assertEqual(personas.last_coach().name, "Coach Test")
        self.write_log("Coach E", "Coach Two")
        self.assertEqual(personas.last_coach().name, "Coach Two")
        self.write_log()
        self.assertEqual(personas.last_coach().name, "Coach Test")   # no sessions: the first coach

    def test_log_session_takes_coach_and_voice(self):
        import context
        self.write_log()
        for flag in ("--coach", "--voice"):
            context.main(["log-session", "--date", "2026-10-24", "--minutes", "20", "--kit", "home", flag,
                          "Coach Test", "--movements", "goblet squat", "--topics", "deep dive: news, y"])
        self.assertEqual([s.voice for s in context.sessions(self.log)], ["Coach Test", "Coach Test"])

    def test_set_parses_values(self):
        import contextlib
        import io
        import coaches
        with contextlib.redirect_stdout(io.StringIO()):
            coaches.main(["set", "Coach Test", "local.engine", "qwen3"])
            coaches.main(["set", "Coach Test", "deepgram.voice", "aura-2-apollo-en"])
        p = personas.lookup("Coach Test")
        self.assertEqual((p.table("local")["engine"], p.table("deepgram")["voice"]), ("qwen3", "aura-2-apollo-en"))
        with self.assertRaises(SystemExit):
            coaches.main(["set", "Coach Test", "local.engine", "omnivoice"])


if __name__ == "__main__":
    unittest.main()
