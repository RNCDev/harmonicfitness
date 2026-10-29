"""Coaches: choose one of the coaches HarmonicFitness ships, or audition a web coach and keep the one that sounds
right; measure and tune them.

A coach is a persona folder (tools/personas.py): a person's name, how they talk, and how they sound. The ten
local coaches ship in coaches/ (a clip, its Pocket TTS voice file, recorded counts and cues, a sample); they're
chosen, not made. A web coach is a voice a service designed and saved (Fish Audio, ElevenLabs, Gemini, Inworld,
with the listener's key), kept in me/coaches/.

    ./harmonicfitness coaches                                   # every coach and where it speaks, the last used marked
    ./harmonicfitness coaches audition maya.md                  # candidates from every keyed service, nothing saved
    ./harmonicfitness coaches audition maya.md --services fish,gemini
    ./harmonicfitness coaches audition --coach "Coach Maya"     # a new voice for a coach, on its own service
    ./harmonicfitness coaches keep 2026-10-25-1/B --name "Coach Maya"   # save B at its service as the coach
    ./harmonicfitness coaches keep 2026-10-26-1/A --name "Coach Maya" --replace-old   # re-voice; delete the old voice
    ./harmonicfitness coaches forget-audition 2026-10-25-1      # close an audition (Gemini's unkept voices deleted)
    ./harmonicfitness coaches make "Coach Reed"                 # a pending default: design and save its voice (builds do)
    ./harmonicfitness coaches archive "Coach Julius"            # out of the list, still found for old log lines
    ./harmonicfitness coaches last                              # the coach a build uses when none is named
    ./harmonicfitness coaches measured "Coach Maya" --route local   # exit 0 measured, 1 estimated, 64 unknown
    ./harmonicfitness coaches download                          # the local voice and the take checker (setup does it)

An audition reads a narrative file (persona.md's format: a +++ block with [voice], what the services design
from, and [character], what the script writer follows, then free notes) and lands in
me/coaches/.auditions/<date>-<n>/: each candidate as <service>-<k>.wav and .mp3, lettered A, B, C... in
service order, every one saying the same coaching line, with its cost per workout in candidates.json.
Fish, ElevenLabs and Inworld keep nothing until a candidate is kept; Gemini stores each voice as it
designs it, so forget-audition deletes the ones not kept.
"""
# The command line. The work is in tools/audition.py (audition, keep, forget-audition) and tools/coachmake.py
# (make); the names below re-export theirs for this release, so a caller of coaches.X keeps working.
import argparse
import json
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import coachpick  # noqa: E402
import errors  # noqa: E402
import cloud  # noqa: E402
import context  # noqa: E402
import keys  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import routes  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402
from audition import (CANDIDATES, WORKOUT_CHARS, say, stderr, audition, keep_web,  # noqa: E402,F401
                      forget_audition, _run_audition, _failure_lines, _reason, _mp3, _write_sample, _estimate,
                      _web_ref, _read_candidates, _write_candidates)
from coachmake import MADE, MADE_WAV, make, _make, _made, _record_made  # noqa: E402,F401


def _clip_bytes(src):
    """The clip as a 16-bit mono 24 kHz WAV: the file itself when it already is one (so its key stays the
    same), else converted (a 16-bit WAV in pure Python, anything else through ffmpeg). A clip someone brings
    is never taken as raw PCM: an M4A or any format not recognised by its first bytes goes through ffmpeg."""
    with open(src, "rb") as f:
        data = f.read()
    try:
        with wave.open(src) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2):
                return data
    except (wave.Error, EOFError):
        pass
    if data[:4] == b"RIFF":
        try:
            pcm, rate = cloud.wav_pcm(data)
            return cloud.wav_bytes(cloud.resample(pcm, rate, cloud.SR))
        except ValueError:   # a WAV this reader doesn't handle (24-bit, float): ffmpeg does
            pass
    return cloud.wav_bytes(cloud.ffmpeg_pcm(data, f"The clip {os.path.basename(src)} isn't a WAV"))


def _value(text):
    low = text.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(text)
    except ValueError:
        return text


def default_coach():
    """(the coach a build uses when none is named, or None; why there's none, or None): the coach used last
    being archived is the one reason, said rather than raised, so the list still shows every coach."""
    try:
        return coachpick.default(), None
    except errors.PROBLEMS as e:
        return None, str(e.code)


def listing(last=None, facts=None):
    """Every coach as a dict, in the list's order: name, slug, kind, service, service_name, default, placeholder,
    pending, shipped, speaks_here, description (what --json prints for each), and notes (the list's remarks on it,
    such as "(a stand-in)"). `last` is the coach a build uses when none is named (default_coach). speaks_here: a
    web coach's service has a key here; a local coach renders here (never in the web client). `facts` stands in
    for the computer's, as in routes.usable."""
    out = []
    local = {}   # whether local voices run here, asked once and only when a local coach is listed

    def local_ok(p):
        if paths.WEB or paths.REMOTE:
            return False
        if "facts" not in local:
            local["facts"] = routes.computer(facts)
        return routes.usable("local", p, local["facts"])[0]

    for p in personas.all():
        web = p.is_web
        speaks = keys.is_set(p.service) if web else local_ok(p)
        notes = (["(a stand-in)"] if p.placeholder else []) \
            + (["(made the first time it's used)"] if web and p.pending else []) \
            + ([f"(no {cloud.service_name(p.service)} key here)"] if web and not speaks else []) \
            + ([] if web or p.shipped else ["(a local coach of your own: ./harmonicfitness migrate archives it)"])
        out.append({"name": p.name, "slug": p.slug, "kind": "web" if web else "local",
                    "service": p.service if web else None,
                    "service_name": cloud.service_name(p.service) if web else None,
                    "default": bool(last and p.slug == last.slug), "placeholder": bool(p.placeholder),
                    "pending": bool(web and p.pending), "shipped": bool(p.shipped), "speaks_here": bool(speaks),
                    "description": p.description, "notes": notes})
    return out


def listing_lines(coaches, note=None):
    """The list as the terminal shows it, from listing()."""
    if not coaches:
        return ["No coaches found: the ten local coaches ship in coaches/ (git pull), and a web coach comes from "
                "an audition (./harmonicfitness coaches audition)."]
    lines = []
    for c in coaches:
        mark = "*" if c["default"] else " "
        where = f"web · {c['service_name']}" if c["kind"] == "web" else "local · pocket"
        words = c["notes"] + [(c["description"] or "")[:60]]
        lines.append((f"{mark} {c['name']:22} {where:22} " + " ".join(x for x in words if x)).rstrip())
    lines.append(note or "* the coach a build uses when none is named (the one used last; your own over a stand-in)")
    return lines


def main(argv=None):
    ap = cli.ArgumentParser(prog="harmonicfitness coaches", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    ls = sub.add_parser("list", help="every coach (the default)")
    ls.add_argument("--json", action="store_true",
                    help="the list as one JSON object: coaches [{name, slug, kind, service, service_name, "
                         "default, placeholder, pending, shipped, speaks_here, description}], default (a name or null), "
                         "note (why there's no default, or null)")
    sub.add_parser("last", help="the coach a build uses when none is named: the one used last (your own over a stand-in)")
    m = sub.add_parser("measured", help="exit 0 if the coach's pace is measured on the route, 1 if estimated, 64 unknown")
    m.add_argument("coach")
    m.add_argument("--route", "--engine", dest="route", default=None,
                   help="the route: local, or a web service (default: the profile's render list; --engine is the "
                        "old name)")
    a = sub.add_parser("audition", help="candidates for a web coach from every keyed service; nothing saved")
    a.add_argument("narrative", nargs="?", help="the coach narrative: persona.md's format, with [voice]")
    a.add_argument("--services", help=f"only these, comma-separated ({', '.join(CANDIDATES)})")
    a.add_argument("--coach", help="a new voice for this web coach, on its own service")
    a.add_argument("--play", action="store_true", help="play each candidate with the system's player")
    k = sub.add_parser("keep", help="keep an audition's candidate as a web coach (<audition>/<letter>)")
    k.add_argument("take", help="<audition>/<letter> or <audition>/<service>-<k>")
    k.add_argument("--name", help="the coach's name (a new web coach needs one; default: the take's)")
    k.add_argument("--replace-old", action="store_true",
                   help="re-voicing: delete the coach's old voice at its service")
    mk = sub.add_parser("make", help="make a pending web coach: design its voice and save the first candidate")
    mk.add_argument("coach")
    f = sub.add_parser("forget-audition", help="close an audition: Gemini's unkept voices deleted, the folder removed")
    f.add_argument("audition", help="its id (such as 2026-10-25-1) or folder")
    r = sub.add_parser("archive", help="move a coach out of the list (old log lines still find them)")
    r.add_argument("coach")
    s = sub.add_parser("set", help="set one of a coach's settings: <table>.<key> <value>")
    s.add_argument("coach")
    s.add_argument("setting", help="for example elevenlabs.model, or description")
    s.add_argument("value")
    sub.add_parser("download", help="fetch the local voice (Pocket TTS) and the take checker (setup does it)")
    args = ap.parse_args(argv)

    if args.cmd == "last":
        try:
            p = coachpick.default()
        except errors.PROBLEMS as e:   # the coach used last is archived
            print(e.code, file=sys.stderr)
            return cli.ISSUES
        if not p:
            print("No coach yet.", file=sys.stderr)
            return cli.ISSUES
        print(p.name)
        return cli.OK
    if args.cmd == "measured":
        p = personas.lookup(args.coach)
        if p.is_web:   # a web coach needs no smoke test (made or pending): an estimate stands until its first render
            return cli.OK
        route = coachpick.pick(context.render_preferences(), p, override=args.route)
        v = personas.voice_for(p, route)
        return cli.OK if voices.pace(v)[1] else cli.ISSUES
    if args.cmd == "audition":
        wanted = [x.strip() for x in args.services.split(",") if x.strip()] if args.services else None
        folder, cands, failures = _run_audition(args.narrative, wanted, args.coach, args.play)
        for line in _failure_lines(failures):   # a service that sent none: a failure, on stderr
            print(line, file=sys.stderr)
        if not cands:
            must_act = any(isinstance(e, cloud.ServiceError) and e.listener_must_act for _, e in failures)
            return cli.SERVICE if must_act else cli.ISSUES
        audition_id = os.path.basename(folder)
        print(f"Listen, then keep the one that sounds right:\n  ./harmonicfitness coaches keep {audition_id}/"
              f"{cands[0]['letter']} --name \"Coach ...\"\nWhen done: ./harmonicfitness coaches forget-audition {audition_id}")
        return cli.OK
    if args.cmd == "keep" and _web_ref(args.take):
        keep_web(args.take, args.name, args.replace_old)   # a service's refusal exits through cli.run
        return cli.OK
    if args.cmd == "make":
        make(args.coach)
        return cli.OK
    if args.cmd == "forget-audition":
        for line in forget_audition(args.audition):
            print(line)
        return cli.OK
    if args.cmd == "archive":
        p = personas.lookup(args.coach)
        print(f"Archived {p.name} in {show(personas.archive(p))}: out of the list; old log lines still find them.")
        return cli.OK
    if args.cmd == "keep":
        raise cli.Usage(f"{args.take} isn't an audition's candidate (<audition>/<letter>). Local coaches are the "
                        "ten HarmonicFitness ships, chosen rather than made; a voice of your own is a web coach.")
    if args.cmd == "set":
        p = personas.lookup(args.coach)
        value = _value(args.value)
        personas.set_setting(p, args.setting, value)
        print(f"{p.name}: {args.setting} = {value}")
        return cli.OK
    if args.cmd == "download":
        if paths.WEB:
            print("The web client speaks with web coaches only, so there's no local model to fetch.", file=sys.stderr)
            return cli.USAGE
        if paths.REMOTE:
            print("Claude Code on the web renders with a cloud voice only, so there's no local model to fetch here.",
                  file=sys.stderr)
            return cli.USAGE
        voices.download()
        return cli.OK
    last, note = default_coach()
    found = listing(last)
    if getattr(args, "json", False):
        print(json.dumps({"coaches": [{k: v for k, v in c.items() if k != "notes"} for c in found],
                          "default": last.name if last else None, "note": note}, indent=1, ensure_ascii=False))
        return cli.OK
    print("\n".join(listing_lines(found, note)))
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
