"""The home page's demo clips (tools/demos.py, docs/demos/): the shipped set reads clean, a demo listener's folder is
made and shares its coach, a command runs as one with the listener's key file, a clip is cut from a full draft with
its menu, and HARMONICFITNESS_KEYS points the engine at another key file. No network, models or personal files."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import check  # noqa: E402
import context  # noqa: E402
import demos  # noqa: E402
import draft  # noqa: E402
import errors  # noqa: E402
import harmonicfitness  # noqa: E402
import paths  # noqa: E402
import helpers  # noqa: E402

SHIPPED_DEMOS = paths.DEMOS   # the real docs/demos/, read before any test points paths elsewhere

DRAFT = """movements: glute bridge, dead bug

@@ 60 | Welcome
Your left knee stays light today.

@@ 45 | Glute bridge, set one
Feet flat, and lift. [reps 10]

@@ 40 | Rest
A story about the moon.

@@ 50 | Dead bug
Slow and steady.
"""


class ShippedSet(unittest.TestCase):
    """docs/demos/ as it ships: every demo's listener and coach file is there, and every listener reads clean."""

    def test_every_demo_has_its_listener_and_coach(self):
        import content
        m = demos.manifest(os.path.join(SHIPPED_DEMOS, "demos.toml"))
        self.assertEqual(len(m["demo"]), 7)
        formats = content.recipe().formats
        stories = [d["clip"]["story"] for d in m["demo"]]
        self.assertEqual(len(set(stories)), 7, "each clip shows a different kind of story")
        for story in stories:
            self.assertIn(story, formats)
            self.assertNotEqual(formats[story].research, "news", f"{story}: a clip plays for a year, so no news")
        self.assertEqual(m["model"], "eleven_v4")   # the more natural model, never the turbo one
        for d in m["demo"]:
            with self.subTest(demo=d["slug"]):
                self.assertTrue(os.path.isfile(os.path.join(SHIPPED_DEMOS, "listeners", d["slug"], "profile.md")))
                coach = context.persona(os.path.join(SHIPPED_DEMOS, d["coach_file"])).settings
                self.assertEqual((coach["name"], coach["service"], coach["model"]), (d["coach"], "elevenlabs", "eleven_v4"))
                self.assertTrue(coach.get("voice_id"), "a stock voice: nothing to design")
                self.assertIn(d["coach"], m["coaches"])
                self.assertIn(f'--coach "{d["coach"]}"', d["brief"])
                self.assertTrue(25 <= d["minutes"] <= 45)
        self.assertEqual(len(m["coaches"]), 3)   # three voices, each designed once

    def test_every_listener_reads_as_the_tools_expect(self):
        for slug in sorted(os.listdir(os.path.join(SHIPPED_DEMOS, "listeners"))):
            with self.subTest(listener=slug), tempfile.TemporaryDirectory() as d:
                shutil.copytree(os.path.join(SHIPPED_DEMOS, "listeners", slug), os.path.join(d, "me"))
                with helpers.home(os.path.join(d, "me")):
                    issues = [i for i in check.check() if not getattr(i, "note", False)]
                self.assertEqual(issues, [])


class Demos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = helpers.home(os.path.join(self.tmp, "me"))
        self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)
        # a small set of two demo listeners, each its own folder, sharing one coach
        self.demos = os.path.join(self.tmp, "docs", "demos")
        for slug in ("ann", "bo"):
            shutil.copytree(paths.EXAMPLE, os.path.join(self.demos, "listeners", slug),
                            ignore=shutil.ignore_patterns("workouts", "coaches", ".gitignore"))
        with open(os.path.join(self.demos, "demos.toml"), "w", encoding="utf-8") as f:
            f.write('service = "elevenlabs"\nmodel = "eleven_v4"\ncoaches = ["Coach Pat"]\n'
                    '[[demo]]\nslug = "ann"\norder = 1\nminutes = 30\ncoach = "Coach Pat"\ncoach_file = "coaches/pat.md"\n'
                    '[[demo]]\nslug = "bo"\norder = 2\nminutes = 25\ncoach = "Coach Pat"\ncoach_file = "coaches/pat.md"\n')
        patch = mock.patch.object(paths, "DEMOS", self.demos)
        patch.start()
        self.addCleanup(patch.stop)

    def make_coach(self, slug, model=None):
        folder = os.path.join(demos.home_of(slug), "coaches", "coach-pat-elevenlabs")
        settings = {"name": "Coach Pat", "kind": "web", "service": "elevenlabs", "voice_id": "v123", "made": "2026-11-04",
                    "voice": {"who": "a coach"}}
        if model:
            settings["model"] = model
        os.makedirs(folder)
        with open(os.path.join(folder, "persona.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text(settings, ""))
        with open(os.path.join(folder, "sample.mp3"), "wb") as f:
            f.write(b"ID3")
        return folder

    def test_a_demo_is_its_own_folder_in_docs_and_never_in_me(self):
        self.assertEqual(demos.home_of("ann"), os.path.join(self.demos, "listeners", "ann"))
        self.assertFalse(demos.home_of("ann").startswith(paths.HOME))
        self.assertEqual(demos.clips_dir(), os.path.join(self.demos, "clips"))

    def test_a_coach_file_with_no_stock_voice_is_refused(self):
        os.makedirs(os.path.join(self.demos, "coaches"))
        with open(os.path.join(self.demos, "coaches", "pat.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Pat", "kind": "web", "service": "elevenlabs",
                                          "voice": {"who": "a coach"}}, ""))
        with self.assertRaises(errors.CoachError):
            demos.make_home("ann", report=lambda s: None)

    def test_an_installed_coach_is_held_to_the_sets_model(self):
        self.make_coach("ann", model="eleven_v4_turbo")
        said = []
        demos.make_home("ann", report=said.append)
        self.assertEqual(demos._coach_in(demos.home_of("ann"), "Coach Pat").model, "eleven_v4")
        self.assertTrue(any("speaks with eleven_v4" in s for s in said), said)

    def test_a_stock_voice_is_installed_from_its_coach_file_with_nothing_designed(self):
        os.makedirs(os.path.join(self.demos, "coaches"))
        with open(os.path.join(self.demos, "coaches", "pat.md"), "w", encoding="utf-8") as f:
            f.write(context.persona_text({"name": "Coach Pat", "kind": "web", "service": "elevenlabs",
                                          "voice_id": "stock-1", "model": "eleven_v4", "voice": {"who": "a coach"}},
                                         ""))
        said = []
        for slug in ("ann", "bo"):
            demos.make_home(slug, report=said.append)
            p = demos._coach_in(demos.home_of(slug), "Coach Pat")
            self.assertEqual((p.voice_id, p.model), ("stock-1", "eleven_v4"))
            self.assertEqual(os.path.basename(p.folder), "coach-pat-elevenlabs")
        self.assertEqual(sum("a stock voice, nothing designed" in s for s in said), 2)
        self.assertTrue(all("coaches sample" in s for s in said if "Installed" in s))

    def test_run_points_the_engine_at_the_demo_and_the_listeners_key_file(self):
        os.remove(os.path.join(demos.home_of("bo"), "profile.md"))
        with self.assertRaises(errors.UsageError):
            demos.run_as("bo", ["check"])   # no listener there
        for refused in (["backup"], ["demos", "list"], ["setup"], []):
            with self.subTest(argv=refused), self.assertRaises(errors.UsageError):
                demos.run_as("ann", refused)
        with mock.patch.object(demos.subprocess, "call", return_value=3) as call:
            self.assertEqual(demos.run_as("ann", ["check", "--x"]), 3)
        argv, env = call.call_args.args[0], call.call_args.kwargs["env"]
        self.assertEqual(argv[-2:], ["check", "--x"])
        self.assertEqual(env["HARMONICFITNESS_HOME"], demos.home_of("ann"))
        self.assertEqual(env["HARMONICFITNESS_KEYS"], paths.ENV_FILE)

    def write_draft(self, limits):
        path = os.path.join(paths.WORKOUTS, "2026-11-04-demo", "2026-11-04-demo.draft.txt")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write(DRAFT)
        with open(draft.menu_path(path), "w", encoding="utf-8") as f:
            json.dump({"date": "2026-11-04", "request": {"goal": "general", "limits": limits}, "seconds": 195,
                       "movements": []}, f)
        return path

    def test_an_excerpt_is_a_draft_of_its_own_with_the_menu_beside_it(self):
        path = self.write_draft([])
        self.assertEqual([n for n, _, _ in demos.segments(path)], [1, 2, 3, 4])
        out, seconds = demos.excerpt(path, 2, 3)
        self.assertEqual(seconds, 85)
        self.assertEqual(os.path.basename(out), "2026-11-04-demo-clip.draft.txt")
        with open(out, encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("movements: glute bridge, dead bug"))
        self.assertEqual([s["label"] for s in draft.parse(text)], ["Glute bridge, set one", "Rest"])
        self.assertNotIn("Welcome", text)
        with open(draft.menu_path(out), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["seconds"], 85)
        with self.assertRaises(errors.UsageError):
            demos.excerpt(path, 3, 5)

    def test_under_a_one_sided_limit_a_clip_starts_at_the_opening(self):
        path = self.write_draft(["knee=delicate:left"])
        with self.assertRaises(errors.HarmonicFitnessError) as caught:
            demos.excerpt(path, 2, 3)
        self.assertIn("segment 1", str(caught.exception))
        self.assertEqual(demos.excerpt(path, 1, 2)[1], 105)

    def test_publish_copies_the_clip(self):
        mp3 = os.path.join(self.tmp, "clip.mp3")
        with open(mp3, "wb") as f:
            f.write(b"ID3clip")
        dst = demos.publish("bo", mp3)
        self.assertEqual(dst, os.path.join(demos.clips_dir(), "bo.mp3"))
        with self.assertRaises(errors.UsageError):
            demos.publish("nobody", mp3)

    def test_status_says_how_far_each_has_got(self):
        self.make_coach("ann")
        lines = demos.status()
        self.assertIn("ann", lines[0])
        self.assertIn("folder, coach", lines[0])
        self.assertIn("folder", lines[1])
        self.assertNotIn("coach,", lines[1])


class KeyFile(unittest.TestCase):
    def test_harmonicfitness_keys_names_another_key_file(self):
        code = "import paths; print(paths.ENV_FILE)"
        tools = os.path.join(paths.ROOT, "tools")
        with tempfile.TemporaryDirectory() as d:
            keys = os.path.join(d, "elsewhere.env")
            env = dict(os.environ, HARMONICFITNESS_HOME=os.path.join(d, "me"), HARMONICFITNESS_KEYS=keys)
            out = subprocess.run([sys.executable, "-c", code], cwd=tools, env=env, capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), os.path.abspath(keys))
            env.pop("HARMONICFITNESS_KEYS")
            out = subprocess.run([sys.executable, "-c", code], cwd=tools, env=env, capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), os.path.join(os.path.abspath(os.path.join(d, "me")), ".env"))

    def test_the_tests_never_see_another_key_file(self):
        env = harmonicfitness.test_env({"HARMONICFITNESS_KEYS": "/somewhere/.env"})
        self.assertNotIn("HARMONICFITNESS_KEYS", env)


if __name__ == "__main__":
    unittest.main()
