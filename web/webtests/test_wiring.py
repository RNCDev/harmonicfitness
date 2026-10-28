import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import webapp  # noqa: E402


class Wiring(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(webapp.APP_NAME, "HarmonicFitness")


if __name__ == "__main__":
    unittest.main()
