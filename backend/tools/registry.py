"""Tool registration and schema export."""

from backend.tools.base import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def gemini_tools(self) -> list[dict]:
        return [definition.to_gemini_tool() for definition in self._tools.values()]

