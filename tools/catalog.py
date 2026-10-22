"""The movement catalog: one TOML file of equipment, tags, groups, kit presets and movements.

`load` reads knowledge/movements.toml (plus any private movements) and `problems` checks it,
one plain sentence per fault. `resolve` turns a name from the log or a script into a movement.
Library only; the command line lives elsewhere.
"""
import re
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import paths

POSITIONS = ("standing", "seated", "lying", "side-lying", "kneeling", "all-fours")
MEASURES = ("reps", "time")
SIDE_WORDS = ("left ", "right ", "both sides ")
SPOKEN_OK = re.compile(r"[A-Za-z .,'?!-]*")


@dataclass
class Movement:
    id: str
    name: str
    aliases: List[str]
    kind: str
    needs: List[str]
    position: str
    sided: bool
    measure: str
    groups: List[str]
    tags: List[str]
    setup: str
    cues: List[str]
    easier: List[str]
    harder: List[str]
    private: bool = False


@dataclass
class Catalog:
    groups: List[str]
    kinds: List[str]
    equipment: Dict[str, dict]
    tags: Dict[str, str]
    presets: Dict[str, List[str]]
    movements: Dict[str, Movement]
    entries: List[Movement] = field(default_factory=list)   # every entry in order, repeats included


def _movement(raw: dict, private: bool) -> Movement:
    return Movement(
        id=raw["id"], name=raw.get("name", raw["id"]), aliases=list(raw.get("aliases", [])),
        kind=raw.get("kind", ""), needs=list(raw.get("needs", [])), position=raw.get("position", ""),
        sided=bool(raw.get("sided", False)), measure=raw.get("measure", ""),
        groups=list(raw.get("groups", [])), tags=list(raw.get("tags", [])),
        setup=raw.get("setup", ""), cues=list(raw.get("cues", [])),
        easier=list(raw.get("easier", [])), harder=list(raw.get("harder", [])), private=private)


def load(path: Optional[str] = None, extra: Optional[List[dict]] = None) -> Catalog:
    """Read the catalog at `path` (default: the shipped one); `extra` are private movement tables."""
    with open(path or paths.MOVEMENTS, "rb") as f:
        data = tomllib.load(f)
    entries = [_movement(m, False) for m in data.get("movement", [])]
    entries += [_movement(m, True) for m in (extra or [])]
    movements: Dict[str, Movement] = {}
    for m in entries:
        movements.setdefault(m.id, m)
    return Catalog(
        groups=list(data.get("groups", [])), kinds=list(data.get("kinds", [])),
        equipment=dict(data.get("equipment", {})), tags=dict(data.get("tags", {})),
        presets={k: list(v.get("equipment", [])) for k, v in data.get("presets", {}).items()},
        movements=movements, entries=entries)


def _spoken_fault(text: str) -> Optional[str]:
    """What is wrong with a piece of spoken text, or None."""
    if any(c.isdigit() for c in text):
        return "a digit"
    if not SPOKEN_OK.fullmatch(text):
        return "a symbol or bracket"
    return None


def problems(cat: Catalog) -> List[str]:
    out: List[str] = []
    seen: Dict[str, int] = {}   # lowercase id, name or alias -> index of the entry that holds it
    ids = set(cat.movements)
    entries = cat.entries or list(cat.movements.values())
    for n, m in enumerate(entries):
        for label, word in [("id", m.id), ("name", m.name)] + [("alias", a) for a in m.aliases]:
            key = word.lower()
            if seen.setdefault(key, n) != n:
                out.append(f"The {label} \"{word}\" on movement {m.id} is already used by movement {entries[seen[key]].id}.")
        if m.kind not in cat.kinds:
            out.append(f"Movement {m.id} has the unknown kind \"{m.kind}\".")
        if m.position not in POSITIONS:
            out.append(f"Movement {m.id} has the unknown position \"{m.position}\".")
        if m.measure not in MEASURES:
            out.append(f"Movement {m.id} has the unknown measure \"{m.measure}\".")
        for g in m.groups:
            if g not in cat.groups:
                out.append(f"Movement {m.id} has the unknown group \"{g}\".")
        for t in m.tags:
            if t not in cat.tags:
                out.append(f"Movement {m.id} has the unknown tag \"{t}\".")
        for need in m.needs:
            for alt in need.split("|"):
                if alt not in cat.equipment:
                    out.append(f"Movement {m.id} needs the unknown equipment \"{alt}\".")
        for label, ref in [("easier", m.easier), ("harder", m.harder)]:
            for other in ref:
                if other not in ids:
                    out.append(f"Movement {m.id} lists \"{other}\" as {label}, which is not a movement in the catalog.")
        for label, text in [("setup", m.setup)] + [("cue", c) for c in m.cues]:
            fault = _spoken_fault(text)
            if fault == "a digit":
                out.append(f"The {label} of movement {m.id} has a digit in it: \"{text}\".")
            elif fault:
                out.append(f"The {label} of movement {m.id} has a symbol or bracket in it: \"{text}\".")
    for name, equipment in cat.presets.items():
        for item in equipment:
            if item not in cat.equipment:
                out.append(f"The preset {name} lists the unknown equipment \"{item}\".")
    return out


def resolve(cat: Catalog, name: str) -> Optional[Movement]:
    """The movement a spoken or logged name means, or None."""
    said = " ".join(name.lower().split())
    for side in SIDE_WORDS:
        if said.startswith(side):
            said = said[len(side):]
            break
    candidates = [said]
    if said.endswith("s") and not said.endswith("ss"):
        candidates.append(said[:-1])   # "goblet squats" means "goblet squat"
    for word in candidates:
        for m in cat.movements.values():
            if word == m.name.lower() or word == m.id or word in (a.lower() for a in m.aliases):
                return m
    return None
