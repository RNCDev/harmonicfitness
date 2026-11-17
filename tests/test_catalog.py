"""Checks for the movement catalog loader, against a small synthetic catalog and the real one."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402
import check  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "movements.toml")


def lim(area, side="both", level="delicate", flags=(), rehab=()):
    return catalog.Limit(area, side, level, list(flags), list(rehab), "")


def entry(**kw):
    """A draft catalog entry with the fields every entry needs, then `kw`."""
    return {"id": "y", "name": "y", "draft": True, "patterns": ["squat"], "position": "standing",
            "measure": "reps", "setup": "Stand.", "cues": ["Go."], **kw}


class CatalogFormat(unittest.TestCase):
    def test_loads_and_resolves_the_fixture(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(catalog.problems(cat), [])
        self.assertEqual(cat.patterns[0], "squat")
        self.assertEqual(cat.movements["goblet-squat"].loads["knee"], 3)
        self.assertTrue(cat.movements["old-style"].draft)
        self.assertEqual(cat.movements["split-squat"].support, {"knee": 1, "ankle": 1})
        for said in ("goblet squat", "Goblet Squat", "kettlebell goblet squat", "left goblet squats"):
            self.assertEqual(catalog.resolve(cat, said).id, "goblet-squat")
        self.assertIsNone(catalog.resolve(cat, "mystery moves"))

    def test_problems_name_each_fault(self):
        dup = dict(vars(catalog.load(FIXTURE).movements["goblet-squat"]))
        dup.pop("private")
        rows = (
            (entry(id="x", name="x", draft=False), ("loads", "intensity", "level", "seconds_per_rep",
                                                    "transition_seconds", "muscles")),
            ({k: v for k, v in entry(id="legacy", name="legacy").items() if k != "patterns"}, ("legacy", "patterns")),
            (entry(patterns=["wiggle"], loads={"tail": 2}, flags=["wobbly"], level="wizard", intensity="vibes"),
             ("wiggle", "tail", "wobbly", "wizard", "vibes")),
            (entry(loads={"knee": 4}, support={"knee": 1}, sided=False), ("4", "support")),
            (entry(needs=["anvil"], setup="Stand up 2 times.", easier=["nope"]), ("anvil", "nope", "digit")),
            (entry(setup="Stand (tall).", cues=["Go & go."]), ("symbol",)),
            (entry(rep="One rep: down and up.", feel="Thighs (front)."), ("symbol",)),
            (dup, ("goblet-squat",)),
            (entry(id="z", name="Chair Squat"), ("chair squat",)),
        )
        for bad, words in rows:
            with self.subTest(words=words):
                msgs = " ".join(catalog.problems(catalog.load(FIXTURE, extra=[bad]))).lower()
                for word in words:
                    self.assertIn(word, msgs)
        for cues, words in (({"tail": {"delicate": ["Wag."]}}, ("unknown area", "tail")),
                            ({"knee": {"sore": ["Easy."]}}, ("unknown level", "sore")),
                            ({"knee": {"delicate": ["A.", "B.", "C.", "D."]}}, ("knee delicate", "one to")),
                            ({"knee": {"delicate": ["Bend 2 times."]}}, ("knee delicate", "digit")),
                            ({"knee": ["Easy."]}, ("knee", "not a table"))):
            with self.subTest(cues=cues):
                cat = catalog.load(FIXTURE)
                cat.limit_cues = cues
                msgs = catalog.problems(cat)
                self.assertTrue(any(all(w in m for w in words) for m in msgs), (cues, msgs))

    def test_limit_cues_fill_in_the_side(self):
        cat = catalog.load(FIXTURE)
        self.assertEqual(catalog.limit_cues(cat, lim("wrist", "left"))[0],
                         "Keep the left wrist straight, in line with the forearm.")
        self.assertEqual(catalog.limit_cues(cat, lim("wrist"))[0], "Keep the sore wrist straight, in line with the forearm.")
        self.assertEqual(catalog.limit_cues(cat, lim("wrist", level="off-limits")), ["No weight through the injured hand."])
        self.assertEqual(catalog.limit_cues(cat, lim("neck")), [])


class RealCatalog(unittest.TestCase):
    def test_real_catalog_is_clean(self):
        self.assertEqual(catalog.problems(catalog.load()), [])

    def test_limits_filter_the_real_catalog(self):
        """Each row: a limit, the kit, the movements it must leave out and those it must keep."""
        cat = catalog.load()
        everything = set(cat.equipment)
        ankle_kit = {"dumbbells", "kettlebell", "bench", "bike"}
        rows = (
            (lim("low-back", level="off-limits"), {"mat"}, ("childs-pose", "thread-the-needle"), ()),
            (lim("low-back"), {"mat"}, (), ("childs-pose",)),
            (lim("ankle", "left", "off-limits"), ankle_kit,
             ("wall-sit", "romanian-deadlift", "goblet-squat", "bike-easy-spin", "bike-steady"), ("dead-bug",)),
            (lim("ankle", "left"), ankle_kit, (), ("bike-easy-spin",)),
            (lim("neck"), everything, ("overhead-press", "seated-shoulder-press", "half-kneeling-kettlebell-press",
                                       "pike-push-up"), ()),
            (lim("neck", level="off-limits"), everything,
             ("glute-bridge", "prone-y-t-w-raise", "hip-thrust", "single-leg-glute-bridge"), ()),
            (lim("calf", "right"), {"bike"}, ("bike-cadence-surge",), ()),
            (lim("foot", "right"), set(), (), ("seated-speed-bag",)),
            (lim("groin"), everything, ("reverse-lunge", "split-squat", "bulgarian-split-squat",
                                        "worlds-greatest-stretch", "childs-pose"), ()),
            (lim("groin", level="off-limits"), everything, ("figure-four-stretch",), ()),
            (lim("calf"), everything, ("split-squat", "bulgarian-split-squat", "step-up"), ()),
            (lim("calf", level="off-limits"), everything, ("reverse-lunge",), ()),
            (lim("calf", "left"), everything, ("split-squat",), ()),   # the rear foot is on its toes
            (lim("wrist"), everything, ("thread-the-needle",), ()),   # support wrist 2
            (lim("low-back", level="off-limits"), everything, ("single-arm-row",), ()),   # support 1
        )
        for limit, kit, out, kept in rows:
            with self.subTest(limit=limit):
                sel = catalog.select(cat, kit, "advanced", [limit])
                allowed = {m.id for m in sel.allowed + sel.healthy_side_only}
                for mid in out:
                    self.assertIn(mid, sel.left_out, mid)
                    self.assertNotIn(mid, allowed, mid)
                for mid in kept:
                    self.assertIn(mid, allowed, mid)
        sel = catalog.select(cat, {"dumbbells", "bench", "bike"}, "experienced", [lim("ankle", "right", "off-limits")])
        self.assertTrue(all(m.position != "standing" for m in sel.allowed))
        self.assertTrue(any(m.intensity == "conditioning" and m.effort in ("moderate", "hard") for m in sel.allowed))

    def test_a_faulty_private_entry_is_never_planned(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "movements.toml")
            with open(path, "w", encoding="utf-8") as f:   # no loads, so no limit could screen it
                f.write('[[movement]]\nid = "my-jump-squat"\nname = "my jump squat"\nneeds = []\n'
                        'position = "standing"\nmeasure = "reps"\npatterns = ["squat"]\nmuscles = ["quads"]\n'
                        'flags = ["impact"]\nintensity = "strength"\nlevel = "novice"\nseconds_per_rep = 2\n'
                        'transition_seconds = 10\ndraft = false\nsetup = "Stand tall."\ncues = ["Jump."]\n')
            with mock.patch.object(catalog.paths, "MY_MOVEMENTS", path):
                cat = catalog.load()
            self.assertTrue(cat.movements["my-jump-squat"].draft)
            off = [lim("knee", level="off-limits")]
            self.assertEqual(catalog.select(cat, set(), "novice", off).left_out["my-jump-squat"], ["draft"])
            with open(path, "w", encoding="utf-8") as f:
                f.write("[[movement]\nid = ")
            with mock.patch.object(catalog.paths, "MY_MOVEMENTS", path), mock.patch("sys.stderr"):
                cat = catalog.load()   # an unreadable file is skipped, not a crash
            self.assertIn("air-squat", cat.movements)
            self.assertIn("can't be read", check.check_movements(path)[0].message)


class Select(unittest.TestCase):
    def test_left_out_reasons(self):
        """Each row: (kit, limits, dislikes and avoid, movement, its reasons) against the fixture."""
        gs = {"goblet-squat"}
        rows = (
            ({"dumbbells"}, [], set(), "old-style", ["draft"]),
            ({"dumbbells"}, [], set(), "bike-easy-spin", ["equipment"]),
            ({"mat"}, [lim("knee", level="off-limits")], set(), "glute-bridge", None),   # knee = 1
            ({"mat"}, [lim("knee")], set(), "air-squat", ["knee delicate"]),
            ({"dumbbells", "mat"}, [lim("knee", "left", "off-limits")], set(), "split-squat", None),   # support 1 >= 1
            ({"mat"}, [lim("wrist", flags=["floor"], rehab=["old-style"])], set(), "old-style", ["draft"]),
            (set(), [lim("knee", "left"), lim("knee", "right")], set(), "split-squat", ["knee delicate"]),
            ({"dumbbells"}, [lim("low-back", level="off-limits")], set(), "one-arm-row", ["low-back off limits"]),
            (set(), [lim("knee", level="off-limits", rehab=["air-squat"])], set(), "air-squat",
             ["knee off limits"]),   # air-squat is no rehab entry
            (set(), [lim("wrist")], set(), "push-up", ["wrist delicate"]),   # wrist = 2: delicate stops at two
            ({"dumbbells"}, [lim("knee")], gs, "goblet-squat", ["disliked", "avoided", "knee delicate"]),
        )
        for kit, limits, avoid, mid, reasons in rows:
            with self.subTest(mid=mid, limits=limits):
                sel = catalog.select(catalog.load(FIXTURE), kit, "novice", limits, dislikes=avoid, avoid=avoid)
                self.assertIn(mid, sel.left_out)
                if reasons is not None:
                    self.assertEqual(sel.left_out[mid], reasons)
        self.assertIn("floor", catalog.select(catalog.load(FIXTURE), {"mat"}, "novice",
                                              [lim("wrist", flags=["floor"])]).left_out["glute-bridge"])
        cat = catalog.load(FIXTURE)
        cat.movements["air-squat"].level = "advanced"
        cat.movements["push-up"].rehab = True
        sel = catalog.select(cat, set(), "experienced", [])
        self.assertEqual((sel.left_out["air-squat"], sel.left_out["push-up"]), (["level"], ["rehab"]))
        sel = catalog.select(cat, set(), "experienced", [lim("wrist", level="off-limits", rehab=["push-up"])])
        self.assertIn("push-up", {m.id for m in sel.allowed})   # named by the limit's rehab list

    def test_sides_support_and_impact(self):
        cat = catalog.load(FIXTURE)
        sel = catalog.select(cat, {"dumbbells", "mat"}, "novice", [lim("knee", "left")])
        self.assertIn("air-squat", sel.left_out)
        self.assertIn("split-squat", {m.id for m in sel.healthy_side_only})   # support knee = 1 < 2
        self.assertNotIn("split-squat", {m.id for m in sel.allowed})
        self.assertIn("glute-bridge", {m.id for m in catalog.select(cat, {"mat"}, "novice", [lim("knee")]).allowed})
        both = catalog.select(cat, set(), "novice", [lim("knee", "left"), lim("knee", "right")])
        self.assertNotIn("split-squat", {m.id for m in both.healthy_side_only})
        self.assertIn("one-arm-row", {m.id for m in catalog.select(cat, {"dumbbells"}, "novice",
                                                                      [lim("low-back", "left")]).allowed})
        cat.movements["one-arm-row"].support["wrist"] = 2
        self.assertEqual(catalog.select(cat, {"dumbbells"}, "novice", [lim("wrist")]).left_out["one-arm-row"],
                         ["wrist delicate"])
        cat.movements["split-squat"].loads["ankle"] = 2
        cat.movements["split-squat"].support["ankle"] = 0
        sel = catalog.select(cat, set(), "novice", [lim("knee", "left"), lim("ankle", "right", "off-limits")])
        self.assertEqual(sel.left_out["split-squat"],   # standing is out with an ankle off limits, too
                         ["standing with the ankle off limits", "knee delicate", "ankle off limits"])
        cat = catalog.load(FIXTURE)
        cat.movements["air-squat"].flags = ["impact"]
        cat.movements["push-up"].flags = ["fast"]
        squat, push = cat.movements["air-squat"], cat.movements["push-up"]
        quiet = next(a for a in cat.areas if not push.loads.get(a) and not push.support.get(a)
                     and not squat.loads.get(a))
        sel = catalog.select(cat, set(), "novice", [lim(quiet)])
        self.assertEqual(sel.left_out["air-squat"], ["impact"])   # impact is out under any delicate area
        self.assertNotIn("push-up", sel.left_out)   # fast work that doesn't load the delicate area stays in
        loaded = next(a for a in cat.areas if push.loads.get(a))
        self.assertIn("fast", catalog.select(cat, set(), "novice", [lim(loaded)]).left_out["push-up"])

    def test_limit_values_are_defined_once_and_unknown_ones_raise(self):
        import health
        import screen
        self.assertEqual(catalog.LIMIT_SIDES, ("left", "right", "both"))
        self.assertEqual(catalog.LIMIT_LEVELS, ("off-limits", "delicate"))
        for mod in (health, screen):
            self.assertIs(mod.LIMIT_SIDES, catalog.LIMIT_SIDES, mod.__name__)
            self.assertIs(mod.LIMIT_LEVELS, catalog.LIMIT_LEVELS, mod.__name__)
        self.assertEqual((catalog.threshold(lim("knee")), catalog.threshold(lim("knee", level="off-limits"))), (2, 1))
        cat = catalog.load(FIXTURE)
        for bad in (lim("knee", level="soft"), lim("knee", "up")):
            with self.assertRaises(ValueError):
                catalog.select(cat, set(), "novice", [bad])


if __name__ == "__main__":
    unittest.main()
