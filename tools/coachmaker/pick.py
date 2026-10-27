"""Make a designed take a shipped coach's clip (maintainer only; not a listener command).

  .venv/Scripts/python tools/coachmaker/pick.py andy qwen3-101 [claire voxcpm-101 ...]

Copies .cache/design/takes/<coach>/<take>.wav to coaches/coach-<coach>-local/clip.wav, writes clip.txt (the
script, after checking the recognizer heard every word of it in that take), and records the designer, its
model revision, the seed and the exact description in coaches/roster.toml under [picks.<coach>], so the
clip can be made again.
"""
import json
import os
import re
import shutil
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
ROSTER = os.path.join(ROOT, "coaches", "roster.toml")
TAKES = os.path.join(ROOT, ".cache", "design", "takes")


def toml_str(s):
    return json.dumps(s, ensure_ascii=False)


def main(argv):
    if not argv or len(argv) % 2:
        raise SystemExit(__doc__)
    with open(ROSTER, "rb") as f:
        roster = tomllib.load(f)
    with open(os.path.join(TAKES, "takes.json"), encoding="utf-8") as f:
        takes = json.load(f)
    with open(ROSTER, encoding="utf-8") as f:
        text = f.read()
    for slug, take in zip(argv[::2], argv[1::2]):
        t = takes.get(f"{slug}/{take}")
        if not t:
            raise SystemExit(f"No take {slug}/{take} in {TAKES}/takes.json")
        if t.get("errors") or t.get("missed_cues") or t.get("problems"):
            raise SystemExit(f"{slug}/{take} doesn't say the script cleanly (heard: {t.get('heard')}); "
                             "write its clip.txt by hand from what was said.")
        folder = os.path.join(ROOT, "coaches", f"coach-{slug}-local")
        os.makedirs(folder, exist_ok=True)
        shutil.copyfile(t["wav"], os.path.join(folder, "clip.wav"))
        with open(os.path.join(folder, "clip.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write(t.get("text", roster["script"]) + "\n")
        block = (f"[picks.{slug}]\ndesigner = {toml_str(t['designer'])}\n"
                 f"repo = {toml_str(roster['designers'][t['designer']]['repo'])}\n"
                 f"revision = {toml_str(t['revision'])}\nseed = {t['seed']}\n"
                 f"seconds = {t['seconds']}\ndevice = {toml_str(t.get('device') or '')}\ntorch = {toml_str(t.get('torch') or '')}\ndescription = {toml_str(t['description'])}\n")
        text = re.sub(rf"\n\[picks\.{slug}\]\n(?:[^\[\n].*\n)*", "\n", text)   # a re-pick replaces the old one
        text = text.rstrip("\n") + "\n\n" + block
        print(f"{slug}: {take}, {t['seconds']} s -> {os.path.relpath(folder, ROOT)}")
    with open(ROSTER + ".part", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    tomllib.loads(text)
    os.replace(ROSTER + ".part", ROSTER)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
