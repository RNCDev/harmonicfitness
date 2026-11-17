"""A workout for later (0.60.0): the picked time read. No database: the queue and the endpoints are in
test_jobs and test_api."""
import datetime
import os
import sys
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi import HTTPException  # noqa: E402

from webapp.routes import conversations  # noqa: E402
from webapp import turns  # noqa: E402

UTC = datetime.timezone.utc
NOON = datetime.datetime(2026, 11, 3, 17, 0, tzinfo=UTC)   # noon in New York


class PickedTime(unittest.TestCase):
    def test_a_time_later_today_is_kept_on_the_listeners_clock(self):
        later = conversations.later_from("2026-11-03T19:30:00-05:00", NOON)
        self.assertEqual(later, {"at": "2026-11-04T00:30:00+00:00", "local": "2026-11-03 Tuesday 19:30",
                                 "offset": -300})
        self.assertEqual(turns.said_when(later["local"]), "Tuesday at 19:30")
        # none picked, or inside the lead: a workout now
        self.assertIsNone(conversations.later_from(None, NOON))
        self.assertIsNone(conversations.later_from("2026-11-03T12:10:00-05:00", NOON))   # ten minutes off: at once

    def test_a_time_past_a_day_without_an_offset_or_unreadable_is_refused(self):
        for bad in ("2026-11-04T13:00:00-05:00", "2026-11-03T19:30:00", "seven thirty"):
            with self.assertRaises(HTTPException, msg=bad) as e:
                conversations.later_from(bad, NOON)
            self.assertEqual(e.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
