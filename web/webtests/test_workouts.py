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
    def test_list_script_rate_feedback_delete(self):
        files = listener_files()
        rows = workouts.listing(ROOT, files)
        self.assertEqual([(r["build_id"], r["has_script"], r["rating"]) for r in rows], [("ccc333", True, None)])
        self.assertIn("Fifteen minutes", workouts.script(ROOT, files, "ccc333"))

        changed = workouts.rate(ROOT, files, "ccc333", "positive")
        self.assertEqual(set(changed), {"log.md"})
        files.update(changed)
        changed = workouts.add_feedback(ROOT, files, "1", "  loved   the climbs ")
        files.update(changed)
        row = workouts.listing(ROOT, files)[0]
        self.assertEqual((row["rating"], row["feedback"]), ("positive", ["loved the climbs"]))

        changed = workouts.delete(ROOT, files, "ccc333")
        self.assertIn("log.md", changed)
        self.assertIsNone(changed[f"{STEM}/Workout.txt"])
        for path, body in changed.items():
            if body is None:
                files.pop(path)
            else:
                files[path] = body
        self.assertEqual(workouts.listing(ROOT, files), [])

    def test_refusals(self):
        files = listener_files()
        for call, args in ((workouts.script, ("zzz999",)), (workouts.rate, ("ccc333", "great")),
                           (workouts.add_feedback, ("ccc333", "   ")), (workouts.delete, ("../x",))):
            with self.subTest(call=call.__name__), self.assertRaises(workouts.Refused):
                call(ROOT, files, *args)

    def test_a_listener_without_a_log_has_no_workouts(self):
        self.assertEqual(workouts.listing(ROOT, {}), [])


class Routes(test_api.ApiCase):
    def test_the_logs_routes(self):
        _, uk = self.signed_in()
        store.write_back(self.conn, uk, listener_files(), {})
        self.conn.commit()
        rows = self.client.get("/api/workouts").json()["workouts"]
        self.assertEqual(rows[0]["build_id"], "ccc333")
        self.assertIn("bike", self.client.get("/api/workouts/ccc333/script").json()["script"])
        r = self.client.put("/api/workouts/ccc333/rating", json={"rating": "negative"}, headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        r = self.client.post("/api/workouts/ccc333/feedback", json={"text": "too long"}, headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        row = self.client.get("/api/workouts").json()["workouts"][0]
        self.assertEqual((row["rating"], row["feedback"]), ("negative", ["too long"]))
        self.assertEqual(self.client.put("/api/workouts/ccc333/rating", json={"rating": "great"},
                                         headers=self.origin()).status_code, 422)
        self.assertEqual(self.client.get("/api/workouts/nope99/script").status_code, 404)
        r = self.client.delete("/api/workouts/ccc333", headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(self.client.get("/api/workouts").json()["workouts"], [])
        self.conn.rollback()
        self.assertNotIn(f"{STEM}/Workout.txt", store.read_all(self.conn, uk))

    def test_the_logs_routes_need_a_session_and_same_origin(self):
        self.assertEqual(self.client.get("/api/workouts").status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.delete("/api/workouts/ccc333").status_code, 403)


if __name__ == "__main__":
    unittest.main()
