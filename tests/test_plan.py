"""Checks for the plan a draft holds (draft.summary, `get plan`): worked out from the draft's own segments, so
its times always add up to the draft's, which a plan table written by hand didn't (a 600 s workout's table
added to 500 s). Each movement's sets in the order it comes, then the rests, then the talk."""
import contextlib
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
import draft  # noqa: E402
import errors  # noqa: E402
import helpers  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTENER = os.path.join(ROOT, "tests", "fixtures", "listener")
TEXT = """movements: arm circles, air squat, push-up, box breathing
@@ 60 | Welcome and rules
Welcome.
@@ 60 | Warm-up: arm circles
Circles.
@@ 20 | Transition to circuit
Up you get.
@@ 50 | Air squat set 1, 10 reps
Squats.
@@ 30 | Rest
Breathe.
@@ 50 | Push-ups set 1, 10 reps
Push-ups.
@@ 30 | Rest
Breathe.
@@ 50 | Air squats set 2
Squats.
@@ 60 | Cool-down: box breathing
Breathe.
"""


class Plan(unittest.TestCase):
    def test_rows_come_from_the_segments_and_add_up(self):
        names = [("Arm circles", ["arm circles"]), ("Air squat", ["air squat"]), ("Push-up", ["push-up"]),
                 ("Box breathing", ["box breathing"])]
        plan = draft.summary(TEXT, names)
        rows = [(r["what"], r["kind"], r["segments"], r["seconds"]) for r in plan["rows"]]
        self.assertEqual(rows, [("Arm circles", "movement", 1, 60), ("Air squat", "movement", 2, 100),
                                ("Push-up", "movement", 1, 50), ("Box breathing", "movement", 1, 60),
                                ("Rests", "rest", 2, 60), (draft.TALK, "talk", 2, 80)])
        self.assertEqual(plan["seconds"], 410)
        self.assertEqual(sum(r["seconds"] for r in plan["rows"]), plan["seconds"])
        table = draft.summary_lines(plan)
        self.assertIn("| Air squat | 2 | 1:40 |", table)
        self.assertEqual(table[-1], "| **Total** | | **6:50** |")

    def test_get_plan_names_movements_by_the_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.join(tmp, "me")
            shutil.copytree(LISTENER, home)
            path = os.path.join(home, "workouts", "x.draft.txt")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(TEXT.replace("movements: arm circles", "movements: arm-circles"))
            out = io.StringIO()
            with helpers.home(home), contextlib.redirect_stdout(out):
                self.assertEqual(context.main(["get", "plan", "--draft", path, "--json"]), cli.OK)
            plan = json.loads(out.getvalue())
            self.assertEqual(plan["rows"][0]["what"], "Arm circles")   # the id declared, the catalog's name shown
            self.assertEqual(plan["seconds"], 410)
            with helpers.home(home), self.assertRaises(errors.UsageError):
                context.main(["get", "plan"])


if __name__ == "__main__":
    unittest.main()
