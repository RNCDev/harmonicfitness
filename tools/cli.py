"""Exit codes and the argument parser every tool shares.

The exit codes are the tools' contract with the skills, which branch on them:
    0   done
    1   issues to fix (a lint flag, a missing file, a measurement not on file yet)
    2   the rendered workout ran more than the tolerance over or under plan (render only)
    3   the voice's speaking rate hasn't been measured yet (build.sh only)
    64  the command itself was wrong: a mistyped option, an unknown voice

Python's argparse exits 2 on a mistyped option, which would read as "the workout ran
long", so every tool parses its arguments with ArgumentParser below, which exits 64.
"""
import argparse
import sys

OK, ISSUES, DRIFT, UNMEASURED, USAGE = 0, 1, 2, 3, 64


class ArgumentParser(argparse.ArgumentParser):
    """argparse, but a command-line mistake exits 64 (EX_USAGE), never 2."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(USAGE, f"{self.prog}: error: {message}\n")
