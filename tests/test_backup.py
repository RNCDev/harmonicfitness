"""`./sweatcast backup`: commit and push the context folder when it's its own repo.
Local repos and a bare remote only; no network."""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import backup  # noqa: E402
import cli  # noqa: E402
import paths  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def new_repo(path):
    os.makedirs(path, exist_ok=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "commit.gpgsign", "false")


def run(home, message="Workout", push=True):
    out = io.StringIO()   # both streams: a refusal goes to stderr
    with redirect_stdout(out), redirect_stderr(out):
        code = backup.backup(home, message, push=push)
    return code, out.getvalue()


@unittest.skipUnless(shutil.which("git"), "git not installed")
class Backup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "me")
        shutil.copytree(paths.EXAMPLE, self.home)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_not_its_own_repo_changes_nothing(self):
        new_repo(self.tmp)                      # an outer repo, like the engine's
        code, out = run(self.home)
        self.assertEqual(code, cli.OK)
        self.assertIn("isn't its own git repo", out)
        self.assertEqual(git(self.tmp, "status", "--porcelain").count("me/"), 1)   # still untracked
        with self.assertRaises(subprocess.CalledProcessError):
            git(self.tmp, "rev-parse", "HEAD")  # nothing was committed to the outer repo

    def test_commits_and_pushes_leaving_out_clips_and_mp3s(self):
        new_repo(self.home)
        remote = os.path.join(self.tmp, "remote.git")
        git(self.tmp, "init", "-q", "--bare", remote)
        git(self.home, "remote", "add", "origin", remote)
        cache = os.path.join(self.home, "workouts", ".audio-cache")
        os.makedirs(cache)
        for name in ("abc.pcm", "voice-pace.json"):
            open(os.path.join(cache, name), "w").close()
        open(os.path.join(self.home, "workouts", "Workout.mp3"), "w").close()

        code, out = run(self.home, "Workout 2026-10-22 Legs 30 min")
        self.assertEqual(code, cli.OK, out)
        self.assertIn("Pushed to origin", out)
        pushed = git(remote, "ls-tree", "-r", "--name-only", "HEAD").split()
        self.assertIn("profile.md", pushed)
        self.assertIn("workouts/.audio-cache/voice-pace.json", pushed)
        self.assertNotIn("workouts/.audio-cache/abc.pcm", pushed)
        self.assertNotIn("workouts/Workout.mp3", pushed)
        self.assertIn("Workout 2026-10-22 Legs 30 min", git(remote, "log", "-1", "--format=%s"))

        code, out = run(self.home)              # again, with nothing changed
        self.assertEqual(code, cli.OK, out)
        self.assertIn("Nothing new to commit", out)

    def test_no_remote_commits_locally(self):
        new_repo(self.home)
        code, out = run(self.home)
        self.assertEqual(code, cli.OK, out)
        self.assertIn("No remote", out)
        self.assertEqual(git(self.home, "status", "--porcelain"), "")

    def test_public_github_remote_is_refused(self):
        new_repo(self.home)
        git(self.home, "remote", "add", "origin", "https://github.com/someone/sweatcast-me.git")
        with mock.patch.object(backup, "visibility", return_value="PUBLIC") as seen, \
             mock.patch.object(backup, "git", wraps=backup.git) as calls:
            code, out = run(self.home)
        seen.assert_called_once_with("someone/sweatcast-me")
        self.assertEqual(code, cli.ISSUES)
        self.assertIn("is public", out)
        self.assertFalse([c for c in calls.call_args_list if "push" in c.args])
    def test_any_env_file_is_refused(self):
        new_repo(self.home)
        for name in ("keys.env", ".env.bak"):
            with open(os.path.join(self.home, name), "w", encoding="utf-8") as f:
                f.write("FISH_AUDIO_API_KEY=x\n")
        code, out = run(self.home, push=False)
        self.assertEqual(code, cli.ISSUES)
        self.assertIn("keys.env", out)
        self.assertIn(".env.bak", out)
        with self.assertRaises(subprocess.CalledProcessError):
            git(self.home, "rev-parse", "HEAD")   # nothing committed

    def test_an_unverifiable_github_remote_is_refused_unless_asked(self):
        new_repo(self.home)
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "-m", "first")
        git(self.home, "remote", "add", "origin", "https://github.com/someone/sweatcast-me.git")
        with mock.patch.object(backup, "visibility", return_value=None), \
                mock.patch.object(backup, "_push", return_value=subprocess.CompletedProcess([], 0, "", "")) as pushed:
            code, out = run(self.home)
            self.assertEqual(code, cli.ISSUES)
            self.assertIn("couldn't confirm", out)
            self.assertIn("--unverified", out)
            self.assertFalse(pushed.called)
            out = io.StringIO()
            with redirect_stdout(out):
                code = backup.backup(self.home, "Workout", push=True, unverified=True)
            self.assertEqual(code, cli.OK)
            self.assertTrue(pushed.called)
            # the verdict is remembered for this remote: the next plain run pushes without asking again
            pushed.reset_mock()
            code, out = run(self.home)
            self.assertEqual(code, cli.OK, out)
            self.assertTrue(pushed.called)
            git(self.home, "remote", "set-url", "origin", "https://github.com/someone/another-repo.git")
            code, out = run(self.home)   # another remote: not remembered
            self.assertEqual(code, cli.ISSUES)

    def test_a_private_verdict_is_remembered(self):
        new_repo(self.home)
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "-m", "first")
        git(self.home, "remote", "add", "origin", "https://github.com/someone/sweatcast-me.git")
        with mock.patch.object(backup, "visibility", side_effect=["PRIVATE", None]), \
                mock.patch.object(backup, "_push", return_value=subprocess.CompletedProcess([], 0, "", "")):
            self.assertEqual(run(self.home)[0], cli.OK)   # GitHub said private
            self.assertEqual(run(self.home)[0], cli.OK)   # GitHub silent: remembered

    def test_a_remembered_remote_that_turned_public_is_refused(self):
        new_repo(self.home)
        git(self.home, "add", "-A")
        git(self.home, "commit", "-q", "-m", "first")
        git(self.home, "remote", "add", "origin", "https://github.com/someone/sweatcast-me.git")
        backup.remember_private(self.home, "someone/sweatcast-me", "github")
        with mock.patch.object(backup, "visibility", return_value="PUBLIC"), \
                mock.patch.object(backup, "_push", return_value=subprocess.CompletedProcess([], 0, "", "")) as pushed:
            code, out = run(self.home)
        self.assertEqual(code, cli.ISSUES)
        self.assertIn("is public", out)
        self.assertFalse(pushed.called)

    def test_a_push_that_hangs_gives_up(self):
        with mock.patch.object(backup.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 1)):
            out = backup._push(self.home, ["push"])
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("no answer", out.stderr)

    def test_a_token_authenticates_the_api_read(self):
        seen = {}

        class Answer:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b'{"private": true, "visibility": "private"}'

        def fake_urlopen(req, timeout=None):
            seen["auth"] = req.get_header("Authorization")
            return Answer()
        import urllib.request
        with mock.patch.dict(os.environ, {"GH_TOKEN": "ghp_test_token"}), \
                mock.patch.object(urllib.request, "urlopen", fake_urlopen):
            self.assertEqual(backup._api_visibility("x/sweatcast-me"), "PRIVATE")
        self.assertEqual(seen["auth"], "Bearer ghp_test_token")

    def test_git_never_waits_on_a_credential_prompt(self):
        with mock.patch.object(backup.subprocess, "run",
                               return_value=subprocess.CompletedProcess([], 0, "", "")) as run_:
            backup.git(self.home, "status")
        self.assertEqual(run_.call_args.kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(run_.call_args.kwargs["env"]["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")   # nor on ssh's
        with mock.patch.dict(os.environ, {"GIT_SSH_COMMAND": "ssh -i ~/.ssh/other"}), \
                mock.patch.object(backup.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 0, "", "")) as run_:
            backup.git(self.home, "status")
        self.assertEqual(run_.call_args.kwargs["env"]["GIT_SSH_COMMAND"], "ssh -i ~/.ssh/other")   # the listener's own


    def test_github_slug(self):
        self.assertEqual(backup.github_slug("https://github.com/RNC/sweatcast-me.git\n"), "RNC/sweatcast-me")
        self.assertEqual(backup.github_slug("git@github.com:RNC/sweatcast-me.git"), "RNC/sweatcast-me")
        self.assertEqual(backup.github_slug("https://github.com/RNC/sweatcast-me"), "RNC/sweatcast-me")
        self.assertIsNone(backup.github_slug("/srv/git/me.git"))


class Template(unittest.TestCase):
    def test_example_gitignore_keeps_the_pace_and_drops_clips(self):
        with open(os.path.join(paths.EXAMPLE, ".gitignore"), encoding="utf-8") as f:
            lines = f.read().split("\n")
        for rule in ("workouts/.audio-cache/*", "!workouts/.audio-cache/voice-pace.json", "*.mp3"):
            self.assertIn(rule, lines)


class Visibility(unittest.TestCase):
    """Without gh (Claude Code on the web), GitHub's API still says whether a repo is public."""

    def serve(self, status, body):
        import http.server
        import threading

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/repos/"

    def test_visibility_without_gh(self):
        with mock.patch.object(backup.shutil, "which", return_value=None):
            with mock.patch.object(backup, "API", self.serve(200, '{"private": false, "visibility": "public"}')):
                self.assertEqual(backup.visibility("x/sweatcast-me"), "PUBLIC")
            with mock.patch.object(backup, "API", self.serve(404, '{"message": "Not Found"}')):
                self.assertIsNone(backup.visibility("x/sweatcast-me"))


if __name__ == "__main__":
    unittest.main()
