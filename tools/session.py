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

Time the slots do not use goes to a second pass through the patterns (once every dose is at its
ceiling), then to rests between slots (up to thirty seconds each), then to the cool-down and warm-up
up to their ceilings, and the rest to the cool-down with a warning past a tenth of the request.
A request too short for every slot drops slots, never squeezes the total.
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
CYCLING = ("holds", "intervals")   # work kinds whose patterns repeat to fill the block
CYCLE_CAP = 12       # most slots a cycling block holds
SPARE_WARNING = 0.10   # spare beyond this share of the request, after everything else, is warned about
STEP = {"sets": 1, "rounds": 1, "reps": 1, "rest_seconds": 15}   # other keys (seconds of work) step by 5
LIMIT_SIDES = ("left", "right", "both")
LIMIT_LEVELS = ("off-limits", "delicate")
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


# ---- timing ------------------------------------------------------------------------------

def _work_each(m: catalog.Movement, dose: dict) -> int:
    """Seconds of work in one set or hold of `m` at `dose`."""
    if m.measure == "reps" and "reps" in dose:
        return dose["reps"] * m.seconds_per_rep
    for key in ("hold_seconds", "drill_seconds", "work_seconds"):
        if key in dose:
            return dose[key]
    return m.hold_seconds


def _work_time(m: catalog.Movement, dose: dict) -> int:
    """Seconds of work in one set or hold of `m`, both sides of a sided movement."""
    return _work_each(m, dose) * (2 if m.sided else 1)


def slot_seconds(m: catalog.Movement, dose: dict, work: str) -> int:
    """Seconds one movement takes at `dose` for the method's kind of work.

    sets: transition, every set, a rest between sets. pairs: the same with half of the pair's rests,
    since one rest follows each pass through the pair. rounds: one transition and one set per round
    (the rests between rounds belong to the block, see block_seconds). intervals: rounds of work
    and rest. holds: rounds of holds after one transition. A sided movement's work covers both sides,
    then one rest; an interval's work is the dose's work seconds, whichever side."""
    w, t = _work_time(m, dose), m.transition_seconds
    rest = dose.get("rest_seconds", 0)
    if work == "sets":
        return t + dose["sets"] * w + (dose["sets"] - 1) * rest
    if work == "pairs":
        return t + dose["sets"] * w + (dose["sets"] - 1) * rest // 2
    if work == "rounds":
        return dose["rounds"] * (t + w)
    if work == "intervals":
        return dose["rounds"] * (dose["work_seconds"] + rest)
    if work == "holds":
        return dose["rounds"] * w + t
    raise ValueError(f"unknown work \"{work}\" (choose from: {', '.join(sessions.WORK)})")


def block_seconds(ms: List[catalog.Movement], dose: dict, work: str) -> List[int]:
    """Each slot's seconds in a block of movements in order, so the block's rests land in its slots:
    the odd second of a pair's rests goes to its second slot, a lone last slot of `pairs` takes all its
    rests, and the rests between rounds are shared evenly (the remainder on the last slot)."""
    out = [slot_seconds(m, dose, work) for m in ms]
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

def _ranges(sess: sessions.Sessions, method: sessions.Method, intensity: str, level: str) -> Dict[str, list]:
    """{dose key: [least, most]} for one block: the method's fixed shape, or the intensity's dose table
    for the level (breathing has none and uses mobility's; circuit rounds come from strength sets)."""
    if method.fixed:
        return {k: [v, v] for k, v in method.fixed.items()}
    table = sessions.dose(sess, intensity if intensity in sess.dose else "mobility", level)
    if intensity != "strength":
        return {k: list(v) for k, v in table.items()}
    return {("rounds" if method.work == "rounds" else "sets"): list(table["sets"]),
            "reps": list(table["reps"]), "rest_seconds": list(table["rest_seconds"])}


def _raise_order(ranges: Dict[str, list]) -> List[str]:
    """Count first (sets or rounds), then the work (reps or seconds), then rest."""
    count = [k for k in ("sets", "rounds") if k in ranges]
    rest = [k for k in ("rest_seconds",) if k in ranges]
    return count + [k for k in ranges if k not in count + rest] + rest


def _fit(movers: List[catalog.Movement], ranges: Dict[str, list], work: str, budget: int,
         least_slots: int, fixed: bool, what: str, first: int) -> Tuple[int, dict]:
    """(slots, dose) for one block: grow the slot count at the floor dose while the next slot fits, up to
    `first` slots (variety before volume), then raise the dose toward its ceilings while the block still
    fits. When every slot of the first pass and every ceiling are reached, slots past `first` (a second
    pass through the patterns) are added while they fit."""
    dose = {k: v[0] for k, v in ranges.items()}
    cost = lambda n, d: sum(block_seconds(movers[:n], d, work))  # noqa: E731
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
        for key in _raise_order(ranges):
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


def _pair_up(entries: list) -> list:
    """Slots in paired order: each next unpaired slot with the first later one of another family,
    else with the next one."""
    left, out = list(entries), []
    while left:
        a = left.pop(0)
        out.append(a)
        if left:
            j = next((i for i, e in enumerate(left) if family(e[0]) != family(a[0])), 0)
            out.append(left.pop(j))
    return out


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


def _order(cat: catalog.Catalog, patterns: List[str], targets: List[str], week: Dict[str, int],
           leads) -> List[str]:
    """Targets first (a muscle picks the patterns whose movements list it first), then the patterns the
    week has not trained, then the rest, each in the method's order."""
    wanted: List[str] = []
    for t in targets:
        if t in cat.patterns:
            wanted.append(t)
        else:
            wanted += [p for p in patterns if t in leads(p)] or [p for p in cat.patterns if t in leads(p)]
    wanted = list(dict.fromkeys(wanted))
    rest = [p for p in patterns if p not in wanted]
    return wanted + [p for p in rest if week.get(p, 0) == 0] + [p for p in rest if week.get(p, 0)]


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
        level = "experienced"
        warnings.append("no experience level in the profile; assuming experienced")
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
    own = context.limits(health, cat.areas)
    rows = health.settings.get("limits") or []
    if len(rows if isinstance(rows, list) else [rows]) > len(own):   # a dropped row protects nothing
        raise Unfit("health.md: a [[limits]] row was ignored (run ./sweatcast check)")
    if context.prose_injuries(health) and not own:
        warnings.append("health.md lists injuries in prose but has no [[limits]] rows, so no limit is "
                        "applied for them; add a row for each")
    limits = own + list(request.get("limits") or [])
    likes, dislikes = _ids(cat, context.likes(profile)), _ids(cat, context.dislikes(profile))
    avoid = set(request.get("avoid") or ())
    try:
        sel = catalog.select(cat, equipment, level, limits, avoid=avoid, dislikes=dislikes)
    except ValueError as e:   # request limits are checked above, so this is a row in health.md
        raise Unfit(f"{paths.show(health.path or paths.HEALTH)}: {e}; fix the [[limits]] row")

    last = log[-1] if log else None
    last_format = last.format if last else None
    env = {"minutes": minutes, "sess": sess, "cat": cat, "request": request, "level": level, "log": log,
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
    for i, method in enumerate(ranked):   # the next method when one cannot fill its slots today
        try:
            return _build(method, why if i == 0 else f"{first.name} did not fit", env)
        except Unfit as e:
            if i == 0:
                failed = e
    raise failed


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
    rank = lambda m: (m.id in last_ids, m.id not in likes, closeness(m), limited(m), order[m.id])  # noqa: E731
    ctx = {"likes": likes, "last": last_ids if last else None, "healthy": healthy, "areas": areas,
           "week": week, "rehab": {i for lim in limits for i in lim.rehab}}
    leads = lambda p: {m.muscles[0] for m in pool if m.muscles and p in m.patterns}  # noqa: E731

    blocks: List[Tuple[str, List[Slot]]] = []
    dropped: List[str] = []
    used: Set[str] = set()
    spent = 0
    for b, block in enumerate(method.blocks):
        budget = main - spent if b == len(method.blocks) - 1 else round(main * block["share"])
        pats = _order(cat, block["patterns"], (request.get("target") or []) if b == 0 else [], week, leads)
        filled = []
        for p in pats:
            ms = _candidates(p, pool, rank, used)
            if ms:
                filled.append((p, ms))
                used.add(ms[0].id)
        least = method.min_slots if len(method.blocks) == 1 else 1
        if len(filled) < least and len(method.blocks) > 1:
            raise Unfit(f"no movement fits the {block['intensity']} block of {method.name} "
                        "with today's kit, level and limits")
        if len(filled) < least:
            raise Unfit(f"only {len(filled)} of the {least} movement slots {method.name} needs have a "
                        "movement that fits today's kit, level and limits")
        if method.work in CYCLING:   # one pattern may fill several slots, each with the next movement first
            first = CYCLE_CAP
            entries = [(p, _rotate(ms, i // len(filled))) for i in range(first)
                       for p, ms in [filled[i % len(filled)]]]
        else:                        # a second pass through the patterns, only once the first is full
            first = len(filled)
            entries = filled + [(p, _rotate(ms, 1)) for p, ms in filled]
        n, dose = _fit([ms[0] for _, ms in entries], _ranges(sess, method, block["intensity"], level),
                       method.work, budget, least, bool(method.fixed), f"a {minutes} minute session", first)
        chosen = _pair_up(entries[:n]) if method.work == "pairs" else entries[:n]
        secs = block_seconds([ms[0] for _, ms in chosen], dose, method.work)
        slots = [Slot(p, block["intensity"], dict(dose), s, [(m, _reasons(m, ms, p, ctx)) for m in ms])
                 for (p, ms), s in zip(chosen, secs)]
        dropped += [p for p, _ in filled if p not in {s.pattern for s in slots}]
        spent += sum(secs)
        blocks.append((block["intensity"], slots))
    count = sum(len(slots) for _, slots in blocks)
    if count < method.min_slots:
        raise Unfit(f"only {count} of the {method.min_slots} movement slots {method.name} needs fit today")

    spare = main - spent
    flat = [(bi, si) for bi, (_, slots) in enumerate(blocks) for si in range(len(slots))
            if method.work != "pairs" or si % 2 == 1 or si == len(slots) - 1]   # pairs rest only between pairs
    for bi, si in flat[:-1]:
        extra = min(BETWEEN_SLOTS, spare)
        if extra <= 0:
            break
        slot = blocks[bi][1][si]
        blocks[bi][1][si] = slot._replace(seconds=slot.seconds + extra)
        spare -= extra
    for part, name in ((method.cooldown, "cooldown"), (method.warmup, "warmup")):
        extra = max(0, min(spare, part["seconds"][1] - (cooldown if name == "cooldown" else warmup)))
        cooldown, warmup = (cooldown + extra, warmup) if name == "cooldown" else (cooldown, warmup + extra)
        spare -= extra
    if spare > SPARE_WARNING * total:
        warnings.append(f"method filled early: {spare} s spare went to the cool-down")
    cooldown += spare

    today_lines = [f"today: {lim.area} {lim.level}" + (f" {lim.side}" if lim.side != "both" else "")
                   for lim in request.get("limits") or []]
    return Skeleton(method, minutes, warmup, blocks, finisher, cooldown, dropped, warnings,
                    _would_open(cat, sel, equipment, level, limits, avoid, dislikes),
                    tuple(context.clinician_lines(health, cat.areas)) + tuple(today_lines), why,
                    {m.id: _healthy_side(m, limits) for m in sel.healthy_side_only})


def _healthy_side(m: catalog.Movement, limits: List[catalog.Limit]) -> str:
    """The side a healthy-side-only movement works: the one opposite the sided limit that loads it."""
    for lim in limits:
        if lim.side in OTHER_SIDE and m.id not in lim.rehab and m.loads.get(lim.area, 0) >= catalog.threshold(lim):
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


def _named(m: catalog.Movement, sk: Skeleton) -> str:
    """A movement's name with its side words, for a draft title."""
    words = _side_words(m, sk)
    return f"{m.name} {words}" if words else m.name


def _dose_text(slot: Slot, sk: Skeleton) -> str:
    d, m, work = slot.dose, slot.candidates[0][0], sk.method.work
    if work == "intervals":
        return f"{d['rounds']} rounds of {d['work_seconds']} s on, {d.get('rest_seconds', 0)} s off"
    count, label = (d["sets"], "sets") if "sets" in d else (d.get("rounds", 1), "rounds")
    each = str(d["reps"]) if m.measure == "reps" and "reps" in d else f"{_work_each(m, d)} s"
    text = f"{count} {label} of {each}" + (f" ({_side_words(m, sk)})" if _side_words(m, sk) else "")
    return text + (f", rest {d['rest_seconds']} s" if d.get("rest_seconds") else "")


def _total(sk: Skeleton) -> int:
    return sk.warmup + sum(s.seconds for _, slots in sk.blocks for s in slots) + sk.finisher + sk.cooldown


def render(sk: Skeleton) -> List[str]:
    """The skeleton as lines: health rules, warnings, the method, then the timing and each slot's
    pattern, dose and top three movements with the reasons they rank there."""
    out = [f"Health: {line}" for line in sk.health] + list(sk.warnings)
    out.append(f"Method: {sk.method.name}, because {sk.why}. {sk.method.about}")
    out.append(f"Warm-up: {sk.warmup} s")
    for intensity, slots in sk.blocks:
        out.append(f"{intensity} block, {sum(s.seconds for s in slots)} s:")
        for s in slots:
            picks = "; ".join(f"{m.id} [{why}]" if why else m.id for m, why in s.candidates[:3])
            out.append(f"  {s.pattern} ({_dose_text(s, sk)}, {s.seconds} s): {picks}")
    if sk.finisher:
        out.append(f"Finisher: {sk.finisher} s")
    out.append(f"Cool-down: {sk.cooldown} s")
    out.append(f"Total: {_total(sk)} s of {sk.minutes * 60} s")
    if sk.dropped:
        out.append(f"Dropped: {', '.join(sk.dropped)} (no time left for them)")
    if sk.would_open:
        out.append("Would open up: " + ", ".join(f"{e} (+{n})" for e, n in sk.would_open))
    return out


def _round_markers(slots: List[Slot], sk: Skeleton) -> List[str]:
    """One marker per round of a `rounds` block; the rests and spare go to the rounds before the last."""
    rounds = slots[0].dose.get("rounds", 1)
    base = sum(s.candidates[0][0].transition_seconds + _work_time(s.candidates[0][0], s.dose) for s in slots)
    extra = sum(s.seconds for s in slots) - rounds * base
    names = ", ".join(_named(s.candidates[0][0], sk) for s in slots)
    out = []
    for i in range(rounds):
        secs = base
        if rounds > 1 and i < rounds - 1:
            secs += extra // (rounds - 1) + (extra % (rounds - 1) if i == rounds - 2 else 0)
        elif rounds == 1:
            secs += extra
        out.append(f"@@ {secs} | Round {i + 1} of {rounds}: {names}")
    return out


def render_draft(sk: Skeleton) -> List[str]:
    """Only the `@@ <seconds> | <title>` markers, in order: the warm-up, one per slot (one per round for
    rounds, one per work-and-rest pair for intervals), the finisher when there is one, the cool-down.
    Each title names the slot's default movement, with "each side" for a sided one or "<side> side only"
    for a healthy-side-only one (not on intervals); the seconds add up to the skeleton's total."""
    out = [f"@@ {sk.warmup} | Warm-up"]
    work = sk.method.work
    for _, slots in sk.blocks:
        if work == "rounds" and slots:
            out += _round_markers(slots, sk)
            continue
        for s in slots:
            name = s.candidates[0][0].name
            if work != "intervals":   # an interval's work is the same seconds whichever side
                name = _named(s.candidates[0][0], sk)
            if work == "intervals":
                rounds, each = s.dose["rounds"], s.dose["work_seconds"] + s.dose.get("rest_seconds", 0)
                out += [f"@@ {each + (s.seconds - rounds * each if i == rounds - 1 else 0)} | "
                        f"{name}, interval {i + 1} of {rounds}" for i in range(rounds)]
            else:
                out.append(f"@@ {s.seconds} | {name[:1].upper() + name[1:]}")
    if sk.finisher:
        out.append(f"@@ {sk.finisher} | Finisher")
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
    return catalog.Limit(area, side, level, [], [], "")


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
