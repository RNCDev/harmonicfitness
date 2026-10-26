"""The audio bench (tools/bench.py): its script, what each computer runs, and the PyTorch environments it
writes. Nothing here installs a model or runs uv."""
import os
import sys
import tempfile
import tomllib
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import bench  # noqa: E402
import cli  # noqa: E402
from tts_build import lint_line  # noqa: E402

KINDS = {"welcome", "safety", "cue", "countdown", "short", "form", "numbers", "energy", "story", "breath", "close"}


class Script(unittest.TestCase):
    def test_every_line_passes_the_lint_and_has_a_kind(self):
        lines = bench.load_script()
        self.assertGreater(len(lines), 30)
        for line in lines:
            self.assertEqual(lint_line(1, line["text"]), [], line["id"])
            self.assertIn(line["kind"], KINDS, line["id"])

    def test_the_quick_lines_exist(self):
        ids = {l["id"] for l in bench.load_script()}
        self.assertLessEqual({"welcome", "count-switch", "go"}, ids)

    def test_two_lines_with_one_id_are_refused(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write('[[line]]\nid = "a"\nkind = "cue"\ntext = "Go."\n[[line]]\nid = "a"\nkind = "cue"\ntext = "Rest."\n')
        self.addCleanup(os.remove, f.name)
        with self.assertRaises(SystemExit):
            bench.load_script(f.name)


class Plan(unittest.TestCase):
    def test_a_mac_runs_every_model_through_mlx_but_pocket(self):
        with mock.patch.object(bench.sys, "platform", "darwin"), mock.patch.object(bench.platform, "machine", return_value="arm64"):
            runs = bench.plan()
        self.assertEqual([m for m, _, _ in runs], list(bench.MAC))
        self.assertEqual({d for m, d, _ in runs if m != "pocket"}, {"mlx"})
        self.assertEqual(dict((m, d) for m, d, _ in runs)["pocket"], "cpu")

    def test_a_pc_with_a_card_runs_all_on_it_then_the_small_ones_on_the_processor(self):
        with mock.patch.object(bench.sys, "platform", "win32"), mock.patch.object(bench, "nvidia", return_value={"name": "x"}):
            runs = [(m, d) for m, d, _ in bench.plan()]
        self.assertEqual([m for m, d in runs if d == "cuda"], list(bench.PC))
        self.assertEqual([m for m, d in runs if d == "cpu"], ["turbo", "lure", "pocket"])

    def test_a_pc_without_a_card_runs_only_the_processor(self):
        with mock.patch.object(bench.sys, "platform", "win32"), mock.patch.object(bench, "nvidia", return_value=None):
            self.assertEqual({d for _, d, _ in bench.plan()}, {"cpu"})

    def test_an_unknown_model_is_a_usage_error(self):
        with mock.patch.object(bench.sys, "platform", "win32"), mock.patch.object(bench, "nvidia", return_value=None), \
                self.assertRaises(cli.Usage):
            bench.plan(["kokoro"])


class TorchProject(unittest.TestCase):
    def test_torch_comes_from_pytorchs_own_index(self):
        with tempfile.TemporaryDirectory() as d:
            cmd = bench.torch_project(d, "cuda", ["qwen-tts==0.1.1"])
            with open(os.path.join(d, "pyproject.toml"), "rb") as f:
                proj = tomllib.load(f)
        self.assertEqual(cmd[:4], ["uv", "run", "--project", d])
        self.assertIn("torch==2.6.0", proj["project"]["dependencies"])
        self.assertIn("qwen-tts==0.1.1", proj["project"]["dependencies"])
        self.assertEqual(proj["tool"]["uv"]["index"][0]["url"], bench.TORCH_INDEX["cuda"])
        self.assertTrue(proj["tool"]["uv"]["index"][0]["explicit"])
        self.assertEqual(proj["tool"]["uv"]["sources"]["torch"], {"index": "pytorch"})


class Summary(unittest.TestCase):
    def test_a_summary_counts_takes_and_rates(self):
        rows = [{"kind": "cue", "words": 10, "errors": 1, "missed_cues": [], "problems": [], "ok": False,
                 "heard": "x", "audio_s": 4.0, "render_s": 2.0, "level_db": -24.0},
                {"kind": "countdown", "words": 5, "errors": 1, "missed_cues": ["rest"], "problems": [], "ok": False,
                 "heard": "y", "audio_s": 2.0, "render_s": 1.0, "level_db": -26.0},
                {"kind": "cue", "error": "boom", "render_s": 0.1}]
        s = bench.summarize(rows, {"load_s": 3.0}, 0, 60.0)
        self.assertEqual((s["takes"], s["takes_failed_to_render"], s["takes_missing_a_cue"]), (2, 1, 1))
        self.assertAlmostEqual(s["word_error_rate"], 2 / 15, places=3)
        self.assertEqual(s["render_ratio"], 0.5)
        self.assertEqual(s["by_kind"]["countdown"]["failed"], 1)
        md = bench.summary_md({"date": "d", "where": "mac", "computer": {}, "sweatcast": "v", "lines": 1, "asr": {},
                               "models": {"lure-cpu": s}})
        self.assertIn("| lure | cpu | ok | 2 | 2 | 1 | 0 | 13.3% | 0.5 | 3.0 |", md)


if __name__ == "__main__":
    unittest.main()
