"""`./sweatcast check`: everything in the context folder the tools can't read or that's still to fill in.

Issues (exit 1) are what stops a tool or applies no rule: a settings block that won't parse or doesn't close,
a [[limits]] row that can't be read, a feed with no value, a coach with no voice or clip. Notes are worth
knowing but break nothing: a stand-in coach, no delivery folder, what the quick start left for later. The
context files themselves are read and written only through tools/context.py; this module only looks."""
import difflib
import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402
from context import (FEED_KINDS, HANDLE_KEYS, PROFILE_PARTS, SCHEMA, SETTING_HOMES, Health, Issue, Session,  # noqa: E402
                     body, delivery_patterns, experience, feed_sources, front, kits, listener_name, parse_session,
                     part_paths, persona, placeholder, profile, read_raw, route_issues, schema_of, schema_problem,
                     section, split, unfilled, wpm, files as context_files)
from context import (_catalog, _limit_row, _names, _weight_problems, clinician_avoids, limit_rows,  # noqa: E402
                     prose_injury_gap)


BODY_HINT_RE = re.compile(r"^\s*- ([^:\[\]]+):\s*(\[|$)")   # "- Neighborhood: [neighborhood, city]", or nothing after the colon


def _check_profile(path):
    """[Issue] for the profile's four files, each pointing at the file that holds what's wrong."""
    parts = part_paths(path)
    for name, part in parts.items():   # a part in the wrong format is check()'s own issue
        if os.path.exists(part) and schema_problem(part, read_raw(part)):
            return []
    try:
        p = profile(path)
    except SystemExit as e:
        return [Issue(path, 1, str(e.code))]
    settings = p.settings

    def at(key):
        return p.sources.get(key) or parts[SETTING_HOMES.get(key, "profile.md")]

    out = [Issue(lost, 0, f"{k} is also set in {os.path.basename(won)}, which wins; keep it in one place")
           for k, won, lost in p.duplicates]
    known = set(SETTING_HOMES) | {"schema"}
    for name, part in parts.items():   # a key the tools don't read is a typo more often than not
        if os.path.exists(part):
            for key in split(part, read_raw(part))[0]:
                if key not in known:
                    close = difflib.get_close_matches(key, sorted(known), n=1, cutoff=0.6)
                    out.append(Issue(part, 0, f"unknown setting '{key}', which no tool reads"
                                              + (f" (did you mean {close[0]}?)" if close else ""), note=True))
    out += [i._replace(path=at("render")) for i in route_issues(p)]
    if wpm(p) is None:
        out.append(Issue(at("words_per_minute"), 0, "no words_per_minute (./sweatcast get wpm prints "
                                                    "nothing; builds use each coach's measured pace)", note=True))
    if not delivery_patterns(p):
        out.append(Issue(at("deliver_to"), 0, "no deliver_to folder, so finished MP3s stay in me/workouts/",
                         note=True))
    for i, f in enumerate(settings.get("feeds") or [], 1):
        if not isinstance(f, dict):
            continue
        kind = str(f.get("kind", "")).lower()
        name = f.get("label") or f"feed {i}"
        if kind not in FEED_KINDS:
            out.append(Issue(at("feeds"), 0, f"feed '{name}': unknown kind '{f.get('kind', '')}' "
                                             f"(one of {', '.join(FEED_KINDS)})"))
        elif unfilled(f.get("value")) or unfilled(f.get("label")):
            out.append(Issue(at("feeds"), 0, f"feed '{name}' isn't filled in yet ({kind}: "
                                             f"{f.get('value') or 'no value'}); fill it in or remove it"))
    if not feed_sources(p):
        out.append(Issue(at("feeds"), 0, "no feeds, so research searches for everything", note=True))
    out += _interest_problems(at("interests"), settings)
    for key in HANDLE_KEYS.values():
        for h in settings.get(key) or []:
            if placeholder(h):
                out.append(Issue(at(key), 0, f"{key}: '{h}' isn't filled in yet"))
    cat = _catalog()
    if experience(p) is None:
        out.append(Issue(at("experience"), 0, "no experience level: novice, experienced or advanced", note=True))
    if listener_name(p) is None:
        out.append(Issue(at("name"), 0, "no name: the coach can't greet the listener by name", note=True))
    if cat:
        for key in ("likes", "dislikes"):
            for name in _names(p, key):
                if not catalog.resolve(cat, name):
                    out.append(Issue(at(key), 0, f"{key}: '{name}' isn't a movement in the catalog", note=True))
        for kit, equipment in kits(p).items():
            for e in equipment:
                if e not in cat.equipment:
                    out.append(Issue(at("kits"), 0, f"kit '{kit}': '{e}' isn't equipment in the catalog",
                                     note=True))
    for k in settings.get("kits") or []:
        if isinstance(k, dict):
            for problem in _weight_problems(k):
                out.append(Issue(at("kits"), 0, f"kit '{k.get('name', '?')}': {problem}"))
    for name, part in parts.items():
        if name.endswith(".md") and os.path.exists(part):
            out += _hint_issues(part, read_raw(part))
    if setup_stage(p) == "quick":   # the quick start leaves these for later: worth knowing, nothing breaks
        out = [i._replace(note=True) if "isn't filled in yet" in i.message else i for i in out]
        out.append(Issue(at("setup"), 0, "setup's second half is still to do (interests, feeds, delivery, your "
                                         "own coach): say \"finish setting me up\"", note=True))
    return out


def _hint_issues(path, text):
    """[Issue] for each `- Label: [hint]` or `- Label:` line in a file's prose: still the template's, or empty.
    A block that won't parse is reported elsewhere; it has no prose to scan."""
    try:
        rest = body(text)
    except SystemExit:
        return []
    offset = len(text.splitlines()) - len(rest.splitlines())
    out = []
    for n, line in enumerate(rest.splitlines(), 1):
        m = BODY_HINT_RE.match(line)
        if m and m.group(2):   # the template's [hint], still there
            out.append(Issue(path, n + offset, f"'{m.group(1).strip()}' isn't filled in yet (still the template's "
                                               "[hint]); fill it in or delete the line"))
        elif m:                # an empty label: worth knowing, nothing breaks
            out.append(Issue(path, n + offset, f"'{m.group(1).strip()}' isn't filled in yet (empty); fill it in or "
                                               "delete the line", note=True))
    return out


def setup_stage(p):
    """"quick" while the quick start's second half is still to do (the profile's `setup` setting), else "full"."""
    return "quick" if str(p.settings.get("setup", "")).strip().lower() == "quick" else "full"


def _interest_problems(path, settings):
    import content   # here, not at the top: content imports this module
    slots = content.recipe().slots
    out = []
    for i, row in enumerate(settings.get("interests") or [], 1):
        if not isinstance(row, dict):
            out.append(Issue(path, 0, f"interests: entry {i} isn't a table (name, slot, detail)"))
        elif unfilled(row.get("name")) or unfilled(row.get("slot")):
            out.append(Issue(path, 0, f"interests: entry {i} isn't filled in yet (it needs a name and a slot)"))
        elif str(row["slot"]).strip() not in slots:
            out.append(Issue(path, 0, f"interests: '{row['name']}' has an unknown slot '{row['slot']}' "
                                      f"(one of {', '.join(slots)})"))
    return out


def _check_health(path, text):
    try:
        settings, rest = front(text)
    except SystemExit as e:
        return [Issue(path, 1, str(e.code))]
    h = Health(settings, rest, path)
    cat = _catalog()
    out = []
    rows = settings.get("limits") or []
    if not isinstance(rows, list):
        return [Issue(path, 0, "limits must be written as [[limits]] tables")]
    if not cat:
        return out
    good, problems = limit_rows(h, cat.areas, cat.flags)
    out += [Issue(path, 0, f"[[limits]] {problem}; the row is ignored, and the brief won't plan until it's fixed")
            for problem in problems]
    for i, row in enumerate(rows, 1):
        lim, _ = _limit_row(row, cat.areas, cat.flags)
        for mid in lim.rehab if lim else []:
            m = cat.movements.get(mid)
            if m is None or m.draft:
                out.append(Issue(path, 0, f"[[limits]] row {i}: rehab '{mid}' isn't a movement "
                                          "in the catalog (or is still a draft)", note=True))
            elif not m.rehab:
                out.append(Issue(path, 0, f"[[limits]] row {i}: rehab '{mid}' isn't a rehab movement, "
                                          "so naming it lets nothing through; name only rehab "
                                          "movements, or loosen the limit itself"))
    for word in clinician_avoids(h):
        try:
            catalog.avoid_set(cat, [word])
        except ValueError as e:
            out.append(Issue(path, 0, f"Avoid: {e}; the brief won't plan until it's fixed"))
    gap = prose_injury_gap(h, len(good))
    if gap:
        out.append(Issue(path, 0, gap))
    return out


def check(home_files=None):
    """[Issue] across the context files: schema, the formats the tools read, and
    template lines not filled in yet. Issues with note=True don't stop anything."""
    out = []
    quick_by_folder = {}

    def quick(path):
        """Whether the profile beside `path` is still in the quick start (its unfilled lines are notes)."""
        folder = os.path.dirname(path)
        if folder not in quick_by_folder:
            prof = os.path.join(folder, "profile.md")
            try:
                quick_by_folder[folder] = os.path.exists(prof) and setup_stage(profile(prof)) == "quick"
            except SystemExit:
                quick_by_folder[folder] = False
        return quick_by_folder[folder]

    for path in home_files or context_files():
        name = os.path.basename(path)
        if not os.path.exists(path):
            prof = os.path.join(os.path.dirname(path), "profile.md")
            if name in PROFILE_PARTS[1:] and os.path.exists(prof) and schema_of(read_raw(prof)) < SCHEMA:
                continue   # an older profile, not split yet: its schema issue says to migrate
            out.append(Issue(path, 0, "missing; ./sweatcast setup copies it from me.example/"))
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        problem = schema_problem(path, text)
        if problem:
            out.append(Issue(path, 0, problem))
            continue
        if name == "profile.md":
            out += _check_profile(path)
        elif name == "health.md":
            found = _check_health(path, text) + _hint_issues(path, text)
            if quick(path):   # the quick start leaves these for later: worth knowing, nothing breaks
                found = [i._replace(note=True) if "isn't filled in yet" in i.message else i for i in found]
            out += found
        elif name == "log.md":
            rest = body(text)
            offset = len(text.splitlines()) - len(rest.splitlines())
            if not any(line.strip().lower() == "## sessions" for line in rest.splitlines()):
                out.append(Issue(path, 0, "no '## Sessions' heading"))
            for n, line in section(rest, "Sessions"):
                if line.startswith("- "):
                    s = parse_session(line, n)
                    if not isinstance(s, Session):
                        out.append(Issue(path, n + offset, s))
    if home_files is None:
        out += check_coaches()
        out += check_movements()
        old = os.path.join(paths.HOME, "exercise-science.md")
        if os.path.exists(old):   # 5.1.0 stopped reading it
            out.append(Issue(old, 0, "no longer used (sessions draw no exercise-science asides now); "
                                     "delete it once anything worth keeping is copied out", note=True))
    return out


def check_coaches(folder=None):
    """[Issue] for the coaches in me/personas/ (not the archive or auditions): a persona.md the tools can't read,
    a local coach of the listener's own (no longer rendered), a web coach with no voice (a note while one is
    pending), and how-they-talk lines still showing the template's [hint]."""
    import personas
    folder = folder or paths.PERSONAS
    found = personas.persona_dirs(folder)
    if not found:
        return []   # the ten shipped coaches are always there to choose from
    out = []
    for slug in found:
        path = os.path.join(folder, slug, "persona.md")
        try:
            p = persona(path)
        except SystemExit as e:
            out.append(Issue(path, 0, str(e.code)))
            continue
        if p.settings.get("kind") == "web":
            name = p.settings.get("name") or slug
            if p.settings.get("pending"):
                how = ("made the first time a build uses it" if p.settings.get("placeholder")
                       else "the coach skill auditions one")
                out.append(Issue(path, 0, f"{name} has no voice yet ({p.settings['pending']} pending): {how}",
                                 note=True))
            elif not p.settings.get("voice_id"):
                out.append(Issue(path, 0, f"{name} is a web coach with no voice_id: audition a voice and keep one "
                                          "(the coach skill)"))
            if p.settings.get("style"):
                out.append(Issue(path, 0, f"{name}: Gemini's API takes no style setting yet (2026-10-25); "
                                          "leave style empty"))
        else:
            out.append(Issue(path, 0, f"{p.settings.get('name') or slug} is a local coach of your own, which "
                                      "sweatcast 15.0.0 no longer renders: ./sweatcast migrate archives it (the ten "
                                      "shipped coaches and web coaches remain)"))
        if p.settings.get("placeholder"):
            out.append(Issue(path, 0, f"{p.settings.get('name') or slug} is a stand-in coach: say \"I want a new "
                                      "coach\" to make your own", note=True))
        offset = len(read_raw(path).splitlines()) - len(p.body.splitlines())
        for n, line in enumerate(p.body.splitlines(), 1):
            m = BODY_HINT_RE.match(line)
            if m:
                out.append(Issue(path, n + offset, f"'{m.group(1).strip()}' still shows the template's hint"))
    return out


def check_movements(path=None):
    """[Issue] for the listener's private movements file (`movements.toml` in the context folder):
    each catalog problem that names one of its entries. None when there is no such file."""
    path = path or paths.MY_MOVEMENTS
    if not os.path.exists(path):
        return []
    try:
        extra = catalog.private_movements(path)
    except (tomllib.TOMLDecodeError, OSError) as e:
        return [Issue(path, 0, f"can't be read: {e}")]
    ids = {str(m.get("id", "")) for m in extra}
    cat = catalog.load(paths.MOVEMENTS, extra=extra)
    return [Issue(path, 0, p) for p in catalog.problems(cat)
            if any(re.search(rf"\b{re.escape(i)}\b", p) for i in ids if i)]


def describe(issue):
    where = f"{show(issue.path)}{f':{issue.line}' if issue.line else ''}"
    return f"{where}: {'note: ' if issue.note else ''}{issue.message}"


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast check",
                            description="Check every context file in me/: its format, and what's still to fill in.")
    ap.parse_args(argv)
    issues = check()
    for issue in issues:
        print(describe(issue))
    problems = [i for i in issues if not i.note]
    if not problems:
        print(f"Context folder {show(paths.HOME)}: schema {SCHEMA}, every file reads as the tools expect.")
    return cli.ISSUES if problems else cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
