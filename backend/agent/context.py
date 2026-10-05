"""Build bounded, application-owned model context for each agent step."""

from typing import Any

from backend.agent.task_manager import Task
from backend.llm.schemas import LLMRequest
from backend.memory.store import MemoryStore
from backend.tools.registry import ToolRegistry


class ContextManager:
    def __init__(self, memories: MemoryStore, registry: ToolRegistry, max_tool_chars: int = 6000, max_messages: int = 12) -> None:
        self.memories = memories
        self.registry = registry
        self.max_tool_chars = max_tool_chars
        self.max_messages = max_messages

    def build(self, task: Task, messages: list[dict[str, Any]]) -> LLMRequest:
        recent = messages[-self.max_messages:]
        bounded: list[dict[str, Any]] = []
        for message in recent:
            item = dict(message)
            if item.get("role") == "tool" and isinstance(item.get("content"), str):
                item["content"] = item["content"][: self.max_tool_chars]
            bounded.append(item)
        relevant = self.memories.relevant(task.user_message)
        if relevant:
            bounded.insert(0, {"role": "system", "content": "Relevant user-created memory:\n" + "\n".join(f"- {item['content']}" for item in relevant)})
        bounded.insert(0, {"role": "system", "content": f"Task id: {task.id}. Use only the provided context and tools. Do not invent completed actions."})
        return LLMRequest(input=bounded, system_instruction="You are a careful local laptop assistant. Persistent memory is explicit user-created information only.", tools=self.registry.gemini_tools())
