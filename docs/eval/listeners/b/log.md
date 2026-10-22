+++
schema = 3
+++
# Workout log

An invented listener for the judged grid in docs/eval/.

One line per session: date, length, kit, voice, main movements, topics, then `format:` and `loads:` (movement = load and tempo, separated by semicolons). No injury details. The workout skill adds each line with `./sweatcast log-session`, which checks the fields; `./sweatcast check` lists any line the tools can't read.

## Sessions
- 2026-10-15 | 40 min | hotel-gym | Chatterbox Coach | goblet squat, dumbbell bench press, single-arm row | invented topics | format: straight-sets
- 2026-10-18 | 30 min | hotel-gym | Chatterbox Coach | reverse lunge, push-up, dead bug | invented topics | format: circuit

## Feedback
