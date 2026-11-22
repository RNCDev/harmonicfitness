"""What the page does with a refusal or a step, as a code beside the words: the page reads the code, never the
wording, so the words can change without taking a button away (0.71.0).

A job's error is stored as plain words (jobs.fail), its code beside them. A step's kind comes from its tool."""


def of_status(status: dict) -> str | None:
    """The code stored beside a job's error (0.76.0), or None. The two a job could carry before 0.88.0, for a
    listener's own key missing or refused, went with those keys: a page that reads one finds nothing to offer."""
    return status.get("code")


def step_kind(text: str, tool: str, think: bool) -> str | None:
    """What a step is waiting on, for the page's note on a long wait: "think", "recording", "voice", or None."""
    if think:
        return "think"
    if tool.startswith("run coaches make") or (tool.startswith("run build") and text.startswith("Designing")):
        return "voice"
    if tool.startswith("run build") and "--lint-only" not in tool:
        return "recording"
    return None
