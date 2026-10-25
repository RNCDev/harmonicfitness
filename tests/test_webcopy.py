"""The web copy: a speech-bitrate MP3 in parts under a size limit, and the player page that plays them."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ffmpeg  # noqa: E402
import webcopy  # noqa: E402

FFMPEG = ffmpeg.exe()


@unittest.skipUnless(FFMPEG, "ffmpeg not installed")
class WebCopy(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)

    def tone(self, seconds):
        path = os.path.join(self.d, "full.mp3")
        subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        f"sine=frequency=330:duration={seconds}", "-ac", "2", "-ar", "24000", "-c:a", "libmp3lame",
                        "-b:a", "96k", path], check=True, timeout=60)
        return path

    def test_single_part(self):
        parts = webcopy.make(self.tone(20), "X", self.d)
        self.assertEqual([os.path.basename(p) for p in parts], ["X.web-1.mp3"])
        size = os.path.getsize(parts[0])
        self.assertLess(abs(size - 20 * 6000) / (20 * 6000), 0.3, size)   # 48 kbps is 6 KB a second
        self.assertAlmostEqual(webcopy.duration(parts[0]), 20, delta=0.5)
        out = subprocess.run([FFMPEG, "-hide_banner", "-i", parts[0]], capture_output=True, text=True)
        self.assertIn("mono", out.stderr)

    def test_a_rebuild_in_fewer_parts_leaves_no_stale_part(self):
        for n in (2, 3, 12):
            with open(os.path.join(self.d, f"X.web-{n}.mp3"), "wb") as f:
                f.write(b"old")
        keep = os.path.join(self.d, "X.web-notes.mp3")   # not a part: left alone
        open(keep, "wb").close()
        parts = webcopy.make(self.tone(5), "X", self.d)
        self.assertEqual(sorted(f for f in os.listdir(self.d) if f.startswith("X.web-")),
                         ["X.web-1.mp3", "X.web-notes.mp3"])
        self.assertEqual(len(parts), 1)

    def test_split_parts_and_page_lists_them_in_order(self):
        parts = webcopy.make(self.tone(30), "Long one", self.d, max_bytes=70_000)   # three parts of ~10 s
        self.assertEqual([os.path.basename(p) for p in parts],
                         ["Long one.web-1.mp3", "Long one.web-2.mp3", "Long one.web-3.mp3"])
        self.assertTrue(all(os.path.getsize(p) <= 70_000 for p in parts))
        self.assertAlmostEqual(sum(webcopy.duration(p) for p in parts), 30, delta=1)
        page = webcopy.page("Long one", parts, os.path.join(self.d, "Long one.player.html"))
        with open(page, encoding="utf-8") as f:
            text = f.read()
        at = [text.index(f'"Long one.web-{n}.mp3"') for n in (1, 2, 3)]
        self.assertEqual(at, sorted(at))
        self.assertIn("Part ", text)
        self.assertIn("prefers-color-scheme: dark", text)
        self.assertNotIn("<script src", text)   # self-contained


class Timeouts(unittest.TestCase):
    def test_a_stuck_ffmpeg_is_a_message(self):
        from unittest import mock
        stuck = subprocess.TimeoutExpired(["ffmpeg"], 60)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(webcopy, "_ffmpeg", return_value="ffmpeg"):
            with mock.patch.object(webcopy.subprocess, "run", side_effect=stuck), self.assertRaises(SystemExit) as got:
                webcopy.duration(os.path.join(d, "x.mp3"))
            self.assertIn("length", str(got.exception.code))
            with mock.patch.object(webcopy, "duration", return_value=30.0), \
                    mock.patch.object(webcopy.subprocess, "run", side_effect=stuck), self.assertRaises(SystemExit) as got:
                webcopy.make(os.path.join(d, "x.mp3"), "X", d)
            self.assertIn("web copy", str(got.exception.code))


class Page(unittest.TestCase):
    def test_one_part_has_one_download(self):
        with tempfile.TemporaryDirectory() as d:
            page = webcopy.page("A & B", [os.path.join(d, "A & B.web-1.mp3")], os.path.join(d, "p.html"))
            with open(page, encoding="utf-8") as f:
                text = f.read()
        self.assertIn("<title>A &amp; B</title>", text)
        self.assertIn("Download the MP3", text)
        self.assertNotIn("parts, which play", text)


if __name__ == "__main__":
    unittest.main()
