"""Web coaches made by audition: candidates from every keyed service (audition), one kept as a coach
(keep_web), the audition closed (forget_audition). ./sweatcast coaches is the command; this is the library.

An audition reads a narrative file (persona.md's format: a +++ block with [voice], what the services design
from, and [character], what the script writer follows, then free notes) and lands in
me/coaches/.auditions/<date>-<n>/: each candidate as <service>-<k>.wav and .mp3, lettered A, B, C... in
service order, every one saying the same coaching line, with its cost per workout in candidates.json.
Fish, ElevenLabs and Inworld keep nothing until a candidate is kept; Gemini stores each voice as it
designs it, so forget-audition deletes the ones not kept.

Nothing here prints: what it says goes through `report` (progress; default `say`, printed) and `warn` (what
went wrong; default `stderr`), so a build or a test can take either.
"""
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import cloud  # noqa: E402
import context  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402

CANDIDATES = {s: v["candidates"] for s, v in cloud.services().items()}   # per audition, lettered in this order
WORKOUT_CHARS = 20000   # a workout's characters, for the cost a candidate is labeled with


def say(line):
    """What the coach tools say, by default: printed and flushed, so it lands in order with the render's output.
    make, keep_web and _run_audition take another `report` (a build passes its own)."""
    print(line, flush=True)


def stderr(line):
    """Where a warning goes, by default: what went wrong, on stderr (cli.run's rule for every failure)."""
    print(line, file=sys.stderr, flush=True)


def _auditions():
    return os.path.join(paths.PERSONAS, ".auditions")


def _narrative(path):
    """The narrative file as a context Persona (settings, body), refused without a [voice] to design from."""
    if not os.path.exists(path):
        raise errors.CoachError(f"No narrative at {path}.")
    n = context.persona(path)
    voice = n.settings.get("voice")
    if not isinstance(voice, dict) or not personas.voice_description(voice):
        raise errors.CoachError(f"{show(path)} has no [voice] to design from (who, sound, energy, pace, avoid).")
    return n


def _new_audition():
    base = _auditions()
    os.makedirs(base, exist_ok=True)
    today = datetime.date.today().isoformat()
    taken = [int(d[len(today) + 1:]) for d in os.listdir(base)
             if d.startswith(today + "-") and d[len(today) + 1:].isdigit()]
    n = max(taken, default=0) + 1
    while True:
        folder = os.path.join(base, f"{today}-{n}")
        try:
            os.makedirs(folder)
            return folder
        except FileExistsError:
            n += 1


def _reason(e):
    if isinstance(e, SystemExit):
        return cloud.scrub(str(e.code))
    return cloud.scrub(getattr(e, "message", None) or str(e) or type(e).__name__)


def _mp3(wav, mp3):
    """The candidate as an MP3 (mono, 48 kbps) to listen to; False when ffmpeg isn't here."""
    import ffmpeg
    exe = ffmpeg.exe()
    if not exe:
        return False
    try:
        ffmpeg.to_mp3(wav, mp3, "48k", path=exe)
    except errors.RenderStopped:   # a sample to listen to: the WAV is still there
        return False
    return True


def _write_sample(coach, wav, mp3=None, report=say):
    """The coach's sample.mp3: a copy of `mp3` if there is one, else made from the `wav` bytes."""
    sample = coach.sample
    if mp3 and os.path.exists(mp3):
        fileio.atomic_copy(mp3, sample)
        return
    part, part_mp3 = sample + ".part.wav", sample + ".part.mp3"
    try:
        fileio.atomic_write(part, wav)
        if _mp3(part, part_mp3):
            os.replace(part_mp3, sample)
        else:
            report("(No sample.mp3: ffmpeg isn't here to make one.)")
    finally:
        for leftover in (part, part_mp3):
            if os.path.exists(leftover):
                os.remove(leftover)


def _estimate(coach, service, wav, text):
    """The coach's pace estimate from its sample: weighted characters over the trimmed seconds."""
    pcm = cloud.trim(cloud.audio_pcm(wav, service=service))
    seconds = len(pcm) / 2 / cloud.SR
    if seconds > 0:
        voices.record_estimate(cloud.voice_for(coach, service), voices.weight(text), seconds)


def _write_candidates(folder, cands):
    fileio.atomic_write(os.path.join(folder, "candidates.json"), json.dumps(cands, indent=1) + "\n")


def _plain_file(name):
    """A file name with no folder in it (a candidate's WAV or MP3 sits in its audition's folder)."""
    return isinstance(name, str) and name not in ("", ".", "..") and os.path.basename(name) == name \
        and "/" not in name and "\\" not in name


def _read_candidates(folder):
    """The audition's candidates, refused (CoachError) unless each is a dict with a str letter, a known
    service, an int k and a plain WAV (and MP3) file name in the folder."""
    path = os.path.join(folder, "candidates.json")
    try:
        cands = fileio.read_json(path, shape=list)
    except OSError as e:
        raise errors.CoachError(f"{show(path)} can't be read ({e}).")
    except errors.ContextError as e:
        raise errors.CoachError(str(e))
    ok = isinstance(cands, list) and all(
        isinstance(c, dict) and isinstance(c.get("letter"), str) and c.get("service") in cloud.SERVICES
        and type(c.get("k")) is int and _plain_file(c.get("wav"))
        and (c.get("mp3") is None or _plain_file(c.get("mp3"))) for c in cands)
    if not ok:
        raise errors.CoachError(f"{show(path)} isn't an audition's candidates list (a letter, service, k and wav "
                                "for each); it was changed by hand, so nothing was done.")
    return cands


def _run_audition(narrative=None, services=None, coach=None, play=False, report=say, warn=stderr):
    """Design candidates on every keyed service (or `services`) in parallel. Returns (folder, candidates,
    failures as (service, error)); folder is None when no candidate landed. The failures are returned, not
    said: the caller says them (_failure_lines). With no key for any service, `warn` says so. A service's
    refusal, a stop the listener can fix or a file that won't write is a failure; anything else is a bug in
    the engine, and is raised (exit 70)."""
    import keys
    table = cloud.services()   # loaded once, before the threads
    revoice = None
    if coach:
        revoice = personas.lookup(coach)
        if not revoice.is_web or revoice.service not in CANDIDATES:
            raise errors.CoachError(f"{revoice.name} is a local coach: a web audition makes a new web coach "
                             "(audition a narrative without --coach).")
        if services and list(services) != [revoice.service]:
            raise errors.CoachError(f"{revoice.name} speaks on {cloud.service_name(revoice.service)}: a coach is re-voiced on "
                             "its own service only (leave out --services).")
        services = [revoice.service]
        narrative = narrative or revoice.path
    if not narrative:
        raise errors.CoachError("Name the narrative file to design from (or --coach for a coach's new voice).")
    n = _narrative(narrative)
    wanted = list(services) if services else list(CANDIDATES)
    unknown = [s for s in wanted if s not in CANDIDATES]
    if unknown:
        raise errors.CoachError(f"No web service {', '.join(unknown)}: the services are {', '.join(CANDIDATES)}.")
    wanted = [s for s in CANDIDATES if s in wanted]
    keyed = [s for s in wanted if keys.is_set(s)]
    for s in wanted:
        if s not in keyed and services:
            report(f"{cloud.service_name(s)}: no key here, skipped (./sweatcast keys).")
    if not keyed:
        warn("No web service has a key here, so there's nothing to audition on. Add one: ./sweatcast keys "
             "(then ./sweatcast keys init <service>).")
        return None, [], []

    folder = _new_audition()
    audition_id = os.path.basename(folder)
    planned, at = {}, 0
    for s in keyed:   # Gemini names its voice as it designs it, before any letter is final: the planned one
        planned[s] = chr(ord("A") + at)
        at += CANDIDATES[s]
    description = personas.voice_description(n.settings["voice"])
    for s in keyed:
        cost = table[s].get("design_usd")
        report(f"{table[s]['name']}: asking for {CANDIDATES[s]} candidate{'s' if CANDIDATES[s] > 1 else ''}, "
               + (f"design about ${cost:.2f}" if cost is not None else "design cost not published"))

    def design(service):
        module = cloud.service_module(service)
        return module.design(description, voices.DESIGN_LINE, CANDIDATES[service],
                             f"sweatcast audition {audition_id} {planned[service]}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(keyed)) as pool:
        futures = {s: pool.submit(design, s) for s in keyed}
    cands, failures, bugs = [], [], []
    for s in keyed:   # service order, whatever finished first
        try:
            made = futures[s].result()
        except (cloud.ServiceError, errors.SweatcastError, OSError) as e:
            failures.append((s, e))
            continue
        except Exception as e:   # a bug in the engine: raised once the other services' paid designs are kept
            bugs.append(e)
            continue
        usd = round(cloud.estimate(s, table[s]["default_model"], ["x" * WORKOUT_CHARS])[1], 4)
        for k, c in enumerate(made, 1):
            stem = f"{s}-{k}"
            fileio.atomic_write(os.path.join(folder, stem + ".wav"), c["wav"])   # as sent: Fish's save sends it back
            entry = {"letter": chr(ord("A") + len(cands)), "service": s, "k": k, "draft_id": c.get("draft_id"),
                     "signature": c.get("signature"), "text": c.get("text") or voices.DESIGN_LINE,
                     "wav": stem + ".wav", "mp3": None, "usd_per_workout": usd,
                     "design_usd": table[s].get("design_usd"), "note": table[s].get("note")}
            if revoice:
                entry["coach"] = revoice.name
            cands.append(entry)
    if not cands:
        shutil.rmtree(folder, ignore_errors=True)
    else:   # the designs are paid for: on disk before anything else can fail
        fileio.atomic_copy(narrative, os.path.join(folder, "narrative.md"))
        _write_candidates(folder, cands)
    if bugs:
        raise bugs[0]
    import ffmpeg
    have_ffmpeg = bool(ffmpeg.exe())
    if cands and have_ffmpeg:
        for c in cands:   # one that won't convert is one line; its WAV plays as well
            stem = os.path.splitext(c["wav"])[0]
            try:
                if _mp3(os.path.join(folder, c["wav"]), os.path.join(folder, stem + ".mp3")):
                    c["mp3"] = stem + ".mp3"
                else:
                    report(f"(no MP3 for {c['letter']}: ffmpeg failed; its WAV plays as well.)")
            except OSError as e:   # ffmpeg.run already turns its failures and hangs into a False
                report(f"(no MP3 for {c['letter']}: {e}; its WAV plays as well.)")
        _write_candidates(folder, cands)
    import player
    for c in cands:
        listen = os.path.join(folder, c["mp3"] or c["wav"])
        report(f"{c['letter']}  {table[c['service']]['name']:10}  about ${c['usd_per_workout']:.2f} a workout  "
               f"{show(listen)}" + (f"  ({c['note']})" if c["note"] else ""))
        if play and not player.play(listen):
            report("    (no audio player found here; open the file to listen)")
    if cands and not have_ffmpeg:
        report(f"(No MP3s: ffmpeg isn't here, {ffmpeg.install_hint()}; the WAVs play as well.)")
    return (folder if cands else None), cands, failures


def _failure_lines(failures):
    """One line per service that sent no candidates, and why."""
    return [f"{cloud.service_name(s)}: no candidates ({_reason(e)})" for s, e in failures]


def audition(narrative, services=None, coach=None, play=False, report=say, warn=stderr):
    """Candidates for a web coach from `narrative` (a persona.md-format file), one design per keyed service
    (or each of `services`), in parallel, each saying the coaching line; nothing saved. With `coach`, a new
    voice for that coach on its own service, from its own persona.md unless a narrative is given. Returns
    the audition folder."""
    folder, _, failures = _run_audition(narrative, services, coach, play, report, warn)
    if folder is not None:
        for line in _failure_lines(failures):
            report(line)
    if folder is None:
        raise errors.CoachError("No candidates: " + ("; ".join(f"{cloud.service_name(s)}: {_reason(e)}" for s, e in failures)
                                              or "no web service has a key here (./sweatcast keys)."))
    return folder


def _find_audition(ref):
    """The audition folder `ref` names (its id, or a path to it), or None. Only a folder directly inside
    the auditions folder counts, however the path is written: forget-audition removes what this returns."""
    base = os.path.realpath(_auditions())
    for guess in (os.path.join(base, ref), ref):   # by id; else a path as given (absolute, or from here)
        folder = os.path.realpath(guess)
        if os.path.dirname(folder) == base and os.path.isfile(os.path.join(folder, "candidates.json")):
            return folder
    return None


def _web_ref(ref):
    """(audition folder, candidate) for `<audition>/<letter>` or `<audition>/<service>-<k>` (the audition
    by id or path, inside the auditions folder; a .wav or .mp3 on the candidate is allowed), else None."""
    head, _, tail = ref.replace("\\", "/").rstrip("/").rpartition("/")
    if not head or not tail:
        return None
    tail = re.sub(r"\.(wav|mp3)$", "", tail, flags=re.IGNORECASE)
    folder = _find_audition(head)
    return (folder, tail) if folder else None


def _audition_folder(ref):
    folder = _find_audition(ref)
    if folder is None:
        raise errors.CoachError(f"No audition {ref} (in {show(_auditions())}).")
    return folder


def _resumable(c):
    """Whether candidate `c` was saved at its service but its coach never written (keep stopped between the
    two): a new coach with no persona.md, or a re-voiced coach still on the voice it replaces."""
    if not (c.get("kept") and c.get("voice_id")):
        return False
    try:
        coach = personas.lookup(c["kept"], archived=True)   # an archived coach was written: never resurrected
    except errors.PROBLEMS:
        return True
    if os.path.dirname(coach.folder) != paths.PERSONAS.rstrip(os.sep):
        return False
    return "replaces" in c and coach.voice_id == c["replaces"] and coach.voice_id != c["voice_id"]


def _existing(name):
    try:
        return personas.lookup(name)
    except errors.PROBLEMS:
        return None


def keep_web(ref, name, replace_old=False, report=say):
    """Save candidate `ref` (`<audition>/<letter>` or `<audition>/<service>-<k>`) at its service as
    "sweatcast <name>" and write the coach: persona.md (the narrative's [voice], [character] and notes,
    with kind, service, voice_id, made), sample.mp3 and a pace estimate. An audition made with --coach
    re-voices that coach: a new voice_id and sample, the old voice's pace dropped, and with `replace_old`
    the old voice deleted at the service. Returns the coach's folder."""
    found = _web_ref(ref)
    if not found:
        raise errors.CoachError(f"{ref} isn't a candidate in an audition: <audition>/<letter>, such as "
                         f"{datetime.date.today().isoformat()}-1/B.")
    folder, which = found
    cands = _read_candidates(folder)
    c = next((x for x in cands if which.lower() in (x["letter"].lower(), f"{x['service']}-{x['k']}")), None)
    if c is None:
        raise errors.CoachError(f"No candidate {which} in audition {os.path.basename(folder)}: "
                         f"{', '.join(x['letter'] for x in cands)}.")
    resume = _resumable(c)
    if c.get("kept") and not resume:
        raise errors.CoachError(f"Candidate {c['letter']} is already {c['kept']}.")
    if resume and name and personas.slug(name) != personas.slug(c["kept"]):
        raise errors.CoachError(f"Candidate {c['letter']} was saved as {c['kept']}; finish keeping it with --name "
                         f"\"{c['kept']}\".")
    name = (c["kept"] if resume else name) or c.get("coach")
    if not name:
        raise errors.CoachError("Give the coach a person's name: --name \"Coach Maya\".")
    existing = _existing(name)
    revoice = c.get("coach")
    if existing is None and not resume and os.path.exists(personas.folder_for(name, c["service"])):
        raise errors.CoachError(f"{show(personas.folder_for(name, c['service']))} is already there; pick another name.")
    revoiced = _existing(revoice) if revoice else None
    if existing is not None and (revoiced is None or revoiced.folder != existing.folder):
        raise errors.CoachError(f"There's already a coach called {existing.name}. Pick another name, or for a new voice "
                         f"for {existing.name}, audition with --coach \"{existing.name}\" and keep from that.")
    service = c["service"]
    if existing is not None and existing.service != service:
        raise errors.CoachError(f"{existing.name} speaks on {cloud.service_name(existing.service)}; candidate {c['letter']} is "
                         f"from {cloud.service_name(service)}. A coach is re-voiced on its own service only.")
    n = context.persona(os.path.join(folder, "narrative.md"))
    voice = n.settings.get("voice") or {}
    with open(os.path.join(folder, c["wav"]), "rb") as f:
        wav = f.read()
    candidate = {"wav": wav, "text": c["text"], "draft_id": c["draft_id"], "signature": c["signature"]}
    module = cloud.service_module(service)
    if resume:   # saved before, but the coach was never written: finish with the voice already saved
        voice_id = c["voice_id"]
        report(f"Finishing {name}: {c['letter']} is already saved at {cloud.service_name(service)}.")
    else:
        if c.get("saving") and not c.get("voice_id"):
            report(f"(An earlier keep of {c['letter']} sent a save to {cloud.service_name(service)} whose answer "
                   f"couldn't be read: if \"sweatcast {c['saving']}\" is there, this keep makes a second; delete one "
                   "there.)")
        report(f"Saving {c['letter']} at {cloud.service_name(service)} as \"sweatcast {name}\".")
        c["saving"] = name   # on disk before the save is sent: if its answer is lost, the audition still says so
        _write_candidates(folder, cands)
        voice_id = module.save(candidate, name, personas.voice_description(voice), wav)
        c.pop("saving", None)
        c.update(voice_id=voice_id, kept=name)   # recorded before any local write, so it's never lost
        if existing is not None:
            c["replaces"] = existing.voice_id
        _write_candidates(folder, cands)

    today = datetime.date.today().isoformat()
    if existing is not None and existing.shipped and not existing.is_web:
        raise errors.CoachError(f"{existing.name} is one of the local coaches sweatcast ships; give the web coach "
                         "another name.")
    if existing is not None:   # a new voice for a coach: how they talk stays (a stock coach's goes to me/coaches/)
        target, prose = existing.home_folder, existing.prose
        # a stand-in re-voiced is the listener's own choice now: no longer a placeholder
        settings = {k: v for k, v in existing.settings.items() if k not in ("schema", "pending", "placeholder")}
        settings.update(voice_id=voice_id, made=today, voice=voice)
        if existing.placeholder and str(settings.get("description", "")).startswith("A stand-in"):
            settings.pop("description", None)
            if n.settings.get("description") and not str(n.settings["description"]).startswith("A stand-in"):
                settings["description"] = n.settings["description"]
    else:
        target, prose = personas.folder_for(name, service), n.body
        settings = {"name": name, "aliases": [], "kind": "web", "service": service, "voice_id": voice_id,
                    "made": today}
        if n.settings.get("description"):
            settings["description"] = n.settings["description"]
        settings["voice"] = voice
        if isinstance(n.settings.get("character"), dict):
            settings["character"] = n.settings["character"]
    os.makedirs(target, exist_ok=True)
    coach = personas.Persona(os.path.basename(target), target, settings, prose)
    _write_sample(coach, wav, os.path.join(folder, c["mp3"]) if c.get("mp3") else None, report)
    if existing is not None and existing.voice_id:
        models = list(cloud.services()[service].get("models") or {}) + [existing.model or ""]
        for model in dict.fromkeys(m for m in models if m):
            voices.forget_pace(existing.pace_file, cloud.web_key(existing, model))
    _estimate(coach, service, wav, c["text"])
    fileio.atomic_write(coach.path, context.persona_text(settings, prose))   # last: all or nothing

    if existing is not None and existing.voice_id and replace_old:
        try:
            module.delete(existing.voice_id)
            report(f"Deleted {existing.name}'s old voice at {cloud.service_name(service)}.")
        except (cloud.ServiceError, *errors.PROBLEMS) as e:
            report(f"Couldn't delete the old voice at {cloud.service_name(service)} ({_reason(e)}); delete "
                   f"\"sweatcast {existing.name}\" there by hand.")
    report(f"Kept {name} ({cloud.service_name(service)}) in {show(target)}.")
    return target


def forget_audition(audition):
    """Close an audition: delete Gemini's stored voices that weren't kept, then the folder. Returns the lines
    said. If a Gemini voice won't delete, the folder stays so it can be tried again."""
    folder = _audition_folder(audition)
    cands = _read_candidates(folder)
    in_use = {p.voice_id for p in personas.all() + personas.all(os.path.join(paths.PERSONAS, ".archive"))
              if p.voice_id}
    lines = []
    def stores(service):   # a service that keeps a designed voice until it's deleted (Gemini)
        return getattr(cloud.service_module(service), "STORES_DRAFTS", False)

    for c in cands:   # a voice a coach uses (active or archived) is never deleted, kept mark or not
        if stores(c["service"]) and not c.get("kept") and c.get("draft_id") and c["draft_id"] not in in_use:
            name = cloud.service_name(c["service"])
            try:
                cloud.service_module(c["service"]).delete(c["draft_id"])
            except (cloud.ServiceError, *errors.PROBLEMS) as e:
                raise errors.CoachError(f"{name}: couldn't delete audition voice {c['letter']} ({_reason(e)}); the "
                                        f"audition stays in {show(folder)} so forget-audition can try again.")
            lines.append(f"Deleted {name}'s stored audition voice {c['letter']}.")
    for c in cands:   # a keep whose save went out but whose answer was lost: a voice may be there
        if c.get("saving") and not c.get("voice_id"):
            lines.append(f"{c['letter']}: a save was sent to {cloud.service_name(c['service'])} whose answer couldn't be "
                         f"read: look for \"sweatcast {c['saving']}\" there and delete it if it's not wanted.")
    others = list(dict.fromkeys(cloud.service_name(c["service"]) for c in cands
                                if not stores(c["service"]) and not c.get("kept") and not c.get("saving")))
    if others:
        lines.append(f"{', '.join(others)}: the unsaved drafts need nothing (nothing was saved there).")
    shutil.rmtree(folder)
    lines.append(f"Removed {show(folder)}.")
    return lines
