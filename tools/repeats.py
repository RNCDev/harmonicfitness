"""Two warnings about how a draft sounds over time, never issues. Lines it repeats from the listener's last few workouts: a sentence of SENTENCE_WORDS or more said word for
word in an earlier draft reads as a template over a run of sessions ("This is the one that counts" every week).
A warning the build prints after the lint, never an issue: a safety line or a limit cue is meant to repeat, and
those are left out. And lines that claim to have seen the listener ("that set looked smoother", "best set yet",
"not once"): the coach has no eyes on them, so praise like that is made up (seen_claims). Library only; build.py
calls both."""
import glob
import os
import re
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog
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


# what only eyes would know (knowledge/script.md, The coach can't see them); stories are left out
SEEN = re.compile(
    r"\b(?:that|this|the last|your|the) (?:set|rep|round|one|interval|lap|climb|carry)s? (?:looked|look|was looking)\b"
    r"|\blooked (?:good|great|strong|stronger|smooth|smoother|clean|cleaner|solid|sharp|sharper|easy|easier)\b"
    r"|\b(?:best|strongest|cleanest|smoothest|fastest) (?:set|rep|round|one|interval|lap) (?:yet|so far|of the day|today)\b"
    r"|\bnot once\b"
    r"|\bI (?:can )?(?:see|saw|noticed|watched) (?:you|your|that)\b"
    r"|\b(?:stayed|kept|held|was|were) [a-z]+ (?:on |through |for )?every (?:single )?(?:set|rep|round|one|interval)\b"
    r"|\bthat'?s (?:exactly |just )?(?:where|what) (?:we|I) want(?:ed)? (?:it|you|to see)?\b"
    r"|\b(?:that was a|that's a|what a|and a) (?:really )?(?:strong|great|solid|excellent|powerful|fantastic) "
    r"(?:first |last )?(?:ride|session|workout|set|effort|climb|surge|round|sprint|interval|one)\b"
    r"|\b(?:nailed|crushed|smashed) (?:it|that|all|every|those|each)\b"
    # 0.82.0, from a 40-minute session's rests: "the tempo has been rock solid", "every movement pattern is dialed
    # in", "you're moving with tremendous focus", "that was sharp, controlled work"
    r"|\b(?:has|have|had) been (?:rock solid|rock steady|spot on|dialed in|flawless|perfect|sharp|smooth|clean)\b"
    r"|\b(?:is|are|was|were|looks|looked) (?:all |totally |completely )?dialed in\b"
    r"|\byou(?:'re| are| were|'ve been| have been) moving (?:with|well|beautifully|smoothly|great)\b"
    r"|\bthat was (?:sharp|smooth|clean|crisp|tight|controlled|solid|flawless)\b"
    r"|\byou(?:'re| are) (?:flying|crushing it|killing it)\b"
    r"|\b(?:executed|done|performed) with (?:clean|perfect|great|good|solid) (?:form|technique)\b"
    r"|\b(?:solid|great|real|good) (?:discipline|work stepping|control)\b|\bsolid work\b"
    r"|\b(?:completely|totally|perfectly) (?:safe|protected|stable)\b"
    r"|\b(?:clean|crisp|smooth|solid) (?:dumbbell |kettlebell |barbell )?(?:pressing|presses|deadlifts|squats|rows|reps|form|technique)\b"
    r"|\b(?:great|excellent|perfect|beautiful|fantastic|outstanding|sharp|tremendous) (?:execution|control|posture|form"
    r"|technique|strength|focus|tempo)\b"
    r"|\b(?:outstanding|beautiful|perfect|excellent|fantastic) (?:set|rep|round|carry|press|pull|lift|squat|lunge)s?\b"
    r"|\bwith (?:fantastic|great|excellent|perfect|beautiful|total|real) control\b"
    r"|\b(?:held|kept) your (?:posture|form|back|spine|core|hips|chest) (?:clean|perfect|tight|steady|straight|neutral"
    r"|solid|tall)\b",
    re.IGNORECASE)
# "eight to ten clean reps" sets a target; it's a claim only when it praises what was done
TARGET_BEFORE = re.compile(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|\d+)"
                           r"\s+(?:more\s+)?$", re.IGNORECASE)


STACKED = 3   # stories in one segment past which it's a pile, not a rest: "one story to a rest" (script.md)
WORK = re.compile(r"\[count \d+ go\]|\[hold", re.IGNORECASE)   # a set under way: its stories are one, broken by the checks


def stacked_stories(text: str) -> List[str]:
    """Warnings for a rest holding STACKED or more [story] blocks: unrelated items told back to back. A timed set's
    one story, broken by its time checks (script.md's own example), is left alone (0.59.0)."""
    out = []
    for seg in draft.parse(text):
        if WORK.search("\n".join(line for _, line in seg["lines"])):
            continue
        stories = draft.story_split(seg)[1]
        if len(stories) >= STACKED:
            out.append(f'segment "{seg["label"]}" tells {len(stories)} stories in a row; one story to a rest (a longer '
                       "rest gets a bigger story, not two or three), the others to other rests or left untold")
    return out[:SHOWN]


EMPTY_STORY = re.compile(r"\[story\]\s*\[/story\]", re.IGNORECASE)   # a skeleton's mark for a piece told in the work
WORD = re.compile(r"[A-Za-z][A-Za-z']*")
# How far under the content plan's story share a draft may land before it's named: a session's stories move with
# what research found, so only a clear shortfall is worth a warning (0.82.0).
BALANCE_SLACK = 0.1


def _spoken_words(text: str) -> int:
    return len(WORD.findall(draft.STORY_TAG_RE.sub(" ", draft.MARK_RE.sub(" ", text))))


def story_share(text: str) -> tuple:
    """(the words told inside [story] tags, all the words spoken) across a draft; (0, 0) for a skeleton."""
    told = spoken = 0
    for seg in draft.parse(text):
        coaching, stories, _ = draft.story_split(seg)
        n = sum(_spoken_words(s) for s in stories)
        told, spoken = told + n, spoken + n + _spoken_words(coaching)
    return told, spoken


def story_balance(text: str, share: float, in_work: int) -> List[str]:
    """Warnings for a session whose talk is mostly instruction, against the content plan's `share` of the spoken
    words told as stories and its `in_work` pieces told during steady timed sets. A skeleton is checked by its plan:
    a counted set carries cues only, so a skeleton of counted sets with few timed sets marked for a piece makes a
    script of instruction however the rests are written (the listener's 2026-11-16 40-minute session: twelve
    counted sets, three marked, 29 percent stories against the half they asked for)."""
    told, spoken = story_share(text)
    if not spoken:
        segs = [("\n".join(line for _, line in seg["lines"])) for seg in draft.parse(text)]
        marked = sum(1 for body in segs if EMPTY_STORY.search(body))
        counted = sum(1 for body in segs if draft.REPS_RE.search(body))
        if in_work and marked < in_work and counted > marked:
            return [f"this skeleton marks {marked} timed set(s) for a piece and has {counted} counted set(s), and the "
                    f"content plan tells about {in_work} pieces in the work: a counted set carries cues only, so make "
                    "the steady sets timed (forty to sixty seconds at the dose's load) and mark each with an empty "
                    "[story] [/story] after its go, keeping counted sets for the heaviest lifts"]
        return []
    if share and told / spoken < share - BALANCE_SLACK:
        return [f"stories are {told / spoken:.0%} of the spoken words and the content plan aims for about {share:.0%}: "
                "the set-ups after a movement's first round are one line, a counted set's cues say only what the "
                "listener needs (the side, the tempo, the switch), and the time that frees goes to the rests' "
                "stories and the timed sets' pieces"]
    return []


# a figure said aloud: digits, or a run of number words holding a magnitude ("sixteen point three billion")
_NUMBER = (r"(?:\d[\d,.]*|zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
           r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
           r"hundred|thousand|million|billion|trillion|point|percent|and|a)")
FIGURE_RUN = re.compile(rf"\b{_NUMBER}(?:[\s-]+{_NUMBER})*\b", re.IGNORECASE)
MAGNITUDE = re.compile(r"\d|hundred|thousand|million|billion|trillion|percent", re.IGNORECASE)
FIGURES = 4   # figures in one segment's stories past which the ear can't hold them (judges marked down five to nine)


def crowded_figures(text: str) -> List[str]:
    """Warnings for a segment whose stories say more than FIGURES figures: a list of numbers read out, which a
    listener mid-workout can't follow (loop 2 of the 30-minute evals read nine from one filing)."""
    out = []
    for seg in draft.parse(text):
        stories = " ".join(draft.story_split(seg)[1])
        figures = [m.group(0) for m in FIGURE_RUN.finditer(stories) if MAGNITUDE.search(m.group(0))]
        if len(figures) > FIGURES:
            out.append(f'segment "{seg["label"]}" reads out {len(figures)} figures ({", ".join(f.strip() for f in figures[:4])}'
                       f"...); keep the one or two that make the point and say what they mean for the listener")
    return out[:SHOWN]


WHOLE_BODY = (("push", ("horizontal-push", "vertical-push")), ("pull", ("horizontal-pull", "vertical-pull")),
              ("squat or lunge", ("squat", "lunge")), ("hinge", ("hinge",)))


def missing_patterns(cat, text: str, menu: dict) -> List[str]:
    """For a full-body session (goal general, no target), a warning naming each of push, pull, squat or lunge, and
    hinge that no declared movement trains while today's menu allows one: every 30-minute full-body script in
    the evals left out the pull. A pattern today's limits leave off the menu isn't asked for."""
    request = (menu or {}).get("request") or {}
    if request.get("goal") != "general" or request.get("target"):
        return []

    def patterns(names):
        found = set()
        for name in names:
            m = catalog.resolve(cat, name)
            if m:
                found.update(m.patterns)
        return found
    trained = patterns(draft.declared(text))
    allowed = patterns(m.get("id", "") for m in menu.get("movements") or [] if isinstance(m, dict))
    gone = [label for label, pats in WHOLE_BODY if not trained.intersection(pats) and allowed.intersection(pats)]
    return [f"a whole-body session with no {', no '.join(gone)}: add {'it' if len(gone) == 1 else 'them'} from "
            "the menu (a light set or two is enough when the morning trained it)"] if gone else []


SAME_SHARE = 0.5   # a draft sharing this much of its movements with a recent workout sounds like a rerun
SAME_LEAST = 4     # and at least this many: a short session can share a warm-up without being one
SAME_LAST = 2      # earlier days compared (programming.md, Variety: the last two sessions)


def same_movements(cat, draft_path: str, text: str) -> List[str]:
    """A warning when the draft's movements are mostly those of one of the last SAME_LAST days' workouts (the last
    draft of each earlier day, so a same-day rewrite isn't compared with itself): the sessions ran as two
    alternating templates while the menu held a hundred more movements."""
    def ids(names):
        return {m.id for m in (catalog.resolve(cat, n) for n in names) if m}
    mine = ids(draft.declared(text))
    if len(mine) < SAME_LEAST:
        return []
    today = os.path.basename(os.path.dirname(os.path.abspath(draft_path)))[:10]
    by_day = {}
    for path in earlier(draft_path, last=50):
        day = os.path.basename(os.path.dirname(path))[:10]
        if day < today:
            by_day[day] = path   # sorted, so the day's last draft wins
    out = []
    for day in sorted(by_day)[-SAME_LAST:]:
        try:
            with open(by_day[day], encoding="utf-8") as f:
                shared = mine & ids(draft.declared(f.read()))
        except (OSError, UnicodeDecodeError, errors.HarmonicFitnessError):
            continue
        if len(shared) >= SAME_LEAST and len(shared) >= SAME_SHARE * len(mine):
            names = sorted(cat.movements[i].name for i in shared)
            out.append(f"{len(shared)} of today's {len(mine)} movements were in the {day} workout too ("
                       + ", ".join(names) + "): keep at most two main ones to progress, and swap the rest, warm-up "
                       "and cool-down included, for movements the menu shows untagged")
    return out


def seen_claims(text: str) -> List[str]:
    """Warnings for coaching sentences that claim to have seen the listener (SEEN), outside [story] tags."""
    out = []
    for seg in draft.parse(text):
        coaching = draft.story_split(seg)[0]
        for para in draft.paragraphs([(0, line) for line in coaching.split("\n")]):
            spoken = " ".join(draft.MARK_RE.sub(" ", para).split())
            for sentence in SENTENCE.split(spoken):
                m = SEEN.search(sentence)
                if m and m.group(0).lower().startswith(("clean ", "crisp ", "smooth ", "solid ")) \
                        and TARGET_BEFORE.search(sentence[:m.start()]):
                    m = None
                if m:
                    out.append(f'"{sentence.strip()}" says the coach saw them ("{m.group(0)}"), but the coach has no '
                               "eyes on the listener; ask how it felt, or plan from their answer")
    return out[:SHOWN]
