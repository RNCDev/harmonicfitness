"""A workout's web copy: the MP3 at a speech bitrate, in parts small enough to publish, and a player page.

Claude Code on the web has no folder that syncs to a phone, so a build there makes this copy instead:
mono, 48 kbps (about 360 KB a minute), in parts of at most 14 MB (about 38 minutes
each), named <name>.web-1.mp3, <name>.web-2.mp3, ..., and <name>.player.html, a page with one player
that plays the parts in order and a download link for each. The workout skill publishes the page as a
private artifact, with the parts beside it, and ./sweatcast backup commits the parts to the private repo.

    ./sweatcast build <draft> "<name>" --web     # anywhere; on by default in a Claude Code cloud session
"""
import glob
import html
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffmpeg as ffmpeg_tool  # noqa: E402
import errors  # noqa: E402
import fileio  # noqa: E402

MAX_BYTES = 14_000_000
BITRATE = "48k"
DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def _ffmpeg():
    exe = ffmpeg_tool.exe()
    if not exe:
        raise errors.RenderStopped(f"ffmpeg isn't here, so there's no web copy ({ffmpeg_tool.install_hint()}).")
    return exe


def duration(path):
    """The audio's length in seconds, from ffmpeg's own report (no ffprobe needed)."""
    try:
        out = subprocess.run([_ffmpeg(), "-hide_banner", "-i", path], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise errors.RenderStopped(f"Couldn't read the length of {path}: ffmpeg took over a minute.") from None
    m = DURATION_RE.search(out.stderr)
    if not m:
        raise errors.RenderStopped(f"Couldn't read the length of {path}.")
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def kbps(bitrate):
    return int(str(bitrate).rstrip("kK"))


def make(mp3, name, out_dir, max_bytes=MAX_BYTES, bitrate=BITRATE):
    """Re-encode `mp3` as mono at `bitrate`, split into equal parts under `max_bytes`. Returns the parts in order."""
    total = duration(mp3)
    per_second = kbps(bitrate) * 1000 / 8
    parts = max(1, math.ceil(total * per_second * 1.05 / max_bytes))   # 5% for the frames' overhead
    length = total / parts
    _remove_parts(out_dir, name)   # a rebuild in fewer parts leaves no stale part for the backup to commit
    out = []
    for i in range(parts):
        path = os.path.join(out_dir, f"{name}.web-{i + 1}.mp3")
        cmd = [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{i * length:.3f}", "-i", mp3]
        if i < parts - 1:
            cmd += ["-t", f"{length:.3f}"]
        cmd += ["-ac", "1", "-c:a", "libmp3lame", "-b:a", str(bitrate), path]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            _remove_parts(out_dir, name)
            raise errors.RenderStopped(f"Couldn't make the web copy: ffmpeg took over ten minutes on part {i + 1}.") from None
        if done.returncode:
            _remove_parts(out_dir, name)
            raise errors.RenderStopped(f"Couldn't make the web copy: {done.stderr.strip()[-300:]}")
        out.append(path)
    return out


def _remove_parts(out_dir, name):
    """Remove every <name>.web-<n>.mp3 in out_dir (a part set is made whole or not at all)."""
    pattern = os.path.join(glob.escape(out_dir), glob.escape(name) + ".web-*.mp3")
    for path in glob.glob(pattern):
        if re.fullmatch(r"\d+", os.path.basename(path)[len(name) + len(".web-"):-len(".mp3")]):
            os.remove(path)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root {{ --bg: #f7f5f0; --fg: #1d1c1a; --muted: #6b675f; --accent: #2f6f4f; --card: #ffffff; --line: #e3dfd6; }}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{ --bg: #151513; --fg: #ecebe6; --muted: #a29f96; --accent: #7cc5a0; --card: #1f1f1c; --line: #33322e; }}
}}
:root[data-theme="dark"] {{ --bg: #151513; --fg: #ecebe6; --muted: #a29f96; --accent: #7cc5a0; --card: #1f1f1c; --line: #33322e; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width: 560px; margin: 0 auto; padding: 32px 16px 48px; }}
h1 {{ font-size: 1.5rem; margin: 0 0 4px; }}
p {{ color: var(--muted); margin: 0 0 20px; }}
.card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 16px; }}
audio {{ width: 100%; }}
.now {{ font-size: .9rem; color: var(--muted); margin: 8px 0 0; }}
ul {{ list-style: none; padding: 0; margin: 20px 0 0; }}
li {{ margin: 6px 0; }}
a {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
<p>Press play, put the phone away, and follow the coach. {count}</p>
<div class="card">
<audio id="player" controls preload="metadata" src="{first}"></audio>
<div class="now" id="now"></div>
</div>
<ul>{links}</ul>
</main>
<script>
const parts = {parts};
const player = document.getElementById("player");
const now = document.getElementById("now");
let at = 0;
function show() {{ now.textContent = parts.length > 1 ? `Part ${{at + 1}} of ${{parts.length}}` : ""; }}
player.addEventListener("ended", () => {{
  if (at + 1 < parts.length) {{ at += 1; player.src = parts[at]; show(); player.play(); }}
}});
show();
</script>
</body>
</html>
"""


def page(name, parts, out_path):
    """Write the player page for `parts` (paths beside it) to `out_path`. Returns out_path."""
    # Each name as a link (a "#" or "?" in a workout's name would otherwise end the address early), and the
    # script's list with "<" escaped, so no name can close the script.
    names = [urllib.parse.quote(os.path.basename(p)) for p in parts]
    links = "".join(f'<li><a href="{html.escape(n)}" download>Download part {i + 1}</a></li>' if len(names) > 1
                    else f'<li><a href="{html.escape(n)}" download>Download the MP3</a></li>'
                    for i, n in enumerate(names))
    count = f"It's in {len(names)} parts, which play one after another." if len(names) > 1 else ""
    text = PAGE.format(title=html.escape(name), count=count, first=html.escape(names[0]), links=links,
                       parts=json.dumps(names).replace("<", "\\u003c"))
    fileio.atomic_write(out_path, text)
    return out_path
