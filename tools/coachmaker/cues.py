"""Each shipped coach's count and cue clips (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/cues.py make andy marcus ...    (no names: every coach in the roster)
  .venv/bin/python tools/coachmaker/cues.py make --no-render ...     (score the takes already made)
  .venv/bin/python tools/coachmaker/cues.py make theo --seeds 50-57   (another batch of takes)
  .venv/bin/python tools/coachmaker/cues.py keep andy marcus ...    (approved: copy into coaches/<coach>/cues/)
  .venv/bin/python tools/coachmaker/cues.py keep maya go=45         (keep, with another seed for one clip)

A draft's `[count 5 go]` plays five, four, three, two, one and then "go", one a second, and `[cue rest]` one
cue alone (docs/plans/15.0.0-ten-local-coaches.md, Counts and cues). Those are clips each coach ships, made
here once on Pocket from the coach's pocket.safetensors, through the public model as a listener runs it:

- The counts come from one countdown, "Ten. Nine. ... One.", so they keep a counting voice and "one" sounds
  like the end. Each take is cut at its nine gaps into ten clips. A take passes when it splits into exactly
  ten (breaths dropped), every number is MIN_PIECE to MAX_COUNT seconds, and the recognizer hears the ten numbers in order with
  the pieces laid on the beat, as a workout plays them. (Heard as one fast list, the recognizer often drops
  the last few numbers that are there: 2026-10-27, three coaches.)
- Each cue is said alone ("Go!", "Rest."...). A take passes when the recognizer hears it and it's under
  MAX_CUE seconds.

Every clip gets SEEDS takes. Of the passing ones, the tool keeps the one nearest the coach's typical length
for that clip (a rushed or dragged take stands out on a beat), and builds a demo of the chosen clips on the
beat, as a build will lay them: .cache/design/cues/<coach>/demo.mp3, with .cache/design/cues/report.json.
The ear approves each coach's demo; `keep` then copies the chosen clips (trimmed, leveled as a build levels
a clip) to coaches/<coach>/cues/ with cues.toml (each clip's words, seed and length).
"""
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "coachmaker"))
import asr  # noqa: E402
import bench  # noqa: E402
import qa  # noqa: E402
import render  # noqa: E402
import verify  # noqa: E402

ROOT = qa.ROOT
COACHES = qa.COACHES
WORK = os.path.join(ROOT, ".cache", "design", "cues")
SEEDS = list(range(42, 50))
NUMBERS = ["ten", "nine", "eight", "seven", "six", "five", "four", "three", "two", "one"]
COUNTDOWN = "Ten. Nine. Eight. Seven. Six. Five. Four. Three. Two. One."
CUES = {"go": "Go!", "rest": "Rest.", "switch": "Switch.", "switch-sides": "Switch sides.", "stop": "Stop.",
        "hold": "Hold."}
MIN_PIECE = 0.15     # seconds: anything shorter is a click, not a number
MAX_COUNT = 0.8      # a number longer than this crowds a one-second beat
MAX_CUE = 1.2
BEAT = 1.0
GAP_DB = 30.0        # a gap is a run of frames this far under the take's loudest
MIN_GAP = 0.06       # seconds of quiet that count as a gap between numbers
BREATH_DB = 8.0      # a voiced stretch this far under the others' median is a breath, not a number
KEEP = 0.03          # seconds of quiet kept at each end of a clip
SOFT_DB = 50.0       # a number's own trim: only what's this far under its loudest is silence
FRAME = 0.01


def frames(a):
    import numpy as np
    f = int(FRAME * verify.SR)
    n = len(a) // f
    return 10 * np.log10(np.mean(a[: n * f].reshape(n, f) ** 2, axis=1) + 1e-12)


def trim(a, below=GAP_DB):
    import numpy as np
    db = frames(a)
    loud = np.flatnonzero(db > db.max() - below)
    if not len(loud):
        return a[:0]
    f, k = int(FRAME * verify.SR), int(KEEP * verify.SR)
    return a[max(0, loud[0] * f - k): min(len(a), (loud[-1] + 1) * f + k)]


def _runs(db):
    """Voiced stretches: runs of loud frames between gaps of MIN_GAP or more, as [start, end] frames."""
    loud = db >= db.max() - GAP_DB
    runs, start, quiet = [], None, 0
    for i, v in enumerate(list(loud) + [False] * (int(MIN_GAP / FRAME) + 1)):
        if v:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * FRAME >= MIN_GAP:
                runs.append([start, i - quiet + 1])
                start, quiet = None, 0
    return runs


def _join(runs, i):
    runs[i:i + 2] = [[runs[i][0], runs[i + 1][1]]]


def split_countdown(a, way="breaths"):
    """The ten numbers, or None. Three ways to cut, because Pocket's countdowns differ: "gaps" cuts at the nine
    longest gaps; "breaths" drops a breath (a stretch BREATH_DB under the others' median, as Pocket sometimes
    breathes mid count) and joins the closest pair while there are more than ten; "fragments" also joins a
    fragment too short to be a number (the "ks" of "six", after its stop) to its word first. The recognizer,
    hearing the pieces on the beat, decides which cut is right (choose)."""
    import numpy as np
    a = trim(a)
    db = frames(a)
    runs = _runs(db)
    if not runs:
        return None
    if way == "gaps":
        gaps = sorted(((runs[i + 1][0] - runs[i][1], i) for i in range(len(runs) - 1)), reverse=True)
        if len(gaps) < 9:
            return None
        keep = sorted(i for _, i in gaps[:9])
        bounds, s_ = [], runs[0][0]
        for i in keep:
            bounds.append([s_, runs[i][1]])
            s_ = runs[i + 1][0]
        bounds.append([s_, runs[-1][1]])
        runs = bounds
    else:
        level = [float(np.mean(db[s_:e])) for s_, e in runs]
        floor = float(np.median(level)) - BREATH_DB
        runs = [r for r, lv in zip(runs, level) if lv >= floor]
        if way == "fragments":
            short = int(MIN_PIECE / FRAME)
            while len(runs) > 1 and any(e - s_ < short for s_, e in runs):
                i = next(j for j, (s_, e) in enumerate(runs) if e - s_ < short)
                before = runs[i][0] - runs[i - 1][1] if i > 0 else None
                after = runs[i + 1][0] - runs[i][1] if i + 1 < len(runs) else None
                _join(runs, i - 1 if after is None or (before is not None and before <= after) else i)
        while len(runs) > 10:
            gaps = [runs[i + 1][0] - runs[i][1] for i in range(len(runs) - 1)]
            _join(runs, gaps.index(min(gaps)))
    if len(runs) != 10:
        return None
    # Cut halfway through each gap, then trim only true silence: a number's soft edges (the s of "six" and
    # "seven", the t of "eight") sit far under its vowel, and a tight cut clips them (2026-10-27, by ear).
    f = int(FRAME * verify.SR)
    cuts = [0] + [(runs[i][1] + runs[i + 1][0]) // 2 * f for i in range(9)] + [len(a)]
    return [trim(a[cuts[i]:cuts[i + 1]], SOFT_DB) for i in range(10)]


WAYS = ("breaths", "gaps", "fragments")


def pcm(a):
    import numpy as np
    return (np.clip(a, -1, 1) * 32767).astype("<i2").tobytes()


def load(path):
    import numpy as np
    return np.frombuffer(bench.pcm_24k(path), dtype="<i2").astype(np.float32) / 32768


def render_takes(slug):
    folder = os.path.join(COACHES, f"coach-{slug}-local")
    out = os.path.join(WORK, slug, "takes")
    lines = [{"id": "countdown", "text": COUNTDOWN}] + [{"id": k, "text": t} for k, t in CUES.items()]
    job = {"model": "pocket", "device": "cpu", "engine": "pocket", "repo": "kyutai/pocket-tts-without-voice-cloning",
           "language": qa.LANGUAGE, "public_only": True, "ref_audio": os.path.join(folder, "pocket.safetensors"),
           "out": out, "seeds": SEEDS, "lines": lines}
    os.makedirs(out, exist_ok=True)
    job_path = os.path.join(out, "job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    env = dict(os.environ, HF_HUB_CACHE=qa.public_cache(), HF_HOME=os.path.join(qa.PUBLIC_HF, "home"),
               HF_HUB_DISABLE_IMPLICIT_TOKEN="1", PYTHONIOENCODING="utf-8")
    env.pop("HF_TOKEN", None)
    with open(os.path.join(out, "worker.log"), "w", encoding="utf-8") as log:
        code = subprocess.call([qa.env_python("pocket-cpu"), "-I", bench.WORKER, "render", job_path],
                               stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=env)
    if code:
        raise SystemExit(f"{slug}: Pocket stopped (exit {code}); see {out}/worker.log")
    return {(k, s): os.path.join(out, str(s), k + ".wav") for k in ["countdown", *CUES] for s in SEEDS}


def on_beat(pieces):
    import numpy as np
    beat = int(BEAT * verify.SR)
    out = np.zeros(beat * (len(pieces) + 1), dtype=np.float32)
    for i, p in enumerate(pieces):
        out[beat // 2 + i * beat: beat // 2 + i * beat + len(p[:beat])] += p[:beat]
    return out


def beat_takes(slug, takes):
    """Each countdown take, cut each way that gives ten, laid on the beat as a WAV: {(take path, way): WAV}."""
    import wave
    out = {}
    for s_ in SEEDS:
        path = takes["countdown", s_]
        if not os.path.exists(path):
            continue
        a = load(path)
        for way in WAYS:
            pieces = split_countdown(a, way)
            if not pieces:
                continue
            dest = path.replace(".wav", f"-beat-{way}.wav")
            with wave.open(dest, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(verify.SR)
                w.writeframes(pcm(on_beat(pieces)))
            out[path, way] = dest
    return out


def choose(slug, takes, heard, beats):
    """{clip name: (seed, pieces or None, why)} and the candidates' numbers."""
    import numpy as np
    sr = verify.SR
    passing = {}
    # The countdown.
    ok = []
    for s in SEEDS:
        path = takes["countdown", s]
        if not os.path.exists(path):
            continue
        for way in WAYS:
            if verify.words(heard.get(beats.get((path, way), "")) or "") != NUMBERS:
                continue
            pieces = split_countdown(load(path), way)
            lens = [len(p) / sr for p in pieces]
            if all(MIN_PIECE <= x <= MAX_COUNT for x in lens):
                ok.append((s, way, pieces, lens))
                break
    if not ok:   # none confirmed: the first take that cuts into ten, for the ear to judge (marked unverified)
        for s in SEEDS:
            path = takes["countdown", s]
            for way in WAYS:
                pieces = split_countdown(load(path), way) if os.path.exists(path) else None
                if pieces:
                    passing["countdown"] = {"seed": s, "way": way, "pieces": pieces, "passing": 0, "unverified": True,
                                            "seconds": [round(len(p) / sr, 2) for p in pieces]}
                    break
            if "countdown" in passing:
                break
    if ok:
        typical = np.median([x for *_, ls in ok for x in ls])
        s, way, pieces, lens = min(ok, key=lambda o: np.mean([abs(x - typical) for x in o[3]]))
        passing["countdown"] = {"seed": s, "way": way, "pieces": pieces, "seconds": [round(x, 2) for x in lens],
                                "passing": len(ok)}
    # The cues.
    for k, text in CUES.items():
        ok = []
        for s in SEEDS:
            path = takes[k, s]
            if not os.path.exists(path):
                continue
            a = trim(load(path))
            v = verify.score(text, heard.get(path) or "")
            if not v["errors"] and not v["missed_cues"] and MIN_PIECE <= len(a) / sr <= MAX_CUE:
                ok.append((s, a))
        if ok:
            typical = np.median([len(a) for _, a in ok])
            s, a = min(ok, key=lambda o: abs(len(o[1]) - typical))
            passing[k] = {"seed": s, "audio": a, "seconds": round(len(a) / sr, 2), "passing": len(ok)}
    return passing


def demo(slug, got):
    """Ten down to one on the beat; three, two, one, go; then each other cue alone, as a build lays them."""
    import numpy as np
    sr = verify.SR
    beat = int(BEAT * sr)

    def lev(a):
        return np.frombuffer(render.level(pcm(a)), dtype="<i2").astype(np.float32) / 32768

    parts = []

    def count(pieces, then=None):
        seq = [lev(p) for p in pieces] + ([lev(then)] if then is not None else [])
        out = np.zeros(beat * len(seq), dtype=np.float32)
        for i, p in enumerate(seq):
            out[i * beat: i * beat + len(p)] += p[: beat]
        parts.append(out)
        parts.append(np.zeros(int(1.5 * sr), dtype=np.float32))

    if "countdown" in got:
        p = got["countdown"]["pieces"]
        count(p)
        if "go" in got:
            count(p[-3:], got["go"]["audio"])
        if "rest" in got:
            count(p[-5:], got["rest"]["audio"])
    for k in ("switch", "switch-sides", "stop", "hold"):
        if k in got:
            parts.append(lev(got[k]["audio"]))
            parts.append(np.zeros(int(1.2 * sr), dtype=np.float32))
    wav = os.path.join(WORK, slug, "demo.wav")
    import wave
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm(np.concatenate(parts) if parts else np.zeros(sr, dtype=np.float32)))
    import ffmpeg as ffmpeg_tool
    mp3 = os.path.join(WORK, slug, "demo.mp3")
    subprocess.run([ffmpeg_tool.exe(), "-y", "-v", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", mp3],
                   check=True)
    return mp3


def make(slugs, rerender=True):
    report_path = os.path.join(WORK, "report.json")
    try:
        with open(report_path, encoding="utf-8") as f:
            report = json.load(f)
    except (OSError, ValueError):
        report = {}
    for slug in slugs:
        if rerender:
            print(f"{slug}: {len(SEEDS)} takes of each clip on Pocket", flush=True)
            takes = render_takes(slug)
        else:
            takes = {(k, s_): os.path.join(WORK, slug, "takes", str(s_), k + ".wav") for k in ["countdown", *CUES]
                     for s_ in SEEDS}
        beats = beat_takes(slug, takes)
        heard = asr.transcribe([p for p in takes.values() if os.path.exists(p) and "countdown" not in p]
                               + list(beats.values()), os.path.join(WORK, slug, "asr"))
        got = choose(slug, takes, heard, beats)
        missing = [k for k in ["countdown", *CUES] if k not in got or got[k].get("unverified")]
        report[slug] = {"chosen": {k: v["seed"] for k, v in got.items()},
                        "countdown_way": got.get("countdown", {}).get("way"),
                        "countdown_unverified": bool(got.get("countdown", {}).get("unverified")),
                        "passing": {k: v["passing"] for k, v in got.items()},
                        "seconds": {k: v["seconds"] for k, v in got.items()},
                        "missing": missing, "demo": demo(slug, got)}
        print(f"  chosen {report[slug]['chosen']}" + (f"; no take passed: {', '.join(missing)}" if missing else ""),
              flush=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=1)
    return 0


def keep(argv):
    import tomllib
    with open(os.path.join(WORK, "report.json"), encoding="utf-8") as f:
        report = json.load(f)
    slug, over = None, {}
    groups = []
    for a in argv:
        if "=" in a and slug:
            k, s = a.split("=", 1)
            over.setdefault(slug, {})[k] = int(s)
        else:
            slug = a
            groups.append(a)
    for slug in groups:
        r = report.get(slug)
        if not r:
            raise SystemExit(f"No cues made for {slug} yet: run make first.")
        chosen = dict(r["chosen"], **over.get(slug, {}))
        missing = [k for k in ["countdown", *CUES] if k not in chosen]
        if missing:
            raise SystemExit(f"{slug} has no take for {', '.join(missing)}: make again, or name a seed (k=seed).")
        takes = {(k, s_): os.path.join(WORK, slug, "takes", str(s_), k + ".wav") for k, s_ in chosen.items()}
        dest = os.path.join(COACHES, f"coach-{slug}-local", "cues")
        os.makedirs(dest, exist_ok=True)
        rows = []
        import wave

        def write(name, a):
            with wave.open(os.path.join(dest, name + ".wav"), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(verify.SR)
                data = render.level(pcm(a))
                w.writeframes(data)
            return round(len(data) / 2 / verify.SR, 2)

        pieces = split_countdown(load(takes["countdown", chosen["countdown"]]), r.get("countdown_way") or "breaths")
        if not pieces:
            raise SystemExit(f"{slug}: countdown take {chosen['countdown']} doesn't split into ten.")
        for word, p in zip(NUMBERS, pieces):
            rows.append(f'[count.{word}]\nwords = "{word.capitalize()}."\nseed = {chosen["countdown"]}\n'
                        f'seconds = {write(word, p)}\n')
        for k, text in CUES.items():
            a = trim(load(takes[k, chosen[k]]))
            rows.append(f'[cue.{k.replace("-", "_")}]\nfile = "{k}.wav"\nwords = "{text}"\nseed = {chosen[k]}\n'
                        f'seconds = {write(k, a)}\n')
        head = ("# The coach's count and cue clips (tools/coachmaker/cues.py): Pocket, the public model, from\n"
                "# pocket.safetensors. Counts come from one countdown take, cut at its gaps. Leveled as a build\n"
                "# levels a clip.\n\n")
        text = head + "\n".join(rows)
        tomllib.loads(text)
        with open(os.path.join(dest, "cues.toml"), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"{slug}: kept {len(NUMBERS)} counts and {len(CUES)} cues in {os.path.relpath(dest, ROOT)}")
    return 0


def main(argv):
    global SEEDS
    rerender = "--no-render" not in argv
    argv = [a for a in argv if a != "--no-render"]
    if "--seeds" in argv:   # another batch of takes: --seeds 50-57
        i = argv.index("--seeds")
        lo, hi = (int(x) for x in argv[i + 1].split("-"))
        SEEDS = list(range(lo, hi + 1))
        del argv[i:i + 2]
    if not argv or argv[0] not in ("make", "keep"):
        raise SystemExit(__doc__)
    import tomllib
    with open(os.path.join(COACHES, "roster.toml"), "rb") as f:
        roster = tomllib.load(f)
    rest = argv[1:] or [c["slug"] for c in roster["coach"]]
    return make(rest, rerender) if argv[0] == "make" else keep(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
