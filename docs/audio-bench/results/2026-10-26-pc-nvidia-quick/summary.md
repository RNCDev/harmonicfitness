# Audio bench, 2026-10-26, pc

AMD64 Family 23 Model 113 Stepping 0, AuthenticAMD, Windows 10, NVIDIA GeForce RTX 2080 SUPER 8192 MiB; sweatcast 14.2.0; 3 lines; recognizer nemo-parakeet-tdt-0.6b-v3.

| Model | Device | Status | Takes | Not ok | Missing a cue | Audio problems | WER | Render ratio | Load s | Peak memory |
|---|---|---|---|---|---|---|---|---|---|---|
| turbo | cuda | ok | 3 | 0 | 0 | 0 | 0.0% | 0.662 | 426.47 | 3.3 GB |
| qwen3 | cuda | ok | 3 | 0 | 0 | 0 | 0.0% | 6.392 | 413.81 | 5.2 GB |
| lure | cuda | ok | 3 | 0 | 0 | 0 | 0.0% | 4.356 | 241.75 | 3.3 GB |
| ming | cuda | ok | 3 | 0 | 0 | 0 | 0.0% | 2.64 | 279.06 | 3.1 GB |
| pocket | cuda | load: ValueError: We could not download the weights for the  | 0 | 0 | 0 | 0 |  |  |  | 1.4 GB |
| turbo | cpu | ok | 3 | 0 | 0 | 0 | 0.0% | 2.717 | 64.53 | 6.6 GB |
| lure | cpu | ok | 3 | 0 | 0 | 0 | 0.0% | 11.147 | 39.98 | 7.3 GB |
| pocket | cpu | load: ValueError: We could not download the weights for the  | 0 | 0 | 0 | 0 |  |  |  | 1.0 GB |

Render ratio: seconds of rendering per second of speech (lower is faster).
