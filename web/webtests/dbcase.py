"""Base class for tests that need Postgres: a fresh schema per test class."""
import os
import sys
import unittest
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import crypto, db, store  # noqa: E402

URL = os.environ.get("WT_TEST_DATABASE_URL", "").strip()
MASTER = bytes(range(32))


class DBCase(unittest.TestCase):
    conn = None
    schema = None

    @classmethod
    def setUpClass(cls):
        if not URL:
            raise unittest.SkipTest("WT_TEST_DATABASE_URL is not set")
        cls.schema = "t_" + uuid.uuid4().hex[:12]
        admin = db.connect(URL)
        admin.autocommit = True
        admin.execute(f"create schema {cls.schema}")
        admin.close()
        cls.conn = db.connect(URL, schema=cls.schema)
        cls.addClassCleanup(cls._drop)
        db.migrate(cls.conn)

    @classmethod
    def _drop(cls):
        cls.conn.close()
        admin = db.connect(URL)
        admin.autocommit = True
        admin.execute(f"drop schema {cls.schema} cascade")
        admin.close()

    def make_user(self, email=None):
        """Insert a user with a fresh data key; return (user_id, UserKey)."""
        email = email or f"{uuid.uuid4().hex[:8]}@example.test"
        plain, wrapped = crypto.new_data_key(MASTER)
        row = self.conn.execute(
            "insert into users (email, wrapped_key) values (%s, %s) returning id",
            (email, wrapped)).fetchone()
        self.conn.commit()
        return row[0], store.UserKey(user_id=row[0], key=plain)
