"""What's left on each web voice service's account: `./harmonicfitness balances [--json]`.

Fish Audio reports its API credit in US dollars and ElevenLabs this period's credits used against the plan's
limit; Gemini and Inworld report nothing through their APIs, so their rows name the billing page instead. Only a
service with a key here is asked, with one GET that spends nothing; a refusal is that row's answer, never a stop.

--json prints one object, {service: row}, each row with: name, billing_page, set (a key here), reports (the
service can say), and once asked: ok, then usd (Fish), or used, limit and resets (ElevenLabs; resets a Unix
time or null), or, when it refused, kind (auth, billing, quota, bad_request, unavailable) and message."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cloud  # noqa: E402
import errors  # noqa: E402
import keys  # noqa: E402
from redact import scrub  # noqa: E402


def balances():
    """{service: row} in services.toml's order, as --json prints it."""
    out = {}
    for service, s in cloud.services().items():
        module = cloud.service_module(service)
        row = {"name": s["name"], "billing_page": s["billing_page"], "set": keys.is_set(service),
               "reports": hasattr(module, "balance")}
        if row["set"] and row["reports"]:
            try:
                row.update(module.balance(), ok=True)
            except cloud.ServiceError as e:
                row.update(ok=False, kind=e.kind, message=scrub(e.message))
            except keys.BadKey as e:
                row.update(ok=False, kind="auth", message=scrub(str(e)))
        out[service] = row
    return out


def line(row):
    """One row as words."""
    if not row["set"]:
        return "no key"
    if not row["reports"]:
        return f"not reported through its API; see {row['billing_page']}"
    if not row["ok"]:
        return f"couldn't ask ({row['message']}); see {row['billing_page']}"
    if "usd" in row:
        return f"${row['usd']:,.2f} of API credit"
    return f"{row['used']:,} of {row['limit']:,} credits used this period"


def main(argv=None):
    import cli
    ap = cli.ArgumentParser(prog="harmonicfitness balances", description=__doc__)
    ap.add_argument("--json", action="store_true", help="print one JSON object (its keys above)")
    args = ap.parse_args(argv)
    rows = balances()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False))
    else:
        for service, row in rows.items():
            print(f"{service:10}: {line(row)}")
    return errors.OK


if __name__ == "__main__":
    import cli
    sys.exit(cli.run(main))
