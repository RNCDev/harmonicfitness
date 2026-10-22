"""Checks for the session methods and dose rules (knowledge/sessions.toml)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402
import sessions  # noqa: E402


class Methods(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = sessions.load()
        cls.cat = catalog.load()

    def test_real_file_is_clean(self):
        self.assertEqual(sessions.problems(self.s, self.cat), [])

    def test_choose_rotates_away_from_last_format(self):
        pick = sessions.choose_method(self.s, "strength", 30, "experienced", "straight-sets", set())
        self.assertEqual(pick.name, "paired-sets")
        pick = sessions.choose_method(self.s, "strength", 30, "experienced", "paired-sets", set())
        self.assertEqual(pick.name, "straight-sets")
        pick = sessions.choose_method(self.s, "strength", 30, "experienced", None, set())
        self.assertEqual(pick.name, "straight-sets")

    def test_choose_respects_minutes_and_needs(self):
        pick = sessions.choose_method(self.s, "strength", 15, "experienced", None, set())
        self.assertIsNotNone(pick)
        self.assertNotEqual(pick.name, "straight-sets")
        no_bike = [m.name for m in sessions.fitting(self.s, "conditioning", 40, "experienced", {"dumbbells"})]
        self.assertNotIn("bike-intervals", no_bike)
        for need in ("bike", "air-bike"):
            names = [m.name for m in sessions.fitting(self.s, "conditioning", 40, "experienced", {need})]
            self.assertIn("bike-intervals", names)

    def test_choose_returns_none_when_nothing_fits(self):
        self.assertIsNone(sessions.choose_method(self.s, "conditioning", 5, "experienced", None, {"bike"}))

    def test_choose_falls_back_when_only_last_format_fits(self):
        fits = sessions.fitting(self.s, "mobility", 30, "novice", set())
        self.assertEqual([m.name for m in fits], ["flow"])
        self.assertEqual(sessions.choose_method(self.s, "mobility", 30, "novice", "flow", set()).name, "flow")

    def test_dose_has_every_level(self):
        for intensity, keys in (("strength", ("sets", "reps", "rest_seconds", "hard_sets_per_session")),
                                ("conditioning", ("work_seconds", "rest_seconds", "rounds")),
                                ("mobility", ("hold_seconds", "rounds")),
                                ("skill", ("drill_seconds", "rounds"))):
            for level in catalog.LEVELS:
                d = sessions.dose(self.s, intensity, level)
                for key in keys:
                    least, most = d[key]
                    self.assertLessEqual(least, most, f"{intensity} {level} {key}")

    def test_methods_in_file_order(self):
        self.assertEqual(list(self.s.methods), ["straight-sets", "paired-sets", "circuit", "intervals", "tabata",
                                                "bike-intervals", "flow", "skill"])
        self.assertEqual(self.s.methods["tabata"].fixed, {"work_seconds": 20, "rest_seconds": 10, "rounds": 8})
        self.assertEqual(self.s.methods["bike-intervals"].needs, ["bike|air-bike"])
        self.assertIsNone(self.s.methods["circuit"].finisher)

    def test_problems_name_bad_values(self):
        s = sessions.load()
        m = s.methods["circuit"]
        m.goals = ["vibes"]
        m.levels = ["wizard"]
        m.work = "juggling"
        m.min_slots = 0
        m.needs = ["hovercraft"]
        m.about = "Do it 3 times."
        m.minutes = [40, 10]
        m.blocks = [{"intensity": "chaos", "patterns": ["wiggle"], "share": 0.5}]
        del s.dose["mobility"]["advanced"]
        msgs = " ".join(sessions.problems(s, self.cat))
        for word in ("vibes", "wizard", "juggling", "min_slots", "hovercraft", "digit", "minutes", "chaos",
                     "wiggle", "sum", "advanced"):
            self.assertIn(word, msgs)


if __name__ == "__main__":
    unittest.main()
