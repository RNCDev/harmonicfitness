"""The two assistants' files: ChatGPT's Codex files stay in step with the Claude Code ones."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import harness  # noqa: E402


def copy_harness(d):
    """The files the harness check reads, copied into a scratch root."""
    for rel in (".claude", ".agents", ".codex"):
        shutil.copytree(os.path.join(ROOT, rel), os.path.join(d, rel))
    shutil.copy(os.path.join(ROOT, "AGENTS.md"), d)
    return d


class Harness(unittest.TestCase):
    def test_the_repo_is_in_step(self):
        self.assertEqual(harness.problems(ROOT), [])

    def test_every_claude_skill_is_copied_whole_for_codex(self):
        names = os.listdir(os.path.join(ROOT, ".claude", "skills"))
        self.assertEqual(sorted(names), sorted(os.listdir(os.path.join(ROOT, ".agents", "skills"))))
        for name in names:
            for fn in os.listdir(os.path.join(ROOT, ".claude", "skills", name)):
                with open(os.path.join(ROOT, ".claude", "skills", name, fn), encoding="utf-8") as a, \
                        open(os.path.join(ROOT, ".agents", "skills", name, fn), encoding="utf-8") as b:
                    self.assertEqual(a.read(), b.read(), f"{name}/{fn}")
    def test_the_env_deny_rules_are_checked(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            copy_harness(d)
            settings = os.path.join(d, ".claude", "settings.json")
            with open(settings, encoding="utf-8") as f:
                data = json.load(f)
            data["permissions"]["deny"] = ["Edit(/me/.env)"]
            with open(settings, "w", encoding="utf-8") as f:
                json.dump(data, f)
            found = [p for p in harness.problems(d) if "me/.env" in p]
            self.assertTrue(found, harness.problems(d))

    def test_a_binary_file_in_a_skill_is_copied_and_compared(self):
        with tempfile.TemporaryDirectory() as d:
            copy_harness(d)
            with open(os.path.join(d, ".claude", "skills", "workout", "icon.png"), "wb") as f:
                f.write(b"\x89PNG\r\n\x00\xff\xfe")
            self.assertIn(os.path.join(".agents", "skills", "workout", "icon.png") + ": missing", harness.problems(d))
            harness.sync(d)
            self.assertEqual(harness.problems(d), [])

    def test_sync_removes_a_dropped_skill_with_its_subfolders(self):
        with tempfile.TemporaryDirectory() as d:
            copy_harness(d)
            old = os.path.join(d, ".agents", "skills", "old", "sub")
            os.makedirs(old)
            with open(os.path.join(old, "f.md"), "w", encoding="utf-8") as f:
                f.write("x\n")
            harness.sync(d)
            self.assertFalse(os.path.exists(os.path.join(d, ".agents", "skills", "old")))


    def test_agents_md_sends_codex_to_claude_md_and_guards_the_keys(self):
        with open(os.path.join(ROOT, "AGENTS.md"), encoding="utf-8") as f:
            text = f.read()
        for needle in ("CLAUDE.md", "me/.env", "./sweatcast show", "AskUserQuestion", "Data Controls"):
            self.assertIn(needle, text)

    def test_an_edited_description_is_caught_and_synced(self):
        with tempfile.TemporaryDirectory() as d:
            copy_harness(d)
            path = os.path.join(d, ".claude", "skills", "coach", "SKILL.md")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            with open(path, "w", encoding="utf-8") as f:
                f.write(text.replace("description: ", "description: Also when they say \"new trainer\". ", 1))
            with open(os.path.join(d, ".claude", "skills", "workout", "research.md"), "a", encoding="utf-8") as f:
                f.write("\nOne more line.\n")
            self.assertIn(os.path.join(".agents", "skills", "coach", "SKILL.md") + ": out of step with the Claude "
                          "Code files", harness.problems(d))
            self.assertIn(os.path.join(".agents", "skills", "workout", "research.md") + ": out of step with the "
                          "Claude Code files", harness.problems(d))
            harness.sync(d)
            self.assertEqual(harness.problems(d), [])

    def test_a_new_skill_is_added_and_a_removed_one_goes(self):
        with tempfile.TemporaryDirectory() as d:
            copy_harness(d)
            os.makedirs(os.path.join(d, ".claude", "skills", "stretch"))
            with open(os.path.join(d, ".claude", "skills", "stretch", "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: stretch\ndescription: A stretch.\n---\n\nBody.\n")
            shutil.rmtree(os.path.join(d, ".claude", "skills", "coach"))
            left = harness.problems(d)
            self.assertIn(os.path.join(".agents", "skills", "stretch", "SKILL.md") + ": missing", left)
            self.assertIn(os.path.join(".agents", "skills", "coach", "SKILL.md") + ": no Claude skill file of that name "
                          "any more", left)
            self.assertIn("AGENTS.md: out of step with the Claude Code files", left)
            harness.sync(d)
            self.assertEqual(harness.problems(d), [])
            self.assertFalse(os.path.exists(os.path.join(d, ".agents", "skills", "coach")))

    def test_the_codex_rule_and_the_claude_allow_list_name_the_same_command(self):
        with tempfile.TemporaryDirectory() as d:
            copy_harness(d)
            with open(os.path.join(d, harness.CODEX_RULES), "w", encoding="utf-8") as f:
                f.write("")
            self.assertTrue(any("should allow" in p for p in harness.problems(d)))

    def test_the_command(self):
        out = subprocess.run(["sh", "sweatcast", "harness"], cwd=ROOT, capture_output=True, text=True,
                             env=dict(os.environ, SWEATCAST_PYTHON=sys.executable))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("in step", out.stdout)


class CodexSandbox(unittest.TestCase):
    def test_inside_codexs_sandbox_uvs_cache_stays_in_the_project(self):
        with tempfile.TemporaryDirectory() as d:
            fake = os.path.join(d, "python")
            with open(fake, "w") as f:
                f.write('#!/bin/sh\necho "$UV_CACHE_DIR"\n')
            os.chmod(fake, 0o755)
            env = {k: v for k, v in os.environ.items() if k != "UV_CACHE_DIR"}
            out = subprocess.run(["sh", "sweatcast", "help"], cwd=ROOT, capture_output=True, text=True,
                                 env=dict(env, CODEX_SANDBOX="seatbelt", SWEATCAST_PYTHON=fake))
            self.assertEqual(out.stdout.strip(), os.path.join(ROOT, ".cache", "uv"))
            out = subprocess.run(["sh", "sweatcast", "help"], cwd=ROOT, capture_output=True, text=True,
                                 env=dict(env, SWEATCAST_PYTHON=fake))
            self.assertEqual(out.stdout.strip(), "")

if __name__ == "__main__":
    unittest.main()
