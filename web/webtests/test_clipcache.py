"""The web clip cache marks a clip used only when a build used it, and makes room at its cap (0.76.0)."""
import os
import shutil
import sys
import tempfile
import time
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import clipcache  # noqa: E402
from webtests.dbcase import DBCase  # noqa: E402


class ClipCache(DBCase):
    def setUp(self):
        self.conn.rollback()
        self.tmp = tempfile.mkdtemp(prefix="hf-clips-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        _, self.uk = self.make_user()

    def folder(self, name):
        path = os.path.join(self.tmp, name, clipcache.FOLDER)
        os.makedirs(path, exist_ok=True)
        return path

    def put(self, folder, name, body):
        with open(os.path.join(folder, name), "wb") as f:
            f.write(body)

    def used(self):
        return dict(self.conn.execute("select path, used_at from clip_cache where user_id = %s",
                                      (self.uk.user_id,)).fetchall())

    def test_loading_marks_nothing_and_a_hit_is_marked_without_being_sent_again(self):
        made = self.folder("made")
        for name in ("a.pcm", "b.pcm"):
            self.put(made, name, name.encode() * 100)
        self.assertEqual(clipcache.save(self.conn, self.uk, os.path.dirname(os.path.dirname(made)), {}), 2)
        self.conn.commit()
        first = self.used()
        time.sleep(0.05)
        home = os.path.join(self.tmp, "next")
        before = clipcache.load(self.conn, self.uk, home)
        self.conn.commit()
        self.assertEqual(self.used(), first)                         # loading marks nothing used
        cache = os.path.join(home, clipcache.FOLDER)
        os.utime(os.path.join(cache, "a.pcm"), (time.time() + 5, time.time() + 5))   # the build read a.pcm
        with mock.patch.object(clipcache.crypto, "seal", wraps=clipcache.crypto.seal) as seal:
            self.assertEqual(clipcache.save(self.conn, self.uk, home, before), 0)   # nothing sent again
        seal.assert_not_called()
        self.conn.commit()
        now = self.used()
        self.assertGreater(now["a.pcm"], first["a.pcm"])
        self.assertEqual(now["b.pcm"], first["b.pcm"])               # unused: ages, and a week on it goes

    def test_at_the_cap_the_clips_used_longest_ago_make_room(self):
        with mock.patch.object(clipcache, "MAX_TOTAL", 310):
            for name in ("old.pcm", "mid.pcm", "new.pcm"):   # three recordings, one clip each
                self.put(self.folder(name), name, b"x" * 100)
                self.assertEqual(clipcache.save(self.conn, self.uk, os.path.join(self.tmp, name), {}), 1)
                self.conn.commit()
                time.sleep(0.02)
            home = os.path.join(self.tmp, "fourth")
            before = clipcache.load(self.conn, self.uk, home)
            cache = os.path.join(home, clipcache.FOLDER)
            self.put(cache, clipcache.PACE, b"{}")
            self.put(cache, "next.pcm", b"y" * 100)
            self.assertEqual(clipcache.save(self.conn, self.uk, home, before), 2)   # both kept, none skipped
            self.conn.commit()
        kept = set(self.used())
        self.assertNotIn("old.pcm", kept)                            # used longest ago: it made room
        self.assertEqual(kept, {"mid.pcm", "new.pcm", "next.pcm", clipcache.PACE})
        self.conn.rollback()
