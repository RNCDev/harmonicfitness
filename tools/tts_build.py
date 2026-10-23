#!/usr/bin/env python3
"""Lint a segmented workout draft and export a clean transcript.

The draft format (`@@ <seconds> | <label>` markers, [pause] and [chime]) is defined in
draft.py. Markers are stripped on export.

Structure checks (a locator opening each segment, one countdown per segment, few
exclamation points, no praise line used over and over, no run of segments opening alike, no
newsreader handoffs, and the listener's name from the profile used in the warm-up but not too
often) print as warnings; with
--strict they count as issues.

With --voice, each segment's spoken length is predicted for that voice (see
voices.py) and checked against its planned seconds. Without it, word
count against --wpm is the rough fallback.

lint() returns a Report; main() only prints it. Exit codes are in cli.py: 1 when
there are issues (nothing exported), 64 for a mistyped command.

Usage:
    ./sweatcast lint draft.txt --voice "Chatterbox Coach" --out "Workout 2026-10-18.txt"
    ./sweatcast lint draft.txt --wpm 170 --out final.txt --force   # export despite issues
    ./sweatcast lint draft.txt --voice "Chatterbox Coach" --out x.txt --strict  # structure warnings count
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


LOCATOR_RE = re.compile(
    r"\b(minute|minutes|round|block|halfway|last|final|warm-up|warm up|finisher|cool-down|"
    r"cool down|box breathing|set|part|circuit|interval|to go|one more|next up|here we go|back to|again)\b"
    r"|^(that's|that is|that was)\b",
    re.IGNORECASE)
COUNTDOWN_RE = re.compile(r"\bthree\s*(?:\.\.\.|…)\s*two\s*(?:\.\.\.|…)\s*one\b", re.IGNORECASE)
PRAISE_WORDS = {"good", "nice", "great", "solid", "perfect", "beautiful", "well", "done", "work",
                "job", "that's", "it", "very", "really", "there", "strong", "lovely"}
PRAISE_START = {"good", "nice", "great", "solid", "perfect", "beautiful", "well", "strong", "lovely"}
MAX_EXCLAIM, PRAISE_REPEAT = 2, 3
NAME_MOST = 5          # past this the listener's name sounds like a sales call
SAME_OPENING = 3       # this many segments in a row opening alike reads as a template
NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
                "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
                "twenty", "thirty", "forty", "fifty", "sixty", "first", "second", "third", "fourth", "fifth"}
NEWSREADER_RE = re.compile(r"\b(today's story is|in other news|turning now to|turning to the news|"
                           r"and now,? the news|in today's headlines)\b", re.IGNORECASE)


def _opening(sentence):
    """A segment's opening shape: its first three words with numbers as #, to spot a template."""
    words = re.findall(r"[a-z’'-]+", sentence.lower())[:3]
    return " ".join("#" if w in NUMBER_WORDS else w for w in words)


def sentences(text):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", MARK_RE.sub(" ", text)) if x.strip()]


def structure_warnings(segments, name=None):
    """Coaching-structure checks from the workout skill and tts-rules.md, as messages. With the
    listener's `name`, also checks it is used, and not too often."""
    out, praise, exclaim, openings, named = [], {}, 0, [], []
    for i, seg in enumerate(segments, 1):
        paras = paragraphs(seg["lines"])
        text = " ".join(paras)
        if name:
            named += [i] * len(re.findall(rf"\b{re.escape(name)}\b", text, re.IGNORECASE))
        for m in NEWSREADER_RE.finditer(text):
            out.append(f"segment {i} ({seg['label']}): \"{m.group(0)}\" sounds like a newsreader; hand off "
                       "the way a person would, like \"Okay, while you breathe, here's a strange one.\"")
        if i > 1 and paras:
            first = (sentences(paras[0]) or [""])[0]
            openings.append((i, _opening(first)))
            if not LOCATOR_RE.search(first):
                out.append(f"segment {i} ({seg['label']}): opens without a locator (\"{first[:40]}\"); "
                           "say where we are, like \"Minute nine of twenty-five.\"")
        n = len(COUNTDOWN_RE.findall(text))
        if n > 1:
            out.append(f"segment {i} ({seg['label']}): {n} countdowns; keep one per segment")
        exclaim += text.count("!")
        for sent in sentences(text):
            words = re.findall(r"[a-z’']+", sent.lower().replace("’", "'"))
            if 0 < len(words) <= 4 and words[0] in PRAISE_START and all(w in PRAISE_WORDS for w in words):
                key = " ".join(words)
                praise.setdefault(key, []).append(i)
    run = []
    for i, shape in openings + [(None, None)]:
        if run and shape == run[-1][1] and i == run[-1][0] + 1:
            run.append((i, shape))
            continue
        if len(run) >= SAME_OPENING and run[0][1]:
            out.append(f"segments {run[0][0]} to {run[-1][0]} all open \"{run[0][1].replace('#', '...')}\"; "
                       "vary the locator (\"Here we go, round three.\", \"Two to go.\", \"Back on the floor for this one.\")")
        run = [(i, shape)] if i is not None else []
    if name and not named:
        out.append(f"the listener's name ({name}) never comes up; greet them by name in the warm-up "
                   "and use it again at the hardest set and the sign-off")
    elif name and 1 not in named:
        out.append(f"the warm-up doesn't greet {name} by name; open with it")
    elif name and len(named) > NAME_MOST:
        out.append(f"the name {name} comes up {len(named)} times; two to four is warm, more sounds like a sales call")
    if exclaim > MAX_EXCLAIM:
        out.append(f"{exclaim} exclamation points; keep to {MAX_EXCLAIM} a session, they can make the voice shout")
    for key, where in sorted(praise.items()):
        if len(where) >= PRAISE_REPEAT:
            out.append(f"praise \"{key}\" used {len(where)} times (segments "
                       f"{', '.join(map(str, sorted(set(where))))}); vary it")
    return out


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
    clip_issues: List[str] = field(default_factory=list)
    line_issues: List[str] = field(default_factory=list)

    @property
    def fill(self):
        return self.spoken / self.seconds if self.spoken is not None and self.seconds else None


@dataclass
class Report:
    rows: List[Row]
    warnings: List[str]
    strict: bool
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
        n = sum(len(r.clip_issues) + len(r.line_issues) + bool(r.flag) for r in self.rows)
        n += int(self.total_off)
        return n + (len(self.warnings) if self.strict else 0)


def lint(segments, voice=None, wpm=DEFAULT_WPM, min_fill=MIN_FILL, max_fill=MAX_FILL,
         total_tolerance=TOTAL_TOLERANCE, word_tolerance=WORD_TOLERANCE, strict=False, name=None):
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
            row.flag = fill_flag(row.spoken, seg["seconds"], min_fill, max_fill, held=holds(seg)[1] > 0)
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
    report = Report(rows, structure_warnings(segments, name), strict, guide_wpm, voice, rate, exact,
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
                    f"  <-- ends {r.seconds - r.spoken:.1f}s early; add a little" if r.flag == "short" else "")
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

    if report.warnings:
        out.append(f"\nStructure {'issues' if report.strict else 'warnings (not blocking; --strict to enforce)'}:")
        out += ["  " + w for w in report.warnings]
    return out


def export_text(segments):
    """The clean transcript: paragraphs with markers stripped."""
    paras = [re.sub(r"\s{2,}", " ", MARK_RE.sub(" ", p)).strip()
             for seg in segments for p in paragraphs(seg["lines"])]
    return "\n\n".join(p for p in paras if p) + "\n", len([p for p in paras if p])


def _listener_name():
    """The profile's name, for the name checks, or None when there's no readable profile."""
    try:
        import context
        return context.listener_name(context.profile())
    except (SystemExit, OSError, ValueError):
        return None


def main():
    ap = cli.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", help="a voice's name: check predicted spoken seconds")
    ap.add_argument("--wpm", type=float, default=DEFAULT_WPM, help="word guide without --voice, words per minute")
    ap.add_argument("--min-fill", type=float, default=MIN_FILL, help="below this, the segment is far too short")
    ap.add_argument("--max-fill", type=float, default=MAX_FILL, help="above this, the segment is far too long")
    ap.add_argument("--total-tolerance", type=float, default=TOTAL_TOLERANCE,
                    help="the whole workout may run this fraction over or under plan")
    ap.add_argument("--word-tolerance", type=float, default=WORD_TOLERANCE,
                    help="word-count tolerance per segment without --voice")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--strict", action="store_true", help="structure warnings count as issues")
    args = ap.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        segments = parse(f.read())
    voice = None
    if args.voice:
        from voices import lookup
        voice = lookup(args.voice)

    report = lint(segments, voice, args.wpm, args.min_fill, args.max_fill,
                  args.total_tolerance, args.word_tolerance, args.strict, name=_listener_name())
    print("\n".join(render_report(report)))

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
