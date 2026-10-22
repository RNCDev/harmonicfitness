"""`./sweatcast backup`: commit and push the context folder when it's its own repo.
Local repos and a bare remote only; no network."""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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
    out = io.StringIO()
    with redirect_stdout(out):
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


if __name__ == "__main__":
    unittest.main()
