"""Checks for the session log and the content log: log-session with --draft takes the date, length and kit
from the menu and needs a build of that exact draft, refuses a second line for the same session, and
logs loads by catalog name; coverage reads old free-text loads through the catalog; content log checks
the category and refuses a reserve piece already told. They run
on the invented listener in tests/fixtures/listener, copied to a temporary folder."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import cli  # noqa: E402
import content  # noqa: E402
import context  # noqa: E402
import sessionlog  # noqa: E402
import records  # noqa: E402
import coverage  # noqa: E402
import draft  # noqa: E402
import helpers  # noqa: E402
import errors  # noqa: E402
import menu  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTENER = os.path.join(ROOT, "tests", "fixtures", "listener")
TEXT = "movements: goblet squat, dead bug\n@@ 300 | Work\nGoblet squats, then dead bugs.\n"


class LogSession(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self.tmp.name, "me")
        shutil.copytree(LISTENER, self.home)
        self.stem = os.path.join(self.home, "workouts", "2026-10-25-strength-5", "2026-10-25-strength-5")
        self.draft = self.stem + draft.DRAFT_SUFFIX
        os.makedirs(os.path.dirname(self.draft))
        with open(self.draft, "w", encoding="utf-8") as f:
            f.write(TEXT)
        self.menu({"goal": "strength", "minutes": 5, "equipment": ["dumbbells", "mat"]})
        self.builds = os.path.join(self.home, "workouts", ".logs", "builds.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def menu(self, request, date="2026-10-25"):
        menu.write(draft.menu_path(self.draft), {"format": menu.FORMAT, "date": date, "health_sha256": "x",
                                                 "request": request, "seconds": request["minutes"] * 60,
                                                 "movements": []})

    def record(self, **fields):
        os.makedirs(os.path.dirname(self.builds), exist_ok=True)
        rec = {"draft": "x", "draft_sha256": hashlib.sha256(TEXT.encode("utf-8")).hexdigest(), "drift": 0.0}
        rec.update(fields)
        with open(self.builds, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def test_web_builds_counts_every_build_that_sent_a_script(self):
        """get web-builds: what the privacy line before the first web build reads; a failed web render sent text too."""
        self.assertEqual(records.web_builds(self.builds), 0)                 # no file yet
        self.record(route="local")
        self.record()                                                         # an old record, before routes
        self.assertEqual(records.web_builds(self.builds), 0)
        self.record(route="fish", failed=True)
        with open(self.builds, "a", encoding="utf-8") as f:
            f.write("not json\n")
        self.record(route="gemini")
        self.assertEqual(records.web_builds(self.builds), 2)
        out = io.StringIO()
        with helpers.home(self.home), contextlib.redirect_stdout(out):
            self.assertEqual(context.main(["get", "web-builds"]), cli.OK)
        self.assertEqual(out.getvalue().strip(), "2")

    def log(self, *extra, base=True):
        args = ["log-session", "--coach", "Chatterbox Coach", "--topics", "t"]
        if base:
            args += ["--draft", self.draft, "--format", "circuit"]
        out = io.StringIO()
        with helpers.home(self.home), contextlib.redirect_stdout(out):
            code = context.main(args + list(extra))
        return code, out.getvalue()

    def refused(self, *extra, words, base=True):
        with self.assertRaises(errors.PROBLEMS) as got:
            self.log(*extra, base=base)
        self.assertIn("Not logged", str(got.exception))
        self.assertIn(words, str(got.exception))

    def test_the_menu_gives_the_date_the_length_and_an_equipment_kit(self):
        self.record()
        code, out = self.log()
        self.assertEqual(code, cli.OK)
        self.assertIn("- 2026-10-25 | 5 min | custom: dumbbells, mat | Chatterbox Coach | goblet squat, dead bug", out)
        with helpers.home(self.home):
            last = sessionlog.sessions()[-1]
        self.assertEqual((last.kit, last.format), ("custom: dumbbells, mat", "circuit"))

    def test_a_kit_or_a_preset_is_logged_by_its_name(self):
        self.record()
        self.menu({"goal": "strength", "minutes": 5, "preset": "hotel-room"})
        self.assertIn("| hotel-room |", self.log()[1])

    def test_a_typed_value_must_agree_with_the_menu(self):
        self.record()
        self.refused("--minutes", "30", words="--minutes 30")
        self.refused("--date", "2026-10-24", words="--date 2026-10-24")
        self.refused("--kit", "home", words="--kit home")
        code, _ = self.log("--minutes", "5", "--date", "2026-10-25", "--kit", "Custom: dumbbells, mat")
        self.assertEqual(code, cli.OK)

    def test_log_session_takes_keywords_not_a_command_line(self):
        """logsession.log_session is called with its fields by name: no parsed command line to fake."""
        import inspect
        import logsession
        params = inspect.signature(logsession.log_session).parameters
        self.assertTrue(all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values()))
        self.assertEqual(list(params), ["topics", "draft", "date", "minutes", "kit", "coach", "movements", "fmt",
                                        "loads", "rpe"])
        self.record()
        with helpers.home(self.home):
            line = logsession.log_session(topics="t", draft=self.draft, coach="Chatterbox Coach", fmt="circuit",
                                          loads="goblet squat = 12 kg")
            self.assertIn("goblet squat", line)
            self.assertTrue(line.startswith("Logged: - 2026-10-25 | 5 min | custom: dumbbells, mat | "
                                            "Chatterbox Coach"), line)
            with self.assertRaises(errors.UsageError):   # neither movements nor a draft
                logsession.log_session(topics="t", coach="Chatterbox Coach", minutes=10, kit="home")
            line = logsession.log_session(topics="t2", movements="glute bridge", coach="Chatterbox Coach",
                                          minutes=10, kit="home", date="2026-10-26")
        self.assertIn("2026-10-26 | 10 min | home | Chatterbox Coach | glute bridge", line)

    def test_format_is_required_with_a_draft(self):
        self.record()
        with self.assertRaises(errors.PROBLEMS) as got, helpers.home(self.home):
            context.main(["log-session", "--coach", "Chatterbox Coach", "--topics", "t", "--draft", self.draft])
        self.assertIn("--format", str(got.exception))

    def test_a_draft_needs_its_menu(self):
        self.record()
        os.remove(draft.menu_path(self.draft))
        self.refused(words="menu")

    def test_a_draft_must_have_been_built(self):
        self.refused(words="no build")
        self.record(failed=True)                              # a web render that stopped partway made no MP3
        self.record(draft_sha256="0" * 64)                    # an earlier version of the draft
        self.refused(words="no build")
        self.record(drift=0.05)   # a build that ran off plan (exit 2) still made an MP3, so it counts
        self.assertEqual(self.log()[0], cli.OK)

    def test_a_session_is_logged_once(self):
        self.record()
        self.assertEqual(self.log()[0], cli.OK)
        self.refused(words="already logged")
        # the same movements on the same day by --movements count as the same session too
        self.refused("--date", "2026-10-25", "--minutes", "5", "--kit", "home", "--movements",
                     "goblet squats, dead bug", base=False, words="already logged")

    def test_loads_are_logged_by_catalog_name_and_must_be_the_sessions(self):
        self.record()
        self.refused("--loads", "push-up = bodyweight", words="push-up")
        self.refused("--loads", "nonsense = 20s", words="nonsense")
        self.refused("--rpe", "kettlebell swing = 7", words="kettlebell swing")
        code, out = self.log("--loads", "Goblet squats = twenties, three down", "--rpe", "dead bugs = 6")
        self.assertEqual(code, cli.OK)
        self.assertIn("loads: goblet squat = twenties, three down | rpe: dead bug = 6", out)

    def logged(self, *args):
        out = io.StringIO()
        with helpers.home(self.home), contextlib.redirect_stdout(out):
            code = context.main(["log-session", "--topics", "t", "--draft", self.draft, "--format", "circuit", *args])
        return code, out.getvalue()

    def test_the_session_links_to_its_newest_build(self):
        self.record(voice="Coach Julius", build_id="old111111111")
        self.record(failed=True, voice="Coach Julius", build_id="failed222222")   # made no MP3
        self.record(voice="Coach Julius", build_id="abc123def456")
        self.record(event="delivered", build_id="evt333333333")                   # an outcome line, not a build
        sha = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
        self.assertEqual(records.latest_build(sha, self.builds)["build_id"], "abc123def456")
        self.assertIsNone(records.latest_build("0" * 64, self.builds))
        code, out = self.logged()   # no --coach: the build's coach
        self.assertEqual(code, cli.OK)
        self.assertIn("| Coach Julius |", out)
        self.assertTrue(out.rstrip().endswith("| build: abc123def456"), out)
        with helpers.home(self.home):
            last = sessionlog.sessions()[-1]
        self.assertEqual((last.voice, last.build_id), ("Coach Julius", "abc123def456"))

    def test_a_coach_that_disagrees_with_the_build_is_refused(self):
        self.record(voice="Coach Julius", build_id="abc123def456")
        with self.assertRaises(errors.LogRefused) as got:
            self.logged("--coach", "Coach Solo")
        self.assertIn("disagrees", str(got.exception))
        code, out = self.logged("--coach", "Chatterbox Coach")   # an alias of the build's coach is the same coach
        self.assertEqual(code, cli.OK)
        self.assertIn("| Coach Julius |", out)

    def test_a_record_without_a_coach_needs_one_typed(self):
        self.record()   # from before builds named their coach
        with self.assertRaises(errors.LogRefused):
            self.logged()
        code, out = self.logged("--coach", "Chatterbox Coach")
        self.assertEqual(code, cli.OK)
        self.assertNotIn("build:", out)   # nor a build_id to link

    def test_a_line_without_a_build_still_reads(self):
        line = "- 2026-10-21 | 20 min | Home | Coach Julius | goblet squat | t | format: circuit"
        s = sessionlog.parse_session(line)
        self.assertIsInstance(s, sessionlog.Session)
        self.assertIsNone(s.build_id)
        self.assertEqual(sessionlog.parse_session(line + " | build: abc123def456").build_id, "abc123def456")
        bad = sessionlog.Session("2026-10-21", 20, "Home", "V", ["goblet squat"], "t", build_id="a|b")
        self.assertTrue(bad.problems())

    def test_without_a_draft_the_coach_is_typed(self):
        with self.assertRaises(errors.UsageError):
            with helpers.home(self.home):
                context.main(["log-session", "--topics", "t", "--movements", "goblet squat", "--minutes", "10",
                              "--kit", "home"])

    def test_without_a_draft_the_length_and_kit_are_typed(self):
        self.refused("--movements", "goblet squat", "--kit", "home", base=False, words="--minutes")
        self.refused("--movements", "goblet squat", "--minutes", "10", base=False, words="--kit")
        code, out = self.log("--movements", "goblet squat", "--minutes", "10", "--kit", "home", base=False)
        self.assertEqual(code, cli.OK)


class Loads(unittest.TestCase):
    def test_last_loads_merge_spellings_of_one_movement(self):
        log = [sessionlog.Session("2026-10-20", 20, "home", "V", ["goblet squat"], "t", loads={"Goblet squat": "15s"}),
               sessionlog.Session("2026-10-22", 20, "home", "V", ["goblet squats"], "t", loads={"goblet squats": "20s"}),
               sessionlog.Session("2026-10-23", 20, "home", "V", ["wall angel thing"], "t", loads={"Wall angel thing": "x"})]
        self.assertEqual(coverage.last_loads(log), {"goblet squat": ("2026-10-22", "20s"),
                                                    "Wall angel thing": ("2026-10-23", "x")})


class ContentLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.told = os.path.join(self.tmp.name, "told.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_topic_must_be_one_of_theirs(self):
        profile = context.Profile({}, "## Topics\n- Hockey: the Devils\n")
        with self.assertRaises(ValueError) as got:
            content.log("2026-10-23", ["Hokey | quick hit | A result"], path=self.told, profile=profile)
        self.assertIn("Hokey", str(got.exception))
        self.assertIn("Hockey", str(got.exception))
        content.log("2026-10-23", ["hockey | quick hit | A result"], path=self.told, profile=profile)
        # an old [[interests]] row is a topic too
        old = context.Profile({"interests": [{"name": "Sports", "slot": "today", "detail": ""}]}, "")
        content.log("2026-10-23", ["sports | quick_hit | A result"], path=self.told, profile=old)

    def test_a_reserve_piece_is_told_once(self):
        reserve = os.path.join(self.tmp.name, "reserve")
        os.makedirs(reserve)
        with open(os.path.join(reserve, "grid-plan.md"), "w", encoding="utf-8") as f:
            f.write("# Grid\n- Topic: history\n- Format: explainer\n")
        with mock.patch.object(content.paths, "RESERVE", reserve):
            with self.assertRaises(ValueError) as got:   # twice in one call
                content.log("2026-10-23", ["history | explainer | Grid | | grid-plan"] * 2, path=self.told)
            content.log("2026-10-23", ["history | explainer | Grid | | grid-plan"], path=self.told)
            with self.assertRaises(ValueError) as got:
                content.log("2026-10-24", ["history | explainer | Grid | | grid-plan"], path=self.told)
        self.assertIn("already told", str(got.exception))


if __name__ == "__main__":
    unittest.main()
