import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import engine, folder  # noqa: E402
from webapp.agent import tools  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
TODAY = "2026-10-28"


class ToolsCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="hf-agent-")
        self.addCleanup(shutil.rmtree, self.home, True)
        folder.materialize(folder.seed(ROOT), self.home)
        self.deps = tools.Deps(engine_root=ROOT, home=self.home, keys={}, today=TODAY,
                               now=TODAY + "T08:00:00Z")

    def brief(self, **over):
        args = {"goal": "strength", "minutes": 20, "kit": None, "preset": "bodyweight",
                "equipment": None, "coach": "Coach Andy"}
        args.update(over)
        return tools.brief(self.deps, **args)


class Tools(ToolsCase):
    def test_read_file_and_missing(self):
        r = tools.read_file(self.deps, "profile.md")
        self.assertEqual(r.code, 0)
        self.assertIn("+++", r.output)
        os.remove(os.path.join(self.home, "log.md"))
        r = tools.read_file(self.deps, "log.md")
        self.assertEqual((r.code, r.error), (1, "no such file yet"))
        self.assertEqual(tools.read_file(self.deps, "../me/.env").code, 64)

    def test_brief_saves_menu_and_sets_stem(self):
        r = self.brief()
        self.assertEqual(r.code, 0, r.error)
        stem = f"{TODAY}-strength-20"
        self.assertEqual(self.deps.stem, stem)
        self.assertTrue(os.path.exists(os.path.join(self.home, "workouts", stem, f"{stem}.menu.json")))
        self.assertIn("brief", r.output.lower())

    def test_brief_second_today_gets_suffix(self):
        self.assertEqual(self.brief().code, 0)
        self.assertEqual(self.brief().code, 0)
        self.assertEqual(self.deps.stem, f"{TODAY}-strength-20-2")
        self.assertEqual(self.brief().code, 0)
        self.assertEqual(self.deps.stem, f"{TODAY}-strength-20-3")

    def test_brief_with_limits_and_equipment(self):
        r = self.brief(preset=None, equipment=["dumbbells", "mat"], limits=["knee=delicate:left"],
                       avoid=["burpee"], target=["quads"], add=["bench"])
        self.assertEqual(r.code, 0, r.error)

    def test_brief_refuses_bad_args_without_running(self):
        bad = [{"goal": "nap"}, {"minutes": 5}, {"minutes": 61}, {"minutes": True}, {"preset": "moon-base"},
               {"kit": "x"},  # two of kit/preset
               {"preset": None}, {"preset": None, "equipment": []},
               {"coach": "--evil"}, {"limits": ["--save=/x"]}, {"avoid": ["a\nb"]},
               {"target": ["-x"]}, {"add": ["-y"]}]
        with mock.patch.object(tools.engine, "run", side_effect=AssertionError("engine ran")):
            for over in bad:
                with self.subTest(over=over):
                    r = self.brief(**over)
                    self.assertEqual(r.code, 64)
                    self.assertTrue(r.error)
        self.assertIsNone(self.deps.stem)

    def test_get_coach_and_check_run(self):
        for r in (tools.get_coach(self.deps), tools.check(self.deps), tools.coaches(self.deps),
                  tools.coverage(self.deps), tools.content_plan(self.deps, 20)):
            self.assertIn(r.code, (0, 1), r.error)
            self.assertTrue(r.output.strip() or r.error.strip())
        self.assertEqual(tools.get_coach(self.deps).code, 0)
        self.assertEqual(tools.coaches(self.deps).code, 0)

    def test_get_route_and_content_plan_args(self):
        with mock.patch.object(tools.engine, "run", side_effect=AssertionError("engine ran")):
            self.assertEqual(tools.get_route(self.deps, "--x").code, 64)
            self.assertEqual(tools.content_plan(self.deps, 0).code, 64)

    def test_argv_and_keys_pass_through_engine_run(self):
        self.deps.keys = {"FISH_AUDIO_API_KEY": "k" * 12}
        seen = {}

        def fake(root, home, argv, extra_env={}, timeout=120):
            seen.update(argv=argv, env=extra_env, timeout=timeout)
            return engine.Result(0, "ok", "")
        with mock.patch.object(tools.engine, "run", fake):
            tools.get_route(self.deps, "Coach Andy")
        self.assertEqual(seen["argv"], ["get", "route", "--coach", "Coach Andy"])
        self.assertEqual(seen["env"], self.deps.keys)
        self.assertNotIn("k" * 12, repr(self.deps))

    def test_output_is_cut(self):
        big = engine.Result(0, "x" * 50000, "y" * 30000)
        with mock.patch.object(tools.engine, "run", return_value=big):
            r = tools.check(self.deps)
        self.assertEqual(len(r.output), tools.LIMIT + len(tools.CUT))
        self.assertTrue(r.output.endswith("[cut]"))
        self.assertTrue(r.error.endswith("[cut]"))


if __name__ == "__main__":
    unittest.main()
