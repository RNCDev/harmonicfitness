"""Speaker embeddings for the coach QA (maintainer only), inside the Turbo environment: Chatterbox's own
VoiceEncoder, the one Turbo conditions on. Imports nothing from sweatcast.

  python embed_worker.py <job.json>

The job: {"ve": <folder holding ve.safetensors>, "groups": {name: [wav paths]}, "out": <json path>}. Each
group's takes become one speaker embedding (the mean of the takes', normalized); the output holds every
group's embedding as a list of floats.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.curdir) != _HERE]


def main(job_path):
    import librosa
    import numpy as np
    import soundfile as sf
    import torch
    from safetensors.torch import load_file
    from chatterbox.models.voice_encoder import VoiceEncoder
    with open(job_path, encoding="utf-8") as f:
        job = json.load(f)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ve = VoiceEncoder()
    ve.load_state_dict(load_file(os.path.join(job["ve"], "ve.safetensors")))
    ve.to(device).eval()
    out = {}
    for name, wavs in job["groups"].items():
        audio = []
        for w in wavs:
            a, sr = sf.read(w, dtype="float32")
            a = a.mean(axis=1) if a.ndim > 1 else a
            if sr != ve.hp.sample_rate:   # the encoder's own resampler needs resampy, which isn't installed
                a = librosa.resample(a, orig_sr=sr, target_sr=ve.hp.sample_rate, res_type="soxr_hq")
            audio.append(a)
        emb = ve.embeds_from_wavs(audio, sample_rate=ve.hp.sample_rate, as_spk=True)
        out[name] = [float(x) for x in np.asarray(emb).reshape(-1)]
        print(f"  {name}: {len(wavs)} take(s)", flush=True)
    with open(job["out"], "w", encoding="utf-8") as f:
        json.dump(out, f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
