"""Checks for today's brief (tools/brief.py), the menu it saves and the build's menu check
(tools/menu.py), and the draft's movements: header (tools/draft.py). They run on the shipped catalog
and the invented listener in tests/fixtures/listener, with no models or network."""
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import errors  # noqa: E402
import helpers  # noqa: E402

import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import context  # noqa: E402
import health as health_md  # noqa: E402
import draft  # noqa: E402
import menu  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTENER = os.path.join(ROOT, "tests", "fixtures", "listener")
SECTIONS = ("## The listener", "## Today in the week", "## Today's limits", "## Safe menu",
            "## Programming guide", "## Equipment notes", "## Writing it")


def run(cmd, *args, home=LISTENER):
    env = dict(os.environ, HARMONICFITNESS_PYTHON=sys.executable, HARMONICFITNESS_HOME=home)
    return subprocess.run(["sh", os.path.join(ROOT, "harmonicfitness"), cmd, *args],
                          capture_output=True, text=True, env=env, cwd=ROOT, timeout=120)


def brief(*args, home=LISTENER):
    return run("brief", "--today", "2026-10-21", *args, home=home)


def menu_section(text):
    return text.split("## Safe menu", 1)[1].split("## Programming guide", 1)[0]


def ids_in(text):
    return {line.split("(`", 1)[1].split("`", 1)[0] for line in text.splitlines() if line.startswith("- **")}


class Brief(unittest.TestCase):
    def test_prints_every_section(self):
        r = brief("--goal", "strength", "--minutes", "30", "--kit", "home")
        self.assertEqual(r.returncode, 0, r.stderr)
        for heading in SECTIONS:
            self.assertIn(heading, r.stdout, heading)
        self.assertIn("Level: experienced", r.stdout)
        self.assertIn("No pushing through wrist pain.", r.stdout)   # the clinician rule, as written
        self.assertIn("Rest and pairing:", r.stdout)                 # programming.md's rules
        self.assertIn("**Dumbbells.**", r.stdout)                    # kits.md's notes for the kit
        self.assertIn("exactly 1800 s", r.stdout)

    def test_the_brief_quotes_how_the_coach_talks(self):
        r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", "--coach", "Coach Solo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("- Coach: Coach Solo (A coach for the tests.)", r.stdout)
        self.assertIn("- Tone: calm and focused.", r.stdout)

    def test_brief_quotes_the_character_table(self):
        import brief as brief_tool
        from unittest import mock
        import paths
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, "coach-maya"))
        settings = {"name": "Coach Maya", "kind": "web", "service": "inworld", "voice_id": "v1",
                    "voice": {"who": "A woman in her thirties"},
                    "character": {"calls_you": "Alex", "humor": "Dry, now and then", "cueing": "",
                                  "signature": ["Stay with it.", "That's the pace we want."]}}
        with open(os.path.join(d, "coach-maya", "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text(settings, "Free notes.\n- Tone: calm and focused.\n"))
        with mock.patch.object(paths, "PERSONAS", d):
            lines = brief_tool._coach_lines("Coach Maya")
        self.assertEqual(lines, ["- Coach: Coach Maya", "- Calls you: Alex", "- Humor: Dry, now and then",
                                 "- Signature: Stay with it.; That's the pace we want.",
                                 "- Tone: calm and focused."])

    def test_writing_it_gives_the_voices_words_a_minute(self):
        r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", "--coach", "Qwen3 Coach")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"Talk to time: Coach Solo speaks about \d+ words a minute")

    def test_words_a_minute_follow_the_voices_pace(self):
        import brief as brief_tool
        from unittest import mock
        import paths
        with mock.patch.object(paths, "PERSONAS", os.path.join(LISTENER, "personas")), \
                mock.patch.object(paths, "PROFILE", os.path.join(LISTENER, "profile.md")):
            with mock.patch("voices.pace", return_value=(10.0, True)):
                slow, exact = brief_tool.talk_rate("Chatterbox Coach")   # an old name finds Coach Julius
            with mock.patch("voices.pace", return_value=(20.0, True)):
                fast, _ = brief_tool.talk_rate("Coach Julius")
            self.assertTrue(exact)
            self.assertAlmostEqual(fast, slow * 2)
            self.assertIsNone(brief_tool.talk_rate("Nobody At All"))

    def test_talk_rate_web_coach_without_key(self):
        import brief as brief_tool
        import personas
        from unittest import mock
        web = next(p for p in personas.all() if p.is_web)
        with mock.patch("coachpick.resolve", side_effect=errors.CoachError("no key")):
            got = brief_tool.talk_rate(web.name)
        self.assertIsNotNone(got)
        self.assertFalse(got[1])

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

    def test_every_menu_entry_has_its_coaching_notes(self):
        r = brief("--goal", "strength", "--minutes", "30", "--kit", "home")
        section = menu_section(r.stdout)
        entries = section.split("\n- **")[1:]
        self.assertTrue(entries)
        for e in entries:
            self.assertIn("Setup:", e, e[:60])
            self.assertIn("Cues:", e, e[:60])

    def test_a_sided_limit_lists_healthy_side_work_and_fills_the_cues(self):
        r = brief("--goal", "strength", "--minutes", "30", "--preset", "hotel-gym", "--limit", "knee=off-limits:right")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("### Healthy side only", r.stdout)
        self.assertIn("left side only", r.stdout)
        self.assertIn("the right knee", r.stdout)           # the limit cues name the side
        self.assertNotIn("{side}", r.stdout)

    def test_limits_show_each_movements_load_on_them(self):
        r = brief("--goal", "strength", "--minutes", "30", "--kit", "home")
        self.assertIn("load on today's limits: wrist 1", r.stdout)   # delicate wrist: loads of one stay in

    def test_save_writes_the_brief_and_the_menu_beside_the_draft(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            folder = os.path.join(home, "workouts", "2026-10-21-strength")
            target = os.path.join(folder, "2026-10-21-strength.draft.txt")
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", "--save", target, home=home)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(os.path.join(folder, "2026-10-21-strength.brief.md")) as f:
                self.assertEqual(f.read(), r.stdout)
            with open(os.path.join(folder, "2026-10-21-strength.menu.json")) as f:
                saved = json.load(f)
        self.assertEqual(saved["seconds"], 1800)
        self.assertEqual(saved["request"]["kit"], "home")
        self.assertEqual({e["id"] for e in saved["movements"]}, ids_in(menu_section(r.stdout)))

    def test_a_dropped_limits_row_stops_it(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(home, "health.md")
            with open(path) as f:
                text = f.read()
            with open(path, "w") as f:
                f.write(text.replace('level = "delicate"', 'level = "sore"', 1))
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", home=home)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("a [[limits]] row was ignored", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_clinician_avoid_lines_leave_movements_out(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            with open(os.path.join(home, "health.md"), "a") as f:
                f.write("- Avoid: goblet-squat, overhead\n")
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        listed = ids_in(menu_section(r.stdout))
        self.assertNotIn("goblet-squat", listed)
        cat = catalog.load()
        self.assertFalse([i for i in listed if "overhead" in cat.movements[i].flags])
        self.assertIn("goblet squat (not on today's menu)", r.stdout)   # liked, but avoided today

    def test_usage_on_unknown_values(self):
        for args in (["--kit", "castle"], ["--preset", "castle"], ["--equipment", "anvil"],
                     ["--kit", "home", "--limit", "tail=delicate"], ["--kit", "home", "--level", "wizard"],
                     ["--kit", "home", "--avoid", "wobbly"], ["--kit", "home", "--target", "wiggle"]):
            r = brief("--goal", "strength", "--minutes", "30", *args)
            self.assertEqual(r.returncode, 64, args)
            self.assertTrue(r.stderr.strip(), args)

    def test_usage_on_bad_numbers_and_a_save_outside_the_workouts(self):
        for minutes in ("0", "-5", "ten", "2.5"):
            r = brief("--goal", "strength", "--minutes", minutes, "--kit", "home")
            self.assertEqual(r.returncode, 64, minutes)
            self.assertIn("--minutes", r.stderr)
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "elsewhere", "x.draft.txt")
            r = brief("--goal", "strength", "--minutes", "30", "--kit", "home", "--save", target)
            self.assertEqual(r.returncode, 64, r.stderr)
            self.assertIn("--save", r.stderr)
            self.assertFalse(os.path.exists(os.path.join(d, "elsewhere")))
            self.assertEqual(r.stdout, "")   # refused before anything is printed

    def test_a_damaged_knowledge_file_is_the_files_problem_not_the_commands(self):
        """A corrupt sessions.toml is exit 1 (fix the file), never 64 (the flags were wrong)."""
        import sessions
        with tempfile.TemporaryDirectory() as d:
            bad = os.path.join(d, "sessions.toml")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("format = 2\n[methods.broken\n")
            with self.assertRaises(errors.ContextError):
                sessions.load(bad)
            import contextlib
            import io
            import brief as brief_tool
            import cli
            import paths
            from unittest import mock
            err = io.StringIO()
            with helpers.home(LISTENER), mock.patch.object(paths, "SESSIONS", bad), \
                    contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                code = cli.run(brief_tool.main, ["--goal", "strength", "--minutes", "30", "--kit", "home"])
            self.assertEqual(code, 1, err.getvalue())
            self.assertIn("isn't valid TOML", err.getvalue())

    def test_a_first_session_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            r = brief("--goal", "mobility", "--minutes", "20", "--kit", "home", "--log",
                      os.path.join(ROOT, "docs", "eval", "listeners", "d", "log.md"), home=home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("No sessions logged yet", r.stdout)
        self.assertIn("Mobility:", r.stdout)   # the mobility dose for the level


DRAFT = """movements: goblet squat, dead bug
movements: box breathing

@@ 120 | Warm-up
Welcome. Swing your arms easy, then squat down slow. Push up through your heels.

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


class Menu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.load()

    def check(self, text, m):
        return menu.check(self.cat, m, text, draft.parse(text))

    def test_a_draft_on_its_menu_passes(self):
        issues, warnings = self.check(DRAFT, fake_menu("goblet-squat", "dead-bug", "box-breathing"))
        self.assertEqual(issues, [])
        self.assertEqual(warnings, [])   # "swing", "squat" and "push up" are coaching words, not movements

    def test_no_menu_is_an_issue(self):
        issues, _ = self.check(DRAFT, None)
        self.assertIn("no menu", issues[0])

    def test_a_declared_movement_off_the_menu_fails(self):
        issues, _ = self.check(DRAFT, fake_menu("goblet-squat", "box-breathing"))
        self.assertTrue(any("dead bug" in i and "isn't on today's menu" in i for i in issues), issues)

    def test_an_unknown_declared_movement_fails(self):
        issues, _ = self.check(DRAFT.replace("dead bug", "moon walk", 1), fake_menu("goblet-squat", "box-breathing", "dead-bug"))
        self.assertTrue(any("moon walk" in i and "isn't a movement" in i for i in issues), issues)

    def test_naming_an_unlisted_movement_fails(self):
        text = DRAFT.replace("Then the dead bug.", "Then the dead bug, and a dumbbell bench press.")
        issues, _ = self.check(text, fake_menu("goblet-squat", "dead-bug", "box-breathing"))
        self.assertTrue(any("dumbbell bench press" in i and "dumbbell-bench-press" in i for i in issues), issues)

    def test_a_hyphenated_name_needs_its_hyphen(self):
        text = DRAFT.replace("Then the dead bug.", "Then the dead bug, and ten push-ups.")
        issues, _ = self.check(text, fake_menu("goblet-squat", "dead-bug", "box-breathing"))
        self.assertTrue(any("push-up" in i for i in issues), issues)   # "push up through your heels" didn't count

    def test_an_alias_inside_a_longer_name_does_not_match(self):
        m = self.cat.movements["single-leg-glute-bridge"]
        text = ("movements: single-leg glute bridge\n@@ 300 | Work\n"
                "Single leg glute bridges, ten a side. That's the single-leg glute bridge.\n")
        issues, warnings = self.check(text, fake_menu(m.id))
        self.assertEqual((issues, warnings), ([], []))   # glute bridge isn't on the menu, and isn't named

    def test_a_shortened_name_counts_as_the_declared_movement_unless_it_names_another(self):
        text = DRAFT.replace("goblet squat", "dumbbell bench press").replace("Goblet squats now.", "Back to the bench press.")
        issues, warnings = self.check(text, fake_menu("dumbbell-bench-press", "dead-bug", "box-breathing"))
        # "bench press" is a movement of its own (the barbell one, harder), so the short form is taken for it
        self.assertTrue(any("bench press" in i and "isn't on today's menu" in i for i in issues), (issues, warnings))
        # a short form that names no other movement counts as the declared one (MenuScan checks one too)
        text = DRAFT.replace("goblet squat", "dumbbell bench press").replace("Goblet squats now.", "Back to the dumbbell bench press.")
        self.assertEqual(self.check(text, fake_menu("dumbbell-bench-press", "dead-bug", "box-breathing")), ([], []))
    def test_effort_words_are_not_machine_names(self):
        text = "movements: towel door row\n@@ 300 | Work\nEasy rows now, then a brisk walk pace. A steady ride.\n"
        issues, _ = self.check(text, fake_menu("towel-door-row"))
        self.assertEqual(issues, [])
        issues, _ = self.check(text + "Then the steady bike.\n", fake_menu("towel-door-row"))
        self.assertTrue(any("steady bike" in i for i in issues), issues)

    def test_saying_what_is_left_out_is_fine(self):
        text = ("movements: dead bug\n@@ 300 | Work\nNo neck rolls today, and no overhead press. "
                "It should feel like a brisk walk. Now the dead bug.\n")
        issues, _ = self.check(text, fake_menu("dead-bug"))
        self.assertEqual(issues, [])
        for said in ("Now ten overhead presses.", "Now no more than ten overhead presses."):
            issues, _ = self.check(text.replace("Now the dead bug.", said), fake_menu("dead-bug"))
            self.assertTrue(any("overhead press" in i for i in issues), (said, issues))

    def test_a_healthy_side_only_movement_is_allowed(self):
        text = "movements: single-leg glute bridge\n@@ 300 | Work\nRight side only today.\n"
        issues, _ = self.check(text, fake_menu("single-leg-glute-bridge", side="right"))
        self.assertEqual(issues, [])

    def test_an_undeclared_menu_movement_is_a_warning(self):
        text = DRAFT.replace("Then the dead bug.", "Then the dead bug, and a bird dog.")
        issues, warnings = self.check(text, fake_menu("goblet-squat", "dead-bug", "box-breathing", "bird-dog"))
        self.assertEqual(issues, [])
        self.assertTrue(any("bird dog" in w for w in warnings), warnings)

    def test_segments_must_add_up_to_the_request(self):
        issues, _ = self.check(DRAFT, fake_menu("goblet-squat", "dead-bug", "box-breathing", seconds=360))
        self.assertTrue(any("add up to 300 s" in i and "add 60 s" in i for i in issues), issues)

    def test_a_draft_with_nothing_declared_fails(self):
        text = DRAFT.split("\n", 2)[2]
        issues, _ = self.check(text, fake_menu("goblet-squat", "dead-bug", "box-breathing"))
        self.assertTrue(any("no movements: line" in i for i in issues), issues)


class Header(unittest.TestCase):
    def test_the_header_is_read_and_never_spoken(self):
        segs = draft.parse(DRAFT)
        self.assertEqual(len(segs), 3)
        self.assertNotIn("movements", " ".join(line for s in segs for _, line in s["lines"]))
        self.assertEqual(draft.declared(DRAFT), ["goblet squat", "dead bug", "box breathing"])

    def test_other_text_before_the_first_marker_still_fails(self):
        with self.assertRaises(errors.PROBLEMS):
            draft.parse("Hello.\n" + DRAFT)

    def test_menu_and_brief_sit_beside_the_draft(self):
        self.assertEqual(draft.menu_path("a/b/2026-10-21-x.draft.txt"), "a/b/2026-10-21-x.menu.json")
        self.assertEqual(draft.brief_path("a/b/2026-10-21-x"), "a/b/2026-10-21-x.brief.md")
        self.assertEqual(draft.menu_path("docs/eval/out/c06.draft.txt"), "docs/eval/out/c06.menu.json")


class Lint(unittest.TestCase):
    """The lint stage of ./harmonicfitness build --lint-only: every draft but the smoke test needs its menu."""

    def lint(self, text, menu_data):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(home, "workouts", "x", "x.draft.txt")
            os.makedirs(os.path.dirname(path))
            with open(path, "w") as f:
                f.write(text)
            if menu_data is not None:   # a menu from today, made from this listener's health.md, as the brief would
                menu_data = dict(menu_data, date=datetime.date.today().isoformat(),
                                 health_sha256=menu.health_hash(os.path.join(home, "health.md")))
                menu.write(draft.menu_path(path), menu_data)
            env = dict(os.environ, HARMONICFITNESS_HOME=home, HARMONICFITNESS_FAKE_LOCAL_ENGINE="1")
            return subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build.py"), path, "x", "--lint-only",
                                   "--coach", "Coach Julius"],
                                  capture_output=True, text=True, env=env, cwd=ROOT, timeout=120)

    def test_a_missing_menu_fails(self):
        r = self.lint(DRAFT, None)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no menu", r.stdout)

    def test_menu_issues_fail(self):
        r = self.lint(DRAFT, fake_menu("goblet-squat", "box-breathing"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("isn't on today's menu", r.stdout)
        self.assertIn("menu issue(s). Fix and rerun", r.stderr)   # the failure summary: stderr, as every command's
        self.assertNotIn("menu issue(s)", r.stdout)

    def test_a_draft_on_its_menu_passes_the_menu_check(self):
        r = self.lint(DRAFT, fake_menu("goblet-squat", "dead-bug", "box-breathing"))
        self.assertIn("every movement is on today's menu (3 declared)", r.stdout, r.stdout + r.stderr)
        self.assertNotIn("menu issue", r.stdout)


class LogSession(unittest.TestCase):
    def test_log_session_takes_the_declared_movements(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(d, "x.draft.txt")
            text = DRAFT.replace("goblet squat", "goblet-squat", 1)
            with open(path, "w") as f:
                f.write(text)
            # a built draft: its menu (the date, length and kit) and a build record with its hash
            menu.write(draft.menu_path(path), {"format": menu.FORMAT, "date": "2026-10-21",
                                               "request": {"minutes": 5, "kit": "home"},
                                               "seconds": 300, "movements": []})
            os.makedirs(os.path.join(home, "workouts", ".logs"))
            with open(os.path.join(home, "workouts", ".logs", "builds.jsonl"), "w") as f:
                f.write(json.dumps({"draft_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}) + "\n")
            r = run("log-session", "--date", "2026-10-21", "--minutes", "5", "--kit", "home", "--coach",
                    "Chatterbox Coach", "--draft", path, "--topics", "test topics", "--format", "circuit", home=home)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("goblet squat, dead bug, box breathing", r.stdout)   # ids become catalog names
            r = run("log-session", "--minutes", "5", "--kit", "home", "--coach", "Chatterbox Coach",
                    "--topics", "x", home=home)
            self.assertNotEqual(r.returncode, 0)


class MenuScan(unittest.TestCase):
    """The text scan's holes: a shortened name that is another movement, a negation in the sentence before,
    one-word names and spaced plurals."""

    @classmethod
    def setUpClass(cls):
        cls.cat = catalog.load()

    def one(self, declared, line):
        m = catalog.resolve(self.cat, declared)
        text = f"movements: {m.name}\n@@ 300 | A\n{line}\n"
        return menu.check(self.cat, fake_menu(m.id), text, draft.parse(text))[0]

    def test_a_shortened_name_that_is_another_movement_is_caught(self):
        issues = self.one("wall push-up", "Ten push-ups now, nice and strong.")
        self.assertTrue(any("isn't on today's menu" in i and "push-up" in i for i in issues), issues)
        issues = self.one("seated shadow boxing", "Stand up and start shadow boxing.")
        self.assertTrue(any("isn't on today's menu" in i and "shadow" in i for i in issues), issues)
        # a shortened form that names no other movement still counts as the declared one
        for m in self.cat.movements.values():
            words = m.name.split()
            if len(words) >= 3 and catalog.resolve(self.cat, " ".join(words[-2:])) is None:
                self.assertEqual(self.one(m.name, f"Back to the {' '.join(words[-2:])}."), [], m.name)
                break
        else:
            self.fail("no movement to try the shortened form on")

    def test_a_negation_counts_only_within_its_clause(self):
        for line in ("Do not rest. Goblet squats, ten of them.", "If you'd like, add goblet squats here.",
                     "Ten goblet squats."):
            self.assertTrue(any("goblet-squat" in i for i in self.one("dead bug", line)), line)
        for line in ("No goblet squats today.", "Nothing like goblet squats for the legs, but we rest now."):
            self.assertEqual(self.one("dead bug", line), [], line)

    def test_one_word_names_and_spaced_plurals_are_scanned(self):
        for line, mid in (("Ten deadlifts, then rest.", "deadlift"), ("Twenty push ups.", "push-up"),
                          ("Step ups onto the bench.", "step-up")):
            self.assertTrue(any(mid in i for i in self.one("dead bug", line)), line)
        for line in ("Push up through the heels.", "Step up the pace now.", "Swing your arms and squat down."):
            self.assertEqual(self.one("dead bug", line), [], line)


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


class MethodLines(unittest.TestCase):
    def test_a_methods_rest_and_work_reach_the_writer(self):
        r = brief("--goal", "general", "--minutes", "20", "--kit", "home")
        self.assertEqual(r.returncode, 0, r.stderr)
        circuit = next(line for line in r.stdout.splitlines() if line.startswith("- circuit:"))
        self.assertIn("rest 45 to 90 s between rounds", circuit)
        self.assertIn("work: rounds", circuit)


class PatternCache(unittest.TestCase):
    def test_patterns_are_cached_per_catalog_object_not_its_address(self):
        cat = catalog.load()
        first = menu._patterns(cat)
        self.assertIs(menu._patterns(cat), first)
        self.assertIs(cat.__dict__.get("_menu_patterns"), first)   # kept on the object, so no other can inherit it
        other = catalog.load()
        self.assertIsNone(other.__dict__.get("_menu_patterns"))
        self.assertIsNot(menu._patterns(other), first)
        self.assertFalse(hasattr(menu, "_PATTERNS"))


if __name__ == "__main__":
    unittest.main()
