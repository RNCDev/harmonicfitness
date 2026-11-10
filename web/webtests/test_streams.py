"""The one listener every progress stream shares (webapp/streams.py, 0.77.0), against Postgres."""
import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import db, streams  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import DBCase  # noqa: E402


class Hub(DBCase):
    def setUp(self):
        self.opened = []

        def connect():
            conn = db.connect(dbcase.URL, schema=self.schema)
            self.opened.append(conn)
            return conn
        self.hub = streams.Hub(connect)
        self.addCleanup(self.hub.close)

    def notify(self, job_id: int) -> None:
        self.conn.execute("select pg_notify('job_events', %s)", (str(job_id),))
        self.conn.commit()

    def drive(self, body):
        return asyncio.run(body())

    async def subscribe(self, user, job):
        loop = asyncio.get_running_loop()
        return await asyncio.to_thread(self.hub.subscribe, user, job, loop)

    def test_a_notify_wakes_only_its_jobs_streams(self):
        async def body():
            a, b = uuid.uuid4(), uuid.uuid4()
            one, two, other = await self.subscribe(a, 5), await self.subscribe(b, 5), await self.subscribe(a, 6)
            self.assertEqual(len(self.opened), 1)   # one connection for all three
            self.notify(5)
            self.assertTrue(await one.wait(5))
            self.assertTrue(await two.wait(5))
            self.assertFalse(await other.wait(0.3))
            self.notify(6)
            self.assertTrue(await other.wait(5))
        self.drive(body)

    def test_subscribe_returns_once_listening(self):
        """A NOTIFY sent the moment subscribe returns still arrives: LISTEN ran first."""
        async def body():
            sub = await self.subscribe(uuid.uuid4(), 9)
            self.notify(9)
            self.assertTrue(await sub.wait(5))
        self.drive(body)

    def test_a_listeners_fourth_stream_closes_their_oldest(self):
        async def body():
            user = uuid.uuid4()
            subs = [await self.subscribe(user, n) for n in (1, 2, 3)]
            someone_else = await self.subscribe(uuid.uuid4(), 1)
            self.assertFalse(any(s.closed for s in subs))
            fourth = await self.subscribe(user, 4)
            self.assertTrue(subs[0].closed)
            self.assertTrue(await subs[0].wait(1))   # woken, to see it's closed
            self.assertFalse(any(s.closed for s in (*subs[1:], fourth, someone_else)))
            self.notify(1)   # the closed one no longer hears its job
            self.assertTrue(await someone_else.wait(5))
        self.drive(body)

    def test_the_last_stream_leaving_closes_the_connection(self):
        async def body():
            a = await self.subscribe(uuid.uuid4(), 1)
            b = await self.subscribe(uuid.uuid4(), 2)
            self.hub.unsubscribe(a)
            self.assertFalse(self.opened[0].closed)
            self.hub.unsubscribe(b)
            self.hub.unsubscribe(b)   # twice is harmless
            deadline = time.monotonic() + 5
            while not self.opened[0].closed and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            self.assertTrue(self.opened[0].closed)
            again = await self.subscribe(uuid.uuid4(), 3)   # and a new one opens another
            self.assertEqual(len(self.opened), 2)
            self.notify(3)
            self.assertTrue(await again.wait(5))
        self.drive(body)

    def test_a_lost_connection_wakes_every_stream_and_listens_again(self):
        async def body():
            sub = await self.subscribe(uuid.uuid4(), 7)
            self.conn.execute("select pg_terminate_backend(%s)", (self.opened[0].info.backend_pid,))
            self.conn.commit()
            self.assertTrue(await sub.wait(5))   # woken to read its job's status itself
            deadline = time.monotonic() + 10
            while len(self.opened) < 2 and time.monotonic() < deadline:
                await asyncio.sleep(0.05)
            self.assertEqual(len(self.opened), 2)
            self.assertTrue(self.hub.listening.wait(5))
            self.notify(7)
            self.assertTrue(await sub.wait(5))
        with self._patch_backoff():
            self.drive(body)

    def test_a_closed_hub_starts_no_listener(self):
        self.hub.close()
        async def body():
            loop = asyncio.get_running_loop()
            sub = await asyncio.to_thread(self.hub.subscribe, uuid.uuid4(), 1, loop)
            self.assertTrue(sub.closed)
        self.drive(body)
        self.assertEqual(self.opened, [])

    def test_a_closed_stream_asks_the_browser_to_wait_before_reopening(self):
        from types import SimpleNamespace

        from webapp.routes import jobs as jobroutes
        self.hub.close()   # every subscribe now comes back closed, as the listener's oldest does
        st = SimpleNamespace(hub=self.hub)
        uk = SimpleNamespace(user_id=uuid.uuid4())

        async def body():
            return [line async for line in jobroutes._stream(st, uk, 1, 0)]
        self.assertEqual(self.drive(body), [f"retry: {jobroutes.CLOSED_RETRY_MS}\n\n"])

    def _patch_backoff(self):
        from unittest import mock
        return mock.patch.object(streams, "RECONNECT_WAIT", 0.1)


if __name__ == "__main__":
    import unittest
    unittest.main()
