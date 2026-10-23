"""One step from draft to deliverables: lint and export the .txt, render the .mp3, copy it to the phone.

Run it as ./sweatcast build.

    ./sweatcast build <draft> "<name>" [--voice <name>] [--lint-only] [render options...]
    ./sweatcast build me/workouts/drafts/x.draft.txt "Workout 2026-10-19 Bench 25 min" --voice "Chatterbox Coach"

Writes me/workouts/<name>.txt and me/workouts/<name>.mp3 (the context folder is SWEATCAST_HOME if
set). Stops after the lint if it finds issues (fix and rerun). --lint-only skips rendering. Without
--voice, uses the first voice in the profile's settings. After a render, copies the MP3 to each
deliver_to folder that exists and, once every copy matches, removes the local MP3.

--follow renders ahead while the draft is still being written: it keeps the voice model loaded,
renders each new or edited paragraph as it appears in the draft, and stops when the full build starts
(which then renders only what's left), or after --idle seconds with nothing new. --clips-only renders
what the draft holds now, once. Neither lints, writes an MP3 or copies.

--tolerance <fraction> sets how far the total may run off plan, for the lint and the render alike
(default three percent).

Exit codes (tools/cli.py): 0 done, 1 issues to fix, 2 the rendered total ran more than the tolerance
off plan (the MP3 is written but not copied), 3 the voice's pace hasn't been measured yet (render the
smoke test with it first, which measures it, or pass --allow-estimated), 64 the command was wrong (a
mistyped option, an unknown voice): fix the command, not the draft. The render's stderr (model
loading, errors) goes to me/workouts/.logs/<name>.log, and its last lines print on a failure.
"""
import filecmp
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cli  # noqa: E402
import paths  # noqa: E402

USAGE = 'usage: ./sweatcast build <draft> "<name>" [--voice <name>] [--lint-only] [--follow] [render options]'


def python():
    """The Python every tool runs under: SWEATCAST_PYTHON if set (tests use a stand-in), else this one.
    Windows can't run a script with a #! line directly, so a stand-in that isn't an .exe runs under
    this Python."""
    py = os.environ.get("SWEATCAST_PYTHON")
    if not py:
        return [sys.executable]
    return [sys.executable, py] if os.name == "nt" and not py.lower().endswith(".exe") else [py]


def tool(name, *args, **kw):
    return subprocess.run([*python(), os.path.join(HERE, name), *args], **kw)


def option(args, name):
    """The value after `name` in args, or None."""
    return args[args.index(name) + 1] if name in args[:-1] else None


def show_log(log):
    print(f"--- last lines of {log}:", file=sys.stderr)
    with open(log, encoding="utf-8", errors="replace") as f:
        print("".join(f.readlines()[-20:]), end="", file=sys.stderr)


def render(draft, args, log):
    with open(log, "w", encoding="utf-8") as err:
        return tool("render.py", draft, *args, stderr=err).returncode


def deliver(mp3, out_dir):
    """Copy the MP3 to every delivery folder that exists; remove the local one once all match."""
    found = tool("context.py", "deliver", capture_output=True, text=True).stdout.splitlines()
    found = [d for d in found if d.strip()]
    failed = False
    for dest in found:
        target = os.path.join(dest, os.path.basename(mp3))
        try:
            shutil.copyfile(mp3, target)
            ok = filecmp.cmp(mp3, target, shallow=False)
        except OSError:
            ok = False
        if ok:
            print(f"Copied to {dest}/{os.path.basename(mp3)}")
        else:
            failed = True
            print(f"Couldn't copy to {dest}; the MP3 is in {out_dir}")
    if found and not failed:
        os.remove(mp3)
        print(f"Removed the local copy; the text and build record stay in {out_dir}")
    elif not found:
        print(f"The MP3 is in {out_dir}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print(USAGE, file=sys.stderr)
        return cli.USAGE
    draft, name, rest = argv[0], argv[1], argv[2:]
    lint_only, allow_estimated = "--lint-only" in rest, "--allow-estimated" in rest
    rest = [a for a in rest if a not in ("--lint-only", "--allow-estimated")]   # the rest go to the render
    if "/" in name or "\\" in name:
        print(f"The name can't contain a slash: {name}", file=sys.stderr)
        return cli.USAGE
    profile = paths.PROFILE
    out_dir = paths.WORKOUTS
    if not os.path.isfile(profile):
        print(f"No profile at {profile}. Run ./sweatcast setup first (it copies me.example/ to me/).")
        return cli.ISSUES
    if not os.path.isfile(draft):
        print(f"No draft at {draft}", file=sys.stderr)
        return cli.USAGE

    # The default voice lives in the profile; context.py stops here, with the fix, if the
    # context folder needs migrating.
    got = tool("context.py", "get", "default-voice", capture_output=True, text=True)
    if got.returncode:
        print(got.stdout + got.stderr, end="")
        return got.returncode
    voice = option(rest, "--voice")
    if not voice:
        voice = got.stdout.strip()
        if not voice:
            print(f"No --voice given, and no default voice found in {profile}.\nExpected at least one "
                  "[[voices]] entry in the settings at the top of the profile; the first is the default.")
            return cli.ISSUES
        rest += ["--voice", voice]
    tolerance = option(rest, "--tolerance")
    smoke = os.path.basename(draft) == "smoke-test.draft.txt"
    os.makedirs(paths.LOGS, exist_ok=True)
    log = os.path.join(paths.LOGS, f"{name}.log")

    if "--clips-only" in rest or "--follow" in rest:
        # Rendering ahead while the rest of the draft is written: no lint, no MP3.
        status = render(draft, rest, log)
        if status:
            show_log(log)
        return status

    if not smoke and not lint_only:
        measured = tool("voices.py", "measured", voice).returncode
        if measured == cli.USAGE:
            names = tool("context.py", "get", "voices", capture_output=True, text=True).stdout.split("\n")
            print(f"Voices in your profile: {', '.join(n for n in names if n)} (all voices: ./sweatcast voices).")
            return cli.USAGE
        if measured and not allow_estimated:
            print(f"{voice}'s speaking rate hasn't been measured yet, so this draft's timing is a guess.\n"
                  "Render the smoke test with it first, which measures it, then rerun:\n"
                  f'  ./sweatcast build voices/smoke-test.draft.txt "smoke-test" --voice "{voice}"\n'
                  "(or pass --allow-estimated to render anyway)")
            return cli.UNMEASURED

    # The smoke test exists to measure a voice, so its lint never blocks the render. Every other
    # draft needs the menu ./sweatcast brief --save wrote beside it: the lint checks each movement
    # the draft declares or names against today's limits, and stops the build without one.
    lint = ["--voice", voice, "--out", os.path.join(out_dir, f"{name}.txt")]
    lint += ["--total-tolerance", tolerance] if tolerance else []
    lint += ["--force"] if smoke else ["--require-menu"]
    status = tool("tts_build.py", draft, *lint).returncode
    if status or lint_only:
        return status

    mp3 = os.path.join(out_dir, f"{name}.mp3")
    status = render(draft, ["--out", mp3, *rest], log)
    # Model loading is chatty on stderr, so it goes to the log; show it on any failure but drift.
    if status not in (cli.OK, cli.DRIFT):
        show_log(log)
    if smoke or status:   # the smoke test is a voice check, not a workout: no copy
        return status
    deliver(mp3, out_dir)
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
