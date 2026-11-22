import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from webapp import providers  # noqa: E402

KEY = "sk-secret-" + "k" * 20


class ModelFor(unittest.TestCase):
    def test_no_model_ever_retries_and_google_times_out_at_180s(self):
        for pid in ("anthropic", "openai", "openrouter"):
            self.assertEqual(providers.model_for(pid, "k" * 20).client.max_retries, 0, pid)
        self.assertEqual(str(providers.model_for("openrouter", "k" * 20).client.base_url).rstrip("/"),
                         "https://openrouter.ai/api/v1")
        m = providers.model_for("google", "k" * 20)
        # _api_client._http_options is private to google-genai; it is where the Client keeps them.
        opts = m.client._api_client._http_options
        self.assertEqual(opts.retry_options.attempts, 1)
        self.assertEqual(opts.timeout, 180000)


def _agent():
    from pydantic_ai import Agent
    return Agent(output_type=str, retries=0)


def _anthropic_model(status, body):
    import httpx2
    from anthropic import AsyncAnthropic
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider
    seen = []

    def handler(request):
        seen.append(request)
        return httpx2.Response(status, json=body)

    client = AsyncAnthropic(api_key=KEY, max_retries=0,
                            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))
    return AnthropicModel(providers.PROVIDERS["anthropic"].model,
                          provider=AnthropicProvider(anthropic_client=client)), seen


class Explain(unittest.TestCase):
    def _run(self, status, body):
        m, seen = _anthropic_model(status, body)
        with self.assertRaises(Exception) as cm:
            _agent().run_sync("hi", model=m)
        return providers.explain("anthropic", cm.exception), seen

    def test_a_refused_key_or_a_server_error_is_sent_once_and_never_shows_the_key(self):
        for status, body, kind, message in (
                (401, {"error": {"type": "authentication_error", "message": "bad " + KEY}}, "auth",
                 "Claude refused the key."),
                (500, {"error": {"type": "api_error", "message": "boom"}}, "unavailable",
                 "Claude didn't answer. Try again in a minute.")):
            with self.subTest(status=status):
                err, seen = self._run(status, body)
                self.assertEqual(len(seen), 1)
                self.assertEqual((err.kind, err.message), (kind, message))
                self.assertNotIn(KEY, err.message)


if __name__ == "__main__":
    unittest.main()
