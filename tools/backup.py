#!/usr/bin/env python3
"""Commit and push the context folder (me/) when it's its own private git repo.

me/ is ignored by the engine's git. Kept as its own private repo, it has a history and
a copy off this machine; this commits everything in it (its .gitignore leaves out the
clip cache and MP3s) and pushes to the repo's remote. The workout skill runs it last.

A context folder that isn't its own repo is skipped with a note (exit 0), and a remote
that GitHub reports as public is refused: me/ holds health details.

    ./sweatcast backup                                  # commit and push
    ./sweatcast backup -m "Workout 2026-10-22 Legs 30 min"
    ./sweatcast backup --no-push                        # commit only
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import paths  # noqa: E402
from paths import show  # noqa: E402

GITHUB = re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$")


PUSH_TIMEOUT = 300   # seconds a push may take before it's given up


def git(home, *args, timeout=None):
    # GIT_TERMINAL_PROMPT=0 and ssh's BatchMode: a push that needs a password or a passphrase fails with the
    # reason instead of waiting forever on a prompt nobody sees (an ssh command the listener set is kept)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    return subprocess.run(["git", *args], cwd=home, capture_output=True, text=True, env=env, timeout=timeout)


def _push(home, args):
    try:
        return git(home, *args, timeout=PUSH_TIMEOUT)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", f"no answer from the remote in {PUSH_TIMEOUT // 60} minutes")


KEY_FILE = re.compile(r"(^|\.)env(\.|$)")   # .env, .env.bak, keys.env, x.env.local


def own_repo(home):
    """True when `home` is the top of its own repo, not merely inside the engine's."""
    if not os.path.isdir(home):
        return False
    out = git(home, "rev-parse", "--show-toplevel")
    if out.returncode:
        return False
    return _same(out.stdout.strip()) == _same(home)


def _same(path):
    return os.path.normcase(os.path.realpath(path))


def github_slug(url):
    """'owner/repo' for a GitHub remote URL, else None."""
    m = GITHUB.search(url.strip())
    return m.group(1) if m else None


def visibility(slug):
    """GitHub's word for the repo's visibility (PUBLIC, PRIVATE, INTERNAL), or None when it can't be told.
    gh first; without it (Claude Code on the web), GitHub's API unauthenticated, which answers only for a
    public repo (a private one is a 404, which says nothing for sure)."""
    if shutil.which("gh"):
        try:
            out = subprocess.run(["gh", "repo", "view", slug, "--json", "visibility", "-q", ".visibility"],
                                 capture_output=True, text=True, timeout=20)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip().upper()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return _api_visibility(slug)


API = "https://api.github.com/repos/"


def _api_visibility(slug, api=None):
    import json
    import urllib.error
    import urllib.request
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "sweatcast-backup"}
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")   # Claude Code on the web, CI: an authenticated read sees a private repo
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    req = urllib.request.Request((api or API) + slug, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if data.get("private") is False:
        return "PUBLIC"
    return str(data.get("visibility") or "").upper() or None


def _memory_path(home):
    """Where this computer remembers which GitHub remote it confirmed private (under .logs/, which me/.gitignore
    leaves out of the backup itself)."""
    return os.path.join(home, "workouts", ".logs", "backup-remote.json")


def remembered_private(home):
    """The GitHub slug this computer confirmed private before (GitHub said so, or the listener did with
    --unverified), or None."""
    try:
        with open(_memory_path(home), encoding="utf-8") as f:
            data = json.load(f)
        return data.get("slug") if data.get("private") else None
    except (OSError, ValueError):
        return None


def remember_private(home, slug, how):
    import fileio
    fileio.atomic_write(_memory_path(home), json.dumps({"slug": slug, "private": True, "how": how,
                                                       "seen": time.strftime("%Y-%m-%d")}) + "\n")


def push_target(home):
    """(remote, git push arguments), or (None, None) when the repo has no remote."""
    up = git(home, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if up.returncode == 0 and "/" in up.stdout:
        return up.stdout.strip().split("/", 1)[0], ["push"]
    remotes = git(home, "remote").stdout.split()
    if not remotes:
        return None, None
    remote = "origin" if "origin" in remotes else remotes[0]
    return remote, ["push", "-u", remote, "HEAD"]


def backup(home, message, push=True, unverified=False):
    """Commit and push; prints what happened and returns an exit code. A GitHub remote whose visibility can't
    be confirmed isn't pushed to unless `unverified` says so."""
    where = show(home)
    if not own_repo(home):
        print(f"{where} isn't its own git repo, so nothing was backed up. To keep it backed up,\n"
              f"make it a private repo: cd {where} && git init && "
              "gh repo create sweatcast-me --private --source . --push")
        return cli.OK
    git(home, "add", "-A")
    staged = git(home, "diff", "--cached", "--name-only", "-z").stdout.split("\0")
    keyfiles = [p for p in staged if p and KEY_FILE.search(os.path.basename(p))]
    if keyfiles:   # API keys never go into the backup, even when the ignore rule is missing
        git(home, "reset", "-q")
        print(f"Not backed up: {', '.join(keyfiles)} looks like a key file (.env and its copies hold API keys, "
              f"which never go into the backup). Move it out of {where} or add it to {where}/.gitignore, then rerun.",
              file=sys.stderr)
        return cli.ISSUES
    if git(home, "diff", "--cached", "--quiet").returncode == 0:
        print("Nothing new to commit.")
    else:
        out = git(home, "commit", "-q", "-m", message)
        if out.returncode:
            print(f"Commit failed: {(out.stderr or out.stdout).strip()}", file=sys.stderr)
            return cli.ISSUES
        print(f"Committed: {message}")
    if not push:
        return cli.OK
    remote, args = push_target(home)
    if not remote:
        print(f"No remote, so it stays on this machine. To add a private one:\n"
              f"  cd {where} && gh repo create sweatcast-me --private --source . --push")
        return cli.OK
    slug = github_slug(git(home, "remote", "get-url", "--push", remote).stdout)
    # GitHub is asked every time (a repo made public since must never get health data); the memory stands in
    # only when GitHub can't say
    seen = visibility(slug) if slug else None
    if slug and seen in ("PRIVATE", "INTERNAL"):
        remember_private(home, slug, "github")
    elif slug and seen is None and remembered_private(home) == slug:
        seen = "PRIVATE"   # confirmed before on this computer: GitHub said so, or the listener did
    if slug and seen == "PUBLIC":
        print(f"Not pushed: github.com/{slug} is public, and this folder holds health details. "
              "Make it private (gh repo edit --visibility private) and rerun.", file=sys.stderr)
        return cli.ISSUES
    if slug and seen is None:
        if not unverified:
            print(f"Not pushed: couldn't confirm github.com/{slug} is private (gh isn't signed in here, or GitHub "
                  "didn't answer; a GH_TOKEN in the environment would let it). Check it at github.com, then rerun with "
                  "--unverified to push anyway; this computer remembers the answer for this remote.", file=sys.stderr)
            return cli.ISSUES
        remember_private(home, slug, "listener")
    if not slug:
        print(f"({remote} isn't on GitHub, so its visibility can't be checked here; make sure it's private.)")
    out = _push(home, args)
    if out.returncode:
        reason = (out.stderr.strip().splitlines() or ["no reason given"])[-1]
        print(f"Push to {remote} failed: {reason}\n"
              f"If another machine pushed first: cd {where} && git pull --rebase, then rerun.", file=sys.stderr)
        return cli.ISSUES
    print(f"Pushed to {remote}.")
    return cli.OK


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast backup", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-m", "--message", help="the commit message (default: sweatcast and the date and time)")
    ap.add_argument("--no-push", action="store_true", help="commit only")
    ap.add_argument("--unverified", action="store_true",
                    help="push even when GitHub won't say whether the remote is private (you checked)")
    args = ap.parse_args(argv)
    message = args.message or time.strftime("sweatcast %Y-%m-%d %H:%M")
    return backup(paths.HOME, message, push=not args.no_push, unverified=args.unverified)


if __name__ == "__main__":
    sys.exit(cli.run(main))
