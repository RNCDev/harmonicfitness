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


if __name__ == "__main__":
    unittest.main()
