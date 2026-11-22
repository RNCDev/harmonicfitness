"""The admin screen's books (0.87.0): only an account HARMONICFITNESS_ADMINS names sees them (anyone else gets 404,
as if there were nothing there), each sale is counted once at what was paid and outlives its account, a refund takes
its money back once, and a cost that isn't tracked is said, never counted as nothing."""
import dataclasses
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import api, books, config, costs, fly  # noqa: E402
from webtests.test_minutes import SiteCase, paid_event, signed  # noqa: E402

NO_FLY = books.Fly(None, why="no token")


class Books(SiteCase):

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
        one, two = uuid.uuid4(), uuid.uuid4()
        self.assertEqual(config._admins({"HARMONICFITNESS_ADMINS": f"{one}, {two}"}), (str(one), str(two)))
        self.assertEqual(config._admins({"HARMONICFITNESS_ADMINS": f"rowan {one}"}), (str(one),))   # never a name

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


    def test_a_job_ending_puts_its_writing_and_its_renders_in_the_books_once(self):
        import json
        import tempfile
        import threading
        import types
        from decimal import Decimal

        from webapp import worker
        user_id, uk = self.make_user()
        home = tempfile.mkdtemp()
        path = os.path.join(home, costs.BUILDS)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"usd_estimate": 0.4}) + "\n")   # an earlier job's render
        meter = types.SimpleNamespace(usd=Decimal("0.0731"))
        ctx = types.SimpleNamespace(conn=self.conn, uk=uk, job_id=77, home=home, meter=meter,
                                    builds_before=costs.builds_lines(home), db_lock=threading.RLock())
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"usd_estimate": 0.18}) + "\n")   # this job's
        worker._record_costs(ctx)
        worker._record_costs(ctx)   # a second way out records nothing more
        rows = self.conn.execute("select kind, usd, estimated from costs where job_id = 77 order by kind").fetchall()
        self.conn.rollback()
        self.assertEqual(rows, [("voice", Decimal("0.180000"), True), ("write", Decimal("0.073100"), False)])

    def test_openrouters_own_count_is_kept_and_a_failed_read_keeps_nothing(self):
        self.conn.execute("delete from provider_spend")
        self.conn.commit()

        def down(key):
            raise OSError("unreachable")
        self.assertIsNone(costs.read_spend(self.conn, "sk-or-site", get=down))
        self.conn.commit()
        self.assertIsNone(self.summary(7)["money"]["unattributed"])
        self.assertEqual(costs.read_spend(self.conn, "sk-or-site", get=lambda k: {"data": {"usage_daily": 1.5}}), 1.5)
        self.assertEqual(costs.read_spend(self.conn, "sk-or-site", get=lambda k: {"data": {"usage_daily": 1.2}}), 1.2)
        self.conn.commit()
        got = self.summary(7)["money"]
        self.assertEqual(got["unattributed"], 1.5)   # a day's count never goes down within the day
        self.assertIsNone(costs.read_spend(self.conn, "", get=lambda k: {"data": {"usage_daily": 9}}))


class Costs(unittest.TestCase):
    def test_every_reply_is_counted_at_what_openrouter_charged(self):
        from decimal import Decimal

        from pydantic_ai import Agent
        from pydantic_ai.messages import ModelResponse, TextPart
        from pydantic_ai.models.function import FunctionModel

        def reply(messages, info):
            return ModelResponse(parts=[TextPart("ok")], provider_details={"cost": 0.0125})

        def unpriced(messages, info):
            return ModelResponse(parts=[TextPart("ok")])
        meter = costs.Metered(FunctionModel(reply))
        Agent(meter).run_sync("one")
        Agent(meter).run_sync("two")
        self.assertEqual((meter.usd, meter.replies), (Decimal("0.025"), 2))
        bare = costs.Metered(FunctionModel(unpriced))
        Agent(bare).run_sync("one")
        self.assertEqual((bare.usd, bare.replies), (Decimal(0), 1))

    def test_a_wrapped_model_keeps_its_kind_and_its_search(self):
        from webapp import providers
        from webapp.agent import native_tools, writers
        plain = providers.model_for("openrouter", "sk-or-test")
        wrapped = costs.Metered(plain)
        self.assertEqual(writers.is_gemini(wrapped), writers.is_gemini(plain))
        self.assertEqual(writers.thinking_settings(wrapped, "HIGH"), writers.thinking_settings(plain, "HIGH"))
        self.assertEqual(len(native_tools(wrapped)), len(native_tools(plain)))

    def test_a_job_counts_only_the_renders_it_made(self):
        import json
        import tempfile
        from decimal import Decimal
        home = tempfile.mkdtemp()
        path = os.path.join(home, costs.BUILDS)
        os.makedirs(os.path.dirname(path))

        def line(**rec):
            return json.dumps(rec) + "\n"
        with open(path, "w", encoding="utf-8") as f:   # an earlier job's recording
            f.write(line(kind="mp3", draft_sha256="a", build_id="b0", usd_estimate=0.4))
        before = costs.builds_lines(home)
        with open(path, "a", encoding="utf-8") as f:   # this job: a render that stopped, then one that made the MP3
            f.write(line(kind="failed", failed=True, draft_sha256="c", build_id="b1", usd_estimate=0.05))
            f.write(line(kind="outcome", event="stopped", build_id="b1"))
            f.write(line(kind="mp3", draft_sha256="c", build_id="b2", usd_estimate=0.25))
            f.write(line(kind="outcome", event="delivered", build_id="b2", usd_estimate=9.0))   # never a render
            f.write("not json\n")
        self.assertEqual(costs.voice_usd(home, before), Decimal("0.30"))
        self.assertEqual(costs.voice_usd(tempfile.mkdtemp(), 0), Decimal(0))

    def test_openrouters_own_charge_reaches_the_meter_through_its_real_model(self):
        """OpenRouter's usage.cost, through pydantic-ai's OpenRouterModel as the site builds it (only the HTTP is
        faked), run as the writers run it and wrapped again as a turn's Narrated wraps it."""
        import httpx
        from decimal import Decimal

        from openai import AsyncOpenAI
        from pydantic_ai import Agent
        from pydantic_ai.models.openrouter import OpenRouterModel
        from pydantic_ai.models.wrapper import WrapperModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        def answer(request):
            return httpx.Response(200, json={
                "id": "gen-1", "object": "chat.completion", "created": 1, "model": "google/gemini-3.8-flash",
                "provider": "Google", "choices": [{"index": 0, "finish_reason": "stop",
                                                    "message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0.00042}})
        client = AsyncOpenAI(api_key="sk-or-test", base_url="https://openrouter.ai/api/v1",
                             http_client=httpx.AsyncClient(transport=httpx.MockTransport(answer)))
        meter = costs.Metered(OpenRouterModel("google/gemini-3.8-flash",
                                              provider=OpenRouterProvider(openai_client=client)))
        Agent(meter).run_sync("as a writer")
        Agent(WrapperModel(meter)).run_sync("as a turn")
        self.assertEqual((meter.usd, meter.replies), (Decimal("0.00084"), 2))


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
