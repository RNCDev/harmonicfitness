"""Shared helpers for the tests: keeping them off the real me/, and pointing every path at a temp folder."""
import contextlib
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import ffmpeg  # noqa: E402
import paths  # noqa: E402

# the ffmpeg the tools would use (the system's, else the environment's own copy): tests that encode skip without one
HAS_FFMPEG = ffmpeg.exe() is not None


def assert_isolated(home):
    """Stop when `home` is a real context folder (holds a profile): the tests must never read or write
    one. ./harmonicfitness test points HARMONICFITNESS_HOME at an absent folder, as CI has no me/."""
    if os.path.exists(os.path.join(home, "profile.md")):
        raise SystemExit(f"The tests would run over a real context folder, {home}. Run them with "
                         "./harmonicfitness test (which sets HARMONICFITNESS_HOME to an absent folder), or set HARMONICFITNESS_HOME.")


@contextlib.contextmanager
def home(root):
    """Every paths.* value under the context folder, pointed under `root` for the block: HOME itself and
    each file and folder derived from it. The engine's own paths (ROOT, knowledge, the template) stay."""
    old = paths.HOME
    root = os.path.abspath(root)
    with contextlib.ExitStack() as stack:
        for name, value in list(vars(paths).items()):
            if name.startswith("_") or not isinstance(value, str):
                continue
            if value == old:
                stack.enter_context(mock.patch.object(paths, name, root))
            elif value.startswith(old + os.sep):
                stack.enter_context(mock.patch.object(paths, name, os.path.join(root, os.path.relpath(value, old))))
        yield root


def menu_for(draft_path, home, today=None, health_sha256=None):
    """Write today's menu beside `draft_path`, holding every movement the draft declares or names, as if
    ./harmonicfitness brief --save had made it from `home`'s health.md."""
    import datetime
    import catalog
    import draft
    import menu
    cat = catalog.load()
    with open(draft_path, encoding="utf-8") as f:
        text = f.read()
    segments = draft.parse(text)
    ids = {m.id for m in (catalog.resolve(cat, w) for w in draft.declared(text)) if m}
    ids |= {mid for mid, _, _ in menu.mentions(cat, menu.spoken_text(segments))}
    rec = {"format": menu.FORMAT, "date": today or datetime.date.today().isoformat(),
           "health_sha256": health_sha256 or menu.health_hash(os.path.join(home, "health.md")),
           # a request the build's re-screen accepts: every piece of equipment, any level (health.md's
           # limits and the profile's dislikes still apply, as they would to a real brief)
           "request": {"goal": "general", "minutes": max(1, sum(seg["seconds"] for seg in segments) // 60),
                       "equipment": sorted(cat.equipment), "level": "advanced"},
           "seconds": sum(seg["seconds"] for seg in segments),
           "movements": [{"id": i, "name": cat.movements[i].name, "aliases": cat.movements[i].aliases} for i in sorted(ids)]}
    menu.write(draft.menu_path(draft_path), rec)
    return draft.menu_path(draft_path)


def draft_with_menu(src, dst, home):
    """Copy the draft at `src` to `dst`, giving it a movements: line (the fixtures predate the menu) and
    today's menu beside it. Returns `dst`."""
    import catalog
    import draft
    import menu
    with open(src, encoding="utf-8") as f:
        text = f.read()
    if not draft.declared(text):
        cat = catalog.load()
        names = sorted({cat.movements[mid].name for mid, _, _ in menu.mentions(cat, menu.spoken_text(draft.parse(text)))})
        text = "movements: " + ", ".join(names) + "\n" + text
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    menu_for(dst, home)
    return dst
