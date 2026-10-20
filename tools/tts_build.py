#!/usr/bin/env python3
"""Lint a segmented workout draft and export a clean, TTS-ready text file.

Draft format: each segment starts with a marker line
    @@ <seconds> | <label>
followed by the spoken text. Markers are stripped on export.

Usage:
    python tts_build.py draft.txt --wpm 140 --out "Workout 2026-10-18.txt"
    python tts_build.py draft.txt --wpm 140 --out final.txt --force   # export despite issues
"""
import argparse
import re
import sys

MARKER = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*)$")

# Characters a reader may announce or mispronounce.
FORBIDDEN_CHARS = set("#*_`|<>[]{}/\\@&%+=~^$°•→×")
ALLOWED_NON_ASCII = set("’‘“”…—–é")  # curly quotes, ellipsis, dashes, common accent

ABBREVIATIONS = [
    r"lbs?", r"kgs?", r"secs?", r"mins?", r"hrs?", r"e\.g\.", r"i\.e\.",
    r"vs\.?", r"etc\.", r"approx\.?", r"RPM", r"RPE", r"BPM", r"mph", r"km", r"Dr\.",
    r"St\.", r"Q[1-4]", r"YoY", r"QoQ", r"bps", r"w/",
]
ABBREV_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(ABBREVIATIONS) + r")(?![A-Za-z])")

YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
DIGIT_RE = re.compile(r"\d")
MD_LINE_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>\s|\|)")
SSML_RE = re.compile(r"<[^>]+>")


def parse(text):
    segments, current = [], None
    for lineno, line in enumerate(text.splitlines(), 1):
        m = MARKER.match(line.strip())
        if m:
            current = {"seconds": int(m.group(1)), "label": m.group(2).strip(),
                       "lines": [], "start": lineno}
            segments.append(current)
        elif current is None:
            if line.strip():
                raise SystemExit(f"Line {lineno}: text before the first @@ marker.")
        else:
            current["lines"].append((lineno, line))
    if not segments:
        raise SystemExit("No @@ segment markers found.")
    return segments


def lint_line(lineno, line):
    issues = []
    if MD_LINE_RE.match(line):
        issues.append("markdown or list syntax at line start")
    if SSML_RE.search(line):
        issues.append("tag markup (readers may speak it)")
    bad = sorted({c for c in line if c in FORBIDDEN_CHARS})
    if bad:
        issues.append("forbidden characters: " + " ".join(bad))
    odd = sorted({c for c in line if ord(c) > 127 and c not in ALLOWED_NON_ASCII})
    if odd:
        issues.append("non-ASCII characters (emoji or symbols?): " + " ".join(odd))
    stripped = YEAR_RE.sub("", line)
    if DIGIT_RE.search(stripped):
        issues.append("digits outside a four-digit year: spell numbers out")
    for m in ABBREV_RE.finditer(line):
        issues.append(f"abbreviation '{m.group(0)}': spell it out")
    if re.search(r"\.\.\.\.", line):
        issues.append("more than three dots")
    return [f"  line {lineno}: {i}" for i in issues]


def word_count(lines):
    return sum(len(re.findall(r"[A-Za-z0-9’']+(?:-[A-Za-z0-9’']+)*", l)) for _, l in lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--wpm", type=float, default=140)
    ap.add_argument("--tolerance", type=float, default=0.08)
    ap.add_argument("--out", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        segments = parse(f.read())

    problems = 0
    total_words, total_seconds = 0, 0
    print(f"{'#':>3} {'secs':>5} {'target':>6} {'words':>5} {'diff':>6}  label")
    for i, seg in enumerate(segments, 1):
        target = round(args.wpm * seg["seconds"] / 60)
        words = word_count(seg["lines"])
        diff = (words - target) / target if target else 0
        flag = ""
        if abs(diff) > args.tolerance:
            flag = "  <-- " + ("too long" if diff > 0 else "too short")
            problems += 1
        print(f"{i:>3} {seg['seconds']:>5} {target:>6} {words:>5} {diff:>+6.0%}  {seg['label']}{flag}")
        for lineno, line in seg["lines"]:
            for msg in lint_line(lineno, line):
                print(msg)
                problems += 1
        total_words += words
        total_seconds += seg["seconds"]

    est = total_words / args.wpm
    print(f"\nPlanned {total_seconds/60:.1f} min | {total_words} words | "
          f"estimated {est:.1f} min at {args.wpm:g} wpm")

    if problems and not args.force:
        print(f"\n{problems} issue(s). Fix and rerun (or --force). Nothing exported.")
        sys.exit(1)

    paragraphs, buf = [], []
    for seg in segments:
        for _, line in seg["lines"] + [(0, "")]:
            if line.strip():
                buf.append(line.strip())
            elif buf:
                paragraphs.append(" ".join(buf))
                buf = []
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(paragraphs) + "\n")
    print(f"\nExported {len(paragraphs)} paragraphs to {args.out}"
          + (f" despite {problems} issue(s)" if problems else ""))


if __name__ == "__main__":
    main()
