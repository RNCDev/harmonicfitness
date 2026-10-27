"""The text of a context file: its +++ TOML front matter, its ## sections, and the template's hints. Pure text,
no files: tools/store.py reads and writes them, and tools/context.py is where the tools reach both."""
import json
import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402


TOML_FRONT_RE = re.compile(r"\A\+\+\+[ \t]*\n(.*?)\n?\+\+\+[ \t]*\n", re.DOTALL)


def front(text):
    """(settings dict, body); no block gives {}. A `+++` block
    that never closes stops here by name, so nobody is sent to migrate over a missing line."""
    text = text.lstrip("\ufeff")   # a byte order mark, from a Windows editor
    m = TOML_FRONT_RE.match(text)
    if m:
        try:
            return tomllib.loads(m.group(1)), text[m.end():]
        except tomllib.TOMLDecodeError as e:
            raise errors.ContextError(f"The settings block at the top of the file isn't valid TOML: {e}")
    if text.startswith("+++"):
        raise errors.ContextError("the +++ settings block at the top doesn't close: the settings need a line holding "
                         "only +++ after them")
    return {}, text


def wrap(block, rest=""):
    """A file's text from a TOML settings block as written (its comments kept) and the text below it. Refuses
    a block that doesn't parse: nothing is ever written that the tools can't read back."""
    block = block.rstrip("\n")
    tomllib.loads(block)
    return f"+++\n{block}\n+++\n{rest}"


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


def dump_block(plain, tables=None, arrays=None, comments=None):
    """A +++ settings block's TOML (without the +++ lines), the one writer every context file and coach file
    uses: `plain` keys first ({key: value}, in order), then each [table] (`tables`, {name: {key: value}}), then
    each list of tables (`arrays`, {name: [rows]}: [[kits]], [[feeds]]). `comments` ({name: text}) puts a
    "# text" line above a plain key, a [table] or a list of tables (a list's comment stays when it has no
    rows). See wrap for the whole block."""
    comments = comments or {}
    out = []
    for k, v in plain.items():
        if k in comments:
            out.append(f"# {comments[k]}")
        out.append(f"{k} = {toml_value(v)}")
    for name, table in (tables or {}).items():
        out.append("")
        if name in comments:
            out.append(f"# {comments[name]}")
        out.append(f"[{name}]")
        out += [f"{k} = {toml_value(v)}" for k, v in table.items()]
    for name, rows in (arrays or {}).items():
        if name in comments:
            out += ["", f"# {comments[name]}"]
        for row in rows or []:
            out += ["", f"[[{name}]]"] + [f"{rk} = {toml_value(rv)}" for rk, rv in row.items()]
    return "\n".join(out)


def dump_settings(settings, comments=None):
    """Settings as TOML: plain keys first, then each list of tables ([[voices]], [[feeds]])."""
    plain = {k: v for k, v in settings.items() if not (isinstance(v, list) and v and isinstance(v[0], dict))}
    arrays = {k: v for k, v in settings.items() if k not in plain}
    return dump_block(plain, arrays=arrays, comments=comments)


def heading(line):
    """The name of the `## name` heading `line` is (the one rule: stripped, exactly two hashes and a space,
    case-folded), or None for any other line."""
    s = line.strip()
    return s[3:].strip().casefold() if s.startswith("## ") else None


def heading_index(lines, name, start=0):
    """The index in `lines` of the first `## name` heading at or after `start` (case doesn't matter), or None."""
    want = name.strip().casefold()
    return next((i for i in range(start, len(lines)) if heading(lines[i]) == want), None)


def section(text, name):
    """The lines under a `## name` heading (case doesn't matter), up to the next heading, with
    their 1-based line numbers in `text`."""
    out, inside, want = [], False, name.strip().casefold()
    for n, line in enumerate(text.splitlines(), 1):
        found = heading(line)
        if found is not None:
            inside = found == want
            continue
        if inside:
            out.append((n, line))
    return out


def placeholder(value):
    """True for a value still showing me.example's [bracketed] hint."""
    return isinstance(value, str) and value.strip().startswith("[")


def unfilled(value):
    return value is None or (isinstance(value, str) and (not value.strip() or placeholder(value)))
