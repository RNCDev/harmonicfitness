import base64
import os
import uuid
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import config, crypto  # noqa: E402


def b64(n):
    return base64.b64encode(os.urandom(n)).decode()


def env(**over):
    base = {"DATABASE_URL": "postgresql://x/y", "HARMONICFITNESS_MASTER_KEY": b64(32),
            "HARMONICFITNESS_BASE_URL": "https://example.test"}
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
        uid = uuid.uuid4()
        key, wrapped = crypto.new_data_key(m1, uid, 1)
        self.assertEqual(crypto.unwrap(m1, wrapped, uid, 1), key)
        self.assertEqual(crypto.unwrap(m1, wrapped, str(uid), 1), key)
        with self.assertRaises(crypto.Tampered):
            crypto.unwrap(m2, wrapped, uid, 1)

    def test_wrapped_key_is_bound_to_its_user_and_version(self):
        m = os.urandom(32)
        uid = uuid.uuid4()
        _, wrapped = crypto.new_data_key(m, uid, 1)
        with self.assertRaises(crypto.Tampered):
            crypto.unwrap(m, wrapped, uuid.uuid4(), 1)
        with self.assertRaises(crypto.Tampered):
            crypto.unwrap(m, wrapped, uid, 2)

    def test_short_blob_is_tampered(self):
        with self.assertRaises(crypto.Tampered):
            crypto.open_(os.urandom(32), b"short", b"a")

    def test_key_length_enforced(self):
        k16 = os.urandom(16)
        with self.assertRaisesRegex(ValueError, "key must be 32 bytes") as cm:
            crypto.seal(k16, b"x", b"a")
        self.assertNotIn(repr(k16), str(cm.exception))
        with self.assertRaisesRegex(ValueError, "key must be 32 bytes"):
            crypto.unwrap(k16, os.urandom(60), uuid.uuid4(), 1)
        with self.assertRaises(ValueError):
            crypto.new_data_key(k16, uuid.uuid4(), 1)
        with self.assertRaises(ValueError):
            crypto.open_(k16, os.urandom(60), b"a")

    def test_nonces_differ(self):
        k = os.urandom(32)
        self.assertNotEqual(crypto.seal(k, b"x", b"a"), crypto.seal(k, b"x", b"a"))


class Config(unittest.TestCase):
    def test_load(self):
        s = config.load(env())
        self.assertEqual((s.role, s.session_days, s.registration), ("web", 90, True))
        self.assertEqual(len(s.master_key), 32)
        self.assertTrue(os.path.isdir(os.path.join(s.engine_root, "tools")))

    def test_registration_switch(self):
        for raw, want in (("closed", False), (" CLOSED ", False), ("open", True), ("", True)):
            self.assertEqual(config.load(env(HARMONICFITNESS_REGISTRATION=raw)).registration, want, raw)
        with self.assertRaises(config.ConfigError):
            config.load(env(HARMONICFITNESS_REGISTRATION="maybe"))

    def test_engine_root_override(self):
        self.assertEqual(config.load(env(HARMONICFITNESS_ENGINE_ROOT="/x")).engine_root, "/x")

    def test_config_refuses_short_master_key(self):
        bad = b64(16)
        with self.assertRaises(config.ConfigError) as cm:
            config.load(env(HARMONICFITNESS_MASTER_KEY=bad))
        self.assertIn("HARMONICFITNESS_MASTER_KEY", str(cm.exception))
        self.assertNotIn(bad, str(cm.exception))

    def test_repr_hides_secrets(self):
        raw = os.urandom(32)
        e = env(HARMONICFITNESS_MASTER_KEY=base64.b64encode(raw).decode(),
                DATABASE_URL="postgresql://u:hunter2pw@h/d")
        r = repr(config.load(e))
        self.assertNotIn(e["HARMONICFITNESS_MASTER_KEY"], r)
        self.assertNotIn(repr(raw), r)
        self.assertNotIn("hunter2pw", r)

    def test_empty_role_refused(self):
        with self.assertRaises(config.ConfigError):
            config.load(env(HARMONICFITNESS_ROLE=""))

    def test_bad_base64(self):
        with self.assertRaises(config.ConfigError) as cm:
            config.load(env(HARMONICFITNESS_MASTER_KEY="!!notbase64!!"))
        self.assertIn("HARMONICFITNESS_MASTER_KEY", str(cm.exception))

    def test_missing_and_bad_role(self):
        e = env()
        del e["DATABASE_URL"]
        with self.assertRaises(config.ConfigError) as cm:
            config.load(e)
        self.assertIn("DATABASE_URL", str(cm.exception))
        with self.assertRaises(config.ConfigError):
            config.load(env(HARMONICFITNESS_ROLE="boss"))
        self.assertEqual(config.load(env(HARMONICFITNESS_ROLE="worker")).role, "worker")


if __name__ == "__main__":
    unittest.main()
