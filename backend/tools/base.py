"""Provider-neutral tool contracts and the structured result envelope."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


ParametersT = TypeVar("ParametersT", bound=BaseModel)


@dataclass(frozen=True)
class ToolDefinition(Generic[ParametersT]):
    name: str
    description: str
    parameters: type[ParametersT]
    risk: RiskLevel
    handler: Any
    path_fields: tuple[str, ...] = ()
    path_guard: Any | None = None
    requires_confirmation: bool | None = None
    timeout_seconds: float = 60
    retry_policy: int | None = None

    def to_gemini_tool(self) -> dict[str, Any]:
        """Return the Interactions API function declaration shape."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.model_json_schema(),
        }


@dataclass(frozen=True)
class ToolError:
    type: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class ToolResult:
    success: bool
    data: Any = None
    error: ToolError | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": None
            if self.error is None
            else {
                "type": self.error.type,
                "message": self.error.message,
                "retryable": self.error.retryable,
            },
            "metadata": self.metadata,
        }
