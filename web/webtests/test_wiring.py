import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import webapp  # noqa: E402


class Wiring(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(webapp.APP_NAME, "HarmonicFitness")

    def test_the_web_process_never_imports_the_worker(self):
        web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        out = subprocess.run([sys.executable, "-c",
                              "import webapp.api, webapp.start, sys; print('webapp.worker' in sys.modules)"],
                             cwd=web, capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(out.stdout.strip(), "False")


if __name__ == "__main__":
    unittest.main()
