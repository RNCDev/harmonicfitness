"""A Claude model reached through the Claude Code CLI (`claude -p`), for the bench only: the writers' room's own code
runs against it with no key and no provider bill, so a change to the room's structure can be tried many times before
a paid run confirms it on the site's model. Never the site's writer.

Each request is one headless CLI call: the writer's instructions as the system prompt, the conversation flattened
to one prompt, the writer's output type as the CLI's JSON schema, and the CLI's own web search where the room
offers search. An answer is kept by what was asked (model, instructions, prompt, schema, search, salt), so an arm of
a comparison that asks a writer the same thing gets the same answer back, and two arms differ only in the step under
test. A different `salt` asks afresh.
"""
import asyncio
import hashlib
import json
import os
import tempfile
import time

from pydantic_ai.messages import (ModelRequest, ModelResponse, NativeToolCallPart, RetryPromptPart, TextPart,
                                  ToolCallPart, ToolReturnPart, UserPromptPart)
from pydantic_ai.models import Model
from pydantic_ai.usage import RequestUsage

AT_ONCE = 4          # CLI calls running at once in this process
SECONDS = 900        # the longest one call is waited for
TRIES = 2            # a call that fails or returns no structured answer is asked once more


def flatten(messages) -> str:
    """The conversation as one prompt: a single request as it stands, a longer one as a labelled transcript."""
    turns = []
    for m in messages:
        if isinstance(m, ModelRequest):
            for p in m.parts:
                if isinstance(p, UserPromptPart):
                    text = p.content if isinstance(p.content, str) else " ".join(c for c in p.content if isinstance(c, str))
                    turns.append(("request", text))
                elif isinstance(p, RetryPromptPart):
                    turns.append(("request", "Your last answer was refused: " + p.model_response()))
                elif isinstance(p, ToolReturnPart):
                    pass   # the output tool's own "final result processed"
        else:
            for p in m.parts:
                if isinstance(p, ToolCallPart):
                    turns.append(("answer", p.args if isinstance(p.args, str) else json.dumps(p.args, ensure_ascii=False)))
                elif isinstance(p, TextPart):
                    turns.append(("answer", p.content))
    if len(turns) == 1:
        return turns[0][1]
    out = []
    for i, (kind, text) in enumerate(turns):
        last = i == len(turns) - 1
        head = "# Now" if last else ("# An earlier request" if kind == "request" else "# Your answer to it")
        out.append(f"{head}\n\n{text}")
    return "\n\n".join(out)


class ClaudeCLI(Model):
    """`claude -p` as a pydantic-ai model: structured output only, with web search when the request offers it."""

    def __init__(self, name: str = "claude-sonnet-5-5", cache: str | None = None, salt: str = "", effort=None,
                 record=None):
        """`effort` is the CLI's effort level, or a function that gives it for the call about to be made."""
        super().__init__()
        self._name, self.cache, self.salt, self.effort, self.record = name, cache, salt, effort, record
        self._gate = None

    @property
    def model_name(self) -> str:
        return self._name

    @property
    def system(self) -> str:
        return "anthropic"

    @classmethod
    def supported_native_tools(cls):
        from pydantic_ai import WebSearchTool  # noqa: PLC0415
        return frozenset({WebSearchTool})

    async def request(self, messages, model_settings, model_request_parameters) -> ModelResponse:
        params = model_request_parameters
        last = next((m for m in reversed(messages) if isinstance(m, ModelRequest)), None)
        instructions = (last.instructions if last is not None else None) or ""
        prompt = flatten(messages)
        tool = params.output_tools[0] if params and params.output_tools else None
        schema = tool.parameters_json_schema if tool is not None else None
        search = bool(params and params.native_tools)
        effort = self.effort() if callable(self.effort) else self.effort
        key = hashlib.sha256(json.dumps([self._name, effort, instructions, prompt, schema, search, self.salt],
                                        sort_keys=True).encode()).hexdigest()
        began = time.monotonic()
        got, cached = self._cached(key), True
        if got is None:
            cached = False
            if self._gate is None:
                self._gate = asyncio.Semaphore(AT_ONCE)
            async with self._gate:
                got = await self._call(instructions, prompt, schema, search, effort)
            self._keep(key, got)
        usage = got.get("usage") or {}
        # the CLI's search runs on a small model of its own, counted under that model's usage
        searches = int((usage.get("server_tool_use") or {}).get("web_search_requests") or 0) + sum(
            int(m.get("webSearchRequests") or 0) for m in (got.get("modelUsage") or {}).values())
        answer = got.get("structured_output")
        parts: list = [NativeToolCallPart("web_search", {}) for _ in range(searches)]
        parts.append(ToolCallPart(tool.tool_name if hasattr(tool, "tool_name") else tool.name, answer)
                     if tool is not None else TextPart(got.get("result") or ""))
        sent = (usage.get("input_tokens") or 0) + (usage.get("cache_creation_input_tokens") or 0) \
            + (usage.get("cache_read_input_tokens") or 0)
        if self.record is not None:
            self.record({"model": self._name, "cached": cached, "seconds": round(time.monotonic() - began, 2),
                         "asked_seconds": round((got.get("duration_ms") or 0) / 1000, 1),
                         "instructions_chars": len(instructions), "prompt_chars": len(prompt),
                         "input_tokens": sent, "output_tokens": usage.get("output_tokens") or 0,
                         "searches": searches, "turns": got.get("num_turns"), "key": key[:12]})
        return ModelResponse(parts=parts, model_name=self._name,
                             usage=RequestUsage(input_tokens=sent, output_tokens=usage.get("output_tokens") or 0))

    def _cached(self, key: str) -> dict | None:
        if not self.cache:
            return None
        try:
            with open(os.path.join(self.cache, key + ".json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _keep(self, key: str, got: dict) -> None:
        if not self.cache:
            return
        os.makedirs(self.cache, exist_ok=True)
        tmp = os.path.join(self.cache, f".{key}.{os.getpid()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(got, f)
        os.replace(tmp, os.path.join(self.cache, key + ".json"))

    async def _call(self, instructions: str, prompt: str, schema: dict | None, search: bool,
                    effort: str | None = None) -> dict:
        why = ""
        for _ in range(TRIES):
            with tempfile.TemporaryDirectory() as tmp:   # an empty folder: the CLI reads no project's files
                system = os.path.join(tmp, "system.txt")
                with open(system, "w", encoding="utf-8") as f:
                    f.write(instructions or "Answer the request.")
                argv = ["claude", "-p", "--model", self._name, "--system-prompt-file", system,
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--no-session-persistence", "--output-format", "json"]
                argv += ["--tools", "WebSearch", "--allowedTools", "WebSearch"] if search else ["--tools", ""]
                if effort:
                    argv += ["--effort", effort]
                if schema is not None:
                    argv += ["--json-schema", json.dumps(schema)]
                proc = await asyncio.create_subprocess_exec(
                    *argv, cwd=tmp, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE)
                try:
                    out, err = await asyncio.wait_for(proc.communicate(prompt.encode()), SECONDS)
                except asyncio.TimeoutError:
                    proc.kill()
                    why = "timed out"
                    continue
            try:
                got = json.loads(out.decode())
            except ValueError:
                why = (err.decode() or out.decode())[:300]
                continue
            if got.get("is_error") or (schema is not None and not isinstance(got.get("structured_output"), dict)):
                why = str(got.get("result"))[:300]
                continue
            return got
        raise RuntimeError(f"claude -p gave no answer: {why}")
