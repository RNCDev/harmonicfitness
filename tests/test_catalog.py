"""Checks for the movement catalog loader, against a small synthetic catalog."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "movements.toml")


class CatalogFormat(unittest.TestCase):
    def test_loads_fixture(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(cat.patterns[0], "squat")
        self.assertEqual(cat.movements["goblet-squat"].loads["knee"], 3)
        self.assertEqual(cat.movements["goblet-squat"].loads.get("wrist", 0), 0)
        self.assertTrue(cat.movements["old-style"].draft)
        self.assertFalse(cat.movements["air-squat"].draft)
        self.assertEqual(cat.movements["split-squat"].support, {"knee": 1, "ankle": 1})
        self.assertEqual(cat.movements["old-style"].seconds_per_rep, 0)
        self.assertEqual(cat.movements["old-style"].level, "")

    def test_fixture_is_clean(self):
        self.assertEqual(catalog.problems(catalog.load(FIXTURE)), [])

    def test_non_draft_entry_must_carry_every_field(self):
        bad = [{"id": "x", "name": "x", "position": "standing", "measure": "reps", "patterns": ["squat"],
                "setup": "Stand.", "cues": ["Go."]}]
        msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
        for word in ("loads", "intensity", "level", "seconds_per_rep", "transition_seconds", "muscles"):
            self.assertIn(word, msgs)

    def test_every_entry_needs_patterns(self):
        old = [{"id": "legacy", "name": "legacy", "kind": "strength", "groups": ["quads"], "tags": ["standing"],
                "position": "standing", "measure": "reps", "setup": "Stand.", "cues": ["Go."]}]
        cat = catalog.load(FIXTURE, extra=old)
        self.assertTrue(cat.movements["legacy"].draft)
        self.assertTrue(any("legacy" in p and "patterns" in p for p in catalog.problems(cat)))

    def test_unknown_values_are_named(self):
        bad = [{"id": "y", "name": "y", "draft": True, "patterns": ["wiggle"], "loads": {"tail": 2},
                "flags": ["wobbly"], "level": "wizard", "intensity": "vibes", "position": "standing",
                "measure": "reps", "setup": "Stand.", "cues": ["Go."]}]
        msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
        for word in ("wiggle", "tail", "wobbly", "wizard", "vibes"):
            self.assertIn(word, msgs)

    def test_load_out_of_range_and_support_on_unsided(self):
        bad = [{"id": "z", "name": "z", "draft": True, "patterns": ["squat"], "loads": {"knee": 4},
                "support": {"knee": 1}, "sided": False, "position": "standing", "measure": "reps",
                "setup": "Stand.", "cues": ["Go."]}]
        msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
        self.assertIn("4", msgs)
        self.assertIn("support", msgs)

    def test_resolve_tolerates_a_plural(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(catalog.resolve(cat, "goblet squats").id, "goblet-squat")
        self.assertIsNone(catalog.resolve(cat, "mystery moves"))

    def test_problems_name_each_fault(self):
        bad = [{"id": "x", "name": "x", "needs": ["anvil"], "position": "standing", "sided": False,
                "measure": "reps", "patterns": ["squat"], "draft": True,
                "setup": "Stand up 2 times.", "cues": ["Go."], "easier": ["nope"], "harder": []}]
        msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=bad)))
        for word in ("anvil", "nope", "digit"):
            self.assertIn(word, msgs)

    def test_symbol_in_spoken_text(self):
        bad = [{"id": "y", "name": "y", "draft": True, "patterns": ["squat"], "position": "standing",
                "measure": "reps", "setup": "Stand (tall).", "cues": ["Go & go."]}]
        msgs = catalog.problems(catalog.load(FIXTURE, extra=bad))
        self.assertEqual(len([m for m in msgs if "symbol" in m and "y" in m]), 2)

    def test_duplicate_id_or_alias_is_a_problem(self):
        dup = dict(vars(catalog.load(FIXTURE).movements["goblet-squat"]))
        dup.pop("private")
        self.assertTrue(any("goblet-squat" in p for p in catalog.problems(catalog.load(FIXTURE, extra=[dup]))))

    def test_duplicate_alias_across_movements(self):
        dup = [{"id": "z", "name": "Chair Squat", "draft": True, "patterns": ["squat"], "position": "standing",
                "measure": "reps", "setup": "Stand.", "cues": ["Go."]}]
        msgs = catalog.problems(catalog.load(FIXTURE, extra=dup))
        self.assertTrue(any("chair squat" in m.lower() for m in msgs))

    def test_resolve(self):
        cat = catalog.load(FIXTURE)
        for said in ("goblet squat", "Goblet Squat", "kettlebell goblet squat", "left goblet squat"):
            self.assertEqual(catalog.resolve(cat, said).id, "goblet-squat")
        self.assertIsNone(catalog.resolve(cat, "mystery move"))


class RealCatalog(unittest.TestCase):
    def test_real_catalog_is_clean(self):
        self.assertEqual(catalog.problems(catalog.load()), [])

    def test_real_catalog_has_the_fixed_lists(self):
        cat = catalog.load()
        self.assertEqual(cat.patterns, [
            "squat", "hinge", "lunge", "horizontal-push", "vertical-push", "horizontal-pull", "vertical-pull",
            "carry", "rotation", "anti-rotation", "anti-extension", "locomotion", "balance", "arms", "hips",
            "mobility", "breathing", "skill"])
        self.assertEqual(cat.areas, ["foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "low-back",
                                     "rib", "shoulder", "elbow", "wrist", "neck"])
        self.assertEqual(cat.flags, ["impact", "single-leg", "kneeling", "floor", "lying-side", "hanging",
                                     "overhead", "spine-flexion", "spine-twist", "lateral", "fast", "grip"])
        self.assertEqual(len(cat.muscles), 15)

    def test_every_real_entry_has_patterns(self):
        for m in catalog.load().entries:
            self.assertTrue(m.patterns, m.id)

    def test_names_the_skill_and_tests_rely_on(self):
        cat = catalog.load()
        for said in ("seated bent-over rowing", "lying leg curl", "dead bug", "side plank from the knee",
                     "single-leg glute bridge", "clamshell", "straight-leg raise", "incline push-up",
                     "goblet squat", "farmer carry", "suitcase carry", "pallof press", "hammer curl"):
            self.assertIsNotNone(catalog.resolve(cat, said), said)

    def test_presets(self):
        cat = catalog.load()
        self.assertEqual(set(cat.presets), {"bodyweight", "hotel-room", "hotel-gym", "full-gym"})
        self.assertIsNotNone(catalog.resolve(cat, "box breathing"))
        self.assertIsNotNone(catalog.resolve(cat, "seated ankle alphabet"))


class KnowledgeFiles(unittest.TestCase):
    def test_programming_reference_is_sourced(self):
        text = open(os.path.join(ROOT, "knowledge", "programming.md")).read()
        for heading in ("## Effort", "## Load range", "## Weekly dose", "## Rest and pairing", "## Tempo",
                        "## Progression", "## Warm-up, finisher and cool-down", "## One-sided training",
                        "## Session templates"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("Source: https://"), 8)


if __name__ == "__main__":
    unittest.main()
