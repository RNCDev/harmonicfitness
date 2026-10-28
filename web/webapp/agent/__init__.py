"""The agent: one loop for every provider, over the typed engine tools, ask_user (a question that pauses
the turn for the user) and show_plan (the plan, shown only when every movement is on the brief's menu).
The model is passed per turn; nothing here knows which provider it is."""
import os
import tomllib
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import (Agent, CallDeferred, DeferredToolRequests, DeferredToolResults,
                         ModelMessagesTypeAdapter, ModelRetry, RunContext, UsageLimits)

from webapp import worker

from . import tools
from .tools import Deps, ToolResult

__all__ = ["AGENT", "Deps", "Option", "Plan", "PlanRow", "Question", "TurnOutcome", "LIMITS",
           "plan_problems", "run_turn"]

LIMITS = UsageLimits(request_limit=25, tool_calls_limit=40, total_tokens_limit=400_000)

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


@AGENT.tool
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


def plan_problems(deps: Deps, plan: Plan) -> list[str]:
    """What keeps this plan from being shown, as sentences (empty when it can be)."""
    if not deps.stem:
        return ["run brief first"]
    catalog, menu, errors, cat = _engine(deps)
    path = os.path.join(deps.home, "workouts", deps.stem, f"{deps.stem}.menu.json")
    try:
        found = menu.load(path)
    except errors.HarmonicFitnessError:   # a damaged menu is the brief's to remake
        found = None
    shape = menu.validate(found) if found is not None else ["there is no menu"]
    if shape:
        return ["the brief's menu can't be read (" + "; ".join(shape) + "): run brief again"]
    stale = menu.staleness(found, today=deps.today, health_path=os.path.join(deps.home, "health.md"))
    if stale:
        return ["the brief's menu doesn't stand for today: run brief again"]
    on_menu = {e["id"] for e in found["movements"]}
    problems = []
    for row in plan.rows:
        for name in row.movements:
            m = catalog.resolve(cat, name)
            if m is not None and m.id in on_menu:
                continue
            problems.append(f'"{name}" ({row.block}) isn\'t on today\'s menu; use a movement the brief lists')
    rows = sum(r.seconds for r in plan.rows)
    if rows != plan.total_seconds:
        problems.append(f"the rows add up to {rows} s, not total_seconds ({plan.total_seconds} s)")
    want = found["seconds"]
    if plan.total_seconds != want:
        problems.append(f"total_seconds is {plan.total_seconds} s, but the request is {want} s "
                        f"({want // 60} minutes)")
    return problems


@AGENT.tool(retries=2)
def show_plan(ctx: RunContext[Deps], plan: Plan) -> str:
    """Show the listener today's plan. Every movement must be on the brief's menu, and the rows' seconds
    must add up to total_seconds, which must be the request's minutes x 60."""
    problems = plan_problems(ctx.deps, plan)
    if problems:
        raise ModelRetry("The plan wasn't shown: " + " ".join(p if p.endswith(".") else p + "." for p in problems))
    ctx.deps.plan = plan.model_dump()
    return "shown"


# ---- a turn ------------------------------------------------------------------------------------

@dataclass
class TurnOutcome:
    history_json: str
    reply: str | None
    question: dict | None
    plan: dict | None
    stem: str | None
    usage: dict


def run_turn(model, deps: Deps, history_json: str | None, prompt: str | None,
             answer: tuple[str, dict] | None) -> TurnOutcome:
    """One run of the agent: the user's line (prompt) or the answer to the open question. UsageLimitExceeded
    and provider errors propagate; the caller decides what they mean."""
    history = ModelMessagesTypeAdapter.validate_json(history_json) if history_json else None
    results = DeferredToolResults(calls={answer[0]: answer[1]}) if answer else None
    result = AGENT.run_sync(prompt, model=model, deps=deps, message_history=history,
                            deferred_tool_results=results, usage_limits=LIMITS)
    reply = question = None
    if isinstance(result.output, DeferredToolRequests):
        asks = [c for c in result.output.calls if c.tool_name == "ask_user"]
        if asks:
            question = dict(asks[0].args_as_dict(), tool_call_id=asks[0].tool_call_id)
    else:
        reply = result.output
    u = result.usage
    usage = {"requests": u.requests, "tool_calls": u.tool_calls, "input_tokens": u.input_tokens,
             "output_tokens": u.output_tokens}
    return TurnOutcome(history_json=result.all_messages_json().decode("utf-8"), reply=reply, question=question,
                       plan=deps.plan, stem=deps.stem, usage=usage)
