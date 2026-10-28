"""The agent: one loop for every provider, over the typed engine tools, ask_user (a question that pauses
the turn for the user) and show_plan (the plan, shown only when every movement is on the brief's menu).
The model is passed per turn; nothing here knows which provider it is."""
import os
import re
import threading
import tomllib
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart, ToolReturnPart
from pydantic_ai import (Agent, CallDeferred, CancellationToken, DeferredToolRequests, DeferredToolResults,
                         ModelMessagesTypeAdapter, ModelRetry, RunContext, UsageLimits)
from pydantic_ai.exceptions import RunCancelled

from webapp import worker

from . import tools
from .tools import Deps, ToolResult

__all__ = ["AGENT", "Deps", "NOT_OPEN", "Option", "Plan", "PlanRow", "Question", "TurnError", "TurnOutcome",
           "LIMITS", "TIMED_OUT", "TURN_SECONDS", "UNFINISHABLE", "plan_problems", "run_turn"]

LIMITS = UsageLimits(request_limit=25, tool_calls_limit=40, total_tokens_limit=800_000)
WATCH_EVERY = 0.2    # seconds between the turn's looks at its cancel event
TURN_SECONDS = 600   # a turn's wall-clock cap: past it the run is cancelled (TurnError TIMED_OUT), never retried

with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "instructions.md"), encoding="utf-8") as _f:
    INSTRUCTIONS = _f.read()

_Short = Field(min_length=1, max_length=200)


class Option(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=200)
    recommended: bool = False


class Question(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    prompt: str = _Short
    options: list[Option] = Field(min_length=2, max_length=6)
    multi: bool = False
    other: bool = False

    @model_validator(mode="after")
    def _one_recommended(self):
        if sum(o.recommended for o in self.options) != 1:
            raise ValueError("mark exactly one option recommended")
        if len({o.label for o in self.options}) != len(self.options):
            raise ValueError("each option needs its own label")
        return self


class PlanRow(BaseModel):
    block: str = Field(min_length=1, max_length=80)
    movements: list[str] = Field(min_length=1, max_length=20)
    dose: str = _Short
    seconds: int = Field(gt=0)


class Plan(BaseModel):
    format: str = _Short
    equipment: str = _Short
    rows: list[PlanRow] = Field(min_length=1, max_length=20)
    left_out: str = Field(max_length=300)
    total_seconds: int = Field(gt=0)


AGENT = Agent(deps_type=Deps, output_type=[str, DeferredToolRequests], instructions=INSTRUCTIONS, retries=1)


@AGENT.instructions
def _now(ctx: RunContext[Deps]) -> str:
    return f"Now: {ctx.deps.now} (today is {ctx.deps.today})."


# ---- the engine tools --------------------------------------------------------------------------

@AGENT.tool
def read_file(ctx: RunContext[Deps], name: Literal["profile.md", "training.md", "health.md", "log.md"]) -> ToolResult:
    """Read one of the listener's files: profile.md, training.md, health.md or log.md."""
    return tools.read_file(ctx.deps, name)


@AGENT.tool
def check(ctx: RunContext[Deps]) -> ToolResult:
    """What the listener's files still need, and anything the tools can't read."""
    return tools.check(ctx.deps)


@AGENT.tool
def get_coach(ctx: RunContext[Deps]) -> ToolResult:
    """The coach a workout takes by default (code 1: the coach used last is archived)."""
    return tools.get_coach(ctx.deps)


@AGENT.tool
def get_route(ctx: RunContext[Deps], coach: str) -> ToolResult:
    """Where a coach speaks: `local` or the web coach's service; code 1, 4 or 64 when it can't speak here."""
    return tools.get_route(ctx.deps, coach)


@AGENT.tool
def coaches(ctx: RunContext[Deps]) -> ToolResult:
    """Every coach the listener can choose, as JSON."""
    return tools.coaches(ctx.deps)


@AGENT.tool
def content_plan(ctx: RunContext[Deps], minutes: int) -> ToolResult:
    """What the rests of a session this long will carry, as JSON."""
    return tools.content_plan(ctx.deps, minutes)


@AGENT.tool
def coverage(ctx: RunContext[Deps]) -> ToolResult:
    """From the log: patterns left out lately, last loads, days since the last session, latest feedback."""
    return tools.coverage(ctx.deps)


@AGENT.tool(sequential=True)   # never alongside show_plan: the menu it checks against is the one this sets
def brief(ctx: RunContext[Deps], goal: str, minutes: int, coach: str, kit: str | None = None,
          preset: str | None = None, equipment: list[str] | None = None, limits: list[str] = [],
          avoid: list[str] = [], target: list[str] = [], add: list[str] = []) -> ToolResult:
    """Today's ingredients: the listener, today's limits, the safe menu, the programming guide. Give exactly
    one of kit, preset or equipment. limits items are `area=level[:side]`."""
    return tools.brief(ctx.deps, goal=goal, minutes=minutes, kit=kit, preset=preset, equipment=equipment,
                       coach=coach, limits=list(limits), avoid=list(avoid), target=list(target), add=list(add))


# ---- the question and the plan -----------------------------------------------------------------

@AGENT.tool
def ask_user(ctx: RunContext[Deps], questions: Annotated[list[Question], Field(min_length=1, max_length=4)]) -> dict:
    """Ask the listener one to four questions; the turn pauses until they answer. The answer is
    {question id: [chosen labels]} or {question id: "other: <text>"}."""
    raise CallDeferred(metadata={"kind": "questions"})


def _engine(deps: Deps):
    """The engine's catalog, menu and errors modules, and the catalog the brief read: the shipped one plus
    the listener's private movements, as the brief's own run loaded it."""
    catalog, menu, errors = worker._engine_modules(deps.engine_root, "catalog", "menu", "errors")
    try:
        extra = catalog.private_movements(os.path.join(deps.home, "movements.toml"))
    except (tomllib.TOMLDecodeError, OSError):   # the brief left them out too
        extra = []
    return catalog, menu, errors, catalog.load(extra=extra)


SIDES = ("left", "right", "both", "healthy")
HEALTHY = re.compile(r"^\s*healthy(?:[\s-]+side)?\s+", re.IGNORECASE)   # catalog.resolve drops left/right/both itself


def _side_problem(catalog, name: str, side: str) -> str | None:
    """Why a plan's name for a movement the menu allows on one side only doesn't hold that side, or None.
    The name's words (catalog.plain) must include the menu's side ("left", "right", or "healthy" when the
    limit named no side) and no other side word ("left", "right", "both"). catalog.resolve has already
    matched the movement with a leading side word dropped, so "right single-leg glute bridge" is the bridge;
    this says whether that side is the one allowed."""
    words = set(catalog.plain(name).split())
    named = words & set(SIDES)
    if side in words and named == {side}:
        return None
    if named - {side}:
        return f'"{name}" names the {", ".join(sorted(named - {side}))} side, but today\'s menu allows it on the {side} side only'
    say = "healthy side" if side == "healthy" else side
    return f'"{name}" is allowed on the {side} side only today; name the side (say "{say} {name}")'


# words that put a movement on both sides (compared as catalog.plain words, so "per-side" is "per side")
# ("left/right", "left-right" and "l/r" become "left right" and "l r"; "switch" covers "switch sides")
BOTH_SIDES = ("each side", "both sides", "each leg", "both legs", "each arm", "both arms", "per side", "per leg",
              "per arm", "alternating", "alternate", "left and right", "right and left", "either side",
              "every side", "every leg", "every arm", "other side", "other leg", "other arm", "opposite side",
              "opposite leg", "opposite arm", "switch", "swap sides", "repeat on the other", "bilateral",
              "two sides", "each hip", "per limb", "left right", "right left", "l r", "r l", "r and l", "l and r")
CLAUSE = re.compile(r"[.!?;:,()\n]")


def _both_sides(catalog, text: str) -> str | None:
    """The words in `text` that do a movement on both sides ("each side", "alternating"...), or None."""
    padded = f" {catalog.plain(text)} "
    return next((w for w in BOTH_SIDES if f" {w} " in padded), None)


def _one_side_problem(catalog, text: str, mname: str, side: str) -> str | None:
    """Why a clause naming (or dosing) a movement the menu allows on one side only puts it on another side
    or both, or None: a both-sides phrase, or a side word ("left", "right", "both") other than the menu's."""
    say = "healthy side" if side == "healthy" else f"{side} side"
    phrase = _both_sides(catalog, text)
    named = set(catalog.plain(text).split()) & {"left", "right", "both"}
    if phrase is None and not (named - {side}):
        return None
    how = f'"{phrase}"' if phrase else f'the {", ".join(sorted(named - {side}))} side'
    return (f'"{text.strip()}" puts {mname} on {how}, but today\'s menu allows it on the {say} only; write its '
            f'dose for that side alone (say "3 x 10, {say} only")')


def _text_problems(catalog, menu, cat, plan: Plan, on_menu: dict) -> list[str]:
    """The plan's free text (format, equipment, left_out, each row's block and dose) checked as the build
    checks a draft's spoken text (menu.mentions, with its EVERYDAY words, shortened names of the plan's own
    movements and negations: "no box jumps today"): a movement that isn't on today's menu is refused, and a
    movement the menu allows on one side only may not be put on another side or both, in the words that
    name it or in the block and dose of a row that holds it."""
    declared, sided_rows = set(), []
    for row in plan.rows:
        for name in row.movements:
            m = catalog.resolve(cat, HEALTHY.sub("", name))
            if m is not None and m.id in on_menu:
                declared.add(m.id)
                if on_menu[m.id].get("side"):
                    sided_rows.append((row, m, on_menu[m.id]["side"]))
    names = [n for i in declared for n in [cat.movements[i].name] + cat.movements[i].aliases]
    problems, flagged, sided = [], set(), set()   # sided: one-sided movements already refused (one line each)
    for row, m, side in sided_rows:   # "3 x 10 each side" for a movement allowed on one side only
        for text in (row.block, row.dose):
            why = _one_side_problem(catalog, text, m.name, side) if _both_sides(catalog, text) else None
            if why and m.id not in sided:
                sided.add(m.id)
                problems.append(why)
    fields = [("format", plan.format), ("equipment", plan.equipment), ("left_out", plan.left_out)]
    for row in plan.rows:
        fields += [(f'the "{row.block}" row\'s block', row.block), (f'the "{row.block}" row\'s dose', row.dose)]
    for where, text in fields:
        for clause in CLAUSE.split(text):
            for mid, said, before in menu.mentions(cat, clause):
                if menu.negated(before):
                    continue   # "no box jumps today"
                side = on_menu.get(mid, {}).get("side")
                if side:   # a one-sided movement named: its clause must keep to that side
                    why = _one_side_problem(catalog, clause, cat.movements[mid].name, side)
                    if why and mid not in sided:
                        sided.add(mid)
                        problems.append(why)
                    continue
                if mid in declared or mid in on_menu or mid in flagged or menu._part_of(cat, said, names, declared):
                    continue
                flagged.add(mid)
                problems.append(f'the plan names "{said}" ({mid}, in {where}), which isn\'t on today\'s menu; take '
                                f'it out (a "no {said} today" is fine)')
    return problems


def plan_problems(deps: Deps, plan: Plan) -> list[str]:
    """What keeps this plan from being shown, as sentences (empty when it can be)."""
    stem = deps.stem   # one menu throughout, even if a brief changes deps.stem meanwhile
    if not stem:
        return ["run brief first"]
    try:
        catalog, menu, errors, cat = _engine(deps)
    except (OSError, ValueError) as e:
        return [f"the movement catalog can't be read ({type(e).__name__}); the plan can't be checked"]
    path = os.path.join(deps.home, "workouts", stem, f"{stem}.menu.json")
    try:
        found = menu.load(path)
    except (errors.HarmonicFitnessError, OSError):   # a damaged menu is the brief's to remake
        found = None
    shape = menu.validate(found) if found is not None else ["there is no menu"]
    if shape:
        return ["the brief's menu can't be read (" + "; ".join(shape) + "): run brief again"]
    stale = menu.staleness(found, today=deps.today, health_path=os.path.join(deps.home, "health.md"))
    if stale:
        reasons = "; ".join(r.split(": rerun")[0] for r in stale)
        return [f"the brief's menu doesn't stand for today ({reasons}): run brief again"]
    on_menu = {e["id"]: e for e in found["movements"]}
    problems = []
    for row in plan.rows:
        for name in row.movements:
            m = catalog.resolve(cat, HEALTHY.sub("", name))
            if m is None or m.id not in on_menu:
                problems.append(f'"{name}" ({row.block}) isn\'t on today\'s menu; use a movement the brief lists')
                continue
            side = on_menu[m.id].get("side")
            why = _side_problem(catalog, name, side) if side else None
            if why:
                problems.append(f"{why} ({row.block})")
    problems += _text_problems(catalog, menu, cat, plan, on_menu)
    rows = sum(r.seconds for r in plan.rows)
    if rows != plan.total_seconds:
        problems.append(f"the rows add up to {rows} s, not total_seconds ({plan.total_seconds} s)")
    want = found["seconds"]
    if plan.total_seconds != want:
        problems.append(f"total_seconds is {plan.total_seconds} s, but the request is {want} s "
                        f"({want // 60} minutes)")
    return problems


@AGENT.tool(retries=2, sequential=True)   # never alongside brief
def show_plan(ctx: RunContext[Deps], plan: Plan) -> str:
    """Show the listener today's plan. Every movement must be on the brief's menu, in the movements lists
    and in any words (block, dose, format, equipment, left_out), and the rows' seconds must add up to
    total_seconds, which must be the request's minutes x 60."""
    stem = ctx.deps.stem
    problems = plan_problems(ctx.deps, plan)
    if not problems and ctx.deps.stem != stem:
        problems = ["a new brief ran meanwhile: show the plan again, from its menu"]
    if problems:
        raise ModelRetry("The plan wasn't shown: " + " ".join(p if p.endswith(".") else p + "." for p in problems))
    ctx.deps.plan = plan.model_dump()
    return "shown"


# ---- a turn ------------------------------------------------------------------------------------

NOT_OPEN = "not_open"            # TurnError.reason: an answer to a call that isn't open (nothing ran)
UNFINISHABLE = "unfinishable"    # TurnError.reason: the run stopped on a deferred call that isn't a question
TIMED_OUT = "timed_out"          # TurnError.reason: the turn ran past TURN_SECONDS and was cancelled


class TurnError(Exception):
    """A turn that can't go on as asked: an answer to a call that isn't open, the agent stopping on a
    deferred call that isn't a question, or the turn running past TURN_SECONDS; `reason` says which
    (NOT_OPEN, UNFINISHABLE or TIMED_OUT). Nothing a retry fixes; the caller fails the turn."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason


NOT_SHOWN = "This question wasn't shown: ask one set of questions at a time, in one ask_user call."
NOT_ANSWERED = "The listener didn't answer this; they wrote a new message instead."


def _pending(history) -> list[str]:
    """The ids of the tool calls in the last model response that have no result yet: the deferred ones."""
    for n in range(len(history) - 1, -1, -1):
        if isinstance(history[n], ModelResponse):
            done = {p.tool_call_id for m in history[n + 1:] for p in m.parts
                    if isinstance(p, (ToolReturnPart, RetryPromptPart))}
            return [p.tool_call_id for p in history[n].parts
                    if isinstance(p, ToolCallPart) and p.tool_call_id not in done]
    return []


@dataclass
class TurnOutcome:
    history_json: str
    reply: str | None
    question: dict | None
    plan: dict | None
    stem: str | None
    usage: dict


def run_turn(model, deps: Deps, history_json: str | None, prompt: str | None,
             answer: tuple[str, dict] | None, cancel: threading.Event | None = None) -> TurnOutcome:
    """One run of the agent: the user's line (prompt) or the answer to the open question. Every call left
    open in the history gets a result, so a conversation is never stuck on one: the answer for the question
    shown, NOT_SHOWN for any other question of the same step, NOT_ANSWERED when the user wrote instead.
    UsageLimitExceeded and provider errors propagate; the caller decides what they mean. `cancel` (default
    deps.cancel, else a new event) becomes deps.cancel: setting it stops the run and every engine call, as
    does the turn running past TURN_SECONDS, which sets it."""
    history = ModelMessagesTypeAdapter.validate_json(history_json) if history_json else None
    pending = _pending(history) if history else []
    if answer and answer[0] not in pending:
        raise TurnError("that question isn't open any more", NOT_OPEN)
    calls = {cid: NOT_SHOWN if answer else NOT_ANSWERED for cid in pending}
    if answer:
        calls[answer[0]] = answer[1]
    results = DeferredToolResults(calls=calls) if calls else None
    # the wall-clock cap: pydantic-ai's own CancellationToken stops the run (its model request and tool tasks)
    # and raises RunCancelled after its own teardown. A sync tool's thread can't be interrupted, so the timer
    # also sets `cancel`, which kills the tool's engine call; a watcher cancels the token when anything else
    # (the worker's heartbeat) sets `cancel`.
    cancel = cancel if cancel is not None else deps.cancel if deps.cancel is not None else threading.Event()
    deps.cancel = cancel
    token = CancellationToken()
    finished = threading.Event()

    def time_up() -> None:
        cancel.set()
        token.cancel()

    def watch() -> None:
        while not finished.is_set():
            if cancel.wait(WATCH_EVERY):
                token.cancel()
                return

    timer = threading.Timer(TURN_SECONDS, time_up)
    timer.daemon = True
    watcher = threading.Thread(target=watch, daemon=True, name="turn-cancel")
    timer.start()
    watcher.start()
    try:
        result = AGENT.run_sync(prompt, model=model, deps=deps, message_history=history,
                                deferred_tool_results=results, usage_limits=LIMITS, cancellation_token=token)
    except RunCancelled:
        raise TurnError("the turn ran too long", TIMED_OUT) from None
    finally:
        timer.cancel()
        finished.set()
        watcher.join()
    reply = question = None
    if isinstance(result.output, DeferredToolRequests):
        asks = [c for c in result.output.calls if c.tool_name == "ask_user"]
        if not asks or result.output.approvals:
            names = [c.tool_name for c in result.output.calls + result.output.approvals]
            raise TurnError(f"the agent stopped on a call it can't finish ({', '.join(names)})", UNFINISHABLE)
        # the questions as ask_user validated them (every field filled), not the model's raw arguments
        asked = [Question.model_validate(q).model_dump() for q in asks[0].args_as_dict()["questions"]]
        question = {"questions": asked, "tool_call_id": asks[0].tool_call_id}
    else:
        reply = result.output
    u = result.usage
    usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens,
             "output_tokens": u.output_tokens}
    return TurnOutcome(history_json=result.all_messages_json().decode("utf-8"), reply=reply, question=question,
                       plan=deps.plan, stem=deps.stem, usage=usage)
