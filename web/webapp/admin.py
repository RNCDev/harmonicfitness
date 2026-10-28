"""Maintainer commands: python -m webapp.admin invite|login-link <email>.

Prints the link and nothing else on stdout, so it can be piped. Never migrates: the web service
applies migrations at start, and these commands refuse a database that lacks any.
"""
import os
import sys

from . import auth, config, db


def main(argv=None, env=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in ("invite", "login-link"):
        print("usage: python -m webapp.admin invite|login-link <email>", file=sys.stderr)
        return 64
    cmd, raw = args
    try:
        settings = config.load(os.environ if env is None else env)
        email = auth._email(raw)
        conn = db.connect(settings.database_url)
        try:
            if db.missing(conn):
                print("the database needs migrations the web service applies at start; deploy first",
                      file=sys.stderr)
                return 1
            if cmd == "login-link":
                row = conn.execute("select 1 from users where email = %s", (email,)).fetchone()
                conn.rollback()
                if row is None:
                    print("No user with that email.", file=sys.stderr)
                    return 1
            print(auth.invite(conn, settings, email))
        finally:
            conn.close()
    except (config.ConfigError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
