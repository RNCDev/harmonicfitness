"""Each shipped coach's 45-second sample.mp3 (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/sample.py .cache/design/samples andy marcus ...

Pocket (the public model, as a listener runs it) speaks each line in four seeds, and the recognizer picks the
first take heard right; render.assemble lays the lines out with the coach's recorded [count 3 go], and
render.encode masters it as a build does. The MP3s go in the folder named first; copy approved ones to
coaches/coach-<slug>-local/sample.mp3."""
import json, os, subprocess, sys, tomllib
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[:0] = [ROOT + "/tools", ROOT + "/tools/coachmaker"]
os.environ.setdefault("SWEATCAST_HOME", "/nonexistent")
import numpy as np
import bench, qa, asr, verify, engines, counts, draft, render

SEEDS = [42, 43, 44, 45]
DRAFT = """@@ 45 | Sample
Hi, I'm {name}. Let's see how this feels. Stand tall, feet about hip width apart, and let your arms hang loose.

We'll start with a few easy squats. Sit back like there's a chair behind you, chest up, and drive through your heels on the way up. [pause 1s]

Find your stance, and get ready. [count 3 go] [chime] Down slow, and up strong. That's the pace. Keep breathing, nice and steady. [hold]

Great work. That's how we'll train together. Shake it out, and when you're ready, we'll start your first workout.
"""

OUT = sys.argv[1]
roster = {c["slug"]: c for c in tomllib.load(open(ROOT + "/coaches/roster.toml", "rb"))["coach"]}
for slug in sys.argv[2:]:
    name = roster[slug]["name"]
    folder = f"{ROOT}/coaches/coach-{slug}-local"
    segs = draft.parse(DRAFT.format(name=name))
    lines = list(dict.fromkeys(t for seg in segs for para in draft.plan(seg) for t, _ in para if draft.spoken(t)))
    work = os.path.join(OUT, slug)
    job = {"model": "pocket", "device": "cpu", "engine": "pocket", "repo": "kyutai/pocket-tts-without-voice-cloning",
           "language": qa.LANGUAGE, "public_only": True, "ref_audio": folder + "/pocket.safetensors", "out": work,
           "seeds": SEEDS, "lines": [{"id": f"l{i}", "text": t} for i, t in enumerate(lines)]}
    os.makedirs(work, exist_ok=True)
    jp = os.path.join(work, "job.json"); json.dump(job, open(jp, "w"))
    env = dict(os.environ, HF_HUB_CACHE=qa.public_cache(), HF_HOME=qa.PUBLIC_HF + "/home", HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
    env.pop("HF_TOKEN", None)
    subprocess.run([qa.env_python("pocket-cpu"), "-I", bench.WORKER, "render", jp], cwd=ROOT, env=env,
                   stdout=open(work + "/log", "w"), stderr=subprocess.STDOUT, check=True)
    # trimmed and leveled as a build's clip; the recognizer hears the trimmed take
    pcms, wavs = {}, {}
    for i in range(len(lines)):
        for s in SEEDS:
            raw = np.frombuffer(bench.pcm_24k(os.path.join(work, str(s), f"l{i}.wav")), dtype="<i2").astype(np.float32) / 32768
            pcm = engines.to_pcm(raw)
            p = os.path.join(work, "trim", f"l{i}-{s}.wav"); os.makedirs(os.path.dirname(p), exist_ok=True)
            import wave
            with wave.open(p, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
            pcms[(i, s)], wavs[(i, s)] = pcm, p
    heard = asr.transcribe(list(wavs.values()), os.path.join(work, "asr"))
    chosen, report = {}, []
    for i, text in enumerate(lines):
        best = None
        for s in SEEDS:
            v = verify.judge(text, heard.get(wavs[(i, s)]) or "", pcms[(i, s)], len(pcms[(i, s)]) / 48000)
            if best is None or (v["ok"] and not best[1]["ok"]) or (v["ok"] == best[1]["ok"] and v["errors"] < best[1]["errors"]):
                best = (s, v)
            if v["ok"]:
                break
        chosen[text] = render.level(pcms[(i, best[0])])
        report.append({"line": text, "seed": best[0], "ok": best[1]["ok"], "errors": best[1]["errors"], "heard": best[1]["heard"]})
    voice = {"name": name, "cues": counts.folder(folder + "/clip.wav")}
    pcm, rows, drift = render.assemble(segs, lambda t: chosen[t], bell=render.chime(), tail=render.end_tone(),
                                       mark=lambda t: counts.pcm(t, voice))
    mp3 = os.path.join(OUT, f"{slug}-sample.mp3")
    render.encode(bytes(pcm), mp3, f"{name} sample")
    spoken_words = sum(len(t.split()) for t in lines)
    speech = sum(len(c) for c in chosen.values()) / 48000
    summary = {"slug": slug, "mp3": mp3, "seconds": round(len(pcm) / 48000, 1), "spoken": round(rows[0][2], 1),
               "wpm": round(spoken_words / speech * 60), "all_ok": all(r["ok"] for r in report), "lines": report}
    json.dump(summary, open(os.path.join(work, "summary.json"), "w"), indent=1)
    print(slug, summary["seconds"], "s,", summary["wpm"], "wpm, all heard right:", summary["all_ok"],
          [r["seed"] for r in report], flush=True)
