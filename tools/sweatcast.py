"""The `./sweatcast` command: one entry point that runs each tool in the project's
environment (.venv, Python 3.11, made by `./sweatcast setup`).

    ./sweatcast <command> [options]      # ./sweatcast help lists them
"""
import importlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# command: (module, the subcommand it stands for in that module, or None; what it does)
COMMANDS = {
    "build":       ("build", None, "lint a draft, render it to an MP3 and copy it to your phone's folder"),
    "lint":        ("tts_build", None, "lint a draft and export its clean transcript (no render)"),
    "render":      ("render", None, "render a draft to audio (build runs this for you)"),
    "coaches":     ("coaches", None, "your coaches: audition, keep, archive, choose, measure and tune them"),
    "voices":      ("coaches", None, "the old name for coaches"),
    "feeds":       ("feeds", None, "fetch the profile's feeds into today's sheet"),
    "coverage":    ("coverage", None, "movement patterns the last sessions left out, last format and loads"),
    "brief":       ("brief", None, "today's ingredients: the listener, limits, safe menu, programming guide (--save writes the menu the build checks)"),
    "movements":   ("movements", None, "the movements a kit allows, by movement pattern, and --about for coaching notes"),
    "content":     ("content", None, "the filler plan for a session, what's been told, and the pantry"),
    "youtube":     ("youtube", None, "deep-dive videos, transcripts, series and puzzles"),
    "check":       ("context", "check", "check every context file in me/ (format, unfilled lines)"),
    "get":         ("context", "get", "print a setting: coach (the one used last), route (what a build uses here), routes, wpm, experience"),
    "deliver":     ("context", "deliver", "print the delivery folders that exist"),
    "log-session": ("context", "log-session", "add a checked session line to me/log.md"),
    "keys":        ("keys", None, "which web voice services have a key in me/.env (never the key), init and open"),
    "backup":      ("backup", None, "commit me/ and push it to its own private repo, if it is one"),
    "migrate":     ("migrate", None, "bring me/ up to this version's format (backs up first)"),
    "models":      ("models", None, "the local voice models in models/, and adopt the ones already downloaded"),
    "cache":       ("cache", None, "the clip cache's size, and prune"),
    "test":        (None, None, "run the engine's tests"),
    "setup":       (None, None, "first-run setup (environment, me/, privacy hook, voice model)"),
    "doctor":      (None, None, "what this computer can do: system, prerequisites, audio routes"),
}


def usage():
    width = max(map(len, COMMANDS))
    lines = ["usage: ./sweatcast <command> [options]   (./sweatcast <command> --help for its options)", ""]
    lines += [f"  {name:<{width}}  {what}" for name, (_, _, what) in COMMANDS.items()]
    return "\n".join(lines)


def main(argv=None):
    # A Windows console defaults to a code page that can't print an emoji in a video title or
    # headline; UTF-8 can, and anything a console still can't show prints as a placeholder.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(usage())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'.\n\n{usage()}", file=sys.stderr)
        return 64
    if cmd == "setup":   # a shell script, so it runs before there's a Python environment
        script = os.path.join(HERE, "setup.sh")
        if os.name == "nt":   # Git Bash's sh; Windows has no exec that keeps the exit code
            return subprocess.call([shutil.which("sh") or "sh", script, *rest])
        os.execv("/bin/sh", ["sh", script, *rest])
    if cmd == "doctor":   # a shell script too: it has to work before setup
        script = os.path.join(HERE, "doctor.sh")
        return subprocess.call([shutil.which("sh") or "sh", script, *rest])
    if cmd == "test":
        return subprocess.call([sys.executable, "-m", "unittest", "discover", "tests", *rest], cwd=ROOT)
    module, sub, _ = COMMANDS[cmd]
    sys.argv = [f"sweatcast {cmd}", *([sub] if sub else []), *rest]
    if sub:
        sys.argv[0] = "sweatcast"   # context's own parser names the subcommand
    result = importlib.import_module(module).main()
    return result or 0


if __name__ == "__main__":
    sys.exit(main())
