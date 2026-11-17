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

    def test_choose(self):
        """Each row: (goal, minutes, level, last format, equipment, the method chosen or None)."""
        rows = (("strength", 30, "experienced", "straight-sets", set(), "paired-sets"),   # rotates away from the last
                ("strength", 30, "experienced", "paired-sets", set(), "straight-sets"),
                ("strength", 30, "experienced", None, set(), "straight-sets"),
                ("conditioning", 30, "novice", None, set(), "intervals"),   # goal fit over file order
                ("conditioning", 30, "novice", "intervals", set(), "circuit"),
                ("conditioning", 30, "experienced", "intervals", set(), "tabata"),
                ("general", 30, "novice", None, set(), "timed-sets"),
                ("conditioning", 5, "experienced", None, {"bike"}, None),   # nothing fits
                ("mobility", 30, "novice", "flow", set(), "flow"))           # only the last fits: it again
        for goal, minutes, level, last, kit, want in rows:
            with self.subTest(goal=goal, level=level, last=last):
                pick = choose(self.s, goal, minutes, level, last, kit)
                self.assertEqual(pick and pick.name, want)
        self.assertNotEqual(choose(self.s, "strength", 15, "experienced", None, set()).name, "straight-sets")
        self.assertNotIn("bike-intervals",
                         [m.name for m in sessions.fitting(self.s, "conditioning", 40, "experienced", {"dumbbells"})])
        for need in ("bike", "air-bike"):
            self.assertIn("bike-intervals", [m.name for m in sessions.fitting(self.s, "conditioning", 40, "experienced",
                                                                              {need})])

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
        self.assertNamed(lambda s: setattr(s, "rep_pace", 0), "timing", "rep_pace")
        self.assertNamed(lambda s: setattr(s, "rep_pace", "fast"), "timing", "rep_pace")


def choose(s, goal, minutes, level, last, equipment):
    """The best-ranked fitting method, or None."""
    fits = sessions.ranked(s, goal, minutes, level, equipment, last)
    return fits[0] if fits else None


if __name__ == "__main__":
    unittest.main()
