"""QA for the shipped coaches (maintainer only; not a listener command).

  .venv/Scripts/python tools/coachmaker/qa.py andy claire ...      (no names: every coach in the roster)

For each coach, the audio bench's 44 lines (docs/audio-bench/script.toml), one seed, on both of a listener's
engines, through the bench's worker on the NVIDIA card:
- Pocket TTS from the coach's pocket.safetensors, through the PUBLIC model only (a Hugging Face cache that
  holds nothing else, offline), as a listener's computer runs it;
- Chatterbox Turbo from clip.wav.
The take check's recognizer (Parakeet 110M, coachmaker/asr.py) hears every take and tools/verify.py judges
it as a build's take check does.

A coach passes with no missed cue and no audio problem on either engine, and a word error rate under
MAX_WER on each. Two more checks, with Chatterbox's speaker encoder: the coach's Pocket and Turbo takes
sound like the same person (similarity at least SAME_MIN), and no two coaches sound alike (pairwise
similarity of their clips under APART_MAX). Each coach's pace (weighted characters a second, trimmed as a
render trims) is measured on both engines too.

Every line is also scored on its own against the clip, so a coach whose lines drift toward another voice
fails (more than MAX_DRIFTING under DRIFT_MIN), and the worst few are listed. The numbers don't replace the
ear: .cache/design/qa/index.html plays each coach's lines end to end on each engine, and the maintainer
approves every coach by listening before it ships.

Results: .cache/design/qa/report.json, report.md and index.html; the takes stay in .cache/design/qa/<coach>/.
"""
import argparse
import json
import os
import shutil
import sys

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
RETRY_SEEDS = (43, 44, 45)   # a line that fails its first take gets these, as a build's take check retries
MAX_WER = 0.015
SAME_MIN = 0.80      # Pocket's and Turbo's takes of one coach
APART_MAX = 0.85     # any two coaches' clips
DRIFT_MIN = 0.70     # one line against the coach's clip, below which it's said to drift (calibrate on the first run)
MAX_DRIFTING = 2     # lines of the 88 that may drift before the coach fails
DRIFT_SECONDS = 2.5  # shorter lines ("Go.") are too short for the speaker encoder to judge
LIST_WORST = 5       # lines listed first for listening
TRIM_DB = -50.0      # as engines.trim: a take's edges below this are cut, keeping TRIM_KEEP
TRIM_KEEP = 0.04


def env_python(name):
    folder = os.path.join(ENVS, name, ".venv")
    return os.path.join(folder, "Scripts", "python.exe") if os.name == "nt" else os.path.join(folder, "bin", "python")


def public_cache():
    """A Hugging Face cache holding only the public Pocket model, so the gated one can't load by accident."""
    dest = os.path.join(PUBLIC_HF, POCKET_PUBLIC)
    if not os.path.isdir(dest):
        shutil.copytree(os.path.join(paths.MODELS, POCKET_PUBLIC), dest, symlinks=False)
    return PUBLIC_HF


def run(engine, slug, lines, seeds=(SEED,), sub=""):
    folder = os.path.join(COACHES, f"coach-{slug}-local")
    out = os.path.join(QA, slug, engine, sub) if sub else os.path.join(QA, slug, engine)
    if engine == "pocket":
        job = {"model": "pocket", "device": "cuda", "engine": "pocket", "repo": "kyutai/pocket-tts-without-voice-cloning",
               "language": LANGUAGE, "public_only": True,
               "ref_audio": os.path.join(folder, "pocket.safetensors")}
        cmd = [env_python("pocket-cuda"), "-I", bench.WORKER]
        env = dict(os.environ, HF_HUB_CACHE=public_cache(), HF_HUB_OFFLINE="1", PYTHONIOENCODING="utf-8")
    else:
        spec = bench.PC["turbo"]
        job = {"model": "turbo", "device": "cuda", "engine": "chatterbox", "repo": spec["repo"],
               "revision": spec["revision"], "ref_audio": os.path.join(folder, "clip.wav")}
        cmd = [env_python("turbo-cuda"), "-I", bench.WORKER]
        env = dict(os.environ, HF_HUB_CACHE=paths.MODELS, HF_HUB_OFFLINE="1", PYTHONIOENCODING="utf-8")
    job.update(out=out, seeds=list(seeds), lines=[{"id": l["id"], "text": l["text"]} for l in lines])
    os.makedirs(out, exist_ok=True)
    job_path = os.path.join(out, "job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    import subprocess
    with open(os.path.join(out, "worker.log"), "w", encoding="utf-8") as log:
        code = subprocess.call([*cmd, "render", job_path], stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, env=env)
    with open(os.path.join(out, "render.json"), encoding="utf-8") as f:
        rec = json.load(f)
    if code or rec.get("error"):
        raise SystemExit(f"{slug} on {engine}: {rec.get('error') or f'exit {code}'}; see {out}/worker.log")
    return rec


def trimmed_seconds(pcm):
    import numpy as np
    a = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    loud = np.flatnonzero(np.abs(a) > 10 ** (TRIM_DB / 20))
    if not len(loud):
        return 0.0
    keep = int(TRIM_KEEP * verify.SR)
    return (min(len(a), loud[-1] + keep) - max(0, loud[0] - keep)) / verify.SR


def embed(groups):
    out = os.path.join(QA, "embeddings.json")
    job = {"ve": bench_turbo_dir(), "groups": groups, "out": out}
    job_path = os.path.join(QA, "embed-job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f)
    import subprocess
    env = dict(os.environ, HF_HUB_CACHE=paths.MODELS, HF_HUB_OFFLINE="1", PYTHONIOENCODING="utf-8")
    subprocess.run([env_python("turbo-cuda"), "-I", EMBED_WORKER, job_path], check=True, cwd=ROOT, env=env)
    with open(out, encoding="utf-8") as f:
        return json.load(f)


def bench_turbo_dir():
    spec = bench.PC["turbo"]
    return os.path.join(paths.MODELS, "models--" + spec["repo"].replace("/", "--"), "snapshots", spec["revision"])


def listen_page(report, wavs, by_id):
    """.cache/design/qa/index.html: each coach's 44 lines end to end on each engine, for the manual check,
    and the lines that sound least like the clip, to hear first."""
    import html
    rows = []
    for slug, c in report["coaches"].items():
        rows.append(f"<h2>{html.escape(slug)} {'passes' if c['pass'] else 'FAILS: ' + html.escape('; '.join(c['fails']))}"
                    f"</h2><p>Same person on both engines: {c['same_person']}. Closest other coach: "
                    f"{html.escape(str(c['closest'][:1]))}</p>")
        for engine in ("pocket", "turbo"):
            ids = [i for (s, e, i) in wavs if s == slug and e == engine]
            mp3 = os.path.join(QA, "listen", f"{slug}-{engine}.mp3")
            bench.listening_file([bench.pcm_24k(wavs[slug, engine, i]) for i in ids], mp3)
            e = c["engines"][engine]
            rows.append(f"<p><b>{engine}</b> WER {e['wer']:.1%}, not ok: {html.escape(', '.join(e['not_ok']) or 'none')}"
                        f"<br><audio controls preload=none src='listen/{slug}-{engine}.mp3'></audio></p>")
        rows.append("<p>Least like the clip:</p><ul>")
        for sim, engine, i in c["worst_lines"]:
            rel = os.path.relpath(wavs[slug, engine, i], QA).replace(os.sep, "/")
            rows.append(f"<li>{sim} {engine} <i>{html.escape(by_id[i]['text'])}</i> "
                        f"<audio controls preload=none src='{rel}'></audio></li>")
        rows.append("</ul>")
    with open(os.path.join(QA, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset=utf-8><title>Coach QA</title><style>body{font:15px system-ui;"
                "margin:24px;max-width:1100px}audio{width:520px;vertical-align:middle}</style><h1>Coach QA</h1>"
                "<p>Each coach's bench lines end to end on each engine. Listen for lines that sound off: odd "
                "intonation, rushing, or the voice drifting toward someone else.</p>" + "".join(rows))


def cos(a, b):
    import numpy as np
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("coaches", nargs="*")
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
        for engine in ("pocket", "turbo"):
            if a.no_render:
                with open(os.path.join(QA, slug, engine, "render.json"), encoding="utf-8") as f:
                    recs[slug, engine] = json.load(f)
            else:
                print(f"{slug}: rendering on {engine}", flush=True)
                recs[slug, engine] = run(engine, slug, lines)

    wavs = {(slug, engine, t["id"]): os.path.join(QA, slug, engine, str(SEED), t["id"] + ".wav")
            for (slug, engine), rec in recs.items() for t in rec["takes"] if "audio_s" in t}
    heard = asr.transcribe(list(wavs.values()), QA)

    def judge(path, line_id):
        text = by_id[line_id]["text"]
        return verify.judge(text, heard.get(path) or "", bench.pcm_24k(path), weight(text) / bench.PACE)

    first = {key: judge(w, key[2]) for key, w in wavs.items()}

    # A line whose first take fails gets more takes, as a build's take check gives it; it fails QA only if
    # none of them is clean, the way a build would stop on it (a dropped cue) or keep a flawed take.
    retakes = {}
    for (slug, engine), rec in recs.items():
        bad = [t["id"] for t in rec["takes"] if not first.get((slug, engine, t["id"]), {"ok": False})["ok"]]
        if not bad:
            continue
        if not a.no_render:
            print(f"{slug}: {len(bad)} line(s) again on {engine}", flush=True)
            run(engine, slug, [by_id[i] for i in bad], RETRY_SEEDS, "retry")
        for i in bad:
            for s in RETRY_SEEDS:
                p_ = os.path.join(QA, slug, engine, "retry", str(s), i + ".wav")
                if os.path.exists(p_):
                    retakes.setdefault((slug, engine, i), []).append(p_)
    heard.update(asr.transcribe([p_ for ps in retakes.values() for p_ in ps], os.path.join(QA, "retry-asr")))

    report = {"coaches": {}, "limits": {"max_wer": MAX_WER, "same_min": SAME_MIN, "apart_max": APART_MAX,
                                        "drift_min": DRIFT_MIN, "drift_seconds": DRIFT_SECONDS}}
    seconds = {}
    for slug in slugs:
        c = report["coaches"][slug] = {"engines": {}}
        for engine in ("pocket", "turbo"):
            rec = recs[slug, engine]
            words = errors = 0
            missed, problems, first_bad, still_bad, w_sum, s_sum, r_sum = [], [], [], [], 0.0, 0.0, 0.0
            for t in rec["takes"]:
                key = (slug, engine, t["id"])
                takes = ([first[key]] if key in first else []) + [judge(p_, t["id"]) for p_ in retakes.get(key, [])]
                if key not in wavs or not first[key]["ok"]:
                    first_bad.append(t["id"])
                if not any(v["ok"] for v in takes):
                    best = min(takes, key=lambda v: (len(v["missed_cues"]), len(v["problems"]), v["errors"]),
                               default=None)
                    still_bad.append(t["id"])
                    if best is None:
                        problems.append(f"{t['id']}: {t.get('error')}")
                    else:
                        missed += [f"{t['id']}: {m}" for m in best["missed_cues"]]
                        problems += [f"{t['id']}: {p_}" for p_ in best["problems"]]
                if key not in wavs:
                    continue
                v = first[key]
                words += v["words"]
                errors += v["errors"]
                pcm = bench.pcm_24k(wavs[key])
                seconds[key] = trimmed_seconds(pcm)
                w_sum += weight(by_id[t["id"]]["text"])
                s_sum += seconds[key]
                r_sum += t["render_s"]
            c["engines"][engine] = {"takes": len(rec["takes"]), "wer": round(errors / max(words, 1), 4),
                                    "first_take_not_ok": first_bad, "not_ok": still_bad,
                                    "missed_cues": missed, "problems": problems,
                                    "weight": round(w_sum, 1), "seconds": round(s_sum, 2),
                                    "pace": round(w_sum / s_sum, 2) if s_sum else None,
                                    "render_ratio": round(r_sum / s_sum, 3) if s_sum else None}

    groups = {}
    for slug in slugs:
        groups[f"{slug}/clip"] = [os.path.join(COACHES, f"coach-{slug}-local", "clip.wav")]
        for engine in ("pocket", "turbo"):
            groups[f"{slug}/{engine}"] = [w for (s, e, _), w in wavs.items() if s == slug and e == engine]
    for (s, e, i), w in wavs.items():   # every line on its own, to find the ones that drift
        groups[f"{s}/{e}/{i}"] = [w]
    print("Speaker embeddings", flush=True)
    emb = embed(groups)
    every = [c["slug"] for c in roster["coach"]
             if os.path.exists(os.path.join(COACHES, f"coach-{c['slug']}-local", "clip.wav"))]
    if set(every) - set(slugs):   # compare against coaches not in this run too
        extra = embed({f"{s}/clip": [os.path.join(COACHES, f"coach-{s}-local", "clip.wav")]
                       for s in every if s not in slugs})
        emb.update(extra)
    for slug in slugs:
        c = report["coaches"][slug]
        c["same_person"] = round(cos(emb[f"{slug}/pocket"], emb[f"{slug}/turbo"]), 3)
        c["pocket_vs_clip"] = round(cos(emb[f"{slug}/pocket"], emb[f"{slug}/clip"]), 3)
        c["turbo_vs_clip"] = round(cos(emb[f"{slug}/turbo"], emb[f"{slug}/clip"]), 3)
        near = sorted(((round(cos(emb[f"{slug}/clip"], emb[f"{o}/clip"]), 3), o) for o in every if o != slug),
                      reverse=True)
        c["closest"] = near[:2]
        lines_sim = sorted((round(cos(emb[f"{s}/{e}/{i}"], emb[f"{slug}/clip"]), 3), e, i)
                           for (s, e, i) in wavs if s == slug)
        lines_sim = [x for x in lines_sim if seconds.get((slug, x[1], x[2]), 0) >= DRIFT_SECONDS]
        c["worst_lines"] = lines_sim[:LIST_WORST]
        c["drifting"] = [x for x in lines_sim if x[0] < DRIFT_MIN]
        fails = []
        for engine, e in c["engines"].items():
            if e["missed_cues"]:
                fails.append(f"{engine} missed cues")
            if e["wer"] >= MAX_WER:
                fails.append(f"{engine} WER {e['wer']:.1%}")
        if c["same_person"] < SAME_MIN:
            fails.append(f"Pocket and Turbo differ ({c['same_person']})")
        if near and near[0][0] >= APART_MAX:
            fails.append(f"sounds like {near[0][1]} ({near[0][0]})")
        if len(c["drifting"]) > MAX_DRIFTING:
            fails.append(f"{len(c['drifting'])} lines drift from the clip")
        c["fails"] = fails
        c["pass"] = not fails

    with open(os.path.join(QA, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    listen_page(report, wavs, by_id)
    md = ["| Coach | Pass | Pocket WER | Turbo WER | Retried, still bad (P/T) | Same person | Closest coach | Pace P/T |",
          "|---|---|---|---|---|---|---|---|"]
    for slug, c in report["coaches"].items():
        p_, t_ = c["engines"]["pocket"], c["engines"]["turbo"]
        md.append(f"| {slug} | {'yes' if c['pass'] else 'NO: ' + '; '.join(c['fails'])} | {p_['wer']:.1%} | "
                  f"{t_['wer']:.1%} | {len(p_['first_take_not_ok'])}, {len(p_['not_ok'])} / {len(t_['first_take_not_ok'])}, {len(t_['not_ok'])} |{c['same_person']} | "
                  f"{c['closest'][0][1] if c['closest'] else '-'} {c['closest'][0][0] if c['closest'] else ''} | "
                  f"{p_['pace']}/{t_['pace']} |")
    with open(os.path.join(QA, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))
    return 0 if all(c["pass"] for c in report["coaches"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
