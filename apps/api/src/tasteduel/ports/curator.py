"""Private bounded model/tool protocol; never a browser or provider payload schema."""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    calls: tuple[ToolCall, ...]
    input_tokens: int = 0
    output_tokens: int = 0
    # Opaque SDK function-call parts/signatures, process-local only; never audit/log them.
    continuation: object | None = None
    usage_complete: bool = True


class ModelUnavailable(Exception):
    """Safe classification only. Never include SDK exceptions or response bodies."""


class CuratorModel(Protocol):
    model_version: str

    async def decide(
        self,
        messages: tuple[dict, ...],
        available_tools: tuple[dict, ...],
        *,
        timeout_seconds: float,
    ) -> ModelTurn: ...
