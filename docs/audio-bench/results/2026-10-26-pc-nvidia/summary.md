# Audio bench, 2026-10-26, pc

AMD64 Family 23 Model 113 Stepping 0, AuthenticAMD, Windows 10, NVIDIA GeForce RTX 2080 SUPER 8192 MiB; sweatcast 14.2.0; 44 lines; recognizer nemo-parakeet-tdt-0.6b-v3.

| Model | Device | Status | Takes | Not ok | Missing a cue | Audio problems | WER | Render ratio | Load s | Peak memory |
|---|---|---|---|---|---|---|---|---|---|---|
| turbo | cuda | ok | 88 | 6 | 1 | 0 | 1.3% | 0.529 | 33.91 | 3.5 GB |
| qwen3 | cuda | ok | 88 | 4 | 1 | 1 | 0.8% | 3.953 | 21.92 | 5.5 GB |
| lure | cuda | ok | 88 | 8 | 0 | 4 | 1.0% | 3.176 | 14.03 | 3.5 GB |
| ming | cuda | ok | 88 | 1 | 0 | 0 | 0.5% | 2.864 | 14.85 | 3.1 GB |
| pocket | cuda | ok | 88 | 1 | 0 | 0 | 0.4% | 0.293 | 26.83 | 0.7 GB |
| turbo | cpu | ok | 44 | 2 | 0 | 0 | 0.9% | 2.497 | 25.65 | 6.5 GB |
| lure | cpu | ok | 44 | 2 | 0 | 0 | 0.9% | 8.83 | 13.93 | 9.2 GB |
| pocket | cpu | ok | 44 | 3 | 0 | 0 | 0.7% | 0.427 | 10.98 | 1.2 GB |

Render ratio: seconds of rendering per second of speech (lower is faster).
