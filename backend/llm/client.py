"""The interface the agent loop uses instead of importing a provider SDK."""

from abc import ABC, abstractmethod

from backend.llm.schemas import LLMRequest, LLMResponse


class LLMClient(ABC):
    """Provider-neutral asynchronous language-model interface."""

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate either a final answer or one or more tool calls."""

