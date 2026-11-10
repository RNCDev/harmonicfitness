"""The engine's own modules and lists, for the web process and the worker alike.

Before importing any engine module (for the session goals and kit presets) this points HARMONICFITNESS_HOME at a
folder that doesn't exist, so the engine's libraries never find a real `me/`.
"""
import importlib
import os
import sys
import tempfile
import uuid

_lists: dict[str, tuple[frozenset, frozenset]] = {}


def _no_home() -> str:
    while True:
        path = os.path.join(tempfile.gettempdir(), f"wt-no-context-{uuid.uuid4().hex}")
        if not os.path.exists(path):
            return path


def modules(engine_root: str, *names: str) -> list:
    """The named engine modules, imported with HARMONICFITNESS_HOME pointed at a folder that doesn't exist,
    `tools/` appended last on sys.path, and each module's origin checked to be inside the engine."""
    home = os.environ.get("HARMONICFITNESS_HOME", "")
    if not home or os.path.exists(home):
        os.environ["HARMONICFITNESS_HOME"] = _no_home()
    tools = os.path.abspath(os.path.join(engine_root, "tools"))
    if tools not in sys.path:
        sys.path.append(tools)   # after everything else, so no engine module shadows another
    before = list(sys.path)
    try:
        mods = [importlib.import_module(n) for n in names]
    finally:
        sys.path[:] = before   # some engine modules (keys) put tools/ first on import: undo that
    for mod in mods:
        where = os.path.abspath(mod.__file__)
        if os.path.dirname(where) != tools and os.path.dirname(os.path.dirname(where)) != tools:
            raise RuntimeError(f"{mod.__name__} was imported from outside the engine")
    return mods


def lists(engine_root: str) -> tuple[frozenset, frozenset]:
    """(session goals, kit presets) from the engine's tools/sessions.py and tools/catalog.py."""
    if engine_root not in _lists:
        catalog, sessions = modules(engine_root, "catalog", "sessions")
        _lists[engine_root] = (frozenset(sessions.load().goals),
                               frozenset(catalog.load(extra=[]).presets))
    return _lists[engine_root]


_services: dict[str, dict[str, dict]] = {}


def services(engine_root: str) -> dict[str, dict]:
    """{service: {"name", "key_var", "key_page", "billing_page", "reports"}} from knowledge/services.toml, in its
    order; `reports`: whether the service's module can say what's left on the account (balance())."""
    if engine_root not in _services:
        services_mod, = modules(engine_root, "services")
        table = services_mod.settings()
        mods = modules(engine_root, *(f"services.{k}" for k in table))
        _services[engine_root] = {k: {**{f: v[f] for f in ("name", "key_var", "key_page", "billing_page")},
                                      "reports": hasattr(m, "balance")}
                                  for (k, v), m in zip(table.items(), mods)}
    return _services[engine_root]


def keys(engine_root: str):
    """The engine's keys module (imported under the guard)."""
    return modules(engine_root, "keys")[0]


def clean_key(engine_root: str, var: str, value: str) -> str | None:
    """The engine's keys.clean_value (stripped); None when it refuses the value as a key (BadKey).
    Anything else it raises is a bug and propagates."""
    keys_mod = keys(engine_root)
    try:
        return keys_mod.clean_value(var, value)
    except keys_mod.BadKey:
        return None
