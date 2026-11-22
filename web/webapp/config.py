"""Settings from the environment. Messages name a variable, never its value."""
import base64
import binascii
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Mapping

from . import spend

ROLES = ("web", "worker")
WRITERS = ("one", "three")   # who writes a script's words: the agent, in passes, or the writers' room


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str = field(repr=False)
    master_key: bytes = field(repr=False)
    base_url: str
    role: str = "web"
    engine_root: str = ""
    session_days: int = 90
    registration: bool = True
    daily_chars: int = spend.DEFAULT_DAILY_CHARS   # each listener's daily allowance for recordings
    writers: str = "three"       # who writes a script's words (WRITERS)
    worker_slots: int = 2        # main-lane loops a worker runs side by side (1 to MAX_SLOTS)
    # Sign-in through Clerk (0.85.0): with both set, the site's own username and password routes are off
    clerk_publishable_key: str = ""
    clerk_secret_key: str = field(default="", repr=False)
    # Minute packs through Stripe: Checkout needs the secret key, the webhook its signing secret
    stripe_secret_key: str = field(default="", repr=False)
    stripe_webhook_secret: str = field(default="", repr=False)
    # The site's own OpenRouter key: it writes and speaks every workout, paid for in minutes (webapp.hosted)
    openrouter_key: str = field(default="", repr=False)
    # The admin screen (0.87.0): the account ids (never usernames, which can be taken again) that may open it
    admins: tuple[str, ...] = ()
    # A read-only Fly token, for the admin screen's estimate of what the site's machines and volumes cost
    fly_token: str = field(default="", repr=False)
    fly_app: str = ""

    @property
    def clerk(self) -> bool:
        return bool(self.clerk_publishable_key and self.clerk_secret_key)

    @property
    def stripe(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def _daily_chars(env: Mapping[str, str]) -> int:
    try:
        return max(0, int(env.get("HARMONICFITNESS_DAILY_CHARS", spend.DEFAULT_DAILY_CHARS)))
    except ValueError:
        return spend.DEFAULT_DAILY_CHARS


def _writers(env: Mapping[str, str]) -> str:
    """Three writers write the script (0.51.0); HARMONICFITNESS_WRITERS=one has the agent write it, in passes."""
    wanted = env.get("HARMONICFITNESS_WRITERS", "three")
    return wanted if wanted in WRITERS else "three"


MAX_SLOTS = 4   # main-lane loops a worker may run: each turn's engine and the model's answers share its memory


def _worker_slots(env: Mapping[str, str]) -> int:
    """HARMONICFITNESS_WORKER_SLOTS: turns a worker runs at once (0.77.0); 1 is how it ran before."""
    try:
        return min(MAX_SLOTS, max(1, int(env.get("HARMONICFITNESS_WORKER_SLOTS", 2))))
    except ValueError:
        return 2


def _admins(env: Mapping[str, str]) -> tuple[str, ...]:
    """HARMONICFITNESS_ADMINS: account ids, by commas or spaces. A malformed one makes no one an admin and is said
    in the log; it never stops the site (a typo in the admin list shouldn't take the site down)."""
    out = []
    for part in env.get("HARMONICFITNESS_ADMINS", "").replace(",", " ").split():
        try:
            out.append(str(uuid.UUID(part)))
        except ValueError:
            print("config: HARMONICFITNESS_ADMINS lists account ids (python -m webapp.admin id <username>); one entry "
                  "isn't one and is ignored", file=sys.stderr, flush=True)
    return tuple(out)


def load(env: Mapping[str, str]) -> Settings:
    database_url = _required(env, "DATABASE_URL")
    base_url = _required(env, "HARMONICFITNESS_BASE_URL")
    raw = _required(env, "HARMONICFITNESS_MASTER_KEY")
    try:
        master = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ConfigError("HARMONICFITNESS_MASTER_KEY is not valid base64") from None
    if len(master) != 32:
        raise ConfigError("HARMONICFITNESS_MASTER_KEY must decode to exactly 32 bytes")
    role = env.get("HARMONICFITNESS_ROLE", "web").strip()
    if role not in ROLES:
        raise ConfigError("HARMONICFITNESS_ROLE must be 'web' or 'worker'")
    reg = env.get("HARMONICFITNESS_REGISTRATION", "open").strip().lower() or "open"
    if reg not in ("open", "closed"):
        raise ConfigError("HARMONICFITNESS_REGISTRATION must be 'open' or 'closed'")
    root = env.get("HARMONICFITNESS_ENGINE_ROOT", "").strip() or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    get = lambda *names: next((v for v in (env.get(n, "").strip() for n in names) if v), "")  # noqa: E731
    clerk = (get("CLERK_PUBLISHABLE_KEY", "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY"), get("CLERK_SECRET_KEY"))
    if bool(clerk[0]) != bool(clerk[1]):
        raise ConfigError("CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY go together: set both, or neither")
    stripe = (get("STRIPE_SECRET_KEY", "STRIPE_API_SECRET_KEY"), get("STRIPE_WEBHOOK_SECRET"))
    openrouter = _required(env, "OPENROUTER_API_KEY")   # the site's own key: it writes and speaks every workout
    return Settings(database_url=database_url, master_key=master, base_url=base_url,
                    role=role, engine_root=root, registration=reg == "open",
                    daily_chars=_daily_chars(env), writers=_writers(env),
                    worker_slots=_worker_slots(env), clerk_publishable_key=clerk[0], clerk_secret_key=clerk[1],
                    stripe_secret_key=stripe[0], stripe_webhook_secret=stripe[1],
                    openrouter_key=openrouter, admins=_admins(env), fly_token=get("FLY_API_TOKEN"),
                    fly_app=get("FLY_APP_NAME"))
