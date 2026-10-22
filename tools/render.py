#!/usr/bin/env python3
"""Render a segmented workout draft to one MP3, voicing each paragraph in-process.

Runs in the project's own environment, .venv (./sweatcast setup makes it; ./sweatcast
runs it there). Each voice is cloned from its reference clip with Chatterbox Turbo or
Qwen3-TTS through mlx-audio on a Mac, or with Resemble AI's PyTorch Chatterbox Turbo on
a Windows PC's NVIDIA GPU (tools/engines.py), using the model revision its
voices/<name>.json pins for that system. A soft chime opens each segment after the first, a [chime]
marker rings it inside a segment, and a three-note tone marks the end of the
workout. A segment's spare seconds widen its paragraph breaks and then it ends
early, a slightly long segment is paid back from the next ones' spare time, the
whole workout is held within three percent of plan, and the result is
loudness-normalized for earbuds.

No app or server needed. Clips are cached in me/workouts/.audio-cache, so rerunning
after editing a few segments only re-renders what changed. Only one render runs at
a time: a second one waits for the first (two voice models don't fit in 16 GB).
Each MP3 gets a record of how it was made: <name>.build.json beside it, and a line
in me/workouts/.logs/builds.jsonl.

Exit codes (cli.py): 0 done, 2 the workout ran more than --tolerance off plan (the MP3
is written), 64 a mistyped command, 1 anything else.

Usage (normally via ./sweatcast build):
    ./sweatcast render draft.txt --voice "Chatterbox Coach" --out "me/workouts/Workout ....mp3"
    ./sweatcast render draft.txt --voice "Chatterbox Coach" --clips-only   # fill the cache, no MP3
"""
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import engines  # noqa: E402
import locks  # noqa: E402
from draft import (CHIME, CHIME_SECONDS, HOLD, PARAGRAPH_GAP, TOTAL_TOLERANCE, fill_flag, layout,  # noqa: E402
                   parse, plan, spoken as is_spoken)
from engines import SR, TRIM_DB, TRIM_KEEP  # noqa: E402
from paths import BUILDS, CACHE as CACHE_DIR, VERSION_FILE, show  # noqa: E402
from voices import MLX_EDGE, check_pace_file, lookup, record_rate, weight  # noqa: E402

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
    """Lay the clips out on the plan's clock, as draft.layout predicts.

    clip(text) returns a clip's PCM. `lead` (the chime) opens every segment after
    the first, `bell` rings at each [chime] marker (default: the chime), and `tail`
    (the end tone) follows the last segment, past the plan's clock. A segment with
    time to spare widens its breaks and ends early instead of padding with silence,
    unless it has a [hold]: its spare time is then silence at its holds.
    Returns (pcm, rows, drift): rows as (n, planned, spoken, label, flag), drift as
    the whole workout's fraction over (+) or under (-) plan, not counting the tail."""
    bell = chime() if bell is None else bell
    built = []
    for i, seg in enumerate(segments, 1):
        paras = []   # each paragraph: PCM pieces, with None where a hold falls
        for para in plan(seg):
            p = [bytearray()]
            for text, pause in para:
                if text == CHIME:
                    p[-1] += bell
                elif text == HOLD:   # a fixed hold is its silence; a bare one takes its share of the spare
                    if not pause:
                        p += [None, bytearray()]
                elif text:
                    p[-1] += clip(text)
                p[-1] += silence(pause)
            paras.append(p)
        head = lead if i > 1 else b""
        gaps = len(paras) - 1
        spoken = (len(head) + sum(len(x) for p in paras for x in p if x is not None)) / 2 / SR \
            + PARAGRAPH_GAP * gaps
        held = any(text == HOLD for para in plan(seg) for text, _ in para)
        built.append((head, paras, spoken, gaps, sum(x is None for p in paras for x in p), held))

    pcm_all, rows = bytearray(), []
    timeline = layout([(spoken, gaps, seg["seconds"], held) for seg, (_, _, spoken, gaps, _, held) in zip(segments, built)])
    for i, (seg, (head, paras, spoken, gaps, n, held), (extra, length)) in enumerate(zip(segments, built, timeline), 1):
        hold = max(length - spoken, 0.0) / n if n else 0.0
        seg_pcm = bytearray(head)
        for j, p in enumerate(paras):
            if j:
                seg_pcm += silence(PARAGRAPH_GAP + extra)
            for x in p:
                seg_pcm += silence(hold) if x is None else x
        seg_pcm += silence(length - len(seg_pcm) / 2 / SR)
        flag = fill_flag(spoken, seg["seconds"], held=held)
        rows.append((i, seg["seconds"], spoken, seg["label"], f"  <-- {flag}" if flag else ""))
        pcm_all += seg_pcm
    built.clear()   # the per-paragraph copies aren't needed once laid out
    planned = sum(seg["seconds"] for seg in segments)
    drift = len(pcm_all) / 2 / SR / planned - 1 if planned else 0.0
    pcm_all += tail
    return pcm_all, rows, drift


def loudness_stats(stderr):
    """The measurements ffmpeg's loudnorm prints as the last JSON object on stderr."""
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr or "")
    try:
        stats = json.loads(m.group(0)) if m else None
        if stats:
            for key in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset"):
                stats[key]
            return stats
    except (ValueError, KeyError):
        pass
    raise SystemExit(f"Couldn't read ffmpeg's loudness measurement ({ffmpeg_version() or 'ffmpeg'}). "
                     f"The end of its output was: {(stderr or '')[-300:].strip()}")


def ffmpeg_version():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=10).stdout
        return out.splitlines()[0] if out else None
    except (OSError, subprocess.SubprocessError):
        return None


def encode(pcm, out, title):
    """Two-pass loudness normalization, then encode by the output's extension."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg not found; install it with: brew install ffmpeg (Mac) "
                         "or winget install Gyan.FFmpeg.Essentials (Windows)")
    codec = CODECS.get(os.path.splitext(out)[1].lower())
    if not codec:
        raise SystemExit(f"--out must end in one of: {', '.join(CODECS)}")
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, "raw.wav")
        with wave.open(raw, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm)
        probe = subprocess.run([ffmpeg, "-hide_banner", "-nostats", "-i", raw, "-af",
                                f"loudnorm={LOUDNESS}:print_format=json", "-f", "null", "-"],
                               capture_output=True, text=True, check=True)
        m = loudness_stats(probe.stderr)
        af = (f"loudnorm={LOUDNESS}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", raw, "-af", af, "-ar", str(SR),
                        "-metadata", f"title={title}", *codec, out], check=True)


@contextlib.contextmanager
def render_lock(folder, wait_message=True):
    """One render at a time: two voice models don't fit in 16 GB. A second render
    waits here for the first to finish, then reuses the clips it cached."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, ".render.lock")
    with open(path, "a+") as f:
        if not locks.acquire(f, block=False):
            f.seek(0)
            holder = f.read().strip() or "unknown"
            if wait_message:
                print(f"Another render is running (pid {holder}); waiting for it to finish.", flush=True)
            locks.acquire(f)
        f.seek(0)
        f.truncate()
        f.write(str(os.getpid()))
        f.flush()
        try:
            yield
        finally:
            locks.release(f)


def engine_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def build_record(draft_path, out, voice, seed, clips_total, clips_rendered, planned, actual, drift,
                 render_seconds, started):
    """How an MP3 was made: enough to tell later what produced it."""
    with open(draft_path, "rb") as f:
        draft_hash = hashlib.sha256(f.read()).hexdigest()
    return {"out": show(os.path.abspath(out)), "engine_version": engine_version(), "draft": show(os.path.abspath(draft_path)),
            "draft_sha256": draft_hash, "voice": voice["name"], "voice_key": voice["key"],
            "engine": voice["engine"], "model": voice["model"], "revision": voice["revision"],
            "backend": voice.get("backend", "mlx"), "runtime": engines.runtime(voice),
            "mlx_audio": engines.mlx_audio_version(), "ffmpeg": ffmpeg_version(), "seed": seed,
            "clips_total": clips_total, "clips_rendered": clips_rendered,
            "planned_s": round(planned, 2), "actual_s": round(actual, 2), "drift": round(drift, 4),
            "render_s": round(render_seconds, 1),
            "started_at": dt.datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds")}


def save_build_record(record, out, log=None):
    """Write <out>.build.json beside the MP3 and append the record to builds.jsonl."""
    log = log or BUILDS
    with open(os.path.splitext(out)[0] + ".build.json", "w", encoding="utf-8") as f:
        json.dump(record, f, indent=1)
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def main():
    ap = cli.ArgumentParser()
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
    check_pace_file()   # a damaged pace file stops the render now, not after it
    started = time.time()

    voice = lookup(args.voice)
    engine = voice["engine"]
    if args.model:   # so the measured rate is filed under this model
        voice["model"], voice["revision"] = args.model, None
    model_repo, revision, seed = voice["model"], voice["revision"], args.seed
    # Everything that changes how a clip sounds goes in its cache key, so changing a
    # setting (or upgrading mlx-audio) re-renders instead of silently reusing old clips.
    settings = (f"{model_repo}@{revision or 'latest'}|{json.dumps(voice['generate'], sort_keys=True)}|"
                f"trim {TRIM_DB} {TRIM_KEEP}|{engines.runtime(voice)}")

    def cache_path(text):
        key = f"{voice['key']}|{engine}|{seed}|{settings}|{text}"
        return os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")

    clips = [text for seg in segments for para in plan(seg) for text, _ in para if is_spoken(text)]
    with render_lock(CACHE_DIR):
        # Counted after the lock, so clips a render that ran first cached aren't redone.
        todo = list(dict.fromkeys(t for t in clips if not os.path.exists(cache_path(t))))
        print(f"{len(clips)} clips, {len(todo)} to render ({len(clips) - len(todo)} cached), "
              f"voice {voice['name']} on {engine}", flush=True)

        if todo:
            say = engines.speaker(voice)
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
            del say
            engines.release()   # the model's memory isn't needed to assemble and encode
            # The lint predicts this voice's length from its measured rate.
            record_rate(voice, measured_weight, audio_secs - MLX_EDGE * len(todo))
            took = time.time() - speaking_started
            print(f"rendered {audio_secs / 60:.1f} min of speech in {took / 60:.1f} min "
                  f"({took / audio_secs:.2f} times its length, not counting the model load)", flush=True)

        if args.clips_only:
            print(f"Clips cached for {len(segments)} segment(s); the full build reuses them.")
            return

        def clip(text):
            path = cache_path(text)
            with open(path, "rb") as f:
                pcm = f.read()
            os.utime(path)   # marks the clip as recently used, for tools/cache.py prune
            return pcm

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
    planned_total = sum(seg["seconds"] for seg in segments)
    save_build_record(build_record(args.draft, out, voice, seed, len(clips), len(todo), planned_total,
                                   planned_total * (1 + drift), drift, time.time() - started, started), out)
    print(f"\nWrote {out}: {total / 60:.1f} min audio, {drift:+.1%} of plan, "
          f"total time {(time.time() - started) / 60:.1f} min")
    if abs(drift) > args.tolerance:
        print(f"The workout runs {'long' if drift > 0 else 'short'} by more than {args.tolerance:.0%}. "
              f"{'Trim' if drift > 0 else 'Add'} words in the segments marked or furthest off and rerun; "
              "unchanged clips come from cache.")
        sys.exit(cli.DRIFT)


if __name__ == "__main__":
    main()
