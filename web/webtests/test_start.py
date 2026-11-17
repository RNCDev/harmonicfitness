"""GET /api/start needs a session."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webtests import test_api  # noqa: E402


class Route(test_api.ApiCase):
    def test_needs_session(self):
        self.assertEqual(self.client.get("/api/start").status_code, 401)


if __name__ == "__main__":
    unittest.main()
