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
older schema stops the tools with the command that brings it up to date, `./harmonicfitness migrate`.

    ./harmonicfitness get coach             # also: route, routes, wpm, experience, web-builds
    ./harmonicfitness get web-builds --json # {"web_builds": 3}: any get value as JSON
    ./harmonicfitness deliver               # existing delivery folders, one per line
    ./harmonicfitness check                 # every file's format, and lines not filled in yet
    ./harmonicfitness log-session --draft me/workouts/<stem>/<stem>.draft.txt \\
        --coach "Coach Andy" --format straight-sets --topics "deep dive: news, a story" \\
        --loads "goblet squat = twenties, three down; seated row = fifteens" --rpe "goblet squat = 7"
                                      # the date, length and kit come from the draft's menu; the draft
                                      # must have been built as it stands, and a session is logged once
    ./harmonicfitness log-session --date 2026-10-21 --minutes 25 --kit Home \\
        --coach "Coach Andy" --movements "goblet squat, seated row" --topics "..."   # without a draft
"""
import argparse
import glob
import json
import os
import sys
import tomllib   # Python 3.11: ./harmonicfitness runs every tool in the project's environment
from dataclasses import dataclass, field
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import errors  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402
# the readers that moved out by job (frontmatter, store, health, sessionlog, records) are reached in their own
# modules; context imports only what it uses
import frontmatter  # noqa: E402
from frontmatter import front, toml_value, section, placeholder, unfilled  # noqa: E402
from store import PERSONA_SCHEMA, split, schema_problem, read_raw  # noqa: E402
from sessionlog import log  # noqa: E402
from records import web_builds  # noqa: E402

FEED_KINDS = ("weather", "espn", "rss", "weekly", "onthisday", "wikipedia")
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


# ---- front matter --------------------------------------------------------------------


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
            raise errors.ContextError(problem)
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


# ---- the shapes settings come in ----------------------------------------------------------------
# Settings are hand-edited, so each reader takes them through these, and ./harmonicfitness check reports what they
# had to forgive (shape_issues). A bare string where a list belongs reads as a one-item list, never as its
# letters; a single [table] where [[tables]] belong reads as one row.

NAME_LISTS = ("likes", "dislikes", "youtube_favorites", "puzzles")   # a list of text
ONE_OR_LIST = ("render", "deliver_to")                                # a text or a list of them, both meant
TABLE_LISTS = ("kits", "interests", "feeds")   # [[tables]] ([[limits]] is stricter: limit_rows refuses a bad one)
SHAPED = (*NAME_LISTS, *ONE_OR_LIST, *TABLE_LISTS)


def str_list(value):
    """A setting as a list of text: a bare string is one item; anything not text is dropped."""
    if isinstance(value, str):
        return [value]
    return [x for x in value if isinstance(x, str)] if isinstance(value, list) else []


def table_list(value):
    """A setting as a list of tables: a single table is one row; anything not a table is dropped."""
    if isinstance(value, dict):
        return [value]
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def shape_problems(settings, keys=None):
    """[(key, message, note)] for settings not in the shape their reader expects: what the reader forgave
    (a note) or had to drop (an issue)."""
    out = []
    for key in SHAPED if keys is None else keys:
        if key not in settings:
            continue
        v = settings[key]
        if key in NAME_LISTS:
            if isinstance(v, str):
                out.append((key, f'{key} is one name; write it as a list, {key} = ["{v}"] (read as one for now)', True))
            elif not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                out.append((key, f'{key} should be a list of names, such as ["..."]; what isn\'t text is ignored', False))
        elif key in ONE_OR_LIST:
            if not isinstance(v, str) and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                out.append((key, f'{key} should be text or a list of text; what isn\'t text is ignored', False))
        elif key in TABLE_LISTS:
            if isinstance(v, dict):
                out.append((key, f"write [[{key}]] (two brackets) for each row; [{key}] is read as one row for now", True))
            elif not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
                out.append((key, f"each {key} row should be a [[{key}]] table; what isn't one is ignored", False))
    return out


def routes(p):
    """The profile's render preference list (default ["local"]): each build takes the first that works here."""
    found = [v.strip().lower() for v in str_list(p.settings.get("render")) if v.strip()]
    return found or ["local"]


class Issue(NamedTuple):
    """One thing ./harmonicfitness check reports (tools/check.py): where, and whether anything breaks."""
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


# The single-valued settings and what each may hold: (int, least, most) for a whole number (a bool is never one),
# or (choices,) for text (read stripped and casefolded; "" means unset). ./harmonicfitness check reports any other value
# (scalar_problems), and the readers below refuse one rather than quietly using the default: a spending cap
# written "5000", in quotes, must never read as the default's 30,000.
SCALARS = {
    "cloud_max_chars": (int, 1, None),
    "words_per_minute": (int, 60, 300),
    "setup": (("quick", "full"),),
    "experience": ("catalog.LEVELS",),   # read when checked: catalog loads the movement catalog
}


def _shown(v):
    try:
        return toml_value(v)
    except TypeError:
        return repr(v)


def _scalar_problem(key, v):
    """Why `v` can't be `key`'s value (SCALARS), or None when it can."""
    rule = SCALARS[key]
    if rule[0] is int:
        _, least, most = rule
        if type(v) is not int:   # bool is an int subclass: true is never a number of characters
            return f"{key} should be a whole number, written without quotes, not {_shown(v)}"
        if v < least or (most is not None and v > most):
            span = f"at least {least}" if most is None else f"from {least} to {most}"
            return f"{key} should be {span}, not {v}"
        return None
    choices = rule[0]
    if choices == "catalog.LEVELS":
        import catalog
        choices = catalog.LEVELS
    if not isinstance(v, str):
        return f"{key} should be one of {', '.join(choices)}, in quotes, not {_shown(v)}"
    if v.strip() and v.strip().casefold() not in choices:
        return f"{key} should be one of {', '.join(choices)}, not {_shown(v)}"
    return None


def scalar_problems(settings):
    """[(key, message, note)] for the single-valued settings (SCALARS) set to a value their reader refuses, as
    shape_problems gives them; each is an issue (note False): the setting doesn't apply as written."""
    out = []
    for key in SCALARS:
        if key in settings:
            problem = _scalar_problem(key, settings[key])
            if problem:
                out.append((key, problem, False))
    return out


def _scalar(p, key):
    """`key`'s value from the profile, None when unset; a value set but not one SCALARS allows raises
    errors.ContextError naming it, never a quiet fallback to the default."""
    if key not in p.settings:
        return None
    problem = _scalar_problem(key, p.settings[key])
    if problem:
        where = (p.sources or {}).get(key) or SETTING_HOMES.get(key, "settings.toml")
        raise errors.ContextError(f"{show(where) if os.path.isabs(where) else where}: {problem} (./harmonicfitness check lists what else needs fixing).")
    return p.settings[key]


def cloud_max_chars(p):
    """The most characters one build may send to a cloud voice, from cloud_max_chars (default 30,000); a value
    that isn't a whole number of at least 1 raises errors.ContextError."""
    v = _scalar(p, "cloud_max_chars")
    return CLOUD_MAX_CHARS if v is None else v


def wpm(p):
    """The profile's rough speaking rate (words_per_minute), or None when unset; a value that isn't a whole
    number from 60 to 300 raises errors.ContextError."""
    return _scalar(p, "words_per_minute")


def delivery_patterns(p):
    """The deliver_to folders with ~ expanded: one string, or a list of them (say one per
    computer, a Mac's Google Drive path and a Windows PC's); unset or hint lines dropped."""
    return [os.path.expanduser(v.strip()) for v in str_list(p.settings.get("deliver_to")) if not unfilled(v)]


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


def delivery_note(p):
    """What to say when the profile names a delivery folder and none of it is on this computer, else None."""
    pattern, found = delivery_folders(p)
    return f"Delivery folder {pattern} not found." if pattern and not found else None


def feed_sources(p):
    """[(label, kind, value)] from [[feeds]], skipping entries not filled in yet."""
    out = []
    for f in table_list(p.settings.get("feeds")):
        label, kind, value = (str(f.get(k, "")).strip() for k in ("label", "kind", "value"))
        if kind.lower() in FEED_KINDS and not unfilled(value) and not unfilled(label):
            out.append((label, kind.lower(), value))
    return out


def handles(p, label):
    """The @handles for "YouTube favorites" or "Puzzles" (youtube_favorites, puzzles)."""
    key = HANDLE_KEYS.get(label, label)
    return [h.strip().lstrip("@") for h in str_list(p.settings.get(key)) if not unfilled(h)]


def experience(p):
    """The listener's level, one of catalog.LEVELS, or None (unset or unrecognised)."""
    v = p.settings.get("experience")
    import catalog
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
    for row in table_list(p.settings.get("interests")):
        if not unfilled(row.get("name")) and not unfilled(row.get("slot")):
            out.append((str(row["name"]).strip(), str(row["slot"]).strip(), str(row.get("detail") or "").strip()))
    return out


def _names(p, key):
    return [x.strip() for x in str_list(p.settings.get(key)) if x.strip()]


def likes(p):
    """Movement ids or names the listener likes."""
    return _names(p, "likes")


def dislikes(p):
    """Movement ids or names the listener dislikes."""
    return _names(p, "dislikes")


def kits(p):
    """{kit name: equipment ids} from [[kits]], as written."""
    return {k["name"].strip(): str_list(k.get("equipment"))
            for k in table_list(p.settings.get("kits")) if isinstance(k.get("name"), str) and k["name"].strip()}


UNITS = ("lb", "kg")


def _weight(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def kit_weight_table(k):
    """(unit, {equipment id: sorted weights}, problems) for one [[kits]] table's optional `weights` (equipment
    id = list of numbers) and `unit` ("lb" by default): what the brief uses, and, as sentences, what it had to
    leave out, which ./harmonicfitness check reports. One reading, so the two can't disagree."""
    problems, table = [], {}
    w = k.get("weights")
    if w is not None and not isinstance(w, dict):
        problems.append("weights should be a table, such as { dumbbells = [10, 15, 20] }")
    for e, ws in (w.items() if isinstance(w, dict) else []):
        if e not in str_list(k.get("equipment")):
            problems.append(f"weights lists '{e}', which isn't in the kit's equipment")
        if not isinstance(ws, list) or not ws or not all(_weight(x) for x in ws):
            problems.append(f"weights for '{e}' should be a list of numbers above zero")
        good = sorted(x for x in ws if _weight(x)) if isinstance(ws, list) else []
        if good:
            table[e] = good
    if "unit" in k and k["unit"] not in UNITS:
        problems.append(f"unit should be {' or '.join(UNITS)}")
    return (k.get("unit") if k.get("unit") in UNITS else "lb"), table, problems


def kit_weights(p):
    """{kit name: (unit, {equipment id: sorted weights})} for the kits that give any weights."""
    out = {}
    for k in table_list(p.settings.get("kits")):
        if isinstance(k.get("name"), str):
            unit, table, _ = kit_weight_table(k)
            if table:
                out[k["name"].strip()] = (unit, table)
    return out


def kit_problems(k):
    """Faults in one [[kits]] table, as sentences: its equipment's shape, and its weights and unit."""
    out = []
    e = k.get("equipment")
    if isinstance(e, str):
        out.append(f'equipment is one item; write it as a list, equipment = ["{e}"] (read as one for now)')
    elif e is not None and not (isinstance(e, list) and all(isinstance(x, str) for x in e)):
        out.append("equipment should be a list of equipment ids, such as [\"dumbbells\"]")
    return out + kit_weight_table(k)[2]


SETTINGS_COMMENTS = {
    "words_per_minute": "A rough speaking rate (./harmonicfitness get wpm prints it); builds use each coach's measured pace.",
    "experience": "Your training level: novice, experienced or advanced. The brief's menu of movements matches it; until set, it assumes novice.",
    "likes": "Movements you enjoy (ids or names from ./harmonicfitness movements); sessions favour them.",
    "dislikes": "Movements to leave out (ids or names); the brief's menu never lists them.",
    "deliver_to": "Where finished MP3s go: a folder that syncs to your phone. ~ is your home folder and * "
                  "matches anything (any Google account). Once the copy is there the local MP3 is removed; "
                  "empty keeps MP3s in me/workouts/. A list gives one folder per computer; each copies to those it has.",
    "youtube_favorites": "Channels (@handles) for the deep dives retold from a video's transcript.",
    "puzzles": "Channels (@handles) whose puzzles can be the session's quiz.",
    "interests": "What the filler between exercises rotates through: a name, its slot (today, science, "
                 "deep_dive, quiz, delight or learn; knowledge/content.toml) and a detail for research. Within "
                 "a slot, the one told longest ago comes next. Without any, knowledge/content.toml's defaults.",
    "feeds": "Fetched by ./harmonicfitness feeds at the start of each session. Kinds: weather (latitude, "
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
    "fish": "Fish Audio: the model (a web voice; ./harmonicfitness keys).",
    "gemini": "Gemini: the model (a web voice; ./harmonicfitness keys).",
    "inworld": "Inworld: the model (a web voice; ./harmonicfitness keys).",
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
        raise errors.ContextError(f"{show(path)} is schema {found}; this engine reads coaches at schema {PERSONA_SCHEMA}: "
                         + ("run ./harmonicfitness migrate." if older else "pull the latest harmonicfitness."))
    return Persona(settings, rest, path)


def persona_text(settings, prose):
    """A persona.md: the settings block (plain keys, then one [table] each: an engine's, [voice], [character]),
    then the prose."""
    plain = {"schema": PERSONA_SCHEMA}
    plain.update((k, v) for k, v in settings.items() if k != "schema" and not isinstance(v, dict))
    tables = {k: v for k, v in settings.items() if isinstance(v, dict)}
    block = frontmatter.dump_block(plain, tables=tables,
                                   comments={k: PERSONA_COMMENTS[k] for k in tables if k in PERSONA_COMMENTS})
    return frontmatter.wrap(block, prose if prose.endswith("\n") or not prose else prose + "\n")


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


# ---- the log ---------------------------------------------------------------------------


# ---- command line ----------------------------------------------------------------------

def _get(args, p):
    """The value `get` prints: a str, an int, a list (routes) or None (nothing set)."""
    if args.what == "coach":
        import coachpick
        coach = coachpick.default()
        return coach.name if coach else None
    if args.what == "web-builds":
        return web_builds()
    if args.what == "routes":
        return list(routes(p))
    if args.what == "route":
        import coachpick
        # an unknown coach, a web coach with no key here or a bad --engine exit 64 through cli.run
        return coachpick.pick(routes(p), coachpick.coach(args.coach), override=args.engine)
    return {"wpm": wpm, "experience": experience}[args.what](p)


def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="print one value from the profile (empty when it has none)")
    g.add_argument("what", choices=("wpm", "experience", "route", "routes", "coach", "web-builds"),
                   help="web-builds: how many builds have sent a script to a web voice service")
    g.add_argument("--coach", help="with route: the coach the build is for (default: the last one used)")
    g.add_argument("--route", "--engine", dest="engine", metavar="ROUTE",
                   help="with route: a route to use if it works here (--engine is the older name)")
    g.add_argument("--json", action="store_true",
                   help='the value as one JSON object keyed by its name, "-" as "_": {"web_builds": 3}, '
                        '{"routes": ["local"]}, {"coach": null} when there is none')
    sub.add_parser("deliver", help="print the existing delivery folders, one per line")
    s = sub.add_parser("log-session", help="add a session to log.md, checked")
    s.add_argument("--draft", help="the built draft: its movements: line gives the movements, and its menu the "
                                   "date, length and kit (a build of this exact draft must exist)")
    s.add_argument("--date", help="YYYY-MM-DD (default: the menu's date with --draft, else today)")
    s.add_argument("--minutes", type=cli.positive_int, help="required without --draft")
    s.add_argument("--kit", help="required without --draft")
    s.add_argument("--coach", dest="voice", help="the session's coach (with --draft, default: the build's; one "
                                                 "that disagrees with the build is refused)")
    s.add_argument("--movements", help="comma-separated, without --draft")
    s.add_argument("--topics", required=True)
    s.add_argument("--format", default=None, help="the session method (required with --draft)")
    s.add_argument("--loads", default="", help="'<movement> = <load and tempo>; ...'")
    s.add_argument("--rpe", default="", help="'<movement> = <effort>; ...' (kept for progress tracking)")
    args = ap.parse_args(argv)

    if args.cmd == "get":
        p = profile()
        value = _get(args, p)
        if args.json:
            print(json.dumps({args.what.replace("-", "_"): value}, ensure_ascii=False))
        elif isinstance(value, list):
            print("\n".join(value))
        elif value is not None:
            print(value)
        return cli.OK
    if args.cmd == "deliver":
        p = profile()
        pattern, found = delivery_folders(p)
        missing = delivery_note(p)
        if not pattern:
            print("No copy made: the profile's settings have no deliver_to folder.", file=sys.stderr)
        elif missing:
            print(missing, file=sys.stderr)
        for d in found:
            print(d)
        return cli.OK
    import logsession
    print(logsession.log_session(
        topics=args.topics, draft=args.draft, date=args.date, minutes=args.minutes, kit=args.kit, coach=args.voice,
        movements=args.movements, fmt=args.format, loads=args.loads, rpe=args.rpe))
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
