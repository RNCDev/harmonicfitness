"""What the page does with a refusal or a step, as a code beside the words: the page reads the code, never the
wording, so the words can change without taking a button away (0.71.0).

A job's error is stored as plain words (jobs.fail); its code is worked out here, from the site's own words, as it
is served. A step's kind comes from its tool."""

# a job that couldn't start: no language-model key, or the one there was refused
NO_MODEL_KEY = "add a language-model key in Settings"
# the codes themselves, as the page reads them
NO_KEY_CODE = "no_model_key"
KEY_REFUSED_CODE = "key_refused"
KEY_REFUSED = " refused the key. Replace it in Settings."


def key_refused(name: str) -> str:
    """The words for a provider that refused the listener's key."""
    return f"{name}{KEY_REFUSED}"


def of_status(status: dict) -> str | None:
    """The code for a job as jobs.status reads it: the one stored beside its error (0.76.0), else, for a job failed
    before that, the one its words imply."""
    return status.get("code") or of_error(status.get("error"))


def of_error(error: str | None) -> str | None:
    """The code for a job's error, when the page has something to offer for it (Open Settings): "no_model_key" or
    "key_refused"; None for every other error."""
    if not error:
        return None
    if error == NO_MODEL_KEY:
        return NO_KEY_CODE
    if error.endswith(KEY_REFUSED):
        return KEY_REFUSED_CODE
    return None


def step_kind(text: str, tool: str, think: bool) -> str | None:
    """What a step is waiting on, for the page's note on a long wait: "think", "recording", "voice", or None."""
    if think:
        return "think"
    if tool.startswith("run coaches make") or (tool.startswith("run build") and text.startswith("Designing")):
        return "voice"
    if tool.startswith("run build") and "--lint-only" not in tool:
        return "recording"
    return None
