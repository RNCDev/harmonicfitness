"""GET /api/start's shaping (pure: no database) and, with one, the route itself."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder, start, worker  # noqa: E402
from webtests import test_api  # noqa: E402
from webtests.test_api import ROOT  # noqa: E402

GOALS, PRESETS = worker.engine_lists(ROOT)
SERVICES = list(worker.engine_services(ROOT))


def web(name, slug, service, shipped=True, placeholder=True):
    return {"name": name, "slug": slug, "kind": "web", "service": service, "service_name": service.title(),
            "shipped": shipped, "placeholder": placeholder}


STOCK = [web("Coach Ellis", "coach-ellis-elevenlabs", "elevenlabs"), web("Coach Nolan", "coach-nolan-gemini", "gemini"),
         web("Coach Owen", "coach-owen-inworld", "inworld"), web("Coach Reed", "coach-reed-fish", "fish"),
         {"name": "Coach Andy", "slug": "coach-andy-local", "kind": "local", "service": None, "shipped": True}]
COVERAGE_EMPTY = {"sessions": 0, "covered": {}, "week": {}, "days_since": None}


def shape(files=None, keyed=(), coaches=STOCK, coverage=None):
    return start.shape(folder.seed(ROOT) if files is None else files, set(keyed), coaches, coverage,
                       engine_root=ROOT, presets=PRESETS, goals=GOALS, services=SERVICES)


def edit(files, path, old, new):
    out = dict(files)
    assert old.encode() in out[path], (path, old)
    out[path] = out[path].replace(old.encode(), new.encode(), 1)
    return out


class Shape(unittest.TestCase):
    def test_starter_template(self):
        r = shape(coverage=COVERAGE_EMPTY)
        self.assertEqual(set(r), {"coaches", "kits", "minutes", "limits", "suggest", "setup_quick"})
        self.assertEqual(r["minutes"], 25)
        self.assertEqual(r["limits"], [])
        self.assertIsNone(r["suggest"])
        self.assertTrue(r["setup_quick"])
        self.assertEqual([k["id"] for k in r["kits"]], ["home", "bodyweight", "hotel-room", "hotel-gym", "full-gym"])
        self.assertEqual(r["kits"][0], {"id": "home", "label": "home", "preset": False})
        self.assertEqual(r["kits"][2], {"id": "hotel-room", "label": "a hotel room", "preset": True})
        coaches = r["coaches"]
        self.assertEqual(len(coaches), 4)   # web only
        self.assertEqual([c["current"] for c in coaches].count(True), 1)
        # nothing keyed: the engine's stand-in order, services.toml's (Fish Audio first)
        self.assertEqual(coaches[0]["slug"], "coach-reed-fish")
        self.assertEqual(coaches[0], {"slug": "coach-reed-fish", "name": "Coach Reed", "first": "Reed",
                                      "service": "fish", "service_name": "Fish", "ready": False, "own": False,
                                      "current": True})

    def test_no_files_at_all(self):
        r = shape(files={}, coaches=[], coverage=None)
        self.assertEqual(r["coaches"], [])
        self.assertEqual(r["minutes"], 25)
        self.assertEqual(r["limits"], [])
        self.assertIsNone(r["suggest"])
        self.assertTrue(r["setup_quick"])
        self.assertEqual(r["kits"][0]["id"], "bodyweight")

    def test_damaged_files_read_as_empty(self):
        files = {"profile.md": b"+++\nnot = [toml\n+++\n", "training.md": b"+++\nnever closes\n",
                 "health.md": b"+++\nlimits = 3\n+++\n", "settings.toml": b"=", "log.md": b"\xff\xfe"}
        r = shape(files=files)
        self.assertEqual((r["minutes"], r["limits"], r["setup_quick"]), (25, [], True))

    def test_ready_coach_is_current_then_ready_first(self):
        r = shape(keyed={"gemini", "inworld"})
        self.assertEqual([c["first"] for c in r["coaches"]], ["Nolan", "Owen", "Reed", "Ellis"])
        self.assertEqual([c["ready"] for c in r["coaches"]], [True, True, False, False])
        self.assertTrue(r["coaches"][0]["current"])

    def test_coach_used_last_wins_even_unkeyed(self):
        files = edit(folder.seed(ROOT), "log.md", "## Sessions\n",
                     "## Sessions\n- 2026-10-01 | 25 min | home | Coach Reed | squat | x\n"
                     "- 2026-10-02 | 25 min | home | Coach Owen | squat | x\n")
        r = shape(files=files, keyed={"gemini"})
        self.assertEqual([(c["first"], c["current"]) for c in r["coaches"]][:2], [("Owen", True), ("Nolan", False)])

    def test_own_coach(self):
        own = web("Coach Dana", "coach-dana-fish", "fish", shipped=False, placeholder=False)
        r = shape(coaches=STOCK + [own], keyed={"fish"})
        self.assertEqual(r["coaches"][0]["slug"], "coach-dana-fish")
        self.assertEqual((r["coaches"][0]["own"], r["coaches"][0]["current"]), (True, True))
        self.assertEqual(r["coaches"][1]["slug"], "coach-reed-fish")
        # a stand-in used last gives way to their own coach that can speak
        files = edit(folder.seed(ROOT), "log.md", "## Sessions\n",
                     "## Sessions\n- 2026-10-02 | 25 min | home | Coach Owen | squat | x\n")
        self.assertEqual(shape(files=files, coaches=STOCK + [own], keyed={"fish"})["coaches"][0]["first"], "Dana")

    def test_minutes(self):
        seed = folder.seed(ROOT)
        for words, want in (("forty-five", 45), ("fifteen", 15), ("30", 30), ("ninety", 60), ("5", 10),
                            ("half an hour", 30), ("an hour", 60), ("whatever", 25)):
            with self.subTest(words):
                files = edit(seed, "training.md", "Usual length: twenty-five minutes", f"Usual length: {words} minutes")
                self.assertEqual(shape(files=files)["minutes"], want)

    def test_limits(self):
        files = edit(folder.seed(ROOT), "health.md", "+++\n# Health",
                     '[[limits]]\narea = "knee"\nside = "left"\nlevel = "delicate"\nnote = "x"\n'
                     '[[limits]]\narea = "shoulder"\nlevel = "off-limits"\n'
                     '[[limits]]\narea = "wrist"\nlevel = "sore"\n+++\n# Health')
        self.assertEqual(shape(files=files)["limits"],
                         [{"area": "knee", "side": "left", "level": "delicate"},
                          {"area": "shoulder", "side": "both", "level": "off-limits"}])

    def test_kits_from_profile_with_presets_after(self):
        files = edit(folder.seed(ROOT), "training.md", 'name = "home"', 'name = "garage"')
        files = edit(files, "training.md", 'equipment = ["dumbbells", "band", "mat"]',
                     'equipment = ["kettlebell"]\n\n[[kits]]\nname = "hotel-room"\nequipment = []')
        kits = shape(files=files)["kits"]
        self.assertEqual([(k["id"], k["preset"]) for k in kits],
                         [("garage", False), ("hotel-room", False), ("bodyweight", True), ("hotel-gym", True),
                          ("full-gym", True)])
        self.assertEqual(kits[3]["label"], "a hotel gym")

    def test_setup_full(self):
        files = edit(folder.seed(ROOT), "settings.toml", 'setup = "quick"', 'setup = "full"')
        self.assertFalse(shape(files=files)["setup_quick"])

    def test_suggest(self):
        patterns = ("squat", "hinge", "lunge", "horizontal-pull", "vertical-pull", "horizontal-push",
                    "vertical-push", "anti-extension", "anti-rotation", "rotation")
        week = {p: 1 for p in patterns}
        covered = {p: ["x"] for p in patterns}
        base = {"sessions": 3, "week": week, "covered": covered, "days_since": 1}
        self.assertIsNone(shape(coverage=base)["suggest"])
        s = shape(coverage={**base, "week": {**week, "squat": 0, "hinge": 0, "lunge": 0}})["suggest"]
        self.assertEqual(s, {"goal": "strength", "target": "legs", "reason": "legs: not trained this week"})
        self.assertIn(s["goal"], GOALS)
        s = shape(coverage={**base, "covered": {**covered, "horizontal-pull": [], "vertical-pull": []}})["suggest"]
        self.assertEqual(s["target"], "back")
        s = shape(coverage={**base, "days_since": 6})["suggest"]
        self.assertEqual(s, {"goal": "general", "target": None, "reason": "6 days since your last session"})
        self.assertIsNone(shape(coverage=COVERAGE_EMPTY)["suggest"])


class Gather(unittest.TestCase):
    """The two engine reads, run for real on the starter template (a few hundred milliseconds)."""

    def test_starter_template(self):
        r = start.gather(ROOT, folder.seed(ROOT), {"elevenlabs"})
        self.assertEqual({c["slug"] for c in r["coaches"]},
                         {"coach-reed-fish", "coach-ellis-elevenlabs", "coach-nolan-gemini", "coach-owen-inworld"})
        self.assertEqual(r["coaches"][0]["slug"], "coach-ellis-elevenlabs")
        self.assertIsNone(r["suggest"])

    def test_a_logged_session(self):
        files = edit(folder.seed(ROOT), "log.md", "## Sessions\n",
                     "## Sessions\n- 2026-01-05 | 25 min | home | Coach Owen | goblet squat, push-up | x\n")
        r = start.gather(ROOT, files, set())
        self.assertEqual(r["coaches"][0]["first"], "Owen")
        self.assertEqual(r["suggest"]["goal"], "strength")
        self.assertEqual(r["suggest"]["target"], "legs")   # months ago: nothing this week

    def test_no_files(self):
        r = start.gather(ROOT, {}, set())
        self.assertEqual(r["coaches"][0]["slug"], "coach-reed-fish")
        self.assertEqual(r["minutes"], 25)


class Route(test_api.ApiCase):
    def test_needs_session(self):
        self.assertEqual(self.client.get("/api/start").status_code, 401)

    def test_new_listener(self):
        user_id, uk = self.signed_in()
        from webapp import keystore, store
        store.write_back(self.conn, uk, folder.seed(ROOT), {})
        keystore.put(self.conn, uk, "gemini", "abc123def456abcd")
        self.conn.commit()
        r = self.client.get("/api/start")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(set(body), {"coaches", "kits", "minutes", "limits", "suggest", "setup_quick"})
        self.assertEqual(body["coaches"][0]["slug"], "coach-nolan-gemini")
        self.assertTrue(body["coaches"][0]["ready"] and body["coaches"][0]["current"])
        self.assertEqual(body["minutes"], 25)
        self.assertTrue(body["setup_quick"])

    def test_shared_model_key_counts_for_gemini(self):
        _, uk = self.signed_in()
        from webapp import keystore
        keystore.put(self.conn, uk, "google", "abc123def456abcd")   # a model key stored before 0.25.2
        self.conn.commit()
        body = self.client.get("/api/start").json()
        self.assertEqual(body["coaches"][0]["slug"], "coach-nolan-gemini")


if __name__ == "__main__":
    unittest.main()
