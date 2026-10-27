"""Bring a context folder (me/, or SWEATCAST_HOME) up to the format this engine reads.

Each context file names its format in front matter (`schema`, see context.py).
After pulling a major release, run this once: it backs up every file it will change
to me/.backup-<date and time>/, applies each step from the file's schema up to the
current one, runs the folder steps that are still due, and then checks the folder.
Run it again and it changes nothing.

    ./sweatcast migrate             # migrate, with a backup
    ./sweatcast migrate --dry-run   # say what would change, change nothing

This engine migrates from context schema 4 (sweatcast 0.9.x) and coach schema 4 (0.10.0). An older
folder (sweatcast 0.8 and before) goes through sweatcast 0.12 first: `git checkout v0.12.0 &&
./sweatcast migrate`, then back to this version and `./sweatcast migrate` again.

Steps:
    4 to 5 (sweatcast 0.9.1): a folder per workout. Each draft in workouts/drafts/ moves, with its
        brief and menu, to workouts/<stem>/, and each build's script and record (and an MP3 not
        yet delivered) moves beside the draft its record names (or, with no record, the one draft
        from the same date). Smoke tests, and anything that can't be placed for sure, go to
        workouts/checks/; each day's research sheet and feeds to workouts/research/daily/. Nothing
        is overwritten. The files' text changes only its schema number.
    5 to 6 (sweatcast 0.12.0): the profile splits by how often each part changes and who reads it.
        profile.md keeps who you are (name, experience, and every prose section but these);
        training.md gets the kits, likes and dislikes and the Equipment kits and Default session
        sections; content.md the interests, feeds, YouTube favorites and puzzles and the Content and
        Taste sections; settings.toml setup, render, cloud_max_chars, deliver_to and
        words_per_minute. Each setting keeps its value (comments are the template's; the originals
        are in the backup). health.md and log.md change only their schema number. It backs up before
        overwriting a training.md, content.md or settings.toml already there (each goes to the backup first).
    Coaches (sweatcast 0.15.0, a folder step with no schema change): personas/ becomes coaches/; each local
        coach of the listener's own moves to coaches/.archive/ (local coaches are now the ten sweatcast ships,
        and a voice of one's own is a web coach); and an unmade copy of a stock web coach (Reed, Ellis, Nolan,
        Owen, still pending design) goes to the backup, since the engine ships them now. A made one stays and
        is used over the stock copy. me/.gitignore's personas/ rules become coaches/ rules.

The folder steps (the split, the folder per workout, the reserve's old name, the .gitignore rules for
coaches) run whenever they still have something to do, whatever the files' schema says, so a run that
stopped halfway finishes on the next. The reserve's old name (sweatcast 0.14): before 0.10.2 the reserve
was research/pantry/ and told.jsonl named a piece under `pantry`; each sheet moves into research/reserve/
(one already there by that name was the one read, so the pantry's copy goes to the backup unless it's
the same), and each `pantry` key becomes `reserve`.

Coach files (me/personas/<coach>/persona.md, and the archive's) carry their own schema, migrated
beside the context files, even when those are already current:
    4 to 5 (sweatcast 0.10.0): web coaches. Each coach's settings gain `kind = "local"` after the
        schema line; nothing else in the file changes. me/.gitignore keeps each web coach's
        sample.mp3 (archived ones too) and leaves out auditions in progress (personas/.auditions/) and a
        make's in-between files (.made.json, .made.wav).
"""
import filecmp
import json
import os
import re
import shutil
import sys
import time
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import errors  # noqa: E402
import check  # noqa: E402
import context  # noqa: E402
import store  # noqa: E402
import fileio  # noqa: E402
import frontmatter  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402
import workouts  # noqa: E402
from paths import show  # noqa: E402


def to_5(text, path):
    """Schema 4 to 5: only the schema number; the workouts folder moves once, in migrate()."""
    m = frontmatter.TOML_FRONT_RE.match(text)
    if not m:
        return store.with_front_matter(text, 5)
    block = re.sub(r"(?m)^schema\s*=\s*4\b", "schema = 5", m.group(1), count=1)
    return frontmatter.wrap(block, text[m.end():])


def to_6(text, path):
    """Schema 5 to 6: only the schema number; the profile splits once, in migrate()."""
    m = frontmatter.TOML_FRONT_RE.match(text)
    if not m:
        return store.with_front_matter(text, 6)
    block = re.sub(r"(?m)^schema\s*=\s*5\b", "schema = 6", m.group(1), count=1)
    return frontmatter.wrap(block, text[m.end():])


# The settings each split file writes, in order, and the comment above each (the template's words).
PART_KEYS = {
    "profile.md": ("name", "experience"),
    "training.md": ("likes", "dislikes", "kits"),
    "content.md": ("youtube_favorites", "puzzles", "interests", "feeds"),
    "settings.toml": ("setup", "render", "cloud_max_chars", "deliver_to", "words_per_minute"),
}
PART_COMMENTS = {
    "name": "What the coach calls you: a first name or nickname, said in the welcome, at the hardest set and at "
            "the sign-off. Empty means no name.",
    "experience": context.SETTINGS_COMMENTS["experience"],
    "likes": context.SETTINGS_COMMENTS["likes"],
    "dislikes": context.SETTINGS_COMMENTS["dislikes"],
    "kits": "Equipment kits a session can be planned with: a name and the equipment ids you have there "
            "(./sweatcast movements lists them); the first is the default. For free weights, add the weights you "
            "have, lightest to heaviest, and their unit, such as weights = { dumbbells = [10, 15, 20] } and "
            "unit = \"lb\".",
    "youtube_favorites": context.SETTINGS_COMMENTS["youtube_favorites"],
    "puzzles": context.SETTINGS_COMMENTS["puzzles"],
    "interests": "What the filler between exercises rotates through: [[interests]] rows, each a name, its slot "
                 "(today, science, deep_dive, quiz, delight or learn; knowledge/content.toml) and a detail for "
                 "research. Within a slot, the one told longest ago comes next. Without any rows, "
                 "knowledge/content.toml's defaults.",
    "feeds": context.SETTINGS_COMMENTS["feeds"],
    "setup": "\"quick\" until the second half of setup is done (interests, feeds, delivery, your own coach): until "
             "then ./sweatcast check lists what's left as notes. Say \"finish setting me up\" to do it.",
    "render": "The audio routes to try, in order (local, fish, elevenlabs, gemini or inworld), when the coach doesn't settle it: a local coach always renders on this computer, and a web coach always speaks through its own service, with its key in me/.env.",
    "cloud_max_chars": "The most characters one web build may send to a voice service; a build over it stops "
                       "before sending (30000, the default, is a 40-minute workout with room for retakes).",
    "deliver_to": context.SETTINGS_COMMENTS["deliver_to"],
    "words_per_minute": context.SETTINGS_COMMENTS["words_per_minute"],
}
PART_INTROS = {
    "training.md": "# Training\n\nHow you train: your kits and weights, the movements you like and dislike (the "
                   "settings above), and your usual session. Every workout reads this; update it when your "
                   "equipment or preferences change.\n",
    "content.md": "# Content\n\nWhat fills the rests between exercises: interests, feeds, YouTube channels and "
                  "puzzles (the settings above), and the topics and taste below. Research reads this before each "
                  "workout.\n",
}
SETTINGS_HEADER = ("# sweatcast's settings for this listener: the setup stage, how audio is made, a web build's "
                   "ceiling, where finished MP3s go, and the speaking rate. The tools read them; setup writes them.")
PROFILE_NOTE = ("Your details are in four files, by how often each changes: this one (who you are), `training.md` "
                "(kits, likes and dislikes, your usual session), `content.md` (interests, feeds and taste, for the "
                "stories) and `settings.toml` (delivery, audio and setup). Injuries are in `health.md`, and the "
                "workout log and feedback in `log.md`.")
STALE_PREFIXES = ("The settings the tools read", "Claude reads this before every workout")


def _dump_part(name, settings):
    keys = list(PART_KEYS[name]) + [k for k in settings if k not in PART_KEYS[name]]
    plain = [k for k in keys if k in settings and not (isinstance(settings[k], list) and settings[k]
                                                         and isinstance(settings[k][0], dict))]
    tables = [k for k in keys if k not in plain and (k in settings or k in ("kits", "interests", "feeds"))]
    return frontmatter.dump_block({k: settings[k] for k in plain}, arrays={k: settings.get(k) or [] for k in tables},
                                  comments=PART_COMMENTS)


def split_profile_text(text):
    """{file name: text} for a schema-6 profile.md written as one file: the four files it splits into."""
    settings, rest = frontmatter.front(text)
    groups = {name: {} for name in context.PROFILE_PARTS}
    for k, v in settings.items():
        if k != "schema":
            groups[context.SETTING_HOMES.get(k, "profile.md")][k] = v
    prose = {name: [] for name in context.PROFILE_PARTS}
    where = "profile.md"
    for ln in rest.splitlines(keepends=True):
        if ln.startswith("## "):
            where = context.PROSE_HOMES.get(ln[3:].strip().lower(), "profile.md")
        elif where == "profile.md" and ln.startswith(STALE_PREFIXES):
            ln = "" if ln.startswith(STALE_PREFIXES[1]) else PROFILE_NOTE + "\n"
        prose[where].append(ln)
    out = {}
    for name in context.PROFILE_PARTS:
        block = f"schema = {store.SCHEMA}\n" + _dump_part(name, groups[name])
        tomllib.loads(block)   # never write a block that doesn't parse
        if name == "settings.toml":
            out[name] = f"{SETTINGS_HEADER}\n{block}\n"
            continue
        body = re.sub(r"\n{3,}", "\n\n", "".join(prose[name]))
        if name in PART_INTROS:
            body = PART_INTROS[name] + ("\n" + body.lstrip("\n") if body.strip() else "")
        out[name] = frontmatter.wrap(block, body)
    return out


def split_profile(home):
    """Write training.md, content.md and settings.toml from profile.md (already at schema 6), and profile.md
    with what stays."""
    path = os.path.join(home, "profile.md")
    with open(path, encoding="utf-8") as f:
        parts = split_profile_text(f.read())
    for name, text in parts.items():
        fileio.atomic_write(os.path.join(home, name), text)


STEPS = {4: to_5, 5: to_6}   # from schema N, the function that makes it N + 1
FLOOR = min(STEPS)           # the oldest context schema this engine migrates (sweatcast 0.9.x)


def persona_to_5(text, path):
    """A coach file, schema 4 to 5: `kind = "local"` after the schema line (unless it names a kind), as a
    text edit, so every other byte stays as it was."""
    m = frontmatter.TOML_FRONT_RE.match(text)
    block = m.group(1) if m else ""
    line = re.search(r"(?m)^schema\s*=\s*4\b.*$", block)
    if not m or not line:
        raise errors.MigrateError(f"{show(path)}: no schema = 4 line in its settings block to migrate.")
    kind = "" if re.search(r"(?m)^kind\s*=", block) else '\nkind = "local"'
    new = block[:line.start()] + "schema = 5" + kind + block[line.end():]
    tomllib.loads(new)   # never write a block that doesn't parse
    return text[:m.start(1)] + new + text[m.end(1):]


PERSONA_STEPS = {4: persona_to_5}   # coach files, from schema N

GITIGNORE_ADD_5 = ("# A workout's web copy (Claude Code on the web) is kept: the private repo is how it reaches you.",
                   "!*.web-*.mp3")
GITIGNORE_ADD_PERSONA_5 = ("# Each web coach's approved sample is kept (archived ones too); auditions in progress, "
                           "and a make between saving a voice and writing the coach, are not.",
                           "!coaches/*/sample.mp3", "!coaches/.archive/*/sample.mp3", "coaches/.auditions/",
                           "coaches/*/.made.json", "coaches/*/.made.wav")

GITIGNORE_ADD_LOCKS = ("# The lock files the tools hold while they change a record (log.md, told.jsonl, builds.jsonl).",
                       "*.lock")   # in the template since 0.5.4; a folder older than that may lack it


def update_gitignore(home, add_lines):
    """Add the rules in `add_lines` that me/.gitignore lacks (and the comment introducing them, once).
    Returns whether anything was added; a folder with no .gitignore is left alone."""
    path = os.path.join(home, ".gitignore")
    try:
        with open(path, encoding="utf-8") as f:
            have = f.read()
    except FileNotFoundError:
        return False
    lines = [ln.strip() for ln in have.splitlines()]
    missing = [ln for ln in add_lines if not ln.startswith("#") and ln not in lines]
    if not missing:
        return False
    add = [ln for ln in add_lines if ln in missing or (ln.startswith("#") and ln not in lines)]
    fileio.atomic_write(path, have + ("" if have.endswith("\n") else "\n") + "\n".join(add) + "\n")
    return True


def _research(home):
    return os.path.join(home, "workouts", "research")


def _told_lines(home):
    """told.jsonl's lines, each kept as it is, and whether any record still names a piece under `pantry`."""
    try:
        with open(os.path.join(_research(home), "told.jsonl"), encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return [], False
    old = any("pantry" in (fileio.jsonl_record(line) or {}) for line in lines)
    return lines, old


def pantry_due(home):
    """What retiring the reserve's old name (before 0.10.2) still has to do, as lines to print; empty when nothing."""
    out = []
    old = os.path.join(_research(home), "pantry")
    if os.path.isdir(old):
        out.append(f"research/pantry/ ({len(os.listdir(old))} file(s)) moves into research/reserve/")
    if _told_lines(home)[1]:
        out.append("told.jsonl's `pantry` keys become `reserve`")
    return out


def retire_pantry(home, backup):
    """research/pantry/ into research/reserve/, never overwriting: a file the reserve already has by that name
    (the one the tools read) stays, and the pantry's copy goes to `backup` unless it's the same. Then each
    told.jsonl record's `pantry` key becomes `reserve` (told.jsonl is backed up first; damaged lines kept)."""
    old, new = os.path.join(_research(home), "pantry"), os.path.join(_research(home), "reserve")
    if os.path.isdir(old):
        os.makedirs(new, exist_ok=True)
        for name in sorted(os.listdir(old)):
            src, dst = os.path.join(old, name), os.path.join(new, name)
            if not os.path.exists(dst):
                shutil.move(src, dst)
            elif os.path.isfile(src) and os.path.isfile(dst) and filecmp.cmp(src, dst, shallow=False):
                os.remove(src)
            else:
                kept = os.path.join(backup, "research", "pantry", name)
                os.makedirs(os.path.dirname(kept), exist_ok=True)
                shutil.move(src, kept)
        os.rmdir(old)
    if not _told_lines(home)[1]:
        return
    told = os.path.join(_research(home), "told.jsonl")
    with locks.file_lock(told):   # no content log appends while the file is rewritten
        lines, _ = _told_lines(home)
        os.makedirs(os.path.join(backup, "research"), exist_ok=True)
        shutil.copy2(told, os.path.join(backup, "research", "told.jsonl"))
        out = []
        for line in lines:
            rec = fileio.jsonl_record(line)   # a damaged line is kept as it is
            if rec is not None and "pantry" in rec:
                slug = rec.get("reserve") or rec["pantry"]
                rec = {("reserve" if k == "pantry" else k): (slug if k == "pantry" else v)
                       for k, v in rec.items() if k != "reserve"}
                line = json.dumps(rec, ensure_ascii=False) + "\n"
            out.append(line)
        fileio.atomic_write(told, "".join(out))


def coach_root(home=None):
    """The listener's coach folder: coaches/, or personas/ in a folder from before 0.15.0 not migrated yet."""
    home = home or paths.HOME
    new, old = os.path.join(home, "coaches"), os.path.join(home, "personas")
    return old if os.path.isdir(old) and not os.path.isdir(new) else new


def persona_files(home=None):
    """Every coach file: coaches/<coach>/persona.md and coaches/.archive/<coach>/persona.md (not auditions), and
    the same under personas/ in a folder from before 0.15.0."""
    import personas
    home = home or paths.HOME
    folders = [os.path.join(home, n) for n in ("coaches", "personas")]
    return [os.path.join(where, d, "persona.md") for folder in folders
            for where in (folder, os.path.join(folder, ".archive")) for d in personas.persona_dirs(where)]


def _stock_web_names():
    import personas
    return {p.name.lower() for p in personas.load_all(paths.SHIPPED) if p.is_web}


def _coach_settings(path):
    """A persona.md's settings, or None when it can't be read (missing, not UTF-8, a block that won't parse)."""
    try:
        return frontmatter.front(store.read_raw(path, "coach"))[0]
    except (*errors.PROBLEMS, OSError, ValueError):   # UnicodeDecodeError is a ValueError
        return None


def acting(steps):
    """coaches_due's steps that change something: an unreadable coach is only reported."""
    return [s for s in steps if s[0] != "unreadable"]


def coaches_due(home):
    """0.15.0's coaches step: [(what, folder name)] still to do: ("rename", "personas"), ("archive", <coach>)
    for a local coach of the listener's own, ("stock", <coach>) for an unmade copy of a stock web coach; and
    ("unreadable", <coach>) for a persona.md that can't be read, left as it is and reported (acting() drops it)."""
    import personas
    out = []
    if os.path.isdir(os.path.join(home, "personas")):
        out.append(("rename", "personas"))
    root = coach_root(home)
    stock = _stock_web_names()
    for d in personas.persona_dirs(root):
        settings = _coach_settings(os.path.join(root, d, "persona.md"))
        if settings is None:
            out.append(("unreadable", d))
            continue
        if str(settings.get("kind") or "local").strip().casefold() == "local":
            out.append(("archive", d))
        elif settings.get("pending") and not settings.get("voice_id") \
                and str(settings.get("name") or "").lower() in stock:
            out.append(("stock", d))
    return out


def coaches_lines(due):
    names = {"rename": "personas/ becomes coaches/ (its new name)",
             "archive": "coaches/{}: a local coach of your own, archived (local coaches are now the ten sweatcast "
                        "ships; a voice of your own is a web coach)",
             "stock": "coaches/{}: a stock web coach not made yet, now shipped with sweatcast (moved to the backup)",
             "unreadable": "coaches/{}: its persona.md can't be read, so it's left as it is (./sweatcast check "
                           "says why)"}
    return [names[what].format(d) for what, d in due]


def rename_coaches(home):
    """personas/ to coaches/. With both there (a copy of the engine that ran before migrating), each coach not
    in coaches/ moves across; the rest stay in personas/ to sort by hand. Returns whether personas/ is gone."""
    old, new = os.path.join(home, "personas"), os.path.join(home, "coaches")
    if not os.path.isdir(old):
        return True
    if not os.path.exists(new):
        os.replace(old, new)
        return True
    for d in os.listdir(old):
        if not os.path.exists(os.path.join(new, d)):
            shutil.move(os.path.join(old, d), os.path.join(new, d))
    if not os.listdir(old):
        os.rmdir(old)
        return True
    return False


def settle_coaches(home, backup):
    """Archive the listener's own local coaches and set aside unmade stock web coaches (coaches_due)."""
    root = os.path.join(home, "coaches")
    for what, d in coaches_due(home):
        src = os.path.join(root, d)
        if what == "archive":
            base = os.path.join(root, ".archive")
            dest, n = os.path.join(base, d), 2
            while os.path.exists(dest):
                dest, n = os.path.join(base, f"{d}-{n}"), n + 1
            os.makedirs(base, exist_ok=True)
            shutil.move(src, dest)
        elif what == "stock":
            dest = os.path.join(backup, "coaches", d)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(src, dest)


def rename_gitignore(home):
    """me/.gitignore's personas/ rules as coaches/ rules."""
    path = os.path.join(home, ".gitignore")
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        have = f.read()
    new = re.sub(r"(?m)^(!?)personas/", r"\1coaches/", have)
    if new != have:
        fileio.atomic_write(path, new)
    return new != have


def _behind(path, current, floor, what):
    with open(path, encoding="utf-8") as f:
        found = store.schema_of(f.read(), path)
    if found > current:
        raise errors.MigrateError(f"{show(path)} is schema {found}, newer than this engine (schema "
                         f"{current}). Pull the latest sweatcast instead of migrating.")
    if found < floor:
        raise errors.MigrateError(f"{show(path)} is schema {found}, older than this engine migrates ({what} from schema {floor}). "
                         "Go through sweatcast 0.12 first: git checkout v0.12.0 && ./sweatcast migrate, then "
                         "git checkout main && ./sweatcast migrate again.")
    return found if found < current else None


def plan():
    """[(path, from schema)] for each context file that's behind, then each coach file that's behind
    (coach files are at store.PERSONA_SCHEMA). Stops on a file older than this engine migrates."""
    out = []
    for path in context.files():
        if os.path.exists(path):
            found = _behind(path, store.SCHEMA, FLOOR, "the context files")
            if found is not None:
                out.append((path, found))
    for path in persona_files():
        found = _behind(path, store.PERSONA_SCHEMA, min(PERSONA_STEPS), "coach files")
        if found is not None:
            out.append((path, found))
    return out


def _is_persona(path):
    return os.path.basename(path) == "persona.md"


def strays(home):
    """The settings still in profile.md whose home is another of the four files: a folder that never split, or
    a split that stopped halfway."""
    path = os.path.join(home, "profile.md")
    if not os.path.exists(path):
        return []
    settings, _ = store.split(path, store.read_raw(path))
    return [k for k in settings if context.SETTING_HOMES.get(k, "profile.md") != "profile.md"]


def move_strays(home):
    """On a folder already split, move each stray setting out of profile.md: into its home file when that file
    doesn't set it, else dropped (the home file's value is the one in effect, as context.profile reads them).
    Prose stays where it is."""
    path = os.path.join(home, "profile.md")
    text = store.read_raw(path)
    settings, rest = frontmatter.front(text)
    stray = [k for k in settings if context.SETTING_HOMES.get(k, "profile.md") != "profile.md"]
    for key in stray:
        home_name = context.SETTING_HOMES[key]
        dest = os.path.join(home, home_name)
        have = store.split(dest, store.read_raw(dest))[0] if os.path.exists(dest) else {}
        if key not in have:
            line = f"{key} = {frontmatter.toml_value(settings[key])}"
            comment = f"# {PART_COMMENTS[key]}\n" if key in PART_COMMENTS else ""
            if home_name.endswith(".toml"):
                body = store.read_raw(dest) if os.path.exists(dest) else f"{SETTINGS_HEADER}\nschema = {store.SCHEMA}\n"
                fileio.atomic_write(dest, body.rstrip("\n") + f"\n{comment}{line}\n")
            else:
                dest_text = (store.read_raw(dest) if os.path.exists(dest)
                             else frontmatter.wrap(f"schema = {store.SCHEMA}"))
                m = frontmatter.TOML_FRONT_RE.match(dest_text)
                block = m.group(1).rstrip("\n") + f"\n{comment}{line}"
                fileio.atomic_write(dest, frontmatter.wrap(block, dest_text[m.end():]))
        settings.pop(key)
    m = frontmatter.TOML_FRONT_RE.match(text)
    block = m.group(1)
    for key in stray:   # drop the stray's lines (and a comment line just above it) from profile.md's block
        block = re.sub(rf"(?m)(^#[^\n]*\n)?^{re.escape(key)}\s*=.*\n", "", block, count=1)
        block = re.sub(rf"(?ms)^\[\[{re.escape(key)}\]\]\n.*?(?=^\[\[|\Z)", "", block)
    fileio.atomic_write(path, frontmatter.wrap(block, text[m.end():]))


def folder_steps_due(home):
    """(the stray settings a split would move, the workout moves a relayout would make, what retiring the
    reserve's old name would do, what the coaches step would do)."""
    return strays(home), workouts.reorganize(home, dry_run=True), pantry_due(home), coaches_due(home)


def migrate(dry_run=False, stamp=None, moves=None):
    """Apply every file step to every file that's behind, then the folder steps still due. Returns (backup folder
    or None, [changed paths]). `moves`, a list, gets the workout files moved (src, dst)."""
    todo = plan()
    home = paths.HOME
    stray, due_moves, pantry, coach_steps = folder_steps_due(home)
    coach_steps = acting(coach_steps)
    if dry_run or not (todo or stray or due_moves or pantry or coach_steps):
        if moves is not None:
            moves.extend(due_moves)
        return None, [p for p, _ in todo]
    backup = os.path.join(home, f".backup-{stamp or time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(backup, exist_ok=True)
    if os.path.exists(os.path.join(home, ".gitignore")):
        shutil.copy2(os.path.join(home, ".gitignore"), os.path.join(backup, ".gitignore"))
    if coach_steps and rename_coaches(home):   # first, so every later step finds the coaches in coaches/
        todo = plan()
    for path, _ in todo:
        if _is_persona(path):   # by their place in the folder: every coach's file is persona.md
            dest = os.path.join(backup, os.path.relpath(path, home))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(path, dest)
        else:
            shutil.copy2(path, os.path.join(backup, os.path.basename(path)))
    if stray:   # the split rewrites every part, so each one there is backed up first
        for name in context.PROFILE_PARTS:
            if os.path.exists(os.path.join(home, name)):
                shutil.copy2(os.path.join(home, name), os.path.join(backup, name))
    changed = [p for p, _ in todo]
    for path, found in todo:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        steps = PERSONA_STEPS if _is_persona(path) else STEPS
        current = store.PERSONA_SCHEMA if _is_persona(path) else store.SCHEMA
        for n in range(found, current):
            text = steps[n](text, path)
        fileio.atomic_write(path, text)
    if stray:
        # A profile that was below schema 6 this run held everything: it splits, and a part file already there
        # (a template copy, say) is replaced, backed up above. A folder already split gets each stray moved
        # to its home file, or dropped when the home file sets it (the home file's value was the one in effect).
        unsplit = any(os.path.basename(p) == "profile.md" and found < 6 for p, found in todo) \
            or not any(os.path.exists(os.path.join(home, n)) for n in context.PROFILE_PARTS[1:])
        (split_profile if unsplit else move_strays)(home)
        changed += [os.path.join(home, n) for n in context.PROFILE_PARTS if os.path.join(home, n) not in changed]
    if due_moves:
        update_gitignore(home, GITIGNORE_ADD_5)
        moved = workouts.reorganize(home)
        if moves is not None:
            moves.extend(moved)
    if pantry:
        retire_pantry(home, backup)
    if coach_steps:
        settle_coaches(home, backup)
    rename_gitignore(home)
    update_gitignore(home, GITIGNORE_ADD_PERSONA_5)
    return backup, changed


def _rel(path):
    return os.path.relpath(path, os.path.join(paths.HOME, "workouts"))


def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="say what would change; change nothing")
    args = ap.parse_args(argv)
    missing = [p for p in context.files() if not os.path.exists(p)]
    if len(missing) == len(context.files()):
        raise errors.MigrateError(f"No context files in {show(paths.HOME)}. A new copy starts with ./sweatcast setup.")

    if not args.dry_run and update_gitignore(paths.HOME, GITIGNORE_ADD_LOCKS):
        print(f"{show(os.path.join(paths.HOME, '.gitignore'))}: added *.lock (lock files never go into a backup).")
    todo = plan()
    stray, due_moves, pantry, coach_steps = folder_steps_due(paths.HOME)
    for line in coaches_lines([s for s in coach_steps if s not in acting(coach_steps)]):
        print(line, file=sys.stderr)   # an unreadable coach: reported, never moved
    coach_steps = acting(coach_steps)
    if not (todo or stray or due_moves or pantry or coach_steps):
        print(f"{show(paths.HOME)} is already at schema {store.SCHEMA}; nothing to do.")
    else:
        for path, found in todo:
            print(f"{show(path)}: schema {found} to "
                  f"{store.PERSONA_SCHEMA if _is_persona(path) else store.SCHEMA}")
        if stray:
            print(f"profile.md: {', '.join(stray)} move to their home files (training.md, content.md, settings.toml)")
        if due_moves:
            print(f"{len(due_moves)} workout file(s) move into a folder per workout (and checks/, research/daily/)")
        for line in pantry:
            print(line)
        for line in coaches_lines(coach_steps):
            print(line)
        if args.dry_run:
            for src, dst in due_moves:
                print(f"  {_rel(src)} would move to {_rel(dst)}")
            print("Dry run: nothing changed.")
            return cli.OK
        moves = []
        backup, _ = migrate(moves=moves)
        if moves:
            print(f"  Moved {len(moves)} workout file(s) into a folder per workout (and checks/, research/daily/).")
        print(f"Backed up the originals to {show(backup)}.")

    issues = check.check()
    for issue in issues:
        print("  " + check.describe(issue))
    if any(not i.note for i in issues):
        print("Migrated, but the lines above need a look (./sweatcast check lists them again).", file=sys.stderr)
        return cli.ISSUES
    print("Every context file reads as this engine expects.")
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
