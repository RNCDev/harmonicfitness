import os
import unittest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import conversations  # noqa: E402
from webtests.dbcase import DBCase  # noqa: E402

QUESTION = {
    "questions": [
        {"id": "limits", "prompt": "Limits?", "options": [{"label": "Nothing new"},
                                                           {"label": "Knee"}],
         "multi": True, "other": True},
        {"id": "length", "prompt": "Length", "options": [{"label": "25 min"}],
         "multi": False, "other": False},
    ],
    "tool_call_id": "call_1",
}


class Conversations(DBCase):
    def raw(self, cid):
        return bytes(self.conn.execute("select body from conversations where id = %s",
                                       (cid,)).fetchone()[0])

    def test_create_load_roundtrip(self):
        _, uk = self.make_user()
        cid = conversations.create(self.conn, uk, "a 25 minute workout")
        self.conn.commit()
        c = conversations.load(self.conn, uk, cid)
        self.assertEqual((c.id, c.state, c.version), (cid, "working", 1))
        self.assertEqual(c.lines, [{"role": "user", "text": "a 25 minute workout"}])
        self.assertIsNone(c.history)
        self.assertIsNone(c.question)
        self.assertIsNone(c.plan)
        self.assertIsNone(c.stem)
        self.assertEqual(conversations.latest(self.conn, uk).id, cid)
        cid2 = conversations.create(self.conn, uk, "another")
        self.conn.commit()
        self.assertEqual(conversations.latest(self.conn, uk).id, cid2)

    def test_latest_none(self):
        _, uk = self.make_user()
        self.assertIsNone(conversations.latest(self.conn, uk))

    def test_body_is_sealed(self):
        _, uk = self.make_user()
        cid = conversations.create(self.conn, uk, "my secret knee story")
        self.conn.commit()
        self.assertNotIn(b"knee", self.raw(cid))
        self.assertNotIn(b"lines", self.raw(cid))

    def test_other_user_is_lookup_error(self):
        _, a = self.make_user()
        _, b = self.make_user()
        cid = conversations.create(self.conn, a, "hi")
        self.conn.commit()
        with self.assertRaises(LookupError):
            conversations.load(self.conn, b, cid)
        self.assertIsNone(conversations.latest(self.conn, b))
        self.assertFalse(conversations.begin_turn(self.conn, b, cid, "x", None))
        self.assertEqual(conversations.load(self.conn, a, cid).state, "working")

    def test_save_version_check(self):
        _, uk = self.make_user()
        cid = conversations.create(self.conn, uk, "hi")
        c = conversations.load(self.conn, uk, cid)
        c.state = "waiting"
        c.history = '[{"x": 1}]'
        c.question = QUESTION
        c.plan = {"title": "t"}
        c.stem = "2026-10-28-strength-25"
        c.lines.append({"role": "agent", "text": "ok"})
        self.assertTrue(conversations.save(self.conn, uk, c, 1))
        self.conn.commit()
        got = conversations.load(self.conn, uk, cid)
        self.assertEqual((got.state, got.version, got.history, got.question, got.plan, got.stem),
                         ("waiting", 2, '[{"x": 1}]', QUESTION, {"title": "t"},
                          "2026-10-28-strength-25"))
        self.assertEqual(len(got.lines), 2)
        before = self.raw(cid)
        c.state = "idle"
        self.assertFalse(conversations.save(self.conn, uk, c, 1))
        self.conn.commit()
        self.assertEqual(self.raw(cid), before)
        self.assertEqual(conversations.load(self.conn, uk, cid).state, "waiting")

    def test_begin_turn_states(self):
        _, uk = self.make_user()
        cid = conversations.create(self.conn, uk, "hi")
        self.assertFalse(conversations.begin_turn(self.conn, uk, cid, "more", None))
        for state in ("idle", "failed"):
            c = conversations.load(self.conn, uk, cid)
            c.state = state
            conversations.save(self.conn, uk, c, c.version)
            self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "more", None))
            got = conversations.load(self.conn, uk, cid)
            self.assertEqual(got.state, "working")
            self.assertEqual(got.lines[-1], {"role": "user", "text": "more"})
        c = conversations.load(self.conn, uk, cid)
        c.state = "waiting"
        c.question = QUESTION
        conversations.save(self.conn, uk, c, c.version)
        self.assertTrue(conversations.begin_turn(
            self.conn, uk, cid, None, {"limits": ["Nothing new"], "length": ["25 min"]}))
        got = conversations.load(self.conn, uk, cid)
        self.assertEqual(got.state, "working")
        self.assertIsNone(got.question)
        self.assertEqual(got.lines[-1],
                         {"role": "user", "text": "Limits: Nothing new · Length: 25 min"})
        self.assertFalse(conversations.begin_turn(self.conn, uk, cid, "x", None))
        self.assertFalse(conversations.begin_turn(self.conn, uk, 999999, "x", None))

    def test_answer_line(self):
        a = {"limits": ["Nothing new", "Knee"], "length": "other: 40 min"}
        self.assertEqual(conversations.answer_line(QUESTION, a),
                         "Limits: Nothing new, Knee · Length: 40 min")
        self.assertEqual(conversations.answer_line(QUESTION, {"length": ["25 min"]}),
                         "Length: 25 min")

    def job(self, uk, state):
        return self.conn.execute("insert into jobs (user_id, kind, args, state) values "
                                 "(%s, 'turn', %s, %s) returning id",
                                 (uk.user_id, b"", state)).fetchone()[0]

    def test_set_job_kept_through_save(self):
        _, uk = self.make_user()
        cid = conversations.create(self.conn, uk, "hi")
        self.assertIsNone(conversations.load(self.conn, uk, cid).job_id)
        job = self.job(uk, "queued")
        conversations.set_job(self.conn, uk, cid, job)
        c = conversations.load(self.conn, uk, cid)
        self.assertEqual((c.job_id, c.version), (job, 1))
        c.state = "idle"
        self.assertTrue(conversations.save(self.conn, uk, c, c.version))
        self.assertEqual(conversations.latest(self.conn, uk).job_id, job)
        _, other = self.make_user()
        conversations.set_job(self.conn, other, cid, None)   # another user's: nothing
        self.assertEqual(conversations.load(self.conn, uk, cid).job_id, job)
        self.conn.execute("delete from jobs where id = %s", (job,))
        self.assertIsNone(conversations.load(self.conn, uk, cid).job_id)
        self.conn.rollback()

    def test_heal(self):
        _, uk = self.make_user()
        for job_state, heals in (("queued", False), ("running", False), ("failed", True),
                                 ("done", True), (None, True)):
            with self.subTest(job_state=job_state):
                cid = conversations.create(self.conn, uk, "hi")
                if job_state:
                    conversations.set_job(self.conn, uk, cid, self.job(uk, job_state))
                c = conversations.load(self.conn, uk, cid)
                c.question = {"questions": [], "tool_call_id": "x"}
                conversations.save(self.conn, uk, c, c.version)
                healed = conversations.heal(self.conn, uk, conversations.load(self.conn, uk, cid))
                stored = conversations.load(self.conn, uk, cid)
                self.assertEqual((healed.state, stored.state), ("failed",) * 2 if heals else ("working",) * 2)
                if heals:
                    self.assertEqual(stored.lines[-1], {"role": "agent", "text": "That didn't work: interrupted"})
                    self.assertIsNone(stored.question)
                    self.assertEqual(healed.version, stored.version)
                self.conn.rollback()
        cid = conversations.create(self.conn, uk, "hi")
        c = conversations.load(self.conn, uk, cid)
        c.state = "idle"
        conversations.save(self.conn, uk, c, c.version)
        self.assertEqual(conversations.heal(self.conn, uk, c).state, "idle")   # only working heals
        stale = conversations.load(self.conn, uk, cid)
        stale.state = "working"
        conversations.save(self.conn, uk, stale, stale.version)
        old = conversations.load(self.conn, uk, cid)
        newer = conversations.load(self.conn, uk, cid)
        conversations.save(self.conn, uk, newer, newer.version)   # moved on meanwhile
        got = conversations.heal(self.conn, uk, old)              # the version check fails: as stored
        self.assertEqual((got.state, got.version), ("working", newer.version))
        self.assertEqual(conversations.load(self.conn, uk, cid).lines, [{"role": "user", "text": "hi"}])
        self.conn.rollback()


class Sealed(unittest.TestCase):
    """The sealed body, without a database."""

    def test_the_coach_flag_round_trips_and_defaults_off(self):
        import uuid
        from webapp import crypto, store
        uk = store.UserKey(user_id=uuid.uuid4(), key=bytes(range(32)))
        for coach in (True, False):
            c = conversations.Conversation(id=7, state="idle", version=1, coach=coach)
            got = conversations._open(uk, 7, "idle", 1, None, conversations._seal(uk, c))
            self.assertIs(got.coach, coach)
        old = crypto.seal(uk.key, b'{"history": null, "lines": []}', conversations._aad(uk, 7))   # before 0.24.0
        self.assertIs(conversations._open(uk, 7, "idle", 1, None, old).coach, False)
