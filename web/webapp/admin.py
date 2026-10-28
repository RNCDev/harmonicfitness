"""Maintainer command: python -m webapp.admin reset-password <username>.

For someone who forgot their password: clears it and prints a one-time sign-in link (24 hours),
and nothing else on stdout, so it can be piped. Opening the link signs them in, and the app asks
for a new password. Never migrates: the web service applies migrations at start, and this refuses
a database that lacks any.
"""
import os
import sys

from . import auth, config, db


def main(argv=None, env=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] != "reset-password":
        print("usage: python -m webapp.admin reset-password <username>", file=sys.stderr)
        return 64
    try:
        settings = config.load(os.environ if env is None else env)
        name = auth.username(args[1])
        conn = db.connect(settings.database_url)
        try:
            if db.missing(conn):
                print("the database needs migrations the web service applies at start; deploy first",
                      file=sys.stderr)
                return 1
            try:
                print(auth.reset_link(conn, settings, name).url)
            except LookupError:
                print("No user with that username.", file=sys.stderr)
                return 1
        finally:
            conn.close()
    except (config.ConfigError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
