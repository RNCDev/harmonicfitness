"""Fast checks for the text and timing logic. No models, no audio rendering.

    python3 -m unittest discover tests
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import coverage  # noqa: E402
import render  # noqa: E402
import tts_build  # noqa: E402
from render import SR, assemble, chime, silence  # noqa: E402
from tts_build import CHIME_SECONDS, PARAGRAPH_GAP, lint_line, parse, plan, spans, word_count  # noqa: E402


def secs(pcm):
    return len(pcm) / 2 / SR


class Parse(unittest.TestCase):
    def test_segments_and_paragraphs(self):
        segs = parse("@@ 60 | Opening\nHello there.\nStill one paragraph.\n\nSecond one.\n@@ 30 | Next\nGo.\n")
        self.assertEqual([(s["seconds"], s["label"]) for s in segs], [(60, "Opening"), (30, "Next")])
        self.assertEqual(plan(segs[0]), [[("Hello there. Still one paragraph.", 0.0)], [("Second one.", 0.0)]])

    def test_text_before_first_marker_is_an_error(self):
        with self.assertRaises(SystemExit):
            parse("stray words\n@@ 60 | A\nHi.\n")

    def test_no_markers_is_an_error(self):
        with self.assertRaises(SystemExit):
            parse("Just text.\n")


class Spans(unittest.TestCase):
    def test_pause_units_and_default(self):
        self.assertEqual(spans("Set up. [pause 3s] Go. [pause 500ms] Now [pause] end"),
                         [("Set up.", 3.0), ("Go.", 0.5), ("Now", tts_build.PAUSE_DEFAULT), ("end", 0.0)])

    def test_pause_is_capped(self):
        self.assertEqual(spans("Rest. [pause 30s]"), [("Rest.", tts_build.PAUSE_MAX)])

    def test_leading_and_back_to_back_pauses(self):
        self.assertEqual(spans("[pause 2s] Breathe."), [("", 2.0), ("Breathe.", 0.0)])
        self.assertEqual(spans("Hold. [pause 2s] [pause 3s] Out."), [("Hold.", 5.0), ("Out.", 0.0)])


class Lint(unittest.TestCase):
    def test_clean_line(self):
        self.assertEqual(lint_line(1, "Three sets of ten. [pause 3s] Three... two... one... switch."), [])

    def test_catches_tts_hazards(self):
        joined = " ".join(lint_line(1, "Do 3 sets, 25 lbs e.g. # now"))
        for expected in ("digits", "abbreviation 'lbs'", "abbreviation 'e.g.'", "forbidden characters"):
            self.assertIn(expected, joined)
        self.assertIn("markdown", " ".join(lint_line(1, "- a bullet")))
        self.assertIn("more than three dots", " ".join(lint_line(1, "Wait.... go")))

    def test_word_count_ignores_pauses_and_counts_hyphenated_as_one(self):
        self.assertEqual(word_count([(1, "Single-leg bridge. [pause 3s] Don't stop.")]), 4)


class Assemble(unittest.TestCase):
    """Layout of rendered clips on the plan's clock (render.assemble)."""

    @staticmethod
    def fake_clip(text):
        # One second of audio per word, nonzero so it can be told from silence.
        return b"\x01\x00" * (len(text.split()) * SR)

    def segs(self, draft):
        return parse(draft)

    def test_each_segment_fills_its_slot(self):
        segs = self.segs("@@ 20 | A\none two three\n\nfour five\n@@ 15 | B\nsix\n")
        pcm, rows, overruns = assemble(segs, self.fake_clip)
        self.assertAlmostEqual(secs(pcm), 35.0, places=3)
        self.assertEqual(overruns, 0)
        self.assertAlmostEqual(rows[0][2], 5 + PARAGRAPH_GAP, places=3)

    def test_spare_time_goes_into_paragraph_breaks_up_to_the_cap(self):
        segs = self.segs("@@ 20 | A\none\n\ntwo\n")
        pcm, _, _ = assemble(segs, self.fake_clip)
        gap = render.MAX_EXTRA_GAP + PARAGRAPH_GAP
        # The second word starts after one second of speech plus the widened break.
        self.assertEqual(pcm[int((1 + gap) * SR) * 2 - 2:int((1 + gap) * SR) * 2], b"\x00\x00")
        self.assertEqual(pcm[int((1 + gap) * SR) * 2 + 2:int((1 + gap) * SR) * 2 + 4], b"\x01\x00")

    def test_overrun_is_flagged_and_borrows_from_the_next_slot(self):
        segs = self.segs("@@ 3 | A\none two three four five\n@@ 10 | B\nsix\n")
        pcm, rows, overruns = assemble(segs, self.fake_clip)
        self.assertEqual(overruns, 1)
        self.assertIn("overrun", rows[0][4])
        # The whole workout still lands on plan: B gives up the two seconds A ran over.
        self.assertAlmostEqual(secs(pcm), 13.0, places=3)

    def test_small_overrun_within_tolerance_is_not_flagged(self):
        segs = self.segs("@@ 20 | A\n" + " ".join(["w"] * 21) + "\n")
        _, rows, overruns = assemble(segs, self.fake_clip, tolerance=0.06)
        self.assertEqual(overruns, 0)

    def test_chime_opens_every_segment_but_the_first(self):
        segs = self.segs("@@ 5 | A\none\n@@ 5 | B\ntwo\n")
        lead = chime()
        self.assertAlmostEqual(secs(lead), CHIME_SECONDS, places=3)
        pcm, rows, _ = assemble(segs, self.fake_clip, lead=lead)
        self.assertEqual(bytes(pcm[:4]), b"\x01\x00\x01\x00")          # A starts with the voice
        b_start = 5 * SR * 2
        self.assertEqual(bytes(pcm[b_start:b_start + len(lead)]), lead)   # B starts with the bell
        self.assertAlmostEqual(rows[1][2], 1 + CHIME_SECONDS, places=3)
        self.assertAlmostEqual(secs(pcm), 10.0, places=3)

    def test_chime_is_soft(self):
        import struct
        lead = chime()
        peak = max(abs(v) for v in struct.unpack(f"<{len(lead) // 2}h", lead))
        self.assertLess(peak, 0.15 * 32767)
        self.assertGreater(peak, 0.05 * 32767)

    def test_silence_never_negative(self):
        self.assertEqual(silence(-1), b"")


class Coverage(unittest.TestCase):
    LOG = """# Workout log

## Sessions
- 2026-10-19 | 15 min | Home | V | seated bent-over rowing, dead bug on the bench, straight-leg raise | topics
- 2026-10-20 | 20 min | Home | V | incline push-up, seated curl, right single-leg glute bridge, clamshell, side plank from the knee, seated punching finisher, mystery move | topics

## Feedback
- 2026-10-20 | not | a | session | line
"""

    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w") as f:
            f.write(self.LOG)

    def tearDown(self):
        os.remove(self.path)

    def test_reads_only_the_sessions_section(self):
        log = coverage.sessions(self.path)
        self.assertEqual([d for d, _ in log], ["2026-10-19", "2026-10-20"])

    def test_groups_and_gaps(self):
        hit, unmapped = coverage.coverage(coverage.sessions(self.path)[-1][1])
        self.assertEqual(hit["arms"], ["seated curl"])
        self.assertEqual(hit["hamstrings"], ["right single-leg glute bridge"])
        self.assertEqual(hit["lateral or anti-rotation core"], ["side plank from the knee"])
        self.assertEqual(hit["anti-extension core"], [])      # a side plank isn't anti-extension
        self.assertEqual(hit["quads"], [])
        self.assertEqual(unmapped, ["mystery move"])         # the finisher is skipped on purpose

    def test_tricky_names(self):
        self.assertEqual(coverage.groups_of("lying leg curl"), ["hamstrings"])
        self.assertEqual(coverage.groups_of("seated bent-over rowing"), ["horizontal pull"])
        self.assertNotIn("horizontal push", coverage.groups_of("overhead press"))


if __name__ == "__main__":
    unittest.main()
