"""The worker: claims a job, runs its handler in a temporary folder, finishes or fails it.

    python -m webapp.worker        (with DATABASE_URL, HARMONICFITNESS_MASTER_KEY, HARMONICFITNESS_BASE_URL in the environment)

A user's files are touched only through `engine.run` in that user's own temporary folder, which is
removed whatever happens; this process never reads or writes anyone's context as the engine would.
Before importing any engine module (for the session goals and kit presets) the worker points
HARMONICFITNESS_HOME at a folder that doesn't exist, so the engine's libraries never find a real `me/`.
"""
import dataclasses
import datetime
import importlib
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

import psycopg

from . import config, conversations, db, engine, folder, jobs, keystore, media, providers, store

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
    keys: dict = field(default_factory=dict, repr=False)   # {key_var: value}: the engine's extra_env, set by run_one
    on_done: Callable[[], None] | None = None   # run in the transaction that marks the job done
    on_lost: Callable[[str], None] | None = None   # run with the job's error (then committed) when the handler returned but the job wasn't done

    def say(self, stage: str, **fields) -> None:
        """A job event, committed now so a stream sees it live. It commits the connection's pending
        work too, so a handler doesn't call it in the middle of a transaction of its own."""
        jobs.event(self.conn, self.uk, self.job_id, {"stage": stage, **fields})

    def key_env(self) -> dict[str, str]:
        """{key_var: value} for each of the user's keys whose service the engine knows, for a job's
        extra_env only. Commits, so no transaction stays open across the engine run."""
        stored = keystore.open_all(self.conn, self.uk)
        self.conn.commit()
        services = engine_services(self.settings.engine_root)
        return {services[s]["key_var"]: v for s, v in stored.items() if s in services}

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
    if tools not in sys.path:
        sys.path.append(tools)   # after everything else, so no engine module shadows another
    before = list(sys.path)
    try:
        mods = [importlib.import_module(n) for n in names]
    finally:
        sys.path[:] = before   # some engine modules (keys) put tools/ first on import: undo that
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


def engine_keys(engine_root: str):
    """The engine's keys module (imported under the guard)."""
    return _engine_modules(engine_root, "keys")[0]


def clean_key(engine_root: str, var: str, value: str) -> str | None:
    """The engine's keys.clean_value (stripped); None when it refuses the value as a key (BadKey).
    Anything else it raises is a bug and propagates."""
    keys = engine_keys(engine_root)
    try:
        return keys.clean_value(var, value)
    except keys.BadKey:
        return None


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
    return goal, minutes, preset, _today(today)


def _today(today: object) -> str:
    """The request's `today`, checked: a date within a day of the worker's own (UTC)."""
    try:
        day = datetime.date.fromisoformat(today) if isinstance(today, str) and len(today) == 10 else None
    except ValueError:
        day = None
    now = datetime.datetime.now(datetime.timezone.utc).date()
    if day is None or abs((day - now).days) > 1:
        raise JobFailed("invalid request: today must be a date within a day of today")
    return day.isoformat()


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
                    "--today", today, "--save", draft], extra_env=ctx.keys, timeout=BRIEF_TIMEOUT)
    if r.code != 0:
        raise JobFailed(f"the engine stopped (exit {r.code})", {"stderr": r.stderr})
    ctx.save(folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK), base)
    return {"brief_md": r.stdout, "stem": stem}


TURN_ARGS = {"conversation_id", "line", "answer", "today", "now"}
TURN_NOW = re.compile(r"\d{4}-\d{2}-\d{2} \w+ \d{2}:\d{2}", re.ASCII)
MAX_LINE = 4000
NO_MODEL_KEY = "add a language-model key in Keys"
TOO_LONG = "this turn ran too long; try again with less to do"
ANSWER_NOT_OPEN = "that answer didn't match the open question; send a message instead"
CANT_FINISH = "the coach stopped on a step it can't finish here; send a message to carry on"
UNEXPECTED = "the job stopped unexpectedly"


class _Stop(Exception):
    """A turn that fails with `message`: the conversation goes failed with it, then the job."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _turn_request(args: dict) -> tuple[str | None, tuple[str, dict] | None, str, str]:
    """(line, answer, today, now), checked; exactly one of line or answer."""
    if set(args) != TURN_ARGS:
        raise _Stop("invalid request: needs conversation_id, line, answer, today and now")
    line, answer = args["line"], args["answer"]
    if (line is None) == (answer is None):
        raise _Stop("invalid request: give exactly one of line or answer")
    if line is not None and not (isinstance(line, str) and 0 < len(line.strip()) and len(line) <= MAX_LINE):
        raise _Stop("invalid request: line must be a message")
    if answer is not None:
        if not (isinstance(answer, dict) and set(answer) == {"tool_call_id", "values"}
                and isinstance(answer["tool_call_id"], str) and answer["tool_call_id"]
                and isinstance(answer["values"], dict)):
            raise _Stop("invalid request: answer needs tool_call_id and values")
        answer = (answer["tool_call_id"], answer["values"])
    try:
        today = _today(args["today"])
    except JobFailed as e:
        raise _Stop(e.error) from None
    now = args["now"]
    if not (isinstance(now, str) and TURN_NOW.fullmatch(now) and now.startswith(today)):
        raise _Stop("invalid request: now must be like 2026-10-28 Wednesday 08:00, on today")
    return line, answer, today, now


def check_turn(args: dict) -> str | None:
    """What's wrong with a turn job's args, in the worker's own words, or None: the API checks a turn
    with this before it queues one."""
    try:
        _turn_request(args)
    except _Stop as e:
        return e.message
    return None


def _agent_line(conv: conversations.Conversation, text: str) -> list:
    return conv.lines + [{"role": "agent", "text": text}]


def _fail_conversation(ctx: Ctx, conv: conversations.Conversation, message: str) -> None:
    """The conversation as stored (as it was before the turn: its history, plan and stem), failed with
    an agent line. Committed: run_one rolls back on JobFailed. Does nothing once it is no longer working,
    or once its turn is another job's (a late loss of an old job never fails a newer turn)."""
    ctx.conn.rollback()
    try:
        conv = conversations.load(ctx.conn, ctx.uk, conv.id)
    except LookupError:
        conv = None
    if conv is None or conv.state != "working" or conv.job_id != ctx.job_id:
        ctx.conn.rollback()
        return
    failed = dataclasses.replace(conv, state="failed", question=None,
                                 lines=_agent_line(conv, f"That didn't work: {message}"))
    if conversations.save(ctx.conn, ctx.uk, failed, conv.version):
        ctx.conn.commit()
    else:
        ctx.conn.rollback()


AUDIO_KEPT = 2   # MP3s a turn keeps, newest first (a turn normally makes one)


def _keep_audio(ctx: Ctx) -> list[dict]:
    """The MP3s this turn's builds made (the folder held none: materialize never writes one), kept 24 hours
    for the listener, newest first. Committed now, so the chat can link them as soon as the turn is saved."""
    found = []
    for dirpath, _, files in os.walk(os.path.join(ctx.home, "workouts")):
        found += [os.path.join(dirpath, f) for f in files if f.endswith(".mp3") and ".web-" not in f]
    found.sort(key=os.path.getmtime, reverse=True)
    kept = []
    for path in found[:AUDIO_KEPT]:
        with open(path, "rb") as f:
            body = f.read(media.MAX_BYTES + 1)
        try:
            kept.append(media.put(ctx.conn, ctx.uk, os.path.basename(path)[:-4], body))
        except ValueError:
            continue
    if kept:
        ctx.conn.commit()
        ctx.say("step", text="Your audio is ready", failed=False)
    return kept


def _step(ctx: Ctx, text: str, tool: str, code: int | None) -> None:
    """One step of a turn, live in the chat (a sealed job event) and in the worker's log (the tool and its
    exit code only, never what it read or wrote)."""
    print(f"worker: job {ctx.job_id} {tool} exit {code}", file=sys.stderr, flush=True)
    ctx.say("step", text=text, failed=code not in (0, None))


def turn(ctx: Ctx) -> dict:
    """One agent turn on the user's folder and language-model key, saved to their conversation."""
    args = ctx.args
    cid = args.get("conversation_id") if isinstance(args, dict) else None
    if type(cid) is not int:
        raise JobFailed("invalid request: needs conversation_id, line, answer, today and now")
    try:
        conv = conversations.load(ctx.conn, ctx.uk, cid)
    except LookupError:
        conv = None
    ctx.conn.commit()
    if conv is None or conv.state != "working" or conv.job_id != ctx.job_id:
        raise JobFailed("the conversation moved on")   # another job's turn, or none
    try:
        return _turn(ctx, conv)
    except _Stop as e:
        _fail_conversation(ctx, conv, e.message)
        raise JobFailed(e.message) from None
    except Exception:
        try:
            _fail_conversation(ctx, conv, UNEXPECTED)
        except Exception:  # noqa: BLE001 - the connection may be what broke; the first error is the one to log
            ctx.conn.rollback()
        raise   # run_one logs its type only


def _turn(ctx: Ctx, conv: conversations.Conversation) -> dict:
    from pydantic_ai.exceptions import UsageLimitExceeded   # pydantic-ai only in the jobs that use it
    from . import agent   # agent imports this module
    line, answer, today, now = _turn_request(ctx.args)
    stored = keystore.open_all(ctx.conn, ctx.uk)
    ctx.conn.commit()
    provider = next((p for p in ctx.settings.providers if stored.get(p)), None)
    if provider is None:
        raise _Stop(NO_MODEL_KEY)
    try:
        model = providers.model_for(provider, stored[provider])
    except Exception as e:  # noqa: BLE001 - the client's own words may hold the key
        print(f"worker: job {ctx.job_id} model client failed: {type(e).__name__}", file=sys.stderr)
        raise _Stop(providers.explain(provider, e).message) from None
    del stored   # the model key lives only in the model client from here on

    ctx.say("folder")
    files = store.read_all(ctx.conn, ctx.uk)
    ctx.conn.commit()
    base = {path: version for path, (version, _) in files.items()}
    written = folder.materialize({path: body for path, (_, body) in files.items()}, ctx.home)
    deps = agent.Deps(engine_root=ctx.settings.engine_root, home=ctx.home, keys=ctx.keys, today=today,
                      now=now, say=lambda text, tool, code: _step(ctx, text, tool, code))
    ctx.say("thinking")
    first = conv.history is None
    background = ThreadPoolExecutor(max_workers=1)
    sheet = os.path.join(ctx.home, "workouts", "research", "daily", f"{today}-feeds.md")
    if not first and not os.path.exists(sheet):
        deps.feeds = agent.start_feeds(deps, background)   # the check-in is answered: research begins now
    try:
        context = None
        if first and line:
            try:
                context = agent.prefetch(deps)
            except Exception as e:  # noqa: BLE001 - without it the model reads step 1 itself
                print(f"worker: job {ctx.job_id} prefetch failed: {type(e).__name__}", file=sys.stderr)
        outcome = agent.run_turn(model, deps, conv.history, line, answer, context=context)
    except agent.TurnError as e:
        raise _Stop({agent.NOT_OPEN: ANSWER_NOT_OPEN, agent.TIMED_OUT: TOO_LONG}.get(e.reason, CANT_FINISH)) from None
    except UsageLimitExceeded:
        raise _Stop(TOO_LONG) from None
    except Exception as e:  # noqa: BLE001 - a provider's failure; only explain's words go anywhere
        print(f"worker: job {ctx.job_id} turn stopped: {type(e).__name__}", file=sys.stderr)
        raise _Stop(providers.explain(provider, e).message) from None
    finally:
        background.shutdown(wait=True)   # feeds writes into the folder: done before it's harvested or removed

    lines = conv.lines if outcome.reply is None else _agent_line(conv, outcome.reply)
    for audio in _keep_audio(ctx):
        lines = lines + [{"role": "agent", "text": "", "audio": audio}]
    done = dataclasses.replace(conv, state="waiting" if outcome.question else "idle",
                               history=outcome.history_json, lines=lines, question=outcome.question,
                               plan=outcome.plan, stem=outcome.stem)   # as returned: None after a failed brief

    def save_turn() -> None:
        if not conversations.save(ctx.conn, ctx.uk, done, conv.version):
            raise RuntimeError("the conversation moved on")   # complete rolls back; the job fails

    ctx.on_done = save_turn
    ctx.on_lost = lambda error: _fail_conversation(ctx, conv, error)
    ctx.save(folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK), base)
    return {"conversation_id": conv.id, "state": done.state}


HANDLERS: dict[str, Callable[[Ctx], dict]] = {"brief": brief, "turn": turn}


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
    media.sweep(conn)
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
        ctx.keys = ctx.key_env()   # every handler passes ctx.keys as the engine's extra_env
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
        _lost(conn, job.id, ctx, "interrupted")
    if outcome[0] == "done":
        error = _complete(conn, uk, job.id, outcome[1], ctx)
        if error is not None:
            _lost(conn, job.id, ctx, error)
    elif not jobs.fail(conn, uk, job.id, outcome[1], outcome[2] if uk is not None else None):
        print(f"worker: job {job.id} was no longer running", file=sys.stderr)
    return True


def _complete(conn, uk, job_id: int, result: dict, ctx: Ctx) -> str | None:
    """Run the handler's on_done, write back its files and mark the job done, in one transaction, only
    while it is running. None when it was; else the job's error."""
    def apply() -> list[dict]:
        if ctx.on_done is not None:
            ctx.on_done()
        if ctx.pending is None:
            return []
        conflicts = store.write_back(conn, uk, *ctx.pending)
        return [{"stage": "saved", "conflicts": conflicts}]
    done = False
    try:
        done = jobs.complete(conn, uk, job_id, result, apply)
    except Exception as e:  # noqa: BLE001 - only the type is logged: the message may be personal
        print(f"worker: job {job_id} stopped: {type(e).__name__}", file=sys.stderr)
        jobs.fail(conn, uk, job_id, UNEXPECTED)
        return UNEXPECTED
    if not done:
        print(f"worker: job {job_id} was no longer running", file=sys.stderr)
        return "interrupted"   # reaped: jobs.reap's word
    return None


def _lost(conn, job_id: int, ctx: Ctx | None, error: str) -> None:
    """The handler's on_lost with the job's error, committed, for a job that returned but was never
    marked done."""
    conn.rollback()
    if ctx is None or ctx.on_lost is None:
        return
    try:
        ctx.on_lost(error)
        conn.commit()
    except Exception as e:  # noqa: BLE001 - only the type is logged
        conn.rollback()
        print(f"worker: job {job_id} couldn't record the loss: {type(e).__name__}", file=sys.stderr)


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
