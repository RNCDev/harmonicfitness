# HarmonicFitness brand

The mark is an H drawn as a stereo level meter: two channels of segments and a middle bar, coloured Ember, from deep coral at the foot to a pale flare at the top. It is the app's sound and the app's name in one shape. The wordmark is HARMONICFITNESS in one word, set in Big Shoulders Display, the face the web app's headings use, with FITNESS in a lighter tone. The wordmark in type is the main logo; the meter stands apart as the mark and the app icon.

## Files

| File | Use |
|---|---|
| `lockup.svg`, `lockup.png` | Mark and wordmark, on light backgrounds |
| `lockup-reversed.svg`, `lockup-reversed.png` | The same, on dark backgrounds |
| `wordmark.svg`, `wordmark-reversed.svg` | The main logo: the wordmark in type, on light and on dark |
| `wordmark-h.svg`, `wordmark-h.png`, `-reversed` | Retired: the wordmark with the meter as its H, kept until a new logo replaces it |
| `mark.svg` | The mark alone, from about 60 px: ten segments a channel |
| `mark-mid.svg` | The mark from about 24 to 60 px: six segments |
| `mark-small.svg` | The mark below about 24 px: four segments |
| `app-icon.svg`, `app-icon-1024.png` | App icon: ink, the meter in Ember |
| `app-icon-coral.svg`, `app-icon-coral-1024.png` | App icon on coral, the meter in ink |
| `favicon.svg`, `favicon.ico` | Browser icons (16, 32 and 48 px in the ICO; 16 and 32 use the small form, 48 the mid) |

The web client's own copies are in `web/client/public/` (favicon and Apple touch icon) and `web/client/src/ui/brand.ts` (the segments of each form and the wordmark's outlines, which `Mark.tsx` draws).

## Colours

| Name | Hex | Use |
|---|---|---|
| Coral | `#FF5A3C` | The brand colour; Ember's upper range, and in the app the request's fixed words and a small mark on what's chosen in Settings |
| Ember low | `#8C2F22` | The foot of the meter |
| Ember high | `#FFC2AE` | The top of the meter |
| Ink | `#111215` | Dark backgrounds; the words on light; the meter on coral |
| Cream | `#EDEAE0` | The words on dark |

Ember runs from Ember low (at 0) through Coral (at 0.65) to Ember high (at 1), mixed in OKLCH. Each segment takes the colour of its height. FITNESS is the words' colour at 62 % opacity.

## Construction

On a 100-unit square the two channels are 16 units wide, at x 16 and 68, from y 10 to 90; the middle bar is the same width at x 42, made of the segments nearest the centre. The still mark reads like a meter mid-song: the left channel lit to 8 of 10, the right to 6 with its peak held at 9 and an unlit segment between. Unlit segments keep their colour at 22 % opacity, so the H's outline never breaks.

Smaller forms use fewer, taller segments, so the gaps stay at least a pixel wide: the full form has 10 a channel (gap 2.4, from about 60 px), the mid 6 (gap 4), the small 4 (gap 7, below about 24 px).

In the retired wordmark-h files the meter is the H itself: square-cut, 1.5 cap heights tall and centred on the caps (rising above them and dropping below the baseline alike), its stems 13.5 % of its height (the font's own stem ratio), six segments, and the font's space before the A widened by a quarter. Centred, it reads as an emblem the word passes through: balanced, not climbing. `LETTER_SCALE` and `LETTER_ALIGN` in `make.py` set its size and place. It read poorly at header size (the pale top of the H fades into a dark ground, and the word reads as ARMONICFITNESS), so the header draws the wordmark in type.

The wordmark is Big Shoulders Display Bold (weight 700, SIL Open Font License 1.1), tracked +0.01 em, outlined, so nothing needs the font installed. In the lockup the mark is 1.3 cap heights tall, centred on the caps, 0.45 cap heights from the wordmark.

## Motion

In the web app the meter moves only where there's sound: beside a workout's player while it plays. The levels are lively but made up, two slow waves and a quick one per channel, with peaks that fall back slowly. At rest, and whenever the system asks for reduced motion, it is the still mark.

## Remaking them

Every file here, and the client's copies, come from `make.py`. Change the geometry there, never in the SVGs:

    curl -sSLfo /tmp/BigShouldersDisplay.ttf "https://github.com/google/fonts/raw/main/ofl/bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf"
    uv run --no-project --with fonttools --with uharfbuzz --with resvg-py --with pillow --with coloraide \
        python assets/brand/make.py --font /tmp/BigShouldersDisplay.ttf
