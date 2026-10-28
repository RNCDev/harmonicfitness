"""Checks for holes in the safety path: what the menu scan catches (jumping and sprint moves, one-word
aliases, negations), what an off-limits area rules out, and how health.md's [[limits]] rows, Avoid:
lines and injury prose are read. They run on the shipped catalog, with no models or network."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import check  # noqa: E402
import context  # noqa: E402
import health as health_md  # noqa: E402
import logsession  # noqa: E402
import draft  # noqa: E402
import errors  # noqa: E402
import helpers  # noqa: E402
import menu  # noqa: E402
import movements  # noqa: E402
import screen  # noqa: E402
import sessions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = catalog.load()
GOALS = sessions.load().goals


def menu_for(*ids):
    return {"format": 2, "date": "2026-10-21", "request": {}, "seconds": 300,
            "movements": [{"id": i, "name": CAT.movements[i].name, "aliases": CAT.movements[i].aliases}
                          for i in ids]}


def issues_for(line, *on_menu):
    """The menu check's issues for one spoken line, with only the dead bug declared."""
    text = f"movements: dead bug\n@@ 300 | Work\n{line}\n"
    return menu.check(CAT, menu_for("dead-bug", *on_menu), text, draft.parse(text))[0]


def knee_menu(level="delicate"):
    sel = catalog.select(CAT, set(CAT.presets["full-gym"]), "advanced",
                         [catalog.Limit("knee", "both", level, [], [], "")])
    return [m.id for m in sel.allowed + sel.healthy_side_only]


class JumpingMoves(unittest.TestCase):
    SAID = ("Twenty burpees, go.", "Now ten box jumps.", "Jump squats for thirty seconds.",
            "Five tuck jumps.", "Mountain climbers now.", "Skater hops, side to side.",
            "Jump lunges, keep going.", "Grab the jump rope.", "Skip rope for a minute.",
            "Two hill sprints.")

    def test_common_jumping_and_sprint_moves_are_caught_off_the_menu(self):
        for line in self.SAID:
            self.assertTrue(any("isn't on today's menu" in i for i in issues_for(line)), line)

    def test_they_are_never_on_a_delicate_knees_menu(self):
        offered = knee_menu()
        for line in self.SAID:
            found = menu.mentions(CAT, line)
            self.assertTrue(found, line)
            self.assertNotIn(found[0][0], offered, line)

    def test_the_catalog_stays_clean(self):
        self.assertEqual(catalog.problems(CAT), [])


class Negation(unittest.TestCase):
    def test_a_negation_must_come_just_before_the_mention(self):
        for line in ("No rest between jumping jacks.", "Do not stop your high knees!",
                     "Don't stop doing jumping jacks.", "Not too fast on the high knees."):
            self.assertTrue(any("isn't on today's menu" in i for i in issues_for(line)), line)

    def test_true_negations_still_pass(self):
        for line in ("No burpees today.", "We're not doing jumping jacks.", "No more high knees.",
                     "Skip the jump squats.", "Instead of burpees, a slow march.", "Rather than burpees, rest.",
                     "Without any jumping jacks today.", "It should feel like a brisk walk."):
            self.assertEqual(issues_for(line), [], line)


class OneWordAliases(unittest.TestCase):
    def test_one_word_aliases_are_scanned(self):
        for line, mid in (("Ten pushups.", "push-up"), ("Now the rdl.", "romanian-deadlift"),
                          ("Then a pulldown.", "lat-pulldown"), ("Ten kickbacks.", "seated-triceps-kickback"),
                          ("Start shadowboxing.", "shadow-boxing"), ("Jog for a minute.", "treadmill-run"),
                          ("Ten birddogs.", "bird-dog"), ("Five walkouts.", "inchworm")):
            issues = issues_for(line)
            self.assertTrue(any(mid in i for i in issues), (line, issues))

    def test_everyday_coaching_words_are_not(self):
        for line in ("Swing your arms, squat down, plank strong, then bridge up.", "Curl the toes, run the reps.",
                     "Press through your heels and row the arms back.", "Keep marching, take the stairs.",
                     "A windmill of the arms.", "Skiing season is coming."):
            self.assertEqual(issues_for(line), [], line)

    def test_no_false_alarm_in_the_shipped_drafts(self):
        for path, named in (("knowledge/smoke-test.draft.txt", {"arm-circles"}),
                            ("tests/fixtures/example.draft.txt", {"arm-circles", "seated-dumbbell-curl", "box-breathing"})):
            with open(os.path.join(ROOT, path), encoding="utf-8") as f:
                said = {mid for mid, _, _ in menu.mentions(CAT, menu.spoken_text(draft.parse(f.read())))}
            self.assertEqual(said, named, path)


class OffLimitsIsAtLeastAsStrict(unittest.TestCase):
    def test_off_limits_rules_out_impact_and_fast_work(self):
        for area in ("neck", "wrist", "rib", "groin"):
            for level in ("delicate", "off-limits"):
                sel = catalog.select(CAT, set(CAT.presets["full-gym"]), "advanced",
                                     [catalog.Limit(area, "both", level, [], [], "")])
                offered = {m.id for m in sel.allowed + sel.healthy_side_only}
                for mid in ("jumping-jacks", "high-knees", "treadmill-run"):
                    self.assertNotIn(mid, offered, (area, level))
                    self.assertIn("impact", sel.left_out[mid])

    def test_off_limits_offers_nothing_delicate_does_not(self):
        for area in CAT.areas:
            menus = {}
            for level in catalog.LIMIT_LEVELS:
                sel = catalog.select(CAT, set(CAT.presets["full-gym"]), "advanced",
                                     [catalog.Limit(area, "both", level, [], [], "")])
                menus[level] = {m.id for m in sel.allowed + sel.healthy_side_only}
            self.assertLessEqual(menus["off-limits"], menus["delicate"], area)

    def test_meaning_says_so(self):
        self.assertIn("no impact work", catalog.meaning("neck", "off-limits"))


def health(settings="", injuries="- None right now.", rules="- Rule: [what a doctor told you]"):
    path = os.path.join(tempfile.mkdtemp(), "health.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"+++\nschema = 6\n{settings}+++\n# Health\n\n## Active injuries and limitations\n{injuries}\n\n"
                f"## Clinician rules\n{rules}\n")
    return path


def screen_with(path):
    profile = context.Profile({"experience": "experienced"}, "")
    return screen.screen({"goal": "strength", "minutes": 30, "preset": "full-gym"}, CAT, GOALS, profile,
                         health_md.health(path))


def issues_in(path):
    with open(path, encoding="utf-8") as f:
        return [i for i in check._check_health(path, f.read()) if not i.note]


class LimitRows(unittest.TestCase):
    def test_a_misspelled_key_is_refused(self):
        path = health('[[limits]]\narea = "knee"\nlevel = "delicate"\nflag = ["impact"]\n')
        _, problem = health_md._limit_row(health_md.health(path).settings["limits"][0], CAT.areas, CAT.flags)
        self.assertIn("flag", problem or "")
        with self.assertRaises(screen.Unfit) as caught:
            screen_with(path)
        self.assertIn("flag", str(caught.exception))
        self.assertTrue(any("flag" in i.message for i in issues_in(path)))
        self.assertEqual(health_md.limits(health_md.health(path), CAT.areas, CAT.flags), [])
        good = health('[[limits]]\narea = "knee"\nlevel = "delicate"\nflags = ["impact"]\nnote = "x"\n'
                      'side = "left"\nrehab = []\n', injuries="- Left knee: invented.")
        self.assertEqual(issues_in(good), [])
        self.assertEqual(len(screen_with(good).limits), 1)


class AvoidLines(unittest.TestCase):
    def test_names_aliases_plurals_and_any_case_resolve(self):
        got = catalog.avoid_set(CAT, ["Impact", "overhead press", "Burpees", "goblet-squat", "spine flexion"])
        self.assertEqual(got, {"impact", "overhead-press", "burpee", "goblet-squat", "spine-flexion"})

    def test_an_unknown_word_stops_the_screen_and_the_cli(self):
        path = health(rules="- Avoid: wobbly-thing")
        with self.assertRaises(screen.Unfit) as caught:
            screen_with(path)
        self.assertIn("wobbly-thing", str(caught.exception))
        self.assertTrue(any("wobbly-thing" in i.message for i in issues_in(path)))
        with self.assertRaises(ValueError):
            movements.avoid_set(CAT, ["wobbly-thing"])

    def test_a_named_movement_is_ruled_out(self):
        scr = screen_with(health(rules="- Avoid: Overhead Press, Impact"))
        offered = {m.id for m in scr.sel.allowed + scr.sel.healthy_side_only}
        self.assertNotIn("overhead-press", offered)
        self.assertNotIn("jumping-jacks", offered)
        self.assertEqual(issues_in(health(rules="- Avoid: Overhead Press, Impact")), [])


class InjuryProse(unittest.TestCase):
    ROW = '[[limits]]\narea = "knee"\nside = "left"\nlevel = "delicate"\n'

    def test_more_injuries_than_rows_warns(self):
        path = health(self.ROW, injuries="- Left knee: invented.\n  - Programming: no jumping.\n- Right wrist: invented.")
        self.assertTrue(any("2 injuries" in w for w in screen_with(path).warnings), screen_with(path).warnings)
        self.assertTrue(any("2 injuries" in i.message for i in issues_in(path)))

    def test_one_row_each_or_unlisted_is_quiet(self):
        for injuries in ("- Left knee: invented.\n  - Programming: no jumping.\n  - Cleared: not yet.",
                         "- Left knee: invented.\n- Unlisted: invented jaw soreness.", "- None right now."):
            path = health(self.ROW, injuries=injuries)
            self.assertFalse(any("injur" in w for w in screen_with(path).warnings), injuries)
            self.assertEqual(issues_in(path), [], injuries)


class MenuTampering(unittest.TestCase):
    """The build's gate re-runs the safety screen from the menu's request against the current health.md and
    profile, so a movement added to menu.json by hand is refused; a malformed menu is an issue, never a
    traceback; and a missing health.md is named as such."""
    TEXT = "movements: dead bug\n@@ 300 | Work\nThe dead bug now.\n"
    TODAY = "2026-10-21"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.home = os.path.join(cls.tmp.name, "me")
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "listener"), cls.home)
        cls.draft = os.path.join(cls.home, "workouts", "x", "x.draft.txt")
        os.makedirs(os.path.dirname(cls.draft))
        with open(cls.draft, "w", encoding="utf-8") as f:
            f.write(cls.TEXT)
        env = dict(os.environ, HARMONICFITNESS_PYTHON=sys.executable, HARMONICFITNESS_HOME=cls.home)
        r = subprocess.run(["sh", os.path.join(ROOT, "harmonicfitness"), "brief", "--today", cls.TODAY, "--goal", "general",
                            "--minutes", "5", "--kit", "home", "--save", cls.draft],
                           capture_output=True, text=True, env=env, cwd=ROOT, timeout=120)
        assert r.returncode == 0, r.stderr
        with open(draft.menu_path(cls.draft), encoding="utf-8") as f:
            cls.saved = json.load(f)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        ctx = helpers.home(self.home)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.addCleanup(menu.write, draft.menu_path(self.draft), self.saved)

    def gate(self, data, strict=True):
        if isinstance(data, str):
            with open(draft.menu_path(self.draft), "w", encoding="utf-8") as f:
                f.write(data)
        else:
            menu.write(draft.menu_path(self.draft), data)
        return menu.gate(CAT, self.draft, self.TEXT, draft.parse(self.TEXT), today=self.TODAY, strict=strict)

    def edited(self, **changes):
        return dict(json.loads(json.dumps(self.saved)), **changes)

    def test_the_brief_menu_passes(self):
        self.assertEqual(self.gate(self.saved), ([], []))

    def test_malformed_menus_are_issues_not_tracebacks(self):
        for bad in (json.dumps([1, 2]),
                    json.dumps(self.edited(movements=[{"name": "dead bug"}, 7])),
                    json.dumps(self.edited(seconds="300", date="yesterday", request=[])),
                    json.dumps(self.edited(movements={"dead-bug": {}}))):
            issues, _ = self.gate(bad)
            self.assertTrue(issues, bad)
            self.assertTrue(all("brief" in i for i in issues), issues)

    def test_validate_names_each_problem(self):
        self.assertEqual(menu.validate(self.saved), [])
        found = menu.validate(self.edited(seconds=0, movements=[{"id": "dead-bug", "side": 1}]))
        self.assertEqual(len(found), 2, found)

    def test_a_menu_without_format_asks_for_a_rerun(self):
        old = self.edited()
        del old["format"]
        issues, _ = self.gate(old)
        self.assertTrue(any("format" in i and "brief ... --save" in i for i in issues), issues)

    def test_a_movement_added_by_hand_is_refused(self):
        on = {e["id"] for e in self.saved["movements"]}
        self.assertNotIn("push-up", on)   # the listener dislikes it
        added = self.edited(movements=self.saved["movements"] + [{"id": "push-up", "name": "Push-up", "aliases": []}])
        issues, _ = self.gate(added)
        self.assertTrue(any("push-up" in i and "screen doesn't allow" in i for i in issues), issues)
        self.assertEqual(self.gate(added, strict=False)[0], [])   # a lint checks the shape and the text only

    def test_a_movement_removed_passes(self):
        fewer = self.edited(movements=[e for e in self.saved["movements"] if e["id"] != "box-breathing"])
        self.assertEqual(self.gate(fewer), ([], []))

    def test_a_healthy_side_only_movement_needs_its_side(self):
        sided = [e for e in self.saved["movements"] if "side" in e]
        if not sided:
            self.skipTest("no healthy-side-only movement on this menu")
        moves = [dict(e) for e in self.saved["movements"]]
        for e in moves:
            if e["id"] == sided[0]["id"]:
                del e["side"]
        issues, _ = self.gate(self.edited(movements=moves))
        self.assertTrue(any(sided[0]["id"] in i and "side" in i for i in issues), issues)

    def test_a_request_can_tighten_but_never_loosen_health(self):
        # the request's own limit, kept in the menu, still applies: a knee limit rules out a knee movement
        tight = self.edited()
        tight["request"]["limits"] = tight["request"].get("limits", []) + ["knee=off-limits:both"]
        issues, _ = self.gate(tight)
        self.assertTrue(any("screen doesn't allow" in i for i in issues), issues)
        # dropping health.md's own limit from the request changes nothing: the file is read again
        loose = self.edited()
        loose["request"].pop("limits", None)
        loose["movements"] = loose["movements"] + [{"id": "push-up", "name": "Push-up", "aliases": []}]
        self.assertTrue(any("push-up" in i for i in self.gate(loose)[0]))

    def test_a_missing_health_file_is_named_not_called_an_old_menu(self):
        health = os.path.join(self.home, "health.md")
        moved = health + ".away"
        os.rename(health, moved)
        self.addCleanup(os.rename, moved, health)
        issues, _ = self.gate(self.saved)
        self.assertTrue(any("no health.md" in i and "setup" in i for i in issues), issues)
        self.assertFalse(any("predates" in i for i in issues), issues)

    def test_the_brief_refuses_without_health_md(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(self.home, home)
            os.remove(os.path.join(home, "health.md"))
            target = os.path.join(home, "workouts", "y", "y.draft.txt")
            env = dict(os.environ, HARMONICFITNESS_PYTHON=sys.executable, HARMONICFITNESS_HOME=home)
            r = subprocess.run(["sh", os.path.join(ROOT, "harmonicfitness"), "brief", "--today", self.TODAY, "--goal",
                                "general", "--minutes", "5", "--kit", "home", "--save", target],
                               capture_output=True, text=True, env=env, cwd=ROOT, timeout=120)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("setup", r.stderr)
            self.assertFalse(os.path.exists(draft.menu_path(target)))

    def test_log_session_refuses_a_malformed_menu(self):
        menu.write(draft.menu_path(self.draft), self.edited(movements="dead-bug"))
        with self.assertRaises(errors.LogRefused) as e:
            logsession.from_draft(self.draft)
        self.assertIn("movements", str(e.exception))


if __name__ == "__main__":
    unittest.main()
