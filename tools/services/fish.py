"""Fish Audio: speech in the coach's voice from the clip itself, sent with every request, so there's no
saved voice to manage; and voice design from a description.

Speech: POST /v1/tts, MessagePack (inline references need it), the model in a `model` header. It asks for
WAV at 24 kHz, whose size fields Fish leaves as placeholders while streaming (cloud.wav_pcm reads to the
end). Fish's speech takes no seed, so a re-render is a new take; the clip cache keeps what's rendered.
Each request carries the clip (about half a megabyte).
Design: POST /v1/voice-design, JSON, `model: voice-design-1`; each candidate is a take (about $0.01 a call).
Docs: docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech and .../voice-design.
"""
import base64
import json

import cloud
import msgpack_min

SERVICE = "fish"
DESIGN_MODEL = "voice-design-1"


def speaker(voice):
    with open(voice["ref_audio"], "rb") as f:
        clip = f.read()
    url = cloud.base_url(SERVICE) + "/v1/tts"

    def say(text, seed, previous_text=None, next_text=None):
        body = msgpack_min.pack({"text": text, "references": [{"audio": clip, "text": voice["ref_text"]}],
                                 "format": "wav", "sample_rate": cloud.SR, "normalize": True, "latency": "normal"})
        headers = {"Authorization": f"Bearer {cloud.key_or_stop(SERVICE)}", "model": voice["model"],
                   "Content-Type": "application/msgpack"}
        _, _, data = cloud.request("POST", url, headers, body, timeout=120, service=SERVICE)
        return cloud.trim(cloud.audio_pcm(data))
    return say


def design(description, line, takes, seed):
    """`takes` takes of `line` in a voice made from `description`: 16-bit mono PCM at 24 kHz each."""
    body = json.dumps({"instruction": description[:2000], "reference_text": line[:150], "n": max(1, min(takes, 4)),
                       "seed": seed}).encode()
    headers = {"Authorization": f"Bearer {cloud.key_or_stop(SERVICE)}", "model": DESIGN_MODEL,
               "Content-Type": "application/json"}
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1/voice-design", headers, body, timeout=180,
                               service=SERVICE)
    out = []
    for c in json.loads(data).get("candidates") or []:
        audio = base64.b64decode(c.get("audio_base64") or "")
        if audio:
            out.append(cloud.trim(cloud.audio_pcm(audio, int(c.get("sample_rate") or cloud.SR))))
    if not out:
        raise cloud.ServiceError("bad_request", SERVICE, "the design came back with no takes")
    return out
