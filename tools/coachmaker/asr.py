"""Transcribe WAVs for the coach tools with the audio bench's recognizer: Parakeet TDT 0.6B v3 through ONNX, on
the processor, the same on a Mac and a PC (bench_worker.py's asr mode, in a throwaway environment).

Not the 110M Parakeet: on the ten coaches' Pocket takes (2026-10-26) it heard about twice as many lines wrong
as the 0.6B, and reported cues as dropped that the 0.6B heard said."""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
import bench  # noqa: E402


def transcribe(wavs, work):
    """{wav path: what was heard, or None}."""
    if not wavs:
        return {}
    os.makedirs(work, exist_ok=True)
    out = os.path.join(work, "heard.json")
    job = os.path.join(work, "asr-job.json")
    with open(job, "w", encoding="utf-8") as f:
        json.dump({"files": list(wavs), "out": out, "asr_repo": bench.ASR_MODEL[0],
                   "asr_revision": bench.ASR_MODEL[1], "asr_dir": os.path.join(bench.WORK, "asr-model")}, f)
    print(f"Transcribing {len(wavs)} take(s) with Parakeet 0.6B (ONNX)", flush=True)
    cmd = ["uv", "run", "--isolated", "--no-project", "--python", bench.PYTHON,
           *[x for p in [*bench.ASR, *bench.COMMON] for x in ("--with", p)], "python", "-I", bench.WORKER, "asr", job]
    with open(os.path.join(work, "asr.log"), "w", encoding="utf-8") as log:
        code = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT,
                               env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    try:
        with open(out, encoding="utf-8") as f:
            return json.load(f)["heard"]
    except (OSError, ValueError, KeyError):
        raise SystemExit(f"The recognizer failed (exit {code}); see {work}/asr.log")
