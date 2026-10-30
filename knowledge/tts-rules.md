# What a voice can read

The coach's voice reads the script exactly as written: a local one (Pocket TTS on this computer) or a web one (the coach's own voice service), through `tools/render.py`. Nothing expands numbers or abbreviations first, and a symbol can come out as noise or a wrong word, so write exactly what should be heard. The build's lint (`tools/tts_build.py`) checks the mechanical points below. How the script should sound is `knowledge/script.md`'s, not a rule here.

## The draft

- The first line is `movements: <every movement the script uses, by its name in the brief's menu, comma separated>`. It is never spoken.
- Then come the `@@ <seconds> | <label>` segments, adding up to exactly the session's seconds. You choose them: a segment can be one set, a round, an interval block or the whole warm-up, as long as it holds the time its work, rest and talk need.
- Draft to roughly the coach's measured words a minute (the brief gives it). The lint predicts each segment's spoken length. A segment with time to spare ends a little early, one that runs long is paid back by the next ones, and only the total must land within three percent of plan.

## Characters

- Letters, spaces, and blank lines between paragraphs.
- Periods, commas, question marks, exclamation points (one or two a session; they can make the voice shout), apostrophes, quotation marks, hyphens inside words (single-leg), and em dashes, sparingly.
- The markers below.
- Nothing else: no digits, headings, bullets, bold, links, emojis, symbols or other brackets. No ellipsis either: a voice tested in 2026 read "Three... two... one... and rest." and lost "and rest" in three takes of five.

## Numbers and abbreviations

| Instead of | Write |
|---|---|
| 3 sets of 10 | three sets of ten |
| 25 lbs | twenty-five pounds |
| 0:45 or 45 sec | forty-five seconds |
| 8-10 reps | eight to ten reps |
| 45/15 | forty-five seconds on, fifteen off |
| 4.25% | four and a quarter percent |
| $2.1B | two point one billion dollars |
| 1st, 2nd | first, second |
| RPE 7 | about a seven out of ten effort |
| S&P 500 | the S and P five hundred |
| Q3 | the third quarter |
| 76ers | the Sixers |
| No. 1 | number one |

Write years as spoken ("twenty twenty-six") and decades in words ("the nineteen sixties"). Spell out abbreviations ("for example", "Doctor", "Saint", "kilograms"). Use company names, not tickers. Acronyms said as words or letters (NASA, NHL) can stay; if one comes out wrong, write it with spaces (N H L) or rephrase.

## Markers

- **Paragraph breaks.** A blank line gives at least a third of a second of quiet, and the render spreads a segment's spare time over its breaks (up to about one and a half seconds more each). Keep a paragraph under about fifty words: the lint refuses one over twenty-two seconds spoken.
- **`[pause 3s]`** is exactly that much silence (also `[pause 500ms]`; at most ten seconds). Use it where the listener needs real time, such as getting into position or a breath. Box breathing, for example: "Breathe in through your nose. [pause 2s] Hold it there. [pause 3s] Out through your mouth. [pause 2s] And hold. [pause 3s]"
- **`[chime]`** rings the bell. A chime already opens every segment after the first; inside a segment, ring one at each change of an interval, and say the cue too ("At the bell, go. [chime] Push.").
- **`[hold 5s]`** is that much silence between two cues of timed work. A bare `[hold]` takes the segment's spare time and keeps the segment its full length; without one, a segment ends early when its words run out. Never use a hold to pad a story or a rest.
- **No silence over eight seconds**, counting holds, pauses and the breaks around them. The lint refuses it.
- **Counts and cues.** Write every countdown as a marker, never in words: `[count 5]` (five down to one, a second apart), `[count 3 go]` (then the cue; the cues are go, rest, switch, switch sides, stop and hold), or `[cue rest]` for one cue alone. A coach with recorded counts plays them on the beat, and a coach without says them in words; the brief's Counts line says which. With recorded counts, the lint refuses a countdown in words.
- **No one-word clips.** A word alone between markers or paragraph breaks ("Go.", "Hold.") is the line a local voice garbles most, and the lint refuses it. Use two words or more ("And go.", "Hold it there."). A one-word sentence inside a longer line is fine.

## Local and web voices

- **A local coach (Pocket) speaks in short pieces.** Pocket was trained on single sentences. It speaks a paragraph in chunks of a sentence or a few (about fifty tokens), and each chunk starts fresh from the coach's voice. So a run of two-word sentences ("Brace. Lower slow. Push.") comes out clipped, like a machine, and can lose its last words. Fuller sentences come out like a person. Join short cues with commas and "and" ("Hands under the shoulders, and brace. Lower slow, and push."). Keep a cue the listener must catch (go, rest, switch, left, right) and every limit cue clear and whole, never buried mid-sentence. (Tested on 2026-10-29: "Last few. Keep the shape." lost its last sentence, and longer chunks looped or dropped words, so this has to be fixed in the writing; `knowledge/voices.md`, Local coaches.)
- **A local take is checked by a speech recognizer** as it renders. One that drops a cue word is rendered again. If four takes all drop it, the build stops and names the line, so reword it.
- **A web coach** reads a whole paragraph at once (ElevenLabs and Inworld with its neighbors for context too), so short cues sound fine. The brief says which kind of coach you're writing for.

## Words that trip a voice

- Homographs: "lead", "live", "read", "close", "row", "tear". Rephrase when the meaning is unclear ("rowing machine", not "the row").
- Exercise names with symbols: "90/90 hip switch" becomes "ninety-ninety hip switch".
- Names likely to be mangled: write around them ("the Flyers' captain") rather than spelling them out phonetically.
- Quotes: paraphrase. A short one gets an introduction ("as he put it,").
