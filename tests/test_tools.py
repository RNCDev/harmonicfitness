"""Fast checks across the engine: a draft's text and timing, the build around the render, the log, feeds, the
context files and the command line. No models, no audio rendering, no network. Python 3.11 or later (the
project's environment).

    ./harmonicfitness test test_tools     # this module; CI runs ./harmonicfitness test engine
"""
import contextlib
import datetime as dt
import io
import glob
import shutil
import subprocess
import json
import os
import re
import sys
import time
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import cache  # noqa: E402
import catalog  # noqa: E402
import check  # noqa: E402
import coachpick  # noqa: E402

# The shipped catalog only: a listener's private movements in me/ never change what the tests see.
catalog.paths.MY_MOVEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "no-private-movements.toml")
import cli  # noqa: E402
import cloud  # noqa: E402
import personas  # noqa: E402
import context  # noqa: E402
import store  # noqa: E402
import sessionlog  # noqa: E402
import health as health_md  # noqa: E402
import coverage  # noqa: E402
import draft  # noqa: E402
import engines  # noqa: E402
import feeds  # noqa: E402
import paths  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
import errors  # noqa: E402
helpers.assert_isolated(paths.HOME)   # never over a real me/: ./harmonicfitness test points HARMONICFITNESS_HOME elsewhere
import records  # noqa: E402
import render  # noqa: E402
import tts_build  # noqa: E402
import voices  # noqa: E402
from draft import CHIME, CHIME_SECONDS, PARAGRAPH_GAP, parse, plan, spans  # noqa: E402
from audio import SR, assemble  # noqa: E402
from tts_build import lint_line, word_count  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def secs(pcm):
    return len(pcm) / 2 / SR


def with_schema(text):
    """A context file's text as the current engine writes it, front matter first."""
    return store.with_front_matter(text)


def profile_text(settings_toml, prose="# Profile\n"):
    """A schema-2 profile: TOML settings, then prose."""
    return f"+++\nschema = {store.SCHEMA}\n{settings_toml}\n+++\n{prose}"


def write_file(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def private_pattern():
    with open(os.path.join(ROOT, "tools", "hooks", "private-paths"), encoding="utf-8") as f:
        return next(l.strip() for l in f if l.strip() and not l.startswith("#"))


def fresh_home(d):
    home = os.path.join(d, "me")
    shutil.copytree(paths.EXAMPLE, home)
    return home


def table(case, rows):
    """Run each (name, check) row as its own subTest."""
    for name, row in rows:
        with case.subTest(name):
            row()


class ParseAndLint(unittest.TestCase):
    """A draft's segments, markers and the lint: what a voice can read and how the plan's clock is kept."""
    CHATTERBOX = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}

    def test_parse(self):
        def segments_and_paragraphs():
            segs = parse("@@ 60 | Opening\nHello there.\nStill one paragraph.\n\nSecond one.\n@@ 30 | Next\nGo.\n")
            self.assertEqual([(s["seconds"], s["label"]) for s in segs], [(60, "Opening"), (30, "Next")])
            self.assertEqual(plan(segs[0]), [[("Hello there. Still one paragraph.", 0.0)], [("Second one.", 0.0)]])

        def text_before_first_marker():
            with self.assertRaises(errors.PROBLEMS):
                parse("stray words\n@@ 60 | A\nHi.\n")

        def no_markers():
            with self.assertRaises(errors.PROBLEMS):
                parse("Just text.\n")

        def zero_second_segment():
            with self.assertRaises(errors.PROBLEMS) as got:
                parse("@@ 30 | A\nHi.\n@@ 0 | x\nGo.\n")
            self.assertIn("Line 3", str(got.exception.code))
            self.assertIn("at least 1 second", str(got.exception.code))
        table(self, [("segments", segments_and_paragraphs), ("stray text", text_before_first_marker),
                     ("no markers", no_markers), ("zero seconds", zero_second_segment)])

    def test_spans(self):
        def pauses():
            self.assertEqual(spans("Set up. [pause 3s] Go. [pause 500ms] Now [pause] end"),
                             [("Set up.", 3.0), ("Go.", 0.5), ("Now", draft.PAUSE_DEFAULT), ("end", 0.0)])
            self.assertEqual(spans("Rest. [pause 30s]"), [("Rest.", draft.PAUSE_MAX)])   # capped
            self.assertEqual(spans("[pause 2s] Breathe."), [("", 2.0), ("Breathe.", 0.0)])
            self.assertEqual(spans("Hold. [pause 2s] [pause 3s] Out."), [("Hold.", 5.0), ("Out.", 0.0)])

        def chimes():
            self.assertEqual(spans("Start at the bell. [chime] Work."),
                             [("Start at the bell.", 0.0), (CHIME, 0.0), ("Work.", 0.0)])
            # A pause after the bell is silence after the bell.
            self.assertEqual(spans("[chime] [pause 1s] Go."), [(CHIME, 1.0), ("Go.", 0.0)])
            self.assertEqual(spans("Rest. [pause 2s] [Chime]"), [("Rest.", 2.0), (CHIME, 0.0)])
            self.assertFalse(draft.spoken(CHIME))
            self.assertFalse(draft.spoken(""))
            self.assertTrue(draft.spoken("Go."))
            self.assertEqual(lint_line(1, "Work starts at the bell. [chime] Go."), [])
            self.assertEqual(word_count([(1, "Ready. [chime] Go now.")]), 3)

        def holds():
            got = draft.spans("Push. [hold] [chime] Easy.")
            self.assertEqual([t for t, _ in got], ["Push.", draft.HOLD, CHIME, "Easy."])
            self.assertFalse(draft.spoken(draft.HOLD))
            self.assertEqual(draft.holds(parse("@@ 10 | A\none [hold] two [hold]\n")[0]), (2, 2))
            self.assertEqual(draft.spans("Go. [hold 20s] Stop."), [("Go.", 0.0), (draft.HOLD, 20.0), ("Stop.", 0.0)])
            self.assertEqual(draft.fill_flag(2, 30, held=True), "")
            self.assertEqual(draft.fill_flag(2, 30), "short")
        table(self, [("pauses", pauses), ("chimes", chimes), ("holds", holds)])

    def test_what_a_voice_can_read(self):
        def clean_line():
            self.assertEqual(lint_line(1, "Three sets of ten. [pause 3s] Three, two, one, switch."), [])
            self.assertEqual(lint_line(1, "Three, two, one, rest."), [])

        def hazards():
            joined = " ".join(lint_line(1, "Do 3 sets, 25 lbs e.g. # now"))
            for expected in ("digits", "abbreviation 'lbs'", "abbreviation 'e.g.'", "forbidden characters"):
                self.assertIn(expected, joined)
            self.assertIn("markdown", " ".join(lint_line(1, "- a bullet")))
            self.assertIn("an ellipsis", " ".join(lint_line(1, "Wait.... go")))
            self.assertIn("an ellipsis", " ".join(lint_line(1, "Three... two... one... rest.")))
            self.assertIn("an ellipsis", " ".join(lint_line(1, "Three… two… one, rest.")))

        def word_counts():
            self.assertEqual(word_count([(1, "Single-leg bridge. [pause 3s] Don't stop.")]), 4)

        def one_word_clip():
            segs = parse("@@ 30 | A\nAt the bell, go. [chime] Hold. [pause 3s] Other way. [hold] And go.\n\nRest.\n")
            report = tts_build.lint(segs, wpm=60)
            issues = report.rows[0].clip_issues
            self.assertEqual(len(issues), 2, issues)
            self.assertIn('"Hold."', issues[0])
            self.assertIn('"Rest."', issues[1])
            self.assertTrue(report.problems >= 2)
            self.assertIn('"Hold."', "\n".join(tts_build.render_report(report)))
        table(self, [("clean", clean_line), ("hazards", hazards), ("word count", word_counts),
                     ("one-word clip", one_word_clip)])

    def test_the_clock(self):
        v = self.CHATTERBOX

        def lint(segs, voice=v, rate=10.0, exact=True, **kw):
            with mock.patch("voices.pace", return_value=(rate, exact)):
                return tts_build.lint(segs, voice, **kw)

        def silence():
            coached = parse("@@ 30 | A\nTwelve reps. And go. [hold 5s] Hips level. [hold 5s] About halfway now. "
                            "[hold 5s] Last few, slow down. [hold 4s] And rest now.\n")
            self.assertEqual(lint(coached).rows[0].clip_issues, [])
            # pauses and holds back to back add up, and so does a bare hold's share of the spare time
            for text in ("@@ 30 | A\nReady now. [pause 5s] [hold 5s] Keep going.\n",
                         "@@ 40 | A\nLie back now. [hold] Good, and again.\n"):
                issues = lint(parse(text)).rows[0].clip_issues
                self.assertTrue(any("of silence" in i for i in issues), (text, issues))
            # without a voice, a fixed hold over eight seconds is still refused
            self.assertTrue(any("of silence" in i for i in tts_build.lint(parse(
                "@@ 30 | A\nGo now please. [hold 12s] And rest now.\n")).rows[0].clip_issues))

        def pulse_bed():
            text = parse("@@ 30 | A\nGo now please. [hold 12s] And rest now.\n")
            self.assertTrue(any("of silence" in i for i in lint(text).rows[0].clip_issues))
            self.assertFalse(any("of silence" in i for i in lint(text, bed=True).rows[0].clip_issues))
            long = parse("@@ 30 | A\nGo now please. [hold 10s] [hold 10s] [hold 3s] And rest now.\n")
            self.assertTrue(any("of silence" in i for i in lint(long, bed=True).rows[0].clip_issues))

        def total():
            report = lint(parse("@@ 10 | A\n" + "word " * 40 + "\n"))
            self.assertGreater(report.drift, 0.03)
            self.assertTrue(report.total_off)
            self.assertEqual(report.rows[0].flag, "long")

        def inline_chime():
            seg = parse("@@ 10 | A\nab [chime] cd\n")[0]
            with mock.patch("voices.pace", return_value=(10.0, True)):
                got = tts_build.spoken_seconds(seg, {"engine": "chatterbox", "key": "x", "name": "x"})
            self.assertAlmostEqual(got, 2 * (2 / 10.0 + voices.EDGE) + CHIME_SECONDS, places=6)

        def skeleton_budgets():
            # words are written to the clock: budgets at the voice's rate on a sample, never the default
            fake = {"name": "Coach Fake", "key": "x", "engine": "chatterbox", "model": "m"}
            segs = parse("@@ 60 | Welcome\n\n@@ 45 | Squats\n[count 3 go]\n[hold 4s]\n\n@@ 75 | Rest\n")
            with mock.patch("voices.pace", return_value=(12.0, False)):
                report = tts_build.lint(segs, fake)
                lines = tts_build.render_report(report)
            self.assertTrue(lines[0].startswith("Skeleton: 3 segments, 180 s. Word budgets with Coach Fake"), lines[0])
            self.assertNotAlmostEqual(report.wpm, tts_build.DEFAULT_WPM)
            self.assertEqual(report.total_words, 0)
            budgets = [r.guide for r in report.rows]
            self.assertTrue(all(b > 0 for b in budgets), budgets)
            self.assertLess(budgets[1], budgets[0])        # the count and hold take their seconds from the set
            self.assertIn(f"About {sum(budgets):,} words still to write", lines[-1])
            self.assertFalse(any("ends" in ln or "To land" in ln for ln in lines))   # not a fix list: a plan
            partial = parse("@@ 60 | Welcome\n\n@@ 45 | Squats\n[count 3 go]\n[hold 4s]\n\n@@ 75 | Rest\n"
                            "Set it down. [story] The Flyers won four to two last night. [/story] Pick it back up.\n")
            with mock.patch("voices.pace", return_value=(12.0, False)):
                report = tts_build.lint(partial, fake)
                lines = tts_build.render_report(report)
            self.assertTrue(lines[0].startswith("Unfinished: 2 of 3 segments have no words yet, 180 s."), lines[0])
            row = next(ln for ln in lines if ln.strip().endswith("Rest"))
            self.assertIn(f"{report.rows[2].words:>5} {max(report.rows[2].guide - report.rows[2].words, 0):>8}", row)
            with mock.patch("voices.pace", return_value=(12.0, False)):
                worded = tts_build.render_report(tts_build.lint(parse("@@ 60 | Welcome\nHello there friend.\n"), fake))
            self.assertFalse(worded[0].startswith(("Skeleton", "Unfinished")))
        table(self, [("silence", silence), ("pulse bed", pulse_bed), ("total", total),
                     ("inline chime", inline_chime), ("skeleton", skeleton_budgets)])

    def test_a_web_voice_s_lint_says_what_it_sends_and_a_local_one_doesn_t(self):
        segs = parse("@@ 20 | A\nHello there, and welcome in.\n")
        web = {"name": "x", "key": "x", "engine": "gemini", "model": "m", "backend": "cloud"}
        local = {"name": "x", "key": "x", "engine": "pocket", "model": "m"}
        with mock.patch("voices.pace", return_value=(14.5, False)):
            sent = tts_build.lint(segs, web)
            kept = tts_build.lint(segs, local)
        self.assertEqual(sent.sent, len("Hello there, and welcome in."))
        self.assertIn(f"Sends {sent.sent:,} characters to the voice service", "\n".join(tts_build.render_report(sent)))
        self.assertIsNone(kept.sent)
        self.assertFalse(any("Sends" in line for line in tts_build.render_report(kept)))
        self.assertEqual(sent.notes, [])   # not an issue: only --max-chars makes one


class Assemble(unittest.TestCase):
    """Layout of rendered clips on the plan's clock (render.assemble)."""

    @staticmethod
    def fake_clip(text):
        # One second of audio per word, nonzero so it can be told from silence.
        return b"\x01\x00" * (len(text.split()) * SR)

    def test_layout_on_the_clock(self):
        clip = self.fake_clip

        def short_widens_then_ends_early():
            pcm, rows, drift = assemble(parse("@@ 20 | A\none two three\n\nfour five\n@@ 15 | B\nsix\n"), clip)
            self.assertAlmostEqual(rows[0][2], 5 + PARAGRAPH_GAP, places=3)
            # A: speech, one break widened by the cap, a short tail. B: speech and a tail.
            a = 5 + PARAGRAPH_GAP + draft.MAX_EXTRA_GAP + draft.END_TAIL
            b = 1 + draft.END_TAIL
            self.assertAlmostEqual(secs(pcm), a + b, places=3)
            self.assertAlmostEqual(drift, (a + b) / 35 - 1, places=3)
            self.assertEqual(rows[0][4], "  <-- short")

        def little_spare_fills():
            pcm, rows, drift = assemble(parse("@@ 5 | A\none two three four\n"), clip)
            self.assertAlmostEqual(secs(pcm), 5.0, places=3)
            self.assertAlmostEqual(drift, 0.0, places=3)
            self.assertEqual(rows[0][4], "")

        def breaks_up_to_the_cap():
            pcm, _, _ = assemble(parse("@@ 20 | A\none\n\ntwo\n"), clip)
            gap = draft.MAX_EXTRA_GAP + PARAGRAPH_GAP
            # The second word starts after one second of speech plus the widened break.
            self.assertEqual(pcm[int((1 + gap) * SR) * 2 - 2:int((1 + gap) * SR) * 2], b"\x00\x00")
            self.assertEqual(pcm[int((1 + gap) * SR) * 2 + 2:int((1 + gap) * SR) * 2 + 4], b"\x01\x00")

        def long_is_paid_back():
            pcm, rows, _ = assemble(parse("@@ 3 | A\none two three four five\n@@ 10 | B\nsix\n"), clip)
            self.assertEqual(rows[0][4], "  <-- long")
            # A runs two seconds late, so B keeps only what's left of its spare time.
            self.assertAlmostEqual(secs(pcm), 5 + 1 + draft.END_TAIL, places=3)

        def small_overrun_unflagged():
            _, rows, drift = assemble(parse("@@ 20 | A\n" + " ".join(["w"] * 21) + "\n"), clip)
            self.assertEqual(rows[0][4], "")
            self.assertAlmostEqual(drift, 0.05, places=3)

        def hold_keeps_the_segment_full():
            pcm, rows, _ = assemble(parse("@@ 30 | A\ngo [chime] push [hold] [chime] easy\n@@ 10 | B\nsix\n"), clip,
                                    bell=b"\x02\x00" * SR)
            # A: three words and two one-second bells, 25 s of hold; then B ends early as usual
            self.assertAlmostEqual(secs(pcm), 30 + 1 + draft.END_TAIL, places=3)
            self.assertEqual(rows[0][4], "")   # a held segment is never flagged short
            quiet = pcm[int(4 * SR) * 2:int(28 * SR) * 2]   # after "go", bell, "push": the hold
            self.assertEqual(set(bytes(quiet)), {0})
            self.assertEqual(bytes(pcm[int(29.5 * SR) * 2:int(29.5 * SR) * 2 + 2]), b"\x01\x00")   # "easy" ends A
            predicted = draft.layout([(5, 0, 30, 1), (1, 0, 10)])
            self.assertAlmostEqual(secs(pcm), sum(length for _, length in predicted), places=3)

        def fixed_hold():
            pcm, _, _ = assemble(parse("@@ 60 | A\ngo [hold 20s] stop [hold] next\n@@ 10 | B\nsix\n"), clip)
            # A: three words, twenty fixed seconds, and the bare hold takes the other 37
            self.assertAlmostEqual(secs(pcm), 60 + 1 + draft.END_TAIL, places=3)
            self.assertEqual(set(bytes(pcm[int(1 * SR) * 2:int(21 * SR) * 2])), {0})
            self.assertEqual(bytes(pcm[int(21 * SR) * 2:int(21 * SR) * 2 + 2]), b"\x01\x00")   # "stop" at 21 s
            pcm, _, _ = assemble(parse("@@ 30 | A\ngo [hold 10s] stop\n"), clip)
            # no bare hold: the fixed hold is its ten seconds, and the segment ends early like any other
            self.assertAlmostEqual(secs(pcm), 1 + 10 + 1 + draft.END_TAIL, places=3)

        def late_start_never_shortens_a_hold():
            # since 0.39.0: A runs two seconds long, and the held B keeps its full 30 s; C pays the lateness back
            pcm, _, _ = assemble(parse("@@ 3 | A\none two three four five\n@@ 30 | B\ngo [hold] easy\n@@ 10 | C\nsix\n"),
                                 clip)
            self.assertEqual(bytes(pcm[int((5 + 29.5) * SR) * 2:int((5 + 29.5) * SR) * 2 + 2]), b"\x01\x00")
            self.assertAlmostEqual(secs(pcm), 5 + 30 + 1 + draft.END_TAIL, places=3)
            self.assertEqual(draft.layout([(5, 0, 3), (2, 0, 30, True), (1, 0, 10)])[1], (0.0, 30))

        def layout_matches():
            pcm, _, _ = assemble(parse("@@ 20 | A\none two\n\nthree\n@@ 4 | B\nfour five six\n\nseven\n@@ 30 | C\neight\n"),
                                 clip)
            predicted = draft.layout([(3 + PARAGRAPH_GAP, 1, 20), (4 + PARAGRAPH_GAP, 1, 4), (1, 0, 30)])
            self.assertAlmostEqual(secs(pcm), sum(length for _, length in predicted), places=3)
        table(self, [("short", short_widens_then_ends_early), ("fills", little_spare_fills),
                     ("breaks", breaks_up_to_the_cap), ("long", long_is_paid_back),
                     ("small overrun", small_overrun_unflagged), ("hold", hold_keeps_the_segment_full),
                     ("fixed hold", fixed_hold), ("late start", late_start_never_shortens_a_hold),
                     ("layout", layout_matches)])

    def test_a_long_silence_as_laid_out_is_reported(self):
        segs = parse("@@ 40 | Work\ngo [hold] stop\n")
        quiet = []
        assemble(segs, self.fake_clip, quiet=quiet)
        self.assertEqual(len(quiet), 1, quiet)
        self.assertEqual(quiet[0][:2], (1, "Work"))
        self.assertAlmostEqual(quiet[0][2], 38, places=0)
        quiet = []
        assemble(segs, self.fake_clip, quiet=quiet, max_silence=draft.BED_MAX_SILENCE * 2)
        self.assertEqual(quiet, [])


class PublicPocket(unittest.TestCase):
    """Pocket TTS takes the public model whatever login the computer has (engines.public_only, speaker)."""

    def test_the_gated_model_a_cloning_model_and_another_version_are_refused(self):
        try:   # imported once, before any test patches sys.modules (PyTorch can't be imported twice)
            import torch  # noqa: F401
        except ImportError:
            self.skipTest("PyTorch isn't installed here")
        calls = []

        class Module:
            @staticmethod
            def download_if_necessary(path):
                calls.append(path)
                return "/cache/" + path.rsplit("/", 1)[-1]
        original = Module.download_if_necessary
        gated = "hf://kyutai/pocket-tts/languages/english_2026-10/model.safetensors@db04f0e"
        public = "hf://kyutai/pocket-tts-without-voice-cloning/languages/english_2026-10/model.safetensors@a7056f5"
        with engines.public_only(Module):
            with self.assertRaises(PermissionError):
                Module.download_if_necessary(gated)
            self.assertEqual(Module.download_if_necessary(public), "/cache/model.safetensors@a7056f5")
        self.assertEqual(calls, [public])   # the gated path never reached the download
        self.assertIs(Module.download_if_necessary, original)   # restored afterwards

        class Model:
            has_voice_cloning = True
            sample_rate = engines.SR

        class TTSModel:
            @staticmethod
            def load_model(language=None):
                return Model()
        voice = {"name": "x", "backend": "torch", "device": "cpu", "voice_state": "x.safetensors"}
        with mock.patch.dict(sys.modules, {"pocket_tts": mock.MagicMock(TTSModel=TTSModel)}), \
                mock.patch.object(engines, "public_only", contextlib.nullcontext), \
                mock.patch.object(engines, "_version", return_value=voices.POCKET_VERSION):
            with self.assertRaises(errors.PROBLEMS) as e:
                engines.speaker(voice)
        self.assertIn("gated", str(e.exception.code))
        with mock.patch.dict(sys.modules, {"pocket_tts": mock.MagicMock()}), \
                mock.patch.object(engines, "_version", return_value="9.9.9"):
            with self.assertRaises(errors.PROBLEMS) as e:
                engines.speaker(voice)
        self.assertIn(voices.POCKET_VERSION, str(e.exception.code))

    def test_the_model_pins(self):
        with open(os.path.join(ROOT, "uv.lock"), encoding="utf-8") as f:
            lock = f.read()
        m = re.search(r'name = "pocket-tts"\nversion = "([^"]+)"', lock)
        self.assertEqual(m.group(1), voices.POCKET_VERSION)
        self.assertRegex(lock, r'name = "onnx-asr"\nversion = "0\.12\.0"')
        self.assertNotIn('name = "mlx-audio"', lock)
        self.assertEqual(voices.LOCAL_MODELS["pocket"], (voices.POCKET_REPO, voices.POCKET_FILES[0][2]))
        try:
            import pocket_tts.utils.config as config
        except ImportError:
            return   # pocket-tts isn't installed here: the lock's pin is checked above
        with open(os.path.join(config.CONFIGS_DIR, voices.POCKET_LANGUAGE + ".yaml"), encoding="utf-8") as f:
            text = f.read()
        named = {"hf://" + m for m in re.findall(r"hf://(kyutai/pocket-tts-without-voice-cloning/[^\s'\"]+)", text)}
        self.assertEqual(named, {f"hf://{repo}/{name}@{rev}" for repo, name, rev in voices.POCKET_FILES})


class Log(unittest.TestCase):
    """The session log: what's written reads back, and a session that can't be read is never written."""
    LOG = """## Sessions
- 2026-10-19 | 15 min | Home | V | seated curl, rows | deep dive: news, x
- 2026-10-20 | 20 min | Home | V | seated curl, squat | topics | format: circuits | loads: seated curl = fifteens, three down; squat = bodyweight
- 2026-10-21 | 20 min | Home | V | seated curl | topics | format: rolling minutes | loads: seated curl = twenties

## Feedback
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "log.md")
        write_file(self.path, with_schema(self.LOG))

    def test_what_is_written_reads_back(self):
        def round_trip():
            log = os.path.join(self.tmp.name, "rt.md")
            write_file(log, with_schema("# Workout log\n\n## Sessions\n\n## Feedback\n- loved it\n"))
            s = sessionlog.Session("2026-10-21", 25, "Home", "Chatterbox Coach", ["goblet squat", "seated row"],
                                   "deep dive: news, a story", "rolling minutes",
                                   {"goblet squat": "twenties, three down"})
            sessionlog.append_session(s, log)
            sessionlog.append_session(sessionlog.Session("2026-10-22", 15, "Travel", "Qwen3 Coach", ["push-up"], "x"), log)
            got = sessionlog.sessions(log)
            self.assertEqual([(g.date, g.minutes, g.movements, g.format, g.loads) for g in got],
                             [("2026-10-21", 25, ["goblet squat", "seated row"], "rolling minutes",
                               {"goblet squat": "twenties, three down"}),
                              ("2026-10-22", 15, ["push-up"], None, {})])
            with open(log, encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(store.schema_of(text), store.SCHEMA)
            self.assertIn("## Feedback\n- loved it", text)            # the rest of the file is untouched
            self.assertLess(text.index("2026-10-22"), text.index("## Feedback"))

        def rpe():
            s = sessionlog.Session("2026-10-21", 20, "Home", "V", ["goblet squat"], "topics", rpe={"goblet squat": "7"})
            line = s.to_line()
            self.assertIn("| rpe: goblet squat = 7", line)
            self.assertEqual(sessionlog.parse_session(line).rpe, {"goblet squat": "7"})
            self.assertEqual(sessionlog.parse_session(line.replace("= 7", "= 7 to 8")).rpe, {"goblet squat": "7 to 8"})

        def format_and_loads():
            e = sessionlog.sessions(self.path)
            self.assertIsNone(e[0].format)
            self.assertEqual(e[0].loads, {})
            self.assertEqual(e[1].format, "circuits")
            self.assertEqual(e[1].loads, {"seated curl": "fifteens, three down", "squat": "bodyweight"})
            self.assertEqual((e[1].date, e[1].minutes, e[1].movements), ("2026-10-20", 20, ["seated curl", "squat"]))
            loads = coverage.last_loads(sessionlog.sessions(self.path))   # the newest wins, by catalog name
            self.assertEqual(loads["seated dumbbell curl"], ("2026-10-21", "twenties"))
            self.assertEqual(loads["air squat"], ("2026-10-20", "bodyweight"))

        def shifted_line():
            log = os.path.join(self.tmp.name, "shifted", "log.md")
            write_file(log, with_schema("## Sessions\n- 2026-10-19 | 15 min | Home | squat, row | topics\n"
                                        "- 2026-10-20 | 20 min | Home | V | squat | topics | format: circuits\n"))
            with mock.patch("sys.stderr", new_callable=io.StringIO) as err:
                got = sessionlog.sessions(log)
            self.assertEqual([s.date for s in got], ["2026-10-20"])     # not read with its fields shifted
            self.assertIn("5 fields", err.getvalue())
            issues = check.check([log])
            self.assertTrue(any(i.path == log and i.line == 5 for i in issues), issues)
        table(self, [("round trip", round_trip), ("rpe", rpe), ("format and loads", format_and_loads),
                     ("shifted", shifted_line)])

    def test_a_bad_session_is_never_written(self):
        for bad in (sessionlog.Session("21 Oct", 25, "Home", "V", ["squat"], "t"),
                    sessionlog.Session("2026-10-21", 25, "Home", "V", [], "t"),
                    sessionlog.Session("2026-10-21", 25, "Home | Gym", "V", ["squat"], "t")):
            with self.subTest(bad=bad), self.assertRaises(errors.PROBLEMS):
                sessionlog.append_session(bad, self.path)
        for bad in ("7; 8", "7 | 8"):
            s = sessionlog.Session("2026-10-21", 20, "Home", "V", ["goblet squat"], "topics", rpe={"goblet squat": bad})
            self.assertTrue(s.problems(), bad)
        # log-session checks the coach, the kit and the format
        home = fresh_home(self.tmp.name)
        base = ["log-session", "--date", "2026-10-25", "--minutes", "10", "--kit", "home", "--coach", "Coach Julius",
                "--movements", "goblet squat", "--topics", "none", "--format", "straight-sets"]
        with helpers.home(home):
            for flag, bad, words in (("--coach", "Nobody", "coach"), ("--kit", "Nowhere", "kit"),
                                     ("--format", "rolling minutes", "format"), ("--topics", "a b", "line break")):
                args = list(base)
                args[args.index(flag) + 1] = bad
                with self.subTest(flag=flag), self.assertRaises(errors.PROBLEMS) as got:
                    context.main(args)
                self.assertIn("Not logged", str(got.exception))
                self.assertIn(words, str(got.exception))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(context.main(base), cli.OK)
                args = list(base)
                args[args.index("--kit") + 1] = "hotel-room"   # a preset counts as a kit
                args[args.index("--date") + 1] = "2026-10-26"  # another day: the same session is logged once
                self.assertEqual(context.main(args), cli.OK)
            self.assertEqual(out.getvalue().count("Logged"), 2)


class Feeds(unittest.TestCase):
    NOW = dt.datetime(2026, 10, 21, 16, 0, tzinfo=dt.timezone.utc)

    def test_config_and_rss(self):
        since = self.NOW - dt.timedelta(hours=72)

        def config():
            p = context.Profile({"feeds": [
                {"label": "Weather, home", "kind": "weather", "value": "39.9, -75.1"},
                {"label": "Devils", "kind": "ESPN", "value": "hockey/nhl/nj"},
                {"label": "Local", "kind": "rss", "value": "https://example.org/feed/"},
                {"label": "Bad", "kind": "ftp", "value": "x"},
                {"label": "[Team]", "kind": "espn", "value": "[sport/league/team]"},   # not filled in: skipped
                {"label": "Empty", "kind": "rss", "value": ""}]}, "")
            self.assertEqual(feeds.config(p), [("Weather, home", "weather", "39.9, -75.1"),
                                               ("Devils", "espn", "hockey/nhl/nj"),
                                               ("Local", "rss", "https://example.org/feed/")])

        def rss_and_atom():
            rss = b"""<?xml version="1.0"?><rss><channel>
                <item><title>New &amp; old</title><link>https://a/1</link>
                  <pubDate>Wed, 21 Oct 2026 10:00:00 -0400</pubDate><description>&lt;p&gt;Hello &lt;b&gt;there&lt;/b&gt;&lt;/p&gt;</description></item>
                <item><title>Stale</title><link>https://a/2</link><pubDate>Mon, 12 Oct 2026 10:00:00 GMT</pubDate></item>
                <item><title>Undated</title><link>https://a/3</link></item>
                </channel></rss>"""
            items = feeds.parse_rss(rss, since)
            self.assertEqual([i["title"] for i in items], ["New & old"])
            self.assertEqual(items[0]["summary"], "Hello there")
            atom = b"""<feed xmlns="http://www.w3.org/2005/Atom">
                <entry><title>Paper</title><link rel="alternate" href="https://b/1"/>
                  <published>2026-10-20T12:00:00Z</published><summary>Qubits.</summary></entry></feed>"""
            items = feeds.parse_rss(atom, since)
            self.assertEqual((items[0]["title"], items[0]["link"], items[0]["summary"]), ("Paper", "https://b/1", "Qubits."))
            rdf = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
                <item><title>Journal news</title><link>https://j/1</link><dc:date>2026-10-21T08:00:00Z</dc:date>
                  <description>Findings.</description></item></rdf:RDF>"""
            items = feeds.parse_rss(rdf, since)
            self.assertEqual([(i["title"], i["link"], i["summary"]) for i in items],
                             [("Journal news", "https://j/1", "Findings.")])

        def weekly():
            rss = b"""<?xml version="1.0"?><rss><channel>
                <item><title>This week</title><link>https://p/1</link><pubDate>Sun, 18 Oct 2026 07:00:00 -0400</pubDate></item>
                <item><title>Last week</title><link>https://p/2</link><pubDate>Sun, 11 Oct 2026 07:00:00 -0400</pubDate></item>
                <item><title>Older</title><link>https://p/3</link><pubDate>Fri, 16 Oct 2026 07:00:00 -0400</pubDate></item>
                <item><title>Ancient</title><link>https://p/4</link><pubDate>Sun, 04 Oct 2026 07:00:00 -0400</pubDate></item>
                </channel></rss>"""
            with mock.patch.object(feeds, "fetch", return_value=rss):
                lines = feeds.gather(("Puzzle", "weekly", "https://p/feed"), self.NOW, since)
            self.assertEqual(len(lines), 2)   # reaches back eight days and keeps two
            self.assertIn("This week", lines[0])
            self.assertIn("Older", lines[1])
            self.assertIn(("Puzzle, x", "weekly", "https://p/feed"), feeds.config(context.Profile(
                {"feeds": [{"label": "Puzzle, x", "kind": "weekly", "value": "https://p/feed"}]}, "")))

        def dates_and_cleaning():
            self.assertEqual(feeds.parse_date("2026-10-20T12:00:00Z"),
                             dt.datetime(2026, 10, 20, 12, tzinfo=dt.timezone.utc))
            self.assertIsNone(feeds.parse_date("soon"))
            self.assertTrue(feeds.clean("word " * 100, limit=20).endswith("…"))
        table(self, [("config", config), ("rss", rss_and_atom), ("weekly", weekly), ("dates", dates_and_cleaning)])

    def test_structured_feeds(self):
        def espn():
            def ev(i, date, home, away, hs=None, as_=None, done=True, hw=None):
                return {"id": i, "date": date, "competitions": [{
                    "status": {"type": {"completed": done, "description": "Final" if done else "Scheduled"}},
                    "venue": {"fullName": "Arena"},
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": home}, "winner": hw,
                         "score": {"displayValue": hs} if hs else None},
                        {"homeAway": "away", "team": {"displayName": away}, "winner": (not hw) if hw is not None else None,
                         "score": {"displayValue": as_} if as_ else None}]}]}
            doc = {"team": {"displayName": "Devils"}, "events": [
                ev("1", "2026-10-20T23:00Z", "Devils", "Avalanche", "4", "3", hw=True),
                ev("2", "2026-10-17T17:00Z", "Capitals", "Devils", "4", "2", hw=True),
                ev("3", "2026-10-01T23:00Z", "Devils", "Flyers", "3", "2", hw=True),        # too old
                ev("4", "2026-10-22T23:00Z", "Devils", "Ducks", done=False),
                ev("5", "2026-11-20T23:00Z", "Devils", "Kings", done=False)]}             # too far out
            doc2 = {"events": [ev("4", "2026-10-22T23:00Z", "Devils", "Ducks", done=False),  # duplicate
                               ev("6", "2026-10-18T18:30Z", "Devils", "Charlotte", "2", "2", hw=False)]}
            team, results, upcoming = feeds.parse_espn([doc, doc2], self.NOW)
            self.assertEqual(team, "Devils")
            self.assertEqual([t for _, t in results], [
                "Avalanche 3, at Devils 4 (Final; Devils won)",
                "Charlotte 2, at Devils 2 (Final; Devils drew)",
                "Devils 2, at Capitals 4 (Final; Devils lost)"])
            self.assertEqual([t for _, t in upcoming], ["Ducks at Devils, Arena"])
            # a final with no score is no result (never a draw); a team name that matches neither side says the score only
            odd = {"team": {"displayName": "New Jersey Devils"}, "events": [
                ev("7", "2026-10-19T23:00Z", "Devils", "Blues", hw=True),
                ev("8", "2026-10-20T23:00Z", "Devils", "Avalanche", "4", "3", hw=True)]}
            _, results, _ = feeds.parse_espn([odd], self.NOW)
            self.assertEqual([t for _, t in results], ["Avalanche 3, at Devils 4 (Final)"])

        def weather():
            d = {"current": {"temperature_2m": 59.9, "weather_code": 0},
                 "daily": {"temperature_2m_max": [66.2, 68], "temperature_2m_min": [48, 42.4],
                           "weather_code": [3, 61], "precipitation_probability_max": [0, 70],
                           "sunset": ["2026-10-21T18:12", "2026-10-22T18:10"]}}
            self.assertEqual(feeds.parse_weather(d), [
                "Now: 60 degrees, clear",
                "Today: high 66, low 48, overcast, 0 percent chance of rain, sunset 18:12",
                "Tomorrow: high 68, low 42, light rain, 70 percent chance of rain, sunset 18:10"])

        def on_this_day():
            d = {"selected": [{"year": 1959, "text": "The Guggenheim Museum (pictured) opened.",
                               "pages": [{"content_urls": {"desktop": {"page": "https://w/G"}}}]}]}
            self.assertEqual(feeds.parse_onthisday(d), [(1959, "The Guggenheim Museum opened.", "https://w/G")])

        def wikipedia():
            page = lambda t, **k: dict({"title": t, "namespace": {"id": 0},
                                        "content_urls": {"desktop": {"page": f"https://w/{t}"}}}, **k)
            d = {"tfa": page("Thuggee", normalizedtitle="Thuggee", extract="Highway robbery. " * 40),
                 "mostread": {"articles": [page("B_page", rank=5, description="second"),
                                           page("Main_Page", rank=1), page("Special:Search", rank=2),
                                           page("A_page", rank=4, description="<i>first</i>")]
                              + [page(f"P{i}", rank=10 + i) for i in range(10)]},
                 "news": [{"story": '<!--Oct 21--><b><a href="./Leap_second">Leap seconds</a></b> are '
                                    '<a href="./x">abolished</a> .', "links": [page("Leap_second"), page("x")]}],
                 "dyk": [{"text": "... that Taku was a ship?",
                          "html": '... that <b><a href="https://w/SMS_Taku">Taku</a></b> was a ship?'}]}
            p = feeds.parse_featured(d)
            self.assertEqual(p["featured"][0], "Thuggee")
            self.assertLessEqual(len(p["featured"][1]), 401)
            self.assertEqual(p["mostread"][:2], [("A page", "first", "https://w/A_page"),
                                                 ("B page", "second", "https://w/B_page")])
            self.assertEqual(len(p["mostread"]), 8)                       # Main_Page and Special: left out, top eight kept
            self.assertEqual(p["news"], [("Leap seconds are abolished.", "https://w/Leap_second")])
            self.assertEqual(p["dyk"], [("... that Taku was a ship?", "https://w/SMS_Taku")])
            empty = feeds.parse_featured({"mostread": {"articles": []}})   # a day without news or a featured article
            self.assertEqual(empty, {"featured": None, "mostread": [], "news": [], "dyk": []})
            with mock.patch.object(feeds, "fetch", return_value=json.dumps(d).encode()) as f:
                lines = feeds.gather(("Wikipedia", "wikipedia", "featured"), self.NOW, self.NOW)
            self.assertIn("/feed/featured/2026/10/2", f.call_args[0][0])
            self.assertIn("### In the news", lines)
            self.assertIn("- Leap seconds are abolished. (https://w/Leap_second)", lines)
        table(self, [("espn", espn), ("weather", weather), ("on this day", on_this_day), ("wikipedia", wikipedia)])


class FeedLimits(unittest.TestCase):
    def test_only_web_addresses(self):
        for url in ("file:///etc/hosts", "ftp://example.org/x", "/etc/hosts"):
            with self.assertRaises(ValueError):
                feeds.fetch(url)

    def test_oversized_responses_are_skipped(self):
        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return b"x" * (n if n > 0 else 10)
        with mock.patch.object(feeds, "_open", return_value=Resp()):
            with self.assertRaises(ValueError):
                feeds.fetch("https://example.org/feed", limit=100)
            self.assertEqual(len(Resp().read(50)), 50)


class ExitCodes(unittest.TestCase):
    def test_voices_measured_codes(self):
        import coaches
        with tempfile.TemporaryDirectory() as d, helpers.home(fresh_home(d)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            with mock.patch.dict(os.environ, {"HARMONICFITNESS_FAKE_LOCAL_ENGINE": "1"}):
                code = cli.run(lambda: coaches.main(["measured", "Coach Julius", "--engine", "local"]))
            self.assertEqual(code, cli.ISSUES, err.getvalue())   # estimated: nothing measured in a fresh copy
            with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": ""}):
                code = cli.run(lambda: coaches.main(["measured", "Coach Reed"]))
            self.assertEqual(code, cli.OK, err.getvalue())   # a web coach, even pending, needs no smoke test


class BuildCase(unittest.TestCase):
    """tools/build.py lints, gates on the menu and renders in one process; here the lint's prediction and the
    render itself are stood in for, and everything around them (the coach, the route, the menu, the delivery,
    the record, the exit codes) is real."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = self.tmp.name
        self.home = fresh_home(d)
        self.phone = os.path.join(d, "phone")
        os.makedirs(self.phone)
        prof = os.path.join(self.home, "settings.toml")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        write_file(prof, re.sub(r"^deliver_to = .*$", f"deliver_to = {json.dumps(self.phone.replace(os.sep, '/'))}",
                                text, flags=re.M))
        self.folder = os.path.join(self.home, "workouts", "2026-10-25-test-25")
        self.draft = os.path.join(self.folder, "2026-10-25-test-25.draft.txt")
        os.makedirs(self.folder)
        self.copy_draft(self.draft)
        self.runs, self.lints, self.follows = [], [], []
        self.drift = 0.0
        self.render_fails = None
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(helpers.home(self.home))
        self.stack.enter_context(mock.patch.dict(os.environ, {"HARMONICFITNESS_FAKE_LOCAL_ENGINE": "1"}))
        self.stack.enter_context(mock.patch.object(render, "run", side_effect=self.fake_run))
        self.stack.enter_context(mock.patch.object(render, "follow", side_effect=self.fake_follow))
        self.lint_patch = mock.patch.object(tts_build, "lint", side_effect=self.fake_lint)
        self.lint_patch.start()
        self.addCleanup(lambda: self.lint_patch and self.lint_patch.stop())

    def real_lint(self):
        """Most tests stand the lint in; these run it for real on the build's parsed draft."""
        self.lint_patch.stop()
        self.lint_patch = None

    def small_draft(self, text):
        path = os.path.join(self.folder, "small.draft.txt")
        write_file(path, text)
        self.write_menu(path)
        return path

    def copy_draft(self, path):
        """The fixture draft (from before the menu, so it declares nothing) with a movements: line naming
        what its text names, and today's menu beside it."""
        helpers.draft_with_menu(os.path.join(ROOT, "tests", "fixtures", "example.draft.txt"), path, self.home)

    def write_menu(self, draft_path, today=None, health=None):
        helpers.menu_for(draft_path, self.home, today=today, health_sha256=health)

    def fake_lint(self, segments, voice=None, **kw):
        self.lints.append(dict(kw, voice=voice))
        return tts_build.Report(rows=[], strict=False, wpm=185.0)

    def fake_run(self, segments, voice, out, **kw):
        self.runs.append(dict(kw, voice=voice, out=out))
        if self.render_fails:
            os.write(2, b"render failed for a test reason\n")   # as a native library would, on the descriptor
            raise SystemExit(self.render_fails)
        write_file(out, "x")
        with open(os.path.splitext(out)[0] + ".build.json", "w", encoding="utf-8") as f:
            json.dump({"route": voice.get("route", "local")}, f)
        return self.drift

    def fake_follow(self, voice, draft_path, **kw):
        self.follows.append(dict(kw, voice=voice, draft_path=draft_path))

    def build(self, *extra, estimated_ok=True, draft_path=None):
        import build
        argv = [draft_path or self.draft, "Test build", *(["--allow-estimated"] if estimated_ok else []), *extra]
        self.out, self.err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(self.out), contextlib.redirect_stderr(self.err):
            return cli.run(lambda: build.main(argv))

    def said(self):
        return self.out.getvalue() + self.err.getvalue()

    def add_web_coach(self, estimate=True):
        """Coach Reed on Fish Audio with a saved voice, and (by default) only an estimate of his pace."""
        folder = os.path.join(self.home, "coaches", "coach-reed-fish")
        os.makedirs(folder, exist_ok=True)
        write_file(os.path.join(folder, "persona.md"), context.persona_text(
            {"name": "Coach Reed", "kind": "web", "service": "fish", "voice_id": "fish-model-1"},
            "## How this coach talks\n"))
        if estimate:
            v = cloud.voice_for(personas.Persona("coach-reed", folder, {"name": "Coach Reed", "kind": "web",
                                "service": "fish", "voice_id": "fish-model-1"}, ""), "fish")
            voices.record_estimate(v, 150.0, 10.0)

    def web_build(self, *extra, key=True, draft_path=None, **more):
        env = {"FISH_AUDIO_API_KEY": "test-key" if key else ""}
        env.update(more)
        with mock.patch.dict(os.environ, env):
            return self.build("--coach", "Coach Reed", *extra, estimated_ok=False, draft_path=draft_path)

    def fake_service(self, service):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import fakes
        fake = fakes.FakeService(fakes.design_answer(service))
        fake.__enter__()
        self.addCleanup(fake.__exit__)
        return fake


class InProcessBuild(BuildCase):
    """The menu gate, the lint, the exit codes, the delivery and the record of a build."""

    def test_the_real_lint_stops_a_draft_a_voice_cant_read(self):
        self.real_lint()
        path = self.small_draft("movements: box breathing\n@@ 60 | A\nBreathe in for 4 counts, then out. [hold]\n")
        self.assertEqual(self.build(draft_path=path), cli.ISSUES, self.said())
        self.assertIn("digits", self.said())
        self.assertFalse(os.path.exists(os.path.join(self.folder, "Test build.txt")))
        self.assertEqual(self.runs, [])

    def test_a_stale_menu_stops_a_render_and_a_lint_alike(self):
        # since 0.39.0 a lint holds the menu as the build does, so a clean lint means a clean menu check
        self.write_menu(self.draft, today="2026-10-20")
        self.assertEqual(self.build(), cli.ISSUES, self.said())
        self.assertIn("2026-10-20", self.said())
        self.assertEqual(self.runs, [])
        self.assertEqual(self.build("--lint-only"), cli.ISSUES, self.said())
        self.assertIn("2026-10-20", self.said())

    def test_a_changed_health_file_stops_the_render(self):
        with open(os.path.join(self.home, "health.md"), "a", encoding="utf-8") as f:
            f.write("- Unlisted: a new problem since the brief\n")
        self.assertEqual(self.build(), cli.ISSUES, self.said())
        self.assertIn("health.md changed", self.said())
        self.assertEqual(self.runs, [])

    def test_a_copy_of_the_smoke_test_elsewhere_needs_a_menu(self):
        copy = os.path.join(self.folder, "smoke-test.draft.txt")   # the smoke test is known by its place, not its name
        shutil.copy(paths.SMOKE_DRAFT, copy)
        self.assertEqual(self.build(draft_path=copy), cli.ISSUES, self.said())
        self.assertIn("no menu", self.said())
        self.assertEqual(self.runs, [])

    def test_exit_codes(self):
        def unmeasured_is_3():
            self.assertEqual(self.build(estimated_ok=False), cli.UNMEASURED, self.said())

        def unknown_coach_is_64():
            self.assertEqual(self.build("--coach", "Nobody At All", estimated_ok=False), cli.USAGE, self.said())
            self.assertNotIn("measured", self.said())

        def a_bad_tolerance_is_64():
            for bad in ("nan", "-0.1", "0.6", "inf", "lots"):
                self.assertEqual(self.build("--tolerance", bad), cli.USAGE, bad)
            self.assertEqual(self.lints, [])

        def a_web_coach_without_its_key_is_64():
            self.assertEqual(self.web_build(key=False), cli.USAGE, self.said())
            self.assertIn("FISH_AUDIO_API_KEY", self.said())

        def an_engine_override_on_a_web_coach_is_64():
            self.assertEqual(self.web_build("--engine", "local"), cli.USAGE, self.said())

        def drift_is_2_and_still_delivers():
            self.drift = 0.07
            self.assertEqual(self.build(), cli.DRIFT, self.said())
            self.assertTrue(os.path.exists(os.path.join(self.phone, "Test build.mp3")))   # a workout, as it is
            self.assertIn("runs long by 7.0%", self.said())
            outcome = [r for r in records.build_records() if r["kind"] == "outcome"][-1]
            self.assertEqual((outcome["event"], outcome["drift"]), ("delivered", 0.07))
            self.runs.clear()

        def rows(*named):
            for name, row in named:
                self.lints.clear()
                with self.subTest(name):
                    row()
                    self.assertEqual(self.runs, [])
        rows(("3", unmeasured_is_3), ("unknown coach", unknown_coach_is_64), ("tolerance", a_bad_tolerance_is_64),
             ("2", drift_is_2_and_still_delivers))
        self.add_web_coach()   # the listener's own coach is the default from here
        rows(("no key", a_web_coach_without_its_key_is_64), ("engine", an_engine_override_on_a_web_coach_is_64))

    def test_a_failed_copy_keeps_the_mp3_and_leaves_no_partial_file(self):
        import build

        def half_copy(src, dst):
            write_file(dst, "half an mp3")
            raise OSError("the disk filled up")
        with mock.patch.object(build.shutil, "copyfile", side_effect=half_copy):
            self.assertEqual(self.build(), 0, self.said())
        self.assertIn("Couldn't copy", self.said())
        self.assertEqual(os.listdir(self.phone), [])   # neither the MP3 nor a .part
        self.assertTrue(os.path.exists(os.path.join(self.folder, "Test build.mp3")))

    def test_each_build_has_an_id_and_one_outcome_line(self):
        self.assertEqual(self.build(), 0, self.said())
        build_id = self.runs[0]["build_id"]
        self.assertRegex(build_id, r"^[0-9a-f]{12}$")
        lines = list(records.build_records())
        self.assertEqual([(r["event"], r["build_id"]) for r in lines], [("delivered", build_id)])
        self.assertFalse(any(records.is_mp3(r) for r in lines))   # an outcome line is never counted as an MP3
        with open(os.path.join(paths.LOGS, "Test build.log"), encoding="utf-8") as f:
            self.assertIn(f"({build_id})", f.read())
        self.render_fails = 1   # a stopped render leaves a stopped line
        self.assertEqual(self.build(), 1)
        line = list(records.build_records())[-1]
        self.assertEqual((line["event"], line["stage"], line["build_id"]), ("stopped", "render", self.runs[1]["build_id"]))
        self.assertFalse(records.built(line["draft_sha256"]))


class WebBuild(BuildCase):
    """A build with a web coach: nothing sent past an allowance, nothing made for a build that stops."""

    def test_max_chars_stops_before_sending(self):
        """--max-chars is a web build's allowance: the lint stops a longer script before the render is reached."""
        self.real_lint()
        self.add_web_coach()
        fake = self.fake_service("fish")   # a fake service, so "nothing sent" can be counted
        path = self.small_draft("movements: box breathing\n@@ 10 | A\n"
                                "Breathe in, and all the way out. Then once more, slow and easy. [hold]\n")
        self.assertEqual(self.web_build("--max-chars", "50", draft_path=path, HARMONICFITNESS_FISH_URL=fake.url),
                         cli.ISSUES, self.said())
        self.assertIn("--max-chars", self.said())
        self.assertIn("at most 50", self.said())
        self.assertEqual(fake.requests, [])
        self.assertEqual(self.runs, [])
        (line,) = list(records.build_records())
        self.assertEqual((line["event"], line["stage"]), ("stopped", "lint"))
        self.assertEqual(self.web_build("--max-chars", "5000", draft_path=path, HARMONICFITNESS_FISH_URL=fake.url),
                         0, self.said())   # the same script under a roomier allowance builds

    def test_build_refuses_follow_on_a_cloud_route(self):
        self.add_web_coach()
        self.assertEqual(self.web_build("--follow"), cli.USAGE, self.said())
        self.assertIn("billed", self.said())
        self.assertEqual(self.follows, [])

    def test_get_cost(self):
        def get_cost(*args):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cli.run(lambda: context.main(["get", "cost", *args]))
            return code, out.getvalue()
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test-key"}):
            got = json.loads(get_cost("--coach", "Coach Reed", "--json")[1])   # pending: the design is added
            self.assertTrue(got["pending_design"])
            self.assertEqual(got["design_usd"], cloud.services()["fish"]["design_usd"])
        self.assertEqual(get_cost("--coach", "Coach Andy")[0], cli.USAGE)   # a local coach
        self.add_web_coach()
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "test-key"}):
            code, text = get_cost("--coach", "Coach Reed", "--json")
            self.assertEqual(code, 0)
            got = json.loads(text)
            self.assertEqual((got["coach"], got["service"]), ("Coach Reed", "fish"))
            self.assertEqual((got["chars"], got["ceiling"]), (30000, 30000))
            self.assertEqual(got["usd"], round(cloud.estimate("fish", got["model"], ["x" * 30000])[1], 4))
            self.assertFalse(got["pending_design"])
            self.assertIsNone(got["design_usd"])
            code, text = get_cost("--coach", "Coach Reed", "--chars", "1000", "--json")
            self.assertEqual(json.loads(text)["chars"], 1000)
            code, text = get_cost("--coach", "Coach Reed")   # the plain form is a sentence
            self.assertIn("Fish Audio", text)
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": ""}):
            self.assertEqual(get_cost("--coach", "Coach Reed")[0], cli.USAGE)   # a coach that can't speak

    def test_a_pending_coach_is_made_once(self):
        # no coach named: the keyed service's default is made, once across two builds, in me/, never in the stock
        stock = os.path.join(self.tmp.name, "stock")   # only the real stock: Coach Andy and the web defaults
        shutil.copytree(paths.SHIPPED, stock, ignore=shutil.ignore_patterns("coach-julius", "coach-solo"))
        self.stack.enter_context(mock.patch.object(paths, "SHIPPED", stock))
        inworld = self.fake_service("inworld")
        env = {"INWORLD_API_KEY": "test-key", "FISH_AUDIO_API_KEY": "", "ELEVENLABS_API_KEY": "",
               "GEMINI_API_KEY": "", "HARMONICFITNESS_INWORLD_URL": inworld.url, "HARMONICFITNESS_RETRY_WAIT": "0",
               "HARMONICFITNESS_FAKE_LOCAL_ENGINE": "0"}
        with mock.patch.dict(os.environ, env):
            for _ in range(2):
                self.assertEqual(self.build(estimated_ok=False), 0, self.said())
        self.assertEqual([(r["voice"]["name"], r["voice"]["route"]) for r in self.runs],
                         [("Coach Owen", "inworld")] * 2)
        posts = [r.path.split(":")[-1] for r in inworld.requests if r.method == "POST"]
        self.assertEqual(posts[:2], ["design", "publish"])   # made once across two builds
        self.assertNotIn("design", posts[2:])   # the rest: its sample
        with open(os.path.join(paths.PERSONAS, "coach-owen-inworld", "persona.md"), encoding="utf-8") as f:
            self.assertIn("voice_id", f.read())
        with open(os.path.join(stock, "coach-owen-inworld", "persona.md"), encoding="utf-8") as f:
            self.assertIn('pending = "design"', f.read())
        # a named pending coach: made the first time it's used, and the made voice speaks
        self.runs.clear()
        self.assertEqual(personas.lookup("Coach Reed").pending, "design")
        fish = self.fake_service("fish")
        env = {"HARMONICFITNESS_FISH_URL": fish.url, "HARMONICFITNESS_RETRY_WAIT": "0"}
        self.assertEqual(self.web_build(**env), 0, self.said())
        self.assertIn("Coach Reed is made the first time it's used", self.said())
        self.assertEqual(self.web_build(**env), 0, self.said())
        self.assertNotIn("made the first time", self.said())
        posts = [r.path for r in fish.requests if r.method == "POST"]
        # one design and one save in all, then the made coach's sample (spoken once, at the first build)
        self.assertEqual(posts[:2], ["/v1/voice-design", "/model"])
        self.assertEqual(set(posts[2:]), {"/v1/tts"})
        self.assertEqual(len(self.runs), 2)
        self.assertEqual(self.runs[0]["voice"]["voice_id"], "fish-model-1")   # the made voice, not the stale persona
        self.assertEqual(personas.lookup("Coach Reed").voice_id, "fish-model-1")

    def test_a_pending_coach_is_never_paid_for_when_the_build_stops(self):
        self.assertEqual(personas.lookup("Coach Reed").pending, "design")
        fake = self.fake_service("fish")
        env = {"HARMONICFITNESS_FISH_URL": fake.url, "HARMONICFITNESS_RETRY_WAIT": "0"}
        self.assertEqual(self.web_build("--lint-only", **env), 0, self.said())   # --lint-only never makes one
        self.assertEqual((fake.requests, len(self.lints), self.runs), ([], 1, []))
        self.write_menu(self.draft, today="2026-10-20")   # a stale menu: the gate stops it
        self.assertEqual(self.web_build(**env), cli.ISSUES, self.said())
        self.assertEqual(fake.requests, [])
        self.write_menu(self.draft)
        fake.answer = lambda r: (401, {}, b'{"message": "Invalid api key"}')   # a failed make stops the build
        self.assertEqual(self.web_build(**env), cli.SERVICE, self.said())
        self.assertEqual(self.runs, [])   # linted first, at the estimated pace, and never rendered
        fake.requests.clear()
        self.real_lint()
        path = self.small_draft("movements: box breathing\n@@ 60 | A\nBreathe in for 4 counts. [hold]\n")
        self.assertEqual(self.web_build(draft_path=path, **env), cli.ISSUES, self.said())   # the lint stops it
        self.assertEqual(fake.requests, [])   # nothing designed or saved, so nothing paid for
        self.assertEqual(personas.lookup("Coach Reed").pending, "design")
        self.assertEqual(self.runs, [])


class RenderGates(unittest.TestCase):
    """render.run checks ffmpeg and the output name before a single clip is rendered (and billed)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = fresh_home(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(helpers.home(self.home))
        self.stack.enter_context(mock.patch.dict(os.environ, {"HARMONICFITNESS_FAKE_LOCAL_ENGINE": "1"}))
        self.stack.enter_context(mock.patch.object(engines, "speaker", side_effect=AssertionError("nothing may render")))
        self.draft = os.path.join(self.tmp.name, "x.draft.txt")
        shutil.copy(os.path.join(ROOT, "tests", "fixtures", "example.draft.txt"), self.draft)

    def test_the_output_name_and_ffmpeg_are_checked_before_any_clip(self):
        voice = personas.voice_for(personas.lookup("Coach Julius"), "local")
        segments = parse("@@ 30 | A\nHello.\n")
        with self.assertRaises(errors.UsageError):
            render.run(segments, voice, os.path.join(self.tmp.name, "x.ogg"), self.draft, "0" * 64)
        with mock.patch.object(render.ffmpeg_tool, "exe", return_value=None), self.assertRaises(errors.PROBLEMS) as got:
            render.run(segments, voice, os.path.join(self.tmp.name, "x.mp3"), self.draft, "0" * 64)
        self.assertIn("ffmpeg", str(got.exception))


class Locks(unittest.TestCase):
    def test_cache_prune_waits_for_the_render_lock(self):
        import locks
        with tempfile.TemporaryDirectory() as d, mock.patch.object(locks, "render_lock") as lock:
            lock.return_value.__enter__ = lambda *a: None
            lock.return_value.__exit__ = lambda *a: False
            cache.prune(0, d)
        self.assertTrue(lock.called)

    def test_a_render_waits_for_a_render_and_stops_a_render_ahead(self):
        def hold(d, ready, body, follow=False):
            return subprocess.Popen([sys.executable, "-c", "\n".join((
                "import os, sys, time; sys.path.insert(0, 'tools'); import render",
                f"with render.render_lock({d!r}, follow={follow}):",
                f"    open({ready!r}, 'w').close()", *body))], cwd=ROOT)

        def wait_for(path):
            deadline = time.time() + 20
            while not os.path.exists(path) and time.time() < deadline:
                time.sleep(0.01)
        with tempfile.TemporaryDirectory() as d:
            ready = os.path.join(d, "ready")
            holder = hold(d, ready, ["    time.sleep(0.6)"])
            try:
                wait_for(ready)
                started = time.time()
                with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    with render.render_lock(d):
                        waited = time.time() - started
                self.assertGreater(waited, 0.2)   # the first render still held the lock
                self.assertIn("waiting", out.getvalue())
            finally:
                holder.wait(timeout=20)
        with tempfile.TemporaryDirectory() as d:
            ready, saw = os.path.join(d, "ready"), os.path.join(d, "saw-stop")
            ahead = hold(d, ready, ["    for _ in range(400):",
                                    f"        if os.path.exists(render.stop_file({d!r})):",
                                    f"            open({saw!r}, 'w').close(); break",
                                    "        time.sleep(0.05)"], follow=True)
            try:
                wait_for(ready)
                with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
                    with render.render_lock(d):
                        pass
                self.assertTrue(os.path.exists(saw), "the render ahead was asked to stop")
                self.assertIn("running ahead", out.getvalue())
            finally:
                ahead.wait(timeout=30)


class PaceFile(unittest.TestCase):
    V1 = {"name": "One", "key": "k1", "engine": "chatterbox", "model": "m"}
    V2 = {"name": "Two", "key": "k2", "engine": "qwen3", "model": "m"}

    def test_two_voices_are_kept_and_a_damaged_file_is_set_aside(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "cache", "voice-pace.json")
            with mock.patch.object(paths, "PACE_FILE", path):
                voices.record_rate(self.V1, 600.0, 40.0)
                voices.record_rate(self.V2, 700.0, 50.0)
                voices.record_rate(self.V1, 600.0, 40.0)
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.assertEqual(sorted(r["name"] for r in data.values()), ["One", "Two"])
                self.assertEqual(voices.pace(self.V1), (15.0, True))
                with open(path, "a", encoding="utf-8") as f:
                    f.write("\n{garbage")
                with open(path, encoding="utf-8") as f:
                    damaged = f.read()
                with self.assertRaises(errors.PROBLEMS):
                    voices.record_rate(self.V2, 700.0, 50.0)
                kept = glob.glob(path + ".corrupt-*")
                self.assertEqual(len(kept), 1)
                with open(kept[0], encoding="utf-8") as f:
                    self.assertEqual(f.read(), damaged)   # set aside, not overwritten
                self.assertFalse(os.path.exists(path))
                with self.assertRaises(errors.PROBLEMS):
                    write_file(path, "{nope")
                    voices.check_pace_file()      # what render.py calls before loading a model


class Hooks(unittest.TestCase):
    """The pre-push hook checks every pushed commit (one push of several branches, as git sends it)."""
    ZERO = "0" * 40

    def git(self, *args):
        out = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                              "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                             cwd=self.repo, capture_output=True, text=True, encoding="utf-8", check=True)
        return out.stdout.strip()

    def commit(self, msg, add=None, remove=None):
        if add:
            write_file(os.path.join(self.repo, add), "x\n")
            self.git("add", "-f", add)
        if remove:
            self.git("rm", "-q", "--cached", remove)
        self.git("commit", "-q", "--allow-empty", "-m", msg)
        return self.git("rev-parse", "HEAD")

    def push(self, *lines):
        hook = os.path.join(ROOT, "tools", "hooks", "pre-push")
        return subprocess.run(["sh", hook, "origin", "url"], cwd=self.repo, capture_output=True, text=True,
                              encoding="utf-8", input="".join(f"refs/heads/{b} {local} refs/heads/{b} {remote}\n"
                                                              for b, local, remote in lines))

    def test_the_pre_push_hook(self):
        if not shutil.which("git"):
            self.skipTest("no git")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = tmp.name
        self.git("init", "-q", "-b", "main")
        base = self.commit("base")

        def branch(name):
            self.git("checkout", "-q", "-b", name, base)
        branch("leak")   # added, then removed: still refused
        self.commit("oops", add="me/health.md")
        leak = self.commit("remove", remove="me/health.md")
        branch("old")   # the old layout's health file
        old = self.commit("old layout", add="knowledge/health.md")
        branch("fix")   # removing a file already pushed is allowed (that's the fix)
        pushed = self.commit("oops", add="me/log.md")
        self.git("update-ref", "refs/remotes/origin/fix", pushed)
        fix = self.commit("remove", remove="me/log.md")
        branch("clean")
        clean = self.commit("engine change", add="tools/x.py")
        out = self.push(("leak", leak, self.ZERO), ("old", old, base))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("me/health.md", out.stdout)
        self.assertIn("knowledge/health.md", out.stdout)
        out = self.push(("fix", fix, pushed), ("clean", clean, self.ZERO), ("clean", clean, base))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


class QuickSetup(unittest.TestCase):
    """setup = "quick": what the quick start leaves for later is a note, not an issue."""
    SETTINGS = ('name = "Sam"\nexperience = "novice"\n{stage}'
                '\n[[feeds]]\nlabel = "[Team]"\nkind = "espn"\nvalue = "[sport/league/team]"\n')
    PROSE = "# Profile\n- Neighborhood: [where you live]\n\n## Topics\n- [a topic you follow]\n"

    def issues(self, stage):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "profile.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(profile_text(self.SETTINGS.format(stage=stage), self.PROSE))
            return check._check_profile(path)

    def test_quick_setup_unfilled_are_notes_and_full_setup_issues(self):
        found = self.issues('setup = "quick"')
        unfilled = [i for i in found if "isn't filled in yet" in i.message]
        self.assertGreaterEqual(len(unfilled), 3, found)
        self.assertTrue(all(i.note for i in found), [i for i in found if not i.note])
        self.assertTrue(any("finish setting me up" in i.message for i in found))
        found = self.issues("")
        unfilled = [i for i in found if "isn't filled in yet" in i.message]
        self.assertGreaterEqual(len(unfilled), 3, found)
        self.assertTrue(all(not i.note for i in unfilled))
        self.assertFalse(any("finish setting me up" in i.message for i in found))


class Context(unittest.TestCase):
    PROSE = "# Profile\n\n## Basics\n- Neighborhood: [neighborhood, city]\n- Goals right now: strength\n"

    def test_delivery_folders(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "GoogleDrive-a", "W"), os.path.join(d, "GoogleDrive-b", "W")
            os.makedirs(a)
            os.makedirs(b)
            p = context.Profile({"deliver_to": f"{d}/GoogleDrive-*/W"}, "")
            self.assertEqual(context.delivery_folders(p)[1], [a, b])   # stars expand
            self.assertEqual(context.delivery_folders(context.Profile({"deliver_to": f"{d}/no"}, ""))[1], [])
            here = os.path.join(d, "Drive", "W")
            os.makedirs(here)
            p = context.Profile({"deliver_to": [f"{d}/Mac-*/W", f"{d}/Drive/W", "[a folder]"]}, "")
            pattern, found = context.delivery_folders(p)
            self.assertEqual([os.path.normpath(f) for f in found], [here])   # only the folder this computer has
            self.assertIn(" or ", pattern)
            self.assertEqual(context.delivery_patterns(context.Profile({"deliver_to": []}, "")), [])
            self.assertEqual(context.delivery_patterns(context.Profile({"deliver_to": "[a folder]"}, "")), [])

    def test_old_and_new_schemas_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            profile = os.path.join(d, "profile.md")
            write_file(profile, self.PROSE)
            with self.assertRaises(errors.PROBLEMS) as e:
                context.profile(profile)
            self.assertIn("older", str(e.exception.code))
            write_file(profile, f"+++\nschema = {store.SCHEMA + 1}\n+++\n" + self.PROSE)
            with self.assertRaises(errors.PROBLEMS) as e:
                context.profile(profile)
            self.assertIn("newer", str(e.exception.code))


class ProfileAndHealth(unittest.TestCase):
    """The health file's limits and clinician rules, as read and as check notes them; and the level, set alone."""

    HEALTH = """# Health

## Active injuries and limitations
- Right wrist: invented strain.

## Clinician rules
- No jumping until cleared.
[what your clinician told you]
<!-- a note for the listener -->

## Other
- not a rule
"""
    ROW = """[[limits]]
area = "wrist"
side = "right"
level = "delicate"
rehab = ["calf-raise"]
note = "Therapist: no weight through the hand."
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name

    def health_file(self, settings, prose=None):
        path = os.path.join(self.dir, "health.md")
        write_file(path, f"+++\nschema = {store.SCHEMA}\n{settings}\n+++\n{prose or self.HEALTH}")
        return path

    def test_health_limits_and_clinician_rules(self):
        def limits_and_clinician_lines():
            h = health_md.health(self.health_file(self.ROW))
            self.assertEqual(health_md.limits(h), [catalog.Limit("wrist", "right", "delicate", [], ["calf-raise"],
                                                               "Therapist: no weight through the hand.")])
            self.assertEqual(health_md.clinician_lines(h), ["wrist delicate right: Therapist: no weight through the hand.",
                                                          "No jumping until cleared."])
            bare = health_md.health(self.health_file('[[limits]]\narea = "knee"\nlevel = "off-limits"\n'))
            self.assertEqual(health_md.clinician_lines(bare), ["knee off-limits", "No jumping until cleared."])
            self.assertEqual(health_md.limits(health_md.health(self.health_file(""))), [])

        def bad_limit_rows():
            bad = ('[[limits]]\narea = "elbowish"\nlevel = "delicate"\n\n[[limits]]\narea = "knee"\n'
                   'side = "up"\nlevel = "off-limits"\n\n[[limits]]\narea = "knee"\nlevel = "sore"\n\n'
                   '[[limits]]\narea = "knee"\nlevel = "off-limits"\n')
            path = self.health_file(bad)
            got = health_md.limits(health_md.health(path))
            self.assertEqual([(l.area, l.side, l.level) for l in got], [("knee", "both", "off-limits")])
            msgs = [i.message for i in check.check([path]) if not i.note]
            self.assertEqual(len(msgs), 3, msgs)
            self.assertTrue(any("elbowish" in m and "knee" in m for m in msgs))     # names the valid areas
            self.assertTrue(any("left, right or both" in m for m in msgs))
            self.assertTrue(any("off-limits or delicate" in m for m in msgs))

        def malformed_flags_or_rehab():
            for bad in ('flags = "floor"', 'rehab = "towel-scrunch"', 'flags = ["wobbly"]', 'rehab = [3]'):
                path = self.health_file(f'[[limits]]\narea = "knee"\nlevel = "off-limits"\n{bad}\n')
                self.assertEqual(health_md.limits(health_md.health(path)), [], bad)
                msgs = [i.message for i in check.check([path]) if not i.note]
                self.assertTrue(any("[[limits]] row 1" in m and "ignored" in m for m in msgs), msgs)
            good = self.health_file('[[limits]]\narea = "knee"\nlevel = "off-limits"\nflags = ["floor"]\n')
            self.assertEqual(health_md.limits(health_md.health(good))[0].flags, ["floor"])

        def rehab_ids():
            issues = check.check([self.health_file(self.ROW.replace('"calf-raise"', '"goblet-squat"'))])
            self.assertTrue(any(not i.note and "goblet-squat" in i.message for i in issues), issues)   # not rehab
            issues = check.check([self.health_file(self.ROW.replace('"calf-raise"', '"towel-scrunch"'))])
            self.assertFalse(any(not i.note and "towel-scrunch" in i.message for i in issues), issues)   # a rehab entry
            issues = check.check([self.health_file(self.ROW.replace('"calf-raise"', '"no-such-move"'))])
            self.assertTrue(any(i.note and "no-such-move" in i.message for i in issues))   # unknown: a note
            self.assertFalse(any(not i.note for i in issues))

        def unlisted_injuries():
            for line in ("- Unlisted: invented jaw soreness.", "- unlisted: invented jaw soreness."):
                path = self.health_file("", self.HEALTH.replace("- Right wrist: invented strain.", line))
                self.assertFalse(health_md.prose_injuries(health_md.health(path)), line)
                self.assertFalse(any("have no [[limits]]" in i.message for i in check.check([path])))
            both = self.HEALTH.replace("- Right wrist: invented strain.", "- Unlisted: invented jaw.\n- Left knee: invented.")
            self.assertTrue(health_md.prose_injuries(health_md.health(self.health_file("", both))))

        def prose_injuries_without_limits():
            path = self.health_file("")
            self.assertTrue(health_md.prose_injuries(health_md.health(path)))
            found = [i for i in check.check([path]) if "no rule" in i.message or "[[limits]]" in i.message]
            self.assertEqual(len(found), 1)
            self.assertFalse(found[0].note)
            self.assertIn("injuries written in prose have no [[limits]] entry", found[0].message)
            with_row = health_md.health(self.health_file(self.ROW))
            self.assertTrue(health_md.prose_injuries(with_row))
            self.assertFalse(any("have no [[limits]]" in i.message for i in check.check([with_row.path])))
            none = self.HEALTH.replace("- Right wrist: invented strain.", "- None right now.")
            self.assertFalse(health_md.prose_injuries(health_md.health(self.health_file("", none))))
            commented = self.HEALTH.replace("- Right wrist: invented strain.",
                                            "- None right now.\n<!-- e.g.\n- Right wrist: strain\n-->")
            self.assertFalse(health_md.prose_injuries(health_md.health(self.health_file("", commented))))

        def a_rule_label_is_not_the_clinicians_words():
            path = self.health_file("", "# Health\n\n## Clinician rules\n- Rule: No deep knee bends.\n"
                                        "- No pushing through wrist pain.\n"
                                        "- Rule: [what a doctor or physical therapist told you]\n")
            self.assertEqual(health_md.clinician_lines(health_md.health(path)),
                             ["No deep knee bends.", "No pushing through wrist pain."])
        table(self, [("limits", limits_and_clinician_lines), ("bad rows", bad_limit_rows),
                     ("malformed", malformed_flags_or_rehab), ("rehab ids", rehab_ids),
                     ("unlisted", unlisted_injuries), ("prose", prose_injuries_without_limits),
                     ("rule label", a_rule_label_is_not_the_clinicians_words)])

    def test_set_experience_keeps_every_other_line(self):
        home = fresh_home(self.dir)
        path = os.path.join(home, "profile.md")
        with open(path, encoding="utf-8") as f:
            before = f.read()

        def set_level(level):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = cli.run(lambda: context.main(["set", "experience", level]))
            return code, out.getvalue()
        with helpers.home(home):
            self.assertEqual(set_level("novice"), (0, "experience = novice\n"))
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), before.replace('experience = ""', 'experience = "novice"'))
            self.assertEqual(set_level("expert")[0], cli.USAGE)
            # a profile with no experience line gets one, with its comment, inside the settings block
            write_file(path, '+++\nschema = 6\nname = "Sam"\n+++\n# My Profile\n')
            set_level("advanced")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith('+++\nschema = 6\nname = "Sam"\n# Your training level'), text)
        self.assertIn('experience = "advanced"\n+++\n# My Profile\n', text)


class CachePrune(unittest.TestCase):
    def test_prune_clips_and_logs_by_age(self):
        month = time.time() - 60 * 86400
        with tempfile.TemporaryDirectory() as d:   # only clips unused for the window
            old, new, pace = (os.path.join(d, n) for n in ("old.pcm", "new.pcm", "voice-pace.json"))
            for p in (old, new, pace):
                write_file(p, "abcd")
            os.utime(old, (month, month))
            os.utime(pace, (month, month))
            self.assertEqual(cache.prune(45, d), (1, 4))
            self.assertEqual(sorted(n for n in os.listdir(d) if not n.startswith(".")), ["new.pcm", "voice-pace.json"])
            self.assertEqual(cache.size(d), (1, 4))
        with tempfile.TemporaryDirectory() as d:   # only old render logs
            names = ("old.log", "old.log.1", "new.log", "builds.jsonl", "builds.jsonl.lock", "told.jsonl", "notes.txt")
            for n in names:
                write_file(os.path.join(d, n), "abcd")
                if n != "new.log":
                    os.utime(os.path.join(d, n), (month, month))
            self.assertEqual(cache.prune_logs(30, d), (2, 8))
            self.assertEqual(sorted(os.listdir(d)),
                             ["builds.jsonl", "builds.jsonl.lock", "new.log", "notes.txt", "told.jsonl"])
        with tempfile.TemporaryDirectory() as d, helpers.home(d):   # --logs-older alone leaves the clips
            clip, log = os.path.join(paths.CACHE, "old.pcm"), os.path.join(paths.LOGS, "old.log")
            for p in (clip, log):
                write_file(p, "abcd")
                os.utime(p, (time.time() - 90 * 86400,) * 2)
            with mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(cache.main(["prune", "--logs-older", "60"]), cli.OK)
            self.assertTrue(os.path.exists(clip))
            self.assertFalse(os.path.exists(log))
            with mock.patch("sys.stdout", io.StringIO()):
                cache.main(["prune", "--days", "60", "--logs-older", "60"])
            self.assertFalse(os.path.exists(clip))
            with mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(cli.run(cache.main, ["prune", "--logs-older", "-1"]), cli.USAGE)


class CoachBackends(unittest.TestCase):
    def test_a_local_coach_of_the_listeners_own_is_refused(self):
        with tempfile.TemporaryDirectory() as d, helpers.home(os.path.join(d, "me")):
            own = os.path.join(paths.PERSONAS, "coach-mine")
            shutil.copytree(os.path.join(paths.SHIPPED, "coach-julius"), own)
            with open(os.path.join(own, "persona.md"), encoding="utf-8") as f:
                text = f.read().replace('name = "Coach Julius"', 'name = "Coach Mine"').replace(
                    'aliases = ["Chatterbox Coach", "Coach E"]', "aliases = []")
            with open(os.path.join(own, "persona.md"), "w", encoding="utf-8") as f:
                f.write(text)
            with self.assertRaises(errors.PROBLEMS) as e:
                personas.voice_for(personas.lookup("Coach Mine"), "local")
            self.assertIn("migrate", str(e.exception.code))


class Isolation(unittest.TestCase):
    """The tests never touch the real me/: ./harmonicfitness test points HARMONICFITNESS_HOME elsewhere, test_tools
    refuses to import over a real context folder, and helpers.home() redirects every path at once."""

    def test_the_test_command_points_home_at_an_absent_folder(self):
        import harmonicfitness
        env = harmonicfitness.test_env({"PATH": "/usr/bin"})
        home = env["HARMONICFITNESS_HOME"]
        self.assertFalse(os.path.exists(home), home)                 # absent, as in CI, where there's no me/
        self.assertTrue(os.path.isdir(os.path.dirname(home)), home)  # inside a folder that exists
        self.assertEqual(env["PATH"], "/usr/bin")
        kept = harmonicfitness.test_env({"HARMONICFITNESS_HOME": "/elsewhere/me"})
        self.assertEqual(kept["HARMONICFITNESS_HOME"], "/elsewhere/me")   # an explicit home is respected

    def test_the_guard_refuses_a_real_context_folder(self):
        with tempfile.TemporaryDirectory() as d:
            helpers.assert_isolated(d)                               # empty: fine
            helpers.assert_isolated(os.path.join(d, "absent"))       # absent: fine
            write_file(os.path.join(d, "profile.md"), "+++\nschema = 6\n+++\n")
            with self.assertRaises(SystemExit) as got:   # the tests' own guard: it stops the run
                helpers.assert_isolated(d)
            self.assertIn("./harmonicfitness test", str(got.exception))

    def test_helpers_home_redirects_every_path_and_restores(self):
        before = (paths.HOME, paths.PROFILE, paths.TOLD, paths.PERSONAS, paths.CACHE)
        with tempfile.TemporaryDirectory() as d:
            with helpers.home(d):
                self.assertEqual(paths.HOME, d)
                self.assertEqual(paths.PROFILE, os.path.join(d, "profile.md"))
                self.assertEqual(paths.TOLD, os.path.join(d, "workouts", "research", "told.jsonl"))
                self.assertEqual(paths.PERSONAS, os.path.join(d, "coaches"))
                self.assertEqual(paths.CACHE, os.path.join(d, "workouts", ".audio-cache"))
                self.assertEqual(paths.ROOT, ROOT)                   # the engine's own paths don't move
        self.assertEqual((paths.HOME, paths.PROFILE, paths.TOLD, paths.PERSONAS, paths.CACHE), before)


class ExitCodeMapper(unittest.TestCase):
    """cli.run turns what a tool raises into the documented exit codes, from every entry point."""

    def test_run_maps_each_kind_of_stop(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.run(lambda: None), cli.OK)
            self.assertEqual(cli.run(lambda: cli.ISSUES), cli.ISSUES)

            def usage():
                raise cli.Usage("no such coach")
            self.assertEqual(cli.run(usage), cli.USAGE)

            def stop():
                raise SystemExit("a file can't be read")
            self.assertEqual(cli.run(stop), cli.ISSUES)

            def explicit():
                raise SystemExit(3)
            self.assertEqual(cli.run(explicit), 3)

            class Known(Exception):
                exit_code = cli.SERVICE

            def known():
                raise Known("the service refused the key")
            self.assertEqual(cli.run(known), cli.SERVICE)
        self.assertIn("no such coach", err.getvalue())
        self.assertIn("a file can't be read", err.getvalue())
        self.assertIn("the service refused the key", err.getvalue())

        def bug():
            raise KeyError("x")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):   # a real bug is 70, never 1 ("fix the draft"), with its traceback
            self.assertEqual(cli.run(bug), cli.BUG)
        self.assertIn("Traceback", err.getvalue())
        self.assertIn("KeyError", err.getvalue())

    def test_the_known_stops_carry_their_codes(self):
        import routes
        import screen
        self.assertTrue(issubclass(personas.UnknownCoach, errors.UsageError))
        self.assertTrue(issubclass(routes.WebCoachUnavailable, errors.UsageError))
        self.assertEqual(personas.UnknownCoach("x").exit_code, cli.USAGE)
        self.assertFalse(issubclass(personas.UnknownCoach, SystemExit))   # an ordinary error, caught as one
        self.assertEqual(cloud.ServiceError("auth", "fish", "bad key").exit_code, cli.SERVICE)
        self.assertEqual(cloud.ServiceError("bad_request", "fish", "odd").exit_code, cli.ISSUES)
        self.assertEqual(screen.Unfit("a row can't be read").exit_code, cli.ISSUES)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(personas.UnknownCoach):
                personas.lookup("Nobody At All", folder=d)

    def test_commands_exit_64_on_an_unknown_coach_or_a_missing_draft(self):
        import build
        import coaches
        with tempfile.TemporaryDirectory() as d, helpers.home(os.path.join(d, "me")):   # absent: no coaches at all
            for main, args in ((coaches.main, ["archive", "Nobody At All"]),
                               (coaches.main, ["set", "Nobody At All", "local.engine", "qwen3"]),
                               (build.main, [os.path.join(d, "missing.draft.txt"), "x"])):
                err = io.StringIO()
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                    code = cli.run(lambda: main(args))
                self.assertEqual(code, cli.USAGE, (args, err.getvalue()))
                self.assertNotIn("Traceback", err.getvalue(), args)


class KeyLeaks(unittest.TestCase):
    """A key never appears in anything the engine prints, whatever a library or a service echoes."""
    SECRET = "sk-test-NEVERPRINT-456"

    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": self.SECRET})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_scrub_hides_every_set_key(self):
        self.assertEqual(cloud.scrub(f"Bearer {self.SECRET} was refused"), "Bearer <key> was refused")
        self.assertEqual(cloud.scrub("nothing here"), "nothing here")

    def test_a_header_the_client_refuses_never_shows_the_key(self):
        with self.assertRaises(cloud.ServiceError) as got:
            cloud.request("POST", "http://127.0.0.1:9/x", {"Authorization": f"Bearer {self.SECRET}\r"}, b"{}",
                          service="fish", tries=1)
        self.assertEqual(got.exception.kind, "auth")
        self.assertNotIn(self.SECRET, str(got.exception))
        self.assertIn("FISH_AUDIO_API_KEY", str(got.exception))

    def test_service_errors_and_audition_reasons_are_scrubbed(self):
        import audition
        e = cloud.ServiceError("bad_request", "fish", f"echo: {self.SECRET} (HTTP 400)")
        self.assertNotIn(self.SECRET, str(e))
        self.assertNotIn(self.SECRET, audition._reason(ValueError(f"Invalid header value b'Bearer {self.SECRET}\\r'")))

    def test_the_speed_key_names_no_hostname(self):
        import platform
        key = voices.speed_key({"backend": "mlx"})
        if platform.node():
            self.assertNotIn(platform.node(), key)
        self.assertEqual(key, voices.speed_key({"backend": "mlx"}))   # stable on this computer
        self.assertTrue(key.endswith("|mlx"), key)


class PrivatePaths(unittest.TestCase):
    """The one list of paths never pushed covers every context file, wherever a listener keeps it."""

    def test_the_pattern_covers_every_context_path_and_spares_the_engine(self):
        pattern = private_pattern()
        for p in ("me/profile.md", "me/.env", "me.real/health.md", "me.test/workouts/x.txt", "workouts/x.mp3",
                  "profile.md", "health.md", "training.md", "content.md", "settings.toml", "log.md", "movements.toml",
                  ".env", "personas/coach-x/persona.md", "voices/x.wav", "knowledge/health.md"):
            self.assertTrue(re.search(pattern, p), p)
        for p in ("knowledge/movements.toml", "docs/notes.md", "docs/x/log.md",
                  "tools/context.py", "README.md", "tests/fixtures/listener/profile.md", "tests/fixtures/profile-5.md"):
            self.assertFalse(re.search(pattern, p), p)

    def test_nothing_personal_is_tracked(self):
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("not a git checkout")
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split("\n")
        pattern = private_pattern()
        self.assertTrue(re.search(pattern, "knowledge/health.md"))   # the one CI used to miss
        # the template is the one me.* folder that's part of the engine; the hook and CI spare it the same way
        self.assertEqual([p for p in tracked if re.search(pattern, p) and not p.startswith("me.example/")], [])

    def test_the_hook_refuses_context_files_and_spares_the_template(self):
        if not shutil.which("git"):
            self.skipTest("git not installed")
        hook = os.path.join(ROOT, "tools", "hooks", "check-private.sh")
        with tempfile.TemporaryDirectory() as d:
            def g(*args):
                return subprocess.run(["git", *args], cwd=d, capture_output=True, text=True, encoding="utf-8", check=True)
            g("init", "-q")
            g("config", "user.name", "T")
            g("config", "user.email", "t@example.com")
            g("config", "commit.gpgsign", "false")
            write_file(os.path.join(d, "me.example", "profile.md"), "template\n")
            g("add", "-A")
            g("commit", "-q", "-m", "the template")
            ok = subprocess.run(["sh", hook, "HEAD"], cwd=d, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
            write_file(os.path.join(d, "me.real", "profile.md"), "mine\n")
            write_file(os.path.join(d, "profile.md"), "mine\n")
            g("add", "-A")
            g("commit", "-q", "-m", "oops")
            bad = subprocess.run(["sh", hook, "HEAD~1..HEAD"], cwd=d, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
            self.assertIn("me.real/profile.md", bad.stdout)
            self.assertIn("  profile.md", bad.stdout)


class ContextRobustness(unittest.TestCase):
    """A BOM reads, and one bad coach file hides no others."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = fresh_home(self.tmp.name)

    def test_a_byte_order_mark_reads_fine(self):
        path = os.path.join(self.home, "profile.md")
        with open(path, encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8-sig") as f:   # as a Windows editor may save it
            f.write(text)
        with helpers.home(self.home):
            messages = [i.message for i in check.check([path])]
            self.assertEqual([m for m in messages if "schema" in m or "migrate" in m or "close" in m], [], messages)
            self.assertEqual(store.schema_of(store.read_raw(path)), 6)
            self.assertIsNotNone(context.profile(path))   # reads, BOM and all

    def test_one_unreadable_coach_file_hides_no_others(self):
        folder = os.path.join(self.home, "coaches")
        shutil.copytree(os.path.join(paths.SHIPPED, "coach-julius"), os.path.join(folder, "coach-julius"))
        write_file(os.path.join(folder, "coach-broken", "persona.md"), "+++\nname = \n+++\n")   # invalid TOML
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            names = [p.name for p in personas.all(folder)]
        self.assertIn("Coach Julius", names)
        self.assertIn("coach-broken", err.getvalue())
        self.assertTrue(any("coach-broken" in i.path and not i.note for i in check.check_coaches(folder)))


class SkillsAndTemplate(unittest.TestCase):
    def test_movements_default_to_the_profiles_level(self):
        import movements
        with tempfile.TemporaryDirectory() as d:
            home = fresh_home(d)
            prof = os.path.join(home, "profile.md")
            with open(prof, encoding="utf-8") as f:
                text = f.read()
            write_file(prof, text.replace('experience = ""', 'experience = "novice"', 1))
            with helpers.home(home):
                self.assertEqual(movements.default_level(), "novice")
            with helpers.home(os.path.join(d, "absent")):
                self.assertEqual(movements.default_level(), "experienced")


class BadKeyPredicates(unittest.TestCase):
    """A key that can't be read (a stray character) is "not set" to every yes-or-no question, so the coach list,
    the default coach and the readiness check still answer; it stops a command only where that key would be used."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = fresh_home(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(helpers.home(self.home))
        self.stack.enter_context(mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "abc def", "INWORLD_API_KEY": "good-key",
                                                               "ELEVENLABS_API_KEY": "", "GEMINI_API_KEY": "",
                                                               "HARMONICFITNESS_FAKE_LOCAL_ENGINE": "0"}))

    def test_the_predicates_say_not_set_and_the_default_coach_is_still_chosen(self):
        import keys
        import routes
        self.assertFalse(keys.is_set("fish"))
        self.assertTrue(keys.is_set("inworld"))
        with self.assertRaises(keys.BadKey):
            keys.get("fish")
        ok, reason = routes.usable("fish")
        self.assertFalse(ok)
        self.assertIn("FISH_AUDIO_API_KEY", reason)
        self.assertEqual(coachpick.default().name, "Coach Owen")   # the keyed service's stand-in, Fish set aside
        import coaches
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(coaches.main([]), cli.OK)
        self.assertIn("Coach Owen", out.getvalue())

    def test_a_web_coach_on_the_bad_key_stops_with_the_variable(self):
        import keys
        reed = personas.lookup("Coach Reed")
        with self.assertRaises(keys.BadKey) as got:
            coachpick.pick(["local"], reed)
        self.assertIn("FISH_AUDIO_API_KEY", str(got.exception))
        self.assertEqual(got.exception.exit_code, cli.SERVICE)


if __name__ == "__main__":
    unittest.main()
