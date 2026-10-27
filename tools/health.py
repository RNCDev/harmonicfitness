"""The health file (me/health.md): its [[limits]] rows, which the brief applies as rules, its ## Clinician rules,
followed literally, and the injuries its prose names, so a story without a row is flagged."""
from dataclasses import dataclass
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import errors  # noqa: E402
import paths  # noqa: E402
from frontmatter import front, section, placeholder  # noqa: E402
from store import schema_problem, read_raw  # noqa: E402


HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
INJURIES_HEADING = "Active injuries and limitations"
CLINICIAN_HEADING = "Clinician rules"
LIMIT_SIDES, LIMIT_LEVELS = catalog.LIMIT_SIDES, catalog.LIMIT_LEVELS


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
        raise errors.ContextError(problem)
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
