"""Checks for the movement catalog loader, against a small synthetic catalog."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "movements.toml")


def run_movements(args):
    """Run `./sweatcast movements ...` against the real catalog; returns the CompletedProcess."""
    env = dict(os.environ, SWEATCAST_PYTHON=sys.executable)
    return subprocess.run(["sh", os.path.join(ROOT, "sweatcast"), "movements", *args],
                          capture_output=True, text=True, env=env, cwd=ROOT)


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

    def test_every_preset_covers_the_core_patterns_at_every_level(self):
        cat = catalog.load()
        core = ["squat", "hinge", "lunge", "horizontal-push", "horizontal-pull", "anti-extension",
                "anti-rotation", "locomotion", "mobility", "breathing"]
        extra = {"hotel-gym": ["vertical-push", "carry"], "full-gym": ["vertical-push", "vertical-pull", "carry"]}
        for preset, equipment in cat.presets.items():
            want = core + extra.get(preset, [])
            for pattern in want:
                for level in catalog.LEVELS:
                    ok = [m for m in cat.movements.values() if not m.draft and m.patterns[0] == pattern
                          and catalog.LEVELS.index(m.level) <= catalog.LEVELS.index(level)
                          and all(any(alt in equipment for alt in need.split("|")) for need in m.needs)]
                    self.assertTrue(ok, f"{preset} has no {pattern} at {level}")

    def test_at_least_sixty_entries_are_annotated(self):
        cat = catalog.load()
        self.assertGreaterEqual(sum(not m.draft for m in cat.movements.values()), 60)


class Select(unittest.TestCase):
    def test_level_and_draft_and_equipment(self):
        cat = catalog.load(FIXTURE)
        sel = catalog.select(cat, {"dumbbells"}, "novice", [])
        ids = {m.id for m in sel.allowed}
        self.assertIn("goblet-squat", ids)
        self.assertEqual(sel.left_out["old-style"], ["draft"])
        self.assertEqual(sel.left_out["bike-easy-spin"], ["equipment"])
        sel = catalog.select(cat, {"dumbbells"}, "novice", [], dislikes={"goblet-squat"})
        self.assertEqual(sel.left_out["goblet-squat"], ["disliked"])

    def test_off_limits_excludes_any_load_and_delicate_moderate(self):
        cat = catalog.load(FIXTURE)
        off = [catalog.Limit("knee", "both", "off-limits", [], [], "")]
        self.assertIn("glute-bridge", catalog.select(cat, {"mat"}, "novice", off).left_out)   # knee = 1
        soft = [catalog.Limit("knee", "both", "delicate", [], [], "")]
        sel = catalog.select(cat, {"mat"}, "novice", soft)
        self.assertIn("glute-bridge", {m.id for m in sel.allowed})
        self.assertEqual(sel.left_out["air-squat"], ["knee delicate"])

    def test_sided_limit_on_unsided_movement_excludes(self):
        cat = catalog.load(FIXTURE)
        left = [catalog.Limit("knee", "left", "delicate", [], [], "")]
        sel = catalog.select(cat, {"dumbbells", "mat"}, "novice", left)
        self.assertIn("air-squat", sel.left_out)
        self.assertIn("split-squat", {m.id for m in sel.healthy_side_only})   # support knee = 1 < 2
        self.assertNotIn("split-squat", {m.id for m in sel.allowed})
        self.assertNotIn("split-squat", sel.left_out)

    def test_sided_limit_checks_the_support_side(self):
        cat = catalog.load(FIXTURE)
        left = [catalog.Limit("knee", "left", "off-limits", [], [], "")]
        sel = catalog.select(cat, {"dumbbells", "mat"}, "novice", left)
        self.assertIn("split-squat", sel.left_out)   # support knee = 1 >= 1

    def test_limit_flags_and_rehab(self):
        cat = catalog.load(FIXTURE)
        lim = [catalog.Limit("wrist", "both", "delicate", ["floor"], ["old-style"], "")]
        sel = catalog.select(cat, {"mat"}, "novice", lim)
        self.assertIn("floor", sel.left_out["glute-bridge"])
        self.assertEqual(sel.left_out["old-style"], ["draft"])   # rehab bypasses limits, never draft

    def test_limits_on_both_sides_leave_no_healthy_side(self):
        cat = catalog.load(FIXTURE)
        both = [catalog.Limit("knee", "left", "delicate", [], [], ""),
                catalog.Limit("knee", "right", "delicate", [], [], "")]
        sel = catalog.select(cat, set(), "novice", both)
        self.assertEqual(sel.left_out["split-squat"], ["knee delicate"])
        self.assertNotIn("split-squat", {m.id for m in sel.healthy_side_only})
        mixed = [catalog.Limit("knee", "left", "delicate", [], [], ""),
                 catalog.Limit("ankle", "right", "off-limits", [], [], "")]
        cat.movements["split-squat"].loads["ankle"] = 2
        cat.movements["split-squat"].support["ankle"] = 0
        sel = catalog.select(cat, set(), "novice", mixed)
        self.assertEqual(sel.left_out["split-squat"], ["knee delicate", "ankle off limits"])

    def test_delicate_boundary_is_exactly_two(self):
        cat = catalog.load(FIXTURE)
        lim = [catalog.Limit("wrist", "both", "delicate", [], [], "")]   # push-up wrist = 2
        self.assertEqual(catalog.select(cat, set(), "novice", lim).left_out["push-up"], ["wrist delicate"])

    def test_sided_limit_below_threshold_allows_sided_movement(self):
        cat = catalog.load(FIXTURE)
        lim = [catalog.Limit("low-back", "left", "delicate", [], [], "")]   # one-arm-row support 1, load 0
        sel = catalog.select(cat, {"dumbbells"}, "novice", lim)
        self.assertIn("one-arm-row", {m.id for m in sel.allowed})

    def test_unknown_limit_values_raise(self):
        cat = catalog.load(FIXTURE)
        for lim in (catalog.Limit("knee", "both", "soft", [], [], ""), catalog.Limit("knee", "up", "delicate", [], [], "")):
            with self.assertRaises(ValueError):
                catalog.select(cat, set(), "novice", [lim])

    def test_reasons_accumulate_and_threshold(self):
        cat = catalog.load(FIXTURE)
        lim = [catalog.Limit("knee", "both", "delicate", [], [], "")]
        sel = catalog.select(cat, {"dumbbells"}, "novice", lim, dislikes={"goblet-squat"}, avoid={"goblet-squat"})
        self.assertEqual(sel.left_out["goblet-squat"], ["disliked", "avoided", "knee delicate"])
        self.assertEqual(catalog.threshold(lim[0]), 2)
        self.assertEqual(catalog.threshold(catalog.Limit("knee", "both", "off-limits", [], [], "")), 1)

    def test_delicate_excludes_impact_and_fast(self):
        cat = catalog.load(FIXTURE)
        cat.movements["air-squat"].flags = ["impact"]
        cat.movements["push-up"].flags = ["fast"]
        lim = [catalog.Limit("neck", "both", "delicate", [], [], "")]
        sel = catalog.select(cat, set(), "novice", lim)
        self.assertEqual(sel.left_out["air-squat"], ["impact"])
        self.assertEqual(sel.left_out["push-up"], ["fast"])

    def test_level_rehab_and_unrehabbed_rehab_entry(self):
        cat = catalog.load(FIXTURE)
        cat.movements["air-squat"].level = "advanced"
        cat.movements["push-up"].rehab = True
        sel = catalog.select(cat, set(), "experienced", [])
        self.assertEqual(sel.left_out["air-squat"], ["level"])
        self.assertEqual(sel.left_out["push-up"], ["rehab"])
        lim = [catalog.Limit("wrist", "both", "off-limits", [], ["push-up"], "")]
        sel = catalog.select(cat, set(), "experienced", lim)
        self.assertIn("push-up", {m.id for m in sel.allowed})   # named by the limit's rehab list


class Filter(unittest.TestCase):
    def test_pattern_keeps_healthy_side_block(self):
        import movements
        cat = catalog.load(FIXTURE)
        sel = catalog.select(cat, set(), "novice", [catalog.Limit("knee", "left", "delicate", [], [], "")])
        out = movements.render(cat, sel, "lunge")
        self.assertIn("Healthy side only", out)
        self.assertNotIn("Healthy side only", movements.render(cat, sel, "squat"))

    def test_preset_prints_by_pattern(self):
        r = run_movements(["--preset", "full-gym"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines()[0], "squat")
        self.assertRegex(r.stdout.splitlines()[-1], r"^Left out today: \d+")

    def test_avoid_flag_and_id(self):
        base = run_movements(["--preset", "full-gym"]).stdout
        self.assertIn("  goblet squat", base)
        self.assertNotIn("  goblet squat", run_movements(["--preset", "full-gym", "--avoid", "goblet-squat"]).stdout)
        flagged = run_movements(["--preset", "full-gym", "--avoid", "impact"])
        self.assertEqual(flagged.returncode, 0)
        self.assertIn("avoided", flagged.stdout.splitlines()[-1])

    def test_pattern_and_level(self):
        only = run_movements(["--preset", "full-gym", "--pattern", "hinge", "--level", "advanced"])
        self.assertEqual(only.returncode, 0, only.stderr)
        self.assertNotIn("\nsquat\n", "\n" + only.stdout)
        self.assertIn("hinge", only.stdout)

    def test_unknown_equipment_is_usage(self):
        for args in (["--equipment", "anvil"], ["--preset", "castle"], ["--preset", "full-gym", "--avoid", "wobbly"],
                     ["--preset", "full-gym", "--level", "godlike"], ["--preset", "full-gym", "--pattern", "calves"]):
            r = run_movements(args)
            self.assertEqual(r.returncode, 64, args)
            self.assertTrue(r.stderr.strip(), args)

    def test_equipment_alias_is_accepted(self):
        self.assertEqual(run_movements(["--equipment", "yoga mat"]).returncode, 0)


class KnowledgeFiles(unittest.TestCase):
    def test_programming_reference_is_sourced(self):
        with open(os.path.join(ROOT, "knowledge", "programming.md")) as f:
            text = f.read()
        for heading in ("## Effort", "## Load range", "## Weekly dose", "## Rest and pairing", "## Tempo",
                        "## Progression", "## Warm-up, finisher and cool-down", "## One-sided training",
                        "## Session templates"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("Source: https://"), 8)


if __name__ == "__main__":
    unittest.main()
