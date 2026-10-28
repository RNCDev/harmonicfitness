"""Settings from the environment. Messages name a variable, never its value."""
import base64
import binascii
import os
from dataclasses import dataclass
from typing import Mapping

ROLES = ("web", "worker")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str
    master_key: bytes
    base_url: str
    role: str = "web"
    engine_root: str = ""
    session_days: int = 90
    invite_days: int = 7


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set")
    return value


def load(env: Mapping[str, str]) -> Settings:
    database_url = _required(env, "DATABASE_URL")
    base_url = _required(env, "WT_BASE_URL")
    raw = _required(env, "WT_MASTER_KEY")
    try:
        master = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ConfigError("WT_MASTER_KEY is not valid base64") from None
    if len(master) != 32:
        raise ConfigError("WT_MASTER_KEY must decode to exactly 32 bytes")
    role = env.get("WT_ROLE", "web").strip() or "web"
    if role not in ROLES:
        raise ConfigError("WT_ROLE must be 'web' or 'worker'")
    root = env.get("WT_ENGINE_ROOT", "").strip() or os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return Settings(database_url=database_url, master_key=master, base_url=base_url,
                    role=role, engine_root=root)
