"""The writers' room for one script, the site's way since 0.51.0 (HARMONICFITNESS_WRITERS=one has the agent write it),
divided as a show's team divides it since 0.55.0. The agent plans the session (the skeleton: every segment's seconds,
counts, holds and reps, and an empty [story] [/story] in each steady timed set that carries a piece). Then, side by
side, a researcher finds what the steady work and the rests carry, from the listener's topics, the day's sheets and
its own searches (started as the brief is saved), and returns notes, not the telling; and a trainer turns the brief
and the movements' notes into each segment's notes for the host, the must-say lines marked. The host, the coach's
voice, writes every word from both, so the script is one person talking; the trainer's review then checks it with
the build's check, safety first and the host's voice left alone. Each reads only its own material; code holds what
must hold (the clock, the silences, what was told, where each story goes)."""
import asyncio
import functools
import os
import re
import time
from dataclasses import replace

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import NativeToolCallPart

from . import tools

HERE = os.path.dirname(os.path.abspath(__file__))
STORY_SHARE = 0.7      # of a rest's words, about the story's: a rest whose share is under SMALLEST_STORY carries none
WORK_STORY_SHARE = 0.55   # of a steady timed set's: its setup, go, first cue, time checks and finish take the rest
SMALLEST_STORY = 40
# The fewest words a story slot leaves its coaching: a breath, the self-check where one falls and what's next (or a
# set's setup, go and time checks) took about this many wherever they went, so a short rest's 30 percent was written
# 80 percent over (0.59.0's bench, 2026-11-03); the story gives way to it rather than the segment running long, down
# to SMALLEST_STORY: a session of thirty-second rests with the floor in full carried no story at all.
COACHING_FLOOR = 60
STORY_WORDS = 140      # what a story is asked to run to, before the skeleton says how long each rest is
# Gemini's coach wrote 9 to 23 percent over the words it was asked for (0.50.3's loop), and paragraph breaks add
# time of their own: it's asked for this share of each segment's words (all of them where a bare [hold] keeps the
# segment its length, since a word short there is a second of silence)
COACH_AIM = 0.85
SILENCE = 8.0          # draft.MAX_SILENCE: a fixed hold or pause past it is refused, so the coach talks through it
PLACE = re.compile(r"[ \t]*\[story\]\s*\[/story\]", re.IGNORECASE)   # a skeleton's mark for a piece told during the work
STORY_REST = re.compile(r"\b(rest|transition|recover\w*)\b", re.IGNORECASE)
NOT_STORY = re.compile(r"\b(welcome|close|cool[- ]?down|warm[- ]?up)\b", re.IGNORECASE)
ROW = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+?)\s*$", re.MULTILINE)
SEGMENT = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*?)\s*$")
TIMED = re.compile(r"\[(?:hold|pause) (\d+(?:\.\d+)?)s\]")
TOLD = re.compile(r"^- (?:\d{4}-\d{2}-\d{2} )?[^/\n]+/ [a-z_]+: (.+)$", re.MULTILINE)
STOCK = re.compile(r"\((/[^,()]+\.md), slug [\w-]+\)")
COMMAND = re.compile(r"\s*\([^()]*`\./harmonicfitness[^`]*`[^()]*\)")
# a passage the engine's files mark for a computer only: the web's copy leaves it out
NOT_WEB = re.compile(r"<!-- web: skip -->\n.*?<!-- web: end -->\n?", re.DOTALL)
LEVELS = ("HIGH", "MEDIUM", "LOW")
# The longest each writer's call is waited for before it's asked again thinking less: Gemini's own deadline (504) is
# about 180 s, and a call that thinks that long is rare but whole (a final writer's 179 s against its usual 26 to 37, before 0.55.0's review).
PATIENCE = {"research": 160, "trainer": 110, "host": 150, "review": 80, "top-up": 90}
# How hard each writer thinks. The review is a checklist, and at MEDIUM its first pass ran past its patience in four
# of six timed 10-minute runs (2026-11-02), each time asked again at LOW, which answered in about ten seconds: the
# turn waited 80 s for nothing. The trainer stays at MEDIUM: at LOW it dropped the self-check a limit adds. The
# researcher thinks at LOW (0.58.0): at MEDIUM it took 78 to 160 s, ran past its patience in five of fifteen timed
# 15-minute runs and held the room up a median 110 s; at LOW it took 17 to 27 s, with six sourced stories every run.
# The host stays at MEDIUM: at LOW its scripts ran long, with silences.
LEVEL = {"research": "LOW", "trainer": "MEDIUM", "host": "MEDIUM", "review": "LOW"}


def web_copy(text: str) -> str:
    """A skill or knowledge file as the web gives it: without its computer-only passages."""
    return NOT_WEB.sub("", text)


class Note(BaseModel):
    number: int = Field(description="the segment's number in the plan")
    notes: str = Field(description="the trainer's notes for the host, short plain lines, never the lines themselves; "
                                   "each line the listener must hear word for word starting SAY EXACTLY:, and each "
                                   "to keep every part of starting SAY, EVERY PART KEPT:")


class Notes(BaseModel):
    segments: list[Note]


class Told(BaseModel):
    number: int = Field(description="its number, from 1, in the order told")
    topic: str = Field(description="its topic as the plan names it, or - for none")
    format: str = Field(description="its format's id in the plan")
    title: str = Field(description="a short title, for the log")
    source: str = Field(description="a link, or the sheet it came from")
    text: str = Field(description="the notes the host tells it from, as short lines: why it's theirs, the facts "
                                  "(names, numbers, dates and quotes exactly as the source gives them), and the "
                                  "point it lands on; never the telling")
    lands: str = Field(default="rest", description="steady if it's easy to follow while moving (a story's beat, a "
                                                   "profile, an explainer), rest if it needs a moment (a quiz asked or "
                                                   "answered, a myth checked, a quick hit)")


class Stories(BaseModel):
    stories: list[Told]


class Edited(BaseModel):
    number: int = Field(description="the segment's number")
    text: str = Field(description="the whole segment as it should read, its markers and [story] tags in place, "
                                  "without its @@ line")


class Edits(BaseModel):
    segments: list[Edited]


RESEARCHER = Agent(output_type=Stories, retries=2)
TRAINER = Agent(output_type=Notes, retries=2)
HOST = Agent(output_type=Edits, retries=2)
REVIEW = Agent(output_type=Edits, retries=2)


class NotReady(Exception):
    """write_script can't run on this draft yet: the message says what to do first."""


def sections(text: str) -> dict[str, str]:
    """A Markdown file's `## ` sections, by heading."""
    out = {}
    for part in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        head, _, body = part.partition("\n")
        out[head.strip()] = body.strip()
    return out


def bullets(section: str, *titles: str) -> str:
    """The bullets of `section` whose bold title starts with one of `titles`, in that order."""
    found = []
    for title in titles:
        m = re.search(rf"^- \*\*{re.escape(title)}.*?(?=^- \*\*|\Z)", section, re.MULTILINE | re.DOTALL)
        if not m:   # a bullet renamed in script.md would drop out of a writer's prompt unnoticed
            raise ValueError(f"no bullet titled {title!r} in the guide")
        found.append(m.group(0).strip())
    return "\n".join(found)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


@functools.lru_cache(maxsize=4)
def guides(engine_root: str) -> dict[str, str]:
    """Each writer's instructions: its short task (beside this file), then the parts of script.md and tts-rules.md it
    writes by, so the guidance lives in one place."""
    script = sections(web_copy(_read(os.path.join(engine_root, "knowledge", "script.md"))))
    tts = sections(web_copy(_read(os.path.join(engine_root, "knowledge", "tts-rules.md"))))
    safety, done, engaged = script["Safety: the rules"], script["Getting the workout done"], script["Keeping them engaged"]

    def voice(*heads):
        return "\n\n# What a voice can read\n\n" + "\n\n".join(f"## {h}\n{tts[h]}" for h in heads if h in tts)

    def task(name):
        return _read(os.path.join(HERE, name)).strip()
    said = ("Characters", "Numbers and abbreviations", "Words that trip a voice")
    out = {
        "research": task("researcher.md") + "\n\n## What makes a good piece\n" + bullets(
            engaged, "Tell it the way a friend would", "Where stories go", "Their taste counts", "Time-proof it",
            "Weave threads") + "\n" + bullets(safety, "Never invent facts"),
        "trainer": task("trainer.md") + f"\n\n## Safety: the rules\n{safety}\n\n## Getting the workout done\n{done}"
                   "\n\n## The shape\n" + bullets(engaged, "Where stories go", "A shape"),
        "host": task("host.md") + f"\n\n## Getting the workout done\n{done}\n\n## Keeping them engaged\n{engaged}"
                + "\n" + bullets(safety, "Never invent facts") + voice(*(h for h in tts if h != "The draft")),
        "review": task("review.md") + f"\n\n## Safety: the rules\n{safety}" + voice(*said, "Markers"),
    }
    out["top-up"] = out["research"]
    return {k: COMMAND.sub("", v) for k, v in out.items()}


def budgets(report: str) -> dict[int, int]:
    """A lint report's word budgets (a skeleton's) by segment number."""
    return {int(m.group(1)): int(m.group(3)) for m in ROW.finditer(report)}


def split(text: str) -> tuple[list[str], list[tuple[str, str, int, list[str]]]]:
    """A draft as (its lines before the first segment, its segments as (the @@ line, label, seconds, body lines))."""
    head, segs = [], []
    for line in text.split("\n"):
        m = SEGMENT.match(line)
        if m:
            segs.append((line, m.group(2), int(m.group(1)), []))
        elif segs:
            segs[-1][3].append(line)
        else:
            head.append(line)
    return head, segs


def steady(segs: list) -> set[int]:
    """The segments the skeleton marks for a piece told during the work (an empty [story] [/story])."""
    return {n for n, (_, _, _, body) in enumerate(segs, 1) if PLACE.search("\n".join(body))}


def slots(segs: list, budget: dict[int, int]) -> dict[int, tuple[int, int]]:
    """The segments that carry a story: the rests, and the steady timed sets the skeleton marks, by number, as (the
    coach's words, the story's)."""
    out, marked = {}, steady(segs)
    for n, (_, label, _, _) in enumerate(segs, 1):
        if n not in marked and (n in (1, len(segs)) or not STORY_REST.search(label) or NOT_STORY.search(label)):
            continue
        whole = budget.get(n, 0)
        story = round(whole * (WORK_STORY_SHARE if n in marked else STORY_SHARE))
        if whole - story < COACHING_FLOOR:   # the coaching's floor, as far as a short story still fits
            story = max(whole - COACHING_FLOOR, min(story, SMALLEST_STORY))
        if story >= SMALLEST_STORY:
            out[n] = (whole - story, story)
    return out


def coach_brief(brief: str, ids: list[str]) -> str:
    """The brief as the trainer needs it: all but the safe menu, whose entries it keeps only for the plan's
    movements, and only the Counts and Voice lines of Writing it."""
    parts, menu = [], ""
    for head, body in sections(brief).items():
        if head == "Safe menu":
            body = _menu_entries(body, ids)
            menu = " ".join(ln.split("; ")[1] for ln in body.split("\n") if ln.startswith("- **") and ln.count("; ") > 1).lower()
        elif head == "Equipment notes":   # the kit's own note, and those for equipment the plan uses
            notes = [p for p in re.split(r"\n(?=\*\*)", body) if p.strip()]
            body = "\n".join(p for i, p in enumerate(notes) if i == 0 or any(
                w.rstrip("s") in menu for w in re.findall(r"[a-z]{4,}", p.split("**")[1].lower() if "**" in p else "")))
        elif head == "Writing it":
            body = "\n".join(ln for ln in body.split("\n") if ln.startswith(("- Counts:", "- Voice:")))
        parts.append(f"## {head}\n{body}")
    return brief.split("\n## ", 1)[0].strip() + "\n\n" + "\n\n".join(parts)


def _menu_entries(menu: str, ids: list[str]) -> str:
    keep, group, entry, side_note = [], "", [], ""
    lines = menu.split("\n")

    def flush():
        if entry and any(f"(`{i}`)" in entry[0] for i in ids):
            keep.extend(entry)
    for i, ln in enumerate(lines):
        if ln.startswith("### "):
            flush()
            entry = []
            group = ln[4:].strip()
            if group == "Healthy side only" and i + 1 < len(lines) and not lines[i + 1].startswith("- "):
                side_note = lines[i + 1]
        elif ln.startswith("- **"):
            flush()
            entry = [ln + (" (healthy side only)" if group == "Healthy side only" else "")]
        elif ln.startswith("  ") and entry:
            entry.append(ln)
        elif "LIGHT ONLY" in ln and not entry:
            keep.insert(0, ln)
    flush()
    return "\n".join(keep + ([side_note] if side_note and any("healthy side only" in k for k in keep) else []))


def _section(sheet: str, start: str) -> str:
    m = re.search(rf"^## {re.escape(start)}.*?(?=^## |\Z)", sheet, re.MULTILINE | re.DOTALL)
    return m.group(0).strip() if m else ""


def told_titles(plan: str) -> list[str]:
    """The titles the content plan lists as told today and in the last thirty days."""
    return list(dict.fromkeys(m.group(1).strip() for m in TOLD.finditer(plan)))


STOP = set("the a an and of to in on for with at from by is was are be its it this that their his her new how what "
           "after into over just more than about".split())


def _key(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 3 and w not in STOP}


def retold(story: Told, titles: list[str]) -> str | None:
    """The told title a story repeats (most of its words in the story's title and opening), or None."""
    mine = _key(story.title + " " + " ".join(story.text.split()[:40]))
    for title in titles:
        key = _key(title)
        if key and len(key & mine) >= max(2, 0.6 * len(key)):
            return title
    return None


def open_holds(skeleton: str, limit: float = SILENCE) -> tuple[str, dict[int, float]]:
    """The skeleton with each fixed hold or pause over `limit` seconds taken out, and those seconds by segment: the
    coach talks through them instead (a skeleton's set of "go", forty seconds of hold, "rest" was kept as written
    and the whole draft rewritten after, in 0.50.3's loop)."""
    freed: dict[int, float] = {}
    out, n = [], 0
    for line in skeleton.split("\n"):
        if SEGMENT.match(line):
            n += 1
        elif n:
            def drop(m):
                if float(m.group(1)) <= limit:
                    return m.group(0)
                freed[n] = freed.get(n, 0) + float(m.group(1))
                return ""
            line = TIMED.sub(drop, line)
            if not line.strip() and freed.get(n):
                continue
        out.append(line)
    return "\n".join(out), freed


def words_a_second(segs: list, budget: dict) -> float:
    """The coach's pace, from the budgets of the segments that hold no markers."""
    plain = [(n, s) for n, (_, _, s, body) in enumerate(segs, 1) if not tools.MARK.search("\n".join(body))]
    seconds = sum(s for _, s in plain)
    return sum(budget.get(n, 0) for n, _ in plain) / seconds if seconds else 2.5


def pieces_for(minutes: int) -> int:
    """How many stories to ask for before the skeleton exists: a 30-minute session has had 11 or 12 rests."""
    return max(2, round(minutes / 2.6))


def asked(n: int, body: list[str], budget: dict) -> int:
    """The words the host is asked for in segment `n`: a share of its budget, since the host writes long (all of
    them where a bare [hold] keeps the segment its length, since a word short there is a second of silence)."""
    return round(budget.get(n, 0) * (1 if "[hold]" in "\n".join(body) else COACH_AIM))


def shares(n: int, words: int, budget: dict, rests: dict) -> tuple[int, int]:
    """A story slot's words as (the coaching's, the story's), in proportion to the slot's budget."""
    story = round(words * rests[n][1] / budget[n]) if budget.get(n) else 0
    return words - story, story


def place(told: list, rests: dict, marked: set) -> dict:
    """The stories by slot, in the order told: each slot takes the first story left that suits it (steady work or a
    rest), else the next one, so a quiz isn't told mid-set while a story waits for a rest."""
    left, out = list(told), {}
    for n in sorted(rests):
        if not left:
            break
        kind = "steady" if n in marked else "rest"
        pick = next((s for s in left if s.lands.strip().lower() == kind), left[0])
        left.remove(pick)
        out[n] = pick
    return out


def _plan_table(segs: list, budget: dict, rests: dict, marked: frozenset = frozenset()) -> str:
    """The plan as the trainer reads it: each segment's time, label, words and markers, and where a story goes and
    how many of the words are left for the coaching around it (0.59.0: without the words, notes ran as long as the
    segment, and the host wrote about as many words as the notes held)."""
    rows, at = [], 0
    for n, (_, label, secs, body) in enumerate(segs, 1):
        marks = " ".join(m for m in tools.MARK.findall("\n".join(body))
                         if m.lower() not in ("[story]", "[/story]")) or "none"
        words = asked(n, body, budget)
        size = f" About {words} words."
        if n in rests:
            coaching, story = shares(n, words, budget, rests)
            size = (f" About {words} words: {story} for a story, told "
                    + ("during the set, after its first cue" if n in marked else "in the rest")
                    + f", and {coaching} for the coaching around it.")
        rows.append(f"#{n} at {at // 60}:{at % 60:02d}, {secs} s, {label}.{size} Markers: {marks}.")
        at += secs
    return "\n".join(rows)


def host_plan(segs: list, budget: dict, notes: dict[int, str], placed: dict, marked: frozenset = frozenset(),
              rests: dict | None = None) -> str:
    """The plan as the host reads it: each segment's time, label, words and markers, the trainer's notes, and the
    story told there, as the researcher's notes, with its share of the words (`rests`: slots' (coach, story) words),
    so a story is told whole rather than summed up and the rest padded with breathing lines."""
    out, at = [], 0
    for n, (_, label, secs, body) in enumerate(segs, 1):
        marks = " ".join(m for m in tools.MARK.findall("\n".join(body))
                         if m.lower() not in ("[story]", "[/story]")) or "none"
        words = asked(n, body, budget)
        story = placed.get(n)
        share = ""
        if story is not None and rests and n in rests and budget.get(n):
            coaching, told = shares(n, words, budget, rests)
            share = (f" About {told} of them are the story, told whole with its detail, and about {coaching} the "
                     "coaching around it (the trainer's notes for it), nothing more.")
        elif story is None and (n in marked or (rests is not None and n in rests)
                                or (1 < n < len(segs) and STORY_REST.search(label))):
            share = (" No story here: the coaching from the trainer's notes fills it, and nothing from outside "
                     "them. The label names the segment; it's never a story to tell.")
        part = [f"## #{n} at {at // 60}:{at % 60:02d}, {secs} s, {label}",
                f"Write about {words} words.{share} Markers, in order: {marks}.",
                "Trainer's notes:\n" + (notes.get(n, "").strip() or "none")]
        if story is not None:
            part.append(f"Tell this story here ({'during the set, after the first cue' if n in marked else 'in the rest'}"
                        f"; {story.format}, {story.topic}):\n{story.text.strip()}")
        out.append("\n".join(part))
        at += secs
    return "\n\n".join(out)


def _home_text(deps, rel: str) -> str:
    """A file of the listener's, without its +++ settings block (the tools' settings, not the writer's)."""
    try:
        text = _read(os.path.join(deps.home, rel))
    except OSError:
        return ""
    return text.split("+++", 2)[2] if text.startswith("+++") and text.count("+++") >= 2 else text


def _stock(deps, plan: str) -> str:
    home = os.path.realpath(deps.home)
    out = []
    for path in STOCK.findall(plan):
        real = os.path.realpath(path)
        if real.startswith(home + os.sep):
            try:
                out.append(f"### {os.path.basename(path)}\n{_read(real).strip()}")
            except OSError:
                pass
    return "\n\n".join(out)


def logline(deps, text: str) -> None:
    """A line for the worker's log: what the room did and how long it took, never what it read or wrote."""
    if getattr(deps, "log", None) is not None:
        try:
            deps.log("room " + text)
        except Exception:  # noqa: BLE001 - a log line never fails the turn
            pass


def _tokens(result) -> tuple[int, int]:
    """The tokens in and out of one writer's run (its own requests, not the turn's)."""
    got_in = got_out = 0
    for m in result.new_messages():
        u = getattr(m, "usage", None)
        if u is not None:
            got_in += u.input_tokens or 0
            got_out += u.output_tokens or 0
    return got_in, got_out


def _thinking(model, level: str) -> dict | None:
    return {"google_thinking_config": {"thinking_level": level}} if type(model).__name__ == "GoogleModel" else None


async def _ask(deps, who: str, agent: Agent, model, prompt: str, usage, level: str, capabilities=(), history=None):
    """One writer's call; cut off by Gemini's own deadline (504, thinking too long), it's
    asked again a level lower, as it is when it runs past its PATIENCE."""
    lower = LEVELS[LEVELS.index(level) + 1:] if level in LEVELS else ()
    began = time.monotonic()
    try:
        result = await asyncio.wait_for(
            agent.run(prompt, model=model, instructions=guides(deps.engine_root)[who],
                      model_settings=_thinking(model, level), usage=usage, capabilities=list(capabilities),
                      message_history=history),
            timeout=PATIENCE.get(who) if lower else None)
    except (ModelHTTPError, asyncio.TimeoutError) as e:
        if isinstance(e, ModelHTTPError) and e.status_code != 504 or not lower:
            logline(deps, f"{who} {level} failed {time.monotonic() - began:.1f}s ({type(e).__name__})")
            raise
        logline(deps, f"{who} {level} gave up {time.monotonic() - began:.1f}s "
                   f"({'504' if isinstance(e, ModelHTTPError) else 'past its patience'}), asked again at {lower[0]}")
        return await _ask(deps, who, agent, model, prompt, usage, lower[0], capabilities, history)
    found = sum(isinstance(p, NativeToolCallPart) for m in result.new_messages() for p in m.parts)
    deps.room_searches += found
    got_in, got_out = _tokens(result)
    logline(deps, f"{who} {level} {time.monotonic() - began:.1f}s, {got_in} tokens in, {got_out} out"
               + (f", {found} web searches" if found else ""))
    return result


async def stories(deps, model, usage, draft: str, minutes: int, search=()) -> list[Told]:
    """The session's stories, in the order told. Started as the brief is saved, it needs nothing from the skeleton,
    so it runs while the agent plans; an item told before is written again, once."""
    full, _ = tools._mine(deps, draft)
    brief = _read(full[:-len(".draft.txt")] + ".brief.md") if full else ""
    plain = replace(deps, say=None)
    plan, feeds = await asyncio.gather(
        asyncio.to_thread(tools.run, plain, ["content", "plan", "--minutes", str(minutes)]),
        asyncio.to_thread(tools.run, plain, ["feeds"]))
    research = _home_text(deps, f"workouts/research/daily/{deps.today}.md")
    count = pieces_for(minutes)
    plan_text = re.sub(r"\n## Restock.*", "", plan.output, flags=re.DOTALL).strip()
    prompt = (f"Now: {deps.now}.\n\n{brief.split(chr(10) + '## ', 1)[0].strip()}\n\n{_section(brief, 'The listener')}\n\n"
              f"# Their profile\n\n{_home_text(deps, 'profile.md').strip()}\n\n# What they like\n\n"
              f"{_home_text(deps, 'content.md').strip()}\n\n# The content plan\n\n{plan_text}\n\n"
              + (f"# The stock\n\n{_stock(deps, plan.output)}\n\n" if STOCK.search(plan.output) else "")
              + (f"# Today's research sheet\n\n{research.strip()}\n\n" if research else "")
              + f"# Today's feeds sheet\n\n{(feeds.output if feeds.code == 0 else '').strip() or 'none today'}\n\n"
              f"# What to write\n\nThe session runs {minutes} minutes, with about {count} places for a piece: some during "
              f"steady timed work, while they move, and some in the rests. {count} pieces, each with notes enough for "
              f"about {STORY_WORDS} words once told (anywhere from {STORY_WORDS // 2} to {STORY_WORDS * 4 // 3}), each "
              "marked steady or rest by where it suits (the plan's formats say where each kind lands). The last two are spares, told only if "
              "there's room: nothing else depends on them.")
    told = await _ask(deps, "research", RESEARCHER, model, prompt, usage, LEVEL["research"], capabilities=search)
    deps.research_history = told.all_messages()   # what a top-up goes on from, once the skeleton's places are known
    found = {s.number: s for s in told.output.stories}
    titles = told_titles(plan.output)
    repeats = {n: t for n, s in found.items() if (t := retold(s, titles))}
    kept = without_retold(found, repeats, count)
    if kept is not None:
        logline(deps, f"research: {len(repeats)} told before, dropped for spares")
        return kept
    if repeats:
        logline(deps, f"research: {len(repeats)} told before, asked again")
        again = await _ask(deps, "research", RESEARCHER, model, (
            "Write these again, whole, each about another item, and return only these: "
            + "; ".join(f"story {n} retells \"{t}\", told before" for n, t in repeats.items()) + "."),
            usage, LEVEL["research"], capabilities=search, history=told.all_messages())
        found.update({s.number: s for s in again.output.stories if s.number in repeats})
        deps.research_history = again.all_messages()
    return [found[n] for n in sorted(found)]


async def top_up(deps, model, usage, got: list, places: int, titles: list[str], search=()) -> list:
    """More pieces when the skeleton has more places than the researcher wrote for (it wrote before the skeleton
    existed): the researcher goes on from its own run, while the trainer works. A place left without one gets
    coaching only, and the host is told so: a rest whose label named a topic got a story made up from the label
    alone (2026-11-02)."""
    short = places - len(got)
    history = getattr(deps, "research_history", None)
    if short <= 0 or not history:
        return got
    first = max((s.number for s in got), default=0) + 1
    try:
        more = await _ask(deps, "top-up", RESEARCHER, model, (
            f"The session has {places} places for a piece, {short} more than these. Write {short} more the same "
            f"way, numbered from {first}, each a different item from those above and nothing the plan lists as "
            "told; return only the new ones."), usage, LEVEL["research"], capabilities=search, history=history)
    except Exception:  # noqa: BLE001 - the places it would have filled get coaching only
        logline(deps, "top-up failed: those places get coaching only")
        return got
    new = [s for s in more.output.stories if not retold(s, titles)][:short]
    return got + [s.model_copy(update={"number": first + i}) for i, s in enumerate(new)]


def without_retold(found: dict, repeats: dict, count: int) -> list | None:
    """The stories without those told before, when what's left still fills all but the two spares asked for (so
    nothing waits on the researcher writing them again); None when there are repeats and too few would be left."""
    if not repeats:
        return None
    left = [found[n] for n in sorted(found) if n not in repeats]
    return left if len(left) >= max(1, count - 2) else None


SAY = re.compile(r"^\s*(?:[-*]\s*)?(SAY EXACTLY:|SAY, EVERY PART KEPT:)\s*(.+?)\s*$", re.MULTILINE)


def must_say(notes: dict[int, str]) -> str:
    """The trainer's must-say lines as the review's checklist, by segment: a line buried in its notes is the one a
    review passes over (a left knee became "the right side" through two reviews, 2026-11-02)."""
    how = {"SAY EXACTLY:": "word for word", "SAY, EVERY PART KEPT:": "every part kept"}
    return "\n".join(f"- #{n}, {how[kind]}: {line}"
                     for n, text in sorted(notes.items()) for kind, line in SAY.findall(text))


def numbered(text: str) -> str:
    """A draft with each @@ line numbered, as the lint numbers segments, for the trainer's review."""
    n = 0
    out = []
    for line in text.split("\n"):
        if SEGMENT.match(line):
            n += 1
            line = f"#{n} {line}"
        out.append(line)
    return "\n".join(out)


async def write(deps, model, usage, path: str, search=(), name: str | None = None,
                coach: str | None = None) -> tuple[str, str]:
    """The script's words for the skeleton at `path`: the researcher's notes (started with the brief, or now) and the
    trainer's beside them, the host's script from both, then the trainer's review, checked by the build `name` and
    `coach` write_script was given (else the stem's name and the brief's coach). (the draft, a note for the agent)."""
    full, rel = tools._mine(deps, path)
    if full is None:
        raise NotReady(rel)
    try:
        skeleton = _read(full)
    except OSError:
        raise NotReady("no such draft yet: write the skeleton with write_file first") from None
    if not tools.is_skeleton(skeleton):
        raise NotReady("write_script fills a skeleton (the @@ lines with their counts and holds, no words yet); this "
                       "draft has words: fix it with edit_segments")
    plain = replace(deps, say=None)
    name, coach = name or tools.build_name(path), coach or deps.brief_coach
    report = deps.reports.get(path)
    if report is None:
        if not (name and coach):
            raise NotReady("build the skeleton first (write_file with build_name and coach): its word budgets come next")
        began = time.monotonic()
        linted = await asyncio.to_thread(tools.run, plain, ["build", path, name, "--coach", coach, "--lint-only"])
        report = linted.output + "\n" + linted.error
        logline(deps, f"skeleton lint {time.monotonic() - began:.1f}s")
    budget = budgets(report)
    head, segs = split(skeleton)
    if len(budget) < len(segs):
        raise NotReady("the skeleton's word budgets couldn't be read; its lint said: " + report.strip()[:1500])
    try:
        brief = _read(full[:-len(".draft.txt")] + ".brief.md")
    except OSError:
        raise NotReady("no brief beside this draft: run brief with --save for it first") from None
    ids = [i.strip() for ln in head if ln.startswith("movements:") for i in ln.split(":", 1)[1].split(",") if i.strip()]
    rate = words_a_second(segs, budget)
    skeleton, freed = open_holds(skeleton)
    head, segs = split(skeleton)
    for n, secs in freed.items():   # a long hold's seconds become words: the coach talks them through
        budget[n] = budget.get(n, 0) + round(secs * rate)

    rests, marked = slots(segs, budget), steady(segs)
    began = time.monotonic()
    about, feeds = await asyncio.gather(asyncio.to_thread(tools.run, plain, ["movements", "--about", ",".join(ids)]),
                                        asyncio.to_thread(tools.run, plain, ["feeds"]))
    logline(deps, f"notes and feeds {time.monotonic() - began:.1f}s")
    weather = _section(feeds.output if feeds.code == 0 else "", "Weather") or "not known"
    trainer_prompt = (
        f"Now: {deps.now}.\n\n# The brief\n\n{coach_brief(brief, ids)}\n\n# The coaching notes\n\n"
        f"{about.output.strip()}\n\n# The plan\n\n{head[0] if head else ''}\n"
        f"{_plan_table(segs, budget, rests, frozenset(marked))}")

    async def the_stories() -> list[Told]:   # started as the brief was saved, or written now; topped up to the places
        job = deps.content_job if deps.content_job is not None and deps.content_for == path else None
        waited = time.monotonic()
        got = None
        if job is not None:
            ready = job.done()
            try:
                got = await asyncio.wrap_future(job)
                logline(deps, "research " + ("was ready" if ready else
                                          f"waited for {time.monotonic() - waited:.1f}s"))
            except Exception:  # noqa: BLE001 - the early run failed: write them now instead
                logline(deps, "research: the early run failed, written now")
        if got is None:
            got = await stories(deps, model, usage, path, max(1, round(sum(s for _, _, s, _ in segs) / 60)), search)
        if len(got) < len(rests):
            plan = await asyncio.to_thread(tools.run, plain, ["content", "plan", "--minutes",
                                                              str(max(1, round(sum(s for _, _, s, _ in segs) / 60)))])
            got = await top_up(deps, model, usage, got, len(rests), told_titles(plan.output), search)
        return got

    # the researcher's notes and the trainer's side by side, each from its own material
    told, noted = await asyncio.gather(the_stories(),
                                       _ask(deps, "trainer", TRAINER, model, trainer_prompt, usage, LEVEL["trainer"]))
    placed = place(told, rests, marked)   # in order, each to a slot it suits: the spares, last, go when there are fewer
    notes = {x.number: x.notes for x in noted.output.segments}

    # the host: every word, from both, as one person talking
    limits = _section(brief, "Today's limits")
    host_prompt = (
        f"Now: {deps.now}.\n\n{_section(brief, 'The listener')}\n\n{limits}\n\n# The weather\n\n{weather}\n\n"
        f"# The plan\n\nThis coach says about {rate:.1f} words a second, so each segment's words fill its seconds: a "
        f"hold or pause you add takes {rate:.1f} words a second from them.\n\n"
        f"{host_plan(segs, budget, notes, placed, frozenset(marked), rests)}")
    hosted = await _ask(deps, "host", HOST, model, host_prompt, usage, LEVEL["host"])
    edits, unasked = without_unasked(hosted.output.segments, placed)
    if unasked:
        logline(deps, f"host told {len(unasked)} stories nobody researched: taken out")
    draft = apply_edits(skeleton, edits)
    spoken = {e.number for e in edits}

    # the trainer's review: the script as the listener hears it, with the build's check and the trainer's notes;
    # once more if the check still finds something after it
    said = "\n\n".join(f"#{n}\n{t.strip()}" for n, t in sorted(notes.items()) if t.strip())
    must = must_say(notes)
    changed: set[int] = set()
    history = None
    for attempt in range(2):
        check = await _lint(deps, plain, path, full, name, coach, draft)
        if attempt and check.startswith("clean"):
            break
        draft = _read(full) if name and coach else draft
        prompt = (f"Now: {deps.now}.\n\n{_section(brief, 'The listener')}\n\n{limits}\n\n"
                  + (f"# The lines to check, one by one\n\n{must}\n\n" if must else "")
                  + ("# Taken out\n\n" + "\n".join(
                      f"- #{n} told a story the researcher didn't bring, and it was taken out: fill its time with "
                      "coaching from your notes, nothing from outside them." for n in unasked) + "\n\n"
                     if unasked else "")
                  + f"# Your notes\n\n{said}\n\n"
                  f"# The script\n\n{numbered(draft)}\n\n# The build's check\n\n{check}") if not attempt else (
                  f"The build's check after your edit:\n\n{check}\n\nFix what it names; return only those segments.")
        edited = await _ask(deps, "review", REVIEW, model, prompt, usage, LEVEL["review"], history=history)
        history = edited.all_messages()
        draft = apply_edits(draft, edited.output.segments)
        changed |= {e.number for e in edited.output.segments}

    logged = [f'--item "{s.topic} | {s.format} | {s.title} | {s.source}"' for _, s in sorted(placed.items())]
    note = (f"The writers' room wrote the words: the host told {len(placed)} stories in {len(rests)} places and wrote "
            f"{len(spoken)} of {len(segs)} segments from the trainer's notes, and the trainer's review changed "
            f"{len(changed)}. "
            + ("After recording, log what was told: `content log --draft <draft> " + " ".join(logged) + "`."
               if logged else ""))
    return draft, note


async def _lint(deps, plain, path: str, full: str, name: str | None, coach: str | None, draft: str) -> str:
    """The build's check of `draft` (written to `path` first): "clean" and its summary, or its issues."""
    if not (name and coach):
        return "not checked"
    began = time.monotonic()
    await asyncio.to_thread(tools.write_file, deps, path, draft)
    r = await asyncio.to_thread(tools.run, plain, ["build", path, name, "--coach", coach, "--lint-only"])
    out = (r.output + "\n" + r.error).strip()
    logline(deps, f"lint exit {r.code} {time.monotonic() - began:.1f}s")
    deps.linted = plain.linted   # a clean lint here: the build after the room prices this text without another
    return ("clean: " if r.code == 0 else "") + out


STORY = re.compile(r"[ \t]*\[story\](.*?)\[/story\][ \t]*\n?", re.IGNORECASE | re.DOTALL)


def without_unasked(edits: list[Edited], placed: dict) -> tuple[list[Edited], list[int]]:
    """The host's segments with any story told where none was placed taken out (a story from nowhere: no notes, so
    nothing it says was checked), and those segments' numbers, for the review to fill."""
    out, unasked = [], []
    for e in edits:
        if e.number not in placed and any(m.strip() for m in STORY.findall(e.text)):
            unasked.append(e.number)
            e = e.model_copy(update={"text": re.sub(r"\n{3,}", "\n\n", STORY.sub("", e.text)).strip()})
        out.append(e)
    return out, unasked


def apply_edits(draft: str, edits: list[Edited]) -> str:
    """The draft with the host's or the review's segments in place of its own, each under its own @@ line (the clock is the
    skeleton's: an edit can't change it)."""
    head, segs = split(draft)
    bodies = {e.number: e.text.strip("\n") for e in edits if 1 <= e.number <= len(segs)}
    out = list(head)
    for n, (at, _, _, body) in enumerate(segs, 1):
        text = bodies.get(n)
        if text is not None:   # an edit that wrote its own @@ line keeps the draft's
            text = "\n".join(ln for ln in text.split("\n") if not SEGMENT.match(ln.lstrip("#0123456789 ")))
        out += [at] + (text.split("\n") + [""] if text is not None else body)
    return "\n".join(out).rstrip("\n") + "\n"
