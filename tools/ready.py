"""The ready-made workouts: five complete thirty-minute sessions (full body, strength, cardio, mobility, core),
written and recorded once on ElevenLabs's stock voices and kept on the app's media bucket, so a new listener can
train before their own coach is ready: on a computer while the local voice downloads, on the web before any key.

    ./harmonicfitness ready                       # the five, and which are on this computer
    ./harmonicfitness ready file ready-core       # a copy here (me/workouts/.ready/), fetched once and checked;
                                                  # --deliver also copies it to the delivery folders
    ./harmonicfitness ready publish <slug> <mp3>  # maintainer: stage a rendered workout in docs/demos/ready/
    ./harmonicfitness ready upload                # maintainer: the staged ones to the bucket, then knowledge/ready.json
                                                  # and web/client/src/ready.json (the bucket's keys in the shell)

docs/demos/ready.toml is the plan (how each is built, as a demo is: `demos home` and `demos run` take their slugs).
knowledge/ready.json is what's published: each one's title, coach, kind, bytes and SHA-256, and the bucket's address,
read only here. A ready-made workout is made for no one, so it isn't screened against anyone's limits: its opening
says so, and the list says so beside it.
"""
import hashlib
import json
import os
import sys
import tomllib
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402

WARNING = "Made for no one in particular, so not adapted to any injury: skip or ease off anything that hurts."


def plan_path():
    return os.path.join(paths.DEMOS, "ready.toml")


def plan(path=None):
    """docs/demos/ready.toml, as a dict; ContextError when it's missing or isn't TOML."""
    path = path or plan_path()
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise errors.ContextError(f"No ready-made plan at {show(path)}.") from None
    except tomllib.TOMLDecodeError as e:
        raise errors.ContextError(f"{show(path)} isn't TOML: {e}") from None


def planned(slug, p=None):
    """The [[workout]] named `slug` in the plan, shaped as a demo is for `demos home` and `demos run`, or None."""
    p = p if p is not None else plan()
    for w in p.get("workout", []):
        if w.get("slug") == slug:
            return dict(w, minutes=w.get("minutes", p.get("minutes")))
    return None


def list_path():
    return os.path.join(paths.ROOT, "knowledge", "ready.json")


def published(path=None):
    """knowledge/ready.json: {"version", "url", "workouts": [...]}, empty until the set is uploaded."""
    try:
        data = fileio.read_json(path or list_path())
    except FileNotFoundError:
        return {"version": 0, "url": "", "workouts": []}
    return {"version": int(data.get("version") or 0), "url": str(data.get("url") or ""),
            "workouts": [w for w in data.get("workouts") or [] if isinstance(w, dict) and w.get("slug")]}


def key(version, slug):
    return f"ready/v{version}/{slug}.mp3"


def find(slug, listing=None):
    listing = listing or published()
    for w in listing["workouts"]:
        if w["slug"] == slug:
            return w
    names = ", ".join(w["slug"] for w in listing["workouts"]) or "none published yet"
    raise errors.UsageError(f"No ready-made workout \"{slug}\" (there are: {names}).")


def url(w, listing=None):
    """A ready-made workout's public address: the bucket's (or HARMONICFITNESS_MEDIA_URL, as the samples')."""
    import media
    listing = listing or published()
    return f"{media.base_url({'url': listing['url'], 'samples': {}})}/{key(listing['version'], w['slug'])}"


def local_dir():
    """Where a listener's copies are kept: me/workouts/.ready/ (a dot folder: not a workout of theirs)."""
    return os.path.join(paths.WORKOUTS, ".ready")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file(slug, listing=None, opener=None):
    """A ready-made workout as a file here, named by its title ("Ready-made 30 min Full body with Coach Bea.mp3"):
    fetched once from the bucket and checked against the list. UsageError for one that isn't listed;
    HarmonicFitnessError when the fetch fails or the file doesn't match."""
    listing = listing or published()
    w = find(slug, listing)
    out = os.path.join(local_dir(), name_of(w) + ".mp3")
    if os.path.isfile(out) and _sha256(out) == w.get("sha256"):
        return out
    address = url(w, listing)
    try:
        with (opener or urllib.request.urlopen)(address, timeout=120) as r:
            body = r.read()
    except (urllib.error.URLError, OSError) as e:
        raise errors.HarmonicFitnessError(f"The ready-made {w.get('title', slug)} couldn't be fetched from {address}: "
                                          f"{e}.") from None
    if hashlib.sha256(body).hexdigest() != w.get("sha256"):
        raise errors.HarmonicFitnessError(f"The ready-made {w.get('title', slug)} at {address} doesn't match "
                                          "knowledge/ready.json.")
    fileio.atomic_write(out, body)
    return out


def name_of(w):
    return f"Ready-made {w.get('minutes', 30)} min {w.get('title', w['slug'])} with {w.get('coach', 'your coach')}"


def deliver(path, say=print):
    """Copy a fetched one to every delivery folder on this computer (me/settings.toml's deliver_to); the local copy
    stays, so it isn't fetched again. Returns the folders it reached."""
    import context
    _, folders = context.delivery_folders(context.profile())
    done = []
    for dest in folders:
        target = os.path.join(dest, os.path.basename(path))
        try:
            fileio.atomic_copy(path, target)
            done.append(dest)
            say(f"Copied to {target}")
        except OSError as e:
            say(f"Couldn't copy to {dest}: {e.strerror or e}")
    if not folders:
        say("No delivery folder on this computer (me/settings.toml's deliver_to): the MP3 stays where it is.")
    return done


# ---- maintainer: publish and upload ------------------------------------------------------------------------------

def staged_dir():
    """Where rendered ones wait for the bucket: docs/demos/ready/ (git-ignored)."""
    return os.path.join(paths.DEMOS, "ready")


def publish(slug, mp3):
    """Stage a rendered ready-made workout for the bucket; returns where it went."""
    if planned(slug) is None:
        raise errors.UsageError(f"No ready-made workout \"{slug}\" in docs/demos/ready.toml.")
    if not mp3.lower().endswith(".mp3") or not os.path.isfile(mp3):
        raise errors.UsageError(f"No MP3 at {mp3}.")
    dst = os.path.join(staged_dir(), slug + ".mp3")
    fileio.atomic_copy(mp3, dst)
    return dst


def entry(w, p, path):
    """One workout as knowledge/ready.json lists it."""
    return {"slug": w["slug"], "order": w.get("order", 0), "title": w.get("title", ""), "kind": w.get("kind", ""),
            "coach": w.get("coach", ""), "minutes": w.get("minutes", p.get("minutes", 30)), "about": w.get("about", ""),
            "bytes": os.path.getsize(path), "sha256": _sha256(path)}


def web_file():
    """The copy the web client builds with: web/client/src/ready.json."""
    return os.path.join(paths.ROOT, "web", "client", "src", "ready.json")


def web_body(listing):
    """The web client's copy: each workout's card and its public address; no hashes."""
    return {"version": listing["version"], "warning": WARNING,
            "workouts": [{k: w.get(k) for k in ("slug", "order", "title", "kind", "coach", "minutes", "about")}
                         | {"audio": url(w, listing)} for w in sorted(listing["workouts"], key=lambda w: w["order"])]}


def write_lists(listing):
    fileio.atomic_write(list_path(), json.dumps(listing, indent=1, ensure_ascii=False) + "\n")
    fileio.atomic_write(web_file(), json.dumps(web_body(listing), indent=1, ensure_ascii=False) + "\n")


def upload(put=None):
    """Every staged workout to the media bucket as ready/v<version>/<slug>.mp3, then knowledge/ready.json and
    web/client/src/ready.json listing them. All five must be staged: the set is published whole. Returns
    [(key, url)]."""
    import bucket
    put = put or bucket.put
    p = plan()
    version = int(p.get("version", 1))
    missing = [w["slug"] for w in p.get("workout", []) if not os.path.isfile(os.path.join(staged_dir(), w["slug"] + ".mp3"))]
    if missing:
        raise errors.HarmonicFitnessError(f"Not staged yet in {show(staged_dir())}: {', '.join(missing)} "
                                          "(ready publish <slug> <mp3> first). The set is published whole.")
    done, workouts = [], []
    for w in sorted(p.get("workout", []), key=lambda w: w.get("order", 0)):
        path = os.path.join(staged_dir(), w["slug"] + ".mp3")
        with open(path, "rb") as f:
            done.append((key(version, w["slug"]), put(key(version, w["slug"]), f.read(), "audio/mpeg")))
        workouts.append(entry(w, p, path))
    write_lists({"version": version, "url": bucket.public_url("", p.get("bucket", "")).rstrip("/"),
                 "workouts": workouts})
    return done


def status(listing=None):
    """One line a workout: its title, coach and length, and whether it's on this computer."""
    listing = listing or published()
    if not listing["workouts"]:
        return ["No ready-made workouts are published yet."]
    lines = []
    for w in sorted(listing["workouts"], key=lambda w: w["order"]):
        here = os.path.isfile(os.path.join(local_dir(), name_of(w) + ".mp3"))
        lines.append(f"{w['slug']:<16} {w.get('minutes', 30)} min, {w.get('title', '')} with {w.get('coach', '')}"
                     f"{' (here)' if here else ''}: {w.get('about', '')}")
    lines.append(WARNING)
    return lines


def main(argv=None):
    import cli
    argv = sys.argv[1:] if argv is None else argv
    ap = cli.ArgumentParser(prog="harmonicfitness ready",
                            description="The ready-made workouts: five thirty-minute sessions recorded once, to "
                                        "play while your own coach gets ready. Not adapted to any injury.")
    ap.add_argument("--json", action="store_true", help="the list as one object")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="the five, and which are on this computer (the default)")
    f = sub.add_parser("file", help="a copy on this computer, fetched once and checked; prints its path")
    f.add_argument("slug")
    f.add_argument("--deliver", action="store_true", help="also copy it to the delivery folders")
    pub = sub.add_parser("publish", help="maintainer: stage a rendered one in docs/demos/ready/")
    pub.add_argument("slug")
    pub.add_argument("mp3")
    sub.add_parser("upload", help="maintainer: the staged five to the media bucket, then the lists (the bucket's keys in the shell)")
    a = ap.parse_args(argv)
    if a.cmd in (None, "list"):
        if a.json:
            listing = published()
            print(json.dumps({"warning": WARNING, "workouts": listing["workouts"]}, indent=1))
        else:
            print("\n".join(status()))
        return 0
    if a.cmd == "file":
        path = file(a.slug)
        print(path)
        if a.deliver:
            deliver(path, say=lambda s: print(s, file=sys.stderr))
        return 0
    if a.cmd == "publish":
        print(f"Staged {show(publish(a.slug, a.mp3))}.")
        return 0
    if a.cmd == "upload":
        for k, u in upload():
            print(f"{k}: {u}")
        print(f"Wrote {show(list_path())} and {show(web_file())}.")
        return 0
    raise cli.Usage(f"ready {a.cmd}: unknown")
