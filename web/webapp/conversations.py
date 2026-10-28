"""An agent conversation, sealed with the user's data key.

The body (history, chat lines, open question, plan, stem) is one sealed JSON document; the
state, version, times and the id of the job that last began a turn (`job_id`) stay plain. Every query is scoped by user id, so another user's
conversation is missing. None of these commit: the caller does.
"""
import dataclasses
import json
from dataclasses import dataclass, field

from . import crypto
from .store import UserKey

_STARTABLE = ("waiting", "idle", "failed")
INTERRUPTED = "That didn't work: interrupted"


@dataclass
class Conversation:
    id: int
    state: str
    version: int
    history: str | None = None
    lines: list = field(default_factory=list)
    question: dict | None = None
    plan: dict | None = None
    stem: str | None = None
    job_id: int | None = None   # plain; written only by set_job, never by save


def _aad(uk: UserKey, cid: int) -> bytes:
    return f"{uk.user_id}:conversations:{cid}".encode()


def _seal(uk: UserKey, c: Conversation) -> bytes:
    body = {"history": c.history, "lines": c.lines, "question": c.question,
            "plan": c.plan, "stem": c.stem}
    return crypto.seal(uk.key, json.dumps(body).encode("utf-8"), _aad(uk, c.id))


def _open(uk: UserKey, cid: int, state: str, version: int, job_id, sealed) -> Conversation:
    body = json.loads(crypto.open_(uk.key, bytes(sealed), _aad(uk, cid)).decode("utf-8"))
    return Conversation(id=cid, state=state, version=version, history=body.get("history"),
                        lines=body.get("lines") or [], question=body.get("question"),
                        plan=body.get("plan"), stem=body.get("stem"), job_id=job_id)


def create(conn, uk: UserKey, first_line: str) -> int:
    """A new working conversation holding the user's first line. The sealed body's AAD names
    the row's id, so the row is inserted with an empty body and sealed in the same transaction."""
    cid = conn.execute(
        "insert into conversations (user_id, state, body) values (%s, 'working', %s) "
        "returning id", (uk.user_id, b"")).fetchone()[0]
    c = Conversation(id=cid, state="working", version=1,
                     lines=[{"role": "user", "text": first_line}])
    conn.execute("update conversations set body = %s where id = %s and user_id = %s",
                 (_seal(uk, c), cid, uk.user_id))
    return cid


def load(conn, uk: UserKey, cid: int) -> Conversation:
    row = conn.execute("select state, version, job_id, body from conversations "
                       "where id = %s and user_id = %s", (cid, uk.user_id)).fetchone()
    if row is None:
        raise LookupError(f"no conversation {cid}")
    return _open(uk, cid, *row)


def latest(conn, uk: UserKey) -> Conversation | None:
    row = conn.execute("select id, state, version, job_id, body from conversations "
                       "where user_id = %s order by updated_at desc, id desc limit 1",
                       (uk.user_id,)).fetchone()
    return None if row is None else _open(uk, *row)


def save(conn, uk: UserKey, conv: Conversation, expect_version: int) -> bool:
    """Write the conversation if its version is still `expect_version`; bumps the version.
    Leaves job_id as it is (set_job writes it)."""
    n = conn.execute(
        "update conversations set state = %s, body = %s, version = version + 1, "
        "updated_at = now() where id = %s and user_id = %s and version = %s",
        (conv.state, _seal(uk, conv), conv.id, uk.user_id, expect_version)).rowcount
    if n == 1:
        conv.version = expect_version + 1
    return n == 1


def set_job(conn, uk: UserKey, cid: int, job_id: int | None) -> None:
    """Record the turn job that now runs the conversation (in the transaction that queues it)."""
    conn.execute("update conversations set job_id = %s where id = %s and user_id = %s",
                 (job_id, cid, uk.user_id))


def heal(conn, uk: UserKey, conv: Conversation) -> Conversation:
    """A working conversation whose turn job is done, failed or gone (the worker died mid-turn, say)
    failed with the agent line "That didn't work: interrupted", under the version check. Returns the
    conversation as it now stands; unchanged when it isn't working or its job is queued or running."""
    if conv.state != "working":
        return conv
    row = None if conv.job_id is None else conn.execute(
        "select state from jobs where id = %s and user_id = %s", (conv.job_id, uk.user_id)).fetchone()
    if row is not None and row[0] in ("queued", "running"):
        return conv
    failed = dataclasses.replace(conv, state="failed", question=None,
                                 lines=conv.lines + [{"role": "agent", "text": INTERRUPTED}])
    if save(conn, uk, failed, conv.version):
        return failed
    return load(conn, uk, conv.id)   # moved on meanwhile: as stored


def answer_line(question: dict, answer: dict) -> str:
    """The user's answers as one chat line: "Limits: Nothing new · Length: 25 min"."""
    parts = []
    for q in question.get("questions", []):
        if q["id"] not in answer:
            continue
        a = answer[q["id"]]
        if isinstance(a, str):
            text = a[len("other:"):].strip() if a.startswith("other:") else a
        else:
            text = ", ".join(a)
        parts.append(f"{q['prompt'].rstrip('?:')}: {text}")
    return " · ".join(parts)


def begin_turn(conn, uk: UserKey, cid: int, line: str | None, answer: dict | None) -> bool:
    """Start a turn from waiting, idle or failed: add the user's line (or the answer's line),
    clear the question, go working. False when missing, not the user's, or already working."""
    try:
        c = load(conn, uk, cid)
    except LookupError:
        return False
    if c.state not in _STARTABLE:
        return False
    text = answer_line(c.question or {}, answer) if answer is not None else line
    if text:
        c.lines.append({"role": "user", "text": text})
    c.question = None
    c.state = "working"
    return save(conn, uk, c, c.version)
