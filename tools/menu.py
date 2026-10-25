"""Today's menu, and the build's check that a draft scripts nothing else.

`./sweatcast brief --save <stem>` writes `<stem>.menu.json` beside the draft: the request and every
movement `catalog.select` allowed today, healthy-side-only ones with the side to work. The draft
declares what it scripts on a `movements:` line (draft.py), and `check` finds:
- issues (the build stops): no menu; a declared movement that isn't on it or
  isn't a movement at all; nothing declared; the text naming a catalog movement that isn't on the
  menu; segments that don't add up to the request's seconds;
- warnings: the text naming a menu movement the declaration leaves out (add it, so the log has it).

The text is scanned for every name and alias, longest first, so "single-leg glute bridge" isn't also
read as "glute bridge", except the one-word aliases in EVERYDAY (squat, swing, curl, plank): they are
everyday coaching words ("swing your arms"), or words a filler story uses ("skiing"), and the
declaration is what the build checks. A shortened name of a declared movement ("the bench press" for
the dumbbell bench press) counts as that movement. A mention right after "no", "not", "skip",
"instead of" or "like", with only small words such as "the" or "doing" between, isn't an instruction
("no neck rolls today", "we're not doing jumping jacks", "like a brisk walk"); "no rest between
jumping jacks" is.
Library only; the brief and the build call it.
"""
import datetime
import hashlib
import json
import os
import re
from typing import Dict, List, Optional, Tuple

import catalog
import draft
import paths

FORMAT = 2   # 2 (13.0.0): health_sha256, so the build knows the menu was made from today's health.md
EFFORT_WORDS = {"easy", "steady", "hard", "brisk", "light", "slow", "quick", "fast", "gentle"}


def record(request: dict, sel: catalog.Selection, sides: Dict[str, str], seconds: int, date: str,
           health_sha256: Optional[str] = None) -> dict:
    """The menu file's contents: the request, the day, a hash of health.md as the brief read it, and every
    movement allowed."""
    def entry(m, side=None):
        out = {"id": m.id, "name": m.name, "aliases": list(m.aliases)}
        if side:
            out["side"] = side
        return out
    return {"format": FORMAT, "date": date, "health_sha256": health_sha256, "request": request, "seconds": seconds,
            "movements": [entry(m) for m in sel.allowed] + [entry(m, sides.get(m.id, "healthy"))
                                                            for m in sel.healthy_side_only]}


def health_hash(path: Optional[str] = None) -> Optional[str]:
    """sha256 of health.md's bytes (the limits and the clinician's rules), or None when there's no such file."""
    path = path or paths.HEALTH
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def staleness(menu: dict, today: Optional[str] = None, health_path: Optional[str] = None) -> List[str]:
    """Why this menu can't stand for today: it was saved another day (a check-in's limit for today lives only
    in the menu), or health.md has changed since the brief read it. Empty when it can."""
    today = today or datetime.date.today().isoformat()
    out = []
    if menu.get("date") != today:
        out.append(f"the menu is from {menu.get('date') or 'an unknown day'}, not today ({today}): rerun "
                   "./sweatcast brief ... --save <the draft's path>, so today's limits apply")
    current = health_hash(health_path)
    if not menu.get("health_sha256"):
        out.append("the menu predates the brief's health check: rerun ./sweatcast brief ... --save <the draft's path>")
    elif current and menu["health_sha256"] != current:
        out.append("health.md changed since the brief read it: rerun ./sweatcast brief ... --save <the draft's path>, "
                   "so the menu follows the new limits")
    return out


def report_lines(draft_path: str, issues: List[str], warnings: List[str], declared: int) -> List[str]:
    """The menu check as the lint and the build print it."""
    if issues or warnings:
        return [f"\nMenu check ({paths.show(os.path.abspath(draft.menu_path(draft_path)))}):"] \
            + [f"  {i}" for i in issues] + [f"  warning: {w}" for w in warnings]
    return [f"\nMenu check: every movement is on today's menu ({declared} declared)."]


def gate(cat: catalog.Catalog, draft_path: str, text: str, segments, today: Optional[str] = None,
         health_path: Optional[str] = None, strict: bool = True, required: bool = True) -> Tuple[List[str], List[str]]:
    """(issues, warnings) for a draft against the menu beside it: the one entry point the build, the render and
    the lint use. No menu is an issue when `required`; a menu that can't be read is one too; a stale menu
    (staleness) is an issue when `strict` (a render) and a warning otherwise (a lint)."""
    path = draft.menu_path(draft_path)
    if not os.path.exists(path):
        return check(cat, None, text, segments) if required else ([], [])
    try:
        menu = load(path)
    except ValueError as e:
        return ([f"the menu beside the draft can't be read ({os.path.basename(path)}: {e}): rerun ./sweatcast brief "
                 "... --save <the draft's path>"], [])
    if not isinstance(menu, dict):
        return ([f"the menu beside the draft isn't a menu ({os.path.basename(path)}): rerun ./sweatcast brief ... "
                 "--save <the draft's path>"], [])
    issues, warnings = check(cat, menu, text, segments)
    stale = staleness(menu, today, health_path)
    if strict:
        issues += stale
    else:
        warnings += stale
    return issues, warnings


def write(path: str, menu: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(menu, f, indent=1)
        f.write("\n")


def load(path: str) -> Optional[dict]:
    """The menu at `path`, or None when there is none."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _norm(text: str) -> str:
    return catalog.plain(text, hyphens=True)


# one-word aliases left out of the scan: coaching cues ("swing your arms", "press through the heels") or
# words a filler story uses ("skiing season", "the Sphinx"); every other one-word alias is scanned
EVERYDAY = {"squat", "swing", "curl", "plank", "bridge", "run", "march", "marching", "stairs", "row", "press",
            "shuffles", "windmill", "halo", "halos", "skiing", "clams", "bicycles", "sphinx", "walk", "step"}


def _patterns(cat: catalog.Catalog) -> List[Tuple[re.Pattern, str, str]]:
    """(regex, movement id, the name it matches) for every name and alias the text scan checks,
    longest first; built once per catalog object and kept on it."""
    cached = cat.__dict__.get("_menu_patterns")
    if cached is not None:
        return cached
    found = {}
    for m in cat.movements.values():
        for name in [m.name] + m.aliases:
            key = _norm(name)
            if key in EVERYDAY and name != m.name:
                continue   # an everyday coaching word (squat, swing, curl, plank)
            found.setdefault(key, (m.id, name))
    # "push up" and "step up" are cues as often as names: when a hyphenated name has the same words,
    # only the hyphenated spelling counts
    found = {k: v for k, v in found.items() if not (" " in k and "-" not in k and k.replace(" ", "-") in found)}
    # "easy rows", "a brisk walk", "a steady ride" describe effort as often as they name a movement;
    # an effort word stays a name only before equipment ("steady bike", "steady rowing")
    gear = {w for e, info in cat.equipment.items() for name in [e] + info.get("aliases", [])
            for w in _norm(name).replace("-", " ").split()}
    found = {k: v for k, v in found.items()
             if not (len(k.split()) == 2 and k.split()[0] in EFFORT_WORDS and k.split()[1] not in gear)}
    out = []
    for key in sorted(found, key=len, reverse=True):
        words = key.split(" ")
        if len(words) > 1:   # "single-leg glute bridge" also matches "single leg glute bridge"
            body = r"[\s-]+".join(re.escape(w).replace(r"\-", r"[\s-]?") for w in words) + r"(?:e?s)?"
        elif "-" in key:     # push-up keeps its hyphen ("push up through the heels" is a cue), but the spaced
            body = re.escape(key) + r"(?:e?s)?|" + re.escape(key).replace(r"\-", r"\s+") + r"e?s"   # plural is a name
        else:                # a one-word name of its own (deadlift, thruster)
            body = re.escape(key) + r"(?:e?s)?"
        out.append((re.compile(r"(?<![a-z'-])(?:" + body + r")(?![a-z'-])"), *found[key]))
    cat.__dict__["_menu_patterns"] = out
    return out


def mentions(cat: catalog.Catalog, text: str) -> List[Tuple[str, str, str]]:
    """(movement id, the words used, the few words before them) for every time the spoken text names
    a catalog movement, in order."""
    text = " ".join(text.lower().replace("’", "'").split())
    original, hits = text, []
    for rx, mid, _ in _patterns(cat):
        for m in rx.finditer(text):
            hits.append((m.start(), mid, m.group(0)))
        text = rx.sub(lambda m: " " * len(m.group(0)), text)   # a longer name keeps its words
    return [(mid, words, " ".join(re.findall(r"[a-z']+", _clause(original[max(0, at - 60):at]))[-BEFORE:]))
            for at, mid, words in sorted(hits)]


def _clause(text: str) -> str:
    """The end of `text` after its last sentence or clause break, so a "not" in the sentence before can't
    excuse a mention ("Do not rest. Box jumps")."""
    return re.split(r"[.!?;:,]", text)[-1]


BEFORE = 6   # words kept before a mention, within its clause
# a mention right after one of these isn't an instruction: "no neck rolls today", "like a brisk walk"
NOT_DOING = {"no", "not", "never", "skip", "skipping", "without", "instead", "avoid", "nothing", "like",
             "unlike", "rather", "isn't", "aren't", "won't", "don't"}
# small words allowed between the negation and the mention: "not doing the jumping jacks", "instead of
# burpees", "rather than burpees" ("no more than ten push-ups" still counts: "ten" isn't one)
FILLER = {"a", "an", "the", "any", "more", "your", "doing", "do", "of", "than"}


def negated(before: str) -> bool:
    """True when the words before a mention end in a negation, with only FILLER after it: "no burpees",
    "not doing the jumping jacks"; not "no rest between jumping jacks" or "do not stop your high knees"."""
    for word in reversed(before.split()):
        if word not in FILLER:
            return word in NOT_DOING
    return False


def _part_of(cat: catalog.Catalog, words: str, names: List[str], declared: set) -> bool:
    """True when `words` (say "bench presses") are a shortened form of one of `names` ("dumbbell bench press")
    and name no other movement: "push-ups" after a declared wall push-up is the push-up, not a short form."""
    other = catalog.resolve(cat, words)
    if other is not None and other.id not in declared:
        return False
    key = _norm(words).replace("-", " ")
    forms = {key, key[:-1] if key.endswith("s") else key, key[:-2] if key.endswith("es") else key}
    return any(f" {form} " in f" {_norm(n).replace('-', ' ')} " for form in forms for n in names)


def spoken_text(segments) -> str:
    return " ".join(line for seg in segments for _, line in seg["lines"])


def check(cat: catalog.Catalog, menu: Optional[dict], text: str, segments) -> Tuple[List[str], List[str]]:
    """(issues, warnings) for a draft's text and parsed segments against today's menu."""
    if menu is None:
        return (["no menu for this draft: run ./sweatcast brief ... --save <the draft's path> first, "
                 "so the build can check every movement against today's limits"], [])
    issues, warnings = [], []
    on_menu = {e["id"]: e for e in menu.get("movements", [])}
    words = draft.declared(text)
    if not words:
        issues.append("no movements: line before the first @@ marker; declare every movement the "
                      "script uses, from the brief's menu")
    declared = set()
    for word in words:
        m = catalog.resolve(cat, word.strip())
        if m is None:
            issues.append(f"declared \"{word}\" isn't a movement in the catalog; use its name from the menu")
        elif m.id not in on_menu:
            issues.append(f"declared \"{word}\" ({m.id}) isn't on today's menu; pick a movement the brief lists")
        else:
            declared.add(m.id)
    names = [n for i in declared for n in [cat.movements[i].name] + cat.movements[i].aliases]
    flagged = set()
    for mid, said, before in mentions(cat, spoken_text(segments)):
        if mid in declared or mid in flagged or _part_of(cat, said, names, declared):
            continue   # declared, already said, or a shortened name of a declared movement
        if negated(before):
            continue   # "no neck rolls today"
        flagged.add(mid)
        if mid not in on_menu:
            issues.append(f"the script names \"{said}\" ({mid}), which isn't on today's menu; take it out or "
                          f"reword it (a \"no {said} today\" is fine)")
        else:
            warnings.append(f"the script names \"{said}\" ({mid}) but the movements: line doesn't; add it")
    want = menu.get("seconds")
    total = sum(seg["seconds"] for seg in segments)
    if want and total != want:
        issues.append(f"the segments add up to {total} s, but the request is {want} s "
                      f"({want // 60} minutes): {'take' if total > want else 'add'} {abs(total - want)} s")
    return issues, warnings
