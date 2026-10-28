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


PROVIDERS: dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Claude", "claude-sonnet-5-5", "https://console.anthropic.com/settings/keys"),
    Provider("openai", "ChatGPT", "gpt-6.1-sol", "https://platform.openai.com/api-keys"),
    Provider("google", "Gemini", "gemini-3.8-flash", "https://aistudio.google.com/apikey"),
)}


def offered(env: Mapping[str, str]) -> list[str]:
    raw = env.get("HARMONICFITNESS_PROVIDERS", "").strip()
    if not raw:
        return ["anthropic"]
    ids = [part.strip() for part in raw.split(",") if part.strip()]
    for pid in ids:
        if pid not in PROVIDERS:
            raise ConfigError(f"HARMONICFITNESS_PROVIDERS names an unknown provider: {pid}")
    return [pid for pid in PROVIDERS if pid in ids] or ["anthropic"]


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
            return ProviderFailed(f"{name} refused the key. Replace it in Keys.", "auth")
        if status == 429 or (status == 400 and any(w in body for w in _QUOTA_WORDS)):
            return ProviderFailed(f"{name} says the account is out of credit or over its limit.", "quota")
        if status >= 500:
            return ProviderFailed(f"{name} didn't answer. Try again in a minute.", "unavailable")
    elif isinstance(exc, (ModelAPIError, TimeoutError, ConnectionError)):
        return ProviderFailed(f"{name} didn't answer. Try again in a minute.", "unavailable")
    elif isinstance(exc, UnexpectedModelBehavior):
        return ProviderFailed(f"{name} couldn't make a plan from the menu; try again.", "other")
    return ProviderFailed(f"{name} stopped with an error.", "other")
