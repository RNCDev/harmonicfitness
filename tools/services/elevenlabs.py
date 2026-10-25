"""ElevenLabs: a web coach's voice is a saved ElevenLabs voice made from a designed preview, and every
paragraph is spoken by its voice ID with its real neighbors (previous_text and next_text), so delivery
flows across them.

Design: POST /v1/text-to-voice/design?output_format=pcm_24000 {voice_description, text (100 to 1,000
characters)}; three previews, each raw 16-bit PCM at 24 kHz with a generated_voice_id.
Save: POST /v1/text-to-voice {voice_name, voice_description, generated_voice_id} -> voice_id (still works
ten minutes after the design, tried live).
Speech: POST /v1/text-to-speech/{voice_id}?output_format=pcm_24000, JSON {text, model_id, seed,
previous_text, next_text}; raw 16-bit PCM at 24 kHz back. The seed is best effort.
Delete: DELETE /v1/voices/{voice_id}.
Tried live 2026-10-25 on Starter; not yet on a Free account (3 voices, a monthly allowance).
"""
import json

import cloud

SERVICE = "elevenlabs"


def _headers(content_type="application/json"):
    return {"xi-api-key": cloud.key_or_stop(SERVICE), "Content-Type": content_type}


def speaker(voice):
    url = f"{cloud.base_url(SERVICE)}/v1/text-to-speech/{voice['voice_id']}?output_format=pcm_24000"

    def say(text, seed, previous_text=None, next_text=None):
        body = {"text": text, "model_id": voice["model"], "seed": int(seed) % 4294967296}
        if previous_text:
            body["previous_text"] = previous_text
        if next_text:
            body["next_text"] = next_text
        _, _, data = cloud.request("POST", url, _headers(), json.dumps(body).encode(), timeout=120, service=SERVICE)
        return cloud.trim(cloud.audio_pcm(data, service=SERVICE))
    return say


def design(description, line, n=3, label=None):
    """Every preview ElevenLabs makes (three) of `line`, repeated to the 100 characters the design needs."""
    text = line
    while len(text) < 100:
        text = f"{text} {line}"
    body = json.dumps({"voice_description": description[:1000], "text": text[:1000]}).encode()
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1/text-to-voice/design?output_format=pcm_24000",
                               _headers(), body, timeout=180, service=SERVICE, idempotent=False)
    answer = cloud.json_answer(data, SERVICE, "the design")
    words = answer.get("text") or text[:1000]
    out = []
    for preview in answer.get("previews") or []:
        audio = cloud.b64_audio(preview.get("audio_base_64"), SERVICE)
        if audio:
            pcm = cloud.trim(cloud.audio_pcm(audio, service=SERVICE))
            out.append({"pcm": pcm, "wav": cloud.wav_bytes(pcm), "text": words,
                        "draft_id": preview.get("generated_voice_id"), "signature": None})
    if not out:
        raise cloud.ServiceError("bad_request", SERVICE, "the design came back with no previews")
    return out


def save(candidate, name, description="", wav=None):
    """Save the preview as a voice in the listener's account; returns its voice ID."""
    body = json.dumps({"voice_name": f"sweatcast {name}", "voice_description": (description or "")[:1000],
                       "generated_voice_id": candidate["draft_id"]}).encode()
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1/text-to-voice", _headers(), body,
                               timeout=120, service=SERVICE, idempotent=False)
    voice_id = cloud.json_answer(data, SERVICE, cloud.saved_what(SERVICE, name)).get("voice_id")
    if not voice_id:
        raise cloud.ServiceError("bad_request", SERVICE, "the saved voice came back with no voice ID")
    return voice_id


def delete(voice_id):
    return cloud.delete(SERVICE, f"{cloud.base_url(SERVICE)}/v1/voices/{voice_id}",
                        {"xi-api-key": cloud.key_or_stop(SERVICE)})
