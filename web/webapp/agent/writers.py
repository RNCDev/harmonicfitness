"""Two writers for one script, side by side: the eval loops' experiment (HARMONICFITNESS_WRITERS=two), not the site's
default. Once the agent has written the skeleton (the clock: every segment's seconds, counts and holds), a coach writer
writes the coaching from the brief and the movements' notes, and a story writer writes what the rests carry from the
listener's topics, the day's sheets and its own searches, each reading only its own material. Code lays both on the
skeleton: a rest is the coach's opener, the story in [story] ... [/story], then the coach's handback."""
import asyncio
import functools
import os
import re
import time
from dataclasses import replace

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelResponse, NativeToolCallPart, NativeToolReturnPart

from . import tools

HERE = os.path.dirname(os.path.abspath(__file__))
STORY_SHARE = 0.7      # of a rest's words, the story's; the coach's opener and handback have the rest
SMALLEST_STORY = 40    # a rest whose story would be shorter carries none: the coach fills it
LINE_WORDS = 25        # the story writer's welcome and close lines, out of those segments' words
# Gemini's coach wrote 9 to 23 percent over the words it was asked for (0.50.3's loop), and paragraph breaks add
# time of their own: it's asked for this share of each segment's words
COACH_AIM = 0.85
STORY_WORDS = 140      # what a story is asked to run to, before the skeleton says how long each rest is
STORY_REST = re.compile(r"\b(rest|transition|recover\w*)\b", re.IGNORECASE)
NOT_STORY = re.compile(r"\b(welcome|close|cool[- ]?down|warm[- ]?up)\b", re.IGNORECASE)
ROW = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+?)\s*$", re.MULTILINE)
SEGMENT = re.compile(r"^@@\s*(\d+)\s*\|\s*(.*?)\s*$")
TOLD = re.compile(r"^- (?:\d{4}-\d{2}-\d{2} )?[^/\n]+/ [a-z_]+: (.+)$", re.MULTILINE)
STOCK = re.compile(r"\((/[^,()]+\.md), slug [\w-]+\)")
COMMAND = re.compile(r"\s*\([^()]*`\./harmonicfitness[^`]*`[^()]*\)")
# a passage the engine's files mark for a computer only: the web's copy leaves it out
NOT_WEB = re.compile(r"<!-- web: skip -->\n.*?<!-- web: end -->\n?", re.DOTALL)


def web_copy(text: str) -> str:
    """A skill or knowledge file as the web gives it: without its computer-only passages."""
    return NOT_WEB.sub("", text)


class Written(BaseModel):
    number: int = Field(description="the segment's number in the plan")
    text: str = Field(description="the segment's words with its markers in place; for a rest that carries a story, "
                                  "its opener")
    handback: str = Field(default="", description="for a rest that carries a story, the words after it; else empty")


class Coaching(BaseModel):
    segments: list[Written]


class Told(BaseModel):
    rest: int = Field(description="its number, from 1, in the order told")
    topic: str = Field(description="its topic as the plan names it, or - for none")
    format: str = Field(description="its format's id in the plan")
    title: str = Field(description="a short title, for the log")
    source: str = Field(description="a link, or the sheet it came from")
    text: str = Field(description="the story as the coach says it: paragraphs of under fifty words, no markers")


class Stories(BaseModel):
    welcome: str = Field(default="", description="one or two sentences the welcome ends on")
    close: str = Field(default="", description="one or two sentences the close opens with")
    stories: list[Told]


COACH = Agent(output_type=Coaching, retries=2)
STORY = Agent(output_type=Stories, retries=2)


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
        if m:
            found.append(m.group(0).strip())
    return "\n".join(found)


def _for_writer(text: str) -> str:
    """A guide with its commands taken out: a writer runs none."""
    return COMMAND.sub("", text)


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


@functools.lru_cache(maxsize=4)
def guides(engine_root: str) -> tuple[str, str]:
    """(the coach writer's instructions, the story writer's): each writer's task, then the parts of script.md and
    tts-rules.md it writes by, so the guidance stays in one place."""
    script = sections(web_copy(_read(os.path.join(engine_root, "knowledge", "script.md"))))
    tts = sections(web_copy(_read(os.path.join(engine_root, "knowledge", "tts-rules.md"))))
    safety, done, engaged = script["Safety: the rules"], script["Getting the workout done"], script["Keeping them engaged"]
    voice = "\n\n".join(f"## {h}\n{tts[h]}" for h in tts if h != "The draft")
    coach = (_read(os.path.join(HERE, "coach-writer.md")).strip()
             + f"\n\n## Safety: the rules\n{safety}\n\n## Getting the workout done\n{done}\n\n## The voice and the shape\n"
             + bullets(engaged, "The coach's voice", "Time-proof it", "A shape") + f"\n\n# What a voice can read\n\n{voice}")
    said = "\n\n".join(f"## {h}\n{tts[h]}" for h in ("Characters", "Numbers and abbreviations",
                                                     "Words that trip a voice") if h in tts)
    story = (_read(os.path.join(HERE, "story-writer.md")).strip() + "\n\n## Telling it\n"
             + bullets(engaged, "The coach's voice", "A rest holds one story", "Their taste counts", "Time-proof it",
                       "Weave threads") + "\n" + bullets(safety, "Never invent facts")
             + f"\n\n# What a voice can read\n\n{said}")
    return _for_writer(coach), _for_writer(story)


def budgets(report: str) -> dict[int, int]:
    """A skeleton's lint report as each segment's word budget, by its number."""
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


def slots(segs: list, budget: dict[int, int]) -> dict[int, tuple[int, int]]:
    """The rests that carry a story: their numbers, as (the coach's words, the story's)."""
    out = {}
    for n, (_, label, _, _) in enumerate(segs, 1):
        if n in (1, len(segs)) or not STORY_REST.search(label) or NOT_STORY.search(label):
            continue
        whole = budget.get(n, 0)
        story = round(whole * STORY_SHARE)
        if story >= SMALLEST_STORY:
            out[n] = (whole - story, story)
    return out


def coach_brief(brief: str, ids: list[str]) -> str:
    """The brief as the coach writer needs it: all but the safe menu, whose entries it keeps only for the plan's
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


def _clean(text: str) -> list[str]:
    """A story's paragraphs, with any marker taken out (the build refuses one inside a story)."""
    text = tools.MARK.sub("", text)
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def story_block(text: str) -> str:
    paras = _clean(text)
    return "[story] " + "\n\n".join(paras) + " [/story]" if paras else ""


def assemble(skeleton: str, coaching: dict[int, Written], stories: dict[int, Told], welcome: str, close: str,
             rests: dict) -> str:
    """The skeleton with every segment's words: the coach's, and in each rest that carries one, the story between
    the coach's opener and handback; the welcome ends on the story writer's line and the close opens with one."""
    head, segs = split(skeleton)
    out = list(head)
    for n, (at, _, _, body) in enumerate(segs, 1):
        w = coaching.get(n)
        parts = [w.text.strip() if w and w.text.strip() else "\n".join(body).strip()]
        if n == len(segs) and close.strip():
            parts.insert(0, story_block(close))
        if n in rests and n in stories:
            parts.append(story_block(stories[n].text))
        if n in rests and w and w.handback.strip():
            parts.append(w.handback.strip())
        if n == 1 and welcome.strip():
            parts.append(story_block(welcome))
        out += [at, "\n\n".join(p for p in parts if p), ""]
    return "\n".join(out).rstrip("\n") + "\n"


def _thinking(model, level: str) -> dict | None:
    return {"google_thinking_config": {"thinking_level": level}} if type(model).__name__ == "GoogleModel" else None


async def _ask(deps, who: str, n: int, agent: Agent, model, instructions: str, prompt: str, usage, level: str,
               capabilities=(), history=None):
    start = time.monotonic()
    try:
        result = await agent.run(prompt, model=model, instructions=instructions, model_settings=_thinking(model, level),
                                 usage=usage, capabilities=list(capabilities), message_history=history)
    except ModelHTTPError as e:   # Gemini's own deadline (504): the call thought too long; once more, thinking less
        if e.status_code != 504 or level == "LOW":
            raise
        deps.tracks.append({"writer": who, "round": n, "seconds": round(time.monotonic() - start, 1),
                            "deadline": True})
        return await _ask(deps, who, n, agent, model, instructions, prompt, usage, "LOW", capabilities, history)
    new = result.new_messages()
    responses = [m for m in new if isinstance(m, ModelResponse)]
    deps.tracks.append({"writer": who, "round": n, "seconds": round(time.monotonic() - start, 1),
                        "requests": len(responses),
                        "input_tokens": sum(m.usage.input_tokens or 0 for m in responses),
                        "output_tokens": sum(m.usage.output_tokens or 0 for m in responses),
                        "searches": sum(isinstance(p, NativeToolCallPart) for m in new for p in m.parts),
                        # what the searches returned, so a judge can check a story's facts against them
                        "found": [str(p.content)[:6000] for m in new for p in m.parts if isinstance(p, NativeToolReturnPart)],
                        "output": result.output.model_dump()})
    return result


def pieces_for(minutes: int) -> int:
    """How many stories to ask for before the skeleton exists: a 30-minute session has had 11 or 12 rests."""
    return max(2, round(minutes / 2.6))


def _plan_table(segs: list, budget: dict, rests: dict, placed: dict, welcome: str, close: str) -> str:
    rows, at = [], 0
    for n, (_, label, secs, body) in enumerate(segs, 1):
        marks = " ".join(tools.MARK.findall("\n".join(body))) or "none"
        # a bare [hold] keeps the segment its full length, so a word short there is a second of silence
        whole = round(budget.get(n, 0) * (1 if "[hold]" in "\n".join(body) else COACH_AIM))
        if n in placed:
            story = placed[n]
            words = tools._words(story.text)
            say = (f"opener and handback, about {max(whole - words, 20)} words together, around this story "
                   f"({words} words), which code places between them: \"{' '.join(story.text.split())}\"")
        elif n == 1 and welcome.strip():
            say = f"about {max(whole - tools._words(welcome), 20)} words, ending on this line, which code adds: \"{welcome}\""
        elif n == len(segs) and close.strip():
            say = f"about {max(whole - tools._words(close), 20)} words, after this line, which code puts first: \"{close}\""
        else:
            say = f"about {whole} words"
        rows.append(f"#{n} at {at // 60}:{at % 60:02d}, {secs} s, {label}. Markers: {marks}. Write: {say}.")
        at += secs
    return "\n".join(rows)


def words_a_second(segs: list, budget: dict) -> float:
    """The coach's pace, from the skeleton's budgets for the segments that hold no markers."""
    seconds = sum(s for n, (_, _, s, body) in enumerate(segs, 1) if not tools.MARK.search("\n".join(body)))
    words = sum(budget.get(n, 0) for n, (_, _, _, body) in enumerate(segs, 1) if not tools.MARK.search("\n".join(body)))
    return words / seconds if seconds else 2.5


# A fixed hold or pause longer than the lint allows (draft.MAX_SILENCE) is refused: the skeleton's set of "go",
# forty seconds of hold, "rest" had the coach writer keep it and the whole draft rewritten after (0.50.3's loop).
SILENCE = 8.0
TIMED = re.compile(r"\[(?:hold|pause) (\d+(?:\.\d+)?)s\]")


def open_holds(skeleton: str, limit: float = SILENCE) -> tuple[str, dict[int, float]]:
    """The skeleton with each fixed hold or pause over `limit` seconds taken out, and those seconds by segment:
    the coach talks through them instead."""
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


def _rate(rate: float) -> str:
    return (f"This coach says about {rate:.1f} words a second, so each segment's words fill its seconds: a hold or "
            f"pause you add costs about {rate:.1f} words a second of it (a five-second hold, about {round(5 * rate)} "
            "words fewer).")


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


async def stories(deps, model, usage, draft: str, minutes: int, search=()) -> tuple[Stories, list[str]]:
    """The session's stories, written as soon as the brief is: (the stories in the order told, what the content
    plan lists as told). Started from the brief, it needs nothing from the skeleton, so it runs while the agent
    designs; an item told before is written again, once."""
    full, _ = tools._mine(deps, draft)
    brief = _read(full[:-len(".draft.txt")] + ".brief.md") if full else ""
    plain = replace(deps, say=None)
    plan, feeds = await asyncio.gather(
        asyncio.to_thread(tools.run, plain, ["content", "plan", "--minutes", str(minutes)]),
        asyncio.to_thread(tools.run, plain, ["feeds"]))
    sheet = feeds.output if feeds.code == 0 else ""
    research = _home_text(deps, f"workouts/research/daily/{deps.today}.md")
    count = pieces_for(minutes)
    plan_text = re.sub(r"\n## Restock.*", "", plan.output, flags=re.DOTALL).strip()
    common = (f"Now: {deps.now}.\n\n{brief.split(chr(10) + '## ', 1)[0].strip()}\n\n{_section(brief, 'The listener')}\n\n"
              f"# Their profile\n\n{_home_text(deps, 'profile.md').strip()}\n\n# What they like\n\n"
              f"{_home_text(deps, 'content.md').strip()}\n\n# The content plan\n\n"
              f"{plan_text}\n\n"
              + (f"# The stock\n\n{_stock(deps, plan.output)}\n\n" if STOCK.search(plan.output) else "")
              + (f"# Today's research sheet\n\n{research.strip()}\n\n" if research else "")
              + f"# Today's feeds sheet\n\n{sheet.strip() or 'none today'}\n\n# Your part\n\n")
    guide = guides(deps.engine_root)[1]
    titles = told_titles(plan.output)
    parts = split_topics(plan.output, count)

    async def part(i: int, first: int, last: int, topics: list[str]):
        ask = (f"The session runs {minutes} minutes, with about {count} rests. {len(parts)} writers share them, each "
               f"its own topics, so no item is told twice. You write stories {first} to {last}, numbered so, in the "
               f"order they're told, about {STORY_WORDS} words each (anywhere from {STORY_WORDS // 2} to "
               f"{STORY_WORDS * 4 // 3}), only on " + "; ".join(topics) + ". "
               + ("Write the welcome line too; leave the close empty. " if i == 0 else
                  "Write the close line too; leave the welcome empty. " if i == len(parts) - 1 else
                  "Leave the welcome and close empty. ")
               + ("The last two are spares, told only if the session has room: nothing earlier depends on them."
                  if i == len(parts) - 1 else ""))
        told = await _ask(deps, "story", i + 1, STORY, model, guide, common + ask, usage, "MEDIUM", capabilities=search)
        found = {s.rest: s for s in told.output.stories if first <= s.rest <= last}
        repeats = {n: t for n, s in found.items() if (t := retold(s, titles))}
        if repeats:
            again = await _ask(deps, "story", i + 1, STORY, model, guide, (
                "Write these stories again, whole, each about another item on your topics, and return only these "
                "(welcome and close empty): " + "; ".join(f"story {n} retells \"{t}\", told before"
                                                          for n, t in repeats.items()) + "."),
                usage, "MEDIUM", capabilities=search, history=told.all_messages())
            found.update({s.rest: s for s in again.output.stories if s.rest in repeats})
        return told.output, found

    done = await asyncio.gather(*(part(i, *p) for i, p in enumerate(parts)))
    found = {n: s for _, f in done for n, s in f.items()}
    out = Stories(welcome=done[0][0].welcome, close=done[-1][0].close, stories=[found[n] for n in sorted(found)])
    return out, titles


TOPIC = re.compile(r"^- ([^:\n(]+?)(?: \(spare\))?:", re.MULTILINE)
PARTS = 3   # story writers side by side: one call writing a dozen stories thought for 80 to 150 s


def split_topics(plan: str, count: int, parts: int = PARTS) -> list[tuple[int, int, list[str]]]:
    """The stories shared out among `parts` writers: each one's (first, last, topics). The content plan's topics due
    go round in turn, the second writer adds what's on near them and the last a recommendation from their Taste, so
    no two writers can tell the same item."""
    due = plan.split("## Topics due", 1)[1].split("\n## ", 1)[0] if "## Topics due" in plan else ""
    topics = [m.group(1).strip() for m in TOPIC.finditer(due)]
    parts = max(1, min(parts, count // 2, len(topics) or 1))
    shares = [topics[i::parts] for i in range(parts)]
    if parts > 1:
        shares[1 % parts].append("what's on at their venues or near them (as the plan's What's on says)")
        shares[-1].append("a recommendation in the spirit of their Taste")
    out, start = [], 1
    for i in range(parts):
        size = count // parts + (1 if i < count % parts else 0)
        out.append((start, start + size - 1, shares[i] or ["any of the plan's topics"]))
        start += size
    return out


async def write(deps, model, usage, path: str, search=()) -> tuple[str, str]:
    """The script's words for the skeleton at `path`: the stories (started with the brief, or now), then the
    coaching written around them. (the draft, a note for the agent)."""
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
    report = deps.reports.get(path)
    if report is None:
        name, coach = tools.build_name(path), deps.brief_coach
        if not (name and coach):
            raise NotReady("build the skeleton first (write_file with build_name and coach): its word budgets come next")
        linted = await asyncio.to_thread(tools.run, plain, ["build", path, name, "--coach", coach, "--lint-only"])
        report = linted.output + "\n" + linted.error
    budget = budgets(report)
    head, segs = split(skeleton)
    if len(budget) < len(segs):
        raise NotReady("the skeleton's word budgets couldn't be read; its lint said: " + report.strip()[:1500])
    stem = full[:-len(".draft.txt")]
    try:
        brief = _read(stem + ".brief.md")
    except OSError:
        raise NotReady("no brief beside this draft: run brief with --save for it first") from None
    ids = [i.strip() for ln in head if ln.startswith("movements:") for i in ln.split(":", 1)[1].split(",") if i.strip()]
    seconds = sum(s for _, _, s, _ in segs)
    job = deps.story_job if deps.story_job is not None and deps.story_for == path else None
    told = None
    if job is not None:
        try:
            told = await asyncio.wrap_future(job)
        except Exception:  # noqa: BLE001 - the early run failed: write them now instead
            told = None
    about, feeds, told = await asyncio.gather(
        asyncio.to_thread(tools.run, plain, ["movements", "--about", ",".join(ids)]),
        asyncio.to_thread(tools.run, plain, ["feeds"]),
        _done(told) if told else stories(deps, model, usage, path, max(1, round(seconds / 60)), search))
    found, _ = told
    rate = words_a_second(segs, budget)
    skeleton, freed = open_holds(skeleton)
    head, segs = split(skeleton)
    for n, secs in freed.items():   # a long hold's seconds become words: the coach talks the listener through them
        budget[n] = budget.get(n, 0) + round(secs * rate)
    rests = slots(segs, budget)
    placed = dict(zip(sorted(rests), found.stories))   # in order: the spares, last, go when there are fewer rests
    welcome, close = found.welcome, found.close
    sheet = feeds.output if feeds.code == 0 else ""
    prompt = (f"Now: {deps.now}.\n\n# The brief\n\n{coach_brief(brief, ids)}\n\n# The coaching notes\n\n"
              f"{about.output.strip()}\n\n# The weather\n\n{_section(sheet, 'Weather') or 'not known'}\n\n"
              f"# The plan\n\n{_rate(rate)}\n\n{head[0] if head else ''}\n"
              f"{_plan_table(segs, budget, rests, placed, welcome, close)}")
    coached = await _ask(deps, "coach", 1, COACH, model, guides(deps.engine_root)[0], prompt, usage, "MEDIUM")
    coaching = {w.number: w for w in coached.output.segments}
    draft = assemble(skeleton, coaching, placed, welcome, close, set(placed))
    logged = [f'--item "{s.topic} | {s.format} | {s.title} | {s.source}"' for _, s in sorted(placed.items())]
    note = (f"Two writers wrote the words: the coaching for {len(coaching)} of {len(segs)} segments, and "
            f"{len(placed)} stories in {len(rests)} rests. "
            + ("After recording, log what was told: `content log --draft <draft> " + " ".join(logged) + "`."
               if logged else ""))
    return draft, note


async def _done(value):
    return value
