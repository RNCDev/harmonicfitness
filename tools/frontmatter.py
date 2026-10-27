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
