#!/usr/bin/env python3
"""The rendered-clip cache in me/workouts/.audio-cache: its size, and pruning old clips.

Each paragraph a render voices is cached as raw audio (about 2.9 MB a minute of
speech), so editing a draft re-renders only what changed. render.py marks a clip as
used whenever a build reads it, so `prune` removes the clips no build has touched in
a while. The voices' measured pace (voice-pace.json) is never touched.

    python3 tools/cache.py                  # how big the cache is
    python3 tools/cache.py prune            # remove clips unused for 45 days
    python3 tools/cache.py prune --days 0   # remove every clip (the next build renders all)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
from paths import CACHE, show  # noqa: E402

CLIP_EXTS = (".pcm", ".pcm.part")


def clips(folder=None):
    folder = folder or CACHE
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(CLIP_EXTS)]


def size(folder=None):
    """(clip count, bytes)."""
    found = clips(folder)
    return len(found), sum(os.path.getsize(p) for p in found)


def prune(days, folder=None, now=None):
    """Remove clips not used in `days` days. Returns (clips removed, bytes freed)."""
    cutoff = (now or time.time()) - days * 86400
    removed = freed = 0
    for path in clips(folder):
        st = os.stat(path)
        if st.st_mtime <= cutoff:
            os.remove(path)
            removed += 1
            freed += st.st_size
    return removed, freed


def main(argv=None):
    ap = cli.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("prune", help="remove clips no build has used recently")
    p.add_argument("--days", type=float, default=45, help="unused for this many days (default 45)")
    args = ap.parse_args(argv)
    if args.cmd == "prune":
        removed, freed = prune(args.days)
        n, total = size()
        print(f"Removed {removed} clips ({freed / 1e6:.0f} MB); {n} left ({total / 1e6:.0f} MB) in {show(CACHE)}.")
    else:
        n, total = size()
        print(f"{n} clips, {total / 1e6:.0f} MB in {show(CACHE)}.")
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
