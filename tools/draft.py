"""A segmented workout draft: its format, and how its segments sit on the plan's clock.

Draft format: each segment starts with a marker line
    @@ <seconds> | <label>
followed by the spoken text. Inside the text, [pause 3s] inserts that much silence
(also [pause 500ms]; at most ten seconds), [chime] rings the segment bell at
that point, for example when work starts in a forty-five-and-fifteen interval, and
[hold] marks where the listener works in silence: a segment with a hold keeps its
full planned length, its spare time silent at its bare holds, shared equally ([hold 20s]
is exactly that much silence, with no ten-second cap, and the rest of the spare time
goes to the bare holds, or to the end when there are none).

Before the first marker, a draft declares the movements it scripts, once, on one or more
header lines that are never spoken:
    movements: goblet squat, dumbbell floor press, dead bug, box breathing
`./sweatcast build` checks them against the menu `./sweatcast brief --save` wrote beside
the draft (`menu_path`).

This is the one source of truth for the draft: the lint (tts_build.py) predicts
from it and the render (render.py) lays clips out with it, so they agree.
"""
import os
import re

MARKER = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*)$")
HEADER = re.compile(r"^movements\s*:\s*(.*)$", re.IGNORECASE)   # the declaration, before the first marker
DRAFT_SUFFIX = ".draft.txt"
PAUSE_RE = re.compile(r"\[\s*pause(?:\s+(\d+(?:\.\d+)?)\s*(ms|s)?)?\s*\]", re.IGNORECASE)
CHIME_RE = re.compile(r"\[\s*chime\s*\]", re.IGNORECASE)
HOLD_RE = re.compile(r"\[\s*hold(?:\s+(\d+(?:\.\d+)?)\s*(ms|s)?)?\s*\]", re.IGNORECASE)
MARK_RE = re.compile(PAUSE_RE.pattern + "|" + CHIME_RE.pattern + "|" + HOLD_RE.pattern, re.IGNORECASE)
CHIME = "[chime]"   # a span whose text is this rings the bell instead of speaking
HOLD = "[hold]"     # a span whose text is this takes a share of the segment's spare time as silence
PAUSE_DEFAULT, PAUSE_MAX = 0.35, 10.0   # seconds: a bare [pause], and the longest one
PARAGRAPH_GAP = 0.35                    # least silence between paragraphs within a segment
MAX_CLIP = 22.0                         # longest a paragraph may speak, in seconds
CHIME_SECONDS = 0.6                     # bell plus quiet that opens each segment after the first

# Timing. A segment's spare time widens its paragraph breaks (up to MAX_EXTRA_GAP each)
# and leaves a short tail; past that it ends early rather than going quiet, so the
# workout runs a little under plan instead of padding with silence. A segment with a
# [hold] is the exception: timed work needs its full length, so all its spare time
# becomes silence at its holds. Only the total is held to plan, within
# TOTAL_TOLERANCE; a segment is flagged only when far off (a held one never as short).
END_TAIL = 1.5          # seconds of spare time kept at a segment's end, at most
MAX_EXTRA_GAP = 1.5     # most spare time added to any one paragraph break
TOTAL_TOLERANCE = 0.03  # the whole workout may run this fraction over or under plan
MIN_FILL, MAX_FILL = 0.80, 1.10   # a segment outside these (speech over planned seconds) is flagged


def parse(text):
    segments, current = [], None
    for lineno, line in enumerate(text.splitlines(), 1):
        m = MARKER.match(line.strip())
        if m:
            current = {"seconds": int(m.group(1)), "label": m.group(2).strip(),
                       "lines": [], "start": lineno}
            segments.append(current)
        elif current is None:
            if line.strip() and not HEADER.match(line.strip()):
                raise SystemExit(f"Line {lineno}: text before the first @@ marker "
                                 "(only a movements: line may come first).")
        else:
            current["lines"].append((lineno, line))
    if not segments:
        raise SystemExit("No @@ segment markers found.")
    return segments


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
    """True for a span the voice speaks (not a bare pause, the bell or a hold)."""
    return bool(text) and text not in (CHIME, HOLD)


def holds(seg):
    """(bare holds, all holds) in a segment: the bare ones share its spare time; any hold keeps
    the segment its full length."""
    marks = [secs for para in plan(seg) for text, secs in para if text == HOLD]
    return sum(secs == 0 for secs in marks), len(marks)


def plan(seg):
    """A segment as paragraphs of spans, exactly as render.py will voice it."""
    return [spans(p) for p in paragraphs(seg["lines"])]


def layout(segments):
    """Lay segments on the clock. `segments` is [(spoken seconds, paragraph breaks,
    planned seconds[, held])]; returns [(extra seconds per break, laid-out seconds)].

    A segment that runs over makes the next ones late, and their spare time pays it
    back; a segment with time to spare widens its breaks, keeps a short tail and ends
    early, unless it is held (has a [hold]): then all its spare time is silence, at its bare
    holds or, with none, at its end. Fixed holds count in its spoken seconds."""
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
    segment (one with a [hold]) is never short, since its silence is planned."""
    fill = spoken_secs / planned if planned else 0.0
    return "long" if fill > max_fill else "short" if fill < min_fill and not held else ""
