"""log-session's checks: one session line for log.md, refused unless the tools can read every field back (the
coach, the kit, the format, each load's movement) and the session isn't logged already. With a draft, the
movements come from its movements: line, the date, length and kit from its menu, and the coach from the build
record of the draft as it stands. context.main parses the command and calls log_session.
"""
import datetime as dt
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import context  # noqa: E402
import draft  # noqa: E402
import errors  # noqa: E402
import locks  # noqa: E402
import menu  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import records  # noqa: E402
import sessionlog  # noqa: E402
import sessions  # noqa: E402
from paths import show  # noqa: E402


def log_session(*, topics: str, draft: Optional[str] = None, date: Optional[str] = None,
                minutes: Optional[int] = None, kit: Optional[str] = None, coach: Optional[str] = None,
                movements: Optional[str] = None, fmt: Optional[str] = None, loads: str = "",
                rpe: str = "") -> str:
    """Check one session and add it to log.md; returns the "Logged: ..." line to print. The fields are the
    log-session command's: `draft` (the built draft; its movements: line, menu and build record give the
    movements, date, length, kit and coach) or `movements` (comma-separated, with `coach`, `minutes` and
    `kit`), the `topics`, the session method `fmt` (required with a draft), and `loads` and `rpe` as
    '<movement> = <value>; ...'. A refusal raises errors.LogRefused, a missing or clashing field
    errors.UsageError (named by its command-line flag)."""
    load_pairs = pairs(loads or "", "load", "load and tempo")
    rpe_pairs = pairs(rpe or "", "rpe", "effort")
    if bool(movements) == bool(draft):
        raise errors.UsageError("Not logged: give the movements with --movements or --draft (one of them).")
    if draft:
        date, minutes, kit, moves, build = from_draft(draft, date, minutes, kit)
        coach = build_coach(build, coach)
        build_id = build.get("build_id")
        if not (fmt or "").strip():
            raise errors.UsageError("Not logged: --format is required with --draft (the method you chose, from "
                                    "knowledge/sessions.toml), so the next session rotates away from it.")
    else:
        for flag, value in (("--coach", coach), ("--minutes", minutes), ("--kit", kit)):
            if value is None:
                raise errors.UsageError(f"Not logged: {flag} is required without --draft.")
        date, kit = date or dt.date.today().isoformat(), kit.strip()
        moves = [m.strip() for m in movements.split(",") if m.strip()]
        coach, build_id = coach.strip(), None
    session = sessionlog.Session(date, minutes, kit, coach, moves, topics.strip(),
                                 (fmt or "").strip() or None,
                                 named_pairs(load_pairs, moves, "load"), named_pairs(rpe_pairs, moves, "rpe"),
                                 build_id=build_id)
    _check_session_names(session, kit_from_menu=bool(draft))
    with locks.file_lock(paths.LOG):   # the duplicate check and the write as one step
        _check_not_logged(session)
        return "Logged: " + sessionlog.append_session(session)


def pairs(text, what, shape):
    """{movement: value} from '<movement> = <value>; ...' (--loads, --rpe), refusing an item not in that shape."""
    out = {}
    for item in text.split(";"):
        mv, sep, val = item.partition("=")
        if item.strip() and not (sep and mv.strip() and val.strip()):
            raise errors.LogRefused(f"Not logged: {what} '{item.strip()}' isn't '<movement> = <{shape}>'.")
        if sep:
            out[mv.strip()] = val.strip()
    return out


def declared_movements(path):
    """The movements a draft's `movements:` line declares, each by its catalog name when the catalog
    knows it."""
    if not os.path.exists(path):
        raise errors.LogRefused(f"Not logged: no draft at {show(path)}.")
    with open(path, encoding="utf-8") as f:
        words = draft.declared(f.read())
    if not words:
        raise errors.LogRefused(f"Not logged: {show(path)} has no movements: line.")
    cat = _catalog()
    found = [(cat.movements.get(w) or catalog.resolve(cat, w)) if cat else None for w in words]
    return list(dict.fromkeys(m.name if m else w for m, w in zip(found, words)))


def menu_kit(request):
    """The kit a menu's request names, as the log writes it: the profile kit's name, the preset's name, or
    "custom: <equipment ids>" for a brief run with --equipment (equipment added with --add isn't logged:
    the kit stays the kit)."""
    if request.get("kit"):
        return str(request["kit"])
    if request.get("preset"):
        return str(request["preset"])
    if request.get("equipment"):
        return "custom: " + ", ".join(request["equipment"])
    return None


def from_draft(path, date=None, minutes=None, kit=None):
    """(date, minutes, kit, movements, build) for a built draft: the movements from its movements: line, the
    date, length and kit from the menu beside it, and the newest build record of the draft as it stands. A
    typed date, length or kit must agree with the menu."""
    movements = declared_movements(path)
    menu_file = draft.menu_path(path)
    try:
        m = menu.load(menu_file)
    except (OSError, errors.ContextError) as e:
        raise errors.LogRefused(f"Not logged: the menu beside the draft can't be read ({show(menu_file)}: {e}).")
    if m is None:
        raise errors.LogRefused(f"Not logged: no menu beside the draft ({show(menu_file)}); a built draft has one.")
    shape = menu.validate(m)
    if shape:
        raise errors.LogRefused(f"Not logged: the menu beside the draft ({show(menu_file)}) won't do: {shape[0]}.")
    request = m["request"]
    want = {"--date": m.get("date"),
            "--minutes": request.get("minutes") or (m.get("seconds") or 0) // 60 or None,
            "--kit": menu_kit(request)}
    for flag, typed in (("--date", date), ("--minutes", minutes), ("--kit", kit)):
        if want[flag] is None:
            raise errors.LogRefused(f"Not logged: the menu ({show(menu_file)}) holds no {flag[2:]}.")
        if typed is not None and str(typed).strip().lower() != str(want[flag]).lower():
            raise errors.LogRefused(f"Not logged: {flag} {typed} disagrees with the menu's {want[flag]} "
                             f"({show(menu_file)}); leave it out, the menu gives it.")
    build = records.latest_build(records.draft_hash(path))
    if build is None:
        raise errors.LogRefused(f"Not logged: no build of {show(path)} as it stands (no record in {show(paths.BUILDS)} "
                         "with its hash). Build it first; if you edited it after building, build it again.")
    return want["--date"], int(want["--minutes"]), want["--kit"], movements, build


def build_coach(build, typed=None):
    """The coach to log for a session built as `build`: the build's own when none is typed; a typed one must be
    the same coach (by name or alias), since the next build takes its default coach from the log. A record from
    before builds named their coach takes the typed one."""
    built_as = (build.get("voice") or "").strip()
    typed = (typed or "").strip()
    if not built_as:
        if not typed:
            raise errors.LogRefused("Not logged: the build record names no coach; give it with --coach.")
        return typed
    if not typed:
        return built_as
    try:
        same = personas.lookup(typed, archived=True).slug == personas.lookup(built_as, archived=True).slug
    except errors.PROBLEMS:
        same = typed.lower() == built_as.lower()
    if not same:
        raise errors.LogRefused(f"Not logged: --coach {typed} disagrees with the build's coach, {built_as}; leave "
                                "--coach out, the build gives it.")
    return built_as


def named_pairs(items, movements, what):
    """{movement: value} with each movement written by its catalog name, refused unless it is one of the
    session's movements, so coverage can read the load back for that movement."""
    cat = _catalog()
    session = {catalog.key(cat, m) for m in movements}
    out = {}
    for name, value in items.items():
        key = catalog.key(cat, name)
        if key not in session:
            raise errors.LogRefused(f"Not logged: {what} for '{name}', which isn't one of the session's movements "
                             f"({', '.join(movements)}).")
        out[cat.movements[key].name if cat and key in cat.movements else name] = value
    return out


def _check_not_logged(session, path=None):
    """Refuse a second line for the same session: the same date and the same movements."""
    cat = _catalog()
    mine = {catalog.key(cat, m) for m in session.movements}
    for old in sessionlog.sessions(path, warn=False):
        if old.date == session.date and {catalog.key(cat, m) for m in old.movements} == mine:
            raise errors.LogRefused(f"Not logged: this session is already logged (log.md line {old.line}: {old.date}, "
                             f"{', '.join(old.movements)}).")


def _check_session_names(session, kit_from_menu=False):
    """A logged coach, kit and format must exist, so the next brief and coverage can read them back: the coach
    by name or alias (archived ones too, for old sessions), the kit from the profile or a catalog preset (one
    taken from the menu was checked by the brief), the format one of knowledge/sessions.toml's methods."""
    try:
        personas.lookup(session.voice, archived=True)
    except errors.PROBLEMS as e:
        raise errors.LogRefused(f"Not logged: no coach '{session.voice}' ({e.code})")
    if not kit_from_menu and os.path.exists(paths.PROFILE):   # with no profile there's nothing to check against
        known_kits = set(context.kits(context.profile())) | set(_catalog_presets())
        if session.kit.lower() not in {k.lower() for k in known_kits}:
            raise errors.LogRefused(f"Not logged: kit '{session.kit}' isn't one of the profile's kits or a catalog preset "
                             f"({', '.join(sorted(known_kits))}).")
    methods = sessions.load().methods
    if session.format and session.format not in methods:
        raise errors.LogRefused(f"Not logged: format '{session.format}' isn't a method in knowledge/sessions.toml "
                         f"({', '.join(methods)}).")


def _catalog():
    try:
        return catalog.default()
    except (*errors.PROBLEMS, ValueError, OSError):
        return None   # the catalog's own check says what's wrong


def _catalog_presets():
    cat = _catalog()
    return cat.presets if cat else {}
