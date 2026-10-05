"""Explicit local fallback when Gemini configuration is absent."""

from backend.llm.client import LLMClient
from backend.llm.errors import LLMConfigurationError
from backend.llm.schemas import LLMRequest, LLMResponse


class UnavailableLLMClient(LLMClient):
    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise LLMConfigurationError("Configure GEMINI_API_KEY and GEMINI_MODEL before starting an agent task")

