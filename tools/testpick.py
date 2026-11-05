"""Which engine tests cover a change, for `./harmonicfitness test changed`: a tighter loop than the whole suite while
working. CI still runs everything on each push, so a release waits for it there.

A test module is picked when it changed itself, or when it names something the change reaches: a changed tool, a
tool that reads a changed file (by its file name), or a tool that imports one of those directly. A change to
the tests' shared helpers or fixtures picks every module. The enforcers, which hold rules every file keeps, always
run. web/ has its own suite (`test web`) and is left out here."""
import os
import re
import subprocess

# Rules every file keeps (exit codes, imports, atomic writes, the two assistants' files): any change can break them.
ENFORCERS = ("test_contract", "test_imports", "test_integrity", "test_harness")


def changed_files(root):
    """Paths changed on this branch and not yet pushed, in the working tree or staged, and new files git doesn't
    ignore. With no upstream (or no git), only what git can say."""
    def git(*args):
        try:
            r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
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
    """A pattern for source that imports or reaches a module by name."""
    s = re.escape(stem)
    return re.compile(rf"\bimport [\w., ]*\b{s}\b|\bfrom {s} import\b|\b{s}\.\w")


def pick(changed, tests, tools):
    """The test modules (sorted) that cover the changed paths. tests and tools map module name to source."""
    if any(p.startswith("tests/") and os.path.splitext(os.path.basename(p))[0] not in tests for p in changed):
        return sorted(tests)   # helpers.py, fakes.py or a fixture: every module leans on them
    chosen = {t for t in ENFORCERS if t in tests}
    reached, names = set(), set()
    for path in changed:
        if path.startswith("web/"):
            continue
        base = os.path.basename(path)
        stem, ext = os.path.splitext(base)
        if path.startswith("tests/"):
            chosen.add(stem)
        elif path.startswith("tools/") and ext == ".py":
            reached.add(stem)
        else:
            names.add(base)
            reached |= {t for t, src in tools.items() if base in src}
    # and the tools that import one directly: one step up, not every step, since the top-level tools import
    # nearly everything (the whole suite is CI's job)
    for m in [_uses(t) for t in reached]:
        reached |= {t for t, src in tools.items() if m.search(src)}
    pats = [_uses(t) for t in reached]
    for name, src in tests.items():
        if name[5:] in reached or any(p.search(src) for p in pats) or any(n in src for n in names):
            chosen.add(name)
    return sorted(chosen)
