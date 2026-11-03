"""The listener's level in Settings (`GET /api/level`, `PUT /api/level`): novice, experienced or advanced, picked by
the sentence that fits them. It sets the movements, the doses and how much the coach explains.

Reading is in-process, from the engine's own modules (as start.py reads the files); a change runs the engine's
`set experience` in a temporary folder, as the Logs page's calls do (workouts._run), and comes back as the files it
changed, for the caller to write back. With none set the engine plans as a novice, so that's what shows."""
import tomllib

from . import worker
from .workouts import Refused, _ok, _run


def parts(engine_root: str) -> tuple[str, ...]:
    """The files `current` reads (the profile's four), so a caller can fetch only those."""
    ctx, = worker._engine_modules(engine_root, "context")
    return tuple(ctx.PROFILE_PARTS)


def current(engine_root: str, files: dict[str, bytes]) -> dict:
    """{"level", "set", "choices": [{"level", "said"}]}: the level the engine reads (its home file first), else
    novice with "set" false."""
    fm, ctx, catalog = worker._engine_modules(engine_root, "frontmatter", "context", "catalog")
    found = None
    for part in ctx.PROFILE_PARTS:   # profile.md, its home, first: the home file wins
        text = (files.get(part) or b"").decode("utf-8", errors="replace")
        if not text:
            continue
        try:
            settings = tomllib.loads(text) if part.endswith(".toml") else fm.front(text)[0]
        except Exception:   # noqa: BLE001 - a damaged file `check` reports; here it just has no level
            continue
        found = ctx.experience(ctx.Profile(settings, ""))
        if found:
            break
    return {"level": found or "novice", "set": found is not None,
            "choices": [{"level": lv, "said": catalog.LEVEL_SAID[lv]} for lv in catalog.LEVELS]}


def choose(engine_root: str, files: dict[str, bytes], level: str) -> dict[str, bytes | None]:
    """The files `set experience <level>` changed (profile.md)."""
    result, changed = _run(engine_root, files, ["set", "experience", level])
    _ok(result)
    if not changed:
        raise Refused("The level couldn't be saved.")
    return changed
