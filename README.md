# HarmonicFitness

Your own workout podcast, made fresh each session. Ask for a workout and HarmonicFitness checks in on how you feel, plans around your equipment and any injuries, writes a narrated script with news, science and stories you care about, and turns it into an MP3 in a coach's voice. The audio is the workout: no screen, no timer, and the whole session lands within five percent of the length you asked for.

It runs inside an AI assistant that can work with files on your own computer: **Claude Code** (the Code tab of the Claude desktop app) or **ChatGPT's Codex** (Codex in the ChatGPT desktop app).

## Invite a friend

Copy and send:

> I've been using HarmonicFitness, a workout podcast made fresh for me each time: it asks how I'm feeling, plans around my equipment and any injuries, and turns the session into an MP3 with a coach's voice and stories I care about. To try it, open the Claude desktop app (the **Code** tab; needs a paid plan) or the ChatGPT desktop app (**Codex**; any plan), open your home folder, and paste: *Can you use https://github.com/RNCDev/harmonicfitness and set me up?* It walks you through the rest.

## Start here

**With Claude** (a paid Claude plan; Pro is fine):
1. Open the [Claude desktop app](https://claude.com/download) and click **Code**. When it asks for a folder, pick your home folder (the one with your name).
2. Paste: **Can you use https://github.com/RNCDev/harmonicfitness and set me up?** Click **Allow** when it asks to run something.
3. Claude downloads HarmonicFitness into a `harmonicfitness` folder in your home folder, then asks you to start a **new** Code session there: click New session, choose the `harmonicfitness` folder, and say **set up HarmonicFitness**.

**With ChatGPT** (any plan, Free included):
1. Open the [ChatGPT desktop app](https://chatgpt.com/download), choose **Codex** at the top left, and open your home folder.
2. Paste: **Can you use https://github.com/RNCDev/harmonicfitness and set me up?** Approve it when it asks to run something.
3. Codex downloads HarmonicFitness into a `harmonicfitness` folder, then asks you to open that folder in Codex. Do that (if it asks whether to trust the folder, say yes: that lets HarmonicFitness's own commands run without a prompt each time) and say **set up HarmonicFitness**.

**In a terminal or an editor** (VS Code, Cursor, JetBrains): `git clone https://github.com/RNCDev/harmonicfitness.git ~/harmonicfitness` (or GitHub's **Code > Download ZIP**), open the folder in Claude Code or Codex, and say "set up harmonicfitness". Keep the folder out of iCloud Drive, Dropbox and other synced folders: it grows to several gigabytes.

Setup asks four questions (your name, experience, equipment, injuries), lets you choose a coach by ear from short samples, and makes a ten-minute first workout. Once you've answered the questions you can step away: the assistant researches, writes and renders the workout on its own, then shows you where the MP3 is and asks which folder syncs to your phone (iCloud Drive, Google Drive or Dropbox), so later workouts land there.

**After setup,** ask for a workout any time, in your own words: "I'd like a workout", "25 minutes at the hotel, just go". Two more things to say when you're ready:
- **"Finish setting me up"**: your topics and favorite shows, which the workout's stories come from.
- **"I want a new coach"**: a coach of your own, with a name and a voice you pick by ear from an audition of web voices (it needs at least one voice service key).

## What you need

- **A Mac or a Windows PC.** Linux runs with Claude Code (the tests run there), though local voices there are not yet tried by hand. On Windows, `./harmonicfitness` runs in Git Bash, which comes with [Git for Windows](https://git-scm.com/download/win); Claude Code needs it anyway. Codex has been tried end to end on a Mac, not yet on Windows.
- **A voice**, one of two kinds:
  - **On your own computer** (an Apple Silicon Mac, or a Windows or Linux PC, with or without an NVIDIA card): free and private, after a one-time download of about 4 GB (the voice engine, Pocket TTS, and the speech recognizer that checks every line). A 30-minute workout renders in about five minutes on a Mac, ten to fifteen on a PC's processor. The readiness check wants at least 6 GB free. You choose from ten coaches that ship with harmonicfitness.
  - **A web coach**, on any computer: a voice service with a pay-as-you-go key of your own, no subscription. The assistant suggests Fish Audio (about $0.30 a workout, no minimum) and walks you through getting the key.
- **No programming, and no GitHub account** (that's only for a private backup of your profile).
- **With ChatGPT,** turn off "Improve the model for everyone" (Settings, Data Controls) if you'd rather your health notes weren't used for training. Codex reminds you before the first workout.

## Where it runs

| Where | Works? |
|---|---|
| Claude Code on your own computer: the Code tab of the Claude desktop app, a terminal or an editor | Yes |
| ChatGPT's Codex on your own computer: Codex in the ChatGPT desktop app, the Codex CLI or an editor | Yes (tried end to end with the Codex the ChatGPT app ships, on the Free plan's model; the app's own prompts not yet tried by hand) |
| Claude Code on the web (claude.ai/code) | Not for setting up. A listener already set up, with their private profile repo attached, can keep using web coaches there |
| The HarmonicFitness web app, in a browser | Yes, with web coaches only: it's its own app ([web/README.md](web/README.md)) |
| A plain Claude or ChatGPT chat, or Codex cloud tasks | No: they can't run HarmonicFitness's commands on your computer |

## For Claude (or ChatGPT's Codex): setting someone up from this link

If someone asks you to use this repository and set them up, and your session isn't already open in a copy of it:

1. **You need to run commands on their own computer.** In a plain chat, on Claude Code on the web (`CLAUDE_CODE_REMOTE=true`) or in a cloud task, say that HarmonicFitness runs on their own computer, in the **Code** tab of the Claude desktop app (https://claude.com/download) or **Codex** in the ChatGPT desktop app (https://chatgpt.com/download), where they open their home folder and ask again. Then stop.
2. **Pick the folder:** `~/harmonicfitness` (on Windows, the same path in Git Bash). Never inside iCloud Drive, Dropbox, OneDrive, Google Drive or a synced Documents folder: the voice model and Python environment take several gigabytes. If `~/harmonicfitness` already holds HarmonicFitness, use it (`git -C ~/harmonicfitness pull` if it's a checkout).
3. **Download it, no account needed.** With git (`command -v git`; on a Mac, `xcode-select -p` too, since a bare `git` there can open an installer): `git clone https://github.com/RNCDev/harmonicfitness.git ~/harmonicfitness`. Without git: download `https://github.com/RNCDev/harmonicfitness/archive/refs/heads/main.zip`, unzip it, and move the `harmonicfitness-main` folder to `~/harmonicfitness`. A ZIP copy works fully, except the privacy hook, which needs git.
4. **Hand over to a session in that folder.** HarmonicFitness's instructions and safety settings (among them the rule that keeps API keys out of the chat) load only in a session opened there, so don't run setup from the session you're in. Give literal steps:
   - Claude desktop app: "click **New session** in the Code tab, choose the **HarmonicFitness** folder in your home folder, and type *set up HarmonicFitness*".
   - ChatGPT desktop app: "open the **HarmonicFitness** folder in your home folder in Codex, trust it if asked, and type *set up HarmonicFitness*".
   - An editor: open the `harmonicfitness` folder and start Claude Code or Codex there. A terminal: `cd ~/harmonicfitness && claude` (or `codex`).

# How it works

## A session

1. **Check-in.** The assistant asks only what you didn't say: how each injury feels, the goal, the length, the kit.
2. **Research.** Your topics (in `me/content.md`) fill the steady work and the rests: today's news from your feeds and a short search, and evergreen pieces researched ahead of time. Nothing told in the last thirty days is told again, and each story is told in its own way: a quick hit, a quiz answered a few rests later, a serial across the session, a recommendation in the spirit of your favorites. Say "update my interests" to add topics.
3. **The plan.** `./harmonicfitness brief` gathers who you are, how the week has gone, today's limits with your clinician's rules, and the safe menu: every movement your kit, level and limits allow. Your level also sets how much the coach explains. The assistant designs the session from it and writes the script.
4. **The build.** `./harmonicfitness build` refuses any movement that isn't on today's menu, checks the script reads cleanly aloud and fits the time, renders the MP3 in your coach's voice, and copies it to your phone's folder.

A soft chime opens each segment and a rising tone ends the workout. No silence runs past eight seconds, so the coach talks you through every set. How the parts connect, in one page: [docs/index.html](docs/index.html).

## Your files

Everything about you lives in `me/` (or wherever `HARMONICFITNESS_HOME` points). It's ignored by git, and a pre-push hook and CI refuse it, so pulling updates never touches it.

| File | Holds |
|---|---|
| `me/profile.md` | Who you are: name, experience, basics |
| `me/training.md` | Your kits and weights, the movements you like and dislike, your usual session |
| `me/content.md` | What the coach talks about: your topics, feeds, YouTube channels, puzzles, taste |
| `me/health.md` | Your injuries and your clinician's rules, followed literally |
| `me/log.md` | Your sessions and feedback |
| `me/settings.toml` | The tools' settings: audio route, delivery folder, web spending ceiling |
| `me/workouts/` | Each workout's script, research and records |
| `me/.env` | Your voice service keys: you paste them in; only the engine reads them, and they're never backed up |

`./harmonicfitness check` says what's still to fill in. When a release changes a file's format, `./harmonicfitness migrate` (or rerunning `./harmonicfitness setup`) brings `me/` up to date, backing up the originals first.

**Back it up.** Without a GitHub account, `me/` stays on your computer and everything works; copy the folder somewhere private now and then (it holds your health notes). With one, keep `me/` as its own private repo and the workout's last step, `./harmonicfitness backup`, pushes each session. With the [GitHub CLI](https://cli.github.com) logged in:

```
cd me && git init && git add -A && git commit -m "My harmonicfitness" && gh repo create harmonicfitness-me --private --source . --push
```

`./harmonicfitness backup` refuses a repo GitHub reports as public. Another computer gets your profile by cloning that repo into `me/`.

## Coaches and voices

A coach is a person's name, how they talk and how they sound. Twenty-five stock coaches ship with it, so you can start at once: **ten local coaches** for a voice on your computer (Andy, Marcus, Theo, Sam and Callum; Maya, Claire, Rosa, Helen and Kate, each with a 45-second sample to choose by ear), **twelve ready-made web coaches**, six on OpenRouter (Graham, Jonah, Leah, Nora, Rowan, Tess) and six on Gemini (Fraser, Freya, June, Miles, Ruby, Wade), each with a sample to hear, and **one stock web coach each** for Fish Audio, ElevenLabs and Inworld (Reed, Ellis and Owen), designed in your account the first time it's used. A coach of your own is a web coach, kept in `me/coaches/`; keep several if you like.
- **A web coach** is an original voice a service designs from your description and saves in your account. You hear candidates from every service you have a key for, pick by ear, and name the ones you keep.
- **A local coach** is one of the ten: a voice designed once for HarmonicFitness, with its counts and cues recorded and checked by ear, spoken on your computer by Pocket TTS. It sounds the same in every workout.

| Where the voice comes from | Engine or service | Cost | Notes |
|---|---|---|---|
| Apple Silicon Mac | Pocket TTS on the processor | Free | About 0.15 times the length of the speech on an M5 |
| Windows or Linux with an NVIDIA card | Pocket TTS on CUDA | Free | About 0.3 times on an RTX 2080 Super; Linux not yet tried by hand |
| Windows or Linux, processor only | Pocket TTS on the processor | Free | About 0.43 times |
| Fish Audio | A designed voice, saved as a private model | About $0.30 a workout | Prepaid credit, no minimum; about $0.01 a design |
| Gemini | A designed voice | About $0.27 a workout through 2026, about $0.54 from 2027 | A Google AI Studio key; its free tier uses requests for training |
| Inworld | A designed voice, in your workspace | About $0.50 a workout | On-Demand plan, prepaid credit |
| OpenRouter | A stock voice (ElevenLabs' or Microsoft's), picked by ear | About $0.80 a workout (ElevenLabs' voices; $0.44 on Microsoft's) | One key for many models; on the web app it also writes the workouts |
| ElevenLabs | A designed voice, in your account | About $1.60 a workout ($0.80 on the faster model) | Free keeps 3 voices and a small monthly allowance (not yet tried on Free); the key needs Text to Speech and Voices: write |

Prices are approximate, for a 30-minute workout, and change. A web build says what it will send and cost before sending, stops above a ceiling you set, and sends only the final script; that script can mention your injuries, so setup says so first. More in [knowledge/voices.md](knowledge/voices.md).

## Health and safety

HarmonicFitness is not medical advice. It programs conservatively around the injuries you describe, and anything a doctor or physical therapist has told you overrides it: write it in `me/health.md` and it's followed literally. Every session has a stop rule (sharp pain, new swelling, numbness or giving way stops that movement), and red flags such as not being able to bear weight stop the session and suggest a clinician.

## Coaches and consent

A web coach's voice is designed from a written description, never copied from a recording, and HarmonicFitness never offers voices that imitate real people or characters. The ten local coaches are original voices too, designed from descriptions (`coaches/roster.toml`); you can't bring a recording to clone.

## For developers

- [docs/index.html](docs/index.html): how the parts connect; [docs/style-guide.html](docs/style-guide.html): the house style.
- [CLAUDE.md](CLAUDE.md): the rules and the code map the assistants work from.
- [web/README.md](web/README.md): the web app.
- `./harmonicfitness help` lists every command (each takes `--help`); `./harmonicfitness test` runs the tests CI runs.

## Support

HarmonicFitness is free and open source. If it gets you moving, you can [buy me a coffee on Ko-fi](https://ko-fi.com/devrc) or [sponsor it on GitHub](https://github.com/sponsors/RNCDev).

## Versioning

HarmonicFitness follows [Semantic Versioning](https://semver.org) and is pre-1.0: a 0.X.0 release may break something (its "For forks" note says what to do), a 0.x.Y release doesn't. The numbering restarted at 0.16.0 (it was 16.0.0); older releases were renumbered to match (`CHANGELOG.md` has the table). Each release is tagged `vX.Y.Z` on GitHub; `CHANGELOG.md` says what changed, and a release's "For forks" note says what to do after pulling it.

## License

MIT, see [LICENSE](LICENSE). `tools/char_weight.py` is vendored from [OmniVoice](https://github.com/k2-fsa/OmniVoice) under the Apache License 2.0, with its header kept. The local voice is [Pocket TTS](https://huggingface.co/kyutai/pocket-tts-without-voice-cloning) by Kyutai (CC-BY 4.0), downloaded, not distributed here, and used as is; each local coach's `pocket.safetensors` is a voice state made with Kyutai's Pocket TTS from an original voice designed with [Qwen3-TTS VoiceDesign](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign) (Apache 2.0), no real person's voice. The take checker is [Parakeet TDT 0.6B v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) (NVIDIA, CC-BY 4.0), in [istupakov's ONNX conversion](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx).
