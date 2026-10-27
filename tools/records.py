"""builds.jsonl: one record per MP3 (and a failed line for a web render that sent text and then stopped), written
under the file's lock and read back by log-session (a session is logged against a build of its draft as it
stands) and get web-builds."""
import datetime as dt
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import errors  # noqa: E402
import paths  # noqa: E402


def save_build_record(record, out, log=None):
    """Write <out>.build.json beside the MP3 and append the record to builds.jsonl."""
    import fileio
    log = log or paths.BUILDS
    fileio.atomic_write(os.path.splitext(out)[0] + ".build.json", json.dumps(record, indent=1) + "\n")
    fileio.append_jsonl(log, record)


def save_failed_record(voice, out, draft_path, draft_sha256, sent, started, error, build_id=None):
    """A cloud render that stopped partway: one line in builds.jsonl with the characters already sent, marked
    "failed" (no MP3, no <name>.build.json). A reader counting MP3s skips lines with "failed"."""
    import cloud
    if isinstance(error, SystemExit):
        reason = str(error.code) if not isinstance(error.code, int) else f"exit {error.code}"
    elif isinstance(error, errors.SweatcastError):
        reason = str(error)
    else:
        reason = type(error).__name__ + (f": {error}" if str(error) else "")
    usd = cloud.estimate(voice["service"], voice["model"], ["x" * sent["started"]])[1]
    record = {"failed": True, "out": paths.show(os.path.abspath(out)),
              "draft": paths.show(os.path.abspath(draft_path)), "draft_sha256": draft_sha256,
              "voice": voice["name"], "voice_key": voice["key"], "engine": voice["engine"], "model": voice["model"],
              "route": voice.get("route"), "chars_sent": sent["started"], "chars_rendered": sent["chars"],
              "usd_estimate": round(usd, 4), "reason": cloud.scrub(reason)[:300],
              "started_at": dt.datetime.fromtimestamp(started).astimezone().isoformat(timespec="seconds")}
    if build_id:
        record["build_id"] = build_id
    try:
        import fileio
        fileio.append_jsonl(paths.BUILDS, record)
    except OSError as e:   # the failure being reported matters more than this line
        print(f"(Couldn't note the failed render in {paths.show(paths.BUILDS)}: {e})", file=sys.stderr)



def draft_hash(path):
    """sha256 of a draft as the build hashes it: read as text (so line endings are \\n), encoded as UTF-8."""
    with open(path, encoding="utf-8") as f:
        return hashlib.sha256(f.read().encode("utf-8")).hexdigest()


def build_records(log=None):
    """Every record in builds.jsonl, oldest first: one per MP3, and a "failed" one for a web render that sent
    text and stopped. A damaged line is skipped."""
    try:
        with open(log or paths.BUILDS, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    yield rec
    except FileNotFoundError:
        return


def note(event, **fields):
    """An outcome line in builds.jsonl beside the MP3 records: "stopped" (a full build stopped at the lint, the
    menu or the render, with why) or "delivered" (where the MP3 went). Each carries the build's build_id, as its
    record, its failed line and its log header do, so one build can be followed through all of them. Readers
    that count MP3s skip lines with an "event". A line that can't be written never stops the build."""
    import fileio
    try:
        fileio.append_jsonl(paths.BUILDS, {"event": event, "at": dt.datetime.now().astimezone().isoformat(
            timespec="seconds"), **{k: v for k, v in fields.items() if v is not None}})
    except OSError as e:
        print(f"(Couldn't note the build's outcome in {paths.show(paths.BUILDS)}: {e})", file=sys.stderr)


def is_mp3(rec):
    """A record of an MP3 made (not a failed web render's line, nor an outcome line)."""
    return not rec.get("failed") and not rec.get("event")


def built(sha256, log=None):
    """True when builds.jsonl records an MP3 made from a draft with this hash. A failed web render made no
    MP3 and doesn't count; a build that ran off plan (exit 2) did make one, and counts."""
    return any(is_mp3(rec) and rec.get("draft_sha256") == sha256 for rec in build_records(log))


def web_builds(log=None):
    """How many builds sent a script to a web voice service, failed ones included (the text went out)."""
    import cloud
    return sum(rec.get("route") in cloud.SERVICES and not rec.get("event") for rec in build_records(log))
