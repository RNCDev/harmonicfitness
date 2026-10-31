# HarmonicFitness brand

The mark is one line, a burst of sound, in coral: the coach's voice arriving in your ear. The wordmark is HARMONICFITNESS in one word, set in Big Shoulders Display, the face the web app's headings use, with FITNESS in a lighter tone.

## Files

| File | Use |
|---|---|
| `lockup.svg`, `lockup.png` | Mark and wordmark, on light backgrounds |
| `lockup-reversed.svg`, `lockup-reversed.png` | The same, on dark backgrounds |
| `mark.svg` | The mark alone; coral on light and on dark alike |
| `mark-small.svg` | The mark below about 40 px: three lobes on a wider line |
| `wordmark.svg`, `wordmark-reversed.svg` | The wordmark alone |
| `app-icon.svg`, `app-icon-1024.png` | App icon: ink, the line in coral |
| `app-icon-coral.svg`, `app-icon-coral-1024.png` | App icon on coral, the line in white |
| `favicon.svg`, `favicon.ico` | Browser icons (16, 32 and 48 px in the ICO; 16 and 32 keep three lobes, 48 five) |

The web client's own copies are in `web/client/public/` (favicon and Apple touch icon) and `web/client/src/brand.ts` (the line, and the paths `Mark.tsx` draws in the text colour).

## Colours

| Name | Hex | Use |
|---|---|---|
| Coral | `#FF5A3C` | The mark, and the request's fixed words in the app |
| Ink | `#111215` | Dark backgrounds; the words on light |
| Cream | `#EDEAE0` | The words on dark |
| White | `#FFFFFF` | The line on coral |

FITNESS is the words' colour at 62 % opacity.

## Construction

The line is a cosine of wavelength 40 whose amplitude, 44 at the centre, falls away as a Gaussian of width 42, drawn 90 either side of the centre with a stroke of 8, all on a 100-unit scale: seven lobes you can see, the loudest in the middle. Below about 60 px the mid form keeps five lobes (wavelength 50, width 40, stroke 11) and below about 40 the small form keeps three (wavelength 60, width 55, stroke 14).

The wordmark is Big Shoulders Display Bold (weight 700, SIL Open Font License 1.1), tracked +0.01 em, outlined, so nothing needs the font installed. In the lockup the mark is 1.3 cap heights tall, centred on the caps, 0.55 cap heights from the wordmark.

## Remaking them

Every file here, and the client's copies, come from `make.py`. Change the geometry there, never in the SVGs:

    curl -sSLfo /tmp/BigShouldersDisplay.ttf "https://github.com/google/fonts/raw/main/ofl/bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf"
    uv run --no-project --with fonttools --with uharfbuzz --with resvg-py --with pillow \
        python assets/brand/make.py --font /tmp/BigShouldersDisplay.ttf
