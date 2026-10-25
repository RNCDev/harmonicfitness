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
    3 to 4 (sweatcast 9.0.0): voices become coaches. Each voice the profile's [[voices]] lists
        becomes a persona folder in me/personas/: its clip and words copied byte for byte (from
        me/voices/, else the clips sweatcast 8 shipped, read from the v8.0.1 git tag),
        its measured pace moved out of workouts/.audio-cache/voice-pace.json, and the profile's
        ## Narrator lines as how the coach talks. Chatterbox Coach becomes Coach Julius and Qwen3
        Coach becomes Coach Solo, each keeping its old names as aliases, so old log lines still
        name them. The profile loses [[voices]] and gains render = ["local"]; me/.gitignore leaves
        out .env (API keys) and designed takes. Cached clips stay valid: the clip, model and
        engine, which their keys are made of, don't change. A voice named for a model that isn't
        one of those two needs a person's name: --name "<old>=<Coach Name>".
    4 to 5 (sweatcast 9.1.0): a folder per workout. Each draft in workouts/drafts/ moves, with its
        brief and menu, to workouts/<stem>/, and each build's script and record (and an MP3 not
        yet delivered) moves beside the draft its record names (or, with no record, the one draft
        from the same date). Smoke tests, and anything that can't be placed for sure, go to
        workouts/checks/; each day's research sheet and feeds to workouts/research/daily/. Nothing
        is overwritten. The files' text changes only its schema number.

Coach files (me/personas/<coach>/persona.md, and the archive's) carry their own schema, migrated
beside the context files, even when those are already current:
    4 to 5 (sweatcast 10.0.0): web coaches. Each coach's settings gain `kind = "local"` after the
        schema line; nothing else in the file changes. me/.gitignore keeps each web coach's
        sample.mp3 (archived ones too) and leaves out auditions in progress (personas/.auditions/) and a
        make's in-between files (.made.json, .made.wav).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import context  # noqa: E402
import paths  # noqa: E402
import workouts  # noqa: E402
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


RENDER_COMMENT = ("How a local coach's workouts become audio, in order of preference: local engines only (local: "
                  "this computer's own engine; each build uses the first that works on the computer it runs on). "
                  "A web coach always speaks through its own service (fish, elevenlabs, gemini or inworld), with "
                  "its key in me/.env.")
NARRATOR_NOTE = "How the coach talks now lives with each coach, in me/personas/<coach>/persona.md."


def to_4(text, path):
    """Schema 3 to 4, a file's text: the profile loses [[voices]] (now me/personas/) and its Narrator
    lines (now each coach's prose), and gains `render`; every file its new schema number."""
    m = context.TOML_FRONT_RE.match(text)
    if not m:
        return context.with_front_matter(text, 4)
    lines = [ln for ln in m.group(1).split("\n") if not re.match(r"\s*schema\s*=\s*3\b", ln)]
    rest = text[m.end():]
    if os.path.basename(path) == "profile.md":
        starts = [i for i, ln in enumerate(lines) if ln.strip() == "[[voices]]"]
        for i in reversed(starts):   # each table runs to the next one; comments just before it are the next's
            end = next((j for j in range(i + 1, len(lines)) if lines[j].lstrip().startswith("[")), len(lines))
            while end > i + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
                end -= 1
            del lines[i:end]
        lines = [ln for ln in lines if not ln.strip().startswith("# Voices from ./sweatcast voices")]
        if not any(re.match(r"render\s*=", ln) for ln in lines):
            at = next((i + 1 for i, ln in enumerate(lines) if ln.startswith("words_per_minute")), None)
            if at is None:
                at = next((i for i, ln in enumerate(lines) if ln.lstrip().startswith("[")), len(lines))
            lines[at:at] = [f"# {RENDER_COMMENT}", 'render = ["local"]']
        rest = _without_narrator(rest)
    block = "\n".join(["schema = 4"] + lines).strip("\n")
    block = re.sub(r"\n{3,}", "\n\n", block)
    context.tomllib.loads(block)   # never write a block that doesn't parse
    return f"+++\n{block}\n+++\n" + rest


def to_5(text, path):
    """Schema 4 to 5: only the schema number; the workouts folder moves once, in migrate()."""
    m = context.TOML_FRONT_RE.match(text)
    if not m:
        return context.with_front_matter(text, 5)
    block = re.sub(r"(?m)^schema\s*=\s*4\b", "schema = 5", m.group(1), count=1)
    return f"+++\n{block}\n+++\n" + text[m.end():]


def _without_narrator(body):
    out, inside = [], False
    for ln in body.splitlines(keepends=True):
        if ln.startswith("## "):
            if inside:
                out.append("\n")
            inside = ln[3:].strip().lower() == "narrator"
            out.append(ln)
            if inside:
                out.append(NARRATOR_NOTE + "\n")
            continue
        if not inside:
            out.append(ln)
    return "".join(out)


STEPS = {0: to_1, 1: to_2, 2: to_3, 3: to_4, 4: to_5}   # from schema N, the function that makes it N + 1


def persona_to_5(text, path):
    """A coach file, schema 4 to 5: `kind = "local"` after the schema line (unless it names a kind), as a
    text edit, so every other byte stays as it was."""
    m = context.TOML_FRONT_RE.match(text)
    block = m.group(1) if m else ""
    line = re.search(r"(?m)^schema\s*=\s*4\b.*$", block)
    if not m or not line:
        raise SystemExit(f"{show(path)}: no schema = 4 line in its settings block to migrate.")
    kind = "" if re.search(r"(?m)^kind\s*=", block) else '\nkind = "local"'
    new = block[:line.start()] + "schema = 5" + kind + block[line.end():]
    context.tomllib.loads(new)   # never write a block that doesn't parse
    return text[:m.start(1)] + new + text[m.end(1):]


PERSONA_STEPS = {4: persona_to_5}   # coach files, from schema N

# ---- 3 to 4: voices become coaches (a folder step, beside the file steps) -------------------

V8_NAMES = {"chatterbox coach": ("Coach Julius", ["Chatterbox Coach", "Coach E"]),
            "qwen3 coach": ("Coach Solo", ["Qwen3 Coach", "Coach G"])}
MODEL_WORDS = ("chatterbox", "qwen")
GITIGNORE_ADD = ("# API keys for cloud voices (./sweatcast keys): never committed, never pushed.", ".env",
                 "# Designed takes not kept, and stock-voice samples.", "personas/*/takes/", "personas/.samples/")
GITIGNORE_ADD_5 = ("# A workout's web copy (Claude Code on the web) is kept: the private repo is how it reaches you.",
                   "!*.web-*.mp3")
GITIGNORE_ADD_PERSONA_5 = ("# Each web coach's approved sample is kept (archived ones too); auditions in progress, "
                           "and a make between saving a voice and writing the coach, are not.",
                           "!personas/*/sample.mp3", "!personas/.archive/*/sample.mp3", "personas/.auditions/",
                           "personas/*/.made.json", "personas/*/.made.wav")


class NeedsName(Exception):
    pass


def _v8_voice(name, home):
    """{"wav": bytes, "txt": words, "conf": settings} for an old voice (by name or alias), or None."""
    want = name.lower()
    folder = os.path.join(home, "voices")
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            stem, ext = os.path.splitext(f)
            if ext != ".json":
                continue
            with open(os.path.join(folder, f), encoding="utf-8") as j:
                conf = json.load(j)
            if want in (stem.lower(), *(a.lower() for a in conf.get("aliases") or [])):
                wav, txt = os.path.join(folder, stem + ".wav"), os.path.join(folder, stem + ".txt")
                if os.path.exists(wav) and os.path.exists(txt):
                    with open(wav, "rb") as a, open(txt, "rb") as t:
                        return {"stem": stem, "wav": a.read(), "txt": t.read(), "conf": conf}
    return _from_git(name)


def _from_git(name):
    """The clip from the v8.0.1 tag, when me/voices/ lacks it: the clips sweatcast 8 shipped."""
    def show(path):
        out = subprocess.run(["git", "-C", paths.ROOT, "show", f"v8.0.1:{path}"], capture_output=True)
        return out.stdout if out.returncode == 0 else None
    try:
        conf, wav, txt = (show(f"voices/{name}{ext}") for ext in (".json", ".wav", ".txt"))
    except OSError:
        return None
    if conf and wav and txt:
        return {"stem": name, "wav": wav, "txt": txt, "conf": json.loads(conf)}
    return None


def coach_name(old, stem, names):
    """(the coach's name, aliases) for an old voice: the two shipped ones are renamed; a private voice keeps its
    name unless it names a model, which needs --name."""
    for key in (old.lower(), (stem or "").lower()):
        if key in names:
            return names[key], [old] if old.lower() != names[key].lower() else []
        if key in V8_NAMES:
            return V8_NAMES[key]
    if any(w in old.lower() for w in MODEL_WORDS):
        raise NeedsName(old)
    return old, []


def _narrator_prose(profile_body):
    lines = [ln for _, ln in context.section(profile_body, "Narrator")]
    while lines and not lines[-1].strip():
        lines.pop()
    body = "\n".join(ln for ln in lines).strip("\n")
    if not body:
        import coaches
        return coaches.PROSE
    return "## How this coach talks\n" + body + "\n"


def plan_coaches(profile_text, home, names=None):
    """[(old name, coach name, aliases, description, voice files or None)] for each [[voices]] entry."""
    names = {k.lower(): v for k, v in (names or {}).items()}
    settings = context.front(profile_text)[0]
    out, missing = [], []
    for v in settings.get("voices") or []:
        if not isinstance(v, dict) or context.unfilled(v.get("name")):
            continue
        old = str(v["name"]).strip()
        found = _v8_voice(old, home)
        if found is None:
            print(f"{old}'s clip comes from sweatcast's v8.0.1 git tag, which this copy doesn't have "
                  f"(a ZIP download?), and me/voices/ lacks it: keep a clip later with ./sweatcast coaches keep.")
        try:
            new, aliases = coach_name(old, found and found["stem"], names)
        except NeedsName:
            missing.append(old)
            continue
        old_aliases = (found or {}).get("conf", {}).get("aliases") or []
        aliases = list(dict.fromkeys([*aliases, *([found["stem"]] if found and found["stem"] != new else []),
                                      *old_aliases]))
        description = re.sub(r"^formerly [^.]*\.\s*", "", str(v.get("description") or "")).strip()
        out.append((old, new, aliases, description, found))
    if missing:
        raise SystemExit("These voices are named for a model, and a coach needs a person's name: "
                         + ", ".join(missing) + ". Rerun with, for example: ./sweatcast migrate "
                         + " ".join(f'--name "{m}=Coach <Name>"' for m in missing))
    return out


def make_coaches(home, plan, prose, pace_file):
    """Each planned coach's folder in home/personas/, never touching one that's already there. Returns the
    names made."""
    import personas
    try:
        with open(pace_file, encoding="utf-8") as f:
            pace = json.load(f)
    except (OSError, ValueError):
        pace = {}
    made = []
    for old, new, aliases, description, found in plan:
        folder = os.path.join(home, "personas", personas.slug(new))
        if os.path.exists(os.path.join(folder, "persona.md")):
            continue
        os.makedirs(folder, exist_ok=True)
        conf = (found or {}).get("conf") or {}
        settings = {"name": new, "aliases": aliases, "kind": "local", "description": description}
        local = {"engine": conf.get("engine") or "chatterbox"}
        import voices
        pin = voices.LOCAL_MODELS.get((local["engine"], "mlx"))
        if conf.get("model") and pin and (conf["model"], conf.get("revision")) != pin:
            local.update(model=conf["model"], revision=conf.get("revision"))
        if conf.get("generate"):
            local["generate"] = conf["generate"]
        if (conf.get("torch") or {}).get("generate"):
            local["torch_generate"] = conf["torch"]["generate"]
        settings["local"] = local
        if found:
            with open(os.path.join(folder, "clip.wav"), "wb") as f:
                f.write(found["wav"])
            with open(os.path.join(folder, "clip.txt"), "wb") as f:
                f.write(found["txt"])
        with open(os.path.join(folder, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text(settings, prose))
        if found:
            key = personas.clip_key(personas.load(folder))[0]
            entries = {k: v for k, v in pace.items() if k.startswith(key + "|")}
            if entries:
                with open(os.path.join(folder, "pace.json"), "w", encoding="utf-8") as f:
                    json.dump(entries, f, indent=1)
        made.append(new + ("" if found else " (no clip found: keep one with ./sweatcast coaches keep)"))
    return made


def update_gitignore(home, add_lines=GITIGNORE_ADD):
    path = os.path.join(home, ".gitignore")
    try:
        with open(path, encoding="utf-8") as f:
            have = f.read()
    except FileNotFoundError:
        return
    lines = [ln.strip() for ln in have.splitlines()]
    add = [ln for ln in add_lines if ln.startswith("#") or ln not in lines]
    if any(not ln.startswith("#") for ln in add):
        with open(path, "a", encoding="utf-8") as f:
            f.write(("" if have.endswith("\n") else "\n") + "\n".join(add) + "\n")


def persona_files(home=None):
    """Every coach file: personas/<coach>/persona.md and personas/.archive/<coach>/persona.md (not auditions)."""
    out = []
    folder = os.path.join(home or paths.HOME, "personas")
    for where in (folder, os.path.join(folder, ".archive")):
        if os.path.isdir(where):
            out += sorted(os.path.join(where, d, "persona.md") for d in os.listdir(where)
                          if not d.startswith(".") and os.path.exists(os.path.join(where, d, "persona.md")))
    return out


def _behind(path, current):
    with open(path, encoding="utf-8") as f:
        found = context.schema_of(f.read())
    if found > current:
        raise SystemExit(f"{show(path)} is schema {found}, newer than this engine (schema "
                         f"{current}). Pull the latest sweatcast instead of migrating.")
    return found if found < current else None


def plan():
    """[(path, from schema)] for each context file that's behind, then each coach file that's behind
    (coach files are at context.PERSONA_SCHEMA)."""
    out = []
    for path in context.files():
        if os.path.exists(path):
            found = _behind(path, context.SCHEMA)
            if found is not None:
                out.append((path, found))
    for path in persona_files():
        found = _behind(path, context.PERSONA_SCHEMA)
        if found is not None and found < min(PERSONA_STEPS):
            raise SystemExit(f"{show(path)} is schema {found}, older than any coach file this engine migrates "
                             f"(schema {min(PERSONA_STEPS)}): check its +++ settings block.")
        if found is not None:
            out.append((path, found))
    return out


def _is_persona(path):
    return os.path.basename(path) == "persona.md"


def migrate(dry_run=False, stamp=None, names=None, report=None, moves=None):
    """Apply every step to every file that's behind. Returns (backup folder or None, [changed paths]).
    `report`, a list, gets the coaches made; `moves`, a list, the workout files moved (src, dst)."""
    todo = plan()
    files = [(p, n) for p, n in todo if not _is_persona(p)]
    coach_files = [(p, n) for p, n in todo if _is_persona(p)]
    relayout = any(found < 5 for _, found in files)
    if not todo or dry_run:
        if dry_run and files:
            _coach_plan(files, names, report)
            if relayout and moves is not None:
                moves.extend(workouts.reorganize(paths.HOME, dry_run=True))
        return None, [p for p, _ in todo]
    home = paths.HOME
    coach_plan = _coach_plan(files, names)   # a voice that needs a name stops here, before anything changes
    backup = os.path.join(home, f".backup-{stamp or time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(backup, exist_ok=True)
    for path, _ in files:
        shutil.copy2(path, os.path.join(backup, os.path.basename(path)))
    for path, _ in coach_files:   # by their place in the folder: every coach's file is persona.md
        dest = os.path.join(backup, os.path.relpath(path, home))
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(path, dest)
    old_pace = os.path.join(home, "workouts", ".audio-cache", "voice-pace.json")
    if coach_plan is not None:   # never .env: the backup holds only what migrate changes
        for extra in (os.path.join(home, ".gitignore"), old_pace):
            if os.path.exists(extra):
                shutil.copy2(extra, os.path.join(backup, os.path.basename(extra)))
        if os.path.isdir(paths.OLD_VOICES):
            shutil.copytree(paths.OLD_VOICES, os.path.join(backup, "voices"))
    elif coach_files and os.path.exists(os.path.join(home, ".gitignore")):
        shutil.copy2(os.path.join(home, ".gitignore"), os.path.join(backup, ".gitignore"))
    for path, found in todo:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        if _is_persona(path):
            for n in range(found, context.PERSONA_SCHEMA):
                text = PERSONA_STEPS[n](text, path)
        else:
            for n in range(found, context.SCHEMA):
                if n == 3 and coach_plan is not None and os.path.basename(path) == "profile.md":
                    made = make_coaches(home, coach_plan, _narrator_prose(context.body(text)), old_pace)
                    if report is not None:
                        report.extend(made)
                text = STEPS[n](text, path)
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    if coach_plan is not None:
        update_gitignore(home)
        if os.path.exists(old_pace):
            os.remove(old_pace)   # it's in the backup; each coach has its own now
        if os.path.isdir(paths.OLD_VOICES):
            shutil.rmtree(paths.OLD_VOICES)   # copied into personas/ and the backup
    if relayout:
        update_gitignore(home, GITIGNORE_ADD_5)
        moved = workouts.reorganize(home)
        if moves is not None:
            moves.extend(moved)
    if coach_files or coach_plan is not None:
        update_gitignore(home, GITIGNORE_ADD_PERSONA_5)
    return backup, [p for p, _ in todo]


def _coach_plan(todo, names=None, report=None):
    """The 3 to 4 coaches step's plan, from the profile as it reads at schema 3, or None when the profile
    isn't crossing schema 4."""
    for path, found in todo:
        if os.path.basename(path) == "profile.md" and found < 4:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for n in range(found, 3):
                text = STEPS[n](text, path)
            result = plan_coaches(text, paths.HOME, names)
            if report is not None:
                report.extend(f"{old} becomes {new}" + ("" if found_ else " (no clip found)")
                              for old, new, _, _, found_ in result)
            return result
    return None


def _rel(path):
    return os.path.relpath(path, os.path.join(paths.HOME, "workouts"))


def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="say what would change; change nothing")
    ap.add_argument("--name", action="append", default=[], metavar="OLD=NEW",
                    help="the coach's name for an old voice named for a model, such as \"Qwen3 Custom=Coach Rae\"")
    args = ap.parse_args(argv)
    names = {}
    for item in args.name:
        old, sep, new = item.partition("=")
        if not sep or not old.strip() or not new.strip():
            ap.error(f"--name takes OLD=NEW, not {item!r}")
        names[old.strip()] = new.strip()
    missing = [p for p in context.files() if not os.path.exists(p)]
    if len(missing) == len(context.files()):
        raise SystemExit(f"No context files in {show(paths.HOME)}. A new copy starts with ./sweatcast setup.")

    todo = plan()
    if not todo:
        print(f"{show(paths.HOME)} is already at schema {context.SCHEMA}; nothing to do.")
    else:
        for path, found in todo:
            print(f"{show(path)}: schema {found} to "
                  f"{context.PERSONA_SCHEMA if _is_persona(path) else context.SCHEMA}")
        report, moves = [], []
        if args.dry_run:
            migrate(dry_run=True, names=names, report=report, moves=moves)
            for line in report:
                print(f"  {line}")
            for src, dst in moves:
                print(f"  {_rel(src)} would move to {_rel(dst)}")
            print("Dry run: nothing changed.")
            return cli.OK
        backup, _ = migrate(names=names, report=report, moves=moves)
        for line in report:
            print(f"  Made the coach {line}")
        if moves:
            print(f"  Moved {len(moves)} workout file(s) into a folder per workout (and checks/, research/daily/).")
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
