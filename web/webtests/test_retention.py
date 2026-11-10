"""What the site stops keeping (0.76.0), and the indexes the busiest queries use."""
import datetime
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import conversations, jobs, retention, worker  # noqa: E402
from webtests.dbcase import DBCase, enqueue  # noqa: E402


class Sweep(DBCase):
    def setUp(self):
        self.conn.rollback()
        self.conn.execute("delete from jobs")
        self.conn.commit()
        _, self.uk = self.make_user()

    def job(self, state="done", days_ago=0):
        job_id = enqueue(self.conn, self.uk, "brief", {})
        self.conn.execute("update jobs set state = %s, finished_at = now() - make_interval(days => %s) where id = %s",
                          (state, days_ago, job_id))
        self.conn.commit()
        return job_id

    def ids(self):
        return {r[0] for r in self.conn.execute("select id from jobs").fetchall()}

    def test_finished_jobs_go_after_their_time_with_their_events(self):
        old, recent, queued = self.job("done", 20), self.job("failed", 3), self.job("queued", 30)
        named = self.job("done", 40)
        cid = conversations.create(self.conn, self.uk, "hi")
        conversations.set_job(self.conn, self.uk, cid, named)
        jobs.event(self.conn, self.uk, old, {"stage": "x"})
        gone = retention.sweep(self.conn)
        self.assertEqual(gone["jobs"], 1)
        self.assertEqual(self.ids(), {recent, queued, named})   # a conversation's job is kept
        self.assertEqual(self.conn.execute("select count(*) from job_events where job_id = %s", (old,)).fetchone()[0], 0)
        self.conn.rollback()

    def test_expired_sessions_links_and_old_allowance_days_go(self):
        uid = self.uk.user_id
        self.conn.execute("insert into sessions (token_hash, user_id, expires_at) values "
                          "('\\x01', %s, now() - interval '1 hour'), ('\\x02', %s, now() + interval '1 day')", (uid, uid))
        self.conn.execute("insert into sign_in_links (token_hash, user_id, expires_at) values "
                          "('\\x03', %s, now() - interval '3 days'), ('\\x04', %s, now() + interval '1 hour')",
                          (uid, uid))
        today = datetime.date.today()
        self.conn.execute("insert into spend (user_id, day, chars) values (%s, %s, 1), (%s, %s, 2)",
                          (uid, today - datetime.timedelta(days=40), uid, today))
        self.conn.commit()
        gone = retention.sweep(self.conn)
        self.assertEqual((gone["sessions"], gone["sign_in_links"], gone["spend"]), (1, 1, 1))
        self.assertEqual(self.conn.execute("select chars from spend where user_id = %s", (uid,)).fetchall(), [(2,)])
        self.conn.rollback()

    def test_the_worker_sweeps_at_most_once_a_minute(self):
        with mock.patch.object(worker, "_last_sweep", [float("-inf")]):
            self.assertTrue(worker._sweep_due())
            self.assertFalse(worker._sweep_due())

    def test_the_busiest_queries_have_their_indexes(self):
        names = {r[0] for r in self.conn.execute(
            "select indexname from pg_indexes where schemaname = current_schema()").fetchall()}
        for name in ("job_events_job", "jobs_queued", "jobs_user_state", "conversations_job", "sessions_user"):
            self.assertIn(name, names)
        self.conn.rollback()
