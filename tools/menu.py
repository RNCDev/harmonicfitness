"""Today's menu, and the build's check that a draft scripts nothing else.

`./sweatcast brief --save <stem>` writes `<stem>.menu.json` beside the draft: the request and every
movement `catalog.select` allowed today, healthy-side-only ones with the side to work. The draft
declares what it scripts on a `movements:` line (draft.py), and `check` finds:
- issues (the build stops, whatever --force says): no menu; a declared movement that isn't on it or
  isn't a movement at all; nothing declared; the text naming a catalog movement that isn't on the
  menu; segments that don't add up to the request's seconds;
- warnings: the text naming a menu movement the declaration leaves out (add it, so the log has it).

The text is scanned for names and aliases of two or more words (hyphen or space between them) and
for one-word hyphenated names (push-up), longest first, so "single-leg glute bridge" isn't also read
as "glute bridge". Plain one-word names (squat, swing, curl, plank) are left out of the scan: they
are everyday coaching words ("swing your arms"), and the declaration is what the build checks. A
shortened name of a declared movement ("the bench press" for the dumbbell bench press) counts as
that movement, and a mention just after "no", "not", "skip", "instead of" or "like" isn't an
instruction ("no neck rolls today", "it should feel like a brisk walk").
Library only; the brief and the lint call it.
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple

import catalog
import draft

FORMAT = 1
EFFORT_WORDS = {"easy", "steady", "hard", "brisk", "light", "slow", "quick", "fast", "gentle"}


def record(request: dict, sel: catalog.Selection, sides: Dict[str, str], seconds: int, date: str) -> dict:
    """The menu file's contents."""
    def entry(m, side=None):
        out = {"id": m.id, "name": m.name, "aliases": list(m.aliases)}
        if side:
            out["side"] = side
        return out
    return {"format": FORMAT, "date": date, "request": request, "seconds": seconds,
            "movements": [entry(m) for m in sel.allowed] + [entry(m, sides.get(m.id, "healthy"))
                                                            for m in sel.healthy_side_only]}


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
    return " ".join(re.sub(r"[^a-z'-]+", " ", text.lower().replace("’", "'")).split())


def resolve(cat: catalog.Catalog, word: str) -> Optional[catalog.Movement]:
    """The movement a declared word means: an id, a name or an alias, forgiving a plural and a
    leading side word, with hyphens and spaces alike."""
    m = cat.movements.get(word.strip()) or catalog.resolve(cat, word)
    if m:
        return m
    said = _norm(word).replace("-", " ")
    for side in ("left ", "right "):
        said = said[len(side):] if said.startswith(side) else said
    for m in cat.movements.values():
        for name in [m.name, m.id] + m.aliases:
            plain = _norm(name).replace("-", " ")
            if said in (plain, plain + "s", plain + "es"):
                return m
    return None


def _patterns(cat: catalog.Catalog) -> List[Tuple[re.Pattern, str, str]]:
    """(regex, movement id, the name it matches) for every name and alias the text scan checks,
    longest first."""
    found = {}
    for m in cat.movements.values():
        for name in [m.name] + m.aliases:
            key = _norm(name)
            if " " not in key and "-" not in key:
                continue   # a plain one-word name: an everyday coaching word
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
            body = r"[\s-]+".join(re.escape(w).replace(r"\-", r"[\s-]?") for w in words)
        else:                # push-up must keep its hyphen: "push up through the heels" is a cue
            body = re.escape(key)
        out.append((re.compile(r"(?<![a-z'-])" + body + r"(?:e?s)?(?![a-z'-])"), *found[key]))
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
    return [(mid, words, " ".join(re.findall(r"[a-z']+", original[max(0, at - 40):at])[-BEFORE:]))
            for at, mid, words in sorted(hits)]


BEFORE = 3   # words looked at before a mention
# a mention just after one of these isn't an instruction: "no neck rolls today", "like a brisk walk"
NOT_DOING = {"no", "not", "never", "skip", "skipping", "without", "instead", "avoid", "nothing", "like",
             "unlike", "rather", "isn't", "aren't", "won't", "don't"}   # not "than": "no more than ten push-ups"


def _part_of(words: str, names: List[str]) -> bool:
    """True when `words` (say "bench presses") are a shortened form of one of `names` ("dumbbell
    bench press")."""
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
        m = resolve(cat, word)
        if m is None:
            issues.append(f"declared \"{word}\" isn't a movement in the catalog; use its name from the menu")
        elif m.id not in on_menu:
            issues.append(f"declared \"{word}\" ({m.id}) isn't on today's menu; pick a movement the brief lists")
        else:
            declared.add(m.id)
    names = [n for i in declared for n in [cat.movements[i].name] + cat.movements[i].aliases]
    flagged = set()
    for mid, said, before in mentions(cat, spoken_text(segments)):
        if mid in declared or mid in flagged or _part_of(said, names):
            continue   # declared, already said, or a shortened name of a declared movement
        if set(before.split()) & NOT_DOING:
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
