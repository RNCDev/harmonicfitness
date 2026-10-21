#!/usr/bin/env python3
"""Render a segmented workout draft to one MP3, voicing each paragraph in-process.

Runs in the project's own environment, .venv (tools/setup.sh makes it; tools/build.sh
picks it). Each voice is cloned from its reference clip with Chatterbox Turbo or
Qwen3-TTS through mlx-audio, using the model revision its voices/<name>.json pins,
and the engine's extra downloads (Chatterbox's speech tokenizer) at the revision
tools/voices.py pins. A soft chime opens each segment after the first, a [chime]
marker rings it inside a segment, and a three-note tone marks the end of the
workout. A segment's spare seconds widen its paragraph breaks and then it ends
early, a slightly long segment is paid back from the next ones' spare time, the
whole workout is held within three percent of plan, and the result is
loudness-normalized for earbuds.

No app or server needed. Clips are cached in me/workouts/.audio-cache, so rerunning
after editing a few segments only re-renders what changed.

Usage (normally via tools/build.sh):
    .venv/bin/python tools/render.py draft.txt --voice "Chatterbox Coach" --out "me/workouts/Workout ....mp3"
    .venv/bin/python tools/render.py draft.txt --voice "Chatterbox Coach" --clips-only   # fill the cache, no MP3
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
from tts_build import (CHIME, CHIME_SECONDS, END_TAIL, MAX_EXTRA_GAP, MAX_FILL, MIN_FILL,  # noqa: E402,F401
                       PARAGRAPH_GAP, TOTAL_TOLERANCE, layout, parse, plan, spoken as is_spoken)  # noqa: E402  (one source of truth for text)
from paths import CACHE as CACHE_DIR  # noqa: E402
from voices import ENGINE_EXTRAS, MLX_EDGE, lookup, record_rate, weight  # noqa: E402

SR = 24000
CHIME_TONE = 0.35     # seconds of bell; the rest of CHIME_SECONDS is quiet before the voice
CHIME_LEVEL = 0.12    # peak; at 0.2 the bell averaged as loud as the voice, so this sits about 4 dB under
END_NOTES = (660, 880, 1320)   # Hz, rising, so the end can't be mistaken for a segment bell
END_NOTE = 0.3        # seconds per note
END_LEAD = 1.0        # seconds of quiet before the end tone
LOUDNESS = "I=-16:TP=-1.5:LRA=11"   # podcast level, with headroom under 0 dBFS
CODECS = {".mp3": ["-c:a", "libmp3lame", "-b:a", "96k"],
          ".m4a": ["-c:a", "aac", "-b:a", "96k"],
          ".wav": ["-c:a", "pcm_s16le"]}


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


def assemble(segments, clip, lead=b"", bell=None, tail=b""):
    """Lay the clips out on the plan's clock, as tts_build.layout predicts.

    clip(text) returns a clip's PCM. `lead` (the chime) opens every segment after
    the first, `bell` rings at each [chime] marker (default: the chime), and `tail`
    (the end tone) follows the last segment, past the plan's clock. A segment with
    time to spare widens its breaks and ends early instead of padding with silence.
    Returns (pcm, rows, drift): rows as (n, planned, spoken, label, flag), drift as
    the whole workout's fraction over (+) or under (-) plan, not counting the tail."""
    bell = chime() if bell is None else bell
    built = []
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
        built.append((head, paras, spoken, gaps))

    pcm_all, rows = bytearray(), []
    timeline = layout([(spoken, gaps, seg["seconds"]) for seg, (_, _, spoken, gaps) in zip(segments, built)])
    for i, (seg, (head, paras, spoken, gaps), (extra, length)) in enumerate(zip(segments, built, timeline), 1):
        seg_pcm = bytearray(head)
        for j, p in enumerate(paras):
            if j:
                seg_pcm += silence(PARAGRAPH_GAP + extra)
            seg_pcm += p
        seg_pcm += silence(length - len(seg_pcm) / 2 / SR)
        fill = spoken / seg["seconds"]
        flag = "  <-- long" if fill > MAX_FILL else "  <-- short" if fill < MIN_FILL else ""
        rows.append((i, seg["seconds"], spoken, seg["label"], flag))
        pcm_all += seg_pcm
    planned = sum(seg["seconds"] for seg in segments)
    drift = len(pcm_all) / 2 / SR / planned - 1 if planned else 0.0
    pcm_all += tail
    return pcm_all, rows, drift


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


TRIM_DB = -40.0       # engine silence below this level is trimmed from each clip's ends
TRIM_KEEP = 0.04      # seconds of it kept at each end


def trim(a):
    """Cut the engine's lead-in and tail silence, keeping a short natural edge."""
    import numpy as np
    loud = np.flatnonzero(np.abs(a) > 10 ** (TRIM_DB / 20))
    if not len(loud):
        return a
    keep = int(TRIM_KEEP * SR)
    return a[max(loud[0] - keep, 0):loud[-1] + keep]


@contextlib.contextmanager
def pinned_extras(engine, hub=None):
    """While a model loads, fetch the repos its engine pulls in on its own (Chatterbox
    Turbo's speech tokenizer) at the revisions tools/voices.py pins. mlx-audio asks for
    their latest version and only warns if that fails, which would leave the voice
    quietly wrong; this fetches the pinned one first, failing loudly, and points
    mlx-audio's own request at it."""
    if hub is None:
        import huggingface_hub as hub
    pins = dict(ENGINE_EXTRAS.get(engine, []))
    for repo, rev in pins.items():
        try:
            hub.snapshot_download(repo, revision=rev)
        except Exception as e:
            raise SystemExit(f"Couldn't fetch {repo} at {rev[:8]}, which {engine} needs: {e}. "
                             "Check the network and rerun; tools/setup.sh downloads it ahead of time.")
    original = hub.hf_hub_download

    def pinned(*args, **kwargs):
        repo = kwargs.get("repo_id", args[0] if args else None)
        if repo in pins:
            kwargs["revision"] = pins[repo]
        return original(*args, **kwargs)

    hub.hf_hub_download = pinned
    try:
        yield
    finally:
        hub.hf_hub_download = original


def mlx_speaker(voice, engine, repo, revision=None):
    """Qwen3-TTS or Chatterbox through mlx-audio, cloning the voice's reference clip."""
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model
    with pinned_extras(engine):
        model = load_model(repo, revision=revision)
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
    ap.add_argument("--voice", required=True, help="a voice from voices/ or me/voices/")
    ap.add_argument("--model", default=None,
                    help="try another model repo for the voice's engine (its latest revision)")
    ap.add_argument("--seed", type=int, default=42, help="a different seed gives a different take of every line")
    ap.add_argument("--tolerance", type=float, default=TOTAL_TOLERANCE,
                    help="how far the whole workout may run over or under plan, as a fraction")
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
    if args.model:   # so the measured rate is filed under this model
        voice["model"], voice["revision"] = args.model, None
    model_repo, revision, seed = voice["model"], voice["revision"], args.seed
    # Everything that changes how a clip sounds goes in its cache key, so changing a
    # setting re-renders instead of silently reusing old clips.
    settings = (f"{model_repo}@{revision or 'latest'}|{json.dumps(voice['generate'], sort_keys=True)}|"
                f"trim {TRIM_DB} {TRIM_KEEP}")

    def cache_path(text):
        key = f"{voice['key']}|{engine}|{seed}|{settings}|{text}"
        return os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")

    clips = [text for seg in segments for para in plan(seg) for text, _ in para if is_spoken(text)]
    todo = list(dict.fromkeys(t for t in clips if not os.path.exists(cache_path(t))))
    print(f"{len(clips)} clips, {len(todo)} to render ({len(clips) - len(todo)} cached), "
          f"voice {voice['name']} on {engine}", flush=True)

    if todo:
        say = mlx_speaker(voice, engine, model_repo, revision)
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
            measured_weight += weight(text)
            print(f"  [{n}/{len(todo)}] {secs:4.1f}s audio in {time.time() - t0:4.1f}s", flush=True)
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

    pcm_all, rows, drift = assemble(segments, clip,
                                    lead=b"" if args.no_chime else chime(), bell=chime(),
                                    tail=b"" if args.no_chime else end_tone())

    print(f"\n{'#':>3} {'plan':>5} {'spoken':>6} {'fill':>5}  label")
    for i, planned, spoken, label, flag in rows:
        print(f"{i:>3} {planned:>5} {spoken:>6.1f} {spoken / planned:>5.0%}  {label}{flag}")

    out = args.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    encode(pcm_all, out, os.path.splitext(os.path.basename(out))[0])

    total = len(pcm_all) / 2 / SR
    print(f"\nWrote {out}: {total / 60:.1f} min audio, {drift:+.1%} of plan, "
          f"total time {(time.time() - started) / 60:.1f} min")
    if abs(drift) > args.tolerance:
        print(f"The workout runs {'long' if drift > 0 else 'short'} by more than {args.tolerance:.0%}. "
              f"{'Trim' if drift > 0 else 'Add'} words in the segments marked or furthest off and rerun; "
              "unchanged clips come from cache.")
        sys.exit(2)


if __name__ == "__main__":
    main()
