"""The take check's recognizer for the coach tools (maintainer only): Parakeet TDT-CTC 110M (its transducer
head) through sherpa-onnx, on the processor, in its own throwaway environment (asr.transcribe starts it).
Imports nothing from sweatcast.

  python asr_worker.py <job.json>     job: {"files": [wav...], "out": <json>, "model_dir": <folder>}
"""
import json
import os
import sys
import time
import wave

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]


def main(job_path):
    import numpy as np
    import sherpa_onnx
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    d = job["model_dir"]
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=os.path.join(d, "encoder.onnx"), decoder=os.path.join(d, "decoder.onnx"),
        joiner=os.path.join(d, "joiner.onnx"), tokens=os.path.join(d, "tokens.txt"),
        num_threads=max(1, (os.cpu_count() or 2) // 2), model_type="nemo_transducer", provider="cpu")
    heard = {}
    started = time.time()
    for path in job["files"]:
        try:
            with wave.open(path) as w:
                sr = w.getframerate()
                a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
            s = rec.create_stream()
            s.accept_waveform(sr, a)
            rec.decode_stream(s)
            heard[path] = s.result.text.strip()
        except Exception as e:
            heard[path] = None
            print(f"  couldn't transcribe {path}: {e}", file=sys.stderr)
    with open(job["out"], "w", encoding="utf-8") as f:
        json.dump({"heard": heard, "asr_s": round(time.time() - started, 1)}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
