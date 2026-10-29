import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import qat_key  # noqa: E402


class QatKey(unittest.TestCase):
    def test_reads_only_the_gemini_line(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("FISH_AUDIO_API_KEY=fish-value\nexport GEMINI_API_KEY=\"AIzaabc123\"\n")
        self.addCleanup(os.remove, f.name)
        self.assertEqual(qat_key.read_key(f.name), "AIzaabc123")
        self.assertIsNone(qat_key.read_key(f.name + ".missing"))

    def test_refuses_a_server_that_isnt_local(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("GEMINI_API_KEY=AIzaabc123\n")
        self.addCleanup(os.remove, f.name)
        for base in ("https://harmonicfitness.fly.dev", "http://localhost.evil.example:8000"):
            self.assertEqual(qat_key.main(["--username", "u", "--password", "p", "--base", base, "--env", f.name]), 64)

    def test_no_key_is_a_bad_command(self):
        self.assertEqual(qat_key.main(["--username", "u", "--password", "p", "--env", "/nonexistent.env"]), 64)


if __name__ == "__main__":
    unittest.main()
