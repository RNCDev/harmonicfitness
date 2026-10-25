"""The readiness check's second half: what needs the Python environment to tell.

tools/doctor.sh describes the computer (and runs before any environment exists); this adds
the voice models on disk, the context folder, the delivery folders and ffmpeg's abilities.
Other tools read the computer's facts through facts(), so the shell script stays the one
place that decides what this computer can do.

    ./sweatcast doctor        # runs doctor.sh, which runs this once the environment exists
"""
import functools
import glob
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import paths  # noqa: E402

DOCTOR_SH = os.path.join(paths.ROOT, "tools", "doctor.sh")


@functools.lru_cache(maxsize=1)
def facts():
    """The computer's facts, from `sh tools/doctor.sh --facts`, read once per process."""
    out = subprocess.run(["sh", DOCTOR_SH, "--facts"], capture_output=True, text=True, timeout=60)
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


def hub_dir():
    """Where the local voice models are (models/, which tools/paths.py points Hugging Face at)."""
    return paths.MODELS


def model_present(repo, revision, hub=None):
    folder = os.path.join(hub or hub_dir(), "models--" + repo.replace("/", "--"), "snapshots")
    if revision:
        return os.path.isdir(os.path.join(folder, revision))
    return bool(glob.glob(os.path.join(folder, "*")))


def _model_lines():
    """The local models this computer's coaches render with (Chatterbox Turbo when there are none yet)."""
    import personas
    import voices
    engines_used = []
    for p in personas.all():
        if p.has_clip:
            engine = p.table("local").get("engine") or "chatterbox"
            if engine not in engines_used:
                engines_used.append(engine)
    lines, seen = [], set()
    for engine in engines_used or ["chatterbox"]:
        pin = voices.LOCAL_MODELS.get((engine, voices.BACKEND))
        if not pin:
            lines.append(f"  {engine}: renders locally only on an Apple Silicon Mac")
            continue
        extras = [] if voices.BACKEND == "torch" else voices.ENGINE_EXTRAS.get(engine, [])
        for repo, rev in [pin, *extras]:
            if repo in seen:
                continue
            seen.add(repo)
            size = voices.SIZES_GB.get(repo)
            state = "downloaded" if model_present(repo, rev) else \
                "not downloaded" + (f" (about {size} GB)" if size else "")
            lines.append(f"  {repo}: {state}")
    return lines


def _context_lines(home):
    import context
    profile = os.path.join(home, "profile.md")
    if not os.path.exists(profile):
        return [f"  {paths.show(home)}: not made yet (./sweatcast setup copies it from me.example/)"]
    with open(profile, encoding="utf-8") as f:
        found = context.schema_of(f.read())
    lines = [f"  {paths.show(home)}: there, schema {found}"
             + ("" if found == context.SCHEMA else f" (this engine reads {context.SCHEMA}: ./sweatcast migrate)")]
    if found != context.SCHEMA:
        return lines
    p = context.profile(profile)
    for pattern in context.delivery_patterns(p):
        hits = glob.glob(pattern) if glob.has_magic(pattern) else [pattern]
        here = any(os.path.isdir(h) for h in hits)
        lines.append(f"  Delivery folder {pattern}: " + ("there" if here else "not on this computer"))
    if not context.delivery_patterns(p):
        lines.append("  Delivery folder: none set; MP3s stay in me/workouts/")
    return lines


def _ffmpeg_lines():
    import ffmpeg
    exe = ffmpeg.exe()
    if not exe:
        return ["  ffmpeg: not found, and the environment's own copy isn't installed: rerun ./sweatcast setup, "
                f"or install it ({ffmpeg.install_hint()})"]
    mp3, loud = ffmpeg.capable(exe)
    where = "bundled with the environment" if ffmpeg.bundled(exe) else exe
    if mp3 and loud:
        return [f"  ffmpeg: {where}, with MP3 encoding and loudness normalization"]
    missing = " and ".join(w for w, ok in (("MP3 encoding (libmp3lame)", mp3), ("loudness normalization (loudnorm)", loud))
                           if not ok)
    return [f"  ffmpeg: {where} lacks {missing}; install a full build ({ffmpeg.install_hint()})"]


def _models_section():
    out = [f"Voice models (in {paths.show(paths.MODELS)}"
           + (f", a link to {os.path.realpath(paths.MODELS)}" if os.path.islink(paths.MODELS) else "") + ")"]
    try:
        out += _model_lines() or ["  none listed"]
        import models
        waiting = models.adopt(dry_run=True)
        if waiting:
            out.append(f"  Also in {paths.OLD_HF_HUB_CACHE}: {', '.join(r for r, _ in waiting)}. "
                       "./sweatcast models adopt moves them here instead of downloading again.")
    except Exception as e:   # a broken voice file shouldn't hide the rest of the report
        out.append(f"  couldn't list them: {e}")
    return out


def kept(home):
    """True when the context folder is its own git repo with a remote, so ./sweatcast backup keeps it."""
    import backup
    return backup.own_repo(home) and bool(backup.git(home, "remote").stdout.split())


def web_lines(home, profile=None):
    """What Claude Code on the web needs: the key as a setting, the hosts to allow, and where the profile lives."""
    import keys
    import routes
    have = [s for s in routes.SERVICES if keys.is_set(s)]
    lines = ["Claude Code on the web",
             "  Cloud voices only: there's no graphics card here for a local one.",
             "  Voice key: " + (f"set for {', '.join(have)}." if have else
                                "none yet. Set it in the cloud environment's settings, under Environment variables, "
                                "as FISH_AUDIO_API_KEY=<key> (or ELEVENLABS_API_KEY, GEMINI_API_KEY, "
                                "INWORLD_API_KEY); never in the chat."),
             "  Network: the environment's network access needs " + ", ".join(
                 h for r in routes.SERVICES for h in routes.hosts(r)) + " (Custom, with the default list kept; "
             "only the service your coach speaks through is needed).",
             "  Feeds, optional (research searches without them): " + ", ".join(routes.feed_hosts(profile)) + "."]
    import personas
    coaches = personas.all(os.path.join(home, "personas"))
    if not any(p.is_web for p in coaches):   # local coaches can't speak here
        lines.append("  No web coach yet (a local coach can't speak here). The way out: "
                     + routes.way_out(os.path.join(home, "personas")))
    if kept(home):
        lines.append(f"  Your context folder: {paths.show(home)}, its own private repo, so ./sweatcast backup keeps it.")
    else:
        lines.append(f"  Your context folder: {paths.show(home)}, not kept: this is a one-time session, and the "
                     "profile, log and coach vanish when it ends. To keep them, attach your private sweatcast-me repo "
                     "to the session (or set SWEATCAST_HOME to where it's cloned).")
    return lines


def report_lines(f=None, home=None):
    """The lines that need the environment: models, the context folder, delivery, ffmpeg."""
    f = f if f is not None else facts()
    home = home or paths.HOME
    if f.get("remote") == "yes":   # Claude Code on the web: what to set up there, and no local models
        import context
        prof = None
        try:
            if os.path.exists(os.path.join(home, "profile.md")):
                prof = context.profile(os.path.join(home, "profile.md"))
        except SystemExit:
            prof = None
        out = web_lines(home, prof)
    else:
        try:
            out = _models_section()
        except SystemExit as e:   # a coach file this engine can't read yet (./sweatcast migrate)
            out = [f"Voice models (in {paths.show(paths.MODELS)})", f"  {e}"]
    out += ["", "Your context folder"]
    try:
        out += _context_lines(home)
    except SystemExit as e:
        out.append(f"  {e}")
    out += ["", "Audio tools"]
    out += _ffmpeg_lines()
    try:
        out += ["", "Audio routes"] + _route_lines(f, home)
    except SystemExit as e:
        out += [f"  {e}"]
    return out


SPEECH_SHARE = 0.75   # about how much of a 30-minute workout is speech (an approximation)


def _route_lines(f, home):
    import context
    import personas
    import routes
    import voices
    if os.path.abspath(home) != os.path.abspath(paths.HOME) or not os.path.exists(paths.PROFILE):
        return ["  (checked once the context folder is set up)"]
    p = context.profile()
    try:
        coach, archived = personas.default(), None
    except SystemExit as e:   # the coach used last is archived: report it, and the routes for no coach
        coach, archived = None, str(e.code)
    lines = routes.report_lines(coach, context.routes(p), f)
    if archived:
        lines.append(f"  {archived}")
    if coach is None and not archived:
        lines.append("  No coach yet: the coach skill makes one (\"I want a new coach\").")
    if f.get("local") == "experimental":
        measured = None
        if coach is not None and coach.has_clip:
            try:
                measured = voices.speed(personas.voice_for(coach, "local"))
            except SystemExit:
                measured = None
        if measured:
            minutes = measured * 30 * SPEECH_SHARE
            lines.append(f"  Local on the processor: about {minutes:.0f} minutes to render a 30-minute workout here "
                         f"(measured {measured:.1f} times the speech's length)"
                         + ("; that's long, so a cloud voice may suit better." if minutes > 60 else "."))
        else:
            lines.append("  Local on the processor: experimental, speed unknown, likely slow. "
                         "The smoke test measures it.")
    return lines


def main():
    print("\n".join(report_lines()))
    return 0


if __name__ == "__main__":
    sys.exit(cli.run(main))
