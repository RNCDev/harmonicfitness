"""The command line's contract with the skills and Codex, which branch on exit codes (tools/cli.py):
a mistyped command or option is 64 on every command, and help is 0. The codes 1 to 4 on the paths that
raise them are pinned where those paths are tested (test_tools, test_cloud, test_routes, test_verify);
an unexpected exception is 70, here."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (puts tools/ on the path)
import cli  # noqa: E402
import paths  # noqa: E402
import harmonicfitness  # noqa: E402

# setup and doctor are shell scripts (the wrapper runs them); test runs the suite.
PYTHON_COMMANDS = [c for c in harmonicfitness.COMMANDS if c not in ("setup", "doctor", "test")]


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = harmonicfitness.main(list(argv))
    finally:
        sys.argv = saved
    return code, out.getvalue(), err.getvalue()


class Contract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copytree(paths.EXAMPLE, os.path.join(self.tmp, "me"))
        self.home = helpers.home(os.path.join(self.tmp, "me"))
        self.home.__enter__()

    def tearDown(self):
        self.home.__exit__(None, None, None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_help_is_zero(self):
        for argv in ([], ["help"], ["--help"]):
            code, out, _ = run(*argv)
            self.assertEqual(code, cli.OK, argv)
            self.assertIn("usage: ./harmonicfitness", out)

    def test_unknown_and_retired_commands_are_usage(self):
        for argv in (["nonsense"], ["lint", "x.draft.txt"], ["render", "x.draft.txt", "x"], ["setup"], ["doctor"]):
            code, out, err = run(*argv)
            self.assertEqual(code, cli.USAGE, argv)
            self.assertTrue(err.strip(), argv)

    def test_an_unknown_option_is_usage_on_every_command(self):
        for cmd in PYTHON_COMMANDS:
            argv = [cmd, "--no-such-option-anywhere"]
            if cmd == "get":
                argv = [cmd, "coach", "--no-such-option-anywhere"]
            with self.subTest(cmd=cmd):
                code, _, err = run(*argv)
                self.assertEqual(code, cli.USAGE)
                self.assertIn("error:", err)   # the unknown option, or a required argument missing first

    def test_every_command_has_help(self):
        for cmd in PYTHON_COMMANDS:
            with self.subTest(cmd=cmd):
                argv = [cmd, "--help"]
                code, out, _ = run(*argv)
                self.assertEqual(code, cli.OK)
                self.assertIn("usage:", out.lower())

    def test_a_missing_draft_is_usage(self):
        code, _, err = run("build", os.path.join(self.tmp, "absent.draft.txt"), "x")
        self.assertEqual(code, cli.USAGE)
        self.assertTrue(err.strip())

    def test_an_unknown_goal_is_usage(self):
        code, _, err = run("brief", "--goal", "levitation", "--minutes", "20", "--preset", "bodyweight")
        self.assertEqual(code, cli.USAGE)
        self.assertIn("levitation", err)

    def test_an_unknown_coach_is_usage(self):
        draft = os.path.join(paths.ROOT, "knowledge", "smoke-test.draft.txt")
        code, _, err = run("build", draft, "x", "--coach", "coach-nobody-at-all", "--lint-only")
        self.assertEqual(code, cli.USAGE)
        self.assertTrue(err.strip())


class FlagNames(unittest.TestCase):
    """The flag rule in cli.py: --date is a recorded day, --today only "pretend today is"; no parser takes both,
    and --json is on the commands whose --help documents it. Every command's parsers are walked by running its
    --help with add_argument recorded."""
    TODAY = {"harmonicfitness brief", "harmonicfitness content plan", "harmonicfitness content trending",
             "harmonicfitness build"}
    DATE = {"harmonicfitness log-session", "harmonicfitness content log", "harmonicfitness content thread",
            "harmonicfitness interests add"}
    JSON = {"harmonicfitness balances", "harmonicfitness coaches list", "harmonicfitness content plan", "harmonicfitness coverage", "harmonicfitness get",
            "harmonicfitness interests", "harmonicfitness ready", "harmonicfitness topics", "harmonicfitness workouts"}

    def flags(self):
        import argparse
        from unittest import mock
        seen = {}
        real = argparse.ArgumentParser.add_argument

        def record(parser, *args, **kw):
            seen.setdefault(parser.prog, set()).update(a for a in args if a.startswith("-"))
            return real(parser, *args, **kw)

        with tempfile.TemporaryDirectory() as d, helpers.home(os.path.join(d, "me")), \
                mock.patch.object(argparse.ArgumentParser, "add_argument", record):
            shutil.copytree(paths.EXAMPLE, paths.HOME)
            for cmd in PYTHON_COMMANDS:
                run(cmd, "--help")
        return seen

    def numeric_options(self):
        """{(prog, flag): type} for every option whose value is a number, found by its type= or its default."""
        import argparse
        from unittest import mock
        seen = {}
        real = argparse.ArgumentParser.add_argument

        def record(parser, *args, **kw):
            flags = [a for a in args if a.startswith("--")]
            kind = kw.get("type")
            if flags and (kind in (int, float) or kind in cli.NUMBER_TYPES
                          or (kind is None and isinstance(kw.get("default"), (int, float))
                              and not isinstance(kw.get("default"), bool) and kw.get("action") is None)):
                seen[(parser.prog, flags[0])] = kind
            return real(parser, *args, **kw)

        with tempfile.TemporaryDirectory() as d, helpers.home(os.path.join(d, "me")), \
                mock.patch.object(argparse.ArgumentParser, "add_argument", record):
            shutil.copytree(paths.EXAMPLE, paths.HOME)
            for cmd in PYTHON_COMMANDS:
                run(cmd, "--help")
        return seen

    def test_every_numeric_option_is_range_checked(self):
        seen = self.numeric_options()
        self.assertIn(("harmonicfitness brief", "--minutes"), seen)   # the walk reached the commands
        loose = {k: getattr(t, "__name__", t) for k, t in seen.items() if t not in cli.NUMBER_TYPES}
        self.assertEqual(loose, {}, "use cli.positive_int, non_negative_int, positive_float or non_negative_float")

    def test_a_bad_number_is_usage(self):
        for argv in (["brief", "--goal", "strength", "--minutes", "0", "--preset", "bodyweight"],
                     ["content", "plan", "--minutes", "-3"], ["coverage", "--last", "0"],
                     ["cache", "prune", "--days", "-1"], ["feeds", "--hours", "nan"],
                     ["youtube", "pick", "--recent", "two"]):
            with self.subTest(argv=argv):
                code, _, err = run(*argv)
                self.assertEqual(code, cli.USAGE)
                self.assertIn("error:", err)

    def test_date_and_today_follow_the_rule(self):
        seen = self.flags()
        self.assertIn("harmonicfitness coverage", seen)   # the walk reached the commands
        both = [prog for prog, f in seen.items() if {"--today", "--date"} <= f]
        self.assertEqual(both, [])
        self.assertEqual({prog for prog, f in seen.items() if "--today" in f}, self.TODAY)
        self.assertEqual({prog for prog, f in seen.items() if "--date" in f}, self.DATE)
        self.assertEqual({prog for prog, f in seen.items() if "--json" in f}, self.JSON)


class ErrorChannel(unittest.TestCase):
    """Library code reports a problem by raising a typed error carrying its exit code; only cli.run ends the
    process. (cli.Usage, a SystemExit, is left to argparse and the commands' main functions; below main a
    wrong command is errors.UsageError, exit 64.)"""

    def test_typed_errors_map_to_their_codes(self):
        import errors
        for exc, code in ((errors.ContextError("x"), cli.ISSUES), (errors.LogRefused("Not logged: x"), cli.ISSUES),
                          (errors.RenderStopped("x", exit_code=cli.SERVICE), cli.SERVICE),
                          (errors.DraftError("x"), cli.ISSUES), (cli.Usage("x"), cli.USAGE),
                          (errors.UsageError("x"), cli.USAGE)):
            def main(e=exc):
                raise e
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.run(main), code, type(exc).__name__)
            self.assertIn("x", err.getvalue())
        self.assertEqual(errors.CoachError("named").code, "named")   # read like SystemExit's code

    def test_a_damaged_services_file_is_a_clean_exit(self):
        """keys and cloud read knowledge/services.toml on first use, not at import, so a damaged file is the reason a
        command stops (exit 1), never a traceback. A process of its own: keys and cloud are imported afresh there."""
        import subprocess
        code = (
            "import sys\n"
            f"sys.path.insert(0, {os.path.join(paths.ROOT, 'tools')!r})\n"
            "import services\n"
            "def damaged():\n"
            "    raise services.SettingsError(\"services.toml isn't valid TOML\")\n"
            "services.settings = damaged\n"
            "import keys, cloud, cli\n"
            "def main():\n"
            "    return len(keys.SERVICE_VARS)\n"
            "sys.exit(cli.run(main))\n")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
                             env={**os.environ, "HARMONICFITNESS_HOME": os.path.join(tempfile.gettempdir(), "absent")})
        self.assertEqual(out.returncode, cli.ISSUES, out.stderr)
        self.assertIn("SettingsError", out.stderr)   # its words withheld: the key scrubber needs the same file
        self.assertNotIn("Traceback", out.stderr)

    def test_an_engine_bug_is_70_with_its_traceback_scrubbed(self):
        from unittest import mock
        self.assertEqual(cli.BUG, 70)   # EX_SOFTWARE: the skills stop and report, never edit the draft

        def main():
            raise ValueError("broke near secret-key-123456")
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "secret-key-123456"}), \
                contextlib.redirect_stderr(err):
            self.assertEqual(cli.run(main), cli.BUG)
        self.assertIn("Traceback", err.getvalue())
        self.assertIn("ValueError", err.getvalue())
        self.assertNotIn("secret-key-123456", err.getvalue())

    def test_no_engine_module_raises_systemexit(self):
        import re
        tools = os.path.join(paths.ROOT, "tools")
        found = []
        for folder in (tools, os.path.join(tools, "services")):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".py") and name not in ("cli.py", "errors.py"):
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        for n, line in enumerate(f, 1):
                            if re.search(r"raise[ (][^#]*\bSystemExit\b|sys\.exit\((?!cli\.run|main)", line):
                                found.append(f"{name}:{n}: {line.strip()}")
        self.assertEqual(found, [], "raise an errors.HarmonicFitnessError (or cli.Usage) instead")

    def test_only_commands_import_cli(self):
        """A module with no main is library code: it raises errors' typed errors and reads the exit codes from
        errors, so it never imports cli (whose Usage is a SystemExit)."""
        import ast
        tools = os.path.join(paths.ROOT, "tools")
        found = []
        for folder in (tools, os.path.join(tools, "services")):
            for name in sorted(os.listdir(folder)):
                if not name.endswith(".py") or name == "cli.py":
                    continue
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                if any(isinstance(n, ast.FunctionDef) and n.name == "main" for n in tree.body):
                    continue
                for n in ast.walk(tree):
                    names = ([a.name for a in n.names] if isinstance(n, ast.Import)
                             else [n.module] if isinstance(n, ast.ImportFrom) else [])
                    if "cli" in names:
                        found.append(f"{name}:{n.lineno}")
        self.assertEqual(found, [], "library code raises errors.UsageError and reads codes from errors")


    def test_paths_are_read_at_call_time(self):
        """`from paths import X` copies X at import, so a test (or HARMONICFITNESS_HOME read later) that points paths
        elsewhere misses it. Only show (a function) and ROOT (the engine's own folder) may be imported so."""
        import ast
        found = []
        for folder, _, files in os.walk(os.path.join(paths.ROOT, "tools")):
            for name in sorted(files):
                if name.endswith(".py"):
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        tree = ast.parse(f.read())
                    for n in ast.walk(tree):
                        if isinstance(n, ast.ImportFrom) and n.module == "paths":
                            found += [f"{name}:{n.lineno}: {a.name}" for a in n.names if a.name not in ("show", "ROOT")]
        self.assertEqual(found, [], "read paths.X when it's needed")

    def test_libraries_import_no_command_or_http_module_they_dont_need(self):
        """brief reads the catalog, not the movements command; records reads services.toml and redact, not the
        HTTP engine in cloud.py."""
        import ast

        def imports(module):
            with open(os.path.join(paths.ROOT, "tools", module + ".py"), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            return {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | \
                {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertNotIn("movements", imports("brief"))
        self.assertNotIn("cloud", imports("records"))


def python_files(*folders):
    for folder in folders:
        for here, dirs, files in os.walk(os.path.join(paths.ROOT, folder)):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules", "fixtures")]
            yield from (os.path.join(here, f) for f in sorted(files) if f.endswith(".py"))


class SameOnEveryComputer(unittest.TestCase):
    """Text read or written without a named encoding is UTF-8 on a Mac and the code page (cp1252) on Windows: a
    name with an accent or a dash reads back garbled there, or stops the read. So every text-mode open(), Path
    read or write, and subprocess decoding names its encoding, in the engine, the web app and their tests."""

    def test_text_names_its_encoding(self):
        import ast
        found = []
        for path in python_files("tools", "tests", "web"):
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for n in ast.walk(tree):
                if not isinstance(n, ast.Call) or any(k.arg == "encoding" for k in n.keywords):
                    continue
                kw = {k.arg: k.value for k in n.keywords}
                func = n.func
                name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
                if name == "open" and isinstance(func, ast.Name):
                    mode = n.args[1] if len(n.args) > 1 else kw.get("mode")
                    text = mode is None or (isinstance(mode, ast.Constant) and "b" not in str(mode.value))
                elif name in ("read_text", "write_text"):
                    text = True
                elif name in ("run", "check_output", "Popen", "check_call", "call"):
                    flag = kw.get("text") or kw.get("universal_newlines")
                    text = isinstance(flag, ast.Constant) and flag.value is True
                else:
                    text = False
                if text:
                    found.append(f"{os.path.relpath(path, paths.ROOT)}:{n.lineno}")
        self.assertEqual(found, [], 'name the encoding (encoding="utf-8"), so Windows reads what a Mac wrote')

    def test_line_endings_are_pinned(self):
        # Without it, Git for Windows checks the shell scripts out with CRLF (core.autocrlf), and a file's bytes
        # differ from a Mac's.
        with open(os.path.join(paths.ROOT, ".gitattributes"), encoding="utf-8") as f:
            rules = [line.split() for line in f if line.strip() and not line.startswith("#")]
        self.assertIn(["*", "text=auto", "eol=lf"], rules)


if __name__ == "__main__":
    unittest.main()
