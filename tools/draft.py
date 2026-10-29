"""A segmented workout draft: its format, and how its segments sit on the plan's clock.

Draft format: each segment starts with a marker line
    @@ <seconds> | <label>
followed by the spoken text. Inside the text, [pause 3s] inserts that much silence
(also [pause 500ms]; at most ten seconds), [chime] rings the segment bell at
that point, for example when work starts in a forty-five-and-fifteen interval, and
[hold] marks a stretch of timed work: [hold 6s] is exactly that much silence, and a bare [hold]
takes an equal share of its segment's spare time, so a segment with a bare hold keeps its full
planned length. A segment with only fixed holds ends early like any other. The lint refuses any
silence longer than MAX_SILENCE, so the coach talks through the work rather than going quiet. For a coach with recorded counts (a
cues/ folder beside its clip), [count 5] plays five, four, three, two, one, a second apart, from where it
sits; [count 5 go] adds the cue a second after "one" (go, rest, switch, switch sides, stop, hold); and
[cue rest] plays one cue alone.

Before the first marker, a draft declares the movements it scripts, once, on one or more
header lines that are never spoken:
    movements: goblet squat, dumbbell floor press, dead bug, box breathing
`./harmonicfitness build` checks them against the menu `./harmonicfitness brief --save` wrote beside
the draft (`menu_path`).

This is the one source of truth for the draft: the lint (tts_build.py) predicts
from it and the render (render.py) lays clips out with it, so they agree.
"""
import os
import re
import errors

MARKER = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*)$")
HEADER = re.compile(r"^movements\s*:\s*(.*)$", re.IGNORECASE)   # the declaration, before the first marker
DRAFT_SUFFIX = ".draft.txt"
PAUSE_RE = re.compile(r"\[\s*pause(?:\s+(\d+(?:\.\d+)?)\s*(ms|s)?)?\s*\]", re.IGNORECASE)
CHIME_RE = re.compile(r"\[\s*chime\s*\]", re.IGNORECASE)
HOLD_RE = re.compile(r"\[\s*hold(?:\s+(\d+(?:\.\d+)?)\s*(ms|s)?)?\s*\]", re.IGNORECASE)
# Counts and cues: a coach's recorded clips, laid on a beat (counts.py holds the clips). Matched loosely, so a
# misspelled one ("[count five]") is still a marker the lint names, not text a voice would read.
COUNT_RE = re.compile(r"\[\s*count\b[^\]]*\]", re.IGNORECASE)
CUE_RE = re.compile(r"\[\s*cue\b[^\]]*\]", re.IGNORECASE)
MARK_RE = re.compile("|".join(r.pattern for r in (PAUSE_RE, CHIME_RE, HOLD_RE, COUNT_RE, CUE_RE)), re.IGNORECASE)
CHIME = "[chime]"   # a span whose text is this rings the bell instead of speaking
HOLD = "[hold]"     # a span whose text is this takes a share of the segment's spare time as silence
NUMBER_WORDS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
CUE_NAMES = ("go", "rest", "switch", "switch sides", "stop", "hold")
COUNT_MIN, COUNT_MAX = 2, 10
BEAT = 1.0          # seconds from one count's start to the next, and from "one" to the cue
_CUE = "(" + "|".join(c.replace(" ", r"\s+") for c in sorted(CUE_NAMES, key=len, reverse=True)) + ")"
COUNT_PARTS = re.compile(r"\[count (\d+)(?: " + _CUE + r")?\]")
CUE_PARTS = re.compile(r"\[cue " + _CUE + r"\]")
PAUSE_DEFAULT, PAUSE_MAX = 0.35, 10.0   # seconds: a bare [pause], and the longest one
PARAGRAPH_GAP = 0.35                    # least silence between paragraphs within a segment
MAX_CLIP = 22.0                         # longest a paragraph may speak, in seconds
CHIME_SECONDS = 0.6                     # bell plus quiet that opens each segment after the first

# Timing. A segment's spare time widens its paragraph breaks (up to MAX_EXTRA_GAP each)
# and leaves a short tail; past that it ends early rather than going quiet, so the
# workout runs a little under plan instead of padding with silence. A segment with a
# A bare [hold] is the exception: timed work needs its full length, so all its spare
# time becomes silence at its bare holds. Only the total is held to plan, within
# TOTAL_TOLERANCE; a segment is flagged only when far off (a held one never as short).
END_TAIL = 1.5          # seconds of spare time kept at a segment's end, at most
MAX_EXTRA_GAP = 1.5     # most spare time added to any one paragraph break
MAX_SILENCE = 8.0       # the longest silence a listener hears before it sounds like a dropped earbud
TOTAL_TOLERANCE = 0.03  # the whole workout may run this fraction over or under plan
MIN_FILL, MAX_FILL = 0.80, 1.10   # a segment outside these (speech over planned seconds) is flagged


def parse(text):
    segments, current = [], None
    for lineno, line in enumerate(text.splitlines(), 1):
        m = MARKER.match(line.strip())
        if m:
            if int(m.group(1)) < 1:
                raise errors.DraftError(f"Line {lineno}: a segment of {m.group(1)} seconds; every @@ segment needs at "
                                 "least 1 second on the plan's clock.")
            current = {"seconds": int(m.group(1)), "label": m.group(2).strip(),
                       "lines": [], "start": lineno}
            segments.append(current)
        elif current is None:
            if line.strip() and not HEADER.match(line.strip()):
                raise errors.DraftError(f"Line {lineno}: text before the first @@ marker "
                                 "(only a movements: line may come first).")
        else:
            current["lines"].append((lineno, line))
    if not segments:
        raise errors.DraftError("No @@ segment markers found.")
    return segments


def tolerance_arg(text):
    """--tolerance as argparse reads it: a fraction from 0 to 0.5 (nan, a negative or more than half is refused)."""
    import argparse
    import math
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or not 0 <= value <= 0.5:
        raise argparse.ArgumentTypeError(f"{text!r} isn't a fraction from 0 to 0.5 (0.03 is three percent)")
    return value


def declared(text):
    """The movements the draft's header declares, in order, as written: every `movements:` line
    before the first marker, split on commas."""
    out = []
    for line in text.splitlines():
        if MARKER.match(line.strip()):
            break
        m = HEADER.match(line.strip())
        if m:
            out += [w.strip() for w in m.group(1).split(",") if w.strip()]
    return list(dict.fromkeys(out))


def is_smoke(path):
    """Whether `path` is the engine's smoke test (knowledge/smoke-test.draft.txt), known by its place, never by
    its name: it's the one draft that builds without a menu."""
    import paths
    try:
        return os.path.realpath(path) == os.path.realpath(paths.SMOKE_DRAFT)
    except OSError:
        return False


def stem(path):
    """A draft's path without `.draft.txt` (or its one extension): the brief, the menu and the draft
    share it."""
    return path[:-len(DRAFT_SUFFIX)] if path.endswith(DRAFT_SUFFIX) else os.path.splitext(path)[0]


def menu_path(path):
    """Where the menu for a draft (or a stem) lives: `<stem>.menu.json` beside it."""
    return stem(path) + ".menu.json"


def brief_path(path):
    return stem(path) + ".brief.md"


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
    """Split a paragraph at [pause], [chime] and [hold] markers: [(text, seconds of silence
    after)]. Text may be empty (a leading pause), CHIME for the bell or HOLD for a hold."""
    out, last = [], 0
    for m in MARK_RE.finditer(paragraph):
        text = paragraph[last:m.start()].strip()
        last = m.end()
        if COUNT_RE.fullmatch(m.group(0)) or CUE_RE.fullmatch(m.group(0)):
            if text:
                out.append((text, 0.0))
            out.append(("[" + " ".join(m.group(0)[1:-1].lower().split()) + "]", 0.0))   # "[count 5 go]"
            continue
        for mark_re, mark in ((CHIME_RE, CHIME), (HOLD_RE, HOLD)):
            got = mark_re.fullmatch(m.group(0))
            if got:
                if text:
                    out.append((text, 0.0))
                fixed = 0.0
                if mark == HOLD and got.group(1):
                    fixed = float(got.group(1)) / (1 if (got.group(2) or "s").lower() == "s" else 1000)
                out.append((mark, fixed))   # a fixed hold is that much silence; a bare one shares the spare
                break
        else:
            mark = None
        if mark:
            continue
        num, unit = m.group(1), (m.group(2) or "").lower()
        secs = PAUSE_DEFAULT if num is None else float(num) / (1 if unit == "s" else 1000)
        if not text and out:
            out[-1] = (out[-1][0], min(out[-1][1] + secs, PAUSE_MAX))
        else:
            out.append((text, min(secs, PAUSE_MAX)))
    tail = paragraph[last:].strip()
    if tail or not out:
        out.append((tail, 0.0))
    return out


def spoken(text):
    """True for a span the voice speaks (not a bare pause, the bell, a hold, a count or a cue)."""
    return bool(text) and text not in (CHIME, HOLD) and not is_mark(text)


def is_mark(text):
    """A count or cue span, as spans() writes it ("[count 5 go]", "[cue rest]"), well formed or not."""
    return text.startswith(("[count", "[cue")) and text.endswith("]")


def count_of(text):
    """(N, cue or None) for a well-formed count span, else None."""
    m = COUNT_PARTS.fullmatch(text)
    return (int(m.group(1)), m.group(2)) if m else None


def cue_of(text):
    m = CUE_PARTS.fullmatch(text)
    return m.group(1) if m else None


def mark_issue(text):
    """What's wrong with a count or cue span, or None."""
    if text.startswith("[cue"):
        return None if cue_of(text) else (f"{text}: the cues are " + ", ".join(CUE_NAMES) + " ([cue rest])")
    got = count_of(text)
    if not got:
        return (f"{text}: write a count as [count N] or [count N cue], N a numeral from {COUNT_MIN} to {COUNT_MAX} "
                "and the cue one of " + ", ".join(CUE_NAMES) + " ([count 5 go])")
    if not COUNT_MIN <= got[0] <= COUNT_MAX:
        return f"{text}: a count runs from {COUNT_MIN} to {COUNT_MAX}"
    return None


def mark_pieces(text):
    """A well-formed count or cue as the clips it plays, in order: [(clip name, beat)], where beat is the
    seconds the clip's slot lasts (BEAT for a number with something after it, so the next starts on the
    beat) or None (the slot is the clip itself). `[count 3 go]`: three, two, one on the beat, then go."""
    cue = cue_of(text)
    if cue:
        return [(cue, None)]
    n, cue = count_of(text)
    nums = [NUMBER_WORDS[k - 1] for k in range(n, 0, -1)]
    return [(w, BEAT if cue or i < n - 1 else None) for i, w in enumerate(nums)] + ([(cue, None)] if cue else [])


def mark_words(text):
    """What a count or cue says, for the transcript: "Three, two, one, go." """
    words = [name for name, _ in mark_pieces(text)]
    return ", ".join(words).capitalize() + "."


def holds(seg):
    """(bare holds, all holds) in a segment: the bare ones share its spare time and keep the segment its
    full length (is_held); a fixed hold is only its own seconds."""
    marks = [secs for para in plan(seg) for text, secs in para if text == HOLD]
    return sum(secs == 0 for secs in marks), len(marks)


def is_held(seg):
    """Whether the segment keeps its full length: it has a bare [hold] to spend its spare time in."""
    return holds(seg)[0] > 0


def plan(seg):
    """A segment as paragraphs of spans, exactly as render.py will voice it."""
    return [spans(p) for p in paragraphs(seg["lines"])]


def layout(segments):
    """Lay segments on the clock. `segments` is [(spoken seconds, paragraph breaks,
    planned seconds[, held])]; returns [(extra seconds per break, laid-out seconds)].

    A segment that runs over makes the next ones late, and their spare time pays it
    back; a segment with time to spare widens its breaks, keeps a short tail and ends
    early, unless it is held (has a bare [hold], is_held): then all its spare time is silence at its
    bare holds. Fixed holds count in its spoken seconds."""
    out, late = [], 0.0
    for spoken_secs, gaps, planned, *rest in segments:
        slack = max(planned - late - spoken_secs, 0.0)
        if rest and rest[0]:
            length = spoken_secs + slack
            late = max(late + length - planned, 0.0)
            out.append((0.0, length))
            continue
        extra = min(max(slack - END_TAIL, 0.0) / gaps, MAX_EXTRA_GAP) if gaps else 0.0
        length = spoken_secs + extra * gaps + min(END_TAIL, slack - extra * gaps)
        late = max(late + length - planned, 0.0)
        out.append((extra, length))
    return out


def fill_flag(spoken_secs, planned, min_fill=MIN_FILL, max_fill=MAX_FILL, held=False):
    """"long" or "short" when a segment's speech is far off its slot, else ""; a held
    segment (one with a bare [hold]) is never short, since its silence is planned."""
    fill = spoken_secs / planned if planned else 0.0
    return "long" if fill > max_fill else "short" if fill < min_fill and not held else ""
