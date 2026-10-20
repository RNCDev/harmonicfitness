# Voices

The VoiceStudio app is only used to make voices. Workouts render through `tools/render.py`, so the app's settings (performance profile, models, speech recognition) have no effect on them. Quit the app before a render; two copies of the model don't fit comfortably in 16 GB.

## Make a voice

From the Gallery (quickest): open a Gallery voice and click **Use voice**. It's saved under the Gallery name ("The Explainer") with a sample the app renders once. The five in `profile.md` came from here.

By design:
1. In VoiceStudio, create a voice and choose **By design**.
2. Type a description into **Describe your voice** ("calm, middle-aged male, low pitch, American accent"), or pick a starting point.
3. Preview it with one workout-style sentence under 100 characters, such as "Minute nine. Sit tall on the bench and keep your back tall."
4. Reroll until it sounds right, then **Keep this seed** and **Save design as profile** with a short name ("Coach").

From audio (a clone): five to fifteen seconds of clean speech, in a quiet room with no music, read at the pace you want; the hard limit is twenty seconds. Add the transcript or let the app transcribe it. Only clone your own voice, or someone who has agreed.

Lock it (recommended): when a take sounds right, **Lock voice identity** pins that exact take as the voice's reference, which keeps it the same across a whole workout. Lock a take whose text is under 100 characters, because locking keeps only the first 100 characters as the transcript, and a transcript cut short against the full audio throws off the voice's pace.

## Pace

OmniVoice speaks at the pace of the voice's reference take: it sets each clip's length from the text and that pace. So choose a take read at the speed you want to hear mid-workout; calm and unhurried beats an announcer read. `--speed 0.95` slows any voice slightly.

## Use it in workouts

1. Quit VoiceStudio and run `python3 tools/voices.py` to see each voice's name and pace.
2. Add it under Voices in `profile.md`, one line per voice: `  - Coach: default, calm and steady.` The first line is the default. Names match the app's, ignoring case; avoid colons in names.
3. Ask for it by name ("use the Coach voice"), or pass `--voice Coach` to `tools/build.sh`.

The first render with a new voice records its exact pace in `workouts/.audio-cache/`. Until then the lint estimates the pace from the raw take, which errs toward predicting slightly longer speech.
