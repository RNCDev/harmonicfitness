"""Cartesia: an instant voice clone of the coach's clip, made once and kept by its ID, then speech as raw
16-bit PCM at 24 kHz.

Clone: POST /voices/clone (multipart: clip, name, language); instant cloning needs the Pro plan.
Speech: POST /tts/bytes, `Authorization: Bearer`, `Cartesia-Version: 2026-08-14`, JSON {model_id,
transcript, voice {mode: id, id}, output_format {container raw, encoding pcm_s16le, sample_rate 24000},
language}. No seed: a re-render is a new take, and the clip cache keeps what's rendered. Joining
paragraphs needs Cartesia's WebSocket API, so plain requests don't.
Not yet tried live: built against a local fake of the documented API (docs.cartesia.ai).
"""
import json

import cloud

SERVICE = "cartesia"
VERSION = "2026-08-14"


def _headers(content_type="application/json"):
    return {"Authorization": f"Bearer {cloud.key_or_stop(SERVICE)}", "Cartesia-Version": VERSION,
            "Content-Type": content_type}


def _clone(p):
    with open(p.clip, "rb") as f:
        clip = f.read()
    body, ctype = cloud.multipart({"name": f"sweatcast {p.name}", "language": "en",
                                   "description": p.description[:500]}, [("clip", "clip.wav", clip, "audio/wav")])
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/voices/clone", _headers(ctype), body,
                               service=SERVICE)
    voice_id = json.loads(data).get("id")
    if not voice_id:
        raise cloud.ServiceError("bad_request", SERVICE, "the clone came back with no voice ID")
    return voice_id


def speaker(voice):
    voice_id = cloud.cloned_voice(voice, _clone)
    url = cloud.base_url(SERVICE) + "/tts/bytes"

    def say(text, seed, previous_text=None, next_text=None):
        body = {"model_id": voice["model"], "transcript": text, "voice": {"mode": "id", "id": voice_id},
                "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": cloud.SR},
                "language": "en"}
        _, _, data = cloud.request("POST", url, _headers(), json.dumps(body).encode(), timeout=120, service=SERVICE)
        return cloud.trim(cloud.audio_pcm(data))
    return say
