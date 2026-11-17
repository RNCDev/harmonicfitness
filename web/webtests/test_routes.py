"""The transaction rules the routers keep (0.76.1)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import conversations, db, spend  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests import test_api  # noqa: E402


class Routes(test_api.ApiCase):
    keyed = test_api.Conversations.keyed
    turn = test_api.Conversations.turn
    start = test_api.Conversations.start
    offered = test_api.Conversations.offered

    def test_a_refusal_inside_a_transaction_leaves_nothing_written(self):
        # record: spend.reserve inserts today's row before it finds the offer over the allowance, then the 409
        _, uk, cid = self.offered(chars=spend.DEFAULT_DAILY_CHARS + 1)
        r = self.client.post(f"/api/conversations/{cid}/record", json=self.turn(), headers=self.origin())
        self.assertEqual(r.status_code, 409)
        self.assertIsNone(self.conn.execute("select 1 from spend where user_id = %s", (uk.user_id,)).fetchone())
        # schedule: an idle conversation with no plan for later is refused, and stays as it was
        before = conversations.load(self.conn, uk, cid)
        self.conn.rollback()
        r = self.client.post(f"/api/conversations/{cid}/schedule", json=self.turn(), headers=self.origin())
        self.assertEqual(r.status_code, 409)
        after = conversations.load(self.conn, uk, cid)
        self.conn.rollback()
        self.assertEqual((after.version, after.state), (before.version, before.state))

    def test_a_session_renewal_is_kept_and_an_expired_one_deleted_though_the_answer_is_401(self):
        user_id, _ = self.signed_in()
        self.conn.execute("update sessions set renewed_at = now() - interval '2 days' where user_id = %s", (user_id,))
        self.conn.commit()
        before = self.renewed(user_id)
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        self.assertGreater(self.renewed(user_id), before)
        self.conn.execute("update sessions set expires_at = now() - interval '1 minute' where user_id = %s", (user_id,))
        self.conn.commit()
        self.assertEqual(self.client.get("/api/me").status_code, 401)
        fresh = db.connect(dbcase.URL, schema=self.schema)
        try:
            self.assertIsNone(fresh.execute("select 1 from sessions where user_id = %s", (user_id,)).fetchone())
        finally:
            fresh.close()

    def renewed(self, user_id):
        """The session's renewed_at, read on a connection of its own (so only what was committed)."""
        fresh = db.connect(dbcase.URL, schema=self.schema)
        try:
            return fresh.execute("select renewed_at from sessions where user_id = %s", (user_id,)).fetchone()[0]
        finally:
            fresh.close()


if __name__ == "__main__":
    unittest.main()
