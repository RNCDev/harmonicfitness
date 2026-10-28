"""Move each stock local coach's shipped pace.json onto its current key (maintainer only; not a listener command).

  .venv/bin/python tools/coachmaker/rekey_pace.py [coach-andy-local ...]

A pace entry is keyed "<clip key>|<engine>|<model>" (voices._rate_key), and the clip key is personas.clip_key:
the clip, its words and pocket.safetensors. When that rule changes, or a coach's voice file is remade, its
measured pace is still right for the voice it was measured on, so this renames each entry onto the new key
instead of measuring again. With no folders named, every coaches/coach-*-local/."""
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.environ.setdefault("HARMONICFITNESS_HOME", "/nonexistent")
import fileio  # noqa: E402
import personas  # noqa: E402
import voices  # noqa: E402


def rekey(folder):
    """Rename every entry in `folder`'s pace.json onto the coach's current clip key. Returns how many moved."""
    p = personas.load(folder)
    key, _ = personas.clip_key(p)
    path = os.path.join(folder, "pace.json")
    data = voices._recorded(path, strict=True)
    out, moved = {}, 0
    for k, rec in data.items():
        old, _, rest = k.partition("|")
        if old != key:
            moved += 1
        new = f"{key}|{rest}"
        if new in out:
            raise SystemExit(f"{path}: two entries would share {new}; fix it by hand")
        out[new] = rec
    if moved:
        fileio.write_json(path, out)
    return moved


def main(args):
    folders = ([a if os.path.isdir(a) else os.path.join(ROOT, "coaches", a) for a in args]
               or sorted(glob.glob(os.path.join(ROOT, "coaches", "coach-*-local"))))
    for folder in folders:
        print(f"{os.path.basename(folder)}: {rekey(folder)} entr(ies) re-keyed")


if __name__ == "__main__":
    main(sys.argv[1:])
