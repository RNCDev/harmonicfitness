"""Checks for what an injury limit means (knowledge/limits.toml, tools/playbook.py): the file covers every area
and level, the brief quotes only today's level, a cleared [[limits]] row leaves the screen but keeps its
after-clearing rule in the brief for a while, and `get limits` gives the check-in its signs. They run on the
invented listener in tests/fixtures/listener, with no models or network."""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import helpers  # noqa: E402

import catalog  # noqa: E402
import health  # noqa: E402
import playbook  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTENER = os.path.join(ROOT, "tests", "fixtures", "listener")
CLEARED_ANKLE = '''
[[limits]]
area = "ankle"
side = "right"
level = "delicate"
note = "Rolled it; cleared by the listener's report."
cleared = 2026-10-01
'''


def run(*args, home=LISTENER):
    env = dict(os.environ, HARMONICFITNESS_PYTHON=sys.executable, HARMONICFITNESS_HOME=home)
    return subprocess.run(["sh", os.path.join(ROOT, "harmonicfitness"), *args],
                          capture_output=True, text=True, encoding="utf-8", env=env, cwd=ROOT, timeout=120)


def with_row(home, row):
    """Add a [[limits]] row to the copy's health.md settings block."""
    path = os.path.join(home, "health.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    head, sep, rest = text.partition("+++\n# Health")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + row.lstrip("\n") + sep + rest)


class TheFile(unittest.TestCase):
    def test_the_shipped_file_covers_every_area_and_level(self):
        self.assertEqual(playbook.problems(playbook.load(), catalog.load().areas), [])

    def test_a_missing_level_field_or_area_is_named(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "limits.toml")
            with open(path, "w", encoding="utf-8") as f:
                f.write('format = 1\n[general]\ncheck_in = "x"\nred_flags = ["y"]\nunlisted = "z"\nemergency = ["e"]\n'
                        '[knee.delicate]\nsession = "s"\nstop = []\n'
                        '[knee.check_in]\ndelicate = "a"\n[elbo.delicate]\nsession = "s"\n')
            found = playbook.problems(playbook.load(path), ["knee", "neck"])
        for needle in ("[knee.off-limits] is missing", "[knee.delicate] needs stop", "[knee.check_in] needs",
                       "[knee.delicate] needs opening", "[neck] is missing", "[elbo] isn't one of the catalog's areas",
                       "[general] needs unlisted_session"):
            self.assertTrue(any(needle in p for p in found), (needle, found))

    def test_a_sign_ends_the_movement_or_the_session_never_both(self):
        pb = playbook.load()
        for name, area in pb.areas.items():
            for level, lv in area.levels.items():
                self.assertFalse(set(lv.stop) & set(lv.stop_today), (name, level))
        lines = playbook.session_lines(pb, "neck", "delicate")
        self.assertTrue(any(line.startswith("  - Stop for today on: pain spreading into the arm") for line in lines),
                        lines)

    def test_the_playbook_is_the_evidence_with_a_section_per_area(self):
        with open(os.path.join(ROOT, "knowledge", "injury-playbook.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("knowledge/limits.toml", text)
        self.assertIn("## How the filter applies limits", text)


class Brief(unittest.TestCase):
    def test_the_brief_quotes_todays_level_and_not_the_other(self):
        r = run("brief", "--today", "2026-10-21", "--goal", "strength", "--minutes", "30", "--kit", "home")
        self.assertEqual(r.returncode, 0, r.stderr)
        pb = playbook.load()
        self.assertIn(pb.areas["wrist"].levels["delicate"].session, r.stdout)
        self.assertNotIn(pb.areas["wrist"].levels["off-limits"].session, r.stdout)
        self.assertIn("Stop that movement on:", r.stdout)
        self.assertNotIn("From the injury playbook", r.stdout)
        self.assertIn(pb.red_flags[0], r.stdout)

    def test_a_cleared_limit_leaves_the_screen_and_carries_its_rule_until_it_runs_out(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            with_row(home, CLEARED_ANKLE)
            with helpers.home(home):
                h = health.health()
                cat = catalog.load()
                self.assertEqual([lim.area for lim in health.limits(h, cat.areas, cat.flags)], ["wrist"])
                self.assertEqual([(lim.area, day) for lim, day in health.cleared_rows(h, cat.areas, cat.flags)],
                                 [("ankle", datetime.date(2026, 10, 1))])
                self.assertEqual(health.limit_rows(h, cat.areas, cat.flags)[1], [])
            plan = playbook.load().areas["ankle"].after_plan
            within = run("brief", "--today", "2026-10-21", "--goal", "strength", "--minutes", "30", "--kit", "home",
                         home=home)
            self.assertEqual(within.returncode, 0, within.stderr)
            self.assertIn("right ankle, cleared 2026-10-01", within.stdout)
            self.assertIn(plan, within.stdout)
            self.assertIn(playbook.load().areas["ankle"].after_say, within.stdout)
            after = run("brief", "--today", "2027-01-04", "--goal", "strength", "--minutes", "30", "--kit", "home",
                        home=home)
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertNotIn(plan, after.stdout)

    def test_an_unlisted_injury_reaches_the_brief_and_an_avoid_line_isnt_quoted(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(home, "health.md")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            text = text.replace("- Left wrist: invented strain.",
                                "- Left wrist: invented strain.\n- Unlisted: an invented repair, ten weeks ago.")
            text = text.replace("- No pushing through wrist pain.",
                                "- No pushing through wrist pain.\n- Avoid: spine-flexion")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            r = run("brief", "--today", "2026-10-21", "--goal", "general", "--minutes", "20", "--preset",
                    "bodyweight", home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        limits = r.stdout.split("## Today's limits", 1)[1].split("\n## ", 1)[0]
        self.assertIn("**Unlisted: an invented repair, ten weeks ago**", limits)
        self.assertIn(playbook.load().unlisted_session, limits)
        rules = limits.split("Clinician rules", 1)[1].split("\n\n", 1)[0].split("\n", 1)[1]   # the rules, not the header
        self.assertIn("No pushing through wrist pain.", rules)
        self.assertNotIn("Avoid:", rules)
        self.assertIn("spine-flexion", limits.split("Also left out of the menu today", 1)[1].splitlines()[0])

    def test_a_healthy_side_movement_isnt_marked_light_for_the_other_sides_limit(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(home, "health.md")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace('level = "delicate"', 'level = "off-limits"', 1))
            r = run("brief", "--today", "2026-10-21", "--goal", "strength", "--minutes", "30", "--preset",
                    "hotel-gym", home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        healthy = r.stdout.split("### Healthy side only", 1)[1].split("\n## ", 1)[0]
        lines = [line for line in healthy.splitlines() if line.startswith("- **")]
        self.assertTrue(lines, healthy)
        self.assertFalse([line for line in lines if "LIGHT ONLY" in line], lines)

    def test_a_cleared_value_that_isnt_a_day_is_a_bad_row(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            with_row(home, CLEARED_ANKLE.replace("2026-10-01", '"last week"'))
            with helpers.home(home):
                cat = catalog.load()
                _, problems = health.limit_rows(health.health(), cat.areas, cat.flags)
            self.assertTrue(any("cleared must be the day" in p for p in problems), problems)


class GetLimits(unittest.TestCase):
    def test_get_limits_gives_the_check_in_its_signs_and_the_red_flags(self):
        r = run("get", "limits")
        self.assertEqual(r.returncode, 0, r.stderr)
        pb = playbook.load()
        self.assertIn("wrist delicate left: clear once " + pb.areas["wrist"].check_in["clear"], r.stdout)
        self.assertIn(pb.check_in, r.stdout)
        self.assertIn(pb.red_flags[0], r.stdout)

    def test_a_necks_artery_signs_are_spoken_with_the_heart_rule(self):
        pb = playbook.shipped()
        for level in ("delicate", "off-limits"):
            said = "\n".join(playbook.session_lines(pb, "neck", level))
            self.assertIn("Heart rule, add", said)
            self.assertIn("a sudden headache or neck pain unlike any before", said)
        self.assertNotIn("Heart rule", "\n".join(playbook.session_lines(pb, "knee", "delicate")))
        bad = dict(pb.raw, neck=dict(pb.raw["neck"], heart_rule_typo="x"))
        self.assertIn("[neck] has a key nothing reads: heart_rule_typo", playbook.problems(
            playbook.Playbook(pb.format, pb.check_in, pb.red_flags, pb.unlisted, pb.areas, bad, pb.emergency,
                              pb.unlisted_session), list(pb.areas)))

    def test_red_flags_add_each_areas_own_once(self):
        pb = playbook.Playbook(1, "x", ["a"], "u", {"calf": playbook.Area({}, {}, red_flags=["b", "a"],
                                                                           emergency=["d"])}, emergency=["c"])
        self.assertEqual(playbook.red_flags(pb, ["calf", "calf", "knee"]), ["a", "b"])
        self.assertEqual(playbook.emergencies(pb, ["calf"]), ["c", "d"])
        self.assertEqual(playbook.emergencies(pb), ["c"])


if __name__ == "__main__":
    unittest.main()
