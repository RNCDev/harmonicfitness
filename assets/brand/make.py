"""Make HarmonicFitness's brand assets from one geometry (maintainer only).

Writes the SVGs and PNGs in assets/brand/, the site's icons in web/client/public/ and the
paths the web client draws its logo from (web/client/src/brand.ts). The wordmark is Big Shoulders
Display Bold (SIL Open Font License), outlined, so nothing needs the font installed.

    curl -sSLfo /tmp/BigShouldersDisplay.ttf \\
        "https://github.com/google/fonts/raw/main/ofl/bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf"
    uv run --no-project --with fonttools --with uharfbuzz --with resvg-py --with pillow \\
        python assets/brand/make.py --font /tmp/BigShouldersDisplay.ttf
"""
from __future__ import annotations

import argparse
import io
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "assets" / "brand"
PUBLIC = ROOT / "web" / "client" / "public"
CLIENT_TS = ROOT / "web" / "client" / "src" / "brand.ts"

INK, CORAL, CREAM, WHITE = "#111215", "#FF5A3C", "#EDEAE0", "#FFFFFF"

# The mark: one line, a burst of sound. Around a centre at x 100 the line is a cosine of wavelength
# lam whose amplitude falls away as a Gaussian of width env, drawn from 100 - X to 100 + X with a
# stroke of sw, all on a 100-unit scale. The full form has seven lobes you can see; below about
# 60 px the mid form keeps five, and below about 40 the small form keeps three, on a wider cut.
TRACE = {
    "full": dict(lam=40, env=42, amp=44, X=90, sw=8),
    "mid": dict(lam=50, env=40, amp=42, X=62.5, sw=11),
    "small": dict(lam=60, env=55, amp=42, X=45, sw=14),
}
STEP = 0.5
WEIGHT = 700
TRACKING = 0.01  # em
FITNESS_OPACITY = 0.62  # "FITNESS" in the wordmark
MARK_RATIO = 1.3  # the mark's height over the cap height, in the lockup
GAP_RATIO = 0.55  # between mark and wordmark, over the cap height


def trace(kind: str) -> tuple[list[tuple[float, float]], float, float, float]:
    """The line's points, moved so its stroke fits a box from (0, 0): (points, width, height, stroke)."""
    p = TRACE[kind]
    x0, x1 = 100 - p["X"], 100 + p["X"]
    pts, x = [], x0
    while x <= x1 + 1e-9:
        e = p["amp"] * math.exp(-((x - 100) / p["env"]) ** 2)
        pts.append((x, 50 - e * math.cos(2 * math.pi * (x - 100) / p["lam"])))
        x += STEP
    top = min(y for _, y in pts) - p["sw"] / 2
    bottom = max(y for _, y in pts) + p["sw"] / 2
    return [(x - x0, y - top) for x, y in pts], x1 - x0, bottom - top, p["sw"]


def mark_body(kind: str, color: str, s: float = 1.0, tx: float = 0.0, ty: float = 0.0) -> str:
    pts, _, _, sw = trace(kind)
    d = "M" + " L".join(f"{fmt(x * s + tx)} {fmt(y * s + ty)}" for x, y in pts)
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{fmt(sw * s)}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def mark_svg(kind: str, color: str) -> str:
    _, vw, vh, _ = trace(kind)
    return svg(vw, vh, mark_body(kind, color), "HarmonicFitness")


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def svg(w: float, h: float, body: str, label: str | None = None) -> str:
    a11y = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" '
            f'width="{fmt(w)}" height="{fmt(h)}"{a11y}>{body}</svg>\n')


# ---- the wordmark ---------------------------------------------------------------------------

def wordmark_paths(font_path: Path):
    """("HARMONIC" path, "FITNESS" path, bounds, cap height) at 100 units to the em, baseline at y 0."""
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
    text = "HARMONICFITNESS"
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": False})
    names = [font.getGlyphName(i.codepoint) for i in buf.glyph_infos]

    pens = [SVGPathPen(glyphs), SVGPathPen(glyphs)]
    bounds = BoundsPen(glyphs)
    x = 0.0
    for n, (name, pos) in enumerate(zip(names, buf.glyph_positions)):
        cluster = buf.glyph_infos[n].cluster
        t = (scale, 0, 0, -scale, (x + pos.x_offset) * scale, -pos.y_offset * scale)
        glyphs[name].draw(TransformPen(pens[0 if cluster < 8 else 1], t))
        glyphs[name].draw(TransformPen(bounds, t))
        x += pos.x_advance + (TRACKING * upem if n < len(names) - 1 else 0)
    return pens[0].getCommands(), pens[1].getCommands(), bounds.bounds, cap


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


# ---- lockups and icons ----------------------------------------------------------------------

def lockup(word, color: str, mark: str = CORAL) -> str:
    """Mark and wordmark: the mark MARK_RATIO cap heights tall, centred on the caps, GAP_RATIO away."""
    harm, fit, (bx0, by0, bx1, by1), cap = word
    _, mw, mh, _ = trace("full")
    s = cap * MARK_RATIO / mh
    mw, mh = mw * s, cap * MARK_RATIO
    centre = -cap / 2
    top = min(by0, centre - mh / 2)
    bottom = max(by1, centre + mh / 2)
    dx = mw + cap * GAP_RATIO - bx0
    body = (mark_body("full", mark, s, 0, centre - mh / 2 - top)
            + f'<path d="{shift_path(harm, dx, -top)}" fill="{color}"/>'
            + f'<path d="{shift_path(fit, dx, -top)}" fill="{color}" opacity="{FITNESS_OPACITY}"/>')
    return svg(mw + cap * GAP_RATIO + bx1 - bx0, bottom - top, body, "HarmonicFitness")


def wordmark(word, color: str) -> str:
    harm, fit, (bx0, by0, bx1, by1), _ = word
    body = (f'<path d="{shift_path(harm, -bx0, -by0)}" fill="{color}"/>'
            f'<path d="{shift_path(fit, -bx0, -by0)}" fill="{color}" opacity="{FITNESS_OPACITY}"/>')
    return svg(bx1 - bx0, by1 - by0, body, "HarmonicFitness")


def icon(size: float, kind: str, bg: str, color: str, radius: float, width: float) -> str:
    """A square icon: the mark `width` of the side wide, centred, on `bg` with corner `radius`."""
    _, vw, vh, _ = trace(kind)
    s = size * width / vw
    tx, ty = (size - vw * s) / 2, (size - vh * s) / 2
    body = (f'<rect width="{fmt(size)}" height="{fmt(size)}" rx="{fmt(radius)}" fill="{bg}"/>'
            + mark_body(kind, color, s, tx, ty))
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

    files = {
        "mark.svg": mark_svg("full", CORAL),
        "mark-small.svg": mark_svg("small", CORAL),
        "wordmark.svg": wordmark(word, INK),
        "wordmark-reversed.svg": wordmark(word, CREAM),
        "lockup.svg": lockup(word, INK),
        "lockup-reversed.svg": lockup(word, CREAM),
        "app-icon.svg": icon(1024, "full", INK, CORAL, 235, 0.74),
        "app-icon-coral.svg": icon(1024, "full", CORAL, WHITE, 235, 0.74),
        "favicon.svg": icon(32, "small", INK, CORAL, 7.5, 0.78),
    }
    for name, text in files.items():
        (BRAND / name).write_text(text)

    square = icon(1024, "full", INK, CORAL, 0, 0.72)  # full bleed: iOS rounds it itself
    (BRAND / "app-icon-1024.png").write_bytes(png(files["app-icon.svg"], 1024))
    (BRAND / "app-icon-coral-1024.png").write_bytes(png(files["app-icon-coral.svg"], 1024))
    (BRAND / "lockup.png").write_bytes(_png_wide(files["lockup.svg"], 1200))
    (BRAND / "lockup-reversed.png").write_bytes(_png_wide(files["lockup-reversed.svg"], 1200))

    (PUBLIC / "favicon.svg").write_text(files["favicon.svg"])
    (PUBLIC / "apple-touch-icon.png").write_bytes(png(square, 180))
    _ico(PUBLIC / "favicon.ico")
    (BRAND / "favicon.ico").write_bytes((PUBLIC / "favicon.ico").read_bytes())

    _client_ts(word)
    print("wrote", len(files) + 7, "files")


def _png_wide(svg_text: str, px: int) -> bytes:
    import resvg_py
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=px))


def _ico(path: Path) -> None:
    from PIL import Image
    images = []
    for px, kind in ((16, "small"), (32, "small"), (48, "mid")):
        text = icon(px, kind, INK, CORAL, px * 0.23, 0.78)
        images.append(Image.open(io.BytesIO(png(text, px))).convert("RGBA"))
    images[-1].save(path, format="ICO", sizes=[(i.width, i.height) for i in images],
                    append_images=images[:-1])


def _client_ts(word) -> None:
    harm, fit, (bx0, by0, bx1, by1), _ = word
    pts, vw, vh, sw = trace("full")
    d = "M" + " L".join(f"{fmt(x)} {fmt(y)}" for x, y in pts)
    CLIENT_TS.write_text(
        "// Made by assets/brand/make.py: the mark's line and the wordmark's outlines. Don't edit by hand.\n"
        f'export const CORAL = "{CORAL}";\n'
        f"export const FITNESS_OPACITY = {FITNESS_OPACITY};\n"
        f'export const MARK = {{ width: {fmt(vw)}, height: {fmt(vh)}, stroke: {fmt(sw)}, d: "{d}" }};\n'
        f"export const WORDMARK = {{\n  width: {fmt(bx1 - bx0)},\n  height: {fmt(by1 - by0)},\n"
        f'  harmonic: "{shift_path(harm, -bx0, -by0)}",\n'
        f'  fitness: "{shift_path(fit, -bx0, -by0)}",\n}};\n')


if __name__ == "__main__":
    main()
