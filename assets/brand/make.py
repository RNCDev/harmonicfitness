"""Make HarmonicFitness's brand assets from one geometry (maintainer only).

Writes the SVGs and PNGs in assets/brand/, the site's icons in web/client/public/ and the
shapes the web client draws its logo from (web/client/src/ui/brand.ts). The wordmark is Big Shoulders
Display Bold (SIL Open Font License), outlined, so nothing needs the font installed.

    curl -sSLfo /tmp/BigShouldersDisplay.ttf \\
        "https://github.com/google/fonts/raw/main/ofl/bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf"
    uv run --no-project --with fonttools --with uharfbuzz --with resvg-py --with pillow --with coloraide \\
        python assets/brand/make.py --font /tmp/BigShouldersDisplay.ttf
"""
from __future__ import annotations

import argparse
import io
import json
from dataclasses import dataclass, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "assets" / "brand"
PUBLIC = ROOT / "web" / "client" / "public"
CLIENT_TS = ROOT / "web" / "client" / "src" / "ui" / "brand.ts"

INK, CORAL, CREAM, WHITE = "#111215", "#FF5A3C", "#EDEAE0", "#FFFFFF"

# Ember: one hue, deep coral at the foot of the meter, the brand's coral in its upper range and a pale flare at
# the top, mixed in OKLCH (as CSS color-mix does) so the middle stays bright. A segment takes the colour of its
# height; an unlit one keeps its colour at UNLIT opacity, so the H's outline never breaks.
EMBER = ((0.0, "#8C2F22"), (0.65, CORAL), (1.0, "#FFC2AE"))
UNLIT = 0.22

# The mark: an H drawn as a stereo level meter, two channels of segments and a middle bar, on a 100-unit
# square (the stems run x 16 to 84, y 10 to 90). At rest the left channel reads `L`, the right `R`, with a
# peak held at `peak`, unlit segments between. Fewer, taller segments at smaller sizes keep the gaps at
# least a pixel wide: full (10) from about 60 px, mid (6) from about 24, small (4) below.
LADDER = {
    "full": dict(n=10, gap=2.4, rx=1.0, L=8, R=6, peak=9),
    "mid": dict(n=6, gap=4.0, rx=1.5, L=5, R=3, peak=5),
    "small": dict(n=4, gap=7.0, rx=1.5, L=4, R=2, peak=4),
}
STEMS = (16.0, 68.0)  # the two channels' left edges
BAR_X = 42.0  # the middle bar's left edge
SEG_W = 16.0
TOP, HEIGHT = 10.0, 80.0

# The wordmark's H, as a letter: square-cut, at cap height, stems the font's own stem width, six segments.
STEM_RATIO = 0.135  # Big Shoulders Display Bold's H stem over its cap height
LETTER = dict(n=6, gap_ratio=0.06, inner_ratio=0.55, L=6, R=4, peak=6)
# How much taller than the capitals the meter-H stands, and where: "centre" on the caps (rising above them and
# dropping below the baseline alike) or "baseline" (standing on it, rising above the caps).
LETTER_SCALE = 1.5
LETTER_ALIGN = "centre"
H_GAP = 0.12  # extra room between the meter H and the A, over the cap height: the meter is heavier than a letter

WEIGHT = 700
TRACKING = 0.01  # em
FITNESS_OPACITY = 0.62  # "FITNESS" in the wordmark
MARK_RATIO = 1.3  # the mark's height over the cap height, in the lockup
GAP_RATIO = 0.45  # between mark and wordmark, over the cap height


@dataclass
class Seg:
    x: float
    y: float
    w: float
    h: float
    rx: float
    fill: str
    ch: str  # "L", "R" or "M" (the middle bar, always lit)
    fb: int  # its place counted from the bottom, 1 to n
    lit: bool


def ember(t: float) -> str:
    from coloraide import Color, stop
    ramp = Color.interpolate([stop(c, at) for at, c in EMBER], space="oklch", out_space="srgb")
    return ramp(t).fit("srgb").to_string(hex=True)


def ladder(n: int, gap: float, rx: float, L: int, R: int, peak: int, *, x: tuple[float, float, float],
           w: float, top: float, height: float, colour=None) -> list[Seg]:
    """The meter's segments: each channel, then the middle bar, coloured by height."""
    colour = colour or (lambda fb: ember((fb - 1) / (n - 1)))
    h = (height - gap * (n - 1)) / n
    pitch = h + gap
    centre = top + height / 2
    segs, middle = [], 0
    for i in range(n):
        y, fb = top + i * pitch, n - i
        for ch, level, pk, xx in (("L", L, 0, x[0]), ("R", R, peak, x[1])):
            segs.append(Seg(xx, y, w, h, rx, colour(fb), ch, fb, fb <= level or fb == pk))
        if abs(y + h / 2 - centre) < max(height / 6, pitch):
            segs.append(Seg(x[2], y, w, h, rx, colour(fb), "M", fb, True))
            middle += 1
    assert middle >= 1, f"a {n}-segment ladder has no middle bar"
    return segs


def mark(kind: str, colour=None) -> list[Seg]:
    """A form of the mark, moved so it fits a box from (0, 0)."""
    p = LADDER[kind]
    segs = ladder(**p, x=(STEMS[0], STEMS[1], BAR_X), w=SEG_W, top=TOP, height=HEIGHT, colour=colour)
    return [Seg(s.x - STEMS[0], s.y - TOP, s.w, s.h, s.rx, s.fill, s.ch, s.fb, s.lit) for s in segs]


MARK_W, MARK_H = STEMS[1] + SEG_W - STEMS[0], HEIGHT


def letter(cap: float, colour=None) -> tuple[list[Seg], float]:
    """The wordmark's H as a meter, at cap height from (0, 0): (segments, width)."""
    sw = cap * STEM_RATIO
    inner = sw * LETTER["inner_ratio"]
    n = LETTER["n"]
    segs = ladder(n, cap * LETTER["gap_ratio"], 0.0, LETTER["L"], LETTER["R"], LETTER["peak"],
                  x=(0.0, 2 * sw + 2 * inner, sw + inner), w=sw, top=0.0, height=cap, colour=colour)
    return segs, 3 * sw + 2 * inner


def segs_body(segs: list[Seg], s: float = 1.0, tx: float = 0.0, ty: float = 0.0) -> str:
    out = []
    for g in segs:
        rx = f' rx="{fmt(g.rx * s)}"' if g.rx else ""
        op = "" if g.lit else f' opacity="{UNLIT}"'
        out.append(f'<rect x="{fmt(g.x * s + tx)}" y="{fmt(g.y * s + ty)}" width="{fmt(g.w * s)}" '
                   f'height="{fmt(g.h * s)}"{rx} fill="{g.fill}"{op}/>')
    return "".join(out)


def mark_svg(kind: str, colour=None) -> str:
    return svg(MARK_W, MARK_H, segs_body(mark(kind, colour)), "HarmonicFitness")


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def svg(w: float, h: float, body: str, label: str | None = None) -> str:
    a11y = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" '
            f'width="{fmt(w)}" height="{fmt(h)}"{a11y}>{body}</svg>\n')


# ---- the wordmark ---------------------------------------------------------------------------

@dataclass
class Word:
    h: str  # the H's outline
    armonic: str  # the rest of HARMONIC
    fitness: str
    bounds: tuple[float, float, float, float]  # the whole word's
    h_right: float  # where the H's ink ends
    a_left: float  # where the A's ink starts
    cap: float


def wordmark_paths(font_path: Path) -> Word:
    """The word's outlines at 100 units to the em, baseline at y 0, the H kept apart from the rest."""
    import uharfbuzz as hb
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    font = instantiateVariableFont(TTFont(font_path), {"wght": WEIGHT})
    upem = font["head"].unitsPerEm
    scale = 100 / upem
    glyphs = font.getGlyphSet()
    cap = font["OS/2"].sCapHeight * scale

    blob = hb.Blob.from_file_path(str(font_path))
    hbfont = hb.Font(hb.Face(blob))
    hbfont.set_variations({"wght": WEIGHT})
    buf = hb.Buffer()
    buf.add_str("HARMONICFITNESS")
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": False})
    names = [font.getGlyphName(i.codepoint) for i in buf.glyph_infos]

    pens = {k: SVGPathPen(glyphs) for k in ("h", "armonic", "fitness")}
    bounds = BoundsPen(glyphs)
    edges: dict[int, tuple] = {}
    x = 0.0
    for n, (name, pos) in enumerate(zip(names, buf.glyph_positions)):
        cluster = buf.glyph_infos[n].cluster
        t = (scale, 0, 0, -scale, (x + pos.x_offset) * scale, -pos.y_offset * scale)
        key = "h" if cluster == 0 else "armonic" if cluster < 8 else "fitness"
        glyphs[name].draw(TransformPen(pens[key], t))
        glyphs[name].draw(TransformPen(bounds, t))
        if cluster < 2:
            one = BoundsPen(glyphs)
            glyphs[name].draw(TransformPen(one, t))
            edges[cluster] = one.bounds
        x += pos.x_advance + (TRACKING * upem if n < len(names) - 1 else 0)
    return Word(pens["h"].getCommands(), pens["armonic"].getCommands(), pens["fitness"].getCommands(),
                bounds.bounds, edges[0][2], edges[1][0], cap)


def shift_path(d: str, dx: float, dy: float) -> str:
    """Moves an absolute SVG path (fontTools writes absolute M L H V Q C Z) by dx, dy."""
    import re
    out, nums, cmd = [], [], ""

    def flush():
        if cmd == "H":
            moved = [v + dx for v in nums]
        elif cmd == "V":
            moved = [v + dy for v in nums]
        else:
            moved = [v + (dx if i % 2 == 0 else dy) for i, v in enumerate(nums)]
        out.append(cmd + " ".join(fmt(v) for v in moved))

    for tok in re.findall(r"[MLHVQCZ]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", d):
        if tok in "MLHVQCZ":
            if nums:
                flush()
                nums = []
            cmd = tok
            if tok == "Z":
                out.append("Z")
        else:
            nums.append(float(tok))
    if nums:
        flush()
    return "".join(out)


def word_body(word: Word, color: str, dx: float, dy: float, with_h: bool = True) -> str:
    harm = (word.h if with_h else "") + word.armonic
    return (f'<path d="{shift_path(harm, dx, dy)}" fill="{color}"/>'
            f'<path d="{shift_path(word.fitness, dx, dy)}" fill="{color}" opacity="{FITNESS_OPACITY}"/>')


def word_h_layout(word: Word, scale: float = LETTER_SCALE, align: str = LETTER_ALIGN):
    """The wordmark with the meter for its H, `scale` cap heights tall:
    (letter segments, letter width, dx for the rest, total width, letter top, top, bottom), y from the baseline."""
    segs, lw = letter(word.cap * scale)
    # the font's own space before the A, a little more for a bigger H, and H_GAP more for the meter's weight
    gap = (word.a_left - word.h_right) * (1 + (scale - 1) / 2) + word.cap * H_GAP
    dx = lw + gap - word.a_left
    lh = word.cap * scale
    ltop = -word.cap / 2 - lh / 2 if align == "centre" else -lh
    _, by0, _, by1 = word.bounds
    return segs, lw, dx, word.bounds[2] + dx, ltop, min(by0, ltop), max(by1, ltop + lh)


# ---- lockups and icons ----------------------------------------------------------------------

def lockup(word: Word, color: str) -> str:
    """Mark and wordmark: the mark MARK_RATIO cap heights tall, centred on the caps, GAP_RATIO away."""
    bx0, by0, bx1, by1 = word.bounds
    cap = word.cap
    s = cap * MARK_RATIO / MARK_H
    mw, mh = MARK_W * s, cap * MARK_RATIO
    centre = -cap / 2
    top = min(by0, centre - mh / 2)
    bottom = max(by1, centre + mh / 2)
    dx = mw + cap * GAP_RATIO - bx0
    body = segs_body(mark("full"), s, 0, centre - mh / 2 - top) + word_body(word, color, dx, -top)
    return svg(mw + cap * GAP_RATIO + bx1 - bx0, bottom - top, body, "HarmonicFitness")


def wordmark(word: Word, color: str) -> str:
    bx0, by0, bx1, by1 = word.bounds
    return svg(bx1 - bx0, by1 - by0, word_body(word, color, -bx0, -by0), "HarmonicFitness")


def wordmark_h(word: Word, color: str, scale: float = LETTER_SCALE, align: str = LETTER_ALIGN) -> str:
    """The wordmark with its H drawn as the meter."""
    segs, _, dx, width, ltop, top, bottom = word_h_layout(word, scale, align)
    body = segs_body(segs, 1, 0, ltop - top) + word_body(word, color, dx, -top, with_h=False)
    return svg(width, bottom - top, body, "HarmonicFitness")


def icon(size: float, kind: str, bg: str, radius: float, fill: float, colour=None) -> str:
    """A square icon: the mark `fill` of the side tall, centred, on `bg` with corner `radius`."""
    s = size * fill / MARK_H
    tx, ty = (size - MARK_W * s) / 2, (size - MARK_H * s) / 2
    body = (f'<rect width="{fmt(size)}" height="{fmt(size)}" rx="{fmt(radius)}" fill="{bg}"/>'
            + segs_body(mark(kind, colour), s, tx, ty))
    return svg(size, size, body, "HarmonicFitness")


def png(svg_text: str, px: int) -> bytes:
    import resvg_py
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=px, height=px))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", type=Path, required=True, help="Big Shoulders Display's variable TTF")
    args = ap.parse_args()
    word = wordmark_paths(args.font)
    BRAND.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    ink = lambda fb: INK  # noqa: E731  the one-colour ladder, on coral

    files = {
        "mark.svg": mark_svg("full"),
        "mark-mid.svg": mark_svg("mid"),
        "mark-small.svg": mark_svg("small"),
        "wordmark.svg": wordmark(word, INK),
        "wordmark-reversed.svg": wordmark(word, CREAM),
        "wordmark-h.svg": wordmark_h(word, INK),
        "wordmark-h-reversed.svg": wordmark_h(word, CREAM),
        "lockup.svg": lockup(word, INK),
        "lockup-reversed.svg": lockup(word, CREAM),
        "app-icon.svg": icon(1024, "full", INK, 235, 0.58),
        "app-icon-coral.svg": icon(1024, "full", CORAL, 235, 0.58, ink),
        "favicon.svg": icon(32, "small", INK, 7.5, 0.74),
    }
    for name, text in files.items():
        (BRAND / name).write_text(text)

    square = icon(1024, "full", INK, 0, 0.56)  # full bleed: iOS rounds it itself
    (BRAND / "app-icon-1024.png").write_bytes(png(files["app-icon.svg"], 1024))
    (BRAND / "app-icon-coral-1024.png").write_bytes(png(files["app-icon-coral.svg"], 1024))
    for name in ("lockup", "lockup-reversed", "wordmark-h", "wordmark-h-reversed"):
        (BRAND / f"{name}.png").write_bytes(_png_wide(files[f"{name}.svg"], 1200))

    (PUBLIC / "favicon.svg").write_text(files["favicon.svg"])
    (PUBLIC / "apple-touch-icon.png").write_bytes(png(square, 180))
    (PUBLIC / "podcast-cover.png").write_bytes(png(square, 1400))   # the private podcast feed's artwork
    _ico(PUBLIC / "favicon.ico")
    (BRAND / "favicon.ico").write_bytes((PUBLIC / "favicon.ico").read_bytes())

    _client_ts(word)
    print("wrote", len(files) + 10, "files")


def _png_wide(svg_text: str, px: int) -> bytes:
    import resvg_py
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=px))


def _ico(path: Path) -> None:
    from PIL import Image
    images = []
    for px, kind in ((16, "small"), (32, "small"), (48, "mid")):
        text = icon(px, kind, INK, px * 0.23, 0.74)
        images.append(Image.open(io.BytesIO(png(text, px))).convert("RGBA"))
    images[-1].save(path, format="ICO", sizes=[(i.width, i.height) for i in images],
                    append_images=images[:-1])


def _client_ts(word: Word) -> None:
    def shape(segs):
        return [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(g).items()} for g in segs]

    forms = {k: {"width": MARK_W, "height": MARK_H, "segments": shape(mark(k))} for k in LADDER}
    bx0, by0, bx1, by1 = word.bounds
    segs, lw, dx, width, ltop, top, bottom = word_h_layout(word)
    CLIENT_TS.write_text(
        "// Made by assets/brand/make.py: the mark's segments and the wordmark's outlines. Don't edit by hand.\n"
        "// A segment's `ch` is its channel (L, R, or M for the middle bar, always lit) and `fb` its place\n"
        "// counted from the bottom; `lit` is the still mark's reading.\n"
        f'export const CORAL = "{CORAL}";\n'
        f"export const FITNESS_OPACITY = {FITNESS_OPACITY};\n"
        f"export const UNLIT = {UNLIT};\n"
        "export type Segment = { x: number; y: number; w: number; h: number; rx: number; fill: string; "
        'ch: "L" | "R" | "M"; fb: number; lit: boolean };\n'
        "export type Form = { width: number; height: number; segments: Segment[] };\n"
        f"export const MARK: Record<\"full\" | \"mid\" | \"small\", Form> = {json.dumps(forms)};\n"
        f"export const WORDMARK = {{\n  width: {fmt(bx1 - bx0)},\n  height: {fmt(by1 - by0)},\n"
        f'  harmonic: "{shift_path(word.h + word.armonic, -bx0, -by0)}",\n'
        f'  fitness: "{shift_path(word.fitness, -bx0, -by0)}",\n}};\n'
        f"export const WORDMARK_H = {{\n  width: {fmt(width)},\n  height: {fmt(bottom - top)},\n"
        f"  letter: {json.dumps({'width': round(lw, 2), 'height': round(word.cap, 2), 'segments': shape(segs)})},\n"
        f"  letterY: {fmt(ltop - top)},\n"
        f'  armonic: "{shift_path(word.armonic, dx, -top)}",\n'
        f'  fitness: "{shift_path(word.fitness, dx, -top)}",\n}};\n')


if __name__ == "__main__":
    main()
