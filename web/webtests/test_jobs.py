import datetime
import json
import os
import sys
import threading
import time
import unittest
from unittest import mock

import psycopg

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import config, db, folder, jobs, keystore, store, worker  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import MASTER, DBCase  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def today() -> str:
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def now() -> str:
    """The listener's clock as the page sends it: the server's own (UTC), so it is never more than 14 hours
    off, whatever the hour the tests run at (a fixed 08:00 was 14.5 hours off after 22:30 UTC)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %A %H:%M")


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
    def test_a_job_not_yet_due_waits_and_one_queued_after_it_runs(self):
        _, uk = self.make_user()
        later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        first = jobs.add(self.conn, uk, "brief", {"x": 1}, not_before=later)
        second = jobs.add(self.conn, uk, "brief", {"x": 2})
        self.conn.commit()
        self.assertEqual(jobs.claim(self.conn).id, second)
        self.assertEqual(self.state(first), ("queued", None))
        self.assertEqual(jobs.due_at(self.conn, first), later)
        self.assertTrue(jobs.cancel_queued(self.conn, uk, first))
        self.assertFalse(jobs.cancel_queued(self.conn, uk, second))   # running: Stop's to end
        self.conn.commit()
        self.assertEqual(self.state(first), ("failed", "cancelled"))

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

    def test_balances_job_keeps_only_what_the_page_shows(self):
        _, uk = self.seeded_user()
        keystore.put(self.conn, uk, "fish", "sk-abcdefghijklmnop")
        self.conn.commit()
        before = store.read_all(self.conn, uk)
        seen = []
        out = json.dumps({"fish": {"name": "Fish Audio", "billing_page": "https://x", "set": True, "reports": True,
                                   "ok": True, "usd": 12.50},
                          "elevenlabs": {"name": "ElevenLabs", "set": True, "reports": True, "ok": False,
                                         "kind": "auth", "message": "the service's own words"},
                          "inworld": {"name": "Inworld", "set": False, "reports": False}})

        def record(root, home, argv, extra_env={}, timeout=120, cancel=None):
            seen.append((argv, dict(extra_env)))
            return worker.engine.Result(0, out, "")
        job = jobs.enqueue(self.conn, uk, "balances", {})
        with mock.patch.object(worker.engine, "run", side_effect=record):
            self.assertTrue(self.run_one())
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(seen, [(["balances", "--json"], {"FISH_AUDIO_API_KEY": "sk-abcdefghijklmnop"})])
        self.assertEqual(jobs.result(self.conn, uk, job), {"balances": {"fish": {"ok": True, "usd": 12.50},
                                                                        "elevenlabs": {"ok": False, "kind": "auth"}}})
        self.assertEqual(store.read_all(self.conn, uk), before)   # no file touched
        self.conn.rollback()

    def test_balances_job_fails_on_an_unreadable_answer_or_args(self):
        _, uk = self.seeded_user()
        with mock.patch.object(worker.engine, "run", return_value=worker.engine.Result(0, "not json", "")):
            job = jobs.enqueue(self.conn, uk, "balances", {})
            self.run_one()
            self.assertEqual(self.state(job), ("failed", "the engine's answer couldn't be read"))
        with mock.patch.object(worker.engine, "run", side_effect=AssertionError("engine ran")):
            job = jobs.enqueue(self.conn, uk, "balances", {"x": 1})
            self.run_one()
            self.assertTrue(self.state(job)[1].startswith("invalid request: "))
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

    def test_brief_gets_the_users_keys(self):
        _, uk = self.seeded_user()
        _, other = self.seeded_user()
        keystore.put(self.conn, uk, "fish", "sk-abcdefghijklmnop")
        keystore.put(self.conn, uk, "retired-service", "sk-zzzzzzzzzzzz")
        self.conn.commit()
        seen = []

        def record(root, home, argv, extra_env={}, timeout=120, cancel=None):
            seen.append(dict(extra_env))
            return worker.engine.Result(1, "", "")
        with mock.patch.object(worker.engine, "run", side_effect=record):
            jobs.enqueue(self.conn, uk, "brief", self.brief_args())
            self.run_one()
            jobs.enqueue(self.conn, other, "brief", self.brief_args())
            self.run_one()
        self.assertEqual(seen, [{"FISH_AUDIO_API_KEY": "sk-abcdefghijklmnop"}, {}])
        self.conn.rollback()

    def test_key_in_engine_output_is_scrubbed(self):
        # engine_root stays the real engine, so the request validates; only the run is pointed at a fake root
        from webtests.test_engine import stub
        fake = stub('echo "$FISH_AUDIO_API_KEY" >&2; exit 1')
        real_run = worker.engine.run
        _, uk = self.seeded_user()
        keystore.put(self.conn, uk, "fish", "sk-abcdefghijklmnop")
        self.conn.commit()
        job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
        with mock.patch.object(worker.engine, "run",
                               side_effect=lambda root, *a, **k: real_run(fake, *a, **k)):
            self.run_one()
        self.assertEqual(self.state(job)[0], "failed")
        detail = jobs.result(self.conn, uk, job)
        self.assertIn("<key>", detail["stderr"])
        self.assertNotIn("sk-abcdefghijklmnop", detail["stderr"])
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


class Reconnect(unittest.TestCase):
    def test_the_worker_reconnects_when_the_database_closes_its_connection(self):
        import threading
        stopping = threading.Event()
        opened, closed = [], []

        class Conn:
            def __init__(self, n):
                self.n = n

            def notifies(self, timeout, stop_after):
                if self.n == 0:
                    raise psycopg.OperationalError("SSL connection has been closed unexpectedly")
                stopping.set()
                return iter(())

            def close(self):
                closed.append(self.n)

        def connect(settings):
            n = len(opened)
            opened.append(n)
            return Conn(n), Conn(n)
        with mock.patch.object(worker, "RECONNECT_WAIT", 0):
            worker.serve(None, stopping, connect=connect, run=lambda conn, settings: False)
        self.assertEqual(opened, [0, 1])          # connected again after the drop, rather than exiting
        self.assertEqual(sorted(closed), [0, 0, 1, 1])

    def test_an_old_or_replaced_connection_is_opened_again_between_jobs(self):
        import threading
        stopping = threading.Event()
        opened, runs = [], []

        class Conn:
            closed, broken = False, False

            def notifies(self, timeout, stop_after):
                return iter(())

            def close(self):
                self.closed = True

        def connect(settings):
            opened.append(1)
            return Conn(), Conn()

        def run(conn, settings):
            runs.append(conn)
            if len(runs) == 2:
                conn.closed = True    # a job replaced it (Ctx.fresh closes the dropped one)
            if len(runs) == 4:
                stopping.set()
            return True
        with mock.patch.object(worker, "MAX_CONNECTION_AGE", 3600):
            worker.serve(None, stopping, connect=connect, run=run)
        self.assertEqual(len(opened), 2)           # once at the start, once after the job closed it
        self.assertIs(runs[0], runs[1])
        self.assertIsNot(runs[1], runs[2])
        opened.clear(), runs.clear(), stopping.clear()
        with mock.patch.object(worker, "MAX_CONNECTION_AGE", -1):   # every connection is too old by the next job
            worker.serve(None, stopping, connect=connect, run=run)
        self.assertEqual(len(opened), 4)


class LostJobs(JobsCase):
    def files_and_events(self, uk, job):
        return set(store.read_all(self.conn, uk)), [b["stage"] for _, b in jobs.events(self.conn, uk, job)]

    def test_job_reaped_before_completion_writes_nothing(self):
        _, uk = self.seeded_user()
        before = set(store.read_all(self.conn, uk))
        real = worker.HANDLERS["brief"]

        def reaped_meanwhile(ctx):
            out = real(ctx)   # the engine has run and the files are harvested
            self.conn.execute("update jobs set state = 'failed', error = 'interrupted', "
                              "finished_at = now() where id = %s", (ctx.job_id,))
            self.conn.commit()
            return out

        with mock.patch.dict(worker.HANDLERS, {"brief": reaped_meanwhile}), \
                mock.patch("sys.stderr") as err:
            job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
            self.assertTrue(self.run_one())
        files, stages = self.files_and_events(uk, job)
        self.assertEqual(files, before)
        self.assertNotIn("saved", stages)
        self.assertEqual(self.state(job), ("failed", "interrupted"))
        self.assertIn(f"job {job} was no longer running", "".join(str(c) for c in err.mock_calls))
        self.conn.rollback()

    def test_lost_heartbeat_skips_the_write_back(self):
        import time
        _, uk = self.seeded_user()
        before = set(store.read_all(self.conn, uk))
        real = worker.HANDLERS["brief"]

        def slow(ctx):
            time.sleep(0.3)
            return real(ctx)

        with mock.patch.dict(worker.HANDLERS, {"brief": slow}), \
                mock.patch.object(worker, "HEARTBEAT_EVERY", 0.05), \
                mock.patch.object(jobs, "heartbeat", return_value=False), \
                mock.patch("sys.stderr"):
            job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
            self.assertTrue(self.run_one())
        files, stages = self.files_and_events(uk, job)
        self.assertEqual(files, before)
        self.assertNotIn("saved", stages)
        self.assertEqual(self.state(job), ("failed", "interrupted"))
        self.conn.rollback()

    def test_heartbeat_connect_failure_skips_the_write_back(self):
        _, uk = self.seeded_user()
        before = set(store.read_all(self.conn, uk))

        def broken():
            raise psycopg.OperationalError("no route")

        hold = threading.Event()
        real = worker.engine.run

        def slow_brief(*a, **k):   # the job outlasts every heartbeat try
            hold.wait(1)
            return real(*a, **k)
        with mock.patch("sys.stderr"), mock.patch.object(worker, "HEARTBEAT_RETRY_WAIT", 0.05), \
                mock.patch.object(worker.engine, "run", side_effect=slow_brief):
            job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
            self.assertTrue(worker.run_one(self.conn, self.settings, connect=broken))
        self.assertEqual(set(store.read_all(self.conn, uk)), before)
        self.assertEqual(self.state(job), ("failed", "interrupted"))
        self.conn.rollback()

    def test_a_heartbeat_that_fails_once_is_tried_again(self):
        _, uk = self.seeded_user()
        tries = []
        real = self.connect

        def flaky():
            tries.append(1)
            if len(tries) == 1:
                raise psycopg.OperationalError("a moment's outage")
            return real()
        with mock.patch("sys.stderr"), mock.patch.object(worker, "HEARTBEAT_RETRY_WAIT", 0.05), \
                mock.patch.object(worker, "HEARTBEAT_EVERY", 0.1):
            job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
            self.assertTrue(worker.run_one(self.conn, self.settings, connect=flaky))
        self.assertEqual(self.state(job), ("done", None))
        self.conn.rollback()

    def test_hung_heartbeat_connect_never_blocks(self):
        import threading
        import time
        _, uk = self.make_user()
        release = threading.Event()
        self.addCleanup(release.set)

        def hung():
            release.wait(60)
            return mock.MagicMock()   # the halt is set by then: it closes and ends quietly

        with mock.patch.dict(worker.HANDLERS, {"noop": lambda ctx: {}}), \
                mock.patch.object(worker, "CONNECT_TIMEOUT", 0), \
                mock.patch.object(worker, "JOIN_SLACK", 0.2), mock.patch("sys.stderr"):
            job = jobs.enqueue(self.conn, uk, "noop", {})
            t = time.monotonic()
            self.assertTrue(worker.run_one(self.conn, self.settings, connect=hung))
        self.assertLess(time.monotonic() - t, 5)
        self.assertEqual(self.state(job)[0], "done")   # no heartbeat was missed in that time
        self.conn.rollback()

    def test_default_heartbeat_connect_has_a_timeout(self):
        _, uk = self.make_user()
        with mock.patch.dict(worker.HANDLERS, {"noop": lambda ctx: {}}), \
                mock.patch.object(worker.psycopg, "connect") as connect:
            jobs.enqueue(self.conn, uk, "noop", {})
            self.assertTrue(worker.run_one(self.conn, self.settings))
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], worker.CONNECT_TIMEOUT)
        self.conn.rollback()


# ---- the turn job ---------------------------------------------------------------------------------

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from pydantic_ai import ModelHTTPError, UsageLimits  # noqa: E402
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart  # noqa: E402
from pydantic_ai.models.function import FunctionModel  # noqa: E402

from webapp import conversations, providers  # noqa: E402

MODEL_KEY = "sk-ant-test-model-key-0123456789"
STEM = f"{today()}-strength-20"
BRIEF_ARGV = ["brief", "--goal", "strength", "--minutes", "20", "--preset", "bodyweight",
              "--save", f"me/workouts/{STEM}/{STEM}.draft.txt"]


def returned(messages):
    return [p.tool_name for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]


class Turn(JobsCase):
    def setUp(self):
        super().setUp()
        self.homes = []
        real = worker.folder.materialize

        def record(files, home):
            self.homes.append(home)
            return real(files, home)
        patcher = mock.patch.object(worker.folder, "materialize", side_effect=record)
        patcher.start()
        self.addCleanup(patcher.stop)

    def user(self, key=True):
        _, uk = self.seeded_user()
        if key:
            keystore.put(self.conn, uk, "anthropic", MODEL_KEY)
            self.conn.commit()
        return uk

    def start(self, uk, line="a 20-minute strength workout"):
        cid = conversations.create(self.conn, uk, line)
        self.conn.commit()
        return cid

    def turn_args(self, cid, line=None, answer=None, **over):
        args = {"conversation_id": cid, "line": line, "answer": answer, "today": today(),
                "now": now()}
        args.update(over)
        return args

    def enqueue_turn(self, uk, cid, args):
        """A turn job recorded as the conversation's own, as the API queues one."""
        job = jobs.enqueue(self.conn, uk, "turn", args)
        conversations.set_job(self.conn, uk, cid, job)
        self.conn.commit()
        return job

    def run_turn(self, uk, script, cid, line=None, answer=None, **over):
        """Enqueue a turn and run it with `script` as the model; (job id, the conversation after)."""
        job = self.enqueue_turn(uk, cid, self.turn_args(cid, line, answer, **over))
        model = FunctionModel(script) if callable(script) else script
        with mock.patch.object(providers, "model_for", return_value=model) as model_for:
            self.assertTrue(self.run_one())
        self.model_for = model_for
        conv = conversations.load(self.conn, uk, cid)
        self.conn.rollback()
        return job, conv

    def test_turn_job_saves_the_reply(self):
        uk = self.user()
        cid = self.start(uk)

        def script(messages, info):
            return ModelResponse(parts=[TextPart("Anything sore or off today?")])
        job, conv = self.run_turn(uk, script, cid, line="a 20-minute strength workout")
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(jobs.result(self.conn, uk, job), {"conversation_id": cid, "state": "idle"})
        self.assertEqual(conv.state, "idle")
        self.assertIsNone(conv.question)
        self.assertIsNone(conv.plan)
        self.assertIsNone(conv.stem)
        self.assertEqual(conv.lines, [{"role": "user", "text": "a 20-minute strength workout"},
                                      {"role": "agent", "text": "Anything sore or off today?"}])
        self.assertIsNotNone(conv.history)
        self.model_for.assert_called_once_with("anthropic", MODEL_KEY)
        self.assertEqual([b["stage"] for _, b in jobs.events(self.conn, uk, job)][:2], ["folder", "thinking"])
        self.conn.rollback()

    def test_first_turn_has_step_one_and_later_turns_start_feeds(self):
        from concurrent.futures import Future
        from webapp import agent
        from pydantic_ai.messages import UserPromptPart
        uk = self.user()
        cid = self.start(uk)
        prompts = []

        def script(messages, info):
            prompts.append([p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1])
            return ModelResponse(parts=[TextPart("1. How long?")])
        started = []

        def fake_feeds(deps, pool):
            started.append(deps.today)
            f = Future()
            f.set_result(agent.tools.ToolResult(code=0, output="sunny"))
            return f
        with mock.patch.object(agent, "start_feeds", side_effect=fake_feeds):
            job, conv = self.run_turn(uk, script, cid, line="stretch please")
            self.assertEqual(self.state(job), ("done", None))
            self.assertTrue(prompts[0].startswith(agent.SETUP_FIRST))   # a new listener: set up first
            self.assertIn("Step 1 is done", prompts[0])
            self.assertIn("### ./harmonicfitness get coach (exit ", prompts[0])
            self.assertEqual(started, [])   # the check-in comes first
            self.assertIn("Getting you set up",
                          [b.get("text") for _, b in jobs.events(self.conn, uk, job)])
            prefetch = [(b["id"], b["state"]) for _, b in jobs.events(self.conn, uk, job)
                        if b.get("text") == "Getting you set up"]
            self.assertEqual(prefetch, [(1, "running"), (1, "done")])   # said as it starts, then as it ends
            self.conn.rollback()
            self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "25 minutes", None))
            self.conn.commit()
            job, conv = self.run_turn(uk, script, cid, line="25 minutes")
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(prompts[1], "25 minutes")
        self.assertEqual(started, [today()])

    def test_the_bare_topics_ask_is_answered_at_once_then_a_light_turn_adds_it(self):
        from concurrent.futures import Future
        from webapp import agent
        from pydantic_ai.messages import UserPromptPart
        uk = self.user()
        ver, body = store.read_all(self.conn, uk)["profile.md"]   # set up: an experience level
        store.write_back(self.conn, uk, {"profile.md": body.replace(b'experience = ""', b'experience = "novice"')},
                         {"profile.md": ver})
        self.conn.commit()
        line = "I'd like to update my interests."
        cid = self.start(uk, line)
        started, prompts = [], []

        def fake_feeds(deps, pool):
            started.append(deps.today)
            f = Future()
            f.set_result(agent.tools.ToolResult(code=0, output="sunny"))
            return f

        def never(messages, info):
            raise AssertionError("the opener needs no model")
        with mock.patch.object(agent, "start_feeds", side_effect=fake_feeds):
            job, conv = self.run_turn(uk, never, cid, line=line)
            self.assertEqual(self.state(job), ("done", None))
            self.assertEqual(conv.lines[-1], {"role": "agent", "text": agent.TOPICS_OPENER})
            self.conn.rollback()

            def script(messages, info):
                prompts.append([p.content for m in messages for p in m.parts if isinstance(p, UserPromptPart)][-1])
                return ModelResponse(parts=[TextPart("Added Example Letter.")])
            nxt = "I like reading https://www.example.com/"
            self.assertTrue(conversations.begin_turn(self.conn, uk, cid, nxt, None))
            self.conn.commit()
            job, conv = self.run_turn(uk, script, cid, line=nxt)
        self.assertEqual(self.state(job), ("done", None))
        self.assertIn("A topics job", prompts[0])          # the topics as they stand, in place of step 1
        self.assertNotIn("Step 1 is done", prompts[0])
        self.assertEqual(started, [])                      # no feeds for a topics job
        self.conn.rollback()

    def test_a_recording_is_priced_then_approved_then_kept(self):
        from webapp import clipcache, media
        uk = self.user()
        cid = self.start(uk)
        real = worker.engine.run
        built = []

        def engine_run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if argv[:2] == ["get", "cost"]:
                return worker.engine.Result(0, '{"service": "fish", "usd": 0.03, "pending_design": false}', "")
            if argv and argv[0] == "build":
                if "--max-chars" in argv and argv[argv.index("--max-chars") + 1] == "1":
                    return worker.engine.Result(64, "the script speaks 2,000 characters; at most 1", "")
                if "--lint-only" in argv:
                    return worker.engine.Result(0, "ok", "")
                built.append(argv)
                cache = os.path.join(home, "workouts", ".audio-cache")
                self.assertTrue(os.path.isfile(os.path.join(cache, "old.wav")) or len(built) == 1)
                os.makedirs(os.path.join(home, "workouts", "w"), exist_ok=True)
                with open(os.path.join(home, "workouts", "w", "Workout 5 min.mp3"), "wb") as f:
                    f.write(b"ID3fake-mp3")
                os.makedirs(cache, exist_ok=True)
                with open(os.path.join(cache, "old.wav"), "wb") as f:
                    f.write(b"RIFFclip")
                return worker.engine.Result(0, "built", "")
            return real(root, home, argv, extra_env=extra_env, timeout=timeout)

        BUILD = ["build", "me/workouts/w/w.draft.txt", "Workout 5 min", "--coach", "Coach Reed"]

        def script(messages, info):
            if not [p for m in messages[-1:] for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BUILD}, tool_call_id=f"b{len(messages)}")])
            return ModelResponse(parts=[TextPart("Done.")])
        with mock.patch.object(worker.engine, "run", side_effect=engine_run):
            job, conv = self.run_turn(uk, script, cid, line="just go")
            self.assertEqual(self.state(job), ("done", None))
            self.assertEqual(built, [])                       # priced, not recorded
            self.assertEqual(conv.offer["chars"], 2000)
            self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "Yes, record it.", None))
            self.conn.commit()
            job, conv = self.run_turn(uk, script, cid, line="Yes, record it.", record=True)
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(built[0][-2:], ["--max-chars", "2000"])
        self.assertIsNone(conv.offer)
        audio = conv.lines[-1]["audio"]
        self.assertEqual(audio["name"], "Workout 5 min")
        self.assertEqual(media.get(self.conn, uk, audio["id"])[1], b"ID3fake-mp3")
        self.conn.rollback()
        self.assertNotIn("workouts/w/Workout 5 min.mp3", store.read_all(self.conn, uk))   # never in the store
        self.conn.rollback()
        home = self.homes[-1]
        os.makedirs(home, exist_ok=True)
        self.assertEqual(list(clipcache.load(self.conn, uk, home)), ["old.wav"])   # kept for the next recording
        self.conn.rollback()

    def test_a_writing_turn_loads_only_the_measured_pace(self):
        import tempfile
        from webapp import clipcache
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        uk = self.user()
        made = os.path.join(tmp.name, "made")
        os.makedirs(os.path.join(made, clipcache.FOLDER))
        for name, body in ((clipcache.PACE, b'{"pace": 1}'), ("clip.pcm", b"pcm")):
            with open(os.path.join(made, clipcache.FOLDER, name), "wb") as f:
                f.write(body)
        clipcache.save(self.conn, uk, made, {})
        self.conn.commit()
        home = os.path.join(tmp.name, "writing")
        self.assertTrue(clipcache.load_pace(self.conn, uk, home))
        self.assertEqual(os.listdir(os.path.join(home, clipcache.FOLDER)), [clipcache.PACE])   # no clips
        with open(os.path.join(home, clipcache.FOLDER, clipcache.PACE), "rb") as f:
            self.assertEqual(f.read(), b'{"pace": 1}')
        self.conn.rollback()
        self.assertFalse(clipcache.load_pace(self.conn, self.user(), os.path.join(tmp.name, "none")))
        self.conn.rollback()

    def test_record_without_asking_records_in_the_same_turn_within_the_allowance(self):
        from webapp import keystore, media, spend
        uk = self.user()
        keystore.set_auto_record(self.conn, uk, True)
        self.conn.commit()
        cid = self.start(uk)
        real = worker.engine.run
        built = []

        def engine_run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if argv[:2] == ["get", "cost"]:
                return worker.engine.Result(0, '{"service": "fish", "usd": 0.03, "pending_design": false}', "")
            if argv and argv[0] == "build":
                if "--lint-only" in argv:
                    return worker.engine.Result(0, "ok\nSends 2,000 characters to the voice service", "")
                built.append(argv)
                os.makedirs(os.path.join(home, "workouts", "w"), exist_ok=True)
                with open(os.path.join(home, "workouts", "w", "Workout 5 min.mp3"), "wb") as f:
                    f.write(b"ID3fake-mp3")
                return worker.engine.Result(0, "built", "")
            return real(root, home, argv, extra_env=extra_env, timeout=timeout)

        BUILD = ["build", "me/workouts/w/w.draft.txt", "Workout 5 min", "--coach", "Coach Reed"]

        def script(messages, info):
            if not [p for m in messages[-1:] for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BUILD}, tool_call_id=f"b{len(messages)}")])
            return ModelResponse(parts=[TextPart("Done.")])
        with mock.patch.object(worker.engine, "run", side_effect=engine_run):
            job, conv = self.run_turn(uk, script, cid, line="just go")
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(built[0][-2:], ["--max-chars", "2000"])   # recorded at once, within its price
        self.assertIsNone(conv.offer)                                # no Record button
        self.assertEqual(conv.state, "idle")
        self.assertEqual(spend.used(self.conn, uk, today()), 2000)   # reserved, as the Record button does
        audio = conv.lines[-1]["audio"]
        self.assertEqual(media.get(self.conn, uk, audio["id"])[1], b"ID3fake-mp3")
        self.conn.rollback()

    def test_a_new_listeners_first_screen_records_their_first_workout_without_asking(self):
        """The first screen's form said the first workout records as soon as it's written: no Record card for it."""
        from webapp import spend
        uk = self.user()
        first = ("Hey, coach Reed, I'd like a 10-minute full-body workout at home, right now. Nothing's bothering me "
                 "today. About me: call me Sam. I'm new to this, or it's been a long while. At home I have no "
                 "equipment: bodyweight only.")
        cid = self.start(uk, first)
        real = worker.engine.run
        built = []

        def engine_run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if argv[:2] == ["get", "cost"]:
                return worker.engine.Result(0, '{"service": "fish", "usd": 0.03, "pending_design": false}', "")
            if argv and argv[0] == "build":
                if "--lint-only" in argv:
                    return worker.engine.Result(0, "ok\nSends 1,500 characters to the voice service", "")
                built.append(argv)
                os.makedirs(os.path.join(home, "workouts", "w"), exist_ok=True)
                with open(os.path.join(home, "workouts", "w", "Workout 10 min.mp3"), "wb") as f:
                    f.write(b"ID3fake-mp3")
                return worker.engine.Result(0, "built", "")
            return real(root, home, argv, extra_env=extra_env, timeout=timeout)

        BUILD = ["build", "me/workouts/w/w.draft.txt", "Workout 10 min", "--coach", "Coach Reed"]

        def script(messages, info):
            if not [p for m in messages[-1:] for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BUILD}, tool_call_id=f"b{len(messages)}")])
            return ModelResponse(parts=[TextPart("Done.")])
        with mock.patch.object(worker.engine, "run", side_effect=engine_run):
            job, conv = self.run_turn(uk, script, cid, line=first)
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(built[0][-2:], ["--max-chars", "1500"])   # recorded at once, within its price
        self.assertIsNone(conv.offer)
        self.assertEqual(spend.used(self.conn, uk, today()), 1500)
        self.conn.rollback()
        # the next workout in this conversation waits for Record, as every later one does
        built.clear()
        self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "Another one, please.", None))
        self.conn.commit()
        with mock.patch.object(worker.engine, "run", side_effect=engine_run):
            job, conv = self.run_turn(uk, script, cid, line="Another one, please.")
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(built, [])
        self.assertIsNotNone(conv.offer)

    def test_record_without_asking_past_the_allowance_offers_record(self):
        from webapp import keystore, spend
        uk = self.user()
        keystore.set_auto_record(self.conn, uk, True)
        self.assertTrue(spend.reserve(self.conn, uk, today(), spend.daily_cap() - 1000, spend.daily_cap()))
        self.conn.commit()
        cid = self.start(uk)
        real = worker.engine.run
        built = []

        def engine_run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if argv[:2] == ["get", "cost"]:
                return worker.engine.Result(0, '{"service": "fish", "usd": 0.03, "pending_design": false}', "")
            if argv and argv[0] == "build":
                if "--lint-only" in argv:
                    return worker.engine.Result(0, "ok\nSends 900 characters to the voice service", "")
                built.append(argv)
                return worker.engine.Result(0, "built", "")
            return real(root, home, argv, extra_env=extra_env, timeout=timeout)

        BUILD = ["build", "me/workouts/w/w.draft.txt", "Workout 5 min", "--coach", "Coach Reed"]

        def script(messages, info):
            if not [p for m in messages[-1:] for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BUILD}, tool_call_id=f"b{len(messages)}")])
            return ModelResponse(parts=[TextPart("Done.")])
        # another tab reserves the rest of today's allowance while this turn prices the script
        orig = spend.reserve

        def crowded(conn, uk_, day, chars, cap):
            orig(conn, uk_, day, 1000, cap)
            return orig(conn, uk_, day, chars, cap)
        with mock.patch.object(worker.engine, "run", side_effect=engine_run), \
                mock.patch.object(spend, "reserve", side_effect=crowded):
            job, conv = self.run_turn(uk, script, cid, line="just go")
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(built, [])                       # nothing sent
        self.assertEqual(conv.offer["chars"], 900)        # the Record button, which says why
        self.conn.rollback()

    def test_what_a_recording_made_is_kept_when_the_turn_then_fails(self):
        from webapp import clipcache, media
        uk = self.user()
        cid = self.start(uk)
        real = worker.engine.run

        def engine_run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            if argv[:2] == ["get", "cost"]:
                return worker.engine.Result(0, '{"service": "inworld", "usd": 0.03, "pending_design": true}', "")
            if argv and argv[0] == "build":
                if "--max-chars" in argv and argv[argv.index("--max-chars") + 1] == "1":
                    return worker.engine.Result(64, "the script speaks 2,000 characters; at most 1", "")
                if "--lint-only" in argv:
                    return worker.engine.Result(0, "ok", "")
                coach = os.path.join(home, "coaches", "coach-owen-inworld")   # designed in this build
                os.makedirs(coach, exist_ok=True)
                with open(os.path.join(coach, "persona.md"), "w", encoding="utf-8") as f:
                    f.write('+++\nname = "Coach Owen"\n+++\n')
                os.makedirs(os.path.join(home, "workouts", "w"), exist_ok=True)
                with open(os.path.join(home, "workouts", "w", "Workout 5 min.mp3"), "wb") as f:
                    f.write(b"ID3fake-mp3")
                with open(os.path.join(home, "workouts", "w", "Workout 5 min.build.json"), "w", encoding="utf-8") as f:
                    f.write('{"build_id": "b0123"}')
                cache = os.path.join(home, "workouts", ".audio-cache")
                os.makedirs(cache, exist_ok=True)
                with open(os.path.join(cache, "clip.wav"), "wb") as f:
                    f.write(b"RIFFclip")
                return worker.engine.Result(2, "built, a little off plan", "")
            return real(root, home, argv, extra_env=extra_env, timeout=timeout)

        BUILD = ["build", "me/workouts/w/w.draft.txt", "Workout 5 min", "--coach", "Coach Owen"]

        def price(messages, info):
            if not [p for m in messages[-1:] for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BUILD}, tool_call_id=f"b{len(messages)}")])
            return ModelResponse(parts=[TextPart("Ready.")])

        def record_then_fail(messages, info):
            if not [p for m in messages[-1:] for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BUILD}, tool_call_id="r1")])
            raise RuntimeError("the provider went away")
        with mock.patch.object(worker.engine, "run", side_effect=engine_run):
            job, conv = self.run_turn(uk, price, cid, line="just go")
            self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "Yes, record it.", None))
            self.conn.commit()
            job, conv = self.run_turn(uk, record_then_fail, cid, line="Yes, record it.", record=True)
        self.assertEqual(self.state(job)[0], "failed")
        self.assertEqual(conv.state, "failed")
        self.assertIsNone(conv.offer)                       # the recording is spent: no Record button again
        audio = [l["audio"] for l in conv.lines if l.get("audio")]
        self.assertEqual([a["name"] for a in audio], ["Workout 5 min"])
        self.assertEqual(media.get(self.conn, uk, audio[0]["id"])[1], b"ID3fake-mp3")
        self.assertEqual(media.by_build(self.conn, uk), {"b0123": audio[0]})   # the Logs page can play it
        self.conn.rollback()
        self.assertIn("coaches/coach-owen-inworld/persona.md", store.read_all(self.conn, uk))   # the paid design
        self.conn.rollback()
        home = self.homes[-1]
        os.makedirs(home, exist_ok=True)
        self.assertEqual(list(clipcache.load(self.conn, uk, home)), ["clip.wav"])
        self.conn.rollback()

    def test_stop_kills_the_turn_and_says_so(self):
        import threading
        from webapp import agent as agentmod
        uk = self.user()
        cid = self.start(uk)
        started = threading.Event()

        def engine_run(root, home, argv, extra_env={}, timeout=120, cancel=None):
            started.set()
            self.assertTrue(cancel.wait(10))   # the Stop arrives through the heartbeat
            return worker.engine.Result(130, "", "stopped")

        def script(messages, info):
            if not [p for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": ["coverage"]}, tool_call_id="c1")])
            return ModelResponse(parts=[TextPart("never")])
        job = self.enqueue_turn(uk, cid, self.turn_args(cid, "go"))
        jobs.request_stop(self.conn, uk, job)
        self.conn.commit()
        with mock.patch.object(worker, "STOP_POLL", 0.05), \
                mock.patch.object(worker.engine, "run", side_effect=engine_run), \
                mock.patch.object(providers, "model_for", return_value=FunctionModel(script)), \
                mock.patch.object(agentmod, "prefetch", return_value=None):
            self.assertTrue(self.run_one())
        conv = conversations.load(self.conn, uk, cid)
        self.conn.rollback()
        self.assertEqual(conv.state, "failed")
        self.assertEqual(conv.lines[-1]["text"], "Stopped. Send a message when you want to carry on.")

    def test_turn_needs_a_model_key(self):
        uk = self.user(key=False)
        keystore.put(self.conn, uk, "fish", "sk-abcdefghijklmnop")   # a voice key is no model key
        self.conn.commit()
        cid = self.start(uk)
        job, conv = self.run_turn(uk, lambda m, i: self.fail("the model ran"), cid, line="go")
        self.assertEqual(self.state(job), ("failed", "add a language-model key in Settings"))
        self.model_for.assert_not_called()
        self.assertEqual(conv.state, "failed")
        self.assertEqual(conv.lines[-1], {"role": "agent", "text": "That didn't work: add a language-model key in Settings"})
        self.conn.rollback()

    def test_turn_maps_provider_errors(self):
        uk = self.user()
        cid = self.start(uk)

        def refuse(messages, info):
            raise ModelHTTPError(status_code=401, model_name="claude-test",
                                 body={"error": f"invalid x-api-key {MODEL_KEY}"})
        with mock.patch("sys.stderr") as err:
            job, conv = self.run_turn(uk, refuse, cid, line="go")
        state, error = self.state(job)
        self.assertEqual(state, "failed")
        self.assertIn("Claude refused the key", error)
        self.assertEqual(conv.state, "failed")
        self.assertIn("Claude refused the key", conv.lines[-1]["text"])
        stored = repr((error, conv.lines, jobs.result(self.conn, uk, job), err.mock_calls))
        self.assertNotIn(MODEL_KEY, stored)
        self.assertNotIn("x-api-key", stored)
        self.conn.rollback()

    def test_turn_stops_at_usage_limit(self):
        uk = self.user()
        cid = self.start(uk)
        _, before = self.run_turn(uk, lambda m, i: ModelResponse(parts=[TextPart("Hello.")]), cid, line="hi")
        self.assertEqual(before.state, "idle")
        self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "and again", None))
        self.conn.commit()
        n = iter(range(1000))

        def forever(messages, info):
            return ModelResponse(parts=[ToolCallPart("run", {"args": ["get", "coach"]}, tool_call_id=f"c{next(n)}")])
        from webapp import agent
        with mock.patch.object(agent, "LIMITS", UsageLimits(request_limit=3)), \
                mock.patch.object(worker.engine, "run", return_value=worker.engine.Result(0, "Coach Andy\n", "")):
            job, conv = self.run_turn(uk, forever, cid, line="and again")
        message = "this turn ran too long; try again with less to do"
        self.assertEqual(self.state(job), ("failed", message))
        self.assertEqual(conv.state, "failed")
        self.assertEqual(conv.history, before.history)
        self.assertEqual(conv.lines[-2:], [{"role": "user", "text": "and again"},
                                           {"role": "agent", "text": f"That didn't work: {message}"}])
        self.conn.rollback()

    def test_model_key_never_in_engine_env(self):
        uk = self.user()
        keystore.put(self.conn, uk, "fish", "sk-abcdefghijklmnop")
        self.conn.commit()
        cid = self.start(uk)
        seen = []
        real = worker.engine.run

        def record(root, home, argv, extra_env={}, timeout=120, cancel=None):
            seen.append((argv[0], dict(extra_env)))
            return real(root, home, argv, extra_env=extra_env, timeout=timeout)

        def script(messages, info):
            names = returned(messages)
            if not names:
                return ModelResponse(parts=[ToolCallPart("run", {"args": ["get", "coach"]}, tool_call_id="c1")])
            if names == ["run"]:
                return ModelResponse(parts=[ToolCallPart("run", {"args": BRIEF_ARGV}, tool_call_id="b1")])
            return ModelResponse(parts=[TextPart("ok")])
        with mock.patch.object(worker.engine, "run", side_effect=record):
            job, conv = self.run_turn(uk, script, cid, line="go")
        self.assertEqual(self.state(job), ("done", None))
        # step 1 up front (5 runs and the route), then the model's two; and the story writer, which starts as the brief
        # is saved (its content plan and feeds), when it gets that far before the turn ends
        self.assertGreaterEqual(len(seen), 2 + 6)
        from webapp.agent import tools as agent_tools
        for command, env in seen:   # the voice key, and the listener's clock (TZ): never the model's key
            # and no key at all for a command that fetches pages (0.76.0)
            want = {} if command in agent_tools.FETCHERS else {"FISH_AUDIO_API_KEY": "sk-abcdefghijklmnop"}
            self.assertIn("TZ", env, command)
            self.assertEqual({k: v for k, v in env.items() if k != "TZ"}, want, command)
            self.assertRegex(env.get("TZ", ""), r"^LCL[+-]\d+(:\d\d)?$")
            self.assertNotIn(MODEL_KEY, env.values())
        self.conn.rollback()

    def test_conversation_not_working_is_left_alone(self):
        uk = self.user()
        cid = self.start(uk)
        _, before = self.run_turn(uk, lambda m, i: ModelResponse(parts=[TextPart("Hello.")]), cid, line="hi")
        job, conv = self.run_turn(uk, lambda m, i: self.fail("the model ran"), cid, line="again")
        self.assertEqual(self.state(job), ("failed", "the conversation moved on"))
        self.assertEqual((conv.state, conv.version, conv.lines), (before.state, before.version, before.lines))
        _, other = self.make_user()
        job = jobs.enqueue(self.conn, other, "turn", self.turn_args(cid, "mine now"))
        self.run_one()
        self.assertEqual(self.state(job), ("failed", "the conversation moved on"))
        self.conn.rollback()

    def test_a_turn_that_isnt_the_conversations_job_is_left_alone(self):
        uk = self.user()
        cid = self.start(uk)
        job = jobs.enqueue(self.conn, uk, "turn", self.turn_args(cid, line="go"))
        other = jobs.enqueue(self.conn, uk, "brief", {})
        conversations.set_job(self.conn, uk, cid, other)   # still working, but on another job's turn
        self.conn.commit()
        before = conversations.load(self.conn, uk, cid)
        self.conn.commit()
        with mock.patch.object(providers, "model_for", side_effect=AssertionError("the model ran")):
            self.run_one()
        self.assertEqual(self.state(job), ("failed", "the conversation moved on"))
        conv = conversations.load(self.conn, uk, cid)
        self.assertEqual((conv.state, conv.version, conv.lines), ("working", before.version, before.lines))
        self.conn.rollback()

    def test_turn_stops_past_its_time(self):
        import asyncio
        from webapp import agent
        uk = self.user()
        cid = self.start(uk)
        calls = []

        async def slow(messages, info):
            calls.append(1)
            await asyncio.sleep(2)
            return ModelResponse(parts=[TextPart("Hello.")])
        with mock.patch.object(agent, "TURN_SECONDS", 0.2):
            job, conv = self.run_turn(uk, FunctionModel(slow), cid, line="go")
        message = "this turn ran too long; try again with less to do"
        self.assertEqual(self.state(job), ("failed", message))
        self.assertEqual(conv.state, "failed")
        self.assertEqual(conv.lines[-1], {"role": "agent", "text": f"That didn't work: {message}"})
        self.assertEqual(len(calls), 1)   # nothing retried
        self.conn.rollback()

    def test_bad_turn_args_fail_the_conversation(self):
        uk = self.user()
        bad = [{"now": "08:00"}, {"now": f"{today()} Wednesday 08:00\n"}, {"today": "2001-01-01"},
               {"line": None}, {"line": "go", "answer": {"tool_call_id": "a1", "values": {}}},
               {"answer": {"tool_call_id": "a1"}, "line": None}, {"line": ""}]
        for over in bad:
            with self.subTest(over=over):
                cid = self.start(uk)
                args = dict({"line": "go"}, **over)
                job, conv = self.run_turn(uk, lambda m, i: self.fail("the model ran"), cid, **args)
                state, error = self.state(job)
                self.assertEqual(state, "failed")
                self.assertTrue(error.startswith("invalid request: "), error)
                self.assertEqual(conv.state, "failed")
        job = jobs.enqueue(self.conn, uk, "turn", {"conversation_id": "1"})
        self.run_one()
        self.assertTrue(self.state(job)[1].startswith("invalid request: "))
        self.conn.rollback()

    def test_lost_heartbeat_fails_the_conversation(self):
        import time
        uk = self.user()
        cid = self.start(uk)
        before = store.read_all(self.conn, uk)
        self.conn.commit()

        def slow(messages, info):
            time.sleep(0.3)
            return ModelResponse(parts=[TextPart("Hello.")])
        with mock.patch.object(worker, "HEARTBEAT_EVERY", 0.05), \
                mock.patch.object(jobs, "heartbeat", return_value=False), mock.patch("sys.stderr"):
            job, conv = self.run_turn(uk, slow, cid, line="hi")
        self.assertEqual(self.state(job), ("failed", "interrupted"))
        self.assertEqual(conv.state, "failed")
        self.assertIsNone(conv.history)
        self.assertEqual(conv.lines[-1], {"role": "agent", "text": "That didn't work: interrupted"})
        self.assertEqual(store.read_all(self.conn, uk), before)
        self.conn.rollback()

    def test_model_client_failure_goes_through_explain(self):
        uk = self.user()
        cid = self.start(uk)
        job = self.enqueue_turn(uk, cid, self.turn_args(cid, "go"))
        with mock.patch.object(providers, "model_for", side_effect=ConnectionError(f"bad {MODEL_KEY}")), \
                mock.patch("sys.stderr") as err:
            self.run_one()
        conv = conversations.load(self.conn, uk, cid)
        message = "Claude didn't answer. Try again in a minute."
        self.assertEqual(self.state(job), ("failed", message))
        self.assertEqual((conv.state, conv.lines[-1]["text"]), ("failed", f"That didn't work: {message}"))
        self.assertNotIn(MODEL_KEY, repr((conv.lines, err.mock_calls)))
        self.conn.rollback()

    def lost_after_handler(self, uk, cid, after, **patches):
        """Run a turn whose handler finishes, then `after(ctx)`; (job, conversation)."""
        real = worker.HANDLERS["turn"]

        def handler(ctx):
            out = real(ctx)
            after(ctx)
            return out
        with mock.patch.dict(worker.HANDLERS, {"turn": handler}), mock.patch("sys.stderr"):
            return self.run_turn(uk, lambda m, i: ModelResponse(parts=[ToolCallPart(
                "run", {"args": BRIEF_ARGV}, tool_call_id="b1")]) if not returned(m) else ModelResponse(
                parts=[TextPart("ok")]), cid, line="go")

    def check_lost(self, uk, job, conv, before, error):
        self.assertEqual(self.state(job), ("failed", error))
        self.assertEqual(conv.state, "failed")
        self.assertIsNone(conv.history)
        self.assertEqual(conv.lines[-1], {"role": "agent", "text": f"That didn't work: {error}"})
        self.assertEqual(store.read_all(self.conn, uk), before)

    def test_conversation_version_moved_before_completion(self):
        uk = self.user()
        cid = self.start(uk)
        before = store.read_all(self.conn, uk)
        self.conn.commit()

        def bump(ctx):
            self.conn.execute("update conversations set version = version + 1 where id = %s", (cid,))
            self.conn.commit()
        job, conv = self.lost_after_handler(uk, cid, bump)
        self.check_lost(uk, job, conv, before, "the job stopped unexpectedly")
        self.conn.rollback()

    def test_job_reaped_before_completion_fails_the_conversation(self):
        uk = self.user()
        cid = self.start(uk)
        before = store.read_all(self.conn, uk)
        self.conn.commit()

        def reap(ctx):
            self.conn.execute("update jobs set state = 'failed', error = 'interrupted', "
                              "finished_at = now() where id = %s", (ctx.job_id,))
            self.conn.commit()
        job, conv = self.lost_after_handler(uk, cid, reap)
        self.check_lost(uk, job, conv, before, "interrupted")
        self.conn.rollback()

    def test_write_back_failure_fails_the_conversation(self):
        uk = self.user()
        cid = self.start(uk)
        before = store.read_all(self.conn, uk)
        self.conn.commit()
        with mock.patch.object(worker.store, "write_back", side_effect=RuntimeError("disk")):
            job, conv = self.lost_after_handler(uk, cid, lambda ctx: None)
        self.check_lost(uk, job, conv, before, "the job stopped unexpectedly")
        self.conn.rollback()

    def test_late_loss_of_an_old_job_leaves_a_newer_turn_alone(self):
        uk = self.user()
        cid = self.start(uk)
        newer = []

        def reaped_then_replaced(ctx):
            self.conn.execute("update jobs set state = 'failed', error = 'interrupted', "
                              "finished_at = now() where id = %s", (ctx.job_id,))
            newer.append(jobs.enqueue(self.conn, uk, "turn", self.turn_args(cid, "again")))
            conversations.set_job(self.conn, uk, cid, newer[0])   # healed and begun anew meanwhile
            self.conn.commit()
        job, conv = self.lost_after_handler(uk, cid, reaped_then_replaced)
        self.assertEqual(self.state(job), ("failed", "interrupted"))
        self.assertEqual((conv.state, conv.job_id), ("working", newer[0]))
        self.assertEqual(conv.lines, [{"role": "user", "text": "a 20-minute strength workout"}])
        self.conn.rollback()

    def test_a_stop_of_an_old_job_leaves_a_newer_turn_alone(self):
        uk = self.user()
        cid = self.start(uk)
        old = jobs.enqueue(self.conn, uk, "turn", self.turn_args(cid, line="go", now="08:00"))
        conversations.set_job(self.conn, uk, cid, None)   # not this job's turn
        self.conn.commit()
        with mock.patch.object(providers, "model_for", side_effect=AssertionError("the model ran")):
            self.run_one()
        self.assertEqual(self.state(old)[0], "failed")
        conv = conversations.load(self.conn, uk, cid)
        self.assertEqual(conv.state, "working")
        self.conn.rollback()

    def test_an_answer_fails_the_conversation_plainly(self):
        uk = self.user()
        cid = self.start(uk)
        _, before = self.run_turn(uk, lambda m, i: ModelResponse(parts=[TextPart("Hello.")]), cid, line="hi")
        self.assertTrue(conversations.begin_turn(self.conn, uk, cid, "x", None))
        self.conn.commit()
        job, conv = self.run_turn(uk, lambda m, i: self.fail("the model ran"), cid,
                                  answer={"tool_call_id": "gone", "values": {"q1": ["Nothing new"]}})
        state, error = self.state(job)
        self.assertEqual(state, "failed")
        self.assertEqual(error, worker.ANSWER_NOT_OPEN)
        self.assertEqual(conv.state, "failed")
        self.assertEqual(conv.history, before.history)
        self.conn.rollback()


class Lanes(JobsCase):
    def test_enrichment_runs_beside_a_turn_and_one_at_a_time(self):
        _, uk = self.make_user()
        turn = jobs.enqueue(self.conn, uk, "turn", {})
        first = jobs.enqueue(self.conn, uk, "enrich", {})
        second = jobs.enqueue(self.conn, uk, "enrich", {})
        self.assertEqual(jobs.claim(self.conn).id, turn)                # the main lane never takes an enrich job
        self.assertEqual(jobs.claim(self.conn, "enrich").id, first)     # beside the running turn
        self.assertIsNone(jobs.claim(self.conn, "enrich"))              # but one enrichment at a time
        self.assertIsNone(jobs.claim(self.conn))
        with self.assertRaises(ValueError):
            jobs.claim(self.conn, "side")
        self.conn.execute("update jobs set state = 'done' where id = %s", (first,))
        self.conn.commit()
        self.assertEqual(jobs.claim(self.conn, "enrich").id, second)

    def test_the_unique_indexes_hold_one_running_job_a_lane(self):
        _, uk = self.make_user()
        a, b = jobs.enqueue(self.conn, uk, "enrich", {}), jobs.enqueue(self.conn, uk, "enrich", {})
        self.conn.execute("update jobs set state = 'running' where id = %s", (a,))
        self.conn.commit()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute("update jobs set state = 'running' where id = %s", (b,))
        self.conn.rollback()


class Enrich(JobsCase):
    TEXT = "Loved the bike story, and that felt too easy"

    def user(self, key=True):
        from webtests.test_workouts import listener_files
        _, uk = self.make_user()
        self.assertEqual(store.write_back(self.conn, uk, listener_files(), {}), [])
        if key:
            keystore.put(self.conn, uk, "anthropic", MODEL_KEY)
        self.conn.commit()
        return uk

    def run_enrich(self, uk, output, text=TEXT):
        job = jobs.enqueue(self.conn, uk, "enrich", {"ref": "ccc333", "text": text, "today": today()})
        seen = []

        def model(messages, info):
            seen.append([p.content for m in messages for p in m.parts if hasattr(p, "content")])
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, output)])
        with mock.patch.object(providers, "model_for", return_value=FunctionModel(model)):
            self.assertTrue(worker.run_one(self.conn, self.settings, connect=self.connect, lane="enrich"))
        return job, seen

    def test_feedback_becomes_evidence_and_a_summary(self):
        uk = self.user()
        out = {"signals": [{"kind": "topic", "name": "Tour de France | history", "weight": 2, "parent": "cycling"},
                           {"kind": "effort", "name": "effort", "weight": 1}],
               "summary": "Noted: more cycling stories, and a little harder next time."}
        job, seen = self.run_enrich(uk, out)
        self.assertEqual(self.state(job), ("done", None))
        self.assertEqual(jobs.result(self.conn, uk, job), {"summary": out["summary"], "signals": 2})
        self.assertIn(self.TEXT, "\n".join(map(str, seen[0])))           # the model read the feedback
        self.assertIn('"build_id": "ccc333"', "\n".join(map(str, seen[0])))   # and the workout's context
        files = store.read_all(self.conn, uk)
        rows = [json.loads(x) for x in files["workouts/research/interests.jsonl"][1].decode().splitlines()]
        self.assertEqual([(r["kind"], r["name"], r["weight"], r["source"], r["build"]) for r in rows],
                         [("topic", "Tour de France / history", 2.0, "feedback", "ccc333"),
                          ("effort", "effort", 1.0, "feedback", "ccc333")])
        self.assertIn("## Learned from you", files["content.md"][1].decode())
        self.assertIn("aiming a little harder", files["training.md"][1].decode())
        self.conn.rollback()

    def test_nothing_to_learn_writes_nothing(self):
        uk = self.user()
        before = store.read_all(self.conn, uk)
        job, _ = self.run_enrich(uk, {"signals": [], "summary": ""}, text="ok")
        self.assertEqual((self.state(job), jobs.result(self.conn, uk, job)), (("done", None), {"summary": "", "signals": 0}))
        self.assertEqual(store.read_all(self.conn, uk), before)
        self.conn.rollback()

    def test_without_a_writer_key_there_is_nothing_to_note(self):
        uk = self.user(key=False)
        job = jobs.enqueue(self.conn, uk, "enrich", {"ref": "ccc333", "text": self.TEXT, "today": today()})
        with mock.patch.object(providers, "model_for") as model_for:
            self.assertTrue(worker.run_one(self.conn, self.settings, connect=self.connect, lane="enrich"))
        model_for.assert_not_called()
        self.assertEqual(jobs.result(self.conn, uk, job), {"summary": "", "signals": 0})
        self.conn.rollback()

    def test_bad_args_fail(self):
        uk = self.user()
        for args in ({"ref": "../x", "text": "hi", "today": today()}, {"ref": "ccc333", "text": " ", "today": today()},
                     {"ref": "ccc333", "text": "hi", "today": "soon"}):
            job = jobs.enqueue(self.conn, uk, "enrich", args)
            worker.run_one(self.conn, self.settings, connect=self.connect, lane="enrich")
            self.assertEqual(self.state(job)[0], "failed", args)
        self.conn.rollback()


class Clock(unittest.TestCase):
    def test_the_engine_runs_on_the_listener_s_clock(self):
        utc = datetime.datetime(2026, 11, 1, 18, 16)
        self.assertEqual(worker.listener_zone("2026-11-01 Sunday 13:16", utc), "LCL+5")      # Philadelphia
        self.assertEqual(worker.listener_zone("2026-11-01 Sunday 23:47", utc), "LCL-5:30")   # Mumbai
        self.assertEqual(worker.listener_zone("2026-11-02 Monday 03:16", utc), "LCL-9")      # Tokyo, the next day
        for bad in ("soon", "2026-11-01 13:16", "2026-11-05 Thursday 13:16", None):
            self.assertIsNone(worker.listener_zone(bad, utc), bad)


class Resilience(JobsCase):
    """0.76.0: what a job made survives a dropped connection, events never commit the job's own work, a deploy stops a
    job cleanly, and the main lane outlives an unexpected error."""

    def handler(self, fn):
        patch = mock.patch.dict(worker.HANDLERS, {"brief": fn})
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_job_whose_connection_dropped_is_still_finished_and_saved(self):
        _, uk = self.seeded_user()

        def dropped(ctx):
            ctx.conn.close()   # the database closed it mid-job, as it does now and then
            ctx.retrying(lambda: (store.put(ctx.conn, ctx.uk, "notes/made.md", b"paid for"), ctx.conn.commit()))
            ctx.save({}, {})
            return {"ok": True}
        self.handler(dropped)
        main = self.connect()
        self.addCleanup(main.close)
        job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
        with mock.patch("sys.stderr"):
            self.assertTrue(worker.run_one(main, self.settings, connect=self.connect))
        self.assertEqual(self.state(job), ("done", None))   # done now, not reaped two minutes on
        self.assertEqual(store.read_one(self.conn, uk, "notes/made.md")[1], b"paid for")
        self.conn.rollback()

    def test_a_progress_line_never_commits_the_job_s_own_work(self):
        _, uk = self.seeded_user()

        def half_done(ctx):
            store.put(ctx.conn, ctx.uk, "notes/half.md", b"not yet")   # not committed
            ctx.say("step", text="Working", failed=False)
            ctx.conn.rollback()
            return {"ok": True}
        self.handler(half_done)
        job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
        self.assertTrue(self.run_one())
        self.assertIsNone(store.read_one(self.conn, uk, "notes/half.md"))
        self.assertIn("step", [b["stage"] for _, b in jobs.events(self.conn, uk, job)])
        self.conn.rollback()

    def test_a_deploy_stops_a_long_job_cleanly(self):
        _, uk = self.make_user()

        def long(ctx):
            ctx.cancel.wait(10)
            raise worker.JobFailed(ctx.why_stopped())
        self.handler(long)
        stopping = threading.Event()
        stopping.set()   # SIGTERM came in while it ran
        job = jobs.enqueue(self.conn, uk, "brief", self.brief_args())
        with mock.patch("sys.stderr"), mock.patch.object(worker, "DRAIN_SECONDS", 0.2), \
                mock.patch.object(worker, "STOP_POLL", 0.05):
            began = time.monotonic()
            self.assertTrue(worker.run_one(self.conn, self.settings, connect=self.connect, stopping=stopping))
        self.assertLess(time.monotonic() - began, 5)
        self.assertEqual(self.state(job), ("failed", worker.RESTARTED))
        self.conn.rollback()

    def test_the_main_lane_outlives_an_unexpected_error(self):
        stopping = threading.Event()
        runs = []

        def serve(settings, stop, lane="main"):
            runs.append(lane)
            if len(runs) == 1:
                raise KeyError("a bug")
            stop.set()
        with mock.patch.object(worker, "serve", side_effect=serve), mock.patch.object(worker, "RECONNECT_WAIT", 0), \
                mock.patch("sys.stderr"):
            worker._lane(self.settings, stopping, "main")
        self.assertEqual(runs, ["main", "main"])
