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
        # the engine prints its environment. `env` runs under its own name (a multi-call coreutils, as on
        # newer Ubuntu, picks its job from that name) and drops what the shell itself adds.
        root, home = stub(f"exec {shutil.which('env')} -u PWD -u OLDPWD -u SHLVL -u _"), tempfile.mkdtemp()
        with mock.patch.dict(os.environ, {"HARMONICFITNESS_MASTER_KEY": "secret-master",
                                          "DATABASE_URL": "postgres://x",
                                          "SESSION_SECRET": "s", "SOMETHING_ELSE": "y",
                                          "TZ": "UTC"}):
            want = {k for k in engine.ALLOWED if k in os.environ} | {"HOME", "HARMONICFITNESS_HOME",
                                                                     "HARMONICFITNESS_WEB"}
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

    def test_web_mode_always_on(self):
        root, home = stub('echo "$HARMONICFITNESS_WEB"'), tempfile.mkdtemp()
        self.assertEqual(engine.run(root, home, []).stdout, "1\n")
        with self.assertRaises(ValueError):
            engine.run(root, home, [], extra_env={"HARMONICFITNESS_WEB": "0"})

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

    def test_cancel_kills_the_group(self):
        import threading
        root, home = stub('sleep 30 & echo $! > "$HOME/child.pid"; wait'), tempfile.mkdtemp()
        cancel = threading.Event()
        threading.Timer(0.3, cancel.set).start()
        t = time.monotonic()
        r = engine.run(root, home, [], cancel=cancel)
        self.assertLess(time.monotonic() - t, 1.5)
        self.assertEqual(r.code, engine.CANCELLED)
        self.assertEqual(r.code, 125)
        self.assertEqual(r.stderr.splitlines()[-1], "stopped: the job was cancelled")
        with open(os.path.join(home, "child.pid")) as f:
            pid = int(f.read())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail("the engine's child outlived the cancel")

    def test_cancel_set_before_never_starts(self):
        import threading
        root, home = stub('touch "$HOME/ran"'), tempfile.mkdtemp()
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(engine.run(root, home, [], cancel=cancel).code, engine.CANCELLED)
        self.assertFalse(os.path.exists(os.path.join(home, "ran")))

    def test_output_is_capped(self):
        # 3 MB on stdout: lines "first", then 3,000 lines of 1,000 x, then "last"
        root, home = stub("echo first; i=0; line=$(printf 'x%.0s' $(seq 1000)); "
                          "while [ $i -lt 3000 ]; do echo $line; i=$((i+1)); done; echo last"), tempfile.mkdtemp()
        r = engine.run(root, home, [], timeout=60)
        self.assertEqual(r.code, 0, r.stderr)
        self.assertLessEqual(len(r.stdout), engine.MAX_OUTPUT + 20)
        self.assertIn("[cut]", r.stdout)
        self.assertTrue(r.stdout.startswith("first\n"))
        self.assertTrue(r.stdout.endswith("\nlast\n"))

    def test_output_under_the_cap_is_whole(self):
        root, home = stub("echo one; echo two >&2"), tempfile.mkdtemp()
        r = engine.run(root, home, [], max_output=10)
        self.assertEqual((r.stdout, r.stderr), ("one\n", "two\n"))
        root = stub("printf 'abcdefghijklmnopqrstuvwxyz'")
        self.assertEqual(engine.run(root, home, [], max_output=10).stdout, "abcde\n[cut]\nvwxyz")

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
