"""The home page's demo clips: seven invented listeners, each with one ask, built by the engine as any listener's
workout is, of which two minutes are rendered and published. docs/demos/index.html is the plan, docs/demos/demos.toml
the seven, and the `demos` skill the steps.

    ./harmonicfitness demos                                   # the seven, and how far each has got
    ./harmonicfitness demos home jo                           # ready docs/demos/listeners/jo/: its coach installed
                                                              # from docs/demos/coaches/, held to the set's model
    ./harmonicfitness demos run jo brief --goal general ...   # any command, as that listener
    ./harmonicfitness demos excerpt <full draft>              # its segments, numbered
    ./harmonicfitness demos excerpt <full draft> --from 3 --to 4   # those segments as a draft of their own, with
                                                              # the menu beside it: the only part rendered
    ./harmonicfitness demos publish jo <clip.mp3>             # to docs/demos/clips/jo.mp3 (git-ignored), for the bucket
    ./harmonicfitness demos upload                            # every staged clip and demos.json to the media bucket,
                                                              # as demos/v<version>/ (the bucket's keys in the shell)
    ./harmonicfitness demos web                               # web/client/src/demos.json: the sign-in page's copy

A demo listener's context folder is docs/demos/listeners/<slug>/ itself: invented, so it lives with the plan in the
engine, never in me/ (the real listener's). Its profile files, research, briefs, menus and drafts are committed; what
the engine generates there (audio caches, logs, MP3s, build records, the installed coach) is git-ignored. It has no
key file: `run` points the engine at the listener's own (paths.ENV_FILE, as this process sees it) through
HARMONICFITNESS_KEYS, so the key is read only by the engine and never copied. Each coach is one of the service's
stock voices, named by its voice ID in docs/demos/coaches/<name>.md, so nothing is designed.
"""
import os
import re
import subprocess
import sys
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context  # noqa: E402
import draft  # noqa: E402
import errors  # noqa: E402
import fileio  # noqa: E402
import menu  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
from paths import show  # noqa: E402

CLIP_SECONDS = (90, 150)   # a clip's segments add up to about two minutes: shorter says too little, longer won't be heard
# Commands a demo listener doesn't run: this one, the shell-only ones, and the ones that act on me/ as a whole.
NOT_AS_A_DEMO = ("demos", "setup", "doctor", "test", "backup", "pull", "sync")
ONE_SIDE = ("left", "right")


def manifest(path=None):
    """docs/demos/demos.toml, as a dict; ContextError when it's missing or isn't TOML."""
    path = path or os.path.join(paths.DEMOS, "demos.toml")
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise errors.ContextError(f"No demo manifest at {show(path)}.") from None
    except tomllib.TOMLDecodeError as e:
        raise errors.ContextError(f"{show(path)} isn't TOML: {e}") from None


def demo(slug, m=None):
    """The [[demo]] named `slug`; UsageError naming the seven when there's none."""
    m = m or manifest()
    for d in m.get("demo", []):
        if d.get("slug") == slug:
            return d
    names = ", ".join(d.get("slug", "?") for d in m.get("demo", []))
    raise errors.UsageError(f"No demo \"{slug}\" in docs/demos/demos.toml (there are: {names}).")


def home_of(slug):
    """A demo listener's context folder: docs/demos/listeners/<slug>/."""
    return os.path.join(paths.DEMOS, "listeners", slug)


def clips_dir():
    """Where finished clips wait for the bucket: docs/demos/clips/ (git-ignored)."""
    return os.path.join(paths.DEMOS, "clips")


def _coach_in(folder, name):
    """The coach called `name` in context folder `folder`'s coaches/, or None."""
    return personas.find(name, personas.all(os.path.join(folder, "coaches")))


def _made(p):
    return p is not None and p.is_web and not p.pending and bool(p.voice_id)


def _stock_coach(d):
    """The demo's coach file (docs/demos/<coach_file>) as a persona when it names a voice (voice_id: one of the
    service's own stock voices, the same on every account), else None (a coach to audition)."""
    path = os.path.join(paths.DEMOS, d.get("coach_file") or "")
    if not d.get("coach_file") or not os.path.isfile(path):
        return None
    p = context.persona(path)
    found = personas.Persona(os.path.splitext(os.path.basename(path))[0], os.path.dirname(path), p.settings, p.body)
    return found if found.voice_id else None


def make_home(slug, report=print):
    """Ready demo `slug`'s folder (docs/demos/listeners/<slug>/): its coach installed from its coach file, a stock
    voice (nothing designed), and held to the manifest's model. Returns the folder."""
    m = manifest()
    d = demo(slug, m)
    dst = home_of(slug)
    if not os.path.isfile(os.path.join(dst, "profile.md")):
        raise errors.ContextError(f"No listener folder at {show(dst)} for demo \"{slug}\".")
    coach = d.get("coach", "")
    here = _coach_in(dst, coach)
    if not _made(here):
        stock = _stock_coach(d)
        if stock is None:
            raise errors.CoachError(f"docs/demos/{d.get('coach_file') or 'coaches/<name>.md'} names no voice_id: a demo "
                                    "coach is one of the service's stock voices, chosen by ear.")
        target = personas.folder_for(coach, stock.settings.get("service", m.get("service", "elevenlabs")),
                                     folder=os.path.join(dst, "coaches"))
        fileio.atomic_write(os.path.join(target, "persona.md"), context.persona_text(stock.settings, stock.prose))
        report(f"Installed {coach} from docs/demos/{d['coach_file']}: a stock voice, nothing designed. Its sample and pace: "
               f"./harmonicfitness demos run {slug} coaches sample \"{coach}\".")
        here = _coach_in(dst, coach)
    model = m.get("model")
    if model and here.model != model:
        settings = dict(here.settings, model=model)
        fileio.atomic_write(here.path, context.persona_text(settings, here.prose))
        report(f"{coach} speaks with {model} in this demo.")
    return dst


def run_as(slug, argv):
    """Run `./harmonicfitness <argv>` as demo `slug`: its folder as the context, the listener's own key file.
    Returns the command's exit code."""
    demo(slug)
    if not argv:
        raise errors.UsageError("demos run <slug> <command> [options]: name the command to run.")
    if argv[0] in NOT_AS_A_DEMO:
        raise errors.UsageError(f"{argv[0]} isn't run as a demo listener.")
    folder = home_of(slug)
    if not os.path.exists(os.path.join(folder, "profile.md")):
        raise errors.UsageError(f"No demo folder at {show(folder)}: run ./harmonicfitness demos home {slug} first.")
    env = dict(os.environ, HARMONICFITNESS_HOME=folder, HARMONICFITNESS_KEYS=paths.ENV_FILE)
    return subprocess.call([sys.executable, os.path.join(paths.ROOT, "tools", "harmonicfitness.py"), *argv], env=env)


def _chunks(text):
    """(header, [segment text]): the lines before the first @@ marker, then each segment from its marker line to
    the next, as written."""
    header, chunks = [], []
    for line in text.splitlines(keepends=True):
        if draft.MARKER.match(line.strip()):
            chunks.append(line)
        elif chunks:
            chunks[-1] += line
        else:
            header.append(line)
    return "".join(header), chunks


def segments(draft_path):
    """[(number from 1, seconds, label)] for the draft's segments."""
    text = _read(draft_path)
    return [(n, seg["seconds"], seg["label"]) for n, seg in enumerate(draft.parse(text), 1)]


def _read(draft_path):
    try:
        with open(draft_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise errors.UsageError(f"No draft at {draft_path}.") from None


def excerpt(draft_path, first, last):
    """Segments `first` to `last` (from 1) of a full draft, as a draft of their own: `<stem>-clip/<stem>-clip.draft.txt`
    beside the draft's folder, its movements: line kept, and the full draft's menu beside it with the clip's seconds.
    Returns (the clip's draft path, its seconds)."""
    text = _read(draft_path)
    segs = draft.parse(text)
    if not 1 <= first <= last <= len(segs):
        raise errors.UsageError(f"--from {first} --to {last}: the draft has segments 1 to {len(segs)}, and --from comes first.")
    full_menu = menu.load(draft.menu_path(draft_path))
    if full_menu is None:
        raise errors.HarmonicFitnessError(f"No menu beside {draft_path}: the full draft's brief (--save) comes first, "
                                          "and the clip is checked against it.")
    sided = [s for s in (full_menu.get("request") or {}).get("limits") or [] if s.rpartition(":")[2] in ONE_SIDE]
    if sided and first != 1:
        raise errors.HarmonicFitnessError(f"Under a one-sided limit ({', '.join(sided)}) a clip starts at the opening, "
                                          "segment 1: the build checks that its first segment names the side.")
    header, chunks = _chunks(text)
    seconds = sum(seg["seconds"] for seg in segs[first - 1:last])
    name = os.path.basename(draft.stem(os.path.abspath(draft_path))) + "-clip"
    folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(draft_path))), name)
    out = os.path.join(folder, name + draft.DRAFT_SUFFIX)
    body = "".join(chunks[first - 1:last])
    fileio.atomic_write(out, header + body if body.endswith("\n") else header + body + "\n")
    menu.write(draft.menu_path(out), dict(full_menu, seconds=seconds))
    return out, seconds


def publish(slug, mp3):
    """Copy a demo's rendered clip to docs/demos/clips/<slug>.mp3 (git-ignored), where it waits for the media
    bucket the home page plays from; returns where it went."""
    demo(slug)
    if not mp3.lower().endswith(".mp3") or not os.path.isfile(mp3):
        raise errors.UsageError(f"No MP3 at {mp3}.")
    dst = os.path.join(clips_dir(), slug + ".mp3")
    fileio.atomic_copy(mp3, dst)
    return dst


# The request's blanks, as the app's own lists offer them (web/client/src/zones/Starter.tsx: TYPES, ROWS and SIDED;
# test_demos holds them in step). A place is kitWords' words for a kit, which depend on the listener's kits.
REQUEST_TYPES = ("full-body workout", "strength workout", "cardio workout", "mobility session", "leg workout",
                 "upper-body workout", "core workout")
BODY_ROWS = ("neck", "shoulder", "elbow", "wrist", "rib", "low back", "hip", "groin", "hamstring", "knee", "calf",
             "ankle", "foot")
SIDED = ("foot", "ankle", "calf", "knee", "hamstring", "hip", "groin", "rib", "shoulder", "elbow", "wrist")
CARE = ("none", "easy", "off")


def request_problems(d):
    """What's wrong with a demo's [demo.request], as sentences (none: it reads as the app would write it)."""
    r = d.get("request") or {}
    slug = d.get("slug", "?")
    out = []
    if r.get("type") not in REQUEST_TYPES:
        out.append(f"{slug}: request type {r.get('type')!r} isn't one the app offers ({', '.join(REQUEST_TYPES)}).")
    place = r.get("place", "")
    if not (place == "at home" or place.startswith(("in a ", "at the ", "with no equipment"))
            or (place.startswith("with my ") and place.endswith(" kit"))):
        out.append(f"{slug}: request place {place!r} isn't how the app words a kit.")
    if not re.fullmatch(r"right now|at \d{1,2}:\d\d [AP]M|tomorrow at \d{1,2}:\d\d [AP]M", r.get("when", "")):
        out.append(f"{slug}: request when {r.get('when')!r} should be \"right now\" or a time (\"at 6:30 AM\").")
    care, area = r.get("care"), r.get("area", "")
    if care not in CARE:
        out.append(f"{slug}: request care {care!r} should be none, easy or off.")
    elif care != "none":
        side, _, base = area.partition(" ") if area.split(" ", 1)[0] in ("left", "right") else ("", "", area)
        if base not in BODY_ROWS or bool(side) != (base in SIDED):
            out.append(f"{slug}: request area {area!r} isn't a body chart row (with its side where it has one).")
    elif area:
        out.append(f"{slug}: request care none takes no area.")
    return out


def card(d, url):
    """What the home page shows for one demo (demos.json): the ask, the coach, the length, the request it reads as,
    the card, the clip."""
    clip = d.get("clip") or {}
    c = d.get("card") or {}
    return {"slug": d.get("slug"), "order": d.get("order"), "name": (c.get("who") or d.get("slug", "")).partition(",")[0],
            "ask": d.get("ask"), "coach": d.get("coach"), "minutes": d.get("minutes"), "shows": d.get("shows"),
            "story": clip.get("story"), "moments": clip.get("moments") or [], "request": d.get("request") or {},
            "card": c, "audio": url}


def _body(m, cards):
    return {"version": m.get("version", 1), "built": m.get("built", ""), "engine": m.get("engine", ""), "demos": cards}


def web_file():
    """The copy the web client builds with: web/client/src/demos.json."""
    return os.path.join(paths.ROOT, "web", "client", "src", "demos.json")


def write_web(m=None):
    """web/client/src/demos.json: every built demo's card, its clip's address on the media bucket (as `upload` puts
    it), for the sign-in page. Returns how many demos it holds."""
    import bucket
    import json
    m = m or manifest()
    problems = [p for d in m.get("demo", []) for p in request_problems(d)]
    if problems:
        raise errors.UsageError("\n".join(problems))
    version = m.get("version", 1)
    cards = [card(d, bucket.public_url(f"demos/v{version}/{d['slug']}.mp3", m.get("bucket", "")))
             for d in sorted(m.get("demo", []), key=lambda d: d.get("order", 0)) if (d.get("clip") or {}).get("from")]
    if not cards:
        raise errors.HarmonicFitnessError("No demo is built yet (its [demo.clip] has no from): nothing to show.")
    fileio.atomic_write(web_file(), (json.dumps(_body(m, cards), indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    return len(cards)


def upload(put=None):
    """Every clip staged in docs/demos/clips/ to the media bucket as demos/v<version>/<slug>.mp3, then demos.json
    beside them (the manifest's version, every demo with a clip uploaded, and its card). Returns [(key, url)]."""
    import bucket
    import json
    put = put or bucket.put
    m = manifest()
    version = m.get("version", 1)
    done, cards = [], []
    for d in sorted(m.get("demo", []), key=lambda d: d.get("order", 0)):
        path = os.path.join(clips_dir(), f"{d.get('slug')}.mp3")
        if not os.path.isfile(path):
            continue
        key = f"demos/v{version}/{d['slug']}.mp3"
        with open(path, "rb") as f:
            url = put(key, f.read(), "audio/mpeg")
        done.append((key, url))
        cards.append(card(d, url))
    if not cards:
        raise errors.HarmonicFitnessError(f"No clips staged in {show(clips_dir())}: demos publish comes first.")
    body = json.dumps(_body(m, cards), indent=1).encode()
    key = f"demos/v{version}/demos.json"
    done.append((key, put(key, body, "application/json")))
    return done


def status(m=None):
    """One line a demo: its ask's length, coach, and how far it has got."""
    m = m or manifest()
    lines = []
    for d in m.get("demo", []):
        slug = d.get("slug", "?")
        folder = home_of(slug)
        steps = []
        if os.path.exists(os.path.join(folder, "profile.md")):
            steps.append("folder")
            if _made(_coach_in(folder, d.get("coach", ""))):
                steps.append("coach")
            work = os.path.join(folder, "workouts")
            if os.path.isdir(work) and any(n.endswith("-clip") for n in os.listdir(work)):
                steps.append("clip draft")
        if os.path.exists(os.path.join(clips_dir(), slug + ".mp3")):
            steps.append("published")
        lines.append(f"{d.get('order', '?')}. {slug:<6} {d.get('minutes', '?')} min, {d.get('coach', '?')}: "
                     + (", ".join(steps) if steps else "not started"))
    return lines


def main(argv=None):
    import cli
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["run"]:   # everything after the slug is the demo's own command, its options included
        if len(argv) < 2 or argv[1].startswith("-"):
            raise cli.Usage("usage: harmonicfitness demos run <slug> <command> [options]")
        rest = argv[2:]
        return run_as(argv[1], rest[1:] if rest[:1] == ["--"] else rest)
    ap = cli.ArgumentParser(prog="harmonicfitness demos",
                            description="The home page's demo clips (docs/demos/): the seven, each demo listener's "
                                        "folder, a command run as one, a clip's segments cut from its full draft, "
                                        "and the clip published. `demos run <slug> <command> ...` runs any command "
                                        "as that listener, with the listener's own key file.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="the seven, and how far each has got (the default)")
    h = sub.add_parser("home", help="ready docs/demos/listeners/<slug>/: install its stock-voice coach, held to the set's model")
    h.add_argument("slug")
    sub.add_parser("run", help="run a command as a demo listener: demos run <slug> <command> [options]")
    e = sub.add_parser("excerpt", help="a full draft's segments, numbered; with --from and --to, those as a draft of their own")
    e.add_argument("draft")
    e.add_argument("--from", dest="first", type=cli.positive_int, help="the clip's first segment, from 1")
    e.add_argument("--to", dest="last", type=cli.positive_int, help="the clip's last segment")
    sub.add_parser("upload", help="every staged clip and demos.json to the media bucket (the bucket's keys in the shell)")
    sub.add_parser("web", help="write web/client/src/demos.json, the sign-in page's copy of the built demos")
    p = sub.add_parser("publish", help="copy a demo's rendered clip to docs/demos/clips/<slug>.mp3, for the media bucket")
    p.add_argument("slug")
    p.add_argument("mp3")
    a = ap.parse_args(argv)
    if a.cmd in (None, "list"):
        print("\n".join(status()))
        return 0
    if a.cmd == "home":
        make_home(a.slug)
        print(f"Run its commands with ./harmonicfitness demos run {a.slug} <command> ...")
        return 0
    if a.cmd == "excerpt":
        if a.first is None and a.last is None:
            for n, seconds, label in segments(a.draft):
                print(f"{n:>3}  {seconds:>4} s  {label}")
            return 0
        if a.first is None or a.last is None:
            raise cli.Usage("demos excerpt: give both --from and --to, or neither to list the segments")
        out, seconds = excerpt(a.draft, a.first, a.last)
        print(f"Wrote {show(out)}: segments {a.first} to {a.last}, {seconds} s, with the menu beside it.")
        if not CLIP_SECONDS[0] <= seconds <= CLIP_SECONDS[1]:
            print(f"It runs {seconds} s; a clip is {CLIP_SECONDS[0]} to {CLIP_SECONDS[1]} s.", file=sys.stderr)
        return 0
    if a.cmd == "upload":
        for key, url in upload():
            print(f"{key}: {url}")
        return 0
    if a.cmd == "publish":
        print(f"Published {show(publish(a.slug, a.mp3))}.")
        return 0
    if a.cmd == "web":
        n = write_web()
        print(f"Wrote {show(web_file())}: {n} demos for the sign-in page.")
        return 0
    raise cli.Usage(f"demos {a.cmd}: run it as demos run <slug> <command> ...")
