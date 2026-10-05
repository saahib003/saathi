"""Scripted fake used by deterministic tests and later agent tests."""

from collections.abc import Iterable

from backend.llm.client import LLMClient
from backend.llm.schemas import LLMRequest, LLMResponse


class FakeLLMClient(LLMClient):
    """Return scripted responses without network access."""

    def __init__(self, responses: Iterable[LLMResponse]) -> None:
        self._responses = iter(responses)
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        try:
            return next(self._responses)
        except StopIteration as exc:
            raise RuntimeError("FakeLLMClient has no scripted response left") from exc

