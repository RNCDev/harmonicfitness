"""Make HarmonicFitness's brand assets from one geometry (maintainer only).

Writes the SVGs and PNGs in assets/brand/, the site's icons in web/client/public/ and the
paths the web client draws its logo from (web/client/src/brand.ts). The wordmark is Inter Tight
SemiBold (SIL Open Font License), outlined, so nothing needs the font installed.

    curl -sSLfo InterTight.ttf "https://github.com/google/fonts/raw/main/ofl/intertight/InterTight%5Bwght%5D.ttf"
    uv run --with fonttools --with uharfbuzz --with resvg-py --with pillow \\
        python assets/brand/make.py --font InterTight.ttf
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAND = ROOT / "assets" / "brand"
PUBLIC = ROOT / "web" / "client" / "public"
CLIENT_TS = ROOT / "web" / "client" / "src" / "brand.ts"

INK, CORAL, MIST, SLATE, SLATE_LIGHT, WHITE = "#15171C", "#FF5A3C", "#F2F3F5", "#6B7080", "#9BA0AC", "#FFFFFF"

# The mark: seven fully rounded bars on a 146 x 100 box, bar 14, gap 8, heights 3 5 8 6 10 5 3;
# the tallest (the fifth) is the accent. Small sizes keep the middle five, then the middle three,
# with slightly heavier bars so they hold at 32 and 16 pixels.
HEIGHTS = [30, 50, 80, 60, 100, 50, 30]
ACCENT = 4
SETS = {"full": (range(0, 7), 14), "five": (range(1, 6), 16), "three": (range(2, 5), 18)}
TRACKING = -0.04  # em, as on the brand sheet
FITNESS_OPACITY = 0.62  # "fitness" in the site's one-colour wordmark


def bars(kind: str) -> tuple[list[tuple[float, float, float, float, bool]], tuple[float, float, float, float]]:
    """Each bar as (x, y, w, h, accent), and the view box that holds them."""
    idx, w = SETS[kind]
    out = []
    for i in idx:
        cx = i * 22 + 7  # the full mark's bar centres
        h = HEIGHTS[i] if kind == "full" else max(HEIGHTS[i], 50 if kind == "five" else 56)
        if kind == "three" and i != ACCENT:
            h = {2: 76, 3: 56}[i]
        out.append((cx - w / 2, 50 - h / 2, w, h, i == ACCENT))
    x0, x1 = out[0][0], out[-1][0] + w
    return out, (x0, 0, x1 - x0, 100)


def mark_body(kind: str, ink: str, accent: str, sx=1.0, tx=0.0, ty=0.0) -> str:
    rs, (vx, _, _, _) = bars(kind)
    parts = []
    for x, y, w, h, is_acc in rs:
        parts.append(f'<rect x="{fmt((x - vx) * sx + tx)}" y="{fmt(y * sx + ty)}" width="{fmt(w * sx)}" '
                     f'height="{fmt(h * sx)}" rx="{fmt(w * sx / 2)}" fill="{accent if is_acc else ink}"/>')
    return "".join(parts)


def mark_svg(kind: str, ink: str, accent: str) -> str:
    _, (_, _, vw, vh) = bars(kind)
    return svg(vw, vh, mark_body(kind, ink, accent), "HarmonicFitness")


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def svg(w: float, h: float, body: str, label: str | None = None) -> str:
    a11y = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(w)} {fmt(h)}" '
            f'width="{fmt(w)}" height="{fmt(h)}"{a11y}>{body}</svg>\n')


# ---- the wordmark ---------------------------------------------------------------------------

def wordmark_paths(font_path: Path):
    """("harmonic" path, "fitness" path, bounds) at 100 units to the em, baseline at y 0."""
    import uharfbuzz as hb
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    font = instantiateVariableFont(TTFont(font_path), {"wght": 600})
    upem = font["head"].unitsPerEm
    scale = 100 / upem
    glyphs = font.getGlyphSet()

    blob = hb.Blob.from_file_path(str(font_path))
    hbfont = hb.Font(hb.Face(blob))
    hbfont.set_variations({"wght": 600})
    buf = hb.Buffer()
    text = "harmonicfitness"
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
    return pens[0].getCommands(), pens[1].getCommands(), bounds.bounds


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

MARK_H = 96          # the mark's height, in hundredths of the em
MARK_GAP = 38.5      # between mark and wordmark
MARK_CENTRE = -36.5  # the mark's centre above the baseline: between x-height and ascender


def lockup(word, ink, accent, rest):
    harm, fit, (bx0, by0, bx1, by1) = word
    s = MARK_H / 100
    _, (_, _, mw, _) = bars("full")
    mw *= s
    top = min(by0, MARK_CENTRE - MARK_H / 2)
    bottom = max(by1, MARK_CENTRE + MARK_H / 2)
    dx = mw + MARK_GAP - bx0
    body = (mark_body("full", ink, accent, s, 0, MARK_CENTRE - MARK_H / 2 - top)
            + f'<path d="{shift_path(harm, dx, -top)}" fill="{ink}"/>'
            + f'<path d="{shift_path(fit, dx, -top)}" fill="{rest}"/>')
    return svg(mw + MARK_GAP + bx1 - bx0, bottom - top, body, "HarmonicFitness")


def wordmark(word, ink, rest):
    harm, fit, (bx0, by0, bx1, by1) = word
    body = (f'<path d="{shift_path(harm, -bx0, -by0)}" fill="{ink}"/>'
            f'<path d="{shift_path(fit, -bx0, -by0)}" fill="{rest}"/>')
    return svg(bx1 - bx0, by1 - by0, body, "HarmonicFitness")


def icon(size: float, kind: str, bg: str, ink: str, accent: str, radius: float, width: float) -> str:
    """A square icon: the mark `width` of the side, centred, on `bg` with corner `radius`."""
    _, (_, _, vw, vh) = bars(kind)
    s = size * width / vw
    tx, ty = (size - vw * s) / 2, (size - vh * s) / 2
    body = (f'<rect width="{fmt(size)}" height="{fmt(size)}" rx="{fmt(radius)}" fill="{bg}"/>'
            + mark_body(kind, ink, accent, s, tx, ty))
    return svg(size, size, body, "HarmonicFitness")


def png(svg_text: str, px: int) -> bytes:
    import resvg_py
    return bytes(resvg_py.svg_to_bytes(svg_string=svg_text, width=px, height=px))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--font", type=Path, required=True, help="Inter Tight's variable TTF")
    args = ap.parse_args()
    word = wordmark_paths(args.font)
    BRAND.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)

    files = {
        "mark.svg": mark_svg("full", INK, CORAL),
        "mark-reversed.svg": mark_svg("full", MIST, CORAL),
        "mark-small.svg": mark_svg("five", INK, CORAL),
        "wordmark.svg": wordmark(word, INK, SLATE),
        "wordmark-reversed.svg": wordmark(word, MIST, SLATE_LIGHT),
        "lockup.svg": lockup(word, INK, CORAL, SLATE),
        "lockup-reversed.svg": lockup(word, MIST, CORAL, SLATE_LIGHT),
        "app-icon.svg": icon(1024, "full", INK, MIST, CORAL, 235, 0.58),
        "app-icon-coral.svg": icon(1024, "full", CORAL, INK, WHITE, 235, 0.58),
        "favicon.svg": icon(32, "five", INK, MIST, CORAL, 7.5, 0.64),
    }
    for name, text in files.items():
        (BRAND / name).write_text(text)

    square = icon(1024, "full", INK, MIST, CORAL, 0, 0.56)  # full bleed: iOS rounds it itself
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
    for px, kind, width in ((16, "three", 0.66), (32, "five", 0.64), (48, "five", 0.62)):
        text = icon(px, kind, INK, MIST, CORAL, px * 0.23, width)
        images.append(Image.open(io.BytesIO(png(text, px))).convert("RGBA"))
    images[-1].save(path, format="ICO", sizes=[(i.width, i.height) for i in images],
                    append_images=images[:-1])


def _client_ts(word) -> None:
    harm, fit, (bx0, by0, bx1, by1) = word
    rs, (vx, _, vw, vh) = bars("full")
    rects = ", ".join(f"{{ x: {fmt(x - vx)}, y: {fmt(y)}, w: {w}, h: {fmt(h)}, accent: {str(a).lower()} }}"
                      for x, y, w, h, a in rs)
    CLIENT_TS.write_text(
        "// Made by assets/brand/make.py: the mark's bars and the wordmark's outlines. Don't edit by hand.\n"
        f'export const CORAL = "{CORAL}";\n'
        f"export const FITNESS_OPACITY = {FITNESS_OPACITY};\n"
        f"export const MARK = {{ width: {fmt(vw)}, height: {fmt(vh)}, bars: [{rects}] }};\n"
        f"export const WORDMARK = {{\n  width: {fmt(bx1 - bx0)},\n  height: {fmt(by1 - by0)},\n"
        f'  harmonic: "{shift_path(harm, -bx0, -by0)}",\n'
        f'  fitness: "{shift_path(fit, -bx0, -by0)}",\n}};\n')


if __name__ == "__main__":
    main()
