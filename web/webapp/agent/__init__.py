"""The agent: one loop for every provider, as in Claude Code. It reads the workout skill itself
(`.claude/skills/workout/`) under a short preamble on what this web client offers, and works through four
tools: run a `./harmonicfitness` command, read, write and list files. The model is passed per turn;
nothing here knows which provider it is."""
import functools
import os
import threading
from dataclasses import dataclass

from pydantic_ai import Agent, CancellationToken, ModelMessagesTypeAdapter, RunContext, UsageLimits
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import ToolCallPart, ToolReturnPart

from . import tools
from .tools import Deps, ToolResult

__all__ = ["AGENT", "Deps", "LIMITS", "NOT_OPEN", "TIMED_OUT", "TURN_SECONDS", "TurnError", "TurnOutcome",
           "UNFINISHABLE", "run_turn"]

LIMITS = UsageLimits(request_limit=60, tool_calls_limit=120, total_tokens_limit=3_000_000)
TURN_SECONDS = 600   # a turn's wall-clock cap: past it the run is cancelled (TurnError TIMED_OUT), never retried
SKILL = (".claude/skills/workout/SKILL.md", ".claude/skills/workout/research.md")

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md"), encoding="utf-8") as _f:
    PREAMBLE = _f.read()


@functools.lru_cache(maxsize=4)
def skill_text(engine_root: str) -> str:
    """The workout skill as the engine ships it, so the web follows the same steps as the CLI."""
    parts = []
    for rel in SKILL:
        with open(os.path.join(engine_root, rel), encoding="utf-8") as f:
            parts.append(f"<file path=\"{rel}\">\n{f.read()}\n</file>")
    return "\n\n".join(parts)


AGENT = Agent(deps_type=Deps, output_type=str, instructions=PREAMBLE, retries=1)


@AGENT.instructions
def _skill(ctx: RunContext[Deps]) -> str:
    return skill_text(ctx.deps.engine_root)


@AGENT.instructions
def _now(ctx: RunContext[Deps]) -> str:
    return f"Now: {ctx.deps.now} (today is {ctx.deps.today})."


# What the listener sees while a tool runs: plain words, never a file's contents.
STEPS = {"brief": "Working out today's safe menu", "build": "Checking the script", "check": "Checking your files",
         "content": "Planning what fills the rests", "coaches": "Looking at the coaches", "coverage":
         "Looking at your recent sessions", "feeds": "Fetching today's news and weather", "get": "Looking up a setting",
         "log-session": "Logging the session", "movements": "Looking through the movements", "youtube":
         "Looking for a video", "keys": "Checking which keys are set", "help": "Reading the engine's help"}


def _step(deps: Deps, text: str, tool: str, result: ToolResult) -> ToolResult:
    if deps.say is not None:
        try:
            deps.say(text, tool, result.code)
        except Exception:  # noqa: BLE001 - a progress line never fails the turn
            pass
    return result


def _shown(path: object) -> str:
    return path if isinstance(path, str) and len(path) <= 120 else "a file"


@AGENT.tool(sequential=True)
def run(ctx: RunContext[Deps], args: list[str]) -> ToolResult:
    """Run one ./harmonicfitness command in the listener's folder: args is the argv after
    ./harmonicfitness, e.g. ["brief", "--goal", "strength", "--minutes", "25", "--preset", "hotel-room",
    "--save", "me/workouts/<stem>/<stem>.draft.txt"]. Returns the exit code, stdout and stderr."""
    first = args[1] if args and args[0] == "./harmonicfitness" and len(args) > 1 else (args[0] if args else "")
    text = STEPS.get(first, "Running the engine") if isinstance(first, str) else "Running the engine"
    return _step(ctx.deps, text, f"run {first}"[:40], tools.run(ctx.deps, args))


@AGENT.tool(sequential=True)
def read_file(ctx: RunContext[Deps], path: str) -> ToolResult:
    """Read a text file: me/... (the listener's folder) or the engine's knowledge/, .claude/skills/, coaches/."""
    return _step(ctx.deps, f"Reading {_shown(path)}", "read_file", tools.read_file(ctx.deps, path))


@AGENT.tool(sequential=True)
def write_file(ctx: RunContext[Deps], path: str, content: str) -> ToolResult:
    """Write (create or replace) a text file in the listener's folder, me/... only."""
    return _step(ctx.deps, f"Writing {_shown(path)}", "write_file", tools.write_file(ctx.deps, path, content))


@AGENT.tool(sequential=True)
def list_files(ctx: RunContext[Deps], path: str = "me/") -> ToolResult:
    """List the files under a folder of the listener's, me/ by default."""
    return _step(ctx.deps, f"Looking through {_shown(path)}", "list_files", tools.list_files(ctx.deps, path))


NOT_OPEN = "not_open"            # TurnError.reason: an answer to a question (this agent asks in the chat)
UNFINISHABLE = "unfinishable"    # TurnError.reason: kept for the worker's wording
TIMED_OUT = "timed_out"          # TurnError.reason: the turn ran past TURN_SECONDS and was cancelled


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
             answer: tuple[str, dict] | None = None) -> TurnOutcome:
    """One run of the agent on the user's line. UsageLimitExceeded and provider errors propagate; the
    caller decides what they mean."""
    if answer is not None or not prompt:
        raise TurnError("this coach asks its questions in the chat; send a message", NOT_OPEN)
    history = None
    if history_json:
        try:
            history = _usable(ModelMessagesTypeAdapter.validate_json(history_json))
        except ValueError:
            history = None
    token = CancellationToken()
    timer = threading.Timer(TURN_SECONDS, token.cancel)
    timer.daemon = True
    timer.start()
    try:
        result = AGENT.run_sync(prompt, model=model, deps=deps, message_history=history,
                                usage_limits=LIMITS, cancellation_token=token)
    except RunCancelled:
        raise TurnError("the turn ran too long", TIMED_OUT) from None
    finally:
        timer.cancel()
    u = result.usage
    usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens,
             "output_tokens": u.output_tokens}
    return TurnOutcome(history_json=result.all_messages_json().decode("utf-8"), reply=result.output, usage=usage)
