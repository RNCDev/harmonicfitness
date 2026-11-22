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
            "HARMONICFITNESS_BASE_URL": "https://example.test", "OPENROUTER_API_KEY": "sk-or-site-key-1234"}
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
        with self.assertRaises(crypto.Tampered):
            crypto.open_(k, b"short", b"a")

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
    def test_registration_switch_and_daily_allowance(self):
        for raw, want in (("closed", False), (" CLOSED ", False), ("open", True), ("", True)):
            self.assertEqual(config.load(env(HARMONICFITNESS_REGISTRATION=raw)).registration, want, raw)
        with self.assertRaises(config.ConfigError):
            config.load(env(HARMONICFITNESS_REGISTRATION="maybe"))
        from webapp import spend
        for raw, want in ((None, spend.DEFAULT_DAILY_CHARS), ("5000", 5000), ("-3", 0), ("lots", spend.DEFAULT_DAILY_CHARS)):
            extra = {} if raw is None else {"HARMONICFITNESS_DAILY_CHARS": raw}
            self.assertEqual(config.load(env(**extra)).daily_chars, want, raw)

    def test_config_refuses_a_short_or_unreadable_master_key(self):
        for bad in (b64(16), "!!notbase64!!"):
            with self.subTest(bad=bad):
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
        self.assertNotIn("sk-or-site-key-1234", r)

    def test_the_site_key_is_required(self):
        with self.assertRaises(config.ConfigError) as cm:
            config.load(env(OPENROUTER_API_KEY=""))
        self.assertIn("OPENROUTER_API_KEY", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
