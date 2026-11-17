"""Kit photos on the web (0.83.0): looked at, never kept. Each is re-saved without its metadata, waits beside its
turn's job (never in its args), is deleted as the turn reads it, and leaves only a line in the saved history."""
import base64
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from PIL import Image  # noqa: E402

from webapp import api, conversations, jobs, keystore, photos, retention, turns  # noqa: E402
from webtests.dbcase import DBCase  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
GPS = 0x8825          # the EXIF tag that holds where a photo was taken
ORIENTATION = 0x0112


def jpeg(width=3000, height=2000, gps=True, rotated=False, fmt="JPEG") -> bytes:
    """A phone photo: large, with a location and a camera's tags, optionally stored on its side."""
    im = Image.new("RGB", (width, height), (200, 120, 40))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"   # Make
    if gps:
        exif[GPS] = {1: "N", 2: (40.0, 26.0, 46.0), 3: "W", 4: (79.0, 58.0, 56.0)}
    if rotated:
        exif[ORIENTATION] = 6     # turn it a quarter to stand upright
    out = io.BytesIO()
    im.save(out, fmt, **({"exif": exif.tobytes()} if fmt in ("JPEG", "PNG", "WEBP") else {}))
    return out.getvalue()


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


class Clean(unittest.TestCase):
    def test_a_photo_is_resaved_small_with_no_metadata(self):
        out = photos.clean(jpeg())
        with Image.open(io.BytesIO(out)) as im:
            self.assertEqual(im.format, "JPEG")
            self.assertEqual(max(im.size), photos.EDGE)
            self.assertEqual(dict(im.getexif()), {})   # no location, no camera, nothing
            self.assertNotIn("exif", im.info)
        self.assertNotIn(b"PhoneMaker", out)

    def test_a_photo_stored_on_its_side_comes_out_upright(self):
        with Image.open(io.BytesIO(photos.clean(jpeg(1200, 800, rotated=True)))) as im:
            self.assertEqual(im.size, (800, 1200))

    def test_png_and_webp_are_read_and_other_files_refused(self):
        for fmt in ("PNG", "WEBP"):
            with Image.open(io.BytesIO(photos.clean(jpeg(400, 300, gps=False, fmt=fmt)))) as im:
                self.assertEqual(im.format, "JPEG", fmt)
        gif = io.BytesIO()
        Image.new("RGB", (10, 10)).save(gif, "GIF")
        for raw in (gif.getvalue(), b"not a photo at all", b"%PDF-1.7 ..."):
            with self.assertRaises(photos.Refused):
                photos.clean(raw)

    def test_a_photo_too_large_to_decode_is_refused_before_it_is_drawn(self):
        with mock.patch.object(photos, "PIXELS_MOST", 1000):
            with self.assertRaises(photos.Refused) as e:
                photos.clean(jpeg(100, 100, gps=False))
        self.assertIn("too large", e.exception.message)

    def test_what_the_page_sends_is_decoded_and_bounded(self):
        raw = jpeg(50, 50, gps=False)
        self.assertEqual(photos.decode(b64(raw)), raw)
        self.assertEqual(photos.decode("data:image/jpeg;base64," + b64(raw)), raw)
        for bad in ("not base64!", ""):
            with self.assertRaises(photos.Refused):
                photos.decode(bad)
        with mock.patch.object(photos, "RAW_MOST", 10), self.assertRaises(photos.Refused):
            photos.decode(b64(raw))
        with self.assertRaises(photos.Refused):
            photos.prepared([b64(raw)] * (photos.MOST + 1))
        self.assertEqual(photos.prepared(None), [])


class TurnArgs(unittest.TestCase):
    def args(self, **more):
        today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
        return {"conversation_id": 1, "line": "my kit", "answer": None, "today": today,
                "now": f"{today} Wednesday 08:00", **more}

    def test_a_turn_carries_only_how_many_photos_wait_for_it(self):
        self.assertIsNone(turns.check(self.args(photos=2)))
        for bad in (0, photos.MOST + 1, "2", True, [b"x"]):
            self.assertIsNotNone(turns.check(self.args(photos=bad)), bad)
        self.assertEqual(turns.PHOTOS_MOST, photos.MOST)


class BodyLimit(unittest.TestCase):
    def test_a_message_may_carry_its_photos_and_nothing_else_grows(self):
        most, words = api._BodyLimit.limit_for("/api/conversations/12/messages")
        self.assertGreater(most, photos.MOST * photos.RAW_MOST * 4 // 3)
        self.assertIn("photos", words)
        self.assertEqual(api._BodyLimit.limit_for("/api/conversations")[0], most)
        for other in ("/api/conversations/12/record", "/api/conversations/x/messages", "/api/link/redeem"):
            self.assertEqual(api._BodyLimit.limit_for(other), (api._BodyLimit.DEFAULT, api._BodyLimit.TOO_LARGE), other)


class History(unittest.TestCase):
    def test_the_saved_history_holds_a_line_in_each_photos_place(self):
        from pydantic_ai import ModelMessagesTypeAdapter
        from pydantic_ai.messages import BinaryContent, ModelRequest, ModelResponse, TextPart, UserPromptPart
        from webapp import agent
        asked = agent.with_photos("Here's my garage.", [b"\xff\xd8one", b"\xff\xd8two"])
        self.assertIn("2 photos", asked[0])
        self.assertEqual([c.data for c in asked[1:]], [b"\xff\xd8one", b"\xff\xd8two"])
        self.assertEqual(agent.with_photos("No photos.", ()), "No photos.")
        messages = [ModelRequest(parts=[UserPromptPart(content=asked)]), ModelResponse(parts=[TextPart("I see a rack.")]),
                    ModelRequest(parts=[UserPromptPart(content="Right.")])]
        kept = agent.without_photos(messages)
        saved = ModelMessagesTypeAdapter.dump_json(kept)
        self.assertNotIn(b"one", base64.b64decode(base64.b64encode(saved)))   # neither the bytes
        self.assertNotIn(b64(b"\xff\xd8one").encode(), saved)              # nor their base64
        self.assertFalse(any(isinstance(c, BinaryContent) for m in kept if isinstance(m, ModelRequest)
                             for p in m.parts if isinstance(p.content, list) for c in p.content))
        self.assertIn(b"2 photos of their kit, looked at in that turn and not kept", saved)
        self.assertIs(kept[1], messages[1])

    def test_the_web_always_carries_the_photo_rules(self):
        from webapp import agent
        rules = agent.kits_from_photos(ROOT)
        self.assertTrue(rules.startswith("**Kits from photos.**"))
        self.assertIn("On the web app", rules)
        self.assertNotIn("read with Read", rules)   # the computer's own way is left out
        for setup in (False, True):
            agent.skill_text.cache_clear()
            self.assertIn("**Kits from photos.**", agent.skill_text(ROOT, setup=setup))


class Kept(DBCase):
    def setUp(self):
        self.conn.rollback()
        self.conn.execute("delete from turn_photos")   # what another test left untaken
        self.conn.commit()
        _, self.uk = self.make_user()

    def queued(self, n=2):
        cid = conversations.create(self.conn, self.uk, "my kit", None, n)
        job_id = jobs.add(self.conn, self.uk, "turn", {"conversation_id": cid, "photos": n})
        photos.add(self.conn, self.uk, job_id, [f"photo {i}".encode() for i in range(n)])
        self.conn.commit()
        return cid, job_id

    def test_photos_wait_sealed_beside_the_job_and_go_as_they_are_read(self):
        cid, job_id = self.queued()
        sealed = [bytes(r[0]) for r in self.conn.execute("select body from turn_photos where job_id = %s", (job_id,))]
        self.assertEqual(len(sealed), 2)
        self.assertFalse(any(b"photo" in s for s in sealed))
        self.assertEqual(jobs.args(self.conn, self.uk, job_id), {"conversation_id": cid, "photos": 2})
        self.assertEqual(photos.take(self.conn, self.uk, job_id), [b"photo 0", b"photo 1"])
        self.assertEqual(photos.take(self.conn, self.uk, job_id), [])
        self.conn.commit()
        self.assertEqual(conversations.load(self.conn, self.uk, cid).lines,
                         [{"role": "user", "text": "my kit", "photos": 2}])
        self.conn.rollback()

    def test_another_users_turn_cannot_take_them(self):
        _, job_id = self.queued(1)
        _, other = self.make_user()
        self.assertEqual(photos.take(self.conn, other, job_id), [])
        self.assertEqual(len(photos.take(self.conn, self.uk, job_id)), 1)
        self.conn.rollback()

    def test_photos_no_turn_took_are_swept_after_the_hour(self):
        _, old = self.queued(1)
        _, fresh = self.queued(1)
        self.conn.execute("update turn_photos set created_at = now() - interval '61 minutes' where job_id = %s", (old,))
        self.conn.commit()
        self.assertEqual(retention.sweep(self.conn)["turn_photos"], 1)
        left = {r[0] for r in self.conn.execute("select job_id from turn_photos")}
        self.assertEqual(left, {fresh})
        self.conn.rollback()

