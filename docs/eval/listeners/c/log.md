+++
schema = 3
+++
# Workout log

An invented listener for the judged grid in docs/eval/.

One line per session: date, length, kit, voice, main movements, topics, then `format:` and `loads:` (movement = load and tempo, separated by semicolons). No injury details. The workout skill adds each line with `./sweatcast log-session`, which checks the fields; `./sweatcast check` lists any line the tools can't read.

## Sessions
- 2026-10-14 | 45 min | full-gym | Qwen3 Coach | box squat, dumbbell bench press, lat pulldown | invented topics | format: paired-sets
- 2026-10-16 | 30 min | full-gym | Qwen3 Coach | rower intervals | invented topics | format: intervals
- 2026-10-19 | 45 min | full-gym | Qwen3 Coach | bulgarian split squat, chest-supported row, seated shoulder press | invented topics | format: straight-sets

## Feedback
