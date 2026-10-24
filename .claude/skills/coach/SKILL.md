---
name: coach
description: Create a new coach (a trainer persona with a person's name, how they talk and how they sound), or change how a coach sounds or talks. Use when someone says "I want a new coach", "design a coach", "a different voice", "make the coach a woman", "change how my coach sounds", in setup or in a workout request, and whenever setup reaches the coach step.
---

# Coach: a trainer of the listener's own

A coach is a persona folder in `me/personas/<slug>/`: a person's name, how they talk (`persona.md`), and a ten-second clip every engine copies (`clip.wav`, `clip.txt`). `knowledge/voices.md` has the details. Nothing renders from a description alone: a description makes takes, the listener keeps one, and that clip is the coach. Never send the listener to the README.

## 1. Who the coach is (one AskUserQuestion round, up to four questions)

- **Name:** a person's name ("Coach Maya"), never a model's. Offer two or three that fit what they've said, plus Other.
- **How they sound:** gender, age, pitch, accent, energy. Offer a few short sketches (a warm baritone trainer in his forties; a crisp instructor in her thirties; an older, calm coach), plus Other.
- **How they talk:** tone and the encouragement that works (notice the effort plainly, say why a movement is there, light humor, no hype), and any pet peeves.
- Turn the answers into one description in the shape of the ones that worked in `knowledge/voices.md` (the person and their role, then what to avoid).

## 2. Takes

`./sweatcast doctor` (already run in setup) says which designer works here; `./sweatcast coaches design` picks the first that does: local on an Apple Silicon Mac (a 4.5 GB model the first time; say so), else Fish Audio or ElevenLabs with the listener's key (Fish costs about a cent a design). With none of them, offer the other two ways: a key for Fish Audio (`./sweatcast keys init fish`; the listener pastes the key into the file themselves, never into the chat), or a clip they bring.

- `./sweatcast coaches design "<name>" "<description>" --takes 2` with `run_in_background: true`. It saves `me/personas/<slug>/takes/<n>.wav`.
- Send the takes with SendUserFile if it's available; otherwise play them with the system's player (`--play`, or `open`, `xdg-open`, `start ""`), or give the paths. Ask which sounds right, and what's off if none does.
- Not right: reword the description from what they said is off (`knowledge/voices.md` lists what worked and what didn't), or another `--seed`, and design again. Earlier takes are kept.
- A clip they bring: about ten seconds of clear speech with its exact words. A real person's voice only with that person's consent; say so plainly.
- A listener on the Deepgram route picks a stock voice instead: `./sweatcast coaches samples deepgram`, send the samples, then `./sweatcast coaches set "<name>" deepgram.voice <voice>`. Say the coach will sound different from any clip.

## 3. Keep it

- `./sweatcast coaches keep "<take>"` (or `keep <clip> --name "<name>" --words "<exact words>"` for a brought clip; `--engine qwen3` for the clearest diction on a Mac, Chatterbox otherwise).
- Write how the coach talks in `me/personas/<slug>/persona.md`, under `## How this coach talks`, from step 1: replace the template's `[hint]` lines, keep the `+++` block. `./sweatcast check` lists any line still showing a hint.
- Measure the coach's pace on this computer's route with the smoke test (about a minute; on a cloud voice about 1,000 characters): `./sweatcast build knowledge/smoke-test.draft.txt "smoke-test" --coach "<name>"`. Send the result and ask how it sounds.

A workout that asked for a new coach continues with them, passing `--coach "<name>"` to the build. A change to how an existing coach talks is just an edit to their `persona.md`; a new sound is a new take kept with `--force` (their pace is measured again).
