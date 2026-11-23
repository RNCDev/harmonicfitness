"""The language models a script can be written with, never retried. The site writes with OpenRouter
(webapp.hosted.SERVICE) on its own key; the others are kept for the writing bench (web/bench/).

PROVIDERS imports no SDK; only model_for and explain do. Nothing here is retried once it may have reached a paid
service."""
from dataclasses import dataclass

TIMEOUT = 180


@dataclass(frozen=True)
class Provider:
    id: str
    name: str
    model: str


PROVIDERS: dict[str, Provider] = {p.id: p for p in (
    Provider("anthropic", "Claude", "claude-sonnet-5-5"),
    Provider("openai", "ChatGPT", "gpt-6.1-sol"),
    Provider("google", "Gemini", "gemini-3.8-flash"),
    # OpenRouter: one key for any model; the same key voices its stock-voice coaches (one id, one row). It writes
    # with Gemini 3.8 Flash, as the Gemini key does, at the same thinking levels (writers.thinking_settings): a
    # 15-minute workout cost 17 to 21 cents on Gemini and about $2.10 on Opus (the bench, 2026-11-10), and a
    # 20-minute one 17 to 22 cents on Gemini in 0.91.3 (2026-11-22)
    Provider("openrouter", "OpenRouter", "google/gemini-3.8-flash"),
)}


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
    if provider == "openrouter":
        from openai import AsyncOpenAI
        from pydantic_ai.models.openrouter import OpenRouterModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider
        client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1", max_retries=0, timeout=TIMEOUT)
        return OpenRouterModel(spec.model, provider=OpenRouterProvider(openai_client=client))
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
            return ProviderFailed(f"{name} refused the key.", "auth")
        if status == 429 or (status == 400 and any(w in body for w in _QUOTA_WORDS)):
            return ProviderFailed(f"{name} says the account is out of credit or over its limit.", "quota")
        if status >= 500:
            return ProviderFailed(f"{name} didn't answer. Try again in a minute.", "unavailable")
    elif isinstance(exc, (ModelAPIError, TimeoutError, ConnectionError)):
        return ProviderFailed(f"{name} didn't answer. Try again in a minute.", "unavailable")
    elif isinstance(exc, UnexpectedModelBehavior):
        return ProviderFailed(f"{name} couldn't make a plan from the menu; try again.", "other")
    return ProviderFailed(f"{name} stopped with an error.", "other")
