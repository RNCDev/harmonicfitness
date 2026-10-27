"""One step from draft to deliverables, in one process: lint and export the .txt, check the draft against its
menu, render the .mp3, copy it to the phone.

Run it as ./sweatcast build.

    ./sweatcast build <draft> "<name>" [--coach <name>] [--route <route>] [--lint-only] [--follow] [--web] [render options]
    ./sweatcast build me/workouts/2026-10-19-bench-25/2026-10-19-bench-25.draft.txt "Workout 2026-10-19 Bench 25 min"

Writes <name>.txt and <name>.mp3 in the draft's workout folder (me/workouts/<stem>/), or in
me/workouts/checks/ for the smoke test and any draft outside one (the context folder is SWEATCAST_HOME
if set). The draft is read once: the lint, the menu check and the render all see the same text, so
nothing can slip in between them. Stops after the lint if it finds issues (fix and rerun). --lint-only
skips rendering. Without --coach, uses the coach used last; without --route (or --engine, its older name), the first route in the
profile's render list that works on this computer (local, or a cloud voice with its key in me/.env). After
a render, copies the MP3 to each deliver_to folder that exists and, once every copy matches, removes the
local MP3.

The menu: every draft but the smoke test (knowledge/smoke-test.draft.txt, known by its place) needs the
menu ./sweatcast brief --save wrote beside it, from today and from health.md as it stands; the build stops
on a movement that isn't on it, a menu from another day or one made before health.md changed (--lint-only
only warns about the last two, so a draft can be checked ahead).

--follow renders ahead while the draft is still being written: it keeps the voice model loaded,
renders each new or edited paragraph as it appears in the draft, and stops when the full build starts
(which then renders only what's left), or after --idle seconds with nothing new. --clips-only renders
what the draft holds now, once. Neither lints, writes an MP3 or copies, and neither runs on a cloud
voice, where every re-render would be billed.

--web also makes the web copy: the MP3 at a speech bitrate in parts of at most 14 MB, and a player page
(tools/webcopy.py). It's on by default in a Claude Code cloud session, where it replaces the copy to a
delivery folder (--no-web turns it off, and the MP3 then stays in the workout folder). The build record,
<name>.build.json, says where the MP3 went.

--tolerance <fraction> sets how far the total may run off plan, for the lint and the render alike
(default three percent).

Exit codes (tools/cli.py): 0 done, 1 issues to fix, 2 the rendered total ran more than the tolerance
off plan (the MP3 is written but not copied), 3 the coach's pace hasn't been measured on this route yet
(render the smoke test with them first, which measures it, or pass --allow-estimated), 4 a cloud voice
service refused the key, the payment or the quota, 64 the command was wrong (a mistyped option, an
unknown coach, a missing draft, rendering ahead on a cloud voice): fix the command, not the draft; 70 a
bug in the engine (its traceback goes to stderr and the build log): nothing to fix in the draft. A
default web coach with no voice yet (pending) is made (./sweatcast coaches make) once the lint and the
menu check pass, never with --lint-only. The render's chatter (model loading, errors) goes to
me/workouts/.logs/<name>.log with the engine's own lines, and its last lines print on a failure. Every
full build (not --lint-only, --follow or --clips-only) leaves one outcome line in builds.jsonl.

run_build(BuildOptions(...)) is the same build without a command line.
"""
import contextlib
import dataclasses
import datetime as dt
import filecmp
import hashlib
import json
import os
import shutil
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cli  # noqa: E402
import errors  # noqa: E402
import draft  # noqa: E402
import fileio  # noqa: E402
import paths  # noqa: E402
import workouts  # noqa: E402


LOG_KEEP = 1_000_000   # bytes: a build log past this starts over, its older lines kept once in <name>.log.1
LOG_TAIL = 64_000      # bytes of the log read back to show its last lines on a failure
CACHE_NOTE = 2 << 30   # bytes: past this, a build mentions ./sweatcast cache prune


class _Tee:
    """sys.stdout for a block of the build: what the engine prints reaches the terminal as before and the
    build log too, so the log tells the whole story beside the libraries' chatter."""

    def __init__(self, stream, log):
        self.stream, self.log = stream, log

    def write(self, s):
        n = self.stream.write(s)
        try:
            self.log.write(s)
            self.log.flush()
        except (OSError, ValueError):
            pass
        return n

    def flush(self):
        self.stream.flush()

    def __getattr__(self, attr):   # fileno, isatty, encoding...: the terminal's
        return getattr(self.stream, attr)


@contextlib.contextmanager
def log_to(path, name, build_id=None, verbose=False):
    """Send everything written to the standard error descriptor to the build log for the block: the engines'
    native libraries write there, not to Python's sys.stderr, so the descriptor itself is pointed at the log
    (and back afterwards). What the engine prints (sys.stdout) goes to the terminal and the log alike. The log
    is appended to, with a dated line naming the build, so two builds of one name both keep it. With
    `verbose`, the chatter stays on the terminal, and the log gets that line and the engine's own lines."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        if os.path.getsize(path) > LOG_KEEP:
            os.replace(path, path + ".1")
    except OSError:
        pass
    with open(path, "a", encoding="utf-8") as log:
        log.write(f"--- {dt.datetime.now().isoformat(timespec='seconds')} build {name}"
                  + (f" ({build_id})" if build_id else "") + "\n")
        log.flush()
        saved_out = sys.stdout
        sys.stdout = _Tee(saved_out, log)
        try:
            if verbose:
                yield
                return
            sys.stderr.flush()
            saved = os.dup(2)
            try:
                os.dup2(log.fileno(), 2)
                yield
            finally:
                try:
                    sys.stderr.flush()
                except (OSError, ValueError):
                    pass
                os.dup2(saved, 2)
                os.close(saved)
        finally:
            sys.stdout = saved_out


def show_log(log):
    print(f"--- last lines of {log}:", file=sys.stderr)
    with open(log, "rb") as f:
        f.seek(max(0, os.path.getsize(log) - LOG_TAIL))
        tail = f.read().decode("utf-8", "replace")
    print("".join(tail.splitlines(keepends=True)[-20:]), end="", file=sys.stderr)


def delivery_plan(remote, web, deliver_to):
    """Where a finished MP3 goes, decided from where the build runs (`remote`: Claude Code on the web), whether
    a web copy was made and the delivery folders found here. Pure: {"copy_to": folders to copy into,
    "remove_local": whether to remove the MP3 now, "record": the record's delivery fields when no copy is made
    (None when the copies decide them), "note": what to tell the listener, with {out} for the workout folder}."""
    if remote and web:   # no folder syncs to a phone from there: the web copy is the delivery
        return {"copy_to": [], "remove_local": True, "note": None,
                "record": {"delivered_to": [], "kept_local": False,
                           "reason": "a Claude Code cloud session: the web copy and player page are the delivery"}}
    if remote:
        return {"copy_to": [], "remove_local": False,
                "note": "The MP3 is in {out} (no web copy was asked for, and no folder syncs from here).",
                "record": {"delivered_to": [], "kept_local": True,
                           "reason": "a Claude Code cloud session with --no-web: the MP3 stays in the workout folder"}}
    if not deliver_to:
        return {"copy_to": [], "remove_local": False, "note": "The MP3 is in {out}",
                "record": {"delivered_to": [], "kept_local": True, "reason": "no delivery folder on this computer"}}
    return {"copy_to": list(deliver_to), "remove_local": False, "note": None, "record": None}


def deliver(mp3, out_dir, folders, say=print):
    """Copy the MP3 into every delivery folder in `folders`; remove the local one once all match.
    Returns what happened, for the build record: {"delivered_to": [...], "kept_local": bool, "reason": str},
    the reason naming each folder that failed and why (a full disk, a permission, an offline sync folder)."""
    done, failed = [], []
    for dest in folders:
        target = os.path.join(dest, os.path.basename(mp3))
        part = target + ".part"   # a synced folder never sees a half-copied MP3 under its real name
        why = ""
        try:
            shutil.copyfile(mp3, part)
            ok = filecmp.cmp(mp3, part, shallow=False)
            if ok:
                os.replace(part, target)
            else:
                why = "the copy didn't match"
        except OSError as e:
            ok, why = False, e.strerror or str(e) or type(e).__name__
        finally:
            try:
                if os.path.exists(part):
                    os.remove(part)
            except OSError:
                pass
        if ok:
            done.append(dest)
            say(f"Copied to {dest}/{os.path.basename(mp3)}")
        else:
            failed.append(f"{dest}: {why}")
            say(f"Couldn't copy to {dest}: {why}; the MP3 is in {paths.show(out_dir)}")
    if folders and not failed:
        os.remove(mp3)
        say(f"Removed the local copy; the text and build record stay in {paths.show(out_dir)}")
        return {"delivered_to": done, "kept_local": False, "reason": ""}
    if not folders:
        say(f"The MP3 is in {paths.show(out_dir)}")
        return {"delivered_to": [], "kept_local": True, "reason": "no delivery folder on this computer"}
    return {"delivered_to": done, "kept_local": True, "reason": "couldn't copy to " + ", ".join(failed)}


def note_in_record(mp3, fields):
    """Merge `fields` into the MP3's <name>.build.json, which the render wrote. Returns the record, or None
    when it can't be read."""
    path = workouts.record_path(mp3)
    try:
        rec = fileio.read_json(path)
    except (OSError, errors.ContextError) as e:
        print(f"Couldn't add where the MP3 went to {paths.show(path)}: {e}", file=sys.stderr)
        return None
    rec.update(fields)
    fileio.atomic_write(path, json.dumps(rec, indent=1) + "\n")
    return rec


def web_copy(mp3, name, out_dir, say=print):
    """The speech-bitrate parts and the player page (tools/webcopy.py). Returns (parts, page)."""
    import webcopy
    parts = webcopy.make(mp3, name, out_dir)
    page = webcopy.page(name, parts, os.path.join(out_dir, f"{name}.player.html"))
    say(f"Web copy: {paths.show(page)}, with " + ", ".join(os.path.basename(p) for p in parts))
    return parts, page


@dataclass(frozen=True)
class BuildOptions:
    """One build's flags, as ./sweatcast build takes them (see the module's docstring)."""
    draft: str
    name: str
    coach: Optional[str] = None
    engine: Optional[str] = None
    lint_only: bool = False
    allow_estimated: bool = False
    follow: bool = False
    clips_only: bool = False
    idle: Optional[float] = None
    web: bool = False
    no_web: bool = False
    tolerance: float = draft.TOTAL_TOLERANCE
    seed: int = 42
    no_chime: bool = False
    no_check: bool = False
    verbose: bool = False
    model: Optional[str] = None

    @property
    def full(self):
        """A build meant to make an MP3: each one leaves exactly one outcome line in builds.jsonl. A lint-only
        run is a writer's check, and rendering ahead makes no MP3."""
        return not (self.lint_only or self.follow or self.clips_only)

    @classmethod
    def from_args(cls, args):
        return cls(**{f.name: getattr(args, f.name) for f in dataclasses.fields(cls)})


@dataclass
class BuildResult:
    """What a build ended with: its exit code, the MP3's build record as delivered (None when no MP3 was made
    or its record can't be read) and every line it said, in order (printed as they were said)."""
    code: int
    record: Optional[dict] = None
    lines: List[str] = field(default_factory=list)


class _Trail:
    """One build's state as it runs: its id, the stage it's at and its outcome line. Every exit of a full build
    leaves exactly one outcome line in builds.jsonl ("stopped", "measured" or "delivered"), carrying its
    build_id, as its record, its failed line and its log header do."""

    def __init__(self, opts, say, log, draft_sha256, fail=None):
        self.opts, self.log, self.draft_sha256 = opts, log, draft_sha256
        self.build_id = uuid.uuid4().hex[:12]
        self.stage = "start"
        self.lines = []
        self.noted = False
        self._say = say
        self._fail = fail or say

    def say(self, line=""):
        self.lines.append(line)
        self._say(line)

    def fail(self, line):
        """The line that says why the build stopped: on stderr from the command line (cli.run's rule for every
        failure summary), in the lines all the same."""
        self.lines.append(line)
        self._fail(line)

    def note(self, event, **fields):
        if self.opts.full and not self.noted:
            import records
            records.note(event, build_id=self.build_id, name=self.opts.name, **fields)
        self.noted = True

    def stopped(self, reason, stage=None, **fields):
        self.note("stopped", stage=stage or self.stage, reason=reason, draft=paths.show(os.path.abspath(
            self.opts.draft)), draft_sha256=self.draft_sha256, **fields)

    def crashed(self, e):
        """Any exception, at any stage: its traceback (a bug's) or its message into the build log, the stop in
        builds.jsonl, and the log's end shown after a failed render."""
        import redact
        interrupted = isinstance(e, KeyboardInterrupt)
        known = isinstance(e, SystemExit) or getattr(e, "exit_code", None) is not None
        reason = "interrupted" if interrupted else redact.scrub(str(e) or type(e).__name__)[:300]
        try:
            os.makedirs(os.path.dirname(self.log), exist_ok=True)
            with open(self.log, "a", encoding="utf-8") as f:
                f.write(f"--- build {self.opts.name} ({self.build_id}) stopped at {self.stage}: {reason}\n"
                        + ("" if known or interrupted else redact.scrub(traceback.format_exc())))
        except OSError:
            pass
        self.stopped(reason)
        ahead = self.opts.follow or self.opts.clips_only
        if not self.opts.verbose and os.path.exists(self.log) and (
                ahead or (self.stage == "render" and not interrupted)):
            show_log(self.log)


def resolve_voice(opts):
    """(coach, route) for the build: the coach named, else the one used last (context.py stops here, with the
    fix, if the context folder needs migrating); the route the coach's own service, else --engine, else the
    first in the profile's render list that works here. Resolved once, for the lint and the render alike."""
    import coachpick
    import context
    coach = coachpick.coach(opts.coach)
    if coach is None:
        raise errors.CoachError("No coach found: the ten local coaches ship in coaches/ (git pull), and a web coach "
                                "comes from the coach skill.")
    return coach, coachpick.pick(context.render_preferences(), coach, override=opts.engine)


def gate(segments, voice, opts, text, smoke):
    """(issues, warnings, report): the lint's report for `voice`, and the menu check's issues and warnings. The
    smoke test exists to measure a voice: it needs no menu. Every other draft is held to its menu, from today
    and today's health.md (a lint-only run only warns about the menu's date and health.md)."""
    import catalog
    import menu
    import tts_build
    report = tts_build.lint(segments, voice, total_tolerance=opts.tolerance, chime=not opts.no_chime)
    issues, warnings = ([], []) if smoke else menu.gate(catalog.default(), opts.draft, text, segments,
                                                         strict=not opts.lint_only)
    return issues, warnings, report


def run_build(opts, say=print, fail=None):
    """Lint, check against the menu, render and deliver one draft (see the module's docstring). Returns a
    BuildResult; a stop the listener or the writer must act on is raised, as cli.run maps it, after the build's
    outcome line is written. `say` takes the report's lines and `fail` the one saying why it stopped (default:
    stderr when `say` is print, else `say`)."""
    name = workouts.safe_name(opts.name)   # before any path is joined from it (exit 64)
    out = os.path.abspath(workouts.out_dir(opts.draft))
    if os.path.dirname(os.path.abspath(os.path.join(out, f"{name}.mp3"))) != out:
        raise errors.UsageError(f"The name would write outside {paths.show(out)}: {name!r}")
    if not os.path.isfile(opts.draft):
        raise errors.UsageError(f"No draft at {opts.draft}")
    if not os.path.isfile(paths.PROFILE):
        raise errors.ContextError(f"No profile at {paths.PROFILE}. Run ./sweatcast setup first (it copies "
                                  "me.example/ to me/).")
    with open(opts.draft, encoding="utf-8") as f:
        text = f.read()   # the one read: the lint, the menu check and the render all see this text
    if fail is None:
        fail = (lambda line: print(line, file=sys.stderr)) if say is print else say
    b = _Trail(opts, say, os.path.join(paths.LOGS, f"{name}.log"), hashlib.sha256(text.encode("utf-8")).hexdigest(),
               fail)
    try:
        return _run(b, text)
    except BaseException as e:
        try:
            b.crashed(e)
        except Exception:   # noting the stop must never hide what stopped it
            pass
        raise


def _run(b, text):
    opts = b.opts
    b.stage = "parse"
    segments = draft.parse(text)
    smoke = draft.is_smoke(opts.draft)
    out_dir = workouts.out_dir(opts.draft)

    import personas
    import render
    import tts_build
    import voices
    b.stage = "coach"
    coach, route = resolve_voice(opts)
    os.makedirs(paths.LOGS, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    if opts.clips_only or opts.follow:
        if route != "local":
            b.fail(f"Rendering ahead is off for a cloud voice ({route}): every re-render would be billed. Run the "
                  "full build once the lint passes.")
            return BuildResult(cli.USAGE, None, b.lines)
        b.stage = "render-ahead"
        voice = personas.voice_for(coach, route)
        with log_to(b.log, opts.name, b.build_id, opts.verbose):   # no lint, no MP3
            if opts.follow:
                render.follow(voice, opts.draft, seed=opts.seed, **({"idle": opts.idle} if opts.idle else {}))
            else:
                render.clips(voice, segments, seed=opts.seed)
        return BuildResult(cli.OK, None, b.lines)

    # A default web coach ships with no voice (pending): the lint and the menu check run first at its
    # estimated pace, and only a draft that passes them has the voice designed and saved (paid), below.
    b.stage = "pace"
    voice = personas.voice_for(coach, route, pending=bool(coach.pending))
    if not smoke and not opts.lint_only and not coach.is_web and not opts.allow_estimated and not voices.pace(voice)[1]:
        b.fail(f"{coach.name}'s speaking rate hasn't been measured on {route} yet, so this draft's timing is a guess.\n"
              "Render the smoke test with them first, which measures it, then rerun:\n"
              f'  ./sweatcast build {paths.show(paths.SMOKE_DRAFT)} "smoke-test" --coach "{coach.name}" --engine {route}\n'
              "(or pass --allow-estimated to render anyway)")
        b.stopped(f"{coach.name} isn't measured on {route}")
        return BuildResult(cli.UNMEASURED, None, b.lines)

    b.stage = "lint"
    issues, warnings, report = gate(segments, voice, opts, text, smoke)
    b.say("\n".join(tts_build.render_report(report)))
    if not smoke:
        import menu
        b.say("\n".join(menu.report_lines(opts.draft, issues, warnings, len(draft.declared(text)))))
    if issues:
        b.fail(f"\n{len(issues)} menu issue(s). Fix and rerun. Nothing exported.")
        b.stopped(f"{len(issues)} menu issue(s)", stage="menu")
        return BuildResult(cli.ISSUES, None, b.lines)
    problems = report.problems
    if problems and not smoke:
        b.fail(f"\n{problems} issue(s). Fix and rerun. Nothing exported.")
        b.stopped(f"{problems} lint issue(s)", stage="lint")
        return BuildResult(cli.ISSUES, None, b.lines)
    b.stage = "export"
    out_text, count = tts_build.export_text(segments)
    txt = os.path.join(out_dir, f"{opts.name}.txt")
    fileio.atomic_write(txt, out_text)
    b.say(f"\nExported {count} paragraphs to {paths.show(txt)}" + (f" despite {problems} issue(s)" if problems else ""))
    if opts.lint_only:
        return BuildResult(cli.OK, None, b.lines)
    if coach.pending:   # the draft passed: now the first build that needs this default designs its voice
        b.stage = "design"
        import coaches
        with log_to(b.log, opts.name, b.build_id, opts.verbose):
            coaches.make(coach.name, report=lambda line: b.say("  " + line))
        coach = personas.lookup(coach.name)   # the make wrote its voice
        voice = personas.voice_for(coach, route)
    return render_and_deliver(b, segments, voice, out_dir, smoke)


def render_and_deliver(b, segments, voice, out_dir, smoke):
    """Render the MP3, then: a total off plan stops here (written, not copied), the smoke test is measured and
    kept, and a workout gets its web copy and goes where delivery_plan says. Returns the BuildResult."""
    import render
    opts = b.opts
    b.stage = "render"
    mp3 = os.path.join(out_dir, f"{opts.name}.mp3")
    with log_to(b.log, opts.name, b.build_id, opts.verbose):   # model loading is chatty: it goes to the log,
        drift = render.run(segments, voice, mp3, seed=opts.seed,  # shown on any failure but drift
                           tolerance=opts.tolerance, no_chime=opts.no_chime, draft_path=opts.draft,
                           draft_sha256=b.draft_sha256, model=opts.model, check=not opts.no_check,
                           build_id=b.build_id)
    if abs(drift) > opts.tolerance:   # the MP3 is written, not copied
        b.fail(render.drift_message(drift, opts.tolerance))
        b.stopped(f"{drift:+.1%} of plan", stage="drift", drift=round(drift, 4))
        return BuildResult(cli.DRIFT, None, b.lines)
    if smoke:   # a voice check, not a workout: no copy
        b.note("measured", voice=voice.get("name"), route=voice.get("route", "local"), drift=round(drift, 4))
        return BuildResult(cli.OK, None, b.lines)
    web = (opts.web or paths.REMOTE) and not opts.no_web
    record = {}
    if web:
        b.stage = "web-copy"
        parts, page = web_copy(mp3, opts.name, out_dir, say=b.say)
        record["web"] = {"page": os.path.basename(page), "parts": [os.path.basename(p) for p in parts]}
    b.stage = "deliver"
    folders = []
    if not paths.REMOTE:
        import context
        pattern, folders = context.delivery_folders(context.profile())
        if pattern and not folders:
            print(f"Delivery folder {pattern} not found.", file=sys.stderr)
    plan = delivery_plan(paths.REMOTE, web, folders)
    if plan["remove_local"]:
        os.remove(mp3)
    if plan["note"]:
        b.say(plan["note"].format(out=paths.show(out_dir)))
    record.update(plan["record"] if plan["record"] is not None else deliver(mp3, out_dir, plan["copy_to"], say=b.say))
    rec = note_in_record(mp3, record)
    b.note("delivered", **{k: record.get(k) for k in ("delivered_to", "kept_local", "reason", "web")})
    b.stage = "done"
    cache_note(say=b.say)
    return BuildResult(cli.OK, rec, b.lines)


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast build", allow_abbrev=False,
                            description="Lint a draft, check it against its menu, render it and copy the MP3.")
    ap.add_argument("draft", help="the draft (me/workouts/<stem>/<stem>.draft.txt)")
    ap.add_argument("name", help="the MP3's name, such as \"Workout 2026-10-25 Strength 25 min\"")
    ap.add_argument("--coach", help="the coach (default: the one used last, else your own, else a stand-in)")
    ap.add_argument("--route", "--engine", dest="engine", metavar="ROUTE",
                    help="the route: local, or a web service (default: the coach's own, or the profile's render "
                         "list); --engine is the older name")
    ap.add_argument("--lint-only", action="store_true", help="stop after the lint and the menu check")
    ap.add_argument("--allow-estimated", action="store_true",
                    help="render with a local coach whose pace isn't measured on this route yet")
    ap.add_argument("--follow", action="store_true", help="render ahead while the draft is written (local only)")
    ap.add_argument("--clips-only", action="store_true", help="render the draft's clips into the cache once (local only)")
    ap.add_argument("--idle", type=cli.positive_float, default=None, help="with --follow, stop after this many idle seconds")
    ap.add_argument("--web", action="store_true", help="also make the web copy and player page")
    ap.add_argument("--no-web", action="store_true", help="no web copy, even in a Claude Code cloud session")
    ap.add_argument("--tolerance", type=draft.tolerance_arg, default=draft.TOTAL_TOLERANCE,
                    help="how far the whole workout may run over or under plan, as a fraction (0 to 0.5)")
    ap.add_argument("--seed", type=cli.non_negative_int, default=42, help="a different seed gives a different take of every line")
    ap.add_argument("--no-chime", action="store_true", help="no bell at each new segment and no end tone")
    ap.add_argument("--no-check", action="store_true",
                    help="don't have the speech recognizer check each local take (a quicker test render)")
    ap.add_argument("--verbose", action="store_true",
                    help="show the engines' loading and rendering chatter here, not only in the build log")
    ap.add_argument("--model", default=None, help="try another model repo for a local coach's engine")
    args = ap.parse_args(argv)
    return run_build(BuildOptions.from_args(args)).code   # each line is printed as it's said


def cache_note(say=print):
    """A line when the clip cache has grown large: it's never pruned on its own, since a web coach's clips are
    paid for and a render running ahead may be using them."""
    import cache
    count, size = cache.size()
    if size > CACHE_NOTE:
        say(f"(The clip cache holds {size / (1 << 30):.1f} GB in {count} clips; ./sweatcast cache prune clears "
              "those unused for 45 days.)")


if __name__ == "__main__":
    sys.exit(cli.run(main))
