"""Today's menu, and the build's check that a draft scripts nothing else.

`./harmonicfitness brief --save <stem>` writes `<stem>.menu.json` beside the draft: the request and every
movement `catalog.select` allowed today, healthy-side-only ones with the side to work. The draft
declares what it scripts on a `movements:` line (draft.py), and `check` finds:
- issues (the build stops): no menu, or one that isn't shaped like one (validate); a movement on it the
  safety screen, run again from its request and the current health.md, doesn't allow (rescreen, on a
  render); a declared movement that isn't on it or isn't a movement at all; nothing declared; the
  text naming a catalog movement that isn't on the menu; segments that don't add up to the request's seconds;
- warnings: the text naming a menu movement the declaration leaves out (add it, so the log has it).

The text is scanned for every name and alias, longest first, so "single-leg glute bridge" isn't also
read as "glute bridge", except the one-word aliases in EVERYDAY (squat, swing, curl, plank): they are
everyday coaching words ("swing your arms"), or words a filler story uses ("skiing"), and the
declaration is what the build checks. A shortened name of a declared movement ("the bench press" for
the dumbbell bench press) counts as that movement. A mention right after "no", "not", "skip",
"instead of" or "like", with only small words such as "the" or "doing" between, isn't an instruction
("no neck rolls today", "we're not doing jumping jacks", "like a brisk walk"); "no rest between
jumping jacks" is.
The [unlisted] names (catalog.Catalog.unlisted: "pistol squat", "muscle-up", a bare "lunges") are
real movements the catalog doesn't hold, so never on a menu: mentions yields each as ("unlisted", ...) and
check refuses it, unless it's a shortened name of a declared movement ("lunges" after a reverse lunge).
A movement the menu allows on one side only keeps to that side (side_issues, per segment): a segment that
names it may hold no both-sides or switch phrase (BOTH_SIDES: "each side", "switch", "the other arm"...) and
no turn to the other side, with its name or without ("then the left", "ten a side"): those tell the listener
to work the side that rests, so they stop the build. A word for the other side in a sentence about its care
("the right arm rests by your side", "keeping off that right shoulder": RESTING) is only a warning; refusing
those failed nearly every first draft (0.69.1's bench).
The opening says the session was written by AI (ai_problems) and, under a one-sided limit, names the side with
its body part (opening_problems); a sentence there that seems to tie the care to the other side, and a heavy
load beside a movement that loads a limited area (load_problems), are warnings. The listener has heard the
rules and that it's made by AI; the build stops only what would have them do something unsafe.
Library only; the brief and the build call it; the web's show_plan uses side_problems and part_of.
"""
import datetime
import hashlib
import os
import re
from typing import Dict, List, Optional, Tuple

import catalog
import errors
import draft
import paths

FORMAT = 2   # 2 (0.13.0): health_sha256, so the build knows the menu was made from today's health.md
UNLISTED = "unlisted"   # the id menu.mentions gives an [unlisted] name: a real movement the catalog doesn't hold
EFFORT_WORDS = {"easy", "steady", "hard", "brisk", "light", "slow", "quick", "fast", "gentle"}


def record(request: dict, sel: catalog.Selection, sides: Dict[str, str], seconds: int, date: str,
           health_sha256: Optional[str] = None) -> dict:
    """The menu file's contents: the request, the day, a hash of health.md as the brief read it, and every
    movement allowed."""
    def entry(m, side=None):
        out = {"id": m.id, "name": m.name, "aliases": list(m.aliases)}
        if side:
            out["side"] = side
        return out
    return {"format": FORMAT, "date": date, "health_sha256": health_sha256, "request": request, "seconds": seconds,
            "movements": [entry(m) for m in sel.allowed] + [entry(m, sides.get(m.id, "healthy"))
                                                            for m in sel.healthy_side_only]}


def health_hash(path: Optional[str] = None) -> Optional[str]:
    """sha256 of health.md's bytes (the limits and the clinician's rules), or None when there's no such file."""
    path = path or paths.HEALTH
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def staleness(menu: dict, today: Optional[str] = None, health_path: Optional[str] = None) -> List[str]:
    """Why this menu can't stand for today: it was saved another day (a check-in's limit for today lives only
    in the menu), health.md is gone, or it has changed since the brief read it. Empty when it can."""
    today = today or datetime.date.today().isoformat()
    out = []
    if menu.get("date") != today:
        out.append(f"the menu is from {menu.get('date') or 'an unknown day'}, not today ({today}): rerun "
                   "./harmonicfitness brief ... --save <the draft's path>, so today's limits apply")
    current = health_hash(health_path)
    if current is None:   # the brief refuses to run without one, so the file went missing since
        out.append(f"no health.md at {paths.show(health_path or paths.HEALTH)}: run ./harmonicfitness setup, then "
                   "./harmonicfitness brief ... --save <the draft's path>")
    elif not menu.get("health_sha256"):
        out.append("the menu predates the brief's health check: rerun ./harmonicfitness brief ... --save <the draft's path>")
    elif menu["health_sha256"] != current:
        out.append("health.md changed since the brief read it: rerun ./harmonicfitness brief ... --save <the draft's path>, "
                   "so the menu follows the new limits")
    return out


def validate(obj) -> List[str]:
    """What's wrong with a menu file's shape, as sentences (empty when it's sound): the format this version
    writes, an ISO date, a request table, the seconds as a whole number above zero, and the movements as a
    list of {"id": str, optional "side": str}. Every reader checks this before it indexes into a menu."""
    if not isinstance(obj, dict):
        return ["it isn't a menu (not a JSON object)"]
    out = []
    if obj.get("format") != FORMAT or isinstance(obj.get("format"), bool):
        out.append(f"it has format {obj.get('format', 'none')}, from an older brief; this version reads format {FORMAT}")
    date = obj.get("date")
    try:
        datetime.date.fromisoformat(date)
    except (TypeError, ValueError):
        out.append(f"its date ({date!r}) isn't YYYY-MM-DD")
    if not isinstance(obj.get("request"), dict):
        out.append("it has no request table")
    seconds = obj.get("seconds")
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
        out.append(f"its seconds ({seconds!r}) aren't a whole number above zero")
    moves = obj.get("movements")
    if not isinstance(moves, list):
        out.append("its movements aren't a list")
    else:
        for n, e in enumerate(moves, 1):
            if not isinstance(e, dict) or not isinstance(e.get("id"), str):
                out.append(f"movement {n} has no id")
            elif "side" in e and not isinstance(e["side"], str):
                out.append(f"movement {n} ({e['id']}) has a side that isn't a word")
    return out


def rescreen(cat: catalog.Catalog, menu: dict, health_path: Optional[str] = None) -> List[str]:
    """The movements this menu lists that the safety screen, run again now, doesn't allow: one issue each
    (or one for the side, when a healthy-side-only movement's side isn't the screen's). One screen pass,
    from the menu's request, the current health.md, profile and catalog. Only additions are refused: a menu
    narrower than the screen passes.

    What it proves: health.md's [[limits]] rows and Avoid: lines, and the profile's dislikes, are read again
    from the files, so a hand-edited menu can't put back a movement they rule out, and a request can only
    tighten them. What it trusts: the request's own fields (goal, minutes, kit, preset, equipment, add,
    level, target, its added limits and avoids) as the brief wrote them; it shows the movements follow from
    the request, not that the request is the one the listener made."""
    import context
    import health
    import screen
    import sessions
    req = menu["request"]
    path = health_path or paths.HEALTH
    try:
        h = health.health(path)
        own = {f"{lim.area}={lim.level}:{lim.side}" for lim in health.limits(h, cat.areas, cat.flags)}
        request = {k: req[k] for k in ("goal", "minutes", "kit", "preset", "equipment", "add", "level", "target")
                   if k in req}
        # health.md's own rows were saved into the request's limits too; they're read again from the file
        # (with their rehab exemptions), so only the ones the request added are taken from the menu
        request["limits"] = [screen.parse_limit(s, cat) for s in req.get("limits") or [] if s not in own]
        request["avoid"] = set(req.get("avoid") or ())
        scr = screen.screen(request, cat, sessions.load().goals, context.profile(), h)
    except (ValueError, TypeError, screen.Unfit, errors.ContextError) as e:
        return [f"the menu's request can't be screened again ({e}): rerun ./harmonicfitness brief ... --save "
                "<the draft's path>"]
    allowed = {m.id for m in scr.sel.allowed}
    sides = {m.id: screen.healthy_side(m, scr.limits) for m in scr.sel.healthy_side_only}
    out = []
    for e in menu["movements"]:
        mid, side = e["id"], e.get("side")
        if mid in allowed or (side is not None and sides.get(mid) == side):
            continue
        if mid in sides:
            out.append(f"the menu lists {mid} for {'both sides' if side is None else f'the {side} side'}, but "
                       f"today's screen allows only the {sides[mid]} side: rerun ./harmonicfitness brief ... --save "
                       "<the draft's path>")
        else:
            out.append(f"the menu lists {mid}, which today's screen doesn't allow: rerun ./harmonicfitness brief ... "
                       "--save <the draft's path>")
    return out


def report_lines(draft_path: str, issues: List[str], warnings: List[str], declared: int) -> List[str]:
    """The menu check as the lint and the build print it."""
    if issues or warnings:
        return [f"\nMenu check ({paths.show(os.path.abspath(draft.menu_path(draft_path)))}):"] \
            + [f"  {i}" for i in issues] + [f"  warning: {w}" for w in warnings]
    return [f"\nMenu check: every movement is on today's menu ({declared} declared)."]


def gate(cat: catalog.Catalog, draft_path: str, text: str, segments, today: Optional[str] = None,
         health_path: Optional[str] = None, strict: bool = True, required: bool = True) -> Tuple[List[str], List[str]]:
    """(issues, warnings) for a draft against the menu beside it: the one entry point the build, the render and
    the lint use. No menu is an issue when `required`; a menu that can't be read, or isn't shaped like one
    (validate), is one too; a stale menu (staleness) is an issue when `strict` (a render) and a warning
    otherwise (a lint). When `strict` and the menu is current, the safety screen runs again (rescreen), so a
    movement added to the menu by hand is refused."""
    path = draft.menu_path(draft_path)
    if not os.path.exists(path):
        return check(cat, None, text, segments) if required else ([], [])
    try:
        menu = load(path)
    except (OSError, errors.ContextError) as e:
        return ([f"the menu beside the draft can't be read ({os.path.basename(path)}: {e}): rerun ./harmonicfitness brief "
                 "... --save <the draft's path>"], [])
    shape = validate(menu)
    if shape:
        return ([f"the menu beside the draft ({os.path.basename(path)}) won't do: {p}; rerun ./harmonicfitness brief ... "
                 "--save <the draft's path>" for p in shape], [])
    issues, warnings = check(cat, menu, text, segments)
    stale = staleness(menu, today, health_path)
    if strict:
        issues += stale or rescreen(cat, menu, health_path)
    else:
        warnings += stale
    return issues, warnings


def write(path: str, menu: dict) -> None:
    import fileio
    fileio.write_json(path, menu)


def load(path: str) -> Optional[dict]:
    """The menu at `path`, or None when there is none; ContextError, naming the file, when it can't be read
    or isn't a JSON object (validate checks what it holds)."""
    import fileio
    try:
        return fileio.read_json(path)
    except FileNotFoundError:
        return None


def _norm(text: str) -> str:
    return catalog.plain(text, hyphens=True)


# one-word aliases left out of the scan: coaching cues ("swing your arms", "press through the heels") or
# words a filler story uses ("skiing season", "the Sphinx"); every other one-word alias is scanned
EVERYDAY = {"squat", "swing", "curl", "plank", "bridge", "run", "march", "marching", "stairs", "row", "press",
            "shuffles", "windmill", "halo", "halos", "skiing", "clams", "bicycles", "sphinx", "walk", "step"}


def _patterns(cat: catalog.Catalog) -> List[Tuple[re.Pattern, str, str]]:
    """(regex, movement id, the name it matches) for every name and alias the text scan checks,
    longest first; built once per catalog object and kept on it."""
    cached = cat.__dict__.get("_menu_patterns")
    if cached is not None:
        return cached
    found = {}
    for m in cat.movements.values():
        for name in [m.name] + m.aliases:
            key = _norm(name)
            if key in EVERYDAY and name != m.name:
                continue   # an everyday coaching word (squat, swing, curl, plank)
            found.setdefault(key, (m.id, name))
    for name in cat.unlisted:   # after every movement, so a private movement of that name wins; matched from
        key = _norm(name)       # the singular, so "lunges" also catches "a lunge" and "pistols" "pistol"
        found.setdefault(key[:-1] if key.endswith("s") and not key.endswith("ss") else key, (UNLISTED, name))
    # "push up" and "step up" are cues as often as names: when a hyphenated name has the same words,
    # only the hyphenated spelling counts
    found = {k: v for k, v in found.items() if not (" " in k and "-" not in k and k.replace(" ", "-") in found)}
    # "easy rows", "a brisk walk", "a steady ride" describe effort as often as they name a movement;
    # an effort word stays a name only before equipment ("steady bike", "steady rowing")
    gear = {w for e, info in cat.equipment.items() for name in [e] + info.get("aliases", [])
            for w in _norm(name).replace("-", " ").split()}
    found = {k: v for k, v in found.items()
             if not (len(k.split()) == 2 and k.split()[0] in EFFORT_WORDS and k.split()[1] not in gear)}
    out = []
    for key in sorted(found, key=len, reverse=True):
        words = key.split(" ")
        if len(words) > 1:   # "single-leg glute bridge" also matches "single leg glute bridge"
            body = r"[\s-]+".join(re.escape(w).replace(r"\-", r"[\s-]?") for w in words[:-1])
            body += r"[\s-]+" + _plural(re.escape(words[-1]).replace(r"\-", r"[\s-]?"))
        elif "-" in key:     # push-up keeps its hyphen ("push up through the heels" is a cue), but the spaced
            body = _plural(re.escape(key)) + "|" + re.escape(key).replace(r"\-", r"\s+") + r"e?s"   # plural is a name
        else:                # a one-word name of its own (deadlift, thruster)
            body = _plural(re.escape(key))
        out.append((re.compile(r"(?<![a-z'-])(?:" + body + r")(?![a-z'-])"), *found[key]))
    cat.__dict__["_menu_patterns"] = out
    return out


def _plural(word: str) -> str:
    """A name's last word (escaped) with its plural: "carry" also "carries", "lunge" "lunges", "press" "presses"."""
    if len(word) > 1 and word.endswith("y") and word[-2] not in "aeiou":
        return word[:-1] + r"(?:y|ies)"
    return word + r"(?:e?s)?"


def mentions(cat: catalog.Catalog, text: str) -> List[Tuple[str, str, str]]:
    """(movement id, the words used, the few words before them) for every time the spoken text names
    a catalog movement, in order; an [unlisted] name's id is UNLISTED ("unlisted")."""
    text = " ".join(catalog.fold(text).split())
    original, hits = text, []
    for rx, mid, _ in _patterns(cat):
        for m in rx.finditer(text):
            if VERB_USE.match(original, m.end()) and m.group(0).endswith("s"):
                continue   # "the weight at your chest presses on the ribs": a verb, not a set of chest presses
            hits.append((m.start(), mid, m.group(0)))
        text = rx.sub(lambda m: " " * len(m.group(0)), text)   # a longer name keeps its words
    return [(mid, words, " ".join(re.findall(r"[a-z']+", _clause(original[max(0, at - 60):at]))[-BEFORE:]))
            for at, mid, words in sorted(hits)]


def _clause(text: str) -> str:
    """The end of `text` after its last sentence or clause break, so a "not" in the sentence before can't
    excuse a mention ("Do not rest. Box jumps")."""
    return re.split(r"[.!?;:,]", text)[-1]


BEFORE = 6   # words kept before a mention, within its clause
# a name's plural used as a verb on a body part ("the bell presses on the ribs", "the strap pulls against your
# neck"): never an instruction to do the movement, whatever a set of it might be called
VERB_USE = re.compile(r"\s+(?:on|into|onto|against|through|down on|in on)\s+(?:the|your|my|that|this|his|her|their)?\s*"
                      r"(?:ribs?|rib cage|ribcage|chest|sternum|breastbone|collarbone|knees?|shoulders?|hips?|back|"
                      r"spine|belly|stomach|neck|wrists?|elbows?|arms?|legs?|feet|foot|hands?|it|them)\b")
# a mention right after one of these isn't an instruction: "no neck rolls today", "like a brisk walk"
NOT_DOING = {"no", "not", "never", "skip", "skipping", "without", "instead", "avoid", "nothing", "like",
             "unlike", "rather", "isn't", "aren't", "won't", "don't", "doesn't", "didn't", "can't", "wasn't",
             "weren't", "shouldn't", "couldn't", "wouldn't"}   # the web contracts "does not" and the rest
# small words allowed between the negation and the mention: "not doing the jumping jacks", "instead of
# burpees", "rather than burpees" ("no more than ten push-ups" still counts: "ten" isn't one)
FILLER = {"a", "an", "the", "any", "more", "your", "doing", "do", "of", "than", "using", "use"}   # "not using the"


def negated(before: str) -> bool:
    """True when the words before a mention end in a negation, with only FILLER after it: "no burpees",
    "not doing the jumping jacks"; not "no rest between jumping jacks" or "do not stop your high knees"."""
    for word in reversed(before.split()):
        if word not in FILLER:
            return word in NOT_DOING
    return False


def part_of(cat: catalog.Catalog, words: str, names: List[str], declared: set) -> bool:
    """True when `words` (say "bench presses") are a shortened form of one of `names` ("dumbbell bench press")
    and name no other movement: "push-ups" after a declared wall push-up is the push-up, not a short form."""
    other = catalog.resolve(cat, words)
    if other is not None and other.id not in declared:
        return False
    key = _norm(words).replace("-", " ")
    forms = {key, key[:-1] if key.endswith("s") else key, key[:-2] if key.endswith("es") else key}
    return any(f" {form} " in f" {_norm(n).replace('-', ' ')} " for form in forms for n in names)


def short_for(words: str, said: List[str]) -> bool:
    """True when `words` ("split squats", "deadlift") end the full name of exactly one declared movement the same
    segment already said in full (`said`: "Bulgarian split squat", "romanian deadlift"): once the listener has heard
    the full name, its tail names that movement, even when the tail alone is another one."""
    key = _norm(words).replace("-", " ")
    forms = {key, key[:-1] if key.endswith("s") else key, key[:-2] if key.endswith("es") else key}
    hits = {n for n in said for form in forms if f" {_norm(n).replace('-', ' ')}".endswith(f" {form}")
            and _norm(n).replace("-", " ") != form}
    return len(hits) == 1


SIDES = ("left", "right", "both", "healthy")   # a menu entry's side, and the side words a name may carry
# words that put a movement on both sides (compared as catalog.plain words, so "per-side" is "per side")
# ("left/right", "left-right" and "l/r" become "left right" and "l r"; "switch" covers "switch sides")
BOTH_SIDES = ("each side", "both sides", "each leg", "both legs", "each arm", "both arms", "per side", "per leg",
              "per arm", "alternating", "alternate", "left and right", "right and left", "either side",
              "every side", "every leg", "every arm", "other side", "other leg", "other arm", "opposite side",
              "opposite leg", "opposite arm", "switch", "swap sides", "repeat on the other", "bilateral",
              "two sides", "each hip", "per limb", "left right", "right left", "l r", "r l", "r and l", "l and r")
# not a comma, a colon or a parenthesis: "Right single-leg glute bridge: ten (each side)." is one sentence
SENTENCE = re.compile(r"[.!?;\n]")


NUMBER_WORDS = "|".join(["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
                          "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
                          "nineteen", "twenty", "thirty", "forty", "fifty", "sixty", "a few", "some"])
# words that name the limited side without saying left or right ("the injured leg", "the weaker side")
HURT_SIDE = re.compile(r"\b(?:injured|sore|bad|hurt|weak|weaker|non working|affected|painful) "
                       r"(?:leg|side|arm|foot|knee|hip|hand|shoulder|ankle|wrist|elbow)s?\b")


def turn_to(text: str, side: str) -> Optional[str]:
    """The words in `text` that turn to the other side without naming it ("change legs", "the other one",
    "ten a side") or naming it in a turn ("then the left"), or None. Every word naming another side is caught
    by opposite_side; this keeps the forms with no side word. For "healthy", either side is another one."""
    padded = f" {catalog.plain(text)} "
    for rx in (r" (?:change|swap|switch|trade) (?:the )?(?:legs|sides|arms|feet|hands|over) ", r" (?:the )?other one ",
               r" the other ", rf" (?:{NUMBER_WORDS}) a side ", r" per side ", r" second (?:leg|side|arm) ",
               r" (?:flip|turn) around ", r" mirror ", r" apiece ", r" with each ", r" do the opposite "):
        m = re.search(rx, padded)
        if m:
            return m.group(0).strip()
    m = re.search(r"\d+\s+a\s+side\b", catalog.fold(text))   # "10 a side" (plain drops the digits)
    if m:
        return m.group(0)
    return None


def _cue_sentences(cat: catalog.Catalog) -> set:
    """Every shipped limit cue's sentences, and the playbook's opening, reason and stop-sign lines, catalog.plain,
    with {side} filled in as the brief fills it: the sentences a segment may say that name the injured side."""
    cached = cat.__dict__.get("_cue_sentences")
    if cached is None:
        import playbook
        lines = [line for levels in cat.limit_cues.values() for group in levels.values() for line in group]
        # and the playbook's lines the brief has the coach say for a limit (its opening, its reason to say): the
        # opening check asks for the opening's line, so a welcome that also names the one-sided movement may say it
        lines += [text for a in playbook.shipped().areas.values() for lv in a.levels.values()
                  for text in (lv.opening, lv.say) if text]
        # and its stop signs, in the forms the brief and the guide give them: script.md has an area's stop signs
        # said at its first working set, often the healthy side's movement, and a line saying when to stop names
        # the resting side without turning the work to it (0.59.0)
        for a in playbook.shipped().areas.values():
            for lv in a.levels.values():
                for sign in lv.stop:
                    lines += [f"Stop that movement on {sign}.", f"Stop that move on {sign}.", f"{sign} means stop that move."]
                for sign in lv.stop_today:
                    lines += [f"Stop for today on {sign}.", f"{sign} means we stop for today."]
        cached = {catalog.plain(sentence) for line in lines for word in ("left", "right", "injured", "sore")
                  for sentence in SENTENCE.split(line.replace(catalog.SIDE_SLOT, word)) if sentence.strip()}
        cat.__dict__["_cue_sentences"] = cached
    return cached


# a sentence about the resting side's care, not a turn to it: "the right arm rests by your side", "down to the floor
# without loading that right arm", "notice how that right shoulder feels". A turn word there doesn't send the work over.
RESTING = re.compile(r"\b(?:rest|rests|resting|keep\w* (?:\w+ ){0,3}off|stays?|out of (?:it|the work|this|harm)|by your "
                     r"side|in your lap|sits? (?:this one|it) out|light|easy|gentle|protect\w*|sore|tender|"
                     r"delicate|injured|without|limp|relax\w*|loose|quiet|soft|still|calm|zero|no (?:weight|load|"
                     r"pressure)|feels?|careful\w*|healthy|helps?)\b", re.IGNORECASE)


def opposite_side(cat: catalog.Catalog, text: str, side: str) -> Optional[str]:
    """The first word in `text` naming a side other than `side` ("left" when the right is allowed; either
    for "healthy"; "the injured leg", "the weaker side" for any),  outside a sentence that is one of the shipped limit cues with its side filled in, or
    None. Structural, so it fails safe: any turn to the other side says its name ("repeat with the left
    leg", "next, left"), and only the limit cues may say it."""
    opp = {"left", "right"} - {side}
    cues = _cue_sentences(cat)
    for sentence in SENTENCE.split(text):
        words = catalog.plain(sentence)   # plain makes "non-working" "non working"
        hurt = HURT_SIDE.search(words)
        hit = next((w for w in words.split() if w in opp), None) or (hurt.group(0) if hurt else None)
        if hit and words not in cues:
            return hit
    return None


def _phrase(text: str, phrases) -> Optional[str]:
    padded = f" {catalog.plain(text)} "
    return next((w for w in phrases if f" {w} " in padded), None)


def _say(side: str) -> str:
    return "healthy side" if side == "healthy" else f"{side} side"


def name_side_problem(name: str, side: str) -> Optional[str]:
    """Why a name for a movement the menu allows on one side only ("right single-leg glute bridge") doesn't
    hold that side, or None. The name's words (catalog.plain) must include the menu's side ("left", "right",
    or "healthy" when the limit named no side) and no other side word. catalog.resolve has already matched
    the movement with a leading side word dropped; this says whether that side is the one allowed."""
    words = set(catalog.plain(name).split())
    named = words & set(SIDES)
    if side in words and named == {side}:
        return None
    if named - {side}:
        return f'"{name}" names the {", ".join(sorted(named - {side}))} side, but today\'s menu allows it on the {side} side only'
    say = "healthy side" if side == "healthy" else side
    return f'"{name}" is allowed on the {side} side only today; name the side (say "{say} {name}")'


def side_problems(cat: catalog.Catalog, on_menu: dict, text: str) -> List[str]:
    """Every side problem side_issues finds, stops and warnings alike (the web's show_plan, the tests)."""
    stops, warns = side_issues(cat, on_menu, text)
    return stops + warns


def side_issues(cat: catalog.Catalog, on_menu: dict, text: str) -> Tuple[List[str], List[str]]:
    """What puts a movement the menu allows on one side only (on_menu: id -> menu entry, its "side" set) on
    another side or both, in one segment's text (or one plan field's), one problem per movement, as (stops,
    warnings). Every sentence of a segment that names one is read (a side word meant for something else in the
    same segment counts too; the writer splits the segment):
    - a stop: a dose or turn for both or either side (HARD: "ten each side", "switch", "alternating", turn_to's
      "change legs" and "ten a side"), or any sentence naming the other side or both ("then the left", "ten more
      on the left", "with both arms", "the other arm next") that isn't about its rest (RESTING);
    - a warning: a word for the other side, or for both, in a sentence about its rest ("the right arm rests by
      your side", "down without loading that right arm", "notice how that right shoulder feels"): the resting
      side's care, whose refusal failed nearly every first draft (0.69.1's bench).
    "Right single-leg glute bridge. Ten each side." stops; so does "Right single-leg glute bridge, ten. Then
    the left."; "Right single-leg glute bridge; the left leg rests" warns."""
    stops, warns, done = [], [], set()
    text = remaining_idioms(text)
    sentences = [x for x in SENTENCE.split(text) if x.strip()]
    named = []
    for sentence in sentences:
        for mid, _, _ in mentions(cat, sentence):
            side = (on_menu.get(mid) or {}).get("side") if mid in cat.movements else None
            if side and mid not in named:
                named.append(mid)
    for mid in named:
        side = on_menu[mid]["side"]
        name = cat.movements[mid].name
        hard = soft = None
        for sentence in sentences:
            how, strict = _other_side(cat, sentence, side)
            if how and strict and hard is None:
                hard = (sentence, how)
            elif how and soft is None:
                soft = (sentence, how)
        for found, bucket in ((hard, stops), (None if hard else soft, warns)):
            if found and mid not in done:
                done.add(mid)
                sentence, how = found
                bucket.append(f'"{" ".join(sentence.split())}" puts {name} on {how}, but today\'s menu allows it '
                              f"on the {_say(side)} only; keep that segment to the {_say(side)}")
    return stops, warns


# both sides or either, in a dose or a turn: never the resting side's care
HARD = ("each side", "each leg", "each arm", "per side", "per leg", "per arm", "per limb", "each hip", "alternating",
        "alternate", "switch", "swap sides", "repeat on the other", "either side", "every side", "every leg",
        "every arm", "two sides", "bilateral")
def _other_side(cat: catalog.Catalog, sentence: str, side: str) -> Tuple[Optional[str], bool]:
    """(the words in `sentence` naming another side or both, whether they send the work there), or (None, False).
    A shipped limit cue or stop sign (opposite_side's exception) names the resting side and is fine."""
    hard = _phrase(sentence, HARD)
    if hard:
        return f'"{hard}"', True
    turn = turn_to(sentence, side)
    if turn and turn not in ("the other", "the other one"):
        return f'"{turn}"', True
    other = _phrase(sentence, BOTH_SIDES) or turn or opposite_side(cat, sentence, side)
    if not other:
        return None, False
    how = f"the {other} side" if other in SIDES else f'"{other}"'
    return how, not RESTING.search(sentence)


def spoken_text(segments) -> str:
    """Every segment's coaching text (what lies outside [story] ... [/story]), as the menu scan reads it."""
    return " ".join(draft.story_split(seg)[0] for seg in segments)


# "two left in the tank", "five seconds left": "left" meaning what remains, never a side, so the one-side check
# reads past it (a turn to the other side always names it some other way: "then the left", "left leg next")
REMAINING = re.compile(r"\bleft(?=\s+(?:in\s+the\s+tank|in\s+reserve|to\s+go|in\s+you)\b)"
                       r"|\b((?:rep|second|minute|round|set|breath)s?)\s+left\b", re.IGNORECASE)


# "hold steady right there", "right now", "all right": "right" meaning just or correct, never a side
RIGHT_IDIOM = re.compile(r"\b(?:all right|that's right|right (?=(?:there|here|now|away|back|after|before|through|into|"
                         r"on time|at the|where|when|then|as|about|up to|over|to the end|off the bat)\b))",
                         re.IGNORECASE)


def remaining_idioms(text: str) -> str:
    """`text` with each "left" that means what remains written "remaining", and each "right" that means just or
    correct taken out, for the one-side check."""
    text = REMAINING.sub(lambda m: f"{m.group(1)} remaining" if m.group(1) else "remaining", text)
    return RIGHT_IDIOM.sub("", text)


# a sentence in a story speaking to the listener ("you", "let's") reads as coaching, not as the story
ADDRESS = re.compile(r"\b(?:you|your|you're|you'll|let's|we'll|we're)\b", re.IGNORECASE)


def story_problems(cat: catalog.Catalog, on_menu: dict, stories: List[str]) -> List[str]:
    """Issues in a segment's stories: a sentence that names a movement off today's menu (or one the catalog
    doesn't hold) while speaking to the listener reads as an instruction, story or not."""
    out = []
    for story in stories:
        for sentence in SENTENCE.split(story):
            if not ADDRESS.search(sentence):
                continue
            for mid, said, before in mentions(cat, sentence):
                if mid not in on_menu and not negated(before):
                    out.append(f'"{" ".join(sentence.split())}" names {said} inside a [story] while speaking to the '
                               "listener, which reads as an instruction, and it isn't on today's menu; tell it about "
                               "someone else, or take it out")
                    break
    return out


HEAVY = re.compile(r"\b(?:heavy|heavier|heaviest|max(?:imal)? (?:load|weight)s?|load (?:it|that|them) up|go big)\b",
                   re.IGNORECASE)


def _negated_heavy(before: str) -> bool:
    """"nothing heavy", "nothing too heavy", "not so heavy": a negation, past an intensifier or two."""
    words = before.lower().split()
    while words and words[-1].strip(",.") in ("too", "so", "very", "overly", "really", "that"):
        words.pop()
    return negated(" ".join(words))


def load_problems(cat: catalog.Catalog, menu: dict, segments) -> List[str]:
    """A segment's coaching that asks for a heavy load ("pick up a heavy pair") while naming a movement that loads
    one of today's limited areas: under a limit those stay light. One issue a segment; "nothing heavy" passes."""
    import screen
    limits = []
    for s in (menu.get("request") or {}).get("limits") or []:
        try:
            limits.append(screen.parse_limit(s, cat))
        except (ValueError, TypeError):
            continue
    if not limits:
        return []
    areas = {lim.area for lim in limits}
    sides = {e["id"]: e.get("side") for e in menu.get("movements", [])}

    def loaded(mid, mv, area):
        """Its load on `area`, as the brief marks it: a movement offered on the healthy side only, under limits on
        that area all on the other side, puts no load there (a heavy press for the healthy arm is fine)."""
        side = sides.get(mid)
        if side and all(lim.side == screen.OTHER_SIDE.get(side) for lim in limits if lim.area == area):
            return 0
        return mv.loads.get(area, 0)
    out = []
    named = [[mid for mid, _, _ in mentions(cat, draft.story_split(seg)[0] + " . " + seg["label"])] for seg in segments]
    for i, seg in enumerate(segments):
        coaching = draft.story_split(seg)[0]
        heavy = next((m for m in HEAVY.finditer(coaching) if not _negated_heavy(coaching[:m.start()])), None)
        if heavy is None:
            continue
        # the movement it's for: named here (or in the label); else the set it sets up next, or the one it follows
        near = named[i] or (named[i + 1] if i + 1 < len(segments) else []) + (named[i - 1] if i else [])
        for mid in near:
            mv = cat.movements.get(mid)
            hit = sorted(a for a in areas if mv is not None and loaded(mid, mv, a) >= 1)
            if hit:
                out.append(f'segment "{seg["label"]}" (line {seg["start"]}): "{heavy.group(0)}" with {mv.name}, which '
                           f"loads today's limited {', '.join(hit)}: keep it light (twelve to fifteen reps with three or "
                           "more in reserve) and say so")
                break
    return out


# words that tie a sentence to the sore side's care: "the right side stays light today"
CARE = re.compile(r"\b(?:light|easy|gentle|careful|sore|delicate|tender|injured|hurt\w*|protect\w*|off limits|"
                  r"sits? (?:this one|it) out)\b", re.IGNORECASE)


# the made-by-AI line, said in every opening: the reason the rest can trust the listener
AI_LINE = re.compile(r"\b(?:AI|A\.I\.|artificial intelligence)\b")


def ai_problems(segments) -> List[str]:
    """The opening (the first segment, stories aside) must say the session was made by AI. Nothing is asked of an
    opening with no words yet (a skeleton's), nor of a draft of one segment (a fragment, a test's), which has no
    opening apart from its work."""
    if len(segments) < 2:
        return []
    seg = segments[0]
    text = draft.story_split(seg)[0]
    if not re.search(r"[A-Za-z]", re.sub(r"\[[^\]]*\]", " ", text)) or AI_LINE.search(text):
        return []
    return [f'segment "{seg["label"]}" (line {seg["start"]}): the opening never says the session was made by AI; '
            'say it in a plain sentence near the rules ("This session was put together by AI, not a trainer or a '
            'clinician, so your body and your doctor have the final say.")']


def opening_problems(menu: dict, segments) -> List[str]:
    """Every opening problem opening_issues finds, stops and warnings alike."""
    stops, warns = opening_issues(menu, segments)
    return stops + warns


def opening_issues(menu: dict, segments) -> Tuple[List[str], List[str]]:
    """Under a one-sided limit, the opening (the first segment, stories aside) names the side with its body part
    ("left knee"), as the brief's opening line does, and no sentence there ties the limit's care to the other side
    ("the right side stays light"): told the wrong side, or none, a listener can load the sore one. One issue a
    limit, as (stops, warnings): an opening that never names the side stops the build; one that seems to tie the
    care to the other side is a warning, since a sentence about something else reads the same way."""
    import playbook
    import screen
    if not segments:
        return [], []
    pb = playbook.shipped()
    seg = segments[0]
    text = remaining_idioms(draft.story_split(seg)[0])
    if not re.search(r"[A-Za-z]", re.sub(r"\[[^\]]*\]", " ", text)):
        return [], []   # an opening with no words yet (a skeleton's): nothing said, so nothing to check
    stops, warns = [], []
    sided = []   # each one-sided limit: (its side, body part, playbook level, level name, how the opening names it)
    for s in (menu.get("request") or {}).get("limits") or []:
        area, _, rest = s.partition("=")
        level, _, side = rest.partition(":")
        if side not in screen.OTHER_SIDE:
            continue
        lv = pb.areas[area].levels.get(level) if area in pb.areas else None
        found = re.search(r"\{side\}\s+([a-z]+)", lv.opening) if lv else None
        part = found.group(1) if found else area.replace("-", " ")
        named = re.compile(rf"\b{side}(?:[\s-]+\w+)?[\s-]+{part}s?\b|\b{part}s?\b[^.!?\n]{{0,20}}\b{side}\b",
                           re.IGNORECASE)
        sided.append((side, part, lv, level, named))
    for side, part, lv, level, named in sided:
        said = (f'say the brief\'s opening line for it, every part kept: "{playbook._sided(lv.opening, level, side)}"'
                if lv and lv.opening else f"say which side, as the brief does: your {side} {part}")
        where = f'segment "{seg["label"]}" (line {seg["start"]})'
        other = screen.OTHER_SIDE[side]
        # a sentence naming another limit's own side and part ("the left knee stays light", under a left knee limit
        # and a right shoulder one) is that limit's care, not this one's on the wrong side
        theirs = [n for s2, _, _, _, n in sided if s2 == other]
        wrong = next((x.strip() for x in SENTENCE.split(text)
                      if re.search(rf"\b{other}\b", x, re.IGNORECASE) and CARE.search(x) and not named.search(x)
                      and not any(n.search(x) for n in theirs)), None)
        if wrong:
            (warns if named.search(text) else stops).append(f'{where}: "{wrong}" ties today\'s care to the {other} side, but the limit is the {side} {part}: '
                       + said)
        elif not named.search(text):
            stops.append(f"{where}: the opening never names the {side} {part}, the side today's limit is on: " + said)
    return stops, warns


def check(cat: catalog.Catalog, menu: Optional[dict], text: str, segments) -> Tuple[List[str], List[str]]:
    """(issues, warnings) for a draft's text and parsed segments against today's menu."""
    if menu is None:
        return (["no menu for this draft: run ./harmonicfitness brief ... --save <the draft's path> first, "
                 "so the build can check every movement against today's limits"], [])
    issues, warnings = [], []
    on_menu = {e["id"]: e for e in menu.get("movements", [])}
    words = draft.declared(text)
    if not words:
        issues.append("no movements: line before the first @@ marker; declare every movement the "
                      "script uses, from the brief's menu")
    declared = set()
    for word in words:
        m = catalog.resolve(cat, word.strip())
        if m is None:
            issues.append(f"declared \"{word}\" isn't a movement in the catalog; use its name from the menu")
        elif m.id not in on_menu:
            issues.append(f"declared \"{word}\" ({m.id}) isn't on today's menu; pick a movement the brief lists")
        else:
            declared.add(m.id)
    names = [n for i in declared for n in [cat.movements[i].name] + cat.movements[i].aliases]
    flagged, unlisted = set(), set()
    for seg in segments:   # segment by segment: a full name said there makes its tail the same movement
        said_full = []
        for mid, said, before in mentions(cat, draft.story_split(seg)[0]):
            if mid in declared:
                said_full.append(said)
                continue
            if short_for(said, said_full):
                continue   # "split squats" after "Bulgarian split squat" in the same segment
            if mid == UNLISTED:   # a real movement the catalog doesn't hold ("pistol squats")
                if _norm(said) in unlisted or part_of(cat, said, names, declared) or negated(before):
                    continue   # already said, "lunges" after a declared reverse lunge, or "no pistol squats"
                unlisted.add(_norm(said))
                issues.append(f'"{said}" isn\'t in the catalog, so it can\'t be on today\'s menu; use a movement '
                              'the brief lists')
                continue
            if mid in flagged or part_of(cat, said, names, declared):
                continue   # already said, or a shortened name of a declared movement
            if negated(before):
                continue   # "no neck rolls today"
            flagged.add(mid)
            if mid not in on_menu:
                issues.append(f"the script names \"{said}\" ({mid}), which isn't on today's menu; take it out or "
                              f"reword it (a \"no {said} today\" is fine, and so is a short name right after the full "
                              "one in the same segment)")
            else:
                warnings.append(f"the script names \"{said}\" ({mid}) but the movements: line doesn't; add it")
    for seg in segments:   # a one-sided movement keeps to its side, segment by segment; stories aside
        coaching, stories, tag_problems = draft.story_split(seg)
        where = f'segment "{seg["label"]}" (line {seg["start"]})'
        stops, warns = side_issues(cat, on_menu, coaching)
        for why in [f"{where}: {p}" for p in tag_problems + stops + story_problems(cat, on_menu, stories)]:
            if why not in issues:
                issues.append(why)
        warnings += [f"{where}: {p}" for p in warns if f"{where}: {p}" not in warnings]
    stops, warns = opening_issues(menu, segments)
    opening = menu.get("excerpt_from", 1) == 1   # a demo clip from mid-session (demos.excerpt) has no opening
    for why in stops + (ai_problems(segments) if opening else []):
        if why not in issues:
            issues.append(why)
    warnings += [w for w in warns + load_problems(cat, menu, segments) if w not in warnings]
    want = menu.get("seconds")
    total = sum(seg["seconds"] for seg in segments)
    if want and total != want:
        issues.append(f"the segments add up to {total} s, but the request is {want} s "
                      f"({want // 60} minutes): {'take' if total > want else 'add'} {abs(total - want)} s")
    return issues, warnings
