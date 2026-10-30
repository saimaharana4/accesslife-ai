"""Exercise installed SDK types with a fake transport; never invoke Vertex/ADC."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from google.genai import types
import pytest

from tasteduel.adapters import vertex_curator
from tasteduel.adapters.vertex_curator import VertexCuratorModel
from tasteduel.agents.curator_tools import tool_schemas
from tasteduel.ports.curator import ModelUnavailable


class SyntheticGenAI:
    def __init__(self, response=None, *, error=None, delay=0):
        self.requests = []
        self.response = response
        self.error = error
        self.delay = delay
        self.cancelled = False
        self.closed = False
        self.aio = SimpleNamespace(models=self, aclose=self.close)

    async def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.error:
            raise self.error
        return self.response

    async def close(self):
        self.closed = True


def function_response(name="fetch_ranked", arguments=None):
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part.from_function_call(
                            name=name,
                            args=arguments or {"target_domain": "movie", "limit": 20},
                        ),
                    ],
                )
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=53,
            candidates_token_count=17,
            thoughts_token_count=9,
        ),
    )


MESSAGES = ({"role": "user", "data": {"confirmed_seed": {"id": "synthetic-known-id", "domain": "artist"}}},)
TOOLS = tool_schemas(("movie",))


async def test_installed_sdk_builds_native_manual_tool_call_configuration():
    transport = SyntheticGenAI(function_response())
    model = VertexCuratorModel(project="synthetic-project-no-api", client=transport)
    turn = await model.decide(MESSAGES, TOOLS, timeout_seconds=1)
    assert len(transport.requests) == 1
    request = transport.requests[0]
    assert request["model"] == vertex_curator.MODEL
    config = request["config"]
    assert config.automatic_function_calling.disable is True
    assert config.tool_config.function_calling_config.mode.value == "ANY"
    assert set(config.tool_config.function_calling_config.allowed_function_names) == {
        tool["name"] for tool in TOOLS
    }
    assert config.candidate_count == 1 and config.temperature == 0
    assert config.max_output_tokens == 512
    assert config.thinking_config.include_thoughts is False
    assert config.thinking_config.thinking_level.value == "MINIMAL"
    assert turn.calls[0].name == "fetch_ranked"
    assert turn.calls[0].arguments == {"target_domain": "movie", "limit": 20}
    assert turn.input_tokens == 53
    assert turn.output_tokens == 26  # Billable thinking tokens count without thought text.


def test_vertex_construction_uses_explicit_adc_iam_with_bounded_http_retries(monkeypatch):
    import google.auth

    credential = object()
    adc = Mock(return_value=(credential, "synthetic-project"))
    constructor = Mock(return_value=SyntheticGenAI())
    monkeypatch.setattr(google.auth, "default", adc)
    monkeypatch.setattr(vertex_curator.genai, "Client", constructor)
    monkeypatch.setenv("GOOGLE_API_KEY", "synthetic-poison-key-not-a-credential")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-poison-key-not-a-credential")
    VertexCuratorModel(project="synthetic-project")
    assert adc.call_args.kwargs == {"scopes": ["https://www.googleapis.com/auth/cloud-platform"]}
    arguments = constructor.call_args.kwargs
    assert arguments["vertexai"] is True
    assert arguments["credentials"] is credential
    assert arguments["location"] == vertex_curator.LOCATION == "global"
    assert arguments["project"] == "synthetic-project"
    assert "api_key" not in arguments
    assert arguments["http_options"].retry_options.attempts == 1
    assert arguments["http_options"].timeout == 8000
    assert arguments["http_options"].api_version == "v1"


async def test_native_model_continuation_and_function_response_preserve_protocol_without_prose():
    transport = SyntheticGenAI(function_response())
    model = VertexCuratorModel(project="synthetic-project", client=transport)
    first = await model.decide(MESSAGES, TOOLS, timeout_seconds=1)
    messages = MESSAGES + (
        {"role": "model", "continuation": first.continuation},
        {
            "role": "tool",
            "name": "fetch_ranked",
            "data": {"snapshot_id": "synthetic-handle", "status": "ready"},
        },
    )
    await model.decide(messages, TOOLS, timeout_seconds=1)
    contents = transport.requests[1]["contents"]
    assert [content.role for content in contents] == ["user", "model", "user"]
    assert contents[1].parts[0].function_call.name == "fetch_ranked"
    response = contents[2].parts[0].function_response
    assert response.name == "fetch_ranked"
    assert response.response == {"snapshot_id": "synthetic-handle", "status": "ready"}


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan")])
async def test_invalid_deadline_never_dispatches_model_request(seconds):
    transport = SyntheticGenAI(function_response())
    model = VertexCuratorModel(project="synthetic-project", client=transport)
    with pytest.raises(ModelUnavailable):
        await model.decide(MESSAGES, TOOLS, timeout_seconds=seconds)
    assert not transport.requests


async def test_sdk_deadline_cancels_request_and_suppresses_response_details():
    transport = SyntheticGenAI(function_response(), delay=0.2)
    model = VertexCuratorModel(project="synthetic-project", client=transport)
    with pytest.raises(ModelUnavailable, match="VERTEX_UNAVAILABLE"):
        await model.decide(MESSAGES, TOOLS, timeout_seconds=0.01)
    assert transport.cancelled and len(transport.requests) == 1


async def test_cancelled_sdk_call_remains_cancellation_instead_of_provider_fallback():
    transport = SyntheticGenAI(function_response(), delay=0.2)
    model = VertexCuratorModel(project="synthetic-project", client=transport)
    task = asyncio.create_task(model.decide(MESSAGES, TOOLS, timeout_seconds=1))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.cancelled


async def test_sdk_error_is_redacted_and_has_no_response_exception_chain():
    transport = SyntheticGenAI(error=RuntimeError("synthetic-private-response-or-key-marker"))
    model = VertexCuratorModel(project="synthetic-project", client=transport)
    with pytest.raises(ModelUnavailable) as raised:
        await model.decide(MESSAGES, TOOLS, timeout_seconds=1)
    assert "synthetic-private" not in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


async def test_oversized_input_fails_before_model_dispatch_and_client_can_close():
    transport = SyntheticGenAI(function_response())
    model = VertexCuratorModel(project="synthetic-project", client=transport)
    messages = ({"role": "user", "data": {"synthetic": "a" * 10001}},)
    with pytest.raises(ModelUnavailable, match="VERTEX_INPUT_BOUND"):
        await model.decide(messages, TOOLS, timeout_seconds=1)
    assert not transport.requests
    await model.aclose()
    assert transport.closed
