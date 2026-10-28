import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import auth, config, db, store  # noqa: E402
from webtests import dbcase  # noqa: E402
from webtests.dbcase import MASTER, DBCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def settings():
    return config.Settings(database_url="x", master_key=MASTER, base_url="https://wt.test/",
                           engine_root=ROOT)


def URL_FOR(case):
    return dbcase.URL + ("?options=-csearch_path%3D" + case.schema)


def token_of(link):
    return link.rsplit("/link/", 1)[1]


class Passwords(unittest.TestCase):
    def test_hash_round_trip(self):
        h = auth.hash_password("correct horse")
        self.assertTrue(h.startswith("scrypt$32768$8$1$"))
        self.assertNotIn("correct horse", h)
        self.assertTrue(auth.verify_password("correct horse", h))
        self.assertFalse(auth.verify_password("correct hors", h))
        self.assertNotEqual(h, auth.hash_password("correct horse"))   # salted

    def test_missing_or_damaged_hash_never_matches(self):
        for stored in (None, "", "plain", "md5$1$1$1$AA==$AA==", "scrypt$x$8$1$AA==$AA=="):
            self.assertFalse(auth.verify_password("anything", stored), stored)

    def test_usernames(self):
        self.assertEqual(auth.username("  Ana.B-2_ "), "ana.b-2_")
        for bad in ("", "ab", "-ana", ".ana", "a" * 33, "ana b", "ana@x", "ånа", None, 5):
            with self.assertRaises(auth.Invalid, msg=repr(bad)):
                auth.username(bad)


class Auth(DBCase):
    def setUp(self):
        self.s = settings()

    def uid(self, name):
        row = self.conn.execute("select id from users where username = %s", (name,)).fetchone()
        self.conn.rollback()
        return row[0]

    def test_register_creates_seeded_user_signed_in(self):
        st = auth.register(self.conn, self.s, " NewOne ", "long enough")
        uid = self.uid("newone")
        self.assertEqual(auth.user_for(self.conn, self.s, st), uid)
        uk = store.user_key(self.conn, self.s, uid)
        self.assertIn("profile.md", store.read_all(self.conn, uk))
        self.conn.rollback()

    def test_register_refuses_taken_and_bad(self):
        auth.register(self.conn, self.s, "taken", "long enough")
        with self.assertRaises(auth.Taken):
            auth.register(self.conn, self.s, "TAKEN", "other password")
        with self.assertRaises(auth.Invalid):
            auth.register(self.conn, self.s, "shortpw", "1234567")
        with self.assertRaises(auth.Invalid):
            auth.register(self.conn, self.s, "x", "long enough")
        n = self.conn.execute("select count(*) from users where username in ('taken', 'shortpw')"
                              ).fetchone()[0]
        self.conn.rollback()
        self.assertEqual(n, 1)

    def test_new_users_key_is_bound_to_its_id(self):
        from webapp import crypto
        auth.register(self.conn, self.s, "bound", "long enough")
        uid, wrapped, version = self.conn.execute(
            "select id, wrapped_key, key_version from users where username = 'bound'").fetchone()
        self.conn.rollback()
        self.assertEqual(version, 1)
        crypto.unwrap(MASTER, bytes(wrapped), uid, version)
        other, = self.conn.execute("select gen_random_uuid()").fetchone()
        self.conn.rollback()
        with self.assertRaises(crypto.Tampered):
            crypto.unwrap(MASTER, bytes(wrapped), other, version)

    def test_sign_in(self):
        auth.register(self.conn, self.s, "signer", "long enough")
        st = auth.sign_in(self.conn, self.s, "Signer", "long enough")
        self.assertEqual(auth.user_for(self.conn, self.s, st), self.uid("signer"))
        for name, pw in (("signer", "wrong one!"), ("nobody", "long enough"), ("x", "y"),
                         (None, None), ("signer", "x" * 5000)):
            with self.assertRaises(auth.WrongPassword):
                auth.sign_in(self.conn, self.s, name, pw)

    def test_no_password_never_signs_in(self):
        uid, _ = self.make_user("nopw")
        with self.assertRaises(auth.WrongPassword):
            auth.sign_in(self.conn, self.s, "nopw", "")

    def test_set_password(self):
        st = auth.register(self.conn, self.s, "changer", "first password")
        uid = self.uid("changer")
        other = auth.sign_in(self.conn, self.s, "changer", "first password")
        with self.assertRaises(auth.WrongPassword):
            auth.set_password(self.conn, uid, "not it", "second password", keep_session=st)
        with self.assertRaises(auth.Invalid):
            auth.set_password(self.conn, uid, "first password", "short", keep_session=st)
        auth.set_password(self.conn, uid, "first password", "second password", keep_session=st)
        self.assertEqual(auth.user_for(self.conn, self.s, st), uid)     # this one stays
        self.assertIsNone(auth.user_for(self.conn, self.s, other))     # every other ends
        auth.sign_in(self.conn, self.s, "changer", "second password")

    def test_first_password_needs_no_current(self):
        uid, _ = self.make_user("first")
        auth.set_password(self.conn, uid, None, "brand new one")
        auth.sign_in(self.conn, self.s, "first", "brand new one")

    def test_reset_link(self):
        auth.register(self.conn, self.s, "forgot", "lost it now")
        uid = self.uid("forgot")
        old = auth.sign_in(self.conn, self.s, "forgot", "lost it now")
        link = auth.reset_link(self.conn, self.s, "Forgot")
        self.assertTrue(link.url.startswith("https://wt.test/link/"))
        self.assertIsNone(auth.user_for(self.conn, self.s, old))
        with self.assertRaises(auth.WrongPassword):
            auth.sign_in(self.conn, self.s, "forgot", "lost it now")
        hours = self.conn.execute("select extract(epoch from expires_at - now())/3600 from "
                                  "sign_in_links where user_id = %s and used_at is null",
                                  (uid,)).fetchone()[0]
        self.conn.rollback()
        self.assertTrue(23 < hours <= 24, hours)
        st = auth.redeem(self.conn, self.s, token_of(link.url))
        self.assertEqual(auth.user_for(self.conn, self.s, st), uid)
        auth.set_password(self.conn, uid, None, "found again")
        with self.assertRaises(LookupError):
            auth.reset_link(self.conn, self.s, "ghost")

    def test_unknown_refused(self):
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, "nope")

    def test_tokens_stored_hashed(self):
        uid, _ = self.make_user()
        t = token_of(auth.device_link(self.conn, self.s, uid).url)
        st = auth.redeem(self.conn, self.s, t)
        for tok, table in ((t, "sign_in_links"), (st, "sessions")):
            for (h,) in self.conn.execute(f"select token_hash from {table}").fetchall():
                self.assertNotIn(tok.encode(), bytes(h))
                self.assertEqual(len(bytes(h)), 32)
        self.conn.rollback()

    def test_device_link_signs_in_same_user(self):
        uid, _ = self.make_user()
        t = token_of(auth.device_link(self.conn, self.s, uid).url)
        st = auth.redeem(self.conn, self.s, t)
        self.assertEqual(auth.user_for(self.conn, self.s, st), uid)
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, t)
        t2 = token_of(auth.device_link(self.conn, self.s, uid).url)
        self.conn.execute("update sign_in_links set expires_at = now() - interval '1 second' "
                          "where used_at is null")
        self.conn.commit()
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, t2)

    def test_device_link_lasts_ten_minutes(self):
        uid, _ = self.make_user()
        link = auth.device_link(self.conn, self.s, uid)
        mins, stored = self.conn.execute(
            "select extract(epoch from expires_at - now())/60, expires_at from sign_in_links "
            "where user_id = %s", (uid,)).fetchone()
        self.conn.rollback()
        self.assertTrue(9 < mins <= 10)
        self.assertEqual(link.expires_at, stored)
        self.assertTrue(link.url.startswith("https://wt.test/link/"))

    def test_session_renews_on_use(self):
        uid, _ = self.make_user()
        st = auth.redeem(self.conn, self.s, token_of(auth.device_link(self.conn, self.s, uid).url))
        self.conn.execute("update sessions set expires_at = now() + interval '10 days', "
                          "renewed_at = now() - interval '2 days' where user_id = %s", (uid,))
        self.conn.commit()
        self.assertEqual(auth.user_for(self.conn, self.s, st), uid)
        days = self.conn.execute("select extract(epoch from expires_at - now())/86400 "
                                 "from sessions where user_id = %s", (uid,)).fetchone()[0]
        self.assertTrue(89 < days < 91, days)

    def test_session_not_renewed_within_a_day(self):
        uid, _ = self.make_user()
        st = auth.redeem(self.conn, self.s, token_of(auth.device_link(self.conn, self.s, uid).url))
        self.conn.execute("update sessions set expires_at = now() + interval '10 days' where user_id = %s", (uid,))
        self.conn.commit()
        auth.user_for(self.conn, self.s, st)
        days = self.conn.execute("select extract(epoch from expires_at - now())/86400 "
                                 "from sessions where user_id = %s", (uid,)).fetchone()[0]
        self.assertTrue(days < 11)

    def test_expired_session_is_none(self):
        uid, _ = self.make_user()
        st = auth.redeem(self.conn, self.s, token_of(auth.device_link(self.conn, self.s, uid).url))
        self.conn.execute("update sessions set expires_at = now() - interval '1 second' where user_id = %s", (uid,))
        self.conn.commit()
        self.assertIsNone(auth.user_for(self.conn, self.s, st))
        self.assertIsNone(auth.user_for(self.conn, self.s, "unknown"))

    def test_sign_out(self):
        uid, _ = self.make_user()
        st = auth.redeem(self.conn, self.s, token_of(auth.device_link(self.conn, self.s, uid).url))
        auth.sign_out(self.conn, st)
        self.assertIsNone(auth.user_for(self.conn, self.s, st))


class Admin(DBCase):
    def run_admin(self, *argv, url=None):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from webapp import admin
        env = {"DATABASE_URL": url or URL_FOR(self), "WT_BASE_URL": "https://wt.test",
               "WT_MASTER_KEY": __import__("base64").b64encode(MASTER).decode(),
               "WT_ENGINE_ROOT": ROOT}
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = admin.main(list(argv), env)
        return code, out.getvalue(), err.getvalue()

    def test_reset_password_prints_only_the_link(self):
        self.make_user("adm")
        code, out, err = self.run_admin("reset-password", "ADM")
        self.assertEqual(code, 0, err)
        self.assertRegex(out, r"^https://wt\.test/link/[A-Za-z0-9_-]+\n$")

    def test_usage(self):
        for argv in ((), ("invite", "a@b.test"), ("reset-password",)):
            self.assertEqual(self.run_admin(*argv)[0], 64, argv)

    def test_refuses_an_unmigrated_database(self):
        import uuid
        name = "t_" + uuid.uuid4().hex[:12]
        admin_conn = db.connect(dbcase.URL)
        admin_conn.autocommit = True
        admin_conn.execute(f"create schema {name}")
        try:
            url = dbcase.URL + "?options=-csearch_path%3D" + name
            # nothing applied at all, then everything but the newest migration
            for step in ("none", "all but one"):
                if step == "all but one":
                    c = db.connect(dbcase.URL, schema=name)
                    db.migrate(c)
                    newest = max(p.name for p in db.MIGRATIONS.glob("*.sql"))
                    c.execute("delete from schema_migrations where name = %s", (newest,))
                    c.commit()
                    c.close()
                code, out, err = self.run_admin("reset-password", "early", url=url)
                self.assertEqual((code, out), (1, ""), step)
                self.assertEqual(err, "the database needs migrations the web service applies "
                                      "at start; deploy first\n", step)
                tables = admin_conn.execute(
                    "select count(*) from information_schema.tables where table_schema = %s "
                    "and table_name = 'schema_migrations'", (name,)).fetchone()[0]
                self.assertEqual(tables, 0 if step == "none" else 1, step)
            c = db.connect(dbcase.URL, schema=name)
            self.assertEqual(c.execute("select count(*) from users").fetchone()[0], 0)
            c.close()
        finally:
            admin_conn.execute(f"drop schema {name} cascade")
            admin_conn.close()

    def test_reset_password_unknown_user(self):
        code, out, err = self.run_admin("reset-password", "ghost")
        self.assertEqual((code, out, err), (1, "", "No user with that username.\n"))


class Migration004(unittest.TestCase):
    """Existing users keep their rows and files, with a username from their email."""

    def test_usernames_from_emails(self):
        import uuid
        if not dbcase.URL:
            self.skipTest("WT_TEST_DATABASE_URL is not set")
        name = "t_" + uuid.uuid4().hex[:12]
        admin_conn = db.connect(dbcase.URL)
        admin_conn.autocommit = True
        admin_conn.execute(f"create schema {name}")
        try:
            c = db.connect(dbcase.URL, schema=name)
            c.execute("create table schema_migrations (name text primary key, "
                      "applied_at timestamptz not null default now())")
            for p in sorted(db.MIGRATIONS.glob("*.sql")):
                if p.name >= "004":
                    break
                c.execute(p.read_text())
                c.execute("insert into schema_migrations (name) values (%s)", (p.name,))
            emails = ["Ana.B@x.test", "ana.b@y.test", "a+b@z.test", "émile@x.test"]
            for i, e in enumerate(emails):
                c.execute("insert into users (email, wrapped_key, created_at) values "
                          "(%s, 'k', now() + make_interval(secs => %s))", (e, i))
            c.execute("insert into invites (token_hash, user_id, expires_at) select "
                      "sha256(id::text::bytea), id, now() + interval '1 day' from users")
            c.commit()
            db.migrate(c)
            names = [r[0] for r in c.execute("select username from users order by created_at")]
            self.assertEqual(names[0], "ana.b")
            self.assertRegex(names[1], r"^ana\.b-[0-9a-f]{6}$")
            self.assertRegex(names[2], r"^user-[0-9a-f]{8}$")      # "ab" is too short
            self.assertEqual(names[3], "mile")
            for n in names:
                auth.username(n)        # every one is a valid username
            self.assertEqual(len(set(names)), 4)
            self.assertEqual(c.execute("select count(*) from sign_in_links").fetchone()[0], 0)
            self.assertIsNone(c.execute("select max(password_hash) from users").fetchone()[0])
            c.close()
        finally:
            admin_conn.execute(f"drop schema {name} cascade")
            admin_conn.close()
