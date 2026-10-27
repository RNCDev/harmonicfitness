"""A coach's recorded counts and cues: what a draft's [count 5 go] and [cue rest] play.

A shipped coach keeps them in cues/ beside its clip: one WAV per number (ten.wav ... one.wav) and per cue
(go.wav, switch-sides.wav ...), 24 kHz mono 16-bit, already leveled, and cues.toml listing each one's words
and seed (tools/coachmaker/cues.py makes them once, by ear). The lint reads each WAV's length and the render
its audio, and both lay them out by draft.mark_pieces, so the prediction is exact. Nothing about a count is
rendered or checked at build time.
"""
import functools
import os
import tomllib
import wave

import draft

FILE = "cues.toml"


def folder(clip):
    """The cues/ folder beside a coach's clip, or None when it has no recorded counts."""
    d = os.path.join(os.path.dirname(os.path.abspath(clip)), "cues")
    return d if os.path.isfile(os.path.join(d, FILE)) else None


@functools.lru_cache(maxsize=16)
def table(where):
    """{clip name: (wav path, seconds)} for the clips cues.toml lists and the folder holds; names as a draft says
    them ("three", "switch sides")."""
    with open(os.path.join(where, FILE), "rb") as f:
        data = tomllib.load(f)
    out = {}
    for kind in ("count", "cue"):
        for key, row in data.get(kind, {}).items():
            name = key.replace("_", " ")
            path = os.path.join(where, row.get("file") or key + ".wav")
            if os.path.isfile(path):
                with wave.open(path, "rb") as w:   # the file's own length, so the lint matches the render exactly
                    out[name] = (path, w.getnframes() / w.getframerate())
    return out


def missing(text, voice):
    """The clips a well-formed count or cue needs that the coach doesn't have (all of them without a cues/)."""
    names = [name for name, _ in draft.mark_pieces(text)]
    got = table(voice["cues"]) if voice.get("cues") else {}
    return [n for n in names if n not in got]


def seconds(text, voice):
    """How long a well-formed count or cue plays, as pcm() lays it out."""
    got = table(voice["cues"])
    return sum(max(beat, got[name][1]) if beat else got[name][1] for name, beat in draft.mark_pieces(text))


def _pcm(path):
    with wave.open(path, "rb") as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, 24000):
            raise SystemExit(f"{path}: a count or cue clip must be 24 kHz mono 16-bit")
        return w.readframes(w.getnframes())


def pcm(text, voice):
    """The audio of a count or cue: each number padded to the beat, so the next starts on it."""
    if not voice.get("cues"):
        raise SystemExit(f"{voice.get('name', 'This coach')} has no recorded counts: write {text} out in words.")
    got = table(voice["cues"])
    out = bytearray()
    for name, beat in draft.mark_pieces(text):
        clip = _pcm(got[name][0])
        out += clip
        if beat:
            out += bytes(max(int(round(beat * 24000)) * 2 - len(clip), 0))
    return bytes(out)
