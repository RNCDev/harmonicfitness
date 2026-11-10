"""A turn job's arguments, checked: by the API before it queues one, and by the worker before it runs one."""
import datetime
import re

TURN_ARGS = {"conversation_id", "line", "answer", "today", "now"}
TURN_NOW = re.compile(r"\d{4}-\d{2}-\d{2} \w+ \d{2}:\d{2}", re.ASCII)
MAX_LINE = 4000


class Invalid(Exception):
    """A request the worker would refuse; `message` is its plain wording."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def day(value: object) -> str:
    """The request's `today`, checked: a date within a day of the worker's own (UTC)."""
    try:
        d = datetime.date.fromisoformat(value) if isinstance(value, str) and len(value) == 10 else None
    except ValueError:
        d = None
    now = datetime.datetime.now(datetime.timezone.utc).date()
    if d is None or abs((d - now).days) > 1:
        raise Invalid("invalid request: today must be a date within a day of today")
    return d.isoformat()


def request(args: dict) -> tuple[str | None, tuple[str, dict] | None, str, str]:
    """(line, answer, today, now), checked; exactly one of line or answer. A scheduled turn (0.60.0) also carries
    `scheduled` and the listener's `offset` from UTC in minutes; its today and now are when it was due."""
    if (set(args) - {"record", "scheduled", "offset"} != TURN_ARGS or args.get("record", False) not in (True, False)
            or args.get("scheduled", False) not in (True, False)
            or ("scheduled" in args) != ("offset" in args)
            or ("offset" in args and not (type(args["offset"]) is int and abs(args["offset"]) <= 14 * 60))):
        raise Invalid("invalid request: needs conversation_id, line, answer, today and now")
    line, answer = args["line"], args["answer"]
    if (line is None) == (answer is None):
        raise Invalid("invalid request: give exactly one of line or answer")
    if line is not None and not (isinstance(line, str) and 0 < len(line.strip()) and len(line) <= MAX_LINE):
        raise Invalid("invalid request: line must be a message")
    if answer is not None:
        if not (isinstance(answer, dict) and set(answer) == {"tool_call_id", "values"}
                and isinstance(answer["tool_call_id"], str) and answer["tool_call_id"]
                and isinstance(answer["values"], dict)):
            raise Invalid("invalid request: answer needs tool_call_id and values")
        answer = (answer["tool_call_id"], answer["values"])
    today = day(args["today"])
    now = args["now"]
    if not (isinstance(now, str) and TURN_NOW.fullmatch(now) and now.startswith(today)):
        raise Invalid("invalid request: now must be like 2026-10-28 Wednesday 08:00, on today")
    return line, answer, today, now


def check(args: dict) -> str | None:
    """What's wrong with a turn job's args, in the worker's own words, or None: the API checks a turn
    with this before it queues one."""
    try:
        request(args)
    except Invalid as e:
        return e.message
    return None


def said_when(local: str) -> str:
    """"Wednesday at 07:00" from "2026-11-04 Wednesday 07:00"."""
    parts = local.split(" ")
    return f"{parts[1]} at {parts[2]}" if len(parts) == 3 else local


def local_clock(offset: int, utc: datetime.datetime | None = None) -> tuple[str, str]:
    """(today, now) on the listener's clock, `offset` minutes east of UTC, as their page would send them."""
    at = (utc or datetime.datetime.now(datetime.timezone.utc)).astimezone(
        datetime.timezone(datetime.timedelta(minutes=offset)))
    return at.strftime("%Y-%m-%d"), at.strftime("%Y-%m-%d %A %H:%M")
