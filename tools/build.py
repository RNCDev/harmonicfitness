"""One step from draft to deliverables, in one process: lint and export the .txt, check the draft against its
menu, render the .mp3, copy it to the phone.

Run it as ./sweatcast build.

    ./sweatcast build <draft> "<name>" [--coach <name>] [--engine <route>] [--lint-only] [--follow] [--web] [render options]
    ./sweatcast build me/workouts/2026-10-19-bench-25/2026-10-19-bench-25.draft.txt "Workout 2026-10-19 Bench 25 min"

Writes <name>.txt and <name>.mp3 in the draft's workout folder (me/workouts/<stem>/), or in
me/workouts/checks/ for the smoke test and any draft outside one (the context folder is SWEATCAST_HOME
if set). The draft is read once: the lint, the menu check and the render all see the same text, so
nothing can slip in between them. Stops after the lint if it finds issues (fix and rerun). --lint-only
skips rendering. Without --coach, uses the coach used last; without --engine, the first route in the
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
unknown coach, a missing draft, rendering ahead on a cloud voice): fix the command, not the draft. A
default web coach with no voice yet (pending) is made (./sweatcast coaches make) once the lint and the
menu check pass, never with --lint-only. The render's chatter (model loading, errors) goes to me/workouts/.logs/<name>.log, and its
last lines print on a failure.
"""
import contextlib
import datetime as dt
import filecmp
import hashlib
import json
import os
import shutil
import sys
import uuid

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


@contextlib.contextmanager
def log_to(path, name, build_id=None, verbose=False):
    """Send everything written to the standard error descriptor to the build log for the block: the engines'
    native libraries write there, not to Python's sys.stderr, so the descriptor itself is pointed at the log
    (and back afterwards). The log is appended to, with a dated line naming the build, so two builds of one name
    both keep it. With `verbose`, the chatter stays on the terminal and the log gets only that line."""
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


def show_log(log):
    print(f"--- last lines of {log}:", file=sys.stderr)
    with open(log, "rb") as f:
        f.seek(max(0, os.path.getsize(log) - LOG_TAIL))
        tail = f.read().decode("utf-8", "replace")
    print("".join(tail.splitlines(keepends=True)[-20:]), end="", file=sys.stderr)


def deliver(mp3, out_dir):
    """Copy the MP3 to every delivery folder that exists; remove the local one once all match.
    Returns what happened, for the build record: {"delivered_to": [...], "kept_local": bool, "reason": str}."""
    import context
    pattern, found = context.delivery_folders(context.profile())
    if pattern and not found:
        print(f"Delivery folder {pattern} not found.", file=sys.stderr)
    done, failed = [], []
    for dest in found:
        target = os.path.join(dest, os.path.basename(mp3))
        part = target + ".part"   # a synced folder never sees a half-copied MP3 under its real name
        try:
            shutil.copyfile(mp3, part)
            ok = filecmp.cmp(mp3, part, shallow=False)
            if ok:
                os.replace(part, target)
        except OSError:
            ok = False
        finally:
            try:
                if os.path.exists(part):
                    os.remove(part)
            except OSError:
                pass
        if ok:
            done.append(dest)
            print(f"Copied to {dest}/{os.path.basename(mp3)}")
        else:
            failed.append(dest)
            print(f"Couldn't copy to {dest}; the MP3 is in {paths.show(out_dir)}")
    if found and not failed:
        os.remove(mp3)
        print(f"Removed the local copy; the text and build record stay in {paths.show(out_dir)}")
        return {"delivered_to": done, "kept_local": False, "reason": ""}
    if not found:
        print(f"The MP3 is in {paths.show(out_dir)}")
        return {"delivered_to": [], "kept_local": True, "reason": "no delivery folder on this computer"}
    return {"delivered_to": done, "kept_local": True, "reason": "couldn't copy to " + ", ".join(failed)}


def note_in_record(mp3, fields):
    """Merge `fields` into the MP3's <name>.build.json, which the render wrote."""
    path = workouts.record_path(mp3)
    try:
        with open(path, encoding="utf-8") as f:
            rec = json.load(f)
    except (OSError, ValueError) as e:
        print(f"Couldn't add where the MP3 went to {paths.show(path)}: {e}", file=sys.stderr)
        return
    rec.update(fields)
    fileio.atomic_write(path, json.dumps(rec, indent=1) + "\n")


def web_copy(mp3, name, out_dir):
    """The speech-bitrate parts and the player page (tools/webcopy.py). Returns (parts, page)."""
    import webcopy
    parts = webcopy.make(mp3, name, out_dir)
    page = webcopy.page(name, parts, os.path.join(out_dir, f"{name}.player.html"))
    print(f"Web copy: {paths.show(page)}, with " + ", ".join(os.path.basename(p) for p in parts))
    return parts, page


def main(argv=None):
    ap = cli.ArgumentParser(prog="sweatcast build", allow_abbrev=False,
                            description="Lint a draft, check it against its menu, render it and copy the MP3.")
    ap.add_argument("draft", help="the draft (me/workouts/<stem>/<stem>.draft.txt)")
    ap.add_argument("name", help="the MP3's name, such as \"Workout 2026-10-25 Strength 25 min\"")
    ap.add_argument("--coach", help="the coach (default: the one used last, else your own, else a stand-in)")
    ap.add_argument("--engine", help="the route: local, or a web service (default: the coach's own, or the "
                                     "profile's render list)")
    ap.add_argument("--lint-only", action="store_true", help="stop after the lint and the menu check")
    ap.add_argument("--allow-estimated", action="store_true",
                    help="render with a local coach whose pace isn't measured on this route yet")
    ap.add_argument("--follow", action="store_true", help="render ahead while the draft is written (local only)")
    ap.add_argument("--clips-only", action="store_true", help="render the draft's clips into the cache once (local only)")
    ap.add_argument("--idle", type=float, default=None, help="with --follow, stop after this many idle seconds")
    ap.add_argument("--web", action="store_true", help="also make the web copy and player page")
    ap.add_argument("--no-web", action="store_true", help="no web copy, even in a Claude Code cloud session")
    ap.add_argument("--tolerance", type=draft.tolerance_arg, default=draft.TOTAL_TOLERANCE,
                    help="how far the whole workout may run over or under plan, as a fraction (0 to 0.5)")
    ap.add_argument("--seed", type=int, default=42, help="a different seed gives a different take of every line")
    ap.add_argument("--no-chime", action="store_true", help="no bell at each new segment and no end tone")
    ap.add_argument("--no-check", action="store_true",
                    help="don't have the speech recognizer check each local take (a quicker test render)")
    ap.add_argument("--verbose", action="store_true",
                    help="show the engines' loading and rendering chatter here, not only in the build log")
    ap.add_argument("--model", default=None, help="try another model repo for a local coach's engine")
    args = ap.parse_args(argv)
    build_id = uuid.uuid4().hex[:12]   # in the log header, the build record, a failed line and each outcome line
    name = args.name
    if "/" in name or "\\" in name:
        raise cli.Usage(f"The name can't contain a slash: {name}")
    if not os.path.isfile(args.draft):
        raise cli.Usage(f"No draft at {args.draft}")
    if not os.path.isfile(paths.PROFILE):
        raise errors.ContextError(f"No profile at {paths.PROFILE}. Run ./sweatcast setup first (it copies "
                                  "me.example/ to me/).")
    cloud_session = os.environ.get("CLAUDE_CODE_REMOTE") == "true"
    web = (args.web or cloud_session) and not args.no_web
    out_dir = workouts.out_dir(args.draft)
    with open(args.draft, encoding="utf-8") as f:
        text = f.read()
    segments = draft.parse(text)   # the one read: the lint, the menu check and the render all see this text
    smoke = draft.is_smoke(args.draft)

    import catalog
    import context
    import menu
    import personas
    import render
    import routes
    import tts_build
    import voices
    # The coach is the one named, else the one used last (context.py stops here, with the fix, if the
    # context folder needs migrating); the route is the coach's own service, else --engine, else the first
    # in the profile's render list that works here. Resolved once, for the lint and the render alike.
    coach = personas.lookup(args.coach) if args.coach else personas.default()
    if coach is None:
        raise errors.CoachError("No coach found: the ten local coaches ship in coaches/ (git pull), and a web coach "
                                "comes from the coach skill.")
    route = routes.pick(context.render_preferences(), coach, override=args.engine)
    os.makedirs(paths.LOGS, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    log = os.path.join(paths.LOGS, f"{name}.log")

    if args.clips_only or args.follow:
        if route != "local":
            print(f"Rendering ahead is off for a cloud voice ({route}): every re-render would be billed. Run the "
                  "full build once the lint passes.")
            return cli.USAGE
        voice = personas.voice_for(coach, route)
        try:   # rendering ahead while the rest of the draft is written: no lint, no MP3
            with log_to(log, name, build_id, args.verbose):
                if args.follow:
                    render.follow(voice, args.draft, seed=args.seed, **({"idle": args.idle} if args.idle else {}))
                else:
                    render.clips(voice, segments, seed=args.seed)
        except BaseException:
            if not args.verbose:
                show_log(log)
            raise
        return cli.OK

    # A default web coach ships with no voice (pending): the lint and the menu check run first at its
    # estimated pace, and only a draft that passes them has the voice designed and saved (paid), below.
    voice = personas.voice_for(coach, route, pending=bool(coach.pending))
    if not smoke and not args.lint_only and not coach.is_web and not args.allow_estimated and not voices.pace(voice)[1]:
        print(f"{coach.name}'s speaking rate hasn't been measured on {route} yet, so this draft's timing is a guess.\n"
              "Render the smoke test with them first, which measures it, then rerun:\n"
              f'  ./sweatcast build {paths.show(paths.SMOKE_DRAFT)} "smoke-test" --coach "{coach.name}" --engine {route}\n'
              "(or pass --allow-estimated to render anyway)")
        return cli.UNMEASURED

    # The lint, then the menu. The smoke test exists to measure a voice: it needs no menu, and its lint
    # never blocks the render. Every other draft is held to its menu, from today and today's health.md.
    report = tts_build.lint(segments, voice, total_tolerance=args.tolerance, chime=not args.no_chime)
    print("\n".join(tts_build.render_report(report)))
    issues, warnings = ([], []) if smoke else menu.gate(catalog.load(), args.draft, text, segments,
                                                         strict=not args.lint_only)
    if not smoke:
        print("\n".join(menu.report_lines(args.draft, issues, warnings, len(draft.declared(text)))))
    draft_sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

    def stopped(stage, reason):   # a full build's stop, in builds.jsonl (a lint-only run is a writer's check)
        if not args.lint_only:
            import records
            records.note("stopped", build_id=build_id, stage=stage, reason=reason, name=name,
                         draft=paths.show(os.path.abspath(args.draft)), draft_sha256=draft_sha256)
    if issues:
        print(f"\n{len(issues)} menu issue(s). Fix and rerun. Nothing exported.")
        stopped("menu", f"{len(issues)} menu issue(s)")
        return cli.ISSUES
    problems = report.problems
    if problems and not smoke:
        print(f"\n{problems} issue(s). Fix and rerun. Nothing exported.")
        stopped("lint", f"{problems} lint issue(s)")
        return cli.ISSUES
    out_text, count = tts_build.export_text(segments)
    txt = os.path.join(out_dir, f"{name}.txt")
    fileio.atomic_write(txt, out_text)
    print(f"\nExported {count} paragraphs to {paths.show(txt)}" + (f" despite {problems} issue(s)" if problems else ""))
    if args.lint_only:
        return cli.OK
    if coach.pending:   # the draft passed: now the first build that needs this default designs its voice
        import coaches
        coaches.make(coach.name)
        coach = personas.lookup(coach.name)   # the make wrote its voice
        voice = personas.voice_for(coach, route)

    mp3 = os.path.join(out_dir, f"{name}.mp3")
    try:
        with log_to(log, name, build_id, args.verbose):   # model loading is chatty: it goes to the log, shown on
            drift = render.run(segments, voice, mp3, seed=args.seed,  # any failure but drift
                               tolerance=args.tolerance, no_chime=args.no_chime, draft_path=args.draft,
                               draft_sha256=draft_sha256, model=args.model, check=not args.no_check,
                               build_id=build_id)
    except BaseException as e:
        import cloud
        stopped("render", "interrupted" if isinstance(e, KeyboardInterrupt) else cloud.scrub(str(e) or type(e).__name__)[:300])
        if not isinstance(e, KeyboardInterrupt) and not args.verbose:
            show_log(log)
        raise
    if abs(drift) > args.tolerance:   # the MP3 is written, not copied
        print(render.drift_message(drift, args.tolerance))
        return cli.DRIFT
    if smoke:   # a voice check, not a workout: no copy
        return cli.OK
    record = {}
    if web:
        parts, page = web_copy(mp3, name, out_dir)
        record["web"] = {"page": os.path.basename(page), "parts": [os.path.basename(p) for p in parts]}
    if cloud_session and web:   # no folder syncs to a phone from here: the web copy is the delivery
        os.remove(mp3)
        record.update({"delivered_to": [], "kept_local": False,
                       "reason": "a Claude Code cloud session: the web copy and player page are the delivery"})
    elif cloud_session:
        print(f"The MP3 is in {paths.show(out_dir)} (no web copy was asked for, and no folder syncs from here).")
        record.update({"delivered_to": [], "kept_local": True,
                       "reason": "a Claude Code cloud session with --no-web: the MP3 stays in the workout folder"})
    else:
        record.update(deliver(mp3, out_dir))
    note_in_record(mp3, record)
    import records
    records.note("delivered", build_id=build_id, name=name, **{k: record.get(k) for k in
                                                                ("delivered_to", "kept_local", "reason", "web")})
    cache_note()
    return cli.OK


def cache_note():
    """A line when the clip cache has grown large: it's never pruned on its own, since a web coach's clips are
    paid for and a render running ahead may be using them."""
    import cache
    count, size = cache.size()
    if size > CACHE_NOTE:
        print(f"(The clip cache holds {size / (1 << 30):.1f} GB in {count} clips; ./sweatcast cache prune clears "
              "those unused for 45 days.)")


if __name__ == "__main__":
    sys.exit(cli.run(main))
