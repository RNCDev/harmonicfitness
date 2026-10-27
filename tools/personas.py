"""Coaches: the ten local coaches sweatcast ships, and the listener's own web coaches.

    coaches/coach-maya-local/      (in the engine: one of the ten, chosen, never made by the listener)
      persona.md          settings (name, aliases, description, [voice], [character]); coaches/roster.toml makes it
      clip.wav, clip.txt  the voice it was made from, and its words
      pocket.safetensors  its Pocket TTS voice state, which every build speaks with
      cues/               its recorded counts and cues ([count 5 go], [cue rest]: tools/counts.py)
      pace.json           its pace, measured from its sample (this computer's renders add to it in voice-pace.json)
      sample.mp3          45 seconds of it, for choosing

    me/coaches/coach-jess-gemini/ (the listener's own: a web coach)

render.py gets a voice dict from voice_for(): a local coach's voice state, the pinned Pocket model and the
coach's pace file. A local coach renders only locally.

A web coach (kind = "web") has no clip: a voice a service designed and saved (service, voice_id, model,
style), which it speaks only through that service (cloud.voice_for), described by its [voice] table, with how
it talks in [character], and the approved audition kept as sample.mp3. Coaches no longer in use move to
coaches/.archive/ (out of the list, still found by name for old log lines); auditions in progress live in
coaches/.auditions/. Every dot folder is left out.
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
import counts  # noqa: E402
import paths  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402
import cli  # noqa: E402

LOCAL_ENGINES = ("pocket",)
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
    found = find(name, all(base))
    return found.folder if found else os.path.join(base, f"{slug(name)}-{where}")


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
        return [a.strip() for a in context.str_list(self.settings.get("aliases")) if a.strip()]

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
    def shipped(self):
        """One of the ten local coaches the engine ships (coaches/), not the listener's own."""
        return os.path.dirname(os.path.abspath(self.folder)) == os.path.abspath(paths.SHIPPED)

    @property
    def home_folder(self):
        """Where what's made for this coach is written: its own folder, or for a stock web coach
        me/coaches/<slug>/ (the voice made in the listener's account), which then wins over the stock copy."""
        return os.path.join(paths.PERSONAS, self.slug) if self.shipped else self.folder

    @property
    def voice_state(self):
        """A local coach's Pocket TTS voice, made once from its clip (tools/coachmaker/export_pocket.py)."""
        return os.path.join(self.folder, "pocket.safetensors")

    @property
    def pace_file(self):
        """Where renders record this coach's pace: beside it; for a stock local coach, the shared voice-pace.json
        beside the clip cache, so a build never writes into the engine and me/coaches/ holds only the
        listener's own coaches (the shipped pace.json is read until this computer's first render:
        voices._with_seed)."""
        if self.shipped and not self.is_web:
            return paths.PACE_FILE
        return os.path.join(self.home_folder, "pace.json")

    @property
    def shipped_pace(self):
        return os.path.join(self.folder, "pace.json")


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


def persona_dirs(folder):
    """The coach folders in `folder` (each holds a persona.md), sorted; dot folders (the archive, auditions)
    are left out. The one listing check and migrate use too."""
    if not os.path.isdir(folder):
        return []
    return sorted(d for d in os.listdir(folder)
                  if not d.startswith(".") and os.path.exists(os.path.join(folder, d, "persona.md")))


def find(name, pool):
    """The coach in `pool` that `name` means (a folder name, a name or an alias, in any case), or None."""
    return next((p for p in pool if _match(p, name)), None)


def _load_all(folder):
    found = []
    for d in persona_dirs(folder):
        try:
            found.append(load(os.path.join(folder, d)))
        except SystemExit as e:   # one coach file the tools can't read hides no other coach; check names it
            print(f"Skipped the coach in {show(os.path.join(folder, d))}: {e.code}", file=sys.stderr)
    return found


def all(folder=None):
    """Every coach, by name: the listener's own in me/coaches/ and, unless another folder is named, the ten the
    engine ships in coaches/ (a coach of the listener's own wins on a name clash). Dot folders (the archive,
    auditions) are left out."""
    found = _load_all(folder or paths.PERSONAS)
    if folder is None:
        names = {p.name.lower() for p in found}
        found += [p for p in _load_all(paths.SHIPPED) if p.name.lower() not in names]
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
    p = find(name, found)
    if p is not None:
        return p
    old = find(name, all(_archive(folder)))
    if old is not None and archived:
        return old
    there = ", ".join(p.name for p in found) or "none yet (the coach skill makes one)"
    if old is not None:
        raise SystemExit(f"{old.name} is archived. Coaches: {there} (in {show(folder or paths.PERSONAS)}).")
    raise UnknownCoach(f"No coach '{name}'. Coaches: {there} (in {show(folder or paths.PERSONAS)}).")


def archive(p):
    """Move coach `p` to coaches/.archive/ (out of the list, still found by lookup(archived=True)).
    Returns its new folder."""
    import shutil
    if p.shipped:
        raise SystemExit(f"{p.name} ships with sweatcast and can't be archived; just choose another coach.")
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
        p = find(session.voice, found)
        if p is not None:
            if p.placeholder:   # their own coach beats a stand-in used last, if it can speak here
                own = next((o for o in found if not o.placeholder and not o.shipped and _usable_here(o)), None)
                return own or p
            return p
        old = find(session.voice, archived)
        if old is not None:
            raise SystemExit(f"{old.name} is archived; name a coach: {', '.join(p.name for p in found)}.")
    own = next((p for p in found if not p.placeholder and not p.shipped), None)
    if own is not None:
        return own
    import cloud
    order = lambda p: (not p.is_web, cloud.SERVICES.index(p.service) if p.service in cloud.SERVICES else 99)
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


def resolve(coach=None, engine=None, pending=False):
    """The voice dict a build uses: `coach` (else the one used last) on `engine` (else the first route in the
    profile's render list that works on this computer). With `pending`, a web coach still to be made gets
    its estimated voice (the lint and the brief; never the render)."""
    import routes
    p = lookup(coach) if coach else default()
    if p is None:
        raise SystemExit("No coach yet: choose one (./sweatcast coaches lists them), or make a web coach (the coach skill).")
    return voice_for(p, routes.pick(context.render_preferences(), p, override=engine), pending)


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
    if not p.has_clip and p.shipped:
        raise SystemExit(f"{p.name} is missing its clip ({show(p.clip)}): update sweatcast (git pull).")
    return _local(p)


def _local(p):
    local = p.table("local")
    engine = local.get("engine") or "pocket"
    if engine not in LOCAL_ENGINES or not p.shipped:
        raise SystemExit(f"{p.name} is a local coach of your own ({show(p.folder)}), and since sweatcast 0.15.0 "
                         "local coaches are the ten it ships (./sweatcast coaches lists them; ./sweatcast migrate "
                         "archives older ones). A voice of your own is a web coach: the coach skill makes one.")
    if not os.path.exists(p.voice_state):
        raise SystemExit(f"{p.name} has no voice file ({show(p.voice_state)}): update sweatcast (git pull).")
    model, revision = voices.LOCAL_MODELS[engine]
    key, words = clip_key(p)
    return {"name": p.name, "persona": p.slug, "engine": engine, "backend": voices.BACKEND, "route": "local",
            "model": model, "revision": revision, "language": voices.POCKET_LANGUAGE, "generate": {},
            "voice_state": p.voice_state, "ref_audio": p.clip, "ref_text": words, "key": key,
            "pace_file": p.pace_file, "pace_seed": p.shipped_pace if p.shipped else None,
            "cues": counts.folder(p.clip)}
