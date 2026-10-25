---
name: coach
description: Create a new coach (a trainer persona with a person's name, how they talk and how they sound), or change how a coach sounds or talks. Use when someone says "I want a new coach", "design a coach", "a different voice", "make the coach a woman", "change how my coach sounds", in setup or in a workout request, and whenever setup reaches the coach step.
---

# Coach: a trainer of the listener's own

A coach is a persona folder in `me/personas/<slug>/`: a person's name, how they talk, and how they sound. There are two kinds (`knowledge/voices.md` has the details):
- **A web coach** (`kind = "web"`): a voice a web service (Fish Audio, ElevenLabs, Gemini or Inworld) designed from the listener's description and saved in the listener's own account there. It speaks only through that service. This is the way to make a coach: **keys, describe, audition, approve and name, the stable.**
- **A local coach** (`kind = "local"`): a ten-second clip every local engine copies. See "Local coaches" at the end.

Never send the listener to the README. Never offer, design or describe a voice that imitates a real person or a character (a celebrity, an announcer, a game or film voice); every coach is an original voice from a description. The listener picks a voice, never a vendor, a model or a voice ID: don't ask which service, and never show a voice ID.

## 0. Keys

`./sweatcast keys` prints "set" or "not set" for each web service (never a key). An audition uses every service that's set. With none set, run setup's keys step first (the `setup` skill, Reference: Keys), then come back. A key goes in `me/.env` (on the web, the environment's settings), pasted by the listener, never into the chat.

## The quick coach (the default for a first coach of their own)

One question, one audition, a few minutes:
1. **One AskUserQuestion:** "Who should coach you?", with three named sketches and Other for their own description: "Coach Maya: a woman in her thirties, crisp and upbeat", "Coach Theo: a calm man in his fifties, low and unhurried", "Coach Rosa: a warm woman in her forties, encouraging, a little playful". Use what they've said (their name, their tone) to pick the three when it points somewhere.
2. **Write the narrative** (step 1 below) to `me/personas/.auditions/<slug>.md`, from the sketch or their words.
3. **Audition** (step 2 below), in the background. It takes a minute or so and costs about a cent a service where the design cost is published (Fish Audio and Gemini; ElevenLabs and Inworld don't publish theirs).
4. **Send the candidates** by letter and cost a workout, and ask which sounds right. One or more may be approved, each with a name.
5. **Keep** each approved one, then **close the audition** (step 3 below). If none is right, ask what's off once, edit `[voice]` and audition again; past two tries, offer the full path below.
6. The next workout uses them (`--coach "<name>"`). The stand-ins stay in `me/personas/` but aren't picked once the listener has a coach of their own.

## 1. Describe (one AskUserQuestion round, up to four questions)

- **Name:** a person's name ("Coach Maya"), never a model's or a service's. Offer two or three that fit what they've said, plus Other.
- **How they sound:** gender, age, pitch, accent, energy. Offer a few short sketches (a warm baritone trainer in his forties; a crisp instructor in her thirties; an older, calm coach), plus Other.
- **How they talk:** tone and the encouragement that works (notice the effort plainly, say why a movement is there, light humor, no hype), and any pet peeves.

Turn the answers into the **narrative**, a file in persona.md's format, written to `me/personas/.auditions/<slug>.md`:

```
+++
schema = 5
name = "Coach Maya"

[voice]
who = "A woman in her thirties, a strength coach talking to one client"
sound = "Warm, mid-low, American accent, crisp diction"
energy = "Steady, calm authority"
pace = "Natural; brisk during work"
avoid = "Hype, shouting, announcer voice, sleepy delivery"

[character]
tone = "Calm and focused; light humor now and then, no hype"
encouragement = "Notices the effort plainly, and says why a movement is there"
pushes = "Asks for one more only when form is clean; backs off at pain"
cueing = "Short body cues and breath; counts only on timed work"
never_says = ["Crush it", "Beast mode", "No pain, no gain"]
sign_off = "Brief and warm; names one thing done well"
+++
- Notes: anything else about how they talk, one "- Label: text" line each.
```

- `[voice]` is what the services design from: the person and their role, how they sound, and always what to avoid. `knowledge/voices.md` lists what worked and what didn't ("upbeat, like leading a class" came out goofy; "calm, relaxed, unhurried" came out sleepy).
- `[character]` is what the script writer follows: the brief quotes each line, and any `key = "text"` (or a list of texts) works. Lines below the block are quoted only in the `- Label: text` form.
- Leave out `style`: Gemini's API takes no style setting yet, and `./sweatcast check` flags one.

## 2. Audition

**Before the first audition**, say once, plainly, what goes where: the audition sends the coach's description to every keyed service, and each workout with a web coach sends its script, which can mention their injuries, to that coach's service; Gemini's free tier uses what it's sent for training, with human review. (This is the `setup` skill's privacy line; say it here unless it was said earlier in this conversation or a web build has already run: `grep -cE '"route": "(fish|elevenlabs|gemini|inworld)"' me/workouts/.logs/builds.jsonl` counts them.)

```
./sweatcast coaches audition me/personas/.auditions/<slug>.md
```

Run it with `run_in_background: true`; add `--play` when SendUserFile isn't available, so each candidate plays as it's listed (rerunning would be a new audition, and a new cost). Every keyed service designs from `[voice]` in parallel (asking Fish Audio for two candidates, ElevenLabs three, Gemini one, Inworld two; a service may return fewer), each saying the same coaching line, lettered A, B, C... It prints one line per candidate: the letter, the service, the approximate cost a workout there, the MP3's path (in `me/personas/.auditions/<audition>/`, the audition's id such as `2026-10-25-1`), and any note (ElevenLabs: not yet tried on a Free account, which keeps 3 voices). A service that fails says why; the others still come. `--services fish,gemini` auditions only those.

- **Send them** with SendUserFile if it's available; otherwise they played with `--play`, or give the paths. Label each by its letter and its cost a workout ("B, about $0.30 a workout"), from the lines the audition printed. Never read out `candidates.json` (it holds the services' IDs), and don't lead with the service: the listener picks by ear.
- Nothing is saved at Fish Audio, ElevenLabs or Inworld until a candidate is kept. Gemini stores each voice as it designs it; closing the audition deletes the ones not kept.
- **Not right?** Ask what's off ("too young", "too bright", "sounds bored"), edit `[voice]` in the narrative, and audition again, on every service or only the ones whose candidates came close (`--services`).

## 3. Approve, name, keep

The listener approves one or more and names each ("B is Coach Maya, D is Coach Dana"). For each:

```
./sweatcast coaches keep <audition>/<letter> --name "<name>"
```

Keep saves the voice at its service as "sweatcast <name>" and writes `me/personas/<slug>/`: `persona.md` (the narrative's `[voice]`, `[character]` and notes, plus the service and the saved voice), `sample.mp3` (the approved candidate) and `pace.json` (a pace estimated from the sample; every render then measures it). Two coaches from one audition each get their own folder, and may grow apart. A name that's taken is refused: pick another.

Then, once every approved one is kept: `./sweatcast coaches forget-audition <audition>`. It deletes Gemini's voices that weren't kept and removes the audition's folder; unsaved drafts at the other services need nothing. Remove the narrative file too: each coach now has its own copy.

## 4. The stable

`./sweatcast coaches` lists every coach with where it speaks (`web · Fish Audio`, `local · chatterbox`), marks the one a build uses when none is named, and says which are stand-ins and which are made the first time they're used. A workout uses a coach by name: `--coach "<name>"`.

- **No longer wanted:** `./sweatcast coaches archive "<name>"` moves it to `me/personas/.archive/`: out of the list, still backed up, and old log lines naming it stay valid. Its voice stays at the service.
- **How they talk** (tone, pet phrases, how they push): edit `[character]` or the notes in their `persona.md`. No audition, no cost.
- **How they sound:** a new voice on that coach's own service, from an edited `[voice]` in their `persona.md`: `./sweatcast coaches audition --coach "<name>"`, send the candidates as above, then `./sweatcast coaches keep <audition>/<letter> --name "<name>"`. It replaces the voice and `sample.mp3` and clears the old voice's pace. Adding `--replace-old` also deletes the old voice at the service: ask the listener first (on an ElevenLabs Free account it frees one of the 3 slots). Then `forget-audition`.

## Local coaches (unchanged until the local redesign)

A local coach is a ten-second clip with its exact words (`clip.wav`, `clip.txt`), which every local engine copies; it renders only locally. Make one only where local voices run (`./sweatcast doctor` says), or when the listener brings a clip.

- **Takes from the local designer** (Qwen3-TTS VoiceDesign on an Apple Silicon Mac, a 4.5 GB model the first time; say so): turn the description into one in the shape of `knowledge/voices.md`'s (the person and their role, then what to avoid), and `./sweatcast coaches design "<name>" "<description>" --takes 2` with `run_in_background: true`. It saves `me/personas/<slug>/takes/<n>.wav`. Send the takes (SendUserFile, else `--play`, else the paths) and ask which sounds right; reword the description or try another `--seed` if none does. Earlier takes are kept.
- **A clip they bring:** about ten seconds of clear speech with its exact words. A real person's voice only with that person's consent; say so plainly.
- **Keep it:** `./sweatcast coaches keep "<take>"` (or `keep <clip> --name "<name>" --words "<exact words>"` for a brought clip; `--engine qwen3` for the clearest diction on a Mac, Chatterbox otherwise). Write how the coach talks in `me/personas/<slug>/persona.md`, under `## How this coach talks`: replace the template's `[hint]` lines, keep the `+++` block. `./sweatcast check` lists any line still showing a hint.
- **Measure its pace:** a new clip has no measured pace, so run the smoke test on this computer (about a minute): `./sweatcast build knowledge/smoke-test.draft.txt "smoke-test" --coach "<name>"`. Send the result and ask how it sounds.
- A new sound for a local coach is a new take kept with `--force` (their pace is measured again).

A workout that asked for a new coach continues with them, passing `--coach "<name>"` to the build.
