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


def git(home, *args):
    return subprocess.run(["git", *args], cwd=home, capture_output=True, text=True)


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
    req = urllib.request.Request((api or API) + slug, headers={"Accept": "application/vnd.github+json",
                                                               "User-Agent": "sweatcast-backup"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if data.get("private") is False:
        return "PUBLIC"
    return str(data.get("visibility") or "").upper() or None


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


def backup(home, message, push=True):
    """Commit and push; prints what happened and returns an exit code."""
    where = show(home)
    if not own_repo(home):
        print(f"{where} isn't its own git repo, so nothing was backed up. To keep it backed up,\n"
              f"make it a private repo: cd {where} && git init && "
              "gh repo create sweatcast-me --private --source . --push")
        return cli.OK
    git(home, "add", "-A")
    staged = git(home, "diff", "--cached", "--name-only", "-z").stdout.split("\0")
    keyfiles = [p for p in staged if p and os.path.basename(p) == ".env"]
    if keyfiles:   # API keys never go into the backup, even when the ignore rule is missing
        git(home, "reset", "-q")
        print(f"Not backed up: {', '.join(keyfiles)} holds API keys and never goes into the backup. "
              f"Add a line .env to {where}/.gitignore, then rerun.")
        return cli.ISSUES
    if git(home, "diff", "--cached", "--quiet").returncode == 0:
        print("Nothing new to commit.")
    else:
        out = git(home, "commit", "-q", "-m", message)
        if out.returncode:
            print(f"Commit failed: {(out.stderr or out.stdout).strip()}")
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
    if slug and visibility(slug) == "PUBLIC":
        print(f"Not pushed: github.com/{slug} is public, and this folder holds health details. "
              "Make it private (gh repo edit --visibility private) and rerun.")
        return cli.ISSUES
    out = git(home, *args)
    if out.returncode:
        reason = (out.stderr.strip().splitlines() or ["no reason given"])[-1]
        print(f"Push to {remote} failed: {reason}\n"
              f"If another machine pushed first: cd {where} && git pull --rebase, then rerun.")
        return cli.ISSUES
    print(f"Pushed to {remote}.")
    return cli.OK


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast backup", description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-m", "--message", help="the commit message (default: sweatcast and the date and time)")
    ap.add_argument("--no-push", action="store_true", help="commit only")
    args = ap.parse_args(argv)
    message = args.message or time.strftime("sweatcast %Y-%m-%d %H:%M")
    return backup(paths.HOME, message, push=not args.no_push)


if __name__ == "__main__":
    sys.exit(cli.run(main))
