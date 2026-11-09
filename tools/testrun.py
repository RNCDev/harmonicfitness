"""The engine's tests, run side by side: `./harmonicfitness test` finds every test class, deals them into batches
and runs each batch in its own process with its own temporary home, as many at once as the computer has cores.

Each class is a unit, so a slow module (test_tools, test_setup) spreads over several processes. The batches are
dealt round-robin from the classes in order, so each batch holds a mix of modules, and the workers pull them as
they free up. HARMONICFITNESS_TEST_JOBS=1 runs them one batch at a time, in order.
"""
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

# Lists the test classes a set of names (or, with none, the whole tests/ folder) holds, one per line. A module that
# fails to import is listed by its own name, so its batch reports the error.
_LIST = r"""
import sys, unittest
def walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite):
            yield from walk(t)
        else:
            yield t
loader = unittest.defaultTestLoader
suite = loader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv) > 1 else loader.discover("tests", top_level_dir="tests")
seen = []
for t in walk(suite):
    kind = type(t)
    unit = t.id().rsplit(".", 1)[-1] if kind.__module__.startswith("unittest") else f"{kind.__module__}.{kind.__qualname__}"
    if unit not in seen:
        seen.append(unit)
print("\n".join(seen))
"""

_RAN = re.compile(r"^Ran (\d+) tests? in", re.M)
_COUNTS = re.compile(r"(failures|errors|skipped|expected failures|unexpected successes)=(\d+)")


def jobs():
    """How many batches run at once: HARMONICFITNESS_TEST_JOBS, else the computer's cores (at most eight)."""
    try:
        n = int(os.environ.get("HARMONICFITNESS_TEST_JOBS", ""))
    except ValueError:
        n = 0
    return max(1, n) if n else max(1, min(os.cpu_count() or 1, 8))


def units(root, env, names):
    """The test classes to run, as unittest names ("test_tools.RenderLock")."""
    r = subprocess.run([sys.executable, "-c", _LIST, *names], cwd=root, env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        return list(names) or ["discover"]
    return [line for line in r.stdout.splitlines() if line.strip()]


def deal(items, n):
    """`items` dealt round-robin into at most `n` non-empty batches."""
    batches = [items[i::n] for i in range(min(n, len(items)))]
    return [b for b in batches if b]


def run(root, env, names=(), opts=(), verbose=False):
    """Runs the named test modules (every one under tests/ when there are none) side by side; returns 0 when all
    pass. Each batch's output prints whole as it finishes when it fails, or with -v; then one summary line."""
    start = time.monotonic()
    found = units(root, env, list(names))
    workers = jobs()
    batches = deal(found, workers * 3) if workers > 1 else [found]
    home = os.path.dirname(env["HARMONICFITNESS_HOME"])

    def one(k, batch):
        e = dict(env, HARMONICFITNESS_HOME=os.path.join(tempfile.mkdtemp(prefix=f"b{k}-", dir=home), "me"))
        argv = [sys.executable, "-m", "unittest", *opts, *batch]
        if batch == ["discover"]:
            argv = [sys.executable, "-m", "unittest", "discover", "tests", *opts]
        r = subprocess.run(argv, cwd=root, env=e, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    totals, ran, failed = {}, 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for code, out in pool.map(lambda kb: one(*kb), enumerate(batches)):
            m = _RAN.search(out)
            ran += int(m.group(1)) if m else 0
            tail = out[m.end():] if m else out
            for key, count in _COUNTS.findall(tail):
                totals[key] = totals.get(key, 0) + int(count)
            if code != 0:
                failed += 1
            if code != 0 or verbose:
                sys.stdout.write(out if out.endswith("\n") else out + "\n")
                sys.stdout.flush()
    took = time.monotonic() - start
    extra = ", ".join(f"{k}={v}" for k, v in totals.items())
    print("-" * 70)
    print(f"Ran {ran} test{'' if ran == 1 else 's'} in {took:.1f}s ({len(found)} classes in {len(batches)} batches, "
          f"{min(workers, len(batches))} at a time)")
    print(("FAILED" if failed else "OK") + (f" ({extra})" if extra else ""))
    return 1 if failed else 0
