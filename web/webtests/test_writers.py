"""The writers' room (the site's way since 0.51.0; trainer, researcher, host and review since 0.55.0): what code does
around the models, without them."""
import os
import sys
import unittest

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from webapp import agent  # noqa: E402
from webapp.agent import tools, writers  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


class Switch(unittest.TestCase):
    def test_stop_ends_a_writers_room_a_clean_skeleton_started(self):
        import asyncio
        import threading
        import time
        from unittest import mock
        deps = tools.Deps(engine_root=ROOT, home=ROOT, keys={}, today="2026-11-01", now="2026-11-01 Sunday 08:00",
                          writers="three", cancel=threading.Event())
        deps.reports["me/x.draft.txt"] = "the budgets"
        ctx = type("Ctx", (), {"deps": deps})()
        cancelled = []

        async def fill(ctx_, path, name, coach):
            try:
                await asyncio.sleep(30)   # a room still writing
            except asyncio.CancelledError:
                cancelled.append(path)
                raise
        loop = asyncio.new_event_loop()
        threading.Thread(target=loop.run_forever, daemon=True).start()
        self.addCleanup(loop.call_soon_threadsafe, loop.stop)
        deps.loop = loop
        threading.Timer(0.2, deps.cancel.set).start()   # the listener presses Stop
        clean = tools.ToolResult(code=1, output="", error="A skeleton, no words yet")
        began = time.monotonic()
        with mock.patch.object(agent, "_fill", fill):
            out = agent._chain(ctx, "me/x.draft.txt", clean, "W", "Coach Freya")
        self.assertLess(time.monotonic() - began, 3)
        self.assertTrue(out.refused)
        time.sleep(0.1)
        self.assertEqual(cancelled, ["me/x.draft.txt"])   # the room's model calls stop with it


class Stock(unittest.TestCase):
    """The researcher is handed the stock's pieces from the engine's content plan, as tools.run returns it (0.76.0:
    the plan's paths are me/... by then, which the old pattern never matched)."""

    def setUp(self):
        import shutil
        import tempfile
        from webapp import folder
        root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
        self.home = tempfile.mkdtemp(prefix="hf-stock-")
        self.addCleanup(shutil.rmtree, self.home, True)
        folder.materialize(folder.seed(root), self.home)
        os.makedirs(os.path.join(self.home, "workouts", "research", "reserve"), exist_ok=True)
        with open(os.path.join(self.home, "workouts", "research", "reserve", "moon-dust.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Moon dust\n- Topic: space\n- Format: one strange fact\n- Source: https://example.org/moon\n"
                    "- Good until: evergreen\n\nThe dust smells of spent gunpowder, the astronauts said.\n")
        self.deps = tools.Deps(engine_root=root, home=self.home, keys={}, today="2026-11-09",
                               now="2026-11-09 Monday 08:00")

    def test_a_stock_path_outside_the_folder_is_never_read(self):
        self.assertEqual(writers._stock(self.deps, "- space / fact: x (me/../../etc/passwd.md, slug x)"), "")


if __name__ == "__main__":
    unittest.main()
