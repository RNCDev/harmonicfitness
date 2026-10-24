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
import paths  # noqa: E402

DOCTOR_SH = os.path.join(paths.ROOT, "tools", "doctor.sh")


@functools.lru_cache(maxsize=1)
def facts():
    """The computer's facts, from `sh tools/doctor.sh --facts`, read once per process."""
    out = subprocess.run(["sh", DOCTOR_SH, "--facts"], capture_output=True, text=True, timeout=60)
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


def hub_dir():
    """Where Hugging Face keeps downloaded models."""
    if os.environ.get("HF_HUB_CACHE"):
        return os.environ["HF_HUB_CACHE"]
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    return os.path.join(home, "hub")


def model_present(repo, revision, hub=None):
    folder = os.path.join(hub or hub_dir(), "models--" + repo.replace("/", "--"), "snapshots")
    if revision:
        return os.path.isdir(os.path.join(folder, revision))
    return bool(glob.glob(os.path.join(folder, "*")))


def _model_lines():
    import voices
    lines, seen = [], set()
    for name in voices.names():
        try:
            v = voices.lookup(name)
        except SystemExit:
            continue
        if not v["model"]:
            continue
        extras = [] if v["backend"] == "torch" else voices.ENGINE_EXTRAS.get(v["engine"], [])
        for repo, rev in [(v["model"], v["revision"]), *extras]:
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


def report_lines(f=None, home=None):
    """The lines that need the environment: models, the context folder, delivery, ffmpeg."""
    f = f if f is not None else facts()
    home = home or paths.HOME
    out = ["Voice models"]
    try:
        out += _model_lines() or ["  none listed"]
    except Exception as e:   # a broken voice file shouldn't hide the rest of the report
        out.append(f"  couldn't list them: {e}")
    out += ["", "Your context folder"]
    try:
        out += _context_lines(home)
    except SystemExit as e:
        out.append(f"  {e}")
    out += ["", "Audio tools"]
    out += _ffmpeg_lines()
    return out


def main():
    print("\n".join(report_lines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
