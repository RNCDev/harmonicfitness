#!/usr/bin/env python3
"""The workouts a listener has logged: list them, leave feedback on one, or delete one.

    ./harmonicfitness workouts                          # newest first, numbered
    ./harmonicfitness workouts --json                   # the same, as JSON (the web's Logs page)
    ./harmonicfitness workouts show 1                   # the script it spoke
    ./harmonicfitness workouts feedback 1 "too long; loved the quiz"
    ./harmonicfitness workouts rate 1 positive          # or neutral, negative, none (clears it)
    ./harmonicfitness workouts delete 1 [--files]       # or a build id, or all

Delete takes a workout back as if it never happened: its line under ## Sessions in me/log.md, the stories it
told (me/workouts/research/told.jsonl, so they can be told again), the threads it opened or closed
(threads.jsonl) and its feedback lines. An item written with the workout's build id goes with it; one from
before 0.40.1 (no build id) goes when no other logged workout shares its date. With --files it also removes
the workout's folder (draft, brief, menu, transcript, build record) and the MP3 copies the build delivered.
builds.jsonl, the record of what each build sent and rendered, is never changed.

A rating is a feedback line, "rated positive" (or neutral or negative), so the coach reads it with the rest;
rating again replaces it.

A workout is named by its number in the list (1 is the newest), its build id, or "all".
"""
import glob
import json
import os
import shutil
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cli  # noqa: E402
import errors  # noqa: E402
import fileio  # noqa: E402
import locks  # noqa: E402
import paths  # noqa: E402
import records  # noqa: E402
import sessionlog  # noqa: E402
from frontmatter import heading, heading_index  # noqa: E402
from store import write  # noqa: E402


def logged():
    """The logged sessions, newest first."""
    return list(reversed(sessionlog.sessions(warn=False)))


def pick(refs: List[str], sessions) -> list:
    """The sessions `refs` name: numbers from the list (1 the newest), build ids, or "all"; UsageError for one
    that names none."""
    if refs == ["all"]:
        return list(sessions)
    out = []
    for ref in refs:
        if ref.isdigit() and 1 <= int(ref) <= len(sessions):
            s = sessions[int(ref) - 1]
        else:
            s = next((x for x in sessions if x.build_id and x.build_id == ref), None)
        if s is None:
            raise errors.UsageError(f"no logged workout '{ref}': give its number from ./harmonicfitness workouts, "
                                    "its build id, or all")
        if s not in out:
            out.append(s)
    return out


def _records_for(build_id):
    """(the MP3 record, [delivered paths]) of a build, from builds.jsonl."""
    mp3, delivered = None, []
    for rec in records.build_records():
        if rec.get("build_id") != build_id:
            continue
        if rec["kind"] == "mp3":
            mp3 = rec
        elif rec["kind"] == "outcome" and rec.get("event") == "delivered":
            # delivered_to names the folders the MP3 was copied into; the file is <name>.mp3 there
            for where in rec.get("delivered_to") or []:
                if isinstance(where, str) and isinstance(rec.get("name"), str):
                    delivered.append(where if where.lower().endswith(".mp3") else
                                     os.path.join(where, rec["name"] + ".mp3"))
    return mp3, delivered


def _build_json(build_id):
    """The `<name>.build.json` in a workout folder that records this build, or None. Read from the folder
    itself, so it holds wherever the context folder lives (the web runs each command in a fresh one)."""
    if not build_id:
        return None
    for path in sorted(glob.glob(os.path.join(glob.escape(paths.WORKOUTS), "*", "*.build.json"))):
        if os.path.basename(os.path.dirname(path)) in ("research", "checks"):
            continue
        try:
            rec = fileio.read_json(path, dict)
        except errors.PROBLEMS:
            continue
        if rec.get("build_id") == build_id:
            return path
    return None


def script_of(session):
    """The script a logged workout spoke (the build's `<name>.txt` in its folder), or None. A session logged
    without a build id is matched by its folder's name, `<date>-...-<minutes>`, when exactly one fits."""
    record = _build_json(session.build_id)
    if record:
        txt = record[:-len(".build.json")] + ".txt"
        return txt if os.path.isfile(txt) else None
    if session.build_id:
        return None
    pattern = os.path.join(glob.escape(paths.WORKOUTS), f"{session.date}-*-{session.minutes}")
    folders = [f for f in glob.glob(pattern) if os.path.isdir(f)]
    if len(folders) != 1:
        return None
    txts = [t for t in glob.glob(os.path.join(glob.escape(folders[0]), "*.txt")) if not t.endswith(".draft.txt")]
    return txts[0] if len(txts) == 1 else None


def folder_of(build_id):
    """The workout folder (me/workouts/<stem>/) a build's draft sits in, or None (a draft elsewhere, or no
    record)."""
    record = _build_json(build_id)
    if record:
        return os.path.dirname(record)
    mp3, _ = _records_for(build_id) if build_id else (None, [])
    if not mp3 or not mp3.get("draft"):
        return None
    draft = mp3["draft"]
    draft = draft if os.path.isabs(draft) else os.path.join(paths.ROOT, draft)
    here = os.path.dirname(os.path.abspath(draft))
    parent = os.path.dirname(here)
    if parent != os.path.abspath(paths.WORKOUTS) or os.path.basename(here) in ("research", "checks"):
        return None
    return here


def _belongs(row, build_ids, dates):
    """Whether a told or thread row goes with the deleted workouts: its build id is one of theirs, or (a row
    from before build ids) its date is one no remaining workout shares."""
    if not isinstance(row, dict):
        return False
    if row.get("build"):
        return row["build"] in build_ids
    return row.get("date") in dates


def _rewrite_jsonl(path, keep):
    """Rewrite a JSONL record keeping the rows `keep` accepts, under its lock; returns how many went."""
    if not os.path.exists(path):
        return 0
    import json
    with locks.file_lock(path):
        rows = list(fileio.read_jsonl(path))
        kept = [r for r in rows if keep(r)]
        if len(kept) != len(rows):
            fileio.atomic_write(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept))
        return len(rows) - len(kept)


def _remove_lines(path, section_name, drop):
    """Remove the `- ` lines under `## <section_name>` in log.md that `drop` accepts; returns how many."""
    text = sessionlog.log(path)
    lines = text.splitlines()
    start = heading_index(lines, section_name)
    if start is None:
        return 0
    end = next((i for i in range(start + 1, len(lines)) if heading(lines[i]) is not None), len(lines))
    gone = [i for i in range(start + 1, end) if lines[i].startswith("- ") and drop(lines[i])]
    for i in reversed(gone):
        del lines[i]
    if gone:
        write(path, "\n".join(lines) + "\n")
    return len(gone)


def delete(targets, files=False, log_path=None) -> List[str]:
    """Take the target sessions back (see the module's docstring); returns what was done, as lines."""
    log_path = log_path or paths.LOG
    everyone = sessionlog.sessions(log_path, warn=False)
    lines_out = {t.to_line() for t in targets}
    build_ids = {t.build_id for t in targets if t.build_id}
    remaining = [s for s in everyone if s.to_line() not in lines_out]
    lone_dates = {t.date for t in targets} - {s.date for s in remaining}
    out = []
    def same(line):
        parsed = sessionlog.parse_session(line.strip())
        return isinstance(parsed, sessionlog.Session) and parsed.to_line() in lines_out
    n = _remove_lines(log_path, "Sessions", same)
    out.append(f"Removed {n} session line(s) from {paths.show(log_path)}.")
    fb = _remove_lines(log_path, "Feedback",
                       lambda line: any(f"build {b})" in line for b in build_ids))
    if fb:
        out.append(f"Removed {fb} feedback line(s).")
    told = _rewrite_jsonl(paths.TOLD, lambda r: not _belongs(r, build_ids, lone_dates))
    out.append(f"Took back {told} told item(s) (they can be told again).")
    threads = _rewrite_jsonl(paths.THREADS, lambda r: not _belongs(r, build_ids, lone_dates))
    if threads:
        out.append(f"Took back {threads} thread line(s).")
    if files:
        for t in targets:
            if not t.build_id:
                out.append(f"{t.date} {t.minutes} min: no build id, so no files are known; left as they are.")
                continue
            folder = folder_of(t.build_id)
            if folder and os.path.isdir(folder):
                shutil.rmtree(folder)
                out.append(f"Deleted {paths.show(folder)}.")
            for copy in _records_for(t.build_id)[1]:
                if os.path.isfile(copy):
                    os.remove(copy)
                    out.append(f"Deleted the delivered copy {copy}.")
    return out


def feedback(target, text: str, log_path=None) -> str:
    """Add a feedback line for a workout under ## Feedback in log.md: "- <date> (<N> min, build <id>): <text>"."""
    text = " ".join(text.split())
    if not text:
        raise errors.UsageError("say what the feedback is")
    if any(c in text for c in sessionlog.LINE_BREAKS):
        raise errors.UsageError("feedback is one line")
    log_path = log_path or paths.LOG
    line = f"- {_tag(target)}: {text}"
    lines = sessionlog.log(log_path).splitlines()
    start = heading_index(lines, "Feedback")
    if start is None:
        lines += ["", "## Feedback", ""]
        start = len(lines) - 2
    end = next((i for i in range(start + 1, len(lines)) if heading(lines[i]) is not None), len(lines))
    last = max([i for i in range(start + 1, end) if lines[i].strip()], default=start)
    insert = [line] if last != start else ["", line]
    lines[last + 1:last + 1] = insert
    write(log_path, "\n".join(lines) + "\n")
    return line


RATINGS = ("positive", "neutral", "negative")
RATED = "rated "   # a rating's feedback line reads "<tag>: rated positive"


def _tag(target) -> str:
    return f"{target.date} ({target.minutes} min" + (f", build {target.build_id})" if target.build_id else ")")


def rate(target, rating: str, log_path=None) -> str:
    """Rate a workout positive, neutral or negative (a feedback line), replacing any rating before; "none"
    clears it. Returns what was done."""
    if rating not in RATINGS + ("none",):
        raise errors.UsageError(f"a rating is one of {', '.join(RATINGS)} or none")
    log_path = log_path or paths.LOG
    prefix = f"- {_tag(target)}: {RATED}"
    cleared = _remove_lines(log_path, "Feedback", lambda line: line.startswith(prefix))
    if rating == "none":
        return "Cleared the rating." if cleared else "There was no rating to clear."
    return f"Added: {feedback(target, RATED + rating, log_path)}"


def notes_for(target, lines) -> tuple:
    """(the workout's feedback texts, its rating or None) from the Feedback lines (dash already off)."""
    tag = _tag(target) + ":"
    texts, rating = [], None
    for line in lines:
        if not line.startswith(tag):
            continue
        text = line[len(tag):].strip()
        if text.startswith(RATED) and text[len(RATED):] in RATINGS:
            rating = text[len(RATED):]
        else:
            texts.append(text)
    return texts, rating


def as_json(sessions) -> dict:
    """Every logged workout, newest first, for the web's Logs page."""
    fb = sessionlog_feedback()
    out = []
    for n, s in enumerate(sessions, 1):
        texts, rating = notes_for(s, fb)
        out.append({"n": n, "date": s.date, "minutes": s.minutes, "kit": s.kit, "coach": s.voice,
                    "format": s.format, "movements": s.movements, "topics": s.topics, "build_id": s.build_id,
                    "feedback": texts, "rating": rating, "has_script": script_of(s) is not None})
    return {"workouts": out}


def listing(sessions) -> List[str]:
    fb = sessionlog_feedback()
    out = []
    for n, s in enumerate(sessions, 1):
        notes, rating = notes_for(s, fb)
        out.append(f"{n:>3}  {s.date}  {s.minutes:>3} min  {s.kit:<12} {s.voice:<16} {s.format or '-':<14} "
                   f"build {s.build_id or '-'}" + (f"  rated {rating}" if rating else "")
                   + (f"\n       feedback: {'; '.join(notes)}" if notes else ""))
    return out or ["No workouts logged yet."]


def sessionlog_feedback():
    import context
    return context.feedback()


def main(argv=None):
    ap = cli.ArgumentParser(prog="harmonicfitness workouts", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    fb = sub.add_parser("feedback", help="add feedback on a workout to me/log.md")
    fb.add_argument("workout", help="its number in the list (1 the newest) or its build id")
    fb.add_argument("text", help="the feedback, in a line")
    sh = sub.add_parser("show", help="print the script a workout spoke")
    sh.add_argument("workout", help="its number in the list (1 the newest) or its build id")
    ra = sub.add_parser("rate", help="rate a workout positive, neutral or negative (none clears it)")
    ra.add_argument("workout", help="its number in the list (1 the newest) or its build id")
    ra.add_argument("rating", choices=RATINGS + ("none",))
    de = sub.add_parser("delete", help="take a workout back: its log line, told stories, threads and feedback")
    de.add_argument("workouts", nargs="+", help="numbers from the list, build ids, or all")
    de.add_argument("--files", action="store_true",
                    help="also delete the workout's folder and the MP3 copies it delivered")
    ap.add_argument("--json", action="store_true", help="the list as JSON: {workouts: [{n, date, minutes, kit, "
                    "coach, format, movements, topics, build_id, feedback, rating, has_script}]}")
    args = ap.parse_args(argv)
    sessions = logged()
    if args.cmd == "show":
        script = script_of(pick([args.workout], sessions)[0])
        if not script:
            raise errors.HarmonicFitnessError("no script is kept for that workout")
        with open(script, encoding="utf-8") as f:
            print(f.read(), end="")
    elif args.cmd == "rate":
        print(rate(pick([args.workout], sessions)[0], args.rating))
    elif args.cmd is None and args.json:
        print(json.dumps(as_json(sessions)))
    elif args.cmd == "feedback":
        print(f"Added: {feedback(pick([args.workout], sessions)[0], args.text)}")
    elif args.cmd == "delete":
        print("\n".join(delete(pick(args.workouts, sessions), files=args.files)))
    else:
        print("\n".join(listing(sessions)))
    return cli.OK


if __name__ == "__main__":
    sys.exit(cli.run(main))
