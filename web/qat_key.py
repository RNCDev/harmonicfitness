"""Give a local QAT walk's throwaway account a Gemini key, with no one pasting it: reads GEMINI_API_KEY from
the repo's root .env (git-ignored; made by the maintainer) and stores it through the app's own Keys API,
as the Keys drawer would. Local servers only: it refuses any address but localhost or 127.0.0.1.

The key is never printed, logged or put on a command line: it's read here and sent only in the PUT's
body. Nothing reads me/.env.

    .venv/bin/python web/qat_key.py --username qat-20261028-2 --password <pw> [--register] [--base http://localhost:8000]

Exit 0 when the key is stored; 1 when the server refused (the status, never the key); 64 on a bad
command (an address that isn't local, no key in .env).
"""
import argparse
import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = ("localhost", "127.0.0.1")


def read_key(path: str) -> str | None:
    """GEMINI_API_KEY's value from a NAME=value file, else None. Reads no other line's value."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                name, eq, value = line.strip().partition("=")
                if eq and name.strip().removeprefix("export ").strip() == "GEMINI_API_KEY":
                    return value.strip().strip("'\"") or None
    except OSError:
        return None
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", required=True)
    ap.add_argument("--register", action="store_true", help="make the account first (a throwaway)")
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--env", default=os.path.join(ROOT, ".env"), help="the file holding GEMINI_API_KEY")
    args = ap.parse_args(argv)

    base = args.base.rstrip("/")
    if urllib.parse.urlparse(base).hostname not in LOCAL:
        print(f"{base} isn't a local server: this only gives keys to a local walk's account.", file=sys.stderr)
        return 64
    key = read_key(args.env)
    if not key:
        print(f"No GEMINI_API_KEY in {os.path.relpath(args.env, ROOT)}.", file=sys.stderr)
        return 64

    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    headers = {"Origin": base, "Content-Type": "application/json"}

    def call(method: str, path: str, body: dict) -> int:
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), method=method, headers=headers)
        try:
            with opener.open(req, timeout=30) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    who = {"username": args.username, "password": args.password}
    status = call("POST", "/api/register" if args.register else "/api/sign-in", who)
    if status not in (200, 201, 204):
        print(f"{'Register' if args.register else 'Sign-in'} answered {status}.", file=sys.stderr)
        return 1
    status = call("PUT", "/api/keys/gemini", {"key": key})
    del key
    if status != 204:
        print(f"Keys answered {status}: the key wasn't stored.", file=sys.stderr)
        return 1
    print(f"Gemini key stored for {args.username} on {base}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
