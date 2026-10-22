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

    def _problems_after(self, change):
        """The problems of the real file after `change(s)` alters it."""
        s = sessions.load()
        change(s)
        return sessions.problems(s, self.cat)

    def assertNamed(self, change, *words):
        msgs = self._problems_after(change)
        self.assertTrue(any(all(w in msg for w in words) for msg in msgs), f"no message with {words}: {msgs}")

    def test_problems_name_each_bad_value(self):
        circuit = lambda s: s.methods["circuit"]  # noqa: E731
        self.assertNamed(lambda s: setattr(circuit(s), "goals", ["vibes"]), "circuit", "goal", "vibes")
        self.assertNamed(lambda s: setattr(circuit(s), "levels", ["wizard"]), "circuit", "level", "wizard")
        self.assertNamed(lambda s: setattr(circuit(s), "work", "juggling"), "circuit", "work", "juggling")
        self.assertNamed(lambda s: setattr(circuit(s), "min_slots", 0), "circuit", "min_slots")
        self.assertNamed(lambda s: setattr(circuit(s), "needs", ["hovercraft"]), "circuit", "hovercraft")
        self.assertNamed(lambda s: setattr(circuit(s), "about", "Do it 3 times."), "circuit", "about", "digit")
        self.assertNamed(lambda s: setattr(circuit(s), "minutes", [40, 10]), "circuit", "minutes", "inverted")
        self.assertNamed(lambda s: circuit(s).blocks[0].update(intensity="chaos"), "circuit", "intensity", "chaos")
        self.assertNamed(lambda s: circuit(s).blocks[0].update(patterns=["wiggle"]), "circuit", "pattern", "wiggle")
        self.assertNamed(lambda s: circuit(s).blocks[0].update(share=0.5), "circuit", "sum")
        self.assertNamed(lambda s: s.dose["mobility"].pop("advanced"), "mobility", "advanced")

    def test_problems_name_a_block_with_no_dose_table(self):
        self.assertNamed(lambda s: s.methods["flow"].blocks[0].update(intensity="breathing"),
                         "flow", "breathing", "dose")


if __name__ == "__main__":
    unittest.main()
