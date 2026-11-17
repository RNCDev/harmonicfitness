"""The one listener every progress stream shares (webapp/streams.py, 0.77.0), against Postgres."""
import asyncio
import os
import sys
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


if __name__ == "__main__":
    import unittest
    unittest.main()
