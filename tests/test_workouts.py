"""The workouts command (tools/workoutlog.py): list, show, feedback, rate and delete, and the build ids that tie told
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

    def test_feedback_written_at_the_same_moment_is_never_lost(self):
        import threading
        target = self.w.pick(["ccc333"], self.w.logged())[0]
        errors_seen = []

        def write(n):
            try:
                for i in range(12):
                    self.w.feedback(target, f"note {n}-{i}")
            except Exception as e:  # noqa: BLE001 - reported by the assertion below
                errors_seen.append(e)
        threads = [threading.Thread(target=write, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors_seen, [])
        with open(paths.LOG, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(sum(f"note {n}-{i}" in text for n in range(4) for i in range(12)), 48)
        self.assertEqual(len(self.w.logged()), 3)   # the sessions themselves untouched

    def test_every_writer_of_the_listener_s_files_takes_its_lock(self):
        import context
        import interests
        import locks
        taken = []
        real = locks.file_lock

        def recording(path):
            taken.append(os.path.basename(path))
            return real(path)
        target = self.w.pick(["ccc333"], self.w.logged())[0]
        with mock.patch.object(locks, "file_lock", side_effect=recording):
            self.w.feedback(target, "fine")
            self.w.rate(target, "positive")
            context.set_experience("advanced")
            context.add_feed("A blog", "rss", "https://example.org/feed")
            context.add_topic_lines(["Chess: endgames"])
            interests.apply()
        for name in ("log.md", "profile.md", "content.md", "training.md"):
            self.assertIn(name, taken)

    def test_delete_takes_back_its_line_stories_threads_and_feedback(self):
        line = self.w.feedback(self.w.pick(["1"], self.w.logged())[0], "loved the quiz, a bit long")
        self.assertEqual(line, "- 2026-10-30 (15 min, build ccc333): loved the quiz, a bit long")
        import content
        import context
        self.assertEqual(context.feedback()[-1], line[2:])
        out = self.w.delete(self.w.pick(["ccc333"], self.w.logged()))
        self.assertIn("Removed 1 session line(s)", out[0])
        self.assertEqual([s.build_id for s in self.w.logged()], ["bbb222", "aaa111"])
        self.assertEqual(self.titles(), ["old, no build", "seven"])
        self.assertEqual([t["id"] for t in content.threads()], ["t1"])   # its close went with it: t1 is open again
        self.assertNotIn(line[2:], context.feedback())
        self.w.delete(self.w.pick(["2"], self.w.logged()))   # a row without a build goes only when no workout
        self.assertEqual(self.titles(), ["seven"])           # shares its date (2026-10-29: the only one that day)

    def test_rating_replaces_the_last_and_what_cant_be_placed_is_a_usage_error(self):
        s = self.w.pick(["1"], self.w.logged())[0]
        self.w.feedback(s, "too long")
        self.w.rate(s, "negative")
        self.w.rate(s, "positive")
        texts, rating = self.w.notes_for(s, __import__("context").feedback())
        self.assertEqual((texts, rating), (["too long"], "positive"))
        with self.assertRaises(errors.UsageError):
            self.w.rate(s, "great")
        for bad in ("9", "zzz"):
            with self.assertRaises(errors.UsageError):
                self.w.pick([bad], self.w.logged())

    def test_delete_all_and_files(self):
        folder = os.path.join(paths.WORKOUTS, "2026-10-30-conditioning-15")
        os.makedirs(folder)
        draft = os.path.join(folder, "2026-10-30-conditioning-15.draft.txt")
        open(draft, "w", encoding="utf-8").close()
        drive = os.path.join(self.tmp.name, "drive")
        os.makedirs(drive)
        copy = os.path.join(drive, "w.mp3")   # delivered_to names the folder; the name gives the file
        open(copy, "w", encoding="utf-8").close()
        os.makedirs(paths.LOGS, exist_ok=True)
        with open(paths.BUILDS, "w", encoding="utf-8") as f:
            f.write(json.dumps({"kind": "mp3", "build_id": "ccc333", "draft": draft, "out": "x.mp3",
                                "draft_sha256": "0" * 64}) + "\n")
            f.write(json.dumps({"kind": "outcome", "event": "delivered", "build_id": "ccc333", "at": "x",
                                "name": "w", "delivered_to": [drive]}) + "\n")
        out = self.w.delete(self.w.pick(["all"], self.w.logged()), files=True)
        self.assertEqual(self.w.logged(), [])
        self.assertEqual(self.titles(), [])
        self.assertFalse(os.path.exists(folder))
        self.assertFalse(os.path.exists(copy))
        self.assertTrue(any("delivered copy" in line for line in out))


if __name__ == "__main__":
    unittest.main()
