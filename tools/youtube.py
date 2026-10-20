#!/usr/bin/env python3
"""YouTube deep dives: find a fresh video on a favorite channel and save its transcript.

Every other session's deep dive retells a video from one of the channels listed
by @handle on the "YouTube favorites" line under Content in knowledge/profile.md.
`transcript` saves the video's English captions as plain paragraphs in
workouts/research/videos/<id>.txt. A video counts as used once its summary sheet,
workouts/research/videos/<id>.md, exists; `pick` skips it from then on.

yt-dlp ships with VoiceStudio's bundled Python, so the tool reruns itself there
when the system python3 doesn't have it.

    python3 tools/youtube.py pick                 # recent unused videos per channel
    python3 tools/youtube.py pick --recent 6      # look further back
    python3 tools/youtube.py transcript <id or URL>
"""
import argparse
import html
import json
import os
import re
import sys

VS_PYTHON = os.path.expanduser(
    "~/Library/Application Support/VoiceStudio/runtime/project/.venv/bin/python")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE = os.path.join(ROOT, "knowledge", "profile.md")
VIDEOS = os.path.join(ROOT, "workouts", "research", "videos")

MIN_SECONDS, MAX_SECONDS = 5 * 60, 3 * 60 * 60   # skip Shorts and marathon streams
PARAGRAPH_WORDS = 120                             # break at the next sentence end after this
TAG_RE = re.compile(r"\[(?:music|applause|laughter)\]", re.IGNORECASE)

try:
    import yt_dlp
except ImportError:
    if os.access(VS_PYTHON, os.X_OK) and sys.executable != VS_PYTHON:
        os.execv(VS_PYTHON, [VS_PYTHON, *sys.argv])
    raise SystemExit("yt-dlp not found (open the VoiceStudio app once to install its runtime)")


def handles():
    with open(PROFILE) as f:
        for line in f:
            if line.lstrip("- ").startswith("YouTube favorites"):
                found = re.findall(r"@([\w.-]*[\w-])", line)   # not a sentence's final period
                if found:
                    return found
    raise SystemExit("No 'YouTube favorites' line with @handles under Content in profile.md.")


def used():
    if not os.path.isdir(VIDEOS):
        return set()
    return {name[:-3] for name in os.listdir(VIDEOS) if name.endswith(".md")}


def ydl(**opts):
    return yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, **opts})


def pick(recent):
    seen = used()
    with ydl(extract_flat=True, playlistend=recent * 3) as y:
        for h in handles():
            try:
                info = y.extract_info(f"https://www.youtube.com/@{h}/videos", download=False)
            except yt_dlp.utils.DownloadError as e:
                print(f"@{h}: couldn't list videos ({e})", file=sys.stderr)
                continue
            fresh = [e for e in info.get("entries") or []
                     if e.get("id") not in seen
                     and MIN_SECONDS <= (e.get("duration") or 0) <= MAX_SECONDS][:recent]
            for e in fresh:
                print(f"@{h:<28} {e['id']}  {round(e['duration'] / 60):>3} min  {e.get('title', '')}")


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
    print(f"{os.path.relpath(path, ROOT)}  ({words} words)  {info.get('title', '')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick", help="list recent unused videos from each favorite channel")
    p.add_argument("--recent", type=int, default=3, help="videos per channel (default 3)")
    t = sub.add_parser("transcript", help="save a video's transcript for the deep dive")
    t.add_argument("video", help="video id or URL")
    args = ap.parse_args()
    if args.cmd == "pick":
        pick(args.recent)
    else:
        transcript(args.video)


if __name__ == "__main__":
    main()
