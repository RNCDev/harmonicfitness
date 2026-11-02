"""Three writers for one script, the site's way since 0.51.0 (HARMONICFITNESS_WRITERS=one has the agent write it).
The agent plans the session (the skeleton: every segment's seconds, counts and holds). Then a personal content writer writes
what the rests carry, from the listener's topics, the day's sheets and its own searches (started as the brief is
saved); a coach writer writes the coaching from the brief and the movements' notes, each rest's around a story of
known length; and a final script writer reads the assembled script with the build's check and makes it one coach talking to one
person. Each reads only its own material; code holds what must hold (the clock, the silences, what was told)."""
import asyncio
import functools
import os
import re
from dataclasses import replace

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

from . import tools

HERE = os.path.dirname(os.path.abspath(__file__))
STORY_SHARE = 0.7      # of a rest's words, about the story's: a rest whose share is under SMALLEST_STORY carries none
SMALLEST_STORY = 40
STORY_WORDS = 140      # what a story is asked to run to, before the skeleton says how long each rest is
# Gemini's coach wrote 9 to 23 percent over the words it was asked for (0.50.3's loop), and paragraph breaks add
# time of their own: it's asked for this share of each segment's words (all of them where a bare [hold] keeps the
# segment its length, since a word short there is a second of silence)
COACH_AIM = 0.85
SILENCE = 8.0          # draft.MAX_SILENCE: a fixed hold or pause past it is refused, so the coach talks through it
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
# about 180 s, and a call that thinks that long is rare but whole (a final script writer's 179 s against its usual 26 to 37).
PATIENCE = {"content": 160, "coach": 110, "final": 80}


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
    number: int = Field(description="its number, from 1, in the order told")
    topic: str = Field(description="its topic as the plan names it, or - for none")
    format: str = Field(description="its format's id in the plan")
    title: str = Field(description="a short title, for the log")
    source: str = Field(description="a link, or the sheet it came from")
    text: str = Field(description="the story as the coach says it, in paragraphs of under fifty words, no markers")


class Stories(BaseModel):
    stories: list[Told]


class Edited(BaseModel):
    number: int = Field(description="the segment's number")
    text: str = Field(description="the whole segment as it should read, its markers and [story] tags in place, "
                                  "without its @@ line")


class Edits(BaseModel):
    segments: list[Edited]


CONTENT = Agent(output_type=Stories, retries=2)
COACH = Agent(output_type=Coaching, retries=2)
FINAL = Agent(output_type=Edits, retries=2)


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
        "content": task("personal-content-writer.md") + "\n\n## Telling it\n" + bullets(
            engaged, "The coach's voice", "A rest holds one story", "Their taste counts", "Time-proof it",
            "Weave threads") + "\n" + bullets(safety, "Never invent facts") + voice(*said),
        "coach": task("coach-writer.md") + f"\n\n## Safety: the rules\n{safety}\n\n## Getting the workout done\n{done}"
                 "\n\n## The voice and the shape\n" + bullets(engaged, "The coach's voice", "Time-proof it", "A shape")
                 + voice(*(h for h in tts if h != "The draft")),
        "final": task("final-script-writer.md") + "\n\n## What it should sound like\n" + bullets(
            engaged, "The coach's voice", "A rest holds one story", "Weave threads", "A shape")
                  + voice(*said, "Markers"),
    }
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


def assemble(skeleton: str, coaching: dict[int, Written], stories: dict[int, Told], rests) -> str:
    """The skeleton with every segment's words: the coach's, and in each rest that carries one, the story between the
    coach's opener and handback."""
    head, segs = split(skeleton)
    out = list(head)
    for n, (at, _, _, body) in enumerate(segs, 1):
        w = coaching.get(n)
        parts = [w.text.strip() if w and w.text.strip() else "\n".join(body).strip()]
        if n in rests and n in stories:
            parts.append(story_block(stories[n].text))
            if w and w.handback.strip():
                parts.append(w.handback.strip())
        out += [at, "\n\n".join(p for p in parts if p), ""]
    return "\n".join(out).rstrip("\n") + "\n"


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


def story_words(budget: dict, rests) -> dict[int, int]:
    """About how long each rest's story runs, for the coach writing beside the personal content writer: what it's asked for,
    or less in a short rest."""
    return {n: min(STORY_WORDS, round(budget.get(n, 0) * STORY_SHARE)) for n in rests}


def _plan_table(segs: list, budget: dict, stories: dict[int, int]) -> str:
    rows, at = [], 0
    for n, (_, label, secs, body) in enumerate(segs, 1):
        marks = " ".join(tools.MARK.findall("\n".join(body))) or "none"
        whole = round(budget.get(n, 0) * (1 if "[hold]" in "\n".join(body) else COACH_AIM))
        if n in stories:
            words = stories[n]
            say = f"opener and handback, about {max(whole - words, 20)} words together (a {words}-word story goes between)"
        else:
            say = f"about {whole} words"
        rows.append(f"#{n} at {at // 60}:{at % 60:02d}, {secs} s, {label}. Markers: {marks}. Write: {say}.")
        at += secs
    return "\n".join(rows)


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


def _thinking(model, level: str) -> dict | None:
    return {"google_thinking_config": {"thinking_level": level}} if type(model).__name__ == "GoogleModel" else None


async def _ask(deps, who: str, agent: Agent, model, prompt: str, usage, level: str, capabilities=(), history=None):
    """One writer's call; cut off by Gemini's own deadline (504, thinking too long), it's
    asked again a level lower, as it is when it runs past its PATIENCE."""
    lower = LEVELS[LEVELS.index(level) + 1:] if level in LEVELS else ()
    try:
        result = await asyncio.wait_for(
            agent.run(prompt, model=model, instructions=guides(deps.engine_root)[who],
                      model_settings=_thinking(model, level), usage=usage, capabilities=list(capabilities),
                      message_history=history),
            timeout=PATIENCE.get(who) if lower else None)
    except (ModelHTTPError, asyncio.TimeoutError) as e:
        if isinstance(e, ModelHTTPError) and e.status_code != 504 or not lower:
            raise
        return await _ask(deps, who, agent, model, prompt, usage, lower[0], capabilities, history)
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
              f"# What to write\n\nThe session runs {minutes} minutes, with about {count} rests: {count} stories, "
              f"about {STORY_WORDS} words each (anywhere from {STORY_WORDS // 2} to {STORY_WORDS * 4 // 3}). The last "
              "two are spares, told only if there's room: nothing earlier depends on them.")
    told = await _ask(deps, "content", CONTENT, model, prompt, usage, "MEDIUM", capabilities=search)
    found = {s.number: s for s in told.output.stories}
    titles = told_titles(plan.output)
    repeats = {n: t for n, s in found.items() if (t := retold(s, titles))}
    if repeats:
        again = await _ask(deps, "content", CONTENT, model, (
            "Write these again, whole, each about another item, and return only these: "
            + "; ".join(f"story {n} retells \"{t}\", told before" for n, t in repeats.items()) + "."),
            usage, "MEDIUM", capabilities=search, history=told.all_messages())
        found.update({s.number: s for s in again.output.stories if s.number in repeats})
    return [found[n] for n in sorted(found)]


def numbered(text: str) -> str:
    """A draft with each @@ line numbered, as the lint numbers segments, for the final script writer."""
    n = 0
    out = []
    for line in text.split("\n"):
        if SEGMENT.match(line):
            n += 1
            line = f"#{n} {line}"
        out.append(line)
    return "\n".join(out)


async def write(deps, model, usage, path: str, search=()) -> tuple[str, str]:
    """The script's words for the skeleton at `path`: the stories (started with the brief, or now), the coaching
    around them, then the edit. (the draft, a note for the agent)."""
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
    name, coach = tools.build_name(path), deps.brief_coach
    report = deps.reports.get(path)
    if report is None:
        if not (name and coach):
            raise NotReady("build the skeleton first (write_file with build_name and coach): its word budgets come next")
        linted = await asyncio.to_thread(tools.run, plain, ["build", path, name, "--coach", coach, "--lint-only"])
        report = linted.output + "\n" + linted.error
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

    rests = slots(segs, budget)
    about, feeds = await asyncio.gather(asyncio.to_thread(tools.run, plain, ["movements", "--about", ",".join(ids)]),
                                        asyncio.to_thread(tools.run, plain, ["feeds"]))
    weather = _section(feeds.output if feeds.code == 0 else "", "Weather") or "not known"
    coach_prompt = (
        f"Now: {deps.now}.\n\n# The brief\n\n{coach_brief(brief, ids)}\n\n# The coaching notes\n\n"
        f"{about.output.strip()}\n\n# The weather\n\n{weather}\n\n# The plan\n\nThis coach says about {rate:.1f} "
        f"words a second, so each segment's words fill its seconds: a hold or pause you add takes {rate:.1f} words a "
        f"second from them.\n\n{head[0] if head else ''}\n{_plan_table(segs, budget, story_words(budget, rests))}")

    async def the_stories() -> list[Told]:   # started as the brief was saved, or written now
        job = deps.content_job if deps.content_job is not None and deps.content_for == path else None
        if job is not None:
            try:
                return await asyncio.wrap_future(job)
            except Exception:  # noqa: BLE001 - the early run failed: write them now instead
                pass
        return await stories(deps, model, usage, path, max(1, round(sum(s for _, _, s, _ in segs) / 60)), search)

    # the stories and the coaching side by side, each from its own material
    told, coached = await asyncio.gather(the_stories(),
                                         _ask(deps, "coach", COACH, model, coach_prompt, usage, "MEDIUM"))
    placed = dict(zip(sorted(rests), told))   # in order: the spares, last, go when there are fewer rests
    coaching = {w.number: w for w in coached.output.segments}
    draft = assemble(skeleton, coaching, placed, rests)

    # the edit: the assembled script as the listener hears it, with the build's check; once more if the check
    # still finds something after it
    limits = _section(brief, "Today's limits")
    changed: set[int] = set()
    history = None
    for attempt in range(2):
        check = await _lint(deps, plain, path, full, name, coach, draft)
        if attempt and check.startswith("clean"):
            break
        draft = _read(full) if name and coach else draft
        prompt = (f"Now: {deps.now}.\n\n{_section(brief, 'The listener')}\n\n{limits}\n\n# The script\n\n"
                  f"{numbered(draft)}\n\n# The build's check\n\n{check}") if not attempt else (
                  f"The build's check after your edit:\n\n{check}\n\nFix what it names; return only those segments.")
        edited = await _ask(deps, "final", FINAL, model, prompt, usage, "MEDIUM", history=history)
        history = edited.all_messages()
        draft = apply_edits(draft, edited.output.segments)
        changed |= {e.number for e in edited.output.segments}

    logged = [f'--item "{s.topic} | {s.format} | {s.title} | {s.source}"' for _, s in sorted(placed.items())]
    note = (f"Three writers wrote the words: {len(placed)} stories in {len(rests)} rests, the coaching for "
            f"{len(coaching)} of {len(segs)} segments, and the final script writer changed {len(changed)}. "
            + ("After recording, log what was told: `content log --draft <draft> " + " ".join(logged) + "`."
               if logged else ""))
    return draft, note


async def _lint(deps, plain, path: str, full: str, name: str | None, coach: str | None, draft: str) -> str:
    """The build's check of `draft` (written to `path` first): "clean" and its summary, or its issues."""
    if not (name and coach):
        return "not checked"
    await asyncio.to_thread(tools.write_file, deps, path, draft)
    r = await asyncio.to_thread(tools.run, plain, ["build", path, name, "--coach", coach, "--lint-only"])
    out = (r.output + "\n" + r.error).strip()
    return ("clean: " if r.code == 0 else "") + out


def apply_edits(draft: str, edits: list[Edited]) -> str:
    """The draft with the final script writer's segments in place of its own, each under its own @@ line (the clock is the
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
