"""./sweatcast migrate from sweatcast 8 (schema 3) to 9 (schema 4): voices become coaches.

The context folder is invented (tests/fixtures/v8-home: the v8.0.1 template, two log lines, and a
pace file with the shipped clips' real keys); the clips come from tools/migrate-assets/v8-voices/."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("SWEATCAST_BACKEND", "mlx")

import context  # noqa: E402

V8 = os.path.join(ROOT, "tests", "fixtures", "v8-home")
JULIUS_KEY, SOLO_KEY = "e5488e8c8349", "fdb9e1b9e92f"   # the keys this listener's pace and clips are filed under


class Migrate4(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(V8, self.home)
        with open(os.path.join(self.home, ".env"), "w") as f:
            f.write("FISH_AUDIO_API_KEY=sk-test-NEVERCOPY\n")

    def migrate(self, *args):
        env = dict(os.environ, SWEATCAST_HOME=self.home)
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "migrate.py"), *args], env=env,
                              capture_output=True, text=True, timeout=120)

    def tool(self, code):
        """Run `code` in a fresh Python with the context folder at self.home; returns its stdout."""
        env = dict(os.environ, SWEATCAST_HOME=self.home)
        out = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'tools')\n" + code], cwd=ROOT,
                             env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def migrated(self, out):
        """Migrated: the template's own [hint] lines make the closing check exit 1, which isn't a failure here."""
        self.assertIn("Backed up the originals", out.stdout, out.stdout + out.stderr)

    def read(self, *parts):
        with open(os.path.join(self.home, *parts), encoding="utf-8") as f:
            return f.read()

    def test_migrate_v8_folder_to_personas(self):
        out = self.migrate()
        self.migrated(out)
        self.assertIn("Made the coach Coach Julius", out.stdout)
        julius = context.persona(os.path.join(self.home, "personas", "coach-julius", "persona.md"))
        solo = context.persona(os.path.join(self.home, "personas", "coach-solo", "persona.md"))
        self.assertEqual((julius.settings["name"], julius.settings["aliases"]), ("Coach Julius", ["Chatterbox Coach", "Coach E"]))
        self.assertEqual((solo.settings["name"], solo.settings["aliases"]), ("Coach Solo", ["Qwen3 Coach", "Coach G"]))
        self.assertEqual((julius.settings["local"]["engine"], solo.settings["local"]["engine"]), ("chatterbox", "qwen3"))
        self.assertFalse(julius.settings["description"].lower().startswith("formerly"))
        keys = self.tool("import personas\nprint(personas.voice_for(personas.lookup('Coach Julius'), 'local')['key'],"
                         " personas.voice_for(personas.lookup('Coach Solo'), 'local')['key'])")
        self.assertEqual(keys.split(), [JULIUS_KEY, SOLO_KEY])
        with open(os.path.join(V8, "workouts", ".audio-cache", "voice-pace.json")) as f:
            old = json.load(f)
        with open(os.path.join(self.home, "personas", "coach-julius", "pace.json")) as f:
            self.assertEqual(json.load(f), {k: v for k, v in old.items() if k.startswith(JULIUS_KEY)})
        with open(os.path.join(self.home, "personas", "coach-solo", "pace.json")) as f:
            self.assertEqual(list(json.load(f)), [k for k in old if k.startswith(SOLO_KEY)])
        measured = self.tool("import personas, voices\nprint(voices.pace(personas.voice_for("
                             "personas.lookup('Coach Julius'), 'local'))[1])")
        self.assertEqual(measured, "True")
        for p in (julius, solo):
            self.assertIn("- Tone: calm and focused.", p.body)
        profile = self.read("profile.md")
        self.assertNotIn("[[voices]]", profile)
        self.assertNotIn("- Tone: calm and focused.", profile)
        self.assertEqual(context.front(profile)[0]["render"], ["local"])
        self.assertEqual(context.front(profile)[0]["schema"], 4)
        backup = [d for d in os.listdir(self.home) if d.startswith(".backup-")]
        self.assertEqual(len(backup), 1)
        saved = os.listdir(os.path.join(self.home, backup[0]))
        for f in ("profile.md", "health.md", "log.md", ".gitignore", "voice-pace.json"):
            self.assertIn(f, saved)
        self.assertNotIn(".env", saved)
        self.assertFalse(any("NEVERCOPY" in open(os.path.join(r, f), errors="ignore").read()
                             for r, _, fs in os.walk(os.path.join(self.home, backup[0])) for f in fs))
        self.assertIn(".env", self.read(".gitignore").splitlines())
        self.assertIn("personas/*/takes/", self.read(".gitignore").splitlines())
        self.assertFalse(os.path.exists(os.path.join(self.home, "workouts", ".audio-cache", "voice-pace.json")))
        self.assertEqual(self.read(".env"), "FISH_AUDIO_API_KEY=sk-test-NEVERCOPY\n")
        self.assertEqual(self.tool("import personas\nprint(personas.last_coach().name)"), "Coach Julius")   # "Coach E"

    def test_migrate_4_is_idempotent_and_never_overwrites_a_persona(self):
        mine = os.path.join(self.home, "personas", "coach-julius")
        os.makedirs(mine)
        with open(os.path.join(mine, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Julius", "description": "mine"}, "## How this coach talks\n- Tone: mine.\n"))
        first = self.migrate()
        self.migrated(first)
        self.assertIn("mine", self.read("personas", "coach-julius", "persona.md"))
        self.assertFalse(os.path.exists(os.path.join(mine, "clip.wav")))   # left as it was
        self.assertTrue(os.path.exists(os.path.join(self.home, "personas", "coach-solo", "clip.wav")))
        second = self.migrate()
        self.assertIn("nothing to do", second.stdout)
        self.assertEqual(len([d for d in os.listdir(self.home) if d.startswith(".backup-")]), 1)

    def test_migrate_asks_for_a_name_it_cant_make(self):
        voices = os.path.join(self.home, "voices")
        os.makedirs(voices)
        for ext in (".wav", ".txt", ".json"):
            shutil.copy(os.path.join(ROOT, "tools", "migrate-assets", "v8-voices", "Qwen3 Coach" + ext),
                        os.path.join(voices, "Qwen3 Custom" + ext))
        with open(os.path.join(voices, "Qwen3 Custom.json"), "w") as f:
            json.dump({"engine": "qwen3"}, f)
        prof = os.path.join(self.home, "profile.md")
        text = self.read("profile.md").replace('[[voices]]\nname = "Qwen3 Coach"', '[[voices]]\nname = "Qwen3 Custom"', 1)
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text)
        before = self.read("profile.md")
        out = self.migrate()
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn('--name "Qwen3 Custom=Coach', out.stdout + out.stderr)
        self.assertEqual(self.read("profile.md"), before)   # nothing changed
        out = self.migrate("--name", "Qwen3 Custom=Coach Rae")
        self.migrated(out)
        rae = context.persona(os.path.join(self.home, "personas", "coach-rae", "persona.md"))
        self.assertIn("Qwen3 Custom", rae.settings["aliases"])
        self.assertFalse(os.path.exists(voices))   # copied into personas/ and the backup

    def test_dry_run_says_who_each_voice_becomes(self):
        out = self.migrate("--dry-run")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("Chatterbox Coach becomes Coach Julius", out.stdout)
        self.assertIn("Qwen3 Coach becomes Coach Solo", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.home, "personas")))

    def test_cached_clip_still_matches_after_migration(self):
        self.migrated(self.migrate())
        code = """import hashlib, json, os, personas, render
folder = os.path.join('tools', 'migrate-assets', 'v8-voices')
conf = json.load(open(os.path.join(folder, 'Chatterbox Coach.json')))
audio = hashlib.sha256(open(os.path.join(folder, 'Chatterbox Coach.wav'), 'rb').read()).hexdigest()
words = open(os.path.join(folder, 'Chatterbox Coach.txt'), encoding='utf-8').read().strip()
old = {'key': hashlib.sha256(f'{audio}|{words}'.encode()).hexdigest()[:12], 'engine': conf['engine'],
       'model': conf['model'], 'revision': conf['revision'], 'generate': {}, 'backend': 'mlx'}
new = personas.voice_for(personas.lookup('Coach Julius'), 'local')
print(render.clip_cache(old, 42)('Set your feet.') == render.clip_cache(new, 42)('Set your feet.'))"""
        self.assertEqual(self.tool(code), "True")


if __name__ == "__main__":
    unittest.main()
