"""Checks for the movement catalog loader, against a small synthetic catalog."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "movements.toml")


class CatalogFormat(unittest.TestCase):
    def test_loads_fixture(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(cat.groups[0], "horizontal push")
        self.assertIn("goblet-squat", cat.movements)

    def test_fixture_is_clean(self):
        self.assertEqual(catalog.problems(catalog.load(FIXTURE)), [])

    def test_problems_name_each_fault(self):
        bad = [{"id": "x", "name": "x", "kind": "strength", "needs": ["anvil"], "position": "standing",
                "sided": False, "measure": "reps", "groups": ["calves"], "tags": ["wobbly"],
                "setup": "Stand up 2 times.", "cues": ["Go."], "easier": ["nope"], "harder": []}]
        msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
        for word in ("anvil", "calves", "wobbly", "nope", "digit"):
            self.assertIn(word, msgs)

    def test_symbol_in_spoken_text(self):
        bad = [{"id": "y", "name": "y", "kind": "strength", "position": "standing", "measure": "reps",
                "setup": "Stand (tall).", "cues": ["Go & go."]}]
        msgs = catalog.problems(catalog.load(FIXTURE, extra=bad))
        self.assertEqual(len([m for m in msgs if "symbol" in m and "y" in m]), 2)

    def test_duplicate_id_or_alias_is_a_problem(self):
        dup = dict(vars(catalog.load(FIXTURE).movements["goblet-squat"]))
        dup.pop("private")
        self.assertTrue(any("goblet-squat" in p for p in catalog.problems(catalog.load(FIXTURE, extra=[dup]))))

    def test_duplicate_alias_across_movements(self):
        dup = [{"id": "z", "name": "Chair Squat", "kind": "strength", "position": "standing",
                "measure": "reps", "setup": "Stand.", "cues": ["Go."]}]
        msgs = catalog.problems(catalog.load(FIXTURE, extra=dup))
        self.assertTrue(any("chair squat" in m.lower() for m in msgs))

    def test_resolve(self):
        cat = catalog.load(FIXTURE)
        for said in ("goblet squat", "Goblet Squat", "kettlebell goblet squat", "left goblet squat"):
            self.assertEqual(catalog.resolve(cat, said).id, "goblet-squat")
        self.assertIsNone(catalog.resolve(cat, "mystery move"))


class RealCatalog(unittest.TestCase):
    def test_real_catalog_has_no_problems(self):
        self.assertEqual(catalog.problems(catalog.load()), [])

    def test_every_kind_of_strength_work_is_there(self):
        cat = catalog.load()
        for g in cat.groups:
            self.assertTrue(any(g in m.groups for m in cat.movements.values()), g)

    def test_names_the_skill_and_tests_rely_on(self):
        cat = catalog.load()
        for said in ("seated bent-over rowing", "lying leg curl", "dead bug", "side plank from the knee",
                     "single-leg glute bridge", "clamshell", "straight-leg raise", "incline push-up",
                     "goblet squat", "farmer carry", "suitcase carry", "pallof press", "hammer curl"):
            self.assertIsNotNone(catalog.resolve(cat, said), said)


if __name__ == "__main__":
    unittest.main()
