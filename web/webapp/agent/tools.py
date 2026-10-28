"""The agent's tools, as in Claude Code: run a `./harmonicfitness` command, read a file, write a file, list
files. Paths are written as the skills write them: `me/...` is the user's own folder (this job's temporary
copy of it), and `knowledge/`, `.claude/skills/` and `coaches/` are the engine's, read-only. Nothing else
is reachable. Keys reach the engine only through engine.run's extra_env; `me/.env` is never read or written.

The engine's own checks (the brief's menu, the build's gate) keep a workout safe; these tools only keep
the agent inside the user's folder and away from what this web client can't do yet."""
import os
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

ENGINE_READ = ("knowledge/", ".claude/skills/", "coaches/")
READ_ONLY = ("health.md",)   # the check-in can't change limits here yet: tell the listener instead

# The commands the agent may run, and for some, the only subcommands. Everything else (setup, keys init,
# migrate, backup, models, cache, a coach's audition or make) isn't part of this web client yet.
COMMANDS = {"brief", "build", "check", "content", "coaches", "coverage", "feeds", "get", "help", "keys",
            "log-session", "movements", "youtube"}
SUBCOMMANDS = {"coaches": {None, "list", "last", "measured"}, "keys": {None}}


@dataclass
class Deps:
    engine_root: str
    home: str
    keys: dict[str, str] = field(repr=False)
    today: str
    now: str
    # tells the listener what the coach is doing, as it happens: (step text, tool name, exit code or None)
    say: Callable[[str, str, int | None], None] | None = field(default=None, repr=False)
    # `feeds`, started in the background as the turn began: `run feeds` waits for it instead of running again
    feeds: Future | None = field(default=None, repr=False)


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
        return None, "me/.env is never read or written: keys are entered in Keys"
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
    if command == "build" and "--lint-only" not in args:
        return _refuse("the web client can't make the audio yet: run build with --lint-only to check the draft, "
                       "then tell the listener the script is ready and the audio comes in a later version")
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
    r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=TIMEOUT)
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
    if not rel or rel in READ_ONLY:
        return _refuse("me/health.md can't be changed here yet: tell the listener what you'd change, and use "
                       "--limit on the brief for today")
    if folder.skipped(rel):
        return _refuse("that kind of file isn't kept here")
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
