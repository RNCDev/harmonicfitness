"""The problems the engine reports, as exceptions a caller can tell apart.

Library code raises one of these; it never exits the process. Each carries the exit code the command ends
with (1 unless it says otherwise; tools/cli.py says what each means), which cli.run reads, printing the message
on stderr. A caller that wants to carry on past a problem catches the kind it means, or PROBLEMS for any
reported one. The exit codes live here, a module that imports nothing, so library code needn't import cli;
cli re-exports them, and cli.Usage (a SystemExit) is left to argparse and the commands' main functions.
"""

OK, ISSUES, DRIFT, UNMEASURED, SERVICE, USAGE, BUG = 0, 1, 2, 3, 4, 64, 70   # see tools/cli.py


class SweatcastError(Exception):
    """A problem the listener or the writer must fix. `message` is what they read."""
    exit_code = ISSUES

    def __init__(self, message="", exit_code=None):
        super().__init__(message)
        if exit_code is not None:
            self.exit_code = exit_code

    @property
    def code(self):
        """The message, as SystemExit's `code` was: code that printed `e.code` keeps working."""
        return str(self)


class UsageError(SweatcastError):
    """The command itself was wrong (exit 64), found below main: an unknown coach, a web coach that can't
    speak here, a draft or an output path that isn't one."""
    exit_code = USAGE


class ContextError(SweatcastError):
    """A file in the context folder is missing, unreadable, or at a schema this engine doesn't read."""


class LogRefused(SweatcastError):
    """log-session refused a session line (its message starts "Not logged:")."""


class CoachError(SweatcastError):
    """A coach can't be used as asked: archived, no voice yet, the wrong kind for the route, an audition fault."""


class RouteUnavailable(SweatcastError):
    """No audio route works on this computer (for this coach)."""


class EngineError(SweatcastError):
    """The local engine or the take checker can't be loaded."""


class DraftError(SweatcastError):
    """A draft isn't in the draft format (tools/draft.py)."""


class RenderStopped(SweatcastError):
    """A render or its encode stopped: a take still dropping a cue, ffmpeg failing, a web render refused."""


class MigrateError(SweatcastError):
    """The context folder can't be migrated as it stands."""


PROBLEMS = (SweatcastError,)   # every problem a command reports; catch this to carry on past one
