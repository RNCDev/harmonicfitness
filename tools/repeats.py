"""Lines a draft repeats from the listener's last few workouts: a sentence of SENTENCE_WORDS or more said word for
word in an earlier draft reads as a template over a run of sessions ("This is the one that counts" every week).
A warning the build prints after the lint, never an issue: a safety line or a limit cue is meant to repeat, and
those are left out. Library only; build.py calls it."""
import glob
import os
import re
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draft  # noqa: E402
import errors  # noqa: E402
import paths  # noqa: E402

LAST = 5              # earlier workouts compared
SENTENCE_WORDS = 6    # a sentence this long, said word for word before, is a repeat
SHOWN = 8             # repeats listed at most
SENTENCE = re.compile(r"(?<=[.!?])\s+")
# safety lines repeat on purpose: the opening's rules, the stop rule, the clinician's words
SAFETY = re.compile(r"\b(pain|stop|clinician|physio|physiotherapist|doctor|swelling|rule|rules)\b", re.I)


def _norm(sentence: str) -> str:
    return " ".join(re.findall(r"[a-z']+", sentence.lower()))


def sentences(text: str) -> List[str]:
    """The spoken sentences of a draft's text: markers and story tags out, split at sentence ends."""
    segs = draft.parse(text)
    out = []
    for seg in segs:
        for para in draft.paragraphs(seg["lines"]):
            spoken = " ".join(draft.MARK_RE.sub(" ", para).split())
            out += [s for s in SENTENCE.split(spoken) if s.strip()]
    return out


def earlier(draft_path: str, last: int = LAST) -> List[str]:
    """The drafts of the `last` workouts before this one (by folder name, which starts with the date), when the
    draft sits in its own folder under me/workouts/; else none."""
    here = os.path.abspath(draft_path)
    if os.path.dirname(os.path.dirname(here)) != os.path.abspath(paths.WORKOUTS):
        return []
    mine = os.path.basename(os.path.dirname(here))
    found = sorted(p for p in glob.glob(os.path.join(paths.WORKOUTS, "*", "*" + draft.DRAFT_SUFFIX))
                   if os.path.basename(os.path.dirname(p)) < mine)
    return found[-last:]


def repeats(draft_path: str, text: str, cue_sentences=frozenset(), last: int = LAST) -> List[str]:
    """Warnings for the sentences `text` says word for word from an earlier workout's draft (earlier), leaving out
    safety lines and the shipped limit cues (`cue_sentences`, as menu._cue_sentences gives them)."""
    before = {}
    for path in earlier(draft_path, last):
        try:
            with open(path, encoding="utf-8") as f:
                old = sentences(f.read())
        except (OSError, *errors.PROBLEMS):
            continue
        for s in old:
            before.setdefault(_norm(s), os.path.basename(os.path.dirname(path)))
    if not before:
        return []
    out, seen = [], set()
    for s in sentences(text):
        key = _norm(s)
        if len(key.split()) < SENTENCE_WORDS or key in seen or SAFETY.search(s) or key in cue_sentences:
            continue
        if key in before:
            seen.add(key)
            out.append(f'"{s.strip()}" is said word for word in {before[key]}; say it fresh, so the sessions don\'t '
                       "sound like a template")
    if len(out) > SHOWN:
        out = out[:SHOWN] + [f"and {len(out) - SHOWN} more repeated sentence(s)"]
    return out
