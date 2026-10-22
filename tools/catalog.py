"""The movement catalog (format 2): one TOML file of equipment, kit presets, the fixed lists of
movement patterns, muscles, joint areas and flags, and every movement with its loads and timing.

`load` reads knowledge/movements.toml (plus any private movements) and `problems` checks it, one
plain sentence per fault. `resolve` turns a name from the log or a script into a movement. An entry
is a draft until it carries every field; drafts are checked lightly and never planned from.
`select` picks the movements a kit, level and the listener's limits allow.
Library only; the command line lives elsewhere.
"""
import re
import tomllib
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Set

import paths

POSITIONS = ("standing", "seated", "lying", "side-lying", "kneeling", "all-fours")
MEASURES = ("reps", "time")
LEVELS = ("novice", "experienced", "advanced")
INTENSITIES = ("strength", "conditioning", "mobility", "skill", "breathing")
LOAD_MAX = 3
SIDE_WORDS = ("left ", "right ", "both sides ")
SPOKEN_OK = re.compile(r"[A-Za-z .,'?!-]*")


@dataclass
class Movement:
    id: str
    name: str
    aliases: List[str]
    needs: List[str]
    position: str
    sided: bool
    measure: str
    patterns: List[str]
    muscles: List[str]
    loads: Dict[str, int]
    support: Dict[str, int]
    flags: List[str]
    intensity: str
    level: str
    seconds_per_rep: int
    hold_seconds: int
    transition_seconds: int
    rehab: bool
    draft: bool
    setup: str
    cues: List[str]
    easier: List[str]
    harder: List[str]
    private: bool = False
    has_loads: bool = True   # False when the entry has no `loads` key at all (an empty table is fine)


@dataclass
class Catalog:
    patterns: List[str]
    muscles: List[str]
    areas: List[str]
    flags: List[str]
    equipment: Dict[str, dict]
    presets: Dict[str, List[str]]
    movements: Dict[str, Movement]
    entries: List[Movement] = field(default_factory=list)   # every entry in order, repeats included


def _movement(raw: dict, private: bool) -> Movement:
    return Movement(
        id=raw["id"], name=raw.get("name", raw["id"]), aliases=list(raw.get("aliases", [])),
        needs=list(raw.get("needs", [])), position=raw.get("position", ""),
        sided=bool(raw.get("sided", False)), measure=raw.get("measure", ""),
        patterns=list(raw.get("patterns", [])), muscles=list(raw.get("muscles", [])),
        loads=dict(raw.get("loads", {})), support=dict(raw.get("support", {})),
        flags=list(raw.get("flags", [])), intensity=raw.get("intensity", ""), level=raw.get("level", ""),
        seconds_per_rep=int(raw.get("seconds_per_rep", 0)), hold_seconds=int(raw.get("hold_seconds", 0)),
        transition_seconds=int(raw.get("transition_seconds", 0)), rehab=bool(raw.get("rehab", False)),
        draft=bool(raw.get("draft", False)) or "patterns" not in raw,
        setup=raw.get("setup", ""), cues=list(raw.get("cues", [])),
        easier=list(raw.get("easier", [])), harder=list(raw.get("harder", [])), private=private,
        has_loads="loads" in raw)


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
        patterns=list(data.get("patterns", [])), muscles=list(data.get("muscles", [])),
        areas=list(data.get("areas", [])), flags=list(data.get("flags", [])),
        equipment=dict(data.get("equipment", {})),
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
        if not m.patterns:
            out.append(f"Movement {m.id} has no patterns; every entry, draft or not, needs at least one.")
        for p in m.patterns:
            if p not in cat.patterns:
                out.append(f"Movement {m.id} has the unknown pattern \"{p}\".")
        for mu in m.muscles:
            if mu not in cat.muscles:
                out.append(f"Movement {m.id} has the unknown muscle \"{mu}\".")
        for label, table in (("loads", m.loads), ("support", m.support)):
            for area, value in table.items():
                if area not in cat.areas:
                    out.append(f"Movement {m.id} has the unknown area \"{area}\" in its {label}.")
                if not isinstance(value, int) or not 0 <= value <= LOAD_MAX:
                    out.append(f"Movement {m.id} has the {label} value {value} for {area}, outside 0 to {LOAD_MAX}.")
        if m.support and not m.sided:
            out.append(f"Movement {m.id} has support but is not sided; support is the load on the resting side.")
        for f in m.flags:
            if f not in cat.flags:
                out.append(f"Movement {m.id} has the unknown flag \"{f}\".")
        if m.intensity and m.intensity not in INTENSITIES:
            out.append(f"Movement {m.id} has the unknown intensity \"{m.intensity}\".")
        if m.level and m.level not in LEVELS:
            out.append(f"Movement {m.id} has the unknown level \"{m.level}\".")
        if m.position not in POSITIONS:
            out.append(f"Movement {m.id} has the unknown position \"{m.position}\".")
        if m.measure not in MEASURES:
            out.append(f"Movement {m.id} has the unknown measure \"{m.measure}\".")
        if not m.draft:
            missing = []
            if not m.has_loads:
                missing.append("loads")
            if not m.muscles:
                missing.append("muscles")
            if not m.intensity:
                missing.append("intensity")
            if not m.level:
                missing.append("level")
            if m.transition_seconds <= 0:
                missing.append("transition_seconds")
            if m.measure == "reps" and m.seconds_per_rep <= 0:
                missing.append("seconds_per_rep")
            if m.measure == "time" and m.hold_seconds <= 0:
                missing.append("hold_seconds")
            if missing:
                out.append(f"Movement {m.id} is not a draft but is missing {', '.join(missing)}.")
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


def kit_equipment(cat: Catalog, kit: dict) -> Set[str]:
    """The equipment keys a kit stands for: its preset's list, its own `equipment`, or both."""
    out: Set[str] = set()
    if "preset" in kit:
        if kit["preset"] not in cat.presets:
            raise ValueError(f"unknown preset \"{kit['preset']}\" (choose from: {', '.join(sorted(cat.presets))})")
        out |= set(cat.presets[kit["preset"]])
    out |= set(kit.get("equipment", []))
    return out


class Limit(NamedTuple):
    """One standing limit from the listener's health file."""
    area: str
    side: str          # "left", "right" or "both"
    level: str         # "off-limits" or "delicate"
    flags: List[str]   # flags this limit rules out
    rehab: List[str]   # movement ids the limit's rehab plan names; they skip this limit's checks
    note: str


class Selection(NamedTuple):
    allowed: List[Movement]
    healthy_side_only: List[Movement]   # sided movements whose working side is the limited one
    left_out: Dict[str, List[str]]      # movement id -> reasons it is out


def threshold(limit: Limit) -> int:
    """The smallest load on the limit's area that rules a movement out."""
    return 1 if limit.level == "off-limits" else 2


def select(cat: Catalog, equipment: Set[str], level: str, limits: List[Limit],
           avoid: Set[str] = frozenset(), dislikes: Set[str] = frozenset()) -> Selection:
    """Sort every movement into allowed, healthy-side-only or left out, with the reasons.

    "draft" and "equipment" end the checks; the rest accumulate. A movement named in a limit's
    `rehab` list skips that limit's checks. `avoid` holds movement ids or flags."""
    allowed: List[Movement] = []
    healthy: List[Movement] = []
    left_out: Dict[str, List[str]] = {}
    for lim in limits:
        if lim.level not in ("off-limits", "delicate"):
            raise ValueError(f"unknown limit level \"{lim.level}\" (choose from: off-limits, delicate)")
        if lim.side not in ("left", "right", "both"):
            raise ValueError(f"unknown limit side \"{lim.side}\" (choose from: left, right, both)")
    named = {i for lim in limits for i in lim.rehab}
    for m in cat.movements.values():
        if m.draft:
            left_out[m.id] = ["draft"]
            continue
        if not all(any(alt in equipment for alt in need.split("|")) for need in m.needs):
            left_out[m.id] = ["equipment"]
            continue
        reasons: List[str] = []
        one_side: List[tuple] = []   # (limited side, reason) where only the working side is loaded
        if LEVELS.index(m.level) > LEVELS.index(level):
            reasons.append("level")
        if m.id in dislikes:
            reasons.append("disliked")
        if m.id in avoid or any(f in avoid for f in m.flags):
            reasons.append("avoided")
        if m.rehab and m.id not in named:
            reasons.append("rehab")
        for lim in limits:
            if m.id in lim.rehab:
                continue
            need = threshold(lim)
            bad = [f for f in lim.flags if f in m.flags]
            if lim.level == "delicate":
                bad += [f for f in ("impact", "fast") if f in m.flags and f not in bad]
            reasons += bad   # a flag is its own reason
            why = f"{lim.area} {'off limits' if lim.level == 'off-limits' else 'delicate'}"
            if lim.side == "both" or not m.sided:
                hit = m.loads.get(lim.area, 0) >= need
            elif m.support.get(lim.area, 0) >= need:
                hit = True
            else:
                hit = False
                if m.loads.get(lim.area, 0) >= need:
                    one_side.append((lim.side, why))
            if hit:
                reasons.append(why)
        if {side for side, _ in one_side} >= {"left", "right"}:
            reasons += [why for _, why in one_side]   # no healthy side is left to work
        if reasons:
            left_out[m.id] = list(dict.fromkeys(reasons))
        elif one_side:
            healthy.append(m)
        else:
            allowed.append(m)
    return Selection(allowed, healthy, left_out)
