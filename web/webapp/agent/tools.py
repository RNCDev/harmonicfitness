"""The agent's tools, as in Claude Code: run a `./harmonicfitness` command, read a file, write a file, list
files. Paths are written as the skills write them: `me/...` is the user's own folder (this job's temporary
copy of it), and `knowledge/`, `.claude/skills/` and `coaches/` are the engine's, read-only. Nothing else
is reachable. Keys reach the engine only through engine.run's extra_env; `me/.env` is never read or written.

The engine's own checks (the brief's menu, the build's gate) keep a workout safe; these tools only keep
the agent inside the user's folder and away from what this web client can't do yet."""
import hashlib
import json
import os
import re
import threading
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from webapp import engine, folder

LIMIT = 120_000         # what a tool's output or a read may hand the model, in characters (a full brief is ~87,000)
WRITE_LIMIT = 200_000   # the most a write may hold, in characters
LIST_LIMIT = 500        # files a listing names
CUT = "[cut]"
TIMEOUT = 300           # seconds for one engine command; the engine's cold start can be slow
BUILD_TIMEOUT = 600     # a full build: a pending coach's voice design, then the web voice renders every line

ENGINE_READ = ("knowledge/", ".claude/skills/", "coaches/")

# The commands the agent may run, and for some, the only subcommands. Everything else (setup, keys init,
# migrate, backup, models, cache) isn't part of this web client yet. `coaches make` designs a stock web
# coach's voice in the listener's account (about a cent), as setup's quick start does. Coaches are chosen here,
# never made (since 0.46.2): no `audition` or `keep`; `forget-audition` stays, to close one opened before.
COMMANDS = {"brief", "build", "check", "content", "coaches", "coverage", "feeds", "get", "help", "interests", "keys",
            "log-session", "movements", "workouts", "youtube"}
SUBCOMMANDS = {"coaches": {None, "list", "last", "measured", "make", "forget-audition", "archive"},
               "keys": {None}}
MADE_MP3 = (0, 2)   # the build's exits that made an MP3 (2: its total ran a little off plan)
RECORDED_NOTE = ("Recorded: the MP3 is saved and shows in the chat by itself. This workout is final: don't lint, "
                 "rewrite or build it again. Log the session as the skill says, then end your turn in one line.")
AFTER_RECORDING = ("this workout is already recorded and final for this turn: don't lint, rewrite or build it "
                   "again. Log the session, then end your turn; a new recording needs a new price and the "
                   "listener's Record, next turn.")
SLOW = {("coaches", "make"), ("coaches", "audition"), ("coaches", "keep")}   # a service designs or saves a voice


@dataclass
class Deps:
    engine_root: str
    home: str
    keys: dict[str, str] = field(repr=False)
    today: str
    now: str
    # tells the listener what the coach is doing, as it happens: (step text, tool name, exit code, step id).
    # A step is said twice under one id: with code None when its tool starts, then with the tool's exit code.
    # A thinking step (the model working between tools) is said with think=True: shown while it runs, then dropped.
    say: Callable[..., None] | None = field(default=None, repr=False)
    # `feeds`, started in the background as the turn began: `run feeds` waits for it instead of running again
    feeds: Future | None = field(default=None, repr=False)
    cancel: threading.Event | None = field(default=None, repr=False)   # the listener's Stop
    auditions: int = 0               # auditions run this turn: one, since each is paid for and heard first
    approved: dict | None = None     # the recording the listener approved this turn (the offer, as made)
    chars_left: int | None = None    # what today's allowance has left, in characters
    offer: dict | None = None        # set when a build was priced and waits for the listener's approval
    setup: bool = False              # the setup skill comes with the workout skill this turn
    coach: bool = False              # the coach skill comes too: a coach is being made, or an audition is open
    coach_done: bool = False         # a candidate was kept or the audition closed: the next turn needs no skill
    steps: int = 0                   # the last step id said this turn
    lint_failed: bool = False        # the last check of the script failed: the next draft is a fix, not a first go
    phase: str = ""                  # what the turn last did (THINK in agent): names what the model is thinking about
    picked: tuple[str, str] | None = None   # the coach chosen on the page (Settings or the sentence): (slug, day)
    recorded: str | None = None      # the draft recorded this turn: the approval is spent, and that workout is final
    auto_record: bool = False        # Settings' Record without asking: a clean price records at once
    # reserves characters from today's allowance (and commits), as the Record button does; whether it fit
    reserve: Callable[[int], bool] | None = field(default=None, repr=False)
    # the last clean lint: (draft, coach, the draft's sha256, characters it sends), so pricing the same text
    # with the same coach needn't lint it again
    linted: tuple | None = None
    # saves what the recording made (the coach, the MP3, the clips) at once, so a later stop can't lose it
    checkpoint: Callable[[], None] | None = field(default=None, repr=False)


class ToolResult(BaseModel):
    code: int
    output: str = ""
    error: str = ""
    # the site refused the call itself (a command or path it won't run): the model's to fix, not the
    # listener's to see as a failed step. Never sent to the model.
    refused: bool = Field(default=False, exclude=True)


def _cut(text: str, limit: int = LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + CUT


def _result(code: int, output: str = "", error: str = "") -> ToolResult:
    return ToolResult(code=code, output=_cut(output), error=_cut(error, 20_000))


def _refuse(message: str) -> ToolResult:
    r = _result(64, error=message)
    r.refused = True
    return r


def _inside(base: str, rel: str) -> str | None:
    """`rel` under `base` as an absolute path, or None when it escapes (.., an absolute path, a symlink out)."""
    if not rel or rel.startswith("/") or "\\" in rel or "\x00" in rel or ".." in rel.split("/"):
        return None
    full = os.path.realpath(os.path.join(base, rel))
    root = os.path.realpath(base)
    return full if full == root or full.startswith(root + os.sep) else None


def _mine(deps: Deps, path: str) -> tuple[str | None, str]:
    """A `me/...` path as (absolute path, path inside the folder), or (None, why not)."""
    if path in ("me", "me/"):
        return os.path.realpath(deps.home), ""
    if not path.startswith("me/"):
        return None, "write paths as the skills do: me/... for the listener's folder"
    rel = path[3:].rstrip("/")
    full = _inside(deps.home, rel)
    if full is None:
        return None, "that path leaves the listener's folder"
    if rel == ".env" or rel.endswith("/.env") or rel.startswith(".env"):
        return None, "me/.env is never read or written: keys are entered in Settings"
    return full, rel


def _arg(deps: Deps, value: str) -> str | None:
    """One argument for the engine: a `me/...` path becomes the folder's own path; any other path is refused."""
    if not isinstance(value, str) or "\x00" in value or "\n" in value:
        return None
    flag, eq, rest = value.partition("=") if value.startswith("--") and "=" in value else ("", "", value)
    if rest.startswith("me/") or rest == "me":
        full, _ = _mine(deps, rest)
        if full is None:
            return None
        rest = full
    elif rest.startswith("/") or ".." in rest.split("/"):
        return None
    return f"{flag}{eq}{rest}" if eq else rest


def run(deps: Deps, args: list[str]) -> ToolResult:
    if not (isinstance(args, list) and args and all(isinstance(a, str) for a in args) and len(args) <= 60):
        return _refuse("args must be a list of strings, the command first: [\"brief\", \"--goal\", ...]")
    if args[0] == "./harmonicfitness":
        args = args[1:]
    command = args[0] if args else ""
    if command not in COMMANDS:
        return _refuse(f"{command or 'nothing'} isn't available here; the commands are {', '.join(sorted(COMMANDS))}")
    sub = args[1] if len(args) > 1 and not args[1].startswith("-") else None
    if command == "coaches" and sub in ("audition", "keep"):
        return _refuse("coaches are chosen on this site, not made: point the listener to the Coaches page "
                       "(beside Logs, at the top); a coach of their own is made with HarmonicFitness on their own "
                       "computer")
    if command in SUBCOMMANDS and sub not in SUBCOMMANDS[command]:
        return _refuse(f"{command} {sub} isn't available in the web client yet")
    if command == "build" and deps.recorded:
        return _refuse(AFTER_RECORDING)
    if command == "build" and any(a in ("--follow", "--clips-only", "--verbose") for a in args):
        return _refuse("--follow, --clips-only and --verbose aren't for the web client: run the build itself")
    if (command, sub) == ("coaches", "audition"):
        if "--play" in args:
            return _refuse("--play isn't for the web client: the candidates play in the chat by themselves")
        if deps.auditions:
            return _refuse("one audition a turn: let the listener hear these candidates first, then audition "
                           "again next turn if none is right")
    if command == "feeds" and deps.feeds is not None:
        try:
            return deps.feeds.result(timeout=TIMEOUT)
        except Exception:  # noqa: BLE001 - the background run failed or hung: run it here instead
            pass
    argv = []
    for a in args:
        mapped = _arg(deps, a)
        if mapped is None:
            return _refuse(f"{a!r}: paths must be me/... inside the listener's folder")
        argv.append(mapped)
    if command == "build" and "--lint-only" not in args:
        return _record(deps, args, argv)
    if command == "build":   # a lint: remembered when clean, for the price that follows
        deps.linted = None
        r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=TIMEOUT, cancel=deps.cancel)
        if r.code == 0 and len(argv) > 1:
            deps.linted = (args[1], _flag(args, "--coach"), _digest(argv[1]), _sends(r.stdout + r.stderr))
        return _result(r.code, *(_mine_text(deps, t) for t in (r.stdout, r.stderr)))
    slow = (command, sub) in SLOW
    if (command, sub) == ("coaches", "audition"):
        deps.auditions += 1   # counted when sent: a failed audition may still have paid for a design
    r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=BUILD_TIMEOUT if slow else TIMEOUT,
                   cancel=deps.cancel)
    if command == "coaches" and sub in ("keep", "forget-audition") and r.code == 0:
        deps.coach_done = True
    home = os.path.realpath(deps.home)
    # the engine prints the folder's real path; the agent knows it as me/
    return _result(r.code, r.stdout.replace(home, "me").replace(deps.home, "me"),
                   r.stderr.replace(home, "me").replace(deps.home, "me"))


def _read(full: str) -> ToolResult:
    try:
        with open(full, encoding="utf-8") as f:
            return _result(0, f.read(LIMIT + 1))
    except FileNotFoundError:
        return _result(1, error="no such file")
    except IsADirectoryError:
        return _result(1, error="that's a folder: use list_files")
    except (OSError, UnicodeDecodeError):
        return _result(1, error="that file can't be read as text")


def read_file(deps: Deps, path: str) -> ToolResult:
    if not isinstance(path, str):
        return _refuse("path must be a string")
    if path.startswith("me/"):
        full, why = _mine(deps, path)
        return _refuse(why) if full is None else _read(full)
    if path.startswith(ENGINE_READ):
        full = _inside(deps.engine_root, path)
        if full is None or not any(full.startswith(os.path.realpath(os.path.join(deps.engine_root, p)))
                                   for p in ENGINE_READ):
            return _refuse("that path leaves the engine's knowledge")
        return _read(full)
    return _refuse(f"readable: me/... and the engine's {', '.join(ENGINE_READ)}")


def write_file(deps: Deps, path: str, content: str) -> ToolResult:
    if not (isinstance(path, str) and isinstance(content, str)):
        return _refuse("path and content must be strings")
    full, rel = _mine(deps, path)
    if full is None:
        return _refuse(rel)
    if not rel:
        return _refuse("give a file's path: me/...")
    if folder.skipped(rel):
        return _refuse("that kind of file isn't kept here")
    if rel.startswith(folder.AUDITIONS) and "/" in rel[len(folder.AUDITIONS):]:
        return _refuse("an audition's own files are the engine's: write only the narrative, "
                       "me/coaches/.auditions/<slug>.md")
    if len(content) > WRITE_LIMIT:
        return _refuse(f"too long: at most {WRITE_LIMIT} characters")
    if deps.recorded and rel.endswith(".draft.txt"):
        return _refuse(AFTER_RECORDING)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    tmp = full + ".tmp-write"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, full)
    if rel.endswith(".draft.txt"):   # the request's length is the brief's: check them against it before linting
        return _result(0, f"wrote {path} ({len(content)} characters): {_adds_up(content)}")
    return _result(0, f"wrote {path} ({len(content)} characters)")


SEGMENT = re.compile(r"^@@\s*\d+\s*\|")   # a draft's segment marker, as tools/draft.py reads it


class SegmentEdit(BaseModel):
    number: int = Field(description="the segment's place in the draft, from 1: the lint's # column")
    text: str = Field(description="the whole new segment, its own @@ <seconds> | <label> line first")


SECONDS = re.compile(r"^@@\s*(\d+)\s*\|", re.MULTILINE)
EDIT_MAX = 40   # segments one edit may carry


def _adds_up(text: str) -> str:
    """What a draft's segments add up to, said for the writer to check against the request."""
    total = sum(int(m) for m in SECONDS.findall(text))
    return f"{len(SECONDS.findall(text))} segments adding up to {total} s ({total / 60:g} min)"


def edit_segments(deps: Deps, path: str, edits: list) -> ToolResult:
    """Replace segments of a draft in one go, each by its place from 1 (the lint's # column) with the whole new
    segment, `@@` line first: every fix one lint names, in one call. All or nothing: nothing is written when any
    edit can't apply."""
    if not isinstance(path, str) or not path.endswith(".draft.txt"):
        return _refuse("edit_segments edits a draft (me/workouts/<stem>/<stem>.draft.txt); use write_file otherwise")
    if not isinstance(edits, list) or not edits or len(edits) > EDIT_MAX:
        return _refuse(f"edits must be a list of 1 to {EDIT_MAX} {{number, text}}")
    full, rel = _mine(deps, path)
    if full is None:
        return _refuse(rel)
    if deps.recorded:
        return _refuse(AFTER_RECORDING)
    try:
        with open(full, encoding="utf-8") as f:
            old = f.read().split("\n")
    except FileNotFoundError:
        return _result(1, error="no such draft yet: write it with write_file first")
    starts = [i for i, x in enumerate(old) if SEGMENT.match(x)]
    wanted = {}
    for e in edits:
        number = e.get("number") if isinstance(e, dict) else getattr(e, "number", None)
        text = e.get("text") if isinstance(e, dict) else getattr(e, "text", None)
        if type(number) is not int or not isinstance(text, str):
            return _refuse("each edit is {number: a whole number, text: the segment}")
        if not 1 <= number <= len(starts):
            return _refuse(f"the draft has {len(starts)} segments: number must be 1 to {len(starts)} (not {number})")
        if number in wanted:
            return _refuse(f"segment {number} is edited twice: one edit a segment")
        lines = text.strip("\n").split("\n")
        if not SEGMENT.match(lines[0]) or any(SEGMENT.match(x) for x in lines[1:]):
            return _refuse(f"edit {number}: text must be exactly one segment, its own @@ <seconds> | <label> line "
                           "first, then its lines")
        wanted[number] = lines
    out = old[:starts[0]] if starts else list(old)
    for n, begin in enumerate(starts, 1):
        end = starts[n] if n < len(starts) else len(old)
        if n in wanted:
            last = n == len(starts)
            out += wanted[n] + ([""] if not last or (old and old[-1] == "") else [])
        else:
            out += old[begin:end]
    new = "\n".join(out)
    if len(new) > WRITE_LIMIT:
        return _refuse(f"too long: at most {WRITE_LIMIT} characters")
    tmp = full + ".tmp-write"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, full)
    return _result(0, f"replaced segment{'s' if len(wanted) > 1 else ''} {', '.join(map(str, sorted(wanted)))} in "
                      f"{path}: now {_adds_up(new)}")


def list_files(deps: Deps, path: str = "me/") -> ToolResult:
    full, why = _mine(deps, path if path.startswith("me") else "")
    if full is None:
        return _refuse(why)
    if not os.path.isdir(full):
        return _result(1, error="no such folder")
    home = os.path.realpath(deps.home)
    names = []
    for dirpath, dirs, files in os.walk(full):
        dirs.sort()
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, name), home).replace(os.sep, "/")
            if not folder.skipped(rel):
                names.append("me/" + rel)
            if len(names) >= LIST_LIMIT:
                return _result(0, "\n".join(names) + f"\n[more than {LIST_LIMIT}: list a smaller folder]")
    return _result(0, "\n".join(names) or "(empty)")


SPEAKS = re.compile(r"the script speaks ([\d,]+) characters")
SENDS = re.compile(r"Sends ([\d,]+) characters to the voice service")   # a web voice's lint, since 0.48.0


def _sends(text: str) -> int | None:
    found = SENDS.search(text) or SPEAKS.search(text)
    return int(found.group(1).replace(",", "")) if found else None


def _digest(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def _flag(args: list[str], name: str) -> str | None:
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def _record(deps: Deps, args: list[str], argv: list[str]) -> ToolResult:
    """A full build sends the script to a paid voice service, so it runs only once the listener has
    approved this draft with this coach, within the price they saw: until then it's priced and offered."""
    draft, coach = (args[1] if len(args) > 1 else ""), _flag(args, "--coach")
    if not draft.startswith("me/") or len(args) < 3 or not coach:
        return _refuse('run it as build "me/workouts/<stem>/<stem>.draft.txt" "<name>" --coach "<coach>"')
    ok = deps.approved
    if ok and ok.get("draft") == draft and ok.get("coach") == coach:
        deps.approved = None   # one approval, one recording: another needs a new price and the listener's Record
        cap = ok["chars"]
        if _flag(args, "--max-chars") is None:
            argv = argv + ["--max-chars", str(cap)]
        r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=BUILD_TIMEOUT,
                       cancel=deps.cancel)
        if r.code in MADE_MP3:
            deps.recorded = draft   # the agent's run tool saves it (deps.checkpoint) once its steps are said
        out, err = (_mine_text(deps, t) for t in (r.stdout, r.stderr))
        if r.code in MADE_MP3:
            out += "\n" + RECORDED_NOTE
        return _result(r.code, out, err)
    seen = deps.linted
    if seen and seen[3] is not None and seen[:3] == (draft, coach, _digest(argv[1])):
        chars = seen[3]   # linted clean just now, as it stands: no second lint
    else:
        lint = engine.run(deps.engine_root, deps.home, argv + ["--lint-only"], extra_env=deps.keys, timeout=TIMEOUT,
                          cancel=deps.cancel)
        if lint.code != 0:   # fix the draft first: nothing is priced, offered or billed
            return _result(lint.code, *(_mine_text(deps, t) for t in (lint.stdout, lint.stderr)))
        chars = _sends(lint.stdout + lint.stderr)
    if chars is None:   # an engine from before 0.48.0 prints no count: ask it the old way
        count = engine.run(deps.engine_root, deps.home, argv + ["--lint-only", "--max-chars", "1"], extra_env=deps.keys,
                           timeout=TIMEOUT, cancel=deps.cancel)
        chars = _sends(count.stdout + count.stderr)
    if chars is None:
        return _refuse("couldn't count the script's characters for its price; this coach may not be a web coach")
    priced = engine.run(deps.engine_root, deps.home, ["get", "cost", "--coach", coach, "--chars", str(chars), "--json"],
                        extra_env=deps.keys, timeout=TIMEOUT, cancel=deps.cancel)
    try:
        cost = json.loads(priced.stdout)
    except ValueError:
        return _result(priced.code or 1, priced.stdout, priced.stderr)
    usd = float(cost.get("usd") or 0) + (float(cost.get("design_usd") or 0) if cost.get("pending_design") else 0)
    if deps.chars_left is not None and chars > deps.chars_left:
        return _refuse(f"not recorded: the script speaks {chars:,} characters and today's allowance has "
                       f"{max(deps.chars_left, 0):,} left. Tell the listener; a shorter workout fits, or tomorrow.")
    deps.offer = {"draft": draft, "name": args[2], "coach": coach, "chars": chars, "usd": round(usd, 3),
                  "service": cost.get("service"), "design": bool(cost.get("pending_design"))}
    return _result(0, (f"Not recorded yet: recording sends {chars:,} characters to {cost.get('service')} for about "
                       f"${usd:.2f}{' (including the coach voice design)' if cost.get('pending_design') else ''}. "
                       "The page now shows the listener a Record button with that price. End your turn: say in a "
                       "line that the script is ready and checked (the button shows the price: don't say it). Don't build again "
                       "until they approve."))


def _mine_text(deps: Deps, text: str) -> str:
    home = os.path.realpath(deps.home)
    return text.replace(home, "me").replace(deps.home, "me")
