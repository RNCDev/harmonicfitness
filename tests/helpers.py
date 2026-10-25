"""Shared helpers for the tests: keeping them off the real me/, and pointing every path at a temp folder."""
import contextlib
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import paths  # noqa: E402


def assert_isolated(home):
    """Stop when `home` is a real context folder (holds a profile): the tests must never read or write
    one. ./sweatcast test points SWEATCAST_HOME at an absent folder, as CI has no me/."""
    if os.path.exists(os.path.join(home, "profile.md")):
        raise SystemExit(f"The tests would run over a real context folder, {home}. Run them with "
                         "./sweatcast test (which sets SWEATCAST_HOME to an absent folder), or set SWEATCAST_HOME.")


@contextlib.contextmanager
def home(root):
    """Every paths.* value under the context folder, pointed under `root` for the block: HOME itself and
    each file and folder derived from it. The engine's own paths (ROOT, knowledge, the template) stay."""
    old = paths.HOME
    root = os.path.abspath(root)
    with contextlib.ExitStack() as stack:
        for name, value in list(vars(paths).items()):
            if name.startswith("_") or not isinstance(value, str):
                continue
            if value == old:
                stack.enter_context(mock.patch.object(paths, name, root))
            elif value.startswith(old + os.sep):
                stack.enter_context(mock.patch.object(paths, name, os.path.join(root, os.path.relpath(value, old))))
        yield root
