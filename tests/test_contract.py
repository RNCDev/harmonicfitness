"""The command line's contract with the skills and Codex, which branch on exit codes (tools/cli.py):
a mistyped command or option is 64 on every command, and help is 0. The codes 1 to 4 on the paths that
raise them are pinned where those paths are tested (test_tools, test_cloud, test_routes, test_verify)."""
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
import sweatcast  # noqa: E402

# setup and doctor are shell scripts (the wrapper runs them); test runs the suite.
PYTHON_COMMANDS = [c for c in sweatcast.COMMANDS if c not in ("setup", "doctor", "test")]


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    saved = sys.argv
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sweatcast.main(list(argv))
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
            self.assertIn("usage: ./sweatcast", out)

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


if __name__ == "__main__":
    unittest.main()
