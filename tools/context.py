"""The listener's context files: the one place that reads and writes them.

me/profile.md, health.md and log.md are Markdown that Claude
reads and the tools parse. Every tool goes through this module, so a format lives in
one place. Each file opens with TOML front matter naming its format's version:

    +++
    schema = 3
    +++

The profile's front matter also holds every setting a tool reads (voices, delivery
folder, words per minute, experience level, likes and dislikes, equipment kits, YouTube
channels, puzzles, feeds), so the prose below it is free-form and only Claude reads it.
Schema 3 adds the profile's `experience`, `likes`, `dislikes` and `[[kits]]`, and the
health file's `[[limits]]` rows (area, side, level, flags, rehab, note) with its
`## Clinician rules` section, which the session tool applies as rules. A file from an older sweatcast (schema 1 used
`---` front matter, schema 0 had none) stops the tools with the command that brings
it up to date, `./sweatcast migrate`.

    ./sweatcast get default-voice     # also: wpm, voices, experience
    ./sweatcast deliver               # existing delivery folders, one per line
    ./sweatcast check                 # every file's format, and lines not filled in yet
    ./sweatcast log-session --date 2026-10-21 --minutes 25 --kit Home \\
        --voice "Chatterbox Coach" --movements "goblet squat, seated row" \\
        --topics "deep dive: news, a story" --format "rolling minutes" \\
        --loads "goblet squat = twenties, three down; seated row = fifteens" \\
        --rpe "goblet squat = 7"
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional

try:
    import tomllib
except ImportError:   # Python before 3.11, such as the Mac's own python3
    raise SystemExit("sweatcast's tools need Python 3.11, which ./sweatcast runs them with. "
                     "Use ./sweatcast <command> (./sweatcast help lists them).")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402

SCHEMA = 3
TOML_FRONT_RE = re.compile(r"\A\+\+\+[ \t]*\n(.*?)\n?\+\+\+[ \t]*\n", re.DOTALL)
YAML_FRONT_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)   # schema 1
SCHEMA_LINE_RE = re.compile(r"^schema:\s*(\d+)\s*$", re.MULTILINE)
FEED_KINDS = ("weather", "espn", "rss", "weekly", "onthisday")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HANDLE_KEYS = {"YouTube favorites": "youtube_favorites", "Puzzles": "puzzles"}


def files():
    """The context files that carry a schema, in the order check() reports them."""
    return [paths.PROFILE, paths.HEALTH, paths.LOG]


# ---- front matter --------------------------------------------------------------------

def front(text):
    """(settings dict, body). Schema-1 `---` front matter gives {"schema": 1}; none gives {}."""
    m = TOML_FRONT_RE.match(text)
    if m:
        try:
            return tomllib.loads(m.group(1)), text[m.end():]
        except tomllib.TOMLDecodeError as e:
            raise SystemExit(f"The settings block at the top of the file isn't valid TOML: {e}")
    m = YAML_FRONT_RE.match(text)
    if m:
        s = SCHEMA_LINE_RE.search(m.group(1))
        return ({"schema": int(s.group(1))} if s else {}), text[m.end():]
    return {}, text


def schema_of(text):
    """The schema a file's front matter names; 0 when it has none (before 2.0.0)."""
    try:
        settings, _ = front(text)
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
    """Text with front matter for `schema`, replacing any it already has. Schema 1 is
    the old `---` form; 2 and later are TOML, carrying `settings` when given."""
    rest = body(text)
    if schema < 2:
        return f"---\nschema: {schema}\n---\n" + rest
    merged = {"schema": schema, **{k: v for k, v in (settings or {}).items() if k != "schema"}}
    return f"+++\n{dump_settings(merged, comments)}\n+++\n" + rest


def schema_problem(path, text):
    """A sentence saying why this file's schema won't do, or None."""
    found = schema_of(text)
    if found == SCHEMA:
        return None
    if found < SCHEMA:
        return (f"{show(path)} is in an older sweatcast format (schema {found}; this engine reads "
                f"schema {SCHEMA}). Bring the context folder up to date with: ./sweatcast migrate")
    return (f"{show(path)} is in a newer format (schema {found}) than this engine reads (schema {SCHEMA}). "
            "Pull the latest sweatcast.")


def read_raw(path, what="file"):
    with open(paths.require(path, what), encoding="utf-8") as f:
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
    m = TOML_FRONT_RE.match(current) or YAML_FRONT_RE.match(current)
    _atomic_write(path, (m.group(0) if m else "") + text)


def _atomic_write(path, text):
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


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


def profile(path=None):
    """The profile: its settings (the TOML at the top) and its prose."""
    path = path or paths.PROFILE
    text = read_raw(path, "profile")
    problem = schema_problem(path, text)
    if problem:
        raise SystemExit(problem)
    settings, rest = front(text)
    return Profile(settings, rest, path)


def voices(p):
    """[(name, description)] from [[voices]]; the first is the default."""
    return [(v["name"].strip(), str(v.get("description", "")).strip())
            for v in p.settings.get("voices") or [] if isinstance(v, dict) and not unfilled(v.get("name"))]


def default_voice(p):
    found = voices(p)
    return found[0][0] if found else None


def wpm(p):
    v = p.settings.get("words_per_minute")
    return int(v) if isinstance(v, (int, float)) and v > 0 else None


def delivery_patterns(p):
    """The deliver_to folders with ~ expanded: one string, or a list of them (say one per
    computer, a Mac's Google Drive path and a Windows PC's); unset or hint lines dropped."""
    value = p.settings.get("deliver_to")
    values = value if isinstance(value, list) else [value]
    return [os.path.expanduser(v.strip()) for v in values if isinstance(v, str) and not unfilled(v)]


def delivery(p):
    """The deliver_to folder (or folders, joined with "or") with ~ expanded, or None
    (unset, or still the hint)."""
    return " or ".join(delivery_patterns(p)) or None


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


def add_voice_to_profile(name, description="", default=False, path=None):
    """List a voice in the profile's [[voices]], first when it's to be the default.
    Edits the settings block as text, so its comments and order survive."""
    path = path or paths.PROFILE
    text = read_raw(path, "profile")
    problem = schema_problem(path, text)
    if problem:
        raise SystemExit(problem)
    m = TOML_FRONT_RE.match(text)
    lines = m.group(1).split("\n")
    entry = ["[[voices]]", f"name = {toml_value(name)}", f"description = {toml_value(description)}"]
    starts = [i for i, line in enumerate(lines) if line.strip() == "[[voices]]"]
    # Drop an existing entry of the same name, so keeping a voice again replaces it.
    for i in reversed(starts):
        end = next((j for j in range(i + 1, len(lines)) if lines[j].lstrip().startswith("[")), len(lines))
        block = tomllib.loads("\n".join(lines[i + 1:end]))
        if str(block.get("name", "")).lower() == name.lower():
            while end > i and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
                end -= 1
            del lines[i:end]
    starts = [i for i, line in enumerate(lines) if line.strip() == "[[voices]]"]
    if starts and default:
        lines[starts[0]:starts[0]] = entry + [""]
    elif starts:
        last = starts[-1]
        end = next((j for j in range(last + 1, len(lines)) if lines[j].lstrip().startswith("[")), len(lines))
        while end > last and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
            end -= 1   # stop before the next table's comment
        lines[end:end] = [""] + entry
    else:
        lines += [""] + entry
    settings_text = "\n".join(lines).strip("\n")
    tomllib.loads(settings_text)   # never write a block that doesn't parse
    _atomic_write(path, f"+++\n{settings_text}\n+++\n" + text[m.end():])


SETTINGS_COMMENTS = {
    "words_per_minute": "The speaking rate ./sweatcast lint assumes when no voice is given; builds use each voice's measured pace.",
    "experience": "Your training level: novice, experienced or advanced. The session tool picks movements to match; until set, it assumes novice.",
    "likes": "Movements you enjoy (ids or names from ./sweatcast movements); the session tool favours them.",
    "dislikes": "Movements to leave out (ids or names); the session tool never picks them.",
    "deliver_to": "Where finished MP3s go: a folder that syncs to your phone. ~ is your home folder and * "
                  "matches anything (any Google account). Once the copy is there the local MP3 is removed; "
                  "empty keeps MP3s in me/workouts/. A list gives one folder per computer; each copies to those it has.",
    "youtube_favorites": "Channels (@handles) for the deep dives retold from a video's transcript.",
    "puzzles": "Channels (@handles) whose puzzles can be the session's quiz.",
    "voices": "Voices from ./sweatcast voices; the first is the default. The description is what the "
              "check-in offers.",
    "feeds": "Fetched by ./sweatcast feeds at the start of each session. Kinds: weather (latitude, "
             "longitude), espn (sport/league/team, as in ESPN's team URLs), rss and weekly (feed URL), "
             "onthisday (selected).",
}


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


def _limit_row(row, areas, flags=None):
    """(Limit, None) for a good [[limits]] row, else (None, a sentence saying what's wrong).
    `flags` are the catalog's; a flag outside them is wrong (None skips that check)."""
    if not isinstance(row, dict):
        return None, "isn't a table"
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


def limits(h, areas=None, flags=None):
    """The valid [[limits]] rows as catalog.Limit; a row with a bad area, side, level, flags or
    rehab is left out (`check` reports it, and the session tool refuses to plan)."""
    areas, flags = _vocab(areas, flags)
    found = (_limit_row(row, areas, flags)[0] for row in h.settings.get("limits") or [])
    return [lim for lim in found if lim]


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
        if line and not line.startswith("#") and not (placeholder(line) and "]" in line):
            out.append(line)
    return out


UNLISTED = "unlisted:"
AVOID = "avoid:"


def clinician_avoids(h):
    """The movement ids and flags on every "Avoid: <ids or flags>" line under `## Clinician rules`,
    in order, which the session tool rules out on every run."""
    out = []
    for line in _section_lines(h, CLINICIAN_HEADING):
        line = line[2:].strip() if line.startswith(("- ", "* ")) else line.strip()
        if line.lower().startswith(AVOID):
            out += [w.strip() for w in line[len(AVOID):].split(",") if w.strip()]
    return list(dict.fromkeys(out))


def prose_injuries(h):
    """True when `## Active injuries and limitations` lists anything but "None right now" or an
    injury outside the catalog's areas, written "- Unlisted: <what>" (its avoids go under
    `## Clinician rules` as "Avoid: <ids or flags>")."""
    for line in _section_lines(h, INJURIES_HEADING):
        if not line.startswith(("- ", "* ")):
            continue
        item = line[2:].strip()
        if item.rstrip(".").lower() != "none right now" and not item.lower().startswith(UNLISTED):
            return True
    return False


# ---- schema 1 (sweatcast 2.0.x): settings as lines in the prose, kept for migrate.py ----

LEGACY_FEED_RE = re.compile(r"^- (.+?) \((\w+)\):\s*(.+?)\s*$")


def legacy_settings(text):
    """The settings a schema-1 profile held as Markdown lines, as a schema-2 settings dict."""
    settings = {}
    m = re.search(r"^- Measured words per minute[^:]*:\s*(\d+)", text, re.MULTILINE)
    if m:
        settings["words_per_minute"] = int(m.group(1))
    deliver = None
    for line in text.splitlines():
        if line.startswith("- Copy finished MP3s to"):
            _, sep, value = line.partition(":")
            deliver = value.strip() if sep else None
            break
    settings["deliver_to"] = "" if not deliver or placeholder(deliver) else deliver
    for label, key in HANDLE_KEYS.items():
        found = []
        content = "\n".join(line for _, line in section(text, "Content"))
        for scope in (content, text):
            for line in scope.splitlines():
                if line.lstrip("- ").startswith(label):
                    found = re.findall(r"@([\w.-]*[\w-])", line)
                    if found:
                        break
            if found:
                break
        settings[key] = found
    vs, inside = [], False
    for line in text.splitlines():
        if line.startswith("- Voices"):
            inside = True
            continue
        if inside:
            if line.startswith("  - "):
                name, _, desc = line[4:].partition(":")
                vs.append({"name": name.strip(), "description": desc.strip()})
            elif not line.startswith("  "):
                break
    settings["voices"] = vs
    feeds = []
    for _, line in section(text, "Feeds"):
        m = LEGACY_FEED_RE.match(line)
        if m and m.group(2).lower() in FEED_KINDS:
            feeds.append({"label": m.group(1), "kind": m.group(2).lower(), "value": m.group(3)})
    settings["feeds"] = feeds
    return settings


LEGACY_LINE_PREFIXES = ("- Copy finished MP3s to", "- Measured words per minute", "- Voices",
                        "- YouTube favorites", "- Puzzles")
SETTINGS_NOTE = ("The settings the tools read (voices, where MP3s are copied, words per minute, YouTube "
                 "channels, puzzles and feeds) are in the `+++` block at the top of this file.")


def legacy_body(text):
    """A schema-1 profile's prose without the lines the settings block now holds: those
    setting lines (with their indented continuation lines), the Feeds section, and the
    old note about keeping line formats; plus one sentence saying where they went."""
    lines, out, i = text.splitlines(), [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(LEGACY_LINE_PREFIXES) or line.startswith("Keep the line formats as they are"):
            i += 1
            while i < len(lines) and lines[i].startswith((" ", "\t")) and lines[i].strip():
                i += 1
            continue
        if line.strip().lower() == "## feeds":
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        out.append(line)
        i += 1
    title = next((n for n, line in enumerate(out) if line.startswith("# ")), None)
    if SETTINGS_NOTE in out:
        pass
    elif title is not None:
        out[title + 1:title + 1] = ["", SETTINGS_NOTE]
    else:
        out[:0] = [SETTINGS_NOTE, ""]
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.rstrip("\n") + "\n"


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
        if any("|" in t or "\n" in t for t in texts):
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


# ---- check ----------------------------------------------------------------------------

class Issue(NamedTuple):
    path: str
    line: int        # 0 means the whole file
    message: str
    note: bool = False   # True: worth knowing, but nothing breaks


BODY_HINT_RE = re.compile(r"^\s*- ([^:\[\]]+):\s*\[")   # "- Neighborhood: [neighborhood, city]"


def _check_profile(path, text):
    out = []
    try:
        settings, rest = front(text)
    except SystemExit as e:
        return [Issue(path, 1, str(e.code))]
    offset = len(text.splitlines()) - len(rest.splitlines())
    p = Profile(settings, rest, path)
    if not voices(p):
        out.append(Issue(path, 0, "no voices: add a [[voices]] entry (name and description); the first is the default"))
    if wpm(p) is None:
        out.append(Issue(path, 0, "no words_per_minute (./sweatcast lint without a voice assumes 185)", note=True))
    if not delivery_patterns(Profile(settings, rest, path)):
        out.append(Issue(path, 0, "no deliver_to folder, so finished MP3s stay in me/workouts/", note=True))
    for i, f in enumerate(settings.get("feeds") or [], 1):
        if not isinstance(f, dict):
            continue
        kind = str(f.get("kind", "")).lower()
        name = f.get("label") or f"feed {i}"
        if kind not in FEED_KINDS:
            out.append(Issue(path, 0, f"feed '{name}': unknown kind '{f.get('kind', '')}' "
                                      f"(one of {', '.join(FEED_KINDS)})"))
        elif unfilled(f.get("value")) or unfilled(f.get("label")):
            out.append(Issue(path, 0, f"feed '{name}' isn't filled in yet ({kind}: "
                                      f"{f.get('value') or 'no value'}); fill it in or remove it"))
    if not feed_sources(p):
        out.append(Issue(path, 0, "no feeds, so research searches for everything", note=True))
    for key in HANDLE_KEYS.values():
        for h in settings.get(key) or []:
            if placeholder(h):
                out.append(Issue(path, 0, f"{key}: '{h}' isn't filled in yet"))
    cat = _catalog()
    if experience(p) is None:
        out.append(Issue(path, 0, "no experience level: novice, experienced or advanced", note=True))
    if listener_name(p) is None:
        out.append(Issue(path, 0, "no name: the coach can't greet the listener by name", note=True))
    if cat:
        for key in ("likes", "dislikes"):
            for name in _names(p, key):
                if not catalog.resolve(cat, name):
                    out.append(Issue(path, 0, f"{key}: '{name}' isn't a movement in the catalog", note=True))
        for kit, equipment in kits(p).items():
            for e in equipment:
                if e not in cat.equipment:
                    out.append(Issue(path, 0, f"kit '{kit}': '{e}' isn't equipment in the catalog", note=True))
    for k in settings.get("kits") or []:
        if isinstance(k, dict):
            for problem in _weight_problems(k):
                out.append(Issue(path, 0, f"kit '{k.get('name', '?')}': {problem}"))
    for n, line in enumerate(rest.splitlines(), 1):
        m = BODY_HINT_RE.match(line)
        if m:
            out.append(Issue(path, n + offset, f"'{m.group(1).strip()}' isn't filled in yet "
                                               "(still the template's [hint]); fill it in or delete the line"))
    return out


def _catalog():
    try:
        return catalog.load()
    except (SystemExit, ValueError, OSError):
        return None   # the catalog's own check says what's wrong


def _check_health(path, text):
    try:
        settings, rest = front(text)
    except SystemExit as e:
        return [Issue(path, 1, str(e.code))]
    h = Health(settings, rest, path)
    cat = _catalog()
    out = []
    rows = settings.get("limits") or []
    if not isinstance(rows, list):
        return [Issue(path, 0, "limits must be written as [[limits]] tables")]
    for i, row in enumerate(rows, 1):
        if cat:
            _, problem = _limit_row(row, cat.areas, cat.flags)
            if problem:
                out.append(Issue(path, 0, f"[[limits]] row {i}: {problem}; the row is ignored"))
            elif isinstance(row, dict):
                for mid in row.get("rehab") or []:
                    m = cat.movements.get(mid)
                    if m is None or m.draft:
                        out.append(Issue(path, 0, f"[[limits]] row {i}: rehab '{mid}' isn't a movement "
                                                  "in the catalog (or is still a draft)", note=True))
                    elif not m.rehab:
                        out.append(Issue(path, 0, f"[[limits]] row {i}: rehab '{mid}' isn't a rehab movement, "
                                                  "so naming it lets nothing through; name only rehab "
                                                  "movements, or loosen the limit itself"))
    if cat:
        for word in clinician_avoids(h):
            if word not in cat.movements and word not in cat.flags:
                out.append(Issue(path, 0, f"Avoid: '{word}' isn't a movement id or flag in the catalog, "
                                          "so it rules nothing out"))
    if cat and prose_injuries(h) and not limits(h, cat.areas, cat.flags):
        out.append(Issue(path, 0, "injuries written in prose have no [[limits]] entry, so the session "
                                  "tool applies no rule for them"))
    return out


def check(home_files=None):
    """[Issue] across the context files: schema, the formats the tools read, and
    template lines not filled in yet. Issues with note=True don't stop anything."""
    out = []
    for path in home_files or files():
        if not os.path.exists(path):
            out.append(Issue(path, 0, "missing; ./sweatcast setup copies it from me.example/"))
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        problem = schema_problem(path, text)
        if problem:
            out.append(Issue(path, 0, problem))
            continue
        name = os.path.basename(path)
        if name == "profile.md":
            out += _check_profile(path, text)
        elif name == "health.md":
            out += _check_health(path, text)
        elif name == "log.md":
            rest = body(text)
            offset = len(text.splitlines()) - len(rest.splitlines())
            if not any(line.strip().lower() == "## sessions" for line in rest.splitlines()):
                out.append(Issue(path, 0, "no '## Sessions' heading"))
            for n, line in section(rest, "Sessions"):
                if line.startswith("- "):
                    s = parse_session(line, n)
                    if not isinstance(s, Session):
                        out.append(Issue(path, n + offset, s))
    if home_files is None:
        out += check_movements()
        old = os.path.join(paths.HOME, "exercise-science.md")
        if os.path.exists(old):   # 5.1.0 stopped reading it
            out.append(Issue(old, 0, "no longer used (sessions draw no exercise-science asides now); "
                                     "delete it once anything worth keeping is copied out", note=True))
    return out


def check_movements(path=None):
    """[Issue] for the listener's private movements file (`movements.toml` in the context folder):
    each catalog problem that names one of its entries. None when there is no such file."""
    path = path or paths.MY_MOVEMENTS
    if not os.path.exists(path):
        return []
    try:
        extra = catalog.private_movements(path)
    except (tomllib.TOMLDecodeError, OSError) as e:
        return [Issue(path, 0, f"can't be read: {e}")]
    ids = {str(m.get("id", "")) for m in extra}
    cat = catalog.load(paths.MOVEMENTS, extra=extra)
    return [Issue(path, 0, p) for p in catalog.problems(cat)
            if any(re.search(rf"\b{re.escape(i)}\b", p) for i in ids if i)]


def describe(issue):
    where = f"{show(issue.path)}{f':{issue.line}' if issue.line else ''}"
    return f"{where}: {'note: ' if issue.note else ''}{issue.message}"


# ---- command line ----------------------------------------------------------------------

def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="print one value from the profile (empty when it has none)")
    g.add_argument("what", choices=("default-voice", "wpm", "voices", "experience"))
    sub.add_parser("deliver", help="print the existing delivery folders, one per line")
    sub.add_parser("check", help="check every context file, and list lines not filled in yet")
    s = sub.add_parser("log-session", help="add a session to log.md, checked")
    s.add_argument("--date", default=dt.date.today().isoformat())
    s.add_argument("--minutes", type=int, required=True)
    s.add_argument("--kit", required=True)
    s.add_argument("--voice", required=True)
    s.add_argument("--movements", required=True, help="comma-separated")
    s.add_argument("--topics", required=True)
    s.add_argument("--format", default=None)
    s.add_argument("--loads", default="", help="'<movement> = <load and tempo>; ...'")
    s.add_argument("--rpe", default="", help="'<movement> = <effort>; ...' (kept for progress tracking)")
    args = ap.parse_args(argv)

    if args.cmd == "get":
        p = profile()
        if args.what == "voices":
            for name, _ in voices(p):
                print(name)
        else:
            v = {"default-voice": default_voice, "wpm": wpm, "experience": experience}[args.what](p)
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
    if args.cmd == "check":
        issues = check()
        for issue in issues:
            print(describe(issue))
        problems = [i for i in issues if not i.note]
        if not problems:
            print(f"Context folder {show(paths.HOME)}: schema {SCHEMA}, every file reads as the tools expect.")
        return cli.ISSUES if problems else cli.OK
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
    session = Session(args.date, args.minutes, args.kit.strip(), args.voice.strip(),
                      [m.strip() for m in args.movements.split(",") if m.strip()], args.topics.strip(),
                      (args.format or "").strip() or None, loads, rpe)
    print("Logged: " + append_session(session))
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
