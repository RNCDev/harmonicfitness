# Writing for Text-to-Speech

The script is read aloud by the voice's engine (Chatterbox or Qwen3-TTS, through `tools/render.py`) exactly as written. Nothing expands numbers or abbreviations first, and the engine guesses at symbols, so a pound sign, slash or digit can come out as noise or a wrong word. Write exactly what should be heard, as if dictating to someone who will read it verbatim. `tools/tts_build.py` enforces the mechanical rules below.

## The final file contains only

- Letters, spaces, and blank lines between paragraphs.
- Periods, commas, question marks, exclamation points, apostrophes, quotation marks, hyphens inside words (single-leg, left-side), em dashes used sparingly, and ellipses.
- Pause markers: `[pause 3s]` (see Pacing), the bell marker `[chime]` and the hold marker `[hold]` (see Orientation).
- Nothing else. No digits, headings, bullets, numbered lists, bold, italics, tables, links, emojis, brackets other than pause, chime and hold markers, or symbols of any kind.

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
| 90 RPM | a cadence around ninety |
| RPE 7 | about a seven out of ten effort |
| 10Y yield | the ten-year Treasury yield |
| S&P 500 | the S and P five hundred |
| Q3 | the third quarter |
| 76ers | the Sixers |
| 3x | three times |
| No. 1 | number one |

Years are written as spoken ("seventeen eighty-one", "twenty twenty-six"), and decades in words ("the nineteen sixties").

## Abbreviations and shorthand

Spell everything out: "for example" not "e.g.", "that is" not "i.e.", "versus" not "vs.", "Doctor" not "Dr.", "Street" or "Saint" not "St.", "and so on" not "etc.", "kilograms", "minutes", "seconds", "miles per hour". Prefer company names to tickers (Nvidia, not N V D A). Common acronyms said as words or letters (NASA, NHL, NFL) can stay; if one comes out wrong in a render, spell it with spaces (N H L) or rephrase.

## Pacing and pauses

- A paragraph break gives a pause of at least a third of a second, and the render spreads the segment's spare time over its breaks (up to about two seconds each). Start a new paragraph for each part of a segment (cue, narrative, handoff).
- Keep each paragraph under about twenty seconds spoken, about fifty words. Long clips are where engines drift, rush or glitch, and short paragraphs give the voice natural breaths. The lint flags paragraphs over twenty-two seconds.
- `[pause 3s]` inserts exactly that much silence (also `[pause 500ms]`; at most ten seconds). Use it where the listener needs real time, such as box breathing or getting into position, not as decoration.
- An ellipsis gives a short beat, at most half a second: "Three... two... one... switch." Keep countdowns to one per segment.
- Commas give short breaths. Long sentences without commas sound rushed.
- Short sentences land cues. "Hands on the bars. Chest tall. Easy spin." is better than one long sentence.
- Box breathing: give each four-second phase a short cue and a pause. A one-word cue like "Hold." takes about a second, and a five-word cue about two, so: "Breathe in through your nose. [pause 2s] Hold. [pause 3s] Out through your mouth. [pause 2s] Hold. [pause 3s]" Pauses are exact; the cues run a little shorter with some voices. Vary the cue wording between rounds.

The lint predicts each segment's spoken length for the chosen voice, pauses included, so timing doesn't need to be counted by hand. It's an estimate from the voice's measured rate, usually within a few percent; a segment with time to spare ends a little early instead of going quiet, one that runs a little long is paid back from the next ones' spare time, and only the whole workout is held to plan, within three percent.

## Orientation without timestamps

The listener can't see a clock, so the voice provides it. A soft chime opens every segment after the first (`tools/render.py` adds it, and the lint counts its six tenths of a second), so the locator lands right after the bell. Open each segment with a spoken locator: "Minute nine of twenty-five." or "Round two of three." or "Halfway there." Name transitions explicitly: "Next up, in fifteen seconds, goblet squats. Grab the heavier dumbbell."

Inside a segment, `[chime]` rings the same bell at that point, for the changes in an interval (work starts, rest starts) that the clock would otherwise give: "At the bell, go. [chime] Push the floor away." The lint counts its time. Keep the spoken cue too; the bell confirms it, it doesn't replace it. A segment normally ends early when its speech runs out, so timed work would shrink; put `[hold]` where the listener works in silence, and the segment keeps its full length, its spare time silent at the hold: "At the bell, go. [chime] Drive the knees. [hold] Last five. [chime] Easy now." A held segment is never flagged short, so a thirty-second effort needs only its cues, not thirty seconds of talk. Use it in timed work and rests only, never to pad a story. The finished MP3 ends with a three-note rising tone, so silence after it means the workout is over.

The lint warns (without blocking) when a segment opens without a locator, has more than one countdown, or when a short praise line ("Good.", "Nice work.") turns up three or more times; with `--strict` the warnings count as issues.

## Words that trip up the voice

- Homographs: "lead" (the metal or to guide), "live" (adjective or verb), "read", "wound", "close" (near or shut), "row" (the exercise or an argument), "tear". Rephrase when context is ambiguous: "rowing machine" rather than "the row", "rest your" rather than "close your" when possible.
- Exercise names with symbols: "push-up" is fine. "T-spine" reads as "tee spine", which is fine. "90/90 hip switch" becomes "ninety-ninety hip switch".
- Names likely to be mangled: rephrase around them ("the Flyers' captain") rather than adding phonetic spellings.
- Quotes: paraphrase rather than quote. If a quote is used, keep it short and introduce it ("as he put it,") so it doesn't sound like the narrator's own opinion.

## Coaching voice

The engines copy the delivery the text suggests: long, smooth sentences come out like a radio announcer reading copy. Cues should sound like a coach standing beside the listener.

- Cue sentences are short: two to five words, a verb first. "Hands under the shoulders. Brace. Lower slow. Push."
- Mid-set check-ins, one or two in each long working set: "Halfway there.", "Breathe out on the push.", "Last few. Keep the shape.", "Good. Stay with it."
- Talk to the listener, not about the movement: "Keep your ribs down", not "The ribs should stay down."
- Save the long sentences for the stories, where an even, conversational read is right.
- Exclamation points sparingly, at most one or two a session; they can make the voice shout.

Before: "Keep the body in one straight line as you lower your chest toward the bench and then push it away."
After: "Body in one line. Lower slow. Now push the bench away."

## Tone

Tone and humor come from the Narrator section of `me/profile.md`. Whatever the tone, avoid hype words and repeated catchphrases, and vary praise; "Nice work" eight times in one session becomes noise.
