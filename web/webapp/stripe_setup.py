"""Sets Stripe up to sell the minute packs (maintainer only): a product and a price for each pack in
minutes.PACKS, found again by its lookup key, and the webhook endpoint that tells the site a pack was paid for.
Safe to run again: what's already there is left as it is, and a pack whose price changed gets a new price that
takes over its lookup key (the old one is archived, so nothing sells at it).

    cd web && python -m webapp.stripe_setup --site https://harmonicfitness.fly.dev --env ../.env

The Stripe key comes from STRIPE_SECRET_KEY (or STRIPE_API_SECRET_KEY), in the environment or in the --env file.
A new webhook endpoint's signing secret is shown by Stripe once: it's written to the --env file as
STRIPE_WEBHOOK_SECRET, never printed, and from there set as the site's secret (fly secrets set). Which account
this runs on, test or live, is the key's own."""
import argparse
import os
import sys

from . import billing, minutes

EVENTS = ("checkout.session.completed", "checkout.session.async_payment_succeeded", "charge.refunded")
HOOK = "/api/stripe/webhook"
KEY_NAMES = ("STRIPE_SECRET_KEY", "STRIPE_API_SECRET_KEY")
SECRET_NAME = "STRIPE_WEBHOOK_SECRET"
# Each product's tax code: AI as a service, cloud based, for personal use. Stripe's Managed Payments (on by default:
# Stripe is the merchant of record and settles sales tax and VAT) refuses a Checkout page for a product without one.
TAX_CODE = "txcd_10105001"


class Failed(Exception):
    pass


def read_env(path: str) -> dict[str, str]:
    """NAME=value lines of a file (quotes dropped, comments skipped); empty when there's no such file."""
    out: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                name, eq, value = line.strip().partition("=")
                if eq and name and not name.startswith("#"):
                    out[name.strip()] = value.strip().strip("\"'")
    except FileNotFoundError:
        pass
    return out


def write_env(path: str, name: str, value: str) -> None:
    """Set NAME=value in the file, in place of the line that set it before; every other line is kept."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    lines = [x for x in lines if x.strip().partition("=")[0].strip() != name] + [f"{name}={value}"]
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, path)


def _ok(what: str, status: int, body) -> dict:
    if status != 200 or not isinstance(body, dict):
        why = body.get("error", {}).get("message") if isinstance(body, dict) else None
        raise Failed(f"{what}: Stripe answered {status}" + (f" ({why})" if isinstance(why, str) else ""))
    return body


def pack_product(api, pack: minutes.Pack) -> None:
    """The pack's product, made unless it's there, with TAX_CODE and the pack's minutes in its name (an older one is brought up to date)."""
    want = {"name": f"HarmonicFitness: {pack.label}", "tax_code": TAX_CODE,
            "description": f"{pack.minutes} minutes of recorded workouts. They don't expire."}
    status, body = api("GET", f"/products/{pack.id}")
    if status == 404:
        _ok("making a product", *api("POST", "/products", [("id", pack.id), *want.items()]))
        return
    product = _ok("looking up a product", status, body)
    # an older product gets what changed since: the tax code, or the minutes its name and description give
    stale = [(k, v) for k, v in want.items() if product.get(k) != v]
    if stale:
        _ok("updating the product", *api("POST", f"/products/{pack.id}", stale))


def pack_price(api, pack: minutes.Pack, say) -> None:
    """The pack's product and price, made unless they're there."""
    pack_product(api, pack)
    found = _ok("looking up a price", *api("GET", f"/prices?lookup_keys[]={pack.id}&limit=1")).get("data") or []
    if found and found[0].get("unit_amount") == pack.cents and found[0].get("currency") == "usd" \
            and found[0].get("active"):
        say(f"{pack.label}: already ${pack.cents / 100:.2f}")
        return
    _ok("making a price", *api("POST", "/prices", [
        ("product", pack.id), ("unit_amount", str(pack.cents)), ("currency", "usd"), ("lookup_key", pack.id),
        ("transfer_lookup_key", "true"), ("nickname", pack.label)]))
    if found and found[0].get("id"):   # the price it replaced: nothing sells at it again
        _ok("archiving the old price", *api("POST", f"/prices/{found[0]['id']}", [("active", "false")]))
    say(f"{pack.label}: ${pack.cents / 100:.2f}" + (" (the old price archived)" if found else ""))


def webhook(api, site: str, env_file: str | None, say) -> None:
    """The site's webhook endpoint: made, with its signing secret written to the env file, unless it's there."""
    url = site.rstrip("/") + HOOK
    rows = _ok("listing webhooks", *api("GET", "/webhook_endpoints?limit=100")).get("data") or []
    events = [(f"enabled_events[{n}]", e) for n, e in enumerate(EVENTS)]
    mine = next((w for w in rows if isinstance(w, dict) and w.get("url") == url), None)
    if mine is not None:
        _ok("updating the webhook", *api("POST", f"/webhook_endpoints/{mine['id']}", events))
        say(f"webhook: already at {url} (its signing secret is the one saved when it was made; roll it in "
            "Stripe's dashboard if it's lost)")
        return
    if not env_file:
        raise Failed("a new webhook's signing secret is shown once: name the file to keep it in with --env")
    made = _ok("making the webhook", *api("POST", "/webhook_endpoints", [
        ("url", url), ("description", "HarmonicFitness: minute packs"), *events]))
    secret = made.get("secret")
    if not isinstance(secret, str) or not secret:
        raise Failed("Stripe made the webhook but sent no signing secret: delete it in the dashboard and run again")
    write_env(env_file, SECRET_NAME, secret)
    say(f"webhook: {url}; its signing secret is in {env_file} as {SECRET_NAME} (set it as the site's secret)")


def main(argv=None, env=None, send=None, say=print) -> int:
    ap = argparse.ArgumentParser(prog="python -m webapp.stripe_setup", description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", required=True, help="the site's address, e.g. https://harmonicfitness.fly.dev")
    ap.add_argument("--env", dest="env_file", help="a NAME=value file: read for the Stripe key, and where a new "
                                                   "webhook's signing secret is written")
    ap.add_argument("--no-webhook", action="store_true", help="only the products and prices")
    args = ap.parse_args(argv)
    env = dict(os.environ if env is None else env)
    if args.env_file:
        env = {**read_env(args.env_file), **env}
    key = next((env[n].strip() for n in KEY_NAMES if env.get(n, "").strip()), "")
    if not key:
        print(f"no Stripe key: set {KEY_NAMES[0]} in the environment or in the --env file", file=sys.stderr)
        return 64
    if not args.site.startswith("https://"):
        print("--site must be the site's https address", file=sys.stderr)
        return 64
    client = billing.Client(key, "", args.site, **({"send": send} if send else {}))
    try:
        say("Stripe account: " + ("live" if key.startswith(("sk_live_", "rk_live_")) else "test mode"))
        for pack in minutes.PACKS:
            pack_price(client._api, pack, say)
        if not args.no_webhook:
            webhook(client._api, args.site, args.env_file, say)
    except (Failed, billing.Unavailable) as e:
        print(str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
