import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import crypto, db, store  # noqa: E402
from webtests.dbcase import MASTER, DBCase  # noqa: E402


class Migrations(DBCase):
    def test_migrate_is_idempotent(self):
        # the class's own connection was migrated in setUpClass; use a new schema
        import uuid
        from webtests import dbcase
        name = "t_" + uuid.uuid4().hex[:12]
        admin = db.connect(dbcase.URL)
        admin.autocommit = True
        admin.execute(f"create schema {name}")
        conn = db.connect(dbcase.URL, schema=name)
        try:
            self.assertEqual(db.migrate(conn), ["001_init.sql", "002_sessions_renewed.sql"])
            self.assertEqual(db.migrate(conn), [])
        finally:
            conn.close()
            admin.execute(f"drop schema {name} cascade")
            admin.close()

    def test_concurrent_migrate_applies_once(self):
        import threading
        import uuid
        from webtests import dbcase
        name = "t_" + uuid.uuid4().hex[:12]
        admin = db.connect(dbcase.URL)
        admin.autocommit = True
        admin.execute(f"create schema {name}")
        conns = [db.connect(dbcase.URL, schema=name) for _ in range(2)]
        barrier = threading.Barrier(2)
        results, errors = [], []

        def run(c):
            try:
                barrier.wait()
                results.append(db.migrate(c))
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=run, args=(c,)) for c in conns]
        try:
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(sorted(results), [[], ["001_init.sql", "002_sessions_renewed.sql"]])
        finally:
            for c in conns:
                c.close()
            admin.execute(f"drop schema {name} cascade")
            admin.close()

    def test_class_schema_is_migrated(self):
        self.assertEqual(db.migrate(self.conn), [])


class Store(DBCase):
    def test_bodies_are_encrypted_at_rest(self):
        _, uk = self.make_user()
        self.assertEqual(store.write_back(self.conn, uk, {"health.md": b"left ankle"}, {}), [])
        self.conn.commit()
        raw = self.conn.execute("select body from context_files where user_id = %s",
                                (uk.user_id,)).fetchone()[0]
        self.assertNotIn(b"left ankle", bytes(raw))
        self.assertEqual(store.read_all(self.conn, uk), {"health.md": (1, b"left ankle")})

    def test_write_back_conflict_keeps_users_edit(self):
        _, uk = self.make_user()
        store.write_back(self.conn, uk, {"health.md": b"v1", "other.md": b"o1"}, {})
        files = store.read_all(self.conn, uk)
        self.assertEqual(files["health.md"][0], 1)
        self.assertEqual(store.put(self.conn, uk, "health.md", b"panel edit"), 2)
        base = {p: v for p, (v, _) in files.items()}
        conflicts = store.write_back(
            self.conn, uk, {"health.md": b"engine edit", "other.md": b"o2"}, base)
        self.assertEqual(conflicts, ["health.md"])
        after = store.read_all(self.conn, uk)
        self.assertEqual(after["health.md"], (2, b"panel edit"))
        self.assertEqual(after["other.md"], (2, b"o2"))

    def test_new_file_conflicts_when_it_exists(self):
        _, uk = self.make_user()
        store.put(self.conn, uk, "a.md", b"x")
        self.assertEqual(store.write_back(self.conn, uk, {"a.md": b"y"}, {}), ["a.md"])
        self.assertEqual(store.read_all(self.conn, uk)["a.md"], (1, b"x"))

    def test_delete_only_at_base_version(self):
        _, uk = self.make_user()
        store.put(self.conn, uk, "a.md", b"x")
        store.put(self.conn, uk, "b.md", b"x")
        store.put(self.conn, uk, "b.md", b"x2")
        out = store.write_back(self.conn, uk, {"a.md": None, "b.md": None}, {"a.md": 1, "b.md": 1})
        self.assertEqual(out, ["b.md"])
        self.assertEqual(list(store.read_all(self.conn, uk)), ["b.md"])

    def test_users_are_isolated(self):
        _, a = self.make_user()
        _, b = self.make_user()
        store.put(self.conn, a, "health.md", b"secret")
        self.assertEqual(store.read_all(self.conn, b), {})
        row = self.conn.execute("select body from context_files where user_id = %s",
                                (a.user_id,)).fetchone()
        with self.assertRaises(crypto.Tampered):
            crypto.open_(b.key, bytes(row[0]), f"{a.user_id}:context_files:health.md".encode())

    def test_aad_binds_the_row_to_its_path(self):
        _, uk = self.make_user()
        store.put(self.conn, uk, "a.md", b"secret")
        self.conn.execute("insert into context_files (user_id, path, version, body) "
                          "select user_id, 'b.md', 1, body from context_files "
                          "where user_id = %s and path = 'a.md'", (uk.user_id,))
        with self.assertRaises(crypto.Tampered):
            store.read_all(self.conn, uk)

    def test_bad_paths_rejected(self):
        _, uk = self.make_user()
        for bad in ("/etc/x", "../x", "a/../b", "", "a\\b"):
            with self.assertRaises(ValueError):
                store.put(self.conn, uk, bad, b"x")
            with self.assertRaises(ValueError):
                store.write_back(self.conn, uk, {bad: b"x"}, {})

    def test_user_key_unwraps(self):
        from webapp import config
        uid, uk = self.make_user()
        s = config.Settings(database_url="x", master_key=MASTER, base_url="https://x")
        self.assertEqual(store.user_key(self.conn, s, uid), uk)
        self.assertNotIn(uk.key.hex(), repr(uk))


if __name__ == "__main__":
    import unittest
    unittest.main()
