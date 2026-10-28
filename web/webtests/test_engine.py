import os
import shutil
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import engine, folder  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def stub(body):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "harmonicfitness")
    with open(p, "w") as f:
        f.write("#!/bin/sh\n" + body + "\n")
    os.chmod(p, 0o755)
    return d


class Engine(unittest.TestCase):
    def test_engine_env_is_allowlisted(self):
        # the engine is `env` itself (no shell, which would add PWD, SHLVL and _ of its own)
        root, home = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.symlink(shutil.which("env"), os.path.join(root, "harmonicfitness"))
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_MASTER_KEY": "secret-master",
                                          "DATABASE_URL": "postgres://x",
                                          "SESSION_SECRET": "s", "SOMETHING_ELSE": "y",
                                          "TZ": "UTC"}):
            want = {k for k in engine.ALLOWED if k in os.environ} | {"HOME", "HARMONICFITNESS_HOME"}
            r = engine.run(root, home, [])
        self.assertEqual(r.code, 0)
        got = dict(line.split("=", 1) for line in r.stdout.splitlines())
        self.assertEqual(set(got), want)
        self.assertIn("TZ", got)
        self.assertEqual((got["HOME"], got["HARMONICFITNESS_HOME"]), (home, home))

    def test_brief_runs_on_a_seeded_folder(self):
        home = tempfile.mkdtemp()
        folder.materialize(folder.seed(ROOT), home)
        draft = f"{home}/workouts/2026-10-27-strength-20/2026-10-27-strength-20.draft.txt"
        r = engine.run(ROOT, home, ["brief", "--goal", "strength", "--minutes", "20",
                                    "--preset", "bodyweight", "--today", "2026-10-27",
                                    "--save", draft], timeout=300)
        self.assertEqual(r.code, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("# Today's brief: strength, 20 minutes"))
        self.assertTrue(os.path.exists(draft.replace(".draft.txt", ".menu.json")))

    def test_extra_env_values_are_scrubbed(self):
        root, home = stub('echo "$FISH_AUDIO_API_KEY"; echo "$FISH_AUDIO_API_KEY" >&2'), tempfile.mkdtemp()
        r = engine.run(root, home, [], extra_env={"FISH_AUDIO_API_KEY": "sk-abcdefghijklmnop"})
        self.assertNotIn("sk-abcdefghijklmnop", r.stdout)
        self.assertNotIn("sk-abcdefghijklmnop", r.stderr)
        self.assertIn("<key>", r.stdout)

    def test_timeout_kills(self):
        root, home = stub("sleep 10"), tempfile.mkdtemp()
        t = time.time()
        r = engine.run(root, home, [], timeout=0.5)
        self.assertEqual(r.code, 124)
        self.assertIn("timed out after 0.5 s", r.stderr.splitlines()[-1])
        self.assertLess(time.time() - t, 8)

    def test_extra_env_cannot_override_home(self):
        root, home = stub("env"), tempfile.mkdtemp()
        for k in ("HOME", "HARMONICFITNESS_HOME"):
            with self.assertRaises(ValueError):
                engine.run(root, home, [], extra_env={k: "/x"})

    def test_nonzero_code_passes_through(self):
        root, home = stub("echo oops >&2; exit 3"), tempfile.mkdtemp()
        r = engine.run(root, home, [])
        self.assertEqual((r.code, r.stderr.strip()), (3, "oops"))


class NotDumpable(unittest.TestCase):
    def test_skipped_off_linux(self):
        with mock.patch.object(engine.sys, "platform", "darwin"):
            self.assertFalse(engine.not_dumpable())

    def test_sets_the_flag_on_linux(self):
        calls = []

        class Libc:
            def prctl(self, *args):
                calls.append(args)
                return 0
        with mock.patch.object(engine.sys, "platform", "linux"), \
                mock.patch.object(engine.ctypes, "CDLL", lambda *a, **k: Libc()):
            self.assertTrue(engine.not_dumpable())
        self.assertEqual(calls, [(4, 0, 0, 0, 0)])


class Scrub(unittest.TestCase):
    def test_floor_of_eight(self):
        self.assertEqual(engine.scrub("abcdefg and abcdefgh", ["abcdefg", "abcdefgh"]),
                         "abcdefg and <key>")

    def test_longest_first_and_stripped_form(self):
        self.assertEqual(engine.scrub("xx-secret12345 and secret12345", ["secret12345", "xx-secret12345"]),
                         "<key> and <key>")
        self.assertEqual(engine.scrub("tok-abcdefgh", ["tok-abcdefgh\n"]), "<key>")


if __name__ == "__main__":
    unittest.main()
