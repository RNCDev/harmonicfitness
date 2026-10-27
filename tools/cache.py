#!/usr/bin/env python3
"""The rendered-clip cache in me/workouts/.audio-cache: its size, and pruning old clips.

Each paragraph a render voices is cached as raw audio (about 2.9 MB a minute of
speech), so editing a draft re-renders only what changed. render.py marks a clip as
used whenever a build reads it, so `prune` removes the clips no build has touched in
a while. The voices' measured pace (voice-pace.json) is never touched.

`prune --logs-older N` removes the builds' render logs in me/workouts/.logs (<name>.log and its
<name>.log.1) not written in N days; builds.jsonl and told.jsonl, the record of what was built,
paid for and told, are never touched. Given alone it prunes only the logs; with --days, both.

    ./sweatcast cache                         # how big the cache is
    ./sweatcast cache prune                   # remove clips unused for 45 days
    ./sweatcast cache prune --days 0          # remove every clip (the next build renders all)
    ./sweatcast cache prune --logs-older 60   # remove render logs not written in 60 days, no clips
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402

CLIP_EXTS = (".pcm", ".pcm.part")
CHECK_EXT = ".check.json"   # a clip's verdict from the take checker (render.check_takes), pruned with it
LOG_EXTS = (".log", ".log.1")   # a build's render log and its one rotated copy (build.py)
DEFAULT_DAYS = 45


def clips(folder=None):
    folder = folder or paths.CACHE
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(CLIP_EXTS)]


def size(folder=None):
    """(clip count, bytes)."""
    found = clips(folder)
    return len(found), sum(os.path.getsize(p) for p in found)


def prune(days, folder=None, now=None):
    """Remove clips not used in `days` days. Returns (clips removed, bytes freed)."""
    folder = folder or paths.CACHE
    cutoff = (now or time.time()) - days * 86400
    removed = freed = 0
    with locks.render_lock(folder, wait_message=False):   # never under a render's feet
        for path in clips(folder):
            st = os.stat(path)
            if st.st_mtime <= cutoff:
                os.remove(path)
                removed += 1
                freed += st.st_size
        for name in os.listdir(folder) if os.path.isdir(folder) else []:   # verdicts whose clip is gone
            if name.endswith(CHECK_EXT) and not os.path.exists(os.path.join(folder, name[:-len(CHECK_EXT)] + ".pcm")):
                path = os.path.join(folder, name)
                freed += os.path.getsize(path)
                os.remove(path)
    return removed, freed


def prune_logs(days, folder=None, now=None):
    """Remove render logs (*.log, *.log.1) not written in `days` days. Returns (logs removed, bytes freed).
    Only those two endings are touched: builds.jsonl, its lock and anything else in the folder stay."""
    folder = folder or paths.LOGS
    cutoff = (now or time.time()) - days * 86400
    removed = freed = 0
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        path = os.path.join(folder, name)
        if not name.endswith(LOG_EXTS) or not os.path.isfile(path):
            continue
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
    p.add_argument("--days", type=cli.non_negative_float, default=None,
                   help=f"clips unused for this many days (default {DEFAULT_DAYS}, unless only --logs-older is given)")
    p.add_argument("--logs-older", type=cli.non_negative_float, default=None, metavar="DAYS",
                   help="also remove render logs (.logs/*.log, *.log.1) not written in this many days; "
                        "builds.jsonl and told.jsonl are never touched. Alone, it prunes no clips")
    args = ap.parse_args(argv)
    if args.cmd == "prune":
        if args.days is not None or args.logs_older is None:
            removed, freed = prune(DEFAULT_DAYS if args.days is None else args.days)
            n, total = size()
            print(f"Removed {removed} clips ({freed / 1e6:.0f} MB); {n} left ({total / 1e6:.0f} MB) in {paths.show(paths.CACHE)}.")
        if args.logs_older is not None:
            removed, freed = prune_logs(args.logs_older)
            print(f"Removed {removed} render logs ({freed / 1e6:.1f} MB) from {paths.show(paths.LOGS)}.")
    else:
        n, total = size()
        print(f"{n} clips, {total / 1e6:.0f} MB in {paths.show(paths.CACHE)}.")
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
