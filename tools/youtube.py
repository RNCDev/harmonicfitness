#!/usr/bin/env python3
"""YouTube deep dives: find a fresh video on a favorite channel and save its transcript.

Every other session's deep dive retells a video from one of the channels listed
by @handle on the "YouTube favorites" line under Content in me/profile.md.
`transcript` saves the video's English captions as plain paragraphs in
me/workouts/research/videos/<id>.txt. A video counts as used once its summary sheet,
me/workouts/research/videos/<id>.md, exists; `pick` skips it from then on.

A long video can be told as a series, one part per video session: its sheet
says "- Parts: 3" and "- Parts done: 1" in its header, `pick` lists it first as a
series to continue, and `done` marks the next part told.

The quiz beat can come from a puzzle channel, listed by @handle on the "Puzzles"
line under Content. `puzzles` lists its recent videos not yet used as a quiz; one
counts as used once me/workouts/research/puzzles/<id>.md exists.

yt-dlp is installed in the project's environment (.venv, made by tools/setup.sh), so
the tool reruns itself there when the system python3 doesn't have it.

    python3 tools/youtube.py pick                 # recent unused videos per channel
    python3 tools/youtube.py pick --recent 6      # look further back
    python3 tools/youtube.py transcript <id or URL>
    python3 tools/youtube.py done <id>            # after a session tells a series part
    python3 tools/youtube.py puzzles              # recent unused puzzles for the quiz
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import PROFILE, PUZZLES, VENV_PYTHON, VIDEOS, require, show  # noqa: E402

MIN_SECONDS, MAX_SECONDS = 5 * 60, 3 * 60 * 60   # skip Shorts and marathon streams
PUZZLE_MAX_SECONDS = 30 * 60                      # a quiz puzzle is short
PARAGRAPH_WORDS = 120                             # break at the next sentence end after this
TAG_RE = re.compile(r"\[(?:music|applause|laughter)\]", re.IGNORECASE)

PARTS_RE = re.compile(r"^- Parts:\s*(\d+)\s*$", re.MULTILINE)
DONE_RE = re.compile(r"^- Parts done:\s*(\d+)\s*$", re.MULTILINE)
TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)
yt_dlp = None


def load_yt_dlp():
    """Import yt-dlp, rerunning under the project's environment if this Python lacks it."""
    global yt_dlp
    try:
        import yt_dlp as module
    except ImportError:
        if os.access(VENV_PYTHON, os.X_OK) and os.path.realpath(sys.executable) != os.path.realpath(VENV_PYTHON):
            os.execv(VENV_PYTHON, [VENV_PYTHON, *sys.argv])
        raise SystemExit("yt-dlp not found: run tools/setup.sh to make the project's environment")
    yt_dlp = module


def handles(label="YouTube favorites", profile=PROFILE):
    with open(require(profile, "profile")) as f:
        for line in f:
            if line.lstrip("- ").startswith(label):
                found = re.findall(r"@([\w.-]*[\w-])", line)   # not a sentence's final period
                if found:
                    return found
    raise SystemExit(f"No '{label}' line with @handles under Content in profile.md.")


def used(folder=VIDEOS):
    if not os.path.isdir(folder):
        return set()
    return {name[:-3] for name in os.listdir(folder) if name.endswith(".md")}


def series_state(sheet):
    """(parts, parts done) from a sheet's text; a sheet without a Parts line is one part, done."""
    parts = PARTS_RE.search(sheet)
    if not parts:
        return 1, 1
    done = DONE_RE.search(sheet)
    return int(parts.group(1)), int(done.group(1)) if done else 0


def in_progress(folder=VIDEOS):
    """[(id, next part, parts, title)] for series with parts still to tell."""
    out = []
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if name.endswith(".md"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                sheet = f.read()
            parts, done = series_state(sheet)
            if done < parts:
                title = TITLE_RE.search(sheet)
                out.append((name[:-3], done + 1, parts, title.group(1) if title else ""))
    return out


def mark_done(video, folder=VIDEOS):
    """Record that the next part of a series was told. Returns (parts done, parts)."""
    path = os.path.join(folder, f"{video}.md")
    if not os.path.exists(path):
        raise SystemExit(f"No sheet at {show(path)}")
    with open(path, encoding="utf-8") as f:
        sheet = f.read()
    parts, done = series_state(sheet)
    if not PARTS_RE.search(sheet):
        raise SystemExit(f"{video} isn't a series (its sheet has no '- Parts:' line)")
    done = min(done + 1, parts)
    if DONE_RE.search(sheet):
        sheet = DONE_RE.sub(f"- Parts done: {done}", sheet, count=1)
    else:
        sheet = PARTS_RE.sub(lambda m: f"{m.group(0)}\n- Parts done: {done}", sheet, count=1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(sheet)
    return done, parts


def ydl(**opts):
    return yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, **opts})


def fresh(entries, seen, low, high, recent):
    """The first `recent` entries not in `seen` whose length is within [low, high] seconds."""
    return [e for e in entries or []
            if e.get("id") not in seen and low <= (e.get("duration") or 0) <= high][:recent]


def list_recent(channels, seen, low, high, recent):
    with ydl(extract_flat=True, playlistend=recent * 3) as y:
        for h in channels:
            try:
                info = y.extract_info(f"https://www.youtube.com/@{h}/videos", download=False)
            except yt_dlp.utils.DownloadError as e:
                print(f"@{h}: couldn't list videos ({e})", file=sys.stderr)
                continue
            for e in fresh(info.get("entries"), seen, low, high, recent):
                print(f"@{h:<28} {e['id']}  {round(e['duration'] / 60):>3} min  {e.get('title', '')}")


def pick(recent):
    for vid, part, parts, title in in_progress():
        print(f"{'continue series':<29} {vid}  part {part} of {parts}  {title}")
    list_recent(handles(), used(), MIN_SECONDS, MAX_SECONDS, recent)


def puzzles(recent):
    # Puzzle videos can be short, so only YouTube Shorts (under a minute) are skipped.
    list_recent(handles("Puzzles"), used(PUZZLES), 60, PUZZLE_MAX_SECONDS, recent)


def caption_track(info):
    """English json3 captions: the creator's own first, then YouTube's speech recognition."""
    for source, langs in ((info.get("subtitles"), ("en", "en-US", "en-GB")),
                          (info.get("automatic_captions"), ("en-orig", "en"))):
        source = source or {}
        keys = [k for k in langs if k in source] + sorted(k for k in source if k.startswith("en-"))
        for k in keys:
            for fmt in source[k]:
                if fmt.get("ext") == "json3":
                    return fmt["url"], source is info.get("subtitles")
    return None, False


def paragraphs(events):
    out, buf = [], []
    for ev in events:
        text = "".join(s.get("utf8", "") for s in ev.get("segs") or [])
        text = TAG_RE.sub(" ", html.unescape(text).replace("\xa0", " ").replace("\n", " "))
        words = text.split()
        if not words:
            continue
        buf.extend(words)
        if len(buf) >= PARAGRAPH_WORDS and buf[-1][-1] in ".?!":
            out.append(" ".join(buf))
            buf = []
    if buf:
        out.append(" ".join(buf))
    return out


def transcript(ref):
    url = ref if ref.startswith("http") else f"https://www.youtube.com/watch?v={ref}"
    with ydl() as y:
        try:
            info = y.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            raise SystemExit(f"Couldn't load {url}: {e}")
        track, manual = caption_track(info)
        if not track:
            raise SystemExit(f"No English captions for {url}; pick another video.")
        events = json.loads(y.urlopen(track).read()).get("events", [])

    body = paragraphs(events)
    d = info.get("upload_date") or ""
    header = [
        f"Title: {info.get('title', '')}",
        f"Channel: {info.get('channel', '')} ({info.get('uploader_id', '')})",
        f"Uploaded: {d[:4]}-{d[4:6]}-{d[6:]}" if d else "Uploaded: unknown",
        f"Length: {round((info.get('duration') or 0) / 60)} min",
        f"URL: https://www.youtube.com/watch?v={info['id']}",
        f"Captions: {'the creator’s own' if manual else 'automatic speech recognition, so names and numbers may be misheard'}",
    ]
    os.makedirs(VIDEOS, exist_ok=True)
    path = os.path.join(VIDEOS, f"{info['id']}.txt")
    with open(path, "w") as f:
        f.write("\n".join(header) + "\n\n" + "\n\n".join(body) + "\n")
    words = sum(len(p.split()) for p in body)
    print(f"{show(path)}  ({words} words)  {info.get('title', '')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick", help="list recent unused videos from each favorite channel")
    p.add_argument("--recent", type=int, default=3, help="videos per channel (default 3)")
    t = sub.add_parser("transcript", help="save a video's transcript for the deep dive")
    t.add_argument("video", help="video id or URL")
    d = sub.add_parser("done", help="mark the next part of a series as told")
    d.add_argument("video", help="video id")
    z = sub.add_parser("puzzles", help="list recent puzzle videos not yet used as a quiz")
    z.add_argument("--recent", type=int, default=8, help="videos to list (default 8)")
    args = ap.parse_args()
    if args.cmd == "done":
        done, parts = mark_done(args.video)
        print(f"{args.video}: part {done} of {parts} told" + ("; series finished" if done == parts else ""))
        return
    load_yt_dlp()
    if args.cmd == "pick":
        pick(args.recent)
    elif args.cmd == "puzzles":
        puzzles(args.recent)
    else:
        transcript(args.video)


if __name__ == "__main__":
    main()
