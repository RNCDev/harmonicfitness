"""Checking a local take: did the voice say the line, and does the clip sound whole?

A local voice sometimes drops, swaps or adds a word, or trails into babble or silence, and the same seed
makes the same mistake every time. render.py has a speech recognizer (tools/engines.py, listener()) hear
each new clip, and scores it here against the line it was given:

- score(): the words heard against the words written, aligned, so a dropped cue word ("rest", "go",
  "switch", a countdown number, "left" or "right") is named, not only counted. Numbers the recognizer
  writes as digits are read as words, and a compound heard split or joined ("warm up", "warmup") counts
  as said.
- problems(): what the audio alone shows: far longer or shorter than the voice's pace predicts (a
  runaway or a cut-off), a long silence inside it, or clipping.

A take passes with every cue word said, no audio problem, and at most one word in twenty off (the
recognizer mishears a little too). Plain Python, with no numpy, so it runs and is tested anywhere.
"""
import re
from array import array

SR = 24000
FRAME = 480                 # 20 ms frames at SR
QUIET_DB = -45.0            # a frame below this level is silence
MAX_GAP = 1.5               # seconds of silence inside a clip that mean a stall
LONG, LONG_PAD = 1.8, 1.0   # a take longer than predicted * LONG + LONG_PAD seconds has run on
SHORT = 0.5                 # a take shorter than predicted * SHORT has been cut off
CLIPPED = 0.001             # the share of samples at full scale that means clipping
ERROR_SHARE = 20            # one word in this many may be off and the take still pass

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
        "sixteen seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
ORDINAL = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth",
           "nine": "ninth", "twelve": "twelfth"}
# The words a listener moves by: a missing one changes what they do, so a take must say every one.
CUES = frozenset(ONES[1:] + TENS[2:] + ["hundred", "go", "rest", "switch", "stop", "start", "begin", "left",
                                         "right", "done", "halfway", "last", "side", "sides", "hold"])
SAME = {"ok": "okay", "alright": "all right"}


def say_number(n):
    """An integer as words, the way a script spells it: years in pairs ("seventeen eighty one")."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if 1100 <= n <= 1999 or 2010 <= n <= 2099:
        hi, lo = divmod(n, 100)
        return say_number(hi) + (" hundred" if lo == 0 else f" oh {ONES[lo]}" if lo < 10 else " " + say_number(lo))
    if n < 1000:
        hi, lo = divmod(n, 100)
        return f"{ONES[hi]} hundred" + ("" if lo == 0 else " " + say_number(lo))
    if n < 1_000_000:
        hi, lo = divmod(n, 1000)
        return f"{say_number(hi)} thousand" + ("" if lo == 0 else " " + say_number(lo))
    return " ".join(ONES[int(d)] for d in str(n))


def _ordinal(words):
    *head, last = words.split()
    if last in ORDINAL:
        last = ORDINAL[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return " ".join(head + [last])


def _number(m):
    whole, frac, suffix, pct = m.group(1), m.group(2), m.group(3), m.group(4)
    out = say_number(int(whole))
    if frac:
        out += " point " + " ".join(ONES[int(d)] for d in frac)
    if suffix:
        out = _ordinal(out)
    if pct:
        out += " percent"
    return f" {out} "


NUMBER_RE = re.compile(r"(\d+)(?:\.(\d+))?(st|nd|rd|th)?(%)?", re.IGNORECASE)


def words(text):
    """The words of `text`, lowercased, digits read as words, punctuation and hyphens gone."""
    text = text.lower().replace("’", "'").replace(",", "")
    text = NUMBER_RE.sub(_number, text)
    out = []
    for w in re.findall(r"[a-z0-9']+", text.replace("-", " ")):
        w = w.strip("'")
        if w:
            out += SAME.get(w, w).split()
    return out


def align(ref, hyp):
    """Align the written words with the heard ones: (errors, the written words not heard as written).
    A written pair heard as one word, or one heard as two, costs nothing when the letters match."""
    n, m = len(ref), len(hyp)
    INF = float("inf")
    d = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    d[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            here = d[i][j]
            if here == INF:
                continue
            steps = []
            if i < n and j < m:
                steps.append((i + 1, j + 1, 0 if ref[i] == hyp[j] else 1, "sub"))
            if i < n:
                steps.append((i + 1, j, 1, "del"))
            if j < m:
                steps.append((i, j + 1, 1, "ins"))
            if i + 1 < n and j < m and ref[i] + ref[i + 1] == hyp[j]:
                steps.append((i + 2, j + 1, 0, "join"))
            if i < n and j + 1 < m and hyp[j] + hyp[j + 1] == ref[i]:
                steps.append((i + 1, j + 2, 0, "split"))
            for a, b, cost, op in steps:
                if here + cost < d[a][b]:
                    d[a][b], back[a][b] = here + cost, (i, j, op)
    missed, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj, op = back[i][j]
        if op == "del" or (op == "sub" and ref[pi] != hyp[pj]):
            missed.append(ref[pi])
        i, j = pi, pj
    return int(d[n][m]), list(reversed(missed))


def score(line, heard):
    """{"words", "errors", "missed_cues"} for the take of `line` the recognizer heard as `heard`."""
    ref, hyp = words(line), words(heard)
    errors, missed = align(ref, hyp)
    return {"words": len(ref), "errors": errors, "missed_cues": [w for w in missed if w in CUES]}


def frame_db(pcm):
    """The level of each 20 ms frame of 16-bit mono PCM, in dBFS."""
    import math
    pcm = pcm[: len(pcm) // 2 * 2]
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:   # where the local voices run; the loop below does the same, slower
        x = np.frombuffer(pcm, dtype="<i2")[: len(pcm) // 2 // FRAME * FRAME].astype(np.float64)
        power = (x.reshape(-1, FRAME) ** 2).mean(axis=1) if len(x) else np.zeros(0)
        with np.errstate(divide="ignore"):
            return [float(v) if np.isfinite(v) else -120.0 for v in 10 * np.log10(power / 32768 ** 2)]
    a = array("h")
    a.frombytes(pcm)
    out = []
    for k in range(0, len(a) - FRAME + 1, FRAME):
        power = sum(x * x for x in a[k:k + FRAME]) / FRAME
        out.append(10 * math.log10(power / 32768 ** 2) if power else -120.0)
    return out


def problems(pcm, predicted):
    """What the audio alone says is wrong with a take, as short phrases (none: it sounds whole).
    `predicted` is the voice's predicted length for the line, in seconds."""
    seconds = len(pcm) / 2 / SR
    found = []
    if predicted:
        if seconds > predicted * LONG + LONG_PAD:
            found.append(f"runs {seconds:.1f}s for about {predicted:.1f}s of words")
        elif seconds < predicted * SHORT:
            found.append(f"stops after {seconds:.1f}s, short of about {predicted:.1f}s of words")
    levels = frame_db(pcm)
    loud = [k for k, db in enumerate(levels) if db > QUIET_DB]
    if loud:
        gap = run = 0
        for db in levels[loud[0]:loud[-1] + 1]:
            run = run + 1 if db <= QUIET_DB else 0
            gap = max(gap, run)
        if gap * FRAME / SR > MAX_GAP:
            found.append(f"goes silent for {gap * FRAME / SR:.1f}s")
    a = array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    if a and sum(1 for x in a if x >= 32767 or x <= -32767) > CLIPPED * len(a):
        found.append("clips")
    return found


def judge(line, heard, pcm, predicted):
    """The verdict on one take: score() plus "problems", and "ok" when it passes."""
    v = score(line, heard)
    v["heard"] = heard
    v["problems"] = problems(pcm, predicted)
    v["ok"] = not v["missed_cues"] and not v["problems"] and v["errors"] * ERROR_SHARE <= v["words"]
    return v


def rank(v):
    """Sort key for takes: fewest missed cues, then audio problems, then word errors."""
    return (len(v["missed_cues"]), len(v["problems"]), v["errors"])
