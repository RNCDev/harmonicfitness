"""The routes behind ./harmonicfitness sync: list, read and write the listener's files, each write only over
the version the computer last saw."""
import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import folder, store  # noqa: E402
from webtests import test_api  # noqa: E402
from webtests.test_api import ROOT  # noqa: E402


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


class SkipLists(unittest.TestCase):
    def test_the_command_skips_what_the_site_never_keeps(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        try:
            import websync
        finally:
            sys.path.remove(os.path.join(ROOT, "tools"))
        self.assertEqual(websync.SKIP, folder.SKIP)
        self.assertEqual(websync.COACH_SAMPLE.pattern, folder.COACH_SAMPLE.pattern)   # and the one MP3 both keep
        self.assertEqual(websync.LOCAL_ONLY, folder.LOCAL_ONLY)   # and what the computer keeps to itself


class Routes(test_api.ApiCase):
    def test_a_file_the_computer_keeps_to_itself_is_never_listed(self):
        """A copy synced before 0.71.2 still holds the backup's remote note; listed, it stops every sync (0.77.1)."""
        _, uk = self.signed_in()
        store.write_back(self.conn, uk, {"log.md": b"log", "workouts/.logs/backup-remote.json": b"{}",
                                         "web/sync-state.json": b"{}"}, {})
        self.conn.commit()
        listed = [f["path"] for f in self.client.get("/api/sync").json()["files"]]
        self.assertEqual(listed, ["log.md"])
        r = self.client.post("/api/sync/read", headers=self.origin(),
                             json={"paths": ["workouts/.logs/backup-remote.json", "log.md"]})
        self.assertEqual([f["path"] for f in r.json()["files"]], ["log.md"])

    def test_bad_paths_and_bodies_are_refused(self):
        self.signed_in()
        r = self.client.post("/api/sync/write", headers=self.origin(), json={"changes": [
            {"path": "../x", "base": None, "body": b64(b"x")},
            {"path": "a.md", "base": None, "body": "not base64!"}]})
        self.assertEqual(r.json()["refused"], ["../x", "a.md"])

    def test_the_routes_need_a_session_and_same_origin(self):
        self.assertEqual(self.client.get("/api/sync").status_code, 401)
        self.signed_in()
        self.assertEqual(self.client.post("/api/sync/write", json={"changes": []}).status_code, 403)
