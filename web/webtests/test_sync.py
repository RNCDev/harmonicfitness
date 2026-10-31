"""The routes behind ./harmonicfitness sync: list, read and write the listener's files, each write only over
the version the computer last saw."""
import base64
import hashlib
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


class Routes(test_api.ApiCase):
    def test_list_read_write(self):
        _, uk = self.signed_in()
        store.write_back(self.conn, uk, {"log.md": b"log", "workouts/w/w.draft.txt": b"draft"}, {})
        self.conn.commit()
        files = {f["path"]: f for f in self.client.get("/api/sync").json()["files"]}
        self.assertEqual(files["log.md"], {"path": "log.md", "version": 1, "sha256": hashlib.sha256(b"log").hexdigest()})

        got = self.client.post("/api/sync/read", json={"paths": ["log.md", "nope.md"]}, headers=self.origin()).json()
        self.assertEqual([(f["path"], base64.b64decode(f["body"])) for f in got["files"]], [("log.md", b"log")])

        r = self.client.post("/api/sync/write", headers=self.origin(), json={"changes": [
            {"path": "log.md", "base": 1, "body": b64(b"log 2")},            # over the version seen: lands
            {"path": "workouts/w/w.draft.txt", "base": 7, "body": b64(b"x")},  # an old version: a conflict
            {"path": "profile.md", "base": None, "body": b64(b"me")},         # new to the site
            {"path": ".env", "base": None, "body": b64(b"KEY=1")},            # never kept
            {"path": "workouts/w/W.mp3", "base": None, "body": b64(b"ID3")},
        ]})
        self.assertEqual(r.status_code, 200, r.text)
        out = r.json()
        self.assertEqual(out["written"], {"log.md": 2, "profile.md": 1})
        self.assertEqual(out["conflicts"], ["workouts/w/w.draft.txt"])
        self.assertEqual(out["refused"], [".env", "workouts/w/W.mp3"])
        self.conn.rollback()
        have = store.read_all(self.conn, uk)
        self.conn.rollback()
        self.assertEqual((have["log.md"], have["workouts/w/w.draft.txt"][1]), ((2, b"log 2"), b"draft"))
        self.assertNotIn(".env", have)

        r = self.client.post("/api/sync/write", headers=self.origin(),
                             json={"changes": [{"path": "profile.md", "base": 1, "body": None}]})
        self.assertEqual(r.json()["written"], {"profile.md": None})

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
