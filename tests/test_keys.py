"""Cloud voice keys in me/.env: read only by the engine, never printed, never backed up.
Every key here is a made-up test value in a temporary folder."""
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
import errors  # noqa: E402
import keys  # noqa: E402

SECRET = "sk-test-NEVERPRINT-123"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def clean_environ(test):
    """No real key in the environment for the test's length."""
    clean = {k: v for k, v in os.environ.items() if k not in keys.SERVICE_VARS.values()}
    patcher = mock.patch.dict(os.environ, clean, clear=True)
    patcher.start()
    test.addCleanup(patcher.stop)


class Keys(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        clean_environ(self)

    def write(self, data):
        with open(self.env, "wb") as f:
            f.write(data)

    def test_a_key_is_stripped_and_a_stray_character_refused_without_showing_it(self):
        os.environ["FISH_AUDIO_API_KEY"] = f"  {SECRET}\n"
        self.assertEqual(keys.get("fish", self.env), SECRET)          # whitespace around it is dropped
        for bad in (f"{SECRET[:5]}\r{SECRET[5:]}", f"{SECRET} extra", f"{SECRET}é"):
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
        self.assertEqual(keys.clean_value("X", " ab12cd34\n"), "ab12cd34")
        for bad in ("ab 12", "abé"):
            with self.assertRaises(keys.BadKey) as e:
                keys.clean_value("X", bad)
            self.assertIn("X", str(e.exception))
            self.assertNotIn(bad, str(e.exception))
        with self.assertRaises(errors.PROBLEMS):   # an unknown service
            keys.init("playht", path=self.env)

    def test_keys_command_never_prints_a_value(self):
        self.write(f"FISH_AUDIO_API_KEY={SECRET}\n".encode())
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out), mock.patch.object(keys.paths, "ENV_FILE", self.env):
            self.assertEqual(keys.main([]), 0)
        self.assertNotIn(SECRET, out.getvalue())
        self.assertRegex(out.getvalue(), r"fish.*: set")
        self.assertRegex(out.getvalue(), r"elevenlabs.*: not set")

    def test_the_file_reads_every_way_its_written_and_the_environment_wins(self):
        for text in (b"FISH_AUDIO_API_KEY=x\n", b"export FISH_AUDIO_API_KEY=x\n", b'FISH_AUDIO_API_KEY = "x"\n',
                     b"FISH_AUDIO_API_KEY='x'\n", b"# a note\r\nFISH_AUDIO_API_KEY=x\r\n",
                     b"\xef\xbb\xbfFISH_AUDIO_API_KEY=x\n", b"OTHER=y\nFISH_AUDIO_API_KEY=x   \n"):
            with self.subTest(text=text):
                self.write(text)
                self.assertEqual(keys.get("fish", path=self.env), "x")
        self.write(b"FISH_AUDIO_API_KEY=\n")
        self.assertIsNone(keys.get("fish", path=self.env))
        self.assertFalse(keys.is_set("fish", path=self.env))
        self.write(b"FISH_AUDIO_API_KEY=from-file\n")
        with mock.patch.dict(os.environ, {"FISH_AUDIO_API_KEY": "from-env"}):
            self.assertEqual(keys.get("fish", path=self.env), "from-env")

    def test_init_appends_once_keeps_what_is_there_and_is_private(self):
        path = keys.init("elevenlabs", path=self.env)
        keys.init("elevenlabs", path=self.env)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count("ELEVENLABS_API_KEY="), 1)
        self.assertIn("elevenlabs.io", text)
        self.assertFalse(keys.is_set("elevenlabs", path=self.env))
        if os.name != "nt":
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
        self.write(f"FISH_AUDIO_API_KEY={SECRET}\n".encode())
        for service in ("fish", "gemini", "inworld"):
            keys.init(service, path=self.env)
        self.assertEqual(keys.get("fish", path=self.env), SECRET)
        with open(self.env, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("GEMINI_API_KEY=", text)
        self.assertIn("INWORLD_API_KEY=", text)

    def test_keys_open_never_reads_the_file(self):
        """The system's editor opens it (made private with init's header if missing, left alone if there);
        with no opener, the file's path is named."""
        calls = []
        with mock.patch.object(keys, "_read", side_effect=AssertionError("open must not read the file")):
            for platform, argv in (("darwin", ["open", "-e", self.env]), ("win32", ["notepad", self.env]),
                                   ("linux", ["xdg-open", self.env])):
                with mock.patch.object(keys.sys, "platform", platform), \
                        mock.patch.object(keys.paths, "REMOTE", False), mock.patch.object(keys.paths, "WEB", False):
                    self.assertEqual(keys.open_env(self.env, run=lambda a: calls.append(a)), argv)
                self.assertEqual(calls[-1], argv)
        with open(self.env, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("API keys for HarmonicFitness", text)
        self.assertNotIn("_API_KEY=", text)   # no service line added
        if os.name != "nt":
            self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)
        self.write(f"FISH_AUDIO_API_KEY={SECRET}\n".encode())

        def missing(argv):
            raise FileNotFoundError(2, "No such file or directory", argv[0])
        out = io.StringIO()
        with mock.patch.object(keys.sys, "platform", "linux"), mock.patch.object(keys.paths, "REMOTE", False), \
                mock.patch.object(keys.paths, "WEB", False), redirect_stdout(out):
            self.assertEqual(keys.open_env(self.env, run=missing), [])
        self.assertIn(os.path.abspath(self.env), out.getvalue())
        self.assertIn("open it in any text editor", out.getvalue())
        with open(self.env, encoding="utf-8") as f:
            self.assertEqual(f.read(), f"FISH_AUDIO_API_KEY={SECRET}\n")


class Paste(unittest.TestCase):
    """keys paste: the key goes from the clipboard to me/.env without passing through the chat or the output."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        self.env = os.path.join(self.d, ".env")
        clean_environ(self)

    @staticmethod
    def clipboard(text, code=0):
        def run(argv, **kw):
            return subprocess.CompletedProcess(argv, code, stdout=text.encode("utf-8"), stderr=b"")
        return run

    def test_a_copied_key_is_saved_private_beside_every_other_line_and_replaced_only_when_asked(self):
        keys.init("fish", path=self.env)
        with open(self.env, "a", encoding="utf-8") as f:
            f.write("GEMINI_API_KEY=gemini-test-key-0123456789\n# a note of their own\n")
        keys.paste("fish", path=self.env, run=self.clipboard(f"  {SECRET}\r\n"))
        self.assertEqual(keys.get("fish", path=self.env), SECRET)
        if os.name != "nt":
            self.assertEqual(os.stat(self.env).st_mode & 0o777, 0o600)
        self.assertEqual(os.listdir(self.d), [".env"])   # no temporary file left
        with open(self.env, encoding="utf-8") as f:
            text = f.read()
        self.assertEqual(text.count("FISH_AUDIO_API_KEY="), 1)
        self.assertIn("# a note of their own", text)
        self.assertIn("fish.audio", text)   # init's comment kept
        self.assertEqual(keys.get("gemini", path=self.env), "gemini-test-key-0123456789")
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


class BackupRefusesKeys(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_backup_refuses_env_without_the_ignore_rule(self):
        import backup
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            os.makedirs(home)
            git(home, "init", "-q")
            for k, v in (("user.name", "Test"), ("user.email", "test@example.com"), ("commit.gpgsign", "false")):
                git(home, "config", k, v)
            with open(os.path.join(home, ".gitignore"), "w", encoding="utf-8") as f:
                f.write("*.mp3\n")
            with open(os.path.join(home, ".env"), "w", encoding="utf-8") as f:
                f.write(f"FISH_AUDIO_API_KEY={SECRET}\n")
            with open(os.path.join(home, "log.md"), "w", encoding="utf-8") as f:
                f.write("log\n")
            out = io.StringIO()   # both streams: a refusal goes to stderr
            with redirect_stdout(out), redirect_stderr(out):
                code = backup.backup(home, "Workout", push=False)
            self.assertEqual(code, 1, out.getvalue())
            self.assertIn(".env", out.getvalue())
            self.assertNotIn(SECRET, out.getvalue())
            self.assertNotIn(".env", git(home, "ls-files"))
            self.assertEqual(git(home, "diff", "--cached", "--name-only"), "")

    def test_example_gitignore_ignores_env(self):
        with open(os.path.join(ROOT, "me.example", ".gitignore"), encoding="utf-8") as f:
            self.assertIn(".env", [line.strip() for line in f])


class OnTheWeb(unittest.TestCase):
    """On Claude Code on the web (REMOTE) and in the web client (WEB), the key commands point to the settings
    there and write no key file; no local model is fetched."""

    def test_keys_point_elsewhere_and_write_nothing(self):
        def never(*a, **kw):
            raise AssertionError("the clipboard must not be read")
        with tempfile.TemporaryDirectory() as d:
            env = os.path.join(d, "me", ".env")
            for flag, argv, needle in (("REMOTE", ["init", "fish"], "FISH_AUDIO_API_KEY=<your key>"),
                                       ("REMOTE", ["open"], "GEMINI_API_KEY"),
                                       ("REMOTE", ["paste", "fish"], "Environment variables"),
                                       ("WEB", ["init", "fish"], "no key to add here"),
                                       ("WEB", ["open"], "no key to add here"),
                                       ("WEB", ["paste", "fish"], "no key to add here")):
                with self.subTest(flag=flag, argv=argv):
                    out = io.StringIO()
                    with redirect_stdout(out), mock.patch.object(keys.paths, "ENV_FILE", env), \
                            mock.patch.object(keys.paths, "WEB", flag == "WEB"), \
                            mock.patch.object(keys.paths, "REMOTE", flag == "REMOTE"), \
                            mock.patch.object(keys, "read_clipboard", never):
                        self.assertEqual(keys.main(argv), errors.OK)
                    self.assertIn(needle, out.getvalue())
                    self.assertFalse(os.path.exists(env))

    def test_download_refused_on_the_web(self):
        import cli
        import coaches
        for flag in ("REMOTE", "WEB"):
            err = io.StringIO()
            with mock.patch.object(coaches.paths, "WEB", flag == "WEB"), \
                    mock.patch.object(coaches.paths, "REMOTE", flag == "REMOTE"), \
                    mock.patch.object(coaches.voices, "download", side_effect=AssertionError("no download")), \
                    redirect_stdout(io.StringIO()), redirect_stderr(err):
                self.assertEqual(cli.run(coaches.main, ["download"]), errors.USAGE, flag)
            self.assertIn("no local model to fetch", err.getvalue())   # a refusal: on stderr


class KeyFile(unittest.TestCase):
    """HARMONICFITNESS_KEYS names another key file (demos run sets it); the tests never see one."""

    def test_harmonicfitness_keys_names_another_key_file(self):
        code = "import paths; print(paths.ENV_FILE)"
        tools = os.path.join(ROOT, "tools")
        with tempfile.TemporaryDirectory() as d:
            other = os.path.join(d, "elsewhere.env")
            env = dict(os.environ, HARMONICFITNESS_HOME=os.path.join(d, "me"), HARMONICFITNESS_KEYS=other)
            out = subprocess.run([sys.executable, "-c", code], cwd=tools, env=env, capture_output=True, text=True,
                                 encoding="utf-8")
            self.assertEqual(out.stdout.strip(), os.path.abspath(other))
            env.pop("HARMONICFITNESS_KEYS")
            out = subprocess.run([sys.executable, "-c", code], cwd=tools, env=env, capture_output=True, text=True,
                                 encoding="utf-8")
            self.assertEqual(out.stdout.strip(), os.path.join(os.path.abspath(os.path.join(d, "me")), ".env"))

    def test_the_tests_never_see_another_key_file(self):
        import harmonicfitness
        env = harmonicfitness.test_env({"HARMONICFITNESS_KEYS": "/somewhere/.env"})
        self.assertNotIn("HARMONICFITNESS_KEYS", env)


if __name__ == "__main__":
    unittest.main()
