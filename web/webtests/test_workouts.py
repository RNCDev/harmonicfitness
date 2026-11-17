"""The Logs page's calls (webapp/workouts.py), against the real engine in a temporary folder, no database;
and, with one, the routes."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder, store, workouts  # noqa: E402
from webtests import test_api  # noqa: E402
from webtests.test_api import ROOT  # noqa: E402

LINE = "- 2026-10-30 | 15 min | home | Coach Reed | easy spin | Sixers | format: intervals | build: ccc333\n"
STEM = "workouts/2026-10-30-conditioning-15"


def listener_files() -> dict[str, bytes]:
    files = dict(folder.seed(ROOT))
    log = files["log.md"].decode().replace("## Sessions\n", "## Sessions\n\n" + LINE, 1)
    files["log.md"] = log.encode()
    files[f"{STEM}/Workout.build.json"] = json.dumps({"build_id": "ccc333",
                                                      "draft": "/tmp/old/me/x.draft.txt"}).encode()
    files[f"{STEM}/Workout.txt"] = b"Evening. Fifteen minutes on the bike.\n"
    files[f"{STEM}/2026-10-30-conditioning-15.draft.txt"] = b"movements: easy spin\n"
    return files


class Calls(unittest.TestCase):
    def test_refusals_and_all_is_never_a_workout(self):
        files = listener_files()
        for call, args in ((workouts.script, ("zzz999",)), (workouts.rate, ("ccc333", "great")),
                           (workouts.add_feedback, ("ccc333", "   ")), (workouts.delete, ("../x",))):
            with self.subTest(call=call.__name__), self.assertRaises(workouts.Refused):
                call(ROOT, files, *args)
        for ref in ("all", "ALL", "All"):
            for call, args in ((workouts.delete, (ref,)), (workouts.rate, (ref, "positive")),
                               (workouts.add_feedback, (ref, "fine")), (workouts.script, (ref,))):
                with self.subTest(ref=ref, call=call.__name__), self.assertRaises(workouts.Refused):
                    call(ROOT, files, *args)
        self.assertEqual(len(workouts.listing(ROOT, files)), 1)

    def test_an_engine_crash_never_reaches_the_page(self):
        from unittest import mock
        crash = workouts.engine.Result(70, "", "Traceback (most recent call last):\nKeyError: 'my knee'\n")
        with mock.patch.object(workouts.engine, "run", return_value=crash):
            with self.assertRaises(workouts.Refused) as got:
                workouts.listing(ROOT, listener_files())
        self.assertEqual((str(got.exception), got.exception.kind), (workouts.DIDNT_WORK, "failed"))


class Routes(test_api.ApiCase):
    def test_feedback_without_a_writer_key_queues_nothing(self):
        _, uk = self.signed_in()
        from webapp import keystore
        for service in list(keystore.listing(self.conn, uk)):
            keystore.delete(self.conn, uk, service)
        store.write_back(self.conn, uk, listener_files(), {})
        self.conn.commit()
        r = self.client.post("/api/workouts/ccc333/feedback", json={"text": "too long"}, headers=self.origin())
        self.assertEqual((r.status_code, r.json()), (202, {"job_id": None}))
        self.assertEqual(self.conn.execute("select count(*) from jobs where kind = 'enrich'").fetchone()[0], 0)
        self.conn.rollback()

    def test_the_logs_routes_need_a_session_and_same_origin(self):
        self.assertEqual(self.client.get("/api/workouts").status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.delete("/api/workouts/ccc333").status_code, 403)


if __name__ == "__main__":
    unittest.main()
