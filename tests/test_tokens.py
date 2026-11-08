"""The brand's tokens are written once: web/client/src/tokens.css. The docs keep an exact copy, the web player page
inlines it, and its brand colours are assets/brand/make.py's, which draws the mark."""
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import webcopy  # noqa: E402

TOKENS = os.path.join(ROOT, "web", "client", "src", "tokens.css")
DOCS_TOKENS = os.path.join(ROOT, "docs", "tokens.css")
MAKE = os.path.join(ROOT, "assets", "brand", "make.py")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def token(css, name):
    m = re.search(rf"--{re.escape(name)}:\s*(#[0-9A-Fa-f]{{6}})", css)
    return m.group(1).upper() if m else None


class Tokens(unittest.TestCase):
    def test_the_docs_copy_is_exact(self):
        self.assertEqual(read(DOCS_TOKENS), read(TOKENS), "copy web/client/src/tokens.css to docs/tokens.css")

    def test_the_brand_colours_are_the_marks(self):
        make = read(MAKE)
        ink, coral, cream, _ = re.search(r'^INK, CORAL, CREAM, WHITE = "(#\w+)", "(#\w+)", "(#\w+)", "(#\w+)"', make, re.M).groups()
        low, _, high = re.search(r'EMBER = \(\(0\.0, "(#\w+)"\), \(0\.65, (\w+)\), \(1\.0, "(#\w+)"\)\)', make).groups()
        css = read(TOKENS)
        self.assertEqual(token(css, "coral"), coral.upper())
        self.assertEqual(token(css, "paper"), ink.upper())
        self.assertEqual(token(css, "ink"), cream.upper())
        self.assertEqual(token(css, "ember-low"), low.upper())
        self.assertEqual(token(css, "ember-high"), high.upper())

    def test_the_docs_stylesheet_takes_the_tokens_and_types_no_brand_colour(self):
        css = read(os.path.join(ROOT, "docs", "docs.css"))
        self.assertIn('@import url("tokens.css");', css)
        body = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        self.assertEqual(re.findall(r"#[0-9A-Fa-f]{3,8}\b", body), [])

    def test_the_player_page_is_the_apps_look(self):
        with tempfile.TemporaryDirectory() as d:
            page = webcopy.page("Workout", [os.path.join(d, "Workout.web-1.mp3")], os.path.join(d, "p.html"))
            text = read(page)
        self.assertIn(read(TOKENS), text)
        self.assertNotIn("#2f6f4f", text)   # the green it had before 0.67.0
        self.assertNotIn('data-theme="light"', text)   # dark only, as the app is

    def test_the_player_page_needs_no_web_client(self):
        """web/ is optional: without it the page still has every token its own rules use."""
        import unittest.mock as mock
        with mock.patch.object(webcopy, "TOKENS", "/nowhere/tokens.css"):
            css = webcopy.tokens()
        rules = webcopy.PAGE[webcopy.PAGE.index("{tokens}"):webcopy.PAGE.index("</style>")]
        used = set(re.findall(r"var\((--[\w-]+)", rules))
        defined = set(re.findall(r"(--[\w-]+):", css))
        self.assertEqual(used - defined, set())


if __name__ == "__main__":
    unittest.main()
