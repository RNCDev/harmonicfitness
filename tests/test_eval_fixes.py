"""What the 2026-11-01 script evals found and the engine now holds: light loads under a limit, a second session in
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
import repeats  # noqa: E402
import sessionlog  # noqa: E402

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
