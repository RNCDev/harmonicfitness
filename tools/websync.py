"""Keep me/ on this computer in step with the listener's files on the web app (./harmonicfitness sync).

Signs in as the listener with HARMONIC_USERNAME and HARMONIC_PASSWORD (the environment or me/.env; HARMONIC_URL
names the app), as `pull` does, then compares three things for every file: what this computer holds now, what
the site holds now, and what both held at the last sync (me/web/sync-state.json, this computer's own record):

  - changed here only        sent to the site (a new file, an edit or a delete)
  - changed on the site only written here
  - changed in both          a conflict: this computer's copy stays, the site's is saved beside it in
                             me/web/conflicts/<date>-<time>/, and the next sync sends this computer's copy
                             (merge what you want from the site's first); --prefer web takes the site's
                             instead, --prefer local sends this computer's now

The first sync has no record, so a file both sides hold with different content is a conflict, and nothing is
deleted. Only the files the site keeps are synced: never .env, MP3s (each web coach's sample.mp3 excepted),
WAVs, the clip cache, render logs, lock files, auditions in progress, backups, git, or me/web/ itself. The
password goes to the app and nowhere else.

    ./harmonicfitness sync
    ./harmonicfitness sync --dry-run
    ./harmonicfitness sync --prefer web
"""
import base64
import datetime
import fnmatch
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import fileio  # noqa: E402
import keys  # noqa: E402
import paths  # noqa: E402
import webpull  # noqa: E402

# What the site never keeps (web/webapp/folder.py's SKIP, which test_websync holds in step), and what is this
# computer's alone: auditions in progress, backups, git, me/web/ (pulls, conflicts and this record), and the backup's
# note of which GitHub remote this computer confirmed private (tools/backup.py).
SKIP = (
    ".env", ".env.*", "*.env", "*.lock", "workouts/.audio-cache/",
    "*.mp3", "*.wav", "*.log", "*.log.1", ".gitignore", ".DS_Store", ".cache/",
)
LOCAL_ONLY = ("web/", "coaches/.auditions/", ".git/", ".backup-*", "*.bundle", "workouts/.logs/backup-remote.json")
# but a web coach's sample, which the site keeps for its Coaches page (web/webapp/folder.py's COACH_SAMPLE)
COACH_SAMPLE = re.compile(r"coaches/[^./][^/]*/sample\.mp3")
STATE = os.path.join("web", "sync-state.json")
BATCH = 200                 # files a request sends or asks for
BATCH_BYTES = 8_000_000     # and bytes a request sends, before base64


def skipped(rel):
    """Whether a path (relative to me/, with /) is never synced."""
    if COACH_SAMPLE.fullmatch(rel):
        return False
    parts = rel.split("/")
    for pat in SKIP + LOCAL_ONLY:
        if pat.endswith("/"):
            prefix = pat.split("/")[:-1]
            if parts[:len(prefix)] == prefix and len(parts) > len(prefix):
                return True
        elif "/" in pat:
            if fnmatch.fnmatchcase(rel, pat):
                return True
        elif fnmatch.fnmatchcase(parts[-1], pat) or fnmatch.fnmatchcase(parts[0], pat):
            return True
    return False


def sha(data):
    return hashlib.sha256(data).hexdigest()


def local_files(home):
    """{path: sha256} of every file here that syncs; links are never followed."""
    out = {}
    for base, dirs, names in os.walk(home, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(base, d)))
        for name in sorted(names):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, home).replace(os.sep, "/")
            if os.path.islink(full) or not os.path.isfile(full) or skipped(rel):
                continue
            with open(full, "rb") as f:
                out[rel] = sha(f.read())
    return out


def _read(home, rel):
    with open(os.path.join(home, *rel.split("/")), "rb") as f:
        return f.read()


def syncable(rel):
    """Whether a path the web app names may be written here: a plain relative path (no empty, `.` or `..` part, no
    backslash or NUL), not one that never syncs, read case-blind too (macOS and Windows fold case, so `.ENV` is
    `.env`)."""
    if not isinstance(rel, str) or not rel or "\\" in rel or "\x00" in rel or rel.startswith("/"):
        return False
    if any(part in ("", ".", "..") for part in rel.split("/")):
        return False
    return not skipped(rel) and not skipped(rel.lower())


def _check_named(rels):
    """Refuse the whole sync when the web app names a file it never keeps: nothing is written then."""
    bad = sorted(r for r in rels if not syncable(r))
    if bad:
        raise errors.HarmonicFitnessError("The web app named a file it never keeps, so nothing was synced: "
                                          + ", ".join(repr(r)[:80] for r in bad[:5]))


def _inside(home, rel):
    """The path under home, with every folder on the way resolved (a link can't send a write elsewhere)."""
    root = os.path.realpath(home)
    target = os.path.join(os.path.realpath(os.path.join(home, *rel.split("/")[:-1])), rel.split("/")[-1])
    if not target.startswith(root + os.sep):
        raise errors.HarmonicFitnessError(f"The web app named a file outside me/: {rel!r}")
    return target


def load_state(home, account_key):
    """The last sync's record, {path: {"version", "sha"}}; empty when there is none, or it was for another
    account or app (a first sync, then)."""
    try:
        with open(os.path.join(home, STATE), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("account") != account_key or not isinstance(data.get("files"), dict):
        return {}
    return {p: e for p, e in data["files"].items()
            if isinstance(e, dict) and isinstance(e.get("version"), int) and isinstance(e.get("sha"), str)}


def save_state(home, account_key, state):
    fileio.atomic_write(os.path.join(home, STATE), json.dumps(
        {"account": account_key, "synced_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
         "files": dict(sorted(state.items()))}, indent=1) + "\n")


def plan(local, remote, state, prefer=None):
    """What to do with each path, from this computer's {path: sha}, the site's {path: (version, sha)} and the
    last sync's {path: {"version", "sha"}}: {"push": [...], "pull": [...], "delete_here": [...],
    "delete_there": [...], "conflict": [...], "same": [...]}. Pure: it reads and writes nothing."""
    out = {k: [] for k in ("push", "pull", "delete_here", "delete_there", "conflict", "same")}
    for path in sorted(set(local) | set(remote) | set(state)):
        here, there, was = local.get(path), remote.get(path), state.get(path)
        there_sha = there[1] if there else None
        if here == there_sha:
            if here is not None:
                out["same"].append(path)
            continue
        changed_here = here != (was["sha"] if was else None)
        changed_there = (there[0] if there else None) != (was["version"] if was else None)
        if was is None and here is not None and there is not None:
            changed_here = changed_there = True   # a first sync: both hold it, differently
        if changed_here and not changed_there:
            out["push" if here is not None else "delete_there"].append(path)
        elif changed_there and not changed_here:
            out["pull" if there is not None else "delete_here"].append(path)
        elif prefer == "local":
            out["push" if here is not None else "delete_there"].append(path)
        elif prefer == "web":
            out["pull" if there is not None else "delete_here"].append(path)
        elif here is None or there is None:   # one side edited it, the other deleted it: keep the copy
            out["push" if here is not None else "pull"].append(path)
        else:
            out["conflict"].append(path)
    return out


class Site:
    """The web app's sync calls on a signed-in webpull.App."""

    def __init__(self, app):
        self.app = app

    def _post(self, path, body):
        status, _, data = self.app._request("POST", path, body)
        if status != 200:
            detail = self.app._detail(data)
            raise errors.HarmonicFitnessError(f"The web app answered HTTP {status} for {path}"
                                              + (f": {detail}" if detail else "."))
        return json.loads(data)

    def listing(self):
        _, data = self.app.get("/api/sync")
        return {f["path"]: (f["version"], f["sha256"]) for f in json.loads(data)["files"]}

    def read(self, paths_):
        out = {}
        for i in range(0, len(paths_), BATCH):
            for f in self._post("/api/sync/read", {"paths": paths_[i:i + BATCH]})["files"]:
                out[f["path"]] = (f["version"], base64.b64decode(f["body"]))
        return out

    def write(self, changes):
        """[(path, base, bytes or None)] -> (written {path: version}, conflicts, refused)."""
        written, conflicts, refused = {}, [], []
        batch, size = [], 0

        def send():
            got = self._post("/api/sync/write", {"changes": batch})
            written.update(got["written"])
            conflicts.extend(got["conflicts"])
            refused.extend(got["refused"])
        for path, base, data in changes:
            item = {"path": path, "base": base, "body": None if data is None else base64.b64encode(data).decode("ascii")}
            if batch and (len(batch) >= BATCH or size + len(data or b"") > BATCH_BYTES):
                send()
                batch, size = [], 0
            batch.append(item)
            size += len(data or b"")
        if batch:
            send()
        return written, conflicts, refused


def sync(account, home=None, prefer=None, dry_run=False, site=None, now=None):
    """Sign in, sync, sign out; what happened, as a dict of path lists (and the conflicts' folder)."""
    home = home or paths.HOME
    username, password = account.get("HARMONIC_USERNAME"), account.get("HARMONIC_PASSWORD")
    missing = [v for v, x in (("HARMONIC_USERNAME", username), ("HARMONIC_PASSWORD", password)) if not x]
    if missing:
        raise errors.UsageError(f"Add {' and '.join(missing)} to me/.env (./harmonicfitness keys open), "
                                "one NAME=value per line, to sign in to the web app.")
    url = webpull.base_url(account.get("HARMONIC_URL"))
    account_key = f"{username}@{url}"
    app = None
    if site is None:
        app = webpull.App(url)
        app.sign_in(username, password)
        site = Site(app)
    try:
        state = load_state(home, account_key)
        local = local_files(home)
        remote = site.listing()
        _check_named(remote)
        todo = plan(local, remote, state, prefer)
        report = {k: list(v) for k, v in todo.items()}
        report.update(conflict_folder=None, refused=[], lost=[])
        if dry_run:
            return report
        new_state = {p: {"version": remote[p][0], "sha": local[p]} for p in todo["same"]}
        for p in todo["conflict"]:   # the next sync sends this computer's copy: it's as if the site's was seen
            new_state[p] = {"version": remote[p][0], "sha": (state.get(p) or {}).get("sha", "")}
        fetched = site.read(todo["pull"] + todo["conflict"])
        _check_named(fetched)
        for p in todo["pull"]:
            if p not in fetched:   # gone from the site since the listing: the next sync sees it
                continue
            version, data = fetched[p]
            fileio.atomic_write(_inside(home, p), data)
            new_state[p] = {"version": version, "sha": sha(data)}
        for p in todo["delete_here"]:
            try:
                os.remove(_inside(home, p))
            except FileNotFoundError:
                pass
        if todo["conflict"]:
            stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d-%H%M%S")
            aside = os.path.join(home, "web", "conflicts", stamp)
            for p in todo["conflict"]:
                if p in fetched:
                    fileio.atomic_write(_inside(aside, p), fetched[p][1])
            report["conflict_folder"] = aside
        changes = [(p, remote[p][0] if p in remote else None, _read(home, p)) for p in todo["push"]]
        changes += [(p, remote[p][0], None) for p in todo["delete_there"] if p in remote]
        written, conflicts, refused = site.write(changes)
        for p, version in written.items():
            if version is not None:
                new_state[p] = {"version": version, "sha": local[p]}
        report["refused"] = sorted(refused)
        report["lost"] = sorted(conflicts)   # changed on the site during this sync: the next one sees it
        for p in conflicts:
            if p in state:
                new_state[p] = state[p]
        for p in refused:
            new_state.pop(p, None)
        save_state(home, account_key, new_state)
        _ignore_web(home)
        return report
    finally:
        if app is not None:
            app.sign_out()


def _ignore_web(home):
    """me/web/ is this computer's own: add it to me/.gitignore when that lacks it, so a backup never commits it."""
    import migrate
    try:
        migrate.update_gitignore(home, migrate.GITIGNORE_ADD_WEB)
    except OSError:
        pass


def main(argv=None):
    import cli
    ap = cli.ArgumentParser(prog="harmonicfitness sync", description=__doc__,
                            formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("--prefer", choices=("local", "web"),
                    help="settle a file changed on both sides this way, rather than saving the site's copy aside")
    ap.add_argument("--dry-run", action="store_true", help="say what would change; change nothing")
    args = ap.parse_args(argv)
    got = sync(keys.web_account(), prefer=args.prefer, dry_run=args.dry_run)
    verb = "would be" if args.dry_run else ""
    rows = (("push", "sent to the web app"), ("delete_there", "deleted on the web app"),
            ("pull", "written here from the web app"), ("delete_here", "deleted here"))
    said = False
    for key, what in rows:
        if got[key]:
            said = True
            print(f"{len(got[key])} {verb + ' ' if verb else ''}{what}:")
            for p in got[key]:
                print(f"  {p}")
    if got["conflict"]:
        said = True
        print(f"{len(got['conflict'])} changed on both sides" + (":" if args.dry_run else
              f"; this computer's copy kept, the web app's saved in {paths.show(got['conflict_folder'])}. "
              "Merge what you want from it; the next sync sends this computer's copy:"))
        for p in got["conflict"]:
            print(f"  {p}")
    if got["refused"]:
        print("The web app refused (it doesn't keep these, or they're too large): " + ", ".join(got["refused"]))
    if got["lost"]:
        print("Changed on the web app during this sync, left for the next one: " + ", ".join(got["lost"]))
    if not said:
        print(f"In step: {len(got['same'])} files the same here and on the web app.")
    return errors.OK


if __name__ == "__main__":
    import cli
    sys.exit(cli.run(main))
