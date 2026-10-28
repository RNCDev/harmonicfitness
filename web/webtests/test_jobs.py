import datetime
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import config, db, folder, jobs, store, worker  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import MASTER, DBCase  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class JobsCase(DBCase):
    def setUp(self):
        self.settings = config.Settings(database_url=dbcase.URL, master_key=MASTER,
                                        base_url="http://localhost", role="worker", engine_root=ROOT)
        self.conn.rollback()
        self.conn.execute("delete from jobs")   # each test starts with an empty queue
        self.conn.commit()

    def connect(self):
        return db.connect(dbcase.URL, schema=self.schema)

    def run_one(self):
        return worker.run_one(self.conn, self.settings, connect=self.connect)

    def seeded_user(self):
        user_id, uk = self.make_user()
        self.assertEqual(store.write_back(self.conn, uk, folder.seed(ROOT), {}), [])
        self.conn.commit()
        return user_id, uk

    def brief_args(self, **over):
        args = {"goal": "strength", "minutes": 20, "preset": "bodyweight", "today": today()}
        args.update(over)
        return args

    def state(self, job_id):
        return self.conn.execute("select state, error from jobs where id = %s", (job_id,)).fetchone()


class Queue(JobsCase):
    def test_args_and_events_are_sealed(self):
        _, uk = self.make_user()
        job = jobs.enqueue(self.conn, uk, "brief", {"goal": "strength", "secret": "left ankle"})
        raw = bytes(self.conn.execute("select args from jobs where id = %s", (job,)).fetchone()[0])
        self.assertNotIn(b"left ankle", raw)
        self.assertEqual(jobs.args(self.conn, uk, job)["secret"], "left ankle")
        jobs.event(self.conn, uk, job, {"stage": "folder", "note": "left ankle"})
        raw = bytes(self.conn.execute("select body from job_events where job_id = %s",
                                      (job,)).fetchone()[0])
        self.assertNotIn(b"left ankle", raw)
        self.assertEqual([b for _, b in jobs.events(self.conn, uk, job)],
                         [{"stage": "folder", "note": "left ankle"}])
        self.conn.rollback()

    def test_one_job_per_user(self):
        _, a = self.make_user()
        _, b = self.make_user()
        first = jobs.enqueue(self.conn, a, "brief", {})
        jobs.enqueue(self.conn, a, "brief", {})
        claimed = jobs.claim(self.conn)
        self.assertEqual(claimed.id, first)
        self.assertIsNone(jobs.claim(self.conn))
        other = jobs.enqueue(self.conn, b, "brief", {})
        self.assertEqual(jobs.claim(self.conn).id, other)
        self.assertIsNone(jobs.claim(self.conn))

    def test_stale_running_job_fails_and_frees_user(self):
        _, uk = self.make_user()
        stale = jobs.enqueue(self.conn, uk, "brief", {})
        self.assertEqual(jobs.claim(self.conn).id, stale)
        later = jobs.enqueue(self.conn, uk, "brief", {})
        self.conn.execute("update jobs set heartbeat_at = now() - interval '5 minutes' where id = %s",
                          (stale,))
        self.conn.commit()
        self.assertIsNone(jobs.claim(self.conn))
        self.assertEqual(jobs.reap(self.conn), [stale])
        self.assertEqual(self.state(stale), ("failed", "interrupted"))
        self.assertEqual(jobs.claim(self.conn).id, later)
        self.assertEqual(self.state(stale)[0], "failed")   # never requeued
        self.conn.rollback()

    def test_fresh_heartbeat_is_not_reaped(self):
        _, uk = self.make_user()
        job = jobs.enqueue(self.conn, uk, "brief", {})
        jobs.claim(self.conn)
        self.conn.execute("update jobs set heartbeat_at = now() - interval '5 minutes' where id = %s",
                          (job,))
        self.conn.commit()
        jobs.heartbeat(self.conn, job)
        self.assertEqual(jobs.reap(self.conn), [])
        self.assertEqual(self.state(job)[0], "running")
        jobs.fail(self.conn, uk, job, "test over")

    def test_finish_after_reap_changes_nothing(self):
        _, uk = self.make_user()
        job = jobs.enqueue(self.conn, uk, "brief", {})
        jobs.claim(self.conn)
        self.conn.execute("update jobs set heartbeat_at = now() - interval '5 minutes' where id = %s",
                          (job,))
        self.conn.commit()
        jobs.reap(self.conn)
        self.assertFalse(jobs.finish(self.conn, uk, job, {"x": 1}))
        self.assertEqual(self.state(job), ("failed", "interrupted"))
        self.conn.rollback()


class Worker(JobsCase):
    def test_brief_job_end_to_end(self):
        _, uk = self.seeded_user()
        before = set(store.read_all(self.conn, uk))
        job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
        self.assertTrue(self.run_one())
        self.assertEqual(self.state(job), ("done", None))
        result = jobs.result(self.conn, uk, job)
        stem = f"{today()}-strength-20"
        self.assertEqual(result["stem"], stem)
        self.assertTrue(result["brief_md"].startswith("# Today's brief"))
        after = set(store.read_all(self.conn, uk))
        self.assertEqual(after - before, {f"workouts/{stem}/{stem}.menu.json",
                                          f"workouts/{stem}/{stem}.brief.md"})
        self.assertEqual([b["stage"] for _, b in jobs.events(self.conn, uk, job)],
                         ["folder", "brief", "saved"])
        self.assertEqual(jobs.events(self.conn, uk, job)[-1][1]["conflicts"], [])
        self.conn.rollback()

    def test_bad_args_never_run_the_engine(self):
        _, uk = self.seeded_user()
        bad = [{"minutes": 999}, {"minutes": "20"}, {"minutes": True}, {"goal": "nap"},
               {"preset": "moon-base"}, {"today": "2001-01-01"}, {"today": "not a date"}]
        with mock.patch.object(worker.engine, "run", side_effect=AssertionError("engine ran")):
            for over in bad:
                with self.subTest(over=over):
                    job = jobs.enqueue(self.conn, uk, "brief", self.brief_args(**over))
                    self.assertTrue(self.run_one())
                    state, error = self.state(job)
                    self.assertEqual(state, "failed")
                    self.assertTrue(error.startswith("invalid request: "), error)
            job = jobs.enqueue(self.conn, uk, "brief", {"goal": "strength"})
            self.run_one()
            self.assertEqual(self.state(job)[0], "failed")
        self.conn.rollback()

    def test_engine_failure_fails_the_job_and_writes_nothing(self):
        _, uk = self.seeded_user()
        before = store.read_all(self.conn, uk)
        job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
        fake = worker.engine.Result(1, "", "something about the listener\n")
        with mock.patch.object(worker.engine, "run", return_value=fake):
            self.run_one()
        self.assertEqual(self.state(job), ("failed", "the engine stopped (exit 1)"))
        self.assertEqual(jobs.result(self.conn, uk, job), {"stderr": "something about the listener\n"})
        self.assertEqual(store.read_all(self.conn, uk), before)
        self.conn.rollback()

    def test_folder_is_removed(self):
        _, uk = self.seeded_user()
        homes = []
        real = worker.HANDLERS["brief"]

        def ok(ctx):
            homes.append(ctx.home)
            return real(ctx)

        def boom(ctx):
            homes.append(ctx.home)
            raise RuntimeError("something personal")

        with mock.patch.dict(worker.HANDLERS, {"brief": ok, "boom": boom}):
            good = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
            self.assertTrue(self.run_one())
            bad = jobs.enqueue(self.conn, uk, "boom", {})
            with mock.patch("sys.stderr") as err:
                self.assertTrue(self.run_one())
        self.assertEqual(self.state(good)[0], "done")
        self.assertEqual(self.state(bad), ("failed", "the job stopped unexpectedly"))
        logged = "".join(str(c) for c in err.mock_calls)
        self.assertNotIn("something personal", logged)
        self.assertIn("RuntimeError", logged)
        self.assertIn(f"job {bad} ", logged)
        self.assertEqual(len(homes), 2)
        for home in homes:
            self.assertFalse(os.path.exists(home))
        self.conn.rollback()

    def test_unknown_kind_fails(self):
        _, uk = self.make_user()
        job = jobs.enqueue(self.conn, uk, "nonsense", {})
        self.assertTrue(self.run_one())
        self.assertEqual(self.state(job), ("failed", "unknown job kind"))
        self.conn.rollback()

    def test_idle_returns_false(self):
        self.assertFalse(self.run_one())

    def test_heartbeat_runs_on_its_own_connection(self):
        _, uk = self.make_user()
        seen = []

        def slow(ctx):
            import time
            start = self.conn.execute("select heartbeat_at from jobs where id = %s",
                                      (ctx.job_id,)).fetchone()[0]
            ctx.conn.commit()
            time.sleep(0.5)
            seen.append(self.conn.execute("select heartbeat_at from jobs where id = %s",
                                          (ctx.job_id,)).fetchone()[0] > start)
            ctx.conn.commit()
            return {}

        with mock.patch.dict(worker.HANDLERS, {"slow": slow}), \
                mock.patch.object(worker, "HEARTBEAT_EVERY", 0.1):
            job = jobs.enqueue(self.conn, uk, "slow", {})
            self.run_one()
        self.assertEqual(seen, [True])
        self.assertEqual(self.state(job)[0], "done")
        self.conn.rollback()
