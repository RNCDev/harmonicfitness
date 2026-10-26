# Audio bench, 2026-10-26, mac

Apple M5, Darwin 27.0.1; sweatcast 14.2.0; 3 lines; recognizer nemo-parakeet-tdt-0.6b-v3.

| Model | Device | Status | Takes | Not ok | Missing a cue | Audio problems | WER | Render ratio | Load s | Peak memory |
|---|---|---|---|---|---|---|---|---|---|---|
| turbo | mlx | ok | 3 | 0 | 0 | 0 | 0.0% | 0.443 | 1.94 | 4.5 GB |
| qwen3 | mlx | ok | 3 | 0 | 0 | 0 | 0.0% | 0.95 | 1.7 | 9.2 GB |
| lure | mlx | ok | 3 | 0 | 0 | 0 | 0.0% | 0.664 | 1.62 | 6.8 GB |
| ming | mlx | ok | 3 | 0 | 0 | 0 | 0.0% | 1.733 | 1.11 | 4.1 GB |
| pocket | cpu | ok | 3 | 0 | 0 | 0 | 0.0% | 0.103 | 2.16 | 1.5 GB |

Render ratio: seconds of rendering per second of speech (lower is faster).
