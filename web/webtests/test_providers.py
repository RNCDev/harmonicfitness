import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from webapp import config, providers  # noqa: E402

KEY = "sk-secret-" + "k" * 20


class Offered(unittest.TestCase):
    def test_offered(self):
        self.assertEqual(providers.offered({}), ["anthropic"])
        self.assertEqual(providers.offered({"HARMONICFITNESS_PROVIDERS": " google, anthropic "}),
                         ["anthropic", "google"])
        with self.assertRaises(config.ConfigError) as cm:
            providers.offered({"HARMONICFITNESS_PROVIDERS": "nope"})
        self.assertIn("nope", str(cm.exception))

    def test_table(self):
        self.assertEqual(list(providers.PROVIDERS), ["anthropic", "openai", "google"])
        self.assertEqual([p.name for p in providers.PROVIDERS.values()], ["Claude", "ChatGPT", "Gemini"])


class ModelFor(unittest.TestCase):
    def test_model_for_builds_each_with_the_key(self):
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.models.openai import OpenAIResponsesModel
        classes = {"anthropic": AnthropicModel, "openai": OpenAIResponsesModel, "google": GoogleModel}
        for pid, cls in classes.items():
            m = providers.model_for(pid, "k" * 20)
            self.assertIsInstance(m, cls)
            self.assertEqual(m.model_name, providers.PROVIDERS[pid].model)
        self.assertEqual(providers.model_for("anthropic", "k" * 20).client.max_retries, 0)
        self.assertEqual(providers.model_for("openai", "k" * 20).client.max_retries, 0)

    def test_google_never_retries_and_times_out_at_180s(self):
        m = providers.model_for("google", "k" * 20)
        # _api_client._http_options is private to google-genai; it is where the Client keeps them.
        opts = m.client._api_client._http_options
        self.assertEqual(opts.retry_options.attempts, 1)
        self.assertEqual(opts.timeout, 180000)

    def test_google_provider_keeps_the_client_we_passed(self):
        from unittest import mock
        import google.genai
        made = []
        real = google.genai.Client

        def spy(*a, **kw):
            made.append(real(*a, **kw))
            return made[-1]

        with mock.patch("google.genai.Client", spy):
            m = providers.model_for("google", "k" * 20)
        self.assertEqual(len(made), 1)
        self.assertIs(m._provider.client, made[0])
        self.assertIs(m.client, made[0])


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

    def test_refused_key_fails_once(self):
        err, seen = self._run(401, {"error": {"type": "authentication_error", "message": "bad " + KEY}})
        self.assertEqual(len(seen), 1)
        self.assertEqual(err.kind, "auth")
        self.assertIn("Claude", err.message)
        self.assertNotIn(KEY, err.message)
        self.assertEqual(err.message, "Claude refused the key. Replace it in Settings.")

    def test_server_error_is_not_retried(self):
        err, seen = self._run(500, {"error": {"type": "api_error", "message": "boom"}})
        self.assertEqual(len(seen), 1)
        self.assertEqual(err.kind, "unavailable")
        self.assertEqual(err.message, "Claude didn't answer. Try again in a minute.")

    def test_explain_quota(self):
        err, seen = self._run(429, {"error": {"type": "rate_limit_error", "message": "slow"}})
        self.assertEqual((err.kind, len(seen)), ("quota", 1))
        err, seen = self._run(400, {"error": {"message": "Your credit balance is too low"}})
        self.assertEqual((err.kind, len(seen)), ("quota", 1))
        self.assertEqual(err.message, "Claude says the account is out of credit or over its limit.")

    def test_other_cases(self):
        from pydantic_ai import ModelHTTPError, UnexpectedModelBehavior
        from pydantic_ai.exceptions import ModelAPIError
        e = providers.explain("openai", ModelHTTPError(400, "m", {"error": {"message": "bad request"}}))
        self.assertEqual((e.kind, e.message), ("other", "ChatGPT stopped with an error."))
        e = providers.explain("google", ModelHTTPError(403, "m", None))
        self.assertEqual(e.kind, "auth")
        e = providers.explain("google", ModelAPIError("m", "connection reset"))
        self.assertEqual(e.kind, "unavailable")
        e = providers.explain("google", TimeoutError())
        self.assertEqual(e.kind, "unavailable")
        e = providers.explain("anthropic", UnexpectedModelBehavior("invalid " + KEY))
        self.assertEqual((e.kind, e.message),
                         ("other", "Claude couldn't make a plan from the menu; try again."))
        e = providers.explain("anthropic", ValueError(KEY))
        self.assertEqual(e.message, "Claude stopped with an error.")
        self.assertNotIn(KEY, e.message)


if __name__ == "__main__":
    unittest.main()
