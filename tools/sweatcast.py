"""The `./sweatcast` command: one entry point that runs each tool in the project's
environment (.venv, Python 3.11, made by `./sweatcast setup`).

    ./sweatcast <command> [options]      # ./sweatcast help lists them
"""
import importlib
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# command: (module, the subcommand it stands for in that module, or None; what it does)
COMMANDS = {
    "build":       (None, None, "lint a draft, render it to an MP3 and copy it to your phone's folder"),
    "lint":        ("tts_build", None, "lint a draft and export its clean transcript (no render)"),
    "render":      ("render", None, "render a draft to audio (build runs this for you)"),
    "voices":      ("voices", None, "list, measure, download, design and keep voices"),
    "feeds":       ("feeds", None, "fetch the profile's feeds into today's sheet"),
    "coverage":    ("coverage", None, "muscle groups the last sessions left out, last format and loads"),
    "youtube":     ("youtube", None, "deep-dive videos, transcripts, series and puzzles"),
    "check":       ("context", "check", "check every context file in me/ (format, unfilled lines)"),
    "get":         ("context", "get", "print a profile setting: default-voice, wpm, voices"),
    "deliver":     ("context", "deliver", "print the delivery folders that exist"),
    "log-session": ("context", "log-session", "add a checked session line to me/log.md"),
    "migrate":     ("migrate", None, "bring me/ up to this version's format (backs up first)"),
    "cache":       ("cache", None, "the clip cache's size, and prune"),
    "test":        (None, None, "run the engine's tests"),
    "setup":       (None, None, "first-run setup (environment, me/, privacy hook, voice model)"),
}


def usage():
    width = max(map(len, COMMANDS))
    lines = ["usage: ./sweatcast <command> [options]   (./sweatcast <command> --help for its options)", ""]
    lines += [f"  {name:<{width}}  {what}" for name, (_, _, what) in COMMANDS.items()]
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("help", "-h", "--help"):
        print(usage())
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'.\n\n{usage()}", file=sys.stderr)
        return 64
    if cmd == "build":
        os.execv("/bin/sh", ["sh", os.path.join(HERE, "build.sh"), *rest])
    if cmd == "setup":
        os.execv("/bin/sh", ["sh", os.path.join(HERE, "setup.sh"), *rest])
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
