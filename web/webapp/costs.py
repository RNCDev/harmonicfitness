"""What the site's own OpenRouter key is charged, for the admin screen's books (0.87.0).

The writing: every model reply carries OpenRouter's own charge (usage.cost, which pydantic-ai keeps in the reply's
provider_details["cost"]); a job's model is wrapped once (`Metered`), so the conversation, the writers' room and the
enricher are all counted, and the job writes the total as it ends, however it ends. A request cut off before its
reply never reports a cost: OpenRouter's own daily count (`read_spend`) shows that as spend no turn claimed.

The voice: the engine renders through OpenRouter in its own process and writes each recording's estimate (its
characters at the voice's price) to builds.jsonl, failed renders too; a job adds the lines it made, as estimated.

Nothing here commits: the worker, which owns its jobs' transactions, does."""
import datetime
import json
import os
import threading
from contextlib import asynccontextmanager
from decimal import Decimal

from pydantic_ai.models.wrapper import WrapperModel

BUILDS = os.path.join("workouts", ".logs", "builds.jsonl")   # under the job's home, as the engine writes it
KEY_URL = "https://openrouter.ai/api/v1/key"
RENDERS = ("mp3", "failed")   # the builds.jsonl lines that each stand for one render's characters (tools/records.py)


def _cost(response) -> Decimal:
    details = getattr(response, "provider_details", None) or {}
    try:
        return max(Decimal(0), Decimal(str(details.get("cost") or 0)))
    except ArithmeticError:
        return Decimal(0)


class Metered(WrapperModel):
    """A model that adds up what OpenRouter charged for each of its replies."""

    def __init__(self, wrapped):
        super().__init__(wrapped)
        self._lock = threading.Lock()
        self._usd = Decimal(0)
        self.replies = 0

    @property
    def usd(self) -> Decimal:
        with self._lock:
            return self._usd

    def supported_native_tools(self):
        """The wrapped model's (its web search): a wrapper that hid them would quietly take the research away."""
        return self.wrapped.supported_native_tools()

    def _add(self, response) -> None:
        with self._lock:
            self._usd += _cost(response)
            self.replies += 1

    async def request(self, messages, model_settings, model_request_parameters):
        response = await super().request(messages, model_settings, model_request_parameters)
        self._add(response)
        return response

    @asynccontextmanager
    async def request_stream(self, messages, model_settings, model_request_parameters, run_context=None):
        async with super().request_stream(messages, model_settings, model_request_parameters, run_context) as stream:
            try:
                yield stream
            finally:
                self._add(stream.get())


def builds_lines(home: str) -> int:
    """How many lines builds.jsonl holds now: a job counts the ones it adds from here."""
    try:
        with open(os.path.join(home, BUILDS), encoding="utf-8") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def voice_usd(home: str, before: int) -> Decimal:
    """The estimates on the lines builds.jsonl gained since it held `before`: what this job's renders cost."""
    total = Decimal(0)
    try:
        with open(os.path.join(home, BUILDS), encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < before:
                    continue
                try:
                    rec = json.loads(line)
                    usd = rec.get("usd_estimate")
                except (ValueError, AttributeError):
                    continue
                if rec.get("kind", "mp3") not in RENDERS:   # a build's outcome line repeats no render
                    continue
                if isinstance(usd, (int, float)) and not isinstance(usd, bool) and usd > 0:
                    total += Decimal(str(usd))
    except OSError:
        pass
    return total


def record(conn, user_id, job_id, kind: str, usd: Decimal, estimated: bool = False) -> None:
    """A cost row, when there's anything to record."""
    if usd <= 0:
        return
    conn.execute("insert into costs (user_id, job_id, kind, usd, estimated) values (%s, %s, %s, %s, %s)",
                 (user_id, job_id, kind, usd, estimated))


def read_spend(conn, key: str, get=None) -> float | None:
    """OpenRouter's own count of what the site's key spent today (UTC), kept as today's provider_spend (each read
    replaces the last, so the day ends at its final reading). The dollars, or None when it couldn't be read."""
    if not key:
        return None
    try:
        data = (get or _get)(key)
        usd = float(data["data"]["usage_daily"])
    except Exception:  # noqa: BLE001 - a failed read leaves the day as it was, never as nothing spent
        return None
    if usd < 0:
        return None
    day = datetime.datetime.now(datetime.timezone.utc).date()
    conn.execute("insert into provider_spend (day, usd) values (%s, %s) on conflict (day) do update "
                 "set usd = greatest(provider_spend.usd, excluded.usd), read_at = now()", (day, usd))
    return usd


def _get(key: str) -> dict:
    import httpx
    r = httpx.get(KEY_URL, headers={"Authorization": f"Bearer {key}"}, timeout=10, follow_redirects=False)
    r.raise_for_status()
    return r.json()
