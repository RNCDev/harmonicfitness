#!/usr/bin/env python3
"""Lint a segmented workout draft and export a clean transcript.

Draft format: each segment starts with a marker line
    @@ <seconds> | <label>
followed by the spoken text. Markers are stripped on export. Inside the text,
[pause 3s] inserts that much silence (also [pause 500ms]; at most ten seconds).

With --voice, each segment's spoken length is predicted for that VoiceStudio
voice (see voices.py) and checked against its planned seconds. Without it, word
count against --wpm is the rough fallback.

Usage:
    python3 tts_build.py draft.txt --voice demo0001 --out "Workout 2026-10-18.txt"
    python3 tts_build.py draft.txt --wpm 170 --out final.txt --force   # export despite issues
"""
import argparse
import re
import sys

MARKER = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*)$")
PAUSE_RE = re.compile(r"\[\s*pause(?:\s+(\d+(?:\.\d+)?)\s*(ms|s)?)?\s*\]", re.IGNORECASE)
PAUSE_DEFAULT, PAUSE_MAX = 0.35, 10.0   # seconds, as in VoiceStudio's pause dialect
PARAGRAPH_GAP = 0.35                    # least silence between paragraphs within a segment
MAX_CLIP = 22.0                         # longest a paragraph may speak, in seconds

# Characters a voice may announce or mispronounce.
FORBIDDEN_CHARS = set("#*_`|<>[]{}/\\@&%+=~^$°•→×")
ALLOWED_NON_ASCII = set("’‘“”…—–é")  # curly quotes, ellipsis, dashes, common accent

ABBREVIATIONS = [
    r"lbs?", r"kgs?", r"secs?", r"mins?", r"hrs?", r"e\.g\.", r"i\.e\.",
    r"vs\.?", r"etc\.", r"approx\.?", r"RPM", r"RPE", r"BPM", r"mph", r"km", r"Dr\.",
    r"St\.", r"Q[1-4]", r"YoY", r"QoQ", r"bps", r"w/",
]
ABBREV_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(ABBREVIATIONS) + r")(?![A-Za-z])")

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


def paragraphs(lines):
    out, buf = [], []
    for _, line in lines + [(0, "")]:
        if line.strip():
            buf.append(line.strip())
        elif buf:
            out.append(" ".join(buf))
            buf = []
    return out


def spans(paragraph):
    """Split a paragraph at [pause] markers: [(text, seconds of silence after)].
    Text may be empty (a leading pause). One source of truth for lint and render."""
    out, last = [], 0
    for m in PAUSE_RE.finditer(paragraph):
        num, unit = m.group(1), (m.group(2) or "").lower()
        secs = PAUSE_DEFAULT if num is None else float(num) / (1 if unit == "s" else 1000)
        text = paragraph[last:m.start()].strip()
        if not text and out:
            out[-1] = (out[-1][0], min(out[-1][1] + secs, PAUSE_MAX))
        else:
            out.append((text, min(secs, PAUSE_MAX)))
        last = m.end()
    tail = paragraph[last:].strip()
    if tail or not out:
        out.append((tail, 0.0))
    return out


def plan(seg):
    """A segment as paragraphs of spans, exactly as render.py will voice it."""
    return [spans(p) for p in paragraphs(seg["lines"])]


def spoken_seconds(seg, voice, speed=None):
    from voices import clip_seconds
    paras = plan(seg)
    return sum(clip_seconds(text, voice, speed) if text else 0.0
               for para in paras for text, _ in para) \
        + sum(pause for para in paras for _, pause in para) \
        + PARAGRAPH_GAP * max(len(paras) - 1, 0)


def lint_line(lineno, line):
    issues = []
    if MD_LINE_RE.match(line):
        issues.append("markdown or list syntax at line start")
    line = PAUSE_RE.sub(" ", line)
    if SSML_RE.search(line):
        issues.append("tag markup (the voice may speak it)")
    bad = sorted({c for c in line if c in FORBIDDEN_CHARS})
    if bad:
        issues.append("forbidden characters: " + " ".join(bad))
    odd = sorted({c for c in line if ord(c) > 127 and c not in ALLOWED_NON_ASCII})
    if odd:
        issues.append("non-ASCII characters (emoji or symbols?): " + " ".join(odd))
    if DIGIT_RE.search(line):
        issues.append("digits: spell numbers and years out")
    for m in ABBREV_RE.finditer(line):
        issues.append(f"abbreviation '{m.group(0)}': spell it out")
    if re.search(r"\.\.\.\.", line):
        issues.append("more than three dots")
    return [f"  line {lineno}: {i}" for i in issues]


def word_count(lines):
    return sum(len(re.findall(r"[A-Za-z0-9’']+(?:-[A-Za-z0-9’']+)*", PAUSE_RE.sub(" ", l)))
               for _, l in lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", help="VoiceStudio voice id or name: check predicted spoken seconds")
    ap.add_argument("--speed", type=float, default=None, help="the speed factor the render will use")
    ap.add_argument("--wpm", type=float, default=185, help="word guide without --voice, words per minute")
    ap.add_argument("--min-fill", type=float, default=0.90, help="below this, the segment has dead air")
    ap.add_argument("--max-fill", type=float, default=1.00, help="above this, the segment overruns")
    ap.add_argument("--tolerance", type=float, default=0.08, help="word-count tolerance without --voice")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        segments = parse(f.read())

    voice = None
    if args.voice:
        from voices import lookup, pace
        voice = lookup(args.voice)
        voice_pace, exact = pace(voice)

    problems = 0
    total_words, total_seconds, total_spoken = 0, 0, 0.0
    wpm = args.wpm
    if voice:
        spokens = [spoken_seconds(seg, voice, args.speed) for seg in segments]
        # The rate this voice actually speaks this draft at, so the guide column
        # says how many words each segment wants with this voice.
        if sum(spokens):
            wpm = sum(word_count(seg["lines"]) for seg in segments) / sum(spokens) * 60
        print(f"{'#':>3} {'secs':>5} {'words':>5} {'guide':>5} {'spoken':>6} {'fill':>5}  label")
    else:
        print(f"{'#':>3} {'secs':>5} {'target':>6} {'words':>5} {'diff':>6}  label")
    for i, seg in enumerate(segments, 1):
        guide = round(wpm * seg["seconds"] / 60)
        words = word_count(seg["lines"])
        flag = ""
        if voice:
            spoken = spokens[i - 1]
            fill = spoken / seg["seconds"]
            if fill > args.max_fill:
                flag = f"  <-- overruns by {spoken - seg['seconds']:.1f}s"
            elif fill < args.min_fill:
                flag = f"  <-- {seg['seconds'] - spoken:.1f}s of dead air"
            total_spoken += spoken
            print(f"{i:>3} {seg['seconds']:>5} {words:>5} {guide:>5} {spoken:>6.1f} {fill:>5.0%}  {seg['label']}{flag}")
            # OmniVoice splits a clip over thirty seconds into pieces and stitches
            # them, and the seams can glitch. Keep every clip comfortably under.
            from voices import clip_seconds
            for para in plan(seg):
                for text, _ in para:
                    secs = clip_seconds(text, voice, args.speed) if text else 0.0
                    if secs > MAX_CLIP:
                        print(f"  paragraph \"{' '.join(text.split()[:6])}...\" speaks for {secs:.0f}s; "
                              f"split it into paragraphs under {MAX_CLIP:.0f}s")
                        problems += 1
        else:
            diff = (words - guide) / guide if guide else 0
            if abs(diff) > args.tolerance:
                flag = "  <-- " + ("too long" if diff > 0 else "too short")
            print(f"{i:>3} {seg['seconds']:>5} {guide:>6} {words:>5} {diff:>+6.0%}  {seg['label']}{flag}")
        problems += bool(flag)
        for lineno, line in seg["lines"]:
            for msg in lint_line(lineno, line):
                print(msg)
                problems += 1
        total_words += words
        total_seconds += seg["seconds"]

    summary = f"\nPlanned {total_seconds / 60:.1f} min | {total_words} words"
    if voice:
        summary += (f" | predicted speech {total_spoken / 60:.1f} min with {voice['name']} "
                    f"({voice_pace:.2f} chars/s{'' if exact else ', estimated until its first render'})")
        summary += (f"\n{voice['name']} speaks this draft at about {wpm:.0f} words a minute, pauses "
                    f"included; the guide column uses that rate")
    else:
        summary += f" | estimated {total_words / args.wpm:.1f} min at {args.wpm:g} wpm"
    print(summary)

    if problems and not args.force:
        print(f"\n{problems} issue(s). Fix and rerun (or --force). Nothing exported.")
        sys.exit(1)

    paras = [re.sub(r"\s{2,}", " ", PAUSE_RE.sub(" ", p)).strip()
             for seg in segments for p in paragraphs(seg["lines"])]
    paras = [p for p in paras if p]
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n\n".join(paras) + "\n")
    print(f"\nExported {len(paras)} paragraphs to {args.out}"
          + (f" despite {problems} issue(s)" if problems else ""))


if __name__ == "__main__":
    from voices import use_voicestudio_python
    use_voicestudio_python()
    main()
