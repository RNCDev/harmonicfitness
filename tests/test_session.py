"""Checks for the session methods and dose rules (knowledge/sessions.toml) and for the composer
(tools/session.py), which runs against a small catalog and an invented listener in tests/fixtures/."""
import datetime
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402
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


def compose_for(health=None, **request):
    """session.compose for a request against the fixture catalog and the invented listener."""
    import session
    if not {"preset", "equipment"} & set(request):
        request.setdefault("kit", "home")
    cat = catalog.load(os.path.join(FIXTURES, "movements.toml"))
    return session.compose(request, cat, sessions.load(), context.profile(os.path.join(LISTENER, "profile.md")),
                           health or context.health(os.path.join(LISTENER, "health.md")),
                           context.sessions(os.path.join(LISTENER, "log.md")), TODAY)


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

    def test_last_session_movements_rank_after_fresh_ones(self):
        sk = compose_for(goal="strength", minutes=30)
        core = next(s for _, slots in sk.blocks for s in slots if s.pattern == "anti-extension")
        ids = [m.id for m, _ in core.candidates]
        self.assertLess(ids.index("one-arm-plank"), ids.index("dead-bug"))   # dead bug was in the last session
        self.assertNotIn("fresh", dict((m.id, r) for m, r in core.candidates)["dead-bug"])

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

    def test_second_pass_before_spare_and_warning_past_a_tenth(self):
        sk = compose_for(goal="strength", minutes=60, equipment={"mat"}, level="novice")
        self.assertWithinTolerance(sk, 60)
        patterns = [s.pattern for _, ss in sk.blocks for s in ss]
        self.assertGreater(len(patterns), len(set(patterns)))   # a second pass through the patterns
        lunges = [s for _, ss in sk.blocks for s in ss if s.pattern == "lunge"]
        self.assertNotEqual(lunges[0].candidates[0][0].id, lunges[1].candidates[0][0].id)
        self.assertEqual(sk.warmup, sk.method.warmup["seconds"][1])
        self.assertTrue(any(w.startswith("method filled early:") for w in sk.warnings), sk.warnings)
        self.assertFalse(any("filled early" in w for w in compose_for(goal="strength", minutes=30).warnings))

    def test_ranking_with_limits_counts_only_limited_areas(self):
        sk = compose_for(goal="strength", minutes=30, limits=[catalog.Limit("knee", "both", "delicate", [], [], "")])
        hinge = next(s for _, ss in sk.blocks for s in ss if s.pattern == "hinge")
        # wrist and knee are limited: the bridge loads the knee (1); the deadlift loads the wrist (1); catalog order breaks the tie
        self.assertEqual([m.id for m, _ in hinge.candidates][:2], ["glute-bridge", "dumbbell-romanian-deadlift"])
        h = context.Health({}, "")
        sk = compose_for(goal="strength", minutes=30, health=h, limits=[catalog.Limit("knee", "both", "delicate", [], [], "")])
        hinge = next(s for _, ss in sk.blocks for s in ss if s.pattern == "hinge")
        self.assertEqual(hinge.candidates[0][0].id, "dumbbell-romanian-deadlift")   # no knee load, despite heavy hips

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

    def test_issues_when_no_method_fits(self):
        r = run_session(["--goal", "strength", "--minutes", "5", "--kit", "home"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(r.stderr.strip())


if __name__ == "__main__":
    unittest.main()
