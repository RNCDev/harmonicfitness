"""The agent's engine tools: typed functions that run `./harmonicfitness` in one user's temporary
folder and nothing else. No tool takes a path, every argv is a list, arguments are checked before
the engine runs, and keys reach the engine only through engine.run's extra_env."""
import os
import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel

from webapp import engine, worker

LIMIT = 20_000          # what a tool's output or error may hand the model, in characters
BRIEF_LIMIT = 120_000   # the brief's output: the whole of it (a full-gym brief is about 87,000)
CUT = "[cut]"
TIMEOUT = 120
FILES = ("profile.md", "training.md", "health.md", "log.md")
_TEXT = re.compile(r"^[^\x00-\x1f\x7f-\x9f-][^\x00-\x1f\x7f-\x9f]{0,99}$")


@dataclass
class Deps:
    engine_root: str
    home: str
    keys: dict[str, str] = field(repr=False)
    today: str
    now: str
    stem: str | None = None
    plan: dict | None = None


class ToolResult(BaseModel):
    code: int
    output: str = ""
    error: str = ""


def _cut(text: str, limit: int = LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + CUT


def _result(code: int, output: str = "", error: str = "", limit: int = LIMIT) -> ToolResult:
    return ToolResult(code=code, output=_cut(output, limit), error=_cut(error))


def _refuse(message: str) -> ToolResult:
    return _result(64, error=message)


def _run(deps: Deps, argv: list[str], limit: int = LIMIT) -> ToolResult:
    r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=TIMEOUT)
    return _result(r.code, r.stdout, r.stderr, limit)


def _text(value: object) -> bool:
    """A short single-line string that can't be read as a flag."""
    return isinstance(value, str) and bool(_TEXT.match(value))


def _items(value: object) -> bool:
    return (isinstance(value, list) and len(value) <= 30
            and all(_text(v) and "," not in v for v in value))


def read_file(deps: Deps, name: Literal["profile.md", "training.md", "health.md", "log.md"]) -> ToolResult:
    if name not in FILES:
        return _refuse(f"name must be one of {', '.join(FILES)}")
    try:
        with open(os.path.join(deps.home, name), encoding="utf-8") as f:
            return _result(0, f.read())
    except FileNotFoundError:
        return _result(1, error="no such file yet")
    except (OSError, UnicodeDecodeError):
        return _result(1, error="that file can't be read")


def check(deps: Deps) -> ToolResult:
    return _run(deps, ["check"])


def get_coach(deps: Deps) -> ToolResult:
    return _run(deps, ["get", "coach"])


def get_route(deps: Deps, coach: str) -> ToolResult:
    if not _text(coach):
        return _refuse("coach must be a coach's name")
    return _run(deps, ["get", "route", "--coach", coach])


def coaches(deps: Deps) -> ToolResult:
    return _run(deps, ["coaches", "list", "--json"])


def content_plan(deps: Deps, minutes: int) -> ToolResult:
    if type(minutes) is not int or not 10 <= minutes <= 60:
        return _refuse("minutes must be a whole number from 10 to 60")
    return _run(deps, ["content", "plan", "--minutes", str(minutes), "--json"])


def coverage(deps: Deps) -> ToolResult:
    return _run(deps, ["coverage", "--json"])


def _stem(deps: Deps, goal: str, minutes: int) -> str:
    base = f"{deps.today}-{goal}-{minutes}"
    stem, n = base, 1
    while os.path.exists(os.path.join(deps.home, "workouts", stem, f"{stem}.menu.json")):
        n += 1
        stem = f"{base}-{n}"
    return stem


def brief(deps: Deps, goal: str, minutes: int, kit: str | None, preset: str | None,
          equipment: list[str] | None, coach: str, limits: list[str] = [], avoid: list[str] = [],
          target: list[str] = [], add: list[str] = []) -> ToolResult:
    # a new brief replaces the last one, even when it's refused or fails: the refused call may have carried
    # today's stricter limit, so show_plan never checks against an older menu
    deps.stem = None
    deps.plan = None
    goals, presets = worker.engine_lists(deps.engine_root)
    if goal not in goals:
        return _refuse(f"goal must be one of {', '.join(sorted(goals))}")
    if type(minutes) is not int or not 10 <= minutes <= 60:
        return _refuse("minutes must be a whole number from 10 to 60")
    if sum(x is not None for x in (kit, preset, equipment)) != 1:
        return _refuse("give exactly one of kit, preset or equipment")
    if preset is not None and preset not in presets:
        return _refuse(f"preset must be one of {', '.join(sorted(presets))}")
    if kit is not None and not _text(kit):
        return _refuse("kit must be a kit's name")
    if equipment is not None and not (equipment and _items(equipment)):
        return _refuse("equipment must be a short list of equipment names")
    if not _text(coach):
        return _refuse("coach must be a coach's name")
    for name, value in (("limits", limits), ("avoid", avoid), ("target", target), ("add", add)):
        if not (_items(value) if name != "limits" else
                isinstance(value, list) and len(value) <= 30 and all(_text(v) for v in value)):
            return _refuse(f"{name} must be a short list of plain names")
    stem = _stem(deps, goal, minutes)
    draft = os.path.join(deps.home, "workouts", stem, f"{stem}.draft.txt")
    argv = ["brief", "--goal", goal, "--minutes", str(minutes)]
    if kit is not None:
        argv += ["--kit", kit]
    elif preset is not None:
        argv += ["--preset", preset]
    else:
        argv += ["--equipment", ",".join(equipment)]
    if add:
        argv += ["--add", ",".join(add)]
    if target:
        argv += ["--target", ",".join(target)]
    for item in limits:
        argv += ["--limit", item]
    if avoid:
        argv += ["--avoid", ",".join(avoid)]
    argv += ["--coach", coach, "--today", deps.today, "--save", draft]
    result = _run(deps, argv, BRIEF_LIMIT)
    if result.code == 0:
        deps.stem = stem
    return result
