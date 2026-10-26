# Audio bench, 2026-10-26, mac

Apple M5, Darwin 27.0.1; sweatcast 14.2.0; 44 lines; recognizer nemo-parakeet-tdt-0.6b-v3.

| Model | Device | Status | Takes | Not ok | Missing a cue | Audio problems | WER | Render ratio | Load s | Peak memory |
|---|---|---|---|---|---|---|---|---|---|---|
| turbo | mlx | ok | 88 | 4 | 0 | 0 | 1.1% | 0.396 | 1.47 | 4.7 GB |
| qwen3 | mlx | ok | 88 | 3 | 1 | 0 | 0.8% | 0.853 | 1.58 | 9.5 GB |
| lure | mlx | ok | 88 | 5 | 1 | 0 | 1.1% | 0.748 | 1.77 | 7.4 GB |
| ming | mlx | ok | 88 | 4 | 1 | 0 | 1.2% | 1.972 | 1.59 | 4.1 GB |
| pocket | cpu | ok | 44 | 3 | 0 | 0 | 0.7% | 0.154 | 2.33 | 1.6 GB |

Render ratio: seconds of rendering per second of speech (lower is faster).
