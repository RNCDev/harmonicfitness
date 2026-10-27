"""One module per web voice service (fish, elevenlabs, gemini, inworld), each with design(description, line,
n, label) -> candidates, save(candidate, name, description, wav) -> voice ID, delete(voice_id) -> bool, and
speaker(voice) -> say(text, seed, previous_text=None, next_text=None) returning 16-bit mono PCM at 24 kHz,
spoken by the web coach's saved voice ID, in that argument order (tests/test_cloud.py holds every module to it).
Optional: STORES_DRAFTS = True where design() saves each candidate at the service, so one not kept is deleted;
DESIGN_NOTE, what else a design costs there, said with its price. cloud.service_module(name) is the one lookup.
The shared core (HTTP, retries, errors, audio, cost) is tools/cloud.py; settings are knowledge/services.toml,
read by settings() here (each table checked by validate()), which imports nothing of the engine's, so keys.py
can read it without cloud.py."""
import functools
import os
import tomllib

import errors   # tools/ is on the path wherever this package is imported; errors imports nothing

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "knowledge", "services.toml")


class SettingsError(ValueError):
    """knowledge/services.toml holds a table the engine can't use: a damaged or mistyped file, named with what's
    wrong rather than failing later as a KeyError. Exits 1 through cli.run (errors.ISSUES)."""
    exit_code = errors.ISSUES


@functools.cache
def settings():
    """{service: settings} from knowledge/services.toml, in its order, each with the file's rates_checked.
    A table that fails validate() raises SettingsError."""
    with open(SETTINGS_FILE, "rb") as f:
        data = tomllib.load(f)
    found = {k: dict(v, rates_checked=data.get("rates_checked")) for k, v in data.items() if isinstance(v, dict)}
    problems = validate(found)
    if problems:
        raise SettingsError(f"{SETTINGS_FILE}: " + "; ".join(problems))
    return found


def names():
    """The web services, in services.toml's order (cloud.SERVICES is this tuple)."""
    return tuple(settings())


def rate(service, model):
    """US dollars per million billed units (characters, or bytes for Fish), approximate."""
    rates = settings()[service]["usd_per_million"]
    if isinstance(rates, dict):
        return rates.get(model) or next(iter(rates.values()))
    return rates


def estimate(service, model, texts):
    """(characters, approximate US dollars) for sending `texts`."""
    s = settings()[service]
    chars = sum(len(t) for t in texts)
    units = sum(len(t.encode("utf-8")) for t in texts) if s.get("unit") == "bytes" else chars
    return chars, units * rate(service, model) / 1e6


def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x >= 0


def _count(x, least):
    return isinstance(x, int) and not isinstance(x, bool) and x >= least


def validate(tables):
    """What's wrong with {service: settings} as the engine reads it (an empty list when nothing is): each needs
    a name, an https:// url and key_page, a key_var, a default_model among its models, a unit (characters or
    bytes), usd_per_million (a number, or one per model), concurrency and candidates (whole numbers, at least 1),
    max_chars (a whole number, 0 for no limit) and tried_live (true or false); design_usd and note are optional."""
    problems = []
    for service, t in tables.items():
        def bad(field, want):
            problems.append(f"[{service}] {field} must be {want} (it's {t.get(field)!r})")
        for field in ("name", "key_var", "default_model"):
            if not isinstance(t.get(field), str) or not t[field].strip():
                bad(field, "a non-empty string")
        for field in ("url", "key_page"):
            if not isinstance(t.get(field), str) or not t[field].startswith("https://"):
                bad(field, "an https:// address")
        models = t.get("models")
        if not isinstance(models, dict) or not models:
            bad("models", "a table of model ids")
        elif t.get("default_model") not in models:
            bad("default_model", "one of models")
        if t.get("unit") not in ("characters", "bytes"):
            bad("unit", '"characters" or "bytes"')
        rates = t.get("usd_per_million")
        if not (_number(rates) or (isinstance(rates, dict) and rates and all(_number(r) for r in rates.values()))):
            bad("usd_per_million", "a number, or a table of numbers by model")
        for field, least in (("concurrency", 1), ("candidates", 1), ("max_chars", 0)):
            if not _count(t.get(field), least):
                bad(field, f"a whole number, at least {least}")
        if not isinstance(t.get("tried_live"), bool):
            bad("tried_live", "true or false")
        if "design_usd" in t and not _number(t["design_usd"]):
            bad("design_usd", "a number")
        if "note" in t and not isinstance(t["note"], str):
            bad("note", "a string")
    return problems

REQUIRED = {"speaker": ["voice"], "design": ["description", "line", "n", "label"],
            "save": ["candidate", "name", "description", "wav"], "delete": ["voice_id"]}
