#!/usr/bin/env python3
"""A session skeleton for a request: the method, its timing and ranked movements for each slot.

The workout skill writes its script under the skeleton instead of planning from memory. From the
request (goal, minutes, kit) and the listener's profile, health limits and log, this picks today's
method (the best fit for the goal, rotating away from the last session's format, and the next one when
it cannot fill its slots), shares the minutes between warm-up, work, finisher and cool-down, fills
the method's movement-pattern slots with the movements the kit, level and limits allow, ranked, and
doses them so the planned total lands on the request.
With --draft it prints only the `@@ <seconds> | <title>` markers the script is written under.

    ./sweatcast session --goal strength --minutes 30 --kit home
    ./sweatcast session --goal general --minutes 20 --preset hotel-room --draft
    ./sweatcast session --goal targeted --minutes 25 --kit home --target glutes --limit knee=delicate:left

Candidates rank fresh, then liked, then nearest the listener's level, then (with load or a cardio
machine on hand) the ones that use it, then by effort (hard first above novice), then lightest on the
limited areas. Interval work never takes an easy movement; when fewer than two locomotion movements are
hard enough, the method's fallback patterns join in; its blocks go round the machines on hand before a
second block on any one, and an all-out sprint rests at least four times its work. A targeted session
gives each target pattern two slots. The hard sets (or efforts) per session never pass the dose's cap.
A circuit's stations done in one place (the floor, a bench or seat, standing) come together, and the
last set of straight or paired sets holds a few seconds to start besides its reps. Each limit today
prints the catalog's spoken limit cues, its side filled in.

Time the slots do not use goes to a second pass through the patterns (once every dose is at its
ceiling), for intervals past the efforts cap to a steady block, then to rests between slots (up to
thirty seconds each), the finisher, the cool-down and warm-up up to their ceilings, and the rest to
the cool-down with a warning past a tenth of the request. A request too short for every slot drops
slots, never squeezes the total. Printed rests are the rests the slots hold.
"""
import datetime
import os
import sys
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402
import context  # noqa: E402
import coverage  # noqa: E402
import movements  # noqa: E402
import paths  # noqa: E402
import sessions  # noqa: E402

BETWEEN_SLOTS = 30   # most spare seconds added as rest after any one slot
CHANGE_SECONDS = 30  # added after an interval slot when the next one is on other equipment
STEADY_LEAST, STEADY_MOST = 90, 600   # a steady block takes interval time past the efforts cap, within these
EFFORT_RANK = {"novice": {"moderate": 0, "hard": 1, "easy": 2},   # which conditioning effort ranks first
               "experienced": {"hard": 0, "moderate": 1, "easy": 2},
               "advanced": {"hard": 0, "moderate": 1, "easy": 2}}
COVERING = ("sets", "pairs")   # straight sets give way to paired sets when pairing keeps a pattern straight sets drop
CYCLING = ("holds", "intervals")   # work kinds whose patterns repeat to fill the block
CYCLE_CAP = 12       # most slots a cycling block holds
SPARE_WARNING = 0.10   # spare beyond this share of the request, after everything else, is warned about
STEP = {"sets": 1, "rounds": 1, "reps": 1, "bodyweight_reps": 1, "rest_seconds": 15}   # other keys (seconds of work) step by 5
LIMIT_SIDES, LIMIT_LEVELS = catalog.LIMIT_SIDES, catalog.LIMIT_LEVELS
# house default: the last set of straight or paired sets, which has no rest after it to get ready in,
# holds a few seconds to settle and start, and every one-sided set the change from one side to the
# other, so no set's segment is only its counted reps
START_SECONDS, SWITCH_SECONDS = 5, 5
OTHER_SIDE = {"left": "right", "right": "left"}


class Unfit(Exception):
    """The request cannot be planned: no method fits, or too few slots fit (exit ISSUES)."""


class Slot(NamedTuple):
    pattern: str
    intensity: str
    dose: dict                                       # the chosen numbers, such as sets, reps, rest_seconds
    seconds: int                                     # everything the slot takes, its rests included
    candidates: List[Tuple[catalog.Movement, str]]   # ranked (movement, reasons); the first is the default


class Skeleton(NamedTuple):
    method: sessions.Method
    minutes: int
    warmup: int
    blocks: List[Tuple[str, List[Slot]]]   # (intensity, slots)
    finisher: int
    cooldown: int
    dropped: List[str]                     # patterns left out for time
    warnings: List[str]
    would_open: List[Tuple[str, int]]      # (equipment not on hand, movements it would admit)
    health: Tuple[str, ...] = ()           # the clinician lines, to follow literally
    why: str = ""                          # why this method today
    healthy_sides: Optional[Dict[str, str]] = None   # healthy-side-only movement id -> the side to work
    extras: Optional[Dict[str, List[Tuple[catalog.Movement, str]]]] = None   # "warmup", "finisher",
    #   "cooldown" -> ranked (movement, reasons), screened by the same kit, level and limits as the slots
    finisher_dose: Optional[dict] = None   # rounds, work_seconds, rest_seconds for the finisher
    kit_loads: str = ""                    # the kit's weights on hand, from the profile, as one line
    cat: Optional[catalog.Catalog] = None  # for the easier and harder names in the coaching notes
    limits: Tuple[catalog.Limit, ...] = ()  # today's limits, health.md's and the request's, for the limit cues


# ---- timing ------------------------------------------------------------------------------

def reps(m: catalog.Movement, dose: dict) -> int:
    """Reps per set of `m`: the dose's bodyweight reps when `m` needs no load equipment, else its reps."""
    if "bodyweight_reps" in dose and not catalog.loaded(m):
        return dose["bodyweight_reps"]
    return dose["reps"]


def _work_each(m: catalog.Movement, dose: dict) -> int:
    """Seconds of work in one set or hold of `m` at `dose`."""
    if m.measure == "reps" and "reps" in dose:
        return reps(m, dose) * m.seconds_per_rep
    for key in ("hold_seconds", "drill_seconds", "work_seconds"):
        if key in dose:
            return dose[key]
    return m.hold_seconds


def _work_time(m: catalog.Movement, dose: dict, one_side: bool = False) -> int:
    """Seconds of work in one set or hold of `m`, both sides of a sided movement unless only one
    side works today."""
    return _work_each(m, dose) * (2 if m.sided and not one_side else 1)


def _set_time(m: catalog.Movement, dose: dict, one_side: bool = False) -> int:
    """Seconds one set of straight or paired sets takes, its transition aside: the reps (both sides of
    a sided movement unless only one works today) and the change of side. The slot's last set also
    holds START_SECONDS, since no rest comes before it ends."""
    switch = SWITCH_SECONDS if m.sided and not one_side else 0
    return _work_time(m, dose, one_side) + switch


def station(m: catalog.Movement) -> Tuple[str, ...]:
    """What a movement is done on: its needs (empty for the floor)."""
    return tuple(m.needs)


def slot_seconds(m: catalog.Movement, dose: dict, work: str, one_side: bool = False) -> int:
    """Seconds one movement takes at `dose` for the method's kind of work.

    sets: transition, every set, a rest between sets. pairs: a transition before every set (the move
    to the station, each pass through the pair) and half of the pair's rests, since one rest follows
    each pass through the pair. A set of either holds its reps and, on a sided movement, the change
    of side (`_set_time`); the last set, with no rest after it, a few seconds to start as well. rounds: one transition and one set per round
    (the rests between rounds belong to the block, see block_seconds). intervals: rounds of work
    and rest. holds: rounds of holds after one transition. A sided movement's work covers both sides,
    then one rest (one side only when `one_side`); an interval's work is the dose's work seconds,
    whichever side."""
    w, t = _work_time(m, dose, one_side), m.transition_seconds
    rest = dose.get("rest_seconds", 0)
    if work == "sets":
        return t + dose["sets"] * _set_time(m, dose, one_side) + (dose["sets"] - 1) * rest + START_SECONDS
    if work == "pairs":
        return dose["sets"] * (t + _set_time(m, dose, one_side)) + (dose["sets"] - 1) * rest // 2 + START_SECONDS
    if work == "rounds":
        return dose["rounds"] * (t + w)
    if work == "intervals":
        return dose["rounds"] * (dose["work_seconds"] + rest)
    if work == "holds":
        return dose["rounds"] * w + t
    raise ValueError(f"unknown work \"{work}\" (choose from: {', '.join(sessions.WORK)})")


def block_seconds(ms: List[catalog.Movement], dose: dict, work: str,
                  one_side: Set[str] = frozenset()) -> List[int]:
    """Each slot's seconds in a block of movements in order, so the block's rests land in its slots:
    the odd second of a pair's rests goes to its second slot, a lone last slot of `pairs` takes all its
    rests, the rests between rounds are shared evenly (the remainder on the last slot), and an interval
    slot followed by one on other equipment gets the time to change over. Movements in `one_side` work
    one side only."""
    out = [slot_seconds(m, dose, work, m.id in one_side) for m in ms]
    if work == "intervals":
        for i in range(len(ms) - 1):
            if station(ms[i]) != station(ms[i + 1]):
                out[i] += CHANGE_SECONDS
    if work == "pairs":
        rests = (dose["sets"] - 1) * dose.get("rest_seconds", 0)
        for i in range(0, len(ms), 2):
            if i + 1 < len(ms):
                out[i + 1] += rests - 2 * (rests // 2)
            else:
                out[i] += rests - rests // 2
    elif work == "rounds" and ms:
        rests = (dose["rounds"] - 1) * dose.get("rest_seconds", 0)
        share = rests // len(ms)
        out = [s + share for s in out]
        out[-1] += rests - share * len(ms)
    return out


def _clamp(part: dict, total: int) -> int:
    least, most = part["seconds"]
    return max(least, min(most, round(part["share"] * total)))


# ---- dose --------------------------------------------------------------------------------

CAPS = ("hard_sets_per_session", "efforts_per_session")   # dose keys that cap a session, not a slot


def _ranges(sess: sessions.Sessions, method: sessions.Method, intensity: str, level: str) -> Dict[str, list]:
    """{dose key: [least, most]} for one block: the method's fixed shape, or the intensity's dose table
    for the level (breathing has none and uses mobility's; circuit rounds come from strength sets, and
    the rest between them from the method's own rest when it has one)."""
    if method.fixed:
        return {k: [v, v] for k, v in method.fixed.items()}
    table = sessions.dose(sess, intensity if intensity in sess.dose else "mobility", level)
    if intensity != "strength":
        return {k: list(v) for k, v in table.items() if k not in CAPS}
    rest = method.rest_seconds if method.work == "rounds" and method.rest_seconds else table["rest_seconds"]
    out = {("rounds" if method.work == "rounds" else "sets"): list(table["sets"]),
           "reps": list(table["reps"]), "rest_seconds": list(rest)}
    if "bodyweight_reps" in table:
        out["bodyweight_reps"] = list(table["bodyweight_reps"])
    return out


def _cap(sess: sessions.Sessions, method: sessions.Method, intensity: str, level: str) -> Optional[int]:
    """The most hard sets (strength) or efforts (conditioning) the block may hold, or None. A circuit's
    stations are lighter than hard sets, so its rounds are not capped."""
    if method.fixed or intensity not in sess.dose or method.work == "rounds":
        return None
    table = sessions.dose(sess, intensity, level)
    return next((table[k][1] for k in CAPS if k in table), None)


def _raise_order(ranges: Dict[str, list], work: str = "sets") -> List[str]:
    """Count first (sets or rounds), then the work (reps or seconds), then rest; intervals raise the
    rest before the work, so a long session gets recovery before longer efforts."""
    count = [k for k in ("sets", "rounds") if k in ranges]
    rest = [k for k in ("rest_seconds",) if k in ranges]
    middle = [k for k in ranges if k not in count + rest]
    return count + (rest + middle if work == "intervals" else middle + rest)


def _fit(movers: List[catalog.Movement], ranges: Dict[str, list], work: str, budget: int,
         least_slots: int, fixed: bool, what: str, first: int, cap: Optional[int] = None,
         one_side: Set[str] = frozenset()) -> Tuple[int, dict]:
    """(slots, dose) for one block: grow the slot count at the floor dose while the next slot fits, up to
    `first` slots (variety before volume), then raise the dose toward its ceilings while the block still
    fits. When every slot of the first pass and every ceiling are reached, slots past `first` (a second
    pass through the patterns) are added while they fit. Slots times sets (or rounds) never pass `cap`."""
    dose = {k: v[0] for k, v in ranges.items()}
    count_key = next((k for k in ("sets", "rounds") if k in ranges), None)
    within = lambda n, d: cap is None or count_key is None or n * d[count_key] <= cap  # noqa: E731
    cost = lambda n, d: (sum(block_seconds(movers[:n], d, work, one_side))  # noqa: E731
                         if within(n, d) else budget + 1)
    n = least_slots
    if cost(n, dose) > budget:
        count = next((k for k in ("sets", "rounds") if k in dose), None)
        if count and not fixed and dose[count] > 2:
            dose[count] = 2
        if cost(n, dose) > budget:
            floor = f" even at two {count} each" if count and not fixed else ""
            raise Unfit(f"{what} is too short for {n} slots of this method{floor}; "
                        "ask for more minutes or another method")
    while n < first and cost(n + 1, dose) <= budget:
        n += 1
    if not fixed:
        for key in _raise_order(ranges, work):
            step = STEP.get(key, 5)
            while dose[key] + step <= ranges[key][1]:
                trial = dict(dose, **{key: dose[key] + step})
                if cost(n, trial) > budget:
                    break
                dose = trial
    if n == first and all(dose[k] == v[1] for k, v in ranges.items()):
        while n < len(movers) and cost(n + 1, dose) <= budget:
            n += 1
    return n, dose


# ---- movements ---------------------------------------------------------------------------

def _ids(cat: catalog.Catalog, names: List[str]) -> Set[str]:
    """Catalog ids for names or ids from the profile or log; unknown names are skipped."""
    found = (catalog.resolve(cat, n) for n in names)
    return {m.id for m in found if m}


def _candidates(pattern: str, pool: List[catalog.Movement], key, used: Set[str]) -> List[catalog.Movement]:
    """Movements for a pattern: primary matches ranked, then secondary ones ranked when fewer than three;
    one already the default of an earlier slot moves to the back."""
    found = sorted((m for m in pool if m.patterns and m.patterns[0] == pattern), key=key)
    if len(found) < 3:
        found += sorted((m for m in pool if pattern in m.patterns[1:]), key=key)
    return [m for m in found if m.id not in used] + [m for m in found if m.id in used]


FAMILIES = {"lower": ("squat", "hinge", "lunge", "hips", "balance"),
            "push": ("horizontal-push", "vertical-push", "arms"),
            "pull": ("horizontal-pull", "vertical-pull"),
            "core": ("anti-extension", "anti-rotation", "rotation", "carry")}


def family(pattern: str) -> str:
    """lower, push, pull, core or other: what a paired set alternates between."""
    return next((name for name, ps in FAMILIES.items() if pattern in ps), "other")


SEATS = ("bench", "chair")   # equipment a movement is done on, seated or lying, rather than on the floor


def place(m: catalog.Movement) -> str:
    """Where a movement is done: standing, on a bench or seat (anything seated, and anything lying or
    kneeling on a bench or chair), or on the floor (lying, side-lying, all-fours, kneeling)."""
    if m.position == "standing":
        return "standing"
    if m.position == "seated" or any(alt in SEATS for need in m.needs for alt in need.split("|")):
        return "seat"
    return "floor"


def _by_place(entries: list) -> list:
    """(pattern, movements) entries with those done in one place together: the first entry's place
    first, then the others in the order they first come, each keeping its own order, so a round
    changes place at most once per place it visits."""
    places = list(dict.fromkeys(place(ms[0]) for _, ms in entries))
    return sorted(entries, key=lambda e: places.index(place(e[1][0])))


def _pair_up(entries: list) -> list:
    """Slots in paired order: each next unpaired slot with a later one of another family, from the
    family most of the rest share (so no like pair is left at the end), else with the next one."""
    left, out = list(entries), []
    while left:
        a = left.pop(0)
        out.append(a)
        if left:
            others = [i for i, e in enumerate(left) if family(e[0]) != family(a[0])]
            if others:
                common = max(others, key=lambda i: sum(family(e[0]) == family(left[i][0]) for e in left))
                j = min(i for i in others if family(left[i][0]) == family(left[common][0]))
            else:
                j = 0
            out.append(left.pop(j))
    return out


def _cycle(filled: list, count: int, spread: bool = False) -> list:
    """`count` (pattern, movements) entries going round the patterns, each led by the first of its
    pattern's top-effort movements (all of them when none carries an effort) no earlier entry leads
    with, else by the next of those round: a hard block repeats a hard movement before a moderate
    one leads it. With `spread` (intervals), a fresh one on a machine no earlier entry led on comes
    first, so the blocks go round the machines on hand before a second block on any one."""
    out, leads, machines = [], set(), set()
    for i in range(count):
        p, ms = filled[i % len(filled)]
        tier = [m for m in ms if m.effort == ms[0].effort]
        fresh = [m for m in tier if m.id not in leads]
        new = [m for m in fresh if spread and _machine(m) and station(m) not in machines]
        lead = (new or fresh or _rotate(tier, i // len(filled)))[0]
        ms = [lead] + [m for m in ms if m is not lead]
        leads.add(lead.id)
        if _machine(lead):
            machines.add(station(lead))
        out.append((p, ms))
    return out


def _machine(m: catalog.Movement) -> bool:
    """True for conditioning on a machine (a bike, a treadmill), not on the floor."""
    return m.intensity == "conditioning" and bool(m.needs)


def _rotate(ms: List[catalog.Movement], k: int) -> List[catalog.Movement]:
    """The list turned so its k-th movement (counting round) comes first."""
    k %= len(ms)
    return ms[k:] + ms[:k]


def _reasons(m: catalog.Movement, ms: List[catalog.Movement], pattern: str, ctx: dict) -> str:
    out = []
    if m.id in ctx["likes"]:
        out.append("liked")
    if ctx["last"] is not None and m.id not in ctx["last"]:
        out.append("fresh (not last session)")
    if m.id in ctx["healthy"]:
        out.append("healthy side only")
    for area in ctx["areas"]:
        if not m.loads.get(area, 0) and any(o.loads.get(area, 0) for o in ms):
            out.append(f"light on the {area}")
    if ctx["week"].get(pattern, 0) == 0:
        out.append(f"{pattern} neglected this week")
    if m.id in ctx["rehab"]:
        out.append("rehab, named in health")
    return ", ".join(out)


def target_patterns(cat: catalog.Catalog, patterns: List[str], targets: List[str], leads) -> List[str]:
    """The patterns a request's targets name: a pattern itself, or for a muscle the method's patterns
    whose movements list it among their first two muscles (any pattern when none of the method's do)."""
    wanted: List[str] = []
    for t in targets:
        if t in cat.patterns:
            wanted.append(t)
        else:
            wanted += [p for p in patterns if t in leads(p)] or [p for p in cat.patterns if t in leads(p)]
    return list(dict.fromkeys(wanted))


def _order(cat: catalog.Catalog, patterns: List[str], targets: List[str], week: Dict[str, int],
           leads, liked: Set[str] = frozenset()) -> List[str]:
    """Targets first (see `target_patterns`), then the patterns holding a liked movement, then the
    patterns the week has not trained, then the rest, each in the method's order."""
    wanted = target_patterns(cat, patterns, targets, leads)
    rest = [p for p in patterns if p not in wanted]
    fond = [p for p in rest if p in liked]
    rest = [p for p in rest if p not in liked]
    return wanted + fond + [p for p in rest if week.get(p, 0) == 0] + [p for p in rest if week.get(p, 0)]


# ---- compose -----------------------------------------------------------------------------

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


def compose(request: dict, cat: catalog.Catalog, sess: sessions.Sessions, profile, health, log,
            today: datetime.date) -> Skeleton:
    """The skeleton for `request` (goal, minutes, and one of kit, preset or equipment; optionally method,
    level, target, limits, avoid). ValueError names an unknown value; Unfit says why nothing fits."""
    goal, minutes = request.get("goal"), request.get("minutes")
    if goal not in sess.goals:
        raise ValueError(f"unknown goal \"{goal}\" (choose from: {', '.join(sess.goals)})")
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
    likes, dislikes = _ids(cat, context.likes(profile)), _ids(cat, context.dislikes(profile))
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

    last = log[-1] if log else None
    last_format = last.format if last else None
    weights = context.kit_weights(profile).get(request.get("kit") or "")
    env = {"kit_loads": _loads_line(weights, equipment) if weights else "", "minutes": minutes, "sess": sess, "cat": cat, "request": request, "level": level, "log": log,
           "today": today, "sel": sel, "limits": limits, "likes": likes, "last": last, "health": health,
           "equipment": equipment, "avoid": avoid, "dislikes": dislikes, "warnings": warnings}
    if request.get("method"):
        method = sess.methods.get(request["method"])
        if method is None or goal not in method.goals:
            fit = [m.name for m in sess.methods.values() if goal in m.goals]
            raise ValueError(f"method \"{request['method']}\" is not one for {goal} (choose from: {', '.join(fit)})")
        return _build(method, "it was asked for", env)
    ranked = sessions.ranked(sess, goal, minutes, level, equipment, last_format)
    if not ranked:
        raise Unfit(f"no method fits a {minutes} minute {goal} session at the {level} level with this kit")
    first = ranked[0]
    rotated = last_format and sessions.ranked(sess, goal, minutes, level, equipment)[0].name == last_format
    why = (f"the last session was {last_format}" if rotated and first.name != last_format
           else f"it suits {goal} in {minutes} minutes")
    built: List[Skeleton] = []
    failed = None
    for i, method in enumerate(ranked):   # the next method when one cannot fill its slots today
        try:
            built.append(_build(method, why if i == 0 else f"{first.name} did not fit", env))
        except Unfit as e:
            if failed is None:
                failed = e
            continue
        if not built[0].dropped or built[0].method.work != "sets" or goal_is(request, "targeted"):
            return built[0]
    if not built:
        raise failed
    return built[0] if goal_is(request, "targeted") else _covering(built, last_format)


def _covering(built: List[Skeleton], last_format: Optional[str]) -> Skeleton:
    """The first skeleton, unless it runs straight sets that drop patterns for time and paired sets (not
    the last session's format) fit more of them into the same minutes: pairing roughly halves the time a
    set takes, and every major muscle group each session beats one format's tidiness (programming.md,
    Rest and pairing, and Muscle coverage)."""
    first = built[0]
    better = [sk for sk in built[1:] if sk.method.work in COVERING and sk.method.name != last_format
              and len(sk.dropped) < len(first.dropped)]
    if not better:
        return first
    best = min(better, key=lambda sk: len(sk.dropped))   # the earliest of the fewest dropped
    drops = f"drops only {', '.join(best.dropped)}" if best.dropped else "fits every pattern"
    return best._replace(why=f"{first.method.name} would drop {', '.join(first.dropped)} for time, "
                             f"and {best.method.name} {drops} in {best.minutes} minutes")


def _build(method: sessions.Method, why: str, env: dict) -> Skeleton:
    """The skeleton for one method, from compose's request, selection and log (`env`)."""
    minutes, sess, cat, request, level, log, today = (env[k] for k in (
        "minutes", "sess", "cat", "request", "level", "log", "today"))
    sel, limits, likes, last, health = env["sel"], env["limits"], env["likes"], env["last"], env["health"]
    equipment, avoid, dislikes = env["equipment"], env["avoid"], env["dislikes"]
    warnings = list(env["warnings"])
    total = minutes * 60
    warmup, cooldown = _clamp(method.warmup, total), _clamp(method.cooldown, total)
    fin = method.finisher
    finisher = _clamp(fin, total) if fin and minutes >= fin.get("from_minutes", 0) else 0
    main = total - warmup - cooldown - finisher
    if main <= 0:
        raise Unfit(f"{minutes} minutes leaves no time for work after the warm-up and cool-down")

    week = coverage.week(log, today, cat=cat)
    order = {mid: i for i, mid in enumerate(cat.movements)}
    healthy = {m.id for m in sel.healthy_side_only}
    pool = sorted(sel.allowed + sel.healthy_side_only, key=lambda m: order[m.id])
    last_ids = _ids(cat, last.movements) if last else set()
    areas = list(dict.fromkeys(lim.area for lim in limits))
    limited = lambda m: sum(m.loads.get(a, 0) + (m.support.get(a, 0) if m.sided else 0) for a in areas)  # noqa: E731
    closeness = lambda m: catalog.LEVELS.index(level) - catalog.LEVELS.index(m.level)  # noqa: E731
    has_load = any(e in catalog.LOAD_EQUIPMENT for e in equipment)
    machines = {e for m in pool if m.intensity == "conditioning" for need in m.needs for e in need.split("|")}
    # with load on hand, a strength movement that uses it ranks ahead of a bodyweight one at the same
    # level; with a cardio machine on hand, conditioning on it ranks ahead of conditioning on the floor
    unloaded = lambda m: ((has_load and m.intensity == "strength" and not catalog.loaded(m))  # noqa: E731
                          or (bool(machines & equipment) and m.intensity == "conditioning" and not m.needs))
    effort = lambda m: EFFORT_RANK[level].get(m.effort, 0)  # noqa: E731
    rank = lambda m: (m.id in last_ids, m.id not in likes, closeness(m), unloaded(m), effort(m),  # noqa: E731
                      limited(m), order[m.id])
    ctx = {"likes": likes, "last": last_ids if last else None, "healthy": healthy, "areas": areas,
           "week": week, "rehab": {i for lim in limits for i in lim.rehab}}
    leads = lambda p: {mu for m in pool if p in m.patterns for mu in m.muscles[:2]}  # noqa: E731
    liked = {p for m in pool if m.id in likes for p in m.patterns[:1]}
    targets = request.get("target") or []

    blocks: List[Tuple[str, List[Slot]]] = []
    dropped: List[str] = []
    used: Set[str] = set()
    spent = 0
    for b, block in enumerate(method.blocks):
        budget = main - spent if b == len(method.blocks) - 1 else round(main * block["share"])
        # interval work is never an easy movement, and a little-rest circuit takes no barbell lift,
        # which wants a spotter and a rack set up for it
        work_pool = [m for m in pool if not (method.work == "intervals" and m.effort == "easy")
                     and not (method.work == "rounds" and "barbell" in m.needs)]
        aim = targets if b == 0 else []
        pats = _order(cat, block["patterns"], aim, week, leads, liked)
        filled = _fill(pats, work_pool, rank, used)
        mixed = False
        # "hard enough" is the level's leading effort: hard above novice, moderate or hard at novice
        enough = sum(1 for _, ms in filled for m in ms if EFFORT_RANK[level].get(m.effort, 0) == 0
                     or (level == "novice" and m.effort == "hard"))
        if block.get("fallback") and enough < 2:
            mixed = True
            more = _order(cat, block["fallback"], aim, week, leads, liked)
            filled += _fill([p for p in more if p not in pats], work_pool, rank, used)
            warnings.append("few movements on today's kit are hard enough for intervals, so timed "
                            f"{', '.join(p for p, _ in filled if p in block['fallback'])} work joins in")
        least = method.min_slots if len(method.blocks) == 1 else 1
        if len(filled) < least and len(method.blocks) > 1:
            raise Unfit(f"no movement fits the {block['intensity']} block of {method.name} "
                        "with today's kit, level and limits")
        if len(filled) < least:
            raise Unfit(f"only {len(filled)} of the {least} movement slots {method.name} needs have a "
                        "movement that fits today's kit, level and limits")
        if method.work in CYCLING:   # one pattern may fill several slots, each with the next movement first
            first = CYCLE_CAP
            entries = _cycle(filled, first, spread=method.work == "intervals")
        else:                        # a second pass through the patterns, only once the first is full
            wanted = set(target_patterns(cat, block["patterns"], aim, leads)) if goal_is(request, "targeted") else set()
            aimed = [(p, ms) for p, ms in filled if p in wanted]
            again = [(p, _rotate(ms, 1)) for p, ms in aimed if len(ms) > 1]   # a target gets two slots
            others = [(p, ms) for p, ms in filled if p not in wanted]
            first = len(aimed) + len(again) + len(others)
            entries = aimed + again + others + [(p, _rotate(ms, 1)) for p, ms in others if len(ms) > 1]
        n, dose = _fit([ms[0] for _, ms in entries], _ranges(sess, method, block["intensity"], level),
                       method.work, budget, least, bool(method.fixed), f"a {minutes} minute session", first,
                       _cap(sess, method, block["intensity"], level), healthy)
        chosen = entries[:n]
        if method.work == "pairs":
            chosen = _pair_up(chosen)
        elif method.work == "rounds":   # stations done in one place together: few trips to and from the floor
            chosen = _by_place(chosen)
        elif method.work == "intervals":   # one machine's slots together, in the order they first come
            seen = list(dict.fromkeys(station(ms[0]) for _, ms in chosen))
            chosen = sorted(chosen, key=lambda e: seen.index(station(e[1][0])))
        secs = block_seconds([ms[0] for _, ms in chosen], dose, method.work, healthy)
        slots = [Slot(p, block["intensity"], _own_dose(ms[0], dose, method, sess), s,
                      [(m, _reasons(m, ms, p, ctx)) for m in ms]) for (p, ms), s in zip(chosen, secs)]
        if mixed and not any(_machine(s.candidates[0][0]) for s in slots):   # all on the floor: a circuit
            slots = [s._replace(dose=dict(s.dose, mixed=1)) for s in slots]
        used |= {s.candidates[0][0].id for s in slots}
        dropped += [p for p, _ in filled if p not in {s.pattern for s in slots}]
        spent += sum(secs)
        blocks.append((block["intensity"], slots))
    count = sum(len(slots) for _, slots in blocks)
    if count < method.min_slots:
        raise Unfit(f"only {count} of the {method.min_slots} movement slots {method.name} needs fit today")

    spare = main - spent
    if method.work == "intervals" and not method.fixed and spare >= STEADY_LEAST:
        steady = _steady(blocks[-1][1], pool, rank, ctx, min(spare, STEADY_MOST), used)
        if steady:
            blocks[-1][1].append(steady)
            used.add(steady.candidates[0][0].id)
            spare = main - sum(s.seconds for _, slots in blocks for s in slots)   # the change is in the last interval
    flat = [(bi, si) for bi, (_, slots) in enumerate(blocks) for si in range(len(slots))
            if method.work != "pairs" or si % 2 == 1 or si == len(slots) - 1]   # pairs rest only between pairs
    for bi, si in flat[:-1]:
        extra = min(BETWEEN_SLOTS, spare)
        if extra <= 0:
            break
        slot = blocks[bi][1][si]
        blocks[bi][1][si] = slot._replace(seconds=slot.seconds + extra)
        spare -= extra
    if finisher:
        extra = max(0, min(spare, fin["seconds"][1] - finisher))
        finisher += extra
        spare -= extra
    for part, name in ((method.cooldown, "cooldown"), (method.warmup, "warmup")):
        extra = max(0, min(spare, part["seconds"][1] - (cooldown if name == "cooldown" else warmup)))
        cooldown, warmup = (cooldown + extra, warmup) if name == "cooldown" else (cooldown, warmup + extra)
        spare -= extra
    if spare > SPARE_WARNING * total:
        warnings.append(f"method filled early: {spare} s spare went to the cool-down")
    cooldown += spare

    today_lines = [f"today: {context.limit_line(lim)}" for lim in request.get("limits") or []]
    sides = {m.id: _healthy_side(m, limits) for m in sel.healthy_side_only}
    first_work = next((s.candidates[0][0] for _, slots in blocks for s in slots), None)
    warm = _extras(pool, _warmup_fit, 5, rank, used, ctx, sides,
                   lambda m: first_work is None or station(m) != station(first_work))
    extras = {"warmup": warm,   # the later lists leave out the warm-up's first picks
              "finisher": (_extras(pool, _finisher_fit(level, sess), 3, rank, used | {m.id for m, _ in warm[:1]}, ctx, sides)
                           if finisher else []),
              # breathing may come back to close a session whose block already breathed
              "cooldown": _extras(pool, _cooldown_fit, 5, rank, {i for i in used if not _breathing(cat, i)}
                                  | {m.id for m, _ in warm[:2]}, ctx, sides)}
    fdose = _finisher_dose(sess, level, finisher, extras["finisher"]) if finisher else None
    return Skeleton(method, minutes, warmup, blocks, finisher, cooldown, dropped, warnings,
                    _would_open(cat, sel, equipment, level, limits, avoid, dislikes),
                    tuple(context.clinician_lines(health, cat.areas, cat.flags)) + tuple(today_lines), why,
                    sides, extras, fdose, env.get("kit_loads", ""), cat, tuple(limits))


def _breathing(cat: catalog.Catalog, mid: str) -> bool:
    m = cat.movements.get(mid)
    return bool(m and m.patterns and m.patterns[0] == "breathing")


def _own_dose(m: catalog.Movement, dose: dict, method: sessions.Method, sess: sessions.Sessions) -> dict:
    """The block's dose for one slot. An interval on a timed movement shorter than the dose's work
    (a twenty second sprint) works for its own seconds and rests the rest of the interval. An all-out
    sprint rests at least [all_out] rest_ratio times its work: the slot keeps its seconds and holds
    fewer, longer intervals (programming.md, Rest between intervals)."""
    out = dict(dose)
    if method.work != "intervals" or method.fixed:
        return out
    if m.measure == "time" and 0 < m.hold_seconds < out.get("work_seconds", 0):
        out["rest_seconds"] = out.get("rest_seconds", 0) + out["work_seconds"] - m.hold_seconds
        out["work_seconds"] = m.hold_seconds
    if sessions.all_out(sess, m):
        out.update(_sprint_shape(sess, out["work_seconds"], out.get("rest_seconds", 0), out["rounds"]))
    return out


def _sprint_shape(sess: sessions.Sessions, work: int, rest: int, rounds: int) -> dict:
    """work_seconds, rest_seconds and rounds for an all-out sprint in the time `rounds` intervals of
    `work` and `rest` take: the rest at least rest_ratio times the work, as many rounds as then fit
    (at least one), the time shared evenly between them."""
    span = rounds * (work + rest)
    least = work * (1 + sess.all_out.get("rest_ratio", 0))
    if work + rest >= least:
        return {"work_seconds": work, "rest_seconds": rest, "rounds": rounds}
    count = max(1, span // least)
    return {"work_seconds": work, "rest_seconds": span // count - work, "rounds": count}


def goal_is(request: dict, goal: str) -> bool:
    return request.get("goal") == goal


def _fill(patterns: List[str], pool: List[catalog.Movement], rank, used: Set[str]) -> list:
    """(pattern, ranked movements) for each pattern with any; each default joins `used`."""
    out = []
    for p in patterns:
        ms = _candidates(p, pool, rank, used)
        if ms:
            out.append((p, ms))
            used.add(ms[0].id)
    return out


def _steady(slots: List[Slot], pool: List[catalog.Movement], rank, ctx: dict, seconds: int,
            used: Set[str]) -> Optional[Slot]:
    """A steady block of moderate locomotion after the intervals, for the time past the efforts cap: a
    movement no slot uses first, on a machine when there is one, ranked as the slots are. None when
    nothing fits."""
    last = slots[-1].candidates[0][0] if slots else None
    found = [m for m in pool if m.patterns and m.patterns[0] == "locomotion" and m.effort == "moderate"
             and not {"fast", "impact"} & set(m.flags)]
    if not found:
        return None
    # a machine first, even one an interval used (a steady ride after bike intervals): one no interval
    # used, else the one the last interval is on (no change), then a movement no slot uses;
    # rank(m)[3] is "on the floor with a machine at hand"
    ridden = {station(s.candidates[0][0]) for s in slots}
    found.sort(key=lambda m: (rank(m)[3], station(m) in ridden,
                              last is not None and station(m) != station(last), m.id in used, rank(m)))
    change = CHANGE_SECONDS if last is not None and station(found[0]) != station(last) else 0
    work = seconds - change
    if work < STEADY_LEAST:
        return None
    if change:   # the change belongs to the last interval
        slots[-1] = slots[-1]._replace(seconds=slots[-1].seconds + change)
    dose = {"rounds": 1, "work_seconds": work, "rest_seconds": 0, "steady": 1}
    return Slot("locomotion", "conditioning", dose, work, [(m, _reasons(m, found, "locomotion", ctx)) for m in found])


def _warmup_fit(m: catalog.Movement) -> Optional[int]:
    """Easy locomotion first, then moderate locomotion with no fast or impact work, then mobility."""
    first = m.patterns[0] if m.patterns else ""
    if first == "locomotion":
        if m.effort == "easy":
            return 0
        if m.effort == "moderate" and not {"fast", "impact"} & set(m.flags):
            return 1
        return None
    return 2 if first == "mobility" else None


def _finisher_fit(level: str, sess: sessions.Sessions):
    """Conditioning in the level's effort order (hard first above novice, moderate first at novice),
    an all-out sprint last, since a finisher's short rests don't suit it; never an easy one."""
    order = EFFORT_RANK[level]
    return lambda m: ((len(order) if sessions.all_out(sess, m) else order[m.effort])
                      if m.intensity == "conditioning" and m.effort in ("hard", "moderate") else None)


def _cooldown_fit(m: catalog.Movement) -> Optional[int]:
    """Box breathing first (the close), then other breathing, then mobility."""
    first = m.patterns[0] if m.patterns else ""
    if first == "breathing":
        return 0 if m.id == "box-breathing" else 1
    return 2 if first == "mobility" else None


def _finisher_dose(sess: sessions.Sessions, level: str, seconds: int, picks=()) -> dict:
    """The finisher's shape from the level's conditioning dose: its shortest work and rest, as many
    rounds as the seconds hold after thirty to get to its equipment. When the first pick is an
    all-out sprint (nothing else fits), it works its own seconds and rests as `_sprint_shape` says."""
    table = sessions.dose(sess, "conditioning", level)
    work, rest = table["work_seconds"][0], table["rest_seconds"][0]
    first = picks[0][0] if picks else None
    if first is not None and sessions.all_out(sess, first):
        rest, work = rest + max(0, work - first.hold_seconds), min(work, first.hold_seconds)
        return _sprint_shape(sess, work, rest, max(1, (seconds - CHANGE_SECONDS) // (work + rest)))
    return {"rounds": max(1, (seconds - CHANGE_SECONDS) // (work + rest)), "work_seconds": work, "rest_seconds": rest}


def _extras(pool: List[catalog.Movement], fits, top: int, key, used: Set[str], ctx: dict,
            sides: Dict[str, str], later=lambda m: False) -> List[Tuple[catalog.Movement, str]]:
    """Up to `top` movements for the warm-up, finisher or cool-down: those of the screened pool that
    `fits` (a number: earlier is preferred; None: left out) and are not in `used` (the slots' defaults
    and the earlier lists' first picks), then those `later` puts behind, then ranked as the slots are;
    a healthy-side-only one says which side it works."""
    found = sorted((m for m in pool if fits(m) is not None and m.id not in used),
                   key=lambda m: (fits(m), later(m), key(m)))
    out = []
    for m in found[:top]:
        why = _reasons(m, found, m.patterns[0], ctx)
        if m.id in sides:
            why = why.replace("healthy side only", f"{sides[m.id]} side only")
        out.append((m, why))
    return out


def _healthy_side(m: catalog.Movement, limits: List[catalog.Limit]) -> str:
    """The side a healthy-side-only movement works: the one opposite the sided limit that loads it."""
    for lim in limits:
        skipped = m.rehab and m.id in lim.rehab   # as in catalog.select
        if lim.side in OTHER_SIDE and not skipped and m.loads.get(lim.area, 0) >= catalog.threshold(lim):
            return OTHER_SIDE[lim.side]
    return "healthy"


def _would_open(cat: catalog.Catalog, sel: catalog.Selection, equipment: Set[str], level: str,
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


# ---- output ------------------------------------------------------------------------------

def _side_words(m: catalog.Movement, sk: Skeleton) -> str:
    """"each side" for a sided movement, "<side> side only" for a healthy-side-only one, else ""."""
    if not m.sided:
        return ""
    side = (sk.healthy_sides or {}).get(m.id)
    return f"{side} side only" if side else "each side"


def _one_side(m: catalog.Movement, sk: Skeleton) -> bool:
    return m.id in (sk.healthy_sides or {})


def _named(m: catalog.Movement, sk: Skeleton) -> str:
    """A movement's name with its side words, for a draft title."""
    words = _side_words(m, sk)
    return f"{m.name} {words}" if words else m.name


def _five(x: float) -> int:
    return int(5 * round(x / 5))


def rest_held(slot: Slot, sk: Skeleton) -> Optional[int]:
    """The rest between a straight-sets slot's sets that its seconds actually hold (spare included),
    to the nearest five seconds; None for one set or another kind of work."""
    m, d = slot.candidates[0][0], slot.dose
    if sk.method.work != "sets" or d.get("sets", 1) < 2:
        return None
    work = m.transition_seconds + d["sets"] * _set_time(m, d, _one_side(m, sk)) + START_SECONDS
    return _five((slot.seconds - work) / (d["sets"] - 1))


def _round_rests(slots: List[Slot], sk: Skeleton) -> Tuple[int, List[int]]:
    """(seconds of one round's work, the rest after each round) for a rounds block: the block's rests
    and spare go to the rounds before the last, the remainder to the one before last."""
    rounds = slots[0].dose.get("rounds", 1)
    base = sum(s.candidates[0][0].transition_seconds
               + _work_time(s.candidates[0][0], s.dose, _one_side(s.candidates[0][0], sk)) for s in slots)
    extra = sum(s.seconds for s in slots) - rounds * base
    if rounds == 1:
        return base, [extra]
    rests = [extra // (rounds - 1)] * (rounds - 1) + [0]
    rests[rounds - 2] += extra % (rounds - 1)
    return base, rests


def _dose_text(slot: Slot, sk: Skeleton) -> str:
    d, m, work = slot.dose, slot.candidates[0][0], sk.method.work
    if work == "intervals":   # an interval's work is the same seconds whichever side, so only a lone side is named
        if d.get("steady"):
            return f"one steady block of {d['work_seconds']} s"
        side = _side_words(m, sk)
        text = f"{d['rounds']} rounds of {d['work_seconds']} s on, {d.get('rest_seconds', 0)} s off"
        return text + (f" ({side})" if side and side != "each side" else "")
    count, label = (d["sets"], "sets") if "sets" in d else (d.get("rounds", 1), "rounds")
    each = str(reps(m, d)) if m.measure == "reps" and "reps" in d else f"{_work_each(m, d)} s"
    text = f"{count} {label} of {each}" + (f" ({_side_words(m, sk)})" if _side_words(m, sk) else "")
    if work == "rounds" or not d.get("rest_seconds"):
        return text
    if work == "pairs":
        return text + f", rest {d['rest_seconds']} s after each pair set"
    held = rest_held(slot, sk)
    return text + (f", rest {held} s" if held is not None else "")


def _total(sk: Skeleton) -> int:
    return sk.warmup + sum(s.seconds for _, slots in sk.blocks for s in slots) + sk.finisher + sk.cooldown


def _picks(candidates: List[Tuple[catalog.Movement, str]]) -> str:
    return "; ".join(f"{m.id} [{why}]" if why else m.id for m, why in candidates)


def _extra_lines(head: str, candidates) -> List[str]:
    """A warm-up, finisher or cool-down line, with its screened candidates on the next line."""
    return [head + ":", f"  {_picks(candidates)}"] if candidates else [head]


def _finisher_head(sk: Skeleton) -> str:
    fd = sk.finisher_dose
    shape = f", {fd['rounds']} rounds of {fd['work_seconds']} s on, {fd['rest_seconds']} s off" if fd else ""
    return f"Finisher: {sk.finisher} s{shape}"


def render(sk: Skeleton) -> List[str]:
    """The skeleton as lines: health rules, warnings, the method, then the timing and each slot's
    pattern, dose and top three movements with the reasons they rank there; the warm-up, finisher and
    cool-down list their screened candidates on the line under them. The muscles, the limit cues and
    the coaching notes close it. A rounds block says the rest
    between its rounds; paired slots are numbered by pair."""
    out = [f"Health: {line}" for line in sk.health] + list(sk.warnings)
    out.append(f"Method: {sk.method.name}, because {sk.why}. {sk.method.about}")
    extras = sk.extras or {}
    out += _extra_lines(f"Warm-up: {sk.warmup} s", extras.get("warmup"))
    for intensity, slots in sk.blocks:
        head = f"{intensity} block, {sum(s.seconds for s in slots)} s"
        if sk.method.work == "rounds" and slots and slots[0].dose.get("rounds", 1) > 1:
            _, rests = _round_rests(slots, sk)
            head += f", rest {_five(sum(rests) / (len(rests) - 1))} s between rounds"
        if slots and slots[0].dose.get("mixed"):
            head += ", as a circuit: each round, one interval of each movement in turn"
        out.append(head + ":")
        for i, s in enumerate(slots):
            alone = i == len(slots) - 1 and i % 2 == 0
            pair = f"pair {i // 2 + 1}, " if sk.method.work == "pairs" and not alone else ""
            out.append(f"  {pair}{s.pattern} ({_dose_text(s, sk)}, {s.seconds} s): {_picks(s.candidates[:3])}")
    if sk.finisher:
        out += _extra_lines(_finisher_head(sk), extras.get("finisher"))
    out += _extra_lines(f"Cool-down: {sk.cooldown} s", extras.get("cooldown"))
    out.append(f"Total: {_total(sk)} s of {sk.minutes * 60} s")
    if sk.dropped:
        out.append(f"Dropped: {', '.join(sk.dropped)} (no time left for them)")
    if sk.would_open:
        out.append("Would open up: " + ", ".join(f"{e} (+{n})" for e, n in sk.would_open))
    if sk.kit_loads:
        out.append(sk.kit_loads)
    out += muscle_lines(sk)
    out += limit_cue_lines(sk)
    out += coaching(sk)
    return out


MAJOR = ("quads", "hamstrings", "glutes", "chest", "back", "shoulders", "biceps", "triceps", "core")
MUSCLE_GROUP = {"lats": "back"}   # muscles counted under a major group


def muscle_lines(sk: Skeleton) -> List[str]:
    """The major muscle groups the work's first picks train, and the ones they leave out."""
    worked = {MUSCLE_GROUP.get(mu, mu) for _, slots in sk.blocks for s in slots for mu in s.candidates[0][0].muscles}
    if not worked:
        return []
    missing = [g for g in MAJOR if g not in worked]
    line = "Muscles: " + ", ".join(g for g in MAJOR if g in worked)
    return [line + (f"; left out: {', '.join(missing)}" if missing else "; every major group")]


def limit_cue_lines(sk: Skeleton) -> List[str]:
    """The catalog's spoken cues for each limit today (health.md's and the request's, each once), under
    a line naming the limit and its side, so the script says how to work around it at every station."""
    if sk.cat is None:
        return []
    out = []
    for lim in dict.fromkeys((lim.area, lim.level, lim.side) for lim in sk.limits):
        area, level, side = lim
        lines = catalog.limit_cues(sk.cat, catalog.Limit(area, side, level, [], [], ""))
        if lines:
            where = f", {side} side" if side in OTHER_SIDE else ""
            out.append(f"  {area} {'off limits' if level == 'off-limits' else 'delicate'}{where}:")
            out += [f"    {line}" for line in lines]
    return ["Limit cues (the catalog's, for each limit today; say them wherever they apply):"] + out if out else []


def _coached(sk: Skeleton) -> List[catalog.Movement]:
    """The movements the coaching notes cover: each slot's first pick, the warm-up's first three, the
    finisher's first two and the cool-down's first two, each once."""
    extras = sk.extras or {}
    ms = [m for m, _ in (extras.get("warmup") or [])[:3]]
    ms += [s.candidates[0][0] for _, slots in sk.blocks for s in slots]
    ms += [m for m, _ in (extras.get("finisher") or [])[:2]] + [m for m, _ in (extras.get("cooldown") or [])[:2]]
    return list({m.id: m for m in ms}.values())


def coaching(sk: Skeleton) -> List[str]:
    """The catalog's spoken coaching for the movements the script will most likely use, so cues come
    from the catalog, not memory. `./sweatcast movements --about <ids>` prints it for any swap."""
    ms = _coached(sk)
    if not ms:
        return []
    out = ["Coaching (the first picks; ./sweatcast movements --about <ids> for any other candidate):"]
    for m in ms:
        out += movements.about(sk.cat, m, (sk.healthy_sides or {}).get(m.id))
    return out


def _loads_line(weights: Tuple[str, Dict[str, list]], equipment: Set[str]) -> str:
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


def _round_markers(slots: List[Slot], sk: Skeleton) -> List[str]:
    """One marker per round of a `rounds` block, each before the last naming the rest that ends it."""
    rounds = slots[0].dose.get("rounds", 1)
    base, rests = _round_rests(slots, sk)
    names = ", ".join(_named(s.candidates[0][0], sk) for s in slots)
    out = []
    for i in range(rounds):
        then = f", then rest {rests[i]} s" if i < rounds - 1 and rests[i] else ""
        out.append(f"@@ {base + rests[i]} | Round {i + 1} of {rounds}: {names}{then}")
    return out


def _pair_markers(slots: List[Slot], sk: Skeleton) -> List[str]:
    """One marker per set of each pair: the move to the first station and its set, the move to the second
    and its set, then the rest; the last set also holds the pair's spare. A lone last slot runs its sets
    alone."""
    out = []
    groups = [slots[i:i + 2] for i in range(0, len(slots), 2)]
    for g, group in enumerate(groups):
        ms = [s.candidates[0][0] for s in group]
        d = group[0].dose
        sets, rest = d["sets"], d.get("rest_seconds", 0)
        work = sum(_set_time(m, d, _one_side(m, sk)) for m in ms)
        secs = [work + sum(m.transition_seconds for m in ms) + (rest if k < sets - 1 else 0) for k in range(sets)]
        secs[-1] += sum(s.seconds for s in group) - sum(secs)
        names = ", then ".join(_named(m, sk) for m in ms)
        head = f"Pair {g + 1} of {sum(len(x) == 2 for x in groups)}, " if len(group) == 2 else ""
        title = names[:1].upper() + names[1:]
        out += [f"@@ {secs[k]} | {head}set {k + 1} of {sets}: {title}" if head else
                f"@@ {secs[k]} | {title}, set {k + 1} of {sets}" for k in range(sets)]
    return out


def _interval_markers(slots: List[Slot], sk: Skeleton) -> List[str]:
    """One marker per work-and-rest interval, numbered within each block when there are several; a
    block's last interval names the next movement when it is on other equipment; a steady block is
    one marker."""
    out = []
    work = [s for s in slots if not s.dose.get("steady")]
    if work and all(s.dose.get("mixed") for s in work):   # a circuit: each round one interval of each
        rounds = work[0].dose["rounds"]
        for i in range(rounds):
            for s in work:
                each = s.dose["work_seconds"] + s.dose.get("rest_seconds", 0)
                secs = each + (s.seconds - s.dose["rounds"] * each if i == rounds - 1 else 0)
                name = _named(s.candidates[0][0], sk).removesuffix(" each side")
                out.append(f"@@ {secs} | Round {i + 1} of {rounds}, {name}")
        return out + [f"@@ {s.seconds} | {_named(s.candidates[0][0], sk)}, steady block"
                      for s in slots if s.dose.get("steady")]
    many = len(work) > 1
    for j, s in enumerate(slots):
        m = s.candidates[0][0]
        name = _named(m, sk).removesuffix(" each side")   # an interval's work is the same whichever side
        if s.dose.get("steady"):
            out.append(f"@@ {s.seconds} | {name}, steady block")
            continue
        rounds, each = s.dose["rounds"], s.dose["work_seconds"] + s.dose.get("rest_seconds", 0)
        nxt = slots[j + 1].candidates[0][0] if j + 1 < len(slots) else None
        move = f", then move to the {nxt.name}" if nxt and station(nxt) != station(m) else ""
        block = f"block {j + 1} of {sum(not x.dose.get('steady') for x in slots)}, " if many else ""
        for i in range(rounds):
            last = i == rounds - 1
            secs = each + (s.seconds - rounds * each if last else 0)
            out.append(f"@@ {secs} | {name}, {block}interval {i + 1} of {rounds}{move if last else ''}")
    return out


def render_draft(sk: Skeleton) -> List[str]:
    """Only the `@@ <seconds> | <title>` markers, in order: the warm-up, then one per slot for straight
    sets and holds, one per set of each pair, one per round for rounds, one per work-and-rest interval,
    the finisher when there is one, the cool-down. Each title names the slot's default movement, with
    "each side" for a sided one (not on intervals) or "<side> side only" for a healthy-side-only one;
    the seconds add up to the skeleton's total."""
    out = [f"@@ {sk.warmup} | Warm-up"]
    work = sk.method.work
    for _, slots in sk.blocks:
        if not slots:
            continue
        if work == "rounds":
            out += _round_markers(slots, sk)
        elif work == "pairs":
            out += _pair_markers(slots, sk)
        elif work == "intervals":
            out += _interval_markers(slots, sk)
        else:
            out += [f"@@ {s.seconds} | {(n := _named(s.candidates[0][0], sk))[:1].upper() + n[1:]}" for s in slots]
    if sk.finisher:
        fd = sk.finisher_dose
        shape = f": {fd['rounds']} rounds of {fd['work_seconds']} s on, {fd['rest_seconds']} s off" if fd else ""
        out.append(f"@@ {sk.finisher} | Finisher{shape}")
    out.append(f"@@ {sk.cooldown} | Cool-down")
    return out


# ---- command line ------------------------------------------------------------------------

def _limit(text: str, cat: catalog.Catalog) -> catalog.Limit:
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


def _words(text: Optional[str]) -> List[str]:
    return [w.strip() for w in (text or "").split(",") if w.strip()]


def main():
    ap = cli.ArgumentParser(prog="sweatcast session")
    ap.add_argument("--goal", required=True, help="strength, general, targeted, conditioning, mobility or skill")
    ap.add_argument("--minutes", required=True, type=int, help="the session's length in minutes")
    kit = ap.add_mutually_exclusive_group(required=True)
    kit.add_argument("--kit", help="a kit named in the profile's [[kits]]")
    kit.add_argument("--preset", help="a kit preset from the catalog, such as hotel-room")
    kit.add_argument("--equipment", help="comma-separated equipment, as keys or aliases")
    ap.add_argument("--method", help="a method from knowledge/sessions.toml (default: chosen for you)")
    ap.add_argument("--level", help="novice, experienced or advanced (default: the profile's)")
    ap.add_argument("--target", help="comma-separated patterns or muscles to put first")
    ap.add_argument("--limit", action="append", default=[], help="area=level[:side], added to health.md's limits")
    ap.add_argument("--avoid", default="", help="comma-separated movement ids or flags to rule out")
    ap.add_argument("--draft", action="store_true", help="print only the @@ markers (health and warnings to stderr)")
    ap.add_argument("--log", help="the log to read (default: the context folder's)")
    ap.add_argument("--today", help="today's date, YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    cat = catalog.load()
    try:
        request = {"goal": args.goal, "minutes": args.minutes, "method": args.method, "level": args.level,
                   "target": _words(args.target), "limits": [_limit(x, cat) for x in args.limit],
                   "avoid": movements.avoid_set(cat, _words(args.avoid))}
        if args.kit:
            request["kit"] = args.kit
        elif args.preset:
            request["preset"] = args.preset
        else:
            request["equipment"] = movements.equipment_keys(cat, _words(args.equipment))
        today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    except ValueError as e:
        print(f"sweatcast session: {e}", file=sys.stderr)
        return cli.USAGE
    try:
        sk = compose(request, cat, sessions.load(), context.profile(), context.health(),
                     context.sessions(args.log), today)
    except ValueError as e:
        print(f"sweatcast session: {e}", file=sys.stderr)
        return cli.USAGE
    except Unfit as e:
        print(f"sweatcast session: {e}", file=sys.stderr)
        return cli.ISSUES
    if args.draft:
        for line in [f"Health: {x}" for x in sk.health] + list(sk.warnings):
            print(line, file=sys.stderr)
        print("\n".join(render_draft(sk)))
    else:
        print("\n".join(render(sk)))
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
