"""The `./harmonicfitness` command: one entry point that runs each tool in the project's
environment (.venv, Python 3.11, made by `./harmonicfitness setup`).

    ./harmonicfitness <command> [options]      # ./harmonicfitness help lists them
"""
import importlib
import importlib.util
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cli  # noqa: E402

# command: (module, the subcommand it stands for in that module, or None; what it does)
COMMANDS = {
    "build":       ("build", None, "lint a draft, render it to an MP3 and copy it to your phone's folder"),
    "coaches":     ("coaches", None, "your coaches: audition, keep, archive, choose, measure and tune them"),
    "feeds":       ("feeds", None, "fetch the profile's feeds into today's sheet"),
    "coverage":    ("coverage", None, "movement patterns the last sessions left out, last format and loads"),
    "brief":       ("brief", None, "today's ingredients: the listener, limits, safe menu, programming guide (--save writes the menu the build checks)"),
    "movements":   ("movements", None, "the movements a kit allows, by movement pattern, and --about for coaching notes"),
    "content":     ("content", None, "the topics due, the formats, what's been told, the stock, and what's trending"),
    "youtube":     ("youtube", None, "deep-dive videos, transcripts, series and puzzles"),
    "check":       ("check", None, "check every context file in me/ (format, unfilled lines)"),
    "get":         ("context", "get", "print a setting: coach (the one used last), route (what a build uses here), routes, wpm, experience, web-builds"),
    "deliver":     ("context", "deliver", "print the delivery folders that exist"),
    "log-session": ("context", "log-session", "add a checked session line to me/log.md"),
    "show":        ("player", None, "open the folder holding a file (a workout's MP3), with it selected"),
    "keys":        ("keys", None, "which web voice services have a key in me/.env (never the key), init and open"),
    "pull":        ("webpull", None, "bring the web app's files, latest conversation and its MP3s into me/web/ (signs in with HARMONIC_USERNAME and HARMONIC_PASSWORD from me/.env)"),
    "backup":      ("backup", None, "commit me/ and push it to its own private repo, if it is one"),
    "migrate":     ("migrate", None, "bring me/ up to this version's format (backs up first)"),
    "models":      ("models", None, "the local voice models in models/, and adopt the ones already downloaded"),
    "cache":       ("cache", None, "the clip cache's size, and prune"),
    "harness":     ("harness", None, "check that ChatGPT's Codex files match the Claude Code ones; sync rewrites them"),
    "test":        (None, None, "run the engine's tests"),
    "setup":       (None, None, "first-run setup (environment, me/, privacy hook, voice model)"),
    "doctor":      (None, None, "what this computer can do: system, prerequisites, audio routes"),
}

# Commands that are gone, and what does their work now.
RETIRED = {"lint": "./harmonicfitness build <draft> \"<name>\" --lint-only",
           "render": "./harmonicfitness build <draft> \"<name>\""}


def usage():
    width = max(map(len, COMMANDS))
    lines = ["usage: ./harmonicfitness <command> [options]   (./harmonicfitness <command> --help for its options)", ""]
    lines += [f"  {name:<{width}}  {what}" for name, (_, _, what) in COMMANDS.items()]
    return "\n".join(lines)


def test_env(env):
    """The environment the tests run in: HARMONICFITNESS_HOME pointed at an absent folder (as in CI, where there is
    no me/), unless it's already set, so no test can read or write the real context folder."""
    env = dict(env)
    if not env.get("HARMONICFITNESS_HOME"):
        env["HARMONICFITNESS_HOME"] = os.path.join(tempfile.mkdtemp(prefix="harmonicfitness-tests-"), "me")
    # The stock coaches the tests see: a fixture set, so a test never depends on the real ten.
    env.setdefault("HARMONICFITNESS_SHIPPED", os.path.join(ROOT, "tests", "fixtures", "stock"))
    return env


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
    if cmd in RETIRED:
        print(f"./harmonicfitness {cmd} is gone (HarmonicFitness 0.14): use {RETIRED[cmd]}.", file=sys.stderr)
        return cli.USAGE
    if cmd not in COMMANDS:
        print(f"Unknown command '{cmd}'.\n\n{usage()}", file=sys.stderr)
        return cli.USAGE
    if cmd in ("setup", "doctor"):   # shell scripts, run by the ./harmonicfitness wrapper before any environment exists
        print(f"Run ./harmonicfitness {cmd} (the shell wrapper runs tools/{cmd}.sh; it needs no Python environment).",
              file=sys.stderr)
        return cli.USAGE
    if cmd == "test":
        env = test_env(os.environ)
        code = subprocess.call([sys.executable, "-m", "unittest", "discover", "tests", *rest], cwd=ROOT, env=env)
        # The web client's tests (web/), when its optional extra is installed; their failure fails the command.
        if importlib.util.find_spec("fastapi") is None:
            print("web tests skipped: install with uv sync --extra web")
            return code
        web = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "web/webtests", "-t", "web", *rest],
                              cwd=ROOT, env=env)
        return code or web
    module, sub, _ = COMMANDS[cmd]
    sys.argv = [f"harmonicfitness {cmd}", *([sub] if sub else []), *rest]
    if sub:
        sys.argv[0] = "harmonicfitness"   # context's own parser names the subcommand
    return cli.run(importlib.import_module(module).main)


if __name__ == "__main__":
    sys.exit(main())
