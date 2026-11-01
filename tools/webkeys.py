"""Send the keys in me/.env to the listener's key store on the web app (./harmonicfitness keys upload).

Signs in as the listener, as pull and sync do (HARMONIC_USERNAME and HARMONIC_PASSWORD), asks which keys the app
already holds (never their values: the app shows none), and sends each key it lacks through the app's own Keys
endpoint, where it's stored encrypted. A key the app already has stays unless --replace. The voice keys
(services.toml) and, when me/.env holds them, the writers' (ANTHROPIC_API_KEY, OPENAI_API_KEY) go; nothing else
does. No value is printed: only each key's name and what happened to it.

    ./harmonicfitness keys upload --dry-run      # what would go
    ./harmonicfitness keys upload                # send the keys the app lacks
    ./harmonicfitness keys upload --replace      # and replace the ones it has
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import keys  # noqa: E402
import webpull  # noqa: E402


def local_keys(only=None):
    """({id: value} for every key set here, {id: why} for one that can't be read), in services.toml's order, then
    the writers'. `only` limits them to those ids; an unknown one is a UsageError."""
    ids = list(keys.SERVICE_VARS) + list(keys.WRITER_VARS)
    wanted = [s.strip() for s in only.split(",") if s.strip()] if only else ids
    unknown = [s for s in wanted if s not in ids]
    if unknown:
        raise errors.UsageError(f"No key called {', '.join(unknown)}: the keys are {', '.join(ids)}.")
    found, bad = {}, {}
    for s in [i for i in ids if i in wanted]:
        try:
            value = keys.get(s) if s in keys.SERVICE_VARS else keys.writer_key(s)
        except keys.BadKey as e:
            bad[s] = str(e)
            continue
        if value:
            found[s] = value
    return found, bad


def upload(account, only=None, replace=False, dry_run=False, app=None):
    """{sent, would_send, kept, refused: {id: why}, bad: {id: why}, none: bool}. Signs in, and always signs out."""
    found, bad = local_keys(only)
    out = {"sent": [], "would_send": [], "kept": [], "refused": {}, "bad": bad, "none": not found}
    if not found:
        return out
    if not account.get("HARMONIC_USERNAME") or not account.get("HARMONIC_PASSWORD"):
        raise errors.UsageError("Put HARMONIC_USERNAME and HARMONIC_PASSWORD (your web app sign-in) in me/.env first: "
                                "./harmonicfitness keys open.")
    app = app or webpull.App(webpull.base_url(account.get("HARMONIC_URL")))
    app.sign_in(account["HARMONIC_USERNAME"], account["HARMONIC_PASSWORD"])
    try:
        _, body = app.get("/api/keys")
        there = {row["service"] for row in json.loads(body) if row.get("set")}
        for s, value in found.items():
            if s in there and not replace:
                out["kept"].append(s)
            elif dry_run:
                out["would_send"].append(s)
            else:
                status, _, answer = app._request("PUT", f"/api/keys/{s}", {"key": value})
                if status == 204:
                    out["sent"].append(s)
                else:
                    detail = app._detail(answer)
                    out["refused"][s] = (detail if status != 404 else "the web app doesn't take this key") \
                        or f"HTTP {status}"
    finally:
        app.sign_out()
    return out


def main(argv=None):
    import cli
    ap = cli.ArgumentParser(prog="harmonicfitness keys upload", description=__doc__,
                            formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("--replace", action="store_true", help="also replace a key the web app already has")
    ap.add_argument("--only", help="only these, comma-separated (such as fish,openrouter)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be sent; send nothing")
    args = ap.parse_args(argv)
    return report(upload(keys.web_account(), only=args.only, replace=args.replace, dry_run=args.dry_run))


def report(got):
    """Print what happened, a line a key; exit 1 when one was refused or couldn't be read."""
    if got["none"] and not got["bad"]:
        print("No keys in me/.env to send (./harmonicfitness keys lists them).")
    for s in got["sent"]:
        print(f"{s:10}: sent to the web app")
    for s in got["would_send"]:
        print(f"{s:10}: would be sent")
    for s in got["kept"]:
        print(f"{s:10}: the web app already has one; kept (--replace sends this one)")
    for s, why in got["refused"].items():
        print(f"{s:10}: refused: {why}")
    for s, why in got["bad"].items():
        print(f"{s:10}: not sent: {why}")
    return errors.ISSUES if got["refused"] or got["bad"] else errors.OK


if __name__ == "__main__":
    import cli
    sys.exit(cli.run(main))
