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

    def test_floors_dont_count_against_hardware_that_runs_voices(self):
        mac = {"OS": "Darwin", "ARCH": "arm64", "MEM_GB": "16", "DISK_GB": "2", "GPU": ""}
        f = facts(mac)
        self.assertEqual((f["local"], f["local_hw"], f["local_engine_hw"]), ("no", "fast", "mlx"))
        f = facts(dict(mac, MEM_GB="", DISK_GB="40"))   # memory unreadable: unknown, not zero
        self.assertEqual(f["local"], "fast")
        f = facts({"OS": "Linux", "ARCH": "arm64", "MEM_GB": "16", "DISK_GB": "40", "GPU": ""})
        self.assertEqual((f["local"], f["local_engine"]), ("experimental", "cpu"))   # PyTorch has Linux ARM builds

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
            prof = os.path.join(home, "settings.toml")
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
    """Claude Code on the web (CLAUDE_CODE_REMOTE=true): sweatcast runs, with cloud voices only."""

    def run_in_copy(self, *args, **env):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        repo = copy_repo(d)
        out = subprocess.run(["sh", os.path.join(repo, "sweatcast"), *args], cwd=repo, env=clean_env(**env),
                             capture_output=True, text=True, timeout=60)
        return out, repo

    def test_remote_facts_no_local(self):
        mac = {"OS": "Darwin", "ARCH": "arm64", "MEM_GB": "16", "DISK_GB": "40", "GPU": ""}
        f = facts(mac, CLAUDE_CODE_REMOTE="true")
        self.assertEqual((f["local"], f["local_hw"], f["local_engine"], f["remote"]), ("no", "no", "", "yes"))
        self.assertIn("Claude Code on the web", f["local_reason"])
        linux = {"OS": "Linux", "ARCH": "x86_64", "MEM_GB": "16", "DISK_GB": "30", "GPU": "NVIDIA A10, 24"}
        self.assertEqual(facts(linux, CLAUDE_CODE_REMOTE="true")["local"], "no")   # even with a card

    def test_wrapper_runs_in_cloud(self):
        out, _ = self.run_in_copy("help", CLAUDE_CODE_REMOTE="true", SWEATCAST_PYTHON=sys.executable)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        out, repo = self.run_in_copy("check", CLAUDE_CODE_REMOTE="true", SWEATCAST_PYTHON=sys.executable)
        self.assertNotIn("doesn't set up here", out.stdout + out.stderr)
        self.assertIn("./sweatcast setup", out.stdout + out.stderr)   # no context folder yet: setup makes one

    def test_doctor_names_the_web(self):
        out, _ = self.run_in_copy("doctor", CLAUDE_CODE_REMOTE="true")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("Claude Code on the web", out.stdout)
        self.assertIn("This computer", out.stdout)

    def test_setup_in_cloud_installs_no_local_engine(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        os.makedirs(os.path.join(d, "engine"))
        repo = copy_repo(os.path.join(d, "engine"))
        uv, log = os.path.join(d, "uv"), os.path.join(d, "uv.log")
        with open(uv, "w") as f:
            f.write(STUB_UV)
        os.chmod(uv, 0o755)
        env = clean_env(CLAUDE_CODE_REMOTE="true", SWEATCAST_UV=uv, UV_LOG=log, SWEATCAST_PYTHON=sys.executable,
                        HOME=d, SWEATCAST_FAKE_OS="Linux", SWEATCAST_FAKE_ARCH="x86_64", SWEATCAST_FAKE_GPU="")
        out = subprocess.run(["sh", os.path.join(repo, "tools", "setup.sh")], cwd=repo, env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(log) as f:
            self.assertNotIn("--extra", f.read())
        self.assertTrue(os.path.exists(os.path.join(repo, "me", "personas", "coach-andy-local", "clip.wav")))
        out = subprocess.run(["sh", os.path.join(repo, "tools", "setup.sh"), "--local"], cwd=repo, env=env,
                             capture_output=True, text=True, timeout=120)
        self.assertEqual(out.returncode, 1)
        self.assertIn("Claude Code on the web", out.stdout)

    def test_find_home_sibling(self):
        import paths
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "sweatcast")
            os.makedirs(os.path.join(root, "tools"))
            mine = os.path.join(d, "sweatcast-me")
            os.makedirs(os.path.join(mine, "personas"))
            open(os.path.join(mine, "profile.md"), "w").close()
            remote = {"CLAUDE_CODE_REMOTE": "true"}
            self.assertEqual(paths.find_home(root, remote), mine)
            self.assertEqual(paths.find_home(root, {}), os.path.join(root, "me"))   # only on the web
            self.assertEqual(paths.find_home(root, dict(remote, SWEATCAST_HOME=os.path.join(d, "x"))),
                             os.path.join(d, "x"))
            other = os.path.join(d, "another")
            os.makedirs(os.path.join(other, "personas"))
            open(os.path.join(other, "profile.md"), "w").close()
            self.assertEqual(paths.find_home(root, remote), os.path.join(root, "me"))   # two: don't guess
            os.makedirs(os.path.join(root, "me"))
            open(os.path.join(root, "me", "profile.md"), "w").close()
            self.assertEqual(paths.find_home(root, remote), os.path.join(root, "me"))

    def test_remote_without_home_says_one_time(self):
        import doctor
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(os.path.join(ROOT, "me.example"), home)
            clean = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
            with mock.patch.dict(os.environ, clean, clear=True), \
                    mock.patch("keys.paths.ENV_FILE", os.path.join(d, "no-env")):
                lines = "\n".join(doctor.web_lines(home))
            self.assertIn("one-time session", lines)
            self.assertIn("api.fish.audio", lines)
            for var in ("FISH_AUDIO_API_KEY", "ELEVENLABS_API_KEY", "GEMINI_API_KEY", "INWORLD_API_KEY"):
                self.assertIn(var, lines)
            for host in ("api.elevenlabs.io", "generativelanguage.googleapis.com", "api.inworld.ai"):
                self.assertIn(host, lines)
            subprocess.run(["git", "init", "-q", home], check=True)
            subprocess.run(["git", "-C", home, "remote", "add", "origin", "https://github.com/x/sweatcast-me.git"],
                           check=True)
            self.assertIn("keeps it", "\n".join(doctor.web_lines(home)))


    def test_remote_with_only_local_coaches_says_no_web_coach_yet(self):
        import doctor
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "me")
            shutil.copytree(os.path.join(ROOT, "me.example"), home)
            env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
            with mock.patch.dict(os.environ, dict(env, FISH_AUDIO_API_KEY="test-key"), clear=True), \
                    mock.patch("keys.paths.ENV_FILE", os.path.join(d, "no-env")):
                self.assertNotIn("No web coach yet", "\n".join(doctor.web_lines(home)))
                for slug in ("coach-reed-fish", "coach-ellis-elevenlabs", "coach-nolan-gemini", "coach-owen-inworld"):   # a 9.x folder
                    shutil.rmtree(os.path.join(home, "personas", slug))
                lines = "\n".join(doctor.web_lines(home))
            self.assertIn("No web coach yet", lines)
            self.assertIn("I want a new coach", lines)
            self.assertIn("Coach Reed", lines)
            self.assertIn(os.path.join("me.example", "personas", "coach-reed-fish"), lines)
            self.assertNotIn("Coach Owen", lines)

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

    def test_low_disk_never_uninstalls_an_engine(self):
        os.makedirs(os.path.join(self.repo, ".venv"))
        with open(os.path.join(self.repo, ".venv", ".sweatcast-extra"), "w") as f:
            f.write("mlx\n")
        out = self.setup(OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="2", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen --extra mlx", self.calls())
        out = self.setup("--local", OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="2", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_a_failed_migration_stops_setup(self):
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "v8-home"), os.path.join(self.repo, "me"))
        prof = os.path.join(self.repo, "me", "profile.md")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text.replace('name = "Qwen3 Coach"', 'name = "Qwen3 Custom"', 1))
        out = self.setup("--no-models", OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("--name", out.stdout)
        self.assertNotIn("Done. Next", out.stdout)

    def test_no_models_on_a_fresh_copy_is_the_base_only(self):
        out = self.setup("--no-models", OS="Darwin", ARCH="arm64", MEM_GB="16", DISK_GB="40", GPU="")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("sync --frozen\n", self.calls())

    def test_a_cloud_only_profile_skips_the_local_engine(self):
        shutil.copytree(os.path.join(self.repo, "me.example"), os.path.join(self.repo, "me"))
        prof = os.path.join(self.repo, "me", "settings.toml")
        with open(prof, encoding="utf-8") as f:
            text = f.read()
        with open(prof, "w", encoding="utf-8") as f:
            f.write(text.replace('render = ["local"]', 'render = ["fish"]', 1))
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
