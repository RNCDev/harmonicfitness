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
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import threading
import time
import tomllib
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

import psycopg

from . import clipcache, config, conversations, db, engine, folder, jobs, keystore, media, providers, spend, store

HEARTBEAT_EVERY = 15      # seconds; jobs.reap fails a job silent for 120
STOP_POLL = 2             # seconds between the heartbeat's looks for the listener's Stop
CONNECT_TIMEOUT = 10      # seconds, for the heartbeat's connection
JOIN_SLACK = 5            # seconds past CONNECT_TIMEOUT that stopping the heartbeat may wait
IDLE_WAIT = 5             # seconds to wait for NOTIFY jobs_queued before polling again
RECONNECT_WAIT = 2        # seconds before reconnecting after the database closed the worker's connection
BRIEF_TIMEOUT = 300       # seconds; the engine's cold start can be slow
NEVER_WRITE_BACK = frozenset()   # the check-in may change health.md, with the listener's permission (the skill's rule)


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
    cancel: threading.Event = field(default_factory=threading.Event)   # the listener's Stop
    on_lost: Callable[[str], None] | None = None   # run with the job's error (then committed) when the handler returned but the job wasn't done
    started: dict = field(default_factory=dict, repr=False)   # {step id: when it started}: the log says how long each took

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
        for legacy, shared in providers.SHARED_KEY.items():   # a model key stored before 0.25.2 voices too
            if legacy in stored and shared not in stored:
                stored[shared] = stored[legacy]
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
    """{service: {"name", "key_var", "key_page", "billing_page", "reports"}} from knowledge/services.toml, in its
    order; `reports`: whether the service's module can say what's left on the account (balance())."""
    if engine_root not in _services:
        services, = _engine_modules(engine_root, "services")
        table = services.settings()
        modules = _engine_modules(engine_root, *(f"services.{k}" for k in table))
        _services[engine_root] = {k: {**{f: v[f] for f in ("name", "key_var", "key_page", "billing_page")},
                                      "reports": hasattr(m, "balance")}
                                  for (k, v), m in zip(table.items(), modules)}
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


BALANCES_TIMEOUT = 90     # seconds: the engine's cold start, then one GET a service
BALANCE_FIELDS = ("ok", "usd", "used", "limit", "resets", "kind")   # never the message: it's the service's words


def balances(ctx: Ctx) -> dict:
    """What's left on each keyed voice service's account (`./harmonicfitness balances --json`): {"balances":
    {service: row}} with only the fields the page shows. Needs none of the listener's files."""
    if ctx.args:
        raise JobFailed("invalid request: a balance check takes nothing")
    r = engine.run(ctx.settings.engine_root, ctx.home, ["balances", "--json"], extra_env=ctx.keys,
                   timeout=BALANCES_TIMEOUT, cancel=ctx.cancel)
    if r.code != 0:
        raise JobFailed(f"the engine stopped (exit {r.code})", {"stderr": r.stderr})
    try:
        rows = json.loads(r.stdout)
    except ValueError:
        rows = None
    if not isinstance(rows, dict):
        raise JobFailed("the engine's answer couldn't be read")
    return {"balances": {s: {f: row[f] for f in BALANCE_FIELDS if f in row}
                         for s, row in rows.items() if isinstance(row, dict) and "ok" in row}}


def listener_zone(now: str, utc: datetime.datetime | None = None) -> str | None:
    """A POSIX TZ for the listener's clock, from the "YYYY-MM-DD Weekday HH:MM" their page sent and the server's
    UTC (to the quarter hour), so every engine command in the turn (the brief's time, the menu's day, the build's)
    reads their local time, not the server's. None when `now` can't be read or is more than 14 hours off."""
    try:
        day, _, clock = now.split(" ")
        local = datetime.datetime.fromisoformat(f"{day} {clock}")
    except (ValueError, AttributeError):
        return None
    utc = (utc or datetime.datetime.now(datetime.timezone.utc)).replace(tzinfo=None)
    minutes = round((local - utc).total_seconds() / 60 / 15) * 15
    if abs(minutes) > 14 * 60:
        return None
    sign = "-" if minutes >= 0 else "+"   # POSIX: the offset to add to local time to reach UTC
    h, m = divmod(abs(minutes), 60)
    return f"LCL{sign}{h}" + (f":{m:02d}" if m else "")


ENRICH_TIMEOUT = 120   # seconds for one enrichment's engine command or model call
ENRICH_REF = re.compile(r"[A-Za-z0-9-]{1,40}")
INTERESTS_FILE = "workouts/research/interests.jsonl"


def enrich(ctx: Ctx) -> dict:
    """What a listener's feedback on one workout teaches (agent.enrich), recorded through `interests add` and
    saved at once, in enrichment's own lane. A write that conflicts with a turn saving the same moment is
    applied again on the files as they now stand (the same signals, no second model call), so no evidence is
    lost. {"summary": what was noted, "signals": how many}; nothing to note without a writer key."""
    from . import agent
    from .agent import enrich as enricher
    args = ctx.args if isinstance(ctx.args, dict) else {}
    ref, text, today = args.get("ref"), args.get("text"), args.get("today")
    if not (isinstance(ref, str) and ENRICH_REF.fullmatch(ref) and isinstance(text, str) and text.strip()
            and isinstance(today, str) and _date_ok(today)):
        raise JobFailed("invalid request: needs ref, text and today")
    stored = keystore.open_all(ctx.conn, ctx.uk)
    chosen = keystore.writer(ctx.conn, ctx.uk)
    ctx.conn.commit()
    provider = providers.pick(ctx.settings.providers, stored, chosen)
    if provider is None:
        return {"summary": "", "signals": 0}
    try:
        model = providers.model_for(provider, providers.stored_key(stored, provider))
    except Exception as e:  # noqa: BLE001 - the client's own words may hold the key
        raise JobFailed(providers.explain(provider, e).message) from None
    del stored
    files, base, written = _materialize(ctx)
    r = engine.run(ctx.settings.engine_root, ctx.home, ["workouts", "context", ref], extra_env=ctx.keys,
                   timeout=ENRICH_TIMEOUT, cancel=ctx.cancel)
    if r.code != 0:
        raise JobFailed(f"the engine stopped (exit {r.code})")
    try:
        facts = json.loads(r.stdout)
    except ValueError:
        raise JobFailed("the engine's answer couldn't be read") from None
    try:
        found = enricher.enrich(model, facts, text.strip()[:1000], agent.native_tools(model))
    except Exception as e:  # noqa: BLE001 - a provider's failure; only explain's words go anywhere
        print(f"worker: job {ctx.job_id} enrich stopped: {type(e).__name__}", file=sys.stderr, flush=True)
        raise JobFailed(providers.explain(provider, e).message) from None
    argv = enricher.signal_args(found.signals)
    if not argv:
        return {"summary": found.summary if found.signals else "", "signals": 0}
    build = (facts.get("workout") or {}).get("build_id")
    add = ["interests", "add", "--source", "feedback", "--date", today, *(["--build", build] if build else []), *argv]
    for attempt in range(2):
        r = engine.run(ctx.settings.engine_root, ctx.home, add, extra_env=ctx.keys, timeout=ENRICH_TIMEOUT,
                       cancel=ctx.cancel)
        if r.code != 0:
            raise JobFailed(f"the engine stopped (exit {r.code})")
        changes = folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK)
        try:
            conflicts = store.write_back(ctx.conn, ctx.uk, changes, base)
            ctx.conn.commit()
        except Exception:
            ctx.conn.rollback()
            raise
        if INTERESTS_FILE not in conflicts:
            break
        if attempt == 0:   # a turn saved the evidence at the same moment: again, on the files as they now stand
            shutil.rmtree(ctx.home, ignore_errors=True)
            os.makedirs(ctx.home, exist_ok=True)
            files, base, written = _materialize(ctx)
        else:
            raise JobFailed("your files were changing too fast; try the feedback again")
    return {"summary": found.summary, "signals": len(argv) // 2}


def _materialize(ctx: Ctx) -> tuple:
    """The user's files in ctx.home: (files, base versions, written digests)."""
    files = store.read_all(ctx.conn, ctx.uk)
    ctx.conn.commit()
    base = {path: version for path, (version, _) in files.items()}
    written = folder.materialize({path: body for path, (_, body) in files.items()}, ctx.home)
    return files, base, written


def _date_ok(day: str) -> bool:
    try:
        datetime.date.fromisoformat(day)
        return True
    except ValueError:
        return False


TURN_ARGS = {"conversation_id", "line", "answer", "today", "now"}
TURN_NOW = re.compile(r"\d{4}-\d{2}-\d{2} \w+ \d{2}:\d{2}", re.ASCII)
MAX_LINE = 4000
NO_MODEL_KEY = "add a language-model key in Settings"
TOO_LONG = "this turn ran too long; try again with less to do"
ANSWER_NOT_OPEN = "that answer didn't match the open question; send a message instead"
CANT_FINISH = "the coach stopped on a step it can't finish here; send a message to carry on"
UNEXPECTED = "the job stopped unexpectedly"
STOPPED = "you stopped it"


class _Stop(Exception):
    """A turn that fails with `message`: the conversation goes failed with it, then the job."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _turn_request(args: dict) -> tuple[str | None, tuple[str, dict] | None, str, str]:
    """(line, answer, today, now), checked; exactly one of line or answer. A scheduled turn (0.60.0) also carries
    `scheduled` and the listener's `offset` from UTC in minutes; its today and now are when it was due."""
    if (set(args) - {"record", "scheduled", "offset"} != TURN_ARGS or args.get("record", False) not in (True, False)
            or args.get("scheduled", False) not in (True, False)
            or ("scheduled" in args) != ("offset" in args)
            or ("offset" in args and not (type(args["offset"]) is int and abs(args["offset"]) <= 14 * 60))):
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


def _fail_conversation(ctx: Ctx, conv: conversations.Conversation, message: str, audio: list[dict] | None = None) -> None:
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
    said = "Stopped. Send a message when you want to carry on." if message == STOPPED else f"That didn't work: {message}"
    lines = conv.lines + [{"role": "agent", "text": "", "audio": a} for a in audio or ()]
    failed = dataclasses.replace(conv, state="failed", question=None, offer=None if audio else conv.offer,
                                 lines=lines + [{"role": "agent", "text": said}])
    if conversations.save(ctx.conn, ctx.uk, failed, conv.version):
        ctx.conn.commit()
    else:
        ctx.conn.rollback()


AUDIO_KEPT = 2   # a workout's or a coach sample's MP3s a turn keeps, newest first (a turn normally makes one)


def _candidate_names(folder_path: str) -> dict[str, str]:
    """{mp3 file name: chat name} for an audition's candidates: by letter and cost a workout, never the
    service (the listener picks by ear). Empty when its candidates list can't be read."""
    import json
    try:
        with open(os.path.join(folder_path, "candidates.json"), encoding="utf-8") as f:
            cands = json.load(f)
        names = {}
        for c in cands:
            usd = c.get("usd_per_workout")
            cost = f", about ${usd:.2f} a workout" if isinstance(usd, (int, float)) else ""
            if isinstance(c.get("mp3"), str) and isinstance(c.get("letter"), str):
                names[c["mp3"]] = f"Candidate {c['letter']}{cost}"
        return names
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def _coach_name(folder_path: str) -> str | None:
    """The coach's name from its persona.md's settings block, else None."""
    try:
        with open(os.path.join(folder_path, "persona.md"), encoding="utf-8") as f:
            text = f.read()
        block = text.split("+++")[1] if text.startswith("+++") else ""
        name = tomllib.loads(block).get("name")
    except (OSError, IndexError, ValueError):
        return None
    return name.strip() if isinstance(name, str) and name.strip() else None


def new_audio(home: str, written: dict[str, str]) -> list[tuple[str, str]]:
    """(path, chat name) of each MP3 this turn made: the newest AUDIO_KEPT workouts or coach samples, then
    every candidate of an audition, in letter order. An MP3 the folder already held (`written`: an audition
    from an earlier turn) isn't one. A coach's sample is named for the coach ("Coach Miles's voice"), and left
    out when the turn also made a workout: the coach was made during that build, and the workout is its voice."""
    found, candidates = [], []
    for top in ("workouts", "coaches"):   # a workout, or a coach's voice sample made at setup or a keep
        for dirpath, _, files in os.walk(os.path.join(home, top)):
            for f in files:
                path = os.path.join(dirpath, f)
                rel = os.path.relpath(path, home).replace(os.sep, "/")
                if not f.endswith(".mp3") or ".web-" in f or rel in written:
                    continue
                (candidates if rel.startswith(folder.AUDITIONS) else found).append(path)
    found.sort(key=os.path.getmtime, reverse=True)
    out = []
    kept = found[:AUDIO_KEPT]
    workout = any(os.path.basename(p) != "sample.mp3" for p in kept)
    for path in kept:
        if os.path.basename(path) != "sample.mp3":
            out.append((path, os.path.basename(path)[:-4]))
        elif not workout:
            where = os.path.dirname(path)
            name = _coach_name(where)
            out.append((path, f"{name}'s voice" if name else f"{os.path.basename(where)}: voice sample"))
    by_audition: dict[str, list[str]] = {}
    for path in sorted(candidates):
        by_audition.setdefault(os.path.dirname(path), []).append(os.path.basename(path))
    named = []
    for where, mp3s in sorted(by_audition.items()):
        names = _candidate_names(where)   # in letter order
        listed = [m for m in names if m in mp3s] + [m for m in mp3s if m not in names]
        named += [(os.path.join(where, m), names.get(m, "Voice candidate")) for m in listed]
    return out + named


def _build_id(mp3: str) -> str | None:
    """The build_id in the build record beside a workout's MP3 (<name>.build.json), or None."""
    import json
    try:
        with open(mp3[:-4] + ".build.json", encoding="utf-8") as f:
            found = json.load(f).get("build_id")
    except (OSError, ValueError, AttributeError):
        return None
    return found if isinstance(found, str) and found else None


def _keep_audio(ctx: Ctx, written: dict[str, str], done: set[str] | None = None) -> list[dict]:
    """The MP3s this turn made (new_audio), kept 24 hours for the listener, less those in `done` (kept
    already this turn; each kept one is added to it). Committed now, so the chat can link them as soon as
    the turn is saved."""
    kept = []
    done = set() if done is None else done
    for path, name in new_audio(ctx.home, written):
        if path in done:
            continue
        done.add(path)
        with open(path, "rb") as f:
            body = f.read(media.MAX_BYTES + 1)
        try:
            kept.append(media.put(ctx.conn, ctx.uk, name, body, _build_id(path)))
        except ValueError:
            continue
    if kept:
        ctx.conn.commit()
        ctx.say("step", text="Your audio is ready", failed=False)
    return kept


def _step(ctx: Ctx, text: str, tool: str, code: int | None, step: int | None = None, think: bool = False) -> None:
    """One step of a turn, live in the chat (a sealed job event) and in the worker's log (the tool and its
    exit code only, never what it read or wrote). With a step id, the step is said as it starts (code None:
    state "running") and again under the same id as it ends ("done" or "failed"); an event without an id, as
    before 0.25.2, is a step already done."""
    failed = code not in (0, None)
    if step is None:
        ctx.say("step", text=text, failed=failed)
        return
    if code is None:
        ctx.started[step] = time.monotonic()
    else:
        began = ctx.started.pop(step, None)
        took = f" {time.monotonic() - began:.1f}s" if began is not None else ""
        # how long the model thought, and each tool's exit: the turn's timeline, never what it read or wrote
        line = f"think{' failed' if failed else ''}{took}" if think else f"{tool} exit {code}{took}"
        print(f"worker: job {ctx.job_id} {line}", file=sys.stderr, flush=True)
    ctx.say("step", text=text, failed=failed, id=step,
            state="running" if code is None else "failed" if failed else "done", **({"think": True} if think else {}))


def api_when(local: str) -> str:
    """"Wednesday at 07:00" from "2026-11-04 Wednesday 07:00"."""
    parts = local.split(" ")
    return f"{parts[1]} at {parts[2]}" if len(parts) == 3 else local


def local_clock(offset: int, utc: datetime.datetime | None = None) -> tuple[str, str]:
    """(today, now) on the listener's clock, `offset` minutes east of UTC, as their page would send them."""
    at = (utc or datetime.datetime.now(datetime.timezone.utc)).astimezone(
        datetime.timezone(datetime.timedelta(minutes=offset)))
    return at.strftime("%Y-%m-%d"), at.strftime("%Y-%m-%d %A %H:%M")


def turn(ctx: Ctx) -> dict:
    """One agent turn on the user's folder and language-model key, saved to their conversation. A scheduled
    turn wakes its conversation first, on the listener's clock as it is now."""
    args = ctx.args
    cid = args.get("conversation_id") if isinstance(args, dict) else None
    if type(cid) is not int:
        raise JobFailed("invalid request: needs conversation_id, line, answer, today and now")
    if args.get("scheduled") is True and type(args.get("offset")) is int:
        today, now = local_clock(args["offset"])
        ctx.args = args = dict(args, today=today, now=now)
        woke = conversations.wake(ctx.conn, ctx.uk, cid, ctx.job_id)
        due = jobs.due_at(ctx.conn, ctx.job_id)
        ctx.conn.commit()
        if not woke:
            raise JobFailed("the conversation moved on")   # cancelled, or changed, as the turn was claimed
        if due is not None:   # how early the run starts, for tuning its lead (the log, never the page)
            late = (datetime.datetime.now(datetime.timezone.utc) - due).total_seconds()
            print(f"worker: job {ctx.job_id} scheduled turn began {late:.0f}s after it was due", file=sys.stderr, flush=True)
    try:
        conv = conversations.load(ctx.conn, ctx.uk, cid)
    except LookupError:
        conv = None
    ctx.conn.commit()
    if conv is None or conv.state != "working" or conv.job_id != ctx.job_id:
        raise JobFailed("the conversation moved on")   # another job's turn, or none
    kept: list[dict] = []   # audio the turn has kept so far: a turn that fails after its recording still shows it
    try:
        return _turn(ctx, conv, kept)
    except _Stop as e:
        _fail_conversation(ctx, conv, e.message, kept)
        raise JobFailed(e.message) from None
    except Exception:
        try:
            _fail_conversation(ctx, conv, UNEXPECTED, kept)
        except Exception:  # noqa: BLE001 - the connection may be what broke; the first error is the one to log
            ctx.conn.rollback()
        raise   # run_one logs its type only


def _turn(ctx: Ctx, conv: conversations.Conversation, kept: list[dict] | None = None) -> dict:
    from pydantic_ai.exceptions import UsageLimitExceeded   # pydantic-ai only in the jobs that use it
    from . import agent   # agent imports this module
    line, answer, today, now = _turn_request(ctx.args)
    stored = keystore.open_all(ctx.conn, ctx.uk)
    chosen = keystore.writer(ctx.conn, ctx.uk)
    picked = keystore.coach(ctx.conn, ctx.uk)
    auto = keystore.auto_record(ctx.conn, ctx.uk)
    ctx.conn.commit()
    provider = providers.pick(ctx.settings.providers, stored, chosen)
    if provider is None:
        raise _Stop(NO_MODEL_KEY)
    try:
        model = providers.model_for(provider, providers.stored_key(stored, provider))
    except Exception as e:  # noqa: BLE001 - the client's own words may hold the key
        print(f"worker: job {ctx.job_id} model client failed: {type(e).__name__}", file=sys.stderr)
        raise _Stop(providers.explain(provider, e).message) from None
    del stored   # the model key lives only in the model client from here on

    ctx.say("folder")
    files = store.read_all(ctx.conn, ctx.uk)
    ctx.conn.commit()
    base = {path: version for path, (version, _) in files.items()}
    written = folder.materialize({path: body for path, (_, body) in files.items()}, ctx.home)
    zone = listener_zone(now)   # the engine's clock is the listener's: the brief's time, today's date for the menu
    deps = agent.Deps(engine_root=ctx.settings.engine_root, home=ctx.home,
                      keys=dict(ctx.keys, **({"TZ": zone} if zone else {})), today=today,
                      now=now, say=lambda text, tool, code, step=None, think=False: _step(ctx, text, tool, code, step, think),
                      cancel=ctx.cancel, picked=picked,
                      log=lambda text: print(f"worker: job {ctx.job_id} {text}", file=sys.stderr, flush=True))
    deps.setup = agent.needs_setup(ctx.home) or agent.wants_setup(line)   # the setup skill comes too
    # and the coach skill only while an old audition waits to be closed: coaches are chosen in the gallery
    # here, never made (since 0.46.2), and the skill's text would steer the agent to an audition
    deps.coach = agent.audition_open(ctx.home)
    record = ctx.args.get("record") is True   # the listener pressed Record: the offer is approved
    deps.approved = conv.offer if record else None
    deps.chars_left = spend.daily_cap() - spend.used(ctx.conn, ctx.uk, today)
    deps.auto_record = auto and not record
    deps.later = conv.later if conv.later and not conv.offer else None
    if ctx.args.get("scheduled") is True:   # "Schedule it" approved one recording, up to its ceiling
        deps.scheduled_run = True
        deps.auto_record = not record
        deps.ceiling = int((conv.later or {}).get("ceiling_chars") or 0) or None

    def reserve(chars: int) -> bool:
        """Today's allowance, reserved for a recording made without the Record button (as its endpoint does)."""
        try:
            fits = spend.reserve(ctx.conn, ctx.uk, today, chars, spend.daily_cap())
            ctx.conn.commit()
            return fits
        except Exception:  # noqa: BLE001 - then the Record button is offered, as without the setting
            ctx.conn.rollback()
            return False
    deps.reserve = reserve
    # re-recording pays only for changes; a turn that may record on its own needs them too
    clips = clipcache.load(ctx.conn, ctx.uk, ctx.home) if record or deps.auto_record else None
    if clips is None:   # a writing turn still plans by the coach's measured pace
        clipcache.load_pace(ctx.conn, ctx.uk, ctx.home)
    ctx.conn.commit()
    kept = [] if kept is None else kept
    kept_paths: set[str] = set()

    def checkpoint() -> None:
        """What the recording made, kept now (the files written back, the clips, the MP3), so a turn
        that later stops or fails loses none of it: the coach designed for it, above all, paid for once."""
        try:
            changes = folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK)
            conflicts = set(store.write_back(ctx.conn, ctx.uk, changes, base))
            if clips is not None:
                clipcache.save(ctx.conn, ctx.uk, ctx.home, clips)
            ctx.conn.commit()
        except Exception as e:  # noqa: BLE001 - the turn's own save at the end tries again
            ctx.conn.rollback()
            print(f"worker: job {ctx.job_id} checkpoint failed: {type(e).__name__}", file=sys.stderr)
            return
        for path, body in changes.items():   # what the end of the turn compares against from here on
            if path in conflicts:
                continue
            if body is None:
                written.pop(path, None)
                base.pop(path, None)
            else:
                written[path] = folder.digest(body)
                base[path] = base.get(path, 0) + 1
        if clips is not None:
            clips.update(clipcache.current(ctx.home))
        kept.extend(_keep_audio(ctx, written, kept_paths))
    deps.checkpoint = checkpoint
    ctx.say("thinking")
    first = conv.history is None
    background = ThreadPoolExecutor(max_workers=1)
    sheet = os.path.join(ctx.home, "workouts", "research", "daily", f"{today}-feeds.md")
    # the check-in is answered (or, a set-up listener's workout request from the page's sentence, needs none):
    # research begins now, while the model reads
    begin = not first or (agent.intent(line) == "workout" and not agent.needs_setup(ctx.home))
    if begin and not os.path.exists(sheet):
        deps.feeds = agent.start_feeds(deps, background)
    try:
        context = None
        if first and line:
            try:
                context = agent.prefetch(deps, line)
            except Exception as e:  # noqa: BLE001 - without it the model reads step 1 itself
                print(f"worker: job {ctx.job_id} prefetch failed: {type(e).__name__}", file=sys.stderr)
        if deps.later and not deps.scheduled_run and first:   # the page's picked time, said plainly for the check-in
            note = (f"This workout is for later: {api_when(deps.later.get('local', ''))}, the listener's time. Do the "
                    "check-in now; once nothing's left to ask, call schedule_workout and end your turn with the plan "
                    "in a line. The brief, the research and the script come fifteen minutes before their time.")
            context = f"{context}\n\n{note}" if context else note
        began = time.monotonic()
        outcome = agent.run_turn(model, deps, conv.history, line, answer, context=context)
        u = outcome.usage
        print(f"worker: job {ctx.job_id} turn {time.monotonic() - began:.1f}s, {u.get('requests')} model requests, "
              f"{u.get('input_tokens')} tokens in, {u.get('output_tokens')} out, {u.get('searches', 0)} web searches",
              file=sys.stderr, flush=True)
    except agent.TurnError as e:
        raise _Stop({agent.NOT_OPEN: ANSWER_NOT_OPEN, agent.TIMED_OUT: TOO_LONG,
                     agent.STOPPED: STOPPED}.get(e.reason, CANT_FINISH)) from None
    except UsageLimitExceeded:
        raise _Stop(TOO_LONG) from None
    except Exception as e:  # noqa: BLE001 - a provider's failure; only explain's words go anywhere
        print(f"worker: job {ctx.job_id} turn stopped: {type(e).__name__}", file=sys.stderr)
        raise _Stop(providers.explain(provider, e).message) from None
    finally:
        background.shutdown(wait=True)   # feeds writes into the folder: done before it's harvested or removed

    if clips is not None:
        clipcache.save(ctx.conn, ctx.uk, ctx.home, clips)
        ctx.conn.commit()
    lines = conv.lines if outcome.reply is None else _agent_line(conv, outcome.reply)
    kept.extend(_keep_audio(ctx, written, kept_paths))
    for audio in kept:
        lines = lines + [{"role": "agent", "text": "", "audio": audio}]
    later = conv.later
    if deps.schedule and not deps.scheduled_run:   # the check-in is done: the plan's estimate, for Schedule it
        later = dict(conv.later or {}, **deps.schedule)
    elif deps.scheduled_run:   # written (and recorded, or priced for the Record button): the page opens it on return
        later = dict({k: v for k, v in (conv.later or {}).items() if k in ("at", "local", "due")}, done=True)
    done = dataclasses.replace(conv, state="waiting" if outcome.question else "idle", later=later,
                               history=outcome.history_json, lines=lines, question=outcome.question,
                               plan=outcome.plan, stem=outcome.stem, offer=deps.offer,
                               coach=deps.coach and not deps.coach_done)   # as returned: None after a failed brief

    def save_turn() -> None:
        if not conversations.save(ctx.conn, ctx.uk, done, conv.version):
            raise RuntimeError("the conversation moved on")   # complete rolls back; the job fails

    ctx.on_done = save_turn
    ctx.on_lost = lambda error: _fail_conversation(ctx, conv, error, kept)
    ctx.save(folder.harvest(ctx.home, written, never=NEVER_WRITE_BACK), base)
    return {"conversation_id": conv.id, "state": done.state}


HANDLERS: dict[str, Callable[[Ctx], dict]] = {"brief": brief, "turn": turn, "balances": balances, "enrich": enrich}


# ---- the loop ---------------------------------------------------------------------------------

class _Heartbeat(threading.Thread):
    """Marks one job alive every HEARTBEAT_EVERY seconds, on a connection of its own. `lost` is set
    when the job was no longer running or the heartbeat couldn't be written: the job may have been
    reaped, so its files are not written back."""

    def __init__(self, connect: Callable[[], Any], job_id: int, cancel: threading.Event | None = None):
        super().__init__(daemon=True, name=f"heartbeat-{job_id}")
        self.connect, self.job_id = connect, job_id
        self.halt, self.lost = threading.Event(), threading.Event()
        self.cancel = cancel if cancel is not None else threading.Event()   # set when the listener presses Stop

    def run(self) -> None:
        conn = None
        try:
            conn = self.connect()
            waited, step = 0.0, min(STOP_POLL, HEARTBEAT_EVERY)
            while not self.halt.wait(step):
                waited += step
                if not self.cancel.is_set() and jobs.stop_requested(conn, self.job_id):
                    self.cancel.set()
                if waited >= HEARTBEAT_EVERY:
                    waited = 0.0
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


def run_one(conn, settings: config.Settings, connect: Callable[[], Any] | None = None, lane: str = "main") -> bool:
    """Reap stale jobs, claim one in `lane` and run it; whether a job ran. `connect` opens the heartbeat's
    own connection (default: settings.database_url). Only the main lane reaps and sweeps."""
    _uv_cache()
    connect = connect or (lambda: psycopg.connect(settings.database_url, connect_timeout=CONNECT_TIMEOUT))
    if lane == "main":
        jobs.reap(conn)
        media.sweep(conn)
        clipcache.prune(conn)
    job = jobs.claim(conn, lane)
    if job is None:
        return False
    cancel = threading.Event()
    beat = _Heartbeat(connect, job.id, cancel)
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
        ctx = Ctx(conn=conn, uk=uk, job_id=job.id, args=args, settings=settings, home=home, cancel=cancel)
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
    # enrichment's own lane: a second loop, so working out what feedback teaches never waits behind a workout
    side = threading.Thread(target=_side_lane, args=(settings, stopping, "enrich"), daemon=True, name="enrich-lane")
    side.start()
    serve(settings, stopping)
    side.join(timeout=ENRICH_TIMEOUT)
    return 0


def _side_lane(settings: config.Settings, stopping: threading.Event, lane: str) -> None:
    """A lane's loop, run again after anything that stops it (logged, by type), until `stopping`: the main loop's
    stop ends the process and Fly restarts it, but a side lane that died alone would leave its jobs queued."""
    while not stopping.is_set():
        try:
            serve(settings, stopping, lane=lane)
        except Exception as e:  # noqa: BLE001 - only the type: the message may be personal
            print(f"worker: the {lane} lane stopped ({type(e).__name__}); starting it again", file=sys.stderr,
                  flush=True)
            stopping.wait(RECONNECT_WAIT)


def serve(settings: config.Settings, stopping: threading.Event, connect: Callable[[config.Settings], tuple] | None = None,
          run: Callable[..., bool] | None = None, lane: str = "main") -> None:
    """Run jobs until `stopping` is set, waiting on NOTIFY between them. When the database closes the
    connection (it does, about hourly), it reconnects rather than exiting; a job running then fails as
    any interrupted job does."""
    connect = connect or _connect
    run = run or run_one
    conn = listen = None
    try:
        while not stopping.is_set():
            try:
                if conn is None:
                    conn, listen = connect(settings)
                if run(conn, settings, **({"lane": lane} if lane != "main" else {})):
                    continue
                for _ in listen.notifies(timeout=IDLE_WAIT, stop_after=1):
                    pass
            except psycopg.OperationalError as e:   # the database closed the connection (it does, about hourly)
                print(f"worker: lost the database ({type(e).__name__}); reconnecting", file=sys.stderr, flush=True)
                _close(conn, listen)
                conn = listen = None
                stopping.wait(RECONNECT_WAIT)
    finally:
        _close(conn, listen)


def _connect(settings: config.Settings) -> tuple:
    """The worker's connection and its listening one (autocommit, on jobs_queued)."""
    conn = db.connect(settings.database_url)
    try:
        listen = psycopg.connect(settings.database_url, autocommit=True, connect_timeout=CONNECT_TIMEOUT)
        listen.execute("listen jobs_queued")
    except BaseException:
        conn.close()
        raise
    return conn, listen


def _close(*conns) -> None:
    for c in conns:
        if c is not None:
            try:
                c.close()
            except Exception:  # noqa: BLE001 - a dead connection may not close cleanly
                pass


if __name__ == "__main__":
    sys.exit(main())
