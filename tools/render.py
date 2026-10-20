#!/usr/bin/env python3
"""Render a segmented workout draft to one audio file with OmniVoice, in-process.

Runs under VoiceStudio's bundled Python (tools/build.sh picks it), loads the
OmniVoice model once (a few seconds), and voices each paragraph with a
VoiceStudio voice profile, conditioned the way the app does it. Each segment is
padded with silence to its planned seconds so every segment starts on the clock,
and the result is loudness-normalized for earbuds.

No VoiceStudio server needed. Clips are cached, so rerunning after editing a few
segments only re-renders what changed.

Usage (normally via tools/build.sh):
    <voicestudio python> tools/render.py draft.txt --voice Coach --out "workouts/Workout ....mp3"
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_build import PARAGRAPH_GAP, parse, plan  # noqa: E402  (one source of truth for text)
from voices import ROOT, lookup, record  # noqa: E402

CACHE_DIR = os.path.join(ROOT, "workouts", ".audio-cache")
SR = 24000
LOUDNESS = "I=-16:TP=-1.5:LRA=11"   # podcast level, with headroom under 0 dBFS
CODECS = {".mp3": ["-c:a", "libmp3lame", "-b:a", "96k"],
          ".m4a": ["-c:a", "aac", "-b:a", "96k"],
          ".wav": ["-c:a", "pcm_s16le"]}


def to_pcm16(tensor):
    import numpy as np
    a = tensor.float().cpu().numpy().reshape(-1)
    return (np.clip(a, -1.0, 1.0) * 32767).astype("<i2").tobytes()


def silence(seconds):
    return b"\x00\x00" * max(int(seconds * SR), 0)


def encode(pcm, out, title):
    """Two-pass loudness normalization, then encode by the output's extension."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found; install it with: brew install ffmpeg")
    codec = CODECS.get(os.path.splitext(out)[1].lower())
    if not codec:
        raise SystemExit(f"--out must end in one of: {', '.join(CODECS)}")
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, "raw.wav")
        with wave.open(raw, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(bytes(pcm))
        probe = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", raw, "-af",
                                f"loudnorm={LOUDNESS}:print_format=json", "-f", "null", "-"],
                               capture_output=True, text=True, check=True)
        m = json.loads(probe.stderr[probe.stderr.rindex("{"):probe.stderr.rindex("}") + 1])
        af = (f"loudnorm={LOUDNESS}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", raw, "-af", af, "-ar", str(SR),
                        "-metadata", f"title={title}", *codec, out], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", required=True, help=".mp3, .m4a or .wav")
    ap.add_argument("--voice", default="demo0001", help="VoiceStudio voice profile id or name")
    # Measured on this M3 (2026-10-19): 8 steps garbled cue words ("curl" heard as "cook");
    # 12, 16 and 32 transcribed equally clean. Time is linear: about 0.06 x real time per step.
    ap.add_argument("--steps", type=int, default=12,
                    help="decoding steps: 12 default; VoiceStudio's balanced is 16, its audiobook setting 32")
    ap.add_argument("--speed", type=float, default=None, help="speaking speed factor (1.0 = natural)")
    ap.add_argument("--seed", type=int, default=None, help="default: the voice's pinned seed, else 42")
    ap.add_argument("--tolerance", type=float, default=0.05,
                    help="allowed overrun past a segment's planned seconds")
    args = ap.parse_args()

    with open(args.draft, encoding="utf-8") as f:
        segments = parse(f.read())
    os.makedirs(CACHE_DIR, exist_ok=True)
    started = time.time()

    voice = lookup(args.voice)
    seed = args.seed if args.seed is not None else (voice["seed"] if voice["seed"] is not None else 42)
    instruct = voice["instruct"]
    if instruct or voice["vd_states"]:
        # As the app does: sanitize the stored design tags, rebuilding them from the
        # design picks if they're unusable.
        from omnivoice.utils.voice_design import heal_design_instruct
        instruct = heal_design_instruct(voice["instruct"], voice["vd_states"])
    instruct = instruct or None

    def cache_path(text):
        key = f"{voice['key']}|{args.steps}|{args.speed}|{seed}|{instruct}|{text}"
        return os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")

    clips = [text for seg in segments for para in plan(seg) for text, _ in para if text]
    todo = list(dict.fromkeys(t for t in clips if not os.path.exists(cache_path(t))))
    print(f"{len(clips)} clips, {len(todo)} to render ({len(clips) - len(todo)} cached), "
          f"voice {voice['name']}, {args.steps} steps", flush=True)

    if todo:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        import torch
        from omnivoice import OmniVoice
        device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device,
                                          dtype=torch.float16 if device != "cpu" else torch.float32,
                                          load_asr=False)
        prompt = model.create_voice_clone_prompt(voice["ref_audio"], ref_text=voice["ref_text"])
        # The trimmed reference length sets the voice's pace; the lint predicts from it.
        record(voice, prompt.ref_text, prompt.ref_audio_tokens.shape[-1])
        print(f"model ready in {time.time() - started:.0f}s", flush=True)
        audio_secs = 0.0
        for n, text in enumerate(todo, 1):
            torch.manual_seed(seed)
            t0 = time.time()
            audio = model.generate(text=text, voice_clone_prompt=prompt, instruct=instruct,
                                   language="en", num_step=args.steps, speed=args.speed)[0]
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
    for i, seg in enumerate(segments, 1):
        seg_pcm = bytearray()
        for j, para in enumerate(plan(seg)):
            if j:
                seg_pcm += silence(PARAGRAPH_GAP)
            for text, pause in para:
                if text:
                    with open(cache_path(text), "rb") as f:
                        seg_pcm += f.read()
                seg_pcm += silence(pause)
        spoken = len(seg_pcm) / 2 / SR
        flag = ""
        if spoken > seg["seconds"] * (1 + args.tolerance):
            flag, overruns = "  <-- overrun", overruns + 1
        else:
            seg_pcm += silence(seg["seconds"] - spoken)
        rows.append((i, seg["seconds"], spoken, seg["label"], flag))
        pcm_all += seg_pcm

    print(f"\n{'#':>3} {'plan':>5} {'spoken':>6} {'fill':>5}  label")
    for i, planned, spoken, label, flag in rows:
        print(f"{i:>3} {planned:>5} {spoken:>6.1f} {spoken / planned:>5.0%}  {label}{flag}")

    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    encode(pcm_all, out, os.path.splitext(os.path.basename(out))[0])

    total = len(pcm_all) / 2 / SR
    print(f"\nWrote {out}: {total / 60:.1f} min audio, total time {(time.time() - started) / 60:.1f} min"
          + (f", {overruns} segment(s) overran their slot" if overruns else ""))
    if overruns:
        print("Overruns push later segments late. Trim those segments' words and rerun; unchanged clips come from cache.")
        sys.exit(2)


if __name__ == "__main__":
    main()
