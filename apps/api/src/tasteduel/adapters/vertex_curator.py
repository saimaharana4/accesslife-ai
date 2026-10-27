"""Google Gen AI native function calls, Vertex IAM only, no automatic tool execution."""

from __future__ import annotations

import asyncio
import json
import math

from google import genai
from google.genai import types

from tasteduel.agents.curator_tools import SYSTEM
from tasteduel.ports.curator import ModelTurn, ModelUnavailable, ToolCall

MODEL = "gemini-3.1-flash-lite"
LOCATION = "global"
SDK_VERSION = "2.33.0"
MAX_OUTPUT_TOKENS = 512


class VertexCuratorModel:
    model_version = MODEL

    def __init__(self, *, project: str, client=None, daily_budget=None):
        if not isinstance(project, str) or not project or len(project) > 100:
            raise ValueError("A Vertex project is required")
        if client is None:
            import google.auth

            # Explicit credentials select IAM/ADC, never an ambient Gemini API key.
            credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            client = genai.Client(
                vertexai=True,
                project=project,
                location=LOCATION,
                credentials=credentials,
                http_options=types.HttpOptions(
                    api_version="v1",
                    timeout=8000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        self.client = client
        self.daily_budget = daily_budget

    @staticmethod
    def input_token_upper_bound(messages, available_tools):
        # Conservative byte admission includes opaque SDK signatures transiently.
        # This representation is never persisted or logged.
        safe = [
            {key: value for key, value in message.items() if key != "continuation"} for message in messages
        ]
        continuation_bytes = sum(
            len(message["continuation"].model_dump_json(exclude_none=True).encode())
            for message in messages
            if message.get("continuation") is not None
        )
        return (
            len(json.dumps([SYSTEM, safe, available_tools], ensure_ascii=False).encode())
            + continuation_bytes
            + 512
        )

    async def decide(self, messages, available_tools, *, timeout_seconds):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ModelUnavailable("VERTEX_DEADLINE")
        input_bound = self.input_token_upper_bound(messages, available_tools)
        if input_bound > 10000:
            raise ModelUnavailable("VERTEX_INPUT_BOUND")
        if self.daily_budget is not None:
            await self.daily_budget.admit(input_bound + MAX_OUTPUT_TOKENS)
        contents = []
        for message in messages:
            if message["role"] == "model":
                contents.append(message["continuation"])
            elif message["role"] == "tool":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_function_response(name=message["name"], response=message["data"])
                        ],
                    )
                )
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=json.dumps(message["data"], sort_keys=True))],
                    )
                )
        declarations = [types.FunctionDeclaration(**item) for item in available_tools]
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0,
            candidate_count=1,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL", include_thoughts=False),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=[item["name"] for item in available_tools]
                )
            ),
            tools=[types.Tool(function_declarations=declarations)],
        )
        try:
            async with asyncio.timeout(min(timeout_seconds, 8)):
                response = await self.client.aio.models.generate_content(
                    model=MODEL, contents=contents, config=config
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            # No SDK exception strings, payloads or credential-bearing HTTP details escape.
            raise ModelUnavailable("VERTEX_UNAVAILABLE") from None
        candidates = response.candidates or []
        parts = candidates[0].content.parts if candidates and candidates[0].content else []
        # Reconstruct allowlisted fields; malformed mixed text/function parts must
        # not retain hidden thought text or other model-returned content.
        function_parts = tuple(
            types.Part(function_call=part.function_call, thought_signature=part.thought_signature)
            for part in (parts or [])
            if part.function_call is not None
        )
        calls = tuple(ToolCall(part.function_call.name, part.function_call.args) for part in function_parts)
        usage = response.usage_metadata
        # Include thinking tokens in cost accounting, while never requesting/retaining thought text.
        output = ((usage.candidates_token_count or 0) + (usage.thoughts_token_count or 0)) if usage else 0
        input_tokens = usage.prompt_token_count or 0 if usage else 0
        return ModelTurn(
            calls,
            input_tokens,
            output,
            types.Content(role="model", parts=list(function_parts)) if function_parts else None,
            bool(
                usage is not None
                and usage.prompt_token_count is not None
                and usage.candidates_token_count is not None
            ),
        )

    async def aclose(self):
        await self.client.aio.aclose()
