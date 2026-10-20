#!/usr/bin/env python3
"""Render a segmented workout draft to one audio file with OmniVoice, in-process.

Runs under VoiceStudio's bundled Python (tools/build.sh picks it), loads the
OmniVoice model once (a few seconds), and synthesizes each paragraph using a
VoiceStudio voice profile as the reference voice. Each segment is padded with
silence to its planned seconds so every segment starts on the clock.

No VoiceStudio server needed. Paragraphs are cached, so rerunning after editing
a few segments only re-renders what changed.

Usage (normally via tools/build.sh):
    <voicestudio python> tools/render.py draft.txt --out "workouts/Workout ....mp3"
"""
import argparse
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_build import parse  # noqa: E402  (one source of truth for segments)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, "workouts", ".audio-cache")
VS_DATA = os.path.expanduser("~/Library/Application Support/OmniVoice")
SR = 24000
STEPS = {"fast": 8, "balanced": 12, "best": 16}


def paragraphs(lines):
    out, buf = [], []
    for _, line in lines + [(0, "")]:
        if line.strip():
            buf.append(line.strip())
        elif buf:
            out.append(" ".join(buf))
            buf = []
    return out


def voice_profile(voice_id):
    """Look up a VoiceStudio voice profile's reference audio and transcript."""
    db = os.path.join(VS_DATA, "omnivoice.db")
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM voice_profiles WHERE id=? OR name=?",
                           (voice_id, voice_id)).fetchone()
        if not row:
            names = [f"{r['id']} ({r['name']})" for r in conn.execute("SELECT id, name FROM voice_profiles")]
            raise SystemExit(f"No VoiceStudio voice '{voice_id}'. Available: {', '.join(names)}")
    audio = row["locked_audio_path"] if row["is_locked"] and row["locked_audio_path"] else row["ref_audio_path"]
    return os.path.join(VS_DATA, "voices", audio), row["ref_text"]


def to_pcm16(tensor):
    import numpy as np
    a = tensor.float().cpu().numpy().reshape(-1)
    return (np.clip(a, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", required=True, help=".mp3, .m4a or .wav")
    ap.add_argument("--voice", default="demo0001", help="VoiceStudio voice profile id or name")
    # fast (8 steps) garbled a safety cue in testing; balanced was clean.
    ap.add_argument("--quality", choices=STEPS, default="balanced",
                    help="decoding steps: fast=8, balanced=12, best=16")
    ap.add_argument("--speed", type=float, default=None, help="speaking speed factor (1.0 = natural)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--gap", type=float, default=0.35,
                    help="seconds of silence between paragraphs within a segment")
    ap.add_argument("--tolerance", type=float, default=0.05,
                    help="allowed overrun past a segment's planned seconds")
    args = ap.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        segments = parse(f.read())
    os.makedirs(CACHE_DIR, exist_ok=True)
    started = time.time()

    ref_audio, ref_text = voice_profile(args.voice)
    steps = STEPS[args.quality]
    with open(ref_audio, "rb") as f:
        voice_key = hashlib.sha256(f.read()).hexdigest()[:12]

    def cache_path(text):
        key = f"{voice_key}|{steps}|{args.speed}|{args.seed}|{text}"
        return os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")

    todo = [p for seg in segments for p in paragraphs(seg["lines"]) if not os.path.exists(cache_path(p))]
    total_paras = sum(len(paragraphs(s["lines"])) for s in segments)
    print(f"{total_paras} paragraphs, {len(todo)} to render ({total_paras - len(todo)} cached), "
          f"voice {args.voice}, quality {args.quality}", flush=True)

    if todo:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from omnivoice import OmniVoice
        device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device,
                                          dtype=torch.float16 if device != "cpu" else torch.float32,
                                          load_asr=False)
        prompt = model.create_voice_clone_prompt(ref_audio, ref_text=ref_text)
        print(f"model ready in {time.time() - started:.0f}s", flush=True)
        audio_secs = 0.0
        for n, text in enumerate(todo, 1):
            torch.manual_seed(args.seed)
            t0 = time.time()
            audio = model.generate(text=text, voice_clone_prompt=prompt, language="en",
                                   num_step=steps, speed=args.speed)[0]
            pcm = to_pcm16(audio)
            tmp = cache_path(text) + ".part"
            with open(tmp, "wb") as f:
                f.write(pcm)
            os.replace(tmp, cache_path(text))
            secs = len(pcm) / 2 / SR
            audio_secs += secs
            print(f"  [{n}/{len(todo)}] {secs:4.1f}s audio in {time.time() - t0:4.1f}s", flush=True)
        print(f"rendered {audio_secs / 60:.1f} min of speech in {(time.time() - started) / 60:.1f} min", flush=True)

    pcm_all, overruns, rows = bytearray(), 0, []
    gap = b"\x00\x00" * int(args.gap * SR)
    for i, seg in enumerate(segments, 1):
        seg_pcm = bytearray()
        for j, p in enumerate(paragraphs(seg["lines"])):
            if j:
                seg_pcm += gap
            with open(cache_path(p), "rb") as f:
                seg_pcm += f.read()
        spoken = len(seg_pcm) / 2 / SR
        flag = ""
        if spoken > seg["seconds"] * (1 + args.tolerance):
            flag, overruns = "  <-- overrun", overruns + 1
        else:
            seg_pcm += b"\x00\x00" * max(int((seg["seconds"] - spoken) * SR), 0)
        rows.append((i, seg["seconds"], spoken, seg["label"], flag))
        pcm_all += seg_pcm

    print(f"\n{'#':>3} {'plan':>5} {'spoken':>6} {'fill':>5}  label")
    for i, plan, spoken, label, flag in rows:
        print(f"{i:>3} {plan:>5} {spoken:>6.1f} {spoken / plan:>5.0%}  {label}{flag}")

    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav_path = out if out.lower().endswith(".wav") else os.path.join(td, "full.wav")
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(bytes(pcm_all))
        if wav_path != out:
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                raise SystemExit("ffmpeg not found; install it or use a .wav --out.")
            codec = ["-c:a", "aac", "-b:a", "96k"] if out.lower().endswith(".m4a") else ["-c:a", "libmp3lame", "-b:a", "96k"]
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", wav_path, *codec, out], check=True)

    total = len(pcm_all) / 2 / SR
    print(f"\nWrote {out}: {total / 60:.1f} min audio, total time {(time.time() - started) / 60:.1f} min"
          + (f", {overruns} segment(s) overran their slot" if overruns else ""))
    if overruns:
        print("Overruns push later segments late. Trim those segments' words and rerun; unchanged paragraphs come from cache.")
        sys.exit(2)


if __name__ == "__main__":
    main()
