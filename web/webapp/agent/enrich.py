"""Enrichment: what a listener's feedback on one workout teaches, as evidence for the engine's interests record.

One model request (a few with the writer's web search, to pin down a name), on the listener's own writer key,
returning a fixed shape: signals and a short summary. Nothing here writes a file or runs the engine: the worker
applies the signals through `./harmonicfitness interests add`, which checks them. The shape has no field for
health: pain stays in the feedback line, which the next check-in reads."""
import json
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, UsageLimits
from pydantic_ai.capabilities import NativeTool

MAX_SIGNALS = 12   # the engine's per_event_max: one feedback line grows the picture a little, not forty topics
LIMITS = UsageLimits(request_limit=6, tool_calls_limit=12)


class Signal(BaseModel):
    kind: Literal["topic", "venue", "taste", "movement", "effort"]
    name: str = Field(min_length=1, max_length=80)
    weight: float = Field(ge=-2, le=2)
    parent: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=160)


class Enrichment(BaseModel):
    signals: list[Signal] = Field(default_factory=list, max_length=MAX_SIGNALS)
    summary: str = Field(default="", max_length=400)


INSTRUCTIONS = """You keep a listener's interests for HarmonicFitness, a narrated workout made fresh each session. \
They just left feedback on one workout. Work out what it teaches, as evidence signals, and say it back in a line.

Signals (at most twelve; often one to four; none when the feedback teaches nothing):
- topic: a subject, person, team or kind of thing they like hearing about (a story they loved, a comedian, a \
cuisine). Name it as it would be followed ("Atsuko Okatsuka", "stand-up comedy", "Italian cooking"), and give a \
person or a narrow subject its broader topic as parent (a comedian's: stand-up comedy; a chef's: their cuisine).
- venue: a place whose shows they'd want to hear about.
- taste: a specific show, restaurant, book, album or place they enjoyed (for recommendations).
- movement: a movement from that workout they liked or didn't, by its name as the workout lists it.
- effort: name "effort": +1 too easy (sessions should be harder), -1 too hard, -2 far too hard.
Weight: 1 for a plain "liked" or a mention, 2 for strong words ("loved", "best ever"), -1 "not for me", -2 \
"never again". Tie "loved that story" to the topic of the story it means, from the stories told. Use web search \
only to pin down who or what a name is (one or two searches). Never a signal for anything under never, and \
nothing about pain, soreness or injury (the next check-in asks about those).

Summary: one or two short sentences to the listener, plain and warm, saying what you noted ("Noted: more \
stand-up, with Atsuko Okatsuka under it; goblet squats are a keeper; next sessions a little harder."). Empty \
when there's nothing to note."""

ENRICHER = Agent(output_type=Enrichment, instructions=INSTRUCTIONS, retries=1)


def prompt(facts: dict, feedback: str) -> str:
    """The workout, what it told, what's known, and the feedback, as the model's one message."""
    return ("The workout and what's known about the listener (JSON):\n" + json.dumps(facts, ensure_ascii=False)
            + "\n\nTheir new feedback on it:\n" + feedback)


def enrich(model, facts: dict, feedback: str, tools=()) -> Enrichment:
    """One enrichment; `tools` are the native tools the writer supports (its web search)."""
    result = ENRICHER.run_sync(prompt(facts, feedback), model=model, usage_limits=LIMITS,
                               capabilities=[NativeTool(t) for t in tools])
    return result.output


def signal_args(signals: list[Signal]) -> list[str]:
    """`--signal "kind | name | weight | parent | note"` arguments for `interests add`, a stray | made a slash."""
    def clean(x: str | None) -> str:
        return " ".join(str(x or "").replace("|", "/").split())
    out = []
    for s in signals[:MAX_SIGNALS]:
        if s.weight == 0 or not clean(s.name):
            continue
        out += ["--signal", f"{s.kind} | {clean(s.name)} | {s.weight:g} | {clean(s.parent)} | {clean(s.note)}"]
    return out
