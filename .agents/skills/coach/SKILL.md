---
name: coach
description: Choose another of the coaches sweatcast ships, or create a web coach of the listener's own (a trainer persona with a person's name, how they talk and how they sound), or change how a coach of their own sounds or talks. Use when someone says "I want a new coach", "switch coach", "design a coach", "a different voice", "make the coach a woman", "change how my coach sounds", in setup or in a workout request, and whenever setup reaches the coach step.
---

# Coach: choosing one, or making one of the listener's own

A coach is a persona folder: a person's name, how they talk, and how they sound (`knowledge/voices.md` has the details).
- **The stock coaches** ship with sweatcast in `coaches/`: **ten local coaches** (`kind = "local"`: Andy, Marcus, Theo, Sam and Callum; Maya, Claire, Rosa, Helen and Kate), each with its Pocket TTS voice, recorded counts and cues, and a 45-second `sample.mp3`; and **four stock web coaches** (Reed on Fish Audio, Ellis on ElevenLabs, Nolan on Gemini, Owen on Inworld), each made in the listener's own account the first time it's used. Local coaches are chosen, never made or re-voiced.
- **A web coach of their own** (`kind = "web"`, in `me/coaches/<slug>/`, such as `coach-dana-fish`): a voice a web service (Fish Audio, ElevenLabs, Gemini or Inworld) designed from the listener's description and saved in the listener's own account there. It speaks only through that service. This is the way to make a coach: **keys, describe, audition, approve and name, the stable.**

## Switch coach: another of the ten

When local voices run here (`./sweatcast doctor` says) and they want a different voice, offer the ten first: free, private, and ready now. One AskUserQuestion with the four styles: **Calm and experienced** (Andy, Sam, Helen), **Upbeat and energetic** (Marcus, Maya, Kate), **Easygoing and friendly** (Theo, Rosa), **Direct and precise** (Callum, Claire), with "A voice of my own (a web coach)" through Other. Send that style's samples (`coaches/coach-<name>-local/sample.mp3`; SendUserFile, else `./sweatcast show <file>`) with each coach's line from `./sweatcast coaches`, and ask which. The next workout passes `--coach "<name>"`, and builds keep using the coach used last, so nothing else changes. A man or a woman they ask for by name ("make the coach a woman") narrows the list the same way.

Never send the listener to the README. Never offer, design or describe a voice that imitates a real person or a character (a celebrity, an announcer, a game or film voice); every coach is an original voice from a description. The listener picks a voice, never a vendor, a model or a voice ID: don't ask which service, and never show a voice ID.

## 0. Keys

`./sweatcast keys` prints "set" or "not set" for each web service (never a key). An audition uses every service that's set. With none set, run setup's keys step first (the `setup` skill, Reference: Keys), then come back. A key goes in `me/.env` (on the web, the environment's settings), pasted by the listener, never into the chat.

## The quick coach (the default for a first coach of their own)

One question, one audition, a few minutes:
1. **One AskUserQuestion:** "Who should coach you?", with three named sketches and Other for their own description: "Coach Dana: a woman in her thirties, crisp and upbeat", "Coach Elliot: a calm man in his fifties, low and unhurried", "Coach Nina: a warm woman in her forties, encouraging, a little playful". Never a stock coach's name (`./sweatcast coaches` lists them): a name that's taken is refused. Use what they've said (their name, their tone) to pick the three when it points somewhere.
2. **Write the narrative** (step 1 below) to `me/coaches/.auditions/<slug>.md`, from the sketch or their words.
3. **Audition** (step 2 below), in the background. It takes a minute or so and costs about a cent a service where the design cost is published (Fish Audio and Gemini; ElevenLabs and Inworld don't publish theirs).
4. **Send the candidates** by letter and cost a workout, and ask which sounds right. One or more may be approved, each with a name.
5. **Keep** each approved one, then **close the audition** (step 3 below). If none is right, ask what's off once, edit `[voice]` and audition again; past two tries, offer the full path below.
6. The next workout uses them (`--coach "<name>"`), and later builds keep the coach used last. The stock coaches stay available to switch back to.

## 1. Describe (one AskUserQuestion round, up to four questions)

- **Name:** a person's name ("Coach Dana"), never a model's or a service's, and never a stock coach's. Offer two or three that fit what they've said, plus Other.
- **How they sound:** gender, age, pitch, accent, energy. Offer a few short sketches (a warm baritone trainer in his forties; a crisp instructor in her thirties; an older, calm coach), plus Other.
- **How they talk:** tone and the encouragement that works (notice the effort plainly, say why a movement is there, light humor, no hype), and any pet peeves.

Turn the answers into the **narrative**, a file in persona.md's format, written to `me/coaches/.auditions/<slug>.md`:

```
+++
schema = 5
name = "Coach Dana"

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

**Before the first audition**, say once, plainly, what goes where: the audition sends the coach's description to every keyed service, and each workout with a web coach sends its script, which can mention their injuries, to that coach's service; Gemini's free tier uses what it's sent for training, with human review. (This is the `setup` skill's privacy line; say it here unless it was said earlier in this conversation or a web build has already run: `./sweatcast get web-builds` counts them.)

```
./sweatcast coaches audition me/coaches/.auditions/<slug>.md
```

Run it with `run_in_background: true`; add `--play` when SendUserFile isn't available, so each candidate plays as it's listed (rerunning would be a new audition, and a new cost). Every keyed service designs from `[voice]` in parallel (asking Fish Audio for two candidates, ElevenLabs three, Gemini one, Inworld two; a service may return fewer), each saying the same coaching line, lettered A, B, C... It prints one line per candidate: the letter, the service, the approximate cost a workout there, the MP3's path (in `me/coaches/.auditions/<audition>/`, the audition's id such as `2026-10-25-1`), and any note (ElevenLabs: not yet tried on a Free account, which keeps 3 voices). A service that fails says why; the others still come. `--services fish,gemini` auditions only those.

- **Send them** with SendUserFile if it's available; otherwise they played with `--play`, or give the paths. Label each by its letter and its cost a workout ("B, about $0.30 a workout"), from the lines the audition printed. Never read out `candidates.json` (it holds the services' IDs), and don't lead with the service: the listener picks by ear.
- Nothing is saved at Fish Audio, ElevenLabs or Inworld until a candidate is kept. Gemini stores each voice as it designs it; closing the audition deletes the ones not kept.
- **Not right?** Ask what's off ("too young", "too bright", "sounds bored"), edit `[voice]` in the narrative, and audition again, on every service or only the ones whose candidates came close (`--services`).

## 3. Approve, name, keep

The listener approves one or more and names each ("B is Coach Dana, D is Coach Nina"). For each:

```
./sweatcast coaches keep <audition>/<letter> --name "<name>"
```

Keep saves the voice at its service as "sweatcast <name>" and writes `me/coaches/<slug>/`: `persona.md` (the narrative's `[voice]`, `[character]` and notes, plus the service and the saved voice), `sample.mp3` (the approved candidate) and `pace.json` (a pace estimated from the sample; every render then measures it). Two coaches from one audition each get their own folder, and may grow apart. A name that's taken is refused: pick another.

Then, once every approved one is kept: `./sweatcast coaches forget-audition <audition>`. It deletes Gemini's voices that weren't kept and removes the audition's folder; unsaved drafts at the other services need nothing. Remove the narrative file too: each coach now has its own copy.

## 4. The stable

`./sweatcast coaches` lists every coach with where it speaks (`web · Fish Audio`, `local · pocket`), marks the one a build uses when none is named (the one used last), and says which are stand-ins and which are made the first time they're used. A workout uses a coach by name: `--coach "<name>"`.

- **No longer wanted:** `./sweatcast coaches archive "<name>"` moves a coach of their own to `me/coaches/.archive/` (a stock coach can't be archived; just choose another): out of the list, still backed up, and old log lines naming it stay valid. Its voice stays at the service.
- **How they talk** (tone, pet phrases, how they push): for a coach of their own, edit `[character]` or the notes in their `persona.md` (`me/coaches/<slug>/`). No audition, no cost. How the stock coaches talk is part of sweatcast (never edit `coaches/`); feedback on a workout ("less chat") goes in the log as always.
- **How they sound** (a web coach): a new voice on that coach's own service, from an edited `[voice]` in their `persona.md`: `./sweatcast coaches audition --coach "<name>"`, send the candidates as above, then `./sweatcast coaches keep <audition>/<letter> --name "<name>"`. It replaces the voice and `sample.mp3` and clears the old voice's pace. Adding `--replace-old` also deletes the old voice at the service: ask the listener first (on an ElevenLabs Free account it frees one of the 3 slots). Then `forget-audition`.

## Local coaches

Since sweatcast 0.15.0 the local coaches are the ten that ship: a listener can't design one or bring a clip (a cloned voice is where local engines garbled words, and a real person's voice needs consent). For a voice of their own, make a web coach (above); it needs a voice key. A local coach from an older sweatcast was moved to `me/coaches/.archive/` by `./sweatcast migrate`.

A workout that asked for a new coach continues with them, passing `--coach "<name>"` to the build.
