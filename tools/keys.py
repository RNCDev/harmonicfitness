"""API keys for the cloud voices, kept in me/.env and nowhere else.

One NAME=value per line, with each service's conventional variable name. The file is never
committed (me/.gitignore leaves it out, and ./harmonicfitness backup refuses it anyway), and this
module never prints a value: only whether one is set. The cloud engines call get() at the
moment they send a request; nothing else reads a key.

A key pasted into the chat would stay in the transcript, so it never passes through it: the listener
copies the key from the service's page and `./harmonicfitness keys paste <service>` saves it from the
clipboard, or they paste it into the file themselves (`keys init <service>` makes the line, `keys open`
opens the file).

    ./harmonicfitness keys                 # which services have a key set (never the key)
    ./harmonicfitness keys paste fish      # save the key on the clipboard as FISH_AUDIO_API_KEY (never shown)
    ./harmonicfitness keys init fish       # add an empty FISH_AUDIO_API_KEY= line to me/.env
    ./harmonicfitness keys open            # open me/.env in the system's editor, to paste a key
    ./harmonicfitness keys upload          # send them to your key store on the web app (tools/webkeys.py)
"""
import functools
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import fileio  # noqa: E402
import services  # noqa: E402  (knowledge/services.toml; not cloud.py, which reads keys)
import paths  # noqa: E402

LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
COMMENT_RE = re.compile(r"\s+#.*$")   # an inline comment after the value


class BadKey(errors.HarmonicFitnessError):
    """A key holds a character a key can't (a stray line break, a space, a symbol): the listener re-pastes it.
    Exits 4 through cli.run, like a service refusing the key; the message names the variable, never the value.
    A reported problem (errors.PROBLEMS), so a caller that carries on past one carries on past this too."""
    kind = "auth"
    listener_must_act = True
    exit_code = errors.SERVICE


def _var(service):
    if service not in _service_vars():
        raise errors.HarmonicFitnessError(f"No cloud voice service '{service}'. "
                                          f"The services: {', '.join(_service_vars())}.")
    return _service_vars()[service]


def _read(path):
    """{NAME: value} from the file; a missing file is empty."""
    try:
        with open(path, encoding="utf-8-sig") as f:   # -sig drops a BOM a Windows editor may add
            text = f.read()
    except FileNotFoundError:
        return {}
    out = {}
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        m = LINE_RE.match(line)
        if m:
            value = m.group(2)
            value = COMMENT_RE.sub("", value).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out[m.group(1)] = value
    return out


APP_SETTINGS = "HarmonicFitness's settings, under Keys"   # where the web client takes keys


def clean_value(var, value):
    """`value` stripped of the whitespace around it; BadKey when what's left can't be a key."""
    value = (value or "").strip()
    if any(c.isspace() or not 32 < ord(c) < 127 for c in value):
        if paths.WEB:
            raise BadKey(f"{var} holds a character a key can't (a stray line break, space or symbol): re-paste the "
                         f"key in {APP_SETTINGS}.")
        raise BadKey(f"{var} holds a character a key can't (a stray line break, space or symbol): re-paste the key "
                     f"after {var}= in me/.env (./harmonicfitness keys open), or fix it in the environment.")
    return value


# The listener's web app account, for ./harmonicfitness pull: their username and password, and optionally the
# app's address. Read like a key (the environment first, then me/.env); the password is scrubbed like one.
ACCOUNT_VARS = ("HARMONIC_USERNAME", "HARMONIC_PASSWORD", "HARMONIC_URL")
# Keys only the web app uses, to write workouts there (keys upload sends them; the engine never does). Gemini's
# and OpenRouter's keys write there too, under their voice service's name.
WRITER_VARS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
# SERVICE_VARS (service -> its key's variable), KEY_PAGES (service -> where a key is made) and SECRET_VARS (every
# variable whose value is scrubbed) come from knowledge/services.toml, read on first use, not at import: a damaged
# file is then the reason a command stops (exit 1), never a traceback.
_FROM_SERVICES = ("SERVICE_VARS", "KEY_PAGES", "SECRET_VARS")


@functools.cache
def _from_services() -> dict:
    table = services.settings()
    service_vars = {s: v["key_var"] for s, v in table.items()}
    return {"SERVICE_VARS": service_vars, "KEY_PAGES": {s: v["key_page"] for s, v in table.items()},
            "SECRET_VARS": tuple(service_vars.values()) + tuple(WRITER_VARS.values()) + ("HARMONIC_PASSWORD",)}


def _service_vars() -> dict:
    return _from_services()["SERVICE_VARS"]


def _key_pages() -> dict:
    return _from_services()["KEY_PAGES"]


def _secret_vars() -> tuple:
    return _from_services()["SECRET_VARS"]


def __getattr__(name):
    if name in _FROM_SERVICES:
        return _from_services()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def raw_values(path=None):
    """Every key value (and the web app password) as set, cleaned or not (for scrubbing them out of messages):
    the environment's, then the file's."""
    found = [os.environ.get(var) for var in _secret_vars()]
    file_values = _read(path or paths.ENV_FILE)
    found += [file_values.get(var) for var in _secret_vars()]
    return [v for v in found if v]


def web_account(path=None):
    """{HARMONIC_USERNAME, HARMONIC_PASSWORD, HARMONIC_URL: value or None}, the environment first, then me/.env.
    Never printed: the caller sends the password to the app and nowhere else."""
    file_values = _read(path or paths.ENV_FILE)
    return {var: (os.environ.get(var) or file_values.get(var) or "").strip() or None for var in ACCOUNT_VARS}


def get(service, path=None):
    """The service's key: the process environment first, then me/.env. None when unset or empty."""
    var = _var(service)
    value = clean_value(var, os.environ.get(var) or _read(path or paths.ENV_FILE).get(var))
    return value or None


def writer_key(provider, path=None):
    """A web app writer's key (WRITER_VARS), as get() reads a voice key. None when unset or empty."""
    var = WRITER_VARS[provider]
    return clean_value(var, os.environ.get(var) or _read(path or paths.ENV_FILE).get(var)) or None


def is_set(service, path=None):
    """Whether a usable key is set. A key that can't be read (BadKey) counts as not set here, so listing coaches
    or picking a default still works; get() raises where the key would be used, and ./harmonicfitness keys names it."""
    try:
        return get(service, path) is not None
    except BadKey:
        return False


def where(service, path=None):
    var = _var(service)
    if os.environ.get(var):
        return "in the environment"
    return f"{var} in {paths.show(path or paths.ENV_FILE)}"


def _make_file(path):
    """Make the key file with its header, private to this user, when it isn't there."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("# API keys for HarmonicFitness's cloud voices. Never committed or backed up; keep this file private.\n")


def init(service, path=None):
    """Make sure the file has a line for the service's key, private to this user. Returns the path."""
    var = _var(service)
    path = path or paths.ENV_FILE
    _make_file(path)
    if var not in _read(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n# {service}: get a key at {_key_pages()[service]}, then paste it after the = "
                    "(no quotes needed).\n"
                    f"{var}=\n")
    if os.name != "nt":
        os.chmod(path, 0o600)
    return path


# What reads the clipboard, by system, tried in order (Linux has no one tool). Windows' PowerShell runs from Git Bash.
CLIPBOARD_READERS = {
    "darwin": (["pbpaste"],),
    "win32": (["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],),
    "linux": (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"],
              ["xsel", "--clipboard", "--output"]),
}
KEY_LENGTH = (16, 1024)   # the web app's bounds (webapp/routes/settings.py), so a key saved here is taken there too


class KeyExists(errors.HarmonicFitnessError):
    """A key is already set and `--replace` wasn't given: a working key may not be shown again by its service,
    so it's never overwritten by surprise. Exit 1."""


def read_clipboard(run=subprocess.run):
    """The clipboard's text, decoded as UTF-8 (anything undecodable becomes a character a key can't hold).
    Never printed. HarmonicFitnessError when there's no tool to read it here."""
    readers = CLIPBOARD_READERS.get(sys.platform, CLIPBOARD_READERS["linux"])
    for argv in readers:
        try:
            done = run(argv, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if done.returncode == 0:
            return (done.stdout or b"").decode("utf-8", "replace")
    raise errors.HarmonicFitnessError(
        f"Couldn't read the clipboard here (tried {', '.join(a[0] for a in readers)}; on Linux an empty clipboard "
        "reads as none). Copy the key again, or paste it into the file instead: ./harmonicfitness keys init "
        "<service>, then ./harmonicfitness keys open.")


def _clipboard_key(service, text):
    """The key on the clipboard, or BadKey naming what's wrong with it (never the value)."""
    var = _var(service)
    again = f"Copy just the key from {_key_pages()[service]}, then run this again. Nothing was saved."
    value = (text or "").strip()
    if not value:
        raise BadKey(f"The clipboard is empty. {again}")
    try:
        value = clean_value(var, value)
    except BadKey:
        raise BadKey(f"What's on the clipboard can't be a {service} key (it holds a space, a line break or a "
                     f"symbol). {again}") from None
    if "://" in value:
        raise BadKey(f"The clipboard holds a web address, not a key. {again}")
    if not KEY_LENGTH[0] <= len(value) <= KEY_LENGTH[1]:
        raise BadKey(f"What's on the clipboard is too {'short' if len(value) < KEY_LENGTH[0] else 'long'} to be "
                     f"a {service} key. {again}")
    return value


def save(service, value, path=None, replace=False):
    """Write the key as the service's line in the key file, every other line kept, private to this user.
    KeyExists when one is set there and `replace` is false. Returns the path."""
    var = _var(service)
    path = path or paths.ENV_FILE
    _make_file(path)
    if not replace and _read(path).get(var):
        raise KeyExists(f"A {service} key is already set in {paths.show(path)}. To put this one in its place, "
                        f"run ./harmonicfitness keys paste {service} --replace.")
    with open(path, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    out, placed = [], False
    for line in lines:
        m = None if line.lstrip().startswith("#") else LINE_RE.match(line)
        if m and m.group(1) == var:
            if not placed:
                out.append(f"{var}={value}")
                placed = True
            continue   # a second line for the same key would shadow this one: dropped
        out.append(line)
    if not placed:
        out += ["", f"# {service}: from {_key_pages()[service]}.", f"{var}={value}"]
    fileio.atomic_write(path, "\n".join(out) + "\n")   # a temporary file, private to this user, renamed into place
    if os.name != "nt":
        os.chmod(path, 0o600)
    return path


def paste(service, path=None, replace=False, run=subprocess.run):
    """Save the key on the clipboard for the service (read_clipboard, then save). Returns the path."""
    return save(service, _clipboard_key(service, read_clipboard(run)), path=path, replace=replace)


def web_instructions(service=None):
    """What to do on Claude Code on the web, where a key file wouldn't outlast the session."""
    names = [_service_vars()[service]] if service else list(_service_vars().values())
    return ("On Claude Code on the web, a key in a file here would be gone when the session ends. Set it in the "
            "cloud environment's settings instead, under Environment variables, as one line:\n"
            + "\n".join(f"  {n}=<your key>" for n in names)
            + (f"\n(get one at {_key_pages()[service]})." if service
               else "\n(the service you use, one line each).")
            + " Never paste it into the chat. A new session picks it up; ./harmonicfitness keys then says it's set.")


def open_env(path=None, run=subprocess.Popen):
    """Open the key file in the system's editor, so the listener can paste a key without it passing through
    the chat. Makes the file (with init's header, no service line) if it's missing; never reads it. Returns the
    command run, or [] on the web or when there's no opener (then it prints the file's path)."""
    if paths.WEB:
        print(f"Add your keys in {APP_SETTINGS}.")
        return []
    if paths.REMOTE:
        print(web_instructions())
        return []
    path = path or paths.ENV_FILE
    _make_file(path)
    if os.name != "nt":
        os.chmod(path, 0o600)
    argv = (["open", "-e", path] if sys.platform == "darwin" else
            ["notepad", path] if sys.platform == "win32" else ["xdg-open", path])
    try:
        run(argv)
    except OSError:   # no opener here (a Linux without xdg-open): say where the file is
        print(f"Couldn't open it here ({argv[0]} isn't available): the file is {os.path.abspath(path)}; "
              "open it in any text editor and paste the key after its NAME= (init adds the line).")
        return []
    return argv


def main(argv=None):
    import cli   # the command only: cli imports redact, which imports this module, so the library never loads cli
    ap = cli.ArgumentParser(prog="harmonicfitness keys", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("init", help="add the service's key line to me/.env (making the file if needed)")
    i.add_argument("service", choices=list(_service_vars()))
    sub.add_parser("open", help="open me/.env in the system's editor, to paste a key")
    p = sub.add_parser("paste", help="save the key on the clipboard for the service in me/.env (never shown)")
    p.add_argument("service", choices=list(_service_vars()))
    p.add_argument("--replace", action="store_true", help="put it in place of a key already set")
    # `keys upload` is tools/webkeys.py's (the dispatcher sends it there), above this module and webpull
    args = ap.parse_args(argv)
    if args.cmd in ("init", "paste") and paths.WEB:
        print(f"Add your {args.service} key in {APP_SETTINGS}. Never paste it into the chat.")
        return errors.OK
    if args.cmd in ("init", "paste") and paths.REMOTE:
        print(web_instructions(args.service))
        return errors.OK
    if args.cmd == "paste":
        path = paste(args.service, replace=args.replace)
        var = _service_vars()[args.service]
        print(f"Saved the {args.service} key from the clipboard as {var} in {paths.show(path)} (never shown). "
              "Its first use checks it with the service.")
        if os.environ.get(var):
            print(f"Note: {var} is also set in the environment, and that one wins.")
        return errors.OK
    if args.cmd == "open":
        argv_run = open_env()
        if argv_run:
            print(f"Opened {os.path.abspath(paths.ENV_FILE)}. Paste the key after its NAME= (init adds the line), "
                  "and save.")
        return errors.OK
    if args.cmd == "init":
        path = init(args.service)
        print(f"Paste your {args.service} key after {_service_vars()[args.service]}= in {os.path.abspath(path)} "
              f"(get one at {_key_pages()[args.service]}), and save. To remove it later, delete that line.")
        return errors.OK
    for service in _service_vars():
        try:   # get(), not is_set(): the listing is where a key that can't be read is named
            state = f"set ({where(service)})" if get(service) is not None else "not set"
        except BadKey:
            state = f"holds a character a key can't; re-paste it ({where(service)})"
        print(f"{service:10}: {state}")
    return errors.OK


if __name__ == "__main__":
    import cli
    sys.exit(cli.run(main))
