"""A held segment's spare time (draft.held_quiet), and the lint's margin on it for a measured or estimated pace."""
import math
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import tts_build  # noqa: E402
from draft import MAX_EXTRA_GAP, HOLD_ROOM, MAX_SILENCE, held_quiet, parse, plan, spread_breaks  # noqa: E402


def paras(body, seconds=60):
    return plan(parse(f"@@ {seconds} | A\n{body}\n")[0])


SET = ("Set up the hinge, back flat. [count 3 go]\n\nPull to the ribs.\n\nHalfway, back stays flat.\n\n"
       "Feel it between the shoulders. [hold]\nLast ten seconds. [cue rest]")


class HeldQuiet(unittest.TestCase):
    def test_how_a_held_segment_spreads_its_spare_time(self):
        """Each row: the spare seconds, the extra each break after the go takes, and the hold's share. Under the
        limit the hold takes it all; past it the breaks take the rest, each up to its cap; the segment keeps its
        length."""
        over = MAX_SILENCE - HOLD_ROOM + 3.0
        for spare, extras, share in ((6.0, [0.0, 0.0, 0.0], 6.0),
                                     (over, [1.0, 1.0, 1.0], MAX_SILENCE - HOLD_ROOM),
                                     (20.0, [MAX_EXTRA_GAP] * 3, 20.0 - 3 * MAX_EXTRA_GAP)):
            with self.subTest(spare=spare):
                got_extras, got_share = held_quiet(paras(SET), spare)
                self.assertEqual(got_extras, extras)
                self.assertAlmostEqual(got_share, share)
                self.assertAlmostEqual(sum(got_extras) + got_share, spare)
        self.assertEqual(held_quiet(paras("Go now. [count 3 go] Keep it up. [hold] And rest. [cue rest]"), 12.0),
                         ([], 12.0))   # one paragraph has no breaks to spread into
        # the setup before the go and the lines after the last hold keep their place
        self.assertEqual(spread_breaks(paras("Grab the bells.\n\nSet up the hinge. [count 3 go]\n\nPull to the ribs."
                                             "\n\nStay with it. [hold]\n\nTen seconds left.")), [2, 3])
        # a break beside a hold's silence is left alone
        self.assertEqual(spread_breaks(paras("Start easy.\n\nKeep going. [hold]\n\nStill easy.\n\nNearly there. "
                                             "[hold]\nAnd stop.")), [1, 3])

    def test_the_lint_checks_holds_as_if_the_voice_ran_fast(self):
        """A measured voice gets a small margin; an estimated pace a larger one."""
        v = {"name": "x", "key": "x", "engine": "fish", "model": "m"}
        talk = " ".join(["Steady now, smooth circles, breathe out long and keep the shoulders soft."] * 12)
        with mock.patch("voices.pace", return_value=(14.5, True)):
            spare = tts_build.lint(parse(f"@@ 120 | A\n{talk} [hold] Last few seconds now.\n"), v,
                                   headroom=False).rows[0].quiet
            seconds = math.ceil(120 - spare + MAX_SILENCE - 1.0)   # one hold of seven to eight seconds as predicted
            segs = parse(f"@@ {seconds} | A\n{talk} [hold] Last few seconds now.\n")
            exact = tts_build.lint(segs, v, headroom=False).rows[0].clip_issues
            margin = tts_build.lint(segs, v).rows[0].clip_issues
        self.assertFalse(any("of silence" in i for i in exact), exact)
        self.assertTrue(any("of silence" in i for i in margin), margin)

        v = dict(v, engine="chatterbox")
        talk = ("Go now, quick legs and steady breathing, the hips quiet on the seat and the hands soft on the bars "
                "while you hold that pace. [hold] And ease off now, let the legs slow down and the breathing settle "
                "back to easy.")
        segs = parse(f"@@ 19 | A\n{talk}\n")
        with mock.patch("voices.pace", return_value=(14.5, True)):
            measured = tts_build.lint(segs, v).rows[0].clip_issues
        with mock.patch("voices.pace", return_value=(14.5, False)):
            estimated = tts_build.lint(segs, v).rows[0].clip_issues
        self.assertFalse(any("of silence" in i for i in measured), measured)
        self.assertTrue(any("of silence" in i for i in estimated), estimated)


if __name__ == "__main__":
    unittest.main()
