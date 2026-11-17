"""Schema 6, the only one this engine reads: the profile's four files read as one, an older folder is refused
with a way forward, and the folder steps that need no schema change (the reserve's old name) still run."""
import contextlib
import glob
import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import errors  # noqa: E402

import check  # noqa: E402
import cli  # noqa: E402
import context  # noqa: E402
import helpers  # noqa: E402
import migrate  # noqa: E402


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run_migrate(home):
    out, err = io.StringIO(), io.StringIO()
    with helpers.home(home), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.run(migrate.main, [])
    return code, out.getvalue(), err.getvalue()


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
        issues = check._check_profile(os.path.join(self.dir, "profile.md"))
        dup = [i for i in issues if "also set in" in i.message]
        self.assertEqual(len(dup), 1)
        self.assertEqual(os.path.basename(dup[0].path), "profile.md")

    def test_a_setting_outside_its_home_still_counts(self):
        write(os.path.join(self.dir, "profile.md"), '+++\nschema = 6\nkits = [{name = "home", equipment = []}]\n+++\n')
        self.assertEqual(context.kits(context.profile(os.path.join(self.dir, "profile.md"))), {"home": []})

    def test_bad_toml_in_settings_names_the_file(self):
        write(os.path.join(self.dir, "profile.md"), '+++\nschema = 6\n+++\n# Me\n')
        write(os.path.join(self.dir, "settings.toml"), 'schema = 6\ndeliver_to = \n')
        with self.assertRaises(errors.PROBLEMS) as e:
            context.profile(os.path.join(self.dir, "profile.md"))
        self.assertIn("settings.toml", str(e.exception.code))


class Older(unittest.TestCase):
    """Support for folders before schema 6 (HarmonicFitness 0.12.0) is gone: migrate and the readers refuse one,
    changing nothing, and say where to go instead."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)

    def test_an_older_file_is_refused_with_a_way_forward(self):
        for name, old, new in (("health.md", "schema = 6", "schema = 5"), ("log.md", "schema = 6", "schema = 4")):
            with self.subTest(name):
                path = os.path.join(self.home, name)
                before = read(path)
                write(path, before.replace(old, new, 1))
                code, out, err = run_migrate(self.home)
                self.assertEqual(code, errors.MigrateError.exit_code)
                self.assertIn("me.example", err)
                self.assertIn("github.com/RNCDev/harmonicfitness", err)
                self.assertEqual(glob.glob(os.path.join(self.home, ".backup-*")), [])   # nothing changed
                issues = check.check([path])
                self.assertTrue(any("me.example" in i.message for i in issues), issues)
                write(path, before)

    def test_an_older_coach_is_refused(self):
        coach = os.path.join(self.home, "coaches", "mine")
        os.makedirs(coach)
        write(os.path.join(coach, "persona.md"), '+++\nschema = 4\nname = "Mine"\n+++\n')
        code, _, err = run_migrate(self.home)
        self.assertEqual(code, errors.MigrateError.exit_code)
        self.assertIn("coach files", err)
        self.assertIn("me.example", err)
        with self.assertRaises(errors.ContextError) as e:
            context.persona(os.path.join(coach, "persona.md"))
        self.assertIn("me.example", str(e.exception))


class Pantry(unittest.TestCase):
    """The reserve's old name (before 0.10.2): research/pantry/ moves into research/reserve/, never overwriting,
    and told.jsonl's `pantry` keys become `reserve`; a second run has nothing to do."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        self.research = os.path.join(self.home, "workouts", "research")
        for folder, name, text in (("pantry", "old.md", "# Old\n"), ("pantry", "same.md", "# Same\n"),
                                   ("pantry", "clash.md", "# Pantry's\n"), ("reserve", "same.md", "# Same\n"),
                                   ("reserve", "clash.md", "# Reserve's\n")):
            os.makedirs(os.path.join(self.research, folder), exist_ok=True)
            write(os.path.join(self.research, folder, name), text)
        self.told = os.path.join(self.research, "told.jsonl")
        write(self.told, '{"date": "2026-10-01", "title": "Old", "pantry": "old"}\nnot json\n'
                         '{"date": "2026-10-02", "title": "New", "reserve": "same"}\n')

    def test_the_pantry_moves_into_the_reserve_once(self):
        self.assertTrue(migrate.pantry_due(self.home))
        _, out, err = run_migrate(self.home)
        self.assertIn("research/pantry/", out, out + err)
        self.assertFalse(os.path.exists(os.path.join(self.research, "pantry")))
        reserve = os.path.join(self.research, "reserve")
        self.assertEqual(sorted(os.listdir(reserve)), ["clash.md", "old.md", "same.md"])
        self.assertEqual(read(os.path.join(reserve, "clash.md")), "# Reserve's\n")   # never overwritten
        backup = glob.glob(os.path.join(self.home, ".backup-*"))[0]
        self.assertEqual(read(os.path.join(backup, "research", "pantry", "clash.md")), "# Pantry's\n")
        self.assertIn('"pantry": "old"', read(os.path.join(backup, "research", "told.jsonl")))
        self.assertEqual(read(self.told).splitlines(),
                         ['{"date": "2026-10-01", "title": "Old", "reserve": "old"}', "not json",
                          '{"date": "2026-10-02", "title": "New", "reserve": "same"}'])
        self.assertEqual(migrate.pantry_due(self.home), [])
        self.assertIn("nothing to do", run_migrate(self.home)[1])


if __name__ == "__main__":
    unittest.main()
