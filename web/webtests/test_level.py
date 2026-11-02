"""The level in Settings (webapp/level.py), against the real engine in a temporary folder, no database; and, with
one, the routes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder, level, store  # noqa: E402
from webtests import test_api  # noqa: E402
from webtests.test_api import ROOT  # noqa: E402


class Calls(unittest.TestCase):
    def test_novice_until_set_then_the_one_chosen(self):
        files = dict(folder.seed(ROOT))
        now = level.current(ROOT, files)
        self.assertEqual((now["level"], now["set"]), ("novice", False))
        self.assertEqual([c["level"] for c in now["choices"]], ["novice", "experienced", "advanced"])
        self.assertIn("want to be pushed", now["choices"][2]["said"])
        changed = level.choose(ROOT, files, "advanced")
        self.assertEqual(set(changed), {"profile.md"})
        self.assertIn('experience = "advanced"', changed["profile.md"].decode())
        files.update(changed)
        self.assertEqual((level.current(ROOT, files)["level"], level.current(ROOT, files)["set"]), ("advanced", True))

    def test_an_unknown_level_is_refused(self):
        with self.assertRaises(level.Refused):
            level.choose(ROOT, dict(folder.seed(ROOT)), "expert")


class Routes(test_api.ApiCase):
    def test_the_level_routes(self):
        _, uk = self.signed_in()
        store.write_back(self.conn, uk, dict(folder.seed(ROOT)), {})
        self.conn.commit()
        self.assertEqual(self.client.get("/api/level").json()["level"], "novice")
        r = self.client.put("/api/level", json={"level": "experienced"}, headers=self.origin())
        self.assertEqual(r.status_code, 204, r.text)
        self.assertEqual(self.client.get("/api/level").json(),
                         {**self.client.get("/api/level").json(), "level": "experienced", "set": True})
        self.conn.rollback()
        self.assertIn(b'experience = "experienced"', store.read_all(self.conn, uk)["profile.md"][1])
        self.assertEqual(self.client.put("/api/level", json={"level": "expert"}, headers=self.origin()).status_code, 422)
        self.assertEqual(self.client.put("/api/level", json={"level": "novice"}).status_code, 403)   # no Origin
