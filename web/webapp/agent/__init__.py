"""The agent: one loop for every provider, as in Claude Code. It reads the workout skill itself
(`.claude/skills/workout/`) under a short preamble on what this web client offers, and works through four
tools: run a `./harmonicfitness` command, read, write and list files. The model is passed per turn;
nothing here knows which provider it is."""
import functools
import json
import os
import re
import tomllib
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from dataclasses import dataclass

from pydantic_ai import Agent, CancellationToken, ModelMessagesTypeAdapter, RunContext, UsageLimits
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

from . import tools
from .tools import Deps, ToolResult

__all__ = ["AGENT", "Deps", "LIMITS", "audition_open", "prefetch", "wants_coach", "start_feeds", "NOT_OPEN", "STOPPED", "TIMED_OUT", "TURN_SECONDS", "TurnError", "TurnOutcome",
           "UNFINISHABLE", "run_turn"]

LIMITS = UsageLimits(request_limit=60, tool_calls_limit=120, total_tokens_limit=3_000_000)
TURN_SECONDS = 900   # a turn's wall-clock cap: past it the run is cancelled (TurnError TIMED_OUT), never retried
SKILL = (".claude/skills/workout/SKILL.md", ".claude/skills/workout/research.md")
SETUP = (".claude/skills/setup/SKILL.md",)
COACH = (".claude/skills/coach/SKILL.md",)
SETUP_WORDS = re.compile(r"\b(set(ting)? me up|set ?up|get(ting)? started|my profile|onboard)", re.IGNORECASE)
# The coach skill's own triggers: a new coach, a different voice, a coach that sounds or talks differently.
COACH_WORDS = re.compile(r"\b(new|another|different|own|switch|change|design|make|create)\b[^.?!]{0,30}"
                         r"\b(coach|voice|trainer)|\b(coach|voice)\b[^.?!]{0,20}\b(sounds?|talks?|a (wo)?man)\b",
                         re.IGNORECASE)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md"), encoding="utf-8") as _f:
    PREAMBLE = _f.read()


@functools.lru_cache(maxsize=8)
def skill_text(engine_root: str, setup: bool = False, coach: bool = False) -> str:
    """The workout skill as the engine ships it (and the setup skill, for a listener not set up yet, and the
    coach skill while a coach is being made), so the web follows the same steps as the CLI."""
    parts = []
    for rel in (SETUP if setup else ()) + (COACH if coach else ()) + SKILL:
        with open(os.path.join(engine_root, rel), encoding="utf-8") as f:
            parts.append(f"<file path=\"{rel}\">\n{f.read()}\n</file>")
    return "\n\n".join(parts)


def needs_setup(home: str) -> bool:
    """A listener whose profile has no experience level yet: setup's quick start sets it first."""
    try:
        with open(os.path.join(home, "profile.md"), encoding="utf-8") as f:
            text = f.read()
        block = text.split("+++")[1] if text.startswith("+++") else ""
        return not tomllib.loads(block).get("experience")
    except (OSError, IndexError, ValueError):
        return True


def wants_setup(line: str | None) -> bool:
    return bool(line and SETUP_WORDS.search(line))


def wants_coach(line: str | None) -> bool:
    return bool(line and COACH_WORDS.search(line))


def audition_open(home: str) -> bool:
    """Whether an audition is waiting for the listener's pick (a candidates list in me/coaches/.auditions/)."""
    base = os.path.join(home, "coaches", ".auditions")
    try:
        return any(os.path.isfile(os.path.join(base, d, "candidates.json")) for d in os.listdir(base))
    except OSError:
        return False


AGENT = Agent(deps_type=Deps, output_type=str, instructions=PREAMBLE, retries=1)


@AGENT.instructions
def _skill(ctx: RunContext[Deps]) -> str:
    return skill_text(ctx.deps.engine_root, ctx.deps.setup, ctx.deps.coach)


@AGENT.instructions
def _now(ctx: RunContext[Deps]) -> str:
    return f"Now: {ctx.deps.now} (today is {ctx.deps.today})."


# What the listener sees while a tool runs: what it means for them, never a command or a file's name.
STEPS = {"brief": "Working out today's safe moves", "build": "Recording your workout",
         "check": "Checking your profile", "content": "Choosing what fills the rests",
         "coaches": "Checking which coaches can speak", "coverage": "Looking at your recent sessions",
         "feeds": "Gathering today's news and weather", "get": "Checking your settings",
         "log-session": "Logging the session", "movements": "Looking through the moves",
         "youtube": "Finding a video", "keys": "Checking your voice keys", "help": "Checking how the coach works"}
COACH_STEPS = {"make": "Making your coach's voice", "audition": "Auditioning voices for your coach",
               "keep": "Saving your new coach", "forget-audition": "Tidying up the audition",
               "archive": "Putting that coach away"}
READS = (("me/profile.md", "Getting to know you"), ("me/training.md", "Checking your training and kit"),
         ("me/health.md", "Checking today's safety limits"), ("me/log.md", "Looking at your recent sessions"),
         ("me/content.md", "Checking your interests"), ("me/workouts/research/", "Gathering today's stories"),
         ("me/workouts/", "Looking at your workout"), ("me/coaches/", "Getting to know your coach"),
         ("coaches/", "Getting to know your coach"), ("knowledge/injury-playbook", "Reviewing the safety rules"),
         ("knowledge/script", "Reviewing how to write the script"), ("knowledge/tts", "Reviewing how to write for the voice"),
         ("knowledge/", "Reviewing the coaching guides"), (".claude/skills/", "Reviewing the workout steps"))


def _read_step(path: object) -> str:
    if isinstance(path, str):
        for prefix, text in READS:
            if path.startswith(prefix):
                return text
    return "Looking through your files"


def _write_step(path: object) -> str:
    if isinstance(path, str) and path.startswith("me/coaches/"):
        return "Describing your coach"
    if isinstance(path, str) and path.endswith(".draft.txt"):
        return "Writing your script"
    if isinstance(path, str) and path.startswith("me/workouts/research/"):
        return "Saving today's research"
    return "Saving your notes"


def _step(deps: Deps, text: str, tool: str, result: ToolResult) -> ToolResult:
    if deps.say is not None:
        try:
            deps.say(text, tool, result.code)
        except Exception:  # noqa: BLE001 - a progress line never fails the turn
            pass
    return result


@AGENT.tool(sequential=True)
def run(ctx: RunContext[Deps], args: list[str]) -> ToolResult:
    """Run one ./harmonicfitness command in the listener's folder: args is the argv after
    ./harmonicfitness, e.g. ["brief", "--goal", "strength", "--minutes", "25", "--preset", "hotel-room",
    "--save", "me/workouts/<stem>/<stem>.draft.txt"]. Returns the exit code, stdout and stderr."""
    first = args[1] if args and args[0] == "./harmonicfitness" and len(args) > 1 else (args[0] if args else "")
    text = STEPS.get(first, "Working on it") if isinstance(first, str) else "Working on it"
    if first == "build" and "--lint-only" in args:
        text = "Checking the script's safety and timing"
    rest = args[1:] if args and args[0] == "./harmonicfitness" else args
    if first == "coaches" and len(rest) > 1 and rest[1] in COACH_STEPS:
        text = COACH_STEPS[rest[1]]
    return _step(ctx.deps, text, f"run {first}"[:40], tools.run(ctx.deps, args))


@AGENT.tool(sequential=True)
def read_file(ctx: RunContext[Deps], path: str) -> ToolResult:
    """Read a text file: me/... (the listener's folder) or the engine's knowledge/, .claude/skills/, coaches/."""
    return _step(ctx.deps, _read_step(path), "read_file", tools.read_file(ctx.deps, path))


@AGENT.tool(sequential=True)
def write_file(ctx: RunContext[Deps], path: str, content: str) -> ToolResult:
    """Write (create or replace) a text file in the listener's folder, me/... only."""
    return _step(ctx.deps, _write_step(path), "write_file", tools.write_file(ctx.deps, path, content))


@AGENT.tool(sequential=True)
def list_files(ctx: RunContext[Deps], path: str = "me/") -> ToolResult:
    """List the files under a folder of the listener's, me/ by default."""
    return _step(ctx.deps, "Looking through your files", "list_files", tools.list_files(ctx.deps, path))


# Step 1 of the skill, run by the worker before the first model request, all at once: the model gets the
# same results in the listener's first message, without a round trip for each.
FIRST_RUNS = (["check"], ["content", "plan", "--minutes", "25"], ["get", "coach"], ["coaches", "list", "--json"])
SETUP_FIRST = ("This listener isn't set up yet: this turn's questions are the setup skill's quick start (what to call "
               "them, their experience, any injuries or limits), together with today's check-in, in one numbered "
               "list. Write their answers before the brief runs.")


def _coaches(r: ToolResult) -> ToolResult:
    """`coaches list --json` as the coaches that can speak here, and those that would with a key: the model is
    given the fact, not asked to filter. The raw result when it can't be read."""
    try:
        found = json.loads(r.output)["coaches"]
        speak = [c for c in found if c.get("speaks_here")]
        keyless = [c for c in found if c.get("kind") == "web" and not c.get("speaks_here")]
    except (ValueError, KeyError, TypeError):
        return r

    def name(c: dict) -> str:
        return c["name"] + (" (the default)" if c.get("default") else "") \
            + (" (made the first time it's used)" if c.get("pending") else "")
    lines = ["Coaches who can speak here (offer only these): "
             + ("; ".join(name(c) for c in speak) if speak else "none yet") + "."]
    if keyless:
        lines.append("Not here without a key (never offer these by name; say \"add a key in Keys for more "
                     "voices\" instead): " + ", ".join(f"{c['name']} ({c.get('service_name')})" for c in keyless) + ".")
    lines.append("Local coaches don't speak on this site.")
    return ToolResult(code=r.code, output="\n".join(lines))
FIRST_READS = ("me/profile.md", "me/training.md", "me/health.md", "me/log.md")


def _block(title: str, r: ToolResult) -> str:
    body = (r.output + ("\n" + r.error if r.error else "")).strip() or "(nothing)"
    return f"### {title} (exit {r.code})\n````\n{body}\n````"


def prefetch(deps: Deps) -> str:
    """Step 1's commands and reads, run at once; returned as text for the first message."""
    plain = replace(deps, say=None, feeds=None)
    with ThreadPoolExecutor(max_workers=len(FIRST_RUNS) + len(FIRST_READS)) as pool:
        runs = [pool.submit(tools.run, plain, list(a)) for a in FIRST_RUNS]
        reads = [pool.submit(tools.read_file, plain, p) for p in FIRST_READS]
        results = [(f"./harmonicfitness {' '.join(a)}", f.result()) for a, f in zip(FIRST_RUNS, runs)]
        results += [(f"read {p}", f.result()) for p, f in zip(FIRST_READS, reads)]
    results[3] = ("./harmonicfitness coaches list", _coaches(results[3][1]))
    coach = results[2][1]
    if coach.code == 0 and coach.output.strip():
        name = coach.output.strip().splitlines()[0].strip()
        results.append((f"./harmonicfitness get route --coach \"{name}\"",
                        tools.run(plain, ["get", "route", "--coach", name])))
    if deps.say is not None:
        try:
            deps.say("Getting to know you and today's limits", "prefetch", 0)
        except Exception:  # noqa: BLE001 - a progress line never fails the turn
            pass
    first = SETUP_FIRST + "\n\n" if deps.setup and needs_setup(deps.home) else ""
    return (first + "Step 1 is done: these are its results, run as this turn began. Don't run or read them again "
            "this turn; go on to the questions.\n\n" + "\n\n".join(_block(t, r) for t, r in results))


def start_feeds(deps: Deps, pool: ThreadPoolExecutor) -> Future:
    """`feeds` in the background, so today's research is ready when the script needs it."""
    return pool.submit(tools.run, replace(deps, say=None, feeds=None), ["feeds"])


NOT_OPEN = "not_open"            # TurnError.reason: an answer to a question (this agent asks in the chat)
UNFINISHABLE = "unfinishable"    # TurnError.reason: kept for the worker's wording
TIMED_OUT = "timed_out"          # TurnError.reason: the turn ran past TURN_SECONDS and was cancelled
STOPPED = "stopped"              # TurnError.reason: the listener pressed Stop


class TurnError(Exception):
    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


@dataclass
class TurnOutcome:
    history_json: str
    reply: str | None
    usage: dict
    question: dict | None = None   # always None: questions are asked in the chat
    plan: dict | None = None
    stem: str | None = None


def _usable(history):
    """The history to go on with, or None when it ends on a tool call left without a result (a conversation
    from before this agent, stopped on a question): the chat lines stay, the model starts fresh."""
    called, returned = set(), set()
    for m in history:
        for p in m.parts:
            if isinstance(p, ToolCallPart):
                called.add(p.tool_call_id)
            elif isinstance(p, ToolReturnPart):
                returned.add(p.tool_call_id)
    return history if called <= returned else None


def run_turn(model, deps: Deps, history_json: str | None, prompt: str | None,
             answer: tuple[str, dict] | None = None, context: str | None = None) -> TurnOutcome:
    """One run of the agent on the user's line, after `context` (prefetch's text) when given.
    UsageLimitExceeded and provider errors propagate; the caller decides what they mean."""
    if answer is not None or not prompt:
        raise TurnError("this coach asks its questions in the chat; send a message", NOT_OPEN)
    history = None
    if history_json:
        try:
            history = _usable(ModelMessagesTypeAdapter.validate_json(history_json))
        except ValueError:
            history = None
    if context:
        prompt = f"{context}\n\n---\n\nThe listener says:\n\n{prompt}"
    token = CancellationToken()
    timer = threading.Timer(TURN_SECONDS, token.cancel)
    timer.daemon = True
    timer.start()
    done = threading.Event()
    def watch() -> None:   # Stop cancels the run as the clock would; the watch ends with the turn
        while not done.is_set():
            if deps.cancel.wait(0.5):
                token.cancel()
                return
    if deps.cancel is not None:
        threading.Thread(target=watch, daemon=True).start()
    try:
        result = AGENT.run_sync(prompt, model=model, deps=deps, message_history=history,
                                usage_limits=LIMITS, cancellation_token=token)
    except RunCancelled:
        if deps.cancel is not None and deps.cancel.is_set():
            raise TurnError("stopped", STOPPED) from None
        raise TurnError("the turn ran too long", TIMED_OUT) from None
    finally:
        done.set()
        timer.cancel()
    u = result.usage
    usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens,
             "output_tokens": u.output_tokens}
    return TurnOutcome(history_json=result.all_messages_json().decode("utf-8"), reply=result.output, usage=usage)
