import ast
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import webapp  # noqa: E402


class Wiring(unittest.TestCase):
    def test_app_name(self):
        self.assertEqual(webapp.APP_NAME, "HarmonicFitness")

    def test_the_web_process_never_imports_the_worker(self):
        web = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        out = subprocess.run([sys.executable, "-c",
                              "import webapp.api, webapp.start, sys; print('webapp.worker' in sys.modules)"],
                             cwd=web, capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(out.stdout.strip(), "False")

    def test_only_the_allowed_functions_commit(self):
        """A function that reads or writes data never commits or rolls back: its caller owns the transaction (a
        route through routes.state's tx or read, the worker loop for its jobs). The job queue's single-step units of
        work, the sweeps and the migrations commit their own."""
        allowed = {
            "routes.state.tx", "routes.state.read",
            "jobs._done", "jobs.claim", "jobs.heartbeat", "jobs.stop_requested", "jobs.finish", "jobs.fail",
            "jobs.reap", "jobs.event", "jobs.complete",
            "media.sweep", "clipcache.prune", "retention.sweep",
            "db.migrate", "db.missing", "db.wait_for_migrations",
            "admin.main", "api.create_app_from_env",
        }
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp")
        found = set()
        for here, _, names in os.walk(root):
            for name in names:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(here, name)
                module = os.path.relpath(path, root)[:-3].replace(os.sep, ".").removesuffix(".__init__")
                with open(path, encoding="utf-8") as f:
                    tree = ast.parse(f.read())

                def visit(node, enclosing):
                    for child in ast.iter_child_nodes(node):
                        inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else enclosing
                        if (isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                                and child.func.attr in ("commit", "rollback")):
                            found.add(f"{module}.{enclosing}")
                        visit(child, inner)
                visit(tree, "<module>")
        found = {f for f in found if not f.startswith("worker.")}   # the worker loop owns its jobs' transactions
        self.assertEqual(found - allowed, set())


if __name__ == "__main__":
    unittest.main()
