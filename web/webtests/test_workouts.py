"""The Logs page's calls (webapp/workouts.py), against the real engine in a temporary folder, no database;
and, with one, the routes."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder, store, workouts  # noqa: E402
from webapp.routes import state as routestate  # noqa: E402
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

    def test_all_is_never_a_workout(self):
        files = listener_files()
        for ref in ("all", "ALL", "All"):
            for call, args in ((workouts.delete, (ref,)), (workouts.rate, (ref, "positive")),
                               (workouts.add_feedback, (ref, "fine")), (workouts.script, (ref,))):
                with self.subTest(ref=ref, call=call.__name__), self.assertRaises(workouts.Refused):
                    call(ROOT, files, *args)
        self.assertEqual(len(workouts.listing(ROOT, files)), 1)

    def test_feedback_that_looks_like_an_option_is_saved_as_words(self):
        files = listener_files()
        for text in ("--help", "-_- too hard"):
            changed = workouts.add_feedback(ROOT, files, "ccc333", text)
            files.update(changed)
        self.assertEqual(workouts.listing(ROOT, files)[0]["feedback"], ["--help", "-_- too hard"])

    def test_an_engine_crash_never_reaches_the_page(self):
        from unittest import mock
        crash = workouts.engine.Result(70, "", "Traceback (most recent call last):\nKeyError: 'my knee'\n")
        with mock.patch.object(workouts.engine, "run", return_value=crash):
            with self.assertRaises(workouts.Refused) as got:
                workouts.listing(ROOT, listener_files())
        self.assertEqual((str(got.exception), got.exception.kind), (workouts.DIDNT_WORK, "failed"))

    def test_an_unknown_workout_is_not_found(self):
        with self.assertRaises(workouts.Refused) as got:
            workouts.script(ROOT, listener_files(), "zzz999")
        self.assertEqual(got.exception.kind, "not_found")

    def test_a_listener_without_a_log_has_no_workouts(self):
        self.assertEqual(workouts.listing(ROOT, {}), [])

    def test_what_the_calls_leave_out_changes_nothing(self):
        """The Logs calls read only workouts.needed's files (0.77.0): the same answers and changes as from all."""
        full = listener_files()
        full.update({"coaches/coach-x/persona.md": b"+++\nschema = 5\n+++\n", "coaches/coach-x/sample.mp3": b"ID3" * 9,
                     "workouts/research/reserve/piece.md": b"a piece", "workouts/research/daily/2026-10-30.md": b"d",
                     "workouts/research/videos/v.md": b"v", "workouts/research/puzzles/p.md": b"p"})
        some = {p: b for p, b in full.items() if workouts.needed(p)}
        self.assertFalse(any(p.startswith(("coaches/", "workouts/research/reserve/")) for p in some))
        self.assertIn("log.md", some)
        self.assertEqual(workouts.listing(ROOT, some), workouts.listing(ROOT, full))
        self.assertEqual(workouts.script(ROOT, some, "ccc333"), workouts.script(ROOT, full, "ccc333"))
        for call, args in ((workouts.rate, ("ccc333", "positive")), (workouts.add_feedback, ("ccc333", "hard")),
                           (workouts.delete, ("ccc333",))):
            with self.subTest(call=call.__name__):
                self.assertEqual(call(ROOT, some, *args), call(ROOT, full, *args))


class Routes(test_api.ApiCase):
    def test_the_logs_routes(self):
        from webapp import keystore
        _, uk = self.signed_in()
        keystore.put(self.conn, uk, "anthropic", "sk-ant-test-model-key-0123456789")   # a writer: feedback is enriched
        store.write_back(self.conn, uk, listener_files(), {})
        self.conn.commit()
        rows = self.client.get("/api/workouts").json()["workouts"]
        self.assertEqual(rows[0]["build_id"], "ccc333")
        self.assertIn("bike", self.client.get("/api/workouts/ccc333/script").json()["script"])
        r = self.client.put("/api/workouts/ccc333/rating", json={"rating": "negative"}, headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        r = self.client.post("/api/workouts/ccc333/feedback", json={"text": "too long"}, headers=self.origin())
        self.assertEqual(r.status_code, 202, r.text)
        job = r.json()["job_id"]   # what it teaches is worked out in enrichment's own lane
        self.assertEqual(self.conn.execute("select kind, state from jobs where id = %s", (job,)).fetchone(),
                         ("enrich", "queued"))
        self.conn.rollback()
        for n in range(2, 5):   # feedback keeps being saved; past the queued cap no more enrich jobs wait
            r = self.client.post("/api/workouts/ccc333/feedback", json={"text": f"note {n}"}, headers=self.origin())
            self.assertEqual(r.status_code, 202, r.text)
        self.assertIsNone(r.json()["job_id"])
        self.assertEqual(self.conn.execute("select count(*) from jobs where kind = 'enrich' and state = 'queued'")
                         .fetchone()[0], routestate.MAX_QUEUED)
        self.conn.rollback()
        row = self.client.get("/api/workouts").json()["workouts"][0]
        self.assertEqual((row["rating"], row["feedback"]), ("negative", ["too long", "note 2", "note 3", "note 4"]))
        self.assertEqual(self.client.put("/api/workouts/ccc333/rating", json={"rating": "great"},
                                         headers=self.origin()).status_code, 422)
        self.assertEqual(self.client.get("/api/workouts/nope99/script").status_code, 404)
        r = self.client.delete("/api/workouts/ccc333", headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(self.client.get("/api/workouts").json()["workouts"], [])
        self.conn.rollback()
        self.assertNotIn(f"{STEM}/Workout.txt", store.read_all(self.conn, uk))

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

    def test_a_workout_carries_its_mp3_while_it_is_kept(self):
        from webapp import media
        _, uk = self.signed_in()
        store.write_back(self.conn, uk, listener_files(), {})
        media.put(self.conn, uk, "Workout", b"ID3old", build_id="ccc333")
        newest = media.put(self.conn, uk, "Workout", b"ID3new", build_id="ccc333")
        media.put(self.conn, uk, "Coach Reed's voice", b"ID3sample")   # no build: never on a workout
        self.conn.commit()
        row = self.client.get("/api/workouts").json()["workouts"][0]
        self.assertEqual(row["audio"], newest)
        self.assertIsNone(newest["expires_at"])   # a workout's MP3 has no expiry
        for build in ("ddd1", "ddd2", "ddd3"):   # three newer workouts replace it
            media.put(self.conn, uk, "Workout", b"ID3later", build_id=build)
        self.conn.commit()
        self.assertNotIn("audio", self.client.get("/api/workouts").json()["workouts"][0])

    def test_the_listing_is_kept_until_a_file_changes(self):
        from unittest import mock
        _, uk = self.signed_in()
        store.write_back(self.conn, uk, listener_files(), {})
        self.conn.commit()
        real, runs = workouts._run, []

        def counting(root, files, argv):
            runs.append((argv, set(files)))
            return real(root, files, argv)
        with mock.patch.object(workouts, "_run", counting):
            first = self.client.get("/api/workouts").json()
            self.assertEqual(self.client.get("/api/workouts").json(), first)
            self.assertEqual(len(runs), 1)
            self.assertFalse(any(p.startswith("coaches/") for p in runs[0][1]))
            r = self.client.put("/api/workouts/ccc333/rating", json={"rating": "positive"}, headers=self.origin())
            self.assertEqual(r.status_code, 204, r.text)
            self.assertEqual(self.client.get("/api/workouts").json()["workouts"][0]["rating"], "positive")
        self.assertEqual([a[0] for a, _ in runs], ["workouts", "workouts", "workouts"])

    def test_the_logs_routes_need_a_session_and_same_origin(self):
        self.assertEqual(self.client.get("/api/workouts").status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.delete("/api/workouts/ccc333").status_code, 403)


if __name__ == "__main__":
    unittest.main()
