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
            self.assertEqual(db.migrate(conn), ["001_init.sql", "002_sessions_renewed.sql", "003_sealed_paths.sql"])
            self.assertEqual(db.migrate(conn), [])
        finally:
            conn.close()
            admin.execute(f"drop schema {name} cascade")
            admin.close()

    def test_wait_for_migrations(self):
        import uuid
        from webtests import dbcase
        name = "t_" + uuid.uuid4().hex[:12]
        admin = db.connect(dbcase.URL)
        admin.autocommit = True
        admin.execute(f"create schema {name}")
        make = lambda: db.connect(dbcase.URL, schema=name)  # noqa: E731
        try:
            # a fresh schema: no schema_migrations table at all, so it times out
            with self.assertRaises(db.MigrationsPending):
                db.wait_for_migrations(make, timeout=0.3, interval=0.05)
            import threading
            ev = threading.Event()
            ev.set()
            self.assertFalse(db.wait_for_migrations(make, timeout=5, interval=0.05, stop=ev))
            conn = make()
            db.migrate(conn)
            conn.close()
            self.assertTrue(db.wait_for_migrations(make, timeout=0.3, interval=0.05))   # returns at once
            # a migration file not yet recorded counts as pending
            conn = make()
            conn.execute("delete from schema_migrations where name = '003_sealed_paths.sql'")
            conn.commit()
            conn.close()
            with self.assertRaises(db.MigrationsPending):
                db.wait_for_migrations(make, timeout=0.3, interval=0.05)
        finally:
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
            self.assertEqual(sorted(results), [[], ["001_init.sql", "002_sessions_renewed.sql", "003_sealed_paths.sql"]])
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
        # a.md's body moved under b.md's hash and sealed path
        self.conn.execute("insert into context_files (user_id, path_hash, path, version, body) "
                          "select user_id, %s, %s, 1, body from context_files "
                          "where user_id = %s and path_hash = %s",
                          (store._path_hash(uk, "b.md"), store._seal_path(uk, "b.md"),
                           uk.user_id, store._path_hash(uk, "a.md")))
        with self.assertRaises(crypto.Tampered):
            store.read_all(self.conn, uk)
        self.conn.rollback()

    def test_sealed_path_is_bound_to_its_user(self):
        _, a = self.make_user()
        _, b = self.make_user()
        sealed = store._seal_path(a, "health.md")
        with self.assertRaises(crypto.Tampered):
            store._open_path(store.UserKey(user_id=b.user_id, key=a.key), sealed)

    def test_paths_never_stored_in_plain(self):
        _, uk = self.make_user()
        path = "workouts/zebra-quartz-path/zebra-quartz.draft.txt"
        store.write_back(self.conn, uk, {path: b"x"}, {})
        store.put(self.conn, uk, path, b"y")
        self.conn.commit()
        cur = self.conn.execute("select * from context_files where user_id = %s", (uk.user_id,))
        rows = cur.fetchall()
        self.assertEqual(len(rows), 1)
        for name, value in zip([d.name for d in cur.description], rows[0]):
            raw = bytes(value) if isinstance(value, (bytes, memoryview)) else str(value).encode()
            for needle in (path, "zebra", "quartz"):
                self.assertNotIn(needle.encode(), raw, name)
        self.assertEqual(store.read_all(self.conn, uk), {path: (2, b"y")})
        self.assertEqual([p for p, _, _ in store.listing(self.conn, uk)], [path])

    def test_path_hash_is_per_user(self):
        _, a = self.make_user()
        _, b = self.make_user()
        self.assertEqual(store._path_hash(a, "health.md"), store._path_hash(a, "health.md"))
        self.assertNotEqual(store._path_hash(a, "health.md"), store._path_hash(a, "other.md"))
        self.assertNotEqual(store._path_hash(a, "health.md"), store._path_hash(b, "health.md"))
        store.put(self.conn, a, "health.md", b"x")
        store.put(self.conn, b, "health.md", b"x")
        self.conn.commit()
        hashes = {uid: bytes(h) for uid, h in self.conn.execute(
            "select user_id, path_hash from context_files where user_id in (%s, %s)",
            (a.user_id, b.user_id)).fetchall()}
        self.conn.rollback()
        self.assertEqual(hashes[a.user_id], store._path_hash(a, "health.md"))
        self.assertEqual(hashes[b.user_id], store._path_hash(b, "health.md"))
        self.assertNotEqual(hashes[a.user_id], hashes[b.user_id])

    def test_listing_is_sorted_by_path(self):
        _, uk = self.make_user()
        for p in ("c.md", "a.md", "b/z.md"):
            store.put(self.conn, uk, p, b"x")
        self.conn.commit()
        self.assertEqual([p for p, _, _ in store.listing(self.conn, uk)], ["a.md", "b/z.md", "c.md"])
        self.assertEqual(list(store.read_all(self.conn, uk)), ["a.md", "b/z.md", "c.md"])

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
