"""The lint: what a voice can read cleanly and how long a draft will speak, and the clean transcript.

The draft format (the `movements:` line, `@@ <seconds> | <label>` markers, [pause], [chime] and
[hold]) is defined in draft.py. Markers are stripped on export. ./sweatcast build runs lint(), prints
render_report() and writes export_text(); with --lint-only it stops there.

What must hold: every line a voice can read cleanly (no digits, symbols, abbreviations or markup), every
paragraph short enough to speak in one clip, no clip of a single word, and the whole workout's predicted
length within three percent of plan. A segment far off its slot (under 80 or over 110 percent) is flagged in the table to help place
the fix, but only the total is held to plan; with strict=True the flags count as issues. A held segment
(one with a [hold]) shows the spare seconds it will spend in silence, so a long quiet rest is easy to spot.
How the script should sound (varied openings, the listener's name, friendly handoffs) is guidance in
knowledge/tts-rules.md, not a check.

With a voice, each segment's spoken length is predicted from that coach's pace (voices.py) and checked
against its planned seconds; without one, word count against `wpm` is the rough fallback.
"""
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from draft import (CHIME, CHIME_SECONDS, CUE_NAMES, MARK_RE, MAX_CLIP, MAX_FILL, MIN_FILL, NUMBER_WORDS,  # noqa: E402
                   PARAGRAPH_GAP, TOTAL_TOLERANCE, fill_flag, holds, is_mark, layout, mark_issue, mark_words,
                   paragraphs, plan, spans, spoken)
import counts  # noqa: E402

# Characters a voice may announce or mispronounce.
FORBIDDEN_CHARS = set("#*_`|<>[]{}/\\@&%+=~^$°•→×")
ALLOWED_NON_ASCII = set("’‘“”…—–é")  # curly quotes, ellipsis (refused on its own), dashes, common accent

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


def spoken_seconds(seg, voice, lead=0.0, rate=None, paras=None):
    """Predicted seconds for a segment; `lead` is the chime that opens it, if any.
    `rate` is the voice's pace (read once per lint); without it, it's looked up. `paras` is plan(seg),
    when the caller has it already."""
    from voices import clip_seconds
    paras = plan(seg) if paras is None else paras
    return lead + sum(clip_seconds(text, voice, rate) if spoken(text) else
                      CHIME_SECONDS if text == CHIME else mark_seconds(text, voice, rate)
                      for para in paras for text, _ in para) \
        + sum(pause for para in paras for _, pause in para) \
        + PARAGRAPH_GAP * max(len(paras) - 1, 0)


def mark_seconds(text, voice, rate=None):
    """A count's or cue's seconds with this coach (its recorded clips, or the count said in words by a coach
    without them), or 0 for anything else (or one the lint will refuse)."""
    from voices import clip_seconds
    if not is_mark(text) or mark_issue(text):
        return 0.0
    words = counts.in_words(text, voice)
    if words:
        return clip_seconds(words, voice, rate)
    return 0.0 if counts.missing(text, voice) else counts.seconds(text, voice)


def mark_problem(text, voice):
    """Why a count or cue can't play with this coach, or None."""
    issue = mark_issue(text)
    if issue:
        return issue
    if not voice:
        return None
    if not voice.get("cues"):
        return None   # said in words by the coach's voice (counts.in_words)
    gone = counts.missing(text, voice)
    if gone:
        return f"{text}: {voice.get('name', 'this coach')}'s cues/ folder has no clip for " + ", ".join(gone)
    return None


NUMBER_RANK = {w: i for i, w in enumerate(NUMBER_WORDS, 1)}
COUNTDOWN_RUN = 3   # number words counting down by one, in a row, that make a written-out countdown


def written_countdown(text):
    """The first run of COUNTDOWN_RUN or more number words counting down by one ("five, four, three"), or None."""
    words = [w.lower() for w in WORD_RE.findall(text)]
    for i in range(len(words) - COUNTDOWN_RUN + 1):
        run = words[i:i + COUNTDOWN_RUN]
        ranks = [NUMBER_RANK.get(w) for w in run]
        if all(ranks) and all(a - b == 1 for a, b in zip(ranks, ranks[1:])):
            return ", ".join(run)
    return None


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
    if re.search(r"\.\.\.|…", line):
        issues.append("an ellipsis: use a comma or a period (a local voice drops the words after one)")
    return [f"  line {lineno}: {i}" for i in issues]


WORD_RE = re.compile(r"[A-Za-z0-9’']+(?:-[A-Za-z0-9’']+)*")
# A clip (the words between two markers) of one word: Pocket TTS garbled "Begin." and "Hold." in every take
# of some coaches (2026-10-26, ten coaches, four seeds each), while two words ("Other way.") never failed.
MIN_CLIP_WORDS = 2


def word_count(lines):
    return sum(len(WORD_RE.findall(MARK_RE.sub(" ", l))) for _, l in lines)


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
         total_tolerance=TOTAL_TOLERANCE, word_tolerance=WORD_TOLERANCE, strict=False, chime=True):
    """Check a parsed draft. With a voice, predicts spoken seconds from its pace,
    which is read once for the whole lint. `chime` says whether the render opens each segment after the
    first with the bell (--no-chime turns it off), so the prediction matches."""
    rate, exact, spokens = None, False, []
    plans = [plan(seg) for seg in segments]   # as the render voices it, computed once
    if voice:
        from voices import clip_seconds, pace
        rate, exact = pace(voice)
        spokens = [spoken_seconds(seg, voice, CHIME_SECONDS if i and chime else 0.0, rate, plans[i])
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
            held = holds(seg)[1] > 0
            row.flag = fill_flag(row.spoken, seg["seconds"], min_fill, max_fill, held=held)
            row.quiet = max(seg["seconds"] - row.spoken, 0.0) if held else 0.0
            # Long clips drift and glitch. Keep every clip comfortably short.
            for para in plans[i - 1]:
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
        has_cues = bool(voice and voice.get("cues"))
        for para in plans[i - 1]:
            for text, _ in para:
                if is_mark(text):
                    problem = mark_problem(text, voice)
                    if problem:
                        row.clip_issues.append("  " + problem)
                    continue
                if not spoken(text):
                    continue
                words = WORD_RE.findall(text)
                if len(words) < MIN_CLIP_WORDS:
                    cue = words[0].lower() if words and words[0].lower() in CUE_NAMES else None
                    hint = (f", or play the coach's recorded cue: [cue {cue}]" if cue and has_cues else
                            ", or a recorded cue ([cue rest])" if has_cues else "")
                    row.clip_issues.append(
                        f"  \"{text}\" is one word between markers, and a local voice often garbles a word "
                        f"on its own; give it two or more (\"Hold it there.\", \"And go.\"){hint}")
                run = written_countdown(text) if has_cues else None
                if run:
                    row.clip_issues.append(
                        f"  \"{run}\" counts down in words, which a voice rushes; use [count N] or [count N go], "
                        "which plays the coach's recorded numbers a second apart")
        rows.append(row)
    report = Report(rows, strict, guide_wpm, voice, rate, exact,
                    total_tolerance=total_tolerance, word_wpm=wpm)
    if voice:
        report.predicted = sum(length for _, length in layout(
            [(spokens[i], max(len(plans[i]) - 1, 0), seg["seconds"], holds(seg)[1]) for i, seg in enumerate(segments)]))
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
            out += r.clip_issues
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
                   + (" (counted as issues: strict)" if report.strict else
                      "; not blocking, since only the total is held to plan, but the fix goes there first"))
    return out


def export_text(segments):
    """The clean transcript: paragraphs with markers stripped, and counts and cues as the words they say."""
    def said(p):
        return " ".join(mark_words(t) if is_mark(t) and not mark_issue(t) else MARK_RE.sub(" ", t)
                        for t, _ in spans(p))
    paras = [re.sub(r"\s{2,}", " ", said(p)).strip()
             for seg in segments for p in paragraphs(seg["lines"])]
    return "\n\n".join(p for p in paras if p) + "\n", len([p for p in paras if p])
