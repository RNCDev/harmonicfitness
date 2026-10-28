"""Runs `./harmonicfitness <command>` in a subprocess for one user's temporary context folder.

The engine sees only an allowlisted environment, so the server's own secrets (database URL, master
key) never reach it. Output is scrubbed a second time here for the values passed in extra_env."""
import codecs
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
CANCELLED = 125
MAX_OUTPUT = 1_000_000   # characters kept of each of stdout and stderr
CUT = "\n[cut]\n"
POLL = 0.2               # seconds between looks at `cancel` while the engine runs
GRACE = 5                # seconds between SIGTERM and SIGKILL


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


class _Capped(threading.Thread):
    """Reads one pipe to its end, keeping at most `limit` characters: past that, the first and last
    halves with CUT between."""

    def __init__(self, pipe, limit: int):
        super().__init__(daemon=True)
        self.pipe, self.half, self.rest = pipe, limit // 2, limit - limit // 2
        self.head: list[str] = []
        self.head_len = 0
        self.tail: list[str] = []
        self.tail_len = 0
        self.total = 0
        self.lock = threading.Lock()

    def _add(self, text: str) -> None:
        self.total += len(text)
        if self.head_len < self.half:
            take = text[:self.half - self.head_len]
            self.head.append(take)
            self.head_len += len(take)
            text = text[len(take):]
        if text:
            self.tail.append(text)
            self.tail_len += len(text)
            if self.tail_len > 2 * self.rest:
                kept = "".join(self.tail)[-self.rest:]
                self.tail, self.tail_len = [kept], len(kept)

    def run(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while chunk := self.pipe.read1(65536):
                with self.lock:
                    self._add(decoder.decode(chunk))
            with self.lock:
                self._add(decoder.decode(b"", final=True))
        except (OSError, ValueError):
            pass   # the pipe closed under us: keep what was read

    def text(self) -> str:
        with self.lock:
            head, tail = "".join(self.head), "".join(self.tail)
            if self.total <= self.half + self.rest:
                return head + tail
            return head + CUT + tail[-self.rest:]


def run(engine_root: str, home: str, argv: list[str],
        extra_env: Mapping[str, str] = {}, timeout: float = 120,
        cancel: threading.Event | None = None, max_output: int = MAX_OUTPUT) -> Result:
    """Run the engine; its code, stdout and stderr (each capped at max_output characters, scrubbed of
    extra_env's values). Past `timeout`, or once `cancel` is set, its whole process group is stopped
    (SIGTERM, then SIGKILL after GRACE seconds) and the code is TIMED_OUT or CANCELLED."""
    env = _env(home, extra_env)
    secrets = list(extra_env.values())
    if cancel is not None and cancel.is_set():
        return Result(CANCELLED, "", "stopped: the job was cancelled\n")
    proc = subprocess.Popen([os.path.join(engine_root, "harmonicfitness"), *argv], cwd=engine_root, env=env,
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    readers = [_Capped(proc.stdout, max_output), _Capped(proc.stderr, max_output)]
    for r in readers:
        r.start()
    stopped = None   # why it was stopped, or None when it ended on its own
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel is not None and cancel.is_set():
                stopped = CANCELLED
                break
            left = deadline - time.monotonic()
            if left <= 0:
                stopped = TIMED_OUT
                break
            try:
                proc.wait(timeout=min(POLL, left))
                break
            except subprocess.TimeoutExpired:
                pass
        if stopped is not None:
            _kill(proc, signal.SIGTERM)
            try:
                proc.wait(timeout=GRACE)
            except subprocess.TimeoutExpired:
                _kill(proc, signal.SIGKILL)
                proc.wait()
    finally:
        _kill(proc, signal.SIGKILL)   # nothing of the engine's may outlive the call
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for r in readers:
            r.join(timeout=GRACE)
        for pipe in (proc.stdout, proc.stderr):
            pipe.close()
    stdout, stderr = (r.text() for r in readers)
    note = {TIMED_OUT: f"timed out after {timeout:g} s", CANCELLED: "stopped: the job was cancelled"}.get(stopped)
    if note:
        stderr = stderr.rstrip("\n") + ("\n" if stderr.strip() else "") + note + "\n"
    return Result(proc.returncode if stopped is None else stopped, scrub(stdout, secrets), scrub(stderr, secrets))
