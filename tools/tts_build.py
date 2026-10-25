#!/usr/bin/env python3
"""Lint a segmented workout draft and export a clean transcript.

The draft format (the `movements:` line, `@@ <seconds> | <label>` markers, [pause], [chime] and
[hold]) is defined in draft.py. Markers are stripped on export.

What must hold, and stops the export: every line a voice can read cleanly (no digits, symbols,
abbreviations or markup), every paragraph short enough to speak in one clip, the whole workout's
predicted length within three percent of plan, and (with --require-menu, or a menu beside the draft)
every movement on today's menu (menu.py). A segment far off its slot (under 80 or over 110 percent)
is flagged in the table to help place the fix, but only the total is held to plan; with --strict the
flags count as issues. A held segment (one with a [hold]) shows the spare seconds it will spend in
silence, so a long quiet rest is easy to spot. How the script should sound (varied openings, the
listener's name, friendly handoffs) is guidance in knowledge/tts-rules.md, not a check.

With --voice, each segment's spoken length is predicted for that voice (see
voices.py) and checked against its planned seconds. Without it, word
count against --wpm is the rough fallback.

lint() returns a Report; main() only prints it. Exit codes are in cli.py: 1 when
there are issues (nothing exported), 64 for a mistyped command.

Usage:
    ./sweatcast lint draft.txt --voice "Chatterbox Coach" --out "Workout 2026-10-18.txt"
    ./sweatcast lint draft.txt --wpm 170 --out final.txt --force   # export despite issues (not menu ones)
    ./sweatcast lint draft.txt --voice "Chatterbox Coach" --out x.txt --strict  # segment flags count
"""
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
from draft import (CHIME, CHIME_SECONDS, MARK_RE, MAX_CLIP, MAX_FILL, MIN_FILL, PARAGRAPH_GAP,  # noqa: E402
                   TOTAL_TOLERANCE, fill_flag, holds, layout, paragraphs, parse, plan, spoken)
from draft import declared as draft_declared, menu_path as draft_menu_path  # noqa: E402

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
DEFAULT_WPM = 185
WORD_TOLERANCE = 0.08


def spoken_seconds(seg, voice, lead=0.0, rate=None):
    """Predicted seconds for a segment; `lead` is the chime that opens it, if any.
    `rate` is the voice's pace (read once per lint); without it, it's looked up."""
    from voices import clip_seconds
    paras = plan(seg)
    return lead + sum(clip_seconds(text, voice, rate) if spoken(text) else
                      (CHIME_SECONDS if text == CHIME else 0.0)
                      for para in paras for text, _ in para) \
        + sum(pause for para in paras for _, pause in para) \
        + PARAGRAPH_GAP * max(len(paras) - 1, 0)


def lint_line(lineno, line):
    issues = []
    if MD_LINE_RE.match(line):
        issues.append("markdown or list syntax at line start")
    line = MARK_RE.sub(" ", line)
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
    return sum(len(re.findall(r"[A-Za-z0-9’']+(?:-[A-Za-z0-9’']+)*", MARK_RE.sub(" ", l)))
               for _, l in lines)


HELD_QUIET = 10.0   # a held segment's spare silence, in seconds, worth pointing out


@dataclass
class Row:
    """One segment's line in the lint table."""
    index: int
    label: str
    seconds: int
    words: int
    guide: int
    spoken: Optional[float] = None   # predicted seconds, with a voice
    diff: Optional[float] = None     # word count over or under the guide, without one
    flag: str = ""                   # "long" or "short" when far off its slot
    quiet: float = 0.0               # a held segment's spare seconds, spent silent at its holds
    clip_issues: List[str] = field(default_factory=list)
    line_issues: List[str] = field(default_factory=list)

    @property
    def fill(self):
        return self.spoken / self.seconds if self.spoken is not None and self.seconds else None


@dataclass
class Report:
    rows: List[Row]
    strict: bool                        # segment flags count as issues
    wpm: float                          # the guide rate: the voice's rate on this draft, or --wpm
    voice: Optional[dict] = None
    pace: Optional[float] = None
    exact: bool = False                 # the voice's pace is measured, not estimated
    predicted: Optional[float] = None   # laid-out seconds of the whole workout, with a voice
    total_tolerance: float = TOTAL_TOLERANCE
    word_wpm: float = DEFAULT_WPM       # --wpm, for the estimate without a voice

    @property
    def total_seconds(self):
        return sum(r.seconds for r in self.rows)

    @property
    def total_words(self):
        return sum(r.words for r in self.rows)

    @property
    def total_spoken(self):
        return sum(r.spoken or 0.0 for r in self.rows)

    @property
    def drift(self):
        if self.predicted is None or not self.total_seconds:
            return None
        return self.predicted / self.total_seconds - 1

    @property
    def total_off(self):
        return self.drift is not None and abs(self.drift) > self.total_tolerance

    @property
    def problems(self):
        n = sum(len(r.clip_issues) + len(r.line_issues) + (bool(r.flag) and self.strict) for r in self.rows)
        return n + int(self.total_off)


def lint(segments, voice=None, wpm=DEFAULT_WPM, min_fill=MIN_FILL, max_fill=MAX_FILL,
         total_tolerance=TOTAL_TOLERANCE, word_tolerance=WORD_TOLERANCE, strict=False):
    """Check a parsed draft. With a voice, predicts spoken seconds from its pace,
    which is read once for the whole lint."""
    rate, exact, spokens = None, False, []
    if voice:
        from voices import clip_seconds, pace
        rate, exact = pace(voice)
        spokens = [spoken_seconds(seg, voice, CHIME_SECONDS if i else 0.0, rate)
                   for i, seg in enumerate(segments)]
        # The rate this voice actually speaks this draft at, so the guide column
        # says how many words each segment wants with this voice.
        guide_wpm = (sum(word_count(seg["lines"]) for seg in segments) / sum(spokens) * 60
                     if sum(spokens) else wpm)
    else:
        guide_wpm = wpm
    rows = []
    for i, seg in enumerate(segments, 1):
        guide = round(guide_wpm * seg["seconds"] / 60)
        row = Row(i, seg["label"], seg["seconds"], word_count(seg["lines"]), guide)
        if voice:
            row.spoken = spokens[i - 1]
            fill = row.fill
            held = holds(seg)[1] > 0
            row.flag = fill_flag(row.spoken, seg["seconds"], min_fill, max_fill, held=held)
            row.quiet = max(seg["seconds"] - row.spoken, 0.0) if held else 0.0
            # Long clips drift and glitch. Keep every clip comfortably short.
            for para in plan(seg):
                for text, _ in para:
                    secs = clip_seconds(text, voice, rate) if spoken(text) else 0.0
                    if secs > MAX_CLIP:
                        row.clip_issues.append(
                            f"  paragraph \"{' '.join(text.split()[:6])}...\" speaks for {secs:.0f}s; "
                            f"split it into paragraphs under {MAX_CLIP:.0f}s")
        else:
            row.diff = (row.words - guide) / guide if guide else 0
            if abs(row.diff) > word_tolerance:
                row.flag = "long" if row.diff > 0 else "short"
        for lineno, line in seg["lines"]:
            row.line_issues += lint_line(lineno, line)
        rows.append(row)
    report = Report(rows, strict, guide_wpm, voice, rate, exact,
                    total_tolerance=total_tolerance, word_wpm=wpm)
    if voice:
        report.predicted = sum(length for _, length in layout(
            [(spokens[i], max(len(plan(seg)) - 1, 0), seg["seconds"], holds(seg)[1]) for i, seg in enumerate(segments)]))
    return report


def render_report(report):
    """The lint's printed table and summary, as lines."""
    out = []
    voice = report.voice
    if voice:
        out.append(f"{'#':>3} {'secs':>5} {'words':>5} {'guide':>5} {'spoken':>6} {'fill':>5}  label")
    else:
        out.append(f"{'#':>3} {'secs':>5} {'target':>6} {'words':>5} {'diff':>6}  label")
    for r in report.rows:
        if voice:
            flag = (f"  <-- runs {r.spoken - r.seconds:.1f}s long; trim it" if r.flag == "long" else
                    f"  <-- ends {r.seconds - r.spoken:.1f}s early; add a little" if r.flag == "short" else
                    f"  ({r.quiet:.0f}s silent at its holds)" if r.quiet >= HELD_QUIET else "")
            out.append(f"{r.index:>3} {r.seconds:>5} {r.words:>5} {r.guide:>5} {r.spoken:>6.1f} "
                       f"{r.fill:>5.0%}  {r.label}{flag}")
            out += r.clip_issues
        else:
            flag = "  <-- too long" if r.flag == "long" else "  <-- too short" if r.flag == "short" else ""
            out.append(f"{r.index:>3} {r.seconds:>5} {r.guide:>6} {r.words:>5} {r.diff:>+6.0%}  {r.label}{flag}")
        out += r.line_issues

    summary = f"\nPlanned {report.total_seconds / 60:.1f} min | {report.total_words} words"
    if voice:
        summary += (f" | predicted speech {report.total_spoken / 60:.1f} min with {voice['name']} "
                    f"({report.pace:.2f} chars/s{'' if report.exact else ', estimated until its first render'})")
        drift = report.drift or 0.0
        summary += (f"\nPredicted length {report.predicted / 60:.1f} min, {drift:+.1%} of plan "
                    f"(within {report.total_tolerance:.0%} is fine)")
        if report.total_off:
            summary += ("  <-- too " + ("long: trim words" if drift > 0 else "short: add words")
                        + " in the segments furthest off")
        summary += (f"\n{voice['name']} speaks this draft at about {report.wpm:.0f} words a minute, pauses "
                    f"included; the guide column uses that rate")
    else:
        summary += f" | estimated {report.total_words / report.word_wpm:.1f} min at {report.word_wpm:g} wpm"
    out.append(summary)

    flagged = sum(bool(r.flag) for r in report.rows)
    if flagged:
        out.append(f"{flagged} segment(s) far off their slots"
                   + (" (counted as issues: --strict)" if report.strict else
                      "; not blocking, since only the total is held to plan, but the fix goes there first"))
    return out


def export_text(segments):
    """The clean transcript: paragraphs with markers stripped."""
    paras = [re.sub(r"\s{2,}", " ", MARK_RE.sub(" ", p)).strip()
             for seg in segments for p in paragraphs(seg["lines"])]
    return "\n\n".join(p for p in paras if p) + "\n", len([p for p in paras if p])


def menu_check(draft_path, text, segments, required):
    """Check the draft against the menu beside it (when there is one, or when `required`), print what
    it finds, and return the issues."""
    path = draft_menu_path(draft_path)
    if not (required or os.path.exists(path)):
        return []
    import catalog
    import menu
    import paths
    issues, warnings = menu.check(catalog.load(), menu.load(path), text, segments)
    if issues or warnings:
        print(f"\nMenu check ({paths.show(os.path.abspath(path))}):")
        print("\n".join([f"  {i}" for i in issues] + [f"  warning: {w}" for w in warnings]))
    else:
        print(f"\nMenu check: every movement is on today's menu ({len(draft_declared(text))} declared).")
    return issues


def main():
    ap = cli.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", required=True)
    ap.add_argument("--coach", "--voice", dest="coach", help="a coach's name: check predicted spoken seconds")
    ap.add_argument("--engine", help="with --coach, the route whose measured pace predicts them (default: the "
                                     "profile's render list)")
    ap.add_argument("--wpm", type=float, default=DEFAULT_WPM, help="word guide without --voice, words per minute")
    ap.add_argument("--min-fill", type=float, default=MIN_FILL, help="below this, the segment is far too short")
    ap.add_argument("--max-fill", type=float, default=MAX_FILL, help="above this, the segment is far too long")
    ap.add_argument("--total-tolerance", type=float, default=TOTAL_TOLERANCE,
                    help="the whole workout may run this fraction over or under plan")
    ap.add_argument("--word-tolerance", type=float, default=WORD_TOLERANCE,
                    help="word-count tolerance per segment without --voice")
    ap.add_argument("--force", action="store_true", help="export despite issues (never despite the menu check)")
    ap.add_argument("--strict", action="store_true", help="segments far off their slots count as issues")
    ap.add_argument("--require-menu", action="store_true",
                    help="fail when the draft has no menu beside it (./sweatcast build passes this)")
    args = ap.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        text = f.read()
    segments = parse(text)
    voice = None
    if args.coach or args.engine:
        import personas
        voice = personas.resolve(args.coach, args.engine, pending=True)   # a coach still to be made: estimated

    report = lint(segments, voice, args.wpm, args.min_fill, args.max_fill,
                  args.total_tolerance, args.word_tolerance, args.strict)
    print("\n".join(render_report(report)))

    menu_issues = menu_check(args.draft, text, segments, args.require_menu)
    if menu_issues:
        print(f"\n{len(menu_issues)} menu issue(s). Fix and rerun; --force doesn't skip the menu check. "
              "Nothing exported.")
        sys.exit(cli.ISSUES)
    problems = report.problems
    if problems and not args.force:
        print(f"\n{problems} issue(s). Fix and rerun (or --force). Nothing exported.")
        sys.exit(cli.ISSUES)

    text, count = export_text(segments)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"\nExported {count} paragraphs to {args.out}"
          + (f" despite {problems} issue(s)" if problems else ""))


if __name__ == "__main__":
    main()
