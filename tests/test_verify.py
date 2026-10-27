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

    def test_another_checker_hears_the_line_again(self):
        line = "Three, two, one, and rest."
        self.cached(line)
        self.heard[len(self.take(42))] = "3, 2, 1, and rest."
        render.check_takes(self.voice, [line], 42, self.cache_path)
        with open(render.check_path(self.cache_path, line), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["checker"], verify.checker_id())
        with mock.patch.object(verify, "CUES", verify.CUES | {"breathe"}):   # a stricter checker ships
            self.assertIsNone(render._verdict(render.check_path(self.cache_path, line)))
            got = render.check_takes(self.voice, [line], 42, self.cache_path)
        self.assertEqual((got["checked_now"], self.said), (1, []))   # heard again; the audio kept
        with open(render.check_path(self.cache_path, line), "w", encoding="utf-8") as f:   # a verdict from before
            f.write(json.dumps({"ok": True, "missed_cues": []}))
        self.assertIsNone(render._verdict(render.check_path(self.cache_path, line)))


class RenderLocal(unittest.TestCase):
    """render._render_local: a render that fails midway still frees the model and keeps what it measured."""

    def test_a_failure_midway_releases_the_model_and_records_the_pace(self):
        voice = {"name": "Test", "engine": "pocket", "backend": "torch"}
        calls = []

        def say(text, seed):
            if len(calls) == 2:
                raise RuntimeError("out of memory")
            calls.append(text)
            return tone(1.0)
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(engines, "speaker", return_value=say), \
                mock.patch.object(engines, "release") as release, \
                mock.patch.object(render, "record_rate") as record, \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            render._render_local(voice, ["One line.", "Two lines.", "Three lines."], 42,
                                 lambda t: os.path.join(d, f"{abs(hash(t))}.pcm"))
        release.assert_called_once()
        record.assert_called_once()
        (v, measured, seconds), kw = record.call_args
        self.assertEqual(measured, render.weight("One line.") + render.weight("Two lines."))
        self.assertAlmostEqual(seconds, 2.0 - 2 * render.EDGE)
        self.assertNotIn("render_seconds", kw)   # this computer's speed needs a whole render


class Fallback(unittest.TestCase):
    """verify's clipping count and audio.level's peak: numpy where it imports, plain Python otherwise, alike."""

    def setUp(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("no numpy here to compare with")
        self.pcm = struct.pack("<6h", 32767, -32768, -32767, 100, -5, 0) + tone(0.5, db=-35.0) + b"\x01"

    def without_numpy(self):
        return mock.patch.dict(sys.modules, {"numpy": None})

    def test_the_clipping_count_agrees(self):
        fast = verify.clipped_samples(self.pcm)
        with self.without_numpy():
            slow = verify.clipped_samples(self.pcm)
        self.assertEqual(fast, slow)
        self.assertEqual(fast[1], 3)

    def test_the_leveled_clip_agrees(self):
        quiet_clip = tone(1.0, db=-40.0) + struct.pack("<2h", -20000, 15000)
        fast = render.level(quiet_clip)
        with self.without_numpy():
            slow = render.level(quiet_clip)
        self.assertEqual(fast, slow)
        self.assertNotEqual(fast, quiet_clip)


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
                mock.patch.object(render.ffmpeg_tool, "version", return_value="ffmpeg test"), \
                mock.patch.object(render.ffmpeg_tool.subprocess, "run", side_effect=fake_run):
            render.encode(quiet(0.1), os.path.join(d, "x.mp3"), "x")
        chains = [c[c.index("-af") + 1] for c in cmds]
        self.assertEqual(len(chains), 2)
        self.assertTrue(all(c.startswith(render.COMPRESS + ",loudnorm=") for c in chains), chains)


@unittest.skipIf(sys.platform == "win32", "the fake ffmpeg is a shell script")
class FfmpegStops(unittest.TestCase):
    """Every ffmpeg the engine starts runs through ffmpeg.run: a hang past its timeout or a failure is a
    RenderStopped naming ffmpeg's version, the exit code and the end of what it said, never a traceback."""

    def fake(self, body):
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        path = os.path.join(d, "ffmpeg")
        with open(path, "w") as f:
            f.write("#!/bin/sh\n"
                    "if [ \"$1\" = -version ]; then echo 'ffmpeg version 9.9-fake'; exit 0; fi\n" + body + "\n")
        os.chmod(path, 0o755)
        env = mock.patch.dict(os.environ, {"PATH": d + os.pathsep + os.environ.get("PATH", "")})
        env.start()
        self.addCleanup(env.stop)
        import ffmpeg
        self.assertEqual(ffmpeg.exe(), path)   # first on PATH: the one the engine finds
        return path

    def test_a_hung_ffmpeg_is_stopped_at_its_timeout(self):
        import ffmpeg
        exe = self.fake("sleep 10")
        with self.assertRaises(errors.RenderStopped) as got:
            ffmpeg.run([exe, "-i", "x.wav", "x.mp3"], "encode the audio", 0.5)
        message = str(got.exception)
        self.assertIn("ffmpeg couldn't encode the audio", message)
        self.assertIn("9.9-fake", message)
        self.assertIn("0.5 seconds", message)
        self.assertEqual(got.exception.exit_code, cli.ISSUES)

    def test_a_failing_ffmpeg_says_its_exit_code_and_last_words(self):
        import ffmpeg
        exe = self.fake("echo 'Unknown encoder libmp3lame' >&2; exit 1")
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "x.wav"), os.path.join(d, "x.mp3")
            with self.assertRaises(errors.RenderStopped) as got:
                ffmpeg.to_mp3(src, dst, what="make the sample")
            message = str(got.exception)
            self.assertIn("make the sample", message)
            self.assertIn("exit 1", message)
            self.assertIn("Unknown encoder libmp3lame", message)
            self.assertIn("9.9-fake", message)
            import coaches   # the audition's sample keeps its yes-or-no answer: no MP3, the WAV plays
            self.assertFalse(coaches._mp3(src, dst))
            import webcopy
            with mock.patch.object(webcopy, "duration", return_value=30.0), self.assertRaises(errors.RenderStopped):
                webcopy.make(src, "X", d)
            self.assertEqual(os.listdir(d), [])
        with self.assertRaises(errors.RenderStopped) as got:   # bytes in: a web service's compressed audio
            render.ffmpeg_tool.run([exe, "-i", "pipe:0", "pipe:1"], "read it", 5, input=b"\x00" * 16)
        self.assertIn("Unknown encoder", str(got.exception))

    def test_the_final_encode_gets_a_timeout_that_grows_with_the_audio(self):
        import subprocess
        seen = []

        def fake_run(cmd, **kw):
            seen.append(kw.get("timeout"))
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(render.ffmpeg_tool, "exe", return_value="ffmpeg"), \
                mock.patch.object(render.ffmpeg_tool, "version", return_value="ffmpeg test"), \
                mock.patch.object(render.ffmpeg_tool.subprocess, "run", side_effect=fake_run):
            for seconds, want in ((1, 120), (300, 600)):
                with self.assertRaises(errors.RenderStopped) as got:
                    render.encode(quiet(seconds), os.path.join(d, "x.mp3"), "x")
                self.assertEqual(seen[-1], want)
                self.assertIn(f"after {want} seconds", str(got.exception))


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
