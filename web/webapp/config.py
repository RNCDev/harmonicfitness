"""Settings from the environment. Messages name a variable, never its value."""
import base64
import binascii
import os
from dataclasses import dataclass, field
from typing import Mapping

ROLES = ("web", "worker")


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
    providers: tuple[str, ...] = ("anthropic",)


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def load(env: Mapping[str, str]) -> Settings:
    from . import providers     # providers imports ConfigError from here
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
    return Settings(database_url=database_url, master_key=master, base_url=base_url,
                    role=role, engine_root=root, registration=reg == "open",
                    providers=tuple(providers.offered(env)))
