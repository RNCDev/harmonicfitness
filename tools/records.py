"""builds.jsonl: one record per MP3 (and a failed line for a web render that sent text and then stopped, and an
outcome line for each full build), written under the file's lock and read back by log-session (a session is
logged against a build of its draft as it stands) and get web-builds.

Every line written since 0.19.0 names its kind: "mp3", "failed" or "outcome". A line from before then has none,
and parse() infers it from the fields it has ("event": an outcome; "failed": a failed render; else an MP3), so
an old me/ folder reads the same and is never rewritten. A line whose fields have the wrong type (a hand edit)
is skipped, so it can't change what get web-builds counts or which build log-session links to."""
import datetime as dt
import hashlib
import json
import os
import sys
from typing import Iterator, Literal, Optional, TypedDict, Union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
import redact  # noqa: E402
import services  # noqa: E402  (services.toml's reader, not the HTTP engine in cloud.py)

KINDS = ("mp3", "failed", "outcome")


class Mp3Record(TypedDict, total=False):
    """An MP3 made (render.build_record's fields, with the route, build_id, check and timings)."""
    kind: Literal["mp3"]
    out: str
    draft: str
    draft_sha256: str   # required
    voice: str
    route: str
    build_id: str
    drift: float


class FailedRecord(TypedDict, total=False):
    """A web render that sent text and then stopped: no MP3."""
    kind: Literal["failed"]
    failed: bool   # required, True (kept for engines before 0.19.0, which read no kind)
    out: str
    draft: str
    draft_sha256: Optional[str]   # required
    voice: str
    route: Optional[str]
    chars_sent: int
    chars_rendered: int
    usd_estimate: float
    reason: str
    build_id: str


class OutcomeRecord(TypedDict, total=False):
    """How a full build ended: "stopped", "measured" or "delivered"."""
    kind: Literal["outcome"]
    event: str   # required
    at: str
    build_id: str
    name: str
    stage: str
    reason: str


Record = Union[Mp3Record, FailedRecord, OutcomeRecord]

_NONE = type(None)
_NUM = (int, float)
REQUIRED = {"mp3": ("draft_sha256",), "failed": ("failed", "draft_sha256"), "outcome": ("event",)}
TYPES = {"kind": str, "event": str, "failed": bool, "draft_sha256": (str, _NONE), "route": (str, _NONE),
         "build_id": (str, _NONE), "voice": (str, _NONE), "out": (str, _NONE), "draft": (str, _NONE),
         "chars_sent": int, "chars_rendered": int, "usd_estimate": _NUM, "drift": _NUM}


def _kind(rec):
    """The kind a line from before 0.19.0 was, from the fields it has (as is_mp3 and web_builds told them apart)."""
    if rec.get("event"):
        return "outcome"
    if rec.get("failed"):
        return "failed"
    return "mp3"


def parse(obj) -> Optional[Record]:
    """A builds.jsonl line (str or bytes) or the dict it holds, as a record with its `kind`, or None when it
    can't be one: not a JSON object, a kind that isn't one, a required field missing, a field of the wrong type,
    or a kind its fields contradict (an "mp3" that says it failed). A line with no kind gets the one it implies."""
    rec = obj if isinstance(obj, dict) else fileio.jsonl_record(obj)
    if rec is None:
        return None
    for key, types in TYPES.items():
        if key in rec:
            value = rec[key]
            if not isinstance(value, types) or (isinstance(value, bool) and types is not bool):
                return None
    implied = _kind(rec)
    kind = rec.get("kind", implied)
    if kind != implied or kind not in KINDS:
        return None
    if any(key not in rec for key in REQUIRED[kind]) or (kind == "failed" and rec["failed"] is not True):
        return None
    return rec if "kind" in rec else {"kind": kind, **rec}


def save_build_record(record, out, log=None):
    """Write <out>.build.json beside the MP3 and append the record to builds.jsonl, as kind "mp3"."""
    log = log or paths.BUILDS
    fileio.atomic_write(os.path.splitext(out)[0] + ".build.json", json.dumps(record, indent=1) + "\n")
    fileio.append_jsonl(log, {"kind": "mp3", **record})


def save_failed_record(voice, out, draft_path, draft_sha256, sent, started, error, build_id=None):
    """A cloud render that stopped partway: one line in builds.jsonl with the characters already sent, of kind
    "failed" (no MP3, no <name>.build.json). A reader counting MP3s skips it."""
    if isinstance(error, SystemExit):
        reason = str(error.code) if not isinstance(error.code, int) else f"exit {error.code}"
    elif isinstance(error, errors.SweatcastError):
        reason = str(error)
    else:
        reason = type(error).__name__ + (f": {error}" if str(error) else "")
    usd = services.estimate(voice["service"], voice["model"], ["x" * sent["started"]])[1]
    record = {"kind": "failed", "failed": True, "out": paths.show(os.path.abspath(out)),
              "draft": paths.show(os.path.abspath(draft_path)), "draft_sha256": draft_sha256,
              "voice": voice["name"], "voice_key": voice["key"], "engine": voice["engine"], "model": voice["model"],
              "route": voice.get("route"), "chars_sent": sent["started"], "chars_rendered": sent["chars"],
              "usd_estimate": round(usd, 4), "reason": redact.scrub(reason)[:300],
              "started_at": dt.datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds")}
    if build_id:
        record["build_id"] = build_id
    try:
        fileio.append_jsonl(paths.BUILDS, record)
    except OSError as e:   # the failure being reported matters more than this line
        print(f"(Couldn't note the failed render in {paths.show(paths.BUILDS)}: {e})", file=sys.stderr)


def draft_hash(path):
    """sha256 of a draft as the build hashes it: read as text (so line endings are \\n), encoded as UTF-8."""
    with open(path, encoding="utf-8") as f:
        return hashlib.sha256(f.read().encode("utf-8")).hexdigest()


def build_records(log=None) -> Iterator[Record]:
    """Every record in builds.jsonl, oldest first, each with its kind: one per MP3, a "failed" one for a web
    render that sent text and stopped, and an "outcome" one per full build. A damaged line, or one parse()
    refuses, is skipped."""
    return fileio.read_jsonl(log or paths.BUILDS, parse)


def note(event, **fields):
    """An outcome line in builds.jsonl beside the MP3 records, one per full build: "stopped" (at the stage it
    reached, with why: the coach, the pace, the lint, the menu, the design, the render, a total off plan, the web
    copy or the delivery), "measured" (the smoke test) or "delivered" (where the MP3 went). Each carries the build's build_id, as its
    record, its failed line and its log header do, so one build can be followed through all of them. Readers
    that count MP3s skip outcome lines. A line that can't be written never stops the build."""
    try:
        fileio.append_jsonl(paths.BUILDS, {"kind": "outcome", "event": event, "at": dt.datetime.now().astimezone().isoformat(
            timespec="seconds"), **{k: v for k, v in fields.items() if v is not None and k != "kind"}})
    except OSError as e:
        print(f"(Couldn't note the build's outcome in {paths.show(paths.BUILDS)}: {e})", file=sys.stderr)


def is_mp3(rec):
    """A record of an MP3 made (not a failed web render's line, nor an outcome line, nor one parse() refuses)."""
    rec = parse(rec)
    return rec is not None and rec["kind"] == "mp3"


def built(sha256, log=None):
    """True when builds.jsonl records an MP3 made from a draft with this hash. A failed web render made no
    MP3 and doesn't count; a build that ran off plan (exit 2) did make one, and counts."""
    return latest_build(sha256, log) is not None


def latest_build(sha256, log=None) -> Optional[Mp3Record]:
    """The newest record of an MP3 made from a draft with this hash (not a failed web render, nor an outcome
    line), or None: what log-session --draft links the session to."""
    found = None
    for rec in build_records(log):
        if rec["kind"] == "mp3" and rec.get("draft_sha256") == sha256:
            found = rec
    return found


def web_builds(log=None):
    """How many builds sent a script to a web voice service, failed ones included (the text went out); outcome
    lines aren't builds."""
    names = services.names()
    return sum(rec["kind"] != "outcome" and rec.get("route") in names for rec in build_records(log))
