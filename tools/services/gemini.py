"""Gemini: a web coach's voice is a stored Gemini voice, designed from a description and named at design
time; every paragraph is spoken by its ID through the interactions endpoint.

Design: POST /v1beta/voices {"voice": {"type": "prompted", "display_name", "prompted": {"input":
<description>}}, "store": true} (nothing else inside `prompted`) -> id, sample_audio, expire_time. The
candidate's audio is the coaching line spoken once by the new voice, like every other service's, not
the sample Gemini chose.
Save: nothing to send; the voice was stored at design, so its ID is the candidate's draft_id.
Speech: POST /v1beta/interactions {model, input: [{type: text, text}], response_modalities: [audio],
generation_config: {speech_config: [{voice: id}]}}; the base64 audio sits deep in the answer (under
steps[].content[] when tried live), so it's found by searching for a `data` string.
No style is sent: speech_metadata was refused in every placement when tried live (2026-10-25), and style
words are never added to the text. Key in `x-goog-api-key`.
Delete: DELETE /v1beta/voices/{id}, never for one of Gemini's own voices.
Gemini's own voices (its 30 prebuilt studio voices and its voice library's, listed by GET /v1beta/voices) speak by
their id the same way and belong to no account, so the ready-made Gemini coaches (coaches/roster.toml) use them
and ship made; nothing designs, stores or deletes them.
"""
import json
import sys

import cloud

SERVICE = "gemini"
STORES_DRAFTS = True   # design() saves each candidate; one not kept is deleted (coaches forget-audition)

# Gemini's 30 prebuilt studio voices (ai.google.dev/gemini-api/docs/speech-generation, 2026-10-31), by id
PREBUILT = ("zephyr", "puck", "charon", "kore", "fenrir", "leda", "orus", "aoede", "callirrhoe", "autonoe",
            "enceladus", "iapetus", "umbriel", "algieba", "despina", "erinome", "algenib", "rasalgethi", "laomedeia",
            "achernar", "alnilam", "schedar", "gacrux", "pulcherrima", "achird", "zubenelgenubi", "vindemiatrix",
            "sadachbia", "sadaltager", "sulafat")


def own_voice(voice_id):
    """Whether `voice_id` is one of Gemini's own voices (a prebuilt one, or the voice library's, whose ids hold a
    language code: en-gb-tutor-16), not one designed and stored in an account (voice_...)."""
    v = str(voice_id or "").lower()
    return v in PREBUILT or (len(v) > 6 and v[2] == "-" and v[5] == "-" and v[:2].isalpha() and v[3:5].isalpha())


def _headers():
    return {"x-goog-api-key": cloud.key_or_stop(SERVICE), "Content-Type": "application/json"}


def _speak(voice_id, model, text):
    body = json.dumps({"model": model, "input": [{"type": "text", "text": text}], "response_modalities": ["audio"],
                       "generation_config": {"speech_config": [{"voice": voice_id}]}}).encode()
    _, headers, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1beta/interactions", _headers(), body,
                                     timeout=120, service=SERVICE)
    try:
        answer = json.loads(data)
    except ValueError:   # audio itself, not JSON: raw 16-bit PCM (what Gemini speaks) only if it's typed as audio
        return cloud.trim(cloud.audio_pcm(data, service=SERVICE, expect="pcm",
                                          content_type=cloud.content_type(headers)))
    audio, mime = cloud.find_audio(answer)
    if not audio:
        raise cloud.ServiceError("bad_request", SERVICE, "the answer held no audio")
    return cloud.trim(cloud.audio_pcm(cloud.b64_audio(audio, SERVICE), cloud.mime_rate(mime), service=SERVICE,
                                      expect="pcm", content_type=cloud.content_type({"Content-Type": mime})))


def speaker(voice):
    def say(text, seed, previous_text=None, next_text=None):
        return _speak(voice["voice_id"], voice["model"], text)
    return say


def design(description, line, n=1, label=""):
    """One candidate: a stored voice named `label`, saying `line`. If speaking the line fails, the stored
    voice is deleted (if it can be) and that failure is raised (never a different line)."""
    body = json.dumps({"voice": {"type": "prompted", "display_name": label, "prompted": {"input": description}},
                       "store": True}).encode()
    _, _, data = cloud.request("POST", cloud.base_url(SERVICE) + "/v1beta/voices", _headers(), body, timeout=180,
                               service=SERVICE, idempotent=False)
    voice_id = cloud.json_answer(data, SERVICE, "the design (a voice may be stored there: look for \"" + str(label)
                                 + "\")").get("id")
    if not voice_id:
        raise cloud.ServiceError("bad_request", SERVICE, "the design came back with no voice ID")
    try:
        pcm = _speak(voice_id, cloud.services()[SERVICE]["default_model"], line)
    except BaseException:
        try:
            delete(voice_id)
        except Exception:   # the speech's failure is the one to raise; the voice is named
            print(f"(Gemini keeps a voice \"{label}\", ID {voice_id}: delete it there by hand.)", file=sys.stderr)
        raise
    return [{"pcm": pcm, "wav": cloud.wav_bytes(pcm), "text": line, "draft_id": voice_id, "signature": None}]


def save(candidate, name=None, description=None, wav=None):
    """The voice was stored at design: its ID is the candidate's."""
    return candidate["draft_id"]


def delete(voice_id):
    if own_voice(voice_id):   # Gemini's own voice: nothing of the listener's to delete
        return True
    return cloud.delete(SERVICE, f"{cloud.base_url(SERVICE)}/v1beta/voices/{cloud.path_part(voice_id)}",
                        {"x-goog-api-key": cloud.key_or_stop(SERVICE)})
