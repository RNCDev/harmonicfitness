"""A pending stock web coach made the first time it's used: one voice designed from its [voice] on its own
service, the first candidate saved with no audition, and the coach written to me/coaches/<slug>/
(./sweatcast coaches make, or the first build that needs it).

Nothing here prints: progress goes through `report` and the notices about a voice left at a service through
`warn` (default: stderr). A build passes both, so a notice reaches the listener's terminal, not only its log.
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audition  # noqa: E402
import errors  # noqa: E402
import cloud  # noqa: E402
import context  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402
from audition import CANDIDATES, say, stderr, _estimate, _write_sample  # noqa: E402
from paths import show  # noqa: E402

MADE = ".made.json"   # in a coach's folder while make is between saving a voice and writing persona.md
MADE_WAV = ".made.wav"


def _record_made(folder, service, voice_id, text, wav):
    """Record a voice make just saved, before any local write, so a failed make resumes from it."""
    fileio.atomic_write(os.path.join(folder, MADE_WAV), wav)
    fileio.atomic_write(os.path.join(folder, MADE), json.dumps(
        {"service": service, "voice_id": voice_id, "text": text}, indent=1) + "\n")


def _made(folder, service):
    """(voice_id, text, wav) a failed make saved for this coach on `service`, else None."""
    try:
        with open(os.path.join(folder, MADE), encoding="utf-8") as f:
            rec = json.load(f)
        with open(os.path.join(folder, MADE_WAV), "rb") as f:
            wav = f.read()
    except (OSError, ValueError):
        return None
    if rec.get("service") != service or not rec.get("voice_id"):
        return None
    return rec["voice_id"], rec.get("text") or voices.DESIGN_LINE, wav


def _made_description(text):
    """A default's description once it's made: without "Made the first time it's used"."""
    return re.sub(r"\s*Made the first time it's used; make", " Make", text or "").strip()


def make(name, report=say, warn=stderr):
    """Make a pending web coach (a default that ships with no voice): design one voice from its [voice] on
    its own service, save the first candidate with no audition, and write voice_id, made, sample.mp3 and a
    pace estimate, persona.md last. Says so (and what it costs) first. Returns the voice ID. A failure
    leaves persona.md as it was, still pending; when a voice was already saved (or stored) at the service,
    `warn` says so, with its ID and what to do (a build passes a `warn` that reaches the terminal).

    One make at a time (a lock in the coaches folder): a design is paid for, and two builds started
    together would each make one. The second finds the coach made once the first is done, and returns
    its voice ID."""
    p = personas.lookup(name)
    if not p.is_web or not p.pending:
        raise errors.CoachError(f"{p.name} is already made: nothing to design.")
    with locks.file_lock(os.path.join(paths.PERSONAS, ".make")):
        p = personas.lookup(p.name)   # again, under the lock: another make may have finished it
        if not p.pending:
            return p.voice_id
        return _make(p, report, warn)


def _make(p, report, warn=stderr):
    description = personas.voice_description(p.voice)
    if not description:
        raise errors.CoachError(f"{show(p.path)} has no [voice] to design from (who, sound, energy, pace, avoid).")
    service = p.service
    table = cloud.services()
    if service not in table or service not in CANDIDATES:
        raise errors.CoachError(f"{p.name} names no known web service ({service or 'none'}).")
    s = table[service]
    cost = (f"about ${s['design_usd']:.2f}" if s.get("design_usd") is not None else "design cost not published")
    module = cloud.service_module(service)
    if getattr(module, "DESIGN_NOTE", ""):   # what else a design costs there (ElevenLabs: a voice slot)
        cost += "; " + module.DESIGN_NOTE
    home = p.home_folder   # a stock coach's made voice goes to me/coaches/<slug>/, never into the engine
    os.makedirs(home, exist_ok=True)
    saved = _made(home, service)
    if saved:   # an earlier make saved the voice but stopped before persona.md: finish with it
        voice_id, text, wav = saved
        c, recorded = {}, True
        report(f"Finishing {p.name}: its voice is already saved at {s['name']}.")
    else:
        report(f"{p.name} is made the first time it's used: designing a voice at {s['name']} from its "
               f"description ({cost}).")
        c = module.design(description, voices.DESIGN_LINE, 1, f"sweatcast {p.name}")[0]
        voice_id, text, wav, recorded = None, c.get("text") or voices.DESIGN_LINE, c["wav"], False
    try:
        if not recorded:
            voice_id = module.save(c, p.name, description, wav)
            _record_made(home, service, voice_id, text, wav)
            recorded = True
        settings = {k: v for k, v in p.settings.items() if k not in ("schema", "pending")}
        settings.update(voice_id=voice_id, made=datetime.date.today().isoformat())
        if settings.get("description"):
            settings["description"] = _made_description(settings["description"])
        coach = personas.Persona(p.slug, home, settings, p.prose)
        _write_sample(coach, wav, report=report)
        _estimate(coach, service, wav, text)
        fileio.atomic_write(coach.path, context.persona_text(settings, p.prose))   # last: all or nothing
    except BaseException:
        if recorded:   # the voice is recorded in the coach's folder: the next make finishes with it
            warn(f"{p.name}'s voice is saved at {s['name']} (voice ID {voice_id}) but the coach wasn't written; "
                 "it's still pending, and the next build (or ./sweatcast coaches make) finishes it without "
                 "designing again.")
        elif getattr(module, "STORES_DRAFTS", False) and c.get("draft_id"):   # stored at design: don't leave it
            try:
                module.delete(c["draft_id"])
            except Exception:   # cleanup only: what stopped the make is raised below either way
                warn(f"({s['name']} keeps a voice \"sweatcast {p.name}\", ID {c['draft_id']}; delete it there "
                     "by hand.)")
        elif voice_id:
            warn(f"{p.name}'s voice was saved at {s['name']} (voice ID {voice_id}) but the coach wasn't written; "
                 f"it's still pending. Delete \"sweatcast {p.name}\" there, or put voice_id = \"{voice_id}\" "
                 f"in {show(os.path.join(home, 'persona.md'))}.")
        raise
    for done in (MADE, MADE_WAV):
        if os.path.exists(os.path.join(home, done)):
            os.remove(os.path.join(home, done))
    report(f"Made {p.name} ({s['name']}): a stand-in until you make your own (\"I want a new coach\").")
    return voice_id
