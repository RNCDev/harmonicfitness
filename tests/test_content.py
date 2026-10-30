"""The topics, the formats, the record of what's been told, the stock and trending (tools/content.py)."""
import datetime
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import content  # noqa: E402
import check  # noqa: E402
import context  # noqa: E402
import frontmatter  # noqa: E402

TODAY = datetime.date(2026, 10, 23)
T = context.Topic


def profile(topics="", settings=None):
    body = "## Topics\nI like to stay current on and learn about:\n" + topics if topics else ""
    return context.Profile(settings or {}, body, None)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Recipe(unittest.TestCase):
    def test_bands_scale_with_length(self):
        r = content.recipe()
        self.assertLess(content.band(r, 15).topics, content.band(r, 25).topics)
        self.assertLessEqual(content.band(r, 25).topics, content.band(r, 60).topics)
        self.assertFalse(content.band(r, 10).serial)
        self.assertTrue(content.band(r, 25).serial)

    def test_every_format_is_whole(self):
        r = content.recipe()
        self.assertGreaterEqual(len(r.formats), 12)
        for f in r.formats.values():
            self.assertIn(f.research, content.RESEARCH, f.id)
            self.assertTrue(f.what and f.name and f.words > 0, f.id)
        for legacy in content.LEGACY_SLOT_FORMAT.values():   # an old stock sheet maps to a format that exists
            self.assertIn(legacy, r.formats)

    def test_a_format_by_its_id_or_name(self):
        r = content.recipe()
        for said in ("quick_hit", "quick hit", "Quick-hit", "big story", "The big story", "Big_Story"):
            self.assertIsNotNone(content.format_id(r, said), said)
        self.assertIsNone(content.format_id(r, "sports"))


class Topics(unittest.TestCase):
    def test_lines_under_topics(self):
        p = profile("- Seattle Kraken: scores and previews\n- Stoic philosophy\n- [a hint]\n\nnot a line\n")
        self.assertEqual(context.topics(p), [T("Seattle Kraken", "scores and previews"),
                                             T("Stoic philosophy", "")])

    def test_old_interest_rows_still_read_less_the_formats(self):
        p = profile("- Jazz: bebop\n", {"interests": [
            {"name": "video", "slot": "deep_dive"}, {"name": "jazz", "slot": "delight", "detail": "x"},
            {"name": "Gardening", "slot": "learn", "detail": "roses"}]})
        self.assertEqual(context.topics(p), [T("Jazz", "bebop"), T("Gardening", "roses")])

    def test_a_note_in_brackets_or_after_a_dash(self):
        self.assertEqual(context.topic_line("- Chips (go deep; Asianometry)"), T("Chips", "go deep; Asianometry"))
        self.assertEqual(context.topic_line("- F1 - race weekends"), T("F1", "race weekends"))
        self.assertEqual(context.topic_line("- Spider-Man comics"), T("Spider-Man comics", ""))


class Rotation(unittest.TestCase):
    def test_never_told_first_then_the_oldest(self):
        items = [{"date": "2026-10-20", "topic": "Kraken", "format": "quick_hit", "title": "a"},
                 {"date": "2026-10-22", "topic": "local", "format": "quick_hit", "title": "b"}]
        picks = content.due([T("Kraken", ""), T("Local", ""), T("Jazz", "")], items, 3)
        self.assertEqual([t.name for t, _ in picks], ["Jazz", "Kraken", "Local"])
        self.assertEqual(picks[1][1], "2026-10-20")

    def test_an_old_lines_category_counts_as_its_topic(self):
        items = [{"date": "2026-10-22", "slot": "today", "category": "sports", "title": "a"}]
        picks = content.due([T("Sports", ""), T("Science", "")], items, 2)
        self.assertEqual([t.name for t, _ in picks], ["Science", "Sports"])

    def test_few_topics_are_all_of_them(self):
        self.assertEqual(len(content.due([T("only", "")], [], 3)), 1)


class Record(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.told = os.path.join(self.tmp.name, "told.jsonl")
        self.reserve = os.path.join(self.tmp.name, "reserve")

    def tearDown(self):
        self.tmp.cleanup()

    def test_log_checks_every_item_before_writing(self):
        p = profile("- History\n- Kraken\n")
        with self.assertRaises(ValueError):
            content.log("2026-10-23", ["Kraken | quick hit | Fine", "Kraken | nowhere | y"], path=self.told, profile=p)
        self.assertFalse(os.path.exists(self.told))
        write(os.path.join(self.reserve, "grid-plan.md"), "# Grid\n- Topic: History\n- Format: explainer\n")
        with mock.patch.object(content.paths, "RESERVE", self.reserve):   # a slug must name a sheet in the stock
            with self.assertRaises(ValueError):
                content.log("2026-10-23", ["history | explainer | Grid | | no-such-sheet"], path=self.told, profile=p)
            content.log("2026-10-23", ["kraken | Quick hit | Home team wins | https://x | ",
                                       "History | explainer | Grid | | grid-plan", "- | brain teaser | A riddle"],
                        path=self.told, profile=p)
        items = content.told(self.told)
        self.assertEqual((items[0]["topic"], items[0]["format"]), ("Kraken", "quick_hit"))   # the listener's spelling
        self.assertEqual(items[0]["source"], "https://x")
        self.assertEqual(items[1]["reserve"], "grid-plan")
        self.assertEqual(items[2]["topic"], "-")

    def test_a_topic_not_theirs_is_refused(self):
        with self.assertRaises(ValueError) as got:
            content.parse_item("Krakn | quick_hit | A result", "2026-10-23", content.recipe(), profile("- Kraken\n"))
        self.assertIn("Kraken", str(got.exception))
        # with no topics at all, any topic is taken
        self.assertEqual(content.parse_item("Anything | quiz | Q", "2026-10-23", content.recipe(), profile())["topic"],
                         "Anything")

    def test_bad_items(self):
        r = content.recipe()
        for bad in ("Kraken | quiz", "Kraken |  | t", "a | quiz | c | d | e | f", "x | history | t",
                    "Kraken | quiz | t | | Bad Slug"):
            with self.assertRaises(ValueError, msg=bad):
                content.parse_item(bad, "2026-10-23", r)

    def test_a_damaged_line_is_skipped(self):
        write(self.told, '{"date": "2026-10-20", "title": "ok"}\nnot json\n')
        self.assertEqual(len(content.told(self.told)), 1)

    def test_a_stock_piece_is_used_once_the_record_names_it_and_ends_when_it_goes_stale(self):
        write(os.path.join(self.reserve, "grid-plan.md"),
              "# Why the grid\n- Topic: Cities\n- Format: explainer\n- Source: https://x\n- Added: 2026-10-23\n"
              "- Good until: evergreen\n\nHook.\n")
        write(os.path.join(self.reserve, "preview.md"),
              "# Tonight's opener\n- Topic: Kraken\n- Format: quick_hit\n- Good until: 2026-10-22\n")
        write(os.path.join(self.reserve, "old-style.md"), "# Old\n- Slot: learn\n- Category: history\n")
        write(os.path.join(self.reserve, "no-header.md"), "Just text.\n")
        got = {p.slug: p for p in content.reserve(self.reserve, items=[], today=TODAY)}
        self.assertEqual(sorted(got), ["grid-plan", "old-style"])          # the stale preview is left out
        self.assertEqual((got["old-style"].topic, got["old-style"].format), ("history", "explainer"))
        self.assertIsNone(got["grid-plan"].good_until)
        self.assertEqual(len(content.reserve(self.reserve, items=[])), 3)   # without today, every unused piece
        used = [{"date": "2026-10-23", "title": "Why the grid", "reserve": "grid-plan"}]
        self.assertEqual([p.slug for p in content.reserve(self.reserve, items=used, today=TODAY)], ["old-style"])

    def test_the_plan_lists_topics_formats_recent_items_the_stock_and_restock(self):
        r = content.recipe()
        items = [{"date": "2026-10-22", "topic": "Kraken", "format": "quick_hit", "title": "Home team wins the opener"},
                 {"date": "2026-08-01", "slot": "today", "category": "Kraken", "title": "Old news"}]
        piece = content.Piece("grid-plan", "Why the grid", "Cities", "explainer", "", None, "x.md")
        p = profile("- Kraken: scores\n- Cities\n- Jazz\n", {"skip_formats": ["memory game"]})
        text = "\n".join(content.plan(25, TODAY, r, p, items, [piece]))
        self.assertIn("Home team wins the opener", text)
        self.assertNotIn("Old news", text)            # older than the window
        self.assertIn("Why the grid", text)
        self.assertIn("- Jazz: 2 more", text)         # never told, nothing held: first
        self.assertIn("- Cities: 1 more", text)       # one held of two
        self.assertNotIn("memory_game (", text)       # left out by the listener
        self.assertIn("left out by the listener: memory_game", text)
        f = content.plan_facts(25, TODAY, r, p, items, [piece])
        self.assertEqual([d["topic"] for d in f["due"]], ["Cities", "Jazz", "Kraken"])
        self.assertEqual(f["restock"][0]["topic"], "Jazz")

    def test_no_topics_still_plans(self):
        text = "\n".join(content.plan(25, TODAY, content.recipe(), profile(), [], []))
        self.assertIn("No topics yet", text)

    def test_restock_stops_at_the_runs_cap(self):
        r = content.recipe()
        tops = [T(f"t{i}", "") for i in range(10)]
        self.assertEqual(sum(k for _, k in content.restock(r, tops, [], [])), r.per_run)
        full = [content.Piece(f"p{i}{n}", "x", t.name, "quiz", "", None, "x") for t in tops for n in range(r.per_topic)
                for i in (0,)]
        self.assertEqual(content.restock(r, tops, [], full), [])


class Trending(unittest.TestCase):
    def test_reddit_safe_for_work_only_one_a_community(self):
        listing = {"data": {"children": [
            {"data": {"subreddit": "pics", "title": "A  view", "over_18": False, "subreddit_type": "public"}},
            {"data": {"subreddit": "nsfwthing", "title": "no", "over_18": True}},
            {"data": {"subreddit": "pics", "title": "another", "over_18": False}},
            {"data": {"subreddit": "x", "title": "adult", "whitelist_status": "promo_adult_nsfw"}},
            {"data": {"subreddit": "space", "title": "Launch", "subreddit_type": "public"}}]}}
        self.assertEqual(content.parse_reddit(listing), [("pics", "A view"), ("space", "Launch")])

    def test_wikipedia_when_reddit_refuses(self):
        def fetch(url):
            if "reddit" in url:
                raise OSError("403")
            return json.dumps({"mostread": {"articles": [
                {"title": "Comet_X", "normalizedtitle": "Comet X", "description": "a comet", "rank": 1}]}}).encode()
        source, lines = content.trending(TODAY, fetch=fetch)
        self.assertIn("Wikipedia", source)
        self.assertEqual(lines, ["- Comet X: a comet"])   # the same page on both days, once

    def test_nothing_reachable_is_a_problem(self):
        def fetch(url):
            raise OSError("down")
        with self.assertRaises(content.errors.HarmonicFitnessError):
            content.trending(TODAY, fetch=fetch)


class ProfileCheck(unittest.TestCase):
    def test_old_rows_are_a_note(self):
        issues = check._interest_problems("p", {"interests": [{"name": "jazz", "slot": "music"}]})
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].note)
        self.assertEqual(check._interest_problems("p", {}), [])

    def test_unknown_skip_formats_and_template_topics(self):
        p = profile("- [a team you follow]\n", {"skip_formats": ["quiz", "dance"]})
        issues = check._topic_problems("p", p, p.settings)
        messages = " ".join(i.message for i in issues)
        self.assertIn("'dance' isn't a format", messages)
        self.assertNotIn("'quiz'", messages)
        self.assertIn("isn't filled in yet", messages)
        self.assertIn("no topics", messages)

    def test_good_topics_pass(self):
        p = profile("- Jazz\n")
        self.assertEqual(check._topic_problems("p", p, p.settings), [])


class Migrate(unittest.TestCase):
    def test_interest_rows_become_topic_lines(self):
        import migrate
        with tempfile.TemporaryDirectory() as home:
            path = os.path.join(home, "content.md")
            write(path, '+++\nschema = 6\npuzzles = ["X"]\n\n# What the filler between exercises rotates through: '
                        'rows.\n\n[[interests]]\nname = "sports"\nslot = "today"\ndetail = "Kraken"\n\n'
                        '[[interests]]\nname = "video"\nslot = "deep_dive"\n\n# Fetched by feeds.\n[[feeds]]\n'
                        'label = "W"\nkind = "weather"\nvalue = "1, 2"\n+++\n# Content\n\nIntro.\n\n## Taste\n- x\n')
            self.assertTrue(migrate.topics_due(home))
            migrate.convert_interests(home, os.path.join(home, ".backup"))
            with open(path, encoding="utf-8") as f:
                text = f.read()
            settings, rest = frontmatter.front(text)
            self.assertNotIn("interests", settings)
            self.assertEqual(settings["puzzles"], ["X"])
            self.assertEqual(len(settings["feeds"]), 1)
            self.assertIn("# Fetched by feeds.", text)
            self.assertIn("## Topics\nI like to stay current on and learn about:\n- sports: Kraken\n\n## Taste", rest)
            self.assertNotIn("video", rest)
            self.assertFalse(migrate.topics_due(home))
            self.assertTrue(os.path.exists(os.path.join(home, ".backup", "content.md.before-topics")))

    def test_an_existing_topics_section_gains_only_new_names(self):
        import migrate
        with tempfile.TemporaryDirectory() as home:
            path = os.path.join(home, "content.md")
            write(path, '+++\nschema = 6\n[[interests]]\nname = "Jazz"\nslot = "delight"\n\n[[interests]]\n'
                        'name = "F1"\nslot = "today"\n+++\n# Content\n\n## Topics\n- jazz: bebop\n\n## Taste\n')
            migrate.convert_interests(home, os.path.join(home, ".backup"))
            with open(path, encoding="utf-8") as f:
                rest = f.read().split("+++", 2)[2]
            self.assertIn("## Topics\n- jazz: bebop\n- F1\n\n## Taste", rest)


class Cli(unittest.TestCase):
    def test_a_bad_item_is_a_usage_error(self):
        self.assertEqual(content.main(["log", "--date", "2026-10-23", "--item", "Kraken | nowhere | b"]), 64)


if __name__ == "__main__":
    unittest.main()
