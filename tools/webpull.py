"""Bring a workout made in the web app down to this computer (./harmonicfitness pull).

Signs in to the web app as the listener, with HARMONIC_USERNAME and HARMONIC_PASSWORD from the environment or
me/.env (HARMONIC_URL names the app, default https://harmonicfitness.fly.dev), as the browser does: the app's
own sign-in, so it needs no server access and sees only what the listener could. Then it saves, in a new folder
me/web/<date>-<time>/:

  - me/...             every file the app keeps for them (its Export: drafts, briefs, menus, the log, coaches)
  - conversation.json  the conversation (the latest, or --conversation N): its chat lines, plan and question
  - <name>.mp3         each MP3 that conversation made, while the app still keeps it (24 hours)

and signs out. Nothing in me/ itself is overwritten. The password goes to the app and nowhere else, and is
scrubbed from anything printed.

    ./harmonicfitness pull
    ./harmonicfitness pull --conversation 12
"""
import datetime
import http.cookies
import io
import json
import os
import posixpath
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import fileio  # noqa: E402
import keys  # noqa: E402
import paths  # noqa: E402

DEFAULT_URL = "https://harmonicfitness.fly.dev"
COOKIE = "wt_session"
TIMEOUT = 120


class SignInRefused(errors.HarmonicFitnessError):
    """The app refused the username or password (exit 4, like a service refusing a key)."""
    exit_code = errors.SERVICE


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """The app's API never redirects; following one could send the session somewhere else."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise errors.HarmonicFitnessError(f"The web app redirected to {urllib.parse.urlsplit(newurl).netloc}; "
                                          f"not followed (HTTP {code}). Check HARMONIC_URL.")


def base_url(raw):
    """The app's address, checked: https, or http only on this computer."""
    url = (raw or DEFAULT_URL).strip().rstrip("/")
    parts = urllib.parse.urlsplit(url)
    local = parts.hostname in ("localhost", "127.0.0.1", "::1")
    if parts.scheme != "https" and not (parts.scheme == "http" and local) or not parts.netloc:
        raise errors.UsageError(f"HARMONIC_URL must be an https address (got {url!r}).")
    return f"{parts.scheme}://{parts.netloc}"


class App:
    """A signed-in session with the web app."""

    def __init__(self, url, opener=None):
        self.url = url
        self.opener = opener or urllib.request.build_opener(_NoRedirect)
        self.session = None

    def _request(self, method, path, body=None):
        headers = {"Accept": "*/*"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if method == "POST":
            headers["Origin"] = self.url   # the app refuses a POST from another origin
        if self.session:
            headers["Cookie"] = f"{COOKIE}={self.session}"
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with self.opener.open(req, timeout=TIMEOUT) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()
        except (urllib.error.URLError, OSError) as e:
            raise errors.HarmonicFitnessError(f"Couldn't reach the web app at {self.url}: "
                                              f"{getattr(e, 'reason', e)}") from None

    @staticmethod
    def _detail(body):
        try:
            return json.loads(body).get("detail") or ""
        except (ValueError, AttributeError):
            return ""

    def sign_in(self, username, password):
        status, headers, body = self._request("POST", "/api/sign-in",
                                              {"username": username, "password": password})
        if status == 400:
            raise SignInRefused("The web app refused HARMONIC_USERNAME and HARMONIC_PASSWORD: wrong username or "
                                "password. Fix them in me/.env (./harmonicfitness keys open).")
        if status == 429:
            raise SignInRefused(self._detail(body) or "Too many sign-in tries; wait 15 minutes.")
        if status != 204:
            raise errors.HarmonicFitnessError(f"The web app's sign-in answered HTTP {status}.")
        for value in headers.get_all("Set-Cookie") or []:
            jar = http.cookies.SimpleCookie()
            jar.load(value)
            if COOKIE in jar:
                self.session = jar[COOKIE].value
        if not self.session:
            raise errors.HarmonicFitnessError("The web app signed in but gave no session.")

    def get(self, path, ok=(200,)):
        status, _, body = self._request("GET", path)
        if status not in ok:
            detail = self._detail(body)
            raise errors.HarmonicFitnessError(f"The web app answered HTTP {status} for {path}"
                                              + (f": {detail}" if detail else "."))
        return status, body

    def sign_out(self):
        if self.session:
            try:
                self._request("POST", "/api/sign-out")
            except errors.HarmonicFitnessError:
                pass
            self.session = None


def _safe(name, fallback):
    """A file name from the app's name for something: no folders, nothing a file can't take."""
    name = posixpath.basename(str(name or "").replace("\\", "/"))
    name = "".join(c if c.isalnum() or c in " -_.()" else "_" for c in name).strip(" .")
    return name or fallback


def _unzip(data, dest):
    """Each file of the app's Export ZIP under `dest`, never outside it."""
    count = 0
    root = os.path.abspath(dest)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            parts = [p for p in info.filename.replace("\\", "/").split("/") if p not in ("", ".")]
            if not parts or ".." in parts or posixpath.basename(info.filename) in (".env", ".env.bak", "keys.env"):
                continue
            target = os.path.abspath(os.path.join(root, *parts))
            if not target.startswith(root + os.sep):
                continue
            fileio.atomic_write(target, z.read(info))
            count += 1
    return count


def pull(account, conversation=None, dest_root=None, app=None, now=None):
    """Sign in, save the files, the conversation and its MP3s under a new folder; what was saved, as a dict."""
    username, password = account.get("HARMONIC_USERNAME"), account.get("HARMONIC_PASSWORD")
    missing = [v for v, x in (("HARMONIC_USERNAME", username), ("HARMONIC_PASSWORD", password)) if not x]
    if missing:
        raise errors.UsageError(f"Add {' and '.join(missing)} to me/.env (./harmonicfitness keys open), "
                                "one NAME=value per line, to sign in to the web app.")
    app = app or App(base_url(account.get("HARMONIC_URL")))
    stamp = (now or datetime.datetime.now()).strftime("%Y-%m-%d-%H%M%S")
    dest = os.path.join(dest_root or os.path.join(paths.HOME, "web"), stamp)
    if os.path.exists(dest):
        raise errors.UsageError(f"{paths.show(dest)} already exists; pull again in a second.")
    app.sign_in(username, password)
    try:
        _, data = app.get("/api/export")
        files = _unzip(data, dest)
        path = f"/api/conversations/{conversation}" if conversation else "/api/conversations/latest"
        status, body = app.get(path, ok=(200, 204))
        conv = json.loads(body) if status == 200 else None
        mp3s, expired = [], 0
        if conv is not None:
            fileio.atomic_write(os.path.join(dest, "conversation.json"), json.dumps(conv, indent=2) + "\n")
            taken = set()
            for line in conv.get("lines") or []:
                audio = line.get("audio") if isinstance(line, dict) else None
                if not isinstance(audio, dict) or not audio.get("id"):
                    continue
                mid = urllib.parse.quote(str(audio["id"]), safe="")
                status, mp3 = app.get(f"/api/media/{mid}?download=1", ok=(200, 404))
                if status == 404:
                    expired += 1
                    continue
                name = _safe(audio.get("name"), "workout")
                name = name[:-4] if name.lower().endswith(".mp3") else name
                out, n = f"{name}.mp3", 2
                while out in taken:
                    out, n = f"{name} ({n}).mp3", n + 1
                taken.add(out)
                fileio.atomic_write(os.path.join(dest, out), mp3)
                mp3s.append(os.path.join(dest, out))
    finally:
        app.sign_out()
    return {"folder": dest, "files": files, "conversation": conv and conv.get("id"),
            "updated_at": conv and conv.get("updated_at"), "mp3s": mp3s, "expired": expired}


def main(argv=None):
    import cli
    ap = cli.ArgumentParser(prog="harmonicfitness pull", description=__doc__,
                            formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("--conversation", type=cli.positive_int, metavar="N",
                    help="the conversation's number (default the latest)")
    args = ap.parse_args(argv)
    got = pull(keys.web_account(), conversation=args.conversation)
    print(f"Saved in {paths.show(got['folder'])}:")
    print(f"  {got['files']} files from the web app (under me/)")
    if got["conversation"] is None:
        print("  no conversation yet")
    else:
        print(f"  conversation {got['conversation']} (last changed {got['updated_at']}): conversation.json")
    for mp3 in got["mp3s"]:
        print(f"  {os.path.basename(mp3)}")
    if got["expired"]:
        print(f"  {got['expired']} MP3 past the app's 24 hours, gone")
    return errors.OK


if __name__ == "__main__":
    import cli
    sys.exit(cli.run(main))
