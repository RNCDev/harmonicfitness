"""QA for the shipped coaches (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/qa.py andy claire ...        (no names: every coach in the roster)
  .venv/Scripts/python tools/coachmaker/qa.py --device cuda      (the PC's NVIDIA card)

For each coach, the audio bench's 44 lines (docs/audio-bench/script.toml), one seed, on Pocket TTS from the
coach's pocket.safetensors, through the PUBLIC model only, as a listener's computer runs it: a Hugging Face
cache that holds nothing else, and no login (a saved token would load the gated model). A line whose first
take fails gets the retries a build gives it. The audio bench's recognizer (Parakeet 0.6B, coachmaker/asr.py)
hears every take and tools/verify.py judges it as a build's take check does.

A coach passes with no line still failing after its retries and a word error rate under MAX_WER, and Pocket
must speak at a coaching pace (MIN_WPM to MAX_WPM words a minute, on the lines of ten words or more): it
copies the clip's pace into every workout, and a little faster. With Chatterbox's speaker encoder (from the Turbo environment, used here only to measure), the
coach's takes must sound like its clip (at least SAME_MIN), no two coaches' clips alike (under APART_MAX), and
no more than MAX_DRIFTING lines drift from the clip (under DRIFT_MIN). Pace (weighted characters a second,
trimmed as a render trims) is measured too.

The numbers don't replace the ear: .cache/design/qa/index.html plays each coach's lines end to end, and the
maintainer approves every coach by listening before it ships.

Results: .cache/design/qa/report.json, report.md and index.html; the takes stay in .cache/design/qa/<coach>/.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import wave

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "coachmaker"))
import asr  # noqa: E402
import bench  # noqa: E402
import paths  # noqa: E402
import verify  # noqa: E402
from char_weight import weight  # noqa: E402

ROOT = paths.ROOT
COACHES = os.path.join(ROOT, "coaches")
QA = os.path.join(ROOT, ".cache", "design", "qa")
PUBLIC_HF = os.path.join(ROOT, ".cache", "design", "public-hf")
POCKET_PUBLIC = "models--kyutai--pocket-tts-without-voice-cloning"
LANGUAGE = "english_2026-10"
ENVS = os.path.join(ROOT, ".cache", "bench", "envs")
EMBED_WORKER = os.path.join(TOOLS, "coachmaker", "embed_worker.py")
SEED = 42
RETRY_SEEDS = (43, 44, 45)   # as a build's take check retries a failing line
MAX_WER = 0.015
MIN_WPM, MAX_WPM = 150, 195  # Pocket's pace on the coach's takes (2026-10-26: Kate 190, Marcus 250)
PACE_WORDS = 10     # lines this long or longer measure it
SAME_MIN = 0.80      # the coach's takes against its clip
APART_MAX = 0.85     # any two coaches' clips
DRIFT_MIN = 0.70     # one line against the coach's clip, below which it's said to drift
MAX_DRIFTING = 2     # lines of the 44 that may drift before the coach fails
DRIFT_SECONDS = 2.5  # shorter lines are too short for the speaker encoder to judge
LIST_WORST = 5       # lines listed first for listening
TRIM_DB = -50.0      # as engines.trim: a take's edges below this are cut, keeping TRIM_KEEP
TRIM_KEEP = 0.04


def env_python(name):
    folder = os.path.join(ENVS, name, ".venv")
    return os.path.join(folder, "Scripts", "python.exe") if os.name == "nt" else os.path.join(folder, "bin", "python")


def public_cache():
    """A Hugging Face cache holding only the public Pocket model, so the gated one can't load by accident.
    Pocket fetches what its language config names into it (the cache in models/ may not hold every file)."""
    dest = os.path.join(PUBLIC_HF, POCKET_PUBLIC)
    if not os.path.isdir(dest):
        shutil.copytree(os.path.join(paths.MODELS, POCKET_PUBLIC), dest, symlinks=False)
    gated = os.path.join(PUBLIC_HF, "models--kyutai--pocket-tts")
    if os.path.isdir(gated):
        shutil.rmtree(gated)
    return PUBLIC_HF


def run(slug, lines, device, seeds=(SEED,), sub=""):
    folder = os.path.join(COACHES, f"coach-{slug}-local")
    out = os.path.join(QA, slug, "pocket", sub) if sub else os.path.join(QA, slug, "pocket")
    job = {"model": "pocket", "device": device, "engine": "pocket", "repo": "kyutai/pocket-tts-without-voice-cloning",
           "language": LANGUAGE, "public_only": True, "ref_audio": os.path.join(folder, "pocket.safetensors"),
           "out": out, "seeds": list(seeds), "lines": [{"id": l["id"], "text": l["text"]} for l in lines]}
    os.makedirs(out, exist_ok=True)
    job_path = os.path.join(out, "job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    # No saved login: a listener has none, and with one Pocket loads the gated model.
    env = dict(os.environ, HF_HUB_CACHE=public_cache(), HF_HOME=os.path.join(PUBLIC_HF, "home"),
               HF_HUB_DISABLE_IMPLICIT_TOKEN="1", PYTHONIOENCODING="utf-8")
    env.pop("HF_TOKEN", None)
    with open(os.path.join(out, "worker.log"), "w", encoding="utf-8") as log:
        code = subprocess.call([env_python(f"pocket-{device}"), "-I", bench.WORKER, "render", job_path],
                               stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=env)
    with open(os.path.join(out, "render.json"), encoding="utf-8") as f:
        rec = json.load(f)
    if code or rec.get("error"):
        raise SystemExit(f"{slug}: {rec.get('error') or f'exit {code}'}; see {out}/worker.log")
    return rec


def trimmed_seconds(pcm):
    import numpy as np
    a = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    loud = np.flatnonzero(np.abs(a) > 10 ** (TRIM_DB / 20))
    if not len(loud):
        return 0.0
    keep = int(TRIM_KEEP * verify.SR)
    return (min(len(a), loud[-1] + keep) - max(0, loud[0] - keep)) / verify.SR


def clip_wpm(slug):
    folder = os.path.join(COACHES, f"coach-{slug}-local")
    with open(os.path.join(folder, "clip.txt"), encoding="utf-8") as f:
        words = len(f.read().split())
    with wave.open(os.path.join(folder, "clip.wav")) as w:
        secs = w.getnframes() / w.getframerate()
    return round(words / secs * 60), round(secs, 1)


def embed(groups, device):
    out = os.path.join(QA, "embeddings.json")
    job = {"ve": bench_turbo_dir(), "groups": groups, "out": out}
    job_path = os.path.join(QA, "embed-job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f)
    env = dict(os.environ, HF_HUB_CACHE=paths.MODELS, HF_HUB_OFFLINE="1", PYTHONIOENCODING="utf-8")
    subprocess.run([env_python(f"turbo-{device}"), "-I", EMBED_WORKER, job_path], check=True, cwd=ROOT, env=env)
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def bench_turbo_dir():
    spec = bench.PC["turbo"]
    return os.path.join(paths.MODELS, "models--" + spec["repo"].replace("/", "--"), "snapshots", spec["revision"])


def listen_page(report, wavs, by_id):
    """.cache/design/qa/index.html: each coach's 44 lines end to end, for the manual check, and the lines that
    sound least like the clip, to hear first."""
    import html
    rows = []
    for slug, c in report["coaches"].items():
        ids = [i for (s, i) in wavs if s == slug]
        mp3 = os.path.join(QA, "listen", f"{slug}.mp3")
        bench.listening_file([bench.pcm_24k(wavs[slug, i]) for i in ids], mp3)
        rows.append(f"<h2>{html.escape(slug)} {'passes' if c['pass'] else 'FAILS: ' + html.escape('; '.join(c['fails']))}"
                    f"</h2><p>Clip {c['clip_seconds']} s at {c['clip_wpm']} wpm; Pocket at {c['wpm']} wpm. WER {c['wer']:.1%}. Still failing: "
                    f"{html.escape(', '.join(c['not_ok']) or 'none')}. Like its clip: {c['like_clip']}. Closest "
                    f"other coach: {html.escape(str(c['closest'][:1]))}</p>"
                    f"<p><audio controls preload=none src='listen/{slug}.mp3'></audio></p><p>Least like the clip:</p><ul>")
        for sim, i in c["worst_lines"]:
            rel = os.path.relpath(wavs[slug, i], QA).replace(os.sep, "/")
            rows.append(f"<li>{sim} <i>{html.escape(by_id[i]['text'])}</i> "
                        f"<audio controls preload=none src='{rel}'></audio></li>")
        rows.append("</ul>")
    with open(os.path.join(QA, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset=utf-8><title>Coach QA</title><style>body{font:15px system-ui;"
                "margin:24px;max-width:1100px}audio{width:520px;vertical-align:middle}</style><h1>Coach QA</h1>"
                "<p>Each coach's bench lines end to end on Pocket. Listen for lines that sound off: odd "
                "intonation, rushing, long gaps, or the voice drifting toward someone else.</p>" + "".join(rows))


def cos(a, b):
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("coaches", nargs="*")
    p.add_argument("--device", choices=("cpu", "cuda"), default="cpu",
                   help="where Pocket runs (the environment .cache/bench/envs/pocket-<device>); default cpu")
    p.add_argument("--no-render", action="store_true", help="score the takes already in .cache/design/qa")
    a = p.parse_args(argv)
    import tomllib
    with open(os.path.join(COACHES, "roster.toml"), "rb") as f:
        roster = tomllib.load(f)
    slugs = a.coaches or [c["slug"] for c in roster["coach"]]
    lines = bench.load_script()
    by_id = {l["id"]: l for l in lines}
    os.makedirs(QA, exist_ok=True)

    recs = {}
    for slug in slugs:
        if a.no_render:
            with open(os.path.join(QA, slug, "pocket", "render.json"), encoding="utf-8") as f:
                recs[slug] = json.load(f)
        else:
            print(f"{slug}: rendering on Pocket ({a.device})", flush=True)
            recs[slug] = run(slug, lines, a.device)

    wavs = {(slug, t["id"]): os.path.join(QA, slug, "pocket", str(SEED), t["id"] + ".wav")
            for slug, rec in recs.items() for t in rec["takes"] if "audio_s" in t}
    heard = asr.transcribe(list(wavs.values()), os.path.join(QA, "asr"))

    def judge(path, line_id):
        text = by_id[line_id]["text"]
        return verify.judge(text, heard.get(path) or "", bench.pcm_24k(path), weight(text) / bench.PACE)

    first = {key: judge(w, key[1]) for key, w in wavs.items()}

    # A line whose first take fails gets more takes, as a build's take check gives it; it fails QA only if
    # none of them is clean, the way a build would stop on it (a dropped cue) or keep a flawed take.
    retakes = {}
    for slug, rec in recs.items():
        bad = [t["id"] for t in rec["takes"] if not first.get((slug, t["id"]), {"ok": False})["ok"]]
        if not bad:
            continue
        if not a.no_render:
            print(f"{slug}: {len(bad)} line(s) again", flush=True)
            run(slug, [by_id[i] for i in bad], a.device, RETRY_SEEDS, "retry")
        for i in bad:
            for s in RETRY_SEEDS:
                p_ = os.path.join(QA, slug, "pocket", "retry", str(s), i + ".wav")
                if os.path.exists(p_):
                    retakes.setdefault((slug, i), []).append(p_)
    heard.update(asr.transcribe([p_ for ps in retakes.values() for p_ in ps], os.path.join(QA, "retry-asr")))

    report = {"coaches": {}, "limits": {"max_wer": MAX_WER, "wpm": [MIN_WPM, MAX_WPM], "same_min": SAME_MIN,
                                        "apart_max": APART_MAX, "drift_min": DRIFT_MIN, "drift_seconds": DRIFT_SECONDS}}
    seconds = {}
    for slug in slugs:
        rec = recs[slug]
        words = errors = 0
        first_bad, still_bad, heard_bad, w_sum, s_sum, r_sum = [], [], {}, 0.0, 0.0, 0.0
        long_words, long_s = 0, 0.0
        for t in rec["takes"]:
            key = (slug, t["id"])
            takes = ([first[key]] if key in first else []) + [judge(p_, t["id"]) for p_ in retakes.get(key, [])]
            if key not in wavs or not first[key]["ok"]:
                first_bad.append(t["id"])
            if not any(v["ok"] for v in takes):
                still_bad.append(t["id"])
                heard_bad[t["id"]] = [heard.get(w) for w in ([wavs[key]] if key in wavs else []) + retakes.get(key, [])]
            if key not in wavs:
                continue
            v = first[key]
            words += v["words"]
            errors += v["errors"]
            seconds[key] = trimmed_seconds(bench.pcm_24k(wavs[key]))
            w_sum += weight(by_id[t["id"]]["text"])
            s_sum += seconds[key]
            r_sum += t["render_s"]
            n = len(by_id[t["id"]]["text"].split())
            if n >= PACE_WORDS:
                long_words, long_s = long_words + n, long_s + seconds[key]
        wpm, clip_s = clip_wpm(slug)
        report["coaches"][slug] = {"takes": len(rec["takes"]), "wer": round(errors / max(words, 1), 4),
                                   "first_take_not_ok": first_bad, "not_ok": still_bad, "heard": heard_bad,
                                   "clip_wpm": wpm, "clip_seconds": clip_s,
                                   "wpm": round(long_words / long_s * 60) if long_s else 0,
                                   "pace": round(w_sum / s_sum, 2) if s_sum else None,
                                   "render_ratio": round(r_sum / s_sum, 3) if s_sum else None}

    groups = {}
    for slug in slugs:
        groups[f"{slug}/clip"] = [os.path.join(COACHES, f"coach-{slug}-local", "clip.wav")]
        groups[f"{slug}/pocket"] = [w for (s, _), w in wavs.items() if s == slug]
    for (s, i), w in wavs.items():   # every line on its own, to find the ones that drift
        groups[f"{s}/{i}"] = [w]
    print("Speaker embeddings", flush=True)
    emb = embed(groups, a.device)
    every = [c["slug"] for c in roster["coach"]
             if os.path.exists(os.path.join(COACHES, f"coach-{c['slug']}-local", "clip.wav"))]
    if set(every) - set(slugs):   # compare against coaches not in this run too
        emb.update(embed({f"{s}/clip": [os.path.join(COACHES, f"coach-{s}-local", "clip.wav")]
                          for s in every if s not in slugs}, a.device))
    for slug in slugs:
        c = report["coaches"][slug]
        c["like_clip"] = round(cos(emb[f"{slug}/pocket"], emb[f"{slug}/clip"]), 3)
        near = sorted(((round(cos(emb[f"{slug}/clip"], emb[f"{o}/clip"]), 3), o) for o in every if o != slug),
                      reverse=True)
        c["closest"] = near[:2]
        lines_sim = sorted((round(cos(emb[f"{s}/{i}"], emb[f"{slug}/clip"]), 3), i) for (s, i) in wavs if s == slug)
        lines_sim = [x for x in lines_sim if seconds.get((slug, x[1]), 0) >= DRIFT_SECONDS]
        c["worst_lines"] = lines_sim[:LIST_WORST]
        c["drifting"] = [x for x in lines_sim if x[0] < DRIFT_MIN]
        fails = []
        if c["not_ok"]:
            fails.append(f"{len(c['not_ok'])} line(s) fail every take: {', '.join(c['not_ok'])}")
        if c["wer"] >= MAX_WER:
            fails.append(f"WER {c['wer']:.1%}")
        if not MIN_WPM <= c["wpm"] <= MAX_WPM:
            fails.append(f"speaks at {c['wpm']} wpm")
        if c["like_clip"] < SAME_MIN:
            fails.append(f"unlike its clip ({c['like_clip']})")
        if near and near[0][0] >= APART_MAX:
            fails.append(f"sounds like {near[0][1]} ({near[0][0]})")
        if len(c["drifting"]) > MAX_DRIFTING:
            fails.append(f"{len(c['drifting'])} lines drift from the clip")
        c["fails"] = fails
        c["pass"] = not fails

    with open(os.path.join(QA, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    listen_page(report, wavs, by_id)
    md = ["| Coach | Pass | Clip | Pocket wpm | WER | First take bad, still bad | Like clip | Closest coach | Pace |",
          "|---|---|---|---|---|---|---|---|---|"]
    for slug, c in report["coaches"].items():
        md.append(f"| {slug} | {'yes' if c['pass'] else 'NO: ' + '; '.join(c['fails'])} | {c['clip_seconds']} s, "
                  f"{c['clip_wpm']} wpm | {c['wpm']} | {c['wer']:.1%} | {len(c['first_take_not_ok'])}, {len(c['not_ok'])} | "
                  f"{c['like_clip']} | {c['closest'][0][1] if c['closest'] else '-'} "
                  f"{c['closest'][0][0] if c['closest'] else ''} | {c['pace']} |")
    with open(os.path.join(QA, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0 if all(c["pass"] for c in report["coaches"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
