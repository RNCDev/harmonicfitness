"""`./harmonicfitness test changed` (tools/testpick.py): the engine tests a change reaches, with the enforcers always."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402,F401  (puts tools/ on the path)
import testpick  # noqa: E402

TOOLS = {"media": "import json\n", "coaches": "import media\nmedia.has_sample(x)\n",
         "catalog": "PATH = 'movements.toml'\n", "brief": "import catalog\n", "other": "import os\n"}
TESTS = {"test_contract": "", "test_imports": "", "test_integrity": "", "test_harness": "",
         "test_media": "import media\n", "test_coaches": "import coaches\n", "test_brief": "import brief\n",
         "test_other": "import other\n"}
ENFORCERS = ["test_contract", "test_harness", "test_imports", "test_integrity"]


class Pick(unittest.TestCase):
    def test_a_tool_reaches_its_tests_and_the_tools_that_import_it(self):
        self.assertEqual(testpick.pick(["tools/media.py"], TESTS, TOOLS),
                         sorted(ENFORCERS + ["test_coaches", "test_media"]))

    def test_a_data_file_reaches_the_tool_that_names_it(self):
        self.assertEqual(testpick.pick(["knowledge/movements.toml"], TESTS, TOOLS),
                         sorted(ENFORCERS + ["test_brief"]))

    def test_a_changed_test_runs_and_web_is_left_to_its_own_suite(self):
        self.assertEqual(testpick.pick(["tests/test_other.py", "web/webapp/api.py"], TESTS, TOOLS),
                         sorted(ENFORCERS + ["test_other"]))
        self.assertEqual(testpick.pick([], TESTS, TOOLS), ENFORCERS)

    def test_a_shared_helper_runs_everything(self):
        self.assertEqual(testpick.pick(["tests/helpers.py"], TESTS, TOOLS), sorted(TESTS))
        self.assertEqual(testpick.pick(["tests/fixtures/stock/coach-x/persona.md"], TESTS, TOOLS), sorted(TESTS))

    def test_the_real_suite_is_found(self):
        tests = testpick.sources(os.path.dirname(os.path.abspath(__file__)), "test_")
        self.assertIn("test_testpick", tests)
        self.assertNotIn("helpers", tests)


if __name__ == "__main__":
    unittest.main()
