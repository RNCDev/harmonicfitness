"""Schema 4 to 5: a folder per workout. The 4.x workouts folder is invented here, in a temp dir:
drafts in drafts/, every build's output loose beside them, a smoke test, a stray file, and the day's
research loose in research/."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import workouts  # noqa: E402


def touch(path, text="x\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def record(path, draft):
    touch(path, json.dumps({"out": "me/workouts/x.mp3", "draft": draft}))


class Layout(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        self.w = os.path.join(self.home, "workouts")

    def at(self, *parts):
        return os.path.join(self.w, *parts)

    def test_out_dir(self):
        self.assertEqual(workouts.out_dir(self.at("2026-10-25-strength-25", "2026-10-25-strength-25.draft.txt"),
                                          self.w), self.at("2026-10-25-strength-25"))
        self.assertEqual(workouts.out_dir(os.path.join(ROOT, "knowledge", "smoke-test.draft.txt"), self.w),
                         self.at("checks"))
        self.assertEqual(workouts.out_dir(os.path.join(self.d, "x.draft.txt"), self.w), self.at("checks"))
        self.assertEqual(workouts.out_dir(self.at("drafts", "a.draft.txt"), self.w), self.at("checks"))
        self.assertEqual(workouts.out_dir(self.at("checks", "a.draft.txt"), self.w), self.at("checks"))

    def test_reorganize_moves_by_build_record(self):
        stem = "2026-10-23-general-circuit"
        for ext in (".draft.txt", ".brief.md", ".menu.json"):
            touch(self.at("drafts", stem + ext))
        touch(self.at("Workout 2026-10-23 General 30 min.txt"))
        record(self.at("Workout 2026-10-23 General 30 min.build.json"), f"me/workouts/drafts/{stem}.draft.txt")
        workouts.reorganize(self.home)
        self.assertEqual(sorted(os.listdir(self.at(stem))), sorted([
            stem + ".brief.md", stem + ".draft.txt", stem + ".menu.json",
            "Workout 2026-10-23 General 30 min.build.json", "Workout 2026-10-23 General 30 min.txt"]))
        self.assertFalse(os.path.exists(self.at("drafts")))

    def test_smoke_goes_to_checks(self):
        for ext in (".txt", ".mp3"):
            touch(self.at("smoke-test" + ext))
        record(self.at("smoke-test.build.json"), "knowledge/smoke-test.draft.txt")
        workouts.reorganize(self.home)
        self.assertEqual(sorted(os.listdir(self.at("checks"))),
                         ["smoke-test.build.json", "smoke-test.mp3", "smoke-test.txt"])

    def test_name_date_matches_single_draft(self):
        touch(self.at("drafts", "2026-10-19-bench-only-15.draft.txt"))
        touch(self.at("Workout 2026-10-19 Bench Only 15 min.txt"))
        workouts.reorganize(self.home)
        self.assertTrue(os.path.exists(self.at("2026-10-19-bench-only-15", "Workout 2026-10-19 Bench Only 15 min.txt")))

    def test_ambiguous_goes_to_checks(self):
        touch(self.at("drafts", "2026-10-20-a.draft.txt"))
        touch(self.at("drafts", "2026-10-20-b.draft.txt"))
        touch(self.at("Workout 2026-10-20 Something.txt"))
        touch(self.at("x.txt"))
        workouts.reorganize(self.home)
        self.assertEqual(sorted(os.listdir(self.at("checks"))), ["Workout 2026-10-20 Something.txt", "x.txt"])

    def test_record_naming_a_missing_draft_goes_to_checks(self):
        touch(self.at("Fish check.txt"))
        record(self.at("Fish check.build.json"), "/tmp/elsewhere/odd.draft.txt")
        workouts.reorganize(self.home)
        self.assertEqual(sorted(os.listdir(self.at("checks"))), ["Fish check.build.json", "Fish check.txt"])

    def test_research_daily(self):
        for name in ("2026-10-21.md", "2026-10-21-feeds.md", "told.jsonl"):
            touch(self.at("research", name))
        touch(self.at("research", "pantry", "a.md"))
        workouts.reorganize(self.home)
        self.assertEqual(sorted(os.listdir(self.at("research", "daily"))), ["2026-10-21-feeds.md", "2026-10-21.md"])
        self.assertTrue(os.path.exists(self.at("research", "told.jsonl")))
        self.assertTrue(os.path.exists(self.at("research", "pantry", "a.md")))

    def test_never_overwrites(self):
        touch(self.at("checks", "x.txt"), "old\n")
        touch(self.at("x.txt"), "new\n")
        workouts.reorganize(self.home)
        self.assertEqual(sorted(os.listdir(self.at("checks"))), ["x (2).txt", "x.txt"])

    def test_dry_run_changes_nothing(self):
        touch(self.at("x.txt"))
        moves = workouts.reorganize(self.home, dry_run=True)
        self.assertEqual(moves, [(self.at("x.txt"), self.at("checks", "x.txt"))])
        self.assertTrue(os.path.exists(self.at("x.txt")))


class Migrate5(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        for name in ("profile.md", "health.md", "log.md"):   # as 9.0.0 wrote them
            path = os.path.join(self.home, name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(re.sub(r"(?m)^schema = \d+$", "schema = 4", text, count=1))
        touch(os.path.join(self.home, "workouts", "drafts", "2026-10-23-general.draft.txt"))
        touch(os.path.join(self.home, "workouts", "x.txt"))

    def migrate(self, *args):
        env = dict(os.environ, SWEATCAST_HOME=self.home)
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "migrate.py"), *args], env=env,
                              capture_output=True, text=True, timeout=120)

    def test_migrate_4_to_5(self):
        out = self.migrate("--dry-run")
        self.assertIn("checks", out.stdout, out.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.home, "workouts", "x.txt")))
        out = self.migrate()
        self.assertIn("Backed up the originals", out.stdout, out.stdout + out.stderr)
        with open(os.path.join(self.home, "profile.md"), encoding="utf-8") as f:
            self.assertIn("schema = 6", f.read())
        w = os.path.join(self.home, "workouts")
        self.assertTrue(os.path.exists(os.path.join(w, "2026-10-23-general", "2026-10-23-general.draft.txt")))
        self.assertTrue(os.path.exists(os.path.join(w, "checks", "x.txt")))
        self.assertFalse(os.path.exists(os.path.join(w, "drafts")))
        out = self.migrate()
        self.assertIn("already at schema 6", out.stdout)


OLD_PERSONA = """+++
schema = 4
name = "Coach Old"
aliases = ["Old Voice"]   # kept as written

# How this coach sounds on this computer: engine chatterbox (most natural) or qwen3 (clearest; Mac only).
[local]
engine = "chatterbox"
+++
## How this coach talks
- Tone: calm.   Spacing   kept.
"""


class MigratePersonas(unittest.TestCase):
    """Coach files from schema 4 to 5: `kind = "local"`, even when the context files are already at 5."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.home = os.path.join(self.d, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), self.home)
        self.paths = [os.path.join(self.home, "personas", "coach-old", "persona.md"),
                      os.path.join(self.home, "personas", ".archive", "coach-older", "persona.md")]
        for path in self.paths:
            touch(path, OLD_PERSONA)
        touch(os.path.join(self.home, "workouts", "x.txt"))   # a 4.x layout would move this to checks/

    def migrate(self, *args):
        env = dict(os.environ, SWEATCAST_HOME=self.home)
        return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "migrate.py"), *args], env=env,
                              capture_output=True, text=True, timeout=120)

    def test_migrate_adds_kind_to_every_persona_including_archive(self):
        out = self.migrate("--dry-run")
        self.assertIn("coach-old", out.stdout, out.stdout + out.stderr)
        with open(self.paths[0], encoding="utf-8") as f:
            self.assertEqual(f.read(), OLD_PERSONA)
        out = self.migrate()
        self.assertIn("Backed up the originals", out.stdout, out.stdout + out.stderr)
        want = OLD_PERSONA.replace("schema = 4\n", 'schema = 5\nkind = "local"\n', 1)
        for path in self.paths:
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), want, path)
        backup = [d for d in os.listdir(self.home) if d.startswith(".backup-")]
        self.assertEqual(len(backup), 1)
        with open(os.path.join(self.home, backup[0], "personas", ".archive", "coach-older", "persona.md"),
                  encoding="utf-8") as f:
            self.assertEqual(f.read(), OLD_PERSONA)
        self.assertTrue(os.path.exists(os.path.join(self.home, "workouts", "x.txt")))   # no relayout
        out = self.migrate()
        self.assertIn("nothing to do", out.stdout, out.stdout + out.stderr)
        self.assertEqual(len([d for d in os.listdir(self.home) if d.startswith(".backup-")]), 1)

    def test_migrate_adds_the_sample_and_audition_ignore_rules(self):
        NEW_RULES = ("!personas/*/sample.mp3", "!personas/.archive/*/sample.mp3", "personas/.auditions/",
                     "personas/*/.made.json", "personas/*/.made.wav")
        ignore = os.path.join(self.home, ".gitignore")
        with open(ignore, encoding="utf-8") as f:
            text = f.read()
        with open(ignore, "w", encoding="utf-8") as f:   # as 9.x wrote it
            f.write("\n".join(ln for ln in text.splitlines()
                              if ln not in NEW_RULES) + "\n")
        self.migrate()
        with open(ignore, encoding="utf-8") as f:
            lines = f.read().splitlines()
        with open(os.path.join(ROOT, "me.example", ".gitignore"), encoding="utf-8") as f:
            shipped = f.read().splitlines()
        for have in (lines, shipped):
            for rule in NEW_RULES:
                self.assertIn(rule, have)
            for kept in ("!personas/*/sample.mp3", "!personas/.archive/*/sample.mp3"):
                self.assertGreater(have.index(kept), have.index("*.mp3"))
        before = open(ignore, encoding="utf-8").read()
        self.migrate()
        self.assertEqual(open(ignore, encoding="utf-8").read(), before)   # added once


if __name__ == "__main__":
    unittest.main()
