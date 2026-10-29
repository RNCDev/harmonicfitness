"""Workout audio as 16-bit mono PCM at SR: silence, each clip leveled to one speech level, the segment chime and
end tone, and assemble(), which lays the clips on the plan's clock. Pure sound, no files, no ffmpeg."""
from array import array
import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
from draft import CHIME, CHIME_SECONDS, HOLD, PARAGRAPH_GAP, fill_flag, is_held, is_mark, layout, plan  # noqa: E402
from engines import SR  # noqa: E402
import verify  # noqa: E402


CHIME_TONE = 0.35     # seconds of bell; the rest of CHIME_SECONDS is quiet before the voice


CHIME_LEVEL = 0.12    # peak; at 0.2 the bell averaged as loud as the voice, so this sits about 4 dB under


END_NOTES = (660, 880, 1320)   # Hz, rising, so the end can't be mistaken for a segment bell


END_NOTE = 0.3        # seconds per note


END_LEAD = 1.0        # seconds of quiet before the end tone


SPEECH_LEVEL = -24.0  # dBFS each clip's speech is leveled to before assembly (clips drift a few dB apart)


LEVEL_MAX = 12.0      # most dB a clip is raised or lowered


LEVEL_SKIP = 0.5      # a clip within this many dB is left alone


LEVEL_PEAK = 0.89     # a raised clip's peak stays under this (-1 dBFS)


def silence(seconds):
    return b"\x00\x00" * max(int(seconds * SR), 0)


def speech_level(pcm):
    """The level of a clip's speech in dBFS: the mean power of its frames above the silence line."""
    loud = [db for db in verify.frame_db(pcm) if db > verify.QUIET_DB + 5]
    if not loud:
        return None
    return 10 * math.log10(sum(10 ** (db / 10) for db in loud) / len(loud))


def level(pcm):
    """The clip with its speech brought to SPEECH_LEVEL (at most LEVEL_MAX dB either way, its peak kept
    under LEVEL_PEAK), so one clip doesn't sit a few dB under the next. The loudness pass then sets the
    whole workout's level."""
    found = speech_level(pcm)
    if found is None:
        return pcm
    db = max(-LEVEL_MAX, min(LEVEL_MAX, SPEECH_LEVEL - found))
    pcm = pcm[: len(pcm) // 2 * 2]
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:   # where the local voices run; the loop below does the same, slower
        x = np.frombuffer(pcm, dtype="<i2")
        peak = max(1, int(np.abs(x.astype(np.int32)).max()))
    else:
        a = array("h")
        a.frombytes(pcm)
        peak = max(1, max(a), -min(a))
    gain = min(10 ** (db / 20), LEVEL_PEAK * 32767 / peak)
    if abs(20 * math.log10(gain)) < LEVEL_SKIP:
        return pcm
    if np is not None:
        return (x * gain).astype("<i2").tobytes()
    return array("h", [int(v * gain) for v in a]).tobytes()


def _bell(seconds, partials, decay=9.0):
    n = int(seconds * SR)
    samples = []
    for i in range(n):
        t = i / SR
        env = min(t / 0.005, 1.0) * math.exp(-decay * t)   # quick attack, bell-like decay
        v = sum(a * math.sin(2 * math.pi * f * t) for f, a in partials)
        samples.append(int(CHIME_LEVEL * env * v * 32767))
    return struct.pack(f"<{n}h", *samples)


def chime():
    """A soft two-note bell that marks a new segment, so the ear has a timing anchor
    even if a spoken cue gets mangled. Followed by a short quiet before the voice."""
    return _bell(CHIME_TONE, ((880, 0.6), (1320, 0.4))) + silence(CHIME_SECONDS - CHIME_TONE)


def end_tone():
    """Three rising notes after the last segment: the workout is over, not the earbud."""
    return silence(END_LEAD) + b"".join(_bell(END_NOTE, ((f, 0.7), (f * 2, 0.3)), decay=6.0)
                                        for f in END_NOTES) + silence(0.5)


def assemble(segments, clip, lead=b"", bell=None, tail=b"", mark=None):
    """Lay the clips out on the plan's clock, as draft.layout predicts.

    clip(text) returns a clip's PCM. `lead` (the chime) opens every segment after
    the first, `bell` rings at each [chime] marker (default: the chime), `mark(text)` returns a
    count's or cue's PCM (the coach's recorded clips on the beat, counts.pcm), and `tail`
    (the end tone) follows the last segment, past the plan's clock. A segment with
    time to spare widens its breaks and ends early instead of padding with silence,
    unless it has a bare [hold]: its spare time is then silence at its bare holds.
    Returns (pcm, rows, drift): rows as (n, planned, spoken, label, flag), drift as
    the whole workout's fraction over (+) or under (-) plan, not counting the tail."""
    bell = chime() if bell is None else bell
    built = []
    for i, seg in enumerate(segments, 1):
        paras = []   # each paragraph: PCM pieces, with None where a hold falls
        for para in plan(seg):
            p = [bytearray()]
            for text, pause in para:
                if text == CHIME:
                    p[-1] += bell
                elif text == HOLD:   # a fixed hold is its silence; a bare one takes its share of the spare
                    if not pause:
                        p += [None, bytearray()]
                elif is_mark(text):
                    if mark is None:
                        raise errors.RenderStopped(f"{text}: this render has no recorded counts to play")
                    p[-1] += mark(text)
                elif text:
                    p[-1] += clip(text)
                p[-1] += silence(pause)
            paras.append(p)
        head = lead if i > 1 else b""
        gaps = len(paras) - 1
        spoken = (len(head) + sum(len(x) for p in paras for x in p if x is not None)) / 2 / SR \
            + PARAGRAPH_GAP * gaps
        held = is_held(seg)   # the one rule the lint uses too
        built.append((head, paras, spoken, gaps, sum(x is None for p in paras for x in p), held))

    pcm_all, rows = bytearray(), []
    timeline = layout([(spoken, gaps, seg["seconds"], held) for seg, (_, _, spoken, gaps, _, held) in zip(segments, built)])
    for i, (seg, (extra, length)) in enumerate(zip(segments, timeline), 1):
        head, paras, spoken, gaps, n, held = built[i - 1]
        built[i - 1] = None   # this segment's paragraph copies go once it's laid out, not at the end
        hold = max(length - spoken, 0.0) / n if n else 0.0
        seg_pcm = bytearray(head)
        for j, p in enumerate(paras):
            if j:
                seg_pcm += silence(PARAGRAPH_GAP + extra)
            for x in p:
                seg_pcm += silence(hold) if x is None else x
        seg_pcm += silence(length - len(seg_pcm) / 2 / SR)
        flag = fill_flag(spoken, seg["seconds"], held=held)
        rows.append((i, seg["seconds"], spoken, seg["label"], f"  <-- {flag}" if flag else ""))
        pcm_all += seg_pcm
        del head, paras, seg_pcm
    planned = sum(seg["seconds"] for seg in segments)
    drift = len(pcm_all) / 2 / SR / planned - 1 if planned else 0.0
    pcm_all += tail
    return pcm_all, rows, drift
