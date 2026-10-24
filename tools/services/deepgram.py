"""Deepgram Aura-2: stock voices only, so the coach's clip doesn't travel here and the coach sounds
different. The coach's persona names the stock voice ([deepgram] voice), picked from samples.

Speech: POST /v1/speak?model=<voice>&encoding=linear16&sample_rate=24000&container=none (raw PCM; the
default container would be WAV), `Authorization: Token <key>`, JSON {text}; 2,000 characters a request.
No seed, and no joining between paragraphs.
Not yet tried live: built against a local fake of the documented API (developers.deepgram.com).
"""
import json
import urllib.parse

import cloud

SERVICE = "deepgram"


def _speak(text, model):
    limit = int(cloud.services()[SERVICE].get("max_chars") or 0)
    if limit and len(text) > limit:
        raise cloud.ServiceError("bad_request", SERVICE, f"a paragraph of {len(text)} characters is over the "
                                                         f"{limit} a request takes; split it")
    query = urllib.parse.urlencode({"model": model, "encoding": "linear16", "sample_rate": cloud.SR,
                                    "container": "none"})
    headers = {"Authorization": f"Token {cloud.key_or_stop(SERVICE)}", "Content-Type": "application/json"}
    _, _, data = cloud.request("POST", f"{cloud.base_url(SERVICE)}/v1/speak?{query}", headers,
                               json.dumps({"text": text}).encode(), timeout=120, service=SERVICE)
    return cloud.trim(cloud.audio_pcm(data, service=SERVICE))


def speaker(voice):
    def say(text, seed, previous_text=None, next_text=None):
        return _speak(text, voice["model"])
    return say


def samples(line, voices):
    """[(voice, PCM)]: `line` in each stock voice, for the listener to pick one."""
    return [(v, _speak(line, v)) for v in voices]
