"""What the first screen's sentence is filled in with: `GET /api/start`.

    "Hey [coach], give me [25 minutes] of [strength] at [home]. Go easy on my [left knee]."

`gather` writes the listener's files to a temporary folder and runs two read-only engine commands there
(`coaches list --json`, `coverage --json`), each in its own process, so HARMONICFITNESS_HOME is never set in
this one. `shape` turns the files and those two answers into the response; it is pure (no database, no
paths) and is what the tests exercise. Nothing here opens a key: `keyed` is only which services have one.
"""
import json
import os
import re
import tempfile
import tomllib

from . import engine, folder, worker

MINUTES_DEFAULT, MINUTES_MIN, MINUTES_MAX = 25, 10, 60
READ_TIMEOUT = 60   # seconds per engine command; a cold start on the server is slower than a laptop's

# A preset's words for "...at [label]".
PRESET_LABELS = {"bodyweight": "the park", "hotel-room": "a hotel room", "hotel-gym": "a hotel gym",
                 "full-gym": "the gym"}

# Body parts a suggestion can name, in the order they're offered, and the movement patterns that train each
# (the catalog's patterns; mobility, breathing, balance, locomotion and skill name no body part).
REGIONS = (("legs", ("squat", "hinge", "lunge")), ("back", ("horizontal-pull", "vertical-pull")),
           ("chest", ("horizontal-push",)), ("shoulders", ("vertical-push",)),
           ("core", ("anti-extension", "anti-rotation", "rotation")))
REST_DAYS = 4   # with every body part trained lately, a gap this long still earns a suggestion

_UNITS = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
          "sixteen seventeen eighteen nineteen").split()
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
         "ninety": 90}


def _number(text: str) -> int | None:
    """The first number in `text`, in digits or words ("25", "twenty-five", "an hour"); None without one."""
    t = text.lower()
    m = re.search(r"\d+", t)
    if m:
        return int(m.group())
    if re.search(r"\bhalf an hour\b", t):
        return 30
    if re.search(r"\b(an|one) hour\b", t):
        return 60
    m = re.search(r"\b(" + "|".join(_TENS) + r")(?:[\s-]+(" + "|".join(_UNITS[1:10]) + r"))?\b", t)
    if m:
        return _TENS[m.group(1)] + (_UNITS.index(m.group(2)) if m.group(2) else 0)
    m = re.search(r"\b(" + "|".join(_UNITS) + r")\b", t)
    return _UNITS.index(m.group(1)) if m else None


def _text(files: dict[str, bytes], path: str) -> str:
    body = files.get(path)
    return body.decode("utf-8", errors="replace") if body else ""


def _front(fm, text: str) -> tuple[dict, str]:
    """(settings, prose) of a context file; a damaged block reads as no settings, never an error."""
    try:
        return fm.front(text)
    except Exception:   # noqa: BLE001 - a hand-edited file the engine's check reports; here it just reads empty
        return {}, text


def _minutes(fm, prose: str) -> int:
    for _, line in fm.section(prose, "Default session"):
        label, _, value = line.lstrip("-* ").partition(":")
        if label.strip().lower() in ("usual length", "length") and value.strip():
            n = _number(value)
            if n is not None:
                return max(MINUTES_MIN, min(MINUTES_MAX, n))
    return MINUTES_DEFAULT


def _kits(ctx, profile: dict, training: dict, presets) -> list[dict]:
    settings = training if "kits" in training else profile
    names = list(ctx.kits(ctx.Profile(settings, "")))
    out = [{"id": n, "label": n, "preset": False} for n in names]
    order = list(PRESET_LABELS)
    for p in sorted(presets, key=lambda p: (order.index(p) if p in order else len(order), p)):
        if p not in names:
            out.append({"id": p, "label": PRESET_LABELS.get(p, p.replace("-", " ")), "preset": True})
    return out


def _limits(health: dict) -> list[dict]:
    rows = health.get("limits")
    rows = [rows] if isinstance(rows, dict) else rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        area, side, level = row.get("area"), row.get("side", "both"), row.get("level")
        if isinstance(area, str) and area.strip() and level in ("delicate", "off-limits") \
                and side in ("left", "right", "both"):
            out.append({"area": area.strip(), "side": side, "level": level})
    return out


def _first(name: str) -> str:
    return name[len("Coach "):].strip() if name.startswith("Coach ") and len(name) > 6 else name


def _coaches(listed: list, keyed, voices_used: list[str], services: list[str]) -> list[dict]:
    """The web coaches, current first, then those whose service has a key, then the rest; within each, the
    listener's own first, then by service in services.toml's order (the order the engine takes stand-ins in).
    Current: the newest logged session's coach, if it's one of these (passed over, as the engine does, for a
    coach of their own that can speak when that one was a stand-in); else the first ready; else the first."""
    web = [c for c in listed if isinstance(c, dict) and c.get("kind") == "web"
           and isinstance(c.get("name"), str) and isinstance(c.get("slug"), str)]
    rank = {s: n for n, s in enumerate(services)}
    web.sort(key=lambda c: (bool(c.get("shipped", True)), rank.get(c.get("service"), len(rank))))
    coaches = [{"slug": c["slug"], "name": c["name"], "first": _first(c["name"]), "service": c.get("service"),
                "service_name": c.get("service_name"), "ready": c.get("service") in keyed,
                "own": not c.get("shipped", True), "current": False, "_stand_in": bool(c.get("placeholder"))}
               for c in web]
    if not coaches:
        return []

    def find(voice: str):
        v = voice.strip().casefold()
        return next((c for c in coaches if v in (c["name"].casefold(), c["slug"].casefold(),
                                                 c["first"].casefold())), None)
    current = next((c for c in map(find, reversed(voices_used)) if c is not None), None)
    if current is not None and current["_stand_in"]:
        current = next((c for c in coaches if c["own"] and not c["_stand_in"] and c["ready"]), current)
    current = current or next((c for c in coaches if c["ready"]), coaches[0])
    current["current"] = True
    ordered = [current] + [c for c in coaches if c is not current and c["ready"]] \
        + [c for c in coaches if c is not current and not c["ready"]]
    for c in ordered:
        del c["_stand_in"]
    return ordered


def _suggest(coverage: dict | None, goals) -> dict | None:
    """A body part not trained this week (or left out last time), else a gap since the last session;
    None with no log or nothing to say."""
    if not isinstance(coverage, dict) or not coverage.get("sessions"):
        return None
    week = coverage.get("week") if isinstance(coverage.get("week"), dict) else {}
    last = coverage.get("covered") if isinstance(coverage.get("covered"), dict) else {}
    if "strength" in goals:
        for part, patterns in REGIONS:
            if all(not week.get(p) for p in patterns):
                return {"goal": "strength", "target": part, "reason": f"{part}: not trained this week"}
        for part, patterns in REGIONS:
            if all(not last.get(p) for p in patterns):
                return {"goal": "strength", "target": part, "reason": f"{part}: left out last time"}
    since = coverage.get("days_since")
    if isinstance(since, int) and since >= REST_DAYS and "general" in goals:
        return {"goal": "general", "target": None, "reason": f"{since} days since your last session"}
    return None


_mods: dict[str, list] = {}


def _modules(engine_root: str) -> list:
    """The engine's frontmatter, context and sessionlog modules, imported (under worker's guard) once."""
    if engine_root not in _mods:
        _mods[engine_root] = worker._engine_modules(engine_root, "frontmatter", "context", "sessionlog")
    return _mods[engine_root]


def shape(files: dict[str, bytes], keyed, coaches: list, coverage: dict | None, *, engine_root: str,
          presets, goals, services: list[str]) -> dict:
    """The response, from the listener's files (path -> bytes), the services with a stored key, `coaches
    list --json`'s coaches and `coverage --json` (None when it didn't run); `presets`, `goals` and
    `services` are the engine's lists (worker.engine_lists, worker.engine_services)."""
    fm, ctx, slog = _modules(engine_root)
    profile, _ = _front(fm, _text(files, "profile.md"))
    training, training_prose = _front(fm, _text(files, "training.md"))
    health, _ = _front(fm, _text(files, "health.md"))
    try:
        settings = tomllib.loads(_text(files, "settings.toml"))
    except tomllib.TOMLDecodeError:
        settings = {}
    setup = settings.get("setup", profile.get("setup", "quick"))
    try:
        voices = [s.voice for s in slog.sessions(text=_text(files, "log.md"), warn=False)]
    except Exception:   # noqa: BLE001 - a log the engine can't read: no coach used last
        voices = []
    if "default session" not in training_prose.lower():   # a folder from before the profile's split
        training_prose = _front(fm, _text(files, "profile.md"))[1]
    return {
        "coaches": _coaches(coaches, frozenset(keyed), voices, list(services)),
        "kits": _kits(ctx, profile, training, presets),
        "minutes": _minutes(fm, training_prose),
        "limits": _limits(health),
        "suggest": _suggest(coverage, goals),
        "setup_quick": setup == "quick",
    }


def _json(r: engine.Result) -> dict | None:
    if r.code != 0:
        return None
    try:
        out = json.loads(r.stdout)
    except ValueError:
        return None
    return out if isinstance(out, dict) else None


def gather(engine_root: str, files: dict[str, bytes], keyed) -> dict:
    """Blocking: the listener's files (over the starter template, so the engine always sees a whole folder)
    in a temporary folder, the two engine reads, then `shape`. Neither command's output leaves here."""
    goals, presets = worker.engine_lists(engine_root)
    with tempfile.TemporaryDirectory(prefix="wt-start-") as tmp:
        home = os.path.join(tmp, "me")
        os.mkdir(home)
        folder.materialize({**folder.seed(engine_root), **files}, home)
        listed = _json(engine.run(engine_root, home, ["coaches", "list", "--json"], timeout=READ_TIMEOUT))
        coverage = _json(engine.run(engine_root, home, ["coverage", "--json"], timeout=READ_TIMEOUT))
    coaches = listed.get("coaches") if listed else None
    return shape(files, keyed, coaches if isinstance(coaches, list) else [], coverage,
                 engine_root=engine_root, presets=presets, goals=goals,
                 services=list(worker.engine_services(engine_root)))
