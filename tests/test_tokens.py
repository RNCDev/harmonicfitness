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



DOCS = os.path.join(ROOT, "docs")
PAGES = sorted(os.path.join(d, f) for d in (DOCS, os.path.join(DOCS, "demos")) for f in os.listdir(d) if f.endswith(".html"))
PALETTE = r"var\(--(ink|ink-2|ink-3|ink-hi|ink-slot|rule|line|paper|sheet|sheet-2|drawer|stop|stop-tint|blue|blue-hi|blue-tint|coral)\)"


def strip(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def docs_rules():
    """docs.css after its own :root, where the docs' own tokens are named (and may use the palette)."""
    css = strip(read(os.path.join(DOCS, "docs.css")))
    return css[css.index("}", css.index(":root")) + 1:]


class DocsKeepToTheTokens(unittest.TestCase):
    """The docs' stylesheet holds to the rules web/client/src/theme.test.ts holds the app's to, and the pages keep
    their look in it: no <style> block, and no style= but a custom property (a colour swatch's --s)."""

    def broken(self, pattern, css=None):
        return re.findall(pattern, docs_rules() if css is None else css)

    def test_the_pages_hold_no_style_of_their_own(self):
        for page in PAGES:
            html = read(page)
            with self.subTest(page=os.path.relpath(page, ROOT)):
                self.assertNotIn("<style", html, "move the rules into docs/docs.css")
                for value in re.findall(r'\sstyle\s*=\s*"([^"]*)"', html):
                    for decl in filter(None, (d.strip() for d in value.split(";"))):
                        self.assertRegex(decl, r"^--[\w-]+\s*:", f'style="{value}": only a custom property may be set here')

    def test_every_page_takes_the_docs_stylesheet(self):
        for page in PAGES:
            with self.subTest(page=os.path.relpath(page, ROOT)):
                self.assertRegex(read(page), r'<link rel="stylesheet" href="(\.\./)?docs\.css">')

    def test_it_types_no_colour_and_mixes_no_tint(self):
        self.assertEqual(self.broken(r"#[0-9a-fA-F]{3,8}\b"), [])
        self.assertEqual(self.broken(r"\brgba?\(|\bhsla?\("), [])
        self.assertEqual(self.broken(r"color-mix\("), [])

    def test_it_names_each_colour_by_its_role(self):
        self.assertEqual(self.broken(PALETTE), [])

    def test_it_types_no_font_size(self):
        self.assertEqual(self.broken(r"font(?:-size)?:[^;}]*?(?:\b\d+(?:\.\d+)?px|clamp\()"), [])

    def test_it_types_no_spacing_in_pixels(self):
        """A hairline of one or two pixels, or a negative nudge, may be typed."""
        spacing = r"(?:^|[;{\s])(?:padding|margin|gap|row-gap|column-gap|inset|top|left|right|bottom)[\w-]*\s*:([^;}]*)"
        found = [v for m in re.findall(spacing, docs_rules()) for v in re.findall(r"(?<![\w.-])\d+px", m) if int(v[:-2]) > 2]
        self.assertEqual(found, [])

    def test_it_sizes_no_control_in_pixels(self):
        """A small mark under 16px, or a layout size over 64px, may be typed."""
        size = r"(?:^|[;{\s])(?:width|height|min-width|min-height)\s*:([^;}]*)"
        found = [v for m in re.findall(size, docs_rules()) for v in re.findall(r"(?<![\w.-])\d+px", m) if 16 <= int(v[:-2]) <= 64]
        self.assertEqual(found, [])

    def test_line_height_spacing_motion_and_focus_come_from_their_tokens(self):
        self.assertEqual(self.broken(r"line-height:(?!\s*(?:var\(--(?:lh-[\w-]+|chip|control)\)|inherit|normal))[^;}]+"), [])
        self.assertEqual(self.broken(r"font:[^;}]*/\s*[\d.]+"), [])
        self.assertEqual(self.broken(r"letter-spacing:(?!\s*(?:var\(--track-[\w-]+\)|0|normal)\s*(?:[;}]|$))[^;}]+"), [])
        self.assertEqual(self.broken(r"opacity:(?!\s*(?:0|1|var\(--(?:o-[\w-]+|disabled)\))\s*(?:[;}!]|$))[^;}]+"), [])
        timed = [t for d in re.findall(r"(?:transition|animation)[\w-]*:[^;}]+", docs_rules())
                 for t in re.findall(r"(?<![\w.-])\d*\.?\d+m?s\b", d) if t != ".01ms"]
        self.assertEqual(timed, [])
        self.assertEqual(self.broken(r"outline-offset:(?!\s*var\(--focus-(?:offset|inset)\))[^;}]+"), [])
        self.assertEqual(self.broken(r"outline:\s*\d+px solid[^;}]*"), [])

    def test_it_rounds_corners_only_by_the_corner_tokens(self):
        corners = [d.strip() for d in re.findall(r"border-radius:\s*[^;}]+", docs_rules())]
        self.assertEqual([d for d in corners if not re.match(r"^border-radius:\s*(var\(--radius-(control|sheet|pill)\)|50%|inherit)$", d)], [])

    def test_it_changes_layout_only_at_the_four_breakpoints(self):
        widths = re.findall(r"@media[^{]*?\((?:max|min)-width:\s*(\d+)px\)", docs_rules())
        self.assertEqual([w for w in widths if w not in ("480", "640", "760", "1000")], [])

    def test_no_form_control_gets_a_hover_look_while_disabled(self):
        """The docs have links and cards, which can't be disabled; a button, input or select would need :not(:disabled)."""
        hovered = [s.strip() for s in re.findall(r"[^{},]*:hover[^{,]*", docs_rules())]
        controls = [s for s in hovered if re.search(r"\b(button|input|select|textarea)\b", s) and ":not(:disabled)" not in s]
        self.assertEqual(controls, [])

    def test_keyboard_focus_shows_the_one_ring(self):
        """With no rule a keyboard user sees each browser's own ring, or none where a rule clears the outline."""
        rule = re.search(r"(?:^|[}\s]):focus-visible\s*\{([^}]*)\}", docs_rules())
        self.assertIsNotNone(rule, "docs.css needs a :focus-visible rule")
        self.assertIn("outline: var(--focus-ring)", rule.group(1))
        self.assertIn("outline-offset: var(--focus-offset)", rule.group(1))
        self.assertEqual(self.broken(r"outline:\s*(?:none|0)\b"), [])

    def test_every_token_the_docs_use_is_defined(self):
        """By tokens.css or docs.css, or set by a page on the element (a swatch's --s)."""
        css = read(os.path.join(DOCS, "docs.css"))
        defined = set(re.findall(r"(--[\w-]+)\s*:", read(TOKENS) + css))
        for page in PAGES:
            defined |= set(re.findall(r'style="[^"]*?(--[\w-]+)\s*:', read(page)))
        used = set(re.findall(r"var\((--[\w-]+)", css))
        for page in PAGES:
            used |= set(re.findall(r"var\((--[\w-]+)", read(page)))
        self.assertEqual(used - defined, set())


class Player(unittest.TestCase):
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

    def test_the_stand_in_tokens_are_the_apps(self):
        """Each token the page carries without web/ has the app's value (the display face may leave out the
        variable font's family, which only the app ships)."""
        def values(css):
            return {m.group(1): " ".join(m.group(2).split()) for m in re.finditer(r"(--[\w-]+):\s*([^;]+);", css)}
        app = values(read(TOKENS))
        drift = {k: (v, app.get(k)) for k, v in values(webcopy.FALLBACK_TOKENS).items()
                 if k != "--display" and v != app.get(k)}
        self.assertEqual(drift, {})

    def test_the_player_page_types_no_size(self):
        """Its own rules take spacing, line heights, weights and lines from the tokens, as the app's do."""
        rules = webcopy.PAGE[webcopy.PAGE.index("{tokens}") + len("{tokens}"):webcopy.PAGE.index("</style>")]
        self.assertEqual(re.findall(r"(?:margin|padding|gap)[\w-]*:[^;}]*?\b(?:[3-9]|\d{2,})px", rules), [])
        self.assertEqual(re.findall(r"font:[^;}]*\/\s*[\d.]+", rules), [])
        self.assertEqual(re.findall(r"font:\s*\d{3}\b", rules), [])
        self.assertEqual(re.findall(r"box-shadow:[^;}]*\dpx", rules), [])


class Guide(unittest.TestCase):
    def test_each_swatch_is_the_token_it_names(self):
        """The style guide's swatches are typed by hand: each one's colour is its own code, and the token it names
        (or, for a brand colour, some token) has that value."""
        guide = read(os.path.join(ROOT, "docs", "style-guide.html"))
        css = read(TOKENS)
        hexes = {h.upper() for h in re.findall(r"--[\w-]+:\s*(#[0-9A-Fa-f]{6})", css)}
        swatches = re.findall(r'<div class="sw" style="--s:(#[0-9A-Fa-f]{6})"><i></i><div><b>([^<]+)</b><code>(#[0-9A-Fa-f]{6})</code>',
                              guide)
        self.assertGreater(len(swatches), 10)
        for drawn, name, said in swatches:
            self.assertEqual(drawn.upper(), said.upper(), name)
            if name.startswith("--"):
                self.assertEqual(token(css, name[2:]), said.upper(), name)
            else:
                self.assertIn(said.upper(), hexes, name)


if __name__ == "__main__":
    unittest.main()
