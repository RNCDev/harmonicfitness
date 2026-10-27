"""Transcribe WAVs with the take check's recognizer (Parakeet TDT-CTC 110M through sherpa-onnx), for the coach
tools. The model is public (no login) and downloads once into .cache/design/asr-110m."""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
WORKER = os.path.join(HERE, "asr_worker.py")
MODEL = ("csukuangfj/sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000", "e9bea5a06247dc3f55319ff23d34b0328f2f5ddf")
PACKAGE = "sherpa-onnx==1.12.40"
MODEL_DIR = os.path.join(ROOT, ".cache", "design", "asr-110m")
FILES = ("encoder.onnx", "decoder.onnx", "joiner.onnx", "tokens.txt")


def fetch():
    if all(os.path.exists(os.path.join(MODEL_DIR, f)) for f in FILES):
        return MODEL_DIR
    from huggingface_hub import snapshot_download
    snapshot_download(MODEL[0], revision=MODEL[1], local_dir=MODEL_DIR, allow_patterns=list(FILES))
    return MODEL_DIR


def transcribe(wavs, work):
    """{wav path: what was heard, or None}."""
    if not wavs:
        return {}
    os.makedirs(work, exist_ok=True)
    out = os.path.join(work, "heard.json")
    job = os.path.join(work, "asr-job.json")
    with open(job, "w", encoding="utf-8") as f:
        json.dump({"files": list(wavs), "out": out, "model_dir": fetch()}, f)
    print(f"Transcribing {len(wavs)} take(s) with Parakeet 110M", flush=True)
    with open(os.path.join(work, "asr.log"), "w", encoding="utf-8") as log:
        code = subprocess.call(["uv", "run", "--isolated", "--no-project", "--python", "3.11", "--with", PACKAGE,
                                "--with", "numpy", "python", "-I", WORKER, job],
                               stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    try:
        with open(out, encoding="utf-8") as f:
            return json.load(f)["heard"]
    except (OSError, ValueError, KeyError):
        raise SystemExit(f"The recognizer failed (exit {code}); see {work}/asr.log")
