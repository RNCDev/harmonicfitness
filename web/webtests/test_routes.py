"""The route table and the transaction rules the routers keep (0.76.1)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import conversations, db, spend  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests import test_api  # noqa: E402
from webtests.test_api import today  # noqa: E402

# FastAPI matches in this order: /api/conversations/latest before /api/conversations/{cid}, the client's catch-all last
ROUTES = [
    (['GET'], '/healthz'),
    (['GET'], '/api/auth'),
    (['POST'], '/api/register'),
    (['POST'], '/api/sign-in'),
    (['POST'], '/api/password'),
    (['GET'], '/link/{token}'),
    (['POST'], '/api/link/redeem'),
    (['POST'], '/api/sign-out'),
    (['POST'], '/api/device-link'),
    (['GET'], '/api/me'),
    (['GET'], '/api/coaches/{slug}/sample.mp3'),
    (['GET'], '/api/start'),
    (['GET'], '/api/sync'),
    (['POST'], '/api/sync/read'),
    (['POST'], '/api/sync/write'),
    (['POST'], '/api/import'),
    (['GET'], '/api/export'),
    (['GET'], '/api/workouts'),
    (['GET'], '/api/workouts/{ref}/script'),
    (['POST'], '/api/workouts/{ref}/feedback'),
    (['PUT'], '/api/workouts/{ref}/rating'),
    (['DELETE'], '/api/workouts/{ref}'),
    (['GET'], '/api/level'),
    (['PUT'], '/api/level'),
    (['POST'], '/api/account/delete'),
    (['GET'], '/api/media/{mid}'),
    (['GET'], '/api/feed'),
    (['POST'], '/api/feed'),
    (['DELETE'], '/api/feed'),
    (['GET', 'HEAD'], '/feed/{token}.xml'),
    (['GET', 'HEAD'], '/feed/{token}/{mid}.mp3'),
    (['GET'], '/api/keys'),
    (['PUT'], '/api/writer'),
    (['PUT'], '/api/coach'),
    (['PUT'], '/api/auto-record'),
    (['PUT'], '/api/sky'),
    (['PUT'], '/api/keys/{service}'),
    (['DELETE'], '/api/keys/{service}'),
    (['POST'], '/api/jobs'),
    (['POST'], '/api/balances'),
    (['GET'], '/api/jobs/{job_id}'),
    (['GET'], '/api/jobs/{job_id}/events'),
    (['POST'], '/api/conversations'),
    (['GET'], '/api/conversations/latest'),
    (['GET'], '/api/conversations/{cid}'),
    (['GET'], '/api/conversations/{cid}/history'),
    (['POST'], '/api/conversations/{cid}/record'),
    (['POST'], '/api/conversations/{cid}/schedule'),
    (['POST'], '/api/conversations/{cid}/cancel'),
    (['POST'], '/api/conversations/{cid}/stop'),
    (['POST'], '/api/conversations/{cid}/messages'),
    (['GET'], '/{path:path}'),
]


def flat(routes) -> list:
    """Every route in the order they're matched: FastAPI (0.161) keeps an included router as one entry, matched in its
    place, whose own routes are matched in their order."""
    out = []
    for r in routes:
        if hasattr(r, "original_router"):
            out += flat(r.original_router.routes)
        elif hasattr(r, "methods"):
            out.append((sorted(r.methods), r.path))
    return out


class Routes(test_api.ApiCase):
    keyed = test_api.Conversations.keyed
    turn = test_api.Conversations.turn
    start = test_api.Conversations.start
    offered = test_api.Conversations.offered

    def test_the_routes_and_their_order_are_unchanged(self):
        self.assertEqual(flat(self.app.routes), ROUTES)

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

    def test_a_session_is_renewed_and_the_renewal_kept(self):
        user_id, _ = self.signed_in()
        self.conn.execute("update sessions set renewed_at = now() - interval '2 days' where user_id = %s", (user_id,))
        self.conn.commit()
        before = self.renewed(user_id)
        self.assertEqual(self.client.get("/api/me").status_code, 200)
        self.assertGreater(self.renewed(user_id), before)

    def test_an_expired_session_is_deleted_though_the_answer_is_401(self):
        user_id, _ = self.signed_in()
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
