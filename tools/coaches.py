"""Coaches: choose one of the coaches sweatcast ships, or audition a web coach and keep the one that sounds
right; measure and tune them.

A coach is a persona folder (tools/personas.py): a person's name, how they talk, and how they sound. The ten
local coaches ship in coaches/ (a clip, its Pocket TTS voice file, recorded counts and cues, a sample); they're
chosen, not made. A web coach is a voice a service designed and saved (Fish Audio, ElevenLabs, Gemini, Inworld,
with the listener's key), kept in me/coaches/.

    ./sweatcast coaches                                   # every coach and where it speaks, the last used marked
    ./sweatcast coaches audition maya.md                  # candidates from every keyed service, nothing saved
    ./sweatcast coaches audition maya.md --services fish,gemini
    ./sweatcast coaches audition --coach "Coach Maya"     # a new voice for a coach, on its own service
    ./sweatcast coaches keep 2026-10-25-1/B --name "Coach Maya"   # save B at its service as the coach
    ./sweatcast coaches keep 2026-10-26-1/A --name "Coach Maya" --replace-old   # re-voice; delete the old voice
    ./sweatcast coaches forget-audition 2026-10-25-1      # close an audition (Gemini's unkept voices deleted)
    ./sweatcast coaches make "Coach Reed"                 # a pending default: design and save its voice (builds do)
    ./sweatcast coaches archive "Coach Julius"            # out of the list, still found for old log lines
    ./sweatcast coaches last                              # the coach a build uses when none is named
    ./sweatcast coaches measured "Coach Maya" --engine local   # exit 0 measured, 1 estimated, 64 unknown
    ./sweatcast coaches download                          # the local voice and the take checker (setup does it)

An audition reads a narrative file (persona.md's format: a +++ block with [voice], what the services design
from, and [character], what the script writer follows, then free notes) and lands in
me/coaches/.auditions/<date>-<n>/: each candidate as <service>-<k>.wav and .mp3, lettered A, B, C... in
service order, every one saying the same coaching line, with its cost per workout in candidates.json.
Fish, ElevenLabs and Inworld keep nothing until a candidate is kept; Gemini stores each voice as it
designs it, so forget-audition deletes the ones not kept.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import errors  # noqa: E402
import cloud  # noqa: E402
import context  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
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


def _clip_bytes(src):
    """The clip as a 16-bit mono 24 kHz WAV: the file itself when it already is one (so its key stays the
    same), else converted (a 16-bit WAV in pure Python, anything else through ffmpeg). A clip someone brings
    is never taken as raw PCM: an M4A or any format not recognised by its first bytes goes through ffmpeg."""
    with open(src, "rb") as f:
        data = f.read()
    try:
        with wave.open(src) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2):
                return data
    except (wave.Error, EOFError):
        pass
    if data[:4] == b"RIFF":
        try:
            pcm, rate = cloud.wav_pcm(data)
            return cloud.wav_bytes(cloud.resample(pcm, rate, cloud.SR))
        except ValueError:   # a WAV this reader doesn't handle (24-bit, float): ffmpeg does
            pass
    return cloud.wav_bytes(cloud.ffmpeg_pcm(data, f"The clip {os.path.basename(src)} isn't a WAV"))


# --- Web coaches: audition, keep, forget-audition, archive ---------------------------------------------------

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
    done = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", wav, "-ac", "1",
                           "-c:a", "libmp3lame", "-b:a", "48k", mp3], capture_output=True, text=True, timeout=120)
    return done.returncode == 0


def _write_sample(coach, wav, mp3=None, report=say):
    """The coach's sample.mp3: a copy of `mp3` if there is one, else made from the `wav` bytes."""
    sample = coach.sample
    if mp3 and os.path.exists(mp3):
        shutil.copyfile(mp3, sample + ".part")
        os.replace(sample + ".part", sample)
        return
    part, part_mp3 = sample + ".part.wav", sample + ".part.mp3"
    with open(part, "wb") as f:
        f.write(wav)
    try:
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
        with open(path, encoding="utf-8") as f:
            cands = json.load(f)
    except (OSError, ValueError) as e:
        raise errors.CoachError(f"{show(path)} can't be read ({e}).")
    ok = isinstance(cands, list) and all(
        isinstance(c, dict) and isinstance(c.get("letter"), str) and c.get("service") in cloud.SERVICES
        and type(c.get("k")) is int and _plain_file(c.get("wav"))
        and (c.get("mp3") is None or _plain_file(c.get("mp3"))) for c in cands)
    if not ok:
        raise errors.CoachError(f"{show(path)} isn't an audition's candidates list (a letter, service, k and wav "
                                "for each); it was changed by hand, so nothing was done.")
    return cands


def _run_audition(narrative=None, services=None, coach=None, play=False, report=say):
    """Design candidates on every keyed service (or `services`) in parallel. Returns (folder, candidates,
    failures as (service, error)); folder is None when no candidate landed. The failures are returned, not
    said: the caller says them (_failure_lines)."""
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
        print("No web service has a key here, so there's nothing to audition on. Add one: ./sweatcast keys "
              "(then ./sweatcast keys init <service>).", file=sys.stderr)
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
    cands, failures = [], []
    for s in keyed:   # service order, whatever finished first
        try:
            made = futures[s].result()
        except (Exception, cli.Usage) as e:
            failures.append((s, e))
            continue
        usd = round(cloud.estimate(s, table[s]["default_model"], ["x" * WORKOUT_CHARS])[1], 4)
        for k, c in enumerate(made, 1):
            stem = f"{s}-{k}"
            with open(os.path.join(folder, stem + ".wav"), "wb") as f:
                f.write(c["wav"])   # as the service sent it: Fish's save sends this WAV back
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
        shutil.copyfile(narrative, os.path.join(folder, "narrative.md"))
        _write_candidates(folder, cands)
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
            except (subprocess.SubprocessError, OSError) as e:
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


def audition(narrative, services=None, coach=None, play=False, report=say):
    """Candidates for a web coach from `narrative` (a persona.md-format file), one design per keyed service
    (or each of `services`), in parallel, each saying the coaching line; nothing saved. With `coach`, a new
    voice for that coach on its own service, from its own persona.md unless a narrative is given. Returns
    the audition folder."""
    folder, _, failures = _run_audition(narrative, services, coach, play, report)
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
            voices.forget_pace(existing.pace_file, personas.web_key(existing, model))
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


MADE = ".made.json"   # in a coach's folder while make is between saving a voice and writing persona.md
MADE_WAV = ".made.wav"


def _record_made(folder, service, voice_id, text, wav):
    """Record a voice make just saved, before any local write, so a failed make resumes from it."""
    with open(os.path.join(folder, MADE_WAV + ".part"), "wb") as f:
        f.write(wav)
    os.replace(os.path.join(folder, MADE_WAV + ".part"), os.path.join(folder, MADE_WAV))
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


def make(name, report=say):
    """Make a pending web coach (a default that ships with no voice): design one voice from its [voice] on
    its own service, save the first candidate with no audition, and write voice_id, made, sample.mp3 and a
    pace estimate, persona.md last. Says so (and what it costs) first. Returns the voice ID. A failure
    leaves persona.md as it was, still pending.

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
        return _make(p, report)


def _make(p, report):
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
            print(f"{p.name}'s voice is saved at {s['name']} but the coach wasn't written; "
                  "it's still pending, and the next build (or ./sweatcast coaches make) finishes it without "
                  "designing again.", file=sys.stderr)
        elif getattr(module, "STORES_DRAFTS", False) and c.get("draft_id"):   # stored at design: don't leave it
            try:
                module.delete(c["draft_id"])
            except (Exception, cli.Usage):
                print(f"({s['name']} keeps a voice \"sweatcast {p.name}\", ID {c['draft_id']}; delete it there "
                      "by hand.)", file=sys.stderr)
        elif voice_id:
            print(f"{p.name}'s voice was saved at {s['name']} (voice ID {voice_id}) but the coach wasn't written; "
                  f"it's still pending. Delete \"sweatcast {p.name}\" there, or put voice_id = \"{voice_id}\" "
                  f"in {show(os.path.join(home, 'persona.md'))}.", file=sys.stderr)
        raise
    for done in (MADE, MADE_WAV):
        if os.path.exists(os.path.join(home, done)):
            os.remove(os.path.join(home, done))
    report(f"Made {p.name} ({s['name']}): a stand-in until you make your own (\"I want a new coach\").")
    return voice_id


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


def _value(text):
    low = text.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(text)
    except ValueError:
        return text


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast coaches", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="every coach (the default)")
    sub.add_parser("last", help="the coach a build uses when none is named: the one used last (your own over a stand-in)")
    m = sub.add_parser("measured", help="exit 0 if the coach's pace is measured on the route, 1 if estimated, 64 unknown")
    m.add_argument("coach")
    m.add_argument("--engine", default=None, help="the route (default: the profile's render list)")
    a = sub.add_parser("audition", help="candidates for a web coach from every keyed service; nothing saved")
    a.add_argument("narrative", nargs="?", help="the coach narrative: persona.md's format, with [voice]")
    a.add_argument("--services", help=f"only these, comma-separated ({', '.join(CANDIDATES)})")
    a.add_argument("--coach", help="a new voice for this web coach, on its own service")
    a.add_argument("--play", action="store_true", help="play each candidate with the system's player")
    k = sub.add_parser("keep", help="keep an audition's candidate as a web coach (<audition>/<letter>)")
    k.add_argument("take", help="<audition>/<letter> or <audition>/<service>-<k>")
    k.add_argument("--name", help="the coach's name (a new web coach needs one; default: the take's)")
    k.add_argument("--replace-old", action="store_true",
                   help="re-voicing: delete the coach's old voice at its service")
    mk = sub.add_parser("make", help="make a pending web coach: design its voice and save the first candidate")
    mk.add_argument("coach")
    f = sub.add_parser("forget-audition", help="close an audition: Gemini's unkept voices deleted, the folder removed")
    f.add_argument("audition", help="its id (such as 2026-10-25-1) or folder")
    r = sub.add_parser("archive", help="move a coach out of the list (old log lines still find them)")
    r.add_argument("coach")
    s = sub.add_parser("set", help="set one of a coach's settings: <table>.<key> <value>")
    s.add_argument("coach")
    s.add_argument("setting", help="for example elevenlabs.model, or description")
    s.add_argument("value")
    sub.add_parser("download", help="fetch the local voice (Pocket TTS) and the take checker (setup does it)")
    args = ap.parse_args(argv)

    if args.cmd == "last":
        try:
            p = personas.default()
        except errors.PROBLEMS as e:   # the coach used last is archived
            print(e.code, file=sys.stderr)
            return cli.ISSUES
        if not p:
            print("No coach yet.", file=sys.stderr)
            return cli.ISSUES
        print(p.name)
        return cli.OK
    if args.cmd == "measured":
        import routes
        p = personas.lookup(args.coach)
        if p.is_web:   # a web coach needs no smoke test (made or pending): an estimate stands until its first render
            return cli.OK
        route = routes.pick(context.render_preferences(), p, override=args.engine)
        v = personas.voice_for(p, route)
        return cli.OK if voices.pace(v)[1] else cli.ISSUES
    if args.cmd == "audition":
        wanted = [x.strip() for x in args.services.split(",") if x.strip()] if args.services else None
        folder, cands, failures = _run_audition(args.narrative, wanted, args.coach, args.play)
        for line in _failure_lines(failures):
            print(line)
        if not cands:
            must_act = any(isinstance(e, cloud.ServiceError) and e.listener_must_act for _, e in failures)
            return cli.SERVICE if must_act else cli.ISSUES
        audition_id = os.path.basename(folder)
        print(f"Listen, then keep the one that sounds right:\n  ./sweatcast coaches keep {audition_id}/"
              f"{cands[0]['letter']} --name \"Coach ...\"\nWhen done: ./sweatcast coaches forget-audition {audition_id}")
        return cli.OK
    if args.cmd == "keep" and _web_ref(args.take):
        keep_web(args.take, args.name, args.replace_old)   # a service's refusal exits through cli.run
        return cli.OK
    if args.cmd == "make":
        make(args.coach)
        return cli.OK
    if args.cmd == "forget-audition":
        for line in forget_audition(args.audition):
            print(line)
        return cli.OK
    if args.cmd == "archive":
        p = personas.lookup(args.coach)
        print(f"Archived {p.name} in {show(personas.archive(p))}: out of the list; old log lines still find them.")
        return cli.OK
    if args.cmd == "keep":
        raise cli.Usage(f"{args.take} isn't an audition's candidate (<audition>/<letter>). Local coaches are the "
                        "ten sweatcast ships, chosen rather than made; a voice of your own is a web coach.")
    if args.cmd == "set":
        p = personas.lookup(args.coach)
        if p.shipped:
            raise errors.CoachError(f"{p.name} ships with sweatcast, so its settings live in the engine "
                             "(coaches/roster.toml).")
        table, _, key = args.setting.rpartition(".")
        if table == "local":
            raise errors.CoachError("A local coach's sound is set by the voice file it ships with; there's nothing to set.")
        value = _value(args.value)
        context.set_persona_setting(p.path, table or None, key, value)
        print(f"{p.name}: {args.setting} = {value}")
        return cli.OK
    if args.cmd == "download":
        if paths.REMOTE:
            print("Claude Code on the web renders with a cloud voice only, so there's no local model to fetch here.")
            return cli.USAGE
        voices.download()
        return cli.OK
    try:
        last, archived = personas.default(), None
    except errors.PROBLEMS as e:   # the coach used last is archived: list them all, and say so
        last, archived = None, str(e.code)
    found = personas.all()
    if not found:
        print("No coaches found: the ten local coaches ship in coaches/ (git pull), and a web coach comes from "
              "an audition (./sweatcast coaches audition).")
        return cli.OK
    for p in found:
        mark = "*" if last and p.slug == last.slug else " "
        if p.is_web:
            where = f"web · {cloud.service_name(p.service)}"
        else:
            where = "local · pocket"
        notes = (["(a stand-in)"] if p.placeholder else []) \
            + (["(made the first time it's used)"] if p.is_web and p.pending else []) \
            + ([] if p.is_web or p.shipped else ["(a local coach of your own: ./sweatcast migrate archives it)"]) \
            + [p.description[:60]]
        print((f"{mark} {p.name:22} {where:22} " + " ".join(x for x in notes if x)).rstrip())
    print(archived or "* the coach a build uses when none is named (the one used last; your own over a stand-in)")
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
