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
    shutil.copytree(FIXTURE, folder, dirs_exist_ok=True)
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
        lines = ["+++", f"schema = {context.SCHEMA}", "+++", "# Log", "", "## Sessions", ""]
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
        import contextlib
        import io
        for flag in ("--coach", "--voice"):
            with contextlib.redirect_stdout(io.StringIO()):
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


MAYA = '''+++
schema = 5
name = "Coach Maya"
aliases = []
kind = "web"                     # web | local (local keeps today's clip files)
service = "inworld"              # fish | elevenlabs | gemini | inworld
voice_id = "funky-finch-6967__design-voice-a5809f1c"
model = "inworld-tts-2"          # optional; default from knowledge/services.toml
style = ""                       # Gemini only: a short constant style annotation, or empty
made = "2026-10-25"

[voice]                          # what the services design or match from
who = "A woman in her thirties, a strength coach"
sound = "Warm, mid-low, American accent, crisp diction"
energy = "Steady, calm authority"
pace = "Natural; brisk during work"
avoid = "Hype, shouting, announcer voice, sleepy delivery"

[character]                      # what the script writer follows (the brief quotes it)
background = "Ten years coaching clients one on one"
calls_you = "Alex"
encouragement = "Notices effort plainly; says why a movement is there"
pushes = "Asks for one more only when form is clean; backs off at pain"
humor = "Dry, now and then"
cueing = "Short body cues and breath; counts only on timed work"
signature = ["Stay with it.", "That's the pace we want."]
never_says = ["Crush it", "Beast mode", "No pain, no gain"]
sign_off = "Brief and warm; names one thing done well"
+++
Free notes on how this coach talks.
'''


def write_persona(folder, slug_, text):
    os.makedirs(os.path.join(folder, slug_), exist_ok=True)
    with open(os.path.join(folder, slug_, "persona.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.join(folder, slug_)


def web_placeholder(name, service):
    return context.persona_text({"name": name, "kind": "web", "service": service, "placeholder": True,
                                 "pending": "design"}, "## How this coach talks\n")


class WebCoaches(unittest.TestCase):
    """Schema 5: web coaches (kind, service, voice_id, [voice], [character]) and the archive."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.folder = persona_home(self.d)
        self.env = os.path.join(self.d, ".env")
        patches = [mock.patch.object(personas.paths, "PERSONAS", self.folder),
                   mock.patch.object(personas.paths, "ENV_FILE", self.env),
                   mock.patch.dict(os.environ, {k: v for k, v in os.environ.items()
                                                if not k.endswith("_API_KEY")}, clear=True)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def maya(self):
        write_persona(self.folder, "coach-maya", MAYA)
        return personas.lookup("Coach Maya")

    def test_web_persona_fields(self):
        p = self.maya()
        self.assertEqual((p.kind, p.service, p.voice_id, p.model, p.style, p.pending),
                         ("web", "inworld", "funky-finch-6967__design-voice-a5809f1c", "inworld-tts-2", "", None))
        self.assertTrue(p.is_web)
        self.assertEqual(p.character["signature"], ["Stay with it.", "That's the pace we want."])
        self.assertEqual(p.voice["who"], "A woman in her thirties, a strength coach")
        self.assertEqual(p.sample, os.path.join(self.folder, "coach-maya", "sample.mp3"))
        again = context.persona_text(p.settings, p.prose)
        self.assertEqual(context.tomllib.loads(context.TOML_FRONT_RE.match(again).group(1)), p.settings)
        self.assertTrue(again.endswith("Free notes on how this coach talks.\n"))
        local = personas.lookup("Coach Test")
        self.assertEqual((local.kind, local.is_web, local.service, local.voice_id, local.model, local.style,
                          local.voice, local.character), ("local", False, None, None, None, "", {}, {}))

    def test_voice_description_joins_the_voice_table(self):
        self.assertEqual(personas.voice_description(self.maya().voice),
                         "A woman in her thirties, a strength coach. Warm, mid-low, American accent, crisp diction. "
                         "Steady, calm authority. Pace: Natural; brisk during work. Avoid: Hype, shouting, "
                         "announcer voice, sleepy delivery.")
        self.assertEqual(personas.voice_description({"who": "A man", "energy": "", "avoid": "Hype"}),
                         "A man. Avoid: Hype.")

    def test_web_key_changes_with_voice_id_model_and_style(self):
        p = self.maya()
        key = personas.web_key(p, "inworld-tts-2")
        self.assertRegex(key, r"^[0-9a-f]{12}$")
        self.assertEqual(key, personas.web_key(p, "inworld-tts-2"))
        self.assertNotEqual(key, personas.web_key(p, "inworld-tts-2-flash"))
        for k, v in (("voice_id", "another-voice"), ("style", "Warm and close.")):
            context.set_persona_setting(p.path, None, k, v)
            changed = personas.lookup("Coach Maya")
            self.assertNotEqual(key, personas.web_key(changed, "inworld-tts-2"), k)
            key = personas.web_key(changed, "inworld-tts-2")

    def test_all_skips_dot_folders(self):
        write_persona(os.path.join(self.folder, ".archive"), "x", web_placeholder("Coach X", "fish"))
        write_persona(os.path.join(self.folder, ".auditions"), "y", web_placeholder("Coach Y", "fish"))
        self.assertEqual([p.name for p in personas.all()], ["Coach Test"])
        self.assertTrue(personas.ARCHIVE.endswith(os.path.join("personas", ".archive")))
        self.assertTrue(personas.AUDITIONS.endswith(os.path.join("personas", ".auditions")))
        self.assertEqual(context.check_coaches(self.folder), [])

    def test_archived_coach_found_only_when_asked(self):
        persona_home(self.d, ("Coach Julius", {"aliases": ["Chatterbox Coach"]}))
        moved = personas.archive(personas.lookup("Coach Julius"))
        self.assertEqual(moved, os.path.join(self.folder, ".archive", "coach-julius"))
        self.assertTrue(os.path.exists(os.path.join(moved, "persona.md")))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "coach-julius")))
        with self.assertRaises(SystemExit):
            personas.lookup("Coach Julius")
        self.assertEqual(personas.lookup("Coach Julius", archived=True).folder, moved)
        self.assertEqual(personas.lookup("chatterbox coach", archived=True).name, "Coach Julius")
        self.assertEqual(personas.lookup("Coach Test", archived=True).name, "Coach Test")   # active still found
        persona_home(self.d, ("Coach Julius", {}))   # a second coach of the same name archives beside it
        self.assertEqual(personas.archive(personas.lookup("Coach Julius")),
                         os.path.join(self.folder, ".archive", "coach-julius-2"))

    def test_default_stops_when_last_coach_is_archived(self):
        persona_home(self.d, ("Coach Julius", {}), ("Coach Maya", {}))
        personas.archive(personas.lookup("Coach Julius"))
        used = [mock.Mock(voice="Coach Maya"), mock.Mock(voice="Coach Julius")]
        with mock.patch.object(context, "sessions", return_value=used):
            with self.assertRaises(SystemExit) as e:
                personas.default()
        message = str(e.exception.code)
        self.assertIn("Coach Julius is archived", message)
        self.assertIn("Coach Maya", message)
        self.assertIn("Coach Test", message)
        with mock.patch.object(context, "sessions", return_value=used[:1]):
            self.assertEqual(personas.default().name, "Coach Maya")

    def test_default_prefers_a_usable_web_default(self):
        import routes
        folder = os.path.join(self.d, "only-placeholders")
        demo = write_persona(folder, "coach-demo", context.persona_text(
            {"name": "Coach Demo", "kind": "local", "placeholder": True}, "## How this coach talks\n"))
        shutil.copy(os.path.join(FIXTURE, "coach-test", "clip.wav"), os.path.join(demo, "clip.wav"))
        shutil.copy(os.path.join(FIXTURE, "coach-test", "clip.txt"), os.path.join(demo, "clip.txt"))
        write_persona(folder, "coach-ellis", web_placeholder("Coach Ellis", "elevenlabs"))
        write_persona(folder, "coach-reed", web_placeholder("Coach Reed", "fish"))
        no_local = mock.patch.object(routes, "usable", return_value=(False, "local: not here"))
        with mock.patch.object(context, "sessions", return_value=[]), no_local:
            self.assertEqual(personas.default(folder).name, "Coach Demo")   # nothing usable: the first
            with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test-key"}):
                self.assertEqual(personas.default(folder).name, "Coach Reed")
                shutil.copytree(os.path.join(FIXTURE, "coach-test"), os.path.join(folder, "coach-test"))
                self.assertEqual(personas.default(folder).name, "Coach Test")   # a coach of their own wins
        with mock.patch.object(context, "sessions", return_value=[]), \
                mock.patch.object(routes, "usable", return_value=(True, "")):
            shutil.rmtree(os.path.join(folder, "coach-test"))
            self.assertEqual(personas.default(folder).name, "Coach Demo")   # local works: Coach Demo

    def test_schema_4_persona_says_migrate(self):
        path = os.path.join(write_persona(self.folder, "coach-old", '+++\nschema = 4\nname = "Coach Old"\n+++\n'),
                            "persona.md")
        with self.assertRaises(SystemExit) as e:
            context.persona(path)
        self.assertIn("./sweatcast migrate", str(e.exception.code))
        issues = context.check_coaches(self.folder)
        self.assertTrue(any("./sweatcast migrate" in i.message and not i.note for i in issues), issues)

    def test_check_web_coach(self):
        write_persona(self.folder, "coach-new", context.persona_text(
            {"name": "Coach New", "kind": "web", "service": "fish"}, "## How this coach talks\n"))
        issues = context.check_coaches(self.folder)
        self.assertEqual(len(issues), 1, issues)
        self.assertFalse(issues[0].note)
        self.assertIn("voice", issues[0].message)
        self.assertNotIn("clip", issues[0].message)
        context.set_persona_setting(issues[0].path, None, "pending", "design")
        issues = context.check_coaches(self.folder)
        self.assertEqual(len(issues), 1, issues)
        self.assertTrue(issues[0].note)
        self.maya()
        self.assertEqual(len(context.check_coaches(self.folder)), 1)   # Maya has her voice: nothing to say


class CoachDemo(unittest.TestCase):
    """Coach Demo ships in me.example/ with its pace measured, as a stand-in until the listener makes one."""
    DEMO = os.path.join(ROOT, "me.example", "personas")

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def use(self, folder):
        patcher = mock.patch.object(personas.paths, "PERSONAS", folder)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_demo_ships_measured(self):
        self.use(self.DEMO)
        p = personas.lookup("Coach Demo")
        self.assertTrue(p.placeholder)
        self.assertTrue(p.has_clip)
        for route in ("fish",):
            self.assertTrue(voices.pace(personas.voice_for(p, route))[1], route)
        with open(p.pace_file, encoding="utf-8") as f:
            pace = json.load(f)
        self.assertTrue(all("speed" not in rec for rec in pace.values()))   # no computer's name ships
        key, _ = personas.clip_key(p)
        self.assertTrue(all(k.startswith(key + "|") for k in pace))

    def test_demo_local_pace_is_measured_on_mlx(self):
        self.use(self.DEMO)
        p = personas.lookup("Coach Demo")
        with mock.patch.object(voices, "BACKEND", "mlx"):
            v = personas.voice_for(p, "local")
        self.assertTrue(voices.pace(v)[1])

    def test_default_prefers_non_placeholder(self):
        folder = os.path.join(self.d, "personas")
        shutil.copytree(self.DEMO, folder, ignore=shutil.ignore_patterns(".gitkeep"))
        self.use(folder)
        with mock.patch.object(context, "sessions", return_value=[]):
            self.assertEqual(personas.default().name, "Coach Demo")   # the only one
            persona_home(self.d, ("Coach Maya", {}))
            self.assertEqual(personas.default().name, "Coach Maya")
        used = mock.Mock(voice="Coach Demo")
        with mock.patch.object(context, "sessions", return_value=[used]):
            self.assertEqual(personas.default().name, "Coach Demo")   # used last wins

    def test_check_notes_placeholder(self):
        folder = os.path.join(self.d, "personas")
        shutil.copytree(self.DEMO, folder, ignore=shutil.ignore_patterns(".gitkeep"))
        issues = context.check_coaches(folder)
        self.assertEqual(len(issues), 1, issues)
        self.assertTrue(issues[0].note)
        self.assertIn("stand-in", issues[0].message)


if __name__ == "__main__":
    unittest.main()
