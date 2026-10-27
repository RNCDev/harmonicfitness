"""Design takes of the shipped coaches' clips (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/design.py andy marcus --takes 6

Each designer runs tools/coachmaker/design_worker.py in its own environment (coaches/roster.toml names it)
on the Mac through mlx-audio, from the model already in models/
(offline: nothing is downloaded). Every take is then made into a clip candidate the way a shipped clip.wav
is: 24 kHz mono 16-bit, quiet ends trimmed to 0.1 s, speech leveled to render.SPEECH_LEVEL with the peak
under -1 dBFS. The take check's recognizer hears each one, so
clip.txt can follow what was said, not the script. Each take's pace is shown in words a minute: Pocket copies
a clip's pace into every workout (and speaks about a tenth faster), so pick a take inside CLIP_WPM.

Takes go in .cache/design/takes/<coach>/<designer>-<seed>.wav, with takes.json (every take's numbers), and
.cache/design/listen/index.html plays them side by side.
"""
import argparse
import html
import json
import os
import subprocess
import sys
import tomllib

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "coachmaker"))
import asr  # noqa: E402
import bench  # noqa: E402
import ffmpeg as ffmpeg_tool  # noqa: E402
import paths  # noqa: E402
import render  # noqa: E402
import verify  # noqa: E402
from char_weight import weight  # noqa: E402

ROOT = paths.ROOT
ROSTER = os.path.join(ROOT, "coaches", "roster.toml")
WORK = os.path.join(ROOT, ".cache", "design")
TAKES = os.path.join(WORK, "takes")
LISTEN = os.path.join(WORK, "listen")
WORKER = os.path.join(TOOLS, "coachmaker", "design_worker.py")
EDGE = 0.1            # seconds of quiet kept at each end of a clip
PEAK = 0.89           # -1 dBFS
CLIP_WPM = (150, 175)   # a clip's pace; Pocket speaks a workout about a tenth faster than its clip


def roster():
    with open(ROSTER, "rb") as f:
        return tomllib.load(f)


def description(r, coach, designer=None, hint=None):
    hint = hint or r["designers"].get(designer, {}).get("pace_hint")
    return " ".join(x for x in (coach["description"], hint, r["studio"]) if x)


def env_python(env):
    folder = os.path.join(ROOT, env, ".venv")
    exe = os.path.join(folder, "Scripts", "python.exe") if os.name == "nt" else os.path.join(folder, "bin", "python")
    if not os.path.exists(exe):
        raise SystemExit(f"No environment at {env}; make it first (see docs/plans/15.0.0-ten-local-coaches.md).")
    return exe


def model_dir(repo, revision):
    path = os.path.join(paths.MODELS, "models--" + repo.replace("/", "--"), "snapshots", revision)
    if not os.path.isdir(path):
        raise SystemExit(f"{repo} at {revision[:8]} isn't in models/.")
    return path


def wpm(text, seconds):
    return round(len(text.split()) / seconds * 60) if seconds else 0


def run_designer(r, name, coaches, seeds, text, hint=None):
    d = r["designers"][name]
    job = {"designer": name, "model_dir": model_dir(d["repo"], d["revision"]), "out": TAKES,
           "takes": [{"slug": c["slug"], "description": description(r, c, name, hint), "text": text, "seed": s}
                     for c in coaches for s in seeds]}
    os.makedirs(WORK, exist_ok=True)
    job_path = os.path.join(WORK, f"{name}-job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    env = dict(os.environ, HF_HUB_OFFLINE="1", PYTHONIOENCODING="utf-8")
    print(f"\n{name}: {len(job['takes'])} take(s)", flush=True)
    code = subprocess.call([env_python(d["env"]), WORKER, job_path], cwd=ROOT, env=env)
    with open(os.path.join(TAKES, f"{name}-render.json"), encoding="utf-8") as f:
        rec = json.load(f)
    if code:
        print(f"{name} stopped (exit {code}); the takes it made are kept.", flush=True)
    return rec


def to_clip(raw):
    """A raw take as a clip candidate: 24 kHz mono 16-bit PCM, ends trimmed, speech leveled."""
    import numpy as np
    pcm = bench.pcm_24k(raw)
    a = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    frame = int(0.01 * verify.SR)
    n = len(a) // frame
    db = 10 * np.log10(np.mean((a[: n * frame].reshape(n, frame) / 32768) ** 2, axis=1) + 1e-12)
    loud = np.nonzero(db > verify.QUIET_DB + 5)[0]
    if len(loud):
        start = max(0, loud[0] * frame - int(EDGE * verify.SR))
        end = min(len(a), (loud[-1] + 1) * frame + int(EDGE * verify.SR))
        a = a[start:end]
    found = render.speech_level(a.astype("<i2").tobytes())
    gain = 10 ** ((render.SPEECH_LEVEL - found) / 20) if found is not None else 1.0
    gain = min(gain, PEAK * 32767 / max(1.0, float(np.abs(a).max())))
    return np.clip(a * gain, -32768, 32767).astype("<i2").tobytes()


def write_wav(path, pcm):
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(verify.SR)
        w.writeframes(pcm)


def to_mp3(wav, mp3):
    subprocess.run([ffmpeg_tool.exe(), "-y", "-v", "error", "-i", wav, "-c:a", "libmp3lame", "-b:a", "128k", mp3],
                   check=True)


def transcribe(wavs):
    return asr.transcribe(wavs, os.path.join(WORK, "asr"))


def load_takes():
    path = os.path.join(TAKES, "takes.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_takes(takes):
    path = os.path.join(TAKES, "takes.json")
    with open(path + ".part", "w", encoding="utf-8") as f:
        json.dump(takes, f, indent=1)
    os.replace(path + ".part", path)


def listening_page(r, takes):
    """index.html in .cache/design/listen: every coach's takes, side by side, with their numbers."""
    os.makedirs(LISTEN, exist_ok=True)
    rows = []
    names = {c["slug"]: c for c in r["coach"]}
    for slug in [c["slug"] for c in r["coach"] if any(t["slug"] == c["slug"] for t in takes.values())]:
        c = names[slug]
        rows.append(f"<h2>{html.escape(c['name'])}</h2><p class=d>{html.escape(c['description'])}</p><table>"
                    "<tr><th>Take</th><th></th><th>Length</th><th>Errors</th><th>Problems</th><th>Heard</th></tr>")
        for key, t in sorted((k, t) for k, t in takes.items() if t["slug"] == slug):
            mp3 = os.path.relpath(t["mp3"], LISTEN).replace(os.sep, "/")
            length = t["seconds"]
            pace = wpm(t.get("text") or r["script"], length)
            flag = "" if CLIP_WPM[0] <= pace <= CLIP_WPM[1] else " class=bad"
            rows.append(f"<tr><td><b>{html.escape(t['label'])}</b></td><td><audio controls preload=none "
                        f"src='{mp3}'></audio></td><td{flag}>{length:.1f} s, {pace} wpm</td>"
                        f"<td>{t.get('errors', '?')}/{t.get('words', '?')}"
                        f"{' missed ' + ', '.join(t['missed_cues']) if t.get('missed_cues') else ''}</td>"
                        f"<td>{html.escape(', '.join(t.get('problems') or []))}</td>"
                        f"<td class=h>{html.escape(t.get('heard') or '')}</td></tr>")
        rows.append("</table>")
    page = ("<!doctype html><meta charset=utf-8><title>Coach takes</title><style>body{font:15px system-ui;"
            "margin:24px;max-width:1400px}td,th{padding:4px 8px;text-align:left;vertical-align:top}"
            ".d{color:#555}.h{font-size:12px;color:#444;max-width:520px}.bad{color:#b00}</style>"
            "<h1>Coach takes</h1><p>Each take as its clip would ship: trimmed, leveled. Pace in red is outside "
            f"{CLIP_WPM[0]} to {CLIP_WPM[1]} words a minute. Errors: words the recognizer heard differently "
            "from the script.</p>" + "".join(rows))
    path = os.path.join(LISTEN, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("coaches", nargs="+", help="coach slugs from coaches/roster.toml")
    p.add_argument("--designers", default="qwen3")
    p.add_argument("--takes", type=int, default=3)
    p.add_argument("--pace-hint", help="a pace line in place of the roster's, to try one")
    p.add_argument("--seed", type=int, default=101, help="the first take's seed; the next takes count up")
    p.add_argument("--no-render", action="store_true",
                   help="process the takes a designer already rendered (its <designer>-render.json) instead")
    a = p.parse_args(argv)
    r = roster()
    by_slug = {c["slug"]: c for c in r["coach"]}
    unknown = [s for s in a.coaches if s not in by_slug]
    if unknown:
        raise SystemExit(f"Not in the roster: {', '.join(unknown)}")
    coaches = [by_slug[s] for s in a.coaches]
    seeds = list(range(a.seed, a.seed + a.takes))
    takes = load_takes()
    fresh = []
    for name in a.designers.split(","):
        if name not in r["designers"]:
            raise SystemExit(f"Unknown designer {name}; the roster has {', '.join(r['designers'])}")
        if a.no_render:
            with open(os.path.join(TAKES, f"{name}-render.json"), encoding="utf-8") as f:
                rec = json.load(f)
            rec["takes"] = [t for t in rec["takes"] if t["slug"] in a.coaches and t["seed"] in seeds]
        else:
            rec = run_designer(r, name, coaches, seeds, r["script"], a.pace_hint)
        for t in rec["takes"]:
            if "wav" not in t:
                continue
            key = f"{t['slug']}/{name}-{t['seed']}"
            wav = t["wav"].replace(".raw.wav", ".wav")
            pcm = to_clip(t["wav"])
            write_wav(wav, pcm)
            mp3 = os.path.join(LISTEN, t["slug"], f"{name}-{t['seed']}.mp3")
            os.makedirs(os.path.dirname(mp3), exist_ok=True)
            to_mp3(wav, mp3)
            takes[key] = {"slug": t["slug"], "designer": name, "seed": t["seed"], "label": f"{name} {t['seed']}",
                          "wav": wav, "mp3": mp3, "seconds": round(len(pcm) / 2 / verify.SR, 2),
                          "render_s": t["render_s"], "source_sr": t["sr"],
                          "revision": r["designers"][name]["revision"], "description": description(r, by_slug[t["slug"]], name, a.pace_hint),
                          "text": t.get("text") or r["script"],
                          "device": rec.get("gpu"), "runtime": rec.get("runtime")}
            fresh.append(key)
    heard = transcribe([takes[k]["wav"] for k in fresh])
    for k in fresh:
        t = takes[k]
        if heard.get(t["wav"]) is not None:
            with open(t["wav"], "rb") as f:
                pcm = f.read()[44:]
            v = verify.judge(t["text"], heard[t["wav"]], pcm, weight(t["text"]) / bench.PACE)
            t.update(heard=v["heard"], words=v["words"], errors=v["errors"], missed_cues=v["missed_cues"],
                     problems=v["problems"])
            t["level_db"] = round(render.speech_level(pcm) or 0, 2)
    save_takes(takes)
    page = listening_page(r, takes)
    print(f"\n{len(fresh)} take(s). Listen: {page}")
    for k in fresh:
        t = takes[k]
        print(f"  {k}: {t['seconds']:.1f}s at {wpm(t['text'], t['seconds'])} wpm, "
              f"{t.get('errors', '?')}/{t.get('words', '?')} words off"
              + (f", problems: {', '.join(t['problems'])}" if t.get("problems") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
