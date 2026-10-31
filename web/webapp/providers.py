"""The language-model providers, each over the listener's own key, never retried.

PROVIDERS and offered import no SDK (the web process imports this through config); only model_for
and explain do. Nothing here is retried once it may have reached a paid service."""
from dataclasses import dataclass
from typing import Mapping

from .config import ConfigError

TIMEOUT = 180


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    model: str
    key_page: str
    billing_page: str   # where the listener sees what's left (no provider reports it to a plain key)


PROVIDERS: dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Claude", "claude-sonnet-5-5", "https://console.anthropic.com/settings/keys",
             "https://console.anthropic.com/settings/billing"),
    Provider("openai", "ChatGPT", "gpt-6.1-sol", "https://platform.openai.com/api-keys",
             "https://platform.openai.com/settings/organization/billing/overview"),
    Provider("google", "Gemini", "gemini-3.8-flash", "https://aistudio.google.com/apikey",
             "https://aistudio.google.com/billing"),
)}


# A provider whose key is also a voice service's: one key, stored under the voice service's id (a key
# stored under the provider's own id, from before 0.25.2, still counts for both).
SHARED_KEY: dict[str, str] = {"google": "gemini"}


def key_service(provider: str) -> str:
    """The id a provider's key is stored and listed under."""
    return SHARED_KEY.get(provider, provider)


def stored_key(stored: Mapping[str, object], provider: str):
    """A provider's stored entry (a key, or when it was set), under its shared id or its own, else None."""
    return stored.get(key_service(provider)) or stored.get(provider)


def provider_of(service: str) -> str:
    """The provider whose key is stored under `service` (Gemini's under "gemini"): the inverse of key_service."""
    return next((p for p, s in SHARED_KEY.items() if s == service), service)


def pick(offered_ids, stored: Mapping[str, object], chosen: str | None) -> str | None:
    """The provider that writes this listener's workouts: the one they chose, when it's offered and has a key;
    else the first offered that has one; else None."""
    if chosen in offered_ids and stored_key(stored, chosen):
        return chosen
    return next((p for p in offered_ids if stored_key(stored, p)), None)


def offered(env: Mapping[str, str]) -> list[str]:
    """The providers a listener can choose from: HARMONICFITNESS_PROVIDERS, else all of them."""
    raw = env.get("HARMONICFITNESS_PROVIDERS", "").strip()
    if not raw:
        return list(PROVIDERS)
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    for pid in ids:
        if pid not in PROVIDERS:
            raise ConfigError(f"HARMONICFITNESS_PROVIDERS names an unknown provider: {pid}")
    return [pid for pid in PROVIDERS if pid in ids] or list(PROVIDERS)


def model_for(provider: str, key: str):
    """A pydantic-ai Model on this key. Imports the SDKs here, not at module load."""
    spec = PROVIDERS[provider]
    if provider == "anthropic":
        from anthropic import AsyncAnthropic
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        client = AsyncAnthropic(api_key=key, max_retries=0, timeout=TIMEOUT)
        return AnthropicModel(spec.model, provider=AnthropicProvider(anthropic_client=client))
    if provider == "openai":
        from openai import AsyncOpenAI
        from pydantic_ai.models.openai import OpenAIResponsesModel
        from pydantic_ai.providers.openai import OpenAIProvider
        client = AsyncOpenAI(api_key=key, max_retries=0, timeout=TIMEOUT)
        return OpenAIResponsesModel(spec.model, provider=OpenAIProvider(openai_client=client))
    if provider == "google":
        from google.genai.types import HttpOptions, HttpRetryOptions
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider
        # The 180 s timeout is in milliseconds for google-genai; attempts=1 means no retry.
        client_opts = HttpOptions(timeout=TIMEOUT * 1000, retry_options=HttpRetryOptions(attempts=1))
        from google.genai import Client
        client = Client(api_key=key, http_options=client_opts)
        return GoogleModel(spec.model, provider=GoogleProvider(client=client))
    raise KeyError(provider)


class ProviderFailed(Exception):
    def __init__(self, message: str, kind: str):
        super().__init__(message)
        self.message = message
        self.kind = kind


_QUOTA_WORDS = ("credit", "billing", "quota")


def explain(provider: str, exc: Exception) -> ProviderFailed:
    """What went wrong, in plain words that name the provider and never the key."""
    from pydantic_ai import ModelHTTPError, UnexpectedModelBehavior
    from pydantic_ai.exceptions import ModelAPIError
    name = PROVIDERS[provider].name
    if isinstance(exc, ModelHTTPError):
        status = exc.status_code
        body = str(exc.body).lower()
        if status in (401, 403):
            return ProviderFailed(f"{name} refused the key. Replace it in Settings.", "auth")
        if status == 429 or (status == 400 and any(w in body for w in _QUOTA_WORDS)):
            return ProviderFailed(f"{name} says the account is out of credit or over its limit.", "quota")
        if status >= 500:
            return ProviderFailed(f"{name} didn't answer. Try again in a minute.", "unavailable")
    elif isinstance(exc, (ModelAPIError, TimeoutError, ConnectionError)):
        return ProviderFailed(f"{name} didn't answer. Try again in a minute.", "unavailable")
    elif isinstance(exc, UnexpectedModelBehavior):
        return ProviderFailed(f"{name} couldn't make a plan from the menu; try again.", "other")
    return ProviderFailed(f"{name} stopped with an error.", "other")
