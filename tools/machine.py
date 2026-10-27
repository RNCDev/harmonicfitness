"""This computer's facts, as the readiness check (tools/doctor.sh) decides them, for any tool to read: the
shell script stays the one place that decides what this computer can do. A library: routes and doctor read it.
In the tests, SWEATCAST_FAKE_* variables stand in for the hardware (doctor.sh reads them)."""
import functools
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths  # noqa: E402

DOCTOR_SH = os.path.join(paths.ROOT, "tools", "doctor.sh")


@functools.lru_cache(maxsize=1)
def facts():
    """The computer's facts, from `sh tools/doctor.sh --facts`, read once per process."""
    try:
        out = subprocess.run(["sh", DOCTOR_SH, "--facts"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:   # no sh here (Python started outside Git Bash), or a hang
        return {"local": "no", "local_reason": f"the readiness check (tools/doctor.sh) couldn't run here ({e}); "
                                                "run ./sweatcast doctor from Git Bash or a terminal"}
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


def hub_dir():
    """Where the local voice models are (models/, which tools/paths.py points Hugging Face at)."""
    return paths.MODELS
