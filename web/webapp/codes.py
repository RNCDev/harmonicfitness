"""What the page does with a refusal or a step, as a code beside the words: the page reads the code, never the
wording, so the words can change without taking a button away (0.71.0).

A job's error is stored as plain words (jobs.fail); its code is worked out here, from the site's own words, as it
is served. A step's kind comes from its tool."""

# a job that couldn't start: no language-model key, or the one there was refused
NO_MODEL_KEY = "add a language-model key in Settings"
KEY_REFUSED = " refused the key. Replace it in Settings."


def key_refused(name: str) -> str:
    """The words for a provider that refused the listener's key."""
    return f"{name}{KEY_REFUSED}"


def of_error(error: str | None) -> str | None:
    """The code for a job's error, when the page has something to offer for it (Open Settings): "no_model_key" or
    "key_refused"; None for every other error."""
    if not error:
        return None
    if error == NO_MODEL_KEY:
        return "no_model_key"
    if error.endswith(KEY_REFUSED):
        return "key_refused"
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
