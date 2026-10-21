#!/usr/bin/env python3
"""Render a segmented workout draft to one MP3, voicing each paragraph in-process.

Runs under VoiceStudio's bundled Python (tools/build.sh picks it). A voice from
voices/ is cloned from its reference clip with Chatterbox (Turbo by default for
Coach E) or Qwen3-TTS through mlx-audio; a voice saved in the VoiceStudio app
renders with OmniVoice. A soft chime opens each segment after the first, a [chime]
marker rings it inside a segment, and a three-note tone marks the end of the
workout. Each segment's spare seconds are spread over its paragraph breaks, a
slightly long segment borrows from the next one's padding, and the result is
loudness-normalized for earbuds.

No VoiceStudio app or server needed. Clips are cached, so rerunning after editing
a few segments only re-renders what changed.

Usage (normally via tools/build.sh):
    <voicestudio python> tools/render.py draft.txt --voice "Coach E" --out "workouts/Workout ....mp3"
    <voicestudio python> tools/render.py draft.txt --voice "Coach E" --clips-only   # fill the cache, no MP3
"""
import argparse
import contextlib
import hashlib
import io
import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tts_build import CHIME, CHIME_SECONDS, PARAGRAPH_GAP, parse, plan, spoken as is_spoken  # noqa: E402  (one source of truth for text)
from voices import MLX_EDGE, ROOT, lookup, record, record_rate, weight  # noqa: E402

CACHE_DIR = os.path.join(ROOT, "workouts", ".audio-cache")
SR = 24000
END_TAIL = 1.5        # seconds of a segment's spare time kept before the next segment
MAX_EXTRA_GAP = 1.5   # most spare time added to any one paragraph break
CHIME_TONE = 0.35     # seconds of bell; the rest of CHIME_SECONDS is quiet before the voice
CHIME_LEVEL = 0.12    # peak; at 0.2 the bell averaged as loud as the voice, so this sits about 4 dB under
END_NOTES = (660, 880, 1320)   # Hz, rising, so the end can't be mistaken for a segment bell
END_NOTE = 0.3        # seconds per note
END_LEAD = 1.0        # seconds of quiet before the end tone
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


def _bell(seconds, partials, decay=9.0):
    n = int(seconds * SR)
    samples = []
    for i in range(n):
        t = i / SR
        env = min(t / 0.005, 1.0) * math.exp(-decay * t)   # quick attack, bell-like decay
        v = sum(a * math.sin(2 * math.pi * f * t) for f, a in partials)
        samples.append(int(CHIME_LEVEL * env * v * 32767))
    return struct.pack(f"<{n}h", *samples)


def chime():
    """A soft two-note bell that marks a new segment, so the ear has a timing anchor
    even if a spoken cue gets mangled. Followed by a short quiet before the voice."""
    return _bell(CHIME_TONE, ((880, 0.6), (1320, 0.4))) + silence(CHIME_SECONDS - CHIME_TONE)


def end_tone():
    """Three rising notes after the last segment: the workout is over, not the earbud."""
    return silence(END_LEAD) + b"".join(_bell(END_NOTE, ((f, 0.7), (f * 2, 0.3)), decay=6.0)
                                        for f in END_NOTES) + silence(0.5)


def assemble(segments, clip, tolerance=0.05, lead=b"", bell=None, tail=b""):
    """Lay the clips out on the plan's clock: one slot per segment.

    clip(text) returns a clip's PCM. `lead` (the chime) opens every segment after
    the first, `bell` rings at each [chime] marker (default: the chime), and `tail`
    (the end tone) follows the last segment, past the plan's clock.
    Returns (pcm, rows, overruns), rows as (n, planned, spoken, label, flag)."""
    bell = chime() if bell is None else bell
    pcm_all, overruns, rows, late = bytearray(), 0, [], 0.0
    for i, seg in enumerate(segments, 1):
        paras = []
        for para in plan(seg):
            p = bytearray()
            for text, pause in para:
                if text == CHIME:
                    p += bell
                elif text:
                    p += clip(text)
                p += silence(pause)
            paras.append(p)
        head = lead if i > 1 else b""
        gaps = len(paras) - 1
        spoken = (len(head) + sum(len(p) for p in paras)) / 2 / SR + PARAGRAPH_GAP * gaps
        # Spread the slot's spare seconds over the paragraph breaks, so the voice
        # breathes between cue and story instead of rushing and then going quiet
        # before the next segment. A short tail stays at the end.
        slot = seg["seconds"] - late   # running late from earlier segments shortens this slot
        slack = max(slot - spoken, 0.0)
        extra = min(max(slack - END_TAIL, 0.0) / gaps, MAX_EXTRA_GAP) if gaps else 0.0
        seg_pcm = bytearray(head)
        for j, p in enumerate(paras):
            if j:
                seg_pcm += silence(PARAGRAPH_GAP + extra)
            seg_pcm += p
        flag = ""
        if spoken > seg["seconds"] * (1 + tolerance):
            flag, overruns = "  <-- overrun", overruns + 1
        seg_pcm += silence(slot - len(seg_pcm) / 2 / SR)
        late = max(late + len(seg_pcm) / 2 / SR - seg["seconds"], 0.0)
        rows.append((i, seg["seconds"], spoken, seg["label"], flag))
        pcm_all += seg_pcm
    pcm_all += tail
    return pcm_all, rows, overruns


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


MLX_MODELS = {"qwen3": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-bf16",
              "chatterbox": "mlx-community/Chatterbox-TTS-fp16"}
TRIM_DB = -40.0       # engine silence below this level is trimmed from each clip's ends
TRIM_KEEP = 0.04      # seconds of it kept at each end


def omnivoice_speaker(voice, instruct, args):
    import torch
    from omnivoice import OmniVoice
    device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map=device,
                                      dtype=torch.float16 if device != "cpu" else torch.float32,
                                      load_asr=False)
    prompt = model.create_voice_clone_prompt(voice["ref_audio"], ref_text=voice["ref_text"])
    # The trimmed reference length sets the voice's pace; the lint predicts from it.
    record(voice, prompt.ref_text, prompt.ref_audio_tokens.shape[-1])

    def say(text, seed):
        torch.manual_seed(seed)
        return to_pcm16(model.generate(text=text, voice_clone_prompt=prompt, instruct=instruct,
                                       language="en", num_step=args.steps, speed=args.speed,
                                       guidance_scale=args.guidance,
                                       class_temperature=args.class_temperature,
                                       position_temperature=args.position_temperature)[0])
    return say


def trim(a):
    """Cut the engine's lead-in and tail silence, keeping a short natural edge."""
    import numpy as np
    loud = np.flatnonzero(np.abs(a) > 10 ** (TRIM_DB / 20))
    if not len(loud):
        return a
    keep = int(TRIM_KEEP * SR)
    return a[max(loud[0] - keep, 0):loud[-1] + keep]


def mlx_speaker(voice, engine, repo):
    """Qwen3-TTS or Chatterbox through mlx-audio, cloning the voice's reference clip."""
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    model = load_model(repo)
    gen = voice.get("generate") or {}   # per-voice engine settings, from voices/<name>.json
    # Chatterbox Turbo re-encodes the reference clip on every call that passes it
    # (about half a second each) and keeps the result on the model. So pass it on the
    # first clip only: the same code path computes the same conditioning, once.
    # The full-size Chatterbox keeps nothing (without the clip it falls back to its
    # built-in voice), and Qwen3 caches its reference codes itself, so both pass it
    # every time.
    keeps_conditioning = type(model).__name__ == "ChatterboxTurboTTS"
    primed = []

    def say(text, seed):
        mx.random.seed(seed)
        if engine == "qwen3":
            results = model.generate(text=text, ref_audio=voice["ref_audio"], ref_text=voice["ref_text"],
                                     verbose=False, **gen)
        elif keeps_conditioning and primed:
            results = model.generate(text=text, verbose=False, **gen)
        else:
            results = model.generate(text=text, ref_audio=voice["ref_audio"], verbose=False, **gen)
            primed.append(True)
        with contextlib.redirect_stdout(io.StringIO()):   # the models print progress per clip
            results = list(results)
        if results[0].sample_rate != SR:
            raise SystemExit(f"{engine} returned {results[0].sample_rate} Hz audio; expected {SR}")
        a = np.concatenate([np.array(r.audio, dtype=np.float32).reshape(-1) for r in results])
        return (np.clip(trim(a), -1.0, 1.0) * 32767).astype("<i2").tobytes()
    return say


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("draft")
    ap.add_argument("--out", help=".mp3, .m4a or .wav (not needed with --clips-only)")
    ap.add_argument("--voice", default="demo0001", help="VoiceStudio voice profile id or name")
    # Measured on this M3 (2026-10-19): 8 steps garbled cue words ("curl" heard as "cook");
    # 12, 16 and 32 transcribed equally clean, but a listen to a 12-step workout
    # (2026-10-20) found glitches and a flat read; 32 is OmniVoice's and VoiceStudio's
    # audiobook default. Time is linear: about 0.07 x real time per step.
    ap.add_argument("--steps", type=int, default=32,
                    help="decoding steps: 32 default (audiobook quality); 16 is faster for drafts")
    ap.add_argument("--speed", type=float, default=None, help="speaking speed factor (1.0 = natural)")
    ap.add_argument("--guidance", type=float, default=2.0, help="guidance scale (OmniVoice default 2.0)")
    # 0.3 chosen by ear on 2026-10-20 (sample E): less flat than greedy, no added glitches.
    # The seed is pinned, so renders stay repeatable.
    ap.add_argument("--class-temperature", type=float, default=0.3,
                    help="token sampling temperature: 0.3 default; 0 = greedy (flatter), 0.7 = livelier, more glitches")
    ap.add_argument("--position-temperature", type=float, default=5.0,
                    help="unmasking-order temperature (OmniVoice default 5.0)")
    ap.add_argument("--model", default=None,
                    help="Qwen3 or Chatterbox model repo; default: the voice's, else the engine's standard one")
    ap.add_argument("--seed", type=int, default=None, help="default: the voice's pinned seed, else 42")
    ap.add_argument("--tolerance", type=float, default=0.05,
                    help="allowed overrun past a segment's planned seconds")
    ap.add_argument("--no-chime", action="store_true",
                    help="leave out the bell at each new segment and the end tone ([chime] markers still ring)")
    ap.add_argument("--clips-only", action="store_true",
                    help="render and cache the draft's clips, then stop: no timing check, no MP3")
    args = ap.parse_args()
    if not args.out and not args.clips_only:
        ap.error("--out is required unless --clips-only")

    with open(args.draft, encoding="utf-8") as f:
        segments = parse(f.read())
    os.makedirs(CACHE_DIR, exist_ok=True)
    started = time.time()

    voice = lookup(args.voice)
    engine = voice["engine"]
    model_repo = args.model or voice.get("model") or MLX_MODELS.get(engine)
    if args.model:
        voice["model"] = args.model   # so the measured rate is filed under this model
    seed = args.seed if args.seed is not None else (voice["seed"] if voice["seed"] is not None else 42)
    instruct = voice["instruct"]
    if engine == "omnivoice" and (instruct or voice["vd_states"]):
        # As the app does: sanitize the stored design tags, rebuilding them from the
        # design picks if they're unusable.
        from omnivoice.utils.voice_design import heal_design_instruct
        instruct = heal_design_instruct(voice["instruct"], voice["vd_states"])
    instruct = instruct or None
    # Everything that changes how a clip sounds goes in its cache key, so changing a
    # setting re-renders instead of silently reusing old clips.
    settings = (f"{args.steps}|{args.speed}|{instruct}|{args.guidance}|{args.class_temperature}|"
                f"{args.position_temperature}" if engine == "omnivoice" else
                f"{model_repo}|{json.dumps(voice.get('generate') or {}, sort_keys=True)}|"
                f"trim {TRIM_DB} {TRIM_KEEP}")

    def cache_path(text):
        key = f"{voice['key']}|{engine}|{seed}|{settings}|{text}"
        return os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")

    clips = [text for seg in segments for para in plan(seg) for text, _ in para if is_spoken(text)]
    todo = list(dict.fromkeys(t for t in clips if not os.path.exists(cache_path(t))))
    print(f"{len(clips)} clips, {len(todo)} to render ({len(clips) - len(todo)} cached), "
          f"voice {voice['name']} on {engine}" + (f", {args.steps} steps" if engine == "omnivoice" else ""),
          flush=True)

    if todo:
        if engine == "omnivoice":
            os.environ.setdefault("HF_HUB_OFFLINE", "1")   # its weights come with VoiceStudio
        say = (omnivoice_speaker(voice, instruct, args) if engine == "omnivoice"
               else mlx_speaker(voice, engine, model_repo))
        print(f"model ready in {time.time() - started:.0f}s", flush=True)
        speaking_started = time.time()
        audio_secs, measured_weight = 0.0, 0.0
        for n, text in enumerate(todo, 1):
            t0 = time.time()
            pcm = say(text, seed)
            tmp = cache_path(text) + ".part"
            with open(tmp, "wb") as f:
                f.write(pcm)
            os.replace(tmp, cache_path(text))
            secs = len(pcm) / 2 / SR
            audio_secs += secs
            if engine != "omnivoice":
                measured_weight += weight(text)
            print(f"  [{n}/{len(todo)}] {secs:4.1f}s audio in {time.time() - t0:4.1f}s", flush=True)
        if engine != "omnivoice":
            # The lint predicts this voice's length from its measured rate.
            record_rate(voice, measured_weight, audio_secs - MLX_EDGE * len(todo))
        took = time.time() - speaking_started
        print(f"rendered {audio_secs / 60:.1f} min of speech in {took / 60:.1f} min "
              f"({took / audio_secs:.2f} times its length, not counting the model load)", flush=True)

    if args.clips_only:
        print(f"Clips cached for {len(segments)} segment(s); the full build reuses them.")
        return

    def clip(text):
        with open(cache_path(text), "rb") as f:
            return f.read()

    pcm_all, rows, overruns = assemble(segments, clip, args.tolerance,
                                       lead=b"" if args.no_chime else chime(), bell=chime(),
                                       tail=b"" if args.no_chime else end_tone())

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
