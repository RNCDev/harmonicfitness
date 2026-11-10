"""A workout for later (0.60.0): the picked time read, the listener's clock when the turn runs, and a scheduled
turn's arguments. No database: the queue and the endpoints are in test_jobs and test_api."""
import datetime
import os
import sys
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi import HTTPException  # noqa: E402

from webapp import api, turns  # noqa: E402

UTC = datetime.timezone.utc
NOON = datetime.datetime(2026, 11, 3, 17, 0, tzinfo=UTC)   # noon in New York


class PickedTime(unittest.TestCase):
    def test_a_time_later_today_is_kept_on_the_listeners_clock(self):
        later = api.later_from("2026-11-03T19:30:00-05:00", NOON)
        self.assertEqual(later, {"at": "2026-11-04T00:30:00+00:00", "local": "2026-11-03 Tuesday 19:30",
                                 "offset": -300})
        self.assertEqual(turns.said_when(later["local"]), "Tuesday at 19:30")

    def test_none_picked_or_inside_the_lead_is_a_workout_now(self):
        self.assertIsNone(api.later_from(None, NOON))
        self.assertIsNone(api.later_from("2026-11-03T12:10:00-05:00", NOON))   # ten minutes off: at once

    def test_a_time_past_a_day_without_an_offset_or_unreadable_is_refused(self):
        for bad in ("2026-11-04T13:00:00-05:00", "2026-11-03T19:30:00", "seven thirty"):
            with self.assertRaises(HTTPException, msg=bad) as e:
                api.later_from(bad, NOON)
            self.assertEqual(e.exception.status_code, 422)


class TheirClock(unittest.TestCase):
    def test_the_turn_runs_on_the_listeners_date_and_time(self):
        self.assertEqual(turns.local_clock(-300, NOON), ("2026-11-03", "2026-11-03 Tuesday 12:00"))
        self.assertEqual(turns.local_clock(9 * 60, NOON), ("2026-11-04", "2026-11-04 Wednesday 02:00"))

    def test_a_scheduled_turns_arguments_pass_and_half_of_them_dont(self):
        today, now = turns.local_clock(-300)
        base = {"conversation_id": 1, "line": "write it", "answer": None, "today": today, "now": now}
        self.assertIsNone(turns.check(dict(base, scheduled=True, offset=-300)))
        for bad in (dict(base, scheduled=True), dict(base, offset=-300), dict(base, scheduled=True, offset="x"),
                    dict(base, scheduled=True, offset=20 * 60)):
            self.assertIsNotNone(turns.check(bad), bad)


if __name__ == "__main__":
    unittest.main()
