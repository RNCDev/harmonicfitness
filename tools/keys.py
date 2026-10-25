"""API keys for the cloud voices, kept in me/.env and nowhere else.

One NAME=value per line, with each service's conventional variable name. The file is never
committed (me/.gitignore leaves it out, and ./sweatcast backup refuses it anyway), and this
module never prints a value: only whether one is set. The cloud engines call get() at the
moment they send a request; nothing else reads a key.

A key pasted into Claude Code would stay in the transcript, so the listener pastes it into the
file themselves: `./sweatcast keys init <service>` makes the line for them.

    ./sweatcast keys                 # which services have a key set (never the key)
    ./sweatcast keys init fish       # add an empty FISH_AUDIO_API_KEY= line to me/.env
    ./sweatcast keys open            # open me/.env in the system's editor, to paste a key
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import paths  # noqa: E402

SERVICE_VARS = {"fish": "FISH_AUDIO_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY",
                "gemini": "GEMINI_API_KEY", "inworld": "INWORLD_API_KEY"}
KEY_PAGES = {"fish": "https://fish.audio/app/api-keys/",
             "elevenlabs": "https://elevenlabs.io/app/settings/api-keys",
             "gemini": "https://aistudio.google.com/apikey",
             "inworld": "https://platform.inworld.ai/api-keys"}
LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _var(service):
    if service not in SERVICE_VARS:
        raise SystemExit(f"No cloud voice service '{service}'. The services: {', '.join(SERVICE_VARS)}.")
    return SERVICE_VARS[service]


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
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            out[m.group(1)] = value
    return out


def get(service, path=None):
    """The service's key: the process environment first, then me/.env. None when unset or empty."""
    var = _var(service)
    value = os.environ.get(var) or _read(path or paths.ENV_FILE).get(var)
    return value or None


def is_set(service, path=None):
    return get(service, path) is not None


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
            f.write("# API keys for sweatcast's cloud voices. Never committed or backed up; keep this file private.\n")


def init(service, path=None):
    """Make sure the file has a line for the service's key, private to this user. Returns the path."""
    var = _var(service)
    path = path or paths.ENV_FILE
    _make_file(path)
    if var not in _read(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n# {service}: get a key at {KEY_PAGES[service]}, then paste it after the = (no quotes needed).\n"
                    f"{var}=\n")
    if os.name != "nt":
        os.chmod(path, 0o600)
    return path


def web_instructions(service=None):
    """What to do on Claude Code on the web, where a key file wouldn't outlast the session."""
    names = [SERVICE_VARS[service]] if service else list(SERVICE_VARS.values())
    return ("On Claude Code on the web, a key in a file here would be gone when the session ends. Set it in the "
            "cloud environment's settings instead, under Environment variables, as one line:\n"
            + "\n".join(f"  {n}=<your key>" for n in names)
            + (f"\n(get one at {KEY_PAGES[service]})." if service else "\n(the service you use, one line each).")
            + " Never paste it into the chat. A new session picks it up; ./sweatcast keys then says it's set.")


def open_env(path=None, run=subprocess.Popen):
    """Open the key file in the system's editor, so the listener can paste a key without it passing through
    the chat. Makes the file (with init's header, no service line) if it's missing; never reads it. Returns the
    command run, or [] on the web or when there's no opener (then it prints the file's path)."""
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
    ap = cli.ArgumentParser(prog="sweatcast keys", description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    i = sub.add_parser("init", help="add the service's key line to me/.env (making the file if needed)")
    i.add_argument("service", choices=list(SERVICE_VARS))
    sub.add_parser("open", help="open me/.env in the system's editor, to paste a key")
    args = ap.parse_args(argv)
    if args.cmd == "init" and paths.REMOTE:
        print(web_instructions(args.service))
        return cli.OK
    if args.cmd == "open":
        argv_run = open_env()
        if argv_run:
            print(f"Opened {os.path.abspath(paths.ENV_FILE)}. Paste the key after its NAME= (init adds the line), "
                  "and save.")
        return cli.OK
    if args.cmd == "init":
        path = init(args.service)
        print(f"Paste your {args.service} key after {SERVICE_VARS[args.service]}= in {os.path.abspath(path)} "
              f"(get one at {KEY_PAGES[args.service]}), and save. To remove it later, delete that line.")
        return cli.OK
    for service in SERVICE_VARS:
        state = f"set ({where(service)})" if is_set(service) else "not set"
        print(f"{service:10}: {state}")
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
