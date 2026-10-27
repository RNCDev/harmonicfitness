"""The session log (me/log.md): one checked line per session under ## Sessions, read back for coverage and the
check-in, and the listener's feedback under ## Feedback."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402
from frontmatter import section  # noqa: E402
from store import read, write  # noqa: E402


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINE_BREAKS = "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029"   # every character str.splitlines breaks on


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
        raise errors.LogRefused("Not logged: " + "; ".join(problems) + ".")
    path = path or paths.LOG
    lines = log(path).splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip().lower() == "## sessions"), None)
    if start is None:
        raise errors.ContextError(f"No '## Sessions' heading in {show(path)}.")
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
