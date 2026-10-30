#!/usr/bin/env python3
"""Today's brief: the ingredients a session is designed and written from.

The workout skill designs the session itself (method, movements, order, doses, timing) and writes it;
this gathers what that needs, in one Markdown page: the listener, how today fits the week, today's
limits with the clinician's rules and the catalog's limit cues, the safe menu (every movement the kit,
level and limits allow, with its coaching notes), the programming guide for the goal and level, and
the kit's equipment notes. It plans nothing.

    ./harmonicfitness brief --goal strength --minutes 30 --kit home
    ./harmonicfitness brief --goal general --minutes 25 --preset hotel-gym --limit knee=delicate:left \\
        --save me/workouts/2026-10-22-general-25/2026-10-22-general-25.draft.txt

With --save <draft path> it also writes the brief (`<stem>.brief.md`) and the menu (`<stem>.menu.json`)
beside the draft; `./harmonicfitness build` checks the draft's movements against that menu and won't build
without it. The safety screen (tools/screen.py) applies the limits, clinician Avoid: lines, dislikes
and level, and refuses when a [[limits]] row can't be read.
"""
import datetime
import os
import sys
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import cli  # noqa: E402
import errors  # noqa: E402
import context  # noqa: E402
import sessionlog  # noqa: E402
import health  # noqa: E402
import frontmatter  # noqa: E402
import coverage  # noqa: E402
import draft  # noqa: E402
import menu  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
import screen  # noqa: E402
import sessions  # noqa: E402
import voices  # noqa: E402

KNOWLEDGE = os.path.join(paths.ROOT, "knowledge")
PLAYBOOK = os.path.join(KNOWLEDGE, "injury-playbook.md")
PROGRAMMING = os.path.join(KNOWLEDGE, "programming.md")
KITS = os.path.join(KNOWLEDGE, "kits.md")

# kits.md's sections, by the equipment or preset they describe
KIT_SECTIONS = {"dumbbells": "Dumbbells", "kettlebell": "Kettlebell", "bike": "Stationary bike",
                "air-bike": "Stationary bike", "stick-and-ball": "Stick and dryland ball",
                "rower": "Rowing machine", "treadmill": "Treadmill", "band": "Resistance bands",
                "bench": "Bench", "mat": "Mat and mobility", "foam-roller": "Mat and mobility",
                "strap": "Mat and mobility"}
PRESET_SECTIONS = {"hotel-room": "Hotel room (no gym)", "hotel-gym": "Hotel gym (assume basic)",
                   "full-gym": "Full gym", "bodyweight": "No equipment"}
BODY_ONLY = {"chair", "towel", "mat", "foam-roller", "strap"}   # a kit of these alone is "no equipment"
PROFILE_SECTIONS = ("Default session",)   # the profile prose the brief quotes
DOSE_WORDS = {"sets": "sets", "reps": "reps", "bodyweight_reps": "reps with no load",
              "rest_seconds": "rest (s)", "hard_sets_per_session": "hard sets a session",
              "work_seconds": "work (s)", "rounds": "rounds", "efforts_per_session": "hard efforts a session",
              "hold_seconds": "hold (s)", "drill_seconds": "drill (s)"}
GOAL_DOSES = {"strength": ("strength", "conditioning"), "general": ("strength", "conditioning"),
              "targeted": ("strength", "conditioning"), "conditioning": ("conditioning", "strength"),
              "mobility": ("mobility",), "skill": ("skill", "strength")}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _sections(text: str) -> Dict[str, str]:
    """{heading: body} for each `## heading` of a Markdown file, bodies stripped."""
    out: Dict[str, List[str]] = {}
    current = None
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _first_paragraph(body: str) -> str:
    return body.split("\n\n")[0].split("\n- ")[0].strip()


def _range(v) -> str:
    return f"{v[0]:g}" if v[0] == v[1] else f"{v[0]:g} to {v[1]:g}"


def _needs(m: catalog.Movement) -> str:
    return ", ".join(" or ".join(n.split("|")) for n in m.needs) or "bodyweight"


def _timing(m: catalog.Movement) -> str:
    each = (f"{m.seconds_per_rep} s a rep" if m.measure == "reps" else f"timed, {m.hold_seconds} s a hold")
    return f"{each}, {m.transition_seconds} s to set up"


def _kind(m: catalog.Movement) -> str:
    return f"{m.intensity}, {m.effort} effort" if m.effort else m.intensity


def _limited(m: catalog.Movement, areas: List[str]) -> str:
    """Its load on today's limited areas, as "neck 1, knee 1 (resting side 1)", or ""."""
    parts = []
    for a in areas:
        load, rest = m.loads.get(a, 0), (m.support.get(a, 0) if m.sided else 0)
        if load or rest:
            parts.append(f"{a} {load}" + (f" (resting side {rest})" if rest else ""))
    return ", ".join(parts)


def menu_lines(cat: catalog.Catalog, scr, sides: Dict[str, str], likes, last_ids, compact=False) -> List[str]:
    """The safe menu: every allowed movement under its primary pattern, then the healthy-side-only
    ones, each with its facts and the catalog's coaching notes. `compact` keeps the facts and the easier and
    harder versions (what designing needs) and leaves the coaching notes to `./harmonicfitness movements --about`,
    except for a movement that loads one of today's limited areas or works one side only: its notes stay."""
    areas = list(dict.fromkeys(lim.area for lim in scr.limits))

    def entry(m, side=None):
        where = f"{side} side only" if side else ("one side at a time" if m.sided else "")
        facts = [m.position + (f", {where}" if where else ""), _needs(m), _timing(m),
                 f"{_kind(m)}, {m.level}", ", ".join(m.muscles)]
        if m.flags:
            facts.append("flags: " + ", ".join(m.flags))
        load = _limited(m, areas)
        if load:
            facts.append(f"load on today's limits ({'the working side' if side else 'as rated'}): {load}"
                         if side else f"load on today's limits: {load}")
        tags = [t for t, on in (("liked", m.id in likes), ("in the last session", m.id in last_ids)) if on]
        head = f"- **{m.name}** (`{m.id}`{', ' + ', '.join(tags) if tags else ''}): " + "; ".join(facts) + "."
        notes = ["  " + line.strip() for line in catalog.about(cat, m)[1:]]
        if compact and not load and not side:
            notes = [n for n in notes if n.strip().startswith(("Easier:", "Harder:"))]
        return [head] + notes

    out = []
    for p in cat.patterns:
        group = [m for m in scr.sel.allowed if m.patterns and m.patterns[0] == p]
        if group:
            out += ["", f"### {p}"]
            for m in group:
                out += entry(m)
    if scr.sel.healthy_side_only:
        out += ["", "### Healthy side only",
                "Only the named side works; say in the audio why the other side rests, and that training "
                "the healthy side still helps the injured one a little (programming.md, One-sided training)."]
        for m in scr.sel.healthy_side_only:
            out += entry(m, sides.get(m.id, "healthy"))
    return out


def _week_lines(cat: catalog.Catalog, log, today: datetime.date, feedback: List[str]) -> List[str]:
    if not log:
        return ["- No sessions logged yet: this is the first one, so welcome them to it."]
    last = log[-1]
    since = coverage.days_ago(last.date, today)
    seven = sum(1 for e in log if (d := coverage.days_ago(e.date, today)) is not None and 0 <= d < 7)
    hit, _ = coverage.coverage(last.movements, cat)
    trained = [p for p in cat.patterns if hit.get(p)]
    out = [f"- Last session: {last.date}" + (f", {since} day{'s' if since != 1 else ''} ago" if since is not None else "")
           + f", {last.minutes} min, {last.kit}, format {last.format or 'not logged'}: "
           + ", ".join(last.movements) + (f" (patterns: {', '.join(trained)})" if trained else "") + ".",
           f"- Sessions in the last seven days: {seven}."]
    week = coverage.week(log, today, cat=cat)
    none = [p for p in cat.patterns if not week.get(p) and p != "skill"]
    once = [p for p in cat.patterns if week.get(p) == 1]
    if none:
        out.append("- Not trained in the last seven days: " + ", ".join(none) + ".")
    if once:
        out.append("- Trained once in the last seven days: " + ", ".join(once) + ".")
    loads = coverage.last_loads(log, cat=cat)
    if loads:
        out.append("- Last loads (progress from these): " + "; ".join(
            f"{mv}: {load} ({date})" for mv, (date, load) in sorted(loads.items(), key=lambda kv: kv[1][0], reverse=True)) + ".")
    if feedback:
        out.append(f"- Latest feedback (honour it, and say so): {feedback[-1]}")
    return out


def _profile_lines(profile) -> List[str]:
    out = []
    for heading in PROFILE_SECTIONS:
        for _, line in frontmatter.section(profile.body, heading):
            item = line.strip()
            key, _, value = item[2:].partition(":") if item.startswith("- ") else ("", "", "")
            if key and value.strip() and not frontmatter.placeholder(value.strip()):
                out.append(f"- {key.strip()}: {value.strip()}")
    return out


def _limit_lines(cat: catalog.Catalog, scr, h, request: dict) -> List[str]:
    playbook = _sections(_read(PLAYBOOK))
    today = list(request.get("limits") or [])
    own = [lim for lim in scr.limits if lim not in today]
    out = []
    for lim in own + today:
        side = f", {lim.side} side" if lim.side in ("left", "right") else ""
        when = " (today only, from the check-in)" if lim in today and lim not in own else ""
        note = f" Note: {lim.note}" if lim.note and lim.note != catalog.meaning(lim.area, lim.level, lim.side) else ""
        out.append(f"- **{lim.area} {lim.level}{side}**{when}: {catalog.meaning(lim.area, lim.level, lim.side)}.{note}")
    if not out:
        out.append("- No limits today.")
    rules = health.clinician_lines(h, cat.areas, cat.flags)[len(health.limits(h, cat.areas, cat.flags)):]
    if rules:
        out += ["", "Clinician rules (say them in the clinician's words, attributed to the clinician; follow "
                "them literally, and where one is stricter than the general stop rule, such as no pushing "
                "through pain, it wins for that area every time it comes up):"] + [f"- {r}" for r in rules]
    if any(catalog.AREA_POSITIONS.get((lim.area, lim.level)) for lim in scr.limits):
        out += ["", "Nothing standing today includes fetching the kit: have everything the session uses set out "
                "within reach before the work starts, and script no walk to a rack or across the room."]
    avoided = sorted(a for a in scr.avoid)
    if avoided:
        out += ["", "Left out today by Avoid: lines and the request: " + ", ".join(avoided) + "."]
    cues = screen.cue_lines(cat, scr.limits)
    if cues:
        out += ["", "Limit cues (the catalog's spoken lines; say them wherever a movement or a transition "
                "touches the limit):"] + [line.replace("    ", "  - ", 1) if line.startswith("    ") else "- " + line.strip()
                                          for line in cues]
    areas = list(dict.fromkeys(lim.area for lim in scr.limits))
    for a in areas:
        title = a.replace("-", " ").capitalize()
        if title in playbook:
            out += ["", f"From the injury playbook, {title}: {_first_paragraph(playbook[title])}"]
    out += ["", "Red flags (stop and suggest a clinician, in chat, not the audio): "
            + _first_paragraph(playbook.get("Red flags", "")).replace("Mention these in chat, not in the audio, if "
                                                                      "the listener reports them: ", "")]
    return out


def _method_shape(m) -> str:
    """What the method's rules say beyond its about: how its work is counted, and a rest of its own."""
    parts = [f"work: {m.work}"]
    if m.rest_seconds:
        parts.append(f"rest {m.rest_seconds[0]} to {m.rest_seconds[1]} s between rounds")
    return "; ".join(parts)


def _programming_lines(sess: sessions.Sessions, request: dict, scr, log) -> List[str]:
    goal, minutes = request["goal"], request["minutes"]
    total = minutes * 60
    out = ["Guidance, not a plan: choose a shape inside it that suits this listener today. Where a dose "
           "range and a rule below disagree, the range is the level's and the rule says where in it to land.", "",
           f"Doses at the {scr.level} level (knowledge/sessions.toml):"]
    for intensity in GOAL_DOSES.get(goal, ("strength",)):
        table = sessions.dose(sess, intensity, scr.level)
        parts = [f"{DOSE_WORDS.get(k, k)} {_range(v)}" for k, v in table.items()]
        out.append(f"- {intensity.capitalize()}: " + "; ".join(parts) + ".")
    if goal in ("conditioning", "general", "strength", "targeted"):
        ao = sess.all_out
        out.append(f"- All-out sprints (a hard timed effort of {ao.get('most_seconds')} s or less) rest at least "
                   f"{ao.get('rest_ratio')} times their work, and stay few.")
    if goal == "conditioning":
        out.append("- On a conditioning day the work intervals run at the effort above, even when the profile says "
                   "it likes moderate sessions: that preference sets the warm-up, the steady work and the easy spells. "
                   "Only a low-readiness check-in, or a limit, keeps the intervals easier.")
    last_format = log[-1].format if log else None
    ranked = sessions.ranked(sess, goal, minutes, scr.level, scr.equipment, last_format)
    if ranked:
        m = ranked[0]
        shares = [f"warm-up about {screen.clamp(m.warmup, total)} s", f"cool-down about {screen.clamp(m.cooldown, total)} s"]
        if m.finisher and minutes >= m.finisher.get("from_minutes", 0):
            shares.append(f"a finisher of about {screen.clamp(m.finisher, total)} s, if you want one")
        out += ["", f"Time ({total} s in all, house defaults): " + ", ".join(shares) + "; the work gets the rest."]
        out += ["", f"Formats that suit a {minutes} minute {goal} session at this level with this kit "
                "(any of them, or a mix, as long as the doses fit):"]
        out += [f"- {x.name}: {x.about} ({_method_shape(x)})" for x in ranked]
    else:
        out += ["", f"No format in knowledge/sessions.toml lists a {minutes} minute {goal} session at this level; "
                "shape one from the doses above, or suggest a different length."]
    if last_format:
        out.append(f"- The last session was {last_format}; a different format today keeps it fresh "
                   "(log today's as `format: <name>`).")
    if request.get("target"):
        out += ["", f"Focus today: {', '.join(request['target'])}. Give it at least half the work, and keep the "
                "rest of the body ticking over."]
    out += ["", "Timing: one set takes its reps times the seconds a rep (both sides for one-sided work, plus "
            "about five seconds to switch), plus its setup the first time. A set with its rest takes about two "
            "minutes, about one when paired."]
    out += ["", "What a good session looks like (the rules in knowledge/programming.md):"]
    for heading, body in _sections(_read(PROGRAMMING)).items():
        for para in body.split("\n\n"):
            para = " ".join(para.split())
            if para.startswith("Rule:"):
                out.append(f"- {heading}: {para[len('Rule:'):].strip()}")
            elif para.startswith(("What a session holds", "The order of steps")):
                out.append(f"- {para}")
    return out


def _equipment_lines(request: dict, equipment) -> List[str]:
    kits = _sections(_read(KITS))
    wanted = []
    if request.get("preset"):
        wanted.append(PRESET_SECTIONS.get(request["preset"]))
    if not set(equipment) - BODY_ONLY:
        wanted.append("No equipment")
    wanted += [KIT_SECTIONS[e] for e in sorted(equipment) if e in KIT_SECTIONS]
    out = []
    for heading in dict.fromkeys(w for w in wanted if w):
        if heading in kits:
            out += [f"**{heading}.** {' '.join(kits[heading].split())}", ""]
    return out[:-1] if out else ["- Nothing to add for this kit."]


def _kit_words(request: dict, equipment) -> str:
    if request.get("kit"):
        return f"the {request['kit']} kit"
    if request.get("preset"):
        return f"the {request['preset']} preset"
    return "equipment: " + (", ".join(sorted(equipment)) or "none")


def _coach(name):
    import coachpick
    try:
        return coachpick.coach(name)
    except errors.PROBLEMS:
        return None


def talk_rate(voice_name: str):
    """(words a minute, measured?) for a coach speaking the smoke test's coaching on the route a build
    would take here, or None for an unknown coach (or one with no route here). Spoken words only: holds,
    pauses and chimes take their own seconds."""
    import coachpick
    import personas
    try:
        voice = coachpick.resolve(voice_name, pending=True)
    except errors.PROBLEMS:   # no route works here (yet): the coach's local pace is still the best guess
        coach = _coach(voice_name)
        try:
            if coach is None:
                voice = None
            elif coach.is_web:   # no key yet: its pace is an estimate from its sample
                voice = personas.voice_for(coach, coach.service, pending=True)
            else:
                voice = personas.voice_for(coach, "local")
        except errors.PROBLEMS:
            voice = None
    if voice is None:
        return None
    rate, exact = voices.pace(voice)
    with open(paths.SMOKE_DRAFT, encoding="utf-8") as f:
        texts = [t for seg in draft.parse(f.read()) for para in draft.plan(seg) for t, _ in para if draft.spoken(t)]
    seconds = sum(voices.weight(t) for t in texts) / rate
    return sum(len(t.split()) for t in texts) / seconds * 60, exact


def _coach_lines(name) -> List[str]:
    """Who's coaching and how they talk: the coach's [character] table, then its persona.md prose, as the
    profile's Narrator was."""
    coach = _coach(name)
    if coach is None:
        return []
    out = [f"- Coach: {coach.name}" + (f" ({coach.description})" if coach.description else "")]
    for key, value in coach.character.items():
        text = "; ".join(str(v).strip() for v in value if str(v).strip()) if isinstance(value, list) \
            else str(value).strip()
        if text and not frontmatter.placeholder(text):
            label = key.replace("_", " ").strip()
            out.append(f"- {label[:1].upper() + label[1:]}: {text}")
    for line in coach.prose.splitlines():
        item = line.strip()
        key, _, value = item[2:].partition(":") if item.startswith("- ") else ("", "", "")
        if key and value.strip() and not frontmatter.placeholder(value.strip()):
            out.append(f"- {key.strip()}: {value.strip()}")
    return out


def _counts_line(voice_name: Optional[str]) -> List[str]:
    """How this coach counts down: [count] markers either way; recorded clips on the beat, or said in words."""
    import counts
    coach = _coach(voice_name)
    if coach is None:
        return []
    how = ("`[count 5]` (five down to one) or `[count 3 go]` (then the cue; the cues are go, rest, switch, "
           "switch sides, stop and hold), and a cue said alone as `[cue rest]`")
    if not coach.is_web and coach.has_clip and counts.folder(coach.clip):
        return [f"- Counts: write a countdown as {how}. {coach.name} plays recorded counts a second apart; a "
                "countdown in words is refused (knowledge/tts-rules.md, Markers)."]
    return [f"- Counts: write a countdown as {how}. {coach.name} has no recorded counts, so the voice says it "
            "in words (\"Three, two, one, go.\"), quickly: one per segment."]


def _voice_line(voice_name: Optional[str]) -> List[str]:
    """How this coach's voice takes the text: a local one in short pieces (a sentence or a few), a web one a paragraph."""
    coach = _coach(voice_name)
    if coach is None:
        return []
    if coach.is_web:
        return [f"- Voice: {coach.name} is a web voice that reads a whole paragraph at once, so short cues sound "
                "fine."]
    return [f"- Voice: {coach.name} is a local voice that speaks in short pieces, each started fresh, so a run of "
            "two-word sentences sounds like a machine and can lose its last words. Write fuller sentences, joining short cues with commas and \"and\" "
            "(\"Lower slow, and push.\"), keeping each cue word clear (knowledge/tts-rules.md, Local and web voices)."]


def _budget_line(voice_name: Optional[str]) -> List[str]:
    coach = _coach(voice_name)
    found = talk_rate(coach.name) if coach else None
    if not found:
        return []
    wpm, exact = found
    voice_name = coach.name
    return [f"- Talk to time: {voice_name} speaks about {wpm:.0f} words a minute"
            f"{'' if exact else ' (estimated; not measured on this computer yet)'}, so twenty seconds of talk "
            f"is about {wpm / 3:.0f} words. Holds, pauses and chimes take their own seconds; "
            "`./harmonicfitness build <draft> <name> --lint-only` gives each segment's exact guide."]


def build(request: dict, cat: catalog.Catalog, sess: sessions.Sessions, profile, health, log,
          today: datetime.date, feedback: Optional[List[str]] = None, voice: Optional[str] = None,
          compact: bool = True):
    """(the brief as Markdown lines, the menu record). ValueError names an unknown value; screen.Unfit
    says a [[limits]] row can't be read. `compact` (the default) prints the menu without each movement's
    coaching notes, which the writer reads with `movements --about` for the movements chosen (menu_lines)."""
    scr = screen.screen(request, cat, sess.goals, profile, health)
    sides = {m.id: screen.healthy_side(m, scr.limits) for m in scr.sel.healthy_side_only}
    last_ids = screen.ids(cat, log[-1].movements) if log else set()
    goal, minutes = request["goal"], request["minutes"]
    name = context.listener_name(profile)
    count = len(scr.sel.allowed) + len(scr.sel.healthy_side_only)
    reasons: Dict[str, int] = {}
    for why in scr.sel.left_out.values():
        for r in why:
            reasons[r] = reasons.get(r, 0) + 1
    left = ", ".join(f"{r} {n}" for r, n in sorted(reasons.items(), key=lambda kv: -kv[1]))

    out = [f"# Today's brief: {goal}, {minutes} minutes, {_kit_words(request, scr.equipment)}",
           f"{today.isoformat()}, {today.strftime('%A')}. Ingredients, not a plan: design the session from "
           "these (method, movements, order, doses, timing), post the plan, then write it.", ""]
    out += [f"Warning: {w}" for w in scr.warnings]
    out += ["## The listener", f"- Name: {name} (greet them by it; two to four times a session)." if name
            else "- No name in the profile: no name in the audio.",
            f"- Level: {scr.level}."]
    liked = [cat.movements[i].name for i in sorted(scr.likes) if i in cat.movements]
    if liked:
        on = {m.id for m in scr.sel.allowed + scr.sel.healthy_side_only}
        out.append("- Likes (use them when they fit): " + ", ".join(
            n + ("" if i in on else " (not on today's menu)") for i, n in zip(sorted(scr.likes), liked)) + ".")
    disliked = [cat.movements[i].name for i in sorted(scr.dislikes) if i in cat.movements]
    if disliked:
        out.append("- Dislikes (left off the menu): " + ", ".join(disliked) + ".")
    out += _coach_lines(voice) + _profile_lines(profile)
    out += ["", "## Today in the week"] + _week_lines(cat, log, today, feedback or [])
    out += ["", "## Today's limits"] + _limit_lines(cat, scr, health, request)
    out += ["", "## Safe menu",
            f"Every movement in the script comes from this list, warm-up and cool-down included: {count} today "
            f"({len(scr.sel.left_out)} left out: {left or 'none'}). Nothing from memory. `./harmonicfitness build` "
            "checks the draft's `movements:` line and its text against it."]
    if compact:
        out.append("Coaching notes: after designing, run `./harmonicfitness movements --about <the ids you chose, comma "
                   "separated>` and coach from them; a movement that loads today's limits or works one side only "
                   "carries its notes here.")
    if scr.sel.allowed or scr.sel.healthy_side_only:
        out += menu_lines(cat, scr, sides, scr.likes, last_ids, compact=compact)
    weights = context.kit_weights(profile).get(request.get("kit") or "")
    loads = screen.loads_line(weights, scr.equipment) if weights else ""
    opens = screen.would_open(cat, scr.sel, scr.equipment, scr.level, scr.limits, scr.avoid, scr.dislikes)
    extra = []
    if loads:
        extra.append(f"- {loads}. Prescribe only these weights, by name.")
    if opens:
        extra.append("- Would open up more movements: " + ", ".join(f"{e} (+{n})" for e, n in opens)
                     + ". Ask once at the check-in if one is on hand; otherwise plan without it.")
    if extra:
        out += [""] + extra
    out += ["", "## Programming guide"] + _programming_lines(sess, request, scr, log)
    out += ["", "## Equipment notes"] + _equipment_lines(request, scr.equipment)
    out += ["", "## Writing it",
            f"- First line of the draft: `movements: <every movement the script uses, by its name above, comma "
            f"separated>`. Then the `@@ <seconds> | <label>` segments, adding up to exactly {minutes * 60} s. "
            "You choose the segments: one can be a set, a pair, a whole round or the whole warm-up.",
            "- Coach each movement from its notes" + (" (`movements --about`, or above)" if compact else " above")
            + " (setup, cues, what one rep is, where to feel it, the faults and their fixes): fully the first time "
            "it appears, then a short reminder, so the rests and the easy work have room for the listener's world."
            " Safety is the one hard rule (knowledge/script.md); beyond it, get the "
            "workout done and keep them engaged. What a voice can read: knowledge/tts-rules.md."]
    out += _budget_line(voice) + _counts_line(voice) + _voice_line(voice)

    req = {k: v for k, v in (("goal", goal), ("minutes", minutes), ("kit", request.get("kit")),
                             ("preset", request.get("preset")),
                             ("equipment", sorted(request["equipment"]) if "equipment" in request else None),
                             ("add", sorted(request["add"]) if request.get("add") else None),
                             ("level", scr.level), ("target", request.get("target") or None),
                             ("limits", [f"{lim.area}={lim.level}:{lim.side}" for lim in scr.limits] or None),
                             ("avoid", sorted(scr.avoid) or None)) if v}
    record = menu.record(req, scr.sel, sides, minutes * 60, today.isoformat(),
                         health_sha256=menu.health_hash(getattr(health, "path", None) or paths.HEALTH))
    return out, record


def main(argv=None):
    ap = cli.ArgumentParser(prog="harmonicfitness brief", description=(
        "Today's ingredients for designing and writing a session: the listener, the week, the limits, the "
        "safe menu with coaching notes, the programming guide and the equipment notes."))
    ap.add_argument("--goal", required=True, help="strength, general, targeted, conditioning, mobility or skill")
    ap.add_argument("--minutes", required=True, type=cli.positive_int, help="the session's length in minutes")
    kit = ap.add_mutually_exclusive_group(required=True)
    kit.add_argument("--kit", help="a kit named in the profile's [[kits]]")
    kit.add_argument("--preset", help="a kit preset from the catalog, such as hotel-room")
    kit.add_argument("--equipment", help="comma-separated equipment, as keys or aliases")
    ap.add_argument("--add", default="", help="comma-separated equipment on hand today, added to the kit's "
                                                "(say, a bench the brief said would open up more movements)")
    ap.add_argument("--level", help="novice, experienced or advanced (default: the profile's)")
    ap.add_argument("--target", help="comma-separated patterns or muscles to focus on")
    ap.add_argument("--limit", action="append", default=[], help="area=level[:side], added to health.md's limits")
    ap.add_argument("--avoid", default="", help="comma-separated movements (ids or names) or flags to rule out")
    ap.add_argument("--save", help="the draft's path (or its stem): write <stem>.brief.md and <stem>.menu.json")
    ap.add_argument("--full", action="store_true",
                    help="print every movement's coaching notes in the menu (by default only those that touch "
                         "today's limits or work one side; movements --about prints the rest)")
    ap.add_argument("--log", help="the log to read (default: the context folder's)")
    cli.today_arg(ap)
    ap.add_argument("--coach", dest="voice",
                    help="the coach the script is written for: how they talk, and their words a minute "
                         "(default: the one used last)")
    args = ap.parse_args(argv)

    # The files first: a damaged catalog, session rules or profile is that file's problem (exit 1 through cli.run),
    # never "the command was wrong". Then every flag is checked (exit 64) before anything is computed.
    cat = catalog.load()
    sess = sessions.load()
    profile = context.profile()
    save = _save_target(args.save)
    request = request_from(args, cat, sess, profile)
    today = args.today or datetime.date.today()
    lines, record = build(request, cat, sess, profile, health.health(), sessionlog.sessions(args.log), today,
                          context.feedback(args.log), voice=args.voice, compact=not args.full)
    text = "\n".join(lines) + "\n"
    print(text, end="")
    if save:
        brief, menu_file = draft.brief_path(save), draft.menu_path(save)
        fileio.atomic_write(brief, text)
        menu.write(menu_file, record)
        print(f"\nSaved the brief to {paths.show(os.path.abspath(brief))} and the menu to "
              f"{paths.show(os.path.abspath(menu_file))}; the draft goes to "
              f"{paths.show(os.path.abspath(draft.stem(save) + draft.DRAFT_SUFFIX))}.", file=sys.stderr)
    return cli.OK


def _usage(e):
    return cli.Usage(f"harmonicfitness brief: {e}")


def request_from(args, cat, sess, profile):
    """The request build() takes, from the command line, every value checked against the catalog, the session
    rules and the profile's kits first: an unknown goal, kit, preset, equipment, level, target, limit or avoid
    word raises cli.Usage (exit 64) naming the choices."""
    if args.goal not in sess.goals:
        raise _usage(f"unknown goal \"{args.goal}\" (choose from: {', '.join(sess.goals)})")
    if args.level is not None and args.level not in catalog.LEVELS:
        raise _usage(f"unknown level \"{args.level}\" (choose from: {', '.join(catalog.LEVELS)})")
    target = screen.words(args.target)
    for t in target:
        if t not in cat.patterns and t not in cat.muscles:
            raise _usage(f"unknown target \"{t}\" (patterns: {', '.join(cat.patterns)}; "
                         f"muscles: {', '.join(cat.muscles)})")
    try:
        request = {"goal": args.goal, "minutes": args.minutes, "level": args.level, "target": target,
                   "limits": [screen.parse_limit(x, cat) for x in args.limit],
                   "avoid": catalog.avoid_set(cat, screen.words(args.avoid))}
        if args.add:
            request["add"] = catalog.equipment_keys(cat, screen.words(args.add))
        if args.kit:
            kits = context.kits(profile)
            if args.kit not in kits:
                raise ValueError(f"unknown kit \"{args.kit}\" (kits in the profile: {', '.join(kits) or 'none'})")
            request["kit"] = args.kit
        elif args.preset:
            catalog.kit_equipment(cat, {"preset": args.preset})   # an unknown preset names the choices
            request["preset"] = args.preset
        else:
            request["equipment"] = catalog.equipment_keys(cat, screen.words(args.equipment))
    except ValueError as e:   # only the flags' own values are read here
        raise _usage(e) from None
    return request


EVAL_OUT = os.path.join(paths.ROOT, "docs", "eval", "out")   # the maintainer's eval grid (git-ignored; briefs.sh)


def _save_target(save):
    """--save's path, which must sit in the workouts folder (a workout's own folder, or checks/), or in the eval
    grid's output folder: the brief and menu are written nowhere else. Anything else is cli.Usage (exit 64)."""
    if not save:
        return None
    where = os.path.normcase(os.path.realpath(os.path.dirname(os.path.abspath(save))))
    for root in (paths.WORKOUTS, EVAL_OUT):
        root = os.path.normcase(os.path.realpath(root))
        if where == root or where.startswith(root.rstrip(os.sep) + os.sep):
            return save
    raise _usage(f"--save must name a draft in {paths.show(paths.WORKOUTS)} (in its own folder, "
                 f"<stem>/<stem>.draft.txt), not {save}")


if __name__ == "__main__":
    sys.exit(cli.run(main))
