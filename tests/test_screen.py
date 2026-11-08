"""Checks for the safety screen behind the brief (tools/screen.py), against a small catalog and an
invented listener in tests/fixtures/."""
import os
import sys
import tempfile
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402
import check  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import context  # noqa: E402
import health as health_md  # noqa: E402
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


def screen_for(h=None, profile=None, **request):
    """screen.screen for a request against the fixture catalog and the invented listener."""
    if not {"preset", "equipment"} & set(request):
        request.setdefault("kit", "home")
    request.setdefault("goal", "strength")
    request.setdefault("minutes", 30)
    return screen.screen(request, FIXTURE_CAT, GOALS, profile or listener_profile(),
                         h or health_md.health(os.path.join(LISTENER, "health.md")))


def offered(scr):
    return {m.id for m in scr.sel.allowed + scr.sel.healthy_side_only}


class Screen(unittest.TestCase):
    def health_with(self, extra_rules):
        with open(os.path.join(LISTENER, "health.md"), encoding="utf-8") as f:
            text = f.read()
        path = os.path.join(tempfile.mkdtemp(), "health.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text.replace("- No pushing through wrist pain.", "- No pushing through wrist pain.\n" + extra_rules))
        return health_md.health(path)

    def test_learned_likes_add_and_a_firm_learned_dislike_leaves_a_movement_off(self):
        from unittest import mock
        import interests
        before = offered(screen_for())
        gone, liked = sorted(before)[:2]
        lr = interests.Learned(likes=[FIXTURE_CAT.movements[liked].name], dislikes=[FIXTURE_CAT.movements[gone].name])
        with mock.patch.object(interests, "learned", return_value=lr):
            scr = screen_for()
        self.assertIn(liked, scr.likes)
        self.assertIn(gone, scr.dislikes)
        self.assertNotIn(gone, offered(scr))

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
        none = health_md.Health({}, "")
        self.assertIn("push-up", offered(screen_for(h=none, profile=listener_profile(dislikes=[]))))
        self.assertNotIn("push-up", offered(screen_for(h=none)))

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
                          health_md.Health({}, ""))   # no kit, preset or equipment

    def test_bad_health_row_is_unfit_not_usage(self):
        with self.assertRaises(screen.Unfit) as caught:
            with unittest.mock.patch.object(health_md, "limit_rows",
                                            return_value=([catalog.Limit("wrist", "both", "sore", [], [], "")], [])):
                screen_for(h=health_md.Health({}, ""))
        self.assertIn("health", str(caught.exception))

    def test_a_dropped_limits_row_is_unfit(self):
        h = health_md.Health({"limits": [{"area": "wrist", "side": "left", "level": "sore"}]}, "")
        with self.assertRaises(screen.Unfit) as caught:
            screen_for(h=h)
        self.assertIn("a [[limits]] row was ignored", str(caught.exception))

    def test_prose_injuries_without_limits_warns(self):
        h = health_md.Health({}, "## Active injuries and limitations\n- Left knee: invented.\n")
        self.assertTrue(any("no [[limits]]" in w for w in screen_for(h=h).warnings))
        self.assertFalse(any("no [[limits]]" in w for w in screen_for().warnings))

    def test_clinician_avoid_lines_apply_without_a_flag(self):
        self.assertIn("goblet-squat", offered(screen_for()))
        h = self.health_with("- Avoid: goblet-squat, impact")
        self.assertEqual(health_md.clinician_avoids(h), ["goblet-squat", "impact"])
        scr = screen_for(h=h)
        self.assertNotIn("goblet-squat", offered(scr))
        self.assertEqual(scr.avoid, {"goblet-squat", "impact"})

    def test_unknown_avoid_word_stops_the_screen(self):
        with self.assertRaises(screen.Unfit) as caught:   # an avoid that rules nothing out protects nothing
            screen_for(h=self.health_with("- Avoid: wobbly-thing"))
        self.assertIn("wobbly-thing", str(caught.exception))
        with open(self.health_with("- Avoid: wobbly-thing").path, encoding="utf-8") as f:
            issues = check._check_health("health.md", f.read())
        self.assertTrue(any("wobbly-thing" in i.message for i in issues))

    def test_a_side_lying_movement_is_never_offered_one_side_only(self):
        """Lying on one side, the working leg may be the top one: "right side only" read as "lie on your right
        side, right knee on the bench", and the side check forbade "left" (0.50.2's loop: a Copenhagen plank)."""
        import catalog as real
        cat = real.load()
        lim = [real.Limit("knee", "left", "delicate", [], [], "")]
        sel = real.select(cat, real.kit_equipment(cat, {"preset": "full-gym"}), "experienced", lim)
        self.assertNotIn("copenhagen-plank", {m.id for m in sel.allowed + sel.healthy_side_only})
        self.assertIn("lying on one side", sel.left_out["copenhagen-plank"])
        self.assertFalse([m.id for m in sel.healthy_side_only if "lying-side" in m.flags])

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
        problems = " ".join(context.kit_problems(k))
        for word in ("kettlebell", "numbers above zero", "unit"):
            self.assertIn(word, problems)
        self.assertEqual(context.kit_problems({"name": "x", "equipment": ["dumbbells"],
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


if __name__ == "__main__":
    unittest.main()
