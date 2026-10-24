"""Coaches: each one a persona folder in me/personas/, owned by the listener.

    me/personas/coach-julius/
      persona.md     settings (name, aliases, description, one table per engine) and how the coach talks
      clip.wav       the sound: about ten seconds, which every engine copies
      clip.txt       the clip's exact words
      pace.json      measured pace, one entry per engine and model (and this computer's render speed)
      services.json  voice IDs a cloud service made from the clip, keyed by service and the clip's hash
      takes/         designed takes, before one is kept

A coach is the same person on every engine: render.py gets a voice dict from voice_for(), with
the clip, the engine's pinned model and the coach's own pace file, whichever route speaks it.
A coach made for Deepgram's stock voices only (stock_only = true) has no clip, and renders only there.
"""
import hashlib
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import context  # noqa: E402
import paths  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402

LOCAL_ENGINES = ("chatterbox", "qwen3")


def slug(name):
    """A folder name for a coach: ASCII, lowercase, words joined by hyphens ("Coach Zoë" -> coach-zoe)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"['’`]", "", ascii_name.lower())
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "coach"


@dataclass
class Persona:
    slug: str
    folder: str
    settings: dict
    prose: str

    @property
    def path(self):
        return os.path.join(self.folder, "persona.md")

    @property
    def name(self):
        return str(self.settings.get("name") or self.slug)

    @property
    def aliases(self):
        return [str(a) for a in self.settings.get("aliases") or []]

    @property
    def description(self):
        return str(self.settings.get("description") or "")

    @property
    def clip(self):
        return os.path.join(self.folder, "clip.wav")

    @property
    def clip_words(self):
        return os.path.join(self.folder, "clip.txt")

    @property
    def has_clip(self):
        return not self.settings.get("stock_only") and os.path.exists(self.clip) and os.path.exists(self.clip_words)

    @property
    def pace_file(self):
        return os.path.join(self.folder, "pace.json")

    @property
    def services_file(self):
        return os.path.join(self.folder, "services.json")

    @property
    def takes(self):
        return os.path.join(self.folder, "takes")

    def table(self, name):
        t = self.settings.get(name)
        return t if isinstance(t, dict) else {}


def load(folder):
    p = context.persona(os.path.join(folder, "persona.md"))
    return Persona(os.path.basename(folder), folder, p.settings, p.body)


def all(folder=None):
    """Every coach in me/personas/, by name."""
    folder = folder or paths.PERSONAS
    if not os.path.isdir(folder):
        return []
    found = [load(os.path.join(folder, d)) for d in os.listdir(folder)
             if os.path.exists(os.path.join(folder, d, "persona.md"))]
    return sorted(found, key=lambda p: p.name.lower())


def lookup(name, folder=None):
    """A coach by folder name, name or alias, in any case. Stops with the coaches there are on a miss."""
    found = all(folder)
    want = name.strip().lower()
    for p in found:
        if want in (p.slug, p.name.lower()) or p.slug == slug(name) or want in (a.lower() for a in p.aliases):
            return p
    there = ", ".join(p.name for p in found) or "none yet (the coach skill makes one)"
    raise SystemExit(f"No coach '{name}'. Coaches: {there} (in {show(folder or paths.PERSONAS)}).")


def clip_key(p):
    """The clip's identity in every pace and cache key: the same rule voices.lookup always used."""
    with open(p.clip, "rb") as a:
        audio_hash = hashlib.sha256(a.read()).hexdigest()
    with open(p.clip_words, encoding="utf-8") as t:
        words = t.read().strip()
    return hashlib.sha256(f"{audio_hash}|{words}".encode()).hexdigest()[:12], words


def clip_hash(p):
    """The clip's full sha256, which keys the voices a service made from it."""
    with open(p.clip, "rb") as a:
        return hashlib.sha256(a.read()).hexdigest()


def voice_for(p, route):
    """The voice dict render.py, the lint and the engines take, for coach `p` on `route`."""
    if route != "deepgram" and not p.has_clip:
        if p.settings.get("stock_only"):
            raise SystemExit(f"{p.name} has no clip of their own, only a Deepgram stock voice, so they render "
                             "only on Deepgram (--engine deepgram).")
        raise SystemExit(f"{p.name} has no clip yet ({show(p.clip)} and clip.txt): keep a take first "
                         "(./sweatcast coaches keep).")
    if route == "local":
        return _local(p)
    import cloud
    return cloud.voice_for(p, route)


def _local(p):
    local = p.table("local")
    engine = local.get("engine") or "chatterbox"
    if engine not in LOCAL_ENGINES:
        raise SystemExit(f"{show(p.path)}: [local] engine must be one of {', '.join(LOCAL_ENGINES)}.")
    backend = voices.BACKEND
    if (engine, backend) not in voices.LOCAL_MODELS:
        raise SystemExit(f"{p.name} speaks with {engine}, which renders locally only on an Apple Silicon Mac. "
                         f"On this computer: ./sweatcast coaches set \"{p.name}\" local.engine chatterbox, "
                         "or a cloud voice.")
    model, revision = voices.LOCAL_MODELS[(engine, backend)]
    if local.get("model"):   # a coach may try another model; its pace is then measured under that model
        model, revision = local["model"], local.get("revision")
    key, words = clip_key(p)
    gen = local.get("torch_generate" if backend == "torch" else "generate") or {}
    return {"name": p.name, "persona": p.slug, "engine": engine, "backend": backend, "route": "local",
            "model": model, "revision": revision, "generate": gen,
            "ref_audio": p.clip, "ref_text": words, "key": key, "pace_file": p.pace_file}


def _services(p):
    try:
        with open(p.services_file, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def services_get(p, service, clip):
    """The voice ID `service` made from this clip, or None (a changed clip needs a new one)."""
    entry = (_services(p).get(service) or {}).get(clip) or {}
    return entry.get("voice_id")


def services_put(p, service, clip, voice_id):
    import datetime as dt
    data = _services(p)
    data.setdefault(service, {})[clip] = {"voice_id": voice_id, "created": dt.date.today().isoformat()}
    tmp = p.services_file + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, p.services_file)
