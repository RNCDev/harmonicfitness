"""The agent: one loop for every provider, as in Claude Code. It reads the workout skill itself
(`.claude/skills/workout/`) under a short preamble on what this web client offers, and works through four
tools: run a `./harmonicfitness` command, read, write and list files. The model is passed per turn;
nothing here knows which provider it is."""
import asyncio
import functools
import json
import os
import re
import threading
import time
import tomllib
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
from dataclasses import dataclass
from typing import Callable

from pydantic_ai import Agent, CancellationToken, ModelMessagesTypeAdapter, RunContext, UsageLimits, WebSearchTool
from pydantic_ai.exceptions import RunCancelled
from pydantic_ai.capabilities import NativeTool
from pydantic_ai.messages import NativeToolCallPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.wrapper import WrapperModel

from . import tools, writers
from .tools import Deps, ToolResult
from .writers import NOT_WEB, web_copy

__all__ = ["AGENT", "Deps", "LIMITS", "audition_open", "prefetch", "wants_coach", "start_feeds", "NOT_OPEN", "STOPPED", "TIMED_OUT", "TURN_SECONDS", "TurnError", "TurnOutcome",
           "UNFINISHABLE", "run_turn"]

LIMITS = UsageLimits(request_limit=60, tool_calls_limit=120, total_tokens_limit=3_000_000)
# The writer's own web search (Gemini's Google Search, Claude's, ChatGPT's, OpenRouter's), billed by its provider
# on the listener's key: research for the topics due and what's on near them. Low context keeps each search
# quick; Claude stops at max_uses a turn, and the instructions ask every writer for about six.
SEARCH = WebSearchTool(search_context_size="low", max_uses=8)
TURN_SECONDS = 900   # a turn's wall-clock cap: past it the run is cancelled (TurnError TIMED_OUT), never retried
SKILL = (".claude/skills/workout/SKILL.md",)   # research.md is for a computer's research agents and sheets: none here
# what the skill says to read before writing, given with it: two round trips fewer before every script
WRITING = ("knowledge/script.md", "knowledge/tts-rules.md")
SETUP = (".claude/skills/setup/SKILL.md",)
COACH = (".claude/skills/coach/SKILL.md",)
SETUP_WORDS = re.compile(r"\b(set(ting)? me up|set ?up|get(ting)? started|my profile|onboard|my interests|"
                         r"(add|new|suggest)\w*( a| some)? topics?)\b", re.IGNORECASE)
# Asking to be set up (the quick start's interview), as against a task the setup skill also covers (interests).
ONBOARD_WORDS = re.compile(r"\b(set(ting)? me up|set ?up|get(ting)? started|my profile|onboard)\b", re.IGNORECASE)
# Asking for a workout: the one request a new listener's setup questions come with.
WORKOUT_WORDS = re.compile(r"\b(workouts?|sessions?|minutes?|mins?|train(ing)?|exercises?|routine|sweat|hiit|"
                           r"cardio|strength|stretch(ing)?|mobility|yoga|run)\b", re.IGNORECASE)
# Telling the coach what they enjoyed (the first screen's "Tell me what you enjoyed" fills in "Lately I enjoyed ").
ENJOYED = re.compile(r"^\W*(lately|recently|last (week|weekend|night)|this (week|weekend))?\W*(i|we)\s+(really\s+)?"
                     r"(enjoyed|loved|liked|saw|went to|tried)\b", re.IGNORECASE)
# The coach skill's own triggers: a new coach, a different voice, a coach that sounds or talks differently.
COACH_WORDS = re.compile(r"\b(new|another|different|own|switch|change|design|make|create)\b[^.?!]{0,30}"
                         r"\b(coach|voice|trainer)|\b(coach|voice)\b[^.?!]{0,20}\b(sounds?|talks?|a (wo)?man)\b",
                         re.IGNORECASE)

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md"), encoding="utf-8") as _f:
    INSTRUCTIONS = _f.read()
# who writes the words: the instructions mark what differs (<!-- writers: one --> ... <!-- writers: end -->)
WRITERS_BLOCK = re.compile(r"<!-- writers: (one|three) -->(.*?)<!-- writers: end -->", re.DOTALL)
WRITERS = ("one", "three")


def preamble(writers: str = "one") -> str:
    """The instructions for a turn whose words this agent writes ("one") or three writers write ("three")."""
    return WRITERS_BLOCK.sub(lambda m: m.group(2) if m.group(1) == writers else "", INSTRUCTIONS)


PREAMBLE = preamble("one")


# With three writers this agent designs and fixes the script but writes none of it: script.md's craft is theirs
CRAFT = "\n## Getting the workout done"


@functools.lru_cache(maxsize=8)
def skill_text(engine_root: str, setup: bool = False, coach: bool = False, writers: str = "one") -> str:
    """The workout skill as the engine ships it (and the setup skill, for a listener not set up yet, and the
    coach skill while a coach is being made), so the web follows the same steps as the CLI, less the passages
    marked for a computer only; with three writers, script.md only up to its craft, which the writers read."""
    parts = []
    for rel in (SETUP if setup else ()) + (COACH if coach else ()) + SKILL + WRITING:
        with open(os.path.join(engine_root, rel), encoding="utf-8") as f:
            text = web_copy(f.read())
        if writers == "three" and rel == "knowledge/script.md" and CRAFT in text:
            text = text[:text.index(CRAFT)]
        parts.append(f"<file path=\"{rel}\">\n{text}\n</file>")
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


def intent(line: str | None) -> str:
    """What a first message asks for: "setup" (to be set up), "workout", "coach", or "task" (one job: change
    the equipment, update an injury or interests, a question). No message reads as a workout request."""
    if not line or not line.strip():
        return "workout"
    if ONBOARD_WORDS.search(line):
        return "setup"
    if COACH_WORDS.search(line):
        return "coach"
    if ENJOYED.search(line):   # "Lately I enjoyed a 5k run" is something they enjoyed, not a workout request
        return "task"
    if WORKOUT_WORDS.search(line) and not re.search(r"\b(equipment|kit|injur\w*|pain|hurts?|sore|interests?|topics?)\b", line, re.I):
        return "workout"
    return "task"


def audition_open(home: str) -> bool:
    """Whether an audition is waiting for the listener's pick (a candidates list in me/coaches/.auditions/)."""
    base = os.path.join(home, "coaches", ".auditions")
    try:
        return any(os.path.isfile(os.path.join(base, d, "candidates.json")) for d in os.listdir(base))
    except OSError:
        return False


AGENT = Agent(deps_type=Deps, output_type=str, retries=1)


@AGENT.instructions
def _preamble(ctx: RunContext[Deps]) -> str:
    return preamble(ctx.deps.writers)


@AGENT.instructions
def _skill(ctx: RunContext[Deps]) -> str:
    return skill_text(ctx.deps.engine_root, ctx.deps.setup, ctx.deps.coach, ctx.deps.writers)


@AGENT.instructions
def _now(ctx: RunContext[Deps]) -> str:
    return f"Now: {ctx.deps.now} (today is {ctx.deps.today})."


# What the listener sees while a tool runs: what it means for them, never a command or a file's name.
STEPS = {"brief": "Working out today's safe moves", "build": "Recording your workout",
         "check": "Checking your profile is complete", "content": "Choosing what fills the rests",
         "coaches": "Checking which coaches can speak", "coverage": "Looking at your recent sessions",
         "feeds": "Gathering today's news and weather", "get": "Checking your settings",
         "log-session": "Logging the session", "movements": "Looking through the moves",
         "youtube": "Finding a video", "keys": "Checking your voice keys", "help": "Looking up how a step works",
         "interests": "Noting what you enjoy", "workouts": "Looking at your past workouts"}
# a command's second word, where it says more than the first
SUB_STEPS = {("get", "cost"): "Pricing the recording", ("get", "web-builds"): "Checking your past recordings",
             ("content", "log"): "Noting the stories you heard", ("content", "reserve"): "Checking the story stock",
             ("content", "trending"): "Seeing what's trending today",
             ("youtube", "transcript"): "Reading a video's transcript", ("youtube", "puzzles"): "Finding a puzzle",
             ("youtube", "done"): "Noting the video series", ("movements", "--about"): "Reading the coaching notes"}
OTHER_STEP = "Running a check"
# After the recording, what the model reads (say, why a total ran off plan) is all one step to the listener.
WRAPPING_UP = "Wrapping up"
# What the model is doing between tools, by what the turn did last (Deps.phase): shown while it thinks.
THINK = {"": "Reading your message", "brief": "Planning your script", "skeleton": "Writing your script",
         "rests": "Writing your script",
         "draft": "Checking over the script", "lint_failed": "Fixing the script",
         "linted": "Getting the recording ready", "priced": "Writing up the plan",
         "recorded": WRAPPING_UP, "audition": "Introducing the voices", "coach": "Working on your coach"}
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


def _write_step(path: object, fixing: bool = False, skeleton: bool = False) -> str:
    if isinstance(path, str) and path.startswith("me/coaches/"):
        return "Describing your coach"
    if isinstance(path, str) and path.endswith(".draft.txt"):
        return "Planning the script's timing" if skeleton else \
            "Tightening the script's timing" if fixing else "Writing your script"
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


# How hard Gemini thinks, by what the turn is doing. Its default thought for 3,000 to 9,500 tokens a request
# (a 96-second write in 0.49.4's loop, two thirds of it thinking): designing, writing and fixing the script get
# medium, and the steps between them (running the brief, the reply that ends the turn) get low. The rests, written
# first after the skeleton and where every story is told, get high: the judges heard headlines read out at medium.
THINK_HARD = ("brief", "skeleton", "draft", "lint_failed")
THINK_HARDEST = ("rests",)


def thinking_level(model, phase: str) -> str | None:
    """HIGH, MEDIUM or LOW for a Gemini model, by the turn's phase; None for any other provider (its default)."""
    if type(model).__name__ != "GoogleModel":
        return None
    return "HIGH" if phase in THINK_HARDEST else "MEDIUM" if phase in THINK_HARD else "LOW"


class Narrated(WrapperModel):
    """The turn's model, saying what it's thinking about while each request runs: the longest waits in a turn
    (reading the message, writing the script) are the model's, between tools, and were silent."""

    def __init__(self, wrapped, deps: Deps):
        super().__init__(wrapped)
        self._deps = deps

    async def request(self, messages, model_settings, model_request_parameters):
        deps = self._deps
        text = THINK.get(deps.phase, THINK_OTHER)
        deps.loop = asyncio.get_running_loop()   # where a tool's thread starts the personal content writer
        n = _begin(deps, text, "think", think=True)
        level = thinking_level(self.wrapped, deps.phase)
        if level:
            model_settings = dict(model_settings or {}, google_thinking_config={"thinking_level": level})
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
    _say(deps, text, tool, 0 if result.refused else result.code, n)   # a refusal is the model's to fix
    return result


def _coach_folders(home: str) -> set[str]:
    try:
        return {d for d in os.listdir(os.path.join(home, "coaches")) if not d.startswith(".")}
    except OSError:
        return set()


RECORDING = "Recording your workout"
AUTO_RECORDED = ("Recorded straight away: the listener chose Record without asking in Settings, so there was no "
                 "Record button. Log the session, then end your turn with the plan in one small table, the coach, "
                 "and a line saying it's ready (in place of the one-line reply).")
OFF_PLAN = 2   # the build's exit when the MP3's total ran more than five percent off plan: an MP3 was still made
OFF_PLAN_NOTE = f"{RECORDING} (a little off its planned length)"
PROGRESS = re.compile(r"^\s*\[(\d+)/(\d+)\]", re.MULTILINE)   # render_cloud's "  [18/40] 4.2s audio"
PROGRESS_EVERY = 2.0   # seconds between progress updates, at most


def _log_sizes(home: str) -> dict[str, int]:
    """Each build log's size now (me/workouts/.logs/*.log), so a recording reads only the lines it adds."""
    where = os.path.join(home, "workouts", ".logs")
    try:
        return {n: os.path.getsize(os.path.join(where, n)) for n in os.listdir(where) if n.endswith(".log")}
    except OSError:
        return {}


def _progress(home: str, before: dict[str, int]) -> tuple[int, int] | None:
    """(sent, of) from the newest "[n/m]" line the build has added to its log since `before`, or None."""
    where = os.path.join(home, "workouts", ".logs")
    found = None
    for name, size in _log_sizes(home).items():
        start = before.get(name, 0)
        if size < start:   # the log passed its limit and started over (build.log_to)
            start = 0
        elif size == start:
            continue
        try:
            with open(os.path.join(where, name), "rb") as f:
                f.seek(start)
                text = f.read().decode("utf-8", "replace")
        except OSError:
            continue
        hits = PROGRESS.findall(text)
        if hits:
            found = (int(hits[-1][0]), int(hits[-1][1]))
    return found


def _recording(deps: Deps, args: list[str], tool: str) -> ToolResult:
    """The approved recording: "Designing <coach>'s voice" first when the coach is made in this build (until its
    folder appears in me/coaches/), then "Recording your workout", which counts the pieces sent as the build's
    log shows them ("Recording your workout: 18 of 40"). A total off plan (exit 2) still made an MP3, so it ends
    as done, with a note. The watch thread says each change while this thread waits on the engine and is joined
    before this thread says anything again, so the worker's connection (`say` writes a job event on it) is never
    used by two threads at once; the heartbeat has its own."""
    ok = deps.approved or {}
    design = f"Designing {ok.get('coach') or 'your coach'}'s voice" if ok.get("design") else None
    folders = _coach_folders(deps.home)
    logs = _log_sizes(deps.home)
    first = _begin(deps, design or RECORDING, tool)
    recording: list[int] = [] if design else [first]
    shown = [RECORDING]
    stop = threading.Event()

    def watch() -> None:
        last = 0.0
        while not stop.wait(1.0):
            if not recording:
                if _coach_folders(deps.home) - folders:
                    _say(deps, design, tool, 0, first)
                    recording.append(_begin(deps, RECORDING, tool))
                continue
            now = time.monotonic()
            if now - last < PROGRESS_EVERY:
                continue
            seen = _progress(deps.home, logs)
            text = f"{RECORDING}: {seen[0]} of {seen[1]}" if seen and seen[1] > 1 else RECORDING
            if text != shown[0]:
                shown[0] = text
                last = now
                _say(deps, text, tool, None, recording[0])
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
        if not recording:
            _say(deps, design, tool, code, first)
        elif code == OFF_PLAN:
            _say(deps, OFF_PLAN_NOTE, tool, 0, recording[0])
        else:
            _say(deps, RECORDING, tool, code, recording[0])


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
    # the worker's log names the command and its subcommand ("run get web-builds"), never a value
    sub = rest[1] if len(rest) > 1 and isinstance(rest[1], str) and re.fullmatch(r"[a-z][a-z-]*", rest[1]) else ""
    tool = (f"run {first} {sub}".strip() + (" --lint-only" if first == "build" and "--lint-only" in args else ""))[:40]
    if first == "build" and "--lint-only" not in args:
        draft = rest[1] if len(rest) > 1 else None
        if deps.approved and deps.approved.get("draft") == draft:
            deps.phase = "recorded"
            result = _recording(deps, args, tool)
            if deps.recorded and deps.checkpoint is not None:
                deps.checkpoint()   # the coach, the MP3 and the clips, kept now: a later stop can't lose them
            return result
        text = "Checking and pricing the script"   # an unapproved build checks the script, then prices it
    if first == "build" and "--lint-only" in args:
        text = ("Planning the script's timing" if deps.skeleton == "skeleton" else
                "Checking the script so far" if deps.skeleton else
                "Checking the script again" if deps.lint_failed else "Checking the script's safety and timing")
    if first == "coaches" and len(rest) > 1 and rest[1] in COACH_STEPS:
        text = COACH_STEPS[rest[1]]
    result = _step(deps, text, tool, lambda: tools.run(deps, args))
    if result.refused:   # the site's own refusal: the script wasn't checked, so nothing about it changes
        return result
    if first == "build" and deps.skeleton:   # the lint gave the budgets: the words come next
        # after the whole skeleton's budgets come the rests, the stories: the request that writes them thinks hardest
        deps.phase = "rests" if deps.skeleton == "skeleton" else "skeleton"
        deps.skeleton = ""
        deps.lint_failed = False
    elif first == "build":
        deps.lint_failed = result.code != 0
        deps.phase = "lint_failed" if result.code != 0 else ("linted" if "--lint-only" in args else "priced")
        offer = deps.offer
        if (deps.phase == "priced" and deps.auto_record and offer and offer.get("draft") == rest[1]
                and not deps.recorded and deps.reserve is not None and deps.reserve(int(offer.get("chars") or 0))):
            # Record without asking (Settings): approved as the Record button would, today's allowance reserved
            # first; past the allowance the offer stays, and the button says why
            deps.approved, deps.offer = offer, None
            recorded = run(ctx, args)
            if not deps.recorded:
                return recorded
            return recorded.model_copy(update={"output": AUTO_RECORDED + "\n" + recorded.output})
    elif first == "brief":
        deps.phase = "brief"
        if deps.writers == "three" and result.code == 0:
            _start_stories(ctx, args)
    elif first == "coaches" and len(rest) > 1 and rest[1] == "audition":
        deps.phase = "audition"
    elif first == "coaches" and len(rest) > 1 and rest[1] in ("make", "keep"):
        deps.phase = "coach"
    return result


@AGENT.tool(sequential=True)
def read_file(ctx: RunContext[Deps], path: str) -> ToolResult:
    """Read a text file: me/... (the listener's folder) or the engine's knowledge/, .claude/skills/, coaches/."""
    text = WRAPPING_UP if ctx.deps.phase == "recorded" else _read_step(path)
    return _step(ctx.deps, text, "read_file", lambda: tools.read_file(ctx.deps, path))


def _start_stories(ctx: RunContext[Deps], args: list[str]) -> None:
    """Two writers: the personal content writer starts as the brief is saved, on the turn's loop, and writes while the
    agent designs the skeleton; write_script waits for it."""
    deps = ctx.deps
    draft, minutes = tools._flag(args, "--save"), tools._flag(args, "--minutes")
    if not (draft and minutes and minutes.isdigit() and deps.loop is not None) or deps.content_for == draft:
        return
    model = getattr(ctx.model, "wrapped", ctx.model)
    deps.content_for = draft
    deps.content_job = asyncio.run_coroutine_threadsafe(
        writers.stories(deps, model, ctx.usage, draft, int(minutes), [NativeTool(t) for t in native_tools(model)]),
        deps.loop)


def _then_build(ctx: RunContext[Deps], path: object, written: ToolResult, name: str | None,
                coach: str | None) -> ToolResult:
    """A draft written with its build's name and coach is built at once, as `run build` would (its lint, then its
    price when clean): one round trip a fix, not two. The write's own line first, then the build's. A draft with
    segments still empty (a skeleton, or one written in passes) is linted only: its report is each segment's word
    budget and what's left to write."""
    if written.code != 0 or not written.build or not (isinstance(path, str) and path.endswith(".draft.txt")):
        return written
    # a draft written without them builds anyway, under its stem's name and the brief's coach: a write left
    # unbuilt is a round trip spent on `run build`
    name, coach = name or tools.build_name(path), coach or ctx.deps.brief_coach
    if not (name and coach):
        return written
    unfinished = written.unfinished > 0
    ctx.deps.skeleton = ("skeleton" if written.unfinished == written.segments else "partial") if unfinished else ""
    built = run(ctx, ["build", path, name, "--coach", coach] + (["--lint-only"] if unfinished else []))
    output = built.output
    if written.unfinished == written.segments:   # a skeleton's budgets: what the writers write to
        ctx.deps.reports[path] = output
    if not unfinished:   # a full draft's "add about N words", scaled to what this writer delivers
        full, _ = tools._mine(ctx.deps, path)
        try:
            with open(full, encoding="utf-8") as f:
                output = tools.scale_ask(ctx.deps, path, output, tools._words(f.read()))
        except (OSError, TypeError):
            pass
    return built.model_copy(update={"output": written.output + "\n\n### build (exit " + str(built.code) + ")\n"
                                    + output})


@AGENT.tool(sequential=True)
def write_file(ctx: RunContext[Deps], path: str, content: str, build_name: str | None = None,
               coach: str | None = None) -> ToolResult:
    """Write (create or replace) a text file in the listener's folder, me/... only. For a draft, pass its build's
    name and coach too, and the build runs right after the write (its lint, then its price when clean), its
    result in this reply: no separate `run build`. A draft with no words yet is the skeleton: its result gives each
    segment's word budget."""
    skeleton = isinstance(path, str) and path.endswith(".draft.txt") and isinstance(content, str) \
        and tools.is_skeleton(content)
    result = _step(ctx.deps, _write_step(path, ctx.deps.lint_failed, skeleton), "write_file",
                   lambda: tools.write_file(ctx.deps, path, content))
    if isinstance(path, str) and path.endswith(".draft.txt"):
        ctx.deps.phase = "draft"
    return _then_build(ctx, path, result, build_name, coach)


@AGENT.tool(sequential=True)
def edit_segments(ctx: RunContext[Deps], path: str, edits: list[tools.SegmentEdit], build_name: str | None = None,
                  coach: str | None = None) -> ToolResult:
    """Replace segments of a draft, all in one call: each edit is a segment's place from 1 (the lint's # column)
    and the whole new segment, its `@@ <seconds> | <label>` line first. Every fix one lint names goes in one call,
    instead of writing the draft again. Pass the build's name and coach, and the build runs right after (its lint,
    then its price when clean), its result in this reply."""
    result = _step(ctx.deps, _write_step(path, ctx.deps.lint_failed), "edit_segments",
                   lambda: tools.edit_segments(ctx.deps, path, list(edits)))
    ctx.deps.phase = "draft"
    return _then_build(ctx, path, result, build_name, coach)


# what the listener sees while the writers work: the longest step in a turn, so they know they can step away
WRITING_STEP = "Writing your script: a few minutes, so feel free to step away"


async def _three_writers(ctx: RunContext[Deps], tool):
    """write_script is offered only to a turn whose words three writers write."""
    return tool if ctx.deps.writers == "three" else None


@AGENT.tool(sequential=True, prepare=_three_writers)
async def write_script(ctx: RunContext[Deps], path: str, build_name: str | None = None,
                       coach: str | None = None) -> ToolResult:
    """Fill a skeleton with the script's words: a coach writer and a personal content writer write side by side, each segment
    to its budget, and the draft builds right after (its lint, then its price when clean), its result and the draft
    in this reply. Only when the instructions name it."""
    deps = ctx.deps
    if deps.writers != "three":
        return tools._refuse("write the script's words yourself, with edit_segments, as the instructions say")
    n = _begin(deps, WRITING_STEP, "write_script")
    model = getattr(ctx.model, "wrapped", ctx.model)   # the turn's model, without the narration
    try:
        draft, note = await writers.write(deps, model, ctx.usage, path, [NativeTool(t) for t in native_tools(model)])
    except writers.NotReady as e:
        _say(deps, WRITING_STEP, "write_script", 0, n)
        return tools._refuse(str(e))
    except BaseException:
        _say(deps, WRITING_STEP, "write_script", 1, n)
        raise
    _say(deps, WRITING_STEP, "write_script", 0, n)
    written = await asyncio.to_thread(tools.write_file, deps, path, draft)
    deps.phase = "draft"
    built = await asyncio.to_thread(_then_build, ctx, path, written, build_name, coach)
    full, _ = tools._mine(deps, path)
    try:
        with open(full, encoding="utf-8") as f:
            text = f.read()
    except (OSError, TypeError):
        text = draft
    return built.model_copy(update={"output": note + "\n\n### the draft, as written\n" + text + "\n\n" + built.output})


@AGENT.tool(sequential=True)
def list_files(ctx: RunContext[Deps], path: str = "me/") -> ToolResult:
    """List the files under a folder of the listener's, me/ by default."""
    text = WRAPPING_UP if ctx.deps.phase == "recorded" else "Looking through your files"
    return _step(ctx.deps, text, "list_files", lambda: tools.list_files(ctx.deps, path))


# Step 1 of the skill, run by the worker before the first model request, all at once: the model gets the
# same results in the listener's first message, without a round trip for each.
FIRST_RUNS = (["check"], ["content", "plan", "--minutes", "25"], ["get", "coach"], ["coaches", "list", "--json"],
              ["get", "web-builds"], ["get", "limits"])
MINUTES = re.compile(r"\b(\d{1,3})[- ]?(?:minutes?|mins?)\b", re.IGNORECASE)


def first_runs(line: str | None) -> list[list[str]]:
    """Step 1's commands, the rests' plan sized to the length the request names (25 when it names none)."""
    found = MINUTES.search(line or "")
    minutes = found.group(1) if found and 0 < int(found.group(1)) <= 180 else "25"
    return [["content", "plan", "--minutes", minutes] if a[:2] == ["content", "plan"] else list(a) for a in FIRST_RUNS]
SETUP_FIRST = ("This listener isn't set up yet: before the workout, the setup skill's quick start asks what to call "
               "them, their experience, and any injuries or limits, then today's check-in. One question a reply, "
               "as the instructions say: ask the first now, and write each answer as it comes, before the brief runs.")


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
def _picked(deps: Deps, listed: ToolResult) -> str | None:
    """The name of the coach chosen on the page, while it can speak here and no workout logged on a later day
    used another (as the page's first screen shows it); None otherwise."""
    if deps.picked is None:
        return None
    slug, day = deps.picked
    try:
        found = json.loads(listed.output)["coaches"]
        coach = next((c for c in found if isinstance(c, dict) and c.get("slug") == slug and c.get("speaks_here")
                      and isinstance(c.get("name"), str)), None)
        if coach is None:
            return None
        with open(os.path.join(deps.home, "log.md"), encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        text = ""
    except (ValueError, KeyError, TypeError, OSError):
        return None
    from .. import start   # start imports worker, which imports this package
    return coach["name"] if start.chosen_holds(coach, day, start.logged(deps.engine_root, text)) else None


FIRST_READS = ("me/profile.md", "me/training.md", "me/health.md", "me/log.md", "me/content.md", "me/settings.toml")


def _block(title: str, r: ToolResult) -> str:
    body = (r.output + ("\n" + r.error if r.error else "")).strip() or "(nothing)"
    return f"### {title} (exit {r.code})\n````\n{body}\n````"


COACH_FIRST = ("This listener isn't set up yet, and asked about their coach. Do only that, now: coaches are chosen on "
               "the Coaches page, so point them there in a line (or, if they named one that can speak here, use it). "
               "No setup questions and no workout check-in this turn.")
TASK_FIRST = ("This listener isn't set up yet, and asked for one thing. Do only that, now, as the instructions' One "
              "request, one job says: no setup questions and no workout check-in this turn, and only the questions "
              "that one job needs, one a reply. When it's done, say in a line that a few quick questions will set "
              "them up when they want a first workout.")


def prefetch(deps: Deps, line: str | None = None) -> str:
    """Step 1's commands and reads, run at once; returned as text for the first message. A listener not set up
    yet gets the setup questions only with a workout (or when they ask to be set up): a coach, or any one job
    (their equipment, an injury, their interests), is done on its own first."""
    plain = replace(deps, say=None, feeds=None)
    fresh = deps.setup and needs_setup(deps.home)
    want = intent(line)
    first_text = (COACH_FIRST if want == "coach" else TASK_FIRST if want == "task" else SETUP_FIRST) if fresh else ""
    label = ("Looking at your coaches" if fresh and want == "coach" else "Getting you set up"
             if fresh and want in ("setup", "workout") else "Reading your profile"
             if want == "task" else "Reading your profile and today's limits")   # limits only matter to a workout
    step = _begin(deps, label, "prefetch")
    commands = first_runs(line)
    with ThreadPoolExecutor(max_workers=len(commands) + len(FIRST_READS)) as pool:
        runs = [pool.submit(tools.run, plain, a) for a in commands]
        sheet = f"me/workouts/research/daily/{deps.today}.md"   # a research sheet a computer wrote today
        extra = (sheet,) if deps.today and os.path.isfile(os.path.join(deps.home, "workouts", "research", "daily",
                                                                       f"{deps.today}.md")) else ()
        reads = [pool.submit(tools.read_file, plain, p) for p in FIRST_READS + extra]
        results = [(f"./harmonicfitness {' '.join(a)}", f.result()) for a, f in zip(commands, runs)]
        results += [(f"read {p}", f.result()) for p, f in zip(FIRST_READS + extra, reads)]
    picked = _picked(deps, results[3][1])
    results[3] = ("./harmonicfitness coaches list", _coaches(results[3][1]))
    coach = results[2][1]
    name = None
    if coach.code == 0 and coach.output.strip():
        name = coach.output.strip().splitlines()[0].strip()
    if picked and picked != name:
        results.append(("the coach they chose on the page", ToolResult(code=0, output=(
            f"{picked}: the listener chose this coach in the page's Settings or its sentence. Use {picked} for "
            f"this workout unless they name another; `get coach` above is only the coach used last."))))
        name = picked
    if name:
        results.append((f"./harmonicfitness get route --coach \"{name}\"",
                        tools.run(plain, ["get", "route", "--coach", name])))
    results.append(("today's workout folders (a new workout's stem takes -2, -3 when one is taken)",
                    ToolResult(code=0, output=_todays_folders(deps))))
    _say(deps, label, "prefetch", 0, step)
    first = first_text + "\n\n" if first_text else ""
    return (first + "Step 1 is done: these are its results, run as this turn began. Don't run or read them again "
            "this turn.\n\n" + "\n\n".join(_block(t, r) for t, r in results))


def _todays_folders(deps: Deps) -> str:
    """The workout folders already made today (me/workouts/<today>-...), so the model needn't list them."""
    try:
        names = sorted(n for n in os.listdir(os.path.join(deps.home, "workouts"))
                       if n.startswith(f"{deps.today}-") and os.path.isdir(os.path.join(deps.home, "workouts", n)))
    except OSError:
        names = []
    return "\n".join(f"me/workouts/{n}/" for n in names) or "none yet today"


def start_feeds(deps: Deps, pool: ThreadPoolExecutor) -> Future:
    """`feeds` in the background, so today's research is ready when the script needs it."""
    return pool.submit(tools._plain_run, replace(deps, say=None, feeds=None), ["feeds"])


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


def native_tools(model) -> list:
    """The writer's web search, where its model supports it; none for a model that doesn't (a test's own)."""
    try:
        supported = model.supported_native_tools()
    except (AttributeError, NotImplementedError):
        return []
    return [SEARCH] if WebSearchTool in supported else []


def run_turn(model, deps: Deps, history_json: str | None, prompt: str | None,
             answer: tuple[str, dict] | None = None, context: str | None = None) -> TurnOutcome:
    """One run of the agent on the user's line, after `context` (prefetch's text) when given.
    UsageLimitExceeded and provider errors propagate; the caller decides what they mean."""
    if answer is not None or not prompt:
        raise TurnError("this coach asks its questions in the chat; send a message", NOT_OPEN)
    # three writers write the script (0.51.0); HARMONICFITNESS_WRITERS=one has this agent write it, in passes
    wanted = os.environ.get("HARMONICFITNESS_WRITERS", "three")
    deps.writers = wanted if wanted in WRITERS else "three"
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
                                usage_limits=LIMITS, cancellation_token=token,
                                capabilities=[NativeTool(t) for t in native_tools(model)])
    except RunCancelled:
        if deps.cancel is not None and deps.cancel.is_set():
            raise TurnError("stopped", STOPPED) from None
        raise TurnError("the turn ran too long", TIMED_OUT) from None
    finally:
        done.set()
        timer.cancel()
        if deps.content_job is not None:   # a personal content writer the turn never waited for stops with it
            deps.content_job.cancel()
    u = result.usage
    searches = sum(isinstance(p, NativeToolCallPart) for m in result.new_messages() for p in m.parts)
    usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens,
             "output_tokens": u.output_tokens, "searches": searches}
    return TurnOutcome(history_json=result.all_messages_json().decode("utf-8"), reply=result.output, usage=usage)
