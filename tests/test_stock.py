"""The stock coaches (coaches/, 0.15.0): every shipped folder complete, the fixture copies in step, the stock and
the listener's own coaches merged, and migrate's coaches step. No models: Pocket's voice files are checked as
files, never loaded."""
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import tomllib
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import context  # noqa: E402
import counts  # noqa: E402
import draft  # noqa: E402
import helpers  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402

REAL = os.path.join(ROOT, "coaches")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "stock")
WEB = ("coach-reed-fish", "coach-ellis-elevenlabs", "coach-nolan-gemini", "coach-owen-inworld")


def roster():
    with open(os.path.join(REAL, "roster.toml"), "rb") as f:
        return tomllib.load(f)


class ShippedCoaches(unittest.TestCase):
    """The real coaches/ folder: ten local coaches made by tools/coachmaker/, four web coaches to make."""

    def test_every_local_coach_is_complete(self):
        slugs = [c["slug"] for c in roster()["coach"]]
        self.assertEqual(len(slugs), 10)
        for slug in slugs:
            folder = os.path.join(REAL, f"coach-{slug}-local")
            with self.subTest(coach=slug):
                p = personas.load(folder)
                self.assertEqual((p.kind, p.table("local").get("engine")), ("local", "pocket"))
                self.assertTrue(p.character, "how the coach talks")
                with open(os.path.join(folder, "clip.txt"), encoding="utf-8") as f:
                    self.assertTrue(f.read().strip())
                for name in ("clip.wav", "sample.mp3"):
                    self.assertGreater(os.path.getsize(os.path.join(folder, name)), 1000, name)
                with open(os.path.join(folder, "pocket.safetensors"), "rb") as f:   # a safetensors header
                    n = struct.unpack("<Q", f.read(8))[0]
                    self.assertIsInstance(json.loads(f.read(n)), dict)
                with open(os.path.join(folder, "pace.json"), encoding="utf-8") as f:
                    pace = json.load(f)
                self.assertTrue(any(k.endswith(f"|pocket|{voices.POCKET_REPO}") and r.get("shipped")
                                    and r["seconds"] > 0 for k, r in pace.items()), pace)
                key, _ = personas.clip_key(p)
                self.assertIn(f"{key}|pocket|{voices.POCKET_REPO}", pace)   # measured from this very clip
                have = counts.table(os.path.join(folder, "cues"))
                self.assertEqual(set(have), set(draft.NUMBER_WORDS) | set(draft.CUE_NAMES))

    def test_each_persona_is_what_the_roster_makes(self):
        spec = importlib.util.spec_from_file_location("coach_persona", os.path.join(ROOT, "tools", "coachmaker",
                                                                                   "persona.py"))
        maker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(maker)
        for c in roster()["coach"]:
            with open(os.path.join(REAL, f"coach-{c['slug']}-local", "persona.md"), encoding="utf-8") as f:
                self.assertEqual(f.read(), maker.text(c), c["slug"])

    def test_the_web_coaches_ship_unmade(self):
        for slug in WEB:
            p = personas.load(os.path.join(REAL, slug))
            self.assertTrue(p.is_web and p.placeholder and p.pending == "design", slug)
            self.assertFalse(p.voice_id, slug)

    def test_the_fixture_copies_are_in_step(self):
        for slug in WEB + ("coach-andy-local",):
            for name in ("persona.md", "clip.txt"):
                real = os.path.join(REAL, slug, name)
                if not os.path.exists(real):
                    continue
                with open(real, encoding="utf-8") as a, open(os.path.join(FIXTURE, slug, name), encoding="utf-8") as b:
                    self.assertEqual(a.read(), b.read(), f"{slug}/{name}")


class StockAndOwn(unittest.TestCase):
    """personas.all() merges the stock coaches with the listener's own; a coach of their own wins a name."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        stack = helpers.home(os.path.join(self.tmp.name, "me"))
        stack.__enter__()
        self.addCleanup(stack.__exit__, None, None, None)
        os.makedirs(paths.PERSONAS)

    def own(self, slug, settings):
        folder = os.path.join(paths.PERSONAS, slug)
        os.makedirs(folder)
        with open(os.path.join(folder, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text(settings, ""))
        return folder

    def test_a_made_copy_of_a_stock_coach_wins(self):
        self.own("coach-reed-fish", {"name": "Coach Reed", "kind": "web", "service": "fish", "voice_id": "v1"})
        reed = personas.lookup("Coach Reed")
        self.assertEqual((reed.voice_id, reed.shipped), ("v1", False))
        self.assertEqual([p.name for p in personas.all()].count("Coach Reed"), 1)
        self.assertTrue(personas.lookup("Coach Julius").shipped)

    def test_a_stock_coach_cant_be_archived(self):
        with self.assertRaises(SystemExit) as e:
            personas.archive(personas.lookup("Coach Julius"))
        self.assertIn("ships with sweatcast", str(e.exception.code))
        self.assertTrue(os.path.exists(os.path.join(paths.SHIPPED, "coach-julius", "persona.md")))

    def test_a_stock_coach_used_last_stays_the_default(self):
        self.own("coach-jess-gemini", {"name": "Coach Jess", "kind": "web", "service": "gemini", "voice_id": "g1"})
        with mock.patch.object(personas, "_usable_here", return_value=True), \
                mock.patch.object(personas.context, "sessions",
                                  return_value=[SimpleNamespace(voice="Coach Jess"), SimpleNamespace(voice="Coach Julius")]):
            self.assertEqual(personas.default().name, "Coach Julius")
        with mock.patch.object(personas, "_usable_here", return_value=True), \
                mock.patch.object(personas.context, "sessions", return_value=[]):
            self.assertEqual(personas.default().name, "Coach Jess")   # no log: the listener's own

    def test_with_no_log_and_nothing_of_their_own_a_stand_in(self):
        with mock.patch.object(personas, "_usable_here", side_effect=lambda p: not p.is_web), \
                mock.patch.object(personas.context, "sessions", return_value=[]):
            self.assertEqual(personas.default().name, "Coach Andy")   # the first stock coach that speaks here
        with mock.patch.object(personas, "_usable_here", side_effect=lambda p: p.is_web and p.service == "inworld"), \
                mock.patch.object(personas.context, "sessions", return_value=[]):
            self.assertEqual(personas.default().name, "Coach Owen")   # a keyed web stand-in first


OWN_LOCAL = """+++
schema = 5
kind = "local"
name = "Coach Mine"
aliases = []

[local]
engine = "chatterbox"
+++
"""


class MigrateCoaches(unittest.TestCase):
    """0.15.0's coaches step: personas/ to coaches/, an own local coach archived, an unmade stock web coach set
    aside, a made one kept, the .gitignore rules renamed; once."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        shutil.rmtree(os.path.join(self.home, "coaches"))   # a 0.14.x folder
        old = os.path.join(self.home, "personas")
        os.makedirs(os.path.join(old, "coach-mine"))
        with open(os.path.join(old, "coach-mine", "persona.md"), "w", encoding="utf-8") as f:
            f.write(OWN_LOCAL)
        shutil.copytree(os.path.join(FIXTURE, "coach-reed-fish"), os.path.join(old, "coach-reed-fish"))
        made = os.path.join(old, "coach-ellis-elevenlabs")
        os.makedirs(made)
        with open(os.path.join(FIXTURE, "coach-ellis-elevenlabs", "persona.md"), encoding="utf-8") as f:
            text = f.read().replace('pending = "design"\n', 'voice_id = "el-1"\n')
        with open(os.path.join(made, "persona.md"), "w", encoding="utf-8") as f:
            f.write(text)
        ignore = os.path.join(self.home, ".gitignore")
        with open(ignore, encoding="utf-8") as f:
            text = f.read()
        with open(ignore, "w", encoding="utf-8") as f:
            f.write(text.replace("coaches/", "personas/"))

    def migrate(self, *args):
        env = dict(os.environ, SWEATCAST_HOME=self.home, SWEATCAST_SHIPPED=FIXTURE)
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "migrate.py"), *args], env=env,
                              capture_output=True, text=True, timeout=120)

    def test_the_coaches_step(self):
        out = self.migrate("--dry-run")
        said = out.stdout + out.stderr
        for line in ("personas/ becomes coaches/", "coaches/coach-mine: a local coach of your own, archived",
                     "coaches/coach-reed-fish: a stock web coach not made yet"):
            self.assertIn(line, said)
        self.assertNotIn("coach-ellis", said)
        self.assertTrue(os.path.isdir(os.path.join(self.home, "personas")))   # a dry run moves nothing
        out = self.migrate()
        self.assertIn("Backed up the originals", out.stdout, out.stdout + out.stderr)
        coaches = os.path.join(self.home, "coaches")
        self.assertFalse(os.path.exists(os.path.join(self.home, "personas")))
        self.assertTrue(os.path.exists(os.path.join(coaches, ".archive", "coach-mine", "persona.md")))
        self.assertFalse(os.path.exists(os.path.join(coaches, "coach-reed-fish")))
        backup = [d for d in os.listdir(self.home) if d.startswith(".backup-")]
        self.assertTrue(os.path.exists(os.path.join(self.home, backup[0], "coaches", "coach-reed-fish", "persona.md")))
        self.assertTrue(os.path.exists(os.path.join(coaches, "coach-ellis-elevenlabs", "persona.md")))   # made: kept
        with open(os.path.join(self.home, ".gitignore"), encoding="utf-8") as f:
            ignore = f.read()
        self.assertNotIn("personas/", ignore)
        self.assertIn("!coaches/*/sample.mp3", ignore)
        out = self.migrate()
        self.assertIn("nothing to do", out.stdout, out.stdout + out.stderr)
        self.assertEqual(len([d for d in os.listdir(self.home) if d.startswith(".backup-")]), 1)


if __name__ == "__main__":
    unittest.main()
