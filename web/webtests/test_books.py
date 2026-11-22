"""The admin screen's books (0.87.0): only an account HARMONICFITNESS_ADMINS names sees them (anyone else gets 404,
as if there were nothing there), each sale is counted once at what was paid and outlives its account, a refund takes
its money back once, and a cost that isn't tracked is said, never counted as nothing."""
import dataclasses
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import api, books, config, fly  # noqa: E402
from webtests.test_minutes import SiteCase, paid_event, signed  # noqa: E402

NO_FLY = books.Fly(None, why="no token")


class Books(SiteCase):
    hosted = True

    def setUp(self):
        super().setUp()
        self.conn.execute("delete from sales")   # the class's tests share one database: each counts from nothing
        self.conn.execute("delete from costs")
        self.conn.commit()

    def as_admin(self, user_id):
        self.settings = dataclasses.replace(self.settings, admins=(str(user_id),))
        self.app = api.create_app(self.settings, connect=self.connect, client_dist=self.dist,
                                  clerk_send=self.fake_clerk, stripe_send=self.fake_stripe)
        client = self.other_client()
        client.cookies = self.client.cookies
        return client

    def webhook(self, payload):
        raw, headers = signed(payload)
        return self.client.post("/api/stripe/webhook", content=raw, headers=headers)

    def summary(self, days=0):
        out = books.summary(self.conn, days, NO_FLY)
        self.conn.rollback()
        return out

    def test_only_a_named_admin_gets_the_books(self):
        with self.subTest("signed out: nothing there"):
            self.assertEqual(self.other_client().get("/api/admin/books").status_code, 401)
        user_id, _ = self.signed_in()
        with self.subTest("signed in, not named: nothing there, and the page isn't offered"):
            self.assertEqual(self.client.get("/api/admin/books").status_code, 404)
            self.assertFalse(self.client.get("/api/me").json()["admin"])
        admin = self.as_admin(user_id)
        with self.subTest("named by id: the books, and the page is offered"):
            r = admin.get("/api/admin/books?days=30")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json()["days"], 30)
            self.assertTrue(admin.get("/api/me").json()["admin"])
        with self.subTest("a range the screen doesn't offer"):
            self.assertEqual(admin.get("/api/admin/books?days=5").status_code, 400)

    def test_a_username_is_not_an_admin_id(self):
        with self.assertRaises(config.ConfigError):
            config._admins({"HARMONICFITNESS_ADMINS": "rowan"})
        one, two = uuid.uuid4(), uuid.uuid4()
        self.assertEqual(config._admins({"HARMONICFITNESS_ADMINS": f"{one}, {two}"}), (str(one), str(two)))

    def test_each_sale_counts_once_and_outlives_its_account(self):
        user_id, _ = self.signed_in()
        for _ in range(2):   # Stripe sends it twice
            self.assertEqual(self.webhook(paid_event(user_id, ref="r1")).status_code, 200)
        got = self.summary()["money"]
        self.assertEqual((got["sales"], got["net"], got["refunds"]), (5.0, 5.0, 0.0))
        with self.subTest("an account gone before Stripe's word came: no minutes, but the money is kept"):
            self.assertEqual(self.webhook(paid_event(uuid.uuid4(), ref="r2")).status_code, 200)
            self.assertEqual(self.summary()["money"]["sales"], 10.0)
        with self.subTest("refunded in full, twice told: taken back once, whatever minutes were left"):
            refund = {"type": "charge.refunded", "data": {"object": {
                "refunded": True, "metadata": {"user": str(user_id), "pack": "hf_minutes_60", "ref": "r1"}}}}
            for _ in range(2):
                self.assertEqual(self.webhook(refund).status_code, 200)
            got = self.summary()["money"]
            self.assertEqual((got["sales"], got["refunds"], got["net"]), (10.0, 5.0, 5.0))
        with self.subTest("deleting the account keeps its sale in the books"):
            self.conn.execute("delete from users where id = %s", (user_id,))
            self.conn.commit()
            got = self.summary()["money"]
            self.assertEqual((got["sales"], got["refunds"]), (10.0, 5.0))

    def test_an_untracked_cost_is_said_not_counted_as_nothing(self):
        user_id, _ = self.signed_in()
        self.assertEqual(self.webhook(paid_event(user_id, ref="r3")).status_code, 200)
        got = self.summary()["money"]
        self.assertIsNone(got["write"])
        self.assertIsNone(got["fly"])
        self.assertIn("Fly", got["missing"])
        with self.subTest("once a cost is reported, it counts from that day"):
            self.conn.execute("insert into costs (user_id, kind, usd) values (%s, 'write', 0.25), (%s, 'voice', 0.5)",
                              (user_id, user_id))
            self.conn.commit()
            got = self.summary(7)["money"]
            self.assertEqual((got["write"], got["voice"]), (0.25, 0.5))
            self.assertEqual(got["profit"], round(5.0 - books.stripe_fee(5.0) - 0.75, 4))
            self.assertTrue(any(m.startswith("OpenRouter writing before ") for m in got["missing"]))


class FlyEstimate(unittest.TestCase):
    def test_priced_from_what_runs_and_unknown_when_unread(self):
        machines = [{"state": "started", "config": {"guest": {"cpu_kind": "shared", "cpus": 1, "memory_mb": 1024},
                                                     "metadata": {"fly_process_group": "web"}}},
                    {"state": "destroyed", "config": {"guest": {"cpus": 8, "memory_mb": 16384}}}]
        got = fly.price(machines, [{"size_gb": 10, "name": "data"}])
        self.assertEqual(got.monthly, round(fly.SHARED_CPU + fly.MEMORY_GB + 10 * fly.VOLUME_GB, 2))
        self.assertTrue(got.left_out)
        self.assertIsNone(fly.estimate("", "harmonicfitness").monthly)

        def broken(token, path):
            raise OSError("down")
        self.assertIsNone(fly.estimate("t", "app-broken", get=broken).monthly)


if __name__ == "__main__":
    unittest.main()
