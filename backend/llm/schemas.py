"""Provider-neutral request and response types."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMRequest:
    """A complete stateless model request assembled by the future ContextManager."""

    input: str | list[dict[str, Any]]
    system_instruction: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LLMResponse:
    is_final: bool
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider_response_id: str | None = None

