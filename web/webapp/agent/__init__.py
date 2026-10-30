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
from typing import Callable

from pydantic_ai import Agent, CancellationToken, ModelMessagesTypeAdapter, RunContext, UsageLimits
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.wrapper import WrapperModel

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
         "check": "Checking your profile is complete", "content": "Choosing what fills the rests",
         "coaches": "Checking which coaches can speak", "coverage": "Looking at your recent sessions",
         "feeds": "Gathering today's news and weather", "get": "Checking your settings",
         "log-session": "Logging the session", "movements": "Looking through the moves",
         "youtube": "Finding a video", "keys": "Checking your voice keys", "help": "Looking up how a step works"}
# a command's second word, where it says more than the first
SUB_STEPS = {("get", "cost"): "Pricing the recording", ("get", "web-builds"): "Checking your past recordings",
             ("content", "log"): "Noting the stories you heard", ("content", "reserve"): "Checking the story reserve",
             ("youtube", "transcript"): "Reading a video's transcript", ("youtube", "puzzles"): "Finding a puzzle",
             ("youtube", "done"): "Noting the video series", ("movements", "--about"): "Reading the coaching notes"}
OTHER_STEP = "Running a check"
# What the model is doing between tools, by what the turn did last (Deps.phase): shown while it thinks.
THINK = {"": "Reading your message", "brief": "Writing your script", "draft": "Checking over the script",
         "lint_failed": "Fixing the script", "linted": "Getting the recording ready", "priced": "Writing up the plan",
         "recorded": "Wrapping up", "audition": "Introducing the voices", "coach": "Working on your coach"}
THINK_OTHER = "Deciding what to do next"
COACH_STEPS = {"make": "Making your coach's voice", "audition": "Auditioning voices for your coach",
               "keep": "Saving your new coach", "forget-audition": "Tidying up the audition",
               "archive": "Putting that coach away"}
READS = ((".claude/skills/coach/", "Reviewing how coaches are made"), (".claude/skills/setup/", "Reviewing the setup steps"),
         ("knowledge/voices", "Reviewing the voice options"), ("knowledge/movements", "Looking through the moves"),
         ("knowledge/programming", "Reviewing how to set effort and rest"),
         ("knowledge/sessions", "Choosing the session's shape"), ("knowledge/kits", "Checking what your kit can do"),
         ("knowledge/content", "Planning what fills the rests"),
         ("me/profile.md", "Getting to know you"), ("me/training.md", "Checking your training and kit"),
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


def _write_step(path: object, fixing: bool = False) -> str:
    if isinstance(path, str) and path.startswith("me/coaches/"):
        return "Describing your coach"
    if isinstance(path, str) and path.endswith(".draft.txt"):
        return "Tightening the script's timing" if fixing else "Writing your script"
    if isinstance(path, str) and path.startswith("me/workouts/research/"):
        return "Saving today's research"
    return "Saving your notes"


def _say(deps: Deps, text: str, tool: str, code: int | None, step: int, think: bool = False) -> None:
    if deps.say is not None:
        try:
            if think:
                deps.say(text, tool, code, step, think=True)
            else:
                deps.say(text, tool, code, step)
        except Exception:  # noqa: BLE001 - a progress line never fails the turn
            pass


def _begin(deps: Deps, text: str, tool: str, think: bool = False) -> int:
    """A step shown as running, as its tool starts (or as the model starts thinking); its id."""
    deps.steps += 1
    _say(deps, text, tool, None, deps.steps, think)
    return deps.steps


class Narrated(WrapperModel):
    """The turn's model, saying what it's thinking about while each request runs: the longest waits in a turn
    (reading the message, writing the script) are the model's, between tools, and were silent."""

    def __init__(self, wrapped, deps: Deps):
        super().__init__(wrapped)
        self._deps = deps

    async def request(self, messages, model_settings, model_request_parameters):
        deps = self._deps
        text = THINK.get(deps.phase, THINK_OTHER)
        n = _begin(deps, text, "think", think=True)
        try:
            response = await super().request(messages, model_settings, model_request_parameters)
        except BaseException:
            _say(deps, text, "think", 1, n, think=True)
            raise
        _say(deps, text, "think", 0, n, think=True)
        if deps.phase == "":
            deps.phase = "working"
        return response


def _step(deps: Deps, text: str, tool: str, work: Callable[[], ToolResult]) -> ToolResult:
    """Run a tool as one step: running while it works, then done or failed."""
    n = _begin(deps, text, tool)
    try:
        result = work()
    except BaseException:
        _say(deps, text, tool, 1, n)
        raise
    _say(deps, text, tool, result.code, n)
    return result


def _coach_folders(home: str) -> set[str]:
    try:
        return {d for d in os.listdir(os.path.join(home, "coaches")) if not d.startswith(".")}
    except OSError:
        return set()


def _recording(deps: Deps, args: list[str], tool: str) -> ToolResult:
    """The approved recording: "Designing <coach>'s voice" first when the coach is made in this build (until its
    folder appears in me/coaches/), then "Recording your workout". The watch thread says the switch while this
    thread waits on the engine and is joined before this thread says anything again, so the worker's connection
    (`say` writes a job event on it) is never used by two threads at once; the heartbeat has its own."""
    ok = deps.approved or {}
    if not ok.get("design"):
        return _step(deps, "Recording your workout", tool, lambda: tools.run(deps, args))
    design = f"Designing {ok.get('coach') or 'your coach'}'s voice"
    before = _coach_folders(deps.home)
    first = _begin(deps, design, tool)
    recording: list[int] = []
    stop = threading.Event()

    def watch() -> None:
        while not stop.wait(1.0):
            if _coach_folders(deps.home) - before:
                _say(deps, design, tool, 0, first)
                recording.append(_begin(deps, "Recording your workout", tool))
                return
    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()
    code = 1
    try:
        result = tools.run(deps, args)
        code = result.code
        return result
    finally:
        stop.set()
        watcher.join()
        _say(deps, "Recording your workout" if recording else design, tool, code,
             recording[0] if recording else first)


@AGENT.tool(sequential=True)
def run(ctx: RunContext[Deps], args: list[str]) -> ToolResult:
    """Run one ./harmonicfitness command in the listener's folder: args is the argv after
    ./harmonicfitness, e.g. ["brief", "--goal", "strength", "--minutes", "25", "--preset", "hotel-room",
    "--save", "me/workouts/<stem>/<stem>.draft.txt"]. Returns the exit code, stdout and stderr."""
    deps = ctx.deps
    first = args[1] if args and args[0] == "./harmonicfitness" and len(args) > 1 else (args[0] if args else "")
    text = STEPS.get(first, OTHER_STEP) if isinstance(first, str) else OTHER_STEP
    rest = args[1:] if args and args[0] == "./harmonicfitness" else args
    if len(rest) > 1 and isinstance(rest[1], str) and (first, rest[1]) in SUB_STEPS:
        text = SUB_STEPS[(first, rest[1])]
    tool = f"run {first}"[:40]
    if first == "build" and "--lint-only" not in args:
        draft = rest[1] if len(rest) > 1 else None
        if deps.approved and deps.approved.get("draft") == draft:
            deps.phase = "recorded"
            return _recording(deps, args, tool)
        text = "Working out what recording costs"   # an unapproved build checks the script, then prices it
    if first == "build" and "--lint-only" in args:
        text = "Checking the script again" if deps.lint_failed else "Checking the script's safety and timing"
    if first == "coaches" and len(rest) > 1 and rest[1] in COACH_STEPS:
        text = COACH_STEPS[rest[1]]
    result = _step(deps, text, tool, lambda: tools.run(deps, args))
    if first == "build":
        deps.lint_failed = result.code != 0
        deps.phase = "lint_failed" if result.code != 0 else ("linted" if "--lint-only" in args else "priced")
    elif first == "brief":
        deps.phase = "brief"
    elif first == "coaches" and len(rest) > 1 and rest[1] == "audition":
        deps.phase = "audition"
    elif first == "coaches" and len(rest) > 1 and rest[1] in ("make", "keep"):
        deps.phase = "coach"
    return result


@AGENT.tool(sequential=True)
def read_file(ctx: RunContext[Deps], path: str) -> ToolResult:
    """Read a text file: me/... (the listener's folder) or the engine's knowledge/, .claude/skills/, coaches/."""
    return _step(ctx.deps, _read_step(path), "read_file", lambda: tools.read_file(ctx.deps, path))


@AGENT.tool(sequential=True)
def write_file(ctx: RunContext[Deps], path: str, content: str) -> ToolResult:
    """Write (create or replace) a text file in the listener's folder, me/... only."""
    result = _step(ctx.deps, _write_step(path, ctx.deps.lint_failed), "write_file",
                   lambda: tools.write_file(ctx.deps, path, content))
    if isinstance(path, str) and path.endswith(".draft.txt"):
        ctx.deps.phase = "draft"
    return result


@AGENT.tool(sequential=True)
def list_files(ctx: RunContext[Deps], path: str = "me/") -> ToolResult:
    """List the files under a folder of the listener's, me/ by default."""
    return _step(ctx.deps, "Looking through your files", "list_files", lambda: tools.list_files(ctx.deps, path))


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
        lines.append("Not here without a key (never offer these by name; say \"add a key in Settings for more "
                     "voices\" instead): " + ", ".join(f"{c['name']} ({c.get('service_name')})" for c in keyless) + ".")
    lines.append("Local coaches don't speak on this site.")
    return ToolResult(code=r.code, output="\n".join(lines))
FIRST_READS = ("me/profile.md", "me/training.md", "me/health.md", "me/log.md")


def _block(title: str, r: ToolResult) -> str:
    body = (r.output + ("\n" + r.error if r.error else "")).strip() or "(nothing)"
    return f"### {title} (exit {r.code})\n````\n{body}\n````"


COACH_FIRST = ("This listener isn't set up yet, and asked for a new coach. Do what they asked, now: the coach skill, "
               "with no setup questions and no workout check-in this turn; ask only what the coach needs. Once the "
               "coach is made, say in a line that a few quick questions will set them up for a first workout.")


def prefetch(deps: Deps, line: str | None = None) -> str:
    """Step 1's commands and reads, run at once; returned as text for the first message. A listener not set up
    yet who asked for a coach gets the coach first, never the setup questionnaire."""
    plain = replace(deps, say=None, feeds=None)
    fresh = deps.setup and needs_setup(deps.home)
    coach_first = fresh and wants_coach(line) and not wants_setup(line)
    label = ("Looking at your coaches" if coach_first else "Getting you set up" if fresh
             else "Reading your profile and today's limits")
    step = _begin(deps, label, "prefetch")
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
    _say(deps, label, "prefetch", 0, step)
    first = (COACH_FIRST if coach_first else SETUP_FIRST) + "\n\n" if fresh else ""
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
        result = AGENT.run_sync(prompt, model=Narrated(model, deps), deps=deps, message_history=history,
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
