"""Checks for the session methods and dose rules (knowledge/sessions.toml, read through
tools/sessions.py), which the brief's programming guide draws on."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import sessions  # noqa: E402


class Methods(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = sessions.load()
        cls.cat = catalog.load()

    def test_real_file_is_clean(self):
        self.assertEqual(sessions.problems(self.s, self.cat), [])

    def test_choose_rotates_away_from_last_format(self):
        pick = choose(self.s, "strength", 30, "experienced", "straight-sets", set())
        self.assertEqual(pick.name, "paired-sets")
        pick = choose(self.s, "strength", 30, "experienced", "paired-sets", set())
        self.assertEqual(pick.name, "straight-sets")
        pick = choose(self.s, "strength", 30, "experienced", None, set())
        self.assertEqual(pick.name, "straight-sets")

    def test_choose_prefers_goal_fit_over_file_order(self):
        self.assertEqual(self.s.methods["circuit"].goals[-1], "conditioning")
        pick = lambda level, last: choose(self.s, "conditioning", 30, level, last, set()).name  # noqa: E731
        self.assertEqual(pick("novice", None), "intervals")
        self.assertEqual(pick("novice", "circuit"), "intervals")
        self.assertEqual(pick("novice", "intervals"), "circuit")     # circuit only after intervals was last
        self.assertEqual(pick("experienced", "intervals"), "tabata")   # a better-fitting method comes first
        self.assertEqual([m.name for m in sessions.ranked(self.s, "general", 30, "novice", set())][0], "circuit")

    def test_choose_respects_minutes_and_needs(self):
        pick = choose(self.s, "strength", 15, "experienced", None, set())
        self.assertIsNotNone(pick)
        self.assertNotEqual(pick.name, "straight-sets")
        no_bike = [m.name for m in sessions.fitting(self.s, "conditioning", 40, "experienced", {"dumbbells"})]
        self.assertNotIn("bike-intervals", no_bike)
        for need in ("bike", "air-bike"):
            names = [m.name for m in sessions.fitting(self.s, "conditioning", 40, "experienced", {need})]
            self.assertIn("bike-intervals", names)

    def test_choose_returns_none_when_nothing_fits(self):
        self.assertIsNone(choose(self.s, "conditioning", 5, "experienced", None, {"bike"}))

    def test_choose_falls_back_when_only_last_format_fits(self):
        fits = sessions.fitting(self.s, "mobility", 30, "novice", set())
        self.assertEqual([m.name for m in fits], ["flow"])
        self.assertEqual(choose(self.s, "mobility", 30, "novice", "flow", set()).name, "flow")

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
        self.assertNamed(lambda s: setattr(circuit(s), "needs", ["hovercraft"]), "circuit", "hovercraft")
        self.assertNamed(lambda s: setattr(circuit(s), "about", "Do it 3 times."), "circuit", "about", "digit")
        self.assertNamed(lambda s: setattr(circuit(s), "minutes", [40, 10]), "circuit", "minutes", "inverted")
        self.assertNamed(lambda s: s.dose["mobility"].pop("advanced"), "mobility", "advanced")

    def test_problems_name_a_bad_all_out_rule(self):
        self.assertEqual(self.s.all_out, {"most_seconds": 20, "rest_ratio": 4})
        self.assertNamed(lambda s: s.all_out.update(rest_ratio=0), "all_out", "rest_ratio")
        self.assertNamed(lambda s: s.all_out.pop("most_seconds"), "all_out", "most_seconds")



def choose(s, goal, minutes, level, last, equipment):
    """The best-ranked fitting method, or None."""
    fits = sessions.ranked(s, goal, minutes, level, equipment, last)
    return fits[0] if fits else None


if __name__ == "__main__":
    unittest.main()
