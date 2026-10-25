"""Inworld: a web coach's voice is a published Inworld voice made from a designed preview, and every
paragraph is spoken by its voice ID with the paragraph before it as context.

Design: POST /voices/v1/voices:design {designPrompt, previewText, languageCode: EN_US, numberOfSamples}
-> previewVoices[].{voiceId, previewText, previewAudio (base64 WAV)}. Two designs a minute: a 429 is
waited out (cloud.request honors Retry-After).
Save: POST /voices/v1/voices/{voiceId}:publish {displayName, description, tags: [sweatcast]} -> the same
voiceId.
Speech: POST /tts/v1/voice {text, voiceId, modelId, audioConfig: {audioEncoding: LINEAR16,
sampleRateHertz: 24000}, synthesisContext: {previousRequests: [{text: <previous paragraph>}]}} ->
base64 audioContent. 2,000 characters a request: a longer paragraph is refused before sending.
Delete: DELETE /voices/v1/voices/{id}.
The key goes as given: `Authorization: Basic <key>` (Inworld's key is already the encoded credential).
Tried live 2026-10-25.
"""
import base64
import json

import cloud

SERVICE = "inworld"
DESCRIPTION_CHARS = 1000


def _headers():
    return {"Authorization": f"Basic {cloud.key_or_stop(SERVICE)}", "Content-Type": "application/json"}


def speaker(voice):
    url = cloud.base_url(SERVICE) + "/tts/v1/voice"
    limit = int(voice.get("max_chars") or cloud.services()[SERVICE].get("max_chars") or 0)

    def say(text, seed, previous_text=None, next_text=None):
        if limit and len(text) > limit:
            raise cloud.ServiceError("bad_request", SERVICE, f"a paragraph of {len(text)} characters is over the "
                                                             f"{limit} a request takes; split it")
        body = {"text": text, "voiceId": voice["voice_id"], "modelId": voice["model"],
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": cloud.SR}}
        if previous_text:
            body["synthesisContext"] = {"previousRequests": [{"text": previous_text}]}
        _, _, data = cloud.request("POST", url, _headers(), json.dumps(body).encode(), timeout=120, service=SERVICE)
        audio = json.loads(data).get("audioContent")
        if not audio:
            raise cloud.ServiceError("bad_request", SERVICE, "the answer held no audio")
        return cloud.trim(cloud.audio_pcm(base64.b64decode(audio), service=SERVICE))
    return say


def design(description, line, n=2, label=None):
    """`n` previews of `line` in voices made from `description`, each keeping the WAV Inworld sent."""
    body = json.dumps({"designPrompt": description, "previewText": line, "languageCode": "EN_US",
                       "numberOfSamples": int(n)}).encode()
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/voices/v1/voices:design", _headers(), body,
                               timeout=180, service=SERVICE, idempotent=False)
    out = []
    for v in json.loads(data).get("previewVoices") or []:
        wav = base64.b64decode(v.get("previewAudio") or "")
        if wav:
            out.append({"pcm": cloud.trim(cloud.audio_pcm(wav, service=SERVICE)), "wav": wav,
                        "text": v.get("previewText") or line, "draft_id": v.get("voiceId"), "signature": None})
    if not out:
        raise cloud.ServiceError("bad_request", SERVICE, "the design came back with no previews")
    return out


def save(candidate, name, description="", wav=None):
    """Publish the preview to the listener's workspace; returns its voice ID."""
    draft = candidate["draft_id"]
    body = json.dumps({"displayName": f"sweatcast {name}", "description": (description or "")[:DESCRIPTION_CHARS],
                       "tags": ["sweatcast"]}).encode()
    _, _, data = cloud.request("POST", f"{cloud.base_url(SERVICE)}/voices/v1/voices/{draft}:publish", _headers(),
                               body, timeout=120, service=SERVICE, idempotent=False)
    try:
        answer = json.loads(data) if data else {}
    except ValueError:
        answer = {}
    nested = answer.get("voice") if isinstance(answer.get("voice"), dict) else {}
    return answer.get("voiceId") or nested.get("voiceId") or draft


def delete(voice_id):
    return cloud.delete(SERVICE, f"{cloud.base_url(SERVICE)}/voices/v1/voices/{voice_id}",
                        {"Authorization": f"Basic {cloud.key_or_stop(SERVICE)}"})
