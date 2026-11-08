"""The codes the page reads beside a job's words (webapp/codes.py): an error's, and a step's kind."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from webapp import codes, providers, worker  # noqa: E402


class CodesTest(unittest.TestCase):
    def test_the_page_gets_a_code_for_what_settings_answers(self):
        self.assertEqual(codes.of_error(worker.NO_MODEL_KEY), "no_model_key")
        self.assertEqual(codes.of_error(codes.key_refused("Claude")), "key_refused")

    def test_a_provider_refusal_carries_its_code(self):
        from pydantic_ai import ModelHTTPError
        refused = providers.explain("google", ModelHTTPError(403, "m", None))   # the words the job is failed with
        self.assertEqual(codes.of_error(refused.message), "key_refused")
        self.assertIsNone(codes.of_error(providers.explain("anthropic", RuntimeError()).message))

    def test_other_errors_have_none(self):
        for error in (None, "", "interrupted", worker.TOO_LONG, worker.STOPPED, worker.UNEXPECTED):
            self.assertIsNone(codes.of_error(error))

    def test_a_step_says_what_it_waits_on(self):
        self.assertEqual(codes.step_kind("Recording your workout", "run build", False), "recording")
        self.assertEqual(codes.step_kind("Designing Reed's voice", "run build", False), "voice")
        self.assertEqual(codes.step_kind("Making your coach's voice", "run coaches make", False), "voice")
        self.assertIsNone(codes.step_kind("Checking the script", "run build --lint-only", False))
        self.assertEqual(codes.step_kind("Planning", "think", True), "think")
        self.assertIsNone(codes.step_kind("Gathering today's news", "run feeds", False))


if __name__ == "__main__":
    unittest.main()
