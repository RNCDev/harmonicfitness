"""Coaches: audition a web coach and keep the one that sounds right; design or bring a local coach's clip;
choose, measure and tune them.

A coach is a persona folder in me/personas/ (tools/personas.py): a person's name, how they talk, and how
they sound. A web coach is a voice a service designed and saved (Fish Audio, ElevenLabs, Gemini, Inworld,
with the listener's key); a local coach is a ten-second clip every local engine copies.

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
    ./sweatcast coaches design "Coach Maya" "A woman in her thirties, warm and mid-low ..."   # local takes
    ./sweatcast coaches keep "me/personas/coach-maya/takes/2.wav"
    ./sweatcast coaches keep my-recording.wav --name "Coach Sam" --words "what the clip says"
    ./sweatcast coaches set "Coach Maya" local.engine qwen3
    ./sweatcast coaches measured "Coach Maya" --engine local   # exit 0 measured, 1 estimated, 64 unknown
    ./sweatcast coaches download ["Coach Maya"]           # the coach's local model

An audition reads a narrative file (persona.md's format: a schema 5 +++ block with [voice], what the
services design from, and [character], what the script writer follows, then free notes) and lands in
me/personas/.auditions/<date>-<n>/: each candidate as <service>-<k>.wav and .mp3, lettered A, B, C... in
service order, every one saying the same coaching line, with its cost per workout in candidates.json.
Fish, ElevenLabs and Inworld keep nothing until a candidate is kept; Gemini stores each voice as it
designs it, so forget-audition deletes the ones not kept.

A local coach's takes come from the local designer (Qwen3-TTS VoiceDesign on MLX, an Apple Silicon Mac;
a 4.5 GB model). Or bring a clip: about ten seconds of a voice with its exact words; a real person's
voice needs that person's consent.
"""
import argparse
import concurrent.futures
import datetime
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import context  # noqa: E402
import paths  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402
from paths import show  # noqa: E402

DESIGNERS = ("local",)
CANDIDATES = {"fish": 2, "elevenlabs": 3, "gemini": 1, "inworld": 2}   # per audition, lettered in this order
WORKOUT_CHARS = 20000   # a workout's characters, for the cost a candidate is labeled with
PROSE = """## How this coach talks
- Tone: calm and focused. Keep humor light and occasional, with no hype.
- How the coach talks to me: like a coach who knows me, warm and direct, first name now and then, contractions, "let's" in the rests. Not a drill sergeant, not a radio host.
- Encouragement that works for me: [for example, notice the effort plainly ("that last set was honest"), tell me why a movement is there, remind me what I did last time]
- Pet peeves in workout audio:
"""


def available_designer():
    import routes
    if voices.BACKEND == "mlx" and routes.local_installed():
        return "local"
    raise SystemExit("No voice designer works here: local design needs an Apple Silicon Mac. Bring a clip of "
                     "about ten seconds with its words (./sweatcast coaches keep <clip.wav> --name ... --words ...), "
                     "or make a web coach (the coach skill).")


def _make_takes(designer):
    if designer == "local":
        import engines
        from render import render_lock

        def make(description, line, takes, seed):
            with render_lock(paths.CACHE):   # another model: one at a time
                pcm = engines.design_takes(voices.VOICE_DESIGN[0], voices.VOICE_DESIGN[1], description, line,
                                           takes, seed)
            return [(x, line) for x in pcm]
        return make
    raise SystemExit(f"--designer must be one of {', '.join(DESIGNERS)}")


def design(name, description, designer=None, takes=2, seed=7, line=voices.DESIGN_LINE, make_takes=None):
    """Render takes of a new (or existing) coach into me/personas/<slug>/takes/<n>.wav, beside each its words
    (<n>.txt) and how it was made (<n>.take.json). Earlier takes are kept. Returns the .wav paths."""
    designer = designer or available_designer()
    if designer not in DESIGNERS:
        raise SystemExit(f"--designer must be one of {', '.join(DESIGNERS)}")
    folder = os.path.join(paths.PERSONAS, personas.slug(name), "takes")
    os.makedirs(folder, exist_ok=True)
    made = (make_takes or _make_takes(designer))(description, line, takes, seed)
    n = max([int(f[:-4]) for f in os.listdir(folder) if f.endswith(".wav") and f[:-4].isdigit()], default=0)
    out = []
    for i, (pcm, words) in enumerate(made):
        n += 1
        stem = os.path.join(folder, str(n))
        voices.write_wav(stem + ".wav", pcm)
        with open(stem + ".txt", "w", encoding="utf-8") as f:
            f.write(words.strip() + "\n")
        meta = {"name": name, "description": description, "designer": designer, "line": words, "seed": seed + i}
        if designer == "local":
            meta.update(model=voices.VOICE_DESIGN[0], revision=voices.VOICE_DESIGN[1])
        with open(stem + ".take.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=1)
        out.append(stem + ".wav")
    return out


def _clip_bytes(src):
    """The clip as a 16-bit mono 24 kHz WAV: the file itself when it already is one (so its key stays the
    same), else converted (WAV in pure Python, anything else through ffmpeg)."""
    import cloud
    with open(src, "rb") as f:
        data = f.read()
    try:
        with wave.open(src) as w:
            if (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2):
                return data
    except (wave.Error, EOFError):
        pass
    return cloud.wav_bytes(cloud.audio_pcm(data))


def keep(take, name=None, words=None, description="", engine="chatterbox", force=False):
    """Make a take (or any clip, with its words) a coach's clip: clip.wav and clip.txt in the coach's folder,
    and a persona.md when the coach is new. Returns the coach's name."""
    if not os.path.exists(take):
        raise SystemExit(f"No clip at {take}.")
    stem = os.path.splitext(take)[0]
    meta = {}
    if os.path.exists(stem + ".take.json"):
        with open(stem + ".take.json", encoding="utf-8") as f:
            meta = json.load(f)
    if words is None and os.path.exists(stem + ".txt"):
        with open(stem + ".txt", encoding="utf-8") as f:
            words = f.read()
    if not (words or "").strip():
        raise SystemExit("A clip needs its exact words: pass --words \"...\" (or a .txt of them beside it).")
    name = name or meta.get("name")
    if not name:
        raise SystemExit("Give the coach a person's name: --name \"Coach Sam\".")
    if engine not in personas.LOCAL_ENGINES:
        raise SystemExit(f"--engine must be one of {', '.join(personas.LOCAL_ENGINES)}")
    folder = os.path.join(paths.PERSONAS, personas.slug(name))
    os.makedirs(folder, exist_ok=True)
    clip, clip_txt, persona_md = (os.path.join(folder, f) for f in ("clip.wav", "clip.txt", "persona.md"))
    if os.path.exists(clip) and not force:
        raise SystemExit(f"{name} already has a clip ({show(clip)}); pass --force to replace it (their pace is "
                         "measured again on the next smoke test).")
    data = _clip_bytes(take)
    with open(clip + ".part", "wb") as f:
        f.write(data)
    os.replace(clip + ".part", clip)
    with open(clip_txt, "w", encoding="utf-8") as f:
        f.write(words.strip() + "\n")
    if not os.path.exists(persona_md):
        settings = {"name": name, "kind": "local", "description": description or meta.get("description", "")}
        if meta.get("description"):
            settings["designed_from"] = meta["description"]
        settings["local"] = {"engine": engine}
        with open(persona_md, "w", encoding="utf-8") as f:
            f.write(context.persona_text(settings, PROSE))
    return name


# --- Web coaches: audition, keep, forget-audition, archive ---------------------------------------------------

def _auditions():
    return os.path.join(paths.PERSONAS, ".auditions")


def _narrative(path):
    """The narrative file as a context Persona (settings, body), refused without a [voice] to design from."""
    if not os.path.exists(path):
        raise SystemExit(f"No narrative at {path}.")
    n = context.persona(path)
    voice = n.settings.get("voice")
    if not isinstance(voice, dict) or not personas.voice_description(voice):
        raise SystemExit(f"{show(path)} has no [voice] to design from (who, sound, energy, pace, avoid).")
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


def _service_name(service):
    import cloud
    return cloud.services().get(service, {}).get("name", service or "no service")


def _reason(e):
    if isinstance(e, SystemExit):
        return str(e.code)
    return getattr(e, "message", None) or str(e) or type(e).__name__


def _mp3(wav, mp3):
    """The candidate as an MP3 (mono, 48 kbps) to listen to; False when ffmpeg isn't here."""
    import ffmpeg
    exe = ffmpeg.exe()
    if not exe:
        return False
    done = subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", "-i", wav, "-ac", "1",
                           "-c:a", "libmp3lame", "-b:a", "48k", mp3], capture_output=True, text=True, timeout=120)
    return done.returncode == 0


def _write_sample(coach, wav, mp3=None):
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
            print("(No sample.mp3: ffmpeg isn't here to make one.)")
    finally:
        for leftover in (part, part_mp3):
            if os.path.exists(leftover):
                os.remove(leftover)


def _estimate(coach, service, wav, text):
    """The coach's pace estimate from its sample: weighted characters over the trimmed seconds."""
    import cloud
    pcm = cloud.trim(cloud.audio_pcm(wav, service=service))
    seconds = len(pcm) / 2 / cloud.SR
    if seconds > 0:
        voices.record_estimate(cloud.voice_for(coach, service), voices.weight(text), seconds)


def _write_candidates(folder, cands):
    context._atomic_write(os.path.join(folder, "candidates.json"), json.dumps(cands, indent=1) + "\n")


def _read_candidates(folder):
    with open(os.path.join(folder, "candidates.json"), encoding="utf-8") as f:
        return json.load(f)


def _run_audition(narrative=None, services=None, coach=None, play=False):
    """Design candidates on every keyed service (or `services`) in parallel. Returns (folder, candidates,
    failures as (service, error)); folder is None when no candidate landed."""
    import cloud
    import keys
    table = cloud.services()   # loaded once, before the threads
    revoice = None
    if coach:
        revoice = personas.lookup(coach)
        if not revoice.is_web or revoice.service not in CANDIDATES:
            raise SystemExit(f"{revoice.name} is a local coach: a web audition makes a new web coach "
                             "(audition a narrative without --coach).")
        if services and list(services) != [revoice.service]:
            raise SystemExit(f"{revoice.name} speaks on {_service_name(revoice.service)}: a coach is re-voiced on "
                             "its own service only (leave out --services).")
        services = [revoice.service]
        narrative = narrative or revoice.path
    if not narrative:
        raise SystemExit("Name the narrative file to design from (or --coach for a coach's new voice).")
    n = _narrative(narrative)
    wanted = list(services) if services else list(CANDIDATES)
    unknown = [s for s in wanted if s not in CANDIDATES]
    if unknown:
        raise SystemExit(f"No web service {', '.join(unknown)}: the services are {', '.join(CANDIDATES)}.")
    wanted = [s for s in CANDIDATES if s in wanted]
    keyed = [s for s in wanted if keys.is_set(s)]
    for s in wanted:
        if s not in keyed and services:
            print(f"{_service_name(s)}: no key here, skipped (./sweatcast keys).")
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
        print(f"{table[s]['name']}: asking for {CANDIDATES[s]} candidate{'s' if CANDIDATES[s] > 1 else ''}, "
              + (f"design about ${cost:.2f}" if cost is not None else "design cost not published"), flush=True)

    def design(service):
        module = importlib.import_module(f"services.{service}")
        return module.design(description, voices.DESIGN_LINE, CANDIDATES[service],
                             f"sweatcast audition {audition_id} {planned[service]}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(keyed)) as pool:
        futures = {s: pool.submit(design, s) for s in keyed}
    cands, failures = [], []
    for s in keyed:   # service order, whatever finished first
        try:
            made = futures[s].result()
        except (Exception, SystemExit) as e:
            failures.append((s, e))
            continue
        usd = round(cloud.estimate(s, table[s]["default_model"], ["x" * WORKOUT_CHARS])[1], 4)
        for k, c in enumerate(made, 1):
            stem = f"{s}-{k}"
            with open(os.path.join(folder, stem + ".wav"), "wb") as f:
                f.write(c["wav"])   # as the service sent it: Fish's save sends this WAV back
            mp3 = stem + ".mp3" if _mp3(os.path.join(folder, stem + ".wav"), os.path.join(folder, stem + ".mp3")) \
                else None
            entry = {"letter": chr(ord("A") + len(cands)), "service": s, "k": k, "draft_id": c.get("draft_id"),
                     "signature": c.get("signature"), "text": c.get("text") or voices.DESIGN_LINE,
                     "wav": stem + ".wav", "mp3": mp3, "usd_per_workout": usd,
                     "design_usd": table[s].get("design_usd"), "note": table[s].get("note")}
            if revoice:
                entry["coach"] = revoice.name
            cands.append(entry)
    if not cands:
        shutil.rmtree(folder, ignore_errors=True)
    else:
        shutil.copyfile(narrative, os.path.join(folder, "narrative.md"))
        _write_candidates(folder, cands)
    import player
    for c in cands:
        listen = os.path.join(folder, c["mp3"] or c["wav"])
        print(f"{c['letter']}  {table[c['service']]['name']:10}  about ${c['usd_per_workout']:.2f} a workout  "
              f"{show(listen)}" + (f"  ({c['note']})" if c["note"] else ""))
        if play and not player.play(listen):
            print("    (no audio player found here; open the file to listen)")
    for s, e in failures:
        print(f"{table[s]['name']}: no candidates ({_reason(e)})")
    if cands and not all(c["mp3"] for c in cands):
        import ffmpeg
        print(f"(No MP3s: ffmpeg isn't here, {ffmpeg.install_hint()}; the WAVs play as well.)")
    return (folder if cands else None), cands, failures


def audition(narrative, services=None, coach=None, play=False):
    """Candidates for a web coach from `narrative` (a persona.md-format file), one design per keyed service
    (or each of `services`), in parallel, each saying the coaching line; nothing saved. With `coach`, a new
    voice for that coach on its own service, from its own persona.md unless a narrative is given. Returns
    the audition folder."""
    folder, _, failures = _run_audition(narrative, services, coach, play)
    if folder is None:
        raise SystemExit("No candidates: " + ("; ".join(f"{_service_name(s)}: {_reason(e)}" for s, e in failures)
                                              or "no web service has a key here (./sweatcast keys)."))
    return folder


def _web_ref(ref):
    """(audition folder, candidate) for `<audition>/<letter>` or `<audition>/<service>-<k>` (the audition
    by id or path; a .wav or .mp3 on the candidate is allowed), else None."""
    head, _, tail = ref.replace("\\", "/").rstrip("/").rpartition("/")
    if not head or not tail:
        return None
    tail = re.sub(r"\.(wav|mp3)$", "", tail, flags=re.IGNORECASE)
    for folder in (head, os.path.join(_auditions(), head)):
        if os.path.isfile(os.path.join(folder, "candidates.json")):
            return folder, tail
    return None


def _audition_folder(ref):
    for folder in (ref, os.path.join(_auditions(), ref)):
        if os.path.isfile(os.path.join(folder, "candidates.json")):
            return folder
    raise SystemExit(f"No audition {ref} (in {show(_auditions())}).")


def _resumable(c):
    """Whether candidate `c` was saved at its service but its coach never written (keep stopped between the
    two): a new coach with no persona.md, or a re-voiced coach still on the voice it replaces."""
    if not (c.get("kept") and c.get("voice_id")):
        return False
    try:
        coach = personas.lookup(c["kept"], archived=True)   # an archived coach was written: never resurrected
    except SystemExit:
        return True
    if os.path.dirname(coach.folder) != paths.PERSONAS.rstrip(os.sep):
        return False
    return bool(coach and "replaces" in c and coach.voice_id == c["replaces"] and coach.voice_id != c["voice_id"])


def _existing(name):
    try:
        return personas.lookup(name)
    except SystemExit:
        return None


def keep_web(ref, name, replace_old=False):
    """Save candidate `ref` (`<audition>/<letter>` or `<audition>/<service>-<k>`) at its service as
    "sweatcast <name>" and write the coach: persona.md (the narrative's [voice], [character] and notes,
    with kind, service, voice_id, made), sample.mp3 and a pace estimate. An audition made with --coach
    re-voices that coach: a new voice_id and sample, the old voice's pace dropped, and with `replace_old`
    the old voice deleted at the service. Returns the coach's folder."""
    import cloud
    found = _web_ref(ref)
    if not found:
        raise SystemExit(f"{ref} isn't a candidate in an audition: <audition>/<letter>, such as "
                         f"{datetime.date.today().isoformat()}-1/B.")
    folder, which = found
    cands = _read_candidates(folder)
    c = next((x for x in cands if which.lower() in (x["letter"].lower(), f"{x['service']}-{x['k']}")), None)
    if c is None:
        raise SystemExit(f"No candidate {which} in audition {os.path.basename(folder)}: "
                         f"{', '.join(x['letter'] for x in cands)}.")
    resume = _resumable(c)
    if c.get("kept") and not resume:
        raise SystemExit(f"Candidate {c['letter']} is already {c['kept']}.")
    if resume and name and personas.slug(name) != personas.slug(c["kept"]):
        raise SystemExit(f"Candidate {c['letter']} was saved as {c['kept']}; finish keeping it with --name "
                         f"\"{c['kept']}\".")
    name = (c["kept"] if resume else name) or c.get("coach")
    if not name:
        raise SystemExit("Give the coach a person's name: --name \"Coach Maya\".")
    existing = _existing(name)
    revoice = c.get("coach")
    if existing is None and not resume and os.path.exists(os.path.join(paths.PERSONAS, personas.slug(name))):
        raise SystemExit(f"{show(os.path.join(paths.PERSONAS, personas.slug(name)))} is already there; pick another name.")
    revoiced = _existing(revoice) if revoice else None
    if existing is not None and (revoiced is None or revoiced.folder != existing.folder):
        raise SystemExit(f"There's already a coach called {existing.name}. Pick another name, or for a new voice "
                         f"for {existing.name}, audition with --coach \"{existing.name}\" and keep from that.")
    service = c["service"]
    if existing is not None and existing.service != service:
        raise SystemExit(f"{existing.name} speaks on {_service_name(existing.service)}; candidate {c['letter']} is "
                         f"from {_service_name(service)}. A coach is re-voiced on its own service only.")
    n = context.persona(os.path.join(folder, "narrative.md"))
    voice = n.settings.get("voice") or {}
    with open(os.path.join(folder, c["wav"]), "rb") as f:
        wav = f.read()
    candidate = {"wav": wav, "text": c["text"], "draft_id": c["draft_id"], "signature": c["signature"]}
    module = importlib.import_module(f"services.{service}")
    if resume:   # saved before, but the coach was never written: finish with the voice already saved
        voice_id = c["voice_id"]
        print(f"Finishing {name}: {c['letter']} is already saved at {_service_name(service)}.", flush=True)
    else:
        print(f"Saving {c['letter']} at {_service_name(service)} as \"sweatcast {name}\".", flush=True)
        voice_id = module.save(candidate, name, personas.voice_description(voice), wav)
        c.update(voice_id=voice_id, kept=name)   # recorded before any local write, so it's never lost
        if existing is not None:
            c["replaces"] = existing.voice_id
        _write_candidates(folder, cands)

    today = datetime.date.today().isoformat()
    if existing is not None:   # a new voice for a coach: how they talk stays
        target, prose = existing.folder, existing.prose
        # a stand-in re-voiced is the listener's own choice now: no longer a placeholder
        settings = {k: v for k, v in existing.settings.items() if k not in ("schema", "pending", "placeholder")}
        settings.update(voice_id=voice_id, made=today, voice=voice)
        if existing.placeholder and str(settings.get("description", "")).startswith("A stand-in"):
            settings.pop("description", None)
            if n.settings.get("description") and not str(n.settings["description"]).startswith("A stand-in"):
                settings["description"] = n.settings["description"]
    else:
        target, prose = os.path.join(paths.PERSONAS, personas.slug(name)), n.body
        settings = {"name": name, "aliases": [], "kind": "web", "service": service, "voice_id": voice_id,
                    "made": today}
        if n.settings.get("description"):
            settings["description"] = n.settings["description"]
        settings["voice"] = voice
        if isinstance(n.settings.get("character"), dict):
            settings["character"] = n.settings["character"]
    os.makedirs(target, exist_ok=True)
    coach = personas.Persona(os.path.basename(target), target, settings, prose)
    _write_sample(coach, wav, os.path.join(folder, c["mp3"]) if c.get("mp3") else None)
    if existing is not None and existing.voice_id:
        models = list(cloud.services()[service].get("models") or {}) + [existing.model or ""]
        for model in dict.fromkeys(m for m in models if m):
            voices.forget_pace(existing.pace_file, personas.web_key(existing, model))
    _estimate(coach, service, wav, c["text"])
    context._atomic_write(coach.path, context.persona_text(settings, prose))   # last: all or nothing

    if existing is not None and existing.voice_id and replace_old:
        try:
            module.delete(existing.voice_id)
            print(f"Deleted {existing.name}'s old voice at {_service_name(service)}.")
        except (cloud.ServiceError, SystemExit) as e:
            print(f"Couldn't delete the old voice at {_service_name(service)} ({_reason(e)}); delete "
                  f"\"sweatcast {existing.name}\" there by hand.")
    print(f"Kept {name} ({_service_name(service)}) in {show(target)}.")
    return target


MADE = ".made.json"   # in a coach's folder while make is between saving a voice and writing persona.md
MADE_WAV = ".made.wav"


def _record_made(folder, service, voice_id, text, wav):
    """Record a voice make just saved, before any local write, so a failed make resumes from it."""
    with open(os.path.join(folder, MADE_WAV + ".part"), "wb") as f:
        f.write(wav)
    os.replace(os.path.join(folder, MADE_WAV + ".part"), os.path.join(folder, MADE_WAV))
    context._atomic_write(os.path.join(folder, MADE), json.dumps(
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


def make(name):
    """Make a pending web coach (a default that ships with no voice): design one voice from its [voice] on
    its own service, save the first candidate with no audition, and write voice_id, made, sample.mp3 and a
    pace estimate, persona.md last. Says so (and what it costs) first. Returns the voice ID. A failure
    leaves persona.md as it was, still pending."""
    import cloud
    p = personas.lookup(name)
    if not p.is_web or not p.pending:
        raise SystemExit(f"{p.name} is already made: nothing to design.")
    description = personas.voice_description(p.voice)
    if not description:
        raise SystemExit(f"{show(p.path)} has no [voice] to design from (who, sound, energy, pace, avoid).")
    service = p.service
    table = cloud.services()
    if service not in table or service not in CANDIDATES:
        raise SystemExit(f"{p.name} names no known web service ({service or 'none'}).")
    s = table[service]
    cost = (f"about ${s['design_usd']:.2f}" if s.get("design_usd") is not None else "design cost not published")
    if service == "elevenlabs":
        cost += "; it uses one of ElevenLabs Free's 3 voice slots"
    module = importlib.import_module(f"services.{service}")
    saved = _made(p.folder, service)
    if saved:   # an earlier make saved the voice but stopped before persona.md: finish with it
        voice_id, text, wav = saved
        c, recorded = {}, True
        print(f"Finishing {p.name}: its voice is already saved at {s['name']} (voice ID {voice_id}).", flush=True)
    else:
        print(f"{p.name} is made the first time it's used: designing a voice at {s['name']} from its description "
              f"({cost}).", flush=True)
        c = module.design(description, voices.DESIGN_LINE, 1, f"sweatcast {p.name}")[0]
        voice_id, text, wav, recorded = None, c.get("text") or voices.DESIGN_LINE, c["wav"], False
    try:
        if not recorded:
            voice_id = module.save(c, p.name, description, wav)
            _record_made(p.folder, service, voice_id, text, wav)
            recorded = True
        settings = {k: v for k, v in p.settings.items() if k not in ("schema", "pending")}
        settings.update(voice_id=voice_id, made=datetime.date.today().isoformat())
        if settings.get("description"):
            settings["description"] = _made_description(settings["description"])
        coach = personas.Persona(p.slug, p.folder, settings, p.prose)
        _write_sample(coach, wav)
        _estimate(coach, service, wav, text)
        context._atomic_write(p.path, context.persona_text(settings, p.prose))   # last: all or nothing
    except BaseException:
        if recorded:   # the voice is recorded in the coach's folder: the next make finishes with it
            print(f"{p.name}'s voice is saved at {s['name']} (voice ID {voice_id}) but the coach wasn't written; "
                  "it's still pending, and the next build (or ./sweatcast coaches make) finishes it without "
                  "designing again.", file=sys.stderr)
        elif service == "gemini" and c.get("draft_id"):   # stored at design: don't leave it behind
            try:
                module.delete(c["draft_id"])
            except (Exception, SystemExit):
                print(f"(Gemini keeps a voice \"sweatcast {p.name}\", ID {c['draft_id']}; delete it there "
                      "by hand.)", file=sys.stderr)
        elif voice_id:
            print(f"{p.name}'s voice was saved at {s['name']} (voice ID {voice_id}) but the coach wasn't written; "
                  f"it's still pending. Delete \"sweatcast {p.name}\" there, or put voice_id = \"{voice_id}\" "
                  f"in {show(p.path)}.", file=sys.stderr)
        raise
    for done in (MADE, MADE_WAV):
        if os.path.exists(os.path.join(p.folder, done)):
            os.remove(os.path.join(p.folder, done))
    print(f"Made {p.name} ({s['name']}): a stand-in until you make your own (\"I want a new coach\").")
    return voice_id


def forget_audition(audition):
    """Close an audition: delete Gemini's stored voices that weren't kept, then the folder. Returns the lines
    said. If a Gemini voice won't delete, the folder stays so it can be tried again."""
    import cloud
    folder = _audition_folder(audition)
    cands = _read_candidates(folder)
    in_use = {p.voice_id for p in personas.all() + personas.all(os.path.join(paths.PERSONAS, ".archive"))
              if p.voice_id}
    lines = []
    for c in cands:   # a voice a coach uses (active or archived) is never deleted, kept mark or not
        if c["service"] == "gemini" and not c.get("kept") and c.get("draft_id") and c["draft_id"] not in in_use:
            gemini = importlib.import_module("services.gemini")
            try:
                gemini.delete(c["draft_id"])
            except (cloud.ServiceError, SystemExit) as e:
                raise SystemExit(f"Gemini: couldn't delete audition voice {c['letter']} ({_reason(e)}); the "
                                 f"audition stays in {show(folder)} so forget-audition can try again.")
            lines.append(f"Deleted Gemini's stored audition voice {c['letter']}.")
    others = list(dict.fromkeys(_service_name(c["service"]) for c in cands
                                if c["service"] != "gemini" and not c.get("kept")))
    if others:
        lines.append(f"{', '.join(others)}: the unsaved drafts need nothing (nothing was saved there).")
    shutil.rmtree(folder)
    lines.append(f"Removed {show(folder)}.")
    return lines


def archive(name):
    """Move coach `name` to personas/.archive/ (out of the list, still found for old log lines). Returns
    where it went."""
    return personas.archive(personas.lookup(name))


def last_line(p):
    return f"{p.name}" + (f": {p.description}" if p.description else "")


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
    g = sub.add_parser("design", help="render takes of a coach from a description")
    g.add_argument("name", help="a person's name, such as 'Coach Maya'")
    g.add_argument("description", help="who they are and how they sound (knowledge/voices.md)")
    g.add_argument("--designer", choices=DESIGNERS, help="default: the first that works here")
    g.add_argument("--takes", type=int, default=2)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--line", default=voices.DESIGN_LINE, help="what the takes say (a coaching line)")
    g.add_argument("--play", action="store_true", help="play each take with the system's player")
    a = sub.add_parser("audition", help="candidates for a web coach from every keyed service; nothing saved")
    a.add_argument("narrative", nargs="?", help="the coach narrative: persona.md's format, with [voice]")
    a.add_argument("--services", help="only these, comma-separated (fish, elevenlabs, gemini, inworld)")
    a.add_argument("--coach", help="a new voice for this web coach, on its own service")
    a.add_argument("--play", action="store_true", help="play each candidate with the system's player")
    k = sub.add_parser("keep", help="keep an audition's candidate as a web coach (<audition>/<letter>), or make "
                                    "a take or a clip you bring a local coach's clip")
    k.add_argument("take", help="<audition>/<letter> or <audition>/<service>-<k>; or a take or clip")
    k.add_argument("--name", help="the coach's name (a new web coach needs one; default: the take's)")
    k.add_argument("--replace-old", action="store_true",
                   help="re-voicing: delete the coach's old voice at its service")
    k.add_argument("--words", help="the clip's exact words (default: the .txt beside it)")
    k.add_argument("--description", default="", help="who the coach is, in a line")
    k.add_argument("--engine", choices=personas.LOCAL_ENGINES, default="chatterbox",
                   help="the local model: chatterbox (most natural) or qwen3 (clearest; Mac only)")
    k.add_argument("--force", action="store_true", help="replace the coach's clip")
    mk = sub.add_parser("make", help="make a pending web coach: design its voice and save the first candidate")
    mk.add_argument("coach")
    f = sub.add_parser("forget-audition", help="close an audition: Gemini's unkept voices deleted, the folder removed")
    f.add_argument("audition", help="its id (such as 2026-10-25-1) or folder")
    r = sub.add_parser("archive", help="move a coach out of the list (old log lines still find them)")
    r.add_argument("coach")
    s = sub.add_parser("set", help="set one of a coach's settings: <table>.<key> <value>")
    s.add_argument("coach")
    s.add_argument("setting", help="for example local.engine, elevenlabs.model, or description")
    s.add_argument("value")
    d = sub.add_parser("download", help="fetch the local model the coaches use (Chatterbox Turbo with none yet)")
    d.add_argument("coach", nargs="*")
    d.add_argument("--all", action="store_true", help="every local engine's model this computer can run")
    args = ap.parse_args(argv)

    if args.cmd == "last":
        try:
            p = personas.last_coach()
        except SystemExit as e:   # the coach used last is archived
            print(e.code, file=sys.stderr)
            return cli.ISSUES
        if not p:
            print("No coach yet.", file=sys.stderr)
            return cli.ISSUES
        print(p.name)
        return cli.OK
    if args.cmd == "measured":
        import routes
        try:
            p = personas.lookup(args.coach)
            route = routes.pick(context.routes(context.profile()) if os.path.exists(paths.PROFILE) else ["local"],
                                p, override=args.engine)
            v = personas.voice_for(p, route)
        except SystemExit as e:
            print(e.code, file=sys.stderr)
            return cli.USAGE
        if p.is_web:   # a web coach needs no smoke test: an estimate stands until its first render measures it
            return cli.OK
        return cli.OK if voices.pace(v)[1] else cli.ISSUES
    if args.cmd == "design":
        designer = args.designer or available_designer()
        print(f"Designing {args.name}: {args.takes} takes with the {designer} designer"
              + (f" ({voices.VOICE_DESIGN[0]}, about {voices.SIZES_GB[voices.VOICE_DESIGN[0]]} GB the first time)"
                 if designer == "local" else "") + ".", flush=True)
        takes = design(args.name, args.description, designer, args.takes, args.seed, args.line)
        import player
        for t in takes:
            print(f"  {show(t)}")
            if args.play and not player.play(t):
                print("    (no audio player found here; open the file to listen)")
        print(f"Listen, then keep the one that sounds right:\n  ./sweatcast coaches keep \"{show(takes[0])}\"\n"
              "None right? Say what's off, reword the description, and design again (or another --seed).")
        return cli.OK
    if args.cmd == "audition":
        import cloud
        wanted = [x.strip() for x in args.services.split(",") if x.strip()] if args.services else None
        folder, cands, failures = _run_audition(args.narrative, wanted, args.coach, args.play)
        if not cands:
            must_act = any(isinstance(e, cloud.ServiceError) and e.listener_must_act for _, e in failures)
            return cli.SERVICE if must_act else cli.ISSUES
        audition_id = os.path.basename(folder)
        print(f"Listen, then keep the one that sounds right:\n  ./sweatcast coaches keep {audition_id}/"
              f"{cands[0]['letter']} --name \"Coach ...\"\nWhen done: ./sweatcast coaches forget-audition {audition_id}")
        return cli.OK
    if args.cmd == "keep" and _web_ref(args.take):
        import cloud
        try:
            keep_web(args.take, args.name, args.replace_old)
        except cloud.ServiceError as e:
            print(e, file=sys.stderr)
            return cli.SERVICE if e.listener_must_act else cli.ISSUES
        return cli.OK
    if args.cmd == "make":
        import cloud
        try:
            make(args.coach)
        except cloud.ServiceError as e:
            print(e, file=sys.stderr)
            return cli.SERVICE if e.listener_must_act else cli.ISSUES
        return cli.OK
    if args.cmd == "forget-audition":
        for line in forget_audition(args.audition):
            print(line)
        return cli.OK
    if args.cmd == "archive":
        name = personas.lookup(args.coach).name
        print(f"Archived {name} in {show(archive(args.coach))}: out of the list; old log lines still find them.")
        return cli.OK
    if args.cmd == "keep":
        name = keep(args.take, args.name, args.words, args.description, args.engine, args.force)
        print(f"Kept {name} in {show(os.path.join(paths.PERSONAS, personas.slug(name)))}. Write how they talk in "
              f"persona.md, then measure their pace with the smoke test:\n"
              f"  ./sweatcast build {show(paths.SMOKE_DRAFT)} \"smoke-test\" --coach \"{name}\"")
        return cli.OK
    if args.cmd == "set":
        p = personas.lookup(args.coach)
        table, _, key = args.setting.rpartition(".")
        value = _value(args.value)
        if table == "local" and key == "engine" and value not in personas.LOCAL_ENGINES:
            raise SystemExit(f"local.engine must be one of {', '.join(personas.LOCAL_ENGINES)}")
        context.set_persona_setting(p.path, table or None, key, value)
        print(f"{p.name}: {args.setting} = {value}")
        return cli.OK
    if args.cmd == "download":
        if paths.REMOTE:
            print("Claude Code on the web renders with a cloud voice only, so there's no local model to fetch here.")
            return cli.USAGE
        if args.all:
            engines_wanted = [e for e in personas.LOCAL_ENGINES if (e, voices.BACKEND) in voices.LOCAL_MODELS]
        else:
            chosen = [personas.lookup(n) for n in args.coach] or personas.all()
            engines_wanted = list(dict.fromkeys(p.table("local").get("engine") or "chatterbox"
                                                for p in chosen if p.has_clip)) or ["chatterbox"]
        for engine in engines_wanted:
            if (engine, voices.BACKEND) not in voices.LOCAL_MODELS:
                print(f"{engine}: renders locally only on an Apple Silicon Mac; skipped.")
                continue
            model, revision = voices.LOCAL_MODELS[(engine, voices.BACKEND)]
            voices.download({"name": engine, "engine": engine, "backend": voices.BACKEND, "model": model,
                             "revision": revision})
        return cli.OK
    try:
        last, archived = personas.last_coach(), None
    except SystemExit as e:   # the coach used last is archived: list them all, and say so
        last, archived = None, str(e.code)
    found = personas.all()
    if not found:
        print("No coaches yet: audition a web coach (./sweatcast coaches audition), or design or bring a local "
              "coach's clip (./sweatcast coaches design, ./sweatcast coaches keep).")
        return cli.OK
    for p in found:
        mark = "*" if last and p.slug == last.slug else " "
        if p.is_web:
            where = f"web · {_service_name(p.service)}"
        else:
            where = f"local · {p.table('local').get('engine') or 'chatterbox'}"
        notes = (["(a stand-in)"] if p.placeholder else []) \
            + (["(made the first time it's used)"] if p.is_web and p.pending else []) \
            + (["(no clip yet)"] if not p.is_web and not p.has_clip else []) + [p.description[:60]]
        print((f"{mark} {p.name:22} {where:22} " + " ".join(x for x in notes if x)).rstrip())
    print(archived or "* the coach a build uses when none is named (the one used last; your own over a stand-in)")
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
