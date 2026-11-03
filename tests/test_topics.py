"""./harmonicfitness topics: a topic added at once under ## Topics, and its feed found without a web search (the
page's own feed link, the usual places, or Apple's podcast directory for a name). No network: topics.get is faked,
and the addresses are example hosts."""
import io
import json
import os
import shutil
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from unittest import mock

import helpers  # noqa: F401 - puts tools/ on the path
import cli  # noqa: E402
import context  # noqa: E402
import errors  # noqa: E402
import frontmatter  # noqa: E402
import paths  # noqa: E402
import topics  # noqa: E402

WEEKLY = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Example Letter</title>
<description>Notes on <b>things</b> worth knowing.</description>
<item><title>Three</title><pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Two</title><pubDate>Mon, 26 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>One</title><pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
DAILY = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Example Daily</title><subtitle>Every day</subtitle>
<entry><title>B</title><published>2026-11-02T10:00:00Z</published></entry>
<entry><title>A</title><published>2026-11-01T10:00:00Z</published></entry></feed>"""
PAGE = b"""<html><head><link rel="alternate" type="application/rss+xml" href="/letter.rss"></head></html>"""


def web(pages):
    """A fake topics.get: each address's bytes, or a failure."""
    def get(url):
        if url in pages:
            return pages[url]
        raise OSError("no such page")
    return mock.patch.object(topics, "get", side_effect=get)


class Topics(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp(prefix="hf-topics-")
        self.addCleanup(shutil.rmtree, d, True)
        self.home = helpers.home(os.path.join(d, "me"))
        self.home.__enter__()
        self.addCleanup(self.home.__exit__, None, None, None)
        shutil.copytree(paths.EXAMPLE, paths.HOME)

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = topics.main(list(argv))
        return code, out.getvalue()

    def text(self):
        with open(paths.CONTENT_MD, encoding="utf-8") as f:
            return f.read()

    def feeds(self):
        return tomllib.loads(frontmatter.TOML_FRONT_RE.match(self.text()).group(1))["feeds"]

    def test_a_topic_goes_under_topics_and_the_template_s_hints_go(self):
        code, out = self.run_cli("add", "Formula 1: race weekends", "Sourdough baking")
        self.assertEqual(code, errors.OK)
        self.assertIn("Added under Topics: Formula 1, Sourdough baking.", out)
        lines = [line for _, line in frontmatter.section(frontmatter.body(self.text()), "Topics")]
        self.assertIn("- Formula 1: race weekends", lines)
        self.assertIn("- Sourdough baking", lines)
        self.assertFalse(any(line.startswith("- [") for line in lines))   # check stops asking about them
        self.assertIn("## Venues", self.text())   # every other section kept

    def test_a_name_already_there_is_left_as_it_is(self):
        self.run_cli("add", "Formula 1: race weekends")
        code, out = self.run_cli("add", "formula 1: something else")
        self.assertEqual(code, errors.OK)
        self.assertIn("Already under Topics, left as it is: formula 1.", out)
        self.assertEqual(self.text().count("Formula 1"), 1)

    def test_a_venue_goes_under_venues(self):
        self.run_cli("add", "The Example Room: comedy", "--venue")
        self.assertEqual([t.name for t in context.venues(context.profile())], ["The Example Room"])

    def test_a_line_that_isn_t_a_topic_writes_nothing(self):
        before = self.text()
        with self.assertRaises(errors.UsageError):
            context.add_topic_lines(["Fine one", "[a hint]"])
        self.assertEqual(self.text(), before)

    def test_a_page_s_own_feed_link_is_found_and_added(self):
        with web({"https://letter.example/": PAGE, "https://letter.example/letter.rss": WEEKLY}):
            code, out = self.run_cli("add", "Example Letter: ideas", "--feed", "https://letter.example/")
        self.assertEqual(code, errors.OK)
        self.assertIn("Feed added: https://letter.example/letter.rss (weekly)", out)
        self.assertIn("The feed's own words", out)
        self.assertEqual(self.feeds()[-1], {"label": "Example Letter", "kind": "weekly",
                                            "value": "https://letter.example/letter.rss"})

    def test_an_address_that_is_a_feed_is_used_and_a_daily_one_is_rss(self):
        with web({"https://daily.example/atom": DAILY}):
            self.run_cli("add", "Science: what's new", "--feed", "https://daily.example/atom")
        self.assertEqual(self.feeds()[-1], {"label": "Science, Example Daily", "kind": "rss",
                                            "value": "https://daily.example/atom"})

    def test_the_usual_places_are_tried_and_a_bare_domain_gets_www(self):
        with web({"https://www.letter.example": b"<html></html>", "https://www.letter.example/feed": WEEKLY}):
            _, out = self.run_cli("add", "Example Letter", "--feed", "letter.example")
        self.assertIn("Feed added: https://www.letter.example/feed", out)

    def test_a_podcast_is_found_by_its_name(self):
        answer = json.dumps({"results": [{"collectionName": "Other Show", "feedUrl": "https://pods.example/other"},
                                         {"collectionName": "Example Show", "feedUrl": "https://pods.example/show"}]})
        with web({topics.ITUNES + "Example%20Show": answer.encode(), "https://pods.example/show": WEEKLY,
                  "https://pods.example/other": DAILY}):
            _, out = self.run_cli("add", "Example Show: the week in tech", "--feed", "Example Show")
        self.assertIn("found as Apple's podcast directory", out)
        self.assertEqual(self.feeds()[-1]["value"], "https://pods.example/show")   # the closest name, not the first

    def test_no_feed_found_still_adds_the_topic(self):
        with web({}):
            code, out = self.run_cli("add", "Example Letter", "--feed", "https://nothing.example/")
        self.assertEqual(code, errors.OK)
        self.assertIn("No feed found", out)
        self.assertIn("Example Letter", [t.name for t in context.topics(context.profile())])

    def test_a_feed_already_there_isn_t_added_twice(self):
        pages = {"https://daily.example/atom": DAILY}
        with web(pages):
            self.run_cli("add", "Science", "--feed", "https://daily.example/atom")
            _, out = self.run_cli("add", "More science", "--feed", "https://daily.example/atom")
        self.assertIn("Already a feed", out)
        self.assertEqual([f["value"] for f in self.feeds()].count("https://daily.example/atom"), 1)

    def test_feed_goes_with_one_topic(self):
        with self.assertRaises(cli.Usage):
            self.run_cli("add", "One", "Two", "--feed", "https://x.example/")

    def test_a_hostile_feed_is_refused_unparsed(self):
        evil = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel><title>&a;</title></channel></rss>'
        self.assertIsNone(topics.read_feed(evil, "https://x.example/", "test"))

    def test_the_listing_and_its_json(self):
        self.run_cli("add", "Formula 1: race weekends")
        code, out = self.run_cli("--json")
        self.assertEqual(code, errors.OK)
        self.assertEqual(json.loads(out)["topics"], [{"name": "Formula 1", "note": "race weekends"}])


if __name__ == "__main__":
    unittest.main()
