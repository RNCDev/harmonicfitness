"""Checks the engine holds on a written script: light loads under a limit, a second session in
a day, a whole-body session's patterns, and claims the coach can't make."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import brief  # noqa: E402
import catalog  # noqa: E402
import draft  # noqa: E402
import menu  # noqa: E402
import paths  # noqa: E402
import repeats  # noqa: E402
import sessionlog  # noqa: E402
import tts_build  # noqa: E402

CAT = catalog.load()
KNEE = {"request": {"limits": ["knee=delicate:left"]}}


def segs(text):
    return draft.parse("movements: farmer carry\n" + text)


class HeavyUnderALimit(unittest.TestCase):
    def test_heavy_with_a_movement_that_loads_a_limited_area_is_refused(self):
        found = menu.load_problems(CAT, KNEE, segs("@@ 60 | Carry\nPick up a heavy pair for the farmer carry, and walk.\n"))
        self.assertEqual(len(found), 1)
        self.assertIn('"heavy" with farmer carry, which loads today\'s limited knee', found[0])

    def test_a_plural_or_a_setup_in_the_rest_before_is_caught(self):
        self.assertTrue(menu.load_problems(CAT, KNEE, segs("@@ 60 | Carries\nTwo heavy suitcase carries now.\n")))
        two = segs("@@ 45 | Rest\nPick up one heavy dumbbell in your right hand.\n\n"
                   "@@ 60 | Set one\nSuitcase carry, walk tall, short steps.\n")
        found = menu.load_problems(CAT, KNEE, two)
        self.assertEqual(len(found), 1)
        self.assertIn('segment "Rest"', found[0])
        after = segs("@@ 60 | Set one\nSuitcase carry, walk tall.\n\n@@ 60 | Carry set 2\nHold that heavy bell steady.\n")
        self.assertIn('segment "Carry set 2"', menu.load_problems(CAT, KNEE, after)[0])

    def test_plurals_ending_in_y_are_names(self):
        for text, mid in (("farmer carries", "farmer-carry"), ("suitcase carries", "suitcase-carry"),
                          ("push-ups", "push-up"), ("goblet squats", "goblet-squat")):
            self.assertEqual([m for m, _, _ in menu.mentions(CAT, text)], [mid], text)

    def test_light_words_a_story_or_no_limit_pass(self):
        for text in ("@@ 60 | Carry\nNothing too heavy on the farmer carry today, light pair.\n",
                     "@@ 60 | Carry\nA light pair for the farmer carry.\n[story] She lifted heavy at the farmer carry worlds. [/story]\n"):
            self.assertEqual(menu.load_problems(CAT, KNEE, segs(text)), [], text)
        self.assertEqual(menu.load_problems(CAT, {"request": {}}, segs("@@ 60 | C\nA heavy farmer carry.\n")), [])



class SecondSession(unittest.TestCase):
    def test_a_session_earlier_today_is_named_and_programmed_around(self):
        today = datetime.date(2026, 11, 1)
        e = sessionlog.Session("2026-11-01", 30, "home", "Coach Freya", ["goblet squat", "romanian deadlift"], "x")
        lines = "\n".join(brief._week_lines(CAT, [e], today, []))
        self.assertIn("A second session today", lines)
        self.assertIn("hinge", lines)
        yesterday = "\n".join(brief._week_lines(CAT, [e], today + datetime.timedelta(days=1), []))
        self.assertNotIn("second session", yesterday)


class SeenClaims(unittest.TestCase):
    def test_more_claims_the_coach_cannot_make(self):
        for line in ("Solid work today, all executed with clean form.", "Your left knee is staying completely protected.",
                     "Clean dumbbell pressing and crisp deadlifts today."):
            self.assertTrue(repeats.seen_claims(f"movements: x\n@@ 30 | Close\n{line}\n"), line)
        self.assertEqual(repeats.seen_claims("movements: x\n@@ 30 | Close\nKeep your form clean on every rep.\n"), [])
        self.assertTrue(repeats.seen_claims("movements: x\n@@ 30 | Close\nSolid discipline across all three rounds.\n"))

    def test_three_stories_in_one_rest_are_a_pile(self):
        three = "movements: x\n@@ 90 | Rest\n[story] One. [/story]\n\n[story] Two. [/story]\n\n[story] Three. [/story]\n"
        self.assertEqual(len(repeats.stacked_stories(three)), 1)
        self.assertEqual(repeats.stacked_stories(three.replace("\n\n[story] Three. [/story]", "")), [])


class ToldToday(unittest.TestCase):
    def test_the_plan_names_what_an_earlier_session_told_today(self):
        import content
        import context
        today = datetime.date(2026, 11, 1)
        items = [{"date": "2026-11-01", "topic": "Hockey", "format": "on_this_day", "title": "Jacques Plante's mask"},
                 {"date": "2026-10-30", "topic": "Hockey", "format": "quick_hit", "title": "Flyers win"}]
        text = "\n".join(content.plan(25, today, content.recipe(), context.Profile({}, "## Topics\n- Hockey\n", None), items, []))
        part = text.split("## Already told today")[1].split("##")[0]
        self.assertIn("Jacques Plante's mask", part)
        self.assertNotIn("Flyers win", part)


if __name__ == "__main__":
    unittest.main()


class ThirtyMinutes(unittest.TestCase):
    """0.49.4: thirty-minute scripts."""

    def test_seen_claims_widen_and_a_rep_target_isnt_one(self):
        import repeats
        for line in ("Great execution on the pull block.", "You held your posture clean throughout.",
                     "You are moving through this circuit with fantastic control.", "Outstanding carry."):
            self.assertTrue(repeats.seen_claims(f"movements: x\n@@ 30 | A\n{line}\n"), line)
        for line in ("Target is eight to ten clean reps, with two in reserve.", "Keep your back straight.",
                     "Two more crisp reps, lock out at the top.", "Halfway there, five more smooth reps.",
                     "Great work, rest now."):
            self.assertEqual(repeats.seen_claims(f"movements: x\n@@ 30 | A\n{line}\n"), [], line)

    def test_a_feeds_sheet_is_as_fresh_as_its_header(self):
        import datetime as dt
        import tempfile
        import feeds
        now = dt.datetime.now().astimezone()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.md")
            for hours, fresh in ((-1, True), (-4, False), (2, False)):   # an hour ago; four; dated ahead (UTC)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# Feeds, {now + dt.timedelta(hours=hours):%A %B %d, %Y %H:%M}\n")
                self.assertEqual(feeds.fresh_sheet(path, now), fresh, hours)   # the file's own time is now

    def test_off_slot_segments_say_fix_only_when_the_total_is_off(self):
        from unittest import mock
        import tts_build
        v = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}
        words = " ".join(["Keep breathing slowly and steadily."] * 9)
        balanced = draft.parse(f"@@ 20 | A\n{words} {words}\n\n@@ 40 | B\n{words}\n")   # long, then short
        with mock.patch("voices.pace", return_value=(14.0, True)):
            report = tts_build.lint(balanced, v)
        said = "\n".join(tts_build.render_report(report))
        self.assertFalse(report.total_off)
        self.assertEqual([r.flag for r in report.rows], ["long", "short"])
        self.assertNotIn("trim it", said)
        self.assertIn("leave them as they are", said)
        with mock.patch("voices.pace", return_value=(4.0, True)):   # far too slow: the total is off
            off = tts_build.lint(balanced, v)
        self.assertTrue(off.total_off)
        self.assertIn("trim it", "\n".join(tts_build.render_report(off)))


class ThirtyMinutesMore(unittest.TestCase):
    """0.49.6: a list of figures, a full-body session's patterns, and the words that land a short draft."""

    def test_a_list_of_figures_is_warned_and_a_point_isnt_one(self):
        many = ("movements: x\n@@ 60 | Rest\n[story] Revenue was sixteen point three billion, up from one point one "
                "six billion; cash flow three point nine billion on eleven point six billion booked, and eighty "
                "billion valued. [/story]\n")
        self.assertTrue(repeats.crowded_figures(many))
        few = "movements: x\n@@ 60 | Rest\n[story] That's the point: two goals in the third, sixteen billion. [/story]\n"
        self.assertEqual(repeats.crowded_figures(few), [])

    def test_a_full_body_session_names_the_pattern_it_left_out(self):
        text = "movements: goblet squat, dumbbell floor press, dumbbell romanian deadlift\n@@ 60 | A\nGo.\n"
        ids = [{"id": i} for i in ("goblet-squat", "dumbbell-floor-press", "dumbbell-romanian-deadlift",
                                   "dumbbell-row")]
        menu_ = {"request": {"goal": "general"}, "movements": ids}
        self.assertIn("no pull", " ".join(repeats.missing_patterns(CAT, text, menu_)))
        self.assertEqual(repeats.missing_patterns(CAT, text, dict(menu_, movements=ids[:3])), [])   # none allowed
        self.assertEqual(repeats.missing_patterns(CAT, text, dict(menu_, request={"goal": "strength"})), [])

    def test_a_short_draft_is_told_how_many_words_and_where(self):
        from unittest import mock
        import tts_build
        v = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}
        w = " ".join(["Keep breathing slowly and steadily."] * 6)
        segs = draft.parse(f"@@ 60 | A\n{w}\n\n@@ 60 | B\n{w} {w}\n\n@@ 90 | C\n{w}\n")
        with mock.patch("voices.pace", return_value=(14.0, True)):
            said = "\n".join(tts_build.render_report(tts_build.lint(segs, v)))
        self.assertRegex(said, r"To land on plan, add about \d+ words in one edit: #3 \+\d+")


class PaceSample(unittest.TestCase):
    def test_the_pace_sample_is_speakable_coaching(self):
        """The sample a skeleton's budgets are read from: a voice could read every line of it, and it mixes
        a set's cues, a rest and a story, as drafts do."""
        with open(paths.PACE_SAMPLE, encoding="utf-8") as f:
            text = f.read()
        segments = draft.parse(text)
        issues = [i for seg in segments for n, line in seg["lines"] for i in tts_build.lint_line(n, line)]
        self.assertEqual(issues, [])
        self.assertTrue(any("[count" in line for seg in segments for _, line in seg["lines"]))
        self.assertIn("[story]", text)
        self.assertGreater(sum(tts_build.word_count(seg["lines"]) for seg in segments), 200)
