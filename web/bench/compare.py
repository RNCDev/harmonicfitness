"""The bench's gate: does a candidate write as well as the baseline, for no more?

  .venv/bin/python web/bench/compare.py <baseline-label> <candidate-label>      (each a folder under .bench/out/)

Prints, per label, the medians of writing cost (tokens.cost over every request of a run), requests, input tokens and
seconds from the brief to the price, and how many runs fail a quality check; then a last line, `GATE: pass` or
`GATE: fail (<reasons>)`. It passes only when every candidate run is compliant and its median writing cost is no
higher than the baseline's. A run is compliant when it is priced, its final lint is clean, and the opening, story
names, voice and never-bring-up checks of summarize.py find nothing.
"""
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import summarize  # noqa: E402
import tokens  # noqa: E402

MIN_COMPLETED = 3
PROVIDER_ERROR = re.compile(r"status_code: (?:5\d\d|429)\b")
CHECKS = ("opening", "not_in_notes", "one_voice", "never_said")


def run_row(run_dir):
    """One run's facts, and its cost, requests and input tokens from requests.jsonl; None when it never finished."""
    path = os.path.join(run_dir, "result.json")
    if not os.path.exists(path):
        return None
    row, _ = summarize.facts(path)
    reqs = tokens.load(run_dir) if os.path.exists(os.path.join(run_dir, "requests.jsonl")) else []
    row["cost"] = sum(tokens.cost(q) for q in reqs)
    row["requests"] = len(reqs)
    row["input"] = sum((q.get("usage") or {}).get("input_tokens") or 0 for q in reqs)
    return row


def load(label):
    d = os.path.join(summarize.OUT, label)
    runs = sorted((n for n in os.listdir(d) if os.path.isdir(os.path.join(d, n))), key=lambda x: int(x) if x.isdigit() else 0)
    return [r for r in (run_row(os.path.join(d, n)) for n in runs) if r]


def problems(row):
    """What keeps a run from being compliant, in words."""
    out = []
    if not row.get("priced"):
        out.append("not priced")
    if not row.get("lint_clean"):
        out.append("lint not clean")
    out += [f"{k}: {row[k]}" for k in CHECKS if row.get(k)]
    return out


def provider_error(row):
    """True when the run ended on the model provider's 5xx or 429 before any price: not completed, not non-compliant."""
    return not row.get("priced") and bool(PROVIDER_ERROR.search(row.get("error") or ""))


def median(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return statistics.median(vals) if vals else 0.0


def gate(baseline, candidate):
    baseline = [r for r in baseline if not provider_error(r)]
    done = [r for r in candidate if not provider_error(r)]
    errors = len(candidate) - len(done)
    note = f", {errors} provider error{'s' if errors != 1 else ''}" if errors else ""
    reasons = []
    for i, r in enumerate(candidate, 1):
        if not provider_error(r):
            reasons += [f"run {i} {p}" for p in problems(r)]
    if len(done) < MIN_COMPLETED:
        reasons.append(f"only {len(done)} completed runs, {MIN_COMPLETED} needed")
    else:
        if median(done, "cost") > median(baseline, "cost"):
            reasons.append(f"median cost ${median(done, 'cost'):.3f} above ${median(baseline, 'cost'):.3f}")
        if median(done, "reviews") > median(baseline, "reviews"):
            reasons.append(f"median review rounds {median(done, 'reviews'):g} above {median(baseline, 'reviews'):g}")
    return f"GATE: pass ({len(done)} completed{note})" if not reasons else f"GATE: fail ({'; '.join(reasons)}{note})"


def show(label, rows):
    done = [r for r in rows if not provider_error(r)]
    lines = [f"## {label}  ({len(rows)} runs, {len(done)} completed)"]
    lines += [f"  run {r['run']} not completed: {r['error']}" for r in rows if provider_error(r)]
    rows = done
    for name, key, fmt in (("writing cost $", "cost", "{:.3f}"), ("requests", "requests", "{:.0f}"),
                           ("input tokens", "input", "{:,.0f}"), ("seconds, brief to price", "from_brief", "{:.0f}"),
                           ("review rounds", "reviews", "{:g}")):
        lines.append(f"  median {name:25}{fmt.format(median(rows, key))}")
    lines.append(f"  runs failing a check     {sum(1 for r in rows if problems(r))} of {len(rows)}")
    return "\n".join(lines)


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 64
    base, cand = load(argv[0]), load(argv[1])
    print(show(argv[0], base), show(argv[1], cand), gate(base, cand), sep="\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
