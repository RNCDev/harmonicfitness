"""The movement catalog: one TOML file of equipment, tags, groups, kit presets and movements.

`load` reads knowledge/movements.toml (plus any private movements) and `problems` checks it,
one plain sentence per fault. `resolve` turns a name from the log or a script into a movement.
`load_rules` reads knowledge/injury-rules.toml and `rule_problems` checks it against the catalog
and the playbook. Library only; the command line lives elsewhere.
"""
import re
import tomllib
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Set

import paths

POSITIONS = ("standing", "seated", "lying", "side-lying", "kneeling", "all-fours")
MEASURES = ("reps", "time")
SIDE_WORDS = ("left ", "right ", "both sides ")
SPOKEN_OK = re.compile(r"[A-Za-z .,'?!-]*")
PHASES = ("protect", "restore", "rebuild", "return")
RULE_LISTS = ("ban", "ban_injured_side", "ban_ids", "include", "advance_when", "sources")


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


class Selection(NamedTuple):
    allowed: List[Movement]
    healthy_side_only: List[Movement]
    left_out: Dict[str, List[str]]   # movement id -> every reason it was ruled out


def kit_equipment(cat: Catalog, kit: dict) -> Set[str]:
    """The equipment keys a kit stands for: its preset's list, its own `equipment`, or both."""
    out: Set[str] = set()
    if "preset" in kit:
        if kit["preset"] not in cat.presets:
            raise ValueError(f"unknown preset \"{kit['preset']}\" (choose from: {', '.join(sorted(cat.presets))})")
        out |= set(cat.presets[kit["preset"]])
    out |= set(kit.get("equipment", []))
    return out


def select(cat: Catalog, equipment: Set[str], avoid: Set[str], avoid_injured_side: Set[str] = frozenset(),
           ban_ids: Set[str] = frozenset()) -> Selection:
    """Split the catalog into what is allowed with this kit and these bans, what is allowed on the
    healthy side only, and what is left out (with every reason)."""
    allowed: List[Movement] = []
    healthy: List[Movement] = []
    left_out: Dict[str, List[str]] = {}
    for m in cat.movements.values():
        reasons: List[str] = []
        if any(not any(alt in equipment for alt in need.split("|")) for need in m.needs):
            reasons.append("equipment")
        reasons += [t for t in m.tags if t in avoid]
        if m.id in ban_ids:
            reasons.append("banned")
        side = [t for t in m.tags if t in avoid_injured_side and t not in avoid]
        if side and not m.sided:
            reasons += side
        if reasons:
            left_out[m.id] = reasons
        elif side:
            healthy.append(m)
        else:
            allowed.append(m)
    return Selection(allowed, healthy, left_out)


def load_rules(path: Optional[str] = None) -> Dict[str, dict]:
    """The injury rules: area -> {"playbook": heading, phase -> {"ban", "ban_injured_side", "ban_ids",
    "caution", "include", "advance_when", "sources"}}, with any missing list or table left empty."""
    with open(path or paths.INJURY_RULES, "rb") as f:
        data = tomllib.load(f)
    out: Dict[str, dict] = {}
    for area, raw in data.get("areas", {}).items():
        rule: dict = {"playbook": raw.get("playbook", "")}
        for phase in PHASES:
            if phase in raw:
                given = raw[phase]
                rule[phase] = {key: list(given.get(key, [])) for key in RULE_LISTS}
                rule[phase]["caution"] = dict(given.get("caution", {}))
        out[area] = rule
    return out


def rule_problems(rules: Dict[str, dict], cat: Catalog, playbook_text: str) -> List[str]:
    """Faults in the injury rules, one plain sentence each: unknown tags or movements, a missing
    phase, a playbook heading that isn't there, a caution that can't be spoken, and a rehab movement
    both banned and included."""
    out: List[str] = []
    headings = {line[3:].strip() for line in playbook_text.splitlines() if line.startswith("## ")}
    for area, rule in rules.items():
        heading = rule.get("playbook", "")
        if heading not in headings:
            out.append(f"The {area} rules point to the playbook heading \"{heading}\", which is not a ## heading in the playbook.")
        for phase in PHASES:
            r = rule.get(phase)
            if r is None:
                out.append(f"The {area} rules have no {phase} phase.")
                continue
            for key in ("ban", "ban_injured_side"):
                for tag in r.get(key, []):
                    if tag not in cat.tags:
                        out.append(f"The {area} {phase} {key} list names the unknown tag \"{tag}\".")
            for key, ids in (("ban_ids", r.get("ban_ids", [])), ("caution", list(r.get("caution", {}))),
                             ("include", r.get("include", []))):
                for mid in ids:
                    if mid not in cat.movements:
                        out.append(f"The {area} {phase} {key} list names \"{mid}\", which is not a movement in the catalog.")
            for mid, condition in r.get("caution", {}).items():
                if _spoken_fault(condition):
                    out.append(f"The {area} {phase} caution for \"{mid}\" has {_spoken_fault(condition)} in it, and it is spoken.")
            for mid in r.get("include", []):
                if mid in r.get("ban_ids", []):
                    out.append(f"The {area} {phase} phase lists \"{mid}\" under both include and ban_ids.")
    return out
