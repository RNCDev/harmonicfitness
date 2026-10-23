"""Checks for the safety screen behind the brief (tools/screen.py), against a small catalog and an
invented listener in tests/fixtures/, and for the judged grid's cases and listeners in docs/eval/."""
import os
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import context  # noqa: E402
import screen  # noqa: E402
import sessions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
LISTENER = os.path.join(FIXTURES, "listener")
FIXTURE_CAT = catalog.load(os.path.join(FIXTURES, "movements.toml"))
GOALS = sessions.load().goals


def listener_profile(**settings):
    """The invented listener's profile, with some settings changed."""
    p = context.profile(os.path.join(LISTENER, "profile.md"))
    p.settings.update(settings)
    return p


def screen_for(health=None, profile=None, **request):
    """screen.screen for a request against the fixture catalog and the invented listener."""
    if not {"preset", "equipment"} & set(request):
        request.setdefault("kit", "home")
    request.setdefault("goal", "strength")
    request.setdefault("minutes", 30)
    return screen.screen(request, FIXTURE_CAT, GOALS, profile or listener_profile(),
                         health or context.health(os.path.join(LISTENER, "health.md")))


def offered(scr):
    return {m.id for m in scr.sel.allowed + scr.sel.healthy_side_only}


class Screen(unittest.TestCase):
    def health_with(self, extra_rules):
        with open(os.path.join(LISTENER, "health.md")) as f:
            text = f.read()
        path = os.path.join(tempfile.mkdtemp(), "health.md")
        with open(path, "w") as f:
            f.write(text.replace("- No pushing through wrist pain.", "- No pushing through wrist pain.\n" + extra_rules))
        return context.health(path)

    def test_wrist_limit_shapes_the_selection(self):
        scr = screen_for()
        self.assertEqual([(lim.area, lim.side, lim.level) for lim in scr.limits], [("wrist", "left", "delicate")])
        for m in scr.sel.allowed:
            self.assertLess(m.loads.get("wrist", 0), 2, m.id)
        self.assertIn("one-arm-plank", {m.id for m in scr.sel.healthy_side_only})

    def test_request_limits_follow_health_rows(self):
        knee = catalog.Limit("knee", "right", "delicate", [], [], "")
        scr = screen_for(limits=[knee])
        self.assertEqual([lim.area for lim in scr.limits], ["wrist", "knee"])

    def test_likes_and_dislikes(self):
        scr = screen_for()
        self.assertEqual(scr.likes, {"goblet-squat"})
        self.assertEqual(scr.dislikes, {"push-up"})
        self.assertNotIn("push-up", offered(scr))
        none = context.Health({}, "")
        self.assertIn("push-up", offered(screen_for(health=none, profile=listener_profile(dislikes=[]))))
        self.assertNotIn("push-up", offered(screen_for(health=none)))

    def test_ids_resolve_names_and_skip_unknown(self):
        self.assertEqual(screen.ids(FIXTURE_CAT, ["reverse lunge", "goblet-squat", "wobbly thing"]),
                         {"reverse-lunge", "goblet-squat"})

    def test_no_experience_assumes_novice(self):
        scr = screen_for(profile=listener_profile(experience=""))
        self.assertIn("no experience level in the profile; assuming novice", scr.warnings)
        self.assertEqual(scr.level, "novice")
        self.assertTrue(all(m.level == "novice" for m in scr.sel.allowed + scr.sel.healthy_side_only))

    def test_unknown_values_raise(self):
        for bad in ({"kit": "castle"}, {"level": "wizard"}, {"target": ["wings"]}, {"goal": "vibes"},
                    {"minutes": 0}, {"equipment": ["anvil"]},
                    {"limits": [catalog.Limit("tail", "both", "delicate", [], [], "")]},
                    {"limits": [catalog.Limit("knee", "both", "sore", [], [], "")]},
                    {"limits": [catalog.Limit("knee", "up", "delicate", [], [], "")]}):
            with self.assertRaises(ValueError, msg=bad):
                screen_for(**bad)
        with self.assertRaises(ValueError):
            screen.screen({"goal": "strength", "minutes": 30}, FIXTURE_CAT, GOALS, listener_profile(),
                          context.Health({}, ""))   # no kit, preset or equipment

    def test_bad_health_row_is_unfit_not_usage(self):
        with self.assertRaises(screen.Unfit) as caught:
            with unittest.mock.patch.object(context, "limits",
                                            return_value=[catalog.Limit("wrist", "both", "sore", [], [], "")]):
                screen_for(health=context.Health({}, ""))
        self.assertIn("health", str(caught.exception))

    def test_a_dropped_limits_row_is_unfit(self):
        h = context.Health({"limits": [{"area": "wrist", "side": "left", "level": "sore"}]}, "")
        with self.assertRaises(screen.Unfit) as caught:
            screen_for(health=h)
        self.assertIn("a [[limits]] row was ignored", str(caught.exception))

    def test_prose_injuries_without_limits_warns(self):
        h = context.Health({}, "## Active injuries and limitations\n- Left knee: invented.\n")
        self.assertTrue(any("no [[limits]]" in w for w in screen_for(health=h).warnings))
        self.assertFalse(any("no [[limits]]" in w for w in screen_for().warnings))

    def test_clinician_avoid_lines_apply_without_a_flag(self):
        self.assertIn("goblet-squat", offered(screen_for()))
        h = self.health_with("- Avoid: goblet-squat, impact")
        self.assertEqual(context.clinician_avoids(h), ["goblet-squat", "impact"])
        scr = screen_for(health=h)
        self.assertNotIn("goblet-squat", offered(scr))
        self.assertEqual(scr.avoid, {"goblet-squat", "impact"})

    def test_unknown_avoid_word_is_warned_not_fatal(self):
        scr = screen_for(health=self.health_with("- Avoid: wobbly-thing"))
        self.assertTrue(any("wobbly-thing" in w for w in scr.warnings), scr.warnings)
        issues = context._check_health("health.md", open(self.health_with("- Avoid: wobbly-thing").path).read())
        self.assertTrue(any("wobbly-thing" in i.message for i in issues))

    def test_healthy_side_is_opposite_the_limit(self):
        scr = screen_for()   # the fixture's left wrist is delicate
        plank = FIXTURE_CAT.movements["one-arm-plank"]
        self.assertEqual(screen.healthy_side(plank, scr.limits), "right")
        scr = screen_for(equipment=["mat", "dumbbells"], limits=[catalog.Limit("knee", "right", "delicate", [], [], "")])
        stretch = FIXTURE_CAT.movements["hip-flexor-stretch"]
        self.assertIn(stretch, scr.sel.healthy_side_only)
        self.assertEqual(screen.healthy_side(stretch, scr.limits), "left")
        both = [catalog.Limit("wrist", "both", "delicate", [], [], "")]
        self.assertEqual(screen.healthy_side(plank, both), "healthy")

    def test_would_open_counts_by_reselecting(self):
        # a kettlebell would admit goblet squat, but the listener dislikes it here, so nothing opens
        scr = screen_for(equipment=["mat", "band"], profile=listener_profile(dislikes=["push-up", "goblet-squat"]))
        opened = dict(screen.would_open(FIXTURE_CAT, scr.sel, scr.equipment, scr.level, scr.limits,
                                        scr.avoid, scr.dislikes))
        self.assertNotIn("kettlebell", opened)
        self.assertEqual(opened.get("dumbbells"), 2)   # one arm row and the deadlift; goblet squat is disliked

    def test_would_open_names_equipment(self):
        scr = screen_for(preset="bodyweight")
        opens = screen.would_open(FIXTURE_CAT, scr.sel, scr.equipment, scr.level, scr.limits, scr.avoid, scr.dislikes)
        self.assertTrue(opens and all(isinstance(n, int) for _, n in opens))
        self.assertLessEqual(len(opens), 3)
        self.assertIn("dumbbells", [e for e, _ in opens])
        self.assertEqual([n for _, n in opens], sorted((n for _, n in opens), reverse=True))

    def test_cue_lines_for_each_limit_with_its_side(self):
        knee = catalog.Limit("knee", "right", "delicate", [], [], "")
        lines = screen.cue_lines(FIXTURE_CAT, screen_for(limits=[knee]).limits)
        self.assertIn("  wrist delicate, left side:", lines)
        self.assertIn("    Keep the left wrist straight, in line with the forearm.", lines)
        self.assertIn("  knee delicate, right side:", lines)
        self.assertIn("    Keep the right knee over the toes.", lines)
        self.assertEqual(screen.cue_lines(FIXTURE_CAT, []), [])
        both = screen.cue_lines(FIXTURE_CAT, [catalog.Limit("wrist", "both", "off-limits", [], [], "")] * 2)
        self.assertEqual(both, ["  wrist off limits:", "    No weight through the injured hand."])   # once each

    def test_kit_weights_print_as_loads_on_hand(self):
        kits = [{"name": "home", "equipment": ["dumbbells", "band", "mat"],
                 "weights": {"dumbbells": [20, 10, 15]}, "unit": "lb"}]
        weights = context.kit_weights(listener_profile(kits=kits))
        self.assertEqual(weights, {"home": ("lb", {"dumbbells": [10, 15, 20]})})
        line = screen.loads_line(weights["home"], {"dumbbells", "band", "mat"})
        self.assertTrue(line.startswith("Loads on hand: dumbbells 10, 15, 20 lb (heaviest 20). At the heaviest"), line)
        self.assertEqual(screen.loads_line(("kg", {"kettlebell": [16]}), {"mat"}), "")
        self.assertIn("kettlebell 16 kg.", screen.loads_line(("kg", {"kettlebell": [16]}), {"kettlebell"}))

    def test_kit_weight_faults_are_listed(self):
        k = {"name": "home", "equipment": ["dumbbells"], "weights": {"kettlebell": [16], "dumbbells": ["heavy"]},
             "unit": "stone"}
        problems = " ".join(context._weight_problems(k))
        for word in ("kettlebell", "numbers above zero", "unit"):
            self.assertIn(word, problems)
        self.assertEqual(context._weight_problems({"name": "x", "equipment": ["dumbbells"],
                                                   "weights": {"dumbbells": [5, 7.5]}}), [])

    def test_parse_limit(self):
        lim = screen.parse_limit("knee=delicate:left", FIXTURE_CAT)
        self.assertEqual((lim.area, lim.side, lim.level), ("knee", "left", "delicate"))
        self.assertTrue(lim.note)   # what the limit means, from the catalog
        self.assertEqual(screen.parse_limit("calf=off-limits", FIXTURE_CAT).side, "both")
        for bad in ("tail=delicate", "wrist=sore", "wrist=delicate:up", "wrist"):
            with self.assertRaises(ValueError, msg=bad):
                screen.parse_limit(bad, FIXTURE_CAT)

    def test_words(self):
        self.assertEqual(screen.words(" glutes, ,hinge "), ["glutes", "hinge"])
        self.assertEqual(screen.words(None), [])

    def test_clamp(self):
        part = {"share": 0.1, "seconds": [120, 300]}
        self.assertEqual(screen.clamp(part, 600), 120)
        self.assertEqual(screen.clamp(part, 2000), 200)
        self.assertEqual(screen.clamp(part, 6000), 300)


EVAL = os.path.join(ROOT, "docs", "eval")
SHORT, LONG = range(10, 21), range(30, 46)


def eval_cases():
    import tomllib
    with open(os.path.join(EVAL, "cases.toml"), "rb") as f:
        data = tomllib.load(f)
    return data, data.get("case", [])


def eval_listener(name):
    home = os.path.join(EVAL, "listeners", name)
    return (context.profile(os.path.join(home, "profile.md")), context.health(os.path.join(home, "health.md")),
            context.sessions(os.path.join(home, "log.md")))


class Eval(unittest.TestCase):
    """The judged grid in docs/eval/: forty cases over four invented listeners."""

    @classmethod
    def setUpClass(cls):
        cls.cat, cls.sess = catalog.load(), sessions.load()

    def test_cases_are_forty_and_valid(self):
        data, cases = eval_cases()
        self.assertEqual(data.get("format"), 1)
        self.assertEqual(len(cases), 40)
        self.assertEqual([c["id"] for c in cases], [f"c{i:02d}" for i in range(1, 41)])
        allowed = {"id", "listener", "goal", "minutes", "preset", "level", "target", "limit", "method"}
        cells, extra, presets = {}, [], {}
        for i, c in enumerate(cases, 1):
            self.assertLessEqual(set(c), allowed, c["id"])
            self.assertTrue({"id", "listener", "goal", "minutes", "preset"} <= set(c), c["id"])
            self.assertIn(c["goal"], self.sess.goals, c["id"])
            self.assertIn(c["preset"], self.cat.presets, c["id"])
            self.assertIsInstance(c["minutes"], int, c["id"])
            profile, _, _ = eval_listener(c["listener"])
            level = c.get("level") or context.experience(profile)
            self.assertIn(level, catalog.LEVELS, c["id"])
            for t in screen.words(c.get("target")):
                self.assertTrue(t in self.cat.patterns or t in self.cat.muscles, (c["id"], t))
            if c.get("method"):
                self.assertIn(c["method"], self.sess.methods, c["id"])
            self.assertEqual(bool(c.get("limit")), i % 3 == 0, f"{c['id']}: every third case, and only those, has a limit")
            if c.get("limit"):
                lim = screen.parse_limit(c["limit"], self.cat)
                self.assertIn(lim.area, {"neck", "low-back", "wrist", "groin", "calf"}, c["id"])
            presets[c["preset"]] = presets.get(c["preset"], 0) + 1
            if c["goal"] in ("strength", "general", "conditioning"):
                cells.setdefault((c["goal"], level), []).append(c)
            else:
                extra.append(c)
        self.assertEqual(len(cells), 9)
        for cell, rows in cells.items():
            self.assertEqual(len(rows), 4, cell)
            by_preset = {}
            for c in rows:
                by_preset.setdefault(c["preset"], []).append(c["minutes"])
            self.assertEqual(len(by_preset), 2, cell)
            for preset, minutes in by_preset.items():
                self.assertEqual(sorted(m in LONG for m in minutes), [False, True], (cell, preset))
                self.assertTrue(all(m in SHORT or m in LONG for m in minutes), (cell, preset))
        self.assertEqual(sorted(c["goal"] for c in extra), ["mobility", "mobility", "targeted", "targeted"])
        self.assertTrue(all(c.get("target") for c in extra if c["goal"] == "targeted"))
        self.assertEqual(set(presets), set(self.cat.presets))
        self.assertTrue(all(n >= 4 for n in presets.values()), presets)

    def test_every_case_screens(self):
        for c in eval_cases()[1]:
            profile, health, _ = eval_listener(c["listener"])
            request = {"goal": c["goal"], "minutes": c["minutes"], "level": c.get("level"), "preset": c["preset"],
                       "target": screen.words(c.get("target")),
                       "limits": [screen.parse_limit(c["limit"], self.cat)] if c.get("limit") else []}
            with self.subTest(case=c["id"]):
                scr = screen.screen(request, self.cat, self.sess.goals, profile, health)
                self.assertTrue(scr.sel.allowed)

    def test_listeners_are_clean(self):
        for name in "abcd":
            home = os.path.join(EVAL, "listeners", name)
            files = [os.path.join(home, f) for f in ("profile.md", "health.md", "log.md")]
            issues = [context.describe(x) for x in context.check(files) if not x.note]
            self.assertEqual(issues, [], name)
            profile, _, _ = eval_listener(name)
            self.assertTrue(context.voices(profile), name)
            self.assertIsNotNone(context.wpm(profile), name)
        likes, dislikes = context.likes(eval_listener("d")[0]), context.dislikes(eval_listener("d")[0])
        self.assertEqual((len(likes), len(dislikes)), (2, 2))
        self.assertFalse(set(likes) & set(dislikes))
        for mid in likes + dislikes:
            self.assertFalse(self.cat.movements[mid].draft, mid)


if __name__ == "__main__":
    unittest.main()
