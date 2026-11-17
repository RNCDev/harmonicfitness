"""Setup and the readiness check, on faked computers. No network, no models. The per-command happy paths
(setup, doctor, check) are the fresh-clone smoke test's; these keep the rules it can't see.

The fakes are the HARMONICFITNESS_FAKE_* variables tools/doctor.sh reads (test-only).
"""
import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))


def clean_env(**extra):
    """The environment minus anything that would change the verdicts (a real cloud session, an override)."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("HARMONICFITNESS_") and k not in ("CLAUDE_CODE_REMOTE",)}
    env.update(extra)
    return env


def facts(fake=None, **extra):
    env = clean_env(**{f"HARMONICFITNESS_FAKE_{k}": v for k, v in (fake or {}).items()}, **extra)
    out = subprocess.run(["sh", os.path.join(ROOT, "tools", "doctor.sh"), "--facts"], env=env,
                         capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert out.returncode == 0, out.stderr
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


class CloudSession(unittest.TestCase):
    def test_the_web_never_gets_a_local_engine(self):
        """Claude Code on the web and the web client's worker: no local engine, even with a graphics card."""
        linux = {"OS": "Linux", "ARCH": "x86_64", "MEM_GB": "16", "DISK_GB": "30", "GPU": "NVIDIA A10, 24"}
        for env, reason in (({"CLAUDE_CODE_REMOTE": "true"}, "Claude Code on the web"),
                            ({"HARMONICFITNESS_WEB": "1"}, "web client")):
            with self.subTest(env=env):
                f = facts(linux, **env)
                self.assertEqual((f["local"], f["local_hw"], f["local_engine"]), ("no", "no", ""))
                self.assertIn(reason, f["local_reason"])


def _setup_snippet(start, end):
    """The lines of tools/setup.sh from the one starting `start` through the one starting `end`."""
    with open(os.path.join(ROOT, "tools", "setup.sh"), encoding="utf-8") as f:
        lines = f.read().splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith(start))
    j = next(n for n in range(i, len(lines)) if lines[n].startswith(end))
    return "\n".join(lines[i:j + 1])


class LocalExtra(unittest.TestCase):
    """The local engine is an optional extra (since 0.9.0), chosen by the readiness check."""

    def want(self, arg, local, installed, engine=""):
        script = (f'LOCAL={local}; INSTALLED="{installed}"; LOCAL_ENGINE="{engine}"; LOCAL_REASON=low\n'
                  f'set -- {arg}\n' + _setup_snippet('case "$1" in', "esac") + '\necho "WANT=$WANT"\n')
        out = subprocess.run(["sh", "-c", script], capture_output=True, text=True, encoding="utf-8", timeout=30)
        return out.returncode, out.stdout

    def test_low_disk_never_uninstalls_an_engine(self):
        """Below the disk floor the readiness check says local=no; an engine already installed stays."""
        for arg in ("", "--local", "--no-models"):
            with self.subTest(arg=arg):
                code, out = self.want(arg, "no", "cpu")
                self.assertEqual(code, 0, out)
                self.assertIn("WANT=cpu", out)

    def test_a_failed_migration_stops_setup(self):
        """A folder older than this engine reads: migrate refuses it, saying what to do, and setup's stop
        condition (neither "Backed up the originals" nor "already at schema") holds."""
        import cli
        import helpers
        import migrate
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(os.path.join(ROOT, "me.example"), home)
            with open(os.path.join(home, "profile.md"), "w", encoding="utf-8") as f:
                f.write("+++\nschema = 3\n+++\n# Profile\n")
            out, err = io.StringIO(), io.StringIO()
            with helpers.home(home), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.run(migrate.main, [])
        said = out.getvalue() + err.getvalue()
        self.assertEqual(code, cli.ISSUES, said)
        self.assertIn("me.example", said)
        self.assertIn("github.com/RNCDev/harmonicfitness", said)
        self.assertFalse(re.search("Backed up the originals|already at schema", said), said)
        stop = _setup_snippet('  if [ "$MIGRATED" -ne 0 ]', "    exit 1")
        self.assertIn("Backed up the originals\|already at schema", stop)


class Skills(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(ROOT, ".claude", "skills", name, "SKILL.md"), encoding="utf-8") as f:
            return f.read()

    def test_skills_name_only_current_commands(self):
        import harmonicfitness
        for name in ("setup", "workout", "coach"):
            text = self.read(name)
            for cmd in re.findall(r"\./harmonicfitness ([a-z-]+)", text):
                self.assertIn(cmd, set(harmonicfitness.COMMANDS) | {"help"}, (name, cmd))
            self.assertNotIn("--voice", text, name)
            self.assertNotIn("voices/", text, name)
        for doc in ("CLAUDE.md", "README.md", os.path.join("knowledge", "voices.md")):
            with open(os.path.join(ROOT, doc), encoding="utf-8") as f:
                text = f.read()
            for cmd in re.findall(r"\./harmonicfitness ([a-z-]+)", text):
                self.assertIn(cmd, set(harmonicfitness.COMMANDS) | {"help"}, (doc, cmd))
            self.assertNotIn("voices/smoke-test", text, doc)


if __name__ == "__main__":
    unittest.main()
