"""Coaches: design one from a description, keep a take as their clip, choose, measure and tune them.

A coach is a persona folder in me/personas/ (tools/personas.py): a person's name, how they talk, and
a ten-second clip every engine copies. Nothing renders from a description alone: a description
makes takes, the listener keeps one, and that clip is the coach from then on.

    ./sweatcast coaches                                   # every coach, the last used marked
    ./sweatcast coaches last                              # the coach a build uses when none is named
    ./sweatcast coaches design "Coach Maya" "A woman in her thirties, warm and mid-low ..." [--designer fish]
    ./sweatcast coaches keep "me/personas/coach-maya/takes/2.wav"
    ./sweatcast coaches keep my-recording.wav --name "Coach Sam" --words "what the clip says"
    ./sweatcast coaches set "Coach Maya" local.engine qwen3
    ./sweatcast coaches measured "Coach Maya" --engine fish   # exit 0 measured, 1 estimated, 64 unknown
    ./sweatcast coaches samples deepgram                  # hear Deepgram's stock voices, to pick one
    ./sweatcast coaches download ["Coach Maya"]           # the coach's local model

Designers, the first that works here unless --designer says: local (Qwen3-TTS VoiceDesign on MLX, an
Apple Silicon Mac; a 4.5 GB model), fish (Fish Audio's voice design, about $0.01 a call) or
elevenlabs (its text-to-voice design), each with the listener's key. Or bring a clip: about ten
seconds of a voice with its exact words; a real person's voice needs that person's consent.
"""
import argparse
import json
import os
import shutil
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import context  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402

DESIGNERS = ("local", "fish", "elevenlabs")
PROSE = """## How this coach talks
- Tone: calm and focused. Keep humor light and occasional, with no hype.
- How the coach talks to me: like a coach who knows me, warm and direct, first name now and then, contractions, "let's" in the rests. Not a drill sergeant, not a radio host.
- Encouragement that works for me: [for example, notice the effort plainly ("that last set was honest"), tell me why a movement is there, remind me what I did last time]
- Pet peeves in workout audio:
"""
SAMPLES = os.path.join(paths.PERSONAS, ".samples")


def available_designer():
    import keys
    import routes
    if voices.BACKEND == "mlx" and routes.local_installed():
        return "local"
    for service in ("fish", "elevenlabs"):
        if keys.is_set(service):
            return service
    raise SystemExit("No voice designer works here: local design needs an Apple Silicon Mac, and the cloud "
                     "designers need a key (./sweatcast keys init fish, or elevenlabs). Or bring a clip of about "
                     "ten seconds with its words: ./sweatcast coaches keep <clip.wav> --name ... --words ...")


def _make_takes(designer):
    if designer == "local":
        import engines
        from render import render_lock

        def make(description, line, takes, seed):
            with render_lock(paths.CACHE):   # another model: one at a time
                pcm = engines.design_takes(voices.VOICE_DESIGN[0], voices.VOICE_DESIGN[1], description, line,
                                           takes, seed)
            return [(x, line) for x in pcm]
        return make
    import importlib
    module = importlib.import_module(f"services.{designer}")
    return module.design


def design(name, description, designer=None, takes=2, seed=7, line=voices.DESIGN_LINE, make_takes=None):
    """Render takes of a new (or existing) coach into me/personas/<slug>/takes/<n>.wav, beside each its words
    (<n>.txt) and how it was made (<n>.take.json). Earlier takes are kept. Returns the .wav paths."""
    designer = designer or available_designer()
    if designer not in DESIGNERS:
        raise SystemExit(f"--designer must be one of {', '.join(DESIGNERS)}")
    folder = os.path.join(paths.PERSONAS, personas.slug(name), "takes")
    os.makedirs(folder, exist_ok=True)
    made = (make_takes or _make_takes(designer))(description, line, takes, seed)
    n = max([int(f[:-4]) for f in os.listdir(folder) if f.endswith(".wav") and f[:-4].isdigit()], default=0)
    out = []
    for i, (pcm, words) in enumerate(made):
        n += 1
        stem = os.path.join(folder, str(n))
        voices.write_wav(stem + ".wav", pcm)
        with open(stem + ".txt", "w", encoding="utf-8") as f:
            f.write(words.strip() + "\n")
        meta = {"name": name, "description": description, "designer": designer, "line": words, "seed": seed + i}
        if designer == "local":
            meta.update(model=voices.VOICE_DESIGN[0], revision=voices.VOICE_DESIGN[1])
        with open(stem + ".take.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        out.append(stem + ".wav")
    return out


def _clip_bytes(src):
    """The clip as a 16-bit mono 24 kHz WAV: the file itself when it already is one (so its key stays the
    same), else converted (WAV in pure Python, anything else through ffmpeg)."""
    import cloud
    with open(src, "rb") as f:
        data = f.read()
    try:
        with wave.open(src) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2):
                return data
    except (wave.Error, EOFError):
        pass
    pcm = cloud.audio_pcm(data)
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    return buf.getvalue()


def keep(take, name=None, words=None, description="", engine="chatterbox", force=False):
    """Make a take (or any clip, with its words) a coach's clip: clip.wav and clip.txt in the coach's folder,
    and a persona.md when the coach is new. Returns the coach's name."""
    if not os.path.exists(take):
        raise SystemExit(f"No clip at {take}.")
    stem = os.path.splitext(take)[0]
    meta = {}
    if os.path.exists(stem + ".take.json"):
        with open(stem + ".take.json", encoding="utf-8") as f:
            meta = json.load(f)
    if words is None and os.path.exists(stem + ".txt"):
        with open(stem + ".txt", encoding="utf-8") as f:
            words = f.read()
    if not (words or "").strip():
        raise SystemExit("A clip needs its exact words: pass --words \"...\" (or a .txt of them beside it).")
    name = name or meta.get("name")
    if not name:
        raise SystemExit("Give the coach a person's name: --name \"Coach Sam\".")
    if engine not in personas.LOCAL_ENGINES:
        raise SystemExit(f"--engine must be one of {', '.join(personas.LOCAL_ENGINES)}")
    folder = os.path.join(paths.PERSONAS, personas.slug(name))
    os.makedirs(folder, exist_ok=True)
    clip, clip_txt, persona_md = (os.path.join(folder, f) for f in ("clip.wav", "clip.txt", "persona.md"))
    if os.path.exists(clip) and not force:
        raise SystemExit(f"{name} already has a clip ({show(clip)}); pass --force to replace it (their pace is "
                         "measured again on the next smoke test).")
    data = _clip_bytes(take)
    with open(clip + ".part", "wb") as f:
        f.write(data)
    os.replace(clip + ".part", clip)
    with open(clip_txt, "w", encoding="utf-8") as f:
        f.write(words.strip() + "\n")
    if not os.path.exists(persona_md):
        settings = {"name": name, "description": description or meta.get("description", "")}
        if meta.get("description"):
            settings["designed_from"] = meta["description"]
        settings["local"] = {"engine": engine}
        with open(persona_md, "w", encoding="utf-8") as f:
            f.write(context.persona_text(settings, PROSE))
    return name


def last_line(p):
    return f"{p.name}" + (f": {p.description}" if p.description else "")


def _value(text):
    low = text.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(text)
    except ValueError:
        return text


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast coaches", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="every coach (the default)")
    sub.add_parser("last", help="the coach a build uses when none is named: the one used last")
    m = sub.add_parser("measured", help="exit 0 if the coach's pace is measured on the route, 1 if estimated, 64 unknown")
    m.add_argument("coach")
    m.add_argument("--engine", default=None, help="the route (default: the profile's render list)")
    g = sub.add_parser("design", help="render takes of a coach from a description")
    g.add_argument("name", help="a person's name, such as 'Coach Maya'")
    g.add_argument("description", help="who they are and how they sound (knowledge/voices.md)")
    g.add_argument("--designer", choices=DESIGNERS, help="default: the first that works here")
    g.add_argument("--takes", type=int, default=2)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--line", default=voices.DESIGN_LINE, help="what the takes say (a coaching line)")
    g.add_argument("--play", action="store_true", help="play each take with the system's player")
    k = sub.add_parser("keep", help="make a take, or a clip you bring, a coach's clip")
    k.add_argument("take")
    k.add_argument("--name", help="the coach's name (default: the take's)")
    k.add_argument("--words", help="the clip's exact words (default: the .txt beside it)")
    k.add_argument("--description", default="", help="who the coach is, in a line")
    k.add_argument("--engine", choices=personas.LOCAL_ENGINES, default="chatterbox",
                   help="the local model: chatterbox (most natural) or qwen3 (clearest; Mac only)")
    k.add_argument("--force", action="store_true", help="replace the coach's clip")
    s = sub.add_parser("set", help="set one of a coach's settings: <table>.<key> <value>")
    s.add_argument("coach")
    s.add_argument("setting", help="for example local.engine, elevenlabs.model, deepgram.voice, or description")
    s.add_argument("value")
    sp = sub.add_parser("samples", help="a line in each of a stock-voice service's voices, to pick one")
    sp.add_argument("service", choices=("deepgram",))
    sp.add_argument("--voices", help="comma-separated (default: the ten in knowledge/services.toml)")
    sp.add_argument("--line", default=voices.DESIGN_LINE)
    d = sub.add_parser("download", help="fetch the local model the coaches use (Chatterbox Turbo with none yet)")
    d.add_argument("coach", nargs="*")
    d.add_argument("--all", action="store_true", help="every local engine's model this computer can run")
    args = ap.parse_args(argv)

    if args.cmd == "last":
        p = personas.last_coach()
        if not p:
            print("No coach yet.", file=sys.stderr)
            return cli.ISSUES
        print(p.name)
        return cli.OK
    if args.cmd == "measured":
        import routes
        try:
            p = personas.lookup(args.coach)
            route = routes.pick(context.routes(context.profile()) if os.path.exists(paths.PROFILE) else ["local"],
                                p, override=args.engine)
            v = personas.voice_for(p, route)
        except SystemExit as e:
            print(e.code, file=sys.stderr)
            return cli.USAGE
        return cli.OK if voices.pace(v)[1] else cli.ISSUES
    if args.cmd == "design":
        designer = args.designer or available_designer()
        print(f"Designing {args.name}: {args.takes} takes with the {designer} designer"
              + (f" ({voices.VOICE_DESIGN[0]}, about {voices.SIZES_GB[voices.VOICE_DESIGN[0]]} GB the first time)"
                 if designer == "local" else "") + ".", flush=True)
        takes = design(args.name, args.description, designer, args.takes, args.seed, args.line)
        import player
        for t in takes:
            print(f"  {show(t)}")
            if args.play and not player.play(t):
                print("    (no audio player found here; open the file to listen)")
        print(f"Listen, then keep the one that sounds right:\n  ./sweatcast coaches keep \"{show(takes[0])}\"\n"
              "None right? Say what's off, reword the description, and design again (or another --seed).")
        return cli.OK
    if args.cmd == "keep":
        name = keep(args.take, args.name, args.words, args.description, args.engine, args.force)
        print(f"Kept {name} in {show(os.path.join(paths.PERSONAS, personas.slug(name)))}. Write how they talk in "
              f"persona.md, then measure their pace with the smoke test:\n"
              f"  ./sweatcast build {show(paths.SMOKE_DRAFT)} \"smoke-test\" --coach \"{name}\"")
        return cli.OK
    if args.cmd == "set":
        p = personas.lookup(args.coach)
        table, _, key = args.setting.rpartition(".")
        value = _value(args.value)
        if table == "local" and key == "engine" and value not in personas.LOCAL_ENGINES:
            raise SystemExit(f"local.engine must be one of {', '.join(personas.LOCAL_ENGINES)}")
        context.set_persona_setting(p.path, table or None, key, value)
        print(f"{p.name}: {args.setting} = {value}")
        return cli.OK
    if args.cmd == "samples":
        import cloud
        import services.deepgram as deepgram
        names = [v.strip() for v in (args.voices or "").split(",") if v.strip()] or \
            cloud.services()["deepgram"]["stock_voices"]
        folder = os.path.join(SAMPLES, args.service)
        os.makedirs(folder, exist_ok=True)
        for name, pcm in deepgram.samples(args.line, names):
            path = os.path.join(folder, f"{name}.wav")
            voices.write_wav(path, pcm)
            print(f"  {show(path)}")
        print("Pick one, then: ./sweatcast coaches set \"<coach>\" deepgram.voice <voice>")
        return cli.OK
    if args.cmd == "download":
        if args.all:
            engines_wanted = [e for e in personas.LOCAL_ENGINES if (e, voices.BACKEND) in voices.LOCAL_MODELS]
        else:
            chosen = [personas.lookup(n) for n in args.coach] or personas.all()
            engines_wanted = list(dict.fromkeys(p.table("local").get("engine") or "chatterbox"
                                                for p in chosen if p.has_clip)) or ["chatterbox"]
        for engine in engines_wanted:
            if (engine, voices.BACKEND) not in voices.LOCAL_MODELS:
                print(f"{engine}: renders locally only on an Apple Silicon Mac; skipped.")
                continue
            model, revision = voices.LOCAL_MODELS[(engine, voices.BACKEND)]
            voices.download({"name": engine, "engine": engine, "backend": voices.BACKEND, "model": model,
                             "revision": revision})
        return cli.OK
    last = personas.last_coach()
    found = personas.all()
    if not found:
        print("No coaches yet: design one (./sweatcast coaches design) or bring a clip (./sweatcast coaches keep).")
        return cli.OK
    for p in found:
        mark = "*" if last and p.slug == last.slug else " "
        engine = p.table("local").get("engine", "chatterbox") if p.has_clip else "Deepgram stock voice only"
        print(f"{mark} {p.name:22} {engine:12} " + ("(a stand-in) " if p.placeholder else "") + p.description[:60])
    print("* the coach a build uses when none is named (the one used last)")
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
