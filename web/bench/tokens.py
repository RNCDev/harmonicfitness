"""Where a bench run's tokens went: `.venv/bin/python web/bench/tokens.py <run-dir>... [--json]`.

Reads each run's requests.jsonl (run_one.py writes it) and prints, per run, the requests by who asked (the agent's
own, by phase and turn, and each writer), with tokens in (and how many of them were read from the provider's
cache), out (and how many of those were thinking), the web searches, and an estimated cost at the rates below.

The rates are list prices per million tokens, checked 2026-11-10: Opus 5.5 from OpenRouter's model list (what the
run paid through it), Gemini 3.8 Flash from Google's own price list for a direct key. A web search is a flat fee
each. Each is approximate; OpenRouter's own figure, when the response carries one, is printed beside it.
"""
import json
import os
import sys
from collections import defaultdict

# dollars per million tokens: input, cached input read, output (thinking is billed as output), and a search each
RATES = {
    "claude-opus-5.5": {"in": 4.00, "cached": 0.20, "cache_write": 5.00, "out": 20.00, "search": 0.010},
    "gemini-3.8-flash": {"in": 0.75, "cached": 0.075, "cache_write": 0.0, "out": 3.75, "search": 0.014},
}


def rate_for(model: str | None) -> dict:
    for name, r in RATES.items():
        if model and name in model:
            return r
    return RATES["gemini-3.8-flash"]


def thinking(usage: dict) -> int:
    d = usage.get("details") or {}
    return int(d.get("thoughts_tokens") or d.get("reasoning_tokens") or 0)


def searches(row: dict) -> int:
    """Gemini's searches come back as calls in the response; OpenRouter's (on Claude) only as a count beside it."""
    server = ((row.get("provider_details") or {}).get("server_tool_use") or {}).get("web_search_requests")
    return int(server or (row.get("parts") or {}).get("NativeToolCallPart", 0))


def cost(row: dict) -> float:
    u, r = row.get("usage") or {}, rate_for(row.get("model"))
    cached = u.get("cache_read_tokens") or 0
    write = u.get("cache_write_tokens") or 0
    fresh = max(0, (u.get("input_tokens") or 0) - cached - write)
    out = u.get("output_tokens") or 0   # thinking included, on both providers (pydantic-ai sums Gemini's)
    return (fresh * r["in"] + cached * r["cached"] + write * r["cache_write"] + out * r["out"]) / 1e6 \
        + searches(row) * r["search"]


def group(row: dict) -> str:
    if row["who"] != "agent":
        return f"room: {row['who']}"
    return f"agent turn {row.get('turn')}: {row.get('phase') or '(start)'}"


def load(run: str) -> list[dict]:
    with open(os.path.join(run, "requests.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def table(run: str) -> dict:
    rows = load(run)
    by = defaultdict(lambda: defaultdict(float))
    order = []
    for r in rows:
        g = group(r)
        if g not in by:
            order.append(g)
        u = r.get("usage") or {}
        b = by[g]
        b["requests"] += 1
        b["in"] += u.get("input_tokens") or 0
        b["cached"] += u.get("cache_read_tokens") or 0
        b["out"] += u.get("output_tokens") or 0
        b["thinking"] += thinking(u)
        b["searches"] += searches(r)
        b["seconds"] += r.get("seconds") or 0
        b["usd"] += cost(r)
        b["or_usd"] += float(((r.get("provider_details") or {}).get("cost")) or 0)
        b["errors"] += 1 if r.get("error") else 0
    total = defaultdict(float)
    for b in by.values():
        for k, v in b.items():
            total[k] += v
    return {"run": run, "groups": [(g, dict(by[g])) for g in order], "total": dict(total)}


def show(t: dict) -> str:
    head = f"{'':38}{'req':>4}{'in':>10}{'cached':>9}{'out':>8}{'think':>8}{'srch':>5}{'s':>7}{'$ est':>8}"
    lines = [t["run"], head]
    for g, b in t["groups"] + [("total", t["total"])]:
        lines.append(f"{g[:37]:38}{b['requests']:>4.0f}{b['in']:>10,.0f}{b['cached']:>9,.0f}{b['out']:>8,.0f}"
                     f"{b['thinking']:>8,.0f}{b['searches']:>5.0f}{b['seconds']:>7.0f}{b['usd']:>8.3f}")
    if t["total"].get("or_usd"):
        lines.append(f"OpenRouter's own figure: ${t['total']['or_usd']:.3f}")
    return "\n".join(lines)


if __name__ == "__main__":
    runs = [a for a in sys.argv[1:] if a != "--json"]
    out = [table(r) for r in runs]
    print(json.dumps(out, indent=1) if "--json" in sys.argv else "\n\n".join(show(t) for t in out))
