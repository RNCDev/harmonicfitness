"""Checks for the session methods and dose rules (knowledge/sessions.toml) and for the composer
(tools/session.py), which runs against a small catalog and an invented listener in tests/fixtures/."""
import datetime
import os
import subprocess
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import context  # noqa: E402
import draft  # noqa: E402
import sessions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
LISTENER = os.path.join(FIXTURES, "listener")
TODAY = datetime.date(2026, 10, 21)


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

    def test_choose_prefers_goal_fit_over_file_order(self):
        self.assertEqual(self.s.methods["circuit"].goals[-1], "conditioning")
        pick = lambda level, last: sessions.choose_method(self.s, "conditioning", 30, level, last, set()).name  # noqa: E731
        self.assertEqual(pick("novice", None), "intervals")
        self.assertEqual(pick("novice", "circuit"), "intervals")
        self.assertEqual(pick("novice", "intervals"), "circuit")     # circuit only after intervals was last
        self.assertEqual(pick("experienced", "intervals"), "tabata")   # a better-fitting method comes first
        self.assertEqual([m.name for m in sessions.ranked(self.s, "general", 30, "novice", set())][0], "circuit")

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


def compose_for(health=None, profile=None, **request):
    """session.compose for a request against the fixture catalog and the invented listener."""
    import session
    if not {"preset", "equipment"} & set(request):
        request.setdefault("kit", "home")
    cat = catalog.load(os.path.join(FIXTURES, "movements.toml"))
    return session.compose(request, cat, sessions.load(), profile or listener_profile(),
                           health or context.health(os.path.join(LISTENER, "health.md")),
                           context.sessions(os.path.join(LISTENER, "log.md")), TODAY)


def listener_profile(**settings):
    """The invented listener's profile, with some settings changed."""
    p = context.profile(os.path.join(LISTENER, "profile.md"))
    p.settings.update(settings)
    return p


def planned(sk):
    return sk.warmup + sum(s.seconds for _, slots in sk.blocks for s in slots) + sk.finisher + sk.cooldown


def run_session(args):
    """Run `./sweatcast session ...` on the real catalog for the invented listener."""
    env = dict(os.environ, SWEATCAST_PYTHON=sys.executable, SWEATCAST_HOME=LISTENER)
    return subprocess.run(["sh", os.path.join(ROOT, "sweatcast"), "session", *args],
                          capture_output=True, text=True, env=env, cwd=ROOT)


class Compose(unittest.TestCase):
    def assertWithinTolerance(self, sk, minutes):
        self.assertLessEqual(abs(planned(sk) - minutes * 60), minutes * 60 * draft.TOTAL_TOLERANCE)

    def test_total_within_tolerance(self):
        for goal, minutes in (("strength", 30), ("strength", 45), ("general", 30), ("general", 12)):
            self.assertWithinTolerance(compose_for(goal=goal, minutes=minutes), minutes)

    def test_rotates_away_from_last_format(self):
        self.assertEqual(compose_for(goal="strength", minutes=30).method.name, "paired-sets")

    def test_wrist_limit_shapes_candidates(self):
        sk = compose_for(goal="general", minutes=30)
        self.assertWithinTolerance(sk, 30)
        offered = [(m, r) for _, slots in sk.blocks for s in slots for m, r in s.candidates]
        for m, _ in offered:
            if not m.sided:
                self.assertLess(m.loads.get("wrist", 0), 2, m.id)
        self.assertTrue(any("healthy side only" in r for _, r in offered))   # one-arm-plank

    def test_liked_ranks_first_and_disliked_never_appears(self):
        sk = compose_for(goal="strength", minutes=45)
        self.assertWithinTolerance(sk, 45)
        squat = next(s for _, slots in sk.blocks for s in slots if s.pattern == "squat")
        self.assertEqual(squat.candidates[0][0].id, "goblet-squat")
        self.assertIn("liked", squat.candidates[0][1])
        self.assertFalse(any(m.id == "push-up" for _, slots in sk.blocks for s in slots for m, _ in s.candidates))

    def test_dislike_and_like_bite_without_limits(self):
        none = context.Health({}, "")
        offered = lambda sk: [m.id for _, ss in sk.blocks for s in ss for m, _ in s.candidates]  # noqa: E731
        self.assertIn("push-up", offered(compose_for(goal="strength", minutes=45, health=none,
                                                     profile=listener_profile(dislikes=[]))))
        self.assertNotIn("push-up", offered(compose_for(goal="strength", minutes=45, health=none)))
        # reverse-lunge comes after split-squat in catalog order; both are fresh, so only the like puts it first
        lunge = lambda sk: next(s for _, ss in sk.blocks for s in ss if s.pattern == "lunge")  # noqa: E731
        plain = compose_for(goal="strength", minutes=45, health=none, profile=listener_profile(likes=[]))
        self.assertEqual(lunge(plain).candidates[0][0].id, "split-squat")
        liked = compose_for(goal="strength", minutes=45, health=none, profile=listener_profile(likes=["reverse lunge"]))
        self.assertEqual(lunge(liked).candidates[0][0].id, "reverse-lunge")
        self.assertIn("liked", lunge(liked).candidates[0][1])

    def test_pairs_cross_families(self):
        import session
        for kw in ({}, {"health": context.Health({}, "")}):
            sk = compose_for(goal="strength", minutes=45, **kw)
            self.assertEqual(sk.method.work, "pairs")
            slots = [s for _, ss in sk.blocks for s in ss]
            for i in range(0, len(slots) - 1, 2):
                a, b = session.family(slots[i].pattern), session.family(slots[i + 1].pattern)
                later = {session.family(s.pattern) for s in slots[i + 2:]}
                if a == b:
                    self.assertEqual(later - {a}, set(), [s.pattern for s in slots])
        mixed = [(p, None) for p in ("squat", "hinge", "horizontal-pull", "lunge", "horizontal-push")]
        self.assertEqual([p for p, _ in session._pair_up(mixed)],
                         ["squat", "horizontal-pull", "hinge", "horizontal-push", "lunge"])

    def test_pairs_take_spare_rest_only_between_pairs(self):
        sk = compose_for(goal="strength", minutes=30)
        slots = [s for _, ss in sk.blocks for s in ss]
        import session
        bare = session.block_seconds([s.candidates[0][0] for s in slots], slots[0].dose, "pairs")
        for i in range(0, len(slots) - 1, 2):
            self.assertEqual(slots[i].seconds, bare[i], i)   # the first of a pair never carries spare rest

    def test_would_open_up_counts_by_reselecting(self):
        # a kettlebell would admit goblet squat, but the listener dislikes it here, so nothing opens
        sk = compose_for(goal="strength", minutes=30, equipment={"mat", "band"},
                         profile=listener_profile(dislikes=["push-up", "goblet-squat"]))
        opened = dict(sk.would_open)
        self.assertNotIn("kettlebell", opened)
        self.assertEqual(opened.get("dumbbells"), 2)   # one arm row and the deadlift; goblet squat is disliked

    def test_bad_health_row_is_unfit_not_usage(self):
        import session
        h = context.Health({}, "")
        with self.assertRaises(session.Unfit) as caught:
            with unittest.mock.patch.object(context, "limits",
                                            return_value=[catalog.Limit("wrist", "both", "sore", [], [], "")]):
                compose_for(goal="strength", minutes=30, health=h)
        self.assertIn("health", str(caught.exception))

    def test_last_session_movements_rank_after_fresh_ones(self):
        sk = compose_for(goal="strength", minutes=40)
        core = next(s for _, slots in sk.blocks for s in slots if s.pattern == "anti-extension")
        ids = [m.id for m, _ in core.candidates]
        self.assertLess(ids.index("one-arm-plank"), ids.index("dead-bug"))   # dead bug was in the last session
        self.assertNotIn("fresh", dict((m.id, r) for m, r in core.candidates)["dead-bug"])

    def test_request_limit_prints_as_a_health_line(self):
        import session
        sk = compose_for(goal="strength", minutes=30, limits=[catalog.Limit("knee", "right", "delicate", [], [], ""),
                                                              catalog.Limit("calf", "both", "off-limits", [], [], "")])
        lines = session.render(sk)
        self.assertIn("Health: today: knee delicate right", lines)
        self.assertIn("Health: today: calf off-limits", lines)
        self.assertNotIn("today:", " ".join(session.render(compose_for(goal="strength", minutes=30))))

    def test_sided_slots_say_each_side_or_the_healthy_side(self):
        import session
        sk = compose_for(goal="strength", minutes=40)   # the fixture's left wrist is delicate
        slots = [s for _, ss in sk.blocks for s in ss]
        lunge = next(s for s in slots if s.pattern == "lunge")
        core = next(s for s in slots if s.pattern == "anti-extension")
        self.assertTrue(lunge.candidates[0][0].sided)
        self.assertEqual(core.candidates[0][0].id, "one-arm-plank")   # healthy side only
        text = "\n".join(session.render(sk))
        self.assertRegex(text, r"lunge \(\d+ sets of \d+ \(each side\)")
        self.assertRegex(text, r"anti-extension \(\d+ sets of \d+ s \(right side only\)")
        titles = [line.split("|", 1)[1].strip().lower() for line in session.render_draft(sk)]
        self.assertTrue(any(lunge.candidates[0][0].name + " each side" in t for t in titles), titles)
        self.assertTrue(any("one arm plank right side only" in t for t in titles), titles)
        squat = next(s for s in slots if s.pattern == "squat")
        self.assertFalse(squat.candidates[0][0].sided)
        self.assertFalse(any(squat.candidates[0][0].name + " each side" in t for t in titles), titles)

    def test_interval_slots_keep_the_healthy_side(self):
        import session
        sk = compose_for(goal="conditioning", minutes=20, method="tabata")   # the fixture's left wrist is delicate
        self.assertEqual(sk.method.work, "intervals")
        core = next(s for _, ss in sk.blocks for s in ss if s.pattern == "anti-extension")
        self.assertEqual(core.candidates[0][0].id, "one-arm-plank")   # healthy side only
        titles = [line.split("|", 1)[1].strip() for line in session.render_draft(sk)]
        plank = [t for t in titles if t.startswith("one arm plank")]
        self.assertTrue(plank)
        self.assertTrue(all(t.startswith("one arm plank right side only, ") and ", interval " in t for t in plank), plank)
        self.assertFalse(any("each side" in t for t in titles), titles)
        text = "\n".join(session.render(sk))
        self.assertRegex(text, r"anti-extension \(8 rounds of 20 s on, 10 s off \(right side only\)")

    def test_warmup_finisher_and_cooldown_candidates_are_screened(self):
        import session
        sk = compose_for(goal="strength", minutes=30, equipment={"mat", "dumbbells", "bike"})   # left wrist delicate
        self.assertTrue(sk.finisher)
        for part in ("warmup", "cooldown"):
            picks = [m for m, _ in sk.extras[part]]
            self.assertTrue(picks, part)
            self.assertLessEqual(len(picks), 5)
            for m in picks:
                self.assertIn(m.patterns[0], ("mobility", "breathing", "locomotion"), m.id)
                if not m.sided:
                    self.assertLess(m.loads.get("wrist", 0), 2, (part, m.id))
            self.assertNotIn("bear-crawl", [m.id for m in picks])
        fin = [m for m, _ in sk.extras["finisher"]]
        self.assertTrue(fin)
        self.assertLessEqual(len(fin), 3)
        self.assertTrue(all(m.intensity == "conditioning" and m.effort != "easy" for m in fin))
        self.assertNotEqual(fin[0].id, sk.extras["warmup"][0][0].id)
        self.assertEqual(sk.extras["warmup"][0][0].effort, "easy")   # the warm-up starts easy
        self.assertEqual(sk.extras["cooldown"][0][0].id, "box-breathing")   # the skill's close is box breathing
        self.assertEqual(sk.extras["warmup"][0][0].patterns[0], "locomotion")
        self.assertNotEqual(sk.extras["warmup"], sk.extras["cooldown"])
        lines = session.render(sk)
        at = lines.index(f"Warm-up: {sk.warmup} s:")
        self.assertNotIn("box-breathing", lines[at + 1])   # breathing closes, it doesn't warm up
        self.assertTrue(lines[at + 1].startswith("  "))
        fd = sk.finisher_dose
        self.assertIn(f"Finisher: {sk.finisher} s, {fd['rounds']} rounds of {fd['work_seconds']} s on, "
                      f"{fd['rest_seconds']} s off:", lines)
        self.assertLessEqual(fd["rounds"] * (fd["work_seconds"] + fd["rest_seconds"]), sk.finisher)
        self.assertIn(f"Cool-down: {sk.cooldown} s:", lines)
        self.assertEqual(session.render_draft(sk)[0], f"@@ {sk.warmup} | Warm-up")
        short = compose_for(goal="general", minutes=12)   # no finisher under twenty-five minutes
        self.assertEqual((short.finisher, short.extras["finisher"]), (0, []))
        self.assertFalse(any(line.startswith("Finisher") for line in session.render(short)))

    def test_healthy_side_extras_name_the_side(self):
        sk = compose_for(goal="strength", minutes=30, equipment={"mat", "dumbbells"},
                         limits=[catalog.Limit("knee", "right", "delicate", [], [], "")])
        stretch = dict((m.id, r) for m, r in sk.extras["warmup"]).get("hip-flexor-stretch")
        self.assertIsNotNone(stretch)
        self.assertIn("left side only", stretch)

    def test_no_experience_assumes_novice(self):
        sk = compose_for(goal="strength", minutes=30, profile=listener_profile(experience=""))
        self.assertIn("no experience level in the profile; assuming novice", sk.warnings)
        offered = [m for _, ss in sk.blocks for s in ss for m, _ in s.candidates]
        self.assertTrue(all(m.level == "novice" for m in offered))

    def test_limit_without_a_note_prints_a_health_line(self):
        import session
        h = context.Health({"limits": [{"area": "knee", "side": "left", "level": "delicate"},
                                       {"area": "calf", "level": "off-limits", "note": "Physio: no calf raises."}]}, "")
        lines = session.render(compose_for(goal="strength", minutes=30, health=h))
        self.assertIn("Health: knee delicate left", lines)
        self.assertIn("Health: calf off-limits: Physio: no calf raises.", lines)

    def test_short_request_drops_slots_not_time(self):   # Review Focus 2
        sk = compose_for(goal="general", minutes=12)
        self.assertGreaterEqual(len(sk.dropped), 1)
        self.assertLessEqual(planned(sk), 720 * (1 + draft.TOTAL_TOLERANCE))
        self.assertWithinTolerance(sk, 12)

    def test_too_short_for_the_method_is_unfit(self):
        import session
        with self.assertRaises(session.Unfit):
            compose_for(goal="strength", minutes=30, limits=[catalog.Limit(area, "both", "off-limits", [], [], "")
                                                           for area in ("knee", "low-back")])

    def test_prose_injuries_without_limits_warns(self):   # Review Focus 3
        h = context.Health({}, "## Active injuries and limitations\n- Left knee: invented.\n")
        sk = compose_for(goal="strength", minutes=30, health=h)
        self.assertTrue(any("no [[limits]]" in w for w in sk.warnings))
        self.assertFalse(any("no [[limits]]" in w for w in compose_for(goal="strength", minutes=30).warnings))

    def test_draft_lines_are_markers(self):
        import session
        sk = compose_for(goal="strength", minutes=30)
        lines = session.render_draft(sk)
        self.assertTrue(all(draft.MARKER.match(line) for line in lines))
        self.assertEqual(lines[0].split("|")[1].strip().lower()[:7], "warm-up")
        segments = draft.parse("\n".join(lines))
        self.assertEqual(sum(seg["seconds"] for seg in segments), planned(sk))
        self.assertEqual(segments[-1]["label"].lower(), "cool-down")

    def test_draft_seconds_match_for_rounds(self):
        import session
        sk = compose_for(goal="general", minutes=12)
        self.assertEqual(sk.method.name, "circuit")
        segments = draft.parse("\n".join(session.render_draft(sk)))
        self.assertEqual(sum(seg["seconds"] for seg in segments), planned(sk))
        rounds = next(s for _, slots in sk.blocks for s in slots).dose["rounds"]
        self.assertEqual(len(segments), rounds + 2)

    def test_would_open_up_names_equipment(self):
        sk = compose_for(goal="strength", minutes=30, preset="bodyweight")
        self.assertTrue(sk.would_open and all(isinstance(n, int) for _, n in sk.would_open))
        self.assertLessEqual(len(sk.would_open), 3)
        self.assertIn("dumbbells", [e for e, _ in sk.would_open])

    def test_target_moves_pattern_first(self):
        sk = compose_for(goal="strength", minutes=30, target=["anti-extension"])
        self.assertEqual(sk.blocks[0][1][0].pattern, "anti-extension")

    def test_unknown_values_raise(self):
        for bad in ({"kit": "castle"}, {"method": "intervals"}, {"level": "wizard"}, {"target": ["wings"]},
                    {"goal": "vibes"}):
            request = dict(goal="strength", minutes=30)
            request.update(bad)
            with self.assertRaises(ValueError, msg=bad):
                compose_for(**request)

    def test_sided_work_counts_both_sides(self):
        import dataclasses
        import session
        cat = catalog.load(os.path.join(FIXTURES, "movements.toml"))
        lunge = cat.movements["split-squat"]
        one_side = dataclasses.replace(lunge, sided=False)
        dose = {"sets": 3, "reps": 8, "rest_seconds": 90}
        for work in ("sets", "pairs"):
            self.assertGreater(session.slot_seconds(lunge, dose, work), session.slot_seconds(one_side, dose, work))
        self.assertEqual(session.slot_seconds(lunge, dose, "sets") - session.slot_seconds(one_side, dose, "sets"), 3 * 24)
        rounds = {"rounds": 3, "reps": 8, "rest_seconds": 90}
        self.assertGreater(session.slot_seconds(lunge, rounds, "rounds"), session.slot_seconds(one_side, rounds, "rounds"))

    def test_flow_fills_the_block_by_cycling(self):
        sk = compose_for(goal="mobility", minutes=30)
        self.assertEqual(sk.method.name, "flow")
        slots = [s for _, ss in sk.blocks for s in ss]
        self.assertGreaterEqual(len(slots), 4)
        self.assertLessEqual(len(slots), 12)
        self.assertLessEqual(sk.cooldown, sk.method.cooldown["seconds"][1])
        self.assertWithinTolerance(sk, 30)

    def test_hard_sets_cap_and_warning_past_a_tenth(self):
        sk = compose_for(goal="strength", minutes=60, equipment={"mat"}, level="novice")
        self.assertWithinTolerance(sk, 60)
        slots = [s for _, ss in sk.blocks for s in ss]
        cap = sessions.dose(sessions.load(), "strength", "novice")["hard_sets_per_session"][1]
        self.assertLessEqual(sum(s.dose["sets"] for s in slots), cap)
        self.assertEqual(sk.warmup, sk.method.warmup["seconds"][1])
        self.assertTrue(any(w.startswith("method filled early:") for w in sk.warnings), sk.warnings)
        self.assertFalse(any("filled early" in w for w in compose_for(goal="strength", minutes=30).warnings))

    def test_ranking_with_limits_counts_only_limited_areas(self):
        sk = compose_for(goal="strength", minutes=30, limits=[catalog.Limit("knee", "both", "delicate", [], [], "")])
        hinge = next(s for _, ss in sk.blocks for s in ss if s.pattern == "hinge")
        # with dumbbells on hand the loaded deadlift ranks ahead of the bodyweight bridge
        self.assertEqual([m.id for m, _ in hinge.candidates][:2], ["dumbbell-romanian-deadlift", "glute-bridge"])
        h = context.Health({}, "")
        sk = compose_for(goal="strength", minutes=30, health=h, limits=[catalog.Limit("knee", "both", "delicate", [], [], "")])
        hinge = next(s for _, ss in sk.blocks for s in ss if s.pattern == "hinge")
        self.assertEqual(hinge.candidates[0][0].id, "dumbbell-romanian-deadlift")   # no knee load, despite heavy hips

    def test_level_closeness_ranks_after_fresh_and_liked(self):
        # bike-steady (novice) comes before bear-crawl (experienced) in the file; both are fresh and unliked
        none = context.Health({}, "")
        sk = compose_for(goal="conditioning", minutes=20, equipment={"bike"}, health=none)
        self.assertEqual(sk.method.name, "intervals")
        first = next(s for _, ss in sk.blocks for s in ss)
        self.assertEqual([m.id for m, _ in first.candidates][:2], ["bear-crawl", "bike-steady"])
        sk = compose_for(goal="conditioning", minutes=20, equipment={"bike"}, health=none,
                         profile=listener_profile(likes=["bike-steady"]))
        first = next(s for _, ss in sk.blocks for s in ss)
        self.assertEqual(first.candidates[0][0].id, "bike-steady")   # liked outranks level

    def test_interval_work_is_never_easy_and_thin_kits_fall_back(self):
        none = context.Health({}, "")
        sk = compose_for(goal="conditioning", minutes=20, equipment={"bike"}, health=none,
                         profile=listener_profile(likes=["bike-easy-spin"]))
        ids = {m.id for _, ss in sk.blocks for s in ss if not s.dose.get("steady") for m, _ in s.candidates}
        self.assertNotIn("bike-easy-spin", ids)   # even liked, an easy spin is no interval
        thin = compose_for(goal="conditioning", minutes=20, equipment={"mat"}, health=none)
        patterns = {s.pattern for _, ss in thin.blocks for s in ss}
        self.assertGreater(len(patterns), 1, patterns)   # one hard locomotion movement: strength moves join in
        self.assertTrue(any("joins in" in w for w in thin.warnings), thin.warnings)

    def test_one_side_only_times_one_side(self):
        import session
        m = catalog.load(os.path.join(FIXTURES, "movements.toml")).movements["split-squat"]
        dose = {"sets": 3, "reps": 8, "rest_seconds": 60}
        both, one = session.slot_seconds(m, dose, "sets"), session.slot_seconds(m, dose, "sets", one_side=True)
        self.assertEqual(both - one, 3 * 8 * m.seconds_per_rep)

    def test_bodyweight_reps_above_novice(self):
        import session
        cat = catalog.load(os.path.join(FIXTURES, "movements.toml"))
        dose = {"reps": 8, "bodyweight_reps": 14}
        self.assertEqual(session.reps(cat.movements["air-squat"], dose), 14)
        self.assertEqual(session.reps(cat.movements["goblet-squat"], dose), 8)
        self.assertEqual(session.reps(cat.movements["air-squat"], {"reps": 8}), 8)

    def test_slot_seconds(self):
        import session
        cat = catalog.load(os.path.join(FIXTURES, "movements.toml"))
        squat = cat.movements["goblet-squat"]   # transition 15, three seconds a rep
        self.assertEqual(session.slot_seconds(squat, {"sets": 3, "reps": 8, "rest_seconds": 90}, "sets"),
                         15 + 3 * 24 + 2 * 90)
        self.assertEqual(session.slot_seconds(squat, {"work_seconds": 30, "rest_seconds": 30, "rounds": 6},
                                              "intervals"), 6 * 60)
        self.assertEqual(session.slot_seconds(cat.movements["box-breathing"], {"hold_seconds": 45, "rounds": 2},
                                              "holds"), 2 * 45 + 10)


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


def eval_request(case, cat):
    """The request `./sweatcast session` builds from a case's flags."""
    import session
    return {"goal": case["goal"], "minutes": case["minutes"], "method": case.get("method"),
            "level": case.get("level"), "preset": case["preset"],
            "target": session._words(case.get("target")),
            "limits": [session._limit(case["limit"], cat)] if case.get("limit") else [], "avoid": set()}


class Eval(unittest.TestCase):
    """The judged grid in docs/eval/: forty cases over four invented listeners."""

    @classmethod
    def setUpClass(cls):
        cls.cat, cls.sess = catalog.load(), sessions.load()

    def test_cases_are_forty_and_valid(self):
        import session
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
            for t in session._words(c.get("target")):
                self.assertTrue(t in self.cat.patterns or t in self.cat.muscles, (c["id"], t))
            if c.get("method"):
                self.assertIn(c["method"], self.sess.methods, c["id"])
            self.assertEqual(bool(c.get("limit")), i % 3 == 0, f"{c['id']}: every third case, and only those, has a limit")
            if c.get("limit"):
                lim = session._limit(c["limit"], self.cat)
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

    def test_next_method_when_the_first_cannot_fill_its_slots(self):
        # advanced, low back off limits, bodyweight, no single-leg work today: a circuit trimmed to its
        # first six patterns fits the goal best but has only a squat and a push; paired-sets adds a
        # vertical push, so it is tried next
        import copy
        import session
        sess = copy.deepcopy(self.sess)
        block = sess.methods["circuit"].blocks[0]
        block["patterns"] = block["patterns"][:6]
        profile, health, log = eval_listener("c")
        request = {"goal": "general", "minutes": 30, "preset": "bodyweight", "avoid": {"single-leg"}, "limits": []}
        self.assertEqual(sessions.ranked(sess, "general", 30, "advanced", set(), log[-1].format)[0].name, "circuit")
        sk = session.compose(request, self.cat, sess, profile, health, log, TODAY)
        self.assertNotEqual(sk.method.name, "circuit")
        self.assertEqual(sk.why, "circuit did not fit")
        self.assertIn("because circuit did not fit", "\n".join(session.render(sk)))
        with self.assertRaises(session.Unfit):   # asked for by name, no fallback
            session.compose(dict(request, method="circuit"), self.cat, sess, profile, health, log, TODAY)

    def test_every_case_composes(self):
        import session
        _, cases = eval_cases()
        self.assertEqual(len(cases), 40)
        for c in cases:
            profile, health, log = eval_listener(c["listener"])
            with self.subTest(case=c["id"]):
                sk = session.compose(eval_request(c, self.cat), self.cat, self.sess, profile, health, log, TODAY)
                self.assertIsNotNone(sk.method)
                self.assertGreaterEqual(sum(len(slots) for _, slots in sk.blocks), sk.method.min_slots)

    def test_listeners_are_clean(self):
        for name in "abcd":
            home = os.path.join(EVAL, "listeners", name)
            files = [os.path.join(home, f) for f in ("profile.md", "health.md", "log.md", "exercise-science.md")]
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


class Grid(unittest.TestCase):
    """What the second judged run asked of the skeletons, checked over all forty cases."""

    @classmethod
    def setUpClass(cls):
        import session
        cls.cat, cls.sess = catalog.load(), sessions.load()
        cls.sk = {}
        for c in eval_cases()[1]:
            profile, health, log = eval_listener(c["listener"])
            cls.sk[c["id"]] = session.compose(eval_request(c, cls.cat), cls.cat, cls.sess, profile, health, log, TODAY)

    def slots(self, cid):
        return [s for _, ss in self.sk[cid].blocks for s in ss]

    def test_markers_add_up_and_parse(self):
        import session
        for cid, sk in self.sk.items():
            with self.subTest(case=cid):
                lines = session.render_draft(sk)
                self.assertEqual(sum(int(x.split()[1]) for x in lines), sk.minutes * 60)
                self.assertEqual(len(draft.parse("\n".join(lines))), len(lines))

    def test_interval_work_is_never_easy_and_one_machine_stays_together(self):
        for cid, sk in self.sk.items():
            if sk.method.work != "intervals":
                continue
            with self.subTest(case=cid):
                work = [s for s in self.slots(cid) if not s.dose.get("steady")]
                self.assertTrue(all(s.candidates[0][0].effort != "easy" for s in work))
                stations = [tuple(s.candidates[0][0].needs) for s in work]
                runs = [k for i, k in enumerate(stations) if i == 0 or stations[i - 1] != k]
                self.assertEqual(len(runs), len(set(runs)), stations)   # no machine comes back later

    def test_caps_hold(self):
        import session
        for cid, sk in self.sk.items():
            with self.subTest(case=cid):
                for intensity, ss in sk.blocks:
                    cap = session._cap(self.sess, sk.method, intensity, eval_level(cid))
                    if cap is None:
                        continue
                    key = "sets" if "sets" in ss[0].dose else "rounds"
                    self.assertLessEqual(sum(s.dose[key] for s in ss if not s.dose.get("steady")), cap)

    def test_no_slot_repeats_a_movement_while_others_remain(self):
        for cid in self.sk:
            with self.subTest(case=cid):
                leads = [s.candidates[0][0].id for s in self.slots(cid)]
                every = {m.id for s in self.slots(cid) for m, _ in s.candidates}
                if len(every) >= len(leads):
                    self.assertEqual(len(leads), len(set(leads)), leads)

    def test_warmup_is_easy_and_the_lists_do_not_lead_with_the_work(self):
        for cid, sk in self.sk.items():
            with self.subTest(case=cid):
                leads = {s.candidates[0][0].id for s in self.slots(cid)}
                warm = [m for m, _ in sk.extras["warmup"]]
                self.assertTrue(warm)
                self.assertFalse({m.id for m in warm} & leads)
                for m in warm:
                    self.assertNotEqual(m.effort, "hard", m.id)
                    self.assertFalse({"fast", "impact"} & set(m.flags), m.id)
                fin = [m for m, _ in sk.extras["finisher"]]
                self.assertTrue(all(m.effort in ("moderate", "hard") for m in fin))
                if fin:
                    self.assertNotEqual(fin[0].id, warm[0].id)
                    self.assertIsNotNone(sk.finisher_dose)
                self.assertEqual(sk.extras["cooldown"][0][0].patterns[0], "breathing")

    def test_paired_sets_get_a_marker_per_pair_set(self):
        import session
        sk = self.sk["c03"]
        self.assertEqual(sk.method.work, "pairs")
        titles = [x.split("|", 1)[1].strip() for x in session.render_draft(sk)]
        sets = self.slots("c03")[0].dose["sets"]
        self.assertEqual(sum(t.startswith("Pair 1 of") for t in titles), sets)
        self.assertIn(", then ", next(t for t in titles if t.startswith("Pair 1 of")))
        self.assertRegex("\n".join(session.render(sk)), r"rest \d+ s after each pair set")

    def test_printed_rest_is_the_rest_the_slot_holds(self):
        import session
        for cid, sk in self.sk.items():
            if sk.method.work != "sets":
                continue
            for s in self.slots(cid):
                m, d = s.candidates[0][0], s.dose
                held = session.rest_held(s, sk)
                if held is None:
                    continue
                with self.subTest(case=cid, slot=s.pattern):
                    work = m.transition_seconds + d["sets"] * session._work_time(m, d, session._one_side(m, sk))
                    self.assertLessEqual(abs(work + (d["sets"] - 1) * held - s.seconds), 3 * (d["sets"] - 1))

    def test_circuit_rounds_name_their_rest(self):
        import session
        sk = self.sk["c14"]
        self.assertEqual(sk.method.work, "rounds")
        lines = session.render_draft(sk)
        self.assertIn("then rest", lines[1])
        self.assertNotIn("then rest", [x for x in lines if "Round" in x][-1])
        self.assertRegex("\n".join(session.render(sk)), r"block, \d+ s, rest \d+ s between rounds:")

    def test_thin_kits_and_limits_still_vary_intervals(self):
        for cid in ("c30", "c36"):
            with self.subTest(case=cid):
                leads = {s.candidates[0][0].id for s in self.slots(cid)}
                self.assertGreaterEqual(len(leads), 3, leads)
                self.assertNotIn("marching-in-place", {s.candidates[0][0].id for s in self.slots(cid)
                                                       if not s.dose.get("steady")})

    def test_kit_load_ranks_ahead_of_bodyweight(self):
        for cid, pattern, want in (("c05", "squat", "goblet-squat"), ("c19", "squat", "goblet-squat"),
                                   ("c10", "horizontal-pull", "face-pull"), ("c21", "horizontal-pull", "face-pull")):
            with self.subTest(case=cid):
                slot = next(s for s in self.slots(cid) if s.pattern == pattern)
                self.assertEqual(slot.candidates[0][0].id, want)

    def test_target_gets_at_least_half_the_slots(self):
        back = [s.pattern for s in self.slots("c38")]
        self.assertGreaterEqual(back.count("horizontal-pull"), 2, back)
        glutes = [s.candidates[0][0] for s in self.slots("c40")]
        self.assertGreaterEqual(sum("glutes" in m.muscles[:2] for m in glutes) * 2, len(glutes))

    def test_safety_tightenings(self):
        for cid in ("c12", "c33", "c39"):   # low back off limits: no bending or twisting the spine
            with self.subTest(case=cid):
                sk = self.sk[cid]
                every = [m for s in self.slots(cid) for m, _ in s.candidates]
                every += [m for part in sk.extras.values() for m, _ in part]
                self.assertFalse({"spine-flexion", "spine-twist"} & {f for m in every for f in m.flags})
        for cid in ("c05", "c38"):   # delicate neck: no overhead pressing
            with self.subTest(case=cid):
                ids = {m.id for s in self.slots(cid) for m, _ in s.candidates}
                self.assertFalse(ids & {"overhead-press", "seated-shoulder-press"}, ids)

    def test_a_sprint_works_its_own_seconds(self):
        sprint = next(s for s in self.slots("c34") if s.candidates[0][0].id == "bike-seated-sprint")
        m = sprint.candidates[0][0]
        self.assertEqual(sprint.dose["work_seconds"], m.hold_seconds)
        other = next(s for s in self.slots("c34") if s.candidates[0][0].hold_seconds >= 45)
        self.assertEqual(sprint.dose["work_seconds"] + sprint.dose["rest_seconds"],
                         other.dose["work_seconds"] + other.dose["rest_seconds"])   # same interval length

    def test_the_fallback_runs_as_a_circuit(self):
        import session
        for cid in ("c30", "c36"):
            with self.subTest(case=cid):
                sk = self.sk[cid]
                titles = [x.split("|", 1)[1].strip() for x in session.render_draft(sk)][1:-1]
                work = [s for s in self.slots(cid) if not s.dose.get("steady")]
                first = [t for t in titles if t.startswith("Round 1 of")]
                self.assertEqual(len(first), len(work))
                self.assertIn("as a circuit", "\n".join(session.render(sk)))

    def test_circuits_take_no_barbell_lift(self):
        for cid, sk in self.sk.items():
            if sk.method.work == "rounds":
                with self.subTest(case=cid):
                    self.assertFalse(any("barbell" in m.needs for s in self.slots(cid) for m, _ in s.candidates))

    def test_today_limit_says_what_it_means(self):
        self.assertIn("today: calf delicate: light loads only on the calf, no impact or fast work",
                      self.sk["c27"].health)


def eval_level(cid):
    case = next(c for c in eval_cases()[1] if c["id"] == cid)
    return case.get("level") or context.experience(eval_listener(case["listener"])[0])


class Cli(unittest.TestCase):
    def test_usage_on_unknown_goal(self):
        r = run_session(["--goal", "vibes", "--minutes", "30", "--kit", "home"])
        self.assertEqual(r.returncode, 64)
        self.assertIn("strength", r.stderr)

    def test_usage_on_unknown_values(self):
        for args in (["--kit", "castle"], ["--preset", "castle"], ["--equipment", "anvil"],
                     ["--kit", "home", "--method", "flow"], ["--kit", "home", "--limit", "tail=delicate"],
                     ["--kit", "home", "--limit", "wrist=sore"], ["--kit", "home", "--limit", "wrist=delicate:up"],
                     ["--kit", "home", "--target", "wiggle"], ["--kit", "home", "--level", "wizard"],
                     ["--kit", "home", "--avoid", "wobbly"], ["--kit", "home", "--today", "someday"]):
            r = run_session(["--goal", "strength", "--minutes", "30", *args])
            self.assertEqual(r.returncode, 64, args)
            self.assertTrue(r.stderr.strip(), args)

    def test_runs_with_draft(self):
        r = run_session(["--goal", "strength", "--minutes", "30", "--kit", "home", "--draft", "--today", "2026-10-21"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(draft.MARKER.match(r.stdout.splitlines()[0]))
        draft.parse(r.stdout)
        self.assertIn("Health: ", r.stderr)
        self.assertNotIn("Health: ", r.stdout)

    def test_runs_without_draft(self):
        r = run_session(["--goal", "strength", "--minutes", "30", "--kit", "home", "--today", "2026-10-21"])
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        self.assertTrue(lines[0].startswith("Health: "))
        self.assertTrue(any(line.startswith("Method: ") for line in lines))
        self.assertTrue(any(line.startswith("Total: ") for line in lines))

    def test_issues_when_a_limits_row_is_dropped(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            for name in os.listdir(LISTENER):
                src = os.path.join(LISTENER, name)
                (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, os.path.join(home, name))
            path = os.path.join(home, "health.md")
            with open(path) as f:
                text = f.read()
            with open(path, "w") as f:
                f.write(text.replace('level = "delicate"', 'level = "sore"', 1))
            env = dict(os.environ, SWEATCAST_PYTHON=sys.executable, SWEATCAST_HOME=home)
            r = subprocess.run(["sh", os.path.join(ROOT, "sweatcast"), "session", "--goal", "strength", "--minutes",
                                "30", "--kit", "home", "--today", "2026-10-21"],
                               capture_output=True, text=True, env=env, cwd=ROOT)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("health.md: a [[limits]] row was ignored (run ./sweatcast check)", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_issues_when_no_method_fits(self):
        r = run_session(["--goal", "strength", "--minutes", "5", "--kit", "home"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stderr.strip())


if __name__ == "__main__":
    unittest.main()
