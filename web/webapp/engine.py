"""Runs `./harmonicfitness <command>` in a subprocess for one user's temporary context folder.

The engine sees only an allowlisted environment, so the server's own secrets (database URL, master
key) never reach it. Output is scrubbed a second time here for the values passed in extra_env."""
import ctypes
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Iterable, Mapping, NamedTuple

ALLOWED = ("PATH", "LANG", "LC_ALL", "TZ", "UV_CACHE_DIR", "HARMONICFITNESS_PYTHON")
RESERVED = ("HOME", "HARMONICFITNESS_HOME", "HARMONICFITNESS_WEB")
TIMED_OUT = 124
STOPPED = 130     # the listener pressed Stop
POLL = 0.25       # seconds between looks at the cancel event and the clock
GRACE = 5         # seconds a killed engine gets to exit


PR_SET_DUMPABLE = 4


def not_dumpable() -> bool:
    """Linux only: mark this process non-dumpable, so its /proc/<pid>/environ and memory are
    root-only and an engine child (same user; the flag resets on its own execve) can't read the
    server's secrets through /proc. Returns whether it was set; False elsewhere (macOS, tests)."""
    if not sys.platform.startswith("linux"):
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_DUMPABLE, 0) failed")
    return True


class Result(NamedTuple):
    code: int
    stdout: str
    stderr: str


def scrub(text: str, secrets: Iterable[str]) -> str:
    """`text` with each secret (longest first, as is and stripped, when at least 8 characters) as <key>."""
    for value in sorted(secrets, key=len, reverse=True):
        for form in (value, value.strip()):
            if len(form) >= 8:
                text = text.replace(form, "<key>")
    return text


def _env(home: str, extra_env: Mapping[str, str]) -> dict[str, str]:
    for name in RESERVED:
        if name in extra_env:
            raise ValueError(f"extra_env may not set {name}")
    env = {k: os.environ[k] for k in ALLOWED if k in os.environ}
    env.update(HOME=home, HARMONICFITNESS_HOME=home, HARMONICFITNESS_WEB="1")
    env.update(extra_env)
    return env


def _kill(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def run(engine_root: str, home: str, argv: list[str],
        extra_env: Mapping[str, str] = {}, timeout: float = 120,
        cancel: threading.Event | None = None) -> Result:
    """One engine command, its output read in a thread so `cancel` (the listener's Stop) and the timeout
    can end it at any time: the engine's whole process group is killed, so nothing it started keeps
    running or billing."""
    env = _env(home, extra_env)
    if cancel is not None and cancel.is_set():
        return Result(STOPPED, "", "stopped\n")
    proc = subprocess.Popen([os.path.join(engine_root, "harmonicfitness"), *argv], cwd=engine_root, env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    box: dict = {}

    def talk() -> None:
        try:
            box["out"] = proc.communicate()
        except Exception as e:  # noqa: BLE001 - reported below as no output
            box["error"] = e
    reader = threading.Thread(target=talk, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    timed_out = stopped = False
    while reader.is_alive():
        reader.join(POLL)
        if cancel is not None and cancel.is_set():
            stopped = True
            break
        if time.monotonic() > deadline:
            timed_out = True
            break
    if reader.is_alive():
        _kill(proc, signal.SIGTERM)
        reader.join(GRACE)
        if reader.is_alive():
            _kill(proc, signal.SIGKILL)
            reader.join(GRACE)
    _kill(proc, signal.SIGKILL)   # nothing of the engine's may outlive the call
    out, err = box.get("out") or (b"", b"")
    stdout = out.decode("utf-8", errors="replace")
    stderr = err.decode("utf-8", errors="replace")
    if timed_out:
        stderr = stderr.rstrip("\n") + ("\n" if stderr.strip() else "") + f"timed out after {timeout:g} s\n"
    if stopped:
        stderr = stderr.rstrip("\n") + ("\n" if stderr.strip() else "") + "stopped\n"
    secrets = list(extra_env.values())
    code = STOPPED if stopped else TIMED_OUT if timed_out else proc.returncode
    return Result(code, scrub(stdout, secrets), scrub(stderr, secrets))
