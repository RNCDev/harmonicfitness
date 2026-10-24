"""The local voice models: list them, and adopt the ones already downloaded elsewhere.

They live in models/ at the repo root (git-ignored, and outside me/, since they aren't personal and
shouldn't go into the private backup), or wherever SWEATCAST_MODELS points; tools/paths.py points
Hugging Face's cache there for every download and load. models/ may be a symlink to a shared place.

`adopt` moves sweatcast's pinned models out of Hugging Face's usual cache (~/.cache/huggingface/hub)
rather than downloading them again. Only sweatcast's repos move. A cache with shared blobs keeps a
repo's files in the cache's own blobs/ folder, linked from the repo by relative paths; those blobs move
with the repo, so the links still resolve, and a blob another repo also uses is copied instead. On the
same disk a move is a rename, so it's instant.

    ./sweatcast models                       # each model folder and its size
    ./sweatcast models adopt --dry-run       # what would move from the old cache
    ./sweatcast models adopt [--from <hub>]  # move them into models/
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402


def pinned():
    """[(repo, revision)] for every model sweatcast renders or designs with."""
    import voices
    out = list(voices.LOCAL_MODELS.values())
    for extras in voices.ENGINE_EXTRAS.values():
        out += extras
    out.append(voices.VOICE_DESIGN)
    return list(dict.fromkeys(out))


def folder(hub, repo):
    return os.path.join(hub, "models--" + repo.replace("/", "--"))


def complete(hub, repo, revision):
    """True when every file of the revision's snapshot is there and readable (its links resolve)."""
    snap = os.path.join(folder(hub, repo), "snapshots", revision)
    if not os.path.isdir(snap):
        return False
    files = [os.path.join(r, f) for r, _, fs in os.walk(snap) for f in fs]
    return bool(files) and all(os.path.isfile(f) for f in files)


def size(path):
    """Bytes of every file under `path`, a linked file counted once wherever it really lives."""
    seen, total = set(), 0
    for r, _, fs in os.walk(path):
        for f in fs:
            real = os.path.realpath(os.path.join(r, f))
            if real in seen or not os.path.isfile(real):
                continue
            seen.add(real)
            total += os.path.getsize(real)
    return total


def _links(top):
    """{symlink path: the path it resolves to} under `top`."""
    out = {}
    for r, dirs, fs in os.walk(top):
        for f in fs + dirs:
            p = os.path.join(r, f)
            if os.path.islink(p):
                out[p] = os.path.realpath(p)
    return out


def _move(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(src, dst)


def adopt(src=None, dst=None, dry_run=False):
    """Move sweatcast's models from the old cache `src` into `dst`. Returns [(repo, revision)] moved (or that
    would move, with dry_run). A repo already complete in `dst` is left where it is."""
    src = os.path.realpath(src or paths.OLD_HF_HUB_CACHE)
    dst = dst or paths.MODELS
    if not os.path.isdir(src) or os.path.realpath(dst) == src:
        return []
    ours = [(repo, rev) for repo, rev in pinned()
            if os.path.isdir(folder(src, repo)) and not complete(dst, repo, rev)]
    if dry_run or not ours:
        return ours
    moving = {os.path.realpath(folder(src, repo)) for repo, _ in ours}
    # Blobs other repos in the old cache link to stay readable there: those are copied, not moved.
    others = set()
    for d in os.listdir(src):
        top = os.path.join(src, d)
        if d.startswith("models--") and os.path.realpath(top) not in moving:
            others.update(_links(top).values())
    os.makedirs(dst, exist_ok=True)
    for marker in ("CACHEDIR.TAG",):
        if os.path.exists(os.path.join(src, marker)) and not os.path.exists(os.path.join(dst, marker)):
            shutil.copy2(os.path.join(src, marker), os.path.join(dst, marker))
    for repo, _ in ours:
        top = folder(src, repo)
        shared = sorted({t for t in _links(top).values() if not t.startswith(os.path.realpath(top) + os.sep)
                         and t.startswith(src + os.sep) and os.path.isfile(t)})
        for blob in shared:
            rel = os.path.relpath(blob, src)
            target = os.path.join(dst, rel)
            if os.path.exists(target):
                continue
            if blob in others:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(blob, target)
            else:
                _move(blob, target)
                for side in (".refs", ".lock"):
                    if os.path.exists(blob + side):
                        _move(blob + side, target + side)
        marker = os.path.join(src, "blobs", ".huggingface-shared-blobs")
        if shared and os.path.exists(marker) and not os.path.exists(os.path.join(dst, "blobs", os.path.basename(marker))):
            os.makedirs(os.path.join(dst, "blobs"), exist_ok=True)
            shutil.copy2(marker, os.path.join(dst, "blobs", os.path.basename(marker)))
        target = folder(dst, repo)
        if os.path.exists(target):
            shutil.rmtree(target)   # an incomplete copy; the old one is whole
        _move(top, target)
    return ours


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast models", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("adopt", help="move sweatcast's models from Hugging Face's usual cache into models/")
    a.add_argument("--from", dest="src", help=f"the old cache (default: {paths.OLD_HF_HUB_CACHE})")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--quiet", action="store_true", help="say nothing when there's nothing to adopt")
    args = ap.parse_args(argv)
    if args.cmd == "adopt":
        src = args.src or paths.OLD_HF_HUB_CACHE
        found = adopt(src, dry_run=True)
        if not found:
            if not args.quiet:
                print(f"Nothing to adopt from {src}.")
            return cli.OK
        gb = sum(size(folder(src, r)) for r, _ in found) / 1e9
        names = ", ".join(r for r, _ in found)
        if args.dry_run:
            print(f"Found sweatcast's models in {src} ({names}), linked to about {gb:.1f} GB of files there. "
                  f"./sweatcast models adopt moves them into {show(paths.MODELS)} instead of downloading them again.")
            return cli.OK
        moved = adopt(src)
        for repo, rev in moved:
            ok = complete(paths.MODELS, repo, rev)
            print(f"  {repo}: " + ("moved, and every file reads" if ok else "moved, but some files are missing"))
        return cli.OK if all(complete(paths.MODELS, r, v) for r, v in moved) else cli.ISSUES
    where = paths.MODELS
    print(f"Models in {show(where)}" + (f" (a link to {os.path.realpath(where)})" if os.path.islink(where) else ""))
    if not os.path.isdir(where):
        print("  none yet")
        return cli.OK
    for repo, rev in pinned():
        if os.path.isdir(folder(where, repo)):
            state = "complete" if complete(where, repo, rev) else "partial"
            print(f"  {repo}: {state}")
    print(f"  {size(where) / 1e9:.1f} GB in all")
    return cli.OK


if __name__ == "__main__":
    sys.exit(main())
