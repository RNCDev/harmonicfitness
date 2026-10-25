"""Render a segmented workout draft to one MP3, voicing each paragraph in-process.

Runs in the project's own environment, .venv (./sweatcast setup makes it; ./sweatcast
runs it there). Each local coach is cloned from its reference clip with Chatterbox Turbo or
Qwen3-TTS through mlx-audio on a Mac, or with Resemble AI's PyTorch Chatterbox Turbo on
a Windows PC's NVIDIA GPU (tools/engines.py); a web coach speaks by its saved voice on its
own service (tools/cloud.py). A soft chime opens each segment after the first, a [chime]
marker rings it inside a segment, and a three-note tone marks the end of the
workout. A segment's spare seconds widen its paragraph breaks and then it ends
early, a slightly long segment is paid back from the next ones' spare time, the
whole workout is held within three percent of plan, and the result is
loudness-normalized for earbuds.

No app or server needed. Clips are cached in me/workouts/.audio-cache, so rerunning
after editing a few segments only re-renders what changed. Only one render runs at
a time: a second one waits for the first (two voice models don't fit in 16 GB).
Each MP3 gets a record of how it was made: <name>.build.json beside it, and a line
in me/workouts/.logs/builds.jsonl (where a web render that sent text and then stopped leaves a "failed" line).

./sweatcast build is the one way in: it lints the draft, holds it to its menu, and then calls run() (or
clips() and follow(), to render ahead) in its own process, and decides what a drift past the tolerance
means (exit 2).
"""
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import engines  # noqa: E402
import ffmpeg as ffmpeg_tool  # noqa: E402
import locks  # noqa: E402
from locks import FOLLOWING, render_lock, stop_file  # noqa: E402,F401
from draft import (CHIME, CHIME_SECONDS, HOLD, PARAGRAPH_GAP, TOTAL_TOLERANCE, fill_flag, holds,  # noqa: E402
                   layout, parse, plan, spoken as is_spoken)
from engines import SR, TRIM_DB, TRIM_KEEP  # noqa: E402
import paths  # noqa: E402
from voices import MLX_EDGE, check_pace_file, record_rate, weight  # noqa: E402

CHIME_TONE = 0.35     # seconds of bell; the rest of CHIME_SECONDS is quiet before the voice
CHIME_LEVEL = 0.12    # peak; at 0.2 the bell averaged as loud as the voice, so this sits about 4 dB under
END_NOTES = (660, 880, 1320)   # Hz, rising, so the end can't be mistaken for a segment bell
END_NOTE = 0.3        # seconds per note
END_LEAD = 1.0        # seconds of quiet before the end tone
LOUDNESS = "I=-16:TP=-1.5:LRA=11"   # podcast level, with headroom under 0 dBFS
FOLLOW_IDLE = 900    # seconds --follow waits with nothing new before it stops
FOLLOW_POLL = 2.0    # seconds between looks at the draft when nothing is new
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
        held = holds(seg)[1] > 0   # the one rule the lint uses too
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
    ffmpeg = ffmpeg_tool.exe()
    if not ffmpeg:
        return None
    try:
        out = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=10).stdout
        return out.splitlines()[0] if out else None
    except (OSError, subprocess.SubprocessError):
        return None


def encode(pcm, out, title):
    """Two-pass loudness normalization, then encode by the output's extension (checked by preflight)."""
    ffmpeg = preflight(out)
    codec = CODECS[os.path.splitext(out)[1].lower()]
    with tempfile.TemporaryDirectory() as td:
        raw = os.path.join(td, "raw.wav")
        with wave.open(raw, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm)
        probe = _ffmpeg_run([ffmpeg, "-hide_banner", "-nostats", "-i", raw, "-af",
                             f"loudnorm={LOUDNESS}:print_format=json", "-f", "null", "-"], "measure the loudness")
        m = loudness_stats(probe.stderr)
        af = (f"loudnorm={LOUDNESS}:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
        # Encoded beside the output under a temporary name (its extension kept, so ffmpeg picks the format),
        # then renamed: an old MP3 is never left half-overwritten, and a failure leaves nothing behind.
        stem, ext = os.path.splitext(out)
        part = f"{stem}.part{ext}"
        try:
            _ffmpeg_run([ffmpeg, "-y", "-loglevel", "error", "-i", raw, "-af", af, "-ar", str(SR),
                         "-metadata", f"title={title}", *codec, part], "encode the audio")
            os.replace(part, out)
        finally:
            if os.path.exists(part):
                os.remove(part)


def _ffmpeg_run(cmd, what):
    """Run ffmpeg; a failure stops with the end of what it said, not a traceback."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        tail = (e.stderr or "").strip()[-300:]
        raise SystemExit(f"ffmpeg couldn't {what} ({ffmpeg_version() or 'ffmpeg'}, exit {e.returncode}): "
                         f"{tail or 'no reason given'}") from None


def engine_version():
    try:
        with open(paths.VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def build_record(draft_path, draft_sha256, out, voice, seed, clips_total, clips_rendered, planned, actual, drift,
                 render_seconds, started):
    """How an MP3 was made: enough to tell later what produced it. `draft_sha256` is the hash of the text
    that was rendered (the caller parsed it)."""
    show = paths.show
    return {"out": show(os.path.abspath(out)), "engine_version": engine_version(), "draft": show(os.path.abspath(draft_path)),
            "draft_sha256": draft_sha256, "voice": voice["name"], "voice_key": voice["key"],
            "engine": voice["engine"], "model": voice["model"], "revision": voice["revision"],
            "backend": voice.get("backend", "mlx"), "runtime": engines.runtime(voice),
            "mlx_audio": engines.mlx_audio_version(), "ffmpeg": ffmpeg_version(), "seed": seed,
            "clips_total": clips_total, "clips_rendered": clips_rendered,
            "planned_s": round(planned, 2), "actual_s": round(actual, 2), "drift": round(drift, 4),
            "render_s": round(render_seconds, 1),
            "started_at": dt.datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds")}


def save_build_record(record, out, log=None):
    """Write <out>.build.json beside the MP3 and append the record to builds.jsonl."""
    import fileio
    log = log or paths.BUILDS
    fileio.atomic_write(os.path.splitext(out)[0] + ".build.json", json.dumps(record, indent=1) + "\n")
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def save_failed_record(voice, out, draft_path, draft_sha256, sent, started, error):
    """A cloud render that stopped partway: one line in builds.jsonl with the characters already sent, marked
    "failed" (no MP3, no <name>.build.json). A reader counting MP3s skips lines with "failed"."""
    import cloud
    if isinstance(error, SystemExit):
        reason = str(error.code) if not isinstance(error.code, int) else f"exit {error.code}"
    else:
        reason = type(error).__name__ + (f": {error}" if str(error) else "")
    usd = cloud.estimate(voice["service"], voice["model"], ["x" * sent["started"]])[1]
    record = {"failed": True, "out": paths.show(os.path.abspath(out)),
              "draft": paths.show(os.path.abspath(draft_path)), "draft_sha256": draft_sha256,
              "voice": voice["name"], "voice_key": voice["key"], "engine": voice["engine"], "model": voice["model"],
              "route": voice.get("route"), "chars_sent": sent["started"], "chars_rendered": sent["chars"],
              "usd_estimate": round(usd, 4), "reason": cloud.scrub(reason)[:300],
              "started_at": dt.datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds")}
    try:
        os.makedirs(os.path.dirname(paths.BUILDS), exist_ok=True)
        with open(paths.BUILDS, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError as e:   # the failure being reported matters more than this line
        print(f"(Couldn't note the failed render in {paths.show(paths.BUILDS)}: {e})", file=sys.stderr)


def prepare_voice(voice, model=None, seed=42):
    """The voice as this render uses it, and cache_path(text), where a line's clip is cached. A damaged pace
    file stops the render now, not after it; `model` (--model) files the measured rate under that model; the
    processor's clips sound a little different, so they get their own key."""
    check_pace_file(voice.get("pace_file"))
    if model:
        voice["model"], voice["revision"] = model, None
    if voice.get("backend") == "torch":
        voice["device"] = engines.torch_device(engines.cuda_available())
    return voice, clip_cache(voice, seed)


def clip_cache(voice, seed):
    """cache_path(text): where a line's clip is cached. Everything that changes how a clip sounds goes in
    its key, so changing a setting (or upgrading mlx-audio) re-renders instead of silently reusing old
    clips; the coach's name and any API key don't, so a renamed coach keeps its clips."""
    settings = (f"{voice['model']}@{voice['revision'] or 'latest'}|{json.dumps(voice['generate'], sort_keys=True)}|"
                f"trim {TRIM_DB} {TRIM_KEEP}|{engines.runtime(voice)}")

    def cache_path(text):
        key = f"{voice['key']}|{voice['engine']}|{seed}|{settings}|{text}"
        return os.path.join(paths.CACHE, hashlib.sha256(key.encode()).hexdigest()[:24] + ".pcm")
    return cache_path


def spoken_clips(segments):
    return [text for seg in segments for para in plan(seg) for text, _ in para if is_spoken(text)]


def render_clip(say, text, seed, cache_path, **context):
    """Speak one line into the cache; returns its seconds of audio. `context` (previous_text, next_text)
    goes to a cloud engine that joins paragraphs."""
    pcm = say(text, seed, **context)
    tmp = cache_path(text) + ".part"
    with open(tmp, "wb") as f:
        f.write(pcm)
    os.replace(tmp, cache_path(text))
    return len(pcm) / 2 / SR


def render_cloud(voice, todo, clips, seed, cache_path, sent):
    """Send the clips not cached yet to the voice's service, a few at a time, after saying what it will cost
    and stopping if it's over the profile's ceiling. Each clip is cached as it lands, so a rerun after a
    failure sends only what's left."""
    import cloud
    import context
    service = cloud.services()[voice["service"]]
    chars, usd = cloud.estimate(voice["service"], voice["model"], todo)
    ceiling = context.cloud_max_chars(context.profile()) if os.path.exists(paths.PROFILE) else context.CLOUD_MAX_CHARS
    print(f"Sending {chars:,} characters to {service['name']} ({voice['model']}): about ${usd:.2f} "
          f"(approximate; rates checked {service.get('rates_checked')})", flush=True)
    if chars > ceiling:
        print(f"That's over this profile's ceiling of {ceiling:,} characters a build (cloud_max_chars in "
              "me/settings.toml), so nothing was sent. Shorten the script, or raise the ceiling and rerun.")
        sys.exit(cli.ISSUES)
    long = [t for t in todo if voice.get("max_chars") and len(t) > voice["max_chars"]]
    if long:
        print(f"A paragraph runs {len(long[0])} characters, over {service['name']}'s {voice['max_chars']} a request: "
              f"split \"{' '.join(long[0].split()[:6])}...\" and rerun. Nothing was sent.")
        sys.exit(cli.ISSUES)
    order = list(dict.fromkeys(clips))   # each paragraph's real neighbors, for services that join them
    at = {t: i for i, t in enumerate(order)}
    started = time.time()
    audio_secs, measured_weight, done = 0.0, 0.0, 0
    from concurrent.futures import ThreadPoolExecutor, as_completed
    pool = ThreadPoolExecutor(max_workers=max(1, voice.get("concurrency") or 1))
    import threading
    stop = threading.Event()   # set by the first failure (or Ctrl-C), so no worker starts another request
    cloud.stop_on(stop)   # and no request already out retries once it's set
    try:
        say = engines.speaker(voice)   # the first request goes out here

        def one(text, **ctx):
            if stop.is_set():
                return None
            sent["started"] += len(text)   # counted as it goes out: a failure may still bill it
            try:
                return render_clip(say, text, seed, cache_path, **ctx)
            except BaseException:
                stop.set()
                raise
        jobs = {}
        for text in todo:
            i = at[text]
            ctx = {"previous_text": order[i - 1] if i else None,
                   "next_text": order[i + 1] if i + 1 < len(order) else None}
            jobs[pool.submit(one, text, **ctx)] = text
        for job in as_completed(jobs):
            secs = job.result()
            if secs is None:
                continue
            done += 1
            audio_secs += secs
            measured_weight += weight(jobs[job])
            sent["chars"] += len(jobs[job])
            print(f"  [{done}/{len(todo)}] {secs:4.1f}s audio", flush=True)
    except BaseException as e:   # anything at all: nothing still queued gets sent (and billed)
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        if done:
            record_rate(voice, measured_weight, audio_secs - MLX_EDGE * done)
        if isinstance(e, cloud.ServiceError):
            print(f"\n{e}")
            if e.listener_must_act:
                print(f"Check the key with ./sweatcast keys (it's {service['key_var']} in me/.env), and the account's "
                      f"plan and balance at {service['name']}. The {done} clip(s) rendered are cached.")
                sys.exit(cli.SERVICE)
            if e.kind == "bad_request":
                print(f"A rerun won't fix that by itself; the {done} clip(s) rendered are cached.")
            else:
                print(f"The {done} clip(s) rendered are cached; rerun to send only the rest.")
            sys.exit(cli.ISSUES)
        if isinstance(e, Exception) and not isinstance(e, SystemExit):
            print(f"\nStopped sending to {service['name']}: {cloud.scrub(str(e))}. The {done} clip(s) rendered are cached.")
            sys.exit(cli.ISSUES)
        raise
    finally:
        cloud.stop_on(None)
    pool.shutdown()
    sent["usd"] = cloud.estimate(voice["service"], voice["model"], todo)[1]
    took = time.time() - started
    record_rate(voice, measured_weight, audio_secs - MLX_EDGE * len(todo), render_seconds=took)
    print(f"rendered {audio_secs / 60:.1f} min of speech in {took / 60:.1f} min", flush=True)


def _render_local(voice, todo, seed, cache_path):
    """Voice `todo` on the local engine, one clip at a time, and fold the measurements into the pace file."""
    started = time.time()
    say = engines.speaker(voice)
    print(f"model ready in {time.time() - started:.0f}s", flush=True)
    speaking_started = time.time()
    audio_secs, measured_weight = 0.0, 0.0
    for n, text in enumerate(todo, 1):
        t0 = time.time()
        secs = render_clip(say, text, seed, cache_path)
        audio_secs += secs
        measured_weight += weight(text)
        print(f"  [{n}/{len(todo)}] {secs:4.1f}s audio in {time.time() - t0:4.1f}s", flush=True)
    del say
    engines.release()   # the model's memory isn't needed to assemble and encode
    took = time.time() - speaking_started
    # The lint predicts this voice's length from its measured rate; the speed is this computer's.
    record_rate(voice, measured_weight, audio_secs - MLX_EDGE * len(todo), render_seconds=took)
    print(f"rendered {audio_secs / 60:.1f} min of speech in {took / 60:.1f} min "
          f"({took / audio_secs:.2f} times its length, not counting the model load)", flush=True)


def preflight(out):
    """What must hold before a single clip is rendered (or billed), and again at the encode: the output's
    extension is one we encode, and ffmpeg is here to encode it. Returns ffmpeg's path."""
    if os.path.splitext(out)[1].lower() not in CODECS:
        raise cli.Usage(f"The output must end in one of: {', '.join(CODECS)} (not {os.path.basename(out)})")
    ffmpeg = ffmpeg_tool.exe()
    if not ffmpeg:
        raise SystemExit(f"ffmpeg not found, and the environment's own copy isn't installed: rerun "
                         f"./sweatcast setup, or install it ({ffmpeg_tool.install_hint()})")
    return ffmpeg


def drift_message(drift, tolerance):
    return (f"The workout runs {'long' if drift > 0 else 'short'} by more than {tolerance:.0%}. "
            f"{'Trim' if drift > 0 else 'Add'} words in the segments marked or furthest off and rerun; "
            "unchanged clips come from cache.")


def run(segments, voice, out, draft_path, draft_sha256, seed=42, tolerance=TOTAL_TOLERANCE, no_chime=False,
        model=None):
    """Render parsed `segments` with `voice` to `out` (.mp3, .m4a or .wav): the clips not cached yet (on the
    voice's service, or the local engine, under the render lock), the layout on the plan's clock, the loudness
    pass, the encode, and the build record. Returns the drift, the fraction the whole ran over (+) or under (-)
    plan; the caller decides what a drift past `tolerance` means (./sweatcast build exits 2). The caller has
    checked the draft against its menu: this renders what it's given."""
    preflight(out)
    started = time.time()
    voice, cache_path = prepare_voice(voice, model, seed)
    engine = voice["engine"]
    clips = spoken_clips(segments)
    with render_lock(paths.CACHE):
        # Counted after the lock, so clips a render that ran first cached aren't redone.
        todo = list(dict.fromkeys(t for t in clips if not os.path.exists(cache_path(t))))
        print(f"{len(clips)} clips, {len(todo)} to render ({len(clips) - len(todo)} cached), "
              f"voice {voice['name']} on {engine}", flush=True)
        sent = {"chars": 0, "started": 0, "usd": 0.0}
        if todo and voice.get("backend") == "cloud":
            try:
                render_cloud(voice, todo, clips, seed, cache_path, sent)
            except BaseException as e:
                if sent["started"]:   # characters went out (and may be billed): builds.jsonl keeps a line for them
                    save_failed_record(voice, out, draft_path, draft_sha256, sent, started, e)
                raise
        elif todo:
            _render_local(voice, todo, seed, cache_path)

        def clip(text):
            path = cache_path(text)
            with open(path, "rb") as f:
                pcm = f.read()
            os.utime(path)   # marks the clip as recently used, for tools/cache.py prune
            return pcm

        pcm_all, rows, drift = assemble(segments, clip,
                                        lead=b"" if no_chime else chime(), bell=chime(),
                                        tail=b"" if no_chime else end_tone())

    print(f"\n{'#':>3} {'plan':>5} {'spoken':>6} {'fill':>5}  label")
    for i, planned, spoken, label, flag in rows:
        print(f"{i:>3} {planned:>5} {spoken:>6.1f} {spoken / planned:>5.0%}  {label}{flag}")

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    try:
        encode(pcm_all, out, os.path.splitext(os.path.basename(out))[0])
    except BaseException as e:
        if sent["started"]:   # the clips are paid for and cached, but no MP3 (and no record) came of them
            save_failed_record(voice, out, draft_path, draft_sha256, sent, started, e)
        raise

    total = len(pcm_all) / 2 / SR
    planned_total = sum(seg["seconds"] for seg in segments)
    record = build_record(draft_path, draft_sha256, out, voice, seed, len(clips), len(todo), planned_total,
                          planned_total * (1 + drift), drift, time.time() - started, started)
    record["route"] = voice.get("route", "local")
    if voice.get("backend") == "cloud":
        record.update(chars_sent=sent["chars"], usd_estimate=round(sent["usd"], 4))
    save_build_record(record, out)
    print(f"\nWrote {out}: {total / 60:.1f} min audio, {drift:+.1%} of plan, "
          f"total time {(time.time() - started) / 60:.1f} min")
    return drift   # the caller says what a drift past its tolerance means (drift_message), and exits 2


def clips(voice, segments, seed=42):
    """--clips-only: render and cache the draft's clips once (local only), no timing check, no MP3."""
    voice, cache_path = prepare_voice(voice, None, seed)
    with render_lock(paths.CACHE):
        todo = list(dict.fromkeys(t for t in spoken_clips(segments) if not os.path.exists(cache_path(t))))
        if todo:
            _render_local(voice, todo, seed, cache_path)
    print(f"Clips cached for {len(segments)} segment(s); the full build reuses them.")


def follow(voice, draft_path, seed=42, idle=FOLLOW_IDLE):
    """Render ahead of a draft that's still being written (local only). Rereads the draft between clips, so
    each new or edited paragraph renders as it appears, one at a time with the model kept
    loaded; a draft caught mid-edit is read again a moment later. Stops when another render
    asks for the lock (the full build, which then renders what's left), or after `idle`
    seconds with nothing new."""
    voice, cache_path = prepare_voice(voice, None, seed)
    stop = stop_file(paths.CACHE)
    with render_lock(paths.CACHE, follow=True):
        if os.path.exists(stop):   # left by a render-ahead that ended before it saw it
            os.remove(stop)
        print(f"Rendering ahead of {draft_path} with {voice['name']}; stops when the build starts "
              f"or after {idle:.0f}s with nothing new.", flush=True)
        say, done, audio_secs, measured_weight = None, 0, 0.0, 0.0
        idle_since = time.time()
        while not os.path.exists(stop):
            try:
                with open(draft_path, encoding="utf-8") as f:
                    todo = [t for t in spoken_clips(parse(f.read())) if not os.path.exists(cache_path(t))]
            except (OSError, ValueError, SystemExit):   # missing for now, or caught mid-edit
                todo = []
            if not todo:
                if time.time() - idle_since > idle:
                    print(f"Nothing new for {idle:.0f}s; stopping.", flush=True)
                    break
                time.sleep(FOLLOW_POLL)
                continue
            if say is None:
                say = engines.speaker(voice)
            t0 = time.time()
            secs = render_clip(say, todo[0], seed, cache_path)
            done, audio_secs, measured_weight = done + 1, audio_secs + secs, measured_weight + weight(todo[0])
            print(f"  [{done}] {secs:4.1f}s audio in {time.time() - t0:4.1f}s", flush=True)
            idle_since = time.time()
        if os.path.exists(stop):
            os.remove(stop)
        if say is not None:
            del say
            engines.release()
        if done:
            record_rate(voice, measured_weight, audio_secs - MLX_EDGE * done)
    print(f"Rendered {done} clip(s) ahead; the full build reuses them.", flush=True)
