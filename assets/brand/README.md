# HarmonicFitness brand

The mark is seven sound bars, the tallest in coral: a voice in your ear, keeping time. The wordmark is "harmonicfitness" in one word, "fitness" in a lighter tone.

## Files

| File | Use |
|---|---|
| `lockup.svg`, `lockup.png` | Mark and wordmark, on light backgrounds |
| `lockup-reversed.svg`, `lockup-reversed.png` | The same, on dark backgrounds |
| `mark.svg`, `mark-reversed.svg` | The mark alone |
| `mark-small.svg` | The mark below about 40 px: the middle five bars, a little heavier |
| `wordmark.svg`, `wordmark-reversed.svg` | The wordmark alone |
| `app-icon.svg`, `app-icon-1024.png` | App icon: ink, light bars, coral accent |
| `app-icon-coral.svg`, `app-icon-coral-1024.png` | App icon on coral |
| `favicon.svg`, `favicon.ico` | Browser icons (16, 32 and 48 px in the ICO; 16 keeps the middle three bars) |

The web client's own copies are in `web/client/public/` (favicon and Apple touch icon) and `web/client/src/brand.ts` (the paths `Mark.tsx` draws in the text colour).

## Colours

| Name | Hex | Use |
|---|---|---|
| Ink | `#15171C` | Bars, "harmonic", dark backgrounds |
| Coral | `#FF5A3C` | The accent bar only |
| Slate | `#6B7080` | "fitness" on light |
| Slate light | `#9BA0AC` | "fitness" on dark |
| Mist | `#F2F3F5` | Light backgrounds, bars on dark |

## Construction

The mark sits on a 146 by 100 box: bars 14 wide with gaps of 8, fully rounded, heights 3, 5, 8, 6, 10, 5, 3 (tenths of the box), the fifth in coral. In the lockup the mark is 0.96 of the type size tall, 0.385 from the wordmark, and centred 0.365 above the baseline.

The wordmark is Inter Tight SemiBold (SIL Open Font License 1.1), tracked -0.04 em, outlined, so nothing needs the font installed.

## Remaking them

Every file here, and the client's copies, come from `make.py`. Change the geometry there, never in the SVGs:

    curl -sSLfo /tmp/InterTight.ttf "https://github.com/google/fonts/raw/main/ofl/intertight/InterTight%5Bwght%5D.ttf"
    uv run --no-project --with fonttools --with uharfbuzz --with resvg-py --with pillow \
        python assets/brand/make.py --font /tmp/InterTight.ttf
