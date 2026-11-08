"""What an injury limit means for a session, the check-in and after it clears: knowledge/limits.toml.

`load` reads the file, `problems` checks it against the catalog (every area, both levels, every required
field), one plain sentence per fault. `session_lines` is what the brief quotes for a limit, `check_in_lines`
what `./harmonicfitness get limits` prints for the check-in, `after_clearing` what carries on once a limit
clears, and `red_flags` the signs that stop a session before it starts. The evidence behind every line is in
knowledge/injury-playbook.md. Library only; the command line lives elsewhere.
"""
import datetime
import functools
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import catalog
import errors
import paths

FORMAT = 1
LEVEL_KEYS = ("opening", "session", "stop", "stop_today", "say", "say_when")
CHECK_IN_KEYS = ("delicate", "clear")


@dataclass
class Level:
    session: str
    stop: List[str]
    say: str = ""
    opening: str = ""
    say_when: str = ""
    stop_today: List[str] = field(default_factory=list)


@dataclass
class Area:
    levels: Dict[str, Level]
    check_in: Dict[str, str]
    after_weeks: int = 0
    after_plan: str = ""
    after_say: str = ""
    red_flags: List[str] = field(default_factory=list)
    emergency: List[str] = field(default_factory=list)
    heart_rule: str = ""   # emergency signs that can start mid-session: spoken with the heart rule


@dataclass
class Playbook:
    format: int
    check_in: str
    red_flags: List[str]
    unlisted: str
    areas: Dict[str, Area]
    raw: dict = field(default_factory=dict, repr=False)
    emergency: List[str] = field(default_factory=list)
    unlisted_session: str = ""


def _strings(value) -> List[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _area(raw: dict) -> Area:
    levels = {lv: Level(str(t.get("session", "")), _strings(t.get("stop")), str(t.get("say", "")),
                        str(t.get("opening", "")), str(t.get("say_when", "")), _strings(t.get("stop_today")))
              for lv, t in raw.items() if lv in catalog.LIMIT_LEVELS and isinstance(t, dict)}
    after = raw.get("after_clearing") if isinstance(raw.get("after_clearing"), dict) else {}
    weeks = after.get("weeks", 0)
    return Area(levels=levels, check_in={k: str(v) for k, v in (raw.get("check_in") or {}).items()},
                after_weeks=weeks if isinstance(weeks, int) and not isinstance(weeks, bool) else 0,
                after_plan=str(after.get("plan", "")), after_say=str(after.get("say", "")),
                red_flags=_strings(raw.get("red_flags")),
                emergency=_strings(raw.get("emergency")), heart_rule=str(raw.get("heart_rule", "")))


def load(path: Optional[str] = None) -> Playbook:
    """Read the limits file at `path` (default: the shipped one)."""
    path = path or paths.LIMITS
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:   # the file's fault (exit 1), never the command's
            raise errors.ContextError(f"{paths.show(path)} isn't valid TOML: {e}") from e
    general = data.get("general") if isinstance(data.get("general"), dict) else {}
    return Playbook(
        format=data.get("format", 0), check_in=str(general.get("check_in", "")),
        red_flags=_strings(general.get("red_flags")), unlisted=str(general.get("unlisted", "")),
        areas={name: _area(raw) for name, raw in data.items() if name not in ("format", "general")
               and isinstance(raw, dict)},
        raw=data, emergency=_strings(general.get("emergency")),
        unlisted_session=str(general.get("unlisted_session", "")))


@functools.lru_cache(maxsize=1)
def shipped() -> Playbook:
    """The shipped file, read once."""
    return load()


def problems(pb: Playbook, areas: List[str]) -> List[str]:
    """What's wrong with the file against the catalog's areas, one sentence each (empty when it's sound)."""
    out = []
    if pb.format != FORMAT:
        out.append(f"format is {pb.format}, expected {FORMAT}")
    if not pb.check_in:
        out.append("[general] needs check_in")
    if not pb.red_flags:
        out.append("[general] needs red_flags")
    if not pb.unlisted:
        out.append("[general] needs unlisted")
    if not pb.emergency:
        out.append("[general] needs emergency")
    if not pb.unlisted_session:
        out.append("[general] needs unlisted_session")
    for name in pb.areas:
        if name not in areas:
            out.append(f"[{name}] isn't one of the catalog's areas")
    for name in areas:
        raw = pb.raw.get(name)
        if not isinstance(raw, dict):
            out.append(f"[{name}] is missing")
            continue
        for key in raw:
            if key not in (*catalog.LIMIT_LEVELS, "check_in", "after_clearing", "red_flags", "emergency",
                           "heart_rule"):
                out.append(f"[{name}] has a key nothing reads: {key}")
        for level in catalog.LIMIT_LEVELS:
            table = raw.get(level)
            if not isinstance(table, dict):
                out.append(f"[{name}.{level}] is missing")
                continue
            for key in table:
                if key not in LEVEL_KEYS:
                    out.append(f"[{name}.{level}] has a key nothing reads: {key}")
            for key in ("opening", "session"):
                if not str(table.get(key, "")).strip():
                    out.append(f"[{name}.{level}] needs {key}")
            if table.get("say_when") and not table.get("say"):
                out.append(f"[{name}.{level}] has say_when but no say")
            stop = table.get("stop")
            if not (isinstance(stop, list) and stop and all(isinstance(s, str) and s.strip() for s in stop)):
                out.append(f"[{name}.{level}] needs stop: a list of one or more signs")
            today = table.get("stop_today")
            if today is not None and not (isinstance(today, list) and today
                                          and all(isinstance(s, str) and s.strip() for s in today)):
                out.append(f"[{name}.{level}] stop_today must be a list of one or more signs")
        check = raw.get("check_in")
        if not isinstance(check, dict) or any(not str(check.get(k, "")).strip() for k in CHECK_IN_KEYS) \
                or any(k not in CHECK_IN_KEYS for k in check):
            out.append(f"[{name}.check_in] needs delicate and clear, and nothing else")
        after = raw.get("after_clearing")
        if after is not None:
            weeks = after.get("weeks") if isinstance(after, dict) else None
            if not (isinstance(weeks, int) and not isinstance(weeks, bool) and weeks > 0
                    and str(after.get("plan", "")).strip()):
                out.append(f"[{name}.after_clearing] needs weeks (a whole number above 0) and plan")
            elif any(k not in ("weeks", "plan", "say") for k in after):
                out.append(f"[{name}.after_clearing] takes only weeks, plan and say")
        for key in ("red_flags", "emergency"):
            if key in raw and not (isinstance(raw[key], list) and raw[key]
                                   and all(isinstance(s, str) and s.strip() for s in raw[key])):
                out.append(f"[{name}] {key} must be a list of one or more signs")
    return out


def _sided(text: str, level: str, side: str) -> str:
    """A line with its {side} filled in, as the limit cues fill theirs (catalog.limit_cues)."""
    word = side if side in ("left", "right") else catalog.BOTH_SIDES.get(level, "injured")
    return text.replace(catalog.SIDE_SLOT, word)


def session_lines(pb: Playbook, area: str, level: str, side: str = "both") -> List[str]:
    """What the writer gets for one limit, as Markdown bullets: the opening's spoken line, today's work, the
    signs that end a movement and those that end the session, and a reason to say."""
    a = pb.areas.get(area)
    lv = a.levels.get(level) if a else None
    if not lv:
        return []
    out = []
    if lv.opening:
        out.append(f"  - Opening (say it in the opening, in your words, keeping its side and body part): "
                   f"\"{_sided(lv.opening, level, side)}\"")
    out.append(f"  - Today, for you: {_sided(lv.session, level, side)}")
    if lv.stop:
        out.append(f"  - Stop that movement on: {_sided('; '.join(lv.stop), level, side)}.")
    if lv.stop_today:
        out.append(f"  - Stop for today on: {_sided('; '.join(lv.stop_today), level, side)}.")
    if lv.say:
        when = f", when {lv.say_when}" if lv.say_when else ""
        out.append(f"  - Say{when}: \"{_sided(lv.say, level, side)}\"")
    if a.heart_rule:
        out.append(f"  - Heart rule, add (said with it in the full rules and the short ones alike: stop the whole "
                   f"session and get help now): {a.heart_rule}.")
    return out


def check_in_lines(pb: Playbook, area: str, level: str) -> List[str]:
    """The check-in's signs for one limit: what loosens it one step from where it stands."""
    a = pb.areas.get(area)
    if not a:
        return []
    if level == "off-limits":
        return [f"delicate once {a.check_in.get('delicate', '')}"]
    return [f"clear once {a.check_in.get('clear', '')}"]


def _flags(general: List[str], pb: Playbook, areas, attr: str) -> List[str]:
    out = list(general)
    for name in dict.fromkeys(areas):
        a = pb.areas.get(name)
        out += [f for f in (getattr(a, attr) if a else []) if f not in out]
    return out


def red_flags(pb: Playbook, areas: List[str] = ()) -> List[str]:
    """The red flags that stop a session and send the listener to a clinician soon: the general ones, then
    each named area's own."""
    return _flags(pb.red_flags, pb, areas, "red_flags")


def emergencies(pb: Playbook, areas: List[str] = ()) -> List[str]:
    """The signs that mean calling emergency services now, not waiting for a clinic: the general ones, then
    each named area's own."""
    return _flags(pb.emergency, pb, areas, "emergency")


def flag_lines(pb: Playbook, areas: List[str] = ()) -> List[str]:
    """The red flags and the emergencies, as the two lines the brief and `get limits` end with."""
    return ["Red flags, for the check-in, in chat (they stop the session before it starts, and suggest a "
            "clinician soon; the audio carries the opening's stop rule and heart rule instead): "
            + "; ".join(red_flags(pb, areas)) + ".",
            "Emergencies, for the check-in, in chat (stop, and call emergency services now): "
            + "; ".join(emergencies(pb, areas)) + "."]


def after_clearing(pb: Playbook, area: str, cleared: datetime.date,
                   today: datetime.date) -> Optional[tuple]:
    """(plan, until, say) while a limit cleared on `cleared` still carries a rule on `today`, else None."""
    a = pb.areas.get(area)
    if not a or not a.after_weeks or not a.after_plan:
        return None
    until = cleared + datetime.timedelta(weeks=a.after_weeks)
    return (a.after_plan, until, a.after_say) if cleared <= today < until else None
