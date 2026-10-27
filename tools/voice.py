"""The voice a build speaks with, in its two shapes: a local coach's (LocalVoice, Pocket TTS from its voice file)
and a web coach's (WebVoice, a voice saved at a service). personas.voice_for and cloud.voice_for build one and
hand on as_dict(), the voice dict the lint, render, engines and records read; its keys and their order are the
contract (the clip cache key and the build record are made from it), so a field here is a key there, in order.
from_dict reads a voice dict back."""
from dataclasses import dataclass, field, fields
from typing import Optional


@dataclass(frozen=True, kw_only=True)
class LocalVoice:
    name: str
    persona: str
    engine: str
    backend: str
    route: str
    model: str
    revision: Optional[str]
    language: str
    generate: dict = field(default_factory=dict)
    voice_state: str
    ref_audio: str
    ref_text: str
    key: str
    pace_file: str
    pace_seed: Optional[str]
    cues: Optional[str]

    def as_dict(self):
        return _dict(self)


@dataclass(frozen=True, kw_only=True)
class WebVoice:
    name: str
    persona: str
    persona_dir: str
    engine: str
    backend: str
    route: str
    service: str
    model: str
    voice_id: Optional[str]
    style: str
    revision: Optional[str]
    generate: dict = field(default_factory=dict)
    pace_file: str
    concurrency: int
    max_chars: int
    key: str

    def as_dict(self):
        return _dict(self)


def _dict(v):
    """The voice dict, in field order; a fresh dict each time, since render adds to it (device, a model)."""
    return {f.name: dict(getattr(v, f.name)) if f.name == "generate" else getattr(v, f.name) for f in fields(v)}


def from_dict(d):
    """The LocalVoice or WebVoice a voice dict describes (a web voice's backend is "cloud"); keys render added
    after it was built (device) are left out."""
    cls = WebVoice if d.get("backend") == "cloud" else LocalVoice
    names = [f.name for f in fields(cls)]
    missing = [n for n in names if n not in d]
    if missing:
        raise ValueError(f"not a {cls.__name__} voice dict: no {', '.join(missing)}")
    return cls(**{n: d[n] for n in names})
