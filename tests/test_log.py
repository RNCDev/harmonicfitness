"""Checks for the session log: log-session with --draft takes the date, length and kit from the menu and needs a
build of that exact draft, refuses a second line for the same session, and logs loads by catalog name. They run
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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import cli  # noqa: E402
import context  # noqa: E402
import sessionlog  # noqa: E402
import records  # noqa: E402
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

    def log(self, *extra, base=True, coach=True):
        args = ["log-session", "--topics", "t"] + (["--coach", "Chatterbox Coach"] if coach else [])
        if base:
            args += ["--draft", self.draft, "--format", "circuit"]
        out = io.StringIO()
        with helpers.home(self.home), contextlib.redirect_stdout(out):
            code = context.main(args + list(extra))
        return code, out.getvalue()

    def refused(self, *extra, words, base=True, coach=True):
        with self.assertRaises(errors.PROBLEMS) as got:
            self.log(*extra, base=base, coach=coach)
        self.assertIn(words, str(got.exception))

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

    def test_the_menu_gives_the_date_the_length_and_the_kit(self):
        self.record()
        self.refused("--minutes", "30", words="--minutes 30")   # a typed value must agree with the menu
        self.refused("--date", "2026-10-24", words="--date 2026-10-24")
        self.refused("--kit", "home", words="--kit home")
        code, out = self.log("--minutes", "5", "--date", "2026-10-25", "--kit", "Custom: dumbbells, mat")
        self.assertEqual(code, cli.OK)
        self.assertIn("- 2026-10-25 | 5 min | custom: dumbbells, mat | Chatterbox Coach | goblet squat, dead bug", out)
        with helpers.home(self.home):
            last = sessionlog.sessions()[-1]
        self.assertEqual((last.kit, last.format), ("custom: dumbbells, mat", "circuit"))
        self.menu({"goal": "strength", "minutes": 5, "preset": "hotel-room"}, date="2026-10-26")
        self.record()
        self.assertIn("| hotel-room |", self.log()[1])

    def test_what_is_refused(self):
        """No build of this exact draft, a second line for one session, no menu, no format, and loads or effort
        for a movement not in the session are each refused; a build that ran off plan still counts."""
        self.refused(words="no build")
        self.record(failed=True)                              # a web render that stopped partway made no MP3
        self.record(draft_sha256="0" * 64)                    # an earlier version of the draft
        self.refused(words="no build")
        self.record(drift=0.05)   # a build that ran off plan (exit 2) still made an MP3, so it counts
        with self.assertRaises(errors.PROBLEMS) as got, helpers.home(self.home):
            context.main(["log-session", "--coach", "Chatterbox Coach", "--topics", "t", "--draft", self.draft])
        self.assertIn("--format", str(got.exception))
        for extra, words in ((("--loads", "push-up = bodyweight"), "push-up"), (("--loads", "nonsense = 20s"), "nonsense"),
                             (("--rpe", "kettlebell swing = 7"), "kettlebell swing")):
            with self.subTest(extra=extra):
                self.refused(*extra, words=words)
        code, out = self.log("--loads", "Goblet squats = twenties, three down", "--rpe", "dead bugs = 6")
        self.assertEqual(code, cli.OK)
        self.assertIn("loads: goblet squat = twenties, three down | rpe: dead bug = 6", out)
        self.refused(words="already logged")
        # the same movements on the same day by --movements count as the same session too
        self.refused("--date", "2026-10-25", "--minutes", "5", "--kit", "home", "--movements",
                     "goblet squats, dead bug", base=False, words="already logged")
        self.refused("--movements", "goblet squat", "--kit", "home", base=False, words="--minutes")
        self.refused("--movements", "goblet squat", "--minutes", "10", base=False, words="--kit")
        with self.assertRaises(errors.UsageError):   # without a draft, the coach is typed
            self.log("--movements", "goblet squat", "--minutes", "10", "--kit", "home", base=False, coach=False)
        os.remove(draft.menu_path(self.draft))
        self.refused(words="menu")

    def test_the_session_links_to_its_newest_build_and_its_coach(self):
        self.record(voice="Coach Julius", build_id="old111111111")
        self.record(failed=True, voice="Coach Julius", build_id="failed222222")   # made no MP3
        self.record(voice="Coach Julius", build_id="abc123def456")
        self.record(event="delivered", build_id="evt333333333")                   # an outcome line, not a build
        sha = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
        self.assertEqual(records.latest_build(sha, self.builds)["build_id"], "abc123def456")
        self.assertIsNone(records.latest_build("0" * 64, self.builds))
        with self.assertRaises(errors.LogRefused) as got:
            self.log("--coach", "Coach Solo", coach=False)
        self.assertIn("disagrees", str(got.exception))
        code, out = self.log(coach=False)   # no --coach: the build's coach
        self.assertEqual(code, cli.OK)
        self.assertIn("| Coach Julius |", out)
        self.assertTrue(out.rstrip().endswith("| build: abc123def456"), out)
        with helpers.home(self.home):
            last = sessionlog.sessions()[-1]
        self.assertEqual((last.voice, last.build_id), ("Coach Julius", "abc123def456"))


if __name__ == "__main__":
    unittest.main()
