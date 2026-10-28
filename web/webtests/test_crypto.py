import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import config, crypto  # noqa: E402


def b64(n):
    return base64.b64encode(os.urandom(n)).decode()


def env(**over):
    base = {"DATABASE_URL": "postgresql://x/y", "WT_MASTER_KEY": b64(32),
            "WT_BASE_URL": "https://example.test"}
    base.update(over)
    return base


class Crypto(unittest.TestCase):
    def test_round_trip(self):
        k = os.urandom(32)
        self.assertEqual(crypto.open_(k, crypto.seal(k, b"x", b"a"), b"a"), b"x")

    def test_wrong_aad_fails(self):
        k = os.urandom(32)
        sealed = crypto.seal(k, b"x", b"u1:context_files:health.md")
        with self.assertRaises(crypto.Tampered):
            crypto.open_(k, sealed, b"u2:context_files:health.md")

    def test_unwrap_needs_the_master(self):
        m1, m2 = os.urandom(32), os.urandom(32)
        key, wrapped = crypto.new_data_key(m1)
        self.assertEqual(crypto.unwrap(m1, wrapped), key)
        with self.assertRaises(crypto.Tampered):
            crypto.unwrap(m2, wrapped)

    def test_short_blob_is_tampered(self):
        with self.assertRaises(crypto.Tampered):
            crypto.open_(os.urandom(32), b"short", b"a")

    def test_nonces_differ(self):
        k = os.urandom(32)
        self.assertNotEqual(crypto.seal(k, b"x", b"a"), crypto.seal(k, b"x", b"a"))


class Config(unittest.TestCase):
    def test_load(self):
        s = config.load(env())
        self.assertEqual((s.role, s.session_days, s.invite_days), ("web", 90, 7))
        self.assertEqual(len(s.master_key), 32)
        self.assertTrue(os.path.isdir(os.path.join(s.engine_root, "tools")))

    def test_engine_root_override(self):
        self.assertEqual(config.load(env(WT_ENGINE_ROOT="/x")).engine_root, "/x")

    def test_config_refuses_short_master_key(self):
        bad = b64(16)
        with self.assertRaises(config.ConfigError) as cm:
            config.load(env(WT_MASTER_KEY=bad))
        self.assertIn("WT_MASTER_KEY", str(cm.exception))
        self.assertNotIn(bad, str(cm.exception))

    def test_bad_base64(self):
        with self.assertRaises(config.ConfigError) as cm:
            config.load(env(WT_MASTER_KEY="!!notbase64!!"))
        self.assertIn("WT_MASTER_KEY", str(cm.exception))

    def test_missing_and_bad_role(self):
        e = env()
        del e["DATABASE_URL"]
        with self.assertRaises(config.ConfigError) as cm:
            config.load(e)
        self.assertIn("DATABASE_URL", str(cm.exception))
        with self.assertRaises(config.ConfigError):
            config.load(env(WT_ROLE="boss"))
        self.assertEqual(config.load(env(WT_ROLE="worker")).role, "worker")


if __name__ == "__main__":
    unittest.main()
