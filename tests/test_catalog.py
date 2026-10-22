"""Checks for the movement catalog loader, against a small synthetic catalog."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "movements.toml")
PHASES = ("protect", "restore", "rebuild", "return")


def run_movements(args, home=None):
    """Run `./sweatcast movements ...` against the real catalog; returns the CompletedProcess."""
    env = dict(os.environ)
    if home:
        env["SWEATCAST_HOME"] = home
    return subprocess.run([os.path.join(ROOT, "sweatcast"), "movements", *args],
                          capture_output=True, text=True, env=env, cwd=ROOT)


class CatalogFormat(unittest.TestCase):
    def test_loads_fixture(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(cat.groups[0], "horizontal push")
        self.assertIn("goblet-squat", cat.movements)

    def test_resolve_tolerates_a_plural(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(catalog.resolve(cat, "goblet squats").id, "goblet-squat")
        self.assertIsNone(catalog.resolve(cat, "mystery moves"))

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

    def test_non_strength_kinds_and_presets(self):
        cat = catalog.load()
        kinds = {m.kind for m in cat.movements.values()}
        self.assertTrue({"cardio", "mobility", "breathing", "skill", "rehab", "finisher"} <= kinds)
        self.assertEqual(set(cat.presets), {"bodyweight", "hotel-room", "hotel-gym", "full-gym"})
        self.assertIsNotNone(catalog.resolve(cat, "box breathing"))
        self.assertIsNotNone(catalog.resolve(cat, "seated ankle alphabet"))


class Filter(unittest.TestCase):
    def setUp(self):
        self.cat = catalog.load(FIXTURE)

    def test_equipment_and_tags_narrow(self):
        sel = catalog.select(self.cat, {"dumbbells"}, {"knee-deep-bend"})
        ids = {m.id for m in sel.allowed}
        self.assertNotIn("goblet-squat", ids)
        self.assertIn("knee-deep-bend", sel.left_out["goblet-squat"])

    def test_needs_alternatives(self):
        self.assertIn("goblet-squat", {m.id for m in catalog.select(self.cat, {"kettlebell"}, set()).allowed})

    def test_every_reason_is_listed(self):
        sel = catalog.select(self.cat, set(), {"knee-deep-bend"}, ban_ids={"goblet-squat"})
        self.assertEqual(sorted(sel.left_out["goblet-squat"]), ["banned", "equipment", "knee-deep-bend"])

    def test_injured_side_only_affects_sided_movements(self):
        sel = catalog.select(self.cat, set(), set(), avoid_injured_side={"single-leg-stance"})
        self.assertIn("single-leg-balance", {m.id for m in sel.healthy_side_only})
        self.assertNotIn("single-leg-balance", {m.id for m in sel.allowed})
        self.assertNotIn("single-leg-balance", sel.left_out)

    def test_injured_side_tag_on_a_non_sided_movement_leaves_it_out(self):
        sel = catalog.select(self.cat, {"dumbbells"}, set(), avoid_injured_side={"knee-deep-bend"})
        self.assertEqual(sel.left_out["goblet-squat"], ["knee-deep-bend"])

    def test_kit_equipment(self):
        self.assertEqual(catalog.kit_equipment(self.cat, {"preset": "full-gym"}),
                         set(self.cat.presets["full-gym"]))
        self.assertEqual(catalog.kit_equipment(self.cat, {"equipment": ["band"]}), {"band"})
        self.assertEqual(catalog.kit_equipment(self.cat, {"preset": "bodyweight", "equipment": ["band"]}), {"band"})
        with self.assertRaises(ValueError):
            catalog.kit_equipment(self.cat, {"preset": "castle"})

    def test_unknown_tag_or_preset_exits_64(self):
        for args in (["--preset", "castle"], ["--equipment", "dumbbells", "--avoid", "wobbly"],
                     ["--equipment", "anvil"], ["--preset", "full-gym", "--group", "calves"]):
            r = run_movements(args)
            self.assertEqual(r.returncode, 64, args)
            self.assertTrue(r.stderr.strip(), args)

    def test_equipment_alias_is_accepted(self):
        self.assertEqual(run_movements(["--equipment", "yoga mat"]).returncode, 0)

    def test_output_is_grouped_in_checklist_order(self):
        out = run_movements(["--preset", "full-gym"]).stdout
        self.assertLess(out.index("horizontal push"), out.index("arms"))

    def test_output_layout(self):
        out = run_movements(["--preset", "hotel-room", "--avoid", "impact"]).stdout
        self.assertRegex(out.splitlines()[-1], r"^Left out today: \d+ \(")
        self.assertIn("(see ", out)
        self.assertIn("Cues: ", out)
        self.assertIn("\nbreathing\n", out)
        only = run_movements(["--preset", "full-gym", "--group", "quads"]).stdout
        self.assertNotIn("\nhorizontal push\n", "\n" + only)   # a "(see horizontal push)" pointer is fine
        self.assertIn("quads", only)

    def test_full_line_sits_under_the_movements_own_first_group(self):
        out = run_movements(["--preset", "full-gym"]).stdout.splitlines()
        quads = out[out.index("quads") + 1:]
        quads = quads[:next(i for i, l in enumerate(quads) if not l.startswith("  "))]
        self.assertTrue(any(l.startswith("  goblet squat (standing)") for l in quads))
        hinge = out[out.index("hip hinge or glutes") + 1:]
        self.assertIn("  goblet squat (see quads)", hinge[:next(i for i, l in enumerate(hinge) if not l.startswith("  "))])


class KnowledgeFiles(unittest.TestCase):
    def test_programming_reference_is_sourced(self):
        text = open(os.path.join(ROOT, "knowledge", "programming.md")).read()
        for heading in ("## Effort", "## Load range", "## Weekly dose", "## Rest and pairing", "## Tempo",
                        "## Progression", "## Warm-up, finisher and cool-down", "## One-sided training",
                        "## Session templates"):
            self.assertIn(heading, text)
        self.assertGreaterEqual(text.count("Source: https://"), 8)


class InjuryRules(unittest.TestCase):
    def test_rules_have_no_problems(self):
        playbook = open(os.path.join(ROOT, "knowledge", "injury-playbook.md")).read()
        self.assertEqual(catalog.rule_problems(catalog.load_rules(), catalog.load(), playbook), [])

    def test_later_phases_never_ban_more(self):
        for area, r in catalog.load_rules().items():
            for a, b in zip(PHASES, PHASES[1:]):
                self.assertLessEqual(set(r[b]["ban"]), set(r[a]["ban"]), f"{area} {b}")

    def test_later_phases_never_leave_out_more_movements(self):
        cat = catalog.load()
        everything = set(cat.equipment)

        def left_out(r):
            avoid = set(r["ban"]) | set(r["ban_injured_side"])
            return set(catalog.select(cat, everything, avoid, ban_ids=set(r["ban_ids"])).left_out)
        for area, r in catalog.load_rules().items():
            for a, b in zip(PHASES, PHASES[1:]):
                self.assertEqual(left_out(r[b]) - left_out(r[a]), set(), f"{area} {b}")

    def test_every_phase_but_return_says_when_to_move_on(self):
        for area, r in catalog.load_rules().items():
            for p in PHASES[:-1]:
                self.assertTrue(r[p]["advance_when"], f"{area} {p}")
                self.assertTrue(r[p]["sources"], f"{area} {p}")

    def test_rule_problems_name_each_fault(self):
        cat = catalog.load(FIXTURE)
        phase = {"ban": [], "ban_injured_side": [], "ban_ids": [], "caution": {}, "include": [],
                 "advance_when": [], "sources": []}
        rules = {"knee": {"playbook": "Knee", "protect": dict(phase, ban=["wobbly"]),
                          "restore": dict(phase, include=["goblet-squat"], ban_ids=["goblet-squat"],
                                          caution={"goblet-squat": "Light; slow."}),
                          "rebuild": dict(phase)}}
        out = catalog.rule_problems(rules, cat, "# Playbook\n\n## Ankle\n")
        self.assertTrue(any("wobbly" in p for p in out), out)
        self.assertTrue(any("return" in p for p in out), out)
        self.assertTrue(any("Knee" in p and "heading" in p for p in out), out)
        self.assertTrue(any("goblet-squat" in p and "include" in p for p in out), out)
        self.assertTrue(any("caution" in p and "symbol" in p for p in out), out)
        self.assertEqual(catalog.rule_problems({"knee": dict(rules["knee"], **{
            "protect": dict(phase), "restore": dict(phase), "return": dict(phase)})},
            cat, "## Knee\n"), [])


if __name__ == "__main__":
    unittest.main()
