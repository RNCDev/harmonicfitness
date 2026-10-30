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
from draft import parse, plan, spans, spoken  # noqa: E402
from render import SR, assemble  # noqa: E402

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


class Markers(Base):
    def test_a_count_is_its_own_span_and_isnt_spoken(self):
        got = spans("Pick up the dumbbells. [count 5 go] Drive the floor away.")
        self.assertEqual(got, [("Pick up the dumbbells.", 0.0), ("[count 5 go]", 0.0), ("Drive the floor away.", 0.0)])
        self.assertFalse(spoken("[count 5 go]"))
        self.assertFalse(spoken("[cue rest]"))
        self.assertEqual(spans("[cue  Switch   Sides] [pause 2s]"), [("[cue switch sides]", 2.0)])

    def test_parts(self):
        self.assertEqual(draft.count_of("[count 5 go]"), (5, "go"))
        self.assertEqual(draft.count_of("[count 3]"), (3, None))
        self.assertEqual(draft.count_of("[count 4 switch sides]"), (4, "switch sides"))
        self.assertEqual(draft.cue_of("[cue hold]"), "hold")
        self.assertIsNone(draft.count_of("[count five]"))

    def test_markers_arent_forbidden_characters_or_digits(self):
        self.assertEqual(tts_build.lint_line(1, "Ready. [count 5 go] And [cue rest]"), [])

    def test_markers_are_no_words(self):
        self.assertEqual(tts_build.word_count([(1, "Ready now. [count 5 go] [cue rest]")]), 2)


class Timing(Base):
    def seconds(self, text):
        return tts_build.spoken_seconds(parse("@@ 30 | A\n" + text + "\n")[0], self.voice)

    def test_a_count_with_a_cue_is_n_beats_and_the_cue(self):
        self.assertAlmostEqual(self.seconds("[count 5 go]"), 5 * draft.BEAT + CUE)

    def test_a_count_alone_ends_with_its_last_number(self):
        self.assertAlmostEqual(self.seconds("[count 3]"), 2 * draft.BEAT + NUMBER)

    def test_a_cue_alone(self):
        self.assertAlmostEqual(self.seconds("[cue switch sides]"), SIDES)

    def test_render_lays_each_count_on_the_beat(self):
        segs = parse("@@ 7 | A\n[count 3 switch sides] [hold]\n")
        pcm, rows, _ = assemble(segs, lambda t: b"", mark=lambda t: counts.pcm(t, self.voice))
        samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        for beat, value in enumerate((3, 2, 1)):
            self.assertEqual(samples[beat * SR], value, f"beat {beat}")
            self.assertEqual(samples[beat * SR + int(NUMBER * SR) + 10], 0, "silence after the number")
        self.assertEqual(samples[3 * SR], 100 + draft.CUE_NAMES.index("switch sides"))
        self.assertAlmostEqual(rows[0][2], self.seconds("[count 3 switch sides]"), places=3)
        self.assertAlmostEqual(len(pcm) / 2 / SR, 7, places=3)

    def test_the_lint_and_the_render_agree(self):
        text = "[count 10 rest] [pause 1s] [cue hold] [count 2]"
        seg = parse("@@ 30 | A\n" + text + "\n")
        _, rows, _ = assemble(seg, lambda t: b"", mark=lambda t: counts.pcm(t, self.voice))
        self.assertAlmostEqual(rows[0][2], self.seconds(text), places=3)


class Lint(Base):
    def test_a_good_count_has_no_issues(self):
        self.assertEqual(self.issues("Pick up the dumbbells. [count 5 go] Drive the floor away."), [])

    def test_a_count_out_of_range_or_misspelled_is_refused(self):
        for text in ("[count 1]", "[count 11]", "[count five]", "[count 3 jump]", "[cue jump]", "[cue]"):
            got = self.issues("Get ready now. " + text)
            self.assertEqual(len(got), 1, (text, got))

    def test_a_coach_without_recorded_counts_says_them_in_words(self):
        voice = dict(self.voice, cues=None)
        self.assertEqual(self.issues("Get ready now. [count 3 go]", voice), [])
        seg = parse("@@ 30 | A\n[count 3 go]\n")[0]
        import voices
        self.assertAlmostEqual(tts_build.spoken_seconds(seg, voice), voices.clip_seconds("Three, two, one, go.", voice))
        import render
        self.assertEqual(render.spoken_clips([seg], voice), ["Three, two, one, go."])
        self.assertEqual(render.spoken_clips([seg], self.voice), [])   # recorded: nothing to speak
        pcm, rows, _ = assemble([seg], lambda t: b"\x01\x00" * SR, mark=lambda t: render.mark_audio(t, voice, lambda w: b"\x01\x00" * SR))
        self.assertAlmostEqual(rows[0][2], 1.0, places=3)

    def test_a_count_written_in_words_is_refused_when_the_coach_has_recorded_ones(self):
        for text in ("Three, two, one, rest.", "Five. Four. Three. Two. One. Go!", "ten nine eight, and go"):
            got = self.issues("Keep the elbows soft. " + text)
            self.assertTrue(any("[count" in i for i in got), (text, got))
        self.assertEqual(self.issues("Keep the elbows soft. Two, one, and rest now."), [])
        self.assertEqual(self.issues("Keep the elbows soft. Three, two, one, rest.", dict(self.voice, cues=None)), [])

    def test_the_one_word_rule_points_to_cue_markers(self):
        got = self.issues("Get ready now. [pause 1s] Rest.")
        self.assertEqual(len(got), 1, got)
        self.assertIn("[cue rest]", got[0])


class Export(Base):
    def test_the_transcript_says_the_counts(self):
        text, n = tts_build.export_text(parse("@@ 30 | A\nPick up the dumbbells. [count 3 go] Drive. [cue switch sides]\n"))
        self.assertEqual(text, "Pick up the dumbbells. Three, two, one, go. Drive. Switch sides.\n")


class Folder(Base):
    def test_a_coach_folder_with_cues(self):
        clip = os.path.join(self.tmp.name, "clip.wav")
        self.assertEqual(counts.folder(clip), self.cues)
        self.assertIsNone(counts.folder(os.path.join(self.tmp.name, "elsewhere", "clip.wav")))

    def test_a_missing_clip_is_named(self):
        os.remove(os.path.join(self.cues, "go.wav"))
        counts.table.cache_clear()
        got = self.issues("Get ready now. [count 3 go]")
        self.assertEqual(len(got), 1, got)
        self.assertIn("go", got[0])


class Brief(Base):
    def coach(self, web=False, clip=None):
        return mock.Mock(is_web=web, has_clip=True, clip=clip or os.path.join(self.tmp.name, "clip.wav"),
                         **{"name": "Coach Test"})

    def test_the_brief_says_how_the_coach_counts(self):
        import brief
        with mock.patch("brief._coach", return_value=self.coach()):
            self.assertIn("[count 5]", brief._counts_line("Coach Test")[0])
        with mock.patch("brief._coach", return_value=self.coach(web=True)):
            self.assertIn("in words", brief._counts_line("Coach Test")[0])
            self.assertIn("[count 5]", brief._counts_line("Coach Test")[0])
        with mock.patch("brief._coach", return_value=self.coach(clip=os.path.join(self.tmp.name, "x", "clip.wav"))):
            self.assertIn("in words", brief._counts_line("Coach Test")[0])

    def test_the_brief_says_how_the_voice_takes_sentences(self):
        import brief
        with mock.patch("brief._coach", return_value=self.coach()):
            self.assertIn("short pieces", brief._voice_line("Coach Test")[0])
        with mock.patch("brief._coach", return_value=self.coach(web=True)):
            self.assertIn("whole paragraph", brief._voice_line("Coach Test")[0])
        with mock.patch("brief._coach", return_value=None):
            self.assertEqual(brief._voice_line("Coach Test"), [])


if __name__ == "__main__":
    unittest.main()
