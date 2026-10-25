"""Cloud voice keys in me/.env: read only by the engine, never printed, never backed up.
Every key here is a made-up test value in a temporary folder."""
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
sys.path.insert(0, os.path.join(ROOT, "tests"))

import keys  # noqa: E402
from test_backup import git, new_repo, run as run_backup  # noqa: E402

SECRET = "sk-test-NEVERPRINT-123"


class Keys(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        clean = {k: v for k, v in os.environ.items() if k not in keys.SERVICE_VARS.values()}
        patcher = mock.patch.dict(os.environ, clean, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, data):
        with open(self.env, "wb") as f:
            f.write(data)

    def test_env_formats_all_read(self):
        for text in (b"FISH_AUDIO_API_KEY=x\n", b"export FISH_AUDIO_API_KEY=x\n", b'FISH_AUDIO_API_KEY = "x"\n',
                     b"FISH_AUDIO_API_KEY='x'\n", b"# a note\r\nFISH_AUDIO_API_KEY=x\r\n",
                     b"\xef\xbb\xbfFISH_AUDIO_API_KEY=x\n", b"OTHER=y\nFISH_AUDIO_API_KEY=x   \n"):
            self.write(text)
            self.assertEqual(keys.get("fish", path=self.env), "x", text)
        self.write(b"FISH_AUDIO_API_KEY=\n")
        self.assertIsNone(keys.get("fish", path=self.env))
        self.assertFalse(keys.is_set("fish", path=self.env))

    def test_the_environment_wins(self):
        self.write(b"FISH_AUDIO_API_KEY=from-file\n")
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "from-env"}):
            self.assertEqual(keys.get("fish", path=self.env), "from-env")

    def test_keys_command_never_prints_a_value(self):
        home = os.path.join(self.d, "me")
        os.makedirs(home)
        with open(os.path.join(home, ".env"), "w") as f:
            f.write(f"FISH_AUDIO_API_KEY={SECRET}\n")
        env = dict(os.environ, SWEATCAST_HOME=home, SWEATCAST_PYTHON=sys.executable)
        out = subprocess.run(["sh", "sweatcast", "keys"], cwd=ROOT, env=env, capture_output=True, text=True,
                             timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn(SECRET, out.stdout + out.stderr)
        self.assertRegex(out.stdout, r"fish.*: set")
        self.assertRegex(out.stdout, r"elevenlabs.*: not set")

    def test_init_appends_once_and_is_private(self):
        path = keys.init("elevenlabs", path=self.env)
        keys.init("elevenlabs", path=self.env)
        with open(path) as f:
            text = f.read()
        self.assertEqual(text.count("ELEVENLABS_API_KEY="), 1)
        self.assertIn("elevenlabs.io", text)
        self.assertFalse(keys.is_set("elevenlabs", path=self.env))
        if os.name != "nt":
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)

    def test_init_keeps_what_is_there(self):
        self.write(f"FISH_AUDIO_API_KEY={SECRET}\n".encode())
        keys.init("fish", path=self.env)
        keys.init("gemini", path=self.env)
        keys.init("inworld", path=self.env)
        self.assertEqual(keys.get("fish", path=self.env), SECRET)
        with open(self.env) as f:
            text = f.read()
        self.assertIn("GEMINI_API_KEY=", text)
        self.assertIn("INWORLD_API_KEY=", text)

    def test_keys_lists_four_services(self):
        self.assertEqual(list(keys.SERVICE_VARS), ["fish", "elevenlabs", "gemini", "inworld"])
        self.assertEqual(keys.SERVICE_VARS["gemini"], "GEMINI_API_KEY")
        self.assertEqual(keys.SERVICE_VARS["inworld"], "INWORLD_API_KEY")
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(keys.paths, "ENV_FILE", self.env):
            keys.main([])
        self.assertEqual([ln.split(":")[0].strip() for ln in out.getvalue().splitlines()],
                         ["fish", "elevenlabs", "gemini", "inworld"])

    def test_keys_open_uses_the_system_editor(self):
        calls = []
        with mock.patch.object(keys, "_read", side_effect=AssertionError("open must not read the file")):
            for platform, argv in (("darwin", ["open", "-e", self.env]), ("win32", ["notepad", self.env]),
                                   ("linux", ["xdg-open", self.env])):
                with mock.patch.object(keys.sys, "platform", platform), \
                        mock.patch.object(keys.paths, "REMOTE", False):
                    self.assertEqual(keys.open_env(self.env, run=lambda a: calls.append(a)), argv)
                self.assertEqual(calls[-1], argv)
        self.assertTrue(os.path.exists(self.env))   # made with init's header
        with open(self.env) as f:
            text = f.read()
        self.assertIn("API keys for sweatcast", text)
        self.assertNotIn("_API_KEY=", text)   # no service line added
        if os.name != "nt":
            self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)

    def test_keys_open_leaves_an_existing_file_alone(self):
        self.write(f"FISH_AUDIO_API_KEY={SECRET}\n".encode())
        with mock.patch.object(keys.paths, "REMOTE", False):
            keys.open_env(self.env, run=lambda a: None)
        with open(self.env) as f:
            self.assertEqual(f.read(), f"FISH_AUDIO_API_KEY={SECRET}\n")

    def test_keys_open_without_an_opener_names_the_file(self):
        import contextlib
        import io

        def missing(argv):
            raise FileNotFoundError(2, "No such file or directory", argv[0])
        out = io.StringIO()
        with mock.patch.object(keys.sys, "platform", "linux"), mock.patch.object(keys.paths, "REMOTE", False), \
                contextlib.redirect_stdout(out):
            self.assertEqual(keys.open_env(self.env, run=missing), [])
        self.assertIn(os.path.abspath(self.env), out.getvalue())
        self.assertIn("open it in any text editor", out.getvalue())

    def test_unknown_service(self):
        with self.assertRaises(SystemExit):
            keys.init("playht", path=self.env)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class BackupRefusesKeys(unittest.TestCase):
    def test_backup_refuses_env_without_the_ignore_rule(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            new_repo(home)
            with open(os.path.join(home, ".gitignore"), "w") as f:
                f.write("*.mp3\n")
            with open(os.path.join(home, ".env"), "w") as f:
                f.write(f"FISH_AUDIO_API_KEY={SECRET}\n")
            with open(os.path.join(home, "log.md"), "w") as f:
                f.write("log\n")
            code, out = run_backup(home, push=False)
            self.assertEqual(code, 1, out)
            self.assertIn(".env", out)
            self.assertNotIn(SECRET, out)
            self.assertNotIn(".env", git(home, "ls-files"))
            self.assertEqual(git(home, "diff", "--cached", "--name-only"), "")

    def test_example_gitignore_ignores_env(self):
        with open(os.path.join(ROOT, "me.example", ".gitignore")) as f:
            self.assertIn(".env", [line.strip() for line in f])


class OnTheWeb(unittest.TestCase):
    def test_init_on_the_web_points_to_the_environment_settings(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_CODE_REMOTE="true", SWEATCAST_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "keys.py"), "init", "fish"], env=env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Environment variables", out.stdout)
            self.assertIn("FISH_AUDIO_API_KEY=<your key>", out.stdout)
            self.assertFalse(os.path.exists(os.path.join(d, "me", ".env")))

    def test_keys_open_on_the_web_points_to_settings(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_CODE_REMOTE="true", SWEATCAST_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "keys.py"), "open"], env=env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Environment variables", out.stdout)
            self.assertIn("GEMINI_API_KEY", out.stdout)
            self.assertFalse(os.path.exists(os.path.join(d, "me", ".env")))

    def test_download_refused_in_cloud(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_CODE_REMOTE="true", SWEATCAST_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "coaches.py"), "download"], env=env,
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 64, out.stdout + out.stderr)
            self.assertIn("cloud voice only", out.stdout)


if __name__ == "__main__":
    unittest.main()
