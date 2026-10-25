#!/usr/bin/env python3
"""The safety screen behind `./sweatcast brief`: what today's request, profile and health file allow.

`screen` checks the request (goal, minutes, kit, level, target, limits, avoid), applies health.md's
[[limits]] rows and the clinician's Avoid: lines, and selects the movements the kit, level, limits and
dislikes allow. A [[limits]] row it can't read stops it (Unfit), since a dropped row protects nothing.
The helpers here read the command line's values (`parse_limit`, `words`) and print what the screen
found (`cue_lines`, `loads_line`, `would_open`, `healthy_side`).
"""
import os
import sys
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import context  # noqa: E402
import paths  # noqa: E402

LIMIT_SIDES, LIMIT_LEVELS = catalog.LIMIT_SIDES, catalog.LIMIT_LEVELS
OTHER_SIDE = {"left": "right", "right": "left"}


class Unfit(Exception):
    """The request can't be screened safely: a [[limits]] row can't be read (exit ISSUES)."""
    exit_code = 1   # cli.ISSUES; a literal so this module keeps importing nothing but the catalog


class Screen(NamedTuple):
    """What today's request, profile and health file allow."""
    equipment: Set[str]
    level: str
    limits: List[catalog.Limit]   # health.md's rows, then the request's
    sel: catalog.Selection
    likes: Set[str]
    dislikes: Set[str]
    avoid: Set[str]               # the request's ids and flags, plus the clinician's Avoid: lines
    warnings: List[str]


def _equipment(request: dict, cat: catalog.Catalog, profile) -> Set[str]:
    if request.get("kit"):
        kits = context.kits(profile)
        if request["kit"] not in kits:
            raise ValueError(f"unknown kit \"{request['kit']}\" (kits in the profile: {', '.join(kits) or 'none'})")
        return set(kits[request["kit"]])
    if request.get("preset"):
        return catalog.kit_equipment(cat, {"preset": request["preset"]})
    if "equipment" in request:
        unknown = [e for e in request["equipment"] if e not in cat.equipment]
        if unknown:
            raise ValueError(f"unknown equipment \"{unknown[0]}\" (choose from: {', '.join(cat.equipment)})")
        return set(request["equipment"])
    raise ValueError("name a kit, a preset or the equipment")


def ids(cat: catalog.Catalog, names: List[str]) -> Set[str]:
    """Catalog ids for names or ids from the profile or log; unknown names are skipped."""
    found = (catalog.resolve(cat, n) for n in names)
    return {m.id for m in found if m}


def screen(request: dict, cat: catalog.Catalog, goals, profile, health) -> Screen:
    """Check `request` (goal, minutes, and one of kit, preset or equipment; optionally level, target,
    limits, avoid) and select the movements its kit, level and limits allow, with health.md's
    [[limits]] rows and clinician Avoid: lines applied. ValueError names an unknown value; Unfit says
    a [[limits]] row can't be read, since a dropped row protects nothing."""
    goal, minutes = request.get("goal"), request.get("minutes")
    if goal not in goals:
        raise ValueError(f"unknown goal \"{goal}\" (choose from: {', '.join(goals)})")
    if not isinstance(minutes, int) or minutes <= 0:
        raise ValueError(f"minutes must be a whole number above zero, not {minutes}")
    equipment = _equipment(request, cat, profile)
    warnings: List[str] = []
    level = request.get("level") or context.experience(profile)
    if not level:
        level = "novice"
        warnings.append("no experience level in the profile; assuming novice")
    if level not in catalog.LEVELS:
        raise ValueError(f"unknown level \"{level}\" (choose from: {', '.join(catalog.LEVELS)})")
    for t in request.get("target") or []:
        if t not in cat.patterns and t not in cat.muscles:
            raise ValueError(f"unknown target \"{t}\" (patterns: {', '.join(cat.patterns)}; "
                             f"muscles: {', '.join(cat.muscles)})")
    for lim in request.get("limits") or []:
        if lim.area not in cat.areas:
            raise ValueError(f"unknown area \"{lim.area}\" (choose from: {', '.join(cat.areas)})")
        if lim.level not in LIMIT_LEVELS or lim.side not in LIMIT_SIDES:
            raise ValueError(f"a limit needs a level ({', '.join(LIMIT_LEVELS)}) and a side ({', '.join(LIMIT_SIDES)})")
    own = context.limits(health, cat.areas, cat.flags)
    rows = health.settings.get("limits") or []
    if len(rows if isinstance(rows, list) else [rows]) > len(own):   # a dropped row protects nothing
        raise Unfit("health.md: a [[limits]] row was ignored (run ./sweatcast check)")
    if context.prose_injuries(health) and not own:
        warnings.append("health.md lists injuries in prose but has no [[limits]] rows, so no limit is "
                        "applied for them; add a row for each")
    limits = own + list(request.get("limits") or [])
    likes, dislikes = ids(cat, context.likes(profile)), ids(cat, context.dislikes(profile))
    avoid = set(request.get("avoid") or ())
    for word in context.clinician_avoids(health):   # the clinician's Avoid: lines apply on every run
        if word in cat.movements or word in cat.flags:
            avoid.add(word)
        else:
            warnings.append(f"health.md: Avoid: '{word}' isn't a movement id or flag, so it rules nothing out")
    try:
        sel = catalog.select(cat, equipment, level, limits, avoid=avoid, dislikes=dislikes)
    except ValueError as e:   # request limits are checked above, so this is a row in health.md
        raise Unfit(f"{paths.show(health.path or paths.HEALTH)}: {e}; fix the [[limits]] row")
    return Screen(equipment, level, limits, sel, likes, dislikes, avoid, warnings)


def clamp(part: dict, total: int) -> int:
    """A method part's seconds (warm-up, finisher, cool-down): its share of `total`, within its range."""
    least, most = part["seconds"]
    return max(least, min(most, round(part["share"] * total)))


def healthy_side(m: catalog.Movement, limits: List[catalog.Limit]) -> str:
    """The side a healthy-side-only movement works: the one opposite the sided limit that loads it."""
    for lim in limits:
        skipped = m.rehab and m.id in lim.rehab   # as in catalog.select
        if lim.side in OTHER_SIDE and not skipped and m.loads.get(lim.area, 0) >= catalog.threshold(lim):
            return OTHER_SIDE[lim.side]
    return "healthy"


def would_open(cat: catalog.Catalog, sel: catalog.Selection, equipment: Set[str], level: str,
               limits: List[catalog.Limit], avoid: Set[str], dislikes: Set[str]) -> List[Tuple[str, int]]:
    """Up to three equipment items not on hand, with how many more movements each would allow today
    (the same level, limits, avoid and dislikes), most first."""
    now = {m.id for m in sel.allowed + sel.healthy_side_only}
    out = []
    for item in cat.equipment:
        if item in equipment:
            continue
        more = catalog.select(cat, equipment | {item}, level, limits, avoid=avoid, dislikes=dislikes)
        n = len({m.id for m in more.allowed + more.healthy_side_only} - now)
        if n:
            out.append((item, n))
    return sorted(out, key=lambda kv: -kv[1])[:3]


def cue_lines(cat: catalog.Catalog, limits) -> List[str]:
    """For each limit (each area, level and side once), a line naming it, then its spoken cues."""
    out = []
    for lim in dict.fromkeys((lim.area, lim.level, lim.side) for lim in limits):
        area, level, side = lim
        lines = catalog.limit_cues(cat, catalog.Limit(area, side, level, [], [], ""))
        if lines:
            where = f", {side} side" if side in OTHER_SIDE else ""
            out.append(f"  {area} {'off limits' if level == 'off-limits' else 'delicate'}{where}:")
            out += [f"    {line}" for line in lines]
    return out


def loads_line(weights: Tuple[str, Dict[str, list]], equipment: Set[str]) -> str:
    """"Loads on hand: dumbbells 10, 15, 20 lb (heaviest 20); kettlebell 30 lb", from the kit's weights."""
    unit, table = weights
    parts = []
    for e, ws in table.items():
        if e not in equipment:
            continue
        shown = ", ".join(f"{w:g}" for w in ws)
        parts.append(f"{e} {shown} {unit}" + (f" (heaviest {ws[-1]:g})" if len(ws) > 1 else ""))
    return ("Loads on hand: " + "; ".join(parts) +
            ". At the heaviest, progress by reps, tempo, pauses, range or one side (programming.md)") if parts else ""


def parse_limit(text: str, cat: catalog.Catalog) -> catalog.Limit:
    """A --limit value, area=level[:side], as a Limit; ValueError naming the choices."""
    area, _, rest = text.partition("=")
    level, _, side = rest.partition(":")
    side = side or "both"
    if area not in cat.areas:
        raise ValueError(f"unknown area \"{area}\" in --limit (choose from: {', '.join(cat.areas)})")
    if level not in LIMIT_LEVELS:
        raise ValueError(f"unknown level \"{level}\" in --limit (choose from: {', '.join(LIMIT_LEVELS)})")
    if side not in LIMIT_SIDES:
        raise ValueError(f"unknown side \"{side}\" in --limit (choose from: {', '.join(LIMIT_SIDES)})")
    return catalog.Limit(area, side, level, [], [], catalog.meaning(area, level, side))


def words(text: Optional[str]) -> List[str]:
    """A comma-separated value as its words, blanks dropped."""
    return [w.strip() for w in (text or "").split(",") if w.strip()]
