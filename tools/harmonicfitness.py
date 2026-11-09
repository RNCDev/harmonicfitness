"""The `./harmonicfitness` command: one entry point that runs each tool in the project's
environment (.venv, Python 3.11, made by `./harmonicfitness setup`).

    ./harmonicfitness <command> [options]      # ./harmonicfitness help lists them
"""
import atexit
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cli  # noqa: E402
import testpick  # noqa: E402
import testrun  # noqa: E402

# command: (module, the subcommand it stands for in that module, or None; what it does)
COMMANDS = {
    "build":       ("build", None, "lint a draft, render it to an MP3 and copy it to your phone's folder"),
    "coaches":     ("coaches", None, "your coaches: audition, keep, archive, choose, measure and tune them"),
    "feeds":       ("feeds", None, "fetch the profile's feeds into today's sheet"),
    "coverage":    ("coverage", None, "movement patterns the last sessions left out, last format and loads"),
    "brief":       ("brief", None, "today's ingredients: the listener, limits, safe menu, programming guide (--save writes the menu the build checks)"),
    "movements":   ("movements", None, "the movements a kit allows, by movement pattern, and --about for coaching notes"),
    "content":     ("content", None, "the topics due, the formats, what's been told, the stock, and what's trending"),
    "topics":      ("topics", None, "the topics and venues; add one at once, its feed found (a site, newsletter, blog or podcast)"),
    "interests":   ("interests", None, "what the listener has shown they like, learned from feedback and mentions: list, add, forget, apply"),
    "youtube":     ("youtube", None, "deep-dive videos, transcripts, series and puzzles"),
    "check":       ("check", None, "check every context file in me/ (format, unfilled lines)"),
    "get":         ("context", "get", "print a setting: coach (the one used last), route (what a build uses here), routes, wpm, experience, web-builds"),
    "set":         ("context", "set", "change a setting: experience (novice, experienced or advanced), every other line kept"),
    "deliver":     ("context", "deliver", "print the delivery folders that exist"),
    "log-session": ("context", "log-session", "add a checked session line to me/log.md"),
    "workouts":    ("workoutlog", None, "the workouts logged: list them, add feedback on one, or delete one (its log line, stories told and threads)"),
    "show":        ("player", None, "open the folder holding a file (a workout's MP3), with it selected"),
    "keys":        ("keys", None, "which web voice services have a key in me/.env (never the key), init, open, and upload to the web app"),
    "balances":    ("balances", None, "what's left on each web voice service's account (Fish Audio and ElevenLabs say; the others link their billing page)"),
    "pull":        ("webpull", None, "bring the web app's files, latest conversation and its MP3s into me/web/ (signs in with HARMONIC_USERNAME and HARMONIC_PASSWORD from me/.env)"),
    "sync":        ("websync", None, "keep me/ in step with your files on the web app, both ways (signs in with HARMONIC_USERNAME and HARMONIC_PASSWORD from me/.env)"),
    "backup":      ("backup", None, "commit me/ and push it to its own private repo, if it is one"),
    "migrate":     ("migrate", None, "bring me/ up to this version's format (backs up first)"),
    "models":      ("models", None, "the local voice models in models/, and adopt the ones already downloaded"),
    "cache":       ("cache", None, "the clip cache's size, and prune"),
    "ready":       ("ready", None, "the ready-made workouts: five thirty-minute sessions recorded once, to play while your own coach gets ready"),
    "demos":       ("demos", None, "the home page's demo clips (docs/demos/): each demo listener's folder, run a command as one, cut a clip's segments, publish it"),
    "harness":     ("harness", None,"check that ChatGPT's Codex files match the Claude Code ones; sync rewrites them"),
    "test":        (None, None, "run the engine's tests, then the web app's (test engine, or test web, runs one; test changed only those covering what's changed; test <name> one module)"),
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
    env.pop("HARMONICFITNESS_KEYS", None)   # a key file outside the test home would be read by the tests
    if not env.get("HARMONICFITNESS_HOME"):
        env["HARMONICFITNESS_HOME"] = os.path.join(tempfile.mkdtemp(prefix="harmonicfitness-tests-"), "me")
    # The stock coaches the tests see: a fixture set, so a test never depends on the real ten.
    env.setdefault("HARMONICFITNESS_SHIPPED", os.path.join(ROOT, "tests", "fixtures", "stock"))
    return env


def engine_env(env):
    """The test environment with tests/ importable, so a batch can name its classes ("test_tools.RenderLock")."""
    return dict(env, PYTHONPATH=os.pathsep.join(filter(None, [os.path.join(ROOT, "tests"), env.get("PYTHONPATH")])))


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
        if not os.environ.get("HARMONICFITNESS_HOME"):   # the run's own temporary home goes when it ends
            atexit.register(shutil.rmtree, os.path.dirname(env["HARMONICFITNESS_HOME"]), True)
        # "changed" runs only the engine tests that cover what's changed and not yet pushed (tools/testpick.py);
        # names ("demos", "test_media") run those modules. Either is the loop while working; CI runs everything.
        # a name is any argument that isn't an option or the pattern after -k
        names = [a for i, a in enumerate(rest) if not a.startswith("-") and (i == 0 or rest[i - 1] != "-k")]
        if names and names[0] not in ("engine", "web"):
            tests = testpick.sources(os.path.join(ROOT, "tests"), "test_")
            if names == ["changed"]:
                files = testpick.changed_files(ROOT)
                picked = testpick.pick(files, tests, testpick.sources(os.path.join(ROOT, "tools")))
                print(f"{len(picked)} of {len(tests)} test modules, for {len(files)} changed files"
                      + (" (web/ changed: run test web, or let CI)" if any(f.startswith("web/") for f in files) else ""))
            else:
                picked = [n if n.startswith("test_") else f"test_{n}" for n in names]
                unknown = [n for n in picked if n not in tests]
                if unknown:
                    print(f"No such test module: {', '.join(unknown)} (tests/test_<name>.py)", file=sys.stderr)
                    return cli.USAGE
            opts = [a for a in rest if a not in names]
            if not picked:
                return 0
            return testrun.run(ROOT, engine_env(env), picked, opts, verbose="-v" in opts)
        # "engine" or "web" first runs only that half (CI runs them side by side, and skips the engine's when a
        # push changed only web/). The engine's run side by side, a batch of test classes per core (tools/testrun.py).
        part = rest.pop(0) if rest and rest[0] in ("engine", "web") else None
        code = 0
        if part != "web":
            code = testrun.run(ROOT, engine_env(env), (), rest, verbose="-v" in rest)
        if part == "engine":
            return code
        # The web client's tests (web/), when its optional extra is installed; their failure fails the command.
        if importlib.util.find_spec("fastapi") is None:
            if part == "web":
                print("web tests need the web extra: uv sync --extra web", file=sys.stderr)
                return cli.USAGE
            print("web tests skipped: install with uv sync --extra web")
            return code
        web = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "web/webtests", "-t", "web", *rest],
                              cwd=ROOT, env=env)
        return code or web
    module, sub, _ = COMMANDS[cmd]
    if cmd == "keys" and rest[:1] == ["upload"]:   # its own module, above keys and webpull
        module, cmd, rest = "webkeys", "keys upload", rest[1:]
    sys.argv = [f"harmonicfitness {cmd}", *([sub] if sub else []), *rest]
    if sub:
        sys.argv[0] = "harmonicfitness"   # context's own parser names the subcommand
    return cli.run(importlib.import_module(module).main)


if __name__ == "__main__":
    sys.exit(main())
