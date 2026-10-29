"""Key values taken out of text before it's printed or recorded: a leaf module (it reads the keys through
tools/keys.py, never the HTTP engine), so the command line can scrub a traceback without loading cloud.py.
Named redact, not secrets: tools/ sits first on sys.path, and a secrets.py here would shadow the standard
library's, which the model libraries import."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import keys  # noqa: E402


def scrub(text):
    """`text` with every key value set here (the environment's or me/.env's) replaced by <key>, so nothing a
    library or a service echoes can print one."""
    try:
        values = keys.raw_values()
    except (OSError, UnicodeError):   # me/.env unreadable: the environment's keys still come out, never none
        values = [v for v in (os.environ.get(var) for var in keys.SECRET_VARS) if v]
    for value in sorted(values, key=len, reverse=True):
        for form in (value, value.strip()):
            if len(form) >= 8:
                text = text.replace(form, "<key>")
    return text
