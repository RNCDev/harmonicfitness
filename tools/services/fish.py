"""Fish Audio: a web coach's voice is a private Fish model made from a designed candidate, and every
paragraph is spoken by that model's ID.

Design: POST /v1/voice-design, JSON {instruction, reference_text, language, n}, header
`model: voice-design-1` (about $0.01 a call). Each candidate carries a base64 WAV, the words it says
and a signature.
Save: POST /model, multipart: visibility=private, type=tts, title, train_mode=fast, texts (the
candidate's words), voice_design_signatures (its signature) and the candidate's own WAV as `voices`;
201 with the model's `_id`, already trained.
Speech: POST /v1/tts, JSON {text, reference_id, format: wav, sample_rate: 24000}, the speech model in a
`model` header. Fish streams WAV with placeholder sizes (cloud.wav_pcm reads to the end). Fish's speech
takes no seed, so a re-render is a new take; the clip cache keeps what's rendered.
Delete: DELETE /model/{id} (204).
Tried live 2026-10-25. Docs: docs.fish.audio/api-reference.
"""
import json

import cloud

SERVICE = "fish"
DESIGN_MODEL = "voice-design-1"


def _auth():
    return f"Bearer {cloud.key_or_stop(SERVICE)}"


def speaker(voice):
    url = cloud.base_url(SERVICE) + "/v1/tts"

    def say(text, seed, previous_text=None, next_text=None):
        body = json.dumps({"text": text, "reference_id": voice["voice_id"], "format": "wav",
                           "sample_rate": cloud.SR}).encode()
        headers = {"Authorization": _auth(), "model": voice["model"], "Content-Type": "application/json"}
        _, _, data = cloud.request("POST", url, headers, body, timeout=120, service=SERVICE)
        return cloud.trim(cloud.audio_pcm(data, service=SERVICE))
    return say


def design(description, line, n, label=None):
    """Up to `n` (at most 4) candidates of `line` in voices made from `description`. Each keeps the WAV Fish
    sent, since saving one sends that WAV back with its signature."""
    body = json.dumps({"instruction": description[:2000], "reference_text": line[:150], "language": "en",
                       "n": max(1, min(int(n), 4))}).encode()
    headers = {"Authorization": _auth(), "model": DESIGN_MODEL, "Content-Type": "application/json"}
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1/voice-design", headers, body, timeout=180,
                               service=SERVICE, idempotent=False)
    out = []
    for c in cloud.json_answer(data, SERVICE, "the design").get("candidates") or []:
        wav = cloud.b64_audio(c.get("audio_base64"), SERVICE)
        if wav:
            pcm = cloud.trim(cloud.audio_pcm(wav, int(c.get("sample_rate") or cloud.SR), service=SERVICE))
            out.append({"pcm": pcm, "wav": wav, "text": c.get("text") or line[:150],
                        "draft_id": c.get("id"), "signature": c.get("signature")})
    if not out:
        raise cloud.ServiceError("bad_request", SERVICE, "the design came back with no candidates")
    return out


def save(candidate, name, description=None, wav=None):
    """Make the candidate a private Fish model; returns its ID."""
    fields = {"visibility": "private", "type": "tts", "title": f"sweatcast {name}", "train_mode": "fast",
              "texts": candidate["text"], "voice_design_signatures": candidate.get("signature") or ""}
    body, ctype = cloud.multipart(fields, [("voices", "voice.wav", wav or candidate["wav"], "audio/wav")])
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/model",
                               {"Authorization": _auth(), "Content-Type": ctype}, body, timeout=180, service=SERVICE,
                               idempotent=False)
    voice_id = cloud.json_answer(data, SERVICE, cloud.saved_what(SERVICE, name)).get("_id")
    if not voice_id:
        raise cloud.ServiceError("bad_request", SERVICE, "the saved voice came back with no ID")
    return voice_id


def delete(voice_id):
    return cloud.delete(SERVICE, f"{cloud.base_url(SERVICE)}/model/{voice_id}", {"Authorization": _auth()})
