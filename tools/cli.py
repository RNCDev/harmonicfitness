"""Exit codes and the argument parser every tool shares.

The exit codes are the tools' contract with the skills, which branch on them:
    0   done
    1   issues to fix (a lint flag, a missing file, a measurement not on file yet)
    2   the rendered workout ran more than the tolerance over or under plan (render only)
    3   the voice's speaking rate hasn't been measured yet (build only)
    4   a cloud voice service refused: the key, the payment or the quota (the listener must act)
    64  the command itself was wrong: a mistyped option, an unknown voice

Python's argparse exits 2 on a mistyped option, which would read as "the workout ran
long", so every tool parses its arguments with ArgumentParser below, which exits 64.

Every tool's main runs through run(), which turns what it raises into these codes: a Usage
(or a subclass, such as an unknown coach or a web coach with no key here) is 64; an exception
carrying an `exit_code` (a web service's refusal, a limits row that can't be read) exits with
it; any other SystemExit with a message is 1, the message on stderr. A real bug still shows its
traceback.
"""
import argparse
import sys

OK, ISSUES, DRIFT, UNMEASURED, SERVICE, USAGE = 0, 1, 2, 3, 4, 64


class Usage(SystemExit):
    """The command itself was wrong (exit 64): an unknown option, coach, draft or route. The message
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
            raise
        print(e, file=sys.stderr)
        return code
    except KeyboardInterrupt:
        return 130
    return code or OK


class ArgumentParser(argparse.ArgumentParser):
    """argparse, but a command-line mistake exits 64 (EX_USAGE), never 2."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(USAGE, f"{self.prog}: error: {message}\n")
