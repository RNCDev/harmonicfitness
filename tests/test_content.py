"""The filler plan, the record of what's been told, and the reserve (tools/content.py)."""
import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import content  # noqa: E402
import check  # noqa: E402
import context  # noqa: E402

TODAY = datetime.date(2026, 10, 23)


def profile(interests):
    return context.Profile({"interests": interests}, "", None)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Recipe(unittest.TestCase):
    def test_bands_scale_with_length(self):
        r = content.recipe()
        self.assertEqual(content.counts(r, 15)["today"], 1)
        self.assertEqual(content.counts(r, 25)["today"], 2)
        self.assertEqual(content.counts(r, 45)["learn"], 2)
        for minutes in (10, 25, 60):
            n = content.counts(r, minutes)
            self.assertEqual(n["deep_dive"], 1)
            self.assertEqual(n["quiz"], 1)

    def test_every_slot_has_defaults_and_the_evergreen_ones_a_reserve_target(self):
        r = content.recipe()
        for sid, slot in r.slots.items():
            self.assertTrue(r.defaults.get(sid), sid)
            self.assertEqual(bool(slot.reserve), not slot.fresh, sid)


class Rotation(unittest.TestCase):
    def test_never_told_first_then_the_oldest(self):
        items = [{"date": "2026-10-20", "slot": "today", "category": "sports", "title": "a"},
                 {"date": "2026-10-22", "slot": "today", "category": "local", "title": "b"}]
        picks = content.due(["sports", "local", "numbers"], items, "today", 3)
        self.assertEqual([c for c, _ in picks], ["numbers", "sports", "local"])
        self.assertEqual(picks[1][1], "2026-10-20")

    def test_another_slots_items_dont_count(self):
        items = [{"date": "2026-10-22", "slot": "learn", "category": "sports", "title": "a"}]
        self.assertEqual(content.due(["sports", "local"], items, "today", 1), [("sports", None)])

    def test_few_categories_repeat(self):
        self.assertEqual(len(content.due(["only"], [], "today", 3)), 3)

    def test_the_profiles_interests_replace_the_defaults_per_slot(self):
        r = content.recipe()
        cats = content.categories(r, profile([{"name": "jazz", "slot": "delight", "detail": "Miles"}]))
        self.assertEqual(cats["delight"], ["jazz"])
        self.assertEqual(cats["learn"], r.defaults["learn"])

    def test_alternating_deep_dive(self):
        items = [{"date": "2026-10-22", "slot": "deep_dive", "category": "news", "title": "a"},
                 {"date": "2026-10-20", "slot": "deep_dive", "category": "video", "title": "b"}]
        self.assertEqual(content.due(["video", "news"], items, "deep_dive", 1)[0][0], "video")


class Record(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.told = os.path.join(self.tmp.name, "told.jsonl")
        self.reserve = os.path.join(self.tmp.name, "reserve")

    def tearDown(self):
        self.tmp.cleanup()

    def test_log_checks_every_item_before_writing(self):
        with self.assertRaises(ValueError):
            content.log("2026-10-23", ["today | sports | Fine", "nowhere | x | y"], path=self.told)
        self.assertFalse(os.path.exists(self.told))
        reserve = os.path.join(os.path.dirname(self.told), "reserve")
        os.makedirs(reserve, exist_ok=True)
        with open(os.path.join(reserve, "grid-plan.md"), "w", encoding="utf-8") as f:
            f.write("# Grid\n- Slot: learn\n- Category: history\n")
        with mock.patch.object(content.paths, "RESERVE", reserve):   # a slug must name a sheet in the reserve
            with self.assertRaises(ValueError):
                content.log("2026-10-23", ["learn | history | Grid | | no-such-sheet"], path=self.told)
            content.log("2026-10-23", ["today | Sports | Home team wins | https://x | ", "learn | history | Grid | | grid-plan"],
                        path=self.told)
        items = content.told(self.told)
        self.assertEqual(items[0]["category"], "sports")
        self.assertEqual(items[0]["source"], "https://x")
        self.assertEqual(items[1]["reserve"], "grid-plan")

    def test_bad_items(self):
        r = content.recipe()
        for bad in ("today | sports", "today |  | t", "a | b | c | d | e | f", "learn | history | t | | Bad Slug"):
            with self.assertRaises(ValueError, msg=bad):
                content.parse_item(bad, "2026-10-23", r)

    def test_a_damaged_line_is_skipped(self):
        write(self.told, '{"date": "2026-10-20", "title": "ok"}\nnot json\n')
        self.assertEqual(len(content.told(self.told)), 1)

    def test_a_reserve_piece_is_used_once_the_record_names_it(self):
        write(os.path.join(self.reserve, "grid-plan.md"),
              "# Why the grid\n- Slot: learn\n- Category: history\n- Source: https://x\n- Added: 2026-10-23\n\nHook.\n")
        write(os.path.join(self.reserve, "no-header.md"), "Just text.\n")
        self.assertEqual([p.slug for p in content.reserve(self.reserve, items=[])], ["grid-plan"])
        used = [{"date": "2026-10-23", "title": "Why the grid", "reserve": "grid-plan"}]
        self.assertEqual(content.reserve(self.reserve, items=used), [])

    def test_the_old_pantry_folder_and_record_key_still_count(self):
        """Before 10.2.0 the reserve was research/pantry/ and the record's key was `pantry`."""
        old = os.path.join(self.tmp.name, "pantry")
        sheet = "# {t}\n- Slot: quiz\n- Category: puzzle\n\nHook.\n"
        write(os.path.join(self.reserve, "new-one.md"), sheet.format(t="New"))
        write(os.path.join(old, "old-one.md"), sheet.format(t="Old"))
        write(os.path.join(old, "new-one.md"), sheet.format(t="Duplicate"))
        found = content.reserve(items=[], folders=(self.reserve, old))
        self.assertEqual(sorted(p.title for p in found), ["New", "Old"])   # a slug in both counts once
        used = [{"date": "2026-10-20", "title": "Old", "pantry": "old-one"}]
        self.assertEqual([p.title for p in content.reserve(items=used, folders=(self.reserve, old))], ["New"])

    def test_the_plan_lists_recent_items_the_reserve_and_restock(self):
        r = content.recipe()
        items = [{"date": "2026-10-22", "slot": "today", "category": "sports", "title": "Home team wins the opener"},
                 {"date": "2026-08-01", "slot": "today", "category": "sports", "title": "Old news"}]
        piece = content.Piece("grid-plan", "Why the grid", "learn", "history", "", "x.md")
        text = "\n".join(content.plan(25, TODAY, r, profile([]), items, [piece]))
        self.assertIn("Home team wins the opener", text)
        self.assertNotIn("Old news", text)            # older than the window
        self.assertIn("Why the grid", text)
        self.assertIn("- learn: 2 more", text)        # three kept, one on hand
        self.assertIn("- quiz: 3 more", text)

    def test_a_full_reserve_needs_no_restock(self):
        r = content.recipe()
        pieces = [content.Piece(f"p{i}-{s}", "t", s, "c", "", "x") for s in ("quiz", "delight", "learn") for i in range(3)]
        self.assertEqual(content.restock(r, content.categories(r), [], pieces), {})


class ProfileCheck(unittest.TestCase):
    def test_an_unknown_slot_is_an_issue(self):
        issues = check._interest_problems("p", {"interests": [{"name": "jazz", "slot": "music"},
                                                                {"name": "x"}, "nope"]})
        self.assertEqual(len(issues), 3)
        self.assertIn("unknown slot 'music'", issues[0].message)

    def test_good_rows_pass(self):
        self.assertEqual(check._interest_problems("p", {"interests": [{"name": "jazz", "slot": "delight"}]}), [])


class Cli(unittest.TestCase):
    def test_a_bad_item_is_a_usage_error(self):
        self.assertEqual(content.main(["log", "--date", "2026-10-23", "--item", "nowhere | a | b"]), 64)


if __name__ == "__main__":
    unittest.main()
