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
BUILD_TIMEOUT = 600     # the least a full build gets: a pending coach's voice design, then the web voice renders every line
RECORD_SHARE = 1.0      # a recording may take up to the workout's own length: thirty minutes for a thirty-minute one
TURN_FINISH = 120       # seconds the turn keeps past its recording's limit, to keep the MP3 and end

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
    # the draft just written is a "skeleton" (no words yet) or "partial" (segments still empty): its build is a
    # lint, whose report is the word budgets; "" otherwise
    skeleton: str = ""
    # each skeleton written this turn, by its draft's path: its segments as (seconds, label), the clock the full
    # draft is held to
    skeletons: dict[str, list] = field(default_factory=dict)
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
    # the turn's clock: gives it at least this many seconds more from now, for a recording's whole limit
    extend_turn: Callable[[float], None] | None = field(default=None, repr=False)
    # the coach the turn's `brief` was run for: a draft written without its build's coach builds with this one
    brief_coach: str | None = None
    # each draft's last "add about N words" as shown to the writer, and its words then: (shown, words), so the
    # next ask is scaled by how much of that one the writer delivered
    asks: dict[str, tuple[int, int]] = field(default_factory=dict)
    # who writes the script's words: "three" (the writers' room: a trainer, a researcher, a host and the trainer's review, `write_script`; the
    # site's way since 0.51.0, which run_turn sets) or "one" (this agent, in passes; HARMONICFITNESS_WRITERS=one)
    writers: str = "one"
    # each skeleton's last lint report, by its draft's path: the word budgets the writers write to
    reports: dict[str, str] = field(default_factory=dict)
    # the personal content writer, started as the brief runs (three writers): its future, and the draft it writes for
    content_job: object = field(default=None, repr=False)
    content_for: str | None = None
    # a workout for later (0.60.0): the conversation's plan for it (conversations.Conversation.later), what
    # schedule_workout worked out for "Schedule it", whether this is the turn that writes it, and the characters
    # the listener's "Schedule it" approved
    later: dict | None = None
    schedule: dict | None = None
    scheduled_run: bool = False
    ceiling: int | None = None
    # the researcher's conversation, for a top-up once the skeleton has more places than it wrote for
    research_history: object = field(default=None, repr=False)
    loop: object = field(default=None, repr=False)   # the turn's event loop, which the personal content writer runs on
    # the web searches the writers' room ran this turn (the researcher's): the turn's usage counts them with its own
    room_searches: int = 0
    # a line for the worker's log about the writers' room (each writer's and lint's time, never what it read or
    # wrote); None in tests
    log: Callable[[str], None] | None = field(default=None, repr=False)
    # the writers' room started by a clean skeleton (agent._chain): its future, cancelled when the turn ends
    room_job: object = field(default=None, repr=False)
    ended: threading.Event = field(default_factory=threading.Event, repr=False)   # set as the turn's run ends


class ToolResult(BaseModel):
    code: int
    output: str = ""
    error: str = ""
    # the site refused the call itself (a command or path it won't run): the model's to fix, not the
    # listener's to see as a failed step. Never sent to the model.
    refused: bool = Field(default=False, exclude=True)
    # a draft just written is built right after, unless its seconds don't add up to the request (the write says
    # what to fix first). Never sent to the model.
    build: bool = Field(default=True, exclude=True)
    # a draft just written: its segments, and how many hold no words yet (all of them: a skeleton). Until every
    # segment has words the build is a lint, whose report is the budgets. Never sent to the model.
    segments: int = Field(default=0, exclude=True)
    unfinished: int = Field(default=0, exclude=True)


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
    if command == "feeds":
        got = None
        if deps.feeds is not None:
            try:
                got = deps.feeds.result(timeout=TIMEOUT)
            except Exception:  # noqa: BLE001 - the background run failed or hung: run it here instead
                got = None
        if got is None:
            got = _plain_run(deps, ["feeds"] + [a for a in args[1:] if a == "--refresh"])
        return _with_sheet(deps, got)
    argv = []
    for a in args:
        mapped = _arg(deps, a)
        if mapped is None:
            return _refuse(f"{a!r}: paths must be me/... inside the listener's folder")
        argv.append(mapped)
    if command == "brief" and deps.later and not deps.scheduled_run:
        return _refuse(f"this workout is for {deps.later.get('local', 'later')}: finish the check-in, then call "
                       "schedule_workout and end your turn with the plan in a line. The brief, the research and the "
                       "script come fifteen minutes before, so the news, the weather and the menu are fresh.")
    if command == "brief" and _flag(args, "--coach"):
        deps.brief_coach = _flag(args, "--coach")
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


def _plain_run(deps: Deps, argv: list[str]) -> ToolResult:
    r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=TIMEOUT, cancel=deps.cancel)
    return _result(r.code, _mine_text(deps, r.stdout), _mine_text(deps, r.stderr))


def _with_sheet(deps: Deps, got: ToolResult) -> ToolResult:
    """`feeds` prints only the weather; here its sheet comes with it, so reading it isn't another round trip."""
    if got.code != 0 or not deps.today:
        return got
    sheet = os.path.join(deps.home, "workouts", "research", "daily", f"{deps.today}-feeds.md")
    try:
        with open(sheet, encoding="utf-8") as f:
            text = f.read(LIMIT)
    except OSError:
        return got
    return got.model_copy(update={"output": got.output + f"\n\n### the feeds sheet (me/workouts/research/daily/"
                                  f"{deps.today}-feeds.md; already read: don't read it again)\n" + text})


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
    if folder.COACH_SAMPLE.fullmatch(rel):
        return _refuse("a coach's sample is the engine's: it's made when the coach is kept")
    if rel.startswith(folder.AUDITIONS) and "/" in rel[len(folder.AUDITIONS):]:
        return _refuse("an audition's own files are the engine's: write only the narrative, "
                       "me/coaches/.auditions/<slug>.md")
    if len(content) > WRITE_LIMIT:
        return _refuse(f"too long: at most {WRITE_LIMIT} characters")
    if deps.recorded and rel.endswith(".draft.txt"):
        return _refuse(AFTER_RECORDING)
    split = 0
    note = ""
    if rel.endswith(".draft.txt"):
        content, split = split_long(content)
        content, _ = contract(content)
        if is_skeleton(content):
            content, note = settle_clock(content, _request_seconds(full))
            note += long_rests(content)
            deps.skeletons[rel] = segments_of(content)
        else:
            content, note = hold_clock(content, deps.skeletons.get(rel), _request_seconds(full))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    tmp = full + ".tmp-write"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, full)
    if rel.endswith(".draft.txt"):   # the request's length is the brief's: check them against it before linting
        out = _result(0, f"wrote {path} ({len(content)} characters): {_adds_up(content)}.{_split_note(split)}{note}")
        out.build = not note.startswith(NOT_BUILT)
        out.segments, out.unfinished = empty_segments(content)
        return out
    return _result(0, f"wrote {path} ({len(content)} characters)")


SEGMENT = re.compile(r"^@@\s*\d+\s*\|")   # a draft's segment marker, as tools/draft.py reads it


class SegmentEdit(BaseModel):
    number: int = Field(description="the segment's place in the draft, from 1: the lint's # column")
    text: str = Field(description="the whole new segment, its own @@ <seconds> | <label> line first")


SECONDS = re.compile(r"^@@\s*(\d+)\s*\|", re.MULTILINE)
EDIT_MAX = 40   # segments one edit may carry


MARK = re.compile(r"\[[^\]]*\]")
WORD = re.compile(r"[A-Za-z0-9']+")


def _words(text: str) -> int:
    """A draft's spoken words: every line but the header and the @@ lines, markers taken out."""
    spoken = [MARK.sub(" ", ln) for ln in text.split("\n") if not ln.startswith(("@@", "movements:"))]
    return sum(len(WORD.findall(ln)) for ln in spoken)


BODIES = re.compile(r"^@@[^\n]*$", re.MULTILINE)


def empty_segments(text: str) -> tuple[int, int]:
    """(segments, those with no spoken words yet) in a draft."""
    bodies = BODIES.split(text)[1:]
    return len(bodies), sum(_words(b) == 0 for b in bodies)


def is_skeleton(text: str) -> bool:
    """A draft with its @@ segments (and their markers) but no words yet: written first, so its build gives each
    segment's word budget before the words are written."""
    n, empty = empty_segments(text)
    return n > 0 and empty == n


LABEL = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*?)\s*$", re.MULTILINE)
NOT_BUILT = " Not built:"


def segments_of(text: str) -> list:
    """A draft's segments as (seconds, label)."""
    return [(int(m.group(1)), m.group(2)) for m in LABEL.finditer(text)]


def _request_seconds(full: str) -> int | None:
    """The request's seconds from the menu beside the draft at `full` (brief --save wrote both), or None."""
    try:
        with open(full[:-len(".draft.txt")] + ".menu.json", encoding="utf-8") as f:
            seconds = json.load(f).get("seconds")
    except (OSError, ValueError, AttributeError):
        return None
    return seconds if isinstance(seconds, int) and seconds > 0 else None


# a skeleton this close to the request is settled here: the difference spread over its rests (0.59.0: ten percent;
# at three, skeletons 3 to 6 percent off went back to the agent up to three times, about 18 s, 2026-11-03)
SETTLE = 0.10
LONGEST_REST = 120   # no dose in sessions.toml rests longer than two minutes: a rest past it is padding
REST_LABEL = re.compile(r"rest|transition|breath|recover|walk|set-?up|shake", re.IGNORECASE)


def _retime(text: str, seconds: list[int]) -> str:
    """`text` with its @@ lines' seconds replaced, in order."""
    fixed = iter(seconds)
    return LABEL.sub(lambda m: f"@@ {next(fixed)} | {m.group(2)}", text)


def settle_clock(text: str, want: int | None) -> tuple[str, str]:
    """A skeleton within SETTLE of the request, settled to it: the difference spread over its rests (every segment
    when none is labelled as one), in steps of five seconds, since a writer told "add 15 s" re-planned the whole
    skeleton five or six times (0.50.0's loops); (the text, a note). Further off, or where a rest would end under
    ten seconds or change by more than half its length, it's left to the writer."""
    segs = segments_of(text)
    total = sum(s for s, _ in segs)
    if not want or total == want or abs(total - want) > SETTLE * want:
        return text, ""
    diff = want - total
    idx = [i for i, (_, label) in enumerate(segs) if REST_LABEL.search(label)] or list(range(len(segs)))
    weight = sum(segs[i][0] for i in idx)
    shares = [round(diff * segs[i][0] / weight / 5) * 5 for i in idx]
    shares[-1] += diff - sum(shares)
    seconds = [s for s, _ in segs]
    for i, share in zip(idx, shares):
        seconds[i] += share
    if any(seconds[i] < 10 or abs(seconds[i] - segs[i][0]) > segs[i][0] / 2 for i in idx):
        return text, ""
    changed = [f"{segs[i][1]} {segs[i][0]} to {seconds[i]}" for i, share in zip(idx, shares) if share]
    return _retime(text, seconds), (f" The segments added up to {total} s: {abs(diff)} s {'given to' if diff > 0 else 'taken from'} "
                                    f"the rests ({'; '.join(changed)}), so they add up to the request's {want} s.")


def long_rests(text: str) -> str:
    """A note naming a skeleton's rests over LONGEST_REST seconds, or ""."""
    long = [f"{label} ({secs} s)" for secs, label in segments_of(text) if REST_LABEL.search(label) and secs > LONGEST_REST]
    return (f" Rests over two minutes: {', '.join(long)}. No dose rests longer than that: give the time to work "
            "(another set, or a movement the week hasn't trained).") if long else ""


def hold_clock(text: str, skeleton: list | None, want: int | None) -> tuple[str, str]:
    """The draft held to the request's clock: (the text, a note). A draft whose segments add up to the request
    passes as written. One that keeps its skeleton's segments but not their seconds gets the skeleton's back
    (it was written to those budgets). Any other draft off the clock isn't built: the note says how far off and
    which of the skeleton's segments it dropped or added, for one edit, since a writer told only the total
    rewrote the whole draft two or three times (0.50.0's loops)."""
    segs = segments_of(text)
    total = sum(s for s, _ in segs)
    if not want or total == want:
        return text, ""
    if skeleton and len(skeleton) == len(segs):
        fixed = iter(skeleton)
        text = LABEL.sub(lambda m: f"@@ {next(fixed)[0]} | {m.group(2)}", text)
        return text, (f" The @@ seconds came to {total} s; the skeleton's ({want} s, the request) are restored, since "
                      "the words were written to its budgets.")
    off = want - total
    note = (f"{NOT_BUILT} the segments add up to {total} s, but the request is {want} s: "
            f"{'add' if off > 0 else 'take'} {abs(off)} s.")
    if skeleton:
        have = {label for _, label in segs}
        had = {label for _, label in skeleton}
        dropped = [f"{label} ({secs} s)" for secs, label in skeleton if label not in have]
        added = [f"{label} ({secs} s)" for secs, label in segs if label not in had]
        if dropped:
            note += f" The skeleton had {len(skeleton)} segments; this draft dropped " + ", ".join(dropped) + "."
        if added:
            note += " New since the skeleton: " + ", ".join(added) + "."
    return text, note + (" Give those seconds, and the words that fill them, to the segments where they belong in "
                         "one edit_segments (each edit the whole segment, its @@ seconds first); the build runs with it.")


def _adds_up(text: str) -> str:
    """What a draft's segments add up to, and its spoken words, said for the writer to check against the request."""
    total = sum(int(m) for m in SECONDS.findall(text))
    words = _words(text)
    return (f"{len(SECONDS.findall(text))} segments adding up to {total} s ({total / 60:g} min), "
            + ("no words yet (a skeleton)" if not words else f"about {words} words"))


# A writer asked to "add about 600 words" re-emits the segments with a third of that (16 to 47 percent in 0.50.2's
# loop), so a draft fifteen percent short took three to five fixes. The site scales the build's ask by what this
# writer delivered on its last one (twice, the first time), so one fix lands.
ASK = re.compile(r"To land on plan, add about (\d+) words in one edit:[^\n]*")
FIRST_ASK = 2.0
MOST_ASK = 3.0
NUMBER = re.compile(r"(about |\+)(\d+)")


def scale_ask(deps: Deps, path: str, output: str, words: int) -> str:
    """The build's output with its "To land on plan, add about N words" ask scaled to this writer, and the ask as
    shown remembered for the next build of `path`; a build that asks nothing forgets it."""
    found = ASK.search(output)
    if not found:
        deps.asks.pop(path, None)
        return output
    factor = FIRST_ASK
    if path in deps.asks:   # the last ask as shown, and what the writer added for it
        shown, before = deps.asks[path]
        delivered = words - before
        factor = min(MOST_ASK, max(1.0, shown / delivered)) if delivered > 0 else MOST_ASK
    line = NUMBER.sub(lambda m: (m.group(1) or "") + str(round(int(m.group(2)) * factor)), found.group(0))
    deps.asks[path] = (round(int(found.group(1)) * factor), words)
    return output[:found.start()] + line + output[found.end():]


# A coach talks in contractions, and a web voice reads exactly what's written: "Let us go, that is one" sounds
# like a letter read aloud. Gemini wrote two or three dozen of these a script with a rule against them (0.50.2's
# loop, every judge quoting them), so the site contracts the forms that read one way only, as it splits long
# paragraphs. A form before a pause ("that is, the hips"; "where you are.") is left alone.
CONTRACT = [(re.compile(rf"\b{a}\b{after}", re.IGNORECASE), b) for a, after, b in (
    (r"let us", r"(?!\s+know\b)", "let's"),
    (r"do not", "", "don't"), (r"does not", "", "doesn't"), (r"did not", "", "didn't"),
    (r"is not", "", "isn't"), (r"are not", "", "aren't"), (r"was not", "", "wasn't"), (r"were not", "", "weren't"),
    (r"cannot", "", "can't"), (r"can not", "", "can't"), (r"will not", "", "won't"),
    (r"should not", "", "shouldn't"), (r"could not", "", "couldn't"), (r"would not", "", "wouldn't"),
    (r"(that|it|there|here|what|who|where|she|he) is", r"(?=\s+[a-z])", r"\1's"),
    (r"(we|you|they) are", r"(?=\s+[a-z])", r"\1're"),
    (r"i am", r"(?=\s+[a-z])", "I'm"),
    (r"(i|you|we|they|it|that|she|he) will", r"(?=\s+[a-z])", r"\1'll"))]


# "stay where you are or drop a plate": after one of these the verb ends its clause, and "where you're or" can't
CLAUSE_FINAL = re.compile(r"\b(where|wherever|how|however|what|whatever|who|as|than)\s+$", re.IGNORECASE)
NEGATIVE = re.compile(r"not$|^cannot$|^can not$", re.IGNORECASE)


def _contract_words(text: str) -> tuple[str, int]:
    n = 0
    for pattern, short in CONTRACT:
        def swap(m, short=short):
            if not NEGATIVE.search(m.group(0)) and CLAUSE_FINAL.search(m.string[max(0, m.start() - 12):m.start()]):
                return m.group(0)
            out = m.expand(short)
            return out[0].upper() + out[1:] if m.group(0)[0].isupper() else out
        text, k = pattern.subn(swap, text)
        n += k
    return text, n


def contract(text: str) -> tuple[str, int]:
    """A draft with its stiff forms contracted ("let us" to "let's", "that is one" to "that's one") in its spoken
    lines, never the movements: or @@ lines nor inside a marker; and how many."""
    out, n = [], 0
    for line in text.split("\n"):
        if line.startswith(("@@", "movements:")):
            out.append(line)
            continue
        pieces = re.split(r"(\[[^\]]*\])", line)
        for i in range(0, len(pieces), 2):
            pieces[i], k = _contract_words(pieces[i])
            n += k
        out.append("".join(pieces))
    return "\n".join(out), n


# A clip (a paragraph's text between markers) the lint finds over draft.MAX_CLIP (22 s) costs a whole round trip to
# split by hand, and first drafts hold one or two nearly every time: the site splits them at a sentence break as
# the draft is written. Characters, not seconds: the slowest web coach speaks about 11.2 a second, so 225 is
# about 20 seconds, and a split clip is inside the limit whoever speaks it.
SPLIT_OVER = 225
SPLIT_TO = 200
# never after an initial or an abbreviation of initials ("U.S. Soccer", "D.C."): a break there is a pause mid-name
SENTENCE_END = re.compile(r"(?<![A-Z]\.[A-Z]\.)(?<!\b[A-Z]\.)(?<=[.!?])(?:[\"\u201d'])?\s+(?=[A-Z\"\u201c\[])")


def _clips(line: str) -> list[str]:
    return [c.strip() for c in MARK.split(line) if c.strip()]


def _split_line(line: str) -> list[str]:
    """`line` as one or more paragraphs, each clip at most SPLIT_TO characters where its sentences allow."""
    if all(len(c) <= SPLIT_OVER for c in _clips(line)):
        return [line]
    ends = [m.end() for m in SENTENCE_END.finditer(line) if line.count("[", 0, m.end()) == line.count("]", 0, m.end())]
    pieces, start = [], 0
    for end in ends + [len(line)]:
        pieces.append(line[start:end].strip())
        start = end
    out = []
    for piece in (p for p in pieces if p):
        if out and len((_clips(out[-1] + " " + piece) or [""])[-1]) <= SPLIT_TO:
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out


def split_long(text: str) -> tuple[str, int]:
    """The draft with each clip over SPLIT_OVER characters split into paragraphs at its sentence breaks, and how
    many paragraphs were added. Lines of a paragraph that runs on over several lines are parted first."""
    lines = text.split("\n")
    out: list[str] = []
    added = 0
    group: list[str] = []

    def flush():
        nonlocal added
        spoken = [ln for ln in group if MARK.sub("", ln).strip()]
        joined = " ".join(group)
        apart = len(spoken) > 1 and any(len(c) > SPLIT_OVER for c in _clips(joined))
        for i, ln in enumerate(group):
            parts = _split_line(ln)
            added += len(parts) - 1
            for j, part in enumerate(parts):
                if j:
                    out.append("")
                out.append(part)
            if apart and i < len(group) - 1 and MARK.sub("", ln).strip() and MARK.sub("", group[i + 1]).strip():
                out.append("")
                added += 1
        group.clear()

    for ln in lines:
        if not ln.strip() or ln.startswith(("@@", "movements:")):
            flush()
            out.append(ln)
        else:
            group.append(ln)
    flush()
    return "\n".join(out), added


def _split_note(n: int) -> str:
    return (f" The site split {n} long paragraph{'s' if n > 1 else ''} at a sentence break (a clip over about 20 "
            "seconds); nothing to do.") if n else ""


STEM = re.compile(r"(\d{4}-\d{2}-\d{2})-([a-z]+(?:-[a-z]+)*)-(\d+)(?:-\d+)?\.draft\.txt$")   # "full-body" too


def build_name(path: str) -> str | None:
    """A draft's build name from its stem, as the skill names one: "Workout 2026-11-01 Strength 30 min"."""
    found = STEM.search(path)
    return f"Workout {found.group(1)} {found.group(2).capitalize()} {found.group(3)} min" if found else None


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
    new, split = split_long("\n".join(out))
    new, _ = contract(new)
    if len(new) > WRITE_LIMIT:
        return _refuse(f"too long: at most {WRITE_LIMIT} characters")
    if is_skeleton(new):
        new, note = settle_clock(new, _request_seconds(full))
        note += long_rests(new)
        deps.skeletons[rel] = segments_of(new)
    else:
        new, note = hold_clock(new, deps.skeletons.get(rel), _request_seconds(full))
    tmp = full + ".tmp-write"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, full)
    result = _result(0, f"replaced segment{'s' if len(wanted) > 1 else ''} {', '.join(map(str, sorted(wanted)))} in "
                        f"{path}: now {_adds_up(new)}.{_split_note(split)}{note}")
    result.build = not note.startswith(NOT_BUILT)
    result.segments, result.unfinished = empty_segments(new)
    return result


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


def build_timeout(path: str) -> float:
    """How long a full build of the draft at `path` may run: the workout's own length, never under BUILD_TIMEOUT.
    A slow voice takes most of it: Gemini, two clips at a time, spoke a thirty-minute workout in 506 s."""
    try:
        with open(path, encoding="utf-8") as f:
            seconds = sum(int(m.group(1)) for m in LABEL.finditer(f.read()))
    except (OSError, UnicodeDecodeError):
        seconds = 0
    return max(BUILD_TIMEOUT, RECORD_SHARE * seconds)


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
        timeout = build_timeout(argv[1])
        if deps.extend_turn is not None:   # the turn's own clock never cuts the recording short
            deps.extend_turn(timeout + TURN_FINISH)
        r = engine.run(deps.engine_root, deps.home, argv, extra_env=deps.keys, timeout=timeout, cancel=deps.cancel)
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
    if deps.ceiling is not None and chars > deps.ceiling:   # over what "Schedule it" approved: the button decides
        deps.auto_record = False
        return _result(0, (f"Not recorded: the script speaks {chars:,} characters, over the {deps.ceiling:,} the "
                           f"listener approved when they scheduled it, for about ${usd:.2f}. The page shows them a "
                           "Record button with that price when they come back. End your turn: say in a line that "
                           "the script is ready and checked but came out longer than planned, so it waits for "
                           "their Record."))
    return _result(0, (f"Not recorded yet: recording sends {chars:,} characters to {cost.get('service')} for about "
                       f"${usd:.2f}{' (including the coach voice design)' if cost.get('pending_design') else ''}. "
                       "The page now shows the listener a Record button with that price. End your turn: say in a "
                       "line that the script is ready and checked (the button shows the price: don't say it). Don't build again "
                       "until they approve."))


def _mine_text(deps: Deps, text: str) -> str:
    home = os.path.realpath(deps.home)
    return text.replace(home, "me").replace(deps.home, "me")
