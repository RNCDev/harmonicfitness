"""Session methods and dose rules (format 2): knowledge/sessions.toml.

A method is the shape of a session's main work: its goals, length, levels, how warm-up, cool-down
and an optional finisher share the time, the kind of work and the blocks of patterns that fill it.
The dose tables give each intensity's ranges by level. `load` reads the file, `problems` checks it
against the movement catalog, one plain sentence per fault, `choose_method` picks today's method and
`dose` gives an intensity's ranges for a level. Library only; the command line lives elsewhere.
"""
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

import catalog
import paths

FORMAT = 2
WORK = ("sets", "pairs", "rounds", "intervals", "holds")
OPTIONAL_DOSE_KEYS = ("bodyweight_reps",)   # checked when present
DOSE_KEYS = {
    "strength": ("sets", "reps", "rest_seconds", "hard_sets_per_session", "bodyweight_reps"),
    "conditioning": ("work_seconds", "rest_seconds", "rounds", "efforts_per_session"),
    "mobility": ("hold_seconds", "rounds"),
    "skill": ("drill_seconds", "rounds"),
}


@dataclass
class Method:
    name: str
    about: str
    goals: List[str]
    minutes: List[int]
    levels: List[str]
    warmup: dict
    cooldown: dict
    work: str
    blocks: List[dict]
    min_slots: int
    finisher: Optional[dict] = None
    fixed: Optional[dict] = None
    needs: List[str] = field(default_factory=list)
    rest_seconds: Optional[List[int]] = None   # rounds: the rest between rounds, in place of the dose's


@dataclass
class Sessions:
    format: int
    goals: List[str]
    methods: Dict[str, Method]
    dose: Dict[str, Dict[str, dict]]


def _method(name: str, raw: dict) -> Method:
    return Method(
        name=name, about=raw.get("about", ""), goals=list(raw.get("goals", [])),
        minutes=list(raw.get("minutes", [])), levels=list(raw.get("levels", [])),
        warmup=dict(raw.get("warmup", {})), cooldown=dict(raw.get("cooldown", {})),
        work=raw.get("work", ""), blocks=[dict(b) for b in raw.get("blocks", [])],
        min_slots=int(raw.get("min_slots", 0)),
        finisher=dict(raw["finisher"]) if "finisher" in raw else None,
        fixed=dict(raw["fixed"]) if "fixed" in raw else None,
        needs=list(raw.get("needs", [])),
        rest_seconds=list(raw["rest_seconds"]) if "rest_seconds" in raw else None)


def load(path: Optional[str] = None) -> Sessions:
    """Read the session rules at `path` (default: the shipped file)."""
    with open(path or paths.SESSIONS, "rb") as f:
        data = tomllib.load(f)
    return Sessions(
        format=data.get("format", 0), goals=list(data.get("goals", [])),
        methods={name: _method(name, raw) for name, raw in data.get("methods", {}).items()},
        dose={k: {lv: dict(t) for lv, t in v.items()} for k, v in data.get("dose", {}).items()})


def _range_fault(value) -> Optional[str]:
    """What is wrong with a [least, most] pair, or None."""
    if not (isinstance(value, list) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value)):
        return "is not a pair of numbers"
    if value[0] > value[1]:
        return "is inverted"
    return None


def problems(s: Sessions, cat: catalog.Catalog) -> List[str]:
    out: List[str] = []
    if s.format != FORMAT:
        out.append(f"The session file has format {s.format}; this version reads format {FORMAT}.")
    for name, m in s.methods.items():
        fault = catalog._spoken_fault(m.about)
        if not m.about:
            out.append(f"Method {name} has no about.")
        elif fault:
            out.append(f"The about of method {name} has {fault} in it: \"{m.about}\".")
        for g in m.goals:
            if g not in s.goals:
                out.append(f"Method {name} has the unknown goal \"{g}\".")
        for lv in m.levels:
            if lv not in catalog.LEVELS:
                out.append(f"Method {name} has the unknown level \"{lv}\".")
        if not m.goals or not m.levels:
            out.append(f"Method {name} needs at least one goal and one level.")
        fault = _range_fault(m.minutes)
        if fault:
            out.append(f"The minutes of method {name} {fault}: {m.minutes}.")
        for label, part in (("warmup", m.warmup), ("cooldown", m.cooldown), ("finisher", m.finisher)):
            if part is None:
                continue
            fault = _range_fault(part.get("seconds"))
            if fault:
                out.append(f"The {label} seconds of method {name} {fault}: {part.get('seconds')}.")
            if not 0 <= part.get("share", -1) <= 1:
                out.append(f"The {label} share of method {name} is not between zero and one.")
        if m.work not in WORK:
            out.append(f"Method {name} has the unknown work \"{m.work}\" (choose from: {', '.join(WORK)}).")
        if m.min_slots < 1:
            out.append(f"Method {name} has min_slots {m.min_slots}; it needs at least one.")
        if not m.blocks:
            out.append(f"Method {name} has no blocks.")
        total = 0.0
        for b in m.blocks:
            if b.get("intensity") not in catalog.INTENSITIES:
                out.append(f"Method {name} has a block with the unknown intensity \"{b.get('intensity')}\".")
            elif b.get("intensity") not in s.dose:
                out.append(f"Method {name} has a {b.get('intensity')} block, but there is no {b.get('intensity')} dose table.")
            for p in b.get("patterns", []) + b.get("fallback", []):
                if p not in cat.patterns:
                    out.append(f"Method {name} has the unknown pattern \"{p}\".")
            if not b.get("patterns"):
                out.append(f"Method {name} has a block with no patterns.")
            share = b.get("share", -1)
            if not 0 < share <= 1:
                out.append(f"Method {name} has a block share of {share}, not between zero and one.")
            total += share
        if m.blocks and abs(total - 1) > 0.01:
            out.append(f"The block shares of method {name} sum to {total:g}, not one.")
        for need in m.needs:
            for alt in need.split("|"):
                if alt not in cat.equipment:
                    out.append(f"Method {name} needs the unknown equipment \"{alt}\".")
        if m.rest_seconds is not None:
            fault = _range_fault(m.rest_seconds)
            if fault:
                out.append(f"The rest_seconds of method {name} {fault}: {m.rest_seconds}.")
            elif m.work != "rounds":
                out.append(f"Method {name} has rest_seconds, which only a rounds method uses.")
    for intensity, keys in DOSE_KEYS.items():
        table = s.dose.get(intensity, {})
        for lv in catalog.LEVELS:
            if lv not in table:
                out.append(f"The {intensity} dose has no {lv} level.")
                continue
            for key in keys:
                if key in OPTIONAL_DOSE_KEYS and key not in table[lv]:
                    continue
                fault = _range_fault(table[lv].get(key))
                if fault:
                    out.append(f"The {intensity} dose for {lv} {key} {fault}: {table[lv].get(key)}.")
    return out


def fitting(s: Sessions, goal: str, minutes: float, level: str, equipment: Set[str]) -> List[Method]:
    """Every method, in file order, that suits the goal, length, level and kit."""
    return [m for m in s.methods.values()
            if goal in m.goals and m.minutes[0] <= minutes <= m.minutes[1] and level in m.levels
            and all(any(alt in equipment for alt in need.split("|")) for need in m.needs)]


def ranked(s: Sessions, goal: str, minutes: float, level: str, equipment: Set[str],
           last_format: Optional[str] = None) -> List[Method]:
    """The fitting methods, best first: by where the goal sits in each method's goals (first goal
    first), then file order; within that, the last session's method moves to the back."""
    fits = sorted(fitting(s, goal, minutes, level, equipment), key=lambda m: m.goals.index(goal))
    return [m for m in fits if m.name != last_format] + [m for m in fits if m.name == last_format]


def choose_method(s: Sessions, goal: str, minutes: float, level: str, last_format: Optional[str],
                  equipment: Set[str]) -> Optional[Method]:
    """The best-ranked fitting method (see `ranked`), or None."""
    fits = ranked(s, goal, minutes, level, equipment, last_format)
    return fits[0] if fits else None


def dose(s: Sessions, intensity: str, level: str) -> dict:
    """An intensity's ranges for a level, each [least, most]."""
    return s.dose[intensity][level]
