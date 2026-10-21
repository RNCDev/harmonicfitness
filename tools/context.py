#!/usr/bin/env python3
"""The listener's context files: the one place that reads and writes them.

me/profile.md, health.md, log.md and exercise-science.md are Markdown that Claude
reads and the tools parse. Every tool goes through this module, so a format lives in
one place. Each file opens with front matter naming its format's version:

    ---
    schema: 1
    ---

A file from an older sweatcast (no front matter is schema 0) stops the tools with
the command that brings it up to date, `python3 tools/migrate.py`.

Standard library only, so the skills can run it with the system python3.

    python3 tools/context.py get default-voice     # also: wpm, voices
    python3 tools/context.py deliver               # existing delivery folders, one per line
    python3 tools/context.py check                 # every file's format, with line numbers
    python3 tools/context.py log-session --date 2026-10-21 --minutes 25 --kit Home \\
        --voice "Chatterbox Coach" --movements "goblet squat, seated row" \\
        --topics "deep dive: news, a story" --format "rolling minutes" \\
        --loads "goblet squat = twenties, three down; seated row = fifteens"
"""
import argparse
import datetime as dt
import glob
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402

SCHEMA = 1
FRONT_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)
SCHEMA_RE = re.compile(r"^schema:\s*(\d+)\s*$", re.MULTILINE)
FEED_KINDS = ("weather", "espn", "rss", "weekly", "onthisday")
FEED_RE = re.compile(r"^- (.+?) \((\w+)\):\s*(.+?)\s*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def files():
    """The context files that carry a schema, in the order check() reports them."""
    return [paths.PROFILE, paths.HEALTH, paths.LOG, paths.EXERCISE_SCIENCE]


# ---- schema and front matter ---------------------------------------------------------

def schema_of(text):
    """The schema a file's front matter names; 0 when it has none (before 2.0.0)."""
    m = FRONT_RE.match(text)
    if not m:
        return 0
    s = SCHEMA_RE.search(m.group(1))
    return int(s.group(1)) if s else 0


def body(text):
    """A file's text without its front matter."""
    m = FRONT_RE.match(text)
    return text[m.end():] if m else text


def with_front_matter(text, schema=SCHEMA):
    """Text with front matter naming `schema`, replacing any it already has."""
    return f"---\nschema: {schema}\n---\n" + body(text)


def schema_problem(path, text):
    """A sentence saying why this file's schema won't do, or None."""
    found = schema_of(text)
    if found == SCHEMA:
        return None
    if found < SCHEMA:
        return (f"{show(path)} is in an older sweatcast format (schema {found}; this engine reads "
                f"schema {SCHEMA}). Bring the context folder up to date with: python3 tools/migrate.py")
    return (f"{show(path)} is in a newer format (schema {found}) than this engine reads (schema {SCHEMA}). "
            "Pull the latest sweatcast.")


def read(path, what="file"):
    """A context file's text, without front matter, after checking its schema."""
    with open(paths.require(path, what), encoding="utf-8") as f:
        text = f.read()
    problem = schema_problem(path, text)
    if problem:
        raise SystemExit(problem)
    return body(text)


def write(path, text):
    """Replace a context file's text atomically, keeping its front matter."""
    with open(path, encoding="utf-8") as f:
        current = f.read()
    m = FRONT_RE.match(current)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write((m.group(0) if m else "") + text)
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


# ---- the profile -----------------------------------------------------------------------

def profile(path=None):
    return read(path or paths.PROFILE, "profile")


def placeholder(value):
    """True for a value still showing me.example's [bracketed] hint."""
    return value.startswith("[")


def bullet(text, label):
    """The value after `- <label>...:` on the first such line, or None."""
    for line in text.splitlines():
        if line.startswith("- " + label):
            _, sep, value = line.partition(":")
            if sep:
                return value.strip()
    return None


def wpm(text):
    """The drafting guide's words per minute ("- Measured words per minute ...: 165"), or None."""
    m = re.search(r"^- Measured words per minute[^:]*:\s*(\d+)", text, re.MULTILINE)
    return int(m.group(1)) if m else None


def voices(text):
    """[(name, description)] from the `- Voices` list; the first is the default."""
    out, inside = [], False
    for line in text.splitlines():
        if line.startswith("- Voices"):
            inside = True
            continue
        if inside:
            if line.startswith("  - "):
                name, _, desc = line[4:].partition(":")
                out.append((name.strip(), desc.strip()))
            elif not line.startswith("  "):
                break
    return out


def default_voice(text):
    found = voices(text)
    return found[0][0] if found else None


def delivery(text):
    """The "Copy finished MP3s to:" value with ~ expanded, or None (no line, or the hint)."""
    value = bullet(text, "Copy finished MP3s to")
    if not value or placeholder(value):
        return None
    return os.path.expanduser(value)


def delivery_folders(text):
    """(pattern, [existing folders it matches]); * in the pattern matches anything."""
    pattern = delivery(text)
    if not pattern:
        return None, []
    found = sorted(glob.glob(pattern)) if glob.has_magic(pattern) else [pattern]
    return pattern, [d for d in found if os.path.isdir(d)]


def feed_sources(text):
    """[(label, kind, value)] from the profile's Feeds section."""
    out = []
    for _, line in section(text, "Feeds"):
        m = FEED_RE.match(line)
        if m and m.group(2).lower() in FEED_KINDS:
            out.append((m.group(1), m.group(2).lower(), m.group(3)))
    return out


def handles(text, label):
    """The @handles on the line starting with `label` (such as "YouTube favorites" or
    "Puzzles"), looked for under Content first, then anywhere."""
    content = "\n".join(line for _, line in section(text, "Content"))
    for scope in (content, text):
        for line in scope.splitlines():
            if line.lstrip("- ").startswith(label):
                found = re.findall(r"@([\w.-]*[\w-])", line)   # not a sentence's final period
                if found:
                    return found
    return []


# ---- the log ---------------------------------------------------------------------------

@dataclass
class Session:
    """One line under `## Sessions` in log.md:
    - <date> | <N> min | <kit> | <voice> | <movements> | <topics> | format: <format> | loads: <m> = <load>; ..."""
    date: str
    minutes: int
    kit: str
    voice: str
    movements: List[str]
    topics: str
    format: Optional[str] = None
    loads: Dict[str, str] = field(default_factory=dict)
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
                 *self.loads.keys(), *self.loads.values()]
        if any("|" in t or "\n" in t for t in texts):
            out.append("a field contains | or a line break")
        if any("," in m for m in self.movements):
            out.append("a movement contains a comma")
        if any(";" in t or "=" in t for t in [*self.loads.keys(), *self.loads.values()]):
            out.append("a load contains ; or =")
        return out

    def to_line(self):
        out = (f"- {self.date} | {self.minutes} min | {self.kit} | {self.voice} | "
               f"{', '.join(self.movements)} | {self.topics}")
        if self.format:
            out += f" | format: {self.format}"
        if self.loads:
            out += " | loads: " + "; ".join(f"{k} = {v}" for k, v in self.loads.items())
        return out


def parse_session(line, lineno=0):
    """A log line as a Session, or a sentence saying why it isn't one."""
    fields = [x.strip() for x in line[2:].split("|")]
    if len(fields) < 6:
        return (f"{len(fields)} fields; a session line has date, length, kit, voice, movements "
                "and topics, then format and loads")
    m = re.match(r"^(\d+)\s*min", fields[1])
    s = Session(fields[0], int(m.group(1)) if m else fields[1], fields[2], fields[3],
                [x.strip() for x in fields[4].split(",") if x.strip()], fields[5], line=lineno)
    for extra in fields[6:]:
        key, _, value = extra.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "format" and value:
            s.format = value
        elif key == "loads":
            for item in value.split(";"):
                mv, _, load = item.partition("=")
                if mv.strip() and load.strip():
                    s.loads[mv.strip()] = load.strip()
        elif extra.strip():
            return f"unknown field '{extra.strip()[:30]}'; only format: and loads: follow the topics"
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
                print(f"Skipped {show(path)} session line {n} (counting after the front matter): {s}. "
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

def check(home_files=None):
    """[(path, line, problem)] across the context files: schema, then the formats the
    tools read. Line 0 means the whole file."""
    out = []
    for path in home_files or files():
        if not os.path.exists(path):
            out.append((path, 0, "missing; tools/setup.sh copies it from me.example/"))
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        problem = schema_problem(path, text)
        if problem:
            out.append((path, 0, problem))
            continue
        offset = len(text.splitlines()) - len(body(text).splitlines())
        text = body(text)
        if os.path.basename(path) == "profile.md":
            if not voices(text):
                out.append((path, 0, "no '- Voices' list with indented '  - <name>: ...' lines"))
            if wpm(text) is None:
                out.append((path, 0, "no '- Measured words per minute ...: <n>' line (the guide assumes 185)"))
            for n, line in section(text, "Feeds"):
                m = FEED_RE.match(line)
                if line.startswith("- ") and not m:
                    out.append((path, n + offset, "a Feeds line isn't '- <label> (<kind>): <value>'"))
                elif m and m.group(2).lower() not in FEED_KINDS:
                    out.append((path, n + offset, f"unknown feed kind '{m.group(2)}' "
                                                  f"(one of {', '.join(FEED_KINDS)})"))
        if os.path.basename(path) == "log.md":
            if not any(line.strip().lower() == "## sessions" for line in text.splitlines()):
                out.append((path, 0, "no '## Sessions' heading"))
            for n, line in section(text, "Sessions"):
                if line.startswith("- "):
                    s = parse_session(line, n)
                    if not isinstance(s, Session):
                        out.append((path, n + offset, s))
    return out


# ---- command line ----------------------------------------------------------------------

def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("get", help="print one value from the profile (empty when it has none)")
    g.add_argument("what", choices=("default-voice", "wpm", "voices"))
    sub.add_parser("deliver", help="print the existing delivery folders, one per line")
    sub.add_parser("check", help="check every context file's format")
    s = sub.add_parser("log-session", help="add a session to log.md, checked")
    s.add_argument("--date", default=dt.date.today().isoformat())
    s.add_argument("--minutes", type=int, required=True)
    s.add_argument("--kit", required=True)
    s.add_argument("--voice", required=True)
    s.add_argument("--movements", required=True, help="comma-separated")
    s.add_argument("--topics", required=True)
    s.add_argument("--format", default=None)
    s.add_argument("--loads", default="", help="'<movement> = <load and tempo>; ...'")
    args = ap.parse_args(argv)

    if args.cmd == "get":
        text = profile()
        value = {"default-voice": default_voice, "wpm": wpm}.get(args.what)
        if value:
            v = value(text)
            if v is not None:
                print(v)
        else:
            for name, _ in voices(text):
                print(name)
        return cli.OK
    if args.cmd == "deliver":
        pattern, found = delivery_folders(profile())
        if not pattern:
            print("No copy made: the profile has no '- Copy finished MP3s to: <folder>' line.", file=sys.stderr)
        elif not found:
            print(f"Delivery folder {pattern} not found.", file=sys.stderr)
        for d in found:
            print(d)
        return cli.OK
    if args.cmd == "check":
        problems = check()
        for path, n, msg in problems:
            print(f"{show(path)}{f':{n}' if n else ''}: {msg}")
        if not problems:
            print(f"Context folder {show(paths.HOME)}: schema {SCHEMA}, every format as the tools expect.")
        return cli.ISSUES if problems else cli.OK
    loads = {}
    for item in args.loads.split(";"):
        mv, sep, load = item.partition("=")
        if item.strip() and not (sep and mv.strip() and load.strip()):
            raise SystemExit(f"Not logged: load '{item.strip()}' isn't '<movement> = <load and tempo>'.")
        if sep:
            loads[mv.strip()] = load.strip()
    session = Session(args.date, args.minutes, args.kit.strip(), args.voice.strip(),
                      [m.strip() for m in args.movements.split(",") if m.strip()], args.topics.strip(),
                      (args.format or "").strip() or None, loads)
    print("Logged: " + append_session(session))
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
