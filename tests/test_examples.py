"""The worked examples in knowledge/script.md keep to the rules the build checks: each one lints clean, its story
tags close, and its spoken text holds nothing a voice can't read."""
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import draft  # noqa: E402
import tts_build  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def examples():
    """Each indented block after an `<!-- example -->` line in script.md, as draft text."""
    with open(os.path.join(ROOT, "knowledge", "script.md"), encoding="utf-8") as f:
        text = f.read()
    out = []
    for m in re.finditer(r"<!-- example -->\n((?:    .*\n|\n)+)", text):
        out.append("\n".join(line[4:] for line in m.group(1).rstrip().split("\n")) + "\n")
    return out


class WorkedExamples(unittest.TestCase):
    def test_there_are_examples(self):
        self.assertGreaterEqual(len(examples()), 4)

    def test_each_example_lints_clean(self):
        voice = {"name": "x", "key": "x", "engine": "pocket", "model": "m"}
        for text in examples():
            segs = draft.parse(text)
            with self.subTest(label=segs[0]["label"]), mock.patch("voices.pace", return_value=(14.5, True)):
                report = tts_build.lint(segs, voice, headroom=False)
                issues = [i for r in report.rows for i in r.clip_issues + r.line_issues]
                self.assertEqual(issues, [])
                for seg in segs:
                    self.assertEqual(draft.story_split(seg)[2], [])
                    self.assertEqual([r.flag for r in report.rows if r.flag == "long"], [])


if __name__ == "__main__":
    unittest.main()
