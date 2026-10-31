"""The workouts command (tools/workoutlog.py): list, feedback and delete, and the build ids that tie told
stories and threads to the workout that told them."""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import errors  # noqa: E402
import helpers  # noqa: E402
import paths  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINE = "- {date} | {m} min | home | Coach Owen | easy spin | Sixers | format: intervals | build: {b}\n"


class Workouts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = os.path.join(self.tmp.name, "me")
        shutil.copytree(os.path.join(ROOT, "me.example"), home)
        self.ctx = helpers.home(home)
        self.home = self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)
        import workoutlog
        self.w = workoutlog
        with open(paths.LOG, encoding="utf-8") as f:
            text = f.read()
        text = text.replace("## Sessions\n", "## Sessions\n\n" + LINE.format(date="2026-10-29", m=25, b="aaa111")
                            + LINE.format(date="2026-10-30", m=7, b="bbb222")
                            + LINE.format(date="2026-10-30", m=15, b="ccc333"), 1)
        with open(paths.LOG, "w", encoding="utf-8") as f:
            f.write(text)
        os.makedirs(paths.RESEARCH, exist_ok=True)
        rows = [{"date": "2026-10-29", "topic": "Sixers", "format": "quiz", "title": "old, no build"},
                {"date": "2026-10-30", "topic": "Sixers", "format": "quick_hit", "title": "seven", "build": "bbb222"},
                {"date": "2026-10-30", "topic": "Devils", "format": "number", "title": "fifteen", "build": "ccc333"}]
        with open(paths.TOLD, "w", encoding="utf-8") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
        with open(paths.THREADS, "w", encoding="utf-8") as f:
            f.write(json.dumps({"event": "open", "id": "t1", "date": "2026-10-30", "kind": "promise", "what": "more",
                                "build": "bbb222"}) + "\n")
            f.write(json.dumps({"event": "close", "id": "t1", "date": "2026-10-30", "build": "ccc333"}) + "\n")

    def titles(self):
        return [r["title"] for r in __import__("content").told()]

    def test_the_list_is_newest_first(self):
        got = self.w.listing(self.w.logged())
        self.assertIn("15 min", got[0])
        self.assertIn("build ccc333", got[0])
        self.assertIn("2026-10-29", got[2])

    def test_delete_takes_back_its_line_stories_and_threads(self):
        out = self.w.delete(self.w.pick(["ccc333"], self.w.logged()))
        self.assertIn("Removed 1 session line(s)", out[0])
        self.assertEqual([s.build_id for s in self.w.logged()], ["bbb222", "aaa111"])
        self.assertEqual(self.titles(), ["old, no build", "seven"])
        import content
        self.assertEqual([t["id"] for t in content.threads()], ["t1"])   # its close went with it: t1 is open again

    def test_a_row_without_a_build_goes_only_when_no_workout_shares_its_date(self):
        self.w.delete(self.w.pick(["3"], self.w.logged()))   # the 2026-10-29 one, the only one that day
        self.assertEqual(self.titles(), ["seven", "fifteen"])

    def test_delete_all_and_files(self):
        folder = os.path.join(paths.WORKOUTS, "2026-10-30-conditioning-15")
        os.makedirs(folder)
        draft = os.path.join(folder, "2026-10-30-conditioning-15.draft.txt")
        open(draft, "w").close()
        drive = os.path.join(self.tmp.name, "drive")
        os.makedirs(drive)
        copy = os.path.join(drive, "w.mp3")
        open(copy, "w").close()
        os.makedirs(paths.LOGS, exist_ok=True)
        with open(paths.BUILDS, "w", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "mp3", "build_id": "ccc333", "draft": draft, "out": "x.mp3",
                                "draft_sha256": "0" * 64}) + "\n")
            f.write(json.dumps({"kind": "outcome", "event": "delivered", "build_id": "ccc333", "at": "x",
                                "name": "w", "delivered_to": [copy]}) + "\n")
        out = self.w.delete(self.w.pick(["all"], self.w.logged()), files=True)
        self.assertEqual(self.w.logged(), [])
        self.assertEqual(self.titles(), [])
        self.assertFalse(os.path.exists(folder))
        self.assertFalse(os.path.exists(copy))
        self.assertTrue(any("delivered copy" in line for line in out))

    def test_feedback_is_tied_to_its_workout_and_goes_with_it(self):
        line = self.w.feedback(self.w.pick(["1"], self.w.logged())[0], "loved the quiz, a bit long")
        self.assertEqual(line, "- 2026-10-30 (15 min, build ccc333): loved the quiz, a bit long")
        import context
        self.assertEqual(context.feedback()[-1], line[2:])
        self.assertIn("feedback: loved the quiz", "\n".join(self.w.listing(self.w.logged())))
        self.w.delete(self.w.pick(["ccc333"], self.w.logged()))
        self.assertNotIn(line[2:], context.feedback())

    def test_an_unknown_workout_is_a_usage_error(self):
        with self.assertRaises(errors.UsageError):
            self.w.pick(["9"], self.w.logged())
        with self.assertRaises(errors.UsageError):
            self.w.pick(["zzz"], self.w.logged())


class BuildLinks(unittest.TestCase):
    def test_told_items_and_threads_carry_the_build(self):
        import content
        with tempfile.TemporaryDirectory() as d:
            told, threads = os.path.join(d, "told.jsonl"), os.path.join(d, "threads.jsonl")
            content.log("2026-10-30", ["- | quiz | A riddle"], path=told, build="abc")
            self.assertEqual(content.told(told)[0]["build"], "abc")
            row = content.open_threads("2026-10-30", ["- | quiz | Q"], path=threads, build="abc")[0]
            self.assertEqual(row["build"], "abc")
            self.assertEqual(content.close_thread("2026-10-30", "t1", path=threads, build="def")["build"], "def")
        with mock.patch("records.latest_build", return_value=None), self.assertRaises(ValueError):
            content.draft_build(os.path.join(ROOT, "knowledge", "smoke-test.draft.txt"))


SECONDS = 19


class EstimatedPaceSilence(unittest.TestCase):
    def test_an_estimated_pace_checks_held_quiet_as_if_the_voice_ran_fast(self):
        import tts_build
        from draft import parse
        v = {"name": "x", "key": "x", "engine": "chatterbox", "model": "m"}
        # four seconds of talk around a bare hold in an eleven-second segment: about seven seconds quiet as predicted
        talk = ("Go now, quick legs and steady breathing, the hips quiet on the seat and the hands soft on the bars "
                "while you hold that pace. [hold] And ease off now, let the legs slow down and the breathing settle "
                "back to easy.")
        segs = parse(f"@@ {SECONDS} | A\n{talk}\n")
        with mock.patch("voices.pace", return_value=(14.5, True)):
            measured = tts_build.lint(segs, v).rows[0].clip_issues
        with mock.patch("voices.pace", return_value=(14.5, False)):
            estimated = tts_build.lint(segs, v).rows[0].clip_issues
        self.assertFalse(any("of silence" in i for i in measured), measured)
        self.assertTrue(any("of silence" in i for i in estimated), estimated)


if __name__ == "__main__":
    unittest.main()
