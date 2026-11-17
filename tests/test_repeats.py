"""The seen-claims check (tools/repeats.py): a line praising what the coach can't see is named."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import repeats  # noqa: E402


class SeenClaims(unittest.TestCase):
    def test_praise_for_what_the_coach_cant_see_is_named(self):
        """Each row: a line, and whether the check names it. Questions, plans, form cues and stories pass."""
        named = ("That set looked smoother.", "Best set yet, Sam.", "No leaning on the rails, not once.",
                 "Your back stayed flat every set.", "I can see you working.", "That's where we want it.",
                 "Eight efforts and a strong first ride.", "You nailed it.", "What a great climb.",
                 # 0.82.0: the lines a 40-minute session's rests said, none named then
                 "Every single movement pattern is dialed in, and the tempo has been rock solid.",
                 "You're moving with tremendous focus today.",
                 "That was sharp, controlled work across all five stations.",
                 "You crushed all three rounds of that circuit.",
                 "Outstanding strength, sharp control, and great focus across all fifteen sets.")
        passed = ("Halfway through the reps, torso rock solid.", "Keep the tempo rock solid.",
                  "Get your stance dialed in before the go.", "That was thirty heavy reps logged today.",
                  "Mighty proud of your work today.",
                  "How did that one feel? If it was a grind, stay at this weight. That's all eight efforts "
                  "done, and a good session to build on next week starts here. "
                  "[story] His best lap yet came in the rain, and the crowd saw it. [/story]")
        for line, want in [(x, 1) for x in named] + [(x, 0) for x in passed]:
            with self.subTest(line=line):
                self.assertEqual(len(repeats.seen_claims(f"@@ 30 | A\n{line}\n")), want)


if __name__ == "__main__":
    unittest.main()
