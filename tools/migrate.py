"""Bring a context folder (me/, or SWEATCAST_HOME) up to the format this engine reads.

Each context file names its format in front matter (`schema`, see context.py).
After pulling a major release, run this once: it backs up every file it will change
to me/.backup-<date and time>/, applies each step from the file's schema up to the
current one, and then checks the folder. Run it again and it changes nothing.

    ./sweatcast migrate             # migrate, with a backup
    ./sweatcast migrate --dry-run   # say what would change, change nothing

Steps:
    0 to 1 (sweatcast 2.0.0): add `---` front matter. Nothing else in the files changes.
    1 to 2 (sweatcast 3.0.0): TOML front matter (`+++`). In profile.md, the settings the
        tools read move out of the prose into it: the Voices list, "Copy finished MP3s
        to:", "Measured words per minute", the YouTube favorites and Puzzles handles, and
        the Feeds section. Their lines leave the prose, and one sentence says where they
        went. The other files only change their front matter.
    2 to 3 (sweatcast 4.0.0): profile.md gains `experience`, `likes` and `dislikes` in its
        settings (empty; fill them in, and add `[[kits]]` tables if you want named kits);
        health.md gains a comment in its settings block saying each injury needs a
        `[[limits]]` entry, which you write yourself (the tools can't read an injury from
        prose), and that the old comment naming injury-rules.toml and phases is to be
        deleted. The other files only change their schema number.
"""
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import context  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402


def to_1(text, path):
    """Schema 0 to 1: the front matter, nothing else."""
    return context.with_front_matter(text, 1)


def to_2(text, path):
    """Schema 1 to 2: TOML front matter; the profile's settings move into it."""
    rest = context.body(text)
    if os.path.basename(path) != "profile.md":
        return context.with_front_matter(rest, 2)
    return context.with_front_matter(context.legacy_body(rest), 2, context.legacy_settings(rest),
                                     context.SETTINGS_COMMENTS)


HEALTH_NOTE = ("# Each injury listed below needs a [[limits]] entry here (area, side, level, note); the brief's safety\n"
               "# screen reads only these rows. Move old \"Clinician rules:\" sub-bullets to the ## Clinician rules section.\n"
               "# Delete the old comment below that names knowledge/injury-rules.toml, phases and advance_when, and\n"
               "# any \"Phase\" or \"Move to the next phase\" sub-bullets: those files and phases are gone.")


def to_3(text, path):
    """Schema 2 to 3: the profile gains experience, likes and dislikes; the health file
    a comment about [[limits]]; every file its new schema number. Edits the settings
    block as text, so its comments and order survive."""
    m = context.TOML_FRONT_RE.match(text)
    if not m:
        return context.with_front_matter(text, 3)
    lines = [ln for ln in m.group(1).split("\n") if not re.match(r"\s*schema\s*=\s*2\b", ln)]
    name = os.path.basename(path)
    if name == "profile.md":
        new = []
        for key, value in (("experience", '""'), ("likes", "[]"), ("dislikes", "[]")):
            if any(re.match(rf"{key}\s*=", ln) for ln in lines):
                continue
            new += [f"# {context.SETTINGS_COMMENTS[key]}", f"{key} = {value}"]
        at = next((i + 1 for i, ln in enumerate(lines) if ln.startswith("words_per_minute")), None)
        if at is None:   # no rate: the new keys go before the first table
            at = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("[")), len(lines))
        lines[at:at] = new
    elif name == "health.md":
        lines.append(HEALTH_NOTE)
    block = "\n".join(["schema = 3"] + lines).strip("\n")
    context.tomllib.loads(block)   # never write a block that doesn't parse
    return f"+++\n{block}\n+++\n" + text[m.end():]


STEPS = {0: to_1, 1: to_2, 2: to_3}   # from schema N, the function that makes it N + 1


def plan():
    """[(path, from schema)] for each context file that's behind."""
    out = []
    for path in context.files():
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            found = context.schema_of(f.read())
        if found > context.SCHEMA:
            raise SystemExit(f"{show(path)} is schema {found}, newer than this engine (schema "
                             f"{context.SCHEMA}). Pull the latest sweatcast instead of migrating.")
        if found < context.SCHEMA:
            out.append((path, found))
    return out


def migrate(dry_run=False, stamp=None):
    """Apply every step to every file that's behind. Returns (backup folder or None, [changed paths])."""
    todo = plan()
    if not todo or dry_run:
        return None, [p for p, _ in todo]
    backup = os.path.join(paths.HOME, f".backup-{stamp or time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(backup, exist_ok=True)
    for path, _ in todo:
        shutil.copy2(path, os.path.join(backup, os.path.basename(path)))
    for path, found in todo:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for n in range(found, context.SCHEMA):
            text = STEPS[n](text, path)
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    return backup, [p for p, _ in todo]


def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="say what would change; change nothing")
    args = ap.parse_args(argv)
    missing = [p for p in context.files() if not os.path.exists(p)]
    if len(missing) == len(context.files()):
        raise SystemExit(f"No context files in {show(paths.HOME)}. A new copy starts with ./sweatcast setup.")

    todo = plan()
    if not todo:
        print(f"{show(paths.HOME)} is already at schema {context.SCHEMA}; nothing to do.")
    else:
        for path, found in todo:
            print(f"{show(path)}: schema {found} to {context.SCHEMA}")
        if args.dry_run:
            print("Dry run: nothing changed.")
            return cli.OK
        backup, _ = migrate()
        print(f"Backed up the originals to {show(backup)}.")

    issues = context.check()
    for issue in issues:
        print("  " + context.describe(issue))
    if any(not i.note for i in issues):
        print("Migrated, but the lines above need a look (./sweatcast check lists them again).")
        return cli.ISSUES
    print("Every context file reads as this engine expects.")
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
