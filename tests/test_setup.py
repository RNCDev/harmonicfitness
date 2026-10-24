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
    keep = ("sweatcast", "tools", "me.example", "knowledge", "voices", "tests", "pyproject.toml", "uv.lock",
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
                 ({"OS": "MINGW64_NT-10.0", "ARCH": "x86_64", "MEM_GB": "32", "DISK_GB": "90", "GPU": ""}, "no", ""),
                 ({"OS": "Linux", "ARCH": "x86_64", "MEM_GB": "32", "DISK_GB": "90", "GPU": "NVIDIA A10, 24"}, "no", ""),
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


if __name__ == "__main__":
    unittest.main()
