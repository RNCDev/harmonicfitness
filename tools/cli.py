"""Exit codes and the argument parser every tool shares.

The exit codes are the tools' contract with the skills, which branch on them:
    0   done
    1   issues to fix (a lint flag, a missing file, a measurement not on file yet)
    2   the rendered workout ran more than the tolerance over or under plan (render only)
    3   the voice's speaking rate hasn't been measured yet (build only)
    4   a cloud voice service refused: the key, the payment or the quota (the listener must act)
    64  the command itself was wrong: a mistyped option, an unknown voice
    70  an engine bug (EX_SOFTWARE): nothing to fix in the draft or the command; report it

Python's argparse exits 2 on a mistyped option, which would read as "the workout ran
long", so every tool parses its arguments with ArgumentParser below, which exits 64.

Every tool's main runs through run(), which turns what it raises into these codes: a Usage
(argparse's or a main's refusal) is 64; an exception carrying an `exit_code` (errors.UsageError, 64,
for an unknown coach or a web coach with no key here; a web service's refusal; a limits row that can't
be read) exits with it; any other SystemExit with a message is 1, the message on stderr. Any other exception is a bug in the
engine: its traceback (with every key value taken out) goes to stderr and the code is 70, so a skill never
reads a crash as a draft to fix.
"""
import argparse
import sys

from errors import OK, ISSUES, DRIFT, UNMEASURED, SERVICE, USAGE, BUG   # noqa: F401  (they live in errors.py)


class Usage(SystemExit):
    """The command line itself was wrong (exit 64), raised by argparse or a main. The message
    is the exit code's payload, as with any SystemExit, so code that prints `e.code` still works."""


def run(main, argv=None):
    """Run a tool's main() and return its exit code, mapping what it raises (see above)."""
    try:
        code = main() if argv is None else main(argv)
    except Usage as e:
        print(e.code, file=sys.stderr)
        return USAGE
    except SystemExit as e:
        if e.code is None or isinstance(e.code, int):
            return e.code or OK
        print(e.code, file=sys.stderr)
        return ISSUES
    except Exception as e:
        code = getattr(e, "exit_code", None)
        if code is None:
            print(_traceback(), file=sys.stderr, end="")
            return BUG
        print(e, file=sys.stderr)
        return code
    except KeyboardInterrupt:
        return 130
    return code or OK


def _traceback():
    """The current exception's traceback with every key value taken out; the raw one if scrubbing fails, since
    a crash handler that crashes would hide the bug."""
    import traceback
    text = traceback.format_exc()
    try:
        import redact   # here, not at the top: redact reads keys, which imports this module
        return redact.scrub(text)
    except Exception:
        return text


def _date(text):
    import datetime
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date: {text!r} (YYYY-MM-DD)") from None


def today_arg(parser):
    """--today: the date to plan for (a datetime.date, None for today); a value that isn't one exits 64."""
    parser.add_argument("--today", type=_date, help="today's date, YYYY-MM-DD (default: today)")


class ArgumentParser(argparse.ArgumentParser):
    """argparse, but a command-line mistake exits 64 (EX_USAGE), never 2."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(USAGE, f"{self.prog}: error: {message}\n")
