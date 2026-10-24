"""ElevenLabs: an instant voice clone of the coach's clip, made once and kept by its ID, then speech
with each paragraph's real neighbors (previous_text and next_text), so delivery flows across them.

Clone: POST /v1/voices/add (multipart: name, files, description); needs the Starter plan or above.
ElevenLabs asks the uploader to hold the rights to the voice: for a designed coach that's the listener,
for a recording of a real person it's that person's consent.
Speech: POST /v1/text-to-speech/{voice_id}?output_format=pcm_24000, JSON {text, model_id, seed,
previous_text, next_text}; raw 16-bit PCM at 24 kHz back. The seed is best effort. eleven_v3 isn't
offered: it takes no previous or next text.
Design: POST /v1/text-to-voice/design?output_format=pcm_24000 {voice_description, text (100 to 1,000
characters), seed}; each preview is a take.
Not yet tried live: built against a local fake of the documented API (elevenlabs.io/docs/api-reference).
"""
import base64
import json

import cloud

SERVICE = "elevenlabs"


def _headers(content_type="application/json"):
    return {"xi-api-key": cloud.key_or_stop(SERVICE), "Content-Type": content_type}


def _clone(p):
    with open(p.clip, "rb") as f:
        clip = f.read()
    body, ctype = cloud.multipart({"name": f"sweatcast {p.name}", "description": p.description[:500]},
                                  [("files", "clip.wav", clip, "audio/wav")])
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1/voices/add", _headers(ctype), body,
                               service=SERVICE)
    voice_id = json.loads(data).get("voice_id")
    if not voice_id:
        raise cloud.ServiceError("bad_request", SERVICE, "the clone came back with no voice ID")
    return voice_id


def speaker(voice):
    voice_id = cloud.cloned_voice(voice, _clone)
    url = f"{cloud.base_url(SERVICE)}/v1/text-to-speech/{voice_id}?output_format=pcm_24000"

    def say(text, seed, previous_text=None, next_text=None):
        body = {"text": text, "model_id": voice["model"], "seed": int(seed) % 4294967296}
        if previous_text:
            body["previous_text"] = previous_text
        if next_text:
            body["next_text"] = next_text
        _, _, data = cloud.request("POST", url, _headers(), json.dumps(body).encode(), timeout=120, service=SERVICE)
        return cloud.trim(cloud.audio_pcm(data))
    return say


def design(description, line, takes, seed):
    """Up to `takes` takes, each (16-bit mono PCM at 24 kHz, the words it says)."""
    text = line
    while len(text) < 100:   # the design takes 100 to 1,000 characters of text
        text = f"{text} {line}"
    body = json.dumps({"voice_description": description[:1000], "text": text[:1000], "seed": seed}).encode()
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1/text-to-voice/design?output_format=pcm_24000",
                               _headers(), body, timeout=180, service=SERVICE)
    answer = json.loads(data)
    words = answer.get("text") or text[:1000]
    out = []
    for preview in answer.get("previews") or []:
        audio = base64.b64decode(preview.get("audio_base_64") or "")
        if audio:
            out.append((cloud.trim(cloud.audio_pcm(audio)), words))
    if not out:
        raise cloud.ServiceError("bad_request", SERVICE, "the design came back with no takes")
    return out[:max(1, takes)]
