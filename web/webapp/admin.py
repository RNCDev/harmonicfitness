"""Maintainer commands: python -m webapp.admin reset-password <username>, and grant <username> <minutes>.

reset-password, for someone who forgot their password: clears it and prints a one-time sign-in link (24 hours),
and nothing else on stdout, so it can be piped. Opening the link signs them in, and the app asks
for a new password. Never migrates: the web service applies migrations at start, and this refuses
a database that lacks any.

grant, on a site that runs on minutes: adds that many to the account (a gift, or a part refund settled by hand)
and prints the new balance.
"""
import os
import secrets
import sys

from . import auth, config, db, minutes

USAGE = "usage: python -m webapp.admin reset-password <username> | grant <username> <minutes>"
GIFT = "Minutes added by the site"


def _grant(conn, name: str, count: int) -> int | None:
    """Add `count` minutes to the account called `name`; the new balance, or None when there's no such account."""
    row = conn.execute("select id from users where username = %s", (name,)).fetchone()
    if row is None:
        return None
    minutes.grant(conn, row[0], count, f"admin-{secrets.token_hex(8)}", GIFT)
    return minutes.balance(conn, row[0])


def main(argv=None, env=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    grant = len(args) == 3 and args[0] == "grant" and args[2].isdigit() and 0 < int(args[2]) <= 10000
    if not grant and (len(args) != 2 or args[0] != "reset-password"):
        print(USAGE, file=sys.stderr)
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
            if grant:
                now = _grant(conn, name, int(args[2]))
                if now is None:
                    conn.rollback()
                    print("No user with that username.", file=sys.stderr)
                    return 1
                conn.commit()
                print(now)
                return 0
            try:
                link = auth.reset_link(conn, settings, name)
            except LookupError:
                conn.rollback()
                print("No user with that username.", file=sys.stderr)
                return 1
            conn.commit()
            print(link.url)
        finally:
            conn.close()
    except (config.ConfigError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
