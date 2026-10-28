import os
import sys
import time
import uuid
from datetime import datetime
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import crypto, keystore  # noqa: E402
from webtests.dbcase import DBCase  # noqa: E402


class KeyStore(DBCase):
    def secret_of(self, user_id, service):
        return bytes(self.conn.execute(
            "select secret from user_keys where user_id = %s and service = %s",
            (user_id, service)).fetchone()[0])

    def test_put_seals_and_open_all_returns(self):
        uid, uk = self.make_user()
        keystore.put(self.conn, uk, "fish", "k-123456789")
        self.conn.commit()
        self.assertNotIn(b"k-123456789", self.secret_of(uid, "fish"))
        self.assertEqual(keystore.open_all(self.conn, uk), {"fish": "k-123456789"})
        first = keystore.listing(self.conn, uk)["fish"]
        time.sleep(0.01)
        keystore.put(self.conn, uk, "fish", "k-987654321")
        self.conn.commit()
        self.assertEqual(keystore.open_all(self.conn, uk), {"fish": "k-987654321"})
        self.assertGreater(keystore.listing(self.conn, uk)["fish"], first)

    def test_listing_never_opens(self):
        _, uk = self.make_user()
        keystore.put(self.conn, uk, "fish", "k-123456789")
        self.conn.commit()
        with mock.patch.object(crypto, "open_", side_effect=AssertionError("opened")):
            out = keystore.listing(self.conn, uk)
        self.assertEqual(list(out), ["fish"])
        self.assertIsInstance(out["fish"], datetime)

    def test_secret_bound_to_user_and_service(self):
        a, uka = self.make_user()
        b, ukb = self.make_user()
        keystore.put(self.conn, uka, "fish", "k-123456789")
        keystore.put(self.conn, ukb, "fish", "other-key-1")
        self.conn.commit()
        stolen = self.secret_of(a, "fish")
        self.conn.execute("update user_keys set secret = %s where user_id = %s", (stolen, b))
        self.conn.commit()
        with self.assertRaises(crypto.Tampered):
            keystore.open_all(self.conn, ukb)
        self.conn.execute("insert into user_keys (user_id, service, secret) values (%s, %s, %s)",
                          (a, "elevenlabs", stolen))
        self.conn.commit()
        with self.assertRaises(crypto.Tampered):
            keystore.open_all(self.conn, uka)

    def test_delete(self):
        _, uk = self.make_user()
        keystore.put(self.conn, uk, "fish", "k-123456789")
        self.conn.commit()
        self.assertTrue(keystore.delete(self.conn, uk, "fish"))
        self.assertFalse(keystore.delete(self.conn, uk, "fish"))
        self.conn.commit()
        self.assertEqual(keystore.open_all(self.conn, uk), {})

    def test_cascade(self):
        uid, uk = self.make_user()
        keystore.put(self.conn, uk, "fish", "k-123456789")
        self.conn.commit()
        self.conn.execute("delete from users where id = %s", (uid,))
        self.conn.commit()
        n = self.conn.execute("select count(*) from user_keys where user_id = %s",
                              (uid,)).fetchone()[0]
        self.assertEqual(n, 0)
