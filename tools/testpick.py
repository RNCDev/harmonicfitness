"""Which engine tests cover a change, for `./harmonicfitness test changed`: a tighter loop than the whole suite while
working. CI still runs everything on each push, so a release waits for it there.

A test module is picked when it changed itself, or when it imports something the change reaches: a changed tool, a
tool that names a changed data file in quotes ("movements.toml"), or a tool that imports one of those directly. A
change to the tests' shared helpers or fixtures picks every module. The enforcers, which hold rules every file keeps,
always run. web/ has its own suite (`test web`), and the docs, the changelog and the version reach no test.

Reaching is by import, never by a name in passing: "content.md" in a path table is not a use of content.py (before
2026-11-17 it was, and a change to one tool picked every module). The hubs every tool imports (paths, context, cli,
errors, fileio) are followed only when they changed themselves: reached through a data file they name, they'd pick
everything."""
import os
import re
import subprocess

# Rules every file keeps (exit codes, imports, atomic writes, the assistants' files): any change can break them.
ENFORCERS = ("test_contract", "test_imports", "test_integrity", "test_harness")
# Modules nearly every tool and test imports: a change to one is everyone's, but one only naming a changed data file
# (paths names them all) reaches nothing through them.
HUBS = ("paths", "context", "cli", "errors", "fileio", "harmonicfitness")
# What no engine test reads: the docs and the release's own files.
NO_TEST = re.compile(r"^(docs/|assets/|\.github/|web/|CHANGELOG\.md$|VERSION$|README\.md$|ROADMAP\.md$|"
                     r"SHARE-HARMONIC\.md$|LICENSE$|uv\.lock$)")


def changed_files(root):
    """Paths changed on this branch and not yet pushed, in the working tree or staged, and new files git doesn't
    ignore. With no upstream (or no git), only what git can say."""
    def git(*args):
        try:
            r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
        except OSError:
            return []
        return r.stdout.splitlines() if r.returncode == 0 else []
    names = (git("diff", "--name-only", "@{upstream}...HEAD") + git("diff", "--name-only", "HEAD")
             + git("ls-files", "--others", "--exclude-standard"))
    return sorted({n.strip() for n in names if n.strip()})


def sources(folder, prefix=""):
    """{module name: its source} for each .py file in a folder and its subfolders whose name starts with prefix,
    named by file stem."""
    out = {}
    for here, _, files in os.walk(folder):
        if "__pycache__" in here:
            continue
        for f in files:
            if f.endswith(".py") and f.startswith(prefix):
                with open(os.path.join(here, f), encoding="utf-8", errors="replace") as fh:
                    out[f[:-3]] = fh.read()
    return out


def _uses(stem):
    """A pattern for source that imports a module by name (at the top or inside a function)."""
    s = re.escape(stem)
    return re.compile(rf"^[ \t]*(?:import [\w., ]*\b{s}\b|from {s} import\b|from \S+ import [\w., ()]*\b{s}\b)",
                      re.MULTILINE)


def _names(base):
    """A pattern for source that names a data file in quotes."""
    return re.compile(rf"[\"']{re.escape(base)}[\"']")


def pick(changed, tests, tools):
    """The test modules (sorted) that cover the changed paths. tests and tools map module name to source."""
    if any(p.startswith("tests/") and os.path.splitext(os.path.basename(p))[0] not in tests for p in changed):
        return sorted(tests)   # helpers.py, fakes.py or a fixture: every module leans on them
    chosen = {t for t in ENFORCERS if t in tests}
    reached, names, direct = set(), [], set()
    for path in changed:
        if NO_TEST.match(path):
            continue
        base = os.path.basename(path)
        stem, ext = os.path.splitext(base)
        if path.startswith("tests/"):
            chosen.add(stem)
        elif path.startswith("tools/") and ext == ".py":
            reached.add(stem)
            direct.add(stem)
        else:
            named = _names(base)
            names.append(named)
            reached |= {t for t, src in tools.items() if t not in HUBS and named.search(src)}
    # and the tools that import one directly: one step up, not every step, since the top-level tools import
    # nearly everything (the whole suite is CI's job); never up from a hub that didn't itself change
    for source in [t for t in reached if t not in HUBS or t in direct]:
        m = _uses(source)   # a changed tool's importers, hubs among them; a reached one's, past the hubs
        reached |= {t for t, src in tools.items() if (source in direct or t not in HUBS) and m.search(src)}
    pats = [_uses(t) for t in reached]
    for name, src in tests.items():
        if name[5:] in reached or any(p.search(src) for p in pats) or any(n.search(src) for n in names):
            chosen.add(name)
    return sorted(chosen)
