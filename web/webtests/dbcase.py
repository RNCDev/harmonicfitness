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
        user_id = uuid.uuid4()
        plain, wrapped = crypto.new_data_key(MASTER, user_id, 1)
        self.conn.execute(
            "insert into users (id, email, wrapped_key, key_version) values (%s, %s, %s, 1)",
            (user_id, email, wrapped))
        self.conn.commit()
        return user_id, store.UserKey(user_id=user_id, key=plain)
