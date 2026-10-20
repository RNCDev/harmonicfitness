# Writing for Text-to-Speech

The listening file is read aloud, character by character, by a machine that doesn't know what formatting is for. Eleven Reader and similar apps will read a pound sign as "number sign", an asterisk as "asterisk", a slash as "slash", and they guess at numbers, ranges, and abbreviations, sometimes badly. Write exactly what should be heard, as if dictating to someone who will read it verbatim.

## The final file contains only

- Letters, spaces, and blank lines between paragraphs.
- Periods, commas, question marks, exclamation points, apostrophes, quotation marks, hyphens inside words (single-leg, left-side), em dashes used sparingly, and ellipses.
- Four-digit years are the one permitted use of digits (1776, 2026). Everything else is spelled out.
- Nothing else. No headings, bullets, numbered lists, bold, italics, tables, links, emojis, brackets, or symbols of any kind.

## Numbers

| Instead of | Write |
|---|---|
| 3 sets of 10 | three sets of ten |
| 25 lbs | twenty-five pounds |
| 0:45 or 45 sec | forty-five seconds |
| 8-10 reps | eight to ten reps |
| 45/15 | forty-five seconds on, fifteen off |
| 3-2-1 | three... two... one... |
| 4.25% | four and a quarter percent |
| $2.1B | two point one billion dollars |
| 1st, 2nd | first, second |
| 90 RPM | ninety R P M, or better, a cadence around ninety |
| RPE 7 | about a seven out of ten effort |
| 10Y yield | the ten-year Treasury yield |
| S&P 500 | the S and P five hundred |
| Q3 | the third quarter |
| 76ers | the Sixers |
| 3x | three times |
| No. 1 | number one |

Years: write them as spoken ("seventeen eighty-one", "twenty twenty-six"). The linter still permits four-digit years, but the VoiceStudio voice gets no number normalization, so spelled-out years are the safe choice. For decades write words ("the nineteen sixties"), since "1960s" is read inconsistently.

## Abbreviations and shorthand

Spell everything out: "for example" not "e.g.", "that is" not "i.e.", "versus" not "vs.", "Doctor" not "Dr.", "Street" or "Saint" not "St.", "and so on" not "etc.", "kilograms", "minutes", "seconds", "miles per hour". Tickers and acronyms the listener would say as letters are written with spaces ("N V D A" is awkward; prefer the company name, Nvidia). Acronyms said as words are fine as words (NASA becomes Nasa only if needed; usually leave common ones like NASA, NHL, NFL, which readers handle well).

## Pacing and pauses

There is no reliable pause tag in a reader app; tags like break markup are read aloud or ignored. Use punctuation:

- A paragraph break gives the longest natural pause. Start a new paragraph for each part of a segment (cue, narrative, handoff).
- An ellipsis gives a beat: "Three... two... one... switch."
- Commas give short breaths. Long sentences without commas sound rushed and breathless.
- Short sentences land cues. "Hands on the bars. Chest tall. Easy spin." is better than one long sentence.
- Box breathing can't rely on bare counts, because the voice says "two... three... four" in about a second and a half, not four seconds. Instead, fill each four-second phase with a calm phrase of about eleven words at a speed of one hundred seventy words a minute, and scale that to the measured words per minute. For example: "Breathe in slowly through your nose, letting your belly rise, two, three, four." Then: "Hold it there, shoulders soft, jaw loose, nothing moving at all." Then out, then hold again, with a different phrase each time. Then the word count matches the clock, and the build script times it correctly.

Ellipses and paragraph breaks add a little time that word counts don't capture. Keep countdowns to one per segment and don't stack ellipses, so the drift stays small.

## Orientation without timestamps

The listener can't see a clock, so the voice provides it. Open each segment with a spoken locator: "Minute nine of twenty-five." or "Round two of three." or "Halfway there." Name transitions explicitly: "Next up, in fifteen seconds, goblet squats. Grab the heavier dumbbell."

## Words that trip up readers

- Homographs: "lead" (the metal or to guide), "live" (adjective or verb), "read", "wound", "close" (near or shut), "row" (the exercise or an argument), "tear". Rephrase when context is ambiguous: "rowing machine" rather than "the row", "rest your" rather than "close your" when possible.
- Exercise names with symbols: "push-up" is fine. "T-spine" reads as "tee spine", which is fine. "90/90 hip switch" becomes "ninety-ninety hip switch".
- Names with unusual pronunciation: if a player or place name is likely to be mangled, consider adding a phonetic hint only if the reader handles it gracefully; otherwise rephrase around it ("the Flyers' captain").
- Quotes: paraphrase rather than quote. If a quote is used, keep it short and introduce it ("as he put it,") so it doesn't sound like the narrator's own opinion.

## Tone

Second person, present tense, warm, a bit wry, confident. Speak like a knowledgeable friend riding the bike next to them. Avoid hype words and repeated catchphrases. Vary praise; "Nice work" eight times in one session becomes noise.
