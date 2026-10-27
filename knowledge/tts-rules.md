# Writing for Text-to-Speech

The script is read aloud exactly as written by the coach's voice: a local one (Pocket TTS on this computer) or a web one (the coach's own voice service), through `tools/render.py`. Nothing expands numbers or abbreviations first, and every voice guesses at symbols, so a pound sign, slash or digit can come out as noise or a wrong word. Write exactly what should be heard, as if dictating to someone who will read it verbatim. The build's lint (`tools/tts_build.py`) enforces the mechanical rules below.

## The final file contains only

- Letters, spaces, and blank lines between paragraphs.
- Periods, commas, question marks, exclamation points, apostrophes, quotation marks, hyphens inside words (single-leg, left-side), em dashes used sparingly, and ellipses.
- Pause markers: `[pause 3s]` (see Pacing), the bell marker `[chime]` and the hold marker `[hold]` (see Orientation), and a coach's recorded counts and cues, `[count 5 go]` and `[cue rest]` (see Pacing).
- Nothing else. No digits, headings, bullets, numbered lists, bold, italics, tables, links, emojis, brackets other than pause, chime and hold markers, or symbols of any kind.

## Numbers

| Instead of | Write |
|---|---|
| 3 sets of 10 | three sets of ten |
| 25 lbs | twenty-five pounds |
| 0:45 or 45 sec | forty-five seconds |
| 8-10 reps | eight to ten reps |
| 45/15 | forty-five seconds on, fifteen off |
| 3-2-1 | three, two, one, |
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

- A paragraph break gives a pause of at least a third of a second, and the render spreads the segment's spare time over its breaks (up to about one and a half seconds more each). Start a new paragraph for each part of a segment (cue, narrative, handoff).
- Keep each paragraph under about twenty seconds spoken, about fifty words. Long clips are where engines drift, rush or glitch, and short paragraphs give the voice natural breaths. The lint flags paragraphs over twenty-two seconds.
- `[pause 3s]` inserts exactly that much silence (also `[pause 500ms]`; at most ten seconds). Use it where the listener needs real time, such as box breathing or getting into position, not as decoration.
- **Counts and cues.** A coach with recorded counts (the brief's Counts line says which) plays them on a beat, so write a countdown as a marker, never in words: `[count 5]` is five, four, three, two, one, a second apart, from where it sits; `[count 3 go]` adds the cue a second after "one" (go, rest, switch, switch sides, stop, hold); `[cue rest]` plays one cue alone, where a cue would otherwise be one word between markers. N runs from two to ten. "Fifteen seconds left. Pick up the dumbbells. [count 5 go] [chime] Drive the floor away." The clips are the same in every workout, heard and approved once, and the lint knows their exact length. A voice reads a written countdown in about two seconds, too fast to move to, so with such a coach the lint refuses three or more number words counting down ("five, four, three"). Put a `[pause]` before a count if the listener needs a moment first.
- With a coach without recorded counts (a web coach), countdowns take commas or periods, never an ellipsis: "Three, two, one, switch." or "Three. Two. One. Switch." The lint refuses an ellipsis: a local voice tested in 2026 (Chatterbox Turbo) read "Three... two... one... and rest." and lost "and rest" in three takes of five, and the commas lost nothing in ten. Keep countdowns to one per segment.
- Every local take is checked by a speech recognizer as it renders. A take that drops a cue word (go, rest, switch, stop, left, right, a count) is rendered again, and if four takes all drop it the build stops and names the line: reword it (a longer line, the cue in its own sentence).
- Never leave one word alone between markers or paragraph breaks: "Hold.", "Go." or "Begin." on its own is a clip of one word, and a local voice garbles it often (Pocket TTS, 2026-10-26: "Begin." and "Hold." failed every take with some coaches, while "Other way." never failed). The lint refuses it. Two words or more: "Hold it there.", "And go.", "Begin now." A one-word sentence inside a longer clip ("Go. Push the floor away.") is fine.
- Commas give short breaths. Long sentences without commas sound rushed.
- Short sentences land cues. "Hands on the bars. Chest tall. Easy spin." is better than one long sentence.
- Box breathing: give each four-second phase a short cue and a pause. A short cue like "Hold it there." takes about a second, and a five-word cue about two, so: "Breathe in through your nose. [pause 2s] Hold it there. [pause 3s] Out through your mouth. [pause 2s] And hold. [pause 3s]" Pauses are exact; the cues run a little shorter with some voices. Vary the cue wording between rounds.

The lint predicts each segment's spoken length for the chosen voice, pauses included, so timing doesn't need to be counted by hand. It's an estimate from the voice's measured rate, usually within a few percent; a segment with time to spare ends a little early instead of going quiet, one that runs a little long is paid back from the next ones' spare time, and only the whole workout is held to plan, within three percent.

## Orientation without timestamps

The listener can't see a clock, so the voice provides it. A soft chime opens every segment after the first (`tools/render.py` adds it, and the lint counts its six tenths of a second), so the locator lands right after the bell. Open each segment with a spoken locator: "Minute nine of twenty-five." or "Round two of three." or "Halfway there." Name transitions explicitly: "Next up, in fifteen seconds, goblet squats. Grab the heavier dumbbell."

Inside a segment, `[chime]` rings the same bell at that point, for the changes in an interval (work starts, rest starts) that the clock would otherwise give: "At the bell, go. [chime] Push the floor away." The lint counts its time. Keep the spoken cue too; the bell confirms it, it doesn't replace it. A segment normally ends early when its speech runs out, so timed work would shrink; put `[hold]` where the listener works in silence, and the segment keeps its full length, its spare time silent at the hold: "At the bell, go. [chime] Drive the knees. [hold] Last five. [chime] Easy now." Bare holds share the spare time equally; `[hold 20s]` is exactly twenty seconds of silence (no ten-second cap), so time the work with a fixed hold and let one bare hold in the rest take what's left: "At the bell, go. [chime] Drive hard. [hold 20s] And stop. [chime] Breathe easy. [hold] Next, squats." A held segment is never flagged short, so a thirty-second effort needs only its cues, not thirty seconds of talk. Use it in timed work and rests only, never to pad a story. The finished MP3 ends with a three-note rising tone, so silence after it means the workout is over.

Keep to one countdown a segment, and don't let one short praise line ("Good.", "Nice work.") turn up again and again. These are guidance for the writer; the lint checks only what a voice can read, the paragraph lengths, one-word clips and the total.

## Words that trip up the voice

- Homographs: "lead" (the metal or to guide), "live" (adjective or verb), "read", "wound", "close" (near or shut), "row" (the exercise or an argument), "tear". Rephrase when context is ambiguous: "rowing machine" rather than "the row", "rest your" rather than "close your" when possible.
- Exercise names with symbols: "push-up" is fine. "T-spine" reads as "tee spine", which is fine. "90/90 hip switch" becomes "ninety-ninety hip switch".
- Names likely to be mangled: rephrase around them ("the Flyers' captain") rather than adding phonetic spellings.
- Quotes: paraphrase rather than quote. If a quote is used, keep it short and introduce it ("as he put it,") so it doesn't sound like the narrator's own opinion.

## Coaching voice

The engines copy the delivery the text suggests: long, smooth sentences come out like a radio announcer reading copy, and nothing but clipped commands comes out like a machine. A good session sounds like one coach beside one person they know. It has two registers, and the script moves between them.

**During the work: cues.** Short, two to five words, a verb first. "Hands under the shoulders. Brace. Lower slow. Push." One or two mid-set check-ins in each long working set: "Halfway there.", "Breathe out on the push.", "Last few. Keep the shape." Talk to the listener, not about the movement: "Keep your ribs down", not "The ribs should stay down."

**Around the work: a person talking.** In the welcome, the rests, the transitions and the close, write the way a coach actually talks to someone they train:
- Contractions and plain words: "you're", "let's", "that's it", "okay".
- "We" and "let's" for what's next: "Let's get you on the bench." "We've got two rounds left."
- One line of why, once per movement at most: "This one's for the back of the hips, the part that does the work when you stand up."
- Notice the effort plainly, not with stock praise: "That last set was honest." "You slowed down on the way down there. Exactly right."
- Continuity, at least once a session, from the brief's Today in the week: "Third session this week." "You said last time felt rushed, so the rests are longer today." "Same fifteens as Tuesday, one more rep."
- A little of the profile's humor, if it has some, and never at the listener's expense.

Before: "Rest. Sit up on the bench and breathe. Today's story is a new chip for six G."
After: "Nice. Sit up and get your breath back, you earned that one. Okay, while you recover, here's a strange one from the chip world."

**The name.** When the profile has a `name`, greet the listener by it in the opening line ("Hey Sam, good to have you back."), and use it again at the hardest set and at the sign-off: two to four times a session. More sounds like a sales call.

**The arc.** A session has a shape, and the voice follows it:
- **Welcome:** a greeting by name, how today fits the week ("second one this week"), then the day (weather, the shape of the calendar), then the plan said like a person: "We're doing four rounds of five today, nothing fancy, just the dumbbells and the bench."
- **Build:** settle in, explain, set the standard for each movement.
- **Peak:** name the hard part when it comes: "This is the round that counts. Stay with me."
- **Ease off:** lower the energy for the last block and the cool-down.
- **Close:** say what they did, specifically ("twenty sets, and the press felt stronger than Tuesday"), thank them or tell them it mattered, and give one reason to come back ("Next time, part two of the story."). Then the sign-off, by name.

**Locators, varied.** Every segment after the first still opens by saying where we are, but not the same way each time: "Round three of four." "Here we go, round three." "Two to go." "Back on the floor for this one." "Last round. Make it count." Three segments in a row opening alike read as a template.

**Handing off to a story.** Talk into it the way a friend would, not a newsreader: "Okay, while you breathe, here's a good one." "You'll like this." "Remember that chip from earlier? Here's the twist." Never "Today's story is", "In other news" or "Turning to".

**Keep the cues clean.** Warmth goes in the gaps, never in the middle of a cue the listener needs to hear: safety and form cues stay short and stand alone.

Exclamation points sparingly, at most one or two a session; they can make the voice shout.

## Tone

Tone and humor come from the coach's `[character]` and notes in their `persona.md`, which the brief quotes (how the coach talks to the listener and what encouragement works for them). Whatever the tone, avoid hype words and repeated catchphrases, and vary praise; "Nice work" eight times in one session becomes noise.
