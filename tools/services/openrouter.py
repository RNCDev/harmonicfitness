"""OpenRouter: one key for many speech models. A coach here is one of their stock voices, chosen by ear, not
a voice designed from a description: OpenRouter can't design or save a voice, and can't reach a voice saved
in someone's own ElevenLabs or Fish account.

Speech: POST /api/v1/audio/speech {model, input, voice, response_format: "mp3"}, Bearer key; the answer is
the audio itself (an error is JSON under `error`). MP3 is asked for because OpenRouter doesn't say each
model's PCM rate; cloud.audio_pcm reads it through ffmpeg.
Voices: ElevenLabs' stock voices (elevenlabs/eleven-v4-turbo, the default since 0.46.2 at half the price, and
eleven-v4) and Microsoft's English MAI-Voice
voices (microsoft/mai-voice-2.1), from OpenRouter's model list on 2026-10-31. A coach's voice ID is the
voice's name; voice_model() names the model that speaks it, so an MAI voice is billed and keyed as MAI, and a
coach naming a model that can't speak its voice is refused.
Design: no request at all. The description picks the closest stock voices (gender, accent, age, a few
sound words), and each says the coaching line once: the audition is by ear, so the matching only steers.
Save: nothing to save; the voice ID is the candidate's. Delete: nothing to delete.
Balance: GET /api/v1/credits, {total_credits, total_usage} in US dollars.
Not yet tried live.
"""
import json
import re

import cloud

SERVICE = "openrouter"
SPEECH = "/api/v1/audio/speech"

ELEVEN = ("elevenlabs/eleven-v4-turbo", "elevenlabs/eleven-v4")   # the first speaks a voice whose coach names no model
MAI = ("microsoft/mai-voice-2.1",)

# name: (gender, accent, age, sound words), from each voice's listing; the audition settles it by ear.
VOICES = {
    "elevenlabs": {
        "george": ("m", "gb", "middle", "warm narration"), "sarah": ("f", "us", "young", "soft confident"),
        "adam": ("m", "us", "middle", "deep"), "alice": ("f", "gb", "middle", "confident clear"),
        "bella": ("f", "us", "young", "warm"), "bill": ("m", "us", "old", "trustworthy steady"),
        "brian": ("m", "us", "middle", "deep resonant warm"), "callum": ("m", "us", "middle", "husky intense"),
        "charlie": ("m", "au", "young", "natural confident"), "chris": ("m", "us", "middle", "casual friendly"),
        "daniel": ("m", "gb", "middle", "authoritative clear"), "eric": ("m", "us", "middle", "smooth calm"),
        "harry": ("m", "us", "young", "energetic intense"), "jessica": ("f", "us", "young", "playful bright"),
        "laura": ("f", "us", "young", "upbeat energetic"), "liam": ("m", "us", "young", "energetic"),
        "lily": ("f", "gb", "middle", "warm smooth"), "matilda": ("f", "us", "middle", "friendly warm"),
        "river": ("n", "us", "middle", "relaxed calm"), "roger": ("m", "us", "middle", "confident casual"),
        "will": ("m", "us", "young", "friendly relaxed"),
    },
    "mai": {f"en-{acc.upper()}-{name}:MAI-Voice-2.1": (g, acc, "middle", "") for name, g, acc in (
        ("Isla", "f", "au"), ("Emily", "f", "gb"), ("Harry", "m", "gb"), ("Dhruv", "m", "in"), ("Priya", "f", "in"),
        ("Ethan", "m", "us"), ("Grant", "m", "us"), ("Harper", "f", "us"), ("Iris", "f", "us"),
        ("Jasper", "m", "us"), ("Olivia", "f", "us"), ("Sage", "n", "us"))},
}
FAMILY_MODELS = {"elevenlabs": ELEVEN, "mai": MAI}

_WORDS = {
    "f": r"\b(woman|female|she|her|girl|lady)\b", "m": r"\b(man|male|he|his|guy)\b",
    "gb": r"\b(british|english|london|uk)\b", "au": r"\b(australian|aussie)\b", "in": r"\b(indian)\b",
    "us": r"\b(american|us)\b",
    "young": r"\b(young|twenties|early thirties)\b", "middle": r"\b(thirties|forties|fifties|middle)\b",
    "old": r"\b(older|sixties|seventies|elderly)\b",
}


def _family(voice_id):
    return next((f for f, names in VOICES.items() if voice_id in names), None)


def voice_model(voice_id):
    """The model that speaks stock voice `voice_id` when the coach names none (an MAI voice is MAI's)."""
    family = _family(voice_id)
    return FAMILY_MODELS[family][0] if family else None


# who makes each model's voices, for the web app's "OpenRouter, powered by ..."
MAKERS = {"elevenlabs/": "ElevenLabs", "microsoft/": "Microsoft MAI"}


def powered_by(model):
    """Who makes the voices `model` speaks ("ElevenLabs"), or None."""
    return next((who for prefix, who in MAKERS.items() if str(model or "").startswith(prefix)), None)


def _model(voice):
    """The coach's model, refused when it can't speak this voice (the cost, cache and pace would name the wrong
    one). voice_for gives a coach naming no model its voice's own."""
    family = _family(voice["voice_id"])
    if family is None:
        raise cloud.ServiceError("bad_request", SERVICE, f"{voice['voice_id']} isn't one of the stock voices "
                                                         "HarmonicFitness knows on OpenRouter")
    if voice.get("model") not in FAMILY_MODELS[family]:
        raise cloud.ServiceError("bad_request", SERVICE, f"the coach's model {voice.get('model')} can't speak "
                                 f"{voice['voice_id']}: remove model from its persona.md, or set it to one of "
                                 + ", ".join(FAMILY_MODELS[family]))
    return voice["model"]


def _score(description, facts):
    text = description.lower()
    gender, accent, age, sound = facts
    said = {k for k, pattern in _WORDS.items() if re.search(pattern, text)}
    wants = said & {"f", "m"}
    score = 0
    if wants:
        score += 3 if gender in wants else (-1 if gender == "n" else -5)
    accents = said & {"gb", "au", "in", "us"}
    if accents:
        score += 2 if accent in accents else -1
    if age in said:
        score += 1
    score += sum(1 for w in sound.split() if re.search(rf"\b{w}\b", text))
    return score


def match(description, n):
    """The `n` stock voices closest to `description`, best first: ElevenLabs' then one MAI voice when n > 1."""
    def ranked(family):
        names = list(VOICES[family])
        return sorted(names, key=lambda v: -_score(description, VOICES[family][v]))   # stable: listing order on ties
    n = max(1, int(n))
    eleven, mai = ranked("elevenlabs"), ranked("mai")
    return eleven[:n] if n == 1 else eleven[:n - 1] + mai[:1]


def _headers():
    return {"Authorization": f"Bearer {cloud.key_or_stop(SERVICE)}", "Content-Type": "application/json"}


def _speak(voice_id, model, text):
    body = json.dumps({"model": model, "input": text, "voice": voice_id, "response_format": "mp3"}).encode()
    _, headers, data = cloud.request("POST", cloud.base_url(SERVICE) + SPEECH, _headers(), body, timeout=120,
                                     service=SERVICE)
    return cloud.trim(cloud.audio_pcm(data, service=SERVICE, expect="mp3", content_type=cloud.content_type(headers)))


def speaker(voice):
    model = _model(voice)

    def say(text, seed, previous_text=None, next_text=None):
        return _speak(voice["voice_id"], model, text)
    return say


def design(description, line, n, label=None):
    """`n` stock voices close to `description`, each saying `line`. Nothing is made or stored at OpenRouter."""
    out = []
    for voice_id in match(description, n):
        pcm = _speak(voice_id, voice_model(voice_id), line)
        out.append({"pcm": pcm, "wav": cloud.wav_bytes(pcm), "text": line, "draft_id": voice_id, "signature": None})
    return out


def save(candidate, name=None, description=None, wav=None):
    """A stock voice needs no saving: its name is the voice ID."""
    return candidate["draft_id"]


def delete(voice_id):
    """Nothing to delete: a stock voice belongs to OpenRouter's catalog, not the listener's account."""
    return True


def balance():
    """{"usd": credits bought less credits used}: GET /api/v1/credits. One GET; nothing is spent."""
    _, _, data = cloud.request("GET", cloud.base_url(SERVICE) + "/api/v1/credits", _headers(), None, timeout=20,
                               service=SERVICE, deadline=30)
    answer = cloud.json_answer(data, SERVICE, "the credit balance").get("data")
    try:
        usd = float(answer["total_credits"]) - float(answer["total_usage"])
    except (TypeError, KeyError, ValueError):
        usd = None
    if usd is None or usd != usd:
        raise cloud.ServiceError("bad_request", SERVICE, "the credit balance couldn't be read")
    return {"usd": round(usd, 4)}
