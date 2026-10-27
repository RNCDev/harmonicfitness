"""The audio bench: the same five-minute script (docs/audio-bench/script.toml) read by each candidate local
voice model on this computer, measured and scored the same way on a Mac and on a PC, so the models can be
compared and one chosen. It changes nothing a workout uses.

  ./sweatcast bench                  everything this computer can run: on a Mac, every model through MLX
                                     (Pocket TTS through PyTorch on the processor); on a PC, every model on
                                     the NVIDIA card if there is one, then the small ones on the processor
  ./sweatcast bench --quick          three lines, one seed: a check that every model installs and speaks
  ./sweatcast bench --models lure,pocket --seeds 1

For each model, tools/bench_worker.py runs in its own throwaway environment (uv run --isolated, or a small
uv project for PyTorch on a PC, so CUDA builds come from PyTorch's index), loads the model, and speaks every
line once per seed, cloning Coach Andy's clip. A model that won't install or load is recorded with why, and
the bench goes on. Then one recognizer, Parakeet TDT 0.6B v3 through ONNX (onnx-asr, the same on both
computers), transcribes every take, and tools/verify.py scores it as a build's take check does: the words,
the cue words, and what the audio alone shows.

Results land in docs/audio-bench/results/<date>-<mac|pc>/ (committed, for the analysis): run.json (the
computer, versions, settings and each model's summary), takes.jsonl (one row per take), summary.md, and
listen/<model>-<device>.mp3 (each model's first seed, laid end to end, for listening). The takes themselves
stay in .cache/bench/ (git-ignored); model downloads go to models/ like the voices'.
"""
import argparse
import datetime as dt
import json
import os
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
import tomllib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import ffmpeg as ffmpeg_tool  # noqa: E402
import paths  # noqa: E402
import render  # noqa: E402
import verify  # noqa: E402
from char_weight import weight  # noqa: E402

ROOT = paths.ROOT
BENCH = os.path.join(ROOT, "docs", "audio-bench")
SCRIPT = os.path.join(BENCH, "script.toml")
WORK = os.path.join(ROOT, ".cache", "bench")
WORKER = os.path.join(ROOT, "tools", "bench_worker.py")
COACH = os.path.join(ROOT, "docs", "audio-bench", "voice")   # Coach Andy's 8.x clip, so runs stay comparable
PYTHON = "3.11"
MLX_AUDIO = "mlx-audio==0.6.1"
TORCH = ["torch==2.6.0", "torchaudio==2.6.0"]
TORCH_INDEX = {"cuda": "https://download.pytorch.org/whl/cu124", "cpu": "https://download.pytorch.org/whl/cpu"}
ASR = ["onnx-asr[cpu,hub]==0.12.0"]
ASR_MODEL = ("istupakov/parakeet-tdt-0.6b-v3-onnx", "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce")
COMMON = ["psutil", "numpy", "soundfile"]
MING_GIT = ("https://github.com/inclusionAI/Ming-3.0-tts.git", "028c1eace193e7acdb256453da89b6e9207e052b")
GAP = 0.6             # seconds between lines in the listening file
PACE = 14.5           # weighted characters a second, for the runaway and cut-off checks
TIMEOUT = {"mlx": 45, "cuda": 45, "cpu": 90}   # minutes a model may take before it's stopped

# The candidates, per computer. engine: the speaker in bench_worker.py; pip: what its environment installs.
MAC = {
    "turbo": dict(engine="mlx", repo="mlx-community/chatterbox-turbo-fp16",
                  revision="b2d0a13aa7cfff0a06d9acb247ae91c8f19a6d75", pip=[MLX_AUDIO], prime_once=True),
    "qwen3": dict(engine="mlx", repo="mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
                  revision="a6eb4f68e4b056f1215157bb696209bc82a6db48", pip=[MLX_AUDIO], ref_text_needed=True),
    "lure": dict(engine="mlx", repo="Tesslate/Lure-TTS-0.6B", revision="9e6bc57acde4e3c9f3ccfe46697d8d5abafacbc8",
                 pip=[MLX_AUDIO], ref_text_needed=True),
    "ming": dict(engine="mlx", repo="mlx-community/Ming-3.0-tts-0.5B-bf16",
                 revision="283b3c342c6fb69a7a87832c97f9799567efe05d", pip=[MLX_AUDIO], ref_text_needed=True),
    "pocket": dict(engine="pocket", repo="kyutai/pocket-tts", pip=["pocket-tts==4.0.1"], device="cpu"),
}
PC = {
    "turbo": dict(engine="chatterbox", repo="ResembleAI/chatterbox-turbo",
                  revision="749d1c1a46eb10492095d68fbcf55691ccf137cd", pip=["chatterbox-tts==0.1.7", "setuptools<81"]),
    "qwen3": dict(engine="qwen-tts", repo="Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                  revision="fd4b254389122332181a7c3db7f27e918eec64e3", pip=["qwen-tts==0.1.1"], gpu_only=True),
    "lure": dict(engine="qwen-tts", repo="Tesslate/Lure-TTS-0.6B", revision="9e6bc57acde4e3c9f3ccfe46697d8d5abafacbc8",
                 pip=["qwen-tts==0.1.1"]),
    "ming": dict(engine="ming", repo="inclusionAI/Ming-3.0-tts-0.5B",
                 revision="8d66b70a00f05ad183fa8a863b4ce609fc83cbc0", pip=[], gpu_only=True),
    "pocket": dict(engine="pocket", repo="kyutai/pocket-tts", pip=["pocket-tts==4.0.1"]),
}
GATED = {"kyutai/pocket-tts": "https://huggingface.co/kyutai/pocket-tts"}


def load_script(path=SCRIPT):
    with open(path, "rb") as f:
        lines = tomllib.load(f)["line"]
    ids = [l["id"] for l in lines]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"{path}: two lines share an id")
    return lines


def computer():
    """What this computer is, without its name: the system, chip, memory and graphics card."""
    info = {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python": platform.python_version()}
    if sys.platform == "darwin":
        for key, name in (("chip", "machdep.cpu.brand_string"), ("memory_bytes", "hw.memsize")):
            try:
                info[key] = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True).stdout.strip()
            except OSError:
                pass
        info["macos"] = platform.mac_ver()[0]
    else:
        info["chip"] = platform.processor()
        info["cpu_count"] = os.cpu_count()
    info["gpu"] = nvidia()
    try:
        info["uv"] = subprocess.run(["uv", "--version"], capture_output=True, text=True).stdout.strip()
    except OSError:
        info["uv"] = None
    return info


def nvidia():
    """The NVIDIA card's name, memory and driver, or None."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return None
    try:
        out = subprocess.run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=20).stdout.strip().splitlines()
    except (OSError, subprocess.SubprocessError):
        return None
    if not out:
        return None
    name, mem, driver = [x.strip() for x in out[0].split(",")[:3]]
    return {"name": name, "memory": mem, "driver": driver}


def plan(models=None, as_pc=False):
    """[(model, device, spec)] this computer runs, in order. `as_pc` runs a PC's PyTorch setups on this
    computer's processor, every model included, to try the PC's paths from a Mac."""
    if as_pc:
        runs = [(m, "cpu", s) for m, s in PC.items()]
    elif sys.platform == "darwin" and platform.machine() == "arm64":
        runs = [(m, s.get("device", "mlx"), s) for m, s in MAC.items()]
    elif sys.platform == "darwin":
        raise SystemExit("The bench runs on an Apple Silicon Mac or a PC; this Mac has no MLX.")
    else:
        runs = [(m, "cuda", s) for m, s in PC.items()] if nvidia() else []
        runs += [(m, "cpu", s) for m, s in PC.items() if not s.get("gpu_only")]
    if models:
        unknown = set(models) - {m for m, _, _ in runs} - set(MAC) - set(PC)
        if unknown:
            raise cli.Usage(f"Unknown model(s): {', '.join(sorted(unknown))}. The candidates: {', '.join(MAC)}")
        runs = [r for r in runs if r[0] in models]
    return runs


def torch_project(folder, device, pip):
    """A small uv project that installs `pip` with PyTorch from its own index (CUDA 12.4 or the processor
    build), as sweatcast's pyproject does, so a PC gets the card's build and never the plain PyPI one."""
    os.makedirs(folder, exist_ok=True)
    deps = ", ".join(json.dumps(p) for p in [*TORCH, *pip, *COMMON])
    with open(os.path.join(folder, "pyproject.toml"), "w", encoding="utf-8") as f:
        f.write(f"""[project]
name = "bench-env"
version = "0"
requires-python = "=={PYTHON}.*"
dependencies = [{deps}]

[tool.uv]
package = false

[[tool.uv.index]]
name = "pytorch"
url = "{TORCH_INDEX[device]}"
explicit = true

[tool.uv.sources]
torch = {{ index = "pytorch" }}
torchaudio = {{ index = "pytorch" }}
""")
    return ["uv", "run", "--project", folder, "--python", PYTHON]


def ming_checkout():
    """Ming-3.0's code (it has no pip package) at the pinned commit, under .cache/bench/; its requirements
    without the optional ones that don't build on Windows (pynini, flash-attn)."""
    repo, commit = MING_GIT
    folder = os.path.join(WORK, "Ming-3.0-tts")
    if not os.path.isdir(os.path.join(folder, ".git")):
        subprocess.run(["git", "clone", "--quiet", repo, folder], check=True)
    subprocess.run(["git", "-C", folder, "fetch", "--quiet", "origin", commit], check=False)
    subprocess.run(["git", "-C", folder, "checkout", "--quiet", commit], check=True)
    with open(os.path.join(folder, "requirements.txt"), encoding="utf-8") as f:
        reqs = [r.split("#")[0].strip() for r in f]
    reqs = [r for r in reqs if r and not re.match(r"(torch|torchaudio|pynini|flash[-_]attn)\b", r)]
    return folder, reqs


def command(model, device, spec, env_dir):
    """The command that starts the worker in this model's environment."""
    if device in ("cuda", "cpu"):
        pip = list(spec["pip"])
        if spec["engine"] == "ming":
            _, reqs = ming_checkout()
            pip += reqs
        return torch_project(env_dir, device, pip)
    with_ = [x for p in [*spec["pip"], *COMMON] for x in ("--with", p)]
    return ["uv", "run", "--isolated", "--no-project", "--python", PYTHON, *with_]


def run_worker(cmd, mode, job, log, minutes):
    """Run the worker; its output goes to `log`. Returns (exit code or "timeout", seconds)."""
    job_path = os.path.join(os.path.dirname(log), f"{mode}-job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, indent=1)
    started = time.time()
    with open(log, "a", encoding="utf-8") as out:
        out.write(f"\n=== {dt.datetime.now().isoformat(timespec='seconds')} {' '.join(cmd)}\n")
        out.flush()
        proc = subprocess.Popen([*cmd, "python", WORKER, mode, job_path], stdout=out, stderr=subprocess.STDOUT,
                                cwd=ROOT)
        try:
            code = proc.wait(timeout=minutes * 60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            code = "timeout"
    return code, time.time() - started


def pcm_24k(path):
    """A take as 16-bit mono PCM at 24 kHz (ffmpeg resamples), for the checks and the listening file."""
    out = subprocess.run([ffmpeg_tool.exe(), "-v", "error", "-i", path, "-ac", "1", "-ar", str(verify.SR),
                          "-f", "s16le", "-"], capture_output=True, check=True)
    return out.stdout


def listening_file(pcms, out):
    """The takes end to end, a short gap between, through the build's compressor and loudness target, as a
    48 kbps mono MP3."""
    gap = b"\x00\x00" * int(GAP * verify.SR)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    raw = out + ".raw"
    with open(raw, "wb") as f:
        for p in pcms:
            f.write(p + gap)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run([ffmpeg_tool.exe(), "-y", "-v", "error", "-f", "s16le", "-ar", str(verify.SR), "-ac", "1",
                    "-i", raw, "-af", f"{render.COMPRESS},loudnorm={render.LOUDNESS}", "-ar", str(verify.SR),
                    "-c:a", "libmp3lame", "-b:a", "48k", out], check=True)
    os.remove(raw)


def summarize(rows, rec, code, took):
    takes = [r for r in rows if "heard" in r]
    words = sum(r["words"] for r in takes)
    errors = sum(r["errors"] for r in takes)
    audio = sum(r["audio_s"] for r in takes)
    render_s = sum(r["render_s"] for r in takes)
    by_kind = {}
    for r in takes:
        k = by_kind.setdefault(r["kind"], {"takes": 0, "failed": 0, "errors": 0, "words": 0})
        k["takes"] += 1
        k["failed"] += not r["ok"]
        k["errors"] += r["errors"]
        k["words"] += r["words"]
    status = rec.get("error") or (f"exit {code}" if code != 0 else None) or \
        ("no take rendered" if not takes else "ok")
    return {"status": status,
            "takes": len(takes), "takes_failed_to_render": sum(1 for r in rows if r.get("error")),
            "takes_not_ok": sum(1 for r in takes if not r["ok"]),
            "takes_missing_a_cue": sum(1 for r in takes if r["missed_cues"]),
            "takes_with_audio_problems": sum(1 for r in takes if r["problems"]),
            "word_error_rate": round(errors / words, 4) if words else None,
            "render_ratio": round(render_s / audio, 3) if audio else None,
            "audio_minutes": round(audio / 60, 2), "load_s": rec.get("load_s"), "wall_minutes": round(took / 60, 1),
            "peak": rec.get("peak"), "packages": rec.get("packages"), "python": rec.get("python"),
            "speech_level_db_spread": round(statistics.pstdev([r["level_db"] for r in takes if r["level_db"]]), 2)
            if len(takes) > 1 else None, "by_kind": by_kind}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="./sweatcast bench", description=__doc__.split("\n\n")[0])
    ap.add_argument("--models", help="only these, comma-separated (" + ", ".join(MAC) + ")")
    ap.add_argument("--seeds", type=int, default=None,
                    help="takes of each line (default 2, or 1 on a PC's processor)")
    ap.add_argument("--quick", action="store_true", help="three lines and one seed: does every model run here?")
    ap.add_argument("--as-pc", action="store_true", help=argparse.SUPPRESS)   # the PC's setups, on this processor
    ap.add_argument("--out", help="the results folder (default docs/audio-bench/results/<date>-<mac|pc>)")
    args = ap.parse_args(argv)
    if not shutil.which("uv"):
        raise SystemExit("The bench needs uv on the PATH (./sweatcast setup installs it).")
    if not ffmpeg_tool.exe():
        raise SystemExit("The bench needs ffmpeg: rerun ./sweatcast setup.")
    lines = load_script()
    if args.quick:
        lines = [l for l in lines if l["id"] in ("welcome", "count-switch", "go")]
    runs = plan(args.models.split(",") if args.models else None, as_pc=args.as_pc)
    where = "mac" if sys.platform == "darwin" else "pc"
    stamp = dt.date.today().isoformat()
    out = args.out or os.path.join(BENCH, "results", f"{stamp}-{where}" + ("-quick" if args.quick else ""))
    n = 2
    while os.path.exists(out) and not args.out:
        out = os.path.join(BENCH, "results", f"{stamp}-{where}" + ("-quick" if args.quick else "") + f"-{n}")
        n += 1
    work = os.path.join(WORK, os.path.basename(out))
    os.makedirs(work, exist_ok=True)
    with open(os.path.join(COACH, "clip.txt"), encoding="utf-8") as f:
        ref_text = f.read().strip()
    ref_audio = os.path.join(COACH, "clip.wav")
    print(f"Audio bench on this {where}: {len(runs)} run(s), {len(lines)} lines. Results: {paths.show(out)}", flush=True)
    print("Each model installs into its own environment and downloads its weights (into models/) the first "
          "time; that can take a while.", flush=True)

    results = []
    for model, device, spec in runs:
        seeds = args.seeds or (1 if args.quick or device == "cpu" else 2)
        name = f"{model}-{device}"
        folder = os.path.join(work, name)
        shutil.rmtree(folder, ignore_errors=True)
        os.makedirs(folder)
        log = os.path.join(folder, "worker.log")
        print(f"\n{name}: installing and loading ({paths.show(log)})", flush=True)
        try:
            cmd = command(model, device, spec, os.path.join(WORK, "envs", name))
        except (subprocess.CalledProcessError, OSError) as e:
            results.append((model, device, spec, seeds, {"error": f"setup: {e}"}, "setup", 0.0))
            print(f"  couldn't set it up: {e}", flush=True)
            continue
        job = {"model": model, "device": device, "engine": spec["engine"], "repo": spec["repo"],
               "revision": spec.get("revision"), "ref_audio": ref_audio, "ref_text": ref_text,
               "ref_text_needed": spec.get("ref_text_needed", False), "prime_once": spec.get("prime_once", False),
               "lines": [{"id": l["id"], "text": l["text"]} for l in lines], "seeds": [42 + k for k in range(seeds)],
               "out": folder}
        if spec["engine"] == "ming":
            job["repo_dir"] = ming_checkout()[0]
        code, took = run_worker(cmd, "render", job, log, TIMEOUT["mlx" if device == "mlx" else device])
        try:
            with open(os.path.join(folder, "render.json"), encoding="utf-8") as f:
                rec = json.load(f)
        except (OSError, ValueError):
            rec = {"error": f"no record (exit {code}); see the log"}
        if code == "timeout":
            rec["error"] = (rec.get("error") or "") + f" stopped after {TIMEOUT.get(device, 45)} minutes"
        done = sum(1 for t in rec.get("takes", []) if "audio_s" in t)
        print(f"  {done} take(s) in {took / 60:.1f} min" + (f"; {rec['error']}" if rec.get("error") else ""), flush=True)
        said = (rec.get("error") or "") + rec.get("traceback", "")
        if spec["repo"] in GATED and any(w in said.lower() for w in ("401", "gated", "accept the terms")):
            print(f"  {spec['repo']} is gated: accept its terms at {GATED[spec['repo']]} with a "
                  "Hugging Face account, run `uvx hf auth login` once, and rerun with --models " + model, flush=True)
        results.append((model, device, spec, seeds, rec, code, took))

    # One recognizer for every take.
    wavs = [os.path.join(work, f"{m}-{d}", str(t["seed"]), t["id"] + ".wav")
            for m, d, _, _, rec, _, _ in results for t in rec.get("takes", []) if "audio_s" in t]
    heard = {}
    if wavs:
        print(f"\nTranscribing {len(wavs)} take(s) with Parakeet (ONNX)", flush=True)
        asr_dir = os.path.join(work, "asr")
        os.makedirs(asr_dir, exist_ok=True)
        cmd = ["uv", "run", "--isolated", "--no-project", "--python", PYTHON,
               *[x for p in [*ASR, *COMMON] for x in ("--with", p)]]
        code, _ = run_worker(cmd, "asr", {"files": wavs, "out": os.path.join(asr_dir, "heard.json"),
                                          "asr_repo": ASR_MODEL[0], "asr_revision": ASR_MODEL[1],
                                          "asr_dir": os.path.join(WORK, "asr-model")},
                             os.path.join(asr_dir, "worker.log"), 60)
        try:
            with open(os.path.join(asr_dir, "heard.json"), encoding="utf-8") as f:
                asr = json.load(f)
            heard = asr["heard"]
        except (OSError, ValueError):
            asr = {"error": f"the recognizer failed (exit {code}); see {paths.show(asr_dir)}/worker.log"}
            print(asr["error"], flush=True)
    else:
        asr = {"error": "nothing to transcribe"}

    os.makedirs(out, exist_ok=True)
    by_id = {l["id"]: l for l in lines}
    all_rows, summaries = [], {}
    for model, device, spec, seeds, rec, code, took in results:
        name = f"{model}-{device}"
        rows, first = [], []
        for t in rec.get("takes", []):
            line = by_id[t["id"]]
            row = {"model": model, "device": device, "id": t["id"], "kind": line["kind"], "seed": t["seed"],
                   "render_s": t.get("render_s"), "audio_s": t.get("audio_s"), "sr": t.get("sr")}
            if "audio_s" not in t:
                row["error"] = t.get("error")
                rows.append(row)
                continue
            wav = os.path.join(work, name, str(t["seed"]), t["id"] + ".wav")
            pcm = pcm_24k(wav)
            predicted = weight(line["text"]) / PACE
            if heard.get(wav) is not None:
                v = verify.judge(line["text"], heard[wav], pcm, predicted)
                row.update(heard=v["heard"], words=v["words"], errors=v["errors"], missed_cues=v["missed_cues"],
                           problems=v["problems"], ok=v["ok"])
            level = render.speech_level(pcm)
            row["level_db"] = round(level, 2) if level is not None else None
            row["peak"] = round(max((abs(x) for x in memoryview(pcm).cast("h")), default=0) / 32768, 3)
            rows.append(row)
            if t["seed"] == 42:
                first.append(pcm)
        if first:
            listening_file(first, os.path.join(out, "listen", f"{name}.mp3"))
        summaries[name] = summarize(rows, rec, code, took)
        summaries[name].update(repo=spec["repo"], revision=spec.get("revision"), engine=spec["engine"], seeds=seeds)
        all_rows += rows

    run = {"bench": "sweatcast audio bench", "date": stamp, "where": where, "quick": args.quick,
           "sweatcast": open(os.path.join(ROOT, "VERSION"), encoding="utf-8").read().strip(),
           "computer": computer(), "script": os.path.relpath(SCRIPT, ROOT), "lines": len(lines),
           "coach_clip": os.path.relpath(ref_audio, ROOT), "asr": {k: v for k, v in asr.items() if k != "heard"},
           "pass_rule": "every cue word said, no audio problem, at most one word in twenty off (tools/verify.py)",
           "models": summaries}
    with open(os.path.join(out, "run.json"), "w", encoding="utf-8") as f:
        json.dump(run, f, indent=1)
    with open(os.path.join(out, "takes.jsonl"), "w", encoding="utf-8") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    with open(os.path.join(out, "summary.md"), "w", encoding="utf-8") as f:
        f.write(summary_md(run))
    print("\n" + summary_md(run))
    print(f"Results in {paths.show(out)}. Commit and push them for the analysis.")
    return 0


def summary_md(run):
    c = run["computer"]
    gpu = c.get("gpu") or {}
    head = (f"# Audio bench, {run['date']}, {run['where']}\n\n"
            f"{c.get('chip') or c.get('machine')}, {c.get('system')} {c.get('macos') or c.get('release')}"
            + (f", {gpu.get('name')} {gpu.get('memory')}" if gpu else "") +
            f"; sweatcast {run['sweatcast']}; {run['lines']} lines; recognizer {run['asr'].get('asr_model', '?')}.\n\n"
            "| Model | Device | Status | Takes | Not ok | Missing a cue | Audio problems | WER | Render ratio | Load s | Peak memory |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n")
    rows = []
    for name, s in run["models"].items():
        model, device = name.rsplit("-", 1)
        peak = s.get("peak") or {}
        mem = peak.get("cuda_peak_bytes") or peak.get("mlx_peak_bytes") or peak.get("rss_bytes")
        wer = "" if s["word_error_rate"] is None else f"{s['word_error_rate'] * 100:.1f}%"
        mem = f"{mem / 1e9:.1f} GB" if mem else ""
        rows.append(f"| {model} | {device} | {s['status'][:60]} | {s['takes']} | {s['takes_not_ok']} | "
                    f"{s['takes_missing_a_cue']} | {s['takes_with_audio_problems']} | {wer} | "
                    f"{s['render_ratio'] or ''} | {s['load_s'] or ''} | {mem} |")
    return head + "\n".join(rows) + "\n\nRender ratio: seconds of rendering per second of speech (lower is faster).\n"


if __name__ == "__main__":
    sys.exit(cli.run(main))
