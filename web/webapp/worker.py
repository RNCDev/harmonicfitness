"""The worker: claims a job, runs its handler in a temporary folder, finishes or fails it.

    python -m webapp.worker        (with DATABASE_URL, HARMONICFITNESS_MASTER_KEY, HARMONICFITNESS_BASE_URL in the environment)

A user's files are touched only through `engine.run` in that user's own temporary folder, which is
removed whatever happens; this process never reads or writes anyone's context as the engine would.
Before importing any engine module (for the session goals and kit presets) the worker points
HARMONICFITNESS_HOME at a folder that doesn't exist, so the engine's libraries never find a real `me/`.
"""
import datetime
import importlib
import os
import shutil
import signal
import sys
import tempfile
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable

import psycopg

from . import config, db, engine, folder, jobs, store

HEARTBEAT_EVERY = 15      # seconds; jobs.reap fails a job silent for 120
CONNECT_TIMEOUT = 10      # seconds, for the heartbeat's connection
JOIN_SLACK = 5            # seconds past CONNECT_TIMEOUT that stopping the heartbeat may wait
IDLE_WAIT = 5             # seconds to wait for NOTIFY jobs_queued before polling again
BRIEF_TIMEOUT = 300       # seconds; the engine's cold start can be slow
NEVER_WRITE_BACK = frozenset({"health.md"})


class JobFailed(Exception):
    """A job that failed in a way the worker expected. `error` is plain, non-personal wording; `detail`
    (what the engine said, say) is stored sealed in the job's result."""

    def __init__(self, error: str, detail: dict | None = None):
        super().__init__(error)
        self.error = error
        self.detail = detail


@dataclass
class Ctx:
    conn: Any
    uk: store.UserKey
    job_id: int
    args: dict
    settings: config.Settings
    home: str
    pending: tuple | None = None   # (changes, base) to write back when the job completes

    def say(self, stage: str, **fields) -> None:
        """A job event, committed now so a stream sees it live. It commits the connection's pending
        work too, so a handler doesn't call it in the middle of a transaction of its own."""
        jobs.event(self.conn, self.uk, self.job_id, {"stage": stage, **fields})

    def save(self, changes: dict[str, bytes | None], base: dict[str, int]) -> None:
        """Files to write back to the store: run_one writes them in the same transaction that marks the
        job done, and only while it is still running, then says "saved" with the conflicts."""
        self.pending = (changes, base)


# ---- the engine's own lists -------------------------------------------------------------------

_lists: dict[str, tuple[frozenset, frozenset]] = {}


def _no_home() -> str:
    while True:
        path = os.path.join(tempfile.gettempdir(), f"wt-no-context-{uuid.uuid4().hex}")
        if not os.path.exists(path):
            return path


def _engine_modules(engine_root: str, *names: str) -> list:
    """The named engine modules, imported with HARMONICFITNESS_HOME pointed at a folder that doesn't exist,
    `tools/` appended last on sys.path, and each module's origin checked to be inside the engine."""
    home = os.environ.get("HARMONICFITNESS_HOME", "")
    if not home or os.path.exists(home):
        os.environ["HARMONICFITNESS_HOME"] = _no_home()
    tools = os.path.abspath(os.path.join(engine_root, "tools"))
    if os.path.join(engine_root, "tools") not in sys.path and tools not in sys.path:
        sys.path.append(os.path.join(engine_root, "tools"))   # after everything else, so no engine module shadows another
    mods = [importlib.import_module(n) for n in names]
    for mod in mods:
        where = os.path.abspath(mod.__file__)
        if os.path.dirname(where) != tools and os.path.dirname(os.path.dirname(where)) != tools:
            raise RuntimeError(f"{mod.__name__} was imported from outside the engine")
    return mods


def engine_lists(engine_root: str) -> tuple[frozenset, frozenset]:
    """(session goals, kit presets) from the engine's tools/sessions.py and tools/catalog.py."""
    if engine_root not in _lists:
        catalog, sessions = _engine_modules(engine_root, "catalog", "sessions")
        _lists[engine_root] = (frozenset(sessions.load().goals),
                               frozenset(catalog.load(extra=[]).presets))
    return _lists[engine_root]


_services: dict[str, dict[str, dict]] = {}


def engine_services(engine_root: str) -> dict[str, dict]:
    """{service: {"name", "key_var", "key_page"}} from knowledge/services.toml, in its order."""
    if engine_root not in _services:
        services, = _engine_modules(engine_root, "services")
        _services[engine_root] = {k: {f: v[f] for f in ("name", "key_var", "key_page")}
                                  for k, v in services.settings().items()}
    return _services[engine_root]


def clean_key(engine_root: str, var: str, value: str) -> str:
    """The engine's keys.clean_value: stripped, or keys.BadKey when it can't be a key."""
    keys, = _engine_modules(engine_root, "keys")
    return keys.clean_value(var, value)


def _uv_cache() -> None:
    """uv's cache outside every user's folder (the engine runs with HOME set to one)."""
    os.environ.setdefault("UV_CACHE_DIR", os.path.join(tempfile.gettempdir(), "wt-uv-cache"))


# ---- handlers ---------------------------------------------------------------------------------

BRIEF_ARGS = {"goal", "minutes", "preset", "today"}


def _brief_request(args: dict, settings: config.Settings) -> tuple[str, int, str, str]:
    if not isinstance(args, dict) or set(args) != BRIEF_ARGS:
        raise JobFailed("invalid request: needs goal, minutes, preset and today")
    goals, presets = engine_lists(settings.engine_root)
    goal, minutes, preset, today = args["goal"], args["minutes"], args["preset"], args["today"]
    if not isinstance(goal, str) or goal not in goals:
        raise JobFailed("invalid request: unknown goal")
    if type(minutes) is not int or not 10 <= minutes <= 60:
        raise JobFailed("invalid request: minutes must be 10..60")
    if not isinstance(preset, str) or preset not in presets:
        raise JobFailed("invalid request: unknown preset")
    try:
        day = datetime.date.fromisoformat(today) if isinstance(today, str) and len(today) == 10 else None
    except ValueError:
        day = None
    now = datetime.datetime.now(datetime.timezone.utc).date()
    if day is None or abs((day - now).days) > 1:
        raise JobFailed("invalid request: today must be a date within a day of today")
    return goal, minutes, preset, day.isoformat()


def brief(ctx: Ctx) -> dict:
    """Run `./harmonicfitness brief` on the user's files and save its brief and menu back."""
    goal, minutes, preset, today = _brief_request(ctx.args, ctx.settings)
    stem = f"{today}-{goal}-{minutes}"
    ctx.say("folder")
    files = store.read_all(ctx.conn, ctx.uk)
    ctx.conn.commit()
    base = {path: version for path, (version, _) in files.items()}
    written = folder.materialize({path: body for path, (_, body) in files.items()}, ctx.home)
    ctx.say("brief")
    draft = os.path.join(ctx.home, "workouts", stem, f"{stem}.draft.txt")
    r = engine.run(ctx.settings.engine_root, ctx.home,
                   ["brief", "--goal", goal, "--minutes", str(minutes), "--preset", preset,
                    "--today", today, "--save", draft], timeout=BRIEF_TIMEOUT)
    if r.code != 0:
        raise JobFailed(f"the engine stopped (exit {r.code})", {"stderr": r.stderr})
    ctx.save(folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK), base)
    return {"brief_md": r.stdout, "stem": stem}


HANDLERS: dict[str, Callable[[Ctx], dict]] = {"brief": brief}


# ---- the loop ---------------------------------------------------------------------------------

class _Heartbeat(threading.Thread):
    """Marks one job alive every HEARTBEAT_EVERY seconds, on a connection of its own. `lost` is set
    when the job was no longer running or the heartbeat couldn't be written: the job may have been
    reaped, so its files are not written back."""

    def __init__(self, connect: Callable[[], Any], job_id: int):
        super().__init__(daemon=True, name=f"heartbeat-{job_id}")
        self.connect, self.job_id = connect, job_id
        self.halt, self.lost = threading.Event(), threading.Event()

    def run(self) -> None:
        conn = None
        try:
            conn = self.connect()
            while not self.halt.wait(HEARTBEAT_EVERY):
                if not jobs.heartbeat(conn, self.job_id):
                    self.lost.set()
                    return
        except Exception as e:  # noqa: BLE001 - the job carries on, but won't write back
            self.lost.set()
            print(f"worker: heartbeat for job {self.job_id} stopped: {type(e).__name__}", file=sys.stderr)
        finally:
            if conn is not None:
                conn.close()

    def stop(self) -> None:
        """Stop it; a hung connect never blocks the worker for long (the thread is a daemon)."""
        self.halt.set()
        self.join(timeout=CONNECT_TIMEOUT + JOIN_SLACK)


def run_one(conn, settings: config.Settings, connect: Callable[[], Any] | None = None) -> bool:
    """Reap stale jobs, claim one and run it; whether a job ran. `connect` opens the heartbeat's
    own connection (default: settings.database_url)."""
    _uv_cache()
    connect = connect or (lambda: psycopg.connect(settings.database_url, connect_timeout=CONNECT_TIMEOUT))
    jobs.reap(conn)
    job = jobs.claim(conn)
    if job is None:
        return False
    beat = _Heartbeat(connect, job.id)
    beat.start()
    home = None
    uk = None
    ctx = None
    outcome: tuple = ("failed", "the job stopped unexpectedly", None)
    try:
        uk = store.user_key(conn, settings, job.user_id)
        args = jobs.args(conn, uk, job.id)
        conn.commit()
        home = tempfile.mkdtemp(prefix="wt-job-")
        handler = HANDLERS.get(job.kind)
        if handler is None:
            raise JobFailed("unknown job kind")
        ctx = Ctx(conn=conn, uk=uk, job_id=job.id, args=args, settings=settings, home=home)
        outcome = ("done", handler(ctx))
    except JobFailed as e:
        conn.rollback()
        outcome = ("failed", e.error, e.detail)
    except Exception as e:  # noqa: BLE001 - only the type is logged: the message may be personal
        conn.rollback()
        print(f"worker: job {job.id} stopped: {type(e).__name__}", file=sys.stderr)
    finally:
        beat.stop()
        if home is not None:
            shutil.rmtree(home, ignore_errors=True)
    if outcome[0] == "done" and beat.lost.is_set():
        print(f"worker: job {job.id} lost its heartbeat; nothing written back", file=sys.stderr)
        outcome = ("failed", "interrupted", None)
    if outcome[0] == "done":
        _complete(conn, uk, job.id, outcome[1], ctx.pending)
    elif not jobs.fail(conn, uk, job.id, outcome[1], outcome[2] if uk is not None else None):
        print(f"worker: job {job.id} was no longer running", file=sys.stderr)
    return True


def _complete(conn, uk, job_id: int, result: dict, pending: tuple | None) -> None:
    """Write back the job's files and mark it done, in one transaction, only while it is running."""
    def apply() -> list[dict]:
        if pending is None:
            return []
        conflicts = store.write_back(conn, uk, *pending)
        return [{"stage": "saved", "conflicts": conflicts}]
    try:
        done = jobs.complete(conn, uk, job_id, result, apply)
    except Exception as e:  # noqa: BLE001 - only the type is logged: the message may be personal
        print(f"worker: job {job_id} stopped: {type(e).__name__}", file=sys.stderr)
        done = jobs.fail(conn, uk, job_id, "the job stopped unexpectedly")
    if not done:
        print(f"worker: job {job_id} was no longer running", file=sys.stderr)


def main() -> int:
    try:
        settings = config.load(os.environ)
    except config.ConfigError as e:
        print(f"worker: {e}", file=sys.stderr)
        return 2
    engine.not_dumpable()   # Linux: the engine child can't read our environment via /proc
    _uv_cache()
    engine_lists(settings.engine_root)
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    try:
        if not db.wait_for_migrations(lambda: psycopg.connect(settings.database_url,
                                                              connect_timeout=CONNECT_TIMEOUT),
                                      stop=stopping):
            return 0
    except db.MigrationsPending as e:
        print(f"worker: {e}", file=sys.stderr)
        return 3
    conn = db.connect(settings.database_url)
    listen = psycopg.connect(settings.database_url, autocommit=True)
    listen.execute("listen jobs_queued")
    try:
        while not stopping.is_set():
            if run_one(conn, settings):
                continue
            for _ in listen.notifies(timeout=IDLE_WAIT, stop_after=1):
                pass
    finally:
        listen.close()
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
