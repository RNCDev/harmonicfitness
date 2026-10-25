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
import ffmpeg  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402
from v8 import HAS_V8_TAG, v8_file  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "personas")
FFMPEG = ffmpeg.exe()   # the MP3s need it; without it they're skipped, as in test_webcopy


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

    @unittest.skipUnless(HAS_V8_TAG, "needs the v8.0.1 tag (a git clone)")
    def test_local_model_pins_match_the_shipped_voices(self):
        for stem in ("Chatterbox Coach", "Qwen3 Coach"):
            conf = json.loads(v8_file(stem, ".json"))
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

    def test_persona_settings_edit_in_place(self):
        self.use(persona_home(self.d))
        p = personas.lookup("Coach Test")
        context.set_persona_setting(p.path, "elevenlabs", "model", "eleven_v4_turbo")
        context.set_persona_setting(p.path, "local", "engine", "qwen3")
        again = personas.lookup("Coach Test")
        self.assertEqual(again.settings["elevenlabs"]["model"], "eleven_v4_turbo")
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

    def test_persona_from_a_designed_take(self):
        import coaches
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from fakes import tone_pcm
        made = lambda description, line, takes, seed: [(tone_pcm(1.0), line)]
        takes = coaches.design("Coach Maya", "A warm coach in her forties.", designer="local", takes=1, seed=7,
                               line="Okay, set your feet.", make_takes=made)
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
        again = coaches.design("Coach Maya", "Warmer.", designer="local", takes=1, seed=8, line="Hi.",
                               make_takes=lambda *a: [(b"\x00\x01" * 2400, "Hi.")])
        self.assertTrue(again[0].endswith("2.wav"))   # earlier takes are kept

    def test_only_the_local_designer_makes_takes(self):
        import coaches
        self.assertEqual(coaches.DESIGNERS, ("local",))
        with self.assertRaises(SystemExit):
            coaches.design("Coach Maya", "A warm coach.", designer="fish", make_takes=lambda *a: [])

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
            coaches.main(["set", "Coach Test", "elevenlabs.model", "eleven_v4_turbo"])
        p = personas.lookup("Coach Test")
        self.assertEqual((p.table("local")["engine"], p.table("elevenlabs")["model"]), ("qwen3", "eleven_v4_turbo"))
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

    def test_check_flags_a_style_the_api_cant_take(self):
        write_persona(self.folder, "coach-nolan", context.persona_text(
            {"name": "Coach Nolan", "kind": "web", "service": "gemini", "voice_id": "voice-abc",
             "style": "Calm and warm"}, "## How this coach talks\n"))
        issues = [i for i in context.check_coaches(self.folder) if "coach-nolan" in i.path]
        self.assertEqual(len(issues), 1, issues)
        self.assertFalse(issues[0].note)
        self.assertIn("Gemini's API takes no style setting yet (2026-10-25); leave style empty", issues[0].message)
        context.set_persona_setting(issues[0].path, None, "style", "")
        self.assertEqual([i for i in context.check_coaches(self.folder) if "coach-nolan" in i.path], [])


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
        with self.assertRaises(SystemExit):   # a local coach renders only locally
            personas.voice_for(p, "fish")
        with open(p.pace_file, encoding="utf-8") as f:
            pace = json.load(f)
        self.assertTrue(all("speed" not in rec for rec in pace.values()))   # no computer's name ships
        key, _ = personas.clip_key(p)
        self.assertTrue(all(k.startswith(key + "|") for k in pace))
        self.assertEqual(p.kind, "local")
        self.assertEqual(sorted(k.split("|")[1] for k in pace), ["chatterbox", "chatterbox"])   # local only

    def test_demo_local_pace_is_measured_on_mlx(self):
        self.use(self.DEMO)
        p = personas.lookup("Coach Demo")
        with mock.patch.object(voices, "BACKEND", "mlx"):
            v = personas.voice_for(p, "local")
        self.assertTrue(voices.pace(v)[1])

    def test_default_prefers_non_placeholder(self):
        folder = os.path.join(self.d, "personas")
        shutil.copytree(os.path.join(self.DEMO, "coach-demo"), os.path.join(folder, "coach-demo"))
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
        self.assertTrue(all(i.note for i in issues), issues)   # five stand-ins, four made on first use
        self.assertEqual(sum("stand-in" in i.message for i in issues), 5, issues)
        pending = [i for i in issues if "pending" in i.message]
        self.assertEqual(len(pending), 4, issues)
        self.assertTrue(all("first time" in i.message for i in pending), pending)

    def test_four_defaults_share_one_description(self):
        self.use(self.DEMO)
        found = {p.service: p for p in personas.all() if p.is_web}
        self.assertEqual(sorted(found), sorted(SERVICE_ORDER))
        self.assertEqual({s: p.name for s, p in found.items()},
                         {"fish": "Coach Reed", "elevenlabs": "Coach Ellis", "gemini": "Coach Nolan",
                          "inworld": "Coach Owen"})
        reed = found["fish"]
        self.assertEqual(reed.voice, {"who": "A man in his forties, a seasoned personal trainer talking to one client",
                                      "sound": "Low, warm baritone, American accent, clear diction",
                                      "energy": "Steady and grounded, calm authority",
                                      "pace": "Natural; brisk during work",
                                      "avoid": "Hype, shouting, announcer voice, sleepy delivery"})
        for p in found.values():
            self.assertEqual((p.kind, p.placeholder, p.pending, p.voice_id), ("web", True, "design", None))
            self.assertEqual((p.voice, p.character, p.description), (reed.voice, reed.character, reed.description))
            again = context.persona_text(p.settings, p.prose)
            self.assertEqual(context.tomllib.loads(context.TOML_FRONT_RE.match(again).group(1)), p.settings)
        self.assertIn("calm", reed.character["tone"].lower())
        self.assertEqual(personas.lookup("Coach Demo").kind, "local")



NARRATIVE = """+++
schema = 5

[voice]
who = "A woman in her thirties, a strength coach"
sound = "Warm, mid-low, American accent, crisp diction"
energy = "Steady, calm authority"
pace = "Natural; brisk during work"
avoid = "Hype, shouting, announcer voice, sleepy delivery"

[character]
calls_you = "Alex"
signature = ["Stay with it.", "That's the pace we want."]
+++
Free notes on how this coach talks.
"""
SERVICE_ORDER = ("fish", "elevenlabs", "gemini", "inworld")


class Auditions(unittest.TestCase):
    """./sweatcast coaches audition, keep, forget-audition, archive and the list, against fake services."""

    def setUp(self):
        import keys
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import fakes
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.folder = persona_home(self.d)
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        env["SWEATCAST_RETRY_WAIT"] = "0"
        self.fakes = {}
        for svc in SERVICE_ORDER:
            fake = fakes.FakeService(fakes.design_answer(svc))
            fake.__enter__()
            self.addCleanup(fake.__exit__)
            self.fakes[svc] = fake
            env[f"SWEATCAST_{svc.upper()}_URL"] = fake.url
            env[keys.SERVICE_VARS[svc]] = f"test-key-{svc}"
        patches = [mock.patch.object(personas.paths, "PERSONAS", self.folder),
                   mock.patch.object(personas.paths, "ENV_FILE", os.path.join(self.d, ".env")),
                   mock.patch.object(personas.paths, "LOG", os.path.join(self.d, "log.md")),
                   mock.patch.dict(os.environ, env, clear=True)]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.narrative = os.path.join(self.d, "maya.md")
        with open(self.narrative, "w", encoding="utf-8") as f:
            f.write(NARRATIVE)
        self.today = __import__("datetime").date.today().isoformat()

    def quiet(self, fn, *args, **kw):
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            result = fn(*args, **kw)
        return result, out.getvalue()

    def audition(self, *args, **kw):
        import coaches
        folder, self.said = self.quiet(coaches.audition, *args, **kw)
        return folder

    def candidates(self, folder):
        with open(os.path.join(folder, "candidates.json"), encoding="utf-8") as f:
            return json.load(f)

    def paths_of(self, svc, method="POST"):
        return [r.path for r in self.fakes[svc].requests if r.method == method]

    def test_audition_makes_lettered_candidates_from_every_keyed_service(self):
        folder = self.audition(self.narrative)
        self.assertEqual(os.path.dirname(folder), os.path.join(self.folder, ".auditions"))
        self.assertEqual(os.path.basename(folder), f"{self.today}-1")
        c = self.candidates(folder)
        self.assertEqual([x["letter"] for x in c], list("ABCDEFGH"))
        self.assertEqual([(x["service"], x["k"]) for x in c],
                         [("fish", 1), ("fish", 2), ("elevenlabs", 1), ("elevenlabs", 2), ("elevenlabs", 3),
                          ("gemini", 1), ("inworld", 1), ("inworld", 2)])
        for x in c:
            self.assertTrue(os.path.exists(os.path.join(folder, x["wav"])), x)
            self.assertEqual(set(x) >= {"letter", "service", "k", "draft_id", "signature", "text", "wav", "mp3",
                                        "usd_per_workout", "design_usd", "note"}, True)
            if FFMPEG:
                self.assertTrue(os.path.exists(os.path.join(folder, x["mp3"])), x)
        by = {x["letter"]: x for x in c}
        self.assertEqual((by["A"]["signature"], by["A"]["draft_id"]), ("sig-0", "cand-0"))
        self.assertEqual(by["C"]["draft_id"], "g0")
        self.assertAlmostEqual(by["A"]["usd_per_workout"], 0.30)
        self.assertAlmostEqual(by["C"]["usd_per_workout"], 1.60)
        self.assertEqual(by["A"]["design_usd"], 0.01)
        self.assertIsNone(by["C"]["design_usd"])
        self.assertIn("Free keeps 3 voices", by["C"]["note"])
        with open(os.path.join(folder, "fish-1.wav"), "rb") as f:   # Fish's own WAV, kept as sent
            self.assertEqual(f.read()[:4], b"RIFF")
        self.assertTrue(os.path.exists(os.path.join(folder, "narrative.md")))
        # nothing saved: only the designs (and Gemini's one line of speech)
        self.assertEqual(self.paths_of("fish"), ["/v1/voice-design"])
        self.assertEqual([p.split("?")[0] for p in self.paths_of("elevenlabs")], ["/v1/text-to-voice/design"])
        self.assertEqual(self.paths_of("inworld"), ["/voices/v1/voices:design"])
        self.assertEqual(self.paths_of("gemini"), ["/v1beta/voices", "/v1beta/interactions"])
        design = json.loads(self.fakes["gemini"].requests[0].body)
        self.assertEqual(design["voice"]["display_name"], f"sweatcast audition {self.today}-1 F")
        fish = json.loads(self.fakes["fish"].requests[0].body)
        self.assertEqual(fish["instruction"], personas.voice_description(context.persona(self.narrative).settings["voice"]))
        self.assertEqual(fish["n"], 2)
        self.assertEqual(json.loads(self.fakes["inworld"].requests[0].body)["numberOfSamples"], 2)
        self.assertIn("about $1.60 a workout", self.said)
        self.assertIn("about $0.01", self.said)
        self.assertIn("design cost not published", self.said)
        self.assertEqual(os.path.basename(self.audition(self.narrative)), f"{self.today}-2")

    def test_audition_survives_one_service_failing(self):
        import cli
        import coaches
        self.fakes["inworld"].answer = lambda r: (401, {}, b'{"message": "Invalid api key"}')
        folder = self.audition(self.narrative)
        self.assertEqual([x["service"] for x in self.candidates(folder)].count("inworld"), 0)
        self.assertEqual(len(self.candidates(folder)), 6)
        self.assertIn("Inworld: no candidates", self.said)
        code, _ = self.quiet(coaches.main, ["audition", self.narrative])
        self.assertEqual(code, cli.OK)
        for fake in self.fakes.values():
            fake.answer = lambda r: (401, {}, b'{"message": "Invalid api key"}')
        code, said = self.quiet(coaches.main, ["audition", self.narrative])
        self.assertEqual(code, cli.SERVICE)
        for svc in ("Fish Audio", "ElevenLabs", "Gemini", "Inworld"):
            self.assertIn(f"{svc}: no candidates", said)
        for fake in self.fakes.values():
            fake.answer = lambda r: (400, {}, b'{"message": "bad description"}')
        code, _ = self.quiet(coaches.main, ["audition", self.narrative])
        self.assertEqual(code, cli.ISSUES)
        import keys
        for svc in SERVICE_ORDER:
            del os.environ[keys.SERVICE_VARS[svc]]
        code, said = self.quiet(coaches.main, ["audition", self.narrative])
        self.assertEqual(code, cli.ISSUES)
        self.assertIn("./sweatcast keys", said)

    def test_audition_only_named_services(self):
        import coaches
        folder = self.audition(self.narrative, services=["fish", "gemini"])
        c = self.candidates(folder)
        self.assertEqual([(x["letter"], x["service"]) for x in c], [("A", "fish"), ("B", "fish"), ("C", "gemini")])
        self.assertEqual(self.fakes["elevenlabs"].requests, [])
        self.assertEqual(self.fakes["inworld"].requests, [])
        self.assertTrue(json.loads(self.fakes["gemini"].requests[0].body)["voice"]["display_name"].endswith(" C"))
        code, _ = self.quiet(coaches.main, ["audition", self.narrative, "--services", "inworld"])
        self.assertEqual(code, 0)
        self.assertEqual(len(self.paths_of("inworld")), 1)
        with self.assertRaises(SystemExit):
            coaches.audition(self.narrative, services=["nonesuch"])

    def keep(self, ref, name, **kw):
        import coaches
        folder, self.said = self.quiet(coaches.keep_web, ref, name, **kw)
        return folder

    def test_keep_saves_and_writes_the_coach(self):
        import coaches
        folder = self.audition(self.narrative)
        code, said = self.quiet(coaches.main, ["keep", os.path.join(folder, "A"), "--name", "Coach Maya"])
        self.assertEqual(code, 0, said)
        p = personas.lookup("Coach Maya")
        self.assertEqual(p.folder, os.path.join(self.folder, "coach-maya"))
        self.assertEqual((p.kind, p.service, p.voice_id, p.settings["made"]), ("web", "fish", "fish-model-1", self.today))
        self.assertEqual(p.voice["who"], "A woman in her thirties, a strength coach")
        self.assertEqual(p.character["signature"], ["Stay with it.", "That's the pace we want."])
        self.assertIn("Free notes on how this coach talks.", p.prose)
        self.assertNotIn("model", p.settings)
        if FFMPEG:
            self.assertTrue(os.path.exists(p.sample))
        saves = [r for r in self.fakes["fish"].requests if r.path == "/model"]
        self.assertEqual(len(saves), 1)
        self.assertIn(b"sweatcast Coach Maya", saves[0].body)
        with open(os.path.join(folder, "fish-1.wav"), "rb") as f:
            self.assertIn(f.read(), saves[0].body)   # Fish gets its own WAV back with the signature
        self.assertIn(b"sig-0", saves[0].body)
        v = personas.voice_for(p, "fish")
        rate, measured = voices.pace(v)
        self.assertFalse(measured)
        with open(p.pace_file, encoding="utf-8") as f:
            rec = json.load(f)[f"{v['key']}|fish|s2.1-pro"]
        self.assertTrue(rec["estimate"])
        self.assertEqual(rec["weight"], voices.weight("Okay, set your feet."))
        self.assertAlmostEqual(rate, rec["weight"] / rec["seconds"])
        self.assertLess(rec["seconds"], 1.05)
        self.assertEqual(self.candidates(folder)[0]["kept"], "Coach Maya")
        with self.assertRaises(SystemExit):   # one candidate, one coach
            coaches.keep_web(os.path.join(folder, "A"), "Coach Mara")

    def test_keep_two_from_one_audition(self):
        folder = self.audition(self.narrative)
        audition_id = os.path.basename(folder)
        self.keep(f"{audition_id}/inworld-2", "Coach Maya")
        self.keep(f"{audition_id}/d", "Coach Dana")
        maya, dana = personas.lookup("Coach Maya"), personas.lookup("Coach Dana")
        self.assertEqual((maya.service, maya.voice_id), ("inworld", "ws__design-1"))
        self.assertEqual((dana.service, dana.voice_id), ("elevenlabs", "el-saved-5"))
        publish = [r for r in self.fakes["inworld"].requests if r.path.endswith(":publish")]
        self.assertEqual(json.loads(publish[0].body)["displayName"], "sweatcast Coach Maya")
        save = [r for r in self.fakes["elevenlabs"].requests if r.path == "/v1/text-to-voice"]
        self.assertEqual(json.loads(save[0].body)["generated_voice_id"], "g1")
        self.assertEqual(json.loads(save[0].body)["voice_name"], "sweatcast Coach Dana")
        kept = {x["letter"]: x.get("kept") for x in self.candidates(folder)}
        self.assertEqual((kept["D"], kept["H"], kept["A"]), ("Coach Dana", "Coach Maya", None))

    def test_revoice_replaces_voice_and_clears_old_pace(self):
        import coaches
        first = self.audition(self.narrative, services=["inworld"])
        self.keep(f"{first}/A", "Coach Maya")
        old = personas.lookup("Coach Maya")
        old_voice = personas.voice_for(old, "inworld")
        voices.record_rate(old_voice, 600.0, 40.0)
        context.set_persona_setting(old.path, "character", "humor", "Dry, now and then")
        with self.assertRaises(SystemExit):   # a coach is re-voiced on its own service only
            coaches.audition(None, services=["fish"], coach="Coach Maya")
        again = self.audition(None, coach="Coach Maya")
        self.assertEqual({x["service"] for x in self.candidates(again)}, {"inworld"})
        self.assertEqual({x.get("coach") for x in self.candidates(again)}, {"Coach Maya"})
        self.keep(f"{again}/B", "Coach Maya", replace_old=True)
        new = personas.lookup("Coach Maya")
        self.assertEqual(new.voice_id, "ws__design-1")
        self.assertEqual(new.character["humor"], "Dry, now and then")   # how they talk is kept
        with open(new.pace_file, encoding="utf-8") as f:
            recorded = json.load(f)
        self.assertFalse(any(k.startswith(old_voice["key"] + "|") for k in recorded), recorded)
        new_voice = personas.voice_for(new, "inworld")
        self.assertTrue(recorded[f"{new_voice['key']}|inworld|inworld-tts-2"]["estimate"])
        self.assertEqual(self.paths_of("inworld", "DELETE"), ["/voices/v1/voices/ws__design-0"])
        if FFMPEG:
            self.assertTrue(os.path.exists(new.sample))
        self.assertEqual(len(personas.all()), 2)   # Coach Test and Coach Maya: no second folder

    def test_forget_audition_deletes_unkept_gemini_only(self):
        import coaches
        first = self.audition(self.narrative, services=["fish", "gemini"])
        self.keep(f"{first}/C", "Coach Nolan")
        lines, _ = self.quiet(coaches.forget_audition, os.path.basename(first))
        self.assertFalse(os.path.exists(first))
        self.assertEqual(self.paths_of("gemini", "DELETE"), [])
        self.assertEqual(self.paths_of("fish", "DELETE"), [])
        self.assertTrue(any("need nothing" in line for line in lines), lines)
        second = self.audition(self.narrative, services=["gemini"])
        self.fakes["gemini"].answer = lambda r: (401, {}, b'{"message": "Invalid api key"}')
        with self.assertRaises(SystemExit):   # the voice is still stored: keep the record to retry
            self.quiet(coaches.forget_audition, second)
        self.assertTrue(os.path.exists(second))
        self.fakes["gemini"].answer = lambda r: (204, {}, b"")
        code, said = self.quiet(coaches.main, ["forget-audition", second])
        self.assertEqual(code, 0)
        self.assertEqual(self.paths_of("gemini", "DELETE")[-1], "/v1beta/voices/gem-voice-2")
        self.assertFalse(os.path.exists(second))

    def test_archive_moves_and_lists_without_it(self):
        import coaches
        persona_home(self.d, ("Coach Julius", {}))
        moved, _ = self.quiet(coaches.archive, "Coach Julius")
        self.assertEqual(moved, os.path.join(self.folder, ".archive", "coach-julius"))
        _, listed = self.quiet(coaches.main, [])
        self.assertNotIn("Coach Julius", listed)
        self.assertIn("Coach Test", listed)
        with self.assertRaises(SystemExit) as e:
            coaches.archive("Coach Julius")
        self.assertIn("archived", str(e.exception.code))
        code, said = self.quiet(coaches.main, ["archive", "Coach Test"])
        self.assertEqual(code, 0)
        self.assertIn(".archive", said)

    def test_list_shows_service(self):
        import coaches
        write_persona(self.folder, "coach-maya", MAYA)
        write_persona(self.folder, "coach-reed", web_placeholder("Coach Reed", "fish"))
        _, listed = self.quiet(coaches.main, ["list"])
        lines = {" ".join(line[2:].split()[:2]): line for line in listed.splitlines() if line[2:].startswith("Coach ")}
        self.assertIn("web · Inworld", lines["Coach Maya"])
        self.assertTrue(lines["Coach Maya"].startswith("*"))
        self.assertIn("local · chatterbox", lines["Coach Test"])
        self.assertIn("web · Fish Audio", lines["Coach Reed"])
        self.assertIn("(a stand-in)", lines["Coach Reed"])
        self.assertIn("(made the first time it's used)", lines["Coach Reed"])
        self.assertNotIn("stand-in", lines["Coach Maya"])

    def add_default(self, slug_):
        shutil.copytree(os.path.join(ROOT, "me.example", "personas", slug_), os.path.join(self.folder, slug_))
        with open(os.path.join(self.folder, slug_, "persona.md"), encoding="utf-8") as f:
            return f.read()

    def test_make_designs_once_and_saves_the_first_candidate(self):
        import coaches
        before = self.add_default("coach-reed")
        voice_id, said = self.quiet(coaches.make, "Coach Reed")
        self.assertEqual(voice_id, "fish-model-1")
        self.assertEqual(said.splitlines()[0], "Coach Reed is made the first time it's used: designing a voice at "
                                               "Fish Audio from its description (about $0.01).")
        self.assertEqual(self.paths_of("fish"), ["/v1/voice-design", "/model"])
        design = json.loads(self.fakes["fish"].requests[0].body)
        reed = context.persona(os.path.join(self.folder, "coach-reed", "persona.md"))
        self.assertEqual(design["n"], 1)
        self.assertEqual(design["instruction"], personas.voice_description(context.tomllib.loads(
            context.TOML_FRONT_RE.match(before).group(1))["voice"]))
        self.assertIn(b"sweatcast Coach Reed", self.fakes["fish"].requests[1].body)
        self.assertIn(b"sig-0", self.fakes["fish"].requests[1].body)   # the first candidate
        p = personas.lookup("Coach Reed")
        self.assertEqual((p.voice_id, p.settings["made"], p.pending, p.placeholder),
                         ("fish-model-1", self.today, None, True))
        self.assertEqual(p.voice["who"], "A man in his forties, a seasoned personal trainer talking to one client")
        self.assertNotIn("pending", reed.settings)
        if FFMPEG:
            self.assertTrue(os.path.exists(p.sample))
        v = personas.voice_for(p, "fish")
        with open(p.pace_file, encoding="utf-8") as f:
            self.assertTrue(json.load(f)[f"{v['key']}|fish|s2.1-pro"]["estimate"])
        self.assertEqual(os.listdir(self.folder).count(".auditions"), 0)   # no audition
        with self.assertRaises(SystemExit) as e:
            coaches.make("Coach Reed")
        self.assertIn("already made", str(e.exception.code))
        with self.assertRaises(SystemExit) as e:   # a message, so the command exits 1
            self.quiet(coaches.main, ["make", "Coach Reed"])
        self.assertIsInstance(e.exception.code, str)
        self.assertEqual(len(self.paths_of("fish")), 2)

    def test_make_says_what_each_service_costs(self):
        import coaches
        self.add_default("coach-ellis")
        self.add_default("coach-owen")
        _, said = self.quiet(coaches.make, "Coach Ellis")
        self.assertIn("designing a voice at ElevenLabs", said)
        self.assertIn("it uses one of ElevenLabs Free's 3 voice slots", said)
        self.assertEqual(personas.lookup("Coach Ellis").voice_id, "el-saved-5")
        _, said = self.quiet(coaches.make, "Coach Owen")
        self.assertIn("design cost not published", said)
        self.assertEqual(personas.lookup("Coach Owen").voice_id, "ws__design-0")
        self.add_default("coach-nolan")
        _, said = self.quiet(coaches.make, "Coach Nolan")
        self.assertIn("designing a voice at Gemini from its description (about $0.01)", said)

    def test_failed_make_leaves_coach_pending(self):
        import cli
        import coaches
        before = self.add_default("coach-reed")
        design = self.fakes["fish"].answer
        self.fakes["fish"].answer = lambda r: (500, {}, b'{"message": "boom"}') if r.path == "/model" else design(r)
        code, said = self.quiet(coaches.main, ["make", "Coach Reed"])
        self.assertNotEqual(code, cli.OK)
        with open(os.path.join(self.folder, "coach-reed", "persona.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(personas.lookup("Coach Reed").pending, "design")
        self.assertFalse(os.path.exists(os.path.join(self.folder, "coach-reed", "pace.json")))
        self.fakes["fish"].answer = design
        with mock.patch.object(voices, "record_estimate", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.quiet(coaches.make, "Coach Reed")
        with open(os.path.join(self.folder, "coach-reed", "persona.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), before)

    def test_failed_make_tells_the_saved_voice_id(self):
        import contextlib
        import io
        import coaches
        self.add_default("coach-reed")
        out = io.StringIO()
        with mock.patch.object(voices, "record_estimate", side_effect=OSError("disk full")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            with self.assertRaises(OSError):
                coaches.make("Coach Reed")
        self.assertIn("fish-model-1", out.getvalue())
        self.assertIn("Fish Audio", out.getvalue())

    def test_make_resumes_after_a_saved_voice(self):
        import coaches
        before = self.add_default("coach-ellis")
        with mock.patch.object(voices, "record_estimate", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.quiet(coaches.make, "Coach Ellis")
        with open(os.path.join(self.folder, "coach-ellis", "persona.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), before)   # still pending
        sent = len(self.fakes["elevenlabs"].requests)
        _, said = self.quiet(coaches.make, "Coach Ellis")
        self.assertEqual(len(self.fakes["elevenlabs"].requests), sent)   # no second design, no second save
        p = personas.lookup("Coach Ellis")
        self.assertEqual((p.voice_id, p.pending), ("el-saved-5", None))
        self.assertEqual([f for f in os.listdir(p.folder) if f.startswith(".made")], [])   # the record is gone
        v = personas.voice_for(p, "elevenlabs")
        with open(p.pace_file, encoding="utf-8") as f:
            self.assertTrue(json.load(f)[f"{v['key']}|elevenlabs|eleven_v4"]["estimate"])
        if FFMPEG:
            self.assertTrue(os.path.exists(p.sample))
        self.assertEqual(p.description, "A stand-in web coach to start with: a man in his forties, warm baritone, "
                                        "a seasoned trainer. Make your own any time (\"I want a new coach\").")
        self.assertFalse([f for f in os.listdir(p.folder) if ".part" in f])

    def test_failed_make_on_gemini_keeps_the_voice_to_resume(self):
        import coaches
        self.add_default("coach-nolan")
        with mock.patch.object(voices, "record_estimate", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.quiet(coaches.make, "Coach Nolan")
        self.assertEqual(self.paths_of("gemini", "DELETE"), [])   # recorded: the next make finishes with it
        self.quiet(coaches.make, "Coach Nolan")
        self.assertEqual(personas.lookup("Coach Nolan").voice_id, "gem-voice-1")
        self.assertEqual(self.paths_of("gemini"), ["/v1beta/voices", "/v1beta/interactions"])

    def test_failed_make_on_gemini_deletes_the_stored_voice(self):
        import coaches
        before = self.add_default("coach-nolan")
        with mock.patch.object(coaches, "_record_made", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.quiet(coaches.make, "Coach Nolan")
        self.assertEqual(self.paths_of("gemini", "DELETE"), ["/v1beta/voices/gem-voice-1"])
        with open(os.path.join(self.folder, "coach-nolan", "persona.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), before)
        _, said = self.quiet(coaches.make, "Coach Nolan")
        self.assertEqual(personas.lookup("Coach Nolan").voice_id, "gem-voice-2")
        label = json.loads(self.fakes["gemini"].requests[3].body)   # the second design, after the delete
        self.assertEqual(label["voice"]["display_name"], "sweatcast Coach Nolan")

    def test_keep_records_the_saved_voice_and_resumes(self):
        import coaches
        folder = self.audition(self.narrative, services=["fish"])
        with mock.patch.object(voices, "record_estimate", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.keep(f"{folder}/A", "Coach Maya")
        a = self.candidates(folder)[0]
        self.assertEqual((a["voice_id"], a["kept"]), ("fish-model-1", "Coach Maya"))   # before any local write
        self.assertFalse(os.path.exists(os.path.join(self.folder, "coach-maya", "persona.md")))
        self.keep(f"{folder}/A", "Coach Maya")
        self.assertEqual(len([r for r in self.fakes["fish"].requests if r.path == "/model"]), 1)   # not saved twice
        self.assertEqual(personas.lookup("Coach Maya").voice_id, "fish-model-1")
        with self.assertRaises(SystemExit) as e:   # now it's really kept
            coaches.keep_web(f"{folder}/A", "Coach Maya")
        self.assertIn("already", str(e.exception.code))

    def test_keep_never_resurrects_an_archived_coach(self):
        import coaches
        folder = self.audition(self.narrative, services=["gemini"])
        self.keep(f"{folder}/A", "Coach Nolan")
        self.quiet(coaches.archive, "Coach Nolan")
        with self.assertRaises(SystemExit) as e:
            coaches.keep_web(f"{folder}/A", None)
        self.assertIn("already", str(e.exception.code))
        self.assertFalse(os.path.exists(os.path.join(self.folder, "coach-nolan")))

    def test_revoice_resumes_after_a_failed_local_write(self):
        first = self.audition(self.narrative, services=["inworld"])
        self.keep(f"{first}/A", "Coach Maya")
        again = self.audition(None, coach="Coach Maya")
        with mock.patch.object(voices, "record_estimate", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.keep(f"{again}/B", "Coach Maya")
        self.assertEqual(personas.lookup("Coach Maya").voice_id, "ws__design-0")   # persona.md unchanged
        self.keep(f"{again}/B", "Coach Maya")
        self.assertEqual(personas.lookup("Coach Maya").voice_id, "ws__design-1")
        self.assertEqual(len([r for r in self.fakes["inworld"].requests if r.path.endswith(":publish")]), 2)

    def test_revoicing_a_stand_in_makes_it_yours(self):
        write_persona(self.folder, "coach-owen", context.persona_text(
            {"name": "Coach Owen", "kind": "web", "service": "inworld", "placeholder": True,
             "voice_id": "ws__made-0", "made": "2026-10-25", "description": "A stand-in web coach to start with.",
             "voice": context.persona(self.narrative).settings["voice"]}, "## How this coach talks\n"))
        again = self.audition(None, coach="Coach Owen")
        self.keep(f"{again}/A", "Coach Owen")
        p = personas.lookup("Coach Owen")
        self.assertEqual(p.voice_id, "ws__design-0")
        self.assertFalse(p.placeholder)
        self.assertNotIn("placeholder", p.settings)
        self.assertNotIn("description", p.settings)   # "A stand-in ..." went with it; the narrative has none

    def test_forget_audition_keeps_a_gemini_voice_a_coach_uses(self):
        import coaches
        folder = self.audition(self.narrative, services=["gemini"])
        self.keep(f"{folder}/A", "Coach Nolan")
        cands = self.candidates(folder)
        del cands[0]["kept"]   # as if the record never got the mark
        with open(os.path.join(folder, "candidates.json"), "w", encoding="utf-8") as f:
            json.dump(cands, f)
        self.quiet(coaches.archive, "Coach Nolan")   # archived coaches count too
        self.quiet(coaches.forget_audition, os.path.basename(folder))
        self.assertEqual(self.paths_of("gemini", "DELETE"), [])
        self.assertFalse(os.path.exists(folder))

    def test_keep_refuses_an_existing_name_without_coach_revoice(self):
        import coaches
        folder = self.audition(self.narrative, services=["fish"])
        with self.assertRaises(SystemExit) as e:
            coaches.keep_web(f"{folder}/A", "Coach Test")
        self.assertIn("--coach", str(e.exception.code))
        with self.assertRaises(SystemExit):   # a new coach needs a name
            coaches.keep_web(f"{folder}/A", None)
        with self.assertRaises(SystemExit):   # no such candidate
            coaches.keep_web(f"{folder}/Z", "Coach Zed")
        self.assertEqual([r for r in self.fakes["fish"].requests if r.path == "/model"], [])
        self.assertFalse(os.path.exists(os.path.join(self.folder, "coach-zed")))


if __name__ == "__main__":
    unittest.main()
