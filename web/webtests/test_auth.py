import os
import sys

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
    return link.rsplit("/invite/", 1)[1]


class Auth(DBCase):
    def setUp(self):
        self.s = settings()

    def test_invite_creates_seeded_user(self):
        link = auth.invite(self.conn, self.s, "  New@Example.TEST ")
        self.assertTrue(link.startswith("https://wt.test/invite/"))
        uid = self.conn.execute("select id from users where email = 'new@example.test'").fetchone()[0]
        uk = store.user_key(self.conn, self.s, uid)
        self.assertIn("profile.md", store.read_all(self.conn, uk))

    def test_new_users_key_is_bound_to_its_id(self):
        from webapp import crypto
        auth.invite(self.conn, self.s, "bound@example.test")
        uid, wrapped, version = self.conn.execute(
            "select id, wrapped_key, key_version from users where email = 'bound@example.test'"
        ).fetchone()
        self.conn.rollback()
        self.assertEqual(version, 1)
        crypto.unwrap(MASTER, bytes(wrapped), uid, version)
        other, = self.conn.execute("select gen_random_uuid()").fetchone()
        self.conn.rollback()
        with self.assertRaises(crypto.Tampered):
            crypto.unwrap(MASTER, bytes(wrapped), other, version)

    def test_bad_emails(self):
        for bad in ("", "nobody", "@x.test", "a@", "a@b@c"):
            with self.assertRaises(ValueError):
                auth.invite(self.conn, self.s, bad)

    def test_invite_is_single_use(self):
        t = token_of(auth.invite(self.conn, self.s, "once@example.test"))
        self.assertTrue(auth.redeem(self.conn, self.s, t))
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, t)

    def test_unknown_refused(self):
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, "nope")

    def test_expired_invite_refused(self):
        t = token_of(auth.invite(self.conn, self.s, "old@example.test"))
        self.conn.execute("update invites set expires_at = now() - interval '1 minute'")
        self.conn.commit()
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, t)

    def test_tokens_stored_hashed(self):
        t = token_of(auth.invite(self.conn, self.s, "hash@example.test"))
        st = auth.redeem(self.conn, self.s, t)
        for tok, table in ((t, "invites"), (st, "sessions")):
            for (h,) in self.conn.execute(f"select token_hash from {table}").fetchall():
                self.assertNotIn(tok.encode(), bytes(h))
                self.assertEqual(len(bytes(h)), 32)

    def test_device_link_signs_in_same_user(self):
        uid, _ = self.make_user()
        t = token_of(auth.device_link(self.conn, self.s, uid).url)
        st = auth.redeem(self.conn, self.s, t)
        self.assertEqual(auth.user_for(self.conn, self.s, st), uid)
        t2 = token_of(auth.device_link(self.conn, self.s, uid).url)
        self.conn.execute("update invites set expires_at = now() - interval '1 second' "
                          "where used_at is null")
        self.conn.commit()
        with self.assertRaises(auth.Refused):
            auth.redeem(self.conn, self.s, t2)

    def test_device_link_lasts_ten_minutes(self):
        uid, _ = self.make_user()
        link = auth.device_link(self.conn, self.s, uid)
        mins = self.conn.execute(
            "select extract(epoch from expires_at - now())/60 from invites "
            "where user_id = %s", (uid,)).fetchone()[0]
        self.assertTrue(9 < mins <= 10)
        stored = self.conn.execute("select expires_at from invites where user_id = %s",
                                   (uid,)).fetchone()[0]
        self.conn.rollback()
        self.assertEqual(link.expires_at, stored)
        self.assertTrue(link.url.startswith("https://wt.test/invite/"))

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

    def test_reinvite_keeps_context(self):
        auth.invite(self.conn, self.s, "twice@example.test")
        uid = self.conn.execute("select id from users where email = 'twice@example.test'").fetchone()[0]
        uk = store.user_key(self.conn, self.s, uid)
        before = store.read_all(self.conn, uk)
        store.put(self.conn, uk, "profile.md", b"mine")
        self.conn.commit()
        auth.invite(self.conn, self.s, "TWICE@example.test")
        n = self.conn.execute("select count(*) from users where email = 'twice@example.test'").fetchone()[0]
        self.assertEqual(n, 1)
        after = store.read_all(self.conn, store.user_key(self.conn, self.s, uid))
        self.assertEqual(after["profile.md"][1], b"mine")
        self.assertEqual(set(after), set(before))


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

    def test_invite_prints_only_the_link(self):
        code, out, err = self.run_admin("invite", "adm@example.test")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"^https://wt\.test/invite/[A-Za-z0-9_-]+\n$")
        code, out, err = self.run_admin("login-link", "ADM@example.test")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"^https://wt\.test/invite/")

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
                code, out, err = self.run_admin("invite", "early@example.test", url=url)
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

    def test_login_link_unknown_email(self):
        code, out, err = self.run_admin("login-link", "ghost@example.test")
        self.assertEqual((code, out), (1, ""))
        self.assertTrue(err)
