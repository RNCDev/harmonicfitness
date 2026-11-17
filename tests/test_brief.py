"""Checks for today's brief (tools/brief.py), the menu it saves and the build's menu check
(tools/menu.py). They run in-process on the shipped catalog and the invented listener in
tests/fixtures/listener, with no models or network."""
import contextlib
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import helpers  # noqa: E402

import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import cli  # noqa: E402
import health as health_md  # noqa: E402
import draft  # noqa: E402
import menu  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTENER = os.path.join(ROOT, "tests", "fixtures", "listener")
FACTS = {"local": "yes"}   # this computer's facts, without running the readiness check (seconds on Windows)


def call(main, argv, home=LISTENER, env=None):
    """A tool's main in this process, over `home`: (returncode, stdout, stderr) as a subprocess would give."""
    out, err = io.StringIO(), io.StringIO()
    with helpers.home(home), mock.patch.dict(os.environ, env or {}), mock.patch("machine.facts", return_value=FACTS),             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.run(main, argv)
    return types.SimpleNamespace(returncode=code, stdout=out.getvalue(), stderr=err.getvalue())


def brief(*args, home=LISTENER):
    import brief as brief_tool
    return call(brief_tool.main, ["--today", "2026-10-21", *args], home=home)


def menu_section(text):
    return text.split("## Safe menu", 1)[1].split("## Programming guide", 1)[0]


def ids_in(text):
    return {line.split("(`", 1)[1].split("`", 1)[0] for line in text.splitlines() if line.startswith("- **")}


class Brief(unittest.TestCase):
    def test_the_menu_is_the_safety_screen(self):
        cat = catalog.load()
        r = brief("--goal", "general", "--minutes", "25", "--preset", "hotel-gym", "--limit", "knee=off-limits")
        self.assertEqual(r.returncode, 0, r.stderr)
        listed = ids_in(menu_section(r.stdout))
        sel = catalog.select(cat, catalog.kit_equipment(cat, {"preset": "hotel-gym"}), "experienced",
                             health_md.limits(health_md.health(os.path.join(LISTENER, "health.md")))
                             + [catalog.Limit("knee", "both", "off-limits", [], [], "")],
                             dislikes={"push-up"})
        self.assertEqual(listed, {m.id for m in sel.allowed + sel.healthy_side_only})
        self.assertNotIn("air-squat", listed)    # loads the knee
        self.assertNotIn("push-up", listed)      # disliked in the profile
        self.assertIn("Dislikes (left off the menu): push-up", r.stdout)
        self.assertIn("knee off-limits** (today only", r.stdout)

    def test_a_sided_limit_lists_healthy_side_work_and_fills_the_cues(self):
        r = brief("--goal", "strength", "--minutes", "30", "--preset", "hotel-gym", "--limit", "knee=off-limits:right")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("### Healthy side only", r.stdout)
        self.assertIn("left side only", r.stdout)
        self.assertIn("the right knee", r.stdout)           # the limit cues name the side
        self.assertNotIn("{side}", r.stdout)

    def test_a_sore_shoulder_keeps_a_one_arm_push_and_pull_for_the_other_side(self):
        r = brief("--goal", "general", "--minutes", "25", "--preset", "bodyweight", "--add", "dumbbells,band",
                  "--limit", "shoulder=delicate:right")
        healthy = r.stdout.split("### Healthy side only", 1)[1]
        self.assertIn("**single-arm band row** (`single-arm-band-row`): standing, left side only", healthy)
        self.assertIn("**single-arm floor press** (`single-arm-floor-press`): lying, left side only", healthy)
        self.assertNotIn("leave no push", r.stdout)
        both = brief("--goal", "general", "--minutes", "25", "--preset", "bodyweight", "--add", "dumbbells,band",
                     "--limit", "shoulder=off-limits")
        self.assertIn("Today's limits and kit leave no push and no pull on the menu", both.stdout)

    def test_a_movement_that_loads_a_limit_is_marked_light_only(self):
        r = brief("--goal", "strength", "--minutes", "25", "--preset", "full-gym", "--limit", "knee=delicate:left")
        self.assertEqual(r.returncode, 0, r.stderr)
        loaded = [ln for ln in menu_section(r.stdout).splitlines() if "load on today's limits" in ln]
        self.assertTrue(loaded)
        self.assertTrue(all("LIGHT ONLY today" in ln for ln in loaded))

    def test_a_dropped_limits_row_stops_it(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(home, "health.md")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace('level = "delicate"', 'level = "sore"', 1))
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", home=home)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("a [[limits]] row was ignored", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_clinician_avoid_lines_leave_movements_out(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            with open(os.path.join(home, "health.md"), "a", encoding="utf-8") as f:
                f.write("- Avoid: goblet-squat, overhead\n")
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        listed = ids_in(menu_section(r.stdout))
        self.assertNotIn("goblet-squat", listed)
        cat = catalog.load()
        self.assertFalse([i for i in listed if "overhead" in cat.movements[i].flags])
        self.assertIn("goblet squat (not on today's menu)", r.stdout)   # liked, but avoided today

    def test_save_writes_the_brief_and_the_menu_beside_the_draft(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            folder = os.path.join(home, "workouts", "2026-10-21-strength")
            target = os.path.join(folder, "2026-10-21-strength.draft.txt")
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", "--save", target, home=home)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(folder, "2026-10-21-strength.brief.md"), encoding="utf-8") as f:
                self.assertEqual(f.read(), r.stdout)
            with open(os.path.join(folder, "2026-10-21-strength.menu.json"), encoding="utf-8") as f:
                saved = json.load(f)
        self.assertEqual(saved["seconds"], 1800)
        self.assertEqual(saved["request"]["kit"], "home")
        self.assertEqual({e["id"] for e in saved["movements"]}, ids_in(menu_section(r.stdout)))


DRAFT = """movements: goblet squat, dead bug
movements: box breathing

@@ 120 | Warm-up
Welcome. Made by AI, so you have the final say. Swing your arms easy, then squat down slow. Push up through your heels.

@@ 120 | Work
Goblet squats now. Then the dead bug.

@@ 60 | Close
Box breathing to finish.
"""


def fake_menu(*ids, seconds=300, side=None):
    cat = catalog.load()
    movements = [{"id": i, "name": cat.movements[i].name, "aliases": cat.movements[i].aliases} for i in ids]
    if side:
        movements[-1]["side"] = side
    request = {"goal": "general", "minutes": seconds // 60, "kit": "home"}
    return {"format": menu.FORMAT, "date": "2026-10-21", "request": request, "seconds": seconds,
            "movements": movements}


def one(cat, declared, line):
    """A one-segment draft declaring `declared`, on a menu of it alone, saying `line`: its issues."""
    m = catalog.resolve(cat, declared)
    text = f"movements: {m.name}\n@@ 300 | A\n{line}\n"
    return menu.check(cat, fake_menu(m.id), text, draft.parse(text))[0]


class Menu(unittest.TestCase):
    """menu.check: what a draft may say against its menu. The text scan's holes too: a shortened name that is
    another movement, a negation in the sentence before, one-word names and spaced plurals."""

    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.load()

    def check(self, text, m):
        return menu.check(self.cat, m, text, draft.parse(text))

    def test_drafts_that_pass(self):
        on_menu = fake_menu("goblet-squat", "dead-bug", "box-breathing")
        bridge = "movements: single-leg glute bridge\n@@ 300 | Work\n"
        left_out = ("movements: dead bug\n@@ 300 | Work\nNo neck rolls today, and no overhead press. "
                    "It should feel like a brisk walk. Now the dead bug.\n")
        bench = DRAFT.replace("goblet squat", "dumbbell bench press").replace(
            "Goblet squats now.", "Back to the dumbbell bench press.")
        rows = (
            # "swing", "squat" and "push up" are coaching words, not movements
            ("on its menu", DRAFT, on_menu),
            # glute bridge isn't on the menu, and isn't named
            ("an alias inside a longer name", bridge + "Single leg glute bridges, ten a side. That's the "
             "single-leg glute bridge.\n", fake_menu("single-leg-glute-bridge")),
            ("a healthy side only movement", bridge + "Right side only today.\n",
             fake_menu("single-leg-glute-bridge", side="right")),
            ("effort words aren't machines", "movements: towel door row\n@@ 300 | Work\nEasy rows now, then a brisk "
             "walk pace. A steady ride.\n", fake_menu("towel-door-row")),
            ("saying what is left out", left_out, fake_menu("dead-bug")),
            ("a short form naming no other movement", bench,
             fake_menu("dumbbell-bench-press", "dead-bug", "box-breathing")),
        )
        for name, text, m in rows:
            with self.subTest(name):
                self.assertEqual(self.check(text, m), ([], []))
        for line in ("No goblet squats today.", "Nothing like goblet squats for the legs, but we rest now.",
                     "Push up through the heels.", "Step up the pace now.", "Swing your arms and squat down."):
            with self.subTest(line):
                self.assertEqual(one(self.cat, "dead bug", line), [])

    def test_drafts_that_fail(self):
        on_menu = ("goblet-squat", "dead-bug", "box-breathing")
        left_out = ("movements: dead bug\n@@ 300 | Work\nNo neck rolls today, and no overhead press. "
                    "It should feel like a brisk walk. Now the dead bug.\n")
        rows = (
            ("no menu", DRAFT, None, ("no menu",)),
            ("declared off the menu", DRAFT, fake_menu("goblet-squat", "box-breathing"),
             ("dead bug", "isn't on today's menu")),
            ("declared unknown", DRAFT.replace("dead bug", "moon walk", 1), fake_menu(*on_menu),
             ("moon walk", "isn't a movement")),
            ("an unlisted movement named", DRAFT.replace("Then the dead bug.", "Then the dead bug, and a dumbbell "
             "bench press."), fake_menu(*on_menu), ("dumbbell bench press", "dumbbell-bench-press")),
            # "push up through your heels" didn't count, "push-ups" does
            ("a hyphenated name", DRAFT.replace("Then the dead bug.", "Then the dead bug, and ten push-ups."),
             fake_menu(*on_menu), ("push-up",)),
            # "bench press" is a movement of its own (the barbell one, harder), so the short form is taken for it
            ("a short form that is another movement", DRAFT.replace("goblet squat", "dumbbell bench press").replace(
                "Goblet squats now.", "Back to the bench press."),
             fake_menu("dumbbell-bench-press", "dead-bug", "box-breathing"), ("bench press", "isn't on today's menu")),
            ("a machine", "movements: towel door row\n@@ 300 | Work\nEasy rows now.\nThen the steady bike.\n",
             fake_menu("towel-door-row"), ("steady bike",)),
            ("a left-out movement done", left_out.replace("Now the dead bug.", "Now ten overhead presses."),
             fake_menu("dead-bug"), ("overhead press",)),
            ("a negation that doesn't reach", left_out.replace("Now the dead bug.", "Now no more than ten overhead "
             "presses."), fake_menu("dead-bug"), ("overhead press",)),
            ("segments short of the request", DRAFT, fake_menu(*on_menu, seconds=360), ("add up to 300 s", "add 60 s")),
            ("nothing declared", DRAFT.split("\n", 2)[2], fake_menu(*on_menu), ("no movements: line",)),
        )
        for name, text, m, words in rows:
            with self.subTest(name):
                issues, _ = self.check(text, m)
                self.assertTrue(any(all(w in i for w in words) for i in issues), issues)
        scans = (("wall push-up", "Ten push-ups now, nice and strong.", ("isn't on today's menu", "push-up")),
                 ("seated shadow boxing", "Stand up and start shadow boxing.", ("isn't on today's menu", "shadow")),
                 ("dead bug", "Do not rest. Goblet squats, ten of them.", ("goblet-squat",)),
                 ("dead bug", "If you'd like, add goblet squats here.", ("goblet-squat",)),
                 ("dead bug", "Ten goblet squats.", ("goblet-squat",)),
                 ("dead bug", "Ten deadlifts, then rest.", ("deadlift",)),
                 ("dead bug", "Twenty push ups.", ("push-up",)),
                 ("dead bug", "Step ups onto the bench.", ("step-up",)))
        for declared, line, words in scans:
            with self.subTest(line):
                issues = one(self.cat, declared, line)
                self.assertTrue(any(all(w in i for w in words) for i in issues), issues)

    def test_a_shortened_name_naming_no_other_movement_counts_as_the_declared_one(self):
        for m in self.cat.movements.values():
            words = m.name.split()
            if len(words) >= 3 and catalog.resolve(self.cat, " ".join(words[-2:])) is None:
                self.assertEqual(one(self.cat, m.name, f"Back to the {' '.join(words[-2:])}."), [], m.name)
                break
        else:
            self.fail("no movement to try the shortened form on")

    def test_an_undeclared_menu_movement_is_a_warning(self):
        text = DRAFT.replace("Then the dead bug.", "Then the dead bug, and a bird dog.")
        issues, warnings = self.check(text, fake_menu("goblet-squat", "dead-bug", "box-breathing", "bird-dog"))
        self.assertEqual(issues, [])
        self.assertTrue(any("bird dog" in w for w in warnings), warnings)

    def test_the_lint_needs_its_menu(self):
        """./harmonicfitness build --lint-only: every draft but the smoke test needs its menu."""
        import build
        rows = (("a missing menu", None, 1, ("no menu",), ()),
                # the lint's own issue counts too, so the work left isn't hidden behind the menu's (on stderr)
                ("menu issues", fake_menu("goblet-squat", "box-breathing"), 1, ("isn't on today's menu",),
                 ("2 menu issue(s) and 1 lint issue(s). Fix and rerun",)),
                ("on its menu", fake_menu("goblet-squat", "dead-bug", "box-breathing"), None,
                 ("every movement is on today's menu (3 declared)",), ()))
        for name, menu_data, code, out_words, err_words in rows:
            with self.subTest(name), tempfile.TemporaryDirectory() as d:
                home = os.path.join(d, "me")
                shutil.copytree(LISTENER, home)
                path = os.path.join(home, "workouts", "x", "x.draft.txt")
                os.makedirs(os.path.dirname(path))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(DRAFT)
                if menu_data is not None:   # a menu from today, made from this listener's health.md, as the brief would
                    menu_data = dict(menu_data, date=datetime.date.today().isoformat(),
                                     health_sha256=menu.health_hash(os.path.join(home, "health.md")))
                    menu.write(draft.menu_path(path), menu_data)
                r = call(build.main, [path, "x", "--lint-only", "--coach", "Coach Julius"], home=home,
                         env={"HARMONICFITNESS_FAKE_LOCAL_ENGINE": "1"})
                if code is not None:
                    self.assertEqual(r.returncode, code, r.stdout + r.stderr)
                for w in out_words:
                    self.assertIn(w, r.stdout, r.stdout + r.stderr)
                for w in err_words:
                    self.assertIn(w, r.stderr)
                self.assertNotIn("menu issue(s)", r.stdout)


class MenuGate(unittest.TestCase):
    """The menu is today's and health.md hasn't changed since the brief; otherwise the build stops (a lint
    only warns), and a menu file that can't be read is an issue, not a traceback."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cat = catalog.load()
        home = os.path.join(self.tmp.name, "me")   # the re-screen reads the profile and health.md
        shutil.copytree(LISTENER, home)
        ctx = helpers.home(home)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.health = os.path.join(home, "health.md")
        self.draft_path = os.path.join(self.tmp.name, "x.draft.txt")
        with open(self.draft_path, "w", encoding="utf-8") as f:
            f.write(DRAFT)
        self.segments = draft.parse(DRAFT)
        self.menu = fake_menu("goblet-squat", "dead-bug", "box-breathing")
        self.menu["date"] = "2026-10-20"
        self.menu["health_sha256"] = menu.health_hash(self.health)
        menu.write(draft.menu_path(self.draft_path), self.menu)

    def gate(self, **kw):
        kw.setdefault("today", "2026-10-20")
        kw.setdefault("health_path", self.health)
        return menu.gate(self.cat, self.draft_path, DRAFT, self.segments, **kw)

    def test_todays_menu_with_unchanged_health_passes(self):
        self.assertEqual(self.gate(), ([], []))

    def test_an_older_menu_is_an_issue_on_a_render_and_a_warning_on_a_lint(self):
        issues, warnings = self.gate(today="2026-10-21")
        self.assertTrue(any("2026-10-20" in i and "brief" in i for i in issues), issues)
        issues, warnings = self.gate(today="2026-10-21", strict=False)
        self.assertEqual(issues, [])
        self.assertTrue(any("2026-10-20" in w for w in warnings), warnings)

    def test_a_changed_health_file_is_an_issue(self):
        with open(self.health, "a", encoding="utf-8") as f:
            f.write("- Unlisted: a new problem\n")
        issues, _ = self.gate()
        self.assertTrue(any("health.md changed" in i for i in issues), issues)

    def test_a_menu_without_the_hash_or_that_cant_be_read_is_an_issue(self):
        del self.menu["health_sha256"]
        menu.write(draft.menu_path(self.draft_path), self.menu)
        issues, _ = self.gate()
        self.assertTrue(any("brief" in i for i in issues), issues)
        with open(draft.menu_path(self.draft_path), "w", encoding="utf-8") as f:
            f.write("not json")
        issues, _ = self.gate()
        self.assertTrue(any("can't be read" in i for i in issues), issues)
        os.remove(draft.menu_path(self.draft_path))
        self.assertIn("no menu", self.gate()[0][0])
        self.assertEqual(self.gate(required=False), ([], []))

    def test_record_carries_the_health_hash(self):
        sel = catalog.select(self.cat, {"mat"}, "novice", [])
        rec = menu.record({"goal": "strength"}, sel, {}, 600, "2026-10-20", health_sha256="abc123")
        self.assertEqual(rec["health_sha256"], "abc123")
        self.assertEqual(menu.health_hash(os.path.join(self.tmp.name, "absent.md")), None)


class BriefAdd(unittest.TestCase):
    def test_add_extends_the_kit_and_the_menu_records_it_with_the_health_hash(self):
        plain = brief("--goal", "strength", "--minutes", "30", "--kit", "home")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            target = os.path.join(home, "workouts", "2026-10-21-strength-30", "2026-10-21-strength-30.draft.txt")
            more = brief("--goal", "strength", "--minutes", "30", "--kit", "home", "--add", "bench", "--save", target,
                         home=home)
            self.assertEqual(more.returncode, 0, more.stderr)
            self.assertTrue(ids_in(menu_section(more.stdout)) > ids_in(menu_section(plain.stdout)))
            self.assertEqual("Loads on hand" in more.stdout, "Loads on hand" in plain.stdout)   # the same kit, plus
            with open(draft.menu_path(target), encoding="utf-8") as f:
                saved = json.load(f)
        self.assertEqual(saved["request"]["add"], ["bench"])
        self.assertEqual(saved["request"]["kit"], "home")
        self.assertEqual(saved["health_sha256"], menu.health_hash(os.path.join(LISTENER, "health.md")))
        self.assertEqual(saved["date"], "2026-10-21")


if __name__ == "__main__":
    unittest.main()
