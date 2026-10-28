# M3 research: Pydantic AI over Anthropic / OpenAI / Gemini, per-request user keys

Checked 2026-10-28. "VERIFIED-LOCAL" = I installed the package in a throwaway venv (Python 3.11) and ran the code, with fake HTTP transports and FunctionModel; no paid calls, no real keys.

## 1. Version to pin
- PyPI https://pypi.org/pypi/pydantic-ai/json (2026-10-28): latest stable 2.63.0 (2026-10-28). Python `>=3.11`. Releases are near-daily; the 2.x line began 2026-06-23 (2.0.0).
- Releases >= 2 weeks old (before 2026-10-14): **2.56.0 (2026-10-13, 15 days old)**; 2.55.0 (10-09). 2.57.0 is 10-16, too new.
- Install: `pydantic-ai-slim[anthropic,openai,google]==2.56.0` (slim: `Requires-Python >=3.11`; extras `anthropic` -> `anthropic`, `openai` -> `openai>=3.19` + `tiktoken`, `google` -> `google-genai>=2.25`). Source: https://pypi.org/pypi/pydantic-ai-slim/2.54.0/json (same extras), plus my install of 2.56.0.
- **GOTCHA (VERIFIED-LOCAL): pydantic-ai-slim 2.56.0 + anthropic SDK 2.x is broken.** The extra says only `anthropic>=1.9.0`, so a fresh resolve gets anthropic 2.0.0-2.3.0 (released 2026-10-21..23), and the first Anthropic request dies with `TypeError: Cannot instantiate typing.Union` (`BetaMessageParam` in `_map_message`). Fix: pin **`anthropic<2`** (tested: 1.17.0 works; 1.12.0 works). pydantic-ai 2.63.0 works with anthropic 2.3.0, but is under 2 weeks old. Tested resolved set: openai 3.40.0, google-genai 2.33.0 (both fine).
- Note the 2.x renames: "builtin tools" are now **native tools** (`pydantic_ai.native_tools`, enabled via `capabilities=[NativeTool(...)]`), `result.usage` is a **property** (not a call), and `pydantic_ai.builtin_tools` is gone.

## 2. Model with an explicit key per call (VERIFIED-LOCAL signatures, v2.56.0)
```python
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

# Anthropic: AnthropicProvider(*, api_key=None, base_url=None, anthropic_client=None, http_client=None)
m = AnthropicModel("claude-sonnet-5-5", provider=AnthropicProvider(
    anthropic_client=AsyncAnthropic(api_key=user_key, max_retries=0, timeout=600)))
# (passing both api_key= and anthropic_client= asserts: "Cannot provide both")
# OpenAI: OpenAIProvider(base_url=None, api_key=None, openai_client=None, http_client=None)
m = OpenAIResponsesModel("gpt-6.1-sol", provider=OpenAIProvider(
    openai_client=AsyncOpenAI(api_key=user_key, max_retries=0)))
# Google: GoogleProvider(*, api_key=None, client=None, http_client=None, base_url=None, retry_options=None)
m = GoogleModel("gemini-3.8-flash", provider=GoogleProvider(api_key=user_key))
```
- Agent can be built once with no model (`Agent(output_type=..., deps_type=...)`) and the model passed per run: `agent.run_sync(prompt, model=m, deps=..., ...)` (VERIFIED-LOCAL). Never use string ids like `"anthropic:claude-..."`: those build the provider from process env vars.
- Using `AnthropicProvider(api_key=...)` alone is also fine for the key, but then the SDK's default 2 retries apply (see 9).
- Sources: https://pydantic.dev/docs/ai/tools-toolsets/native-tools/index.md (uses `'openai-responses:...'`, `'anthropic:...'` ids); signatures read from the installed package.

## 3. Tools, structured returns, ending the run to ask the user (VERIFIED-LOCAL end to end)
```python
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import (Agent, RunContext, CallDeferred, DeferredToolRequests,
                         DeferredToolResults, ModelMessagesTypeAdapter)

@dataclass
class Deps: user_id: int

agent = Agent(output_type=[Plan, DeferredToolRequests], deps_type=Deps)  # Plan = BaseModel

@agent.tool                      # takes RunContext[Deps]; @agent.tool_plain does not
def lookup(ctx: RunContext[Deps], q: str) -> dict:   # any JSON-serialisable / pydantic value is the result
    return {"q": q, "uid": ctx.deps.user_id}

@agent.tool_plain
def ask_user(question: str) -> str:
    raise CallDeferred(metadata={"kind": "question"})   # ends the run here
```
- The run returns `result.output` as `DeferredToolRequests(calls=[ToolCallPart(tool_name='ask_user', args={'question': ...}, tool_call_id='c2')], approvals=[], metadata={'c2': {...}})`. The deferred output type MUST be in `output_type` (otherwise error). Other pending tool calls in the same model response still run; only the deferred ones wait.
- Resume (a new run, new `run_id`, same `conversation_id`):
  `agent.run_sync(None, message_history=history, deferred_tool_results=DeferredToolResults(calls={"c2": "I am 40"}), model=..., deps=...)`. The answer becomes that call's ToolReturnPart. A value may be any return, a `ToolReturn`, `ModelRetry` or `ToolFailed`.
- `requires approval` variant: `ApprovalRequired` / `@agent.tool(requires_approval=True)` -> goes in `.approvals`, answered via `DeferredToolResults(approvals={id: True|False|ToolApproved/ToolDenied})`. Not needed for a question.
- Alternative with no deferral: make a question a normal structured output (`output_type=[Plan, Question]`), then the next run is just a new user prompt with `message_history`. Simpler, but the model's "answer" is a user message, not the tool result; deferred keeps the call/result pairing the providers require.
- **Persisting a pending deferral across processes**: the docs say the messages alone do not carry which calls are deferred plus their metadata; use `ConversationTypeAdapter`:
```python
from pydantic_ai import ConversationTypeAdapter
blob = ConversationTypeAdapter.dump_json(result.conversation)        # bytes; store it
conv = ConversationTypeAdapter.validate_json(blob)                   # later process
res = conv.deferred_tool_requests.build_results(calls={"c2": "I am 40"})  # validates ids
agent.run_sync(None, conversation=conv, deferred_tool_results=res, model=..., deps=...)
```
  I also verified the simpler `all_messages_json()` -> `ModelMessagesTypeAdapter.validate_json()` -> `message_history=` + `DeferredToolResults(calls={id: answer})` works; so you can store `calls[i].tool_call_id` yourself from the first output. Recommended: store `ConversationTypeAdapter` blob (carries metadata too).
- Sources: https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/index.md (checked 2026-10-28); local run.

## 4. Message history (VERIFIED-LOCAL)
```python
js: bytes = result.all_messages_json()                     # full run incl. tool calls/returns, thinking, native-tool parts
history = ModelMessagesTypeAdapter.validate_json(js)       # fresh process
agent.run_sync("next user text", message_history=history, ...)
# or python objects: ModelMessagesTypeAdapter.dump_python(msgs, mode="json")
```
- Round trip with ToolCall/ToolReturn parts and a deferred call worked (2.3 KB for a 3-request run). Provider-specific parts (Anthropic thinking signatures, OpenAI Responses reasoning item ids, native web-search parts) are stored in the same typed parts with `provider_name` / `provider_details`; replay to the SAME provider works. Cross-provider replay: pydantic-ai drops or converts foreign thinking/native parts, but I did NOT test it, so UNCONFIRMED; you said it isn't needed. Keep the model id with the stored history (replaying an OpenAI Responses reasoning id to a different model can be rejected by the provider; UNCONFIRMED).
- `all_messages()` includes previous history; `new_messages()` only this run.

## 5. Web search (native tool)
```python
from pydantic_ai import Agent, WebSearchTool
from pydantic_ai.capabilities import NativeTool, WebSearch
agent = Agent(capabilities=[NativeTool(WebSearchTool(max_uses=5))])
# or capability form: WebSearch(max_uses=5)  (raises UserError on unsupported models unless local='duckduckgo')
```
Source: https://pydantic.dev/docs/ai/tools-toolsets/native-tools/index.md (2026-10-28); `WebSearchTool` signature read locally: `(kind, optional=False, search_context_size='medium', user_location, blocked_domains, allowed_domains, max_uses, external_web_access)`; `optional=True` silently omits it on models that can't do it.
- Supported: Anthropic (full), OpenAI **Responses** only (NOT Chat Completions), Google (no parameters supported), plus xAI/Groq/OpenRouter. Not Bedrock/Mistral/Cohere/HF.
- Params: `search_context_size` OpenAI only; `max_uses` Anthropic only; `allowed_domains`/`blocked_domains` OpenAI+Anthropic (Anthropic accepts one of the two, not both); Google ignores all (setting `allowed_domains`/`max_uses` on Google makes it "unsupported" -> UserError).
- Results/citations: parts appear on `ModelResponse.native_tool_calls` as call/`NativeToolReturnPart`. OpenAI: set model setting `openai_include_web_search_sources` to get sources in the return part. Google: sources in the return part content under `sources` (Gemini 3). Anthropic: the page doesn't say; see its Citations page (UNCONFIRMED how they surface in 2.56).
- Cost: search count is `web_search_requests` in `RequestUsage.details` and added to `RunUsage.cost`. Google counts one billed search per unique query on Gemini 3 and does NOT subtract Google's free grounding allowance. Provider price lists were not checked here (UNCONFIRMED per-search $).

## 6. Usage limits (VERIFIED-LOCAL)
```python
from pydantic_ai import UsageLimits, UsageLimitExceeded
lim = UsageLimits(request_limit=20, tool_calls_limit=40, total_tokens_limit=300_000)
# 2.56 fields: cost_limit (Decimal), request_limit (default 50!), tool_calls_limit, input/output/total_tokens_limit,
#              per_request_input_tokens_limit, count_tokens_before_request
r = agent.run_sync(..., usage_limits=lim)
r.usage   # PROPERTY: RunUsage(input_tokens=107, output_tokens=16, requests=2, tool_calls=1, details=..., cost?)
```
- Exceeding raises `UsageLimitExceeded` (subclass of `AgentRunError`) before the next request. Default `request_limit` is 50 if you pass none. For a deferred run the usage covers that run only; sum across runs yourself (`usage=` param on `run*` accepts a RunUsage to carry on).

## 7. Offline testing (VERIFIED-LOCAL)
```python
from pydantic_ai.models.test import TestModel
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

def script(messages, info: AgentInfo):
    returned = [p.tool_name for m in messages for p in m.parts if isinstance(p, ToolReturnPart)]
    if not returned:            return ModelResponse(parts=[ToolCallPart('lookup', {'q': 'x'}, tool_call_id='c1')])
    if returned == ['lookup']:  return ModelResponse(parts=[ToolCallPart('ask_user', {'question': 'How old?'}, tool_call_id='c2')])
    return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {'title': 't', 'steps': ['a']}, tool_call_id='c3')])
agent.run_sync("hi", model=FunctionModel(script), deps=Deps(1))
```
- `TestModel()` calls every registered tool once with generated args then returns output; `TestModel(call_tools=[...])` limits which. Final structured output is a tool call named `info.output_tools[i].name` (use `info.output_tools[0]`; with a union output type there is one output tool per member). `agent.override(model=...)` also works. Also `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` to guard tests.
- To fake the HTTP layer of real provider classes (what I used): the SDKs now use **httpx2**, not httpx: `import httpx2; AsyncAnthropic(http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(fn)))`; passing a plain `httpx.AsyncClient` raises TypeError.

## 8. Model ids as of 2026-10-28 (exact strings)
- Anthropic (https://platform.claude.com/docs/en/models/overview, fetched 2026-10-28): `claude-sonnet-5-5` ($2/$10 per MTok, "best combination of speed and intelligence"), `claude-opus-5-5` ($4/$20; page says start here for most workloads), `claude-haiku-5-5` ($0.10/$0.50), `claude-fable-5-1` ($10/$50, hardest long-horizon agentic). Dateless ids are pinned snapshots; 1M context, 128K max output. All four are in pydantic-ai 2.56's `AnthropicModelName`. Notes: Sonnet 5.5 rejects `thinking: {type: "disabled"}` (adaptive only).
- OpenAI (https://developers.openai.com/api/docs/models, fetched 2026-10-28; summarised by fetch tool, so re-check before shipping): flagship `gpt-6-astra` ($10/$50, 1.05M ctx); cost-balanced mainline `gpt-6.1-sol` ($2/$10); `gpt-6.1-terra` ($1/$5); `gpt-6-luna` ($0.10/$0.50). pydantic-ai's docs use `openai-responses:gpt-6.1-sol`. **pydantic-ai 2.56's `OpenAIModelName` literal does not list the gpt-6 ids** (it knows up to gpt-5.5/5.6-*); the type accepts any `str`, so it works but gets no editor completion and its price/profile table may lack them (UNCONFIRMED whether `cost` is computed for them in 2.56).
- Google (https://ai.google.dev/gemini-api/docs/models, fetched 2026-10-28): Flash `gemini-3.8-flash` (stable, newest; page recommends 3.5 Flash-Lite or 3.8 Flash for new projects), `gemini-3.6-flash` (stable), `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`; Pro: only `gemini-3.1-pro-preview` (preview) is listed; `gemini-2.5-pro` is legacy/limited. A stable Gemini Pro id: none listed (UNCONFIRMED whether a newer Pro exists elsewhere).
- Suggestion for "tool-heavy, long structured text": `claude-sonnet-5-5`, `gpt-6.1-sol`, `gemini-3.8-flash` (Pro is preview-only). Keep ids in config, not code.

## 9. Gotchas
- **Retries (VERIFIED-LOCAL via fake transports counting requests on HTTP 500):** Anthropic SDK default = 3 requests (max_retries=2); OpenAI SDK default = 3 requests; with `max_retries=0` on the SDK client each makes exactly 1 request. Google via pydantic-ai `GoogleProvider(api_key=...)` made 1 request by default and 1 with `retry_options=HttpRetryOptions(attempts=1)` (so safe, but pass `retry_options=HttpRetryOptions(attempts=1)` explicitly to stay safe if defaults change). Pydantic AI itself does no HTTP retry at the model layer; `Agent(retries=N)` / `ModelRetry` only re-ask the model after a bad tool call or output validation (each re-ask is a NEW paid request: set `retries=0`/low and a `request_limit`). Also timeouts: SDK default timeout is long (Anthropic 10 min); set `AsyncAnthropic(timeout=...)`, `AsyncOpenAI(timeout=...)`, or `model_settings={'timeout': 120}` (a `ModelSettings` key). A timeout may occur after the provider accepted the request, so treat it as "may have been billed".
- Errors (VERIFIED-LOCAL): in 2.56 every HTTP failure is `pydantic_ai.ModelHTTPError` (`.status_code`, `.body`, `.model_name`; 401 bad key, 429 quota/rate, 5xx) and transport failures are `ModelAPIError` (parent of ModelHTTPError; both under `AgentRunError`). Google with a malformed key short-circuits as ModelHTTPError 400 with 0 requests sent. In 2.63 these are finer subclasses (`ModelAuthenticationError`, `ModelRateLimitError`, `ModelQuotaExceededError`, `ModelServerError`, `ModelTimeoutError`, `ModelOverloadedError`...), still under `ModelAPIError`; in 2.56 branch on `status_code`. Other: `UsageLimitExceeded`, `UnexpectedModelBehavior` (bad output after retries), `UserError` (misconfiguration, e.g. unsupported native tool). The key may appear in exception text/body: scrub before logging (the repo's `redact.scrub`).
- Sync/async: `agent.run_sync` works from a plain worker thread (it runs its own event loop); it fails if called from a thread that already has a running loop. Each `run_sync` call with a new SDK client creates connection pools: build the Model per job and close the client afterwards (`await client.close()` / `asyncio.run`), since keys differ per user, do not cache clients across users. Agent objects (tools, output type) are reusable across runs and users because key/deps/model are per-run arguments; deps are per-run (VERIFIED: model passed to `run_sync`). Thread-safety of one shared `Agent` across concurrent threads: UNCONFIRMED (you run one job at a time per process, so not an issue).
- Process-env keys: `AnthropicProvider()` with no key reads `ANTHROPIC_API_KEY`; with an explicit `api_key`/client it does not. Pass explicit clients always; do not set provider env vars.
- Banner: set `PYDANTIC_AI_NO_BANNER=1` (a startup banner prints in 2.56 otherwise; goes to the console).
- The user key must be checked for stray whitespace/newlines before use (HarmonicFitness `keys.BadKey` pattern); the SDKs raise confusing header errors otherwise.
