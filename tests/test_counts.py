"""Counts and cues: [count N cue] and [cue x] in a draft play a coach's recorded clips on a one-second beat."""
import os
import struct
import sys
import tempfile
import unittest
import wave
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import counts  # noqa: E402
import draft  # noqa: E402
import tts_build  # noqa: E402
from draft import parse, spans, spoken  # noqa: E402
from render import SR  # noqa: E402

NUMBER = 0.5      # every number clip in the fixture, in seconds
CUE = 0.6         # every cue clip but switch sides
SIDES = 0.9


def write_wav(path, seconds, value):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack("<h", value) * int(round(seconds * SR)))


def make_cues(folder):
    """A coach's cues/ folder as tools/coachmaker/cues.py keep writes it, with silent-ish clips: each number's
    samples hold its value (one is 1, ten is 10), so a test can tell where each landed."""
    os.makedirs(folder, exist_ok=True)
    lines = []
    for n, word in enumerate(draft.NUMBER_WORDS, 1):
        write_wav(os.path.join(folder, word + ".wav"), NUMBER, n)
        lines += [f"[count.{word}]", f'words = "{word.title()}."', "seed = 42", f"seconds = {NUMBER}", ""]
    for i, cue in enumerate(draft.CUE_NAMES):
        file = cue.replace(" ", "-") + ".wav"
        secs = SIDES if cue == "switch sides" else CUE
        write_wav(os.path.join(folder, file), secs, 100 + i)
        lines += [f"[cue.{cue.replace(' ', '_')}]", f'file = "{file}"', f'words = "{cue.capitalize()}."', "seed = 42",
                  f"seconds = {secs}", ""]
    with open(os.path.join(folder, counts.FILE), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return folder


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cues = make_cues(os.path.join(self.tmp.name, "cues"))
        self.voice = {"engine": "pocket", "key": "x", "name": "Coach Test", "cues": self.cues}
        self.pace = mock.patch("voices.pace", return_value=(10.0, True))
        self.pace.start()

    def tearDown(self):
        self.pace.stop()
        self.tmp.cleanup()

    def issues(self, text, voice="default"):
        report = tts_build.lint(parse("@@ 30 | A\n" + text + "\n"), voice=self.voice if voice == "default" else voice)
        row = report.rows[0]
        return row.clip_issues + row.line_issues


class Lint(Base):
    def test_markers_are_their_own_spans_and_no_words(self):
        got = spans("Pick up the dumbbells. [count 5 go] Drive the floor away.")
        self.assertEqual(got, [("Pick up the dumbbells.", 0.0), ("[count 5 go]", 0.0), ("Drive the floor away.", 0.0)])
        self.assertFalse(spoken("[count 5 go]"))
        self.assertFalse(spoken("[cue rest]"))
        self.assertEqual(spans("[cue  Switch   Sides] [pause 2s]"), [("[cue switch sides]", 2.0)])
        self.assertEqual(draft.count_of("[count 5 go]"), (5, "go"))
        self.assertEqual(draft.count_of("[count 3]"), (3, None))
        self.assertEqual(draft.count_of("[count 4 switch sides]"), (4, "switch sides"))
        self.assertEqual(draft.cue_of("[cue hold]"), "hold")
        self.assertIsNone(draft.count_of("[count five]"))
        self.assertEqual(tts_build.lint_line(1, "Ready. [count 5 go] And [cue rest]"), [])
        self.assertEqual(tts_build.word_count([(1, "Ready now. [count 5 go] [cue rest]")]), 2)
        seg = parse("@@ 30 | A\nGood set.\n[story]\nThe Flyers won last night.\n[/story]\nBack to it.\n")[0]
        self.assertEqual(draft.plan(seg), [[("Good set. The Flyers won last night. Back to it.", 0.0)]])

    def test_what_the_lint_says_of_counts_and_cues(self):
        """Each row: the text after a line of coaching, the coach (recorded counts or none), and whether the lint
        refuses it (and with what words)."""
        words = dict(self.voice, cues=None)
        rows = (
            ("Pick up the dumbbells. [count 5 go] Drive the floor away.", self.voice, None),
            *((t, self.voice, "") for t in ("[count 1]", "[count 11]", "[count five]", "[count 3 jump]",
                                            "[cue jump]", "[cue]")),
            *((t, self.voice, "[count") for t in ("Three, two, one, rest.", "Five. Four. Three. Two. One. Go!",
                                                  "ten nine eight, and go")),
            ("Two, one, and rest now.", self.voice, None),
            ("Three, two, one, rest.", words, None),          # a coach without recorded counts says them
            ("[count 3 go]", words, None),
            ("[story] The launch went on time: ten, nine, eight, and liftoff. [/story]", self.voice, None),
            ("[story] The Flyers won last night. [/story] Back to it.", self.voice, None),
            ("[pause 1s] Rest.", self.voice, "[cue rest]"),   # the one-word rule points to cue markers
        )
        for text, voice, refused in rows:
            with self.subTest(text=text):
                got = self.issues("Keep the elbows soft. " + text, voice)
                if refused is None:
                    self.assertEqual(got, [])
                else:
                    self.assertEqual(len(got), 1, got)
                    self.assertIn(refused, got[0])


if __name__ == "__main__":
    unittest.main()
