"""SDK response grounding/privacy; every response is locally fabricated."""

from types import SimpleNamespace

import pytest
from google.genai import types

from tasteduel.adapters.vertex_curator import VertexCuratorModel
from tasteduel.agents.curator_tools import tool_schemas


class ResponseClient:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self.generate))

    async def generate(self, **arguments):
        self.requests.append(arguments)
        return self.response


def response(parts, usage=None):
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=types.Content(role="model", parts=parts))],
        usage_metadata=usage,
    )


async def test_hidden_thought_and_unstructured_prose_do_not_become_tool_or_continuation():
    marker = "SYNTHETIC_PRIVATE_REASONING_NEVER_TO_BE_RECORDED"
    function = types.Part(
        function_call=types.FunctionCall(name="fetch_ranked", args={"target_domain": "movie", "limit": 20}),
        thought_signature=b"opaque-native-signature",
    )
    client = ResponseClient(
        response(
            [
                types.Part(text=marker, thought=True),
                types.Part(text="Invented cultural causation must not become a reveal."),
                function,
            ],
            SimpleNamespace(prompt_token_count=50, candidates_token_count=20, thoughts_token_count=7),
        )
    )
    model = VertexCuratorModel(project="synthetic-project", client=client)
    result = await model.decide(
        ({"role": "user", "data": {"confirmed_seed": {"domain": "artist"}}},),
        tool_schemas(("movie",)),
        timeout_seconds=1,
    )
    assert len(result.calls) == 1
    assert result.calls[0].name == "fetch_ranked"
    assert result.output_tokens == 27  # Billed hidden tokens count without retaining their text.
    assert result.continuation.parts == [function]
    assert result.continuation.parts[0].thought_signature == b"opaque-native-signature"
    assert marker not in str(result)


async def test_prose_only_is_an_empty_tool_turn_and_cannot_become_a_reveal():
    marker = "SYNTHETIC_UNGROUNDED_PSYCHOLOGICAL_STORY"
    client = ResponseClient(response([types.Part(text=marker)]))
    model = VertexCuratorModel(project="synthetic-project", client=client)
    result = await model.decide(
        ({"role": "user", "data": {"confirmed_seed": {"domain": "artist"}}},),
        tool_schemas(("movie",)),
        timeout_seconds=1,
    )
    assert result.calls == ()
    assert result.continuation is None
    assert marker not in str(result)


async def test_mixed_function_part_cannot_smuggle_thought_text_into_private_continuation():
    marker = "SYNTHETIC_THOUGHT_IN_MALFORMED_MIXED_PART"
    mixed = types.Part(
        text=marker,
        thought=True,
        function_call=types.FunctionCall(name="inspect_seed", args={}),
        thought_signature=b"opaque-signature-only",
    )
    client = ResponseClient(response([mixed]))
    model = VertexCuratorModel(project="synthetic-project", client=client)
    result = await model.decide(
        ({"role": "user", "data": {}},),
        tool_schemas(("movie",)),
        timeout_seconds=1,
    )
    assert len(result.calls) == 1
    assert marker not in str(result)
    assert result.continuation.parts[0].text is None
    assert result.continuation.parts[0].thought_signature == b"opaque-signature-only"


@pytest.mark.parametrize(
    "usage",
    [
        None,
        SimpleNamespace(prompt_token_count=None, candidates_token_count=3, thoughts_token_count=None),
        SimpleNamespace(prompt_token_count=10, candidates_token_count=None, thoughts_token_count=None),
        SimpleNamespace(prompt_token_count=None, candidates_token_count=None, thoughts_token_count=None),
    ],
)
async def test_absent_or_partial_usage_is_never_presented_as_complete_measured_usage(usage):
    client = ResponseClient(
        response(
            [
                types.Part(function_call=types.FunctionCall(name="inspect_seed", args={})),
            ],
            usage,
        )
    )
    model = VertexCuratorModel(project="synthetic-project", client=client)
    result = await model.decide(
        ({"role": "user", "data": {}},),
        tool_schemas(("movie",)),
        timeout_seconds=1,
    )
    assert result.usage_complete is False


async def test_reported_zero_usage_can_still_be_complete_without_using_truthiness():
    usage = SimpleNamespace(prompt_token_count=0, candidates_token_count=0, thoughts_token_count=0)
    client = ResponseClient(
        response(
            [
                types.Part(function_call=types.FunctionCall(name="inspect_seed", args={})),
            ],
            usage,
        )
    )
    model = VertexCuratorModel(project="synthetic-project", client=client)
    result = await model.decide(
        ({"role": "user", "data": {}},),
        tool_schemas(("movie",)),
        timeout_seconds=1,
    )
    assert result.usage_complete is True
    assert result.input_tokens == result.output_tokens == 0
