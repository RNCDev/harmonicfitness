"""The private podcast feed's RSS, without a database (the routes are tested in test_api.Feed)."""
import datetime
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import feed  # noqa: E402

ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"
MADE = datetime.datetime(2026, 11, 9, 7, 30, tzinfo=datetime.timezone.utc)


class Rss(unittest.TestCase):
    def test_a_podcast_apps_feed(self):
        items = [("11111111-1111-1111-1111-111111111111", "Legs & lungs <30 min>", 1234, MADE)]
        root = ET.fromstring(feed.rss("https://example.test/", "TOKEN", items))
        channel = root.find("channel")
        self.assertEqual(channel.findtext("title"), "HarmonicFitness workouts")
        self.assertEqual(channel.find(f"{ITUNES}image").get("href"), "https://example.test/podcast-cover.png")
        self.assertEqual(channel.findtext(f"{ITUNES}block"), "Yes")   # private: kept out of directories
        item = channel.find("item")
        self.assertEqual(item.findtext("title"), "Legs & lungs <30 min>")
        self.assertEqual(item.findtext("pubDate"), "Mon, 09 Nov 2026 07:30:00 +0000")
        enc = item.find("enclosure")
        self.assertEqual((enc.get("url"), enc.get("length"), enc.get("type")),
                         ("https://example.test/feed/TOKEN/11111111-1111-1111-1111-111111111111.mp3", "1234",
                          "audio/mpeg"))

    def test_empty_until_the_first_workout(self):
        root = ET.fromstring(feed.rss("https://example.test", "T", []))
        self.assertEqual(root.find("channel").findall("item"), [])

    def test_a_token_is_what_the_route_accepts(self):
        t = feed._token()
        self.assertRegex(t, f"^{feed.TOKEN}$")
        self.assertIsNone(re.fullmatch(feed.TOKEN, t + "x"))
        self.assertEqual(feed.url("https://example.test/", t), f"https://example.test/feed/{t}.xml")


if __name__ == "__main__":
    unittest.main()
