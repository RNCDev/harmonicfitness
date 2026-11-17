"""The topics, the formats, the record of what's been told, the stock and trending (tools/content.py)."""
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

T = context.Topic


def profile(topics="", settings=None):
    body = "## Topics\nI like to stay current on and learn about:\n" + topics if topics else ""
    return context.Profile(settings or {}, body, None)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class Topics(unittest.TestCase):
    def test_lines_under_topics_and_old_interest_rows(self):
        p = profile("- Seattle Kraken: scores and previews\n- Stoic philosophy\n- [a hint]\n\nnot a line\n")
        self.assertEqual(context.topics(p), [T("Seattle Kraken", "scores and previews"),
                                             T("Stoic philosophy", "")])
        p = profile("- Jazz: bebop\n", {"interests": [
            {"name": "video", "slot": "deep_dive"}, {"name": "jazz", "slot": "delight", "detail": "x"},
            {"name": "Gardening", "slot": "learn", "detail": "roses"}]})
        self.assertEqual(context.topics(p), [T("Jazz", "bebop"), T("Gardening", "roses")])
        self.assertEqual(context.topic_line("- Chips (go deep; Asianometry)"), T("Chips", "go deep; Asianometry"))
        self.assertEqual(context.topic_line("- F1 - race weekends"), T("F1", "race weekends"))
        self.assertEqual(context.topic_line("- Spider-Man comics"), T("Spider-Man comics", ""))

    def test_never_told_first_then_the_oldest(self):
        items = [{"date": "2026-10-20", "topic": "Kraken", "format": "quick_hit", "title": "a"},
                 {"date": "2026-10-22", "topic": "local", "format": "quick_hit", "title": "b"}]
        picks = content.due([T("Kraken", ""), T("Local", ""), T("Jazz", "")], items, 3)
        self.assertEqual([t.name for t, _ in picks], ["Jazz", "Kraken", "Local"])
        self.assertEqual(picks[1][1], "2026-10-20")
        items = [{"date": "2026-10-22", "slot": "today", "category": "sports", "title": "a"}]   # an old line
        self.assertEqual([t.name for t, _ in content.due([T("Sports", ""), T("Science", "")], items, 2)],
                         ["Science", "Sports"])
        self.assertEqual(len(content.due([T("only", "")], [], 3)), 1)

    def test_profile_check(self):
        issues = check._interest_problems("p", {"interests": [{"name": "jazz", "slot": "music"}]})
        self.assertEqual(len(issues), 1)
        self.assertTrue(issues[0].note)
        self.assertEqual(check._interest_problems("p", {}), [])
        p = profile("- [a team you follow]\n", {"skip_formats": ["quiz", "dance"]})
        messages = " ".join(i.message for i in check._topic_problems("p", p, p.settings))
        self.assertIn("'dance' isn't a format", messages)
        self.assertNotIn("'quiz'", messages)
        self.assertIn("isn't filled in yet", messages)
        self.assertIn("no topics", messages)
        p = profile("- Jazz\n")
        self.assertEqual(check._topic_problems("p", p, p.settings), [])


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
        with self.assertRaises(ValueError) as got:   # a topic not theirs names theirs
            content.log("2026-10-23", ["Krakn | quick hit | A result"], path=self.told, profile=p)
        self.assertIn("Kraken", str(got.exception))
        self.assertEqual(content.parse_item("Anything | quiz | Q", "2026-10-23", content.recipe(), profile())["topic"],
                         "Anything")   # with no topics at all, any topic is taken
        r = content.recipe()
        for bad in ("Kraken | quiz", "Kraken |  | t", "a | quiz | c | d | e | f", "x | history | t",
                    "Kraken | quiz | t | | Bad Slug"):
            with self.assertRaises(ValueError, msg=bad):
                content.parse_item(bad, "2026-10-23", r)
        write(os.path.join(self.reserve, "grid-plan.md"), "# Grid\n- Topic: History\n- Format: explainer\n")
        with mock.patch.object(content.paths, "RESERVE", self.reserve):   # a slug must name a sheet in the stock
            with self.assertRaises(ValueError):
                content.log("2026-10-23", ["history | explainer | Grid | | no-such-sheet"], path=self.told, profile=p)
            with self.assertRaises(ValueError):   # a reserve piece twice in one call
                content.log("2026-10-23", ["history | explainer | Grid | | grid-plan"] * 2, path=self.told)
            content.log("2026-10-23", ["kraken | Quick hit | Home team wins | https://x | ",
                                       "History | explainer | Grid | | grid-plan", "- | brain teaser | A riddle"],
                        path=self.told, profile=p)
            with self.assertRaises(ValueError) as got:   # and never again
                content.log("2026-10-24", ["history | explainer | Grid | | grid-plan"], path=self.told)
            self.assertIn("already told", str(got.exception))
        with open(self.told, "a", encoding="utf-8") as f:
            f.write("not json\n")
        items = content.told(self.told)   # a damaged line is skipped
        self.assertEqual(len(items), 3)
        self.assertEqual((items[0]["topic"], items[0]["format"]), ("Kraken", "quick_hit"))   # the listener's spelling
        self.assertEqual(items[0]["source"], "https://x")
        self.assertEqual(items[1]["reserve"], "grid-plan")
        self.assertEqual(items[2]["topic"], "-")
        self.assertEqual(content.main(["log", "--date", "2026-10-23", "--item", "Kraken | nowhere | b"]), 64)

    def test_threads_are_checked_then_open_until_closed(self):
        path = os.path.join(self.tmp.name, "threads.jsonl")
        p = profile("- Space\n- Kraken\n")
        with self.assertRaises(ValueError):   # every thread checked before any is written
            content.open_threads("2026-10-23", ["Space | quiz | Longest day?", "Space | gossip | x"], path=path, profile=p)
        self.assertFalse(os.path.exists(path))
        with self.assertRaises(ValueError):
            content.open_threads("2026-10-23", ["Krakn | follow-up | the trade"], path=path, profile=p)
        new = content.open_threads("2026-10-23", ["space | Quiz | Which planet has the longest day? (Venus)",
                                                  "- | take | The coach says pineapple belongs on pizza"],
                                   path=path, profile=p)
        self.assertEqual([t["id"] for t in new], ["t1", "t2"])
        self.assertEqual((new[0]["topic"], new[0]["kind"]), ("Space", "quiz"))
        content.close_thread("2026-10-25", "t1", path=path)
        with self.assertRaises(ValueError):
            content.close_thread("2026-10-25", "t1", path=path)   # already closed
        self.assertEqual([t["id"] for t in content.threads(path)], ["t2"])


class Trending(unittest.TestCase):
    def test_reddit_safe_for_work_only_one_a_community(self):
        listing = {"data": {"children": [
            {"data": {"subreddit": "pics", "title": "A  view", "over_18": False, "subreddit_type": "public"}},
            {"data": {"subreddit": "nsfwthing", "title": "no", "over_18": True}},
            {"data": {"subreddit": "pics", "title": "another", "over_18": False}},
            {"data": {"subreddit": "x", "title": "adult", "whitelist_status": "promo_adult_nsfw"}},
            {"data": {"subreddit": "space", "title": "Launch", "subreddit_type": "public"}}]}}
        self.assertEqual(content.parse_reddit(listing), [("pics", "A view"), ("space", "Launch")])

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


if __name__ == "__main__":
    unittest.main()
