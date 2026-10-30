"""The repeat check (tools/repeats.py): sentences a draft says word for word from the last few workouts."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

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


class SeenClaims(unittest.TestCase):
    def test_praise_for_what_the_coach_cant_see_is_named(self):
        for line in ("That set looked smoother.", "Best set yet, Sam.", "No leaning on the rails, not once.",
                     "Your back stayed flat every set.", "I can see you working."):
            with self.subTest(line=line):
                self.assertEqual(len(repeats.seen_claims(f"@@ 30 | A\nGood. {line}\n")), 1)

    def test_questions_plans_and_stories_pass(self):
        text = ("@@ 30 | A\nHow did that one feel? If it was a grind, stay at this weight. "
                "[story] His best lap yet came in the rain, and the crowd saw it. [/story]\n")
        self.assertEqual(repeats.seen_claims(text), [])


if __name__ == "__main__":
    unittest.main()
