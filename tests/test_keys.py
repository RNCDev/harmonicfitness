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
import errors  # noqa: E402
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

    def test_a_key_is_stripped_and_a_stray_character_refused_without_showing_it(self):
        os.environ["FISH_AUDIO_API_KEY"] = f"  {SECRET}\n"
        self.assertEqual(keys.get("fish", self.env), SECRET)          # whitespace around it is dropped
        for bad in (f"{SECRET[:5]}\r{SECRET[5:]}", f"{SECRET} extra", f"{SECRET}\u00e9"):
            os.environ["FISH_AUDIO_API_KEY"] = bad
            with self.assertRaises(keys.BadKey) as got:
                keys.get("fish", self.env)
            self.assertNotIn(SECRET[:8], str(got.exception))
            self.assertIn("FISH_AUDIO_API_KEY", str(got.exception))
            self.assertEqual(got.exception.exit_code, errors.SERVICE)  # the listener must act (4)
            self.assertIsInstance(got.exception, errors.PROBLEMS)      # a reported problem, not an engine bug
            out = io.StringIO()
            with redirect_stdout(out), mock.patch.object(keys.paths, "ENV_FILE", self.env):
                self.assertEqual(keys.main([]), 0)
            self.assertNotIn(SECRET[:8], out.getvalue())
            self.assertIn("fish      : holds a character", out.getvalue())
        del os.environ["FISH_AUDIO_API_KEY"]
        self.write(f"FISH_AUDIO_API_KEY={SECRET} # pasted on Monday\n".encode())
        self.assertEqual(keys.get("fish", self.env), SECRET)          # an inline comment isn't part of the key

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
        with open(os.path.join(home, ".env"), "w", encoding="utf-8") as f:
            f.write(f"FISH_AUDIO_API_KEY={SECRET}\n")
        env = dict(os.environ, HARMONICFITNESS_HOME=home, HARMONICFITNESS_PYTHON=sys.executable)
        out = subprocess.run(["sh", "harmonicfitness", "keys"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8",
                             timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn(SECRET, out.stdout + out.stderr)
        self.assertRegex(out.stdout, r"fish.*: set")
        self.assertRegex(out.stdout, r"elevenlabs.*: not set")

    def test_init_appends_once_and_is_private(self):
        path = keys.init("elevenlabs", path=self.env)
        keys.init("elevenlabs", path=self.env)
        with open(path, encoding="utf-8") as f:
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
        with open(self.env, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("GEMINI_API_KEY=", text)
        self.assertIn("INWORLD_API_KEY=", text)

    def test_keys_lists_every_service(self):
        self.assertEqual(list(keys.SERVICE_VARS), ["fish", "elevenlabs", "gemini", "inworld", "openrouter"])
        self.assertEqual(keys.SERVICE_VARS["openrouter"], "OPENROUTER_API_KEY")
        self.assertEqual(keys.SERVICE_VARS["gemini"], "GEMINI_API_KEY")
        self.assertEqual(keys.SERVICE_VARS["inworld"], "INWORLD_API_KEY")
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(keys.paths, "ENV_FILE", self.env):
            keys.main([])
        self.assertEqual([ln.split(":")[0].strip() for ln in out.getvalue().splitlines()],
                         ["fish", "elevenlabs", "gemini", "inworld", "openrouter"])

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
        with open(self.env, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("API keys for HarmonicFitness", text)
        self.assertNotIn("_API_KEY=", text)   # no service line added
        if os.name != "nt":
            self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)

    def test_keys_open_leaves_an_existing_file_alone(self):
        self.write(f"FISH_AUDIO_API_KEY={SECRET}\n".encode())
        with mock.patch.object(keys.paths, "REMOTE", False):
            keys.open_env(self.env, run=lambda a: None)
        with open(self.env, encoding="utf-8") as f:
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
        with self.assertRaises(errors.PROBLEMS):
            keys.init("playht", path=self.env)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class Paste(unittest.TestCase):
    """keys paste: the key goes from the clipboard to me/.env without passing through the chat or the output."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        clean = {k: v for k, v in os.environ.items() if k not in keys.SERVICE_VARS.values()}
        patcher = mock.patch.dict(os.environ, clean, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def clipboard(text, code=0):
        def run(argv, **kw):
            return subprocess.CompletedProcess(argv, code, stdout=text.encode("utf-8"), stderr=b"")
        return run

    def test_a_copied_key_is_saved_private_and_read_back(self):
        keys.paste("fish", path=self.env, run=self.clipboard(f"  {SECRET}\r\n"))
        self.assertEqual(keys.get("fish", path=self.env), SECRET)
        if os.name != "nt":
            self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)
        self.assertEqual(os.listdir(self.d), [".env"])   # no temporary file left

    def test_it_fills_the_empty_line_init_made_and_keeps_every_other_line(self):
        keys.init("fish", path=self.env)
        with open(self.env, "a", encoding="utf-8") as f:
            f.write("GEMINI_API_KEY=gemini-test-key-0123456789\n# a note of their own\n")
        keys.paste("fish", path=self.env, run=self.clipboard(SECRET))
        with open(self.env, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count("FISH_AUDIO_API_KEY="), 1)
        self.assertIn("# a note of their own", text)
        self.assertIn("fish.audio", text)   # init's comment kept
        self.assertEqual(keys.get("gemini", path=self.env), "gemini-test-key-0123456789")
        self.assertEqual(keys.get("fish", path=self.env), SECRET)

    def test_a_set_key_is_replaced_only_when_asked(self):
        keys.paste("fish", path=self.env, run=self.clipboard(SECRET))
        newer = "sk-test-NEWER-KEY-456789"
        with self.assertRaises(keys.KeyExists) as e:
            keys.paste("fish", path=self.env, run=self.clipboard(newer))
        self.assertIn("--replace", str(e.exception))
        self.assertEqual(keys.get("fish", path=self.env), SECRET)
        keys.paste("fish", path=self.env, replace=True, run=self.clipboard(newer))
        self.assertEqual(keys.get("fish", path=self.env), newer)

    def test_what_cant_be_a_key_is_refused_unsaved_and_unshown(self):
        for text in ("", "   ", "two words here and more", "https://example.test/zq-made-up-page", "zq7k",
                     "x" * 1025, "key-with-ünïcode-chars-0123"):
            with self.subTest(text=text[:20]):
                with self.assertRaises(keys.BadKey) as e:
                    keys.paste("fish", path=self.env, run=self.clipboard(text))
                if text.strip():
                    self.assertNotIn(text.strip(), str(e.exception))
                self.assertIn("Nothing was saved", str(e.exception))
                self.assertFalse(keys.is_set("fish", path=self.env))

    def test_each_system_has_a_reader_and_none_found_says_what_to_do(self):
        seen = []

        def run(argv, **kw):
            seen.append(argv[0])
            raise FileNotFoundError(2, "No such file", argv[0])
        for platform, first in (("darwin", "pbpaste"), ("win32", "powershell"), ("linux", "wl-paste")):
            with mock.patch.object(keys.sys, "platform", platform), self.assertRaises(errors.PROBLEMS) as e:
                keys.read_clipboard(run)
            self.assertIn(first, seen)
            self.assertIn("keys open", str(e.exception))
        self.assertIn("xclip", seen)   # Linux tries the next tool

    def test_the_command_never_prints_the_key(self):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(keys.paths, "ENV_FILE", self.env), \
                mock.patch.object(keys.paths, "WEB", False), mock.patch.object(keys.paths, "REMOTE", False), \
                mock.patch.object(keys, "read_clipboard", lambda run=None: SECRET):
            self.assertEqual(keys.main(["paste", "fish"]), errors.OK)
        self.assertNotIn(SECRET, out.getvalue())
        self.assertIn("FISH_AUDIO_API_KEY", out.getvalue())
        self.assertEqual(keys.get("fish", path=self.env), SECRET)

    def test_on_the_web_it_points_elsewhere_and_reads_nothing(self):
        def never(*a, **kw):
            raise AssertionError("the clipboard must not be read")
        for flag, needle in (("WEB", "settings"), ("REMOTE", "Environment variables")):
            out = io.StringIO()
            with redirect_stdout(out), mock.patch.object(keys.paths, "WEB", flag == "WEB"), \
                    mock.patch.object(keys.paths, "REMOTE", flag == "REMOTE"), \
                    mock.patch.object(keys, "read_clipboard", never):
                self.assertEqual(keys.main(["paste", "fish"]), errors.OK)
            self.assertIn(needle, out.getvalue())


class BackupRefusesKeys(unittest.TestCase):
    def test_backup_refuses_env_without_the_ignore_rule(self):
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            new_repo(home)
            with open(os.path.join(home, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("*.mp3\n")
            with open(os.path.join(home, ".env"), "w", encoding="utf-8") as f:
                f.write(f"FISH_AUDIO_API_KEY={SECRET}\n")
            with open(os.path.join(home, "log.md"), "w", encoding="utf-8") as f:
                f.write("log\n")
            code, out = run_backup(home, push=False)
            self.assertEqual(code, 1, out)
            self.assertIn(".env", out)
            self.assertNotIn(SECRET, out)
            self.assertNotIn(".env", git(home, "ls-files"))
            self.assertEqual(git(home, "diff", "--cached", "--name-only"), "")

    def test_example_gitignore_ignores_env(self):
        with open(os.path.join(ROOT, "me.example", ".gitignore"), encoding="utf-8") as f:
            self.assertIn(".env", [line.strip() for line in f])


class CleanValue(unittest.TestCase):
    def test_clean_value(self):
        self.assertEqual(keys.clean_value("X", " ab12cd34\n"), "ab12cd34")
        for bad in ("ab 12", "ab\u00e9"):
            with self.assertRaises(keys.BadKey) as e:
                keys.clean_value("X", bad)
            self.assertIn("X", str(e.exception))
            self.assertNotIn(bad, str(e.exception))


class OnTheWeb(unittest.TestCase):
    def test_init_on_the_web_points_to_the_environment_settings(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_CODE_REMOTE="true", HARMONICFITNESS_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "keys.py"), "init", "fish"], env=env,
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Environment variables", out.stdout)
            self.assertIn("FISH_AUDIO_API_KEY=<your key>", out.stdout)
            self.assertFalse(os.path.exists(os.path.join(d, "me", ".env")))

    def test_keys_open_on_the_web_points_to_settings(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_CODE_REMOTE="true", HARMONICFITNESS_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "keys.py"), "open"], env=env,
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Environment variables", out.stdout)
            self.assertIn("GEMINI_API_KEY", out.stdout)
            self.assertFalse(os.path.exists(os.path.join(d, "me", ".env")))

    def run_web_client(self, script, *args):
        with tempfile.TemporaryDirectory() as d:
            env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
            env.update(HARMONICFITNESS_WEB="1", HARMONICFITNESS_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", script), *args], env=env,
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
            return out, os.path.exists(os.path.join(d, "me", ".env"))

    def test_init_in_the_web_client_points_to_the_app(self):
        out, made = self.run_web_client("keys.py", "init", "fish")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("HarmonicFitness's settings", out.stdout)
        self.assertFalse(made)

    def test_open_in_the_web_client_points_to_the_app(self):
        out, made = self.run_web_client("keys.py", "open")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("HarmonicFitness's settings", out.stdout)
        self.assertFalse(made)

    def test_download_refused_in_cloud(self):
        with tempfile.TemporaryDirectory() as d:
            env = dict(os.environ, CLAUDE_CODE_REMOTE="true", HARMONICFITNESS_HOME=os.path.join(d, "me"))
            out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "coaches.py"), "download"], env=env,
                                 capture_output=True, text=True, encoding="utf-8", timeout=60)
            self.assertEqual(out.returncode, 64, out.stdout + out.stderr)
            self.assertIn("cloud voice only", out.stderr)   # a refusal: on stderr


if __name__ == "__main__":
    unittest.main()
