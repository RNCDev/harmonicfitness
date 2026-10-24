"""Setup and the readiness check (./sweatcast doctor), on faked computers. No network, no models.

The fakes are the SWEATCAST_FAKE_* variables tools/doctor.sh reads (test-only), and a stub uv.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def clean_env(**extra):
    """The environment minus anything that would change the verdicts (a real cloud session, an override)."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("SWEATCAST_") and k not in ("CLAUDE_CODE_REMOTE",)}
    env.update(extra)
    return env


def facts(fake=None, root=ROOT, **extra):
    env = clean_env(**{f"SWEATCAST_FAKE_{k}": v for k, v in (fake or {}).items()}, **extra)
    out = subprocess.run(["sh", os.path.join(root, "tools", "doctor.sh"), "--facts"], env=env,
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


def copy_repo(dest):
    """A copy of the engine without .git, .venv, me/ or models (like a zip download)."""
    keep = ("sweatcast", "tools", "me.example", "knowledge", "tests", "pyproject.toml", "uv.lock",
            "VERSION", ".python-version")
    for name in keep:
        src = os.path.join(ROOT, name)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dest, name), ignore=shutil.ignore_patterns("__pycache__"))
        elif os.path.exists(src):
            shutil.copy2(src, os.path.join(dest, name))
    return dest


class Doctor(unittest.TestCase):
    def test_facts_on_faked_platforms(self):
        mac = {"OS": "Darwin", "ARCH": "arm64", "MEM_GB": "16", "DISK_GB": "40", "GPU": ""}
        cases = [(mac, "fast", "mlx"),
                 (dict(mac, ARCH="x86_64"), "no", ""),
                 ({"OS": "MINGW64_NT-10.0", "ARCH": "x86_64", "MEM_GB": "32", "DISK_GB": "90",
                   "GPU": "NVIDIA GeForce RTX 2080 SUPER, 8"}, "fast", "cuda"),
                 ({"OS": "MINGW64_NT-10.0", "ARCH": "x86_64", "MEM_GB": "32", "DISK_GB": "90", "GPU": ""}, "experimental", "cpu"),
                 ({"OS": "Linux", "ARCH": "other", "MEM_GB": "32", "DISK_GB": "90", "GPU": ""}, "no", ""),
                 ({"OS": "Linux", "ARCH": "x86_64", "MEM_GB": "32", "DISK_GB": "90", "GPU": "NVIDIA A10, 24"}, "fast", "cuda"),
                 ({"OS": "Linux", "ARCH": "x86_64", "MEM_GB": "32", "DISK_GB": "90", "GPU": ""}, "experimental", "cpu"),
                 (dict(mac, MEM_GB="4"), "no", ""),
                 (dict(mac, DISK_GB="2"), "no", "")]
        for fake, local, engine in cases:
            f = facts(fake)
            self.assertEqual((f["local"], f["local_engine"]), (local, engine), fake)
            if local == "no":
                self.assertTrue(f["local_reason"].strip(), fake)
        self.assertIn("Intel Mac", facts(dict(mac, ARCH="x86_64"))["local_reason"])
        self.assertIn("memory", facts(dict(mac, MEM_GB="4"))["local_reason"])
        self.assertEqual(facts(mac)["os"], "mac")

    def test_facts_name_the_tools_found(self):
        f = facts()
        for key in ("os", "arch", "mem_gb", "disk_gb", "uv", "git", "ffmpeg", "venv", "in_git", "remote"):
            self.assertIn(key, f)
        self.assertEqual(f["remote"], "no")
        self.assertEqual(facts(CLAUDE_CODE_REMOTE="true")["remote"], "yes")

    def test_report_runs_without_an_environment(self):
        with tempfile.TemporaryDirectory() as d:
            repo = copy_repo(d)
            out = subprocess.run(["sh", os.path.join(repo, "sweatcast"), "doctor"], env=clean_env(),
                                 capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertIn("This computer", out.stdout)
            self.assertIn("once ./sweatcast setup", out.stdout)

    def test_doctor_py_flags_a_missing_delivery_folder(self):
        import doctor
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(os.path.join(ROOT, "me.example"), home)
            missing = os.path.join(d, "no-such-folder").replace(os.sep, "/")
            prof = os.path.join(home, "profile.md")
            with open(prof, encoding="utf-8") as f:
                text = f.read()
            import re
            text = re.sub(r"^deliver_to = .*$", f'deliver_to = "{missing}"', text, flags=re.M)
            with open(prof, "w", encoding="utf-8") as f:
                f.write(text)
            lines = "\n".join(doctor.report_lines({"local": "fast"}, home=home))
            self.assertIn("no-such-folder", lines)
            self.assertIn("not on this computer", lines)


class CloudSession(unittest.TestCase):
    """A Claude Code cloud session (CLAUDE_CODE_REMOTE=true) is declined before anything is installed."""

    def run_in_copy(self, *args, **env):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        repo = copy_repo(d)
        out = subprocess.run(["sh", os.path.join(repo, "sweatcast"), *args], cwd=repo, env=clean_env(**env),
                             capture_output=True, text=True, timeout=60)
        return out, repo

    def test_cloud_session_declines_setup_and_build(self):
        for args in (["setup"], ["build", "x.draft.txt", "x"], ["check"]):
            out, repo = self.run_in_copy(*args, CLAUDE_CODE_REMOTE="true")
            self.assertEqual(out.returncode, 1, args)
            self.assertIn("cloud session", out.stdout + out.stderr)
            self.assertIn("your own computer", out.stdout + out.stderr)
            self.assertFalse(os.path.exists(os.path.join(repo, ".venv")))
            self.assertFalse(os.path.exists(os.path.join(repo, "me")))

    def test_setup_script_run_directly_declines_too(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        repo = copy_repo(d)
        out = subprocess.run(["sh", os.path.join(repo, "tools", "setup.sh")], env=clean_env(CLAUDE_CODE_REMOTE="true"),
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 1)
        self.assertIn("cloud session", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(repo, "me")))

    def test_override_lets_a_developer_through(self):
        out, _ = self.run_in_copy("help", CLAUDE_CODE_REMOTE="true", SWEATCAST_ALLOW_CLOUD_SESSION="1",
                                  SWEATCAST_PYTHON=sys.executable)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        out, _ = self.run_in_copy("setup", "--no-models", CLAUDE_CODE_REMOTE="true",
                                  SWEATCAST_ALLOW_CLOUD_SESSION="1", SWEATCAST_UV="/nonexistent/uv")
        self.assertNotIn("cloud session", out.stdout)

    def test_help_test_and_doctor_still_run_in_a_cloud_session(self):
        out, _ = self.run_in_copy("help", CLAUDE_CODE_REMOTE="true", SWEATCAST_PYTHON=sys.executable)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        out, _ = self.run_in_copy("doctor", CLAUDE_CODE_REMOTE="true")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("cloud session", out.stdout)
        self.assertIn("This computer", out.stdout)


STUB_UV = """#!/bin/sh
echo "$@" >> "$UV_LOG"
exit 0
"""
TOOLS = ("sh", "uname", "dirname", "basename", "cp", "mkdir", "find", "sed", "git", "cat", "awk", "grep",
         "head", "tr", "df", "sysctl", "rm", "ls", "env", "chmod", "mv", "date", "tail", "wc", "cut", "expr",
         "printf", "nvidia-smi")


def restricted_path(d, leave_out=("uv", "ffmpeg")):
    """A PATH holding only the basic tools setup uses, without uv or ffmpeg."""
    bin_dir = os.path.join(d, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    for name in TOOLS:
        found = shutil.which(name)
        if found and name not in leave_out:
            os.symlink(found, os.path.join(bin_dir, name))
    return bin_dir


class Setup(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        os.makedirs(os.path.join(self.d, "repo"))
        self.repo = copy_repo(os.path.join(self.d, "repo"))
        self.uv = os.path.join(self.d, "uv")
        with open(self.uv, "w") as f:
            f.write(STUB_UV)
        os.chmod(self.uv, 0o755)
        self.uv_log = os.path.join(self.d, "uv.log")

    def setup(self, *args, path=None, uv=True, **env):
        e = clean_env(UV_LOG=self.uv_log, SWEATCAST_PYTHON=sys.executable, HOME=self.d, **env)
        if uv:
            e["SWEATCAST_UV"] = self.uv
        if path:
            e["PATH"] = path
        return subprocess.run(["sh", os.path.join(self.repo, "tools", "setup.sh"), *args], cwd=self.repo, env=e,
                              capture_output=True, text=True, timeout=120)

    def test_setup_outside_git_reaches_the_models_step(self):
        out = self.setup("--no-models")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("isn't a git checkout", out.stdout)
        self.assertIn("Voice models", out.stdout)
        self.assertTrue(os.path.exists(os.path.join(self.repo, "me", "profile.md")))

    def test_setup_always_runs_uv_sync(self):
        os.makedirs(os.path.join(self.repo, ".venv", "bin"))
        out = self.setup("--no-models")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(self.uv_log) as f:
            self.assertIn("sync --frozen", f.read())

    def test_missing_uv_names_the_installer(self):
        out = self.setup("--no-models", path=restricted_path(self.d), uv=False)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("astral.sh/uv/install", out.stdout)
        self.assertIn("./sweatcast setup --install-uv", out.stdout)

    def test_missing_ffmpeg_does_not_stop_setup(self):
        out = self.setup("--no-models", path=restricted_path(self.d))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("ffmpeg is missing", out.stdout)


STUB_PY = """#!/bin/sh
# Stands in for the environment's Python: model downloads are logged, not run.
case "$1" in
  tools/coaches.py) echo "$@" >> "$UV_LOG"; exit 0 ;;
esac
exec "{python}" "$@"
"""


class LocalExtra(unittest.TestCase):
    """9.0: the local engines are an optional extra, chosen by the readiness check."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        os.makedirs(os.path.join(self.d, "repo"))
        self.repo = copy_repo(os.path.join(self.d, "repo"))
        self.uv, self.py, self.log = (os.path.join(self.d, n) for n in ("uv", "python", "calls.log"))
        for path, text in ((self.uv, STUB_UV), (self.py, STUB_PY.format(python=sys.executable))):
            with open(path, "w") as f:
                f.write(text)
            os.chmod(path, 0o755)

    def setup(self, *args, **fake):
        env = clean_env(UV_LOG=self.log, SWEATCAST_UV=self.uv, SWEATCAST_PYTHON=self.py, HOME=self.d,
                        **{f"SWEATCAST_FAKE_{k}": v for k, v in fake.items()})
        return subprocess.run(["sh", os.path.join(self.repo, "tools", "setup.sh"), *args], cwd=self.repo, env=env,
                              capture_output=True, text=True, timeout=120)

    def calls(self):
        with open(self.log) as f:
            return f.read()

    def test_setup_installs_the_extra_the_doctor_names(self):
        mac = dict(OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        out = self.setup(**mac)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen --extra mlx", self.calls())
        self.assertIn("tools/coaches.py download", self.calls())
        with open(os.path.join(self.repo, ".venv", ".sweatcast-extra")) as f:
            self.assertEqual(f.read().strip(), "mlx")

    def test_no_models_keeps_an_installed_extra(self):
        os.makedirs(os.path.join(self.repo, ".venv"))
        with open(os.path.join(self.repo, ".venv", ".sweatcast-extra"), "w") as f:
            f.write("mlx\n")
        out = self.setup("--no-models", OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen --extra mlx", self.calls())
        self.assertNotIn("coaches.py download", self.calls())

    def test_an_environment_from_before_the_extras_keeps_its_engine(self):
        os.makedirs(os.path.join(self.repo, ".venv", "lib", "python3.11", "site-packages", "mlx_audio"))
        out = self.setup("--no-models", OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen --extra mlx", self.calls())

    def test_no_models_on_a_fresh_copy_is_the_base_only(self):
        out = self.setup("--no-models", OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen\n", self.calls())

    def test_a_cloud_only_profile_skips_the_local_engine(self):
        shutil.copytree(os.path.join(self.repo, "me.example"), os.path.join(self.repo, "me"))
        prof = os.path.join(self.repo, "me", "profile.md")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text.replace("+++\n", '+++\nrender = ["fish"]\n', 1).replace("schema = 3\n", "schema = 3\n", 1))
        out = self.setup(OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("--extra", self.calls())
        self.assertIn("render list", out.stdout)

    def test_no_local_audio_installs_only_the_base(self):
        out = self.setup(OS="Darwin", ARCH="x86_64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertNotIn("--extra", self.calls())
        self.assertNotIn("coaches.py download", self.calls())
        self.assertIn("Intel Mac", out.stdout)

    def test_local_flag_refuses_where_local_cant_run(self):
        out = self.setup("--local", OS="Darwin", ARCH="x86_64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("Intel Mac", out.stdout)

    def test_processor_computers_get_the_cpu_extra(self):
        out = self.setup("--local", OS="Linux", ARCH="x86_64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen --extra cpu", self.calls())
        self.assertIn("experimental", out.stdout)


class Lock(unittest.TestCase):
    def test_lock_keeps_the_macs_versions(self):
        import tomllib
        with open(os.path.join(ROOT, "uv.lock"), "rb") as f:
            lock = tomllib.load(f)
        versions = {}
        for pkg in lock["package"]:
            versions.setdefault(pkg["name"], []).append((pkg["version"], str(pkg.get("source"))))
        self.assertIn("0.5.0", [v for v, _ in versions["mlx-audio"]])
        self.assertIn("2.2.6", [v for v, _ in versions["numpy"]])
        torch = [src for v, src in versions["torch"] if v.startswith("2.6.0")]
        self.assertTrue(any("cu124" in s for s in torch), torch)
        self.assertTrue(any("whl/cpu" in s for s in torch), torch)
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            project = tomllib.load(f)
        self.assertEqual(set(project["project"]["optional-dependencies"]), {"mlx", "cuda", "cpu"})
        self.assertIn("sys_platform == 'linux'", " ".join(project["tool"]["uv"]["environments"]))


class Skills(unittest.TestCase):
    def read(self, name):
        with open(os.path.join(ROOT, ".claude", "skills", name, "SKILL.md"), encoding="utf-8") as f:
            return f.read()

    def test_setup_skill_triggers(self):
        head = self.read("setup").split("---")[1]
        for phrase in ("set up sweatcast", "setup sweatcast", "install sweatcast", "get started"):
            self.assertIn(phrase, head)

    def test_no_skill_assumes_a_mac(self):
        for name in ("setup", "workout"):
            text = self.read(name)
            self.assertNotIn("afplay", text, name)
            self.assertNotRegex(text, r"brew install (?!.*winget)", name)

    def test_skills_name_only_current_commands(self):
        import re
        import sweatcast
        for name in ("setup", "workout", "coach"):
            text = self.read(name)
            for cmd in re.findall(r"\./sweatcast ([a-z-]+)", text):
                self.assertIn(cmd, set(sweatcast.COMMANDS) | {"help", "session"}, (name, cmd))
            self.assertNotIn("--voice", text, name)
            self.assertNotIn("voices/", text, name)
        for doc in ("CLAUDE.md", "README.md", os.path.join("knowledge", "voices.md")):
            with open(os.path.join(ROOT, doc), encoding="utf-8") as f:
                text = f.read()
            for cmd in re.findall(r"\./sweatcast ([a-z-]+)", text):
                self.assertIn(cmd, set(sweatcast.COMMANDS) | {"help", "session"}, (doc, cmd))
            self.assertNotIn("voices/smoke-test", text, doc)

    def test_player_picks_the_system_player(self):
        from unittest import mock
        import player
        for platform, which, expected in (("darwin", "/usr/bin/afplay", "afplay"),
                                          ("linux", "/usr/bin/xdg-open", "xdg-open")):
            with mock.patch.object(sys, "platform", platform), \
                    mock.patch("shutil.which", side_effect=lambda n, w=which: w if w.endswith(n) else None), \
                    mock.patch("subprocess.Popen") as popen:
                self.assertTrue(player.play("x.wav"))
                self.assertIn(expected, popen.call_args[0][0][0])
        with mock.patch.object(sys, "platform", "linux"), mock.patch("shutil.which", return_value=None):
            self.assertFalse(player.play("x.wav"))


if __name__ == "__main__":
    unittest.main()
