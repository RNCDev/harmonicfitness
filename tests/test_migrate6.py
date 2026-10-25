"""Schema 5 to 6: the profile splits into profile.md, training.md, content.md and settings.toml."""
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import context  # noqa: E402
import migrate  # noqa: E402

OLD = os.path.join(ROOT, "tests", "fixtures", "profile-5.md")   # the one-file template, as 11.x shipped it


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Split(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        for name in context.PROFILE_PARTS[1:]:
            os.remove(os.path.join(self.home, name))
        shutil.copy(OLD, os.path.join(self.home, "profile.md"))
        for name in ("health.md", "log.md"):   # back to schema 5, as an 11.x folder has them
            path = os.path.join(self.home, name)
            write(path, read(path).replace("schema = 6", "schema = 5", 1))
        self.old = context.front(read(OLD))[0]

    def tearDown(self):
        self.tmp.cleanup()

    def migrate(self, *args):
        env = dict(os.environ, SWEATCAST_HOME=self.home)
        return subprocess.run([sys.executable, "tools/migrate.py", *args], cwd=ROOT, env=env,
                              capture_output=True, text=True)

    def test_an_old_profile_says_migrate_and_not_missing(self):
        issues = context.check([os.path.join(self.home, n) for n in context.PROFILE_PARTS])
        self.assertTrue(any("./sweatcast migrate" in i.message for i in issues))
        self.assertFalse(any("missing" in i.message for i in issues), issues)

    def test_each_setting_and_section_lands_in_its_home(self):
        out = self.migrate()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        p = context.profile(os.path.join(self.home, "profile.md"))
        self.assertEqual({k: v for k, v in p.settings.items()},
                         {k: v for k, v in self.old.items() if k != "schema"})   # nothing lost or changed
        self.assertEqual(p.duplicates, [])
        for key, home in context.SETTING_HOMES.items():
            if key in self.old:
                self.assertEqual(os.path.basename(p.sources[key]), home, key)
        training = read(os.path.join(self.home, "training.md"))
        content = read(os.path.join(self.home, "content.md"))
        profile = read(os.path.join(self.home, "profile.md"))
        self.assertIn("## Default session", training)
        self.assertIn("## Equipment kits", training)
        self.assertIn("## Taste", content)
        self.assertIn("## Basics", profile)
        self.assertNotIn("## Taste", profile)
        self.assertIn(migrate.PROFILE_NOTE, profile)   # the old note about one settings block is replaced
        self.assertNotIn("Claude reads this before every workout", profile)
        self.assertIn("schema = 6", read(os.path.join(self.home, "health.md")))
        for name in ("Usual length", "Never bring up"):   # the brief and research still find their sections
            self.assertIn(name, p.body)
        backup = glob.glob(os.path.join(self.home, ".backup-*"))[0]
        self.assertEqual(read(os.path.join(backup, "profile.md")), read(OLD))
        again = self.migrate()
        self.assertIn("already at schema 6", again.stdout)

    def test_a_migrated_folder_matches_the_template(self):
        self.migrate()
        mine = context.profile(os.path.join(self.home, "profile.md"))
        example = context.profile(os.path.join(ROOT, "me.example", "profile.md"))
        self.assertEqual(mine.settings, example.settings)
        self.assertEqual(mine.sources.keys(), example.sources.keys())
        for key in mine.sources:
            self.assertEqual(os.path.basename(mine.sources[key]), os.path.basename(example.sources[key]))

    def test_a_part_already_there_is_backed_up_then_replaced(self):
        write(os.path.join(self.home, "content.md"), "+++\nschema = 6\n+++\nmine\n")
        self.migrate()
        backup = glob.glob(os.path.join(self.home, ".backup-*"))[0]
        self.assertEqual(read(os.path.join(backup, "content.md")), "+++\nschema = 6\n+++\nmine\n")
        self.assertIn("## Taste", read(os.path.join(self.home, "content.md")))


class Merge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_missing_part_reads_as_empty(self):
        write(os.path.join(self.dir, "profile.md"), '+++\nschema = 6\nname = "Sam"\n+++\n# Me\n')
        p = context.profile(os.path.join(self.dir, "profile.md"))
        self.assertEqual(p.settings, {"name": "Sam"})

    def test_a_setting_in_two_files_the_home_file_wins_and_check_says_so(self):
        write(os.path.join(self.dir, "profile.md"), '+++\nschema = 6\ndeliver_to = "~/old"\n+++\n# Me\n')
        write(os.path.join(self.dir, "settings.toml"), 'schema = 6\ndeliver_to = "~/new"\n')
        p = context.profile(os.path.join(self.dir, "profile.md"))
        self.assertEqual(p.settings["deliver_to"], "~/new")
        issues = context._check_profile(os.path.join(self.dir, "profile.md"))
        dup = [i for i in issues if "also set in" in i.message]
        self.assertEqual(len(dup), 1)
        self.assertEqual(os.path.basename(dup[0].path), "profile.md")

    def test_a_setting_outside_its_home_still_counts(self):
        write(os.path.join(self.dir, "profile.md"), '+++\nschema = 6\nkits = [{name = "home", equipment = []}]\n+++\n')
        self.assertEqual(context.kits(context.profile(os.path.join(self.dir, "profile.md"))), {"home": []})

    def test_bad_toml_in_settings_names_the_file(self):
        write(os.path.join(self.dir, "profile.md"), '+++\nschema = 6\n+++\n# Me\n')
        write(os.path.join(self.dir, "settings.toml"), 'schema = 6\ndeliver_to = \n')
        with self.assertRaises(SystemExit) as e:
            context.profile(os.path.join(self.dir, "profile.md"))
        self.assertIn("settings.toml", str(e.exception.code))


if __name__ == "__main__":
    unittest.main()
