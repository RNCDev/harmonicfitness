"""The context folder's files on disk: read, written and held to their schema (SCHEMA for the context files,
PERSONA_SCHEMA for a coach's persona.md). A file at an older schema stops a tool with ./sweatcast migrate."""
import os
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402
from frontmatter import TOML_FRONT_RE, front, body, dump_settings  # noqa: E402


SCHEMA = 6   # 6 (0.12.0) splits the profile into profile.md, training.md, content.md and settings.toml
PERSONA_SCHEMA = 5   # me/coaches/<slug>/persona.md (me/personas/ before 0.15.0), new in sweatcast 0.9; 5 (0.10.0) adds kind and web coaches


def split(path, text):
    """(settings, prose) of any context file: a .toml file is all settings; the others have a +++ block."""
    try:
        if path.endswith(".toml"):
            return tomllib.loads(text), ""
        return front(text)
    except tomllib.TOMLDecodeError as e:
        raise errors.ContextError(f"{show(path)} isn't valid TOML: {e}")
    except errors.PROBLEMS as e:
        raise errors.ContextError(f"{show(path)}: {e.code}")


def schema_of(text, path=None):
    """The schema a file's front matter (or a .toml file's `schema` key) names; 0 when it has none."""
    try:
        settings, _ = split(path or "", text)
    except errors.PROBLEMS:
        return SCHEMA   # a TOML block, just a broken one: check() says what's wrong
    try:
        return int(settings.get("schema", 0))
    except (TypeError, ValueError):
        return 0


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
        raise errors.ContextError(problem)
    return body(text)


def write(path, text):
    """Replace a context file's body atomically, keeping its front matter."""
    current = read_raw(path)
    m = TOML_FRONT_RE.match(current)
    fileio.atomic_write(path, (m.group(0) if m else "") + text)
