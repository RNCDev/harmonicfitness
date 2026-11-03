"""A held segment's spare time (draft.held_quiet), a web voice's measured count beat (voices.record_beat), and the
loudness measurement encode() reads from ebur128 (render.loudness_stats)."""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import draft  # noqa: E402
from draft import MAX_EXTRA_GAP, HOLD_ROOM, MAX_SILENCE, held_quiet, parse, plan, spread_breaks  # noqa: E402


def paras(body, seconds=60):
    return plan(parse(f"@@ {seconds} | A\n{body}\n")[0])


SET = ("Set up the hinge, back flat. [count 3 go]\n\nPull to the ribs.\n\nHalfway, back stays flat.\n\n"
       "Feel it between the shoulders. [hold]\nLast ten seconds. [cue rest]")


class HeldQuiet(unittest.TestCase):
    def test_the_holds_take_it_all_while_under_the_limit(self):
        extras, share = held_quiet(paras(SET), 6.0)
        self.assertEqual(extras, [0.0, 0.0, 0.0])
        self.assertEqual(share, 6.0)

    def test_past_the_limit_the_talk_s_breaks_take_the_rest(self):
        spare = MAX_SILENCE - HOLD_ROOM + 3.0
        extras, share = held_quiet(paras(SET), spare)
        self.assertEqual(extras, [1.0, 1.0, 1.0])   # every break after the go, up to the hold's paragraph
        self.assertAlmostEqual(share, MAX_SILENCE - HOLD_ROOM)
        self.assertAlmostEqual(sum(extras) + share, spare)   # the segment keeps its length

    def test_each_break_takes_at_most_its_cap_and_the_hold_the_rest(self):
        extras, share = held_quiet(paras(SET), 20.0)
        self.assertEqual(extras, [MAX_EXTRA_GAP] * 3)
        self.assertAlmostEqual(share, 20.0 - 3 * MAX_EXTRA_GAP)   # still over the limit: the lint says so

    def test_the_setup_before_the_go_and_the_lines_after_the_last_hold_keep_their_place(self):
        body = ("Grab the bells.\n\nSet up the hinge. [count 3 go]\n\nPull to the ribs.\n\nStay with it. [hold]\n\n"
                "Ten seconds left.")
        self.assertEqual(spread_breaks(paras(body)), [2, 3])

    def test_a_break_beside_a_hold_s_silence_is_left_alone(self):
        body = "Start easy.\n\nKeep going. [hold]\n\nStill easy.\n\nNearly there. [hold]\nAnd stop."
        self.assertEqual(spread_breaks(paras(body)), [1, 3])

    def test_one_paragraph_has_no_breaks_to_spread_into(self):
        extras, share = held_quiet(paras("Go now. [count 3 go] Keep it up. [hold] And rest. [cue rest]"), 12.0)
        self.assertEqual((extras, share), ([], 12.0))

    def test_the_render_lays_it_out_as_the_lint_predicts(self):
        import audio
        from engines import SR
        segs = parse("@@ 16 | A\nLine one here.\n\nLine two here.\n\nLine three here.\n\n"
                     "Line four here. [hold] Last words now.\n")
        quiet = []
        pcm, _, drift = audio.assemble(segs, lambda text: b"\x01\x00" * SR, quiet=quiet)
        self.assertEqual(quiet, [])   # a single hold would have held about ten seconds
        self.assertAlmostEqual(len(pcm) / 2 / SR, 16.0, places=2)
        self.assertAlmostEqual(drift, 0.0, places=3)


class MeasuredMargin(unittest.TestCase):
    def test_a_measured_voice_s_holds_are_checked_as_if_it_ran_a_little_fast(self):
        import tts_build
        v = {"name": "x", "key": "x", "engine": "fish", "model": "m"}
        import math
        talk = " ".join(["Steady now, smooth circles, breathe out long and keep the shoulders soft."] * 12)
        segs = parse(f"@@ 120 | A\n{talk} [hold] Last few seconds now.\n")
        with mock.patch("voices.pace", return_value=(14.5, True)):
            spare = tts_build.lint(segs, v, headroom=False).rows[0].quiet
            seconds = math.ceil(120 - spare + MAX_SILENCE - 1.0)   # one hold of seven to eight seconds as predicted
            segs = parse(f"@@ {seconds} | A\n{talk} [hold] Last few seconds now.\n")
            exact = tts_build.lint(segs, v, headroom=False).rows[0].clip_issues
            margin = tts_build.lint(segs, v).rows[0].clip_issues
        self.assertFalse(any("of silence" in i for i in exact), exact)
        self.assertTrue(any("of silence" in i for i in margin), margin)


class CountBeat(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pace = os.path.join(self.tmp.name, "pace.json")
        self.v = {"name": "Coach X", "key": "k1", "engine": "fish", "model": "s2", "backend": "cloud",
                  "pace_file": self.pace}
        with open(self.pace, "w", encoding="utf-8") as f:
            json.dump({"k1|fish|s2": {"name": "Coach X", "weight": 1600.0, "seconds": 100.0}}, f)

    def test_a_measured_beat_times_the_count_as_the_voice_says_it(self):
        import tts_build
        import voices
        self.assertIsNone(voices.beat(self.v))
        self.assertEqual(tts_build.mark_seconds("[count 3 go]", self.v), 4 * draft.BEAT)
        voices.record_beat(self.v, 5, 2.6)   # "Three, two, one, go." and "Rest.": 2.1 s and 0.5 s
        self.assertAlmostEqual(voices.beat(self.v), 0.52)
        self.assertAlmostEqual(tts_build.mark_seconds("[count 3 go]", self.v), 4 * 0.52)
        with open(self.pace, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["k1|fish|s2"]["weight"], 1600.0)   # the pace is left as it was

    def test_a_beat_outside_any_voice_s_range_is_ignored(self):
        import voices
        voices.record_beat(self.v, 4, 0.2)
        self.assertIsNone(voices.beat(self.v))

    def test_nothing_is_recorded_before_the_voice_has_a_pace(self):
        import voices
        v = dict(self.v, key="k2")
        voices.record_beat(v, 4, 2.0)
        self.assertIsNone(voices.beat(v))

    def test_the_render_measures_the_cached_counts(self):
        import render
        from engines import SR
        segs = parse("@@ 30 | A\nGo now. [count 3 go] Keep going. [cue rest]\n\nAgain. [count 3 go]\n")
        files = {}

        def cache_path(text):
            return files.setdefault(text, os.path.join(self.tmp.name, f"{len(files)}.pcm"))
        for text, secs in (("Three, two, one, go.", 2.0), ("Rest.", 0.5)):
            with open(cache_path(text), "wb") as f:
                f.write(b"\x00\x00" * int(secs * SR))
        with mock.patch.object(render, "record_beat") as rec:
            render.measure_beat(segs, self.v, cache_path)
        pieces, secs = rec.call_args.args[1:]
        self.assertEqual(pieces, 9)                # four, one and four pieces
        self.assertAlmostEqual(secs, 4.5)


class LoudnessStats(unittest.TestCase):
    EBUR128 = """[Parsed_ebur128_1 @ 0x1] Summary:

  Integrated loudness:
    I:         -23.1 LUFS
    Threshold: -33.3 LUFS

  Loudness range:
    LRA:         5.1 LU
    Threshold: -44.1 LUFS
    LRA low:   -27.6 LUFS
    LRA high:  -22.5 LUFS

  True peak:
    Peak:       -4.3 dBFS
"""

    def test_ebur128_s_summary_gives_loudnorm_what_it_needs(self):
        import render
        self.assertEqual(render.loudness_stats(self.EBUR128),
                         {"input_i": "-23.1", "input_tp": "-4.3", "input_lra": "5.1", "input_thresh": "-33.3",
                          "target_offset": "0"})

    def test_a_silent_workout_s_summary_is_a_message(self):
        import errors
        import render
        with self.assertRaises(errors.PROBLEMS):
            render.loudness_stats(self.EBUR128.replace("-23.1 LUFS", "-inf LUFS"))


if __name__ == "__main__":
    unittest.main()
