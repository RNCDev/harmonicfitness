"""The listener's context files: the one place that reads and writes them.

The listener's context is Markdown that Claude reads and the tools parse: profile.md (who they
are), training.md (kits, likes and dislikes, the usual session), content.md (interests, feeds and
taste, for the stories), health.md and log.md, plus settings.toml (the tools' own settings). Every
tool goes through this module, so a format lives in one place. Each Markdown file opens with TOML
front matter naming its format's version (settings.toml names it as a plain key):

    +++
    schema = 6
    +++

The front matter also holds every setting a tool reads, so the prose below it is free-form and
only Claude reads it. profile() reads the four profile files as one: their settings merged, their
prose joined. Each setting has a home file (SETTING_HOMES); one found elsewhere still counts, and
check() notes a setting written twice. The health file's `[[limits]]` rows (area, side, level,
flags, rehab, note) and its `## Clinician rules` section are what the brief applies as rules. A file at an
older schema stops the tools with the command that brings it up to date, `./sweatcast migrate`.

    ./sweatcast get coach             # also: route, routes, wpm, experience, web-builds
    ./sweatcast deliver               # existing delivery folders, one per line
    ./sweatcast check                 # every file's format, and lines not filled in yet
    ./sweatcast log-session --draft me/workouts/<stem>/<stem>.draft.txt \\
        --coach "Coach Andy" --format straight-sets --topics "deep dive: news, a story" \\
        --loads "goblet squat = twenties, three down; seated row = fifteens" --rpe "goblet squat = 7"
                                      # the date, length and kit come from the draft's menu; the draft
                                      # must have been built as it stands, and a session is logged once
    ./sweatcast log-session --date 2026-10-21 --minutes 25 --kit Home \\
        --coach "Coach Andy" --movements "goblet squat, seated row" --topics "..."   # without a draft
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import tomllib   # Python 3.11: ./sweatcast runs every tool in the project's environment
from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402

SCHEMA = 6   # 6 (0.12.0) splits the profile into profile.md, training.md, content.md and settings.toml
PERSONA_SCHEMA = 5   # me/coaches/<slug>/persona.md (me/personas/ before 0.15.0), new in sweatcast 0.9; 5 (0.10.0) adds kind and web coaches
TOML_FRONT_RE = re.compile(r"\A\+\+\+[ \t]*\n(.*?)\n?\+\+\+[ \t]*\n", re.DOTALL)
FEED_KINDS = ("weather", "espn", "rss", "weekly", "onthisday", "wikipedia")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINE_BREAKS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"   # every character str.splitlines breaks on
HANDLE_KEYS = {"YouTube favorites": "youtube_favorites", "Puzzles": "puzzles"}


# The profile is four files, by how often each part changes and who reads it; the tools read them as one
# (profile()). Each setting and prose section has a home file, where setup and the template put it and
# migrate moves it; a setting found anywhere else still counts, but its home file wins.
PROFILE_PARTS = ("profile.md", "training.md", "content.md", "settings.toml")
SETTING_HOMES = {
    "name": "profile.md", "experience": "profile.md",
    "kits": "training.md", "likes": "training.md", "dislikes": "training.md",
    "interests": "content.md", "feeds": "content.md", "youtube_favorites": "content.md", "puzzles": "content.md",
    "setup": "settings.toml", "render": "settings.toml", "cloud_max_chars": "settings.toml",
    "deliver_to": "settings.toml", "words_per_minute": "settings.toml",
}
PROSE_HOMES = {"equipment kits": "training.md", "default session": "training.md",
               "content": "content.md", "taste": "content.md"}   # every other ## section stays in profile.md


def files():
    """The context files that carry a schema, in the order check() reports them."""
    return [paths.PROFILE, paths.TRAINING, paths.CONTENT_MD, paths.SETTINGS, paths.HEALTH, paths.LOG]


def part_paths(profile_path=None):
    """{part name: path} for the profile's four files, beside `profile_path` (default me/profile.md)."""
    folder = os.path.dirname(profile_path or paths.PROFILE)
    return {name: os.path.join(folder, name) for name in PROFILE_PARTS}


def split(path, text):
    """(settings, prose) of any context file: a .toml file is all settings; the others have a +++ block."""
    try:
        if path.endswith(".toml"):
            return tomllib.loads(text), ""
        return front(text)
    except tomllib.TOMLDecodeError as e:
        raise SystemExit(f"{show(path)} isn't valid TOML: {e}")
    except SystemExit as e:
        raise SystemExit(f"{show(path)}: {e.code}")


# ---- front matter --------------------------------------------------------------------

def front(text):
    """(settings dict, body); no block gives {}. A `+++` block
    that never closes stops here by name, so nobody is sent to migrate over a missing line."""
    text = text.lstrip("\ufeff")   # a byte order mark, from a Windows editor
    m = TOML_FRONT_RE.match(text)
    if m:
        try:
            return tomllib.loads(m.group(1)), text[m.end():]
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(f"The settings block at the top of the file isn't valid TOML: {e}")
    if text.startswith("+++"):
        raise SystemExit("the +++ settings block at the top doesn't close: the settings need a line holding "
                         "only +++ after them")
    return {}, text


def schema_of(text, path=None):
    """The schema a file's front matter (or a .toml file's `schema` key) names; 0 when it has none."""
    try:
        settings, _ = split(path or "", text)
    except SystemExit:
        return SCHEMA   # a TOML block, just a broken one: check() says what's wrong
    try:
        return int(settings.get("schema", 0))
    except (TypeError, ValueError):
        return 0


def body(text):
    """A file's text without its front matter."""
    return front(text)[1]


def toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)   # JSON's string escapes are valid TOML
    if isinstance(v, list):
        return "[" + ", ".join(toml_value(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {toml_value(x)}" for k, x in v.items()) + " }"
    raise TypeError(f"can't write {type(v).__name__} as TOML")


def dump_settings(settings, comments=None):
    """Settings as TOML: plain keys first, then each list of tables ([[voices]], [[feeds]])."""
    comments = comments or {}
    plain = {k: v for k, v in settings.items() if not (isinstance(v, list) and v and isinstance(v[0], dict))}
    tables = {k: v for k, v in settings.items() if k not in plain}
    out = []
    for k, v in plain.items():
        if k in comments:
            out.append(f"# {comments[k]}")
        out.append(f"{k} = {toml_value(v)}")
    for k, rows in tables.items():
        if k in comments:
            out += ["", f"# {comments[k]}"]
        for row in rows:
            out += ["", f"[[{k}]]"] + [f"{rk} = {toml_value(rv)}" for rk, rv in row.items()]
    return "\n".join(out)


def with_front_matter(text, schema=SCHEMA, settings=None, comments=None):
    """Text with TOML front matter for `schema`, replacing any it already has, carrying `settings` when given."""
    rest = body(text)
    merged = {"schema": schema, **{k: v for k, v in (settings or {}).items() if k != "schema"}}
    return f"+++\n{dump_settings(merged, comments)}\n+++\n" + rest


def schema_problem(path, text):
    """A sentence saying why this file's schema won't do, or None."""
    found = schema_of(text, path)
    if found == SCHEMA:
        return None
    if found < SCHEMA:
        return (f"{show(path)} is in an older sweatcast format (schema {found}; this engine reads "
                f"schema {SCHEMA}). Bring the context folder up to date with: ./sweatcast migrate")
    return (f"{show(path)} is in a newer format (schema {found}) than this engine reads (schema {SCHEMA}). "
            "Pull the latest sweatcast.")


def read_raw(path, what="file"):
    with open(paths.require(path, what), encoding="utf-8-sig") as f:   # -sig drops a BOM a Windows editor may add
        return f.read()


def read(path, what="file"):
    """A context file's body (without front matter), after checking its schema."""
    text = read_raw(path, what)
    problem = schema_problem(path, text)
    if problem:
        raise SystemExit(problem)
    return body(text)


def write(path, text):
    """Replace a context file's body atomically, keeping its front matter."""
    current = read_raw(path)
    m = TOML_FRONT_RE.match(current)
    fileio.atomic_write(path, (m.group(0) if m else "") + text)


def section(text, heading):
    """The lines under a `## heading` (case doesn't matter), up to the next one, with
    their 1-based line numbers in `text`."""
    out, inside = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            inside = line[3:].strip().lower() == heading.lower()
            continue
        if inside:
            out.append((n, line))
    return out


def placeholder(value):
    """True for a value still showing me.example's [bracketed] hint."""
    return isinstance(value, str) and value.strip().startswith("[")


def unfilled(value):
    return value is None or (isinstance(value, str) and (not value.strip() or placeholder(value)))


# ---- the profile -----------------------------------------------------------------------

@dataclass
class Profile:
    settings: dict
    body: str
    path: str = ""
    sources: dict = field(default_factory=dict)      # setting -> the file it came from
    duplicates: list = field(default_factory=list)   # (setting, file that won, file that lost)


def profile(path=None):
    """The listener, read as one: the settings of profile.md, training.md, content.md and settings.toml
    merged, and their prose joined. Only profile.md must exist; a missing part reads as empty."""
    path = path or paths.PROFILE
    merged, sources, duplicates, bodies = {}, {}, [], []
    for name, part in part_paths(path).items():
        if name == "profile.md":
            text = read_raw(path, "profile")
            part = path
        elif os.path.exists(part):
            with open(part, encoding="utf-8") as f:
                text = f.read()
        else:
            continue
        problem = schema_problem(part, text)
        if problem:
            raise SystemExit(problem)
        settings, rest = split(part, text)
        for k, v in settings.items():
            if k == "schema":
                continue
            if k not in merged:
                merged[k], sources[k] = v, part
            elif SETTING_HOMES.get(k) == name:   # the key's home file wins
                duplicates.append((k, part, sources[k]))
                merged[k], sources[k] = v, part
            else:
                duplicates.append((k, sources[k], part))
        if rest.strip():
            bodies.append(rest.strip("\n"))
    return Profile(merged, "\n\n".join(bodies) + "\n", path, sources, duplicates)


CLOUD_MAX_CHARS = 30000   # a cloud build's default ceiling: a 40-minute workout with room for retakes


def routes(p):
    """The profile's render preference list (default ["local"]): each build takes the first that works here."""
    value = p.settings.get("render")
    values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    found = [str(v).strip().lower() for v in values if str(v).strip()]
    return found or ["local"]


class Issue(NamedTuple):
    """One thing ./sweatcast check reports (tools/check.py): where, and whether anything breaks."""
    path: str
    line: int        # 0 means the whole file
    message: str
    note: bool = False   # True: worth knowing, but nothing breaks


def render_preferences():
    """The profile's render list (routes()), or ["local"] with no profile yet: what a build, a coach check
    and a route lookup all start from."""
    return routes(profile()) if os.path.exists(paths.PROFILE) else ["local"]


def route_issues(p):
    import cloud   # the routes: "local" and knowledge/services.toml's services
    return [Issue(p.path, 0, f"render lists '{r}', which isn't a route ({', '.join(cloud.ROUTES)}); builds skip it")
            for r in routes(p) if r not in cloud.ROUTES]


def cloud_max_chars(p):
    """The most characters one build may send to a cloud voice, from cloud_max_chars (default 30,000)."""
    v = p.settings.get("cloud_max_chars")
    return int(v) if isinstance(v, (int, float)) and v > 0 else CLOUD_MAX_CHARS


def wpm(p):
    v = p.settings.get("words_per_minute")
    return int(v) if isinstance(v, (int, float)) and v > 0 else None


def delivery_patterns(p):
    """The deliver_to folders with ~ expanded: one string, or a list of them (say one per
    computer, a Mac's Google Drive path and a Windows PC's); unset or hint lines dropped."""
    value = p.settings.get("deliver_to")
    values = value if isinstance(value, list) else [value]
    return [os.path.expanduser(v.strip()) for v in values if isinstance(v, str) and not unfilled(v)]


def delivery_folders(p):
    """(pattern, [existing folders it matches]); * in a pattern matches anything. Of a
    list, the folders that exist on this computer."""
    patterns = delivery_patterns(p)
    if not patterns:
        return None, []
    found = []
    for pattern in patterns:
        hits = sorted(glob.glob(pattern)) if glob.has_magic(pattern) else [pattern]
        found += [d for d in hits if os.path.isdir(d) and d not in found]
    return " or ".join(patterns), found


def feed_sources(p):
    """[(label, kind, value)] from [[feeds]], skipping entries not filled in yet."""
    out = []
    for f in p.settings.get("feeds") or []:
        if not isinstance(f, dict):
            continue
        label, kind, value = (str(f.get(k, "")).strip() for k in ("label", "kind", "value"))
        if kind.lower() in FEED_KINDS and not unfilled(value) and not unfilled(label):
            out.append((label, kind.lower(), value))
    return out


def handles(p, label):
    """The @handles for "YouTube favorites" or "Puzzles" (youtube_favorites, puzzles)."""
    key = HANDLE_KEYS.get(label, label)
    return [h.strip().lstrip("@") for h in p.settings.get(key) or [] if isinstance(h, str) and not unfilled(h)]


def experience(p):
    """The listener's level, one of catalog.LEVELS, or None (unset or unrecognised)."""
    v = p.settings.get("experience")
    v = v.strip().lower() if isinstance(v, str) else ""
    return v if v in catalog.LEVELS else None


def listener_name(p):
    """What the coach calls the listener (the profile's `name`), or None when unset."""
    v = p.settings.get("name")
    v = " ".join(v.split()) if isinstance(v, str) else ""
    return v if v and not placeholder(v) else None


def feedback(path=None, text=None):
    """The `- ` lines under `## Feedback` in log.md, oldest first, without the dash."""
    path = path or paths.LOG
    text = log(path) if text is None else text
    return [line[2:].strip() for _, line in section(text, "Feedback") if line.startswith("- ")]


def interests(p):
    """[(name, slot, detail)]: the profile's [[interests]], the categories the filler plan rotates
    through for each slot (knowledge/content.toml). Rows not filled in are skipped."""
    out = []
    for row in p.settings.get("interests") or []:
        if isinstance(row, dict) and not unfilled(row.get("name")) and not unfilled(row.get("slot")):
            out.append((str(row["name"]).strip(), str(row["slot"]).strip(), str(row.get("detail") or "").strip()))
    return out


def _names(p, key):
    return [x.strip() for x in p.settings.get(key) or [] if isinstance(x, str) and x.strip()]


def likes(p):
    """Movement ids or names the listener likes."""
    return _names(p, "likes")


def dislikes(p):
    """Movement ids or names the listener dislikes."""
    return _names(p, "dislikes")


def kits(p):
    """{kit name: equipment ids} from [[kits]], as written."""
    return {str(k["name"]).strip(): [e for e in k.get("equipment") or [] if isinstance(e, str)]
            for k in p.settings.get("kits") or []
            if isinstance(k, dict) and isinstance(k.get("name"), str) and k["name"].strip()}


UNITS = ("lb", "kg")


def kit_weights(p):
    """{kit name: (unit, {equipment id: sorted weights})} from each [[kits]] table's optional `weights`
    (equipment id = list of numbers) and `unit` ("lb" by default), for the kits that give any."""
    out = {}
    for k in p.settings.get("kits") or []:
        if not (isinstance(k, dict) and isinstance(k.get("name"), str) and isinstance(k.get("weights"), dict)):
            continue
        table = {e: sorted(w for w in ws if isinstance(w, (int, float)) and not isinstance(w, bool) and w > 0)
                 for e, ws in k["weights"].items() if isinstance(ws, list)}
        table = {e: ws for e, ws in table.items() if ws}
        if table:
            out[k["name"].strip()] = (k.get("unit") if k.get("unit") in UNITS else "lb", table)
    return out


def _weight_problems(k):
    """Faults in one [[kits]] table's `weights` and `unit`, as sentences."""
    out = []
    w = k.get("weights")
    if w is not None and not isinstance(w, dict):
        out.append("weights should be a table, such as { dumbbells = [10, 15, 20] }")
    for e, ws in (w.items() if isinstance(w, dict) else []):
        if e not in (k.get("equipment") or []):
            out.append(f"weights lists '{e}', which isn't in the kit's equipment")
        if not isinstance(ws, list) or not ws or not all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in ws):
            out.append(f"weights for '{e}' should be a list of numbers above zero")
    if "unit" in k and k["unit"] not in UNITS:
        out.append(f"unit should be {' or '.join(UNITS)}")
    return out


SETTINGS_COMMENTS = {
    "words_per_minute": "A rough speaking rate (./sweatcast get wpm prints it); builds use each coach's measured pace.",
    "experience": "Your training level: novice, experienced or advanced. The brief's menu of movements matches it; until set, it assumes novice.",
    "likes": "Movements you enjoy (ids or names from ./sweatcast movements); sessions favour them.",
    "dislikes": "Movements to leave out (ids or names); the brief's menu never lists them.",
    "deliver_to": "Where finished MP3s go: a folder that syncs to your phone. ~ is your home folder and * "
                  "matches anything (any Google account). Once the copy is there the local MP3 is removed; "
                  "empty keeps MP3s in me/workouts/. A list gives one folder per computer; each copies to those it has.",
    "youtube_favorites": "Channels (@handles) for the deep dives retold from a video's transcript.",
    "puzzles": "Channels (@handles) whose puzzles can be the session's quiz.",
    "interests": "What the filler between exercises rotates through: a name, its slot (today, science, "
                 "deep_dive, quiz, delight or learn; knowledge/content.toml) and a detail for research. Within "
                 "a slot, the one told longest ago comes next. Without any, knowledge/content.toml's defaults.",
    "feeds": "Fetched by ./sweatcast feeds at the start of each session. Kinds: weather (latitude, "
             "longitude), espn (sport/league/team, as in ESPN's team URLs), rss and weekly (feed URL), "
             "onthisday (selected), wikipedia (featured: the featured article, most read, in the news "
             "and did you know).",
}


# ---- coaches (me/coaches/<slug>/persona.md) -------------------------------------------------

@dataclass
class Persona:
    settings: dict
    body: str
    path: str = ""


PERSONA_COMMENTS = {
    "local": "How this coach sounds on this computer: Pocket TTS, from the voice file beside this one.",
    "fish": "Fish Audio: the model (a web voice; ./sweatcast keys).",
    "gemini": "Gemini: the model (a web voice; ./sweatcast keys).",
    "inworld": "Inworld: the model (a web voice; ./sweatcast keys).",
    "elevenlabs": "ElevenLabs: eleven_v4 (more natural) or eleven_v4_turbo (cheaper).",
    "voice": "How this coach sounds: what a web service designs the voice from (an edit means a new audition).",
    "character": "How this coach talks: what the script writer follows (the brief quotes it); edit freely.",
    "settings": "The web service's own voice settings, sent with every request.",
}


def persona(path):
    """A coach's persona.md: its settings (the TOML at the top) and how the coach talks (the prose)."""
    text = read_raw(path, "coach")
    settings, rest = front(text)
    found = settings.get("schema")
    if found != PERSONA_SCHEMA:
        older = isinstance(found, int) and found < PERSONA_SCHEMA
        raise SystemExit(f"{show(path)} is schema {found}; this engine reads coaches at schema {PERSONA_SCHEMA}: "
                         + ("run ./sweatcast migrate." if older else "pull the latest sweatcast."))
    return Persona(settings, rest, path)


def persona_text(settings, prose):
    """A persona.md: the settings block (plain keys, then one [table] each: an engine's, [voice], [character]),
    then the prose."""
    plain = {k: v for k, v in settings.items() if k != "schema" and not isinstance(v, dict)}
    tables = {k: v for k, v in settings.items() if isinstance(v, dict)}
    out = [f"schema = {PERSONA_SCHEMA}"] + [f"{k} = {toml_value(v)}" for k, v in plain.items()]
    for name, table in tables.items():
        out.append("")
        if name in PERSONA_COMMENTS:
            out.append(f"# {PERSONA_COMMENTS[name]}")
        out.append(f"[{name}]")
        out += [f"{k} = {toml_value(v)}" for k, v in table.items()]
    block = "\n".join(out)
    tomllib.loads(block)   # never write a block that doesn't parse
    return f"+++\n{block}\n+++\n" + (prose if prose.endswith("\n") or not prose else prose + "\n")


def set_persona_setting(path, table, key, value):
    """Set one setting in a persona.md (`table` None for a top-level key), keeping its prose."""
    p = persona(path)
    settings = dict(p.settings)
    if table:
        settings[table] = dict(settings.get(table) or {}, **{key: value})
    else:
        settings[key] = value
    fileio.atomic_write(path, persona_text(settings, p.body))


# ---- the health file -------------------------------------------------------------------

LIMIT_SIDES, LIMIT_LEVELS = catalog.LIMIT_SIDES, catalog.LIMIT_LEVELS
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
INJURIES_HEADING = "Active injuries and limitations"
CLINICIAN_HEADING = "Clinician rules"


@dataclass
class Health:
    settings: dict
    body: str
    path: str = ""


def health(path=None):
    """The health file: its settings (the [[limits]] rows) and its prose."""
    path = path or paths.HEALTH
    text = read_raw(path, "health file")
    problem = schema_problem(path, text)
    if problem:
        raise SystemExit(problem)
    settings, rest = front(text)
    return Health(settings, rest, path)


LIMIT_KEYS = ("area", "side", "level", "flags", "rehab", "note")


def _limit_row(row, areas, flags=None):
    """(Limit, None) for a good [[limits]] row, else (None, a sentence saying what's wrong).
    `flags` are the catalog's; a flag outside them is wrong (None skips that check)."""
    if not isinstance(row, dict):
        return None, "isn't a table"
    unknown = [k for k in row if k not in LIMIT_KEYS]
    if unknown:   # a misspelled key ("flag") would drop what it says without a word
        return None, f"'{unknown[0]}' isn't a key a limit takes (one of: {', '.join(LIMIT_KEYS)})"
    area, side = row.get("area"), row.get("side", "both")
    level = row.get("level")
    if area not in areas:
        return None, f"area '{area}' isn't one of: {', '.join(areas)}"
    if side not in LIMIT_SIDES:
        return None, f"side '{side}' must be {', '.join(LIMIT_SIDES[:-1])} or {LIMIT_SIDES[-1]}"
    if level not in LIMIT_LEVELS:
        return None, f"level '{level}' must be {' or '.join(LIMIT_LEVELS)}"
    for key in ("flags", "rehab"):
        value = row.get(key, [])
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            example = "floor" if key == "flags" else "a-movement-id"
            return None, f"{key} must be a list of quoted names, such as {key} = [\"{example}\"]"
    unknown = [f for f in row.get("flags", []) if flags is not None and f not in flags]
    if unknown:
        return None, f"flag '{unknown[0]}' isn't one of: {', '.join(flags)}"
    return catalog.Limit(area, side, level, list(row.get("flags", [])), list(row.get("rehab", [])),
                         str(row.get("note") or "").strip()), None


def _vocab(areas, flags):
    """The catalog's areas and flags, loading the shipped catalog for whichever is None."""
    if areas is None or flags is None:
        cat = catalog.load()
        areas = cat.areas if areas is None else areas
        flags = cat.flags if flags is None else flags
    return areas, flags


def limit_rows(h, areas=None, flags=None):
    """([catalog.Limit], [problem]) for the [[limits]] rows: each good row as a Limit, and for each bad one
    (an unknown key, a bad area, side, level, flags or rehab) "row <n>: <what's wrong>"."""
    areas, flags = _vocab(areas, flags)
    rows = h.settings.get("limits") or []
    if not isinstance(rows, list):
        return [], ["limits must be written as [[limits]] tables"]
    found, problems = [], []
    for n, row in enumerate(rows, 1):
        lim, problem = _limit_row(row, areas, flags)
        if lim:
            found.append(lim)
        else:
            problems.append(f"row {n}: {problem}")
    return found, problems


def limits(h, areas=None, flags=None):
    """The valid [[limits]] rows as catalog.Limit; a bad row is left out (limit_rows names it; `check`
    reports it, and the brief refuses to plan)."""
    return limit_rows(h, areas, flags)[0]


def _section_lines(h, heading):
    text = HTML_COMMENT_RE.sub("", h.body)
    return [line.strip() for _, line in section(text, heading)]


def limit_line(lim):
    """`<area> <level>[ <side>][: <note>]`: how a limit reads as a health line."""
    head = f"{lim.area} {lim.level}" + (f" {lim.side}" if lim.side != "both" else "")
    return f"{head}: {lim.note}" if lim.note else head


def clinician_lines(h, areas=None, flags=None):
    """One line per limit (its area, level, side and note), then every line under
    `## Clinician rules`, as rules to follow literally. Blank lines and the template's
    [hint] don't count."""
    out = [limit_line(lim) for lim in limits(h, areas, flags)]
    for line in _section_lines(h, CLINICIAN_HEADING):
        line = line[2:].strip() if line.startswith("- ") else line
        line = re.sub(r"^rule:\s*", "", line, flags=re.IGNORECASE)   # the template's label, not the clinician's words
        if line and not line.startswith("#") and not (placeholder(line) and "]" in line):
            out.append(line)
    return out


UNLISTED = "unlisted:"
AVOID = "avoid:"


def clinician_avoids(h):
    """The movement ids and flags on every "Avoid: <ids or flags>" line under `## Clinician rules`,
    in order, which the brief's safety screen rules out on every run."""
    out = []
    for line in _section_lines(h, CLINICIAN_HEADING):
        line = line[2:].strip() if line.startswith(("- ", "* ")) else line.strip()
        if line.lower().startswith(AVOID):
            out += [w.strip() for w in line[len(AVOID):].split(",") if w.strip()]
    return list(dict.fromkeys(out))


def prose_injury_count(h):
    """How many injuries `## Active injuries and limitations` lists, each a top-level "- " line (the
    indented lines under one, such as "  - Programming:", are its details), leaving out "None right now"
    and an injury outside the catalog's areas, written "- Unlisted: <what>" (its avoids go under
    `## Clinician rules` as "Avoid: <ids or flags>"). Each one counted needs a [[limits]] row."""
    count = 0
    for _, line in section(HTML_COMMENT_RE.sub("", h.body), INJURIES_HEADING):
        if not line.startswith(("- ", "* ")):
            continue
        item = line[2:].strip()
        if item.rstrip(".").lower() != "none right now" and not item.lower().startswith(UNLISTED):
            count += 1
    return count


def prose_injuries(h):
    """True when the injuries section lists any injury that needs a [[limits]] row (prose_injury_count)."""
    return prose_injury_count(h) > 0


def prose_injury_gap(h, rows):
    """A sentence when the injuries prose lists more injuries than there are good [[limits]] rows (`rows`),
    so some injury has no limit applied; else None."""
    count = prose_injury_count(h)
    if count <= rows:
        return None
    if not rows:
        return "injuries written in prose have no [[limits]] entry, so no limit is applied for them; add a row for each"
    return (f"the injuries section lists {count} injuries but there are only {rows} [[limits]] rows, so one "
            "has no limit applied; add a row for each (or write one outside the catalog's areas as "
            "\"- Unlisted: <what>\")")


# ---- the log ---------------------------------------------------------------------------

@dataclass
class Session:
    """One line under `## Sessions` in log.md:
    - <date> | <N> min | <kit> | <voice> | <movements> | <topics> | format: <format>
      | loads: <m> = <load>; ... | rpe: <m> = <n>; ...   (all on one line)"""
    date: str
    minutes: int
    kit: str
    voice: str
    movements: List[str]
    topics: str
    format: Optional[str] = None
    loads: Dict[str, str] = field(default_factory=dict)
    rpe: Dict[str, str] = field(default_factory=dict)   # effort per movement; reserved for progress tracking
    line: int = 0   # where it was read from, for messages

    def problems(self):
        out = []
        if not DATE_RE.match(self.date):
            out.append(f"date '{self.date}' isn't YYYY-MM-DD")
        else:
            try:
                dt.date.fromisoformat(self.date)
            except ValueError:
                out.append(f"date '{self.date}' isn't a real date")
        if not isinstance(self.minutes, int) or self.minutes <= 0:
            out.append(f"length '{self.minutes}' isn't a whole number of minutes")
        for name in ("kit", "voice", "topics"):
            if not str(getattr(self, name) or "").strip():
                out.append(f"no {name}")
        if not self.movements:
            out.append("no movements")
        texts = [self.date, self.kit, self.voice, self.topics, self.format or "", *self.movements,
                 *self.loads.keys(), *self.loads.values(), *self.rpe.keys(), *self.rpe.values()]
        if any("|" in t or any(c in t for c in LINE_BREAKS) for t in texts):
            out.append("a field contains | or a line break")
        if any("," in m for m in self.movements):
            out.append("a movement contains a comma")
        if any(";" in t or "=" in t for t in [*self.loads.keys(), *self.loads.values()]):
            out.append("a load contains ; or =")
        if any(";" in t or "=" in t for t in [*self.rpe.keys(), *self.rpe.values()]):
            out.append("an rpe contains ; or =")
        return out

    def to_line(self):
        out = (f"- {self.date} | {self.minutes} min | {self.kit} | {self.voice} | "
               f"{', '.join(self.movements)} | {self.topics}")
        if self.format:
            out += f" | format: {self.format}"
        if self.loads:
            out += " | loads: " + "; ".join(f"{k} = {v}" for k, v in self.loads.items())
        if self.rpe:
            out += " | rpe: " + "; ".join(f"{k} = {v}" for k, v in self.rpe.items())
        return out


def parse_session(line, lineno=0):
    """A log line as a Session, or a sentence saying why it isn't one."""
    fields = [x.strip() for x in line[2:].split("|")]
    if len(fields) < 6:
        return (f"{len(fields)} fields; a session line has date, length, kit, voice, movements "
                "and topics, then format, loads and rpe")
    m = re.match(r"^(\d+)\s*min", fields[1])
    s = Session(fields[0], int(m.group(1)) if m else fields[1], fields[2], fields[3],
                [x.strip() for x in fields[4].split(",") if x.strip()], fields[5], line=lineno)
    for extra in fields[6:]:
        key, _, value = extra.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "format" and value:
            s.format = value
        elif key in ("loads", "rpe"):
            for item in value.split(";"):
                mv, _, load = item.partition("=")
                if mv.strip() and load.strip():
                    (s.loads if key == "loads" else s.rpe)[mv.strip()] = load.strip()
        elif extra.strip():
            return f"unknown field '{extra.strip()[:30]}'; only format:, loads: and rpe: follow the topics"
    problems = s.problems()
    return "; ".join(problems) if problems else s


def log(path=None):
    return read(path or paths.LOG, "log")


def sessions(path=None, text=None, warn=True):
    """Each well-formed session in log.md, oldest first. A malformed line is skipped
    with a warning on stderr (never read with its fields shifted); `check` lists them."""
    path = path or paths.LOG
    text = log(path) if text is None else text
    out = []
    for n, line in section(text, "Sessions"):
        if line.startswith("- "):
            s = parse_session(line, n)
            if isinstance(s, Session):
                out.append(s)
            elif warn:
                print(f"Skipped {show(path)} session line {n} (counting after the settings block): {s}. "
                      "Fix it so the plan sees that session.", file=sys.stderr)
    return out


def append_session(session, path=None):
    """Add a session line at the end of `## Sessions`, after checking it."""
    problems = session.problems()
    if problems:
        raise SystemExit("Not logged: " + "; ".join(problems) + ".")
    path = path or paths.LOG
    lines = log(path).splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == "## sessions"), None)
    if start is None:
        raise SystemExit(f"No '## Sessions' heading in {show(path)}.")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    last = max([i for i in range(start + 1, end) if lines[i].strip()], default=start)
    insert = [session.to_line()]
    if last == start:
        insert = [""] + insert   # a blank line under the heading, as the template has it
    if end < len(lines) and last + 1 == end:
        insert.append("")        # keep a blank line before the next heading
    lines[last + 1:last + 1] = insert
    write(path, "\n".join(lines) + "\n")
    return session.to_line()


# ---- command line ----------------------------------------------------------------------

def declared_movements(path):
    """The movements a draft's `movements:` line declares, each by its catalog name when the catalog
    knows it."""
    import draft
    if not os.path.exists(path):
        raise SystemExit(f"Not logged: no draft at {show(path)}.")
    with open(path, encoding="utf-8") as f:
        words = draft.declared(f.read())
    if not words:
        raise SystemExit(f"Not logged: {show(path)} has no movements: line.")
    cat = _catalog()
    found = [(cat.movements.get(w) or catalog.resolve(cat, w)) if cat else None for w in words]
    return list(dict.fromkeys(m.name if m else w for m, w in zip(found, words)))


def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="print one value from the profile (empty when it has none)")
    g.add_argument("what", choices=("wpm", "experience", "route", "routes", "coach", "web-builds"),
                   help="web-builds: how many builds have sent a script to a web voice service")
    g.add_argument("--coach", help="with route: the coach the build is for (default: the last one used)")
    g.add_argument("--engine", help="with route: a route to use if it works here")
    sub.add_parser("deliver", help="print the existing delivery folders, one per line")
    s = sub.add_parser("log-session", help="add a session to log.md, checked")
    s.add_argument("--draft", help="the built draft: its movements: line gives the movements, and its menu the "
                                   "date, length and kit (a build of this exact draft must exist)")
    s.add_argument("--date", help="YYYY-MM-DD (default: the menu's date with --draft, else today)")
    s.add_argument("--minutes", type=int, help="required without --draft")
    s.add_argument("--kit", help="required without --draft")
    s.add_argument("--coach", dest="voice", required=True, help="the session's coach")
    s.add_argument("--movements", help="comma-separated, without --draft")
    s.add_argument("--topics", required=True)
    s.add_argument("--format", default=None, help="the session method (required with --draft)")
    s.add_argument("--loads", default="", help="'<movement> = <load and tempo>; ...'")
    s.add_argument("--rpe", default="", help="'<movement> = <effort>; ...' (kept for progress tracking)")
    args = ap.parse_args(argv)

    if args.cmd == "get":
        p = profile()
        if args.what == "coach":
            import personas
            coach = personas.default()
            if coach:
                print(coach.name)
            return cli.OK
        if args.what == "web-builds":
            print(web_builds())
            return cli.OK
        if args.what in ("route", "routes"):
            if args.what == "routes":
                print("\n".join(routes(p)))
                return cli.OK
            import personas
            import routes as routing
            # an unknown coach, a web coach with no key here or a bad --engine exit 64 through cli.run
            coach = personas.lookup(args.coach) if args.coach else personas.default()
            print(routing.pick(routes(p), coach, override=args.engine))
            return cli.OK
        v = {"wpm": wpm, "experience": experience}[args.what](p)
        if v is not None:
            print(v)
        return cli.OK
    if args.cmd == "deliver":
        pattern, found = delivery_folders(profile())
        if not pattern:
            print("No copy made: the profile's settings have no deliver_to folder.", file=sys.stderr)
        elif not found:
            print(f"Delivery folder {pattern} not found.", file=sys.stderr)
        for d in found:
            print(d)
        return cli.OK
    def pairs(text, what, shape):
        out = {}
        for item in text.split(";"):
            mv, sep, val = item.partition("=")
            if item.strip() and not (sep and mv.strip() and val.strip()):
                raise SystemExit(f"Not logged: {what} '{item.strip()}' isn't '<movement> = <{shape}>'.")
            if sep:
                out[mv.strip()] = val.strip()
        return out
    loads = pairs(args.loads, "load", "load and tempo")
    rpe = pairs(args.rpe, "rpe", "effort")
    if bool(args.movements) == bool(args.draft):
        raise cli.Usage("Not logged: give the movements with --movements or --draft (one of them).")
    if args.draft:
        date, minutes, kit, movements = from_draft(args.draft, args.date, args.minutes, args.kit)
        if not (args.format or "").strip():
            raise cli.Usage("Not logged: --format is required with --draft (the method you chose, from "
                             "knowledge/sessions.toml), so the next session rotates away from it.")
    else:
        for flag, value in (("--minutes", args.minutes), ("--kit", args.kit)):
            if value is None:
                raise cli.Usage(f"Not logged: {flag} is required without --draft.")
        date, minutes, kit = args.date or dt.date.today().isoformat(), args.minutes, args.kit.strip()
        movements = [m.strip() for m in args.movements.split(",") if m.strip()]
    session = Session(date, minutes, kit, args.voice.strip(), movements, args.topics.strip(),
                      (args.format or "").strip() or None,
                      named_pairs(loads, movements, "load"), named_pairs(rpe, movements, "rpe"))
    _check_session_names(session, kit_from_menu=bool(args.draft))
    with locks.file_lock(paths.LOG):   # the duplicate check and the write as one step
        _check_not_logged(session)
        print("Logged: " + append_session(session))
    return cli.OK


def menu_kit(request):
    """The kit a menu's request names, as the log writes it: the profile kit's name, the preset's name, or
    "custom: <equipment ids>" for a brief run with --equipment (equipment added with --add isn't logged:
    the kit stays the kit)."""
    if request.get("kit"):
        return str(request["kit"])
    if request.get("preset"):
        return str(request["preset"])
    if request.get("equipment"):
        return "custom: " + ", ".join(request["equipment"])
    return None


def draft_hash(path):
    """sha256 of a draft as the build hashes it: read as text (so line endings are \\n), encoded as UTF-8."""
    with open(path, encoding="utf-8") as f:
        return hashlib.sha256(f.read().encode("utf-8")).hexdigest()


def build_records(log=None):
    """Every record in builds.jsonl, oldest first: one per MP3, and a "failed" one for a web render that sent
    text and stopped. A damaged line is skipped."""
    try:
        with open(log or paths.BUILDS, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except FileNotFoundError:
        return


def built(sha256, log=None):
    """True when builds.jsonl records an MP3 made from a draft with this hash. A failed web render made no
    MP3 and doesn't count; a build that ran off plan (exit 2) did make one, and counts."""
    return any(not rec.get("failed") and rec.get("draft_sha256") == sha256 for rec in build_records(log))


def web_builds(log=None):
    """How many builds sent a script to a web voice service, failed ones included (the text went out)."""
    import cloud
    return sum(rec.get("route") in cloud.SERVICES for rec in build_records(log))


def from_draft(path, date=None, minutes=None, kit=None):
    """(date, minutes, kit, movements) for a built draft: the movements from its movements: line, the rest
    from the menu beside it. A typed date, length or kit must agree with the menu."""
    import draft
    import menu
    movements = declared_movements(path)
    menu_file = draft.menu_path(path)
    try:
        m = menu.load(menu_file)
    except ValueError as e:
        raise SystemExit(f"Not logged: the menu beside the draft can't be read ({show(menu_file)}: {e}).")
    if not isinstance(m, dict) or not isinstance(m.get("request"), dict):
        raise SystemExit(f"Not logged: no menu beside the draft ({show(menu_file)}); a built draft has one.")
    request = m["request"]
    want = {"--date": m.get("date"),
            "--minutes": request.get("minutes") or (m.get("seconds") or 0) // 60 or None,
            "--kit": menu_kit(request)}
    for flag, typed in (("--date", date), ("--minutes", minutes), ("--kit", kit)):
        if want[flag] is None:
            raise SystemExit(f"Not logged: the menu ({show(menu_file)}) holds no {flag[2:]}.")
        if typed is not None and str(typed).strip().lower() != str(want[flag]).lower():
            raise SystemExit(f"Not logged: {flag} {typed} disagrees with the menu's {want[flag]} "
                             f"({show(menu_file)}); leave it out, the menu gives it.")
    if not built(draft_hash(path)):
        raise SystemExit(f"Not logged: no build of {show(path)} as it stands (no record in {show(paths.BUILDS)} "
                         "with its hash). Build it first; if you edited it after building, build it again.")
    return want["--date"], int(want["--minutes"]), want["--kit"], movements


def _movement_key(cat, name):
    """A movement's catalog id, or its lowercased name when the catalog doesn't know it."""
    found = catalog.resolve(cat, name) if cat else None
    return found.id if found else name.strip().lower()


def named_pairs(items, movements, what):
    """{movement: value} with each movement written by its catalog name, refused unless it is one of the
    session's movements, so coverage can read the load back for that movement."""
    cat = _catalog()
    session = {_movement_key(cat, m) for m in movements}
    out = {}
    for name, value in items.items():
        key = _movement_key(cat, name)
        if key not in session:
            raise SystemExit(f"Not logged: {what} for '{name}', which isn't one of the session's movements "
                             f"({', '.join(movements)}).")
        out[cat.movements[key].name if cat and key in cat.movements else name] = value
    return out


def _check_not_logged(session, path=None):
    """Refuse a second line for the same session: the same date and the same movements."""
    cat = _catalog()
    mine = {_movement_key(cat, m) for m in session.movements}
    for old in sessions(path, warn=False):
        if old.date == session.date and {_movement_key(cat, m) for m in old.movements} == mine:
            raise SystemExit(f"Not logged: this session is already logged (log.md line {old.line}: {old.date}, "
                             f"{', '.join(old.movements)}).")


def _check_session_names(session, kit_from_menu=False):
    """A logged coach, kit and format must exist, so the next brief and coverage can read them back: the coach
    by name or alias (archived ones too, for old sessions), the kit from the profile or a catalog preset (one
    taken from the menu was checked by the brief), the format one of knowledge/sessions.toml's methods."""
    import personas
    import sessions
    try:
        personas.lookup(session.voice, archived=True)
    except SystemExit as e:
        raise SystemExit(f"Not logged: no coach '{session.voice}' ({e.code})")
    if not kit_from_menu and os.path.exists(paths.PROFILE):   # with no profile there's nothing to check against
        known_kits = set(kits(profile())) | set(_catalog_presets())
        if session.kit.lower() not in {k.lower() for k in known_kits}:
            raise SystemExit(f"Not logged: kit '{session.kit}' isn't one of the profile's kits or a catalog preset "
                             f"({', '.join(sorted(known_kits))}).")
    methods = sessions.load().methods
    if session.format and session.format not in methods:
        raise SystemExit(f"Not logged: format '{session.format}' isn't a method in knowledge/sessions.toml "
                         f"({', '.join(methods)}).")


def _catalog():
    try:
        return catalog.load()
    except (SystemExit, ValueError, OSError):
        return None   # the catalog's own check says what's wrong


def _catalog_presets():
    cat = _catalog()
    return cat.presets if cat else {}


if __name__ == "__main__":
    sys.exit(cli.run(main))
