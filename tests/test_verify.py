"""The take checker (tools/verify.py), the render's check-and-retry pass over local takes
(render.check_takes), clip leveling, and the cache prune of verdicts, with a fake voice and recognizer."""
import contextlib
import io
import json
import math
import os
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import errors  # noqa: E402
import cache  # noqa: E402
import cli  # noqa: E402
import engines  # noqa: E402
import render  # noqa: E402
import verify  # noqa: E402

SR = verify.SR


def tone(seconds, db=-20.0, freq=220.0):
    amp = 32767 * 10 ** (db / 20) * math.sqrt(2)   # a sine whose RMS is `db`
    n = int(seconds * SR)
    return struct.pack(f"<{n}h", *(int(amp * math.sin(2 * math.pi * freq * i / SR)) for i in range(n)))


def quiet(seconds):
    return b"\x00\x00" * int(seconds * SR)


class Score(unittest.TestCase):
    def test_a_dropped_cue_is_named(self):
        v = verify.score("Keep the elbows soft. Three, two, one, and rest.", "Keep the elbows soft. 3, 2, 1.")
        self.assertEqual(v["missed_cues"], ["rest"])
        self.assertEqual(v["errors"], 2)

    def test_digits_years_and_ordinals_read_as_words(self):
        line = "On this day in seventeen eighty-one, the first of twenty rounds."
        self.assertEqual(verify.score(line, "On this day in 1781, the 1st of 20 rounds.")["errors"], 0)
        self.assertEqual(verify.words("2026 and 1905 and 2.5%"),
                         "twenty twenty six and nineteen oh five and two point five percent".split())

    def test_a_currency_sign_reads_as_its_word(self):
        # Parakeet writes "two thousand pounds" as "£2,000" (every coach, 2026-10-26).
        line = "That's two thousand pounds moved, give or take."
        self.assertEqual(verify.score(line, "That's£2,000 moved, give or take.")["errors"], 0)
        self.assertEqual(verify.words("$5 and €1.5"), "five dollars and one point five euros".split())

    def test_a_compound_split_or_joined_counts_as_said(self):
        self.assertEqual(verify.score("A good warm-up.", "A good warmup.")["errors"], 0)
        self.assertEqual(verify.score("Your warmup.", "Your warm up.")["errors"], 0)
        self.assertEqual(verify.score("Alright, go.", "All right, go.")["errors"], 0)

    def test_a_swapped_side_is_a_missed_cue(self):
        self.assertEqual(verify.score("Now the left side.", "Now the right side.")["missed_cues"], ["left"])


class Problems(unittest.TestCase):
    def test_a_whole_take_has_none(self):
        self.assertEqual(verify.problems(tone(2.0), 2.0), [])

    def test_a_long_silence_inside_is_a_stall(self):
        found = verify.problems(tone(1.0) + quiet(2.0) + tone(1.0), 4.0)
        self.assertTrue(any("silent" in p for p in found), found)

    def test_a_runaway_and_a_cut_off(self):
        self.assertTrue(any(p.startswith("runs") for p in verify.problems(tone(10.0), 2.0)))
        self.assertTrue(any(p.startswith("stops") for p in verify.problems(tone(1.0), 4.0)))

    def test_clipping(self):
        self.assertIn("clips", verify.problems(struct.pack("<2h", 32767, -32767) * 50 + tone(0.5), None))

    def test_judge_allows_one_word_in_twenty(self):
        line = " ".join(["easy"] * 19 + ["breathing"])   # twenty words, no cue
        heard = " ".join(["easy"] * 19 + ["breeding"])
        self.assertTrue(verify.judge(line, heard, tone(1.0), 1.0)["ok"])
        self.assertFalse(verify.judge("Easy breathing now.", "Easy breeding now.", tone(1.0), 1.0)["ok"])


class CheckTakes(unittest.TestCase):
    """render.check_takes with a fake voice (each seed's take a distinct length) and a fake recognizer."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.voice = {"name": "Test", "engine": "chatterbox", "backend": "mlx"}
        self.heard = {}     # take length in samples -> what the recognizer hears
        self.said = []      # (text, seed) the voice was asked for
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(mock.patch.object(render, "pace", return_value=(14.5, True)))
        stack.enter_context(mock.patch.object(render, "clip_seconds", return_value=1.0))
        stack.enter_context(mock.patch.object(engines, "listener", side_effect=lambda: self.hear))
        stack.enter_context(mock.patch.object(engines, "speaker", side_effect=lambda v: self.say))
        stack.enter_context(mock.patch.object(engines, "release"))

    def cache_path(self, text):
        return os.path.join(self.tmp.name, f"{abs(hash(text))}.pcm")

    def take(self, seed):
        return tone(1.0 + seed / 1000)

    def say(self, text, seed):
        self.said.append((text, seed))
        return self.take(seed)

    def hear(self, pcm):
        return self.heard[len(pcm)]

    def cached(self, text, seed=42):
        with open(self.cache_path(text), "wb") as f:
            f.write(self.take(seed))

    def test_a_good_take_is_kept_without_another_render(self):
        line = "Three, two, one, and rest."
        self.cached(line)
        self.heard[len(self.take(42))] = "3, 2, 1, and rest."
        got = render.check_takes(self.voice, [line], 42, self.cache_path)
        self.assertEqual(self.said, [])
        self.assertEqual((got["checked_now"], got["rendered_again"]), (1, 0))
        with open(render.check_path(self.cache_path, line), encoding="utf-8") as f:
            self.assertTrue(json.load(f)["ok"])

    def test_a_dropped_cue_renders_the_next_seed_and_keeps_it(self):
        line = "Three, two, one, and rest."
        self.cached(line)
        self.heard[len(self.take(42))] = "3, 2, 1."
        self.heard[len(self.take(43))] = "3, 2, 1, and rest."
        got = render.check_takes(self.voice, [line], 42, self.cache_path)
        self.assertEqual(self.said, [(line, 43)])
        self.assertEqual(got["rendered_again"], 1)
        with open(self.cache_path(line), "rb") as f:
            self.assertEqual(f.read(), self.take(43))   # the passing take replaced the cached one
        with open(render.check_path(self.cache_path, line), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["seed"], 43)
        render.check_takes(self.voice, [line], 42, self.cache_path)   # checked once: a rerun hears nothing again
        self.assertEqual(len(self.said), 1)

    def test_a_cue_lost_in_every_take_stops_the_build_and_again_on_a_rerun(self):
        line = "Switch sides."
        self.cached(line)
        for seed in range(42, 42 + render.CHECK_TAKES):
            self.heard[len(self.take(seed))] = "Which sides."
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(errors.PROBLEMS) as got:
            render.check_takes(self.voice, [line], 42, self.cache_path)
        self.assertEqual(got.exception.exit_code, cli.ISSUES)
        self.assertIn("Which sides", str(got.exception))   # what was heard, in the message the build prints
        self.assertEqual(len(self.said), render.CHECK_TAKES - 1)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(errors.PROBLEMS):
            render.check_takes(self.voice, [line], 42, self.cache_path)
        self.assertEqual(len(self.said), render.CHECK_TAKES - 1)   # the verdict stands; no takes are rendered again

    def test_an_unclear_line_keeps_its_best_take_and_goes_on(self):
        line = "Easy breathing now."
        self.cached(line)
        for seed, heard in zip(range(42, 46), ["Easy breeding cow.", "Easy breeding now.", "Peasy breeding cow.",
                                               "Easy breeding cow."]):
            self.heard[len(self.take(seed))] = heard
        with contextlib.redirect_stdout(io.StringIO()):
            got = render.check_takes(self.voice, [line], 42, self.cache_path)
        self.assertEqual(got["unclear"], [line])
        with open(self.cache_path(line), "rb") as f:
            self.assertEqual(f.read(), self.take(43))   # one word off beats two

    def test_a_new_take_drops_the_old_verdict(self):
        line = "Go."
        render.render_clip(lambda t, s: self.take(s), line, 42, self.cache_path)
        with open(render.check_path(self.cache_path, line), "w", encoding="utf-8") as f:
            f.write("{}")
        render.render_clip(lambda t, s: self.take(s), line, 42, self.cache_path)
        self.assertFalse(os.path.exists(render.check_path(self.cache_path, line)))

    def test_a_line_heard_before_never_loads_the_recognizer(self):
        line = "Three, two, one, and rest."
        self.cached(line)
        self.heard[len(self.take(42))] = "3, 2, 1, and rest."
        render.check_takes(self.voice, [line], 42, self.cache_path)
        with mock.patch.object(engines, "listener", side_effect=AssertionError("loaded")):
            got = render.check_takes(self.voice, [line], 42, self.cache_path)   # its verdict is cached
        self.assertEqual(got["checked_now"], 0)


class Level(unittest.TestCase):
    def test_a_quiet_clip_is_raised_to_the_speech_level(self):
        out = render.level(tone(1.0, db=-30.0))
        self.assertAlmostEqual(render.speech_level(out), render.SPEECH_LEVEL, delta=0.3)

    def test_a_clip_near_the_level_and_silence_are_left_alone(self):
        near = tone(1.0, db=render.SPEECH_LEVEL + 0.2)
        self.assertIs(render.level(near), near)
        self.assertEqual(render.level(quiet(1.0)), quiet(1.0))

    def test_a_raised_clip_keeps_its_peak_under_full_scale(self):
        spiky = tone(1.0, db=-40.0) + struct.pack("<h", 20000)
        out = render.level(spiky)
        samples = struct.unpack(f"<{len(out) // 2}h", out)
        self.assertLessEqual(max(samples), int(render.LEVEL_PEAK * 32767) + 1)


class Encode(unittest.TestCase):
    def test_both_loudness_passes_run_the_compressor_first(self):
        import subprocess
        cmds = []
        stats = '{"input_i": "-20", "input_tp": "-3", "input_lra": "5", "input_thresh": "-30", "target_offset": "0"}'

        def fake_run(cmd, **kw):
            cmds.append(cmd)
            if "null" not in cmd:
                with open(cmd[-1], "wb") as f:
                    f.write(b"mp3")
            return subprocess.CompletedProcess(cmd, 0, "", stats)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(render.ffmpeg_tool, "exe", return_value="ffmpeg"), \
                mock.patch.object(render.subprocess, "run", side_effect=fake_run):
            render.encode(quiet(0.1), os.path.join(d, "x.mp3"), "x")
        chains = [c[c.index("-af") + 1] for c in cmds]
        self.assertEqual(len(chains), 2)
        self.assertTrue(all(c.startswith(render.COMPRESS + ",loudnorm=") for c in chains), chains)


class Prune(unittest.TestCase):
    def test_a_verdict_goes_with_its_clip(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("old.pcm", "old.check.json", "kept.pcm", "kept.check.json"):
                with open(os.path.join(d, name), "wb") as f:
                    f.write(b"x")
            os.utime(os.path.join(d, "old.pcm"), (0, 0))
            cache.prune(1, folder=d)
            self.assertEqual(sorted(n for n in os.listdir(d) if not n.startswith(".")), ["kept.check.json", "kept.pcm"])


if __name__ == "__main__":
    unittest.main()
