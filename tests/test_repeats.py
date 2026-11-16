"""The repeat check (tools/repeats.py): sentences a draft says word for word from the last few workouts."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import catalog  # noqa: E402
import helpers  # noqa: E402
import repeats  # noqa: E402


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Repeats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = helpers.home(os.path.join(self.tmp.name, "me"))
        self.root = self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)

    def draft(self, stem, body):
        path = os.path.join(self.root, "workouts", stem, f"{stem}.draft.txt")
        write(path, f"movements: dead bug\n@@ 60 | A\n{body}\n")
        return path

    def test_a_sentence_said_before_is_named_and_safety_lines_are_not(self):
        self.draft("2026-10-20-strength-25", "This is the one that counts, so make it yours. "
                   "Sharp pain means stop that movement right away. Short one.")
        now = self.draft("2026-10-23-strength-25", "Good morning. This is the one that counts, so make it yours! "
                         "Sharp pain means stop that movement right away. Short one. [story] A brand new story "
                         "about the city today. [/story]")
        with open(now, encoding="utf-8") as f:
            got = repeats.repeats(now, f.read())
        self.assertEqual(len(got), 1, got)
        self.assertIn("This is the one that counts", got[0])
        self.assertIn("2026-10-20-strength-25", got[0])

    def test_only_earlier_workouts_count_and_a_draft_elsewhere_has_none(self):
        later = self.draft("2026-10-25-strength-25", "This is the one that counts, so make it yours.")
        now = self.draft("2026-10-23-strength-25", "This is the one that counts, so make it yours.")
        with open(now, encoding="utf-8") as f:
            self.assertEqual(repeats.repeats(now, f.read()), [])
        self.assertEqual(repeats.earlier(os.path.join(self.tmp.name, "x.draft.txt")), [])
        self.assertTrue(later)


class SameMovements(unittest.TestCase):
    """A draft whose movements are mostly a recent workout's is named (programming.md, Variety)."""
    SAME = "arm circles, leg swings, inchworm, reverse lunge, overhead press, kettlebell deadlift, box breathing"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = helpers.home(os.path.join(self.tmp.name, "me"))
        self.root = self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)
        self.cat = catalog.load()

    def draft(self, stem, movements):
        path = os.path.join(self.root, "workouts", stem, f"{stem}.draft.txt")
        write(path, f"movements: {movements}\n@@ 60 | A\nGo.\n")
        return path

    def check(self, path):
        with open(path, encoding="utf-8") as f:
            return repeats.same_movements(self.cat, path, f.read())

    def test_a_rerun_of_a_recent_workout_is_named(self):
        self.draft("2026-11-08-strength-30", self.SAME)
        got = self.check(self.draft("2026-11-16-strength-40", self.SAME + ", bent-over row"))
        self.assertEqual(len(got), 1, got)
        self.assertIn("2026-11-08", got[0])
        self.assertIn("overhead press", got[0])

    def test_a_fresh_session_a_same_day_rewrite_and_an_older_one_pass(self):
        self.draft("2026-11-01-strength-30", self.SAME)   # three days back: only the last two days count
        self.draft("2026-11-05-strength-30", "cat-cow, goblet squat, push-up, romanian deadlift, bent-over row")
        self.draft("2026-11-08-strength-30", "wall sit, floor press, farmer carry, dead bug, child's pose")
        self.draft("2026-11-16-strength-40", self.SAME)   # today's earlier take isn't compared
        self.assertEqual(self.check(self.draft("2026-11-16-strength-40-2", self.SAME)), [])


class SeenClaims(unittest.TestCase):
    def test_praise_for_what_the_coach_cant_see_is_named(self):
        for line in ("That set looked smoother.", "Best set yet, Sam.", "No leaning on the rails, not once.",
                     "Your back stayed flat every set.", "I can see you working.", "That's where we want it.",
                     "Eight efforts and a strong first ride.", "You nailed it.", "What a great climb."):
            with self.subTest(line=line):
                self.assertEqual(len(repeats.seen_claims(f"@@ 30 | A\nGood. {line}\n")), 1)

    def test_a_rests_praise_for_how_it_went_is_named(self):
        """0.82.0: the lines a 40-minute session's rests said, none named then."""
        for line in ("Every single movement pattern is dialed in, and the tempo has been rock solid.",
                     "You're moving with tremendous focus today.",
                     "That was sharp, controlled work across all five stations.",
                     "You crushed all three rounds of that circuit.",
                     "Outstanding strength, sharp control, and great focus across all fifteen sets."):
            with self.subTest(line=line):
                self.assertEqual(len(repeats.seen_claims(f"@@ 30 | A\n{line}\n")), 1)
        for line in ("Halfway through the reps, torso rock solid.", "Keep the tempo rock solid.",
                     "Get your stance dialed in before the go.", "That was thirty heavy reps logged today.",
                     "Mighty proud of your work today."):
            with self.subTest(line=line):
                self.assertEqual(repeats.seen_claims(f"@@ 30 | A\n{line}\n"), [])

    def test_questions_plans_and_stories_pass(self):
        text = ("@@ 30 | A\nHow did that one feel? If it was a grind, stay at this weight. That's all eight efforts "
                "done, and a good session to build on next week starts here. "
                "[story] His best lap yet came in the rain, and the crowd saw it. [/story]\n")
        self.assertEqual(repeats.seen_claims(text), [])


class Balance(unittest.TestCase):
    """0.82.0: the share of the words told as stories, against the content plan's."""

    def test_the_share_counts_spoken_words_inside_and_outside_the_stories(self):
        text = ("movements: x\n@@ 60 | Rest\nBreathe in. [pause 3s] And out, slow and easy.\n"
                "[story] The Devils won seven to four in Washington. [/story]\n")
        self.assertEqual(repeats.story_share(text), (8, 15))

    def test_a_draft_of_mostly_instruction_is_named(self):
        coaching = " ".join(["Drive through the heels."] * 12)
        text = f"movements: x\n@@ 60 | Rest\n{coaching} [story] A short story here. [/story]\n"
        self.assertTrue(repeats.story_balance(text, 0.5, 3))
        even = f"movements: x\n@@ 60 | Rest\nDrive through the heels. [story] {coaching} [/story]\n"
        self.assertEqual(repeats.story_balance(even, 0.5, 3), [])
        self.assertEqual(repeats.story_balance(text, 0.0, 3), [])   # no aim, no warning

    def test_a_skeleton_of_counted_sets_is_named_by_its_plan(self):
        counted = "@@ 40 | Squat set {n}\n[count 3 go] [reps 8]\n@@ 60 | Rest\n"
        timed = "@@ 45 | Bugs set {n}\n[count 3 go] [story] [/story]\n@@ 60 | Rest\n"
        lean = "movements: x\n" + "".join(counted.format(n=n) for n in range(4)) + timed.format(n=1)
        self.assertIn("marks 1 timed set(s)", repeats.story_balance(lean, 0.5, 3)[0])
        full = "movements: x\n" + counted.format(n=1) + "".join(timed.format(n=n) for n in range(3))
        self.assertEqual(repeats.story_balance(full, 0.5, 3), [])


if __name__ == "__main__":
    unittest.main()
