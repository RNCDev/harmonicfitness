"""The agent's tools, as in Claude Code: run a `./harmonicfitness` command, read a file, write a file, list
files. Paths are written as the skills write them: `me/...` is the user's own folder (this job's temporary
copy of it), and `knowledge/`, `.claude/skills/` and `coaches/` are the engine's, read-only. Nothing else
is reachable. Keys reach the engine only through engine.run's extra_env; `me/.env` is never read or written.

The engine's own checks (the brief's menu, the build's gate) keep a workout safe; these tools only keep
the agent inside the user's folder and away from what this web client can't do yet."""
import json
import os
import re
import threading
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field

from pydantic import BaseModel

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
# coach's voice in the listener's account (about a cent), as setup's quick start does; `audition`, `keep`
# and `forget-audition` make a web coach of their own, as the coach skill says.
COMMANDS = {"brief", "build", "check", "content", "coaches", "coverage", "feeds", "get", "help", "keys",
            "log-session", "movements", "workouts", "youtube"}
SUBCOMMANDS = {"coaches": {None, "list", "last", "measured", "make", "audition", "keep", "forget-audition",
                           "archive"},
               "keys": {None}}
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


class ToolResult(BaseModel):
    code: int
    output: str = ""
    error: str = ""


def _cut(text: str, limit: int = LIMIT) -> str:
    return text if len(text) <= limit else text[:limit] + CUT


def _result(code: int, output: str = "", error: str = "") -> ToolResult:
    return ToolResult(code=code, output=_cut(output), error=_cut(error, 20_000))


def _refuse(message: str) -> ToolResult:
    return _result(64, error=message)


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
    if command in SUBCOMMANDS and sub not in SUBCOMMANDS[command]:
        return _refuse(f"{command} {sub} isn't available in the web client yet")
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
    os.makedirs(os.path.dirname(full), exist_ok=True)
    tmp = full + ".tmp-write"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, full)
    return _result(0, f"wrote {path} ({len(content)} characters)")


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
        cap = ok["chars"]
        if _flag(args, "--max-chars") is None:
            argv = argv + ["--max-chars", str(cap)]
        r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=BUILD_TIMEOUT,
                       cancel=deps.cancel)
        return _result(r.code, *(_mine_text(deps, t) for t in (r.stdout, r.stderr)))
    lint = engine.run(deps.engine_root, deps.home, argv + ["--lint-only"], extra_env=deps.keys, timeout=TIMEOUT,
                      cancel=deps.cancel)
    if lint.code != 0:   # fix the draft first: nothing is priced, offered or billed
        return _result(lint.code, *(_mine_text(deps, t) for t in (lint.stdout, lint.stderr)))
    count = engine.run(deps.engine_root, deps.home, argv + ["--lint-only", "--max-chars", "1"], extra_env=deps.keys,
                       timeout=TIMEOUT, cancel=deps.cancel)
    found = SPEAKS.search(count.stdout + count.stderr)
    if not found:
        return _refuse("couldn't count the script's characters for its price; this coach may not be a web coach")
    chars = int(found.group(1).replace(",", ""))
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
