"""Coaches: each one a persona folder in me/personas/, owned by the listener.

    me/personas/coach-julius/
      persona.md     settings (name, aliases, description, one table per engine) and how the coach talks
      clip.wav       the sound: about ten seconds, which every engine copies
      clip.txt       the clip's exact words
      pace.json      measured pace, one entry per engine and model (and this computer's render speed)
      takes/         designed takes, before one is kept

A local coach is the same person on every local engine: render.py gets a voice dict from voice_for(),
with the clip, the engine's pinned model and the coach's own pace file. A local coach renders only
locally.

A web coach (kind = "web", schema 5) has no clip: a voice a service designed and saved (service,
voice_id, model, style), which it speaks only through that service (cloud.voice_for), described by its [voice] table, with how it talks in [character], and the approved audition kept
as sample.mp3. Coaches no longer in use move to personas/.archive/ (out of the list, still found by name
for old log lines); auditions in progress live in personas/.auditions/. Every dot folder is left out.
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
import cli  # noqa: E402

LOCAL_ENGINES = ("chatterbox", "qwen3")
WEB_SERVICES = ("fish", "elevenlabs", "gemini", "inworld")   # the order web stand-ins are tried in
VOICE_PARTS = (("who", ""), ("sound", ""), ("energy", ""), ("pace", "Pace: "), ("avoid", "Avoid: "))


def slug(name):
    """A folder name for a coach: ASCII, lowercase, words joined by hyphens ("Coach Zoë" -> coach-zoe)."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"['’`]", "", ascii_name.lower())
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-") or "coach"


def folder_for(name, where, folder=None):
    """Where coach `name` lives: the folder of a coach already called that, else a new <slug>-<where>, where
    `where` is "local" or the web coach's service (coach-maya-fish, coach-sam-local)."""
    base = folder or paths.PERSONAS
    for p in all(base):
        if _match(p, name):
            return p.folder
    return os.path.join(base, f"{slug(name)}-{where}")


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
    def placeholder(self):
        """A stand-in coach (Coach Andy), used until the listener makes their own."""
        return bool(self.settings.get("placeholder"))

    @property
    def clip(self):
        return os.path.join(self.folder, "clip.wav")

    @property
    def clip_words(self):
        return os.path.join(self.folder, "clip.txt")

    @property
    def has_clip(self):
        return os.path.exists(self.clip) and os.path.exists(self.clip_words)

    @property
    def pace_file(self):
        return os.path.join(self.folder, "pace.json")

    @property
    def takes(self):
        return os.path.join(self.folder, "takes")

    def table(self, name):
        t = self.settings.get(name)
        return t if isinstance(t, dict) else {}

    @property
    def kind(self):
        """"web" (a voice a service designed) or "local" (a clip every engine copies)."""
        return str(self.settings.get("kind") or "local")

    @property
    def is_web(self):
        return self.kind == "web"

    def _text(self, key):
        v = self.settings.get(key)
        return str(v) if v not in (None, "") else None

    @property
    def service(self):
        return self._text("service")

    @property
    def voice_id(self):
        return self._text("voice_id")

    @property
    def model(self):
        """The service's model, or None for the default in knowledge/services.toml."""
        return self._text("model")

    @property
    def style(self):
        """Gemini only: a short constant style annotation, or empty."""
        return str(self.settings.get("style") or "")

    @property
    def pending(self):
        """What's still to do before this web coach can speak ("design"), or None."""
        return self._text("pending")

    @property
    def voice(self):
        """[voice]: what the services design or match from."""
        return self.table("voice")

    @property
    def character(self):
        """[character]: what the script writer follows."""
        return self.table("character")

    @property
    def sample(self):
        """The approved audition sample of a web coach."""
        return os.path.join(self.folder, "sample.mp3")


def load(folder):
    p = context.persona(os.path.join(folder, "persona.md"))
    return Persona(os.path.basename(folder), folder, p.settings, p.body)


def _archive(folder=None):
    return os.path.join(folder or paths.PERSONAS, ".archive")


def all(folder=None):
    """Every coach in me/personas/, by name; dot folders (the archive, auditions) are left out."""
    folder = folder or paths.PERSONAS
    if not os.path.isdir(folder):
        return []
    found = []
    for d in sorted(os.listdir(folder)):
        if d.startswith(".") or not os.path.exists(os.path.join(folder, d, "persona.md")):
            continue
        try:
            found.append(load(os.path.join(folder, d)))
        except SystemExit as e:   # one coach file the tools can't read hides no other coach; check names it
            print(f"Skipped the coach in {show(os.path.join(folder, d))}: {e.code}", file=sys.stderr)
    return sorted(found, key=lambda p: p.name.lower())


def _match(p, name):
    want = name.strip().lower()
    return (want in (p.slug, p.name.lower()) or slug(name) in (p.slug, slug(p.name))   # coach-maya finds coach-maya-fish
            or want in (a.lower() for a in p.aliases))


class UnknownCoach(cli.Usage):
    """No coach by that name, alias or folder (exit 64: the command named the wrong coach)."""


def lookup(name, folder=None, archived=False):
    """A coach by folder name, name or alias, in any case; with `archived`, the archive too (for names read
    from the log). Stops with the coaches there are on a miss."""
    found = all(folder)
    for p in found:
        if _match(p, name):
            return p
    old = next((p for p in all(_archive(folder)) if _match(p, name)), None)
    if old is not None and archived:
        return old
    there = ", ".join(p.name for p in found) or "none yet (the coach skill makes one)"
    if old is not None:
        raise SystemExit(f"{old.name} is archived. Coaches: {there} (in {show(folder or paths.PERSONAS)}).")
    raise UnknownCoach(f"No coach '{name}'. Coaches: {there} (in {show(folder or paths.PERSONAS)}).")


def archive(p):
    """Move coach `p` to personas/.archive/ (out of the list, still found by lookup(archived=True)).
    Returns its new folder."""
    import shutil
    base = os.path.join(os.path.dirname(p.folder), ".archive")
    dest, n = os.path.join(base, p.slug), 2
    while os.path.exists(dest):
        dest, n = os.path.join(base, f"{p.slug}-{n}"), n + 1
    os.makedirs(base, exist_ok=True)
    shutil.move(p.folder, dest)
    return dest


def _usable_here(p):
    """Whether stand-in `p` can speak on this computer: a web coach's service has a key, a local coach's
    engine runs here."""
    if p.is_web:
        import keys
        return bool(p.service) and p.service in keys.SERVICE_VARS and keys.is_set(p.service)
    import routes
    return routes.usable("local", p)[0]


def default(folder=None):
    """The coach a build uses when none is named: the one used last (from the log), stopping if that one
    is archived, and passing over a stand-in used last for a coach of the listener's own that can speak here; else the
    first that isn't a stand-in; else the first stand-in that can speak here (web ones whose service has a
    key, in service order, then local ones); else the first."""
    found = all(folder)
    if not found:
        return None
    archived = all(_archive(folder))
    try:
        sessions = list(reversed(context.sessions(warn=False)))
    except SystemExit:   # no log yet, or one in an older format
        sessions = []
    for session in sessions:
        for p in found:
            if _match(p, session.voice):
                if p.placeholder:   # their own coach beats a stand-in used last, if it can speak here
                    own = next((o for o in found if not o.placeholder and _usable_here(o)), None)
                    return own or p
                return p
        old = next((p for p in archived if _match(p, session.voice)), None)
        if old is not None:
            raise SystemExit(f"{old.name} is archived; name a coach: {', '.join(p.name for p in found)}.")
    own = next((p for p in found if not p.placeholder), None)
    if own is not None:
        return own
    order = lambda p: (not p.is_web, WEB_SERVICES.index(p.service) if p.service in WEB_SERVICES else 99)
    return next((p for p in sorted(found, key=order) if _usable_here(p)), found[0])


def voice_description(voice):
    """The design description a service gets, from a [voice] table: "{who}. {sound}. {energy}. Pace: {pace}.
    Avoid: {avoid}." (empty parts left out)."""
    parts = [(label, str(voice.get(key) or "").strip().rstrip(".")) for key, label in VOICE_PARTS]
    return " ".join(f"{label}{text}." for label, text in parts if text)


def web_key(p, model):
    """A web coach's identity in every pace and cache key: its service, voice, `model`, style and settings."""
    settings = json.dumps(p.table("settings"), sort_keys=True)
    raw = f"{p.service or ''}|{p.voice_id or ''}|{model}|{p.style}|{settings}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def last_coach(folder=None):
    """The coach a build uses when none is named (default()); None with no coaches."""
    return default(folder)


def resolve(coach=None, engine=None, pending=False):
    """The voice dict a build uses: `coach` (else the one used last) on `engine` (else the first route in the
    profile's render list that works on this computer). With `pending`, a web coach still to be made gets
    its estimated voice (the lint and the brief; never the render)."""
    import routes
    p = lookup(coach) if coach else default()
    if p is None:
        raise SystemExit("No coach yet: make one first (the coach skill, or ./sweatcast coaches design).")
    preferences = context.routes(context.profile()) if os.path.exists(paths.PROFILE) else ["local"]
    return voice_for(p, routes.pick(preferences, p, override=engine), pending)


def clip_key(p):
    """The clip's identity in every pace and cache key: the same rule voices.lookup always used."""
    with open(p.clip, "rb") as a:
        audio_hash = hashlib.sha256(a.read()).hexdigest()
    with open(p.clip_words, encoding="utf-8") as t:
        words = t.read().strip()
    return hashlib.sha256(f"{audio_hash}|{words}".encode()).hexdigest()[:12], words


def voice_for(p, route, pending=False):
    """The voice dict render.py, the lint and the engines take, for coach `p` on `route`. A web coach speaks
    through its own service whatever `route` says; a local coach only on the local route."""
    if p.is_web:
        import cloud
        return cloud.voice_for(p, p.service, pending)
    if route != "local":
        raise SystemExit(f"{p.name} is a local coach: a local coach renders only locally, not on {route}. "
                         "A web coach (the coach skill makes one) speaks through a web service.")
    if not p.has_clip:
        raise SystemExit(f"{p.name} has no clip yet ({show(p.clip)} and clip.txt): keep a take first "
                         "(./sweatcast coaches keep).")
    return _local(p)


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
